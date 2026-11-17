import json

from fastapi.testclient import TestClient

from exam_uncheat.adapters import LineParser, ReplayAdapter
from exam_uncheat.hub import create_app
from exam_uncheat.simulator import build


def client(tmp_path, sigdb):
    return TestClient(create_app(tmp_path, sigdb))


def test_full_flow_http_ws_actions_report(tmp_path, sigdb):
    c = client(tmp_path, sigdb)
    assert c.post("/api/v1/events", content="{}").status_code == 409
    assert c.post("/api/v1/session/start", json={"site": "s", "room": "301", "exam": "모의", "period": "1",
                                                 "student_name": "dropped"}).status_code == 200
    items = [o for o in build("all") if o.get("schema") != "exam-uncheat.control/v1"]
    base = [o for o in items if o.get("offset_s", 0) < 120]
    exam = [o for o in items if o.get("offset_s", 0) >= 120]
    nd = "\n".join(json.dumps(o, ensure_ascii=False) for o in base)
    r = c.post("/api/v1/events", content=nd, headers={"Content-Type": "application/x-ndjson"})
    assert r.status_code == 200 and r.json()["accepted"] == len(base)
    assert c.post("/api/v1/session/exam").status_code == 200
    with c.websocket_connect("/ws/ingest") as ws:
        for i in range(0, len(exam), 50):
            ws.send_text(json.dumps(exam[i:i + 50], ensure_ascii=False))
            assert ws.receive_json()["ok"] is True
        ws.send_text("not json")
        assert ws.receive_json()["ok"] is False
    clues = c.get("/api/v1/clues").json()
    assert clues[0]["level"] == "urgent"
    a = c.post("/api/v1/actions", json={"clue_id": clues[0]["clue_id"], "decision": "false_positive",
                                        "actor_role": "proctor-2", "note": "일반 안경"})
    assert a.status_code == 200
    assert c.post("/api/v1/actions", json={"clue_id": "c-9999", "decision": "no_action"}).status_code == 404
    assert c.post("/api/v1/actions", json={"clue_id": clues[0]["clue_id"], "decision": "guilty"}).status_code == 422
    assert c.post("/api/v1/manual-alert", json={"vendor": "ACME RF-1", "note": "뒤편 경보"}).json()["ok"]
    assert "오탐" in c.get("/api/v1/report.md").text
    closed = c.post("/api/v1/session/close").json()
    assert closed["verify"]["ok"] is True
    st = c.get("/api/v1/status").json()["session"]
    assert "student_name" not in st["meta"]
    assert c.get("/").status_code == 200
    assert "<table>" in c.get("/api/v1/report.html").text


def test_line_parser_hello_and_defaults():
    p = LineParser(default_sensor_id="ttyACM0", location={"room": "301"})
    assert p.parse(b"ets Jun  8 2016 boot log\n") is None
    hello = p.parse('{"schema":"exam-uncheat.hello/v1","sensor_id":"esp-a","driver":"esp32-sniffer",'
                    '"driver_version":"0.1.0","tx_capable":false}')
    assert hello["sensor_id"] == "esp-a"
    e = p.parse('{"kind":"ble.adv","rssi_dbm":-60,"attrs":{"company_id":3411}}')
    assert e["sensor"] == {"id": "esp-a", "driver": "esp32-sniffer@0.1.0", "location": {"room": "301"}}
    assert e["schema"] == "exam-uncheat.event/v1"
    assert p.parse("{broken") is None and p.bad_lines == 1


def test_line_parser_refuses_tx_capable_sensor():
    p = LineParser()
    try:
        p.parse('{"schema":"exam-uncheat.hello/v1","sensor_id":"x","tx_capable":true}')
    except ValueError:
        return
    raise AssertionError("tx_capable sensor must be refused")


def test_replay_adapter_feeds_sink():
    got = []
    ad = ReplayAdapter(got.append, build("baseline")[:30], speed=0)
    ad.start(); ad.stop(timeout=5)
    assert len(got) == 30
