"""Lines in the exact format printed by firmware/esp32-sniffer must validate."""
import pytest

from exam_uncheat.adapters import LineParser
from exam_uncheat.schema import validate

HELLO = ('{"schema":"exam-uncheat.hello/v1","sensor_id":"esp32s3-a1b2c3","driver":"esp32-sniffer",'
         '"driver_version":"0.1.0","hw":"esp32s3","capabilities":["ble.adv","wifi.mgmt","wifi.data_stats"],'
         '"bands":["2.4GHz"],"tx_capable":false}')
LINES = [
    '{"kind":"ble.adv","sensor_ts_ms":1234,"rssi_dbm":-60,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},'
    '"attrs":{"connectable":true,"company_id":427,"mfg_data_hex":"0102","name":"x","service_uuids":["fd5f"],"service_data":{"fd5f":"00"}}}',
    '{"kind":"wifi.probe_req","sensor_ts_ms":1,"channel":6,"rssi_dbm":-50,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},'
    '"attrs":{"ssid":"","is_wildcard":true,"p2p_ie":false}}',
    '{"kind":"wifi.beacon","sensor_ts_ms":1,"channel":36,"rssi_dbm":-50,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},'
    '"attrs":{"ssid":"DIRECT-ab","bssid":"6a:1f:00:12:34:56","hidden":false,"is_p2p_go":true}}',
    '{"kind":"wifi.station","sensor_ts_ms":1,"rssi_dbm":-50,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},'
    '"attrs":{"frames":3,"bytes":300,"window_s":10}}',
    '{"kind":"sensor.health","sensor_ts_ms":1,"attrs":{"uptime_s":10,"dropped":0,"free_heap":100000}}',
]


@pytest.mark.parametrize("line", LINES)
def test_firmware_line_validates(line):
    p = LineParser("esp")
    assert p.parse(HELLO) is not None
    evt = p.parse(line)
    assert evt["sensor"]["id"] == "esp32s3-a1b2c3"
    assert validate(evt) == []
