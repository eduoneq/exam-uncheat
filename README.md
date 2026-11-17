# exam-uncheat — 시험장용 오픈소스 RF 센서 허브

**어떤 전파 수신 장비든 꽂으면, 하나의 화면·하나의 증거 기록·하나의 보고서로 묶어 주는 수신 전용 허브입니다.**
감독관의 **판단을 돕는 도구**이며, 부정행위를 판정하지 않습니다.

> ⚠️ **먼저 읽어 주세요**
> - v0.1은 **시뮬레이터와 리플레이로만 검증**했습니다. 실제 시험장 현장 검증과 실물 하드웨어 검증 전입니다. → [탐지 한계](docs/LIMITATIONS.md)
> - **수신만 합니다.** 전파를 보내거나, 막거나(재밍), 기기에 접속하거나, 통신 내용을 복호화하지 않습니다. 이런 코드는 CI가 거부합니다. → [법·개인정보](docs/LEGAL.md)
> - 시험 시행기관의 승인 없이 시험실에 장비를 설치·반입하지 마세요. 수능 고사장은 감독관도 전자기기 반입이 금지된다고 보도된 바 있습니다.

![감독관 콘솔 (시뮬레이션 데이터)](docs/img/console.png)

## 왜 만들었나

2026년 국가자격시험·토익·LEET 등에서 AI 스마트안경 부정행위가 잇따랐고, 교육부는 내년 수능에 시험장용 전파탐지기 도입을 검토하겠다고 밝혔습니다. 그런데 지금까지 국내 적발 사례는 감독관이 육안으로 찾은 것이었고, 금속·전파탐지기는 모의훈련에서 탐지에 실패했다는 보도가 있었습니다.

이 프로젝트는 "더 민감한 탐지기 하나"가 아니라 **장비에 종속되지 않는 공통 구조**를 공개합니다.

- **어떤 하드웨어든 연결**: 만 원대 ESP32, 라즈베리파이 + 모니터 모드 Wi-Fi 어댑터, BLE 스니퍼, SDR, 시리얼 출력이 있는 상용 탐지기, 그리고 감독관의 수동 입력까지 같은 [이벤트 규격](docs/ADAPTER_SPEC.md)으로 받습니다.
- **폰 앱이 못 보는 신호**: 전용 수신기는 Wi-Fi 프로브 요청, 공유기에 붙은 단말, Wi-Fi Direct 그룹, 5 GHz, 연속 BLE 광고를 볼 수 있습니다 (장비별 차이는 [HARDWARE.md](docs/HARDWARE.md)).
- **공개 시그니처 DB**: 블루투스 SIG 공식 등록부의 회사 ID·서비스 UUID와 공개 문헌을 출처와 함께 YAML로 관리합니다. ([signatures/](signatures/))
- **증거 사슬**: 모든 관측·단서·감독관 조치를 해시 체인 원장에 기록하고, `exam-uncheat verify`로 사후 위변조를 확인합니다.
- **사람이 판단**: 단서(참고/확인 권장/즉시 확인 권장) → 감독관 확인(기기 확인함/오탐/추가 확인) → 보고서 초안.
- **데이터는 교실 밖으로 안 나감**: 기기 주소는 저장 전에 세션 키로 가명 처리하고, 세션이 끝나면 키를 폐기합니다. 클라우드 전송 기능이 없고, 기본 30일 후 자동 삭제합니다.

## 5분 데모 (하드웨어 없이)

```bash
git clone https://github.com/eduoneq/exam-uncheat && cd exam-uncheat
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# 1) 오프라인 데모: 빈 교실 → 스마트안경 → Wi-Fi Direct → 핫스팟 → 이어버드
exam-uncheat demo --scenario all --decide
exam-uncheat verify data/sessions/*          # 해시 체인 검증

# 2) 허브 + 감독관 콘솔 (http://127.0.0.1:8765)
exam-uncheat hub
#   콘솔에서 ① 세션 시작 → (다른 터미널) 리플레이 → 자동으로 ② 시험 시작
exam-uncheat replay scenarios/all.jsonl --speed 20
```

## 실제 센서 연결

```bash
# ESP32 (firmware/esp32-sniffer, USB 시리얼 NDJSON)
exam-uncheat hub --serial /dev/ttyACM0:115200 --serial /dev/ttyACM1:115200 --room 301
```
- 다른 장비: [어댑터 규격](docs/ADAPTER_SPEC.md)대로 줄단위 JSON을 시리얼·WebSocket(`/ws/ingest`)·HTTP(`POST /api/v1/events`)로 보내면 됩니다.
- 데이터 출력이 없는 상용 탐지기: 콘솔의 "상용 탐지기 경보 수동 기록"으로 같은 타임라인에 남깁니다.

## 구성

```
src/exam_uncheat/        허브(FastAPI), 어댑터, 시그니처 엔진, 기준선 비교, 증거 원장, 보고서, 시뮬레이터
spec/               이벤트·시그니처·조치 JSON 스키마
signatures/         시그니처 DB (CC BY 4.0)
firmware/           ESP32 수신 전용 펌웨어 (S3·C6 빌드 확인, 실기기 미검증)
scenarios/          합성 시나리오 (무작위 로컬 주소만)
docs/               ARCHITECTURE, ADAPTER_SPEC, HARDWARE, LEGAL, LIMITATIONS
ext/                법적 권한 기관용 확장 지점 — 문서만
tools/              no_tx_check(송신 코드 차단), check_samples, rename
```

## 다른 도구와의 차이

| | 감독관 폰 앱 (예: KoriyoSCAN) | 단일 전용 탐지기 | 온라인/좌석 카메라 감독 | **exam-uncheat** |
| --- | --- | --- | --- | --- |
| 하드웨어 | 폰 1대 | 전용기 1종 | 카메라 | **교체 가능 (ESP32~SDR~상용기)** |
| Wi-Fi | AP 목록 | 제품별 | - | 프로브·단말·P2P·5 GHz (장비별) |
| 기록 | 제한적 | 제품별 | 영상 | **해시 체인 원장 + 감독관 조치 + 보고서** |
| 공개 | 코드 | 비공개 | 상용 | **코드·스키마·시그니처·하드웨어 사양** |

## 라이선스

- 코드: [Apache-2.0](LICENSE)
- 시그니처 DB·문서: [CC BY 4.0](LICENSE-CC-BY-4.0.txt)
- 자세한 고지: [NOTICE](NOTICE)

## 기여

[CONTRIBUTING.md](CONTRIBUTING.md) — 특히 **No-TX 정책**과 시그니처 제보 규칙(출처 필수)을 확인해 주세요. 보안 문제는 [SECURITY.md](SECURITY.md).

만든 곳: **EDUONEQ** · English: [README.en.md](README.en.md)
