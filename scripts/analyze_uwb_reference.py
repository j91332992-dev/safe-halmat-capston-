"""Analyze a capture against its explicitly supplied exact distance, in metres."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev


def percentile(values, quantile):
    values = sorted(values)
    location = (len(values) - 1) * quantile
    low, high = math.floor(location), math.ceil(location)
    return values[low] + (values[high] - values[low]) * (location - low)


def evaluate(values, reference):
    if not values:
        return {"n": 0}
    errors = [value - reference for value in values]
    absolute = [abs(value) for value in errors]
    return {"n": len(values), "mean_m": mean(values), "median_m": median(values),
            "std_m": pstdev(values), "min_m": min(values), "max_m": max(values),
            "bias_m": mean(errors), "mae_m": mean(absolute),
            "rmse_m": math.sqrt(mean([value * value for value in errors])),
            "p95_absolute_error_m": percentile(absolute, .95), "max_absolute_error_m": max(absolute),
            "within_5cm_fraction": sum(value <= .05 for value in absolute) / len(values),
            "within_10cm_fraction": sum(value <= .10 for value in absolute) / len(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--anchor", default="anchor-001")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.capture.read_text(encoding="utf-8").splitlines()]
    metadata = next(row for row in rows if row["event"] == "capture_start")
    if not metadata["reference_is_exact"]:
        raise ValueError("Capture reference was approximate: do not claim measured absolute accuracy")
    reference = metadata["reference_distance_m"]
    summary = next(row for row in reversed(rows) if row["event"] == "capture_end")
    series = {"raw": [], "legacy_cm": [], "existing_median_only": [], "existing_processed": []}
    records = []
    start = datetime.fromisoformat(metadata["started_at"])
    raw_blocks = {}
    for row in rows:
        if row["event"] != "device_frame":
            continue
        firmware = row["firmware"]
        observation = next(item for item in firmware["observations"] if item["anchor_id"] == args.anchor)
        processed = next((item for item in row["processed_measurements"] if item["anchor_id"] == args.anchor), None)
        elapsed = (datetime.fromisoformat(row["received_at"]) - start).total_seconds()
        raw = observation["raw_distance_m"] if observation["status"] == "valid" else None
        if raw is not None:
            series["raw"].append(raw)
            series["legacy_cm"].append(observation["legacy_range_cm"] / 100)
            raw_blocks.setdefault(int(elapsed // 30), []).append(raw)
        if processed is not None:
            series["existing_median_only"].append(processed["median_distance_m"])
            series["existing_processed"].append(processed["distance_m"])
        records.append({"elapsed_s": elapsed, "cycle_id": firmware["cycle_id"],
                        "sequence": firmware["sequence"], "raw_m": raw,
                        "median_m": processed["median_distance_m"] if processed else None,
                        "processed_m": processed["distance_m"] if processed else None,
                        "held": processed["held"] if processed else False,
                        "diagnostics": observation["diagnostics"]})
    result = {"source": str(args.capture.resolve()), "source_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
              "reference_m": reference, "reference_source": "user supplied exact distance", "anchor": args.anchor,
              "capture_summary": summary, "statistics": {name: evaluate(values, reference) for name, values in series.items()},
              "raw_30second_blocks": {str(block): evaluate(values, reference) for block, values in raw_blocks.items()}}
    output = args.capture.with_suffix(".accuracy.json")
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    stats = result["statistics"]
    lines = [f"# UWB 基準距離 {reference:.3f}m 測定結果".replace("基準距離", "기준 거리").replace("測定結果", "측정 결과"), "",
             "사용자가 정확히 맞췄다고 제공한 안테나 간 거리를 정답값으로 사용했다. PC에서 길이를 독립적으로 확인한 것은 아니다.",
             "태그 펌웨어·보정값을 변경하지 않고 USB만 수집했다. 앵커 한 대이므로 X/Y 위치 정확도는 평가하지 않는다.", "",
             "## 거리 및 오차", "", "| 지표 | 반올림 전 원시 거리 | 기존 5개 중앙값만 | 기존 중앙값 + 보정 |", "|---|---:|---:|---:|"]
    columns = [stats[key] for key in ("raw", "existing_median_only", "existing_processed")]
    for field, label, unit, multiplier, digits in (
            ("n", "표본 수", "", 1, 0), ("mean_m", "평균 거리", "m", 1, 4),
            ("median_m", "거리 중앙값", "m", 1, 4), ("std_m", "표준편차(흔들림)", "cm", 100, 2),
            ("bias_m", "평균 부호 오차", "cm", 100, 2), ("mae_m", "평균 절대 오차 MAE", "cm", 100, 2),
            ("rmse_m", "RMSE", "cm", 100, 2), ("p95_absolute_error_m", "절대 오차 95백분위", "cm", 100, 2),
            ("max_absolute_error_m", "최대 절대 오차", "cm", 100, 2)):
        values = [f"{value[field]*multiplier:.{digits}f} {unit}" if field in value else "자료 없음" for value in columns]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    lines += ["", f"기존 보정값: `{metadata['calibration'].get(args.anchor, 0):+.3f}m`. 중앙값 처리와 보정 효과를 분리했다.",
              "이 보정값은 이번 2m 데이터에 맞춰 새로 추정하거나 수정하지 않았다. 결과가 나빠져도 자동으로 보정값을 바꾸지 않는다.",
              "부호 오차는 측정값−2m이며 양수는 길게, 음수는 짧게 측정됐다는 뜻이다. 표준편차는 전체 관측값 기준이다.", "",
              "## 수집 상태", "", f"- 측정 회차: {summary['frames']}, JSON 파싱 오류: {summary['json_parse_errors']}.",
              f"- 펌웨어 누락 카운터 최대: {summary['max_firmware_dropped_cycles']}.",
              f"- 거리 상태: `{summary['range_states']}`.", f"- 진단 상태: `{summary['diagnostic_states']}`.",
              "- 단일 거리·단일 배치·단일 시간 구간의 관측 결과다. 다른 거리와 가림 조건까지 일반화하지 않는다.",
              "- 이전 '약 1.5m' 측정과는 실제 거리가 다르므로 펌웨어 전후 개선 비교로 해석하지 않는다.", "",
              "## 원시 거리의 시간 구간별 상태", "", "| 수집 시작 기준 구간 | n | 평균 m | 표준편차 cm | 평균 오차 cm |", "|---|---:|---:|---:|---:|"]
    for block, values in result["raw_30second_blocks"].items():
        number = int(block)
        lines.append(f"| {number*30}~{number*30+30}초 | {values['n']} | {values['mean_m']:.4f} | {values['std_m']*100:.2f} | {values['bias_m']*100:+.2f} |")
    lines += ["", "## 전체 측정표", "", "| 경과 초 | cycle | seq | 원시 m | 중앙값 m | 기존 보정 후 m | held | 진단 상태 | RX dBm | FP dBm |", "|---:|---:|---:|---:|---:|---:|---|---|---:|---:|"]
    def fmt(value, digits=4):
        return "누락" if value is None else f"{value:.{digits}f}"
    for row in records:
        d = row["diagnostics"]
        lines.append(f"| {row['elapsed_s']:.3f} | {row['cycle_id']} | {row['sequence']} | {fmt(row['raw_m'])} | {fmt(row['median_m'])} | {fmt(row['processed_m'])} | {row['held']} | {d['status']} | {fmt(d.get('rx_power_dbm'),2)} | {fmt(d.get('first_path_power_dbm'),2)} |")
    lines += ["", f"원본: `{args.capture.resolve()}`", f"재계산 통계: `{output.resolve()}`", "원본은 수정하지 않았다. 로그와 보고서는 현재 PC에만 저장했으며 커밋/푸시하지 않았다."]
    args.report.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps(result["statistics"], indent=2))


if __name__ == "__main__":
    main()
