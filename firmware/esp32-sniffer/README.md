# esp32-sniffer (v0.1)

> **상태:** ESP32-S3·ESP32-C6 대상으로 **빌드 확인**(PlatformIO, ESP-IDF 6.1, 경고 없음).
> **실기기 동작 검증은 아직 하지 않았습니다.** ESP32-C5는 아직 빌드 확인 전입니다. 이슈·PR 환영.

수신 전용 ESP32 센서 펌웨어입니다. 관측 결과를 USB 시리얼로 `exam-uncheat` 줄단위 JSON(NDJSON)으로 내보냅니다.

| 대상 | Wi-Fi | BLE |
| --- | --- | --- |
| ESP32-S3 / ESP32-C6 | 2.4 GHz 무차별 수신 (관리 프레임 해석, 데이터 프레임은 개수만) | 패시브 스캔 |
| ESP32-C5 | 2.4 + 5 GHz (`EXU_SCAN_5G`) | 패시브 스캔 |

## 빌드
ESP-IDF (5.3 이상):
```bash
idf.py set-target esp32s3      # esp32c6 / esp32c5
idf.py menuconfig              # "exam-uncheat sensor" 메뉴 (선택)
idf.py build flash monitor
```
PlatformIO:
```bash
pio run -e esp32-s3-devkitc-1 -t upload     # 또는 -e esp32-c6-devkitc-1
```

허브 연결:
```bash
exam-uncheat hub --serial /dev/ttyACM0:115200 --room 301
```

## 설정 (menuconfig → exam-uncheat sensor)
| 항목 | 기본값 | 설명 |
| --- | --- | --- |
| `EXU_ENABLE_BLE` | y | BLE 광고 패시브 수신 |
| `EXU_ENABLE_WIFI` | y | Wi-Fi 관리 프레임 수신 + 데이터 프레임 통계 |
| `EXU_DWELL_MS` | 250 | 채널당 머무는 시간 |
| `EXU_STATS_PERIOD_S` | 10 | 단말 통계·상태(`sensor.health`) 출력 주기 |
| `EXU_SCAN_5G` | y | 5 GHz 채널 포함 (5 GHz 지원 칩만) |

센서 ID는 보드 자신의 공장 MAC 뒤 3바이트로 만듭니다 (예: `esp32s3-a1b2c3`).

## 출력 예
```json
{"schema":"exam-uncheat.hello/v1","sensor_id":"esp32s3-a1b2c3","driver":"esp32-sniffer","driver_version":"0.1.0","hw":"esp32s3","capabilities":["ble.adv","wifi.mgmt","wifi.data_stats"],"bands":["2.4GHz"],"tx_capable":false}
{"kind":"ble.adv","sensor_ts_ms":1234,"rssi_dbm":-60,"subject":{"addr":"6a:1f:00:12:34:56","addr_type":"random"},"attrs":{"connectable":true,"company_id":427,"mfg_data_hex":"0102"}}
{"kind":"sensor.health","sensor_ts_ms":10000,"attrs":{"uptime_s":10,"dropped":0,"free_heap":201234}}
```
이 형식은 `tests/test_firmware_format.py`가 허브 스키마로 검증합니다.

## 수신 전용 원칙
- `WIFI_MODE_NULL` + promiscuous 수신만 사용합니다. 능동 스캔·프레임 송신 API를 쓰지 않습니다.
- BLE는 NimBLE observer 역할만 켜고(`sdkconfig.defaults`에서 broadcaster·peripheral·central 비활성), `passive = 1`로 SCAN_REQ를 보내지 않습니다.
- 데이터 프레임은 송신 주소·개수·바이트·RSSI만 집계하고 페이로드는 읽지 않습니다.
- CI의 `tools/no_tx_check.py`가 송신 관련 API를 발견하면 빌드를 실패시킵니다.

## 알려진 한계
- BLE와 Wi-Fi를 한 칩에서 같이 켜면 무선부를 나눠 쓰므로 각각 놓치는 패킷이 늘어납니다. 보드 2개(BLE 전용·Wi-Fi 전용)를 권장합니다.
- BLE 5 확장 광고는 아직 받지 않습니다.
- 채널 호핑 중에는 다른 채널의 프레임을 놓칩니다.
