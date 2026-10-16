"""Replay actual Wi-Fi observations through isolated P4/current position services.

This compares the numerical server pipeline, not two running HTTP deployments.
Never touches the live server database or its coordinate/distance histories.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import gzip
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev
import subprocess
import sys
from tempfile import TemporaryDirectory
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import Settings, settings
from app.schemas.api import UwbDistancesIn
from app.services.uwb_distance_filter import DistanceFilter
from app.services.location_service import solve_position
from app.services.location_speed_service import LocationSpeedGuard

BASELINE = "722c9fd327997b8d4bdd59ae088928d9285eba40"


def git_source(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT).decode("utf-8")


def module_from_source(name, path, source):
    # The actual historical code retains its relative settings import. Each
    # module has its own histories and dataclass namespace.
    module = types.ModuleType("app.services." + name)
    module.__package__ = "app.services"
    module.__file__ = str(ROOT / path)
    sys.modules[module.__name__] = module
    exec(compile(source, str(ROOT / path) + "@" + name, "exec"), module.__dict__)
    return module


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    p = (len(values) - 1) * q
    lo, hi = math.floor(p), math.ceil(p)
    return values[lo] + (values[hi] - values[lo]) * (p - lo)


def metrics(points, reference):
    if not points:
        return {"n": 0}
    errors = [math.dist(p, reference) for p in points]
    steps = [math.dist(a, b) for a, b in zip(points, points[1:])]
    return dict(n=len(points), mean_x_m=mean(p[0] for p in points), mean_y_m=mean(p[1] for p in points),
                approximate_reference_mae_m=mean(errors), approximate_reference_rmse_m=mean(e*e for e in errors)**.5,
                approximate_reference_p95_m=percentile(errors, .95),
                scatter_std_m=math.hypot(pstdev(p[0] for p in points), pstdev(p[1] for p in points)),
                step_p95_m=percentile(steps, .95), max_step_m=max(steps, default=0),
                jumps_over_30cm=sum(s > .3 for s in steps),
                stationary_display_fraction=sum(s <= .001 for s in steps)/len(steps) if steps else None)


def run_pipeline(rows, name, cfg, solve, smoothing, old_schema=None, conversion=None):
    smoothing.reset_location_filter()
    distance = DistanceFilter(cfg)
    speed = LocationSpeedGuard(cfg)
    initial = rows[0].get("previous_position") or {"x": 0, "y": 0}
    point = (initial["x"], initial["y"])
    last_valid = None
    results = []
    for row in rows:
        wire = row["input"]
        now = datetime.fromisoformat(row["server_received_at"].replace("Z", "+00:00")).timestamp()
        result = dict(mode=name, measurement_id=wire.get("measurement_id"), received_at=row["server_received_at"],
                      solved=False, applied=False, accepted=False, candidate=None, filtered=None,
                      final=list(point), reason=None, position_age_seconds=None)
        try:
            if old_schema:
                p = old_schema.model_validate(wire)
                measurements = conversion(p.measurements, apply_calibration=not p.distances_calibrated)
            else:
                p = UwbDistancesIn.model_validate(wire)
                processing = distance.process(p, now)
                result["distance_processing"] = processing
                if not processing["accepted"]:
                    result["reason"] = processing["reason"]
                    raise SkipFrame()
                measurements = processing["measurements"]
            result["processed_measurements"] = measurements
            x, y, confidence = solve(row["anchors"], measurements)
            if not all(math.isfinite(v) for v in (x, y, confidence)):
                raise ValueError("nonfinite_output")
            result.update(solved=True, candidate=[x, y], confidence=confidence)
            if old_schema:
                check = dict(applied=True, accepted=True, reason="p4_no_speed_guard", reset_smoothing=False)
            else:
                check = speed.check(p, x, y, now=now)
            result["position_check"] = check
            result.update(applied=check["applied"], accepted=check["accepted"], reason=check["reason"])
            if check["applied"]:
                if check["reset_smoothing"]:
                    smoothing.reset_location_filter(p.worker_id)
                fx, fy = smoothing.filter_location(p.worker_id, x, y, None if check["reset_smoothing"] else point)
                result["filtered"] = [fx, fy]
                point = (max(0, min(2, fx)), max(0, min(1, fy)))
                result["final"] = list(point)
            if check["accepted"]:
                last_valid = now
        except SkipFrame:
            pass
        except (ValueError, ArithmeticError) as exc:
            result["reason"] = getattr(exc, "reason", type(exc).__name__ + ":" + str(exc))
        result["position_age_seconds"] = None if last_valid is None else max(0, now-last_valid)
        results.append(result)
    return results


class SkipFrame(Exception):
    pass


def summarize(results, reference):
    candidates = [r["candidate"] for r in results if r["solved"]]
    ages = [r["position_age_seconds"] for r in results if r["position_age_seconds"] is not None]
    return dict(frames=len(results), solved=sum(r["solved"] for r in results),
                applied=sum(r["applied"] for r in results), accepted=sum(r["accepted"] for r in results),
                reasons=dict(Counter(r["reason"] for r in results)),
                candidate=metrics(candidates, reference),
                display_all_frames_including_held=metrics([r["final"] for r in results], reference),
                applied_fixes=metrics([r["final"] for r in results if r["applied"]], reference),
                candidate_outside_map=sum(not (0 <= p[0] <= 2 and 0 <= p[1] <= 1) for p in candidates),
                display_on_boundary=sum(any(abs(v-b)<.001 for v, b in ((r["final"][0],0),(r["final"][0],2),(r["final"][1],0),(r["final"][1],1))) for r in results),
                max_valid_position_age_seconds=max(ages, default=None),
                no_valid_fix_yet=sum(r["position_age_seconds"] is None for r in results))


def live_summary(rows, reference):
    """The output actually sent by the live server, including its warm states."""
    traces = []
    for row in rows:
        if row.get("final_position") is None:
            return None
        candidate = row.get("candidate_position")
        pipeline = row.get("pipeline", {})
        check = row.get("position_check", {})
        traces.append(dict(solved=bool(candidate),
            applied=pipeline.get("position_applied", False), accepted=pipeline.get("position_accepted", False),
            candidate=None if candidate is None else [candidate["x"], candidate["y"]],
            final=[row["final_position"]["x"], row["final_position"]["y"]],
            reason=check.get("reason", row.get("status")),
            position_age_seconds=(row.get("position_status") or {}).get("last_valid_age_seconds")))
    return summarize(traces, reference)


def compare(rows, output, reference=(1, .5)):
    if not rows:
        raise ValueError("No actual Wi-Fi server observations")
    if len({r["input"]["worker_id"] for r in rows}) != 1:
        raise ValueError("This fixed-point comparison requires one worker")
    positions = {"anchor-001": (0,0), "anchor-002": (2,0), "anchor-003": (2,1), "anchor-004": (0,1)}
    if any(not r.get("anchors") or any((a["x"],a["y"]) != positions.get(a["anchor_id"]) for a in r["anchors"]) for r in rows):
        raise ValueError("Capture must use confirmed 2m x 1m anchor layout")
    paths = {key: f"backend/app/{path}" for key, path in dict(
        solver="services/location_service.py", smoothing="services/location_filter_service.py",
        conversion="services/uwb_service.py", schema="schemas/api.py").items()}
    sources = {k: git_source(v) for k, v in paths.items()}
    old = {k: module_from_source("p4_compare_"+k, paths[k], sources[k]) for k in paths}
    offsets = json.loads(git_source("uwb_calibration.json")).get("offset_m", {})
    old["conversion"].calibration_offsets = lambda: {k: float(v) for k,v in offsets.items()}
    traces = {}
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="position-compare-", dir=output.parent) as temp:
        values = {k: getattr(settings,k) for k in type(settings).model_fields if k.startswith(("uwb_", "location_"))}
        for name, window in (("p4_original", None), ("today_n5",5), ("today_median_off",0), ("today_n3",3)):
            cfg = Settings(_env_file=None, **{**values, "uwb_filter_state_path": str(Path(temp)/(name+".sqlite3")),
                "uwb_calibration_enabled": False, "uwb_quality_mode":"observe", "uwb_speed_mode":"observe",
                "uwb_median_enabled":window != 0, "uwb_median_window":window or 5})
            if window is None:
                traces[name] = run_pipeline(rows,name,cfg,old["solver"].solve_position,old["smoothing"],
                                           old["schema"].UwbDistancesIn,old["conversion"].measurements_to_dict)
            else:
                smooth_path=paths["smoothing"]
                smoothing = module_from_source(name+"_smoothing",smooth_path,(ROOT/smooth_path).read_text(encoding="utf-8"))
                traces[name] = run_pipeline(rows,name,cfg,solve_position,smoothing)
    with output.open("w",encoding="utf-8") as f:
        for i in range(len(rows)):
            f.write(json.dumps({"measurement_id": rows[i]["input"].get("measurement_id"),
                                "comparisons":{k:v[i] for k,v in traces.items()}},ensure_ascii=False,allow_nan=False)+"\n")
    summary=dict(baseline_commit=BASELINE,frames=len(rows),reference_m=list(reference),reference_exact=False,
        initial_position=rows[0].get("previous_position"),
        comparison="actual historical/current numerical services replay; not two HTTP servers or firmware A/B",
        old_calibration_offsets_m=offsets, today_policy=dict(calibration=False,quality="observe",speed="observe"),
        historical_source_sha256={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()},
        current_source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            "backend/app/services/location_service.py","backend/app/services/location_filter_service.py",
            "backend/app/services/location_speed_service.py","backend/app/services/uwb_distance_filter.py"]},
        results={k:summarize(v,reference) for k,v in traces.items()})
    summary["live_today"] = live_summary(rows, reference)
    differences = []
    for source, replay in list(zip(rows,traces["today_n5"]))[5:]:
        actual = source.get("candidate_position")
        if actual and replay["candidate"]:
            differences.append(math.dist([actual["x"],actual["y"]],replay["candidate"]))
    summary["today_replay_vs_live_candidate_after_5_frames"] = dict(
        compared=len(differences), max_difference_m=max(differences,default=None))
    output.with_suffix(".summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    report(summary,output.with_suffix(".md"))
    return summary


def report(summary, path):
    lines=["# 2m × 1m 중앙 고정 UWB 위치 비교", "", f"실물 Wi-Fi 원본 {summary['frames']}회차. 기준 P4 커밋 `{BASELINE}`.",
        "", "사용자 기준점은 대략 (1,0.5)m이고 앵커/태그 높이는 같다. 아래 기준점 오차는 참고값이며 정밀 실측 정확도가 아니다.",
        "독립 상태의 실제 수치 처리 서비스 재생이다. 두 HTTP 배포·펌웨어·위험구역/권한/통신 A/B는 검증하지 않았다.",
        "같은 첫 previous_position으로 시작했다. 표시 좌표는 실패 중 유지된 이전 위치도 포함한다.", "",
        "| 조건 | 계산 성공/전체 | 유효 수락 | 표시 기준점 MAE(m) | 표시 산포(m) | 30cm 초과 점프 | 지도 경계 회차 |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for name,r in summary["results"].items():
        m=r["display_all_frames_including_held"]
        lines.append(f"| {name} | {r['solved']}/{r['frames']} | {r['accepted']} | {m['approximate_reference_mae_m']:.3f} | {m['scatter_std_m']:.3f} | {m['jumps_over_30cm']} | {r['display_on_boundary']} |")
    if summary.get("live_today"):
        r=summary["live_today"]; m=r["display_all_frames_including_held"]
        lines.append(f"| live_today (actual server output) | {r['solved']}/{r['frames']} | {r['accepted']} | {m['approximate_reference_mae_m']:.3f} | {m['scatter_std_m']:.3f} | {m['jumps_over_30cm']} | {r['display_on_boundary']} |")
        lines += ["", "live_today는 실제 서버가 보낸 좌표의 통계다. 재생과는 시작 시 내부 이력이 다를 수 있다."]
    lines += ["", "P4는 당시 보정 파일과 거리 cm 입력을 그대로 사용한다. 오늘 조건은 보정 OFF이며 원시 정밀 거리와 공통 필터를 사용한다. 따라서 원본↔수정본 차이를 중앙값 하나의 효과로 단정하지 않는다.",
              "today_median_off/N3는 원인 분리를 위한 오프라인 대조이며 실행 중인 서버 설정은 변경하지 않았다.",
              "계산 실패를 줄이거나 화면을 고정하는 것만으로 정확도 개선이라고 해석하지 않는다. 후보와 표시 좌표, 유효 수락 및 유지 시간을 함께 본다."]
    for name,r in summary["results"].items():
        lines += ["",f"## {name}", "",f"판정 사유: `{json.dumps(r['reasons'],ensure_ascii=False)}`",
                  f"지도 밖 후보 {r['candidate_outside_map']}회, 마지막 유효 위치 최대 나이 {r['max_valid_position_age_seconds']}초."]
    Path(path).write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    opener=gzip.open if args.capture.suffix==".gz" else open
    with opener(args.capture,"rt",encoding="utf-8") as source:
        rows=[json.loads(line) for line in source if line.strip()]
    print(json.dumps(compare(rows,args.output),ensure_ascii=False,indent=2))
