"""Offline signal-policy replay. No server requests or device access."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from statistics import mean
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings
from app.schemas.api import UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter
from app.services.uwb_quality_service import quality_policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-m", type=float)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    counts = {mode: Counter() for mode in ("observe", "enforce")}
    errors = defaultdict(list)
    frames = 0
    with TemporaryDirectory(prefix="uwb-quality-", dir=args.output.parent) as folder:
        processors = {mode: DistanceFilter(Settings(uwb_quality_mode=mode, uwb_filter_state_path=str(Path(folder)/f"{mode}.db")), {})
                      for mode in counts}
        with args.capture.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as target:
            for line in source:
                row = json.loads(line)
                if row.get("event") not in ("device_frame", "usb_cycle") or not row.get("firmware"):
                    continue
                p = UwbDistancesIn.model_validate(row["firmware"])
                now = datetime.fromisoformat(row["received_at"].replace("Z", "+00:00")).timestamp()
                frames += 1
                for mode, processor in processors.items():
                    result = processor.process(p, now)
                    counts[mode]["frames_accepted" if result["accepted"] else "frames_rejected"] += 1
                    for record in result["anchor_processing"]:
                        if record["raw_distance_m"] is None:
                            continue
                        decision = record["signal_quality"]
                        counts[mode][decision["classification"]] += 1
                        counts[mode]["action_"+decision["applied_action"]] += 1
                        if mode == "observe" and args.reference_m is not None:
                            errors[decision["classification"]].append(record["raw_distance_m"]-args.reference_m)
                    target.write(json.dumps(dict(mode=mode, measurement_id=p.measurement_id, processing=result), ensure_ascii=False)+"\n")
        summary = dict(source=str(args.capture.resolve()), source_sha256=hashlib.sha256(args.capture.read_bytes()).hexdigest(),
                       frames=frames, thresholds=quality_policy(Settings()), counts=counts,
                       raw_error_groups={group: dict(n=len(values), bias_m=mean(values), mae_m=mean(abs(v) for v in values),
                                                    rmse_m=mean(v*v for v in values)**.5) for group, values in errors.items()},
                       limitations=["No LOS/body/obstacle ground-truth label: no accuracy or confusion matrix",
                                    "Reference distance is user supplied; one anchor cannot validate XY position",
                                    "Calibration offsets disabled in offline replay only; production calibration unchanged"])
        args.output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
