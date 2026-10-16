"""Replay retained firmware JSON through the real common service, without HTTP."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from statistics import mean, pstdev
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings
from app.schemas.api import UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter


def metrics(values, reference):
    if not values:
        return {"n": 0}
    out = dict(n=len(values), mean_m=mean(values), std_m=pstdev(values), min_m=min(values), max_m=max(values))
    if reference is not None:
        errors = [v-reference for v in values]
        out.update(bias_m=mean(errors), mae_m=mean(abs(v) for v in errors), rmse_m=mean(v*v for v in errors)**.5)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-m", type=float)
    parser.add_argument("--no-calibration", action="store_true", help="Offline analysis only: isolate filtering from saved calibration")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="uwb-replay-", dir=args.output.parent) as temporary:
        processors = {}
        for name, enabled, window in (("off", False, 5), ("n3", True, 3), ("n5", True, 5)):
            cfg = Settings(uwb_filter_state_path=str(Path(temporary)/f"{name}.sqlite3"),
                           uwb_median_enabled=enabled, uwb_median_window=window)
            processors[name] = DistanceFilter(cfg, offsets={} if args.no_calibration else None)
        values = {name: {} for name in processors}
        counts = {name: {"accepted": 0, "rejected": 0} for name in processors}
        frames = 0
        with args.capture.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as target:
            for line in source:
                row = json.loads(line)
                if row.get("event") not in ("device_frame", "usb_cycle") or not row.get("firmware"):
                    continue
                payload = UwbDistancesIn.model_validate(row["firmware"])
                now = datetime.fromisoformat(row["received_at"].replace("Z", "+00:00")).timestamp()
                frames += 1
                for name, processor in processors.items():
                    result = processor.process(payload, now)
                    counts[name]["accepted" if result["accepted"] else "rejected"] += 1
                    for item in result["measurements"]:
                        values[name].setdefault(item["anchor_id"], []).append(item["distance_m"])
                    target.write(json.dumps({"mode": name, "measurement_id": payload.measurement_id,
                                             "received_at": row["received_at"], "processing": result}, ensure_ascii=False)+"\n")
        summary = {"source": str(args.capture.resolve()), "frames": frames, "reference_m": args.reference_m,
                   "calibration": "disabled_for_offline_comparison" if args.no_calibration else "server_file" if cfg.uwb_calibration_enabled else "disabled_by_server_configuration",
                   "counts": counts, "statistics": {name: {anchor: metrics(v, args.reference_m) for anchor, v in anchors.items()}
                                                     for name, anchors in values.items()},
                   "limitation": "Offline single capture replay; not a new hardware or position validation"}
        args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
