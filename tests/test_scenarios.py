import json
from datetime import datetime, timedelta

from exam_uncheat.evidence import verify
from exam_uncheat.runner import run_offline
from exam_uncheat.session import Session, purge_expired
from exam_uncheat.simulator import build


def run(tmp_path, sigdb, scenario):
    items = build(scenario)
    s = Session(tmp_path, {"site": "t", "room": "301", "period": "1"}, sigdb, started_at=items[3]["ts"])
    run_offline(s, items)
    return s


def by_cat(s):
    out = {}
    for c in s.clues():
        for cat in c["categories"] or ["_none"]:
            out.setdefault(cat, []).append(c)
    return out


def test_baseline_only_produces_no_clues(tmp_path, sigdb):
    s = run(tmp_path, sigdb, "baseline")
    assert s.clues() == []
    assert s.rejected == 0


def test_glasses_scenario_escalates_with_wifi_direct(tmp_path, sigdb):
    s = run(tmp_path, sigdb, "glasses")
    cats = by_cat(s)
    strong = [c for c in cats["smart_glasses"] if c["max_rssi"] > -80]
    assert len(strong) == 1
    g = strong[0]
    assert g["level"] == "urgent"
    assert g["distinct_subjects"] == 2            # address rotation grouped by signature
    assert any("Wi-Fi Direct" in r for r in g["reasons"])
    weak = [c for c in cats["smart_glasses"] if c["max_rssi"] < -85]
    assert weak and weak[0]["level"] == "info"     # corridor signal never escalated
    assert cats["wifi_direct"][0]["level"] == "check"
    assert any(c["kind"] == "ble.adv" and not c["categories"] for c in s.clues())  # unknown new device


def test_hotspot_and_earbuds(tmp_path, sigdb):
    s = run(tmp_path, sigdb, "all")
    cats = by_cat(s)
    assert cats["phone_hotspot"][0]["level"] == "check"
    assert {c["signature_ids"][0] for c in cats["earbuds"]} == {"earbuds.google_fast_pair",
                                                                 "earbuds.apple_proximity_pairing"}
    # background AP present in baseline must not become a clue
    assert not any(c["kind"] == "wifi.beacon" and not c["categories"] for c in s.clues())


def test_close_writes_report_verifies_and_contains_no_raw_ids(tmp_path, sigdb):
    s = run(tmp_path, sigdb, "all")
    cid = s.clues()[0]["clue_id"]
    s.add_action({"clue_id": cid, "decision": "needs_more_check", "actor_role": "proctor-1",
                  "checklist": ["안경 다리 두께·버튼 확인"], "note": "추가 확인"})
    s.close()
    ok, msgs = verify(s.dir)
    assert ok, msgs
    report = (s.dir / "report.md").read_text()
    assert "판정하지 않습니다" in report and "추가 확인" in report
    ledger = (s.dir / "ledger.jsonl").read_text()
    for o in build("all"):
        addr = (o.get("subject") or {}).get("addr")
        if addr:
            assert addr not in ledger
    assert "OOO의 iPhone" not in ledger
    assert (s.dir / "report.html").read_text().startswith("<!doctype html>")
    man = json.loads((s.dir / "manifest.json").read_text())
    assert man["retention_days"] == 30 and man["closed_at"]


def test_invalid_events_are_rejected_not_logged(tmp_path, sigdb):
    s = Session(tmp_path, {}, sigdb)
    r = s.ingest({"schema": "exam-uncheat.event/v1", "sensor": {"id": "x"}, "kind": "nope"})
    assert r["ok"] is False and s.rejected == 1


def test_purge_respects_retention(tmp_path, sigdb):
    s = run(tmp_path, sigdb, "baseline")
    s.close()
    assert purge_expired(tmp_path, now=datetime.now().astimezone()) == []
    later = datetime.fromisoformat(s.manifest["delete_after"]) + timedelta(seconds=1)
    assert purge_expired(tmp_path, now=later) == [s.dir.name]
