from exam_uncheat.schema import normalize, validate


def ble(**attrs):
    return normalize({"schema": "exam-uncheat.event/v1", "sensor": {"id": "t"}, "kind": "ble.adv",
                      "subject": {"addr": "02:11:22:33:44:55", "addr_type": "random"}, "attrs": attrs})


def test_valid_event_passes():
    assert validate({"schema": "exam-uncheat.event/v1", "sensor": {"id": "s"}, "kind": "ble.adv", "attrs": {}}) == []


def test_invalid_event_reports_errors():
    errs = validate({"schema": "exam-uncheat.event/v1", "sensor": {"id": "s"}, "kind": "ble.teleport",
                     "subject": {"addr": "not-a-mac"}})
    assert any("kind" in e for e in errs) and any("addr" in e for e in errs)


def test_unknown_top_level_field_rejected():
    assert validate({"schema": "exam-uncheat.event/v1", "sensor": {"id": "s"}, "kind": "ble.adv", "payload": "x"})


def test_signature_files_validate(sigdb):
    assert len(sigdb.signatures) >= 10
    for s in sigdb.signatures:
        assert s["sources"], s["id"]
        assert s["spoofable"] is True


def test_meta_payload_is_high_confidence(sigdb):
    mfg = "0100" + "META_RB_GLASS".encode().hex()
    hits = sigdb.match(ble(company_id=0x01AB, service_uuids=["FD5F"], mfg_data_hex=mfg))
    assert hits[0]["id"] == "glasses.meta.payload"
    ids = {h["id"] for h in hits}
    assert {"glasses.meta.service", "glasses.meta.company_only"} <= ids


def test_meta_company_only_is_low(sigdb):
    hits = sigdb.match(ble(company_id=0x01AB))
    assert [h["id"] for h in hits] == ["glasses.meta.company_only"]
    assert hits[0]["confidence"] == "low"


def test_luxottica_and_fast_pair_and_apple(sigdb):
    assert sigdb.match(ble(company_id=0x0D53))[0]["id"] == "glasses.luxottica.company"
    assert sigdb.match(ble(service_data={"FE2C": "00"}))[0]["id"] == "earbuds.google_fast_pair"
    assert sigdb.match(ble(company_id=0x004C, mfg_data_hex="0719"))[0]["id"] == "earbuds.apple_proximity_pairing"
    assert sigdb.match(ble(company_id=0x004C, mfg_data_hex="1005")) == []  # other Apple message types


def test_wifi_signatures(sigdb):
    def beacon(ssid, **kw):
        return {"schema": "exam-uncheat.event/v1", "sensor": {"id": "t"}, "kind": "wifi.beacon",
                "attrs": {"ssid": ssid, **kw}}
    assert sigdb.match(beacon("DIRECT-ab-Printer"))[0]["id"] == "wifi.direct_group"
    assert sigdb.match(beacon("Kim의 iPhone"))[0]["id"] == "wifi.hotspot.iphone_name"
    assert sigdb.match(beacon("SCHOOL-EDU")) == []
