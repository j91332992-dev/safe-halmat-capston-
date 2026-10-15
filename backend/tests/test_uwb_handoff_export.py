import importlib.util
import csv
import json
from pathlib import Path


spec=importlib.util.spec_from_file_location("handoff_export",
    Path(__file__).resolve().parents[2]/"scripts/package_uwb_handoff.py")
export=importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def test_shareable_ids_preserve_measurement_links_and_raw_numbers():
    session="012345abcdef-12-"+"1"*32
    row=dict(session_id=session,measurement_id=session+":256",sequence=0,cycle_id=256,
             raw_distance_m=2.125,diagnostics={"status":"invalid","rx_power_dbm":None,"raw":{"power":0}})
    result=export.sanitize(row)
    assert result["measurement_id"]==result["session_id"]+":256"
    assert result["session_id"].startswith("c0dec0de0001-12-")
    assert result["sequence"]==0 and result["cycle_id"]==256
    assert result["raw_distance_m"]==2.125 and result["diagnostics"]==row["diagnostics"]


def test_network_credentials_and_workstation_paths_are_not_exported():
    row={"password":"private-password","ssid":"private-network","mac":"12:34:56:78:9a:bc",
         "server":"http://192.168.1.7:8000","file":r"C:\Users\private\logs\run.jsonl","port":"COM6"}
    result=export.sanitize(row)
    assert result["password"]==result["ssid"]=="<REDACTED>"
    assert result["file"]=="<LOCAL_PATH>/run.jsonl"
    assert result["port"]=="<USB_PORT>" and "192.168.1.7" not in result["server"]
    assert result["mac"]=="<TAG_MAC>"


def test_selected_publication_contains_only_requested_paired_comparisons():
    root=Path(__file__).resolve().parents[2]/"docs/measurements/2026-10-15-comparison"
    names={"distance_2m_before", "distance_2m_after_median5", "position_p4", "position_modified"}
    assert {p.stem for p in root.glob("*.csv")} == names
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["scope"]) == names
    assert {p.name for p in (root/"raw").iterdir()} == {r["filename"].split("/")[-1] for r in manifest["sources"]}
    assert len(manifest["sources"]) == len(export.CAPTURES) == 2
    data={}
    for name in names:
        with (root/(name+".csv")).open(encoding="utf-8-sig", newline="") as f:
            data[name]=list(csv.DictReader(f))
    for before, after, count in [("distance_2m_before", "distance_2m_after_median5", 386),
                                 ("position_p4", "position_modified", 382)]:
        assert len(data[before]) == len(data[after]) == count
        assert [r["measurement_id"] for r in data[before]] == [r["measurement_id"] for r in data[after]]
    assert sum(r["solved"] == "False" for r in data["position_modified"]) == 1
