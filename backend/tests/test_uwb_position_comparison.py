"""Validate offline comparison using actual historical and current services."""
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("uwb_position_compare",
    Path(__file__).resolve().parents[2] / "scripts/compare_uwb_positions.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def records(count=12):
    out = []
    anchors = [{"anchor_id":f"anchor-{i:03d}", "x":x,"y":y}
               for i,(x,y) in enumerate(((0,0),(2,0),(2,1),(0,1)),1)]
    for cycle in range(count):
        distance=math.hypot(1,.5)
        wire=dict(worker_id="worker-001",helmet_id="helmet-001",device_id="helmet-001-uwb",uwb_tag_id="tag-001",
                  schema_version=2,session_id="comparison-test",measurement_id=f"comparison-test:{cycle}",
                  cycle_id=cycle,sequence=cycle%256,measured_uptime_us=1000000+cycle*300000,
                  distances_calibrated=False,transport="wifi",
                  measurements=[dict(anchor_id=a["anchor_id"],distance_m=round(distance,2),quality=.95) for a in anchors],
                  observations=[dict(anchor_id=a["anchor_id"],status="valid",raw_distance_m=distance,
                                     diagnostics={"status":"missing","reason":"test_no_diagnostics"}) for a in anchors])
        out.append(dict(input=wire,anchors=anchors,previous_position={"x":0,"y":0},
                        server_received_at=datetime.fromtimestamp(1000+cycle*.3,timezone.utc).isoformat()))
    return out


def test_comparison_uses_same_frames_and_isolated_states(tmp_path):
    path=tmp_path/"compare.jsonl"
    summary=comparison.compare(records(),path)
    assert summary["baseline_commit"] == comparison.BASELINE
    assert summary["reference_exact"] is False
    assert summary["results"]["today_n5"]["solved"] == 12
    assert summary["results"]["today_n5"]["candidate"]["approximate_reference_mae_m"] < .001
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for i,row in enumerate(rows):
        assert {r["measurement_id"] for r in row["comparisons"].values()} == {f"comparison-test:{i}"}
    assert rows[0]["comparisons"]["today_n5"]["distance_processing"]["anchor_processing"][0]["sample_count"] == 1
    assert not list(tmp_path.glob("position-compare-*"))


def test_comparison_rejects_wrong_map_and_empty_data(tmp_path):
    with pytest.raises(ValueError,match="No actual"):
        comparison.compare([],tmp_path/"bad.jsonl")
    rows=records(1); rows[0]["anchors"][1]["x"]=5.8
    with pytest.raises(ValueError,match="confirmed"):
        comparison.compare(rows,tmp_path/"bad.jsonl")


def test_scatter_is_not_accuracy():
    metrics=comparison.metrics([(0,0)]*4,(1,.5))
    assert metrics["scatter_std_m"] == 0
    assert metrics["approximate_reference_mae_m"] > 1


def test_live_summary_uses_actual_output_even_when_solver_fails():
    rows=[dict(final_position={"x":0,"y":1},candidate_position=None,
               pipeline={"position_applied":False,"position_accepted":False},
               position_check={"reason":"nonconverged"}) for _ in range(3)]
    result=comparison.live_summary(rows,(1,.5))
    assert result["solved"] == 0 and result["display_on_boundary"] == 3
    assert result["display_all_frames_including_held"]["n"] == 3
    assert result["reasons"] == {"nonconverged":3}
