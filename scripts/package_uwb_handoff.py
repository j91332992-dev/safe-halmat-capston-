"""Export only two paired UWB comparisons for team sharing; never copy flash/credentials/DB.

Raw distances, timing and diagnostics are preserved. Hardware/network identifiers
and workstation paths are replaced. Private original files remain unchanged.
"""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, median, pstdev
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uwb_live_bridge import parse_tag_line

CAPTURES = [
    ("distance_2m_r2", "uwb-exact-2m-20261015-r2.jsonl"),
    ("position_center_r2", "uwb-position-center-server-20261015-r2.jsonl"),
]


def sanitize(value, key=""):
    if isinstance(value, dict):
        return {k:sanitize(v,k) for k,v in value.items()}
    if isinstance(value,list):
        return [sanitize(v,key) for v in value]
    if not isinstance(value,str):
        return value
    if any(token in key.lower() for token in ("password", "ssid", "api_key", "access_token")):
        return "<REDACTED>"
    if key in ("port", "usb_serial"):
        return "<USB_PORT>" if key=="port" else "<USB_SERIAL>"
    # Preserve reboot number/nonces and every link to a measurement. The
    # replacement remains valid for the server's 12-hex session prefix schema.
    value=re.sub(r"\b[0-9a-fA-F]{12}-(\d+)-([0-9a-fA-F]{32})",r"c0dec0de0001-\1-\2",value)
    value=re.sub(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b","<TAG_MAC>",value)
    value=re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b","<LOCAL_IP>",value)
    value=value.replace("02E4F879","<USB_SERIAL>")
    if re.search(r"[A-Za-z]:[\\/]",value):
        return "<LOCAL_PATH>/"+re.split(r"[\\/]",value)[-1]
    return value


def write_csv(path, rows, columns):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:row.get(k) for k in columns})


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def export(source, out):
    """Publish exactly two paired comparisons, never a directory-wide log dump."""
    from tempfile import TemporaryDirectory
    from app.config import Settings
    from app.schemas.api import UwbDistancesIn
    from app.services.uwb_distance_filter import DistanceFilter

    out.mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(exist_ok=True)
    distance = [r for r in load_rows(source / CAPTURES[0][1])
                if r.get("event") == "device_frame" and r.get("firmware")]
    actual = load_rows(source / CAPTURES[1][1])
    compared = load_rows(source / "uwb-position-center-comparison-20261015-r2.jsonl")
    if len(actual) != len(compared):
        raise ValueError("Position comparisons must have identical frame counts")
    datasets = {k: [] for k in ("distance_2m_before", "distance_2m_after_median5", "position_p4", "position_modified")}
    with TemporaryDirectory(prefix="uwb-selected-") as temporary:
        cfg = Settings(uwb_filter_state_path=str(Path(temporary)/"state.db"),
                       uwb_calibration_enabled=False, uwb_median_enabled=True,
                       uwb_median_window=5, uwb_quality_mode="observe")
        processor = DistanceFilter(cfg, offsets={})
        for row in distance:
            wire = row["firmware"]
            result = processor.process(UwbDistancesIn.model_validate(wire),
                datetime.fromisoformat(row["received_at"].replace("Z", "+00:00")).timestamp())
            if not result["accepted"]:
                raise ValueError("Selected distance frame rejected: " + result["reason"])
            for item in result["measurements"]:
                common = dict(received_at_utc=row["received_at"], measurement_id=wire["measurement_id"],
                    session_id=wire["session_id"], cycle_id=wire["cycle_id"], sequence=wire["sequence"],
                    measured_uptime_us=wire["measured_uptime_us"], anchor_id=item["anchor_id"],
                    reference_m=2.0, raw_distance_m=item["raw_distance_m"],
                    calibration_enabled=False, quality_mode="observe")
                for key, value in [("distance_2m_before", item["raw_distance_m"]),
                                   ("distance_2m_after_median5", item["filtered_distance_m"])]:
                    datasets[key].append(sanitize(dict(**common, distance_m=value,
                        absolute_error_m=abs(value-2), sample_count=item["sample_count"] if "after" in key else 1,
                        sample_ages_seconds=json.dumps(item["sample_ages_seconds"] if "after" in key else [0]),
                        processing_reason=item["reason"] if "after" in key else "unfiltered_raw")))
    for row, trace in zip(actual, compared):
        wire = row["input"]
        if wire["measurement_id"] != trace["measurement_id"]:
            raise ValueError("Position comparison measurement ID mismatch")
        p4 = trace["comparisons"]["p4_original"]
        point = row["final_position"]
        candidate = row.get("candidate_position")
        for key, final, raw, solved, accepted, reason in [
            ("position_p4", p4["final"], p4["candidate"], p4["solved"], p4["accepted"], p4["reason"]),
            ("position_modified", [point["x"], point["y"]],
             [candidate["x"], candidate["y"]] if candidate else None,
             bool(candidate), row["pipeline"]["position_accepted"], row.get("position_check", {}).get("reason"))]:
            datasets[key].append(sanitize(dict(measurement_id=wire["measurement_id"],
                session_id=wire["session_id"], cycle_id=wire["cycle_id"], sequence=wire["sequence"],
                measured_uptime_us=wire["measured_uptime_us"], received_at_utc=row["server_received_at"],
                origin="historical_p4_replay" if key == "position_p4" else "actual_server_output",
                solved=solved, accepted=accepted, reason=reason, x_m=final[0], y_m=final[1],
                candidate_x_m=raw[0] if raw else None, candidate_y_m=raw[1] if raw else None,
                reference_x_m=1.0, reference_y_m=.5, reference_exact=False,
                approximate_reference_error_m=math.dist(final, [1, .5]))))
    summary = {}
    for name, rows in datasets.items():
        write_csv(out / (name + ".csv"), rows, list(rows[0]))
        if name.startswith("distance"):
            values = [r["distance_m"] for r in rows]
            summary[name] = dict(samples=len(rows), mean_m=mean(values), std_m=pstdev(values),
                mae_m=mean(abs(v-2) for v in values))
        else:
            xs, ys = [r["x_m"] for r in rows], [r["y_m"] for r in rows]
            summary[name] = dict(frames=len(rows), solved=sum(r["solved"] for r in rows),
                accepted=sum(r["accepted"] for r in rows), mean_x_m=mean(xs), mean_y_m=mean(ys),
                approximate_reference_mae_m=mean(r["approximate_reference_error_m"] for r in rows),
                scatter_m=math.sqrt(pstdev(xs)**2+pstdev(ys)**2))
    # Two selected measurement sources only. Discard obsolete capture-time
    # calibration/bridge processing from distance rows; keep the original wire.
    shared = [[dict(event=r["event"], received_at=r["received_at"], firmware=r["firmware"]) for r in distance], actual]
    sources = []
    for (_, filename), rows in zip(CAPTURES, shared):
        data = ("\n".join(json.dumps(sanitize(r), ensure_ascii=False, allow_nan=False) for r in rows)+"\n").encode()
        compressed = gzip.compress(data, mtime=0)
        path = out / "raw" / (filename + ".gz")
        path.write_bytes(compressed)
        sources.append(dict(filename=path.relative_to(out).as_posix(), rows=len(rows),
            original_sha256=digest((source/filename).read_bytes()), shared_sha256=digest(compressed)))
    (out/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps(dict(
        scope=list(datasets), sources=sources, p4_commit="722c9fd327997b8d4bdd59ae088928d9285eba40",
        private_p4_replay_trace_sha256=digest((source/"uwb-position-center-comparison-20261015-r2.jsonl").read_bytes()),
        transformations=["hardware identifiers and local paths redacted consistently",
                         "distance: firmware wire only; obsolete bridge processing omitted",
                         "position: original input, diagnostics and actual outputs preserved"],
        limitations=["Distance before/after is same-capture replay with calibration OFF; not separate firmware trials",
                     "P4 positions are historical numerical replay; modified positions are actual live output",
                     "2x1m geometry is experiment metadata only; no deployment map settings are included",
                     "Position reference is approximate, not surveyed ground truth"]), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return datasets


def main():
    sys.path.insert(0, str(ROOT/"backend"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT/"logs")
    parser.add_argument("--output", type=Path, default=ROOT/"docs/measurements/2026-10-15-comparison")
    args = parser.parse_args()
    export(args.source, args.output)


if __name__ == "__main__":
    main()
