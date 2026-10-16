"""Finite USB-only capture for before/after firmware verification. Never posts HTTP."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean, median, pstdev
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import serial
from uwb_live_bridge import parse_tag_line
from legacy_uwb_processing import DistanceProcessor, load_calibration, DEFAULT_CALIBRATION_FILE
from backend.app.services.uwb_log_service import BoundedJsonlLog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM6")
    parser.add_argument("--baud", type=int, default=460800)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", default="post_flash")
    parser.add_argument("--reference-m", type=float)
    parser.add_argument("--reference-exact", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION_FILE)
    parser.add_argument("--legacy-calibration", action="store_true", help="과거 비교 전용: 저장된 앵커 보정값 적용 (기본 비활성)")
    args = parser.parse_args()
    log = BoundedJsonlLog(args.output)
    calibration = load_calibration(args.calibration, disabled=not args.legacy_calibration)
    processor = DistanceProcessor(calibration)
    log.append({"event": "capture_start", "phase": args.phase, "port": args.port, "baud": args.baud,
                "started_at": datetime.now(timezone.utc).isoformat(), "reference_distance_m": args.reference_m,
                "reference_is_exact": args.reference_exact, "calibration": calibration,
                "calibration_file": str(args.calibration.resolve()),
                "legacy_calibration_enabled": args.legacy_calibration,
                "history_size": 5, "anchor_hold_seconds": 2.5, "server_transmission": False})
    frames = 0
    parse_errors = 0
    diagnostic_states = Counter()
    range_states = Counter()
    diagnostic_values = defaultdict(list)
    samples = defaultdict(list)
    sessions = set()
    versions = set()
    sequences = []
    cycle_ids = []
    maximum_dropped = 0
    last_report = time.monotonic()
    with serial.Serial(args.port, args.baud, timeout=0.5) as port:
        if args.reset:
            port.dtr = False
            port.rts = True
            time.sleep(0.12)
            port.rts = False
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            data = port.readline(16384)
            if not data:
                continue
            line = data.decode("utf-8", errors="replace").strip()
            received_at = datetime.now(timezone.utc).isoformat()
            frame = parse_tag_line(line)
            if frame is None:
                parse_errors += int(line.startswith("{"))
                log.append({"event": "serial_line", "received_at": received_at, "line": line})
            else:
                frames += 1
                processed = processor.process(frame)
                log.append({"event": "device_frame", "phase": args.phase, "received_at": received_at,
                            "firmware": frame.payload, "legacy_line": line if frame.payload is None else None,
                            "processed_measurements": processed})
                if frame.payload:
                    sessions.add(frame.payload["session_id"])
                    versions.add(frame.payload.get("firmware_version"))
                    sequences.append(frame.sequence)
                    cycle_ids.append(frame.payload["cycle_id"])
                    maximum_dropped = max(maximum_dropped, frame.payload.get("firmware_dropped_cycles", 0))
                    for item in frame.payload.get("observations", []):
                        range_states[f"{item['anchor_id']}:{item['status']}"] += 1
                        diagnostic_states[f"{item['anchor_id']}:{item['diagnostics']['status']}"] += 1
                        if item["status"] == "valid" and item["raw_distance_m"] is not None:
                            samples[item["anchor_id"]].append(item["raw_distance_m"])
                        for field in ("rx_power_dbm", "first_path_power_dbm", "power_difference_db",
                                      "peak_minus_first_path_samples", "clock_offset_ppm"):
                            value = item["diagnostics"].get(field)
                            if value is not None:
                                diagnostic_values[f"{item['anchor_id']}:{field}"].append(value)
                        capture_us = item["diagnostics"].get("raw", {}).get("capture_us")
                        if capture_us is not None:
                            diagnostic_values[f"{item['anchor_id']}:capture_us"].append(capture_us)
                else:
                    for cm, number in zip(frame.ranges_cm, frame.anchor_numbers):
                        if cm > 0 and number >= 0:
                            samples[f"anchor-{number+1:03d}"].append(cm / 100)
            if time.monotonic() - last_report >= 10:
                print(f"captured_frames={frames} json_parse_errors={parse_errors}", flush=True)
                last_report = time.monotonic()
    summary = {"event": "capture_end", "phase": args.phase, "frames": frames,
               "json_parse_errors": parse_errors, "sessions": sorted(sessions), "versions": sorted(v for v in versions if v),
               "diagnostic_states": dict(diagnostic_states), "max_firmware_dropped_cycles": maximum_dropped,
               "range_states": dict(range_states),
               "sequence_wraps": sum(b < a for a, b in zip(sequences, sequences[1:])),
               "cycle_ids_increasing": all(b > a for a, b in zip(cycle_ids, cycle_ids[1:])) if len(cycle_ids)>1 else None,
               "reference_distance_m": args.reference_m, "reference_is_exact": args.reference_exact,
               "anchors": {}}
    for anchor, values in samples.items():
        summary["anchors"][anchor] = {"n": len(values), "min_m": min(values), "max_m": max(values),
                                       "mean_m": mean(values), "median_m": median(values), "std_m": pstdev(values)}
    summary["diagnostic_values"] = {field: {"n": len(values), "min": min(values), "median": median(values), "max": max(values)}
                                     for field, values in diagnostic_values.items()}
    log.append(summary)
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
