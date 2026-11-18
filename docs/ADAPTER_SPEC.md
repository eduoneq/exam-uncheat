# exam-uncheat 어댑터 규격 (`exam-uncheat.event/v1`)

어떤 장비든 아래 JSON을 한 줄에 하나씩 보내면 허브에 붙일 수 있습니다. 기계가 읽는 정의는 [`spec/event.schema.json`](../spec/event.schema.json)에 있습니다.

## 1. 드라이버가 지켜야 할 것
1. 수신만 합니다. BLE 능동 스캔(SCAN_REQ), 프로브를 보내는 Wi-Fi 능동 스캔, 광고, 연결, 프레임 주입, 재밍은 금지이고 `tools/no_tx_check.py`가 CI에서 검사합니다.
2. 데이터 프레임은 페이로드를 버리고 송신 주소, 개수, 바이트 수, RSSI만 보냅니다.
3. 시작할 때 `hello`를 보내면서 송신 가능 여부(`tx_capable`)를 사실대로 적습니다. 송신이 가능하다고 밝힌 센서는 허브가 받지 않습니다.

## 2. 전송
| 전송 | 엔드포인트 | 형식 |
| --- | --- | --- |
| 시리얼 (기본) | `exam-uncheat hub --serial PORT[:BAUD]` | UTF-8 NDJSON, `\n` 종료. `{`로 시작하지 않는 줄(부트 로그)은 무시 |
| WebSocket | `ws://<hub>:8765/ws/ingest` | 텍스트 프레임 = 이벤트 1개 또는 배열 |
| HTTP | `POST /api/v1/events` | `application/x-ndjson` 또는 JSON 배열 |
| MQTT | (로드맵) `exam-uncheat/v1/{site}/{room}/{sensor_id}/events` | 로컬 브로커만 |

허브는 기본적으로 `127.0.0.1`에만 바인딩합니다. v0.1 허브에는 인증이 없으므로 `--allow-lan`은 격리된 유선망에서만 쓰세요.

## 3. hello
```json
{"schema":"exam-uncheat.hello/v1","sensor_id":"esp32c5-a","driver":"esp32-sniffer","driver_version":"0.1.0",
 "hw":"ESP32-C5-DevKitC-1","capabilities":["ble.adv","wifi.mgmt","wifi.data_stats"],"bands":["2.4GHz","5GHz"],"tx_capable":false}
```

## 4. 이벤트
```json
{"schema":"exam-uncheat.event/v1","sensor":{"id":"esp32c5-a","location":{"room":"301","zone":"front"}},
 "kind":"ble.adv","rssi_dbm":-58,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},
 "attrs":{"company_id":427,"service_uuids":["fd5f"],"mfg_data_hex":"0100…","name":"…","connectable":true}}
```
시리얼에서는 `schema`·`sensor`를 생략하면 hello 값으로 채웁니다. `ts`를 생략하면 허브 수신 시각을 씁니다.

| kind | 주요 attrs |
| --- | --- |
| `ble.adv` | `company_id`(정수), `service_uuids`(16비트는 4자리 hex), `service_data`({uuid: hex}), `mfg_data_hex`(회사 ID 2바이트 *다음*부터), `name`, `connectable` |
| `ble.conn_activity` | `access_addr_hash`, `pkt_count`, `window_s` |
| `wifi.probe_req` | `ssid`, `is_wildcard`, `ie_fingerprint`, `p2p_ie` |
| `wifi.beacon` | `ssid`, `bssid`, `security`, `is_p2p_go`, `hidden` |
| `wifi.station` | `bssid`, `frames`, `bytes`, `window_s` |
| `wifi.p2p` | `role`, `device_name` |
| `rf.energy` | `f_start_mhz`, `f_stop_mhz`(필수), `peak_dbm`, `occupancy`(0~1) |
| `detector.alert` | `level`, `vendor`, `model`, `raw_text`, `manual` |
| `sensor.health` | `uptime_s`, `dropped`, `channel_plan`, `temp_c` |

## 5. 제어 줄 (리플레이 파일 전용)
`{"schema":"exam-uncheat.control/v1","action":"start_exam","offset_s":120}` — 빈 교실 기준선을 확정하고 시험 단계로 전환.

## 6. 새 어댑터 만들기 (Python)
```python
from exam_uncheat.adapters import Adapter

class MyDetector(Adapter):
    name = "my-detector"
    def run(self):
        while not self.stopped:
            r = read_device()                     # 장비에서 읽기 (수신만)
            self.emit({"schema": "exam-uncheat.event/v1", "sensor": {"id": "det-1", "driver": self.name},
                       "kind": "detector.alert", "attrs": {"level": r.level, "vendor": "ACME", "model": "RF-1"}})
```
다른 언어라면 같은 JSON을 WebSocket이나 HTTP로 보내면 됩니다.
