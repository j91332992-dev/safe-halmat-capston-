"""Create human-readable before/after tables from existing logs, without changing them."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[1]


def stats(values):
    return dict(n=len(values), median_m=median(values), mean_m=mean(values), std_m=pstdev(values),
                min_m=min(values), max_m=max(values))


def read_capture(kind):
    path = ROOT / f"logs/uwb-{kind}-flash-20261015.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    start = datetime.fromisoformat(rows[0]["started_at"])
    records = []
    for row in rows:
        if row.get("event") != "device_frame":
            continue
        fw = row.get("firmware")
        diagnostic = {}
        if fw:
            observation = next(x for x in fw["observations"] if x["anchor_id"] == "anchor-001")
            distance = observation["raw_distance_m"] if observation["status"] == "valid" else None
            cm = observation["legacy_range_cm"] if observation["status"] == "valid" else None
            sequence, cycle = fw["sequence"], fw["cycle_id"]
            diagnostic = observation["diagnostics"]
        else:
            line = row["legacy_line"]
            raw = int(re.search(r"range:\(([^)]*)\)", line).group(1).split(",")[0])
            cm = raw if raw > 0 else None
            distance = cm / 100 if cm is not None else None
            sequence = int(re.search(r"seq:(\d+)", line).group(1))
            cycle = None
        processed = next((m["distance_m"] for m in row["processed_measurements"] if m["anchor_id"] == "anchor-001"), None)
        records.append(dict(sample=len(records)+1,
                            seconds=(datetime.fromisoformat(row["received_at"])-start).total_seconds(),
                            received_at=row["received_at"], sequence=sequence, cycle_id=cycle,
                            raw_m=distance, common_cm_m=cm/100 if cm is not None else None,
                            processed_m=processed, diagnostic=diagnostic))
    return path, records


def display(value, digits=3):
    return "누락" if value is None else f"{value:.{digits}f}"


def main():
    captures = {kind: read_capture(kind) for kind in ("before", "after")}
    results = {}
    for kind, (source, records) in captures.items():
        valid = [r for r in records if r["raw_m"] is not None]
        results[kind] = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                             frames=len(records), raw=stats([r["raw_m"] for r in valid]),
                             common_cm_all=stats([r["common_cm_m"] for r in valid]),
                             first_46_common_cm=stats([r["common_cm_m"] for r in valid[:46]]),
                             first_15s_common_cm=stats([r["common_cm_m"] for r in valid if r["seconds"] <= 15]),
                             processed=stats([r["processed_m"] for r in records if r["processed_m"] is not None]))
        title = "업데이트 전" if kind == "before" else "업데이트 후"
        table = [f"# {title} — 앵커 1 측정값 전체", "", f"원본: `{source.name}`", "",
                 "수집 시작부터의 경과 시간은 PC 수신 시각 기준이다. 유효하지 않은 값은 '누락'으로 표시한다.",
                 "보정·중앙값 결과는 기존 5개 중앙값 및 +0.48m 보정이며, 정답 거리로 검증한 값이 아니다.", "",
                 "| 회차 순번 | 경과 초 | seq | cycle_id | 원시 거리 m | 공통 cm 해상도 거리 m | 기존 처리 결과 m | 진단 상태 | RX dBm | FP dBm | 차이 dB |",
                 "|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|"]
        for r in records:
            d = r["diagnostic"]
            table.append(f"| {r['sample']} | {r['seconds']:.3f} | {r['sequence']} | {r['cycle_id'] if r['cycle_id'] is not None else '없음'} | "
                         f"{display(r['raw_m'],6)} | {display(r['common_cm_m'],2)} | {display(r['processed_m'])} | "
                         f"{d.get('status','없음')} | {display(d.get('rx_power_dbm'))} | {display(d.get('first_path_power_dbm'))} | {display(d.get('power_difference_db'))} |")
        (ROOT/f"logs/uwb-{kind}-readable-20261015.md").write_text("\n".join(table)+"\n", encoding="utf-8")
    (ROOT/"logs/uwb-before-after-comparison-20261015.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    b, a = results["before"], results["after"]
    report = ["# UWB 업데이트 전후 데이터 비교 — 2026-10-15", "",
              "**거리 정확도가 개선됐다는 근거는 아직 없다.** 이번 업데이트는 진단 로그 수집을 추가하고 최신 통합본의 clock offset 수정을 유지했다.",
              "새 NLOS 제외·속도 제한·새 거리 필터를 적용하지 않았다. 기준 거리는 사용자 제공 '약 1.5m'이며 정밀한 정답값이 아니다.", "",
              "## 전체 수집 결과", "", "| 항목 | 업데이트 전 | 업데이트 후 |", "|---|---:|---:|",
              "| 수집 설정 시간 | 15초 | 120초 |",
              f"| 기록 회차 / 유효 거리 | {b['frames']} / {b['raw']['n']} | {a['frames']} / {a['raw']['n']} |",
              f"| 원시 중앙값 | {b['raw']['median_m']:.6f} m | {a['raw']['median_m']:.6f} m |",
              f"| 원시 평균 | {b['raw']['mean_m']:.6f} m | {a['raw']['mean_m']:.6f} m |",
              f"| 원시 표준편차 | {b['raw']['std_m']*100:.2f} cm | {a['raw']['std_m']*100:.2f} cm |",
              f"| 원시 최소~최대 | {b['raw']['min_m']:.3f}~{b['raw']['max_m']:.3f} m | {a['raw']['min_m']:.3f}~{a['raw']['max_m']:.3f} m |",
              f"| 기존 중앙값/+0.48m 처리 결과의 중앙값 | {b['processed']['median_m']:.3f} m | {a['processed']['median_m']:.3f} m |", "",
              "전체 원시 중앙값은 약 3.66cm 높아졌고 표준편차는 약 0.23cm 커졌다. 수집 길이, 시간대와 정밀한 배치 유지가 통제되지 않았으므로 펌웨어에 의한 향상/악화로 단정하지 않는다.",
              "업데이트 전 원시 거리는 1cm 단위만 남아 있고 업데이트 후에는 반올림 전 값이 있다. 다음 비교에서는 양쪽의 기존 cm 거리 값을 사용한다.", "",
              "## 동일 표본 수 및 시간 구간 확인", "", "| 비교 구간 / 공통 cm 거리 | 전 중앙값 | 후 중앙값 | 전 표준편차 | 후 표준편차 |", "|---|---:|---:|---:|---:|"]
    for key, label in (("first_46_common_cm", "각 수집의 첫 46개 유효 거리"), ("first_15s_common_cm", "각 수집 시작 시각부터 첫 15초")):
        x,y=b[key],a[key]
        report.append(f"| {label} (n={x['n']}/{y['n']}) | {x['median_m']:.3f} m | {y['median_m']:.3f} m | {x['std_m']*100:.2f} cm | {y['std_m']*100:.2f} cm |")
    report += ["", "초반 구간만 보면 후의 표준편차가 작지만 전체 2분에서는 다르다. 구간 선택에 따라 결론이 달라져 개선 근거로 삼기 어렵다.",
               "수집 시작 기준 시각은 포트 열기/리셋 이전이므로 수집 설정 15초와 정확히 같은 표본 범위가 아니다. 표본 수를 함께 표시했다.", "",
               "## 확인된 성과와 남은 검증", "",
               "- 업데이트 후 385회차에 UWB RX/첫 경로 전력·경로 차이·clock·원시 진단이 추가됐다. 이전에는 해당 진단이 없어 전후 신호 품질 비교는 불가능하다.",
               "- 연속 2분 동안 JSON 오류/펌웨어 큐 누락 0, sequence 255→0과 고유 측정 ID를 확인했다.",
               "- 별도 재부팅 시험에서 새 세션과 cycle_id=0을 확인했다. 리셋 경계의 중단된 UART JSON 조각 1건은 별도 로그에 보존했다.",
               "- 기존 +0.48m 보정의 적합성은 미검증이다. 현재 처리 결과 약 2.18/2.22m를 정확한 실제 거리로 해석하면 안 된다.",
               "- 정확한 정답 거리, 동일 고정 배치·동일 수집 길이의 반복 실험과 LOS/몸/장애물 조건 비교가 필요하다. X/Y 위치 정확도는 이번 한 앵커 시험으로 평가하지 않았다.", "",
               "## 원본 및 전체 측정표", "",
               "- [업데이트 전 원본 JSONL](../logs/uwb-before-flash-20261015.jsonl)",
               "- [업데이트 후 원본 JSONL](../logs/uwb-after-flash-20261015.jsonl)",
               "- [업데이트 전 전체 측정표](../logs/uwb-before-readable-20261015.md)",
               "- [업데이트 후 전체 측정표](../logs/uwb-after-readable-20261015.md)",
               "- [재계산 통계와 원본 SHA256](../logs/uwb-before-after-comparison-20261015.json)", "",
               "원본은 수정하지 않았다. 이 문서와 펼친 표는 현재 PC에만 있으며 커밋/푸시하지 않았다."]
    (ROOT/"docs/UWB_BEFORE_AFTER_COMPARISON_2026-10-15.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
