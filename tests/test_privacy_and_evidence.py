import json

from exam_uncheat.evidence import Ledger, verify, write_sums
from exam_uncheat.privacy import PrivacyGate


def test_scrub_removes_raw_addresses_and_masks_text():
    g = PrivacyGate(b"k" * 32)
    evt = {"kind": "wifi.beacon", "subject": {"addr": "a4:bb:cc:dd:ee:ff", "addr_type": "public"},
           "attrs": {"ssid": "홍길동의 iPhone", "bssid": "a4:bb:cc:dd:ee:ff"}}
    out = g.scrub(evt)
    blob = json.dumps(out, ensure_ascii=False)
    assert "a4:bb:cc:dd:ee:ff" not in blob.lower()
    assert "홍길동" not in blob
    assert out["subject"]["pid"] == g.pid("A4:BB:CC:DD:EE:FF")
    assert out["subject"]["oui"] == "A4:BB:CC"
    assert out["attrs"]["ssid"].startswith("홍길") is True and "***" in out["attrs"]["ssid"]


def test_random_address_has_no_oui_and_key_rotation_unlinks():
    a = PrivacyGate().scrub({"subject": {"addr": "02:00:00:00:00:01", "addr_type": "random"}})
    b = PrivacyGate().scrub({"subject": {"addr": "02:00:00:00:00:01", "addr_type": "random"}})
    assert "oui" not in a["subject"]
    assert a["subject"]["pid"] != b["subject"]["pid"]


def test_destroyed_key_cannot_pseudonymize():
    g = PrivacyGate()
    g.destroy()
    try:
        g.pid("x")
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


def test_ledger_chain_verifies_and_detects_tampering(tmp_path):
    led = Ledger(tmp_path)
    for i in range(5):
        led.append("event", f"2026-11-18T09:00:0{i}+09:00", {"i": i})
    ok, _ = verify(tmp_path)
    assert ok
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    rec = json.loads(lines[2]); rec["data"]["i"] = 99
    lines[2] = json.dumps(rec)
    (tmp_path / "ledger.jsonl").write_text("\n".join(lines) + "\n")
    ok, msgs = verify(tmp_path)
    assert not ok and any("content altered" in m for m in msgs)


def test_ledger_detects_deletion_and_sums(tmp_path):
    led = Ledger(tmp_path)
    for i in range(4):
        led.append("event", "t", {"i": i})
    (tmp_path / "report.md").write_text("report")
    write_sums(tmp_path)
    assert verify(tmp_path)[0]
    (tmp_path / "report.md").write_text("edited")
    ok, msgs = verify(tmp_path)
    assert not ok and any("report.md modified" in m for m in msgs)
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    del lines[1]
    (tmp_path / "ledger.jsonl").write_text("\n".join(lines) + "\n")
    ok, msgs = verify(tmp_path)
    assert not ok and any("sequence gap" in m or "prev hash" in m for m in msgs)


def test_ledger_resume(tmp_path):
    Ledger(tmp_path).append("a", "t", {})
    led = Ledger(tmp_path)
    led.append("b", "t", {})
    assert led.seq == 2 and verify(tmp_path)[0]
