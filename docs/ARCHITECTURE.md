# exam-uncheat 아키텍처

```mermaid
flowchart LR
  subgraph Sensors["센서 (교체 가능, 수신 전용)"]
    E1["ESP32-S3/C6/C5"]
    E2["Linux + 모니터 모드 어댑터"]
    E3["nRF52840 BLE 스니퍼 (로드맵)"]
    E4["SDR 대역 에너지 (로드맵)"]
    E5["상용 탐지기 / 감독관 수동 입력"]
  end
  E1 -->|USB 시리얼 NDJSON| A1["SerialNDJSONAdapter"]
  E2 -->|NDJSON / HTTP| A2["드라이버 프로세스"]
  E3 & E4 -->|WebSocket / HTTP| A2
  E5 -->|콘솔| A3["manual-alert API"]
  subgraph Hub["허브 (로컬, 오프라인)"]
    V["스키마 검증·정규화"] --> S["시그니처 매칭 (원문, 메모리 안)"] --> P["Privacy Gate (HMAC 가명화·마스킹)"]
    P --> B["기준선 / 시험 비교 (Engine)"] --> C["단서 Clue"]
    P --> L[("해시 체인 원장 ledger.jsonl")]
    C --> L
    C --> W["감독관 콘솔"]
    W -->|조치 기록| L
    L --> R["보고서 MD/HTML · SHA256SUMS"]
  end
  A1 & A2 & A3 --> V
  X["ext/authorized-countermeasure (문서만, 코드 없음)"]:::warn
  classDef warn fill:#fde2e1,stroke:#c0392b;
```

## 처리 순서 (`Session.ingest`)
1. **검증** — `spec/event.schema.json` (draft 2020-12). 실패한 이벤트는 원장에 남기지 않고 거부 카운트만 올림
2. **정규화** — `event_id`, `ts`(허브 시각), UUID 소문자화, 제조사 데이터 32바이트로 자르기
3. **시그니처 매칭** — 원문 이름·SSID가 필요하므로 가명화 *전* 메모리 안에서만 수행
4. **Privacy Gate** — 주소 → `pid = HMAC-SHA256(session_key, addr)[:16]`, 전역 주소만 OUI 유지, SSID·기기 이름 마스킹
5. **원장 기록** — `{"seq","type","ts","data","prev","h"}`, `h = sha256(prev + canonical(seq,type,ts,data))`
6. **엔진** — 신호 묶음(group) 단위로 빈 교실 기준선과 비교
   - 묶음 키: 시그니처 일치 시 시그니처 ID(주소 순환에도 같은 묶음), 아니면 BLE 회사ID+서비스, AP는 SSID 가명 등
   - 새 묶음 또는 서로 다른 기기 수가 기준선보다 많으면 후보 → 20초 이상 지속(또는 high 시그니처 3회 이상)이면 단서
   - 점수 = 시그니처 가중치 (+10 강한 신호). 25 이상 확인 권장, 70 이상 즉시 확인 권장. 최고 RSSI가 -85 dBm보다 약하면 항상 "참고"
   - 조합 규칙: 스마트안경 BLE 단서와 Wi-Fi Direct 단서가 180초 안에 함께 나오면 "즉시 확인 권장"
   - 등급은 자동으로 내려가지 않음
7. **세션 종료** — 보고서 생성 → `SHA256SUMS` → 세션 키 폐기

## 세션 폴더
```
data/sessions/<날짜>_<시험장>_<고사실>_<교시>_<id>/
  manifest.json  ledger.jsonl  baseline.json  report.md  report.html  SHA256SUMS
```
