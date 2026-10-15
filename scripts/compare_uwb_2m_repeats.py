"""Summarize retained 2m R1/R2 measurements; never changes operating settings."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    runs = []
    names = (
        ("R1", "uwb-exact-2m-20261015-r1", "uwb-task2-2m-no-calibration", "uwb-quality-2m-replay"),
        ("R2", "uwb-exact-2m-20261015-r2", "uwb-task2-2m-r2-no-calibration", "uwb-quality-2m-r2-replay"),
    )
    for name, base, filtering, quality in names:
        capture = LOGS / f"{base}.jsonl"
        accuracy = read(capture.with_suffix(".accuracy.json"))
        digest = hashlib.sha256(capture.read_bytes()).hexdigest()
        assert digest == accuracy["source_sha256"], "Original capture changed"
        stats = read(LOGS / f"{filtering}.summary.json")
        runs.append(dict(name=name, source=str(capture), sha256=digest,
                         capture_summary=read(capture.with_suffix(".summary.json")),
                         statistics={mode: data["anchor-001"] for mode, data in stats["statistics"].items()},
                         quality=read(LOGS / f"{quality}.summary.json")))
    conditions = read(LOGS / "uwb-exact-2m-20261015-r2.conditions.json")
    outliers = []
    capture = LOGS / "uwb-exact-2m-20261015-r2.jsonl"
    for line in capture.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["event"] != "device_frame":
            continue
        firmware = row["firmware"]
        obs = firmware["observations"][0]
        if obs["raw_distance_m"] is not None and abs(obs["raw_distance_m"]-2) > .3:
            outliers.append(dict(measurement_id=firmware["measurement_id"], received_at=row["received_at"],
                                 distance_m=obs["raw_distance_m"], diagnostics=obs["diagnostics"]))
    output = dict(runs=runs, conditions=conditions, r2_outliers_over_30cm=outliers,
                  settings_changed=False, nlos_ground_truth_available=False)
    (LOGS / "uwb-2m-r1-r2-comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 2m 거리 재측정 R2와 기존 R1 비교", "",
             "펌웨어·보정·신호 임계값을 바꾸지 않고 COM6에서 약 2분 재측정했다. 서버에는 전송하지 않았다.",
             "거리 기준은 사용자가 제공한 2m이며 PC에서 길이를 독립적으로 확인하지 않았다.", "",
             "## 배치와 수집", "",
             "사용자 설명: 두 UWB 보드를 테이블 위에 놓고 각각 천장을 향하게 했으며, 최대한 가리지 않았지만 3D 출력물과 다른 보드가 근처에 있다.",
             "따라서 '탁상·안테나 위쪽·주변 보드/출력물 있음' 조건으로 기록했다. 통제된 LOS 정답으로 취급하지 않는다.",
             "R1 당시 안테나 방향/주변 물체 조건은 충분히 기록되지 않아 원인별 비교는 할 수 없다.", "",
             "| 항목 | 이전 R1 | 새 R2 |", "|---|---:|---:|"]
    first, second = runs
    for field, label in (("frames", "회차"), ("json_parse_errors", "파싱 오류"),
                          ("max_firmware_dropped_cycles", "펌웨어 누락 카운터"), ("sequence_wraps", "sequence 순환")):
        lines.append(f"| {label} | {first['capture_summary'][field]} | {second['capture_summary'][field]} |")
    lines += ["", "두 로그 모두 동일한 `uwb-capture-20261015.1` 펌웨어이며 세션은 다르다. 새 로그는 A0 거리/진단 386개 모두 valid다. 나머지 세 앵커는 missing이다.", "",
              "## 거리 결과: 보정 제외", "",
              "| 처리/지표 | 이전 R1 | 새 R2 |", "|---|---:|---:|"]
    for mode, title in (("off", "원시"), ("n3", "중앙값 3개"), ("n5", "중앙값 5개")):
        for metric, label, factor, unit in (("mean_m", "평균 거리", 1, "m"), ("mae_m", "평균 절대 오차", 100, "cm"),
                                            ("std_m", "표준편차", 100, "cm"), ("rmse_m", "RMSE", 100, "cm")):
            a, b = (run["statistics"][mode][metric]*factor for run in runs)
            lines.append(f"| {title}: {label} | {a:.3f}{unit} | {b:.3f}{unit} |")
    lines += ["", "R2 원시 범위는 1.798229~2.442150m, 중앙값 5개 범위는 1.890480~2.026042m다.",
              "이번 구간은 R1보다 안정적이지만 펌웨어나 설정을 바꾸지 않았으므로 소프트웨어 개선 효과가 아니다. 배치/주변 환경/시간 구간 등 원인은 이 두 로그만으로 분리할 수 없다.",
              "원시 거리는 평균 약 4.6cm 짧게 나오며, 중앙값은 흔들림을 줄여도 이 편향을 없애지는 않는다.", "",
              "## 기존 보정 및 신호 임계값", "",
              "기존 +0.48m 보정을 그대로 포함하면 R2의 예전 USB 처리 재현 평균은 약 2.432m, MAE 약 43.17cm다. 이 보정값은 이번에도 변경하지 않았다.",
              "서버 공통 중앙값 비교는 반올림 전 원시 값, 과거 USB 처리 재현은 cm 반올림 값을 사용하므로 수치가 조금 다르다.", "",
              "| 기존 잠정 판정 | 이전 R1 | 새 R2 |", "|---|---:|---:|"]
    for category, title in (("nominal", "정상 지표"), ("suspect", "의심/감량 후보"), ("nlos_suspected", "강한 복합 의심")):
        values = [r["quality"]["counts"]["observe"].get(category, 0) for r in runs]
        lines.append(f"| {title} | {values[0]} | {values[1]} |")
    lines += ["", "R2의 385개는 suspect, 유일한 nominal 1개는 오히려 최대 거리 2.44215m(오차 44.215cm)였다. nominal은 실제 거리 정답을 뜻하지 않는다.",
              "적용 모드 재생에서는 강한 NLOS 의심 제외는 0개이고, 감량 385개·정상 복귀 확인 대기 1개였다. 관찰 모드는 386개 모두 기존 처리를 유지했다.",
              "R1의 370개 사용 보류와 크게 다르다. 현재 신호 지표 임계값이 거리 오차의 크기를 안정적으로 구분한다는 증거가 없다.",
              "따라서 이 한 배치에 맞춰 임계값을 늘려 대부분을 통과시키거나, 정상 지표로 보인 큰 오차를 잡으려고 반대로 뒤집지 않았다. 운영은 관찰 모드를 유지한다.",
              "다음 임계값 선택에는 동일 배치에서 직접 가림 없음/몸/장애물 조건을 구분한 반복 로그가 필요하다. 단일 앵커이므로 XY 위치 정확도도 검증하지 않았다.", "",
              "## 보존 파일", "",
              "- `logs/uwb-exact-2m-20261015-r2.jsonl`: 원본 거리·신호 진단",
              "- `logs/uwb-exact-2m-20261015-r2.conditions.json`: 사용자 배치 설명",
              "- `docs/UWB_EXACT_2M_R2_MEASUREMENT_2026-10-15.md`: 전체 측정표·기존 처리 비교",
              "- `logs/uwb-task2-2m-r2-no-calibration.summary.json`: 미적용/N=3/N=5 공통 서버 재생",
              "- `logs/uwb-quality-2m-r2-replay.summary.json`: 기존 임계값 관찰/적용 재생",
              "- `logs/uwb-2m-r1-r2-comparison.json`: 비교 통계와 큰 오차 회차의 진단값",
              "", "모두 로컬 파일이다. 기존 원본은 SHA256으로 불변을 확인했다. 펌웨어·운영 설정·커밋·푸시·PR은 변경하지 않았다."]
    report = ROOT / "docs/UWB_2M_REPEAT_COMPARISON_2026-10-15.md"
    report.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(json.dumps({"report": str(report), "outliers_over_30cm": len(outliers), "r2_raw": second["statistics"]["off"],
                      "r2_n5": second["statistics"]["n5"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
