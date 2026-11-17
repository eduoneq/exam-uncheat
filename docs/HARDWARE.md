# exam-uncheat 하드웨어 사양 (v0.1)

- 작성: 2026-11-17 (KST). 가격은 **모두 대략치**이며 같은 날 웹에서 확인한 판매가다. 재고·환율·부가세 포함 여부가 판매처마다 다르니 구매 전 다시 확인할 것
- 원칙: 모든 장비는 **수신 전용으로만** 사용한다. 송신 가능한 장비(HackRF 등)도 exam-uncheat 드라이버는 수신 명령만 쓴다
- 이 문서의 "탐지"는 **신호가 있다는 단서**를 뜻한다. 부정행위 여부를 판정하지 않는다

---

## 0. 한눈에 보기

| 티어 | 구성 | 교실당 대략 비용 | 보는 것 | 못 보는 것 |
| --- | --- | --- | --- | --- |
| **최소 (Minimum)** | 기존 노트북(허브) + ESP32-S3 또는 ESP32-C6 보드 1~2개 | **약 1.5만~5만원** | BLE 광고(연속), 2.4 GHz Wi-Fi 관리 프레임(프로브 요청·비콘·P2P), 2.4 GHz 데이터 프레임 활동 통계 | 5 GHz, 클래식 블루투스, 연결된 BLE 트래픽, LTE/5G |
| **권장 (Recommended)** | 라즈베리파이 5(또는 노트북) + ESP32-C5 보드 1~2개 + MT7612U 모니터 모드 USB 어댑터 1개 | **약 35만~50만원** (파이 포함) / 약 15만~20만원 (노트북 재사용) | 최소 티어 + **5 GHz** 프로브·비콘·단말 활동, Wi-Fi Direct 그룹, 채널별 혼잡도, 교실 앞/뒤 RSSI 비교 | 클래식 블루투스, 연결된 BLE 트래픽, LTE/5G 내용 |
| **고급 (Advanced, 실험)** | 권장 + nRF52840 동글(BLE 스니퍼) + SDR(HackRF One / RTL-SDR V4) 또는 시리얼 스펙트럼 장비(tinySA Ultra / RF Explorer) | **추가 약 3만~80만원** | BLE 연결 시작 순간 추적(조건부), 2.4/5 GHz 대역 에너지, sub-GHz 무전·FM 송신기 에너지(RTL-SDR) | 암호화된 내용, 전원 꺼진 기기, 유선·자기유도 장치 |

v0.1 레퍼런스: **최소 = ESP32-S3-DevKitC-1, 권장 = ESP32-C5-DevKitC-1 + MT7612U 어댑터.** 고급 장비는 "실험". **v0.1은 실물 하드웨어로 검증하지 않았고 시뮬레이터·리플레이로만 검증했습니다.**

---

## 1. 최소 티어 (Minimum)

### 1.1 구성
| 부품 | 권장 모델 | 대략 가격 (확인일 2026-11-17) | 비고 |
| --- | --- | --- | --- |
| 센서 | **ESP32-S3-DevKitC-1** (N8/N16R8) | 약 13,000~18,000원 — VCTEC N16R8 13,000원대(VAT 별도), 디바이스마트 호환 16,500원(VAT 별도), 메카솔루션 18,000원(VAT 포함) | 모듈 ESP32-S3-WROOM-1은 국립전파연구원 적합등록 R-R-es5-ESP32S3WROOM1 ([Espressif KCC 문서](https://documentation.espressif.com/ESP32-S3-WROOM-1%20KCC%20Certification.pdf)) |
| 센서(대안) | **ESP32-C6-DevKitC-1-N8** | 약 14,000~24,000원 — 디바이스마트 14,070원(VAT 별도), 메카솔루션 정품 24,000원(VAT 포함) | Wi-Fi 6(2.4 GHz), BLE 5 |
| 센서(최저가) | ESP32 DevKitC (WROOM-32D) | 약 7,000~9,000원 (디바이스마트) | 구형. 시험용·교육용 |
| 허브 | 기존 노트북 (Windows/macOS/Linux, Python 3.11) | 0원 (보유 장비) | 허브 자체 Wi-Fi·블루투스는 꺼 둘 것 |
| 케이블 | USB-C **데이터** 케이블 1~3 m | 수천 원 | 충전 전용 케이블은 시리얼이 안 됨 |

가격 출처: [VCTEC ESP32-S3-DevKitC-1 N16R8](https://vctec.co.kr/product/esp32-s3-devkitc-1-%EB%B3%B4%EB%93%9C-usb-c-n16r8esp32-s3-devkitc-1-board-usb-c-n16r8/26620/), [디바이스마트 ESP32-S3 N16R8](https://www.devicemart.co.kr/goods/view?no=15028272), [메카솔루션 ESP32-S3 N16R8](https://www.mechasolution.com/goods/goods_view.php?goodsNo=608587), [디바이스마트 ESP32-C6-DevKitC-1-N8](https://www.devicemart.co.kr/goods/view?no=15401248), [메카솔루션 ESP32-C6-DevKitC-1](https://www.mechasolution.com/goods/goods_view.php?goodsNo=604891), [디바이스마트 ESP32 카테고리](https://www.devicemart.co.kr/goods/catalog?code=000500040007)

### 1.2 할 수 있는 것
- **BLE 광고 연속 수신(패시브 스캔)** — 폰 앱처럼 화면 꺼짐·OS 제한으로 멈추지 않음. 회사 ID·서비스 UUID·제조사 데이터·이름을 시그니처 DB와 대조
- **2.4 GHz Wi-Fi 무차별(promiscuous) 수신** — ESP-IDF 스니퍼 모드는 관리·데이터·제어 프레임을 앱으로 넘겨준다([ESP-IDF Wi-Fi Sniffer Mode](https://docs.espressif.com/projects/esp-idf/en/stable/esp32c5/api-guides/wifi-driver/wifi-modes.html)). exam-uncheat 펌웨어는 **관리 프레임(프로브 요청·비콘·P2P)만 해석**하고, 데이터 프레임은 송신 주소·개수·길이·RSSI만 센 뒤 페이로드를 버린다
- 채널 호핑(1~13ch)으로 교실 내 2.4 GHz 활동 파악

### 1.3 못 하는 것
- **5 GHz 불가** (S3·C6는 2.4 GHz 전용)
- **클래식 블루투스(BR/EDR) 불가** (S3·C6는 BLE만) — 구형 이어버드·핸즈프리 일부를 놓칠 수 있음
- 이미 연결된 BLE 기기의 통신(광고 중단된 페어링 안경 포함)
- 한 칩이 BLE와 Wi-Fi를 같은 무선부로 번갈아 쓰므로, 둘 다 켜면 각각 놓치는 패킷이 늘어난다 → **가능하면 보드 2개(BLE 전용 1, Wi-Fi 전용 1)** 권장
- 채널 호핑 중에는 다른 채널의 짧은 신호를 놓친다
- LTE/5G, 유선, 자기유도 루프, 전원 꺼진 기기

---

## 2. 권장 티어 (Recommended)

### 2.1 구성
| 부품 | 권장 모델 | 대략 가격 | 비고 |
| --- | --- | --- | --- |
| 센서 | **ESP32-C5-DevKitC-1** (N8R8 등) | 약 22,800원 (아이씨뱅큐 N8R8) / 소형 Seeed XIAO ESP32-C5 약 10,800~11,100원 (아이씨뱅큐·디바이스마트, 약 6일 배송) | **2.4 + 5 GHz 듀얼밴드 Wi-Fi 6 + BLE 5**. 스니퍼 모드에서 5 GHz 채널(36~165) 호핑 가능 |
| 허브 | **Raspberry Pi 5** (4GB 또는 8GB) + 공식 27W 전원 + microSD/SSD + 케이스 | 8GB 본체만 약 18만~32만원 (판매처별 편차 큼: 퍼스트봇 180,000원, 임베디드코리아 240,000원, 엘레파츠 293,000원, 아이씨팩토리 320,100원) | 노트북으로 대체 가능 |
| Wi-Fi 모니터 모드 어댑터 | **ALFA AWUS036ACM** 또는 Panda PAU0D (**MT7612U**) | AWUS036ACM 약 11.7만~14.3만원 (다나와 해외배송 리스팅 116,570원, 프리쉽 구매대행 142,800원·5~14일) | 리눅스 커널 내장 mt76 드라이버(4.19+), 모니터 모드·Active monitor·VIF 지원. **1순위** |
| 대안 어댑터 | ALFA AWUS036AXML 등 **MT7921AU** | 다나와 리스팅 약 17.8만원부터 | 2.4/5/6 GHz. 커널 6.17~6.18에서 모니터 모드 회귀 버그, **6.19.8에서 수정** 보고 → 커널 버전 확인 필수 |
| 대안 어댑터 | ALFA AWUS036ACH 등 **RTL8812AU** | 다나와 리스팅 약 17.8만~28만원 | 커널 6.14+ 내장 rtw88로 모니터 모드 가능, Active monitor·VIF 미지원. 구형 외부 드라이버는 비권장 |

어댑터 근거: [morrownr/USB-WiFi 칩셋 표](https://github.com/morrownr/USB-WiFi/blob/main/home/USB_WiFi_Chipsets.md), [morrownr 모니터 모드 권장 어댑터](https://github.com/morrownr/USB-WiFi/blob/main/home/Recommended_Adapters_for_Kali_Linux.md), [StationX 2026-11 업데이트(MT7921AU 회귀·6.19.8 수정)](https://app.stationx.net/articles/best-wifi-adapters-for-kali-linux)
가격 출처: [아이씨뱅큐 XIAO ESP32-C5](https://www.icbanq.com/P016998683), [아이씨뱅큐 ESP32-C6/C5 카테고리](https://www.icbanq.com/A02_product/productList.do?cateCode=101144140114), [디바이스마트 XIAO 카테고리](https://www.devicemart.co.kr/goods/catalog?code=000500040012), [퍼스트봇 Pi 5](http://www.firstbot.co.kr/goods/goods_view.php?goodsNo=1000000646), [임베디드코리아 Pi 5](https://eku.co.kr/product/%EB%9D%BC%EC%A6%88%EB%B2%A0%EB%A6%AC%ED%8C%8C%EC%9D%B4-5-raspberry-pi-5-model-8gb-16gb/14/category/1/display/2/), [엘레파츠 라즈베리파이](https://eleparts.co.kr/promotion/cate_event?event_seq=1622), [아이씨팩토리 Pi 5 8GB](https://icfactory.co.kr/product/%EC%A0%95%ED%92%88-%EB%9D%BC%EC%A6%88%EB%B2%A0%EB%A6%AC%ED%8C%8C%EC%9D%B45-raspberry-pi-5-8gb/1240/), [다나와 AWUS036 검색](https://search.danawa.com/dsearch.php?query=AWUS036), [프리쉽 AWUS036ACM](https://mall.freeship.co.kr/goods/content.asp?cate=12552&guid=8995681)

> 라즈베리파이 내장 Wi-Fi(CYW43455)는 기본적으로 모니터 모드가 안 되지만, Kali 2025.1 이후 Nexmon 패키지로 Pi 5 포함 모니터 모드가 가능하다고 Kali가 밝혔다([Kali 블로그 2025-07-22](https://www.kali.org/blog/raspberry-pi-wi-fi-glow-up/)). 다만 Kali 문서도 "항상 안정적이지는 않다"고 적고 있어 **exam-uncheat는 외장 MT7612U 어댑터를 권장**하고 내장 Nexmon은 실험 옵션으로만 둔다.

### 2.2 할 수 있는 것 (최소 티어에 더해)
- **5 GHz 프로브 요청·비콘·단말 활동** (C5, MT7612U)
- **AP에 붙은 단말(STA) 존재와 활동량** — 핫스팟을 끄고 기존 AP에만 붙은 카메라·폰도 데이터 프레임 통계로 보인다(내용은 저장 안 함)
- **Wi-Fi Direct(P2P) 그룹** — 스마트안경이 미디어 전송·라이브뷰에 Wi-Fi Direct를 쓴다는 커뮤니티 역분석 자료가 있음([Meta glasses protocol, 비공식](https://visor.macedonga.com/protocol/radios-and-links/)). **벤치·현장 검증 전 가설**
- 센서 2개를 교실 앞·뒤에 두고 RSSI를 비교해 "어느 쪽에 가까운지" 정도의 힌트

### 2.3 못 하는 것
- 클래식 블루투스 수신, 연결된 BLE 트래픽 내용
- 정확한 좌석 위치(RSSI는 사람·책상·벽에 크게 흔들림)
- 6 GHz(MT7921AU는 가능하지만 v0.1 미지원)
- 암호화된 Wi-Fi 내용(복호화하지 않으며 해서도 안 됨)

---

## 3. 고급 티어 (Advanced, 실험)

| 장비 | 사양(확인됨) | 대략 가격 | exam-uncheat에서의 용도 | 한계·주의 |
| --- | --- | --- | --- | --- |
| **Nordic nRF52840 Dongle (PCA10059)** | Nordic **nRF Sniffer for Bluetooth LE** 공식 지원 보드. LE 2M·Coded PHY 지원 ([Nordic 지원 보드 표](https://docs.nordicsemi.com/r/bundle/nrfutil/page/nrfutil-ble-sniffer/wireshark_sniffer_requirements.html/supported-development-kits-and-dongles)) | 약 4.6만원 (VCTEC 42,000원 VAT 별도, 2026-11-17 확인), DigiKey 17.68달러 | 광고 + **연결 시작 패킷을 잡은 경우** 해당 연결 추적 → `ble.conn_activity` | 이미 맺어진 연결은 따라가기 어렵다. 스니퍼 펌웨어는 Nordic 라이선스(Nordic 칩 전용) → **저장소에 재배포하지 않고** 사용자가 nRF Util로 설치. 디바이스마트의 "nRF52840 MDK USB Dongle"(약 23,760원)은 다른 제품(makerdiary)이라 Nordic 스니퍼 공식 지원 목록에 없음 [확인 필요] |
| **HackRF One** | 1 MHz~6 GHz, 순간 대역폭 최대 20 MHz, 8비트, **반이중 송신 가능** ([SDRmm 비교표](https://sdrmm.com/docs/hardware)) | 약 37.4만원(VCTEC 해외, VAT 별도) ~ 75.1만원(디바이스마트, VAT 별도) / 미국 339.95달러 | `hackrf_sweep`으로 2.4/5 GHz **대역 에너지** 지도 → `rf.energy`. 기준선 대비 점유율 변화 | Wi-Fi/BLE 해독 아님. 필터 없는 광대역 프런트엔드라 강한 신호에 취약. **송신 기능은 절대 사용 금지**(무선국 허가 없는 송신은 전파법 위반 소지). 저가 복제품 다수 |
| **RTL-SDR Blog V4** | 500 kHz~1.766 GHz, 안정 대역폭 2.56 MHz, **송신 불가** ([RTL-SDR V4 데이터시트](https://www.rtl-sdr.com/wp-content/uploads/2024/12/RTLSDR_V4_Datasheet_V_1_0.pdf)) | 국내 약 7.9만원(옥션 리스팅, 정품 여부 확인 필요) ~ 17.2만원(안테나 키트, 로봇사이언스몰, 품절) / 미국 V4L 37.95달러 | sub-GHz 무전기·FM/UHF 음성 송신기 등 **2.4 GHz 밖 송신 장치의 에너지** | **2.4 GHz·5 GHz Wi-Fi/BLE는 못 본다.** 이동통신은 일부 대역의 에너지만, 내용 해독은 하지 않음 |
| **tinySA Ultra** | Ultra 모드에서 6 GHz까지(5.35 GHz 이상은 하모닉 모드), **USB 시리얼 명령**(`scan`, `scanraw` 등) 제공 ([tinySA Ultra 모드](https://tinysa.org/wiki/pmwiki.php?n=TinySA4.Ultra), [USB 인터페이스](https://tinysa.org/wiki/pmwiki.php?n=Main.USBInterface)) | 국내가 미확인 | "시리얼 출력이 있는 상용 스펙트럼 장비" 레퍼런스 → `serial-generic` 드라이버 | 대역 에너지만 |
| **RF Explorer 6G Combo** | 15–2700 MHz + 4.85–6.1 GHz, **UART API 공개** ([RF Explorer UART API](https://github.com/RFExplorer/RFExplorer-for-.NET/wiki/RF-Explorer-UART-API-interface-specification)) | Seeed 365달러 ([Seeed](https://www.seeedstudio.com/RF-Explorer-6G-Combo-p-2197.html)) | 상용 휴대형 분석기 연동 레퍼런스 | 대역 에너지만 |
| **데이터 출력 없는 상용 전파탐지기** | — | — | 감독관 콘솔의 **수동 입력**(`detector.alert`, `manual: true`)으로 같은 타임라인에 기록 | 자동 연동 불가. 모델별 시리얼 출력이 있으면 드라이버 추가 |

가격 출처: [VCTEC nRF52840 동글](https://vctec.co.kr/product/nordic-nrf52840-usb-%EB%8F%99%EA%B8%80-%EB%B8%94%EB%A3%A8%ED%88%AC%EC%8A%A4-5-%EB%A9%94%EC%89%AC-%EC%A7%80%EA%B7%B8%EB%B9%84-ant-nordic-semiconductor-nrf52840/16729/), [DigiKey nRF52840 Dongle](https://www.digikey.com/en/product-highlight/n/nordic-semi/nrf52840-usb-dongle), [디바이스마트 MDK 동글](https://www.devicemart.co.kr/goods/view?no=6500552), [VCTEC HackRF One](https://vctec.co.kr/product/%ED%95%B4%EC%99%B8hackrf-one-%EC%86%8C%ED%94%84%ED%8A%B8%EC%9B%A8%EC%96%B4-%EC%A0%95%EC%9D%98-%EB%AC%B4%EC%84%A0-%EC%9E%A5%EC%B9%98-hackrf-one/5419/), [디바이스마트 HackRF One](https://www.devicemart.co.kr/goods/view?no=1290025), [로봇사이언스몰 RTL-SDR V4](https://m.robotscience.kr/goods/view?no=23272), [퍼니즈 RTL-SDR V4](https://funiz.com/goods/18891938), [poc-radio 가격표(2026-10-18)](https://poc-radio.com/learn/sdr/)

---

## 4. 허브 최소 사양

| 항목 | 최소 | 권장 |
| --- | --- | --- |
| 장치 | 64비트 노트북/미니PC, 또는 Raspberry Pi 4 (4GB) | Raspberry Pi 5 (4GB 이상) 또는 노트북 |
| OS | Windows 10+/macOS 13+/Linux (ESP32 시리얼만 쓸 때) | 모니터 모드 어댑터 사용 시 **Linux 필수**, 커널 6.x (MT7921AU는 6.19.8 이상) |
| 런타임 | Python 3.11 | 동일 |
| 저장 | 여유 2 GB | SSD 권장(로그 쓰기 내구성) |
| USB | 센서 수만큼 (전원 공급 USB 허브 권장) | 동일 |
| 네트워크 | **불필요.** 교실에서 허브 Wi-Fi·블루투스는 끈다 | 대시보드는 허브 화면 또는 유선/USB 연결 태블릿 |
| 시계 | 시험 전 표준시 맞춤(인터넷 가능한 장소에서 사전 동기화) | RTC 배터리(파이 5 지원) |

---

## 5. 교실 배치·전원

**배치(일반 교실 1개 기준, 권고안 — 현장 검증 전)**
- 센서 A: **교탁**(앞), 바닥에서 약 1~1.5 m 높이. 금속 캐비닛·모니터 바로 옆 피하기
- 센서 B(권장 티어): **교실 뒤편 중앙** → 앞·뒤 RSSI 비교로 대략적 방향
- 모니터 모드 어댑터: 허브에 USB 연장선으로 연결, 안테나 세워서 교실 중앙 방향
- 수거한 휴대전화 보관 장소는 **교실 밖**(페어링된 안경은 폰이 근처에 있어야 동작 — 운영 문서에 명시). 교실 안 보관 시 기준선·단서가 크게 오염됨
- 빈 교실 기준선은 **수험생 입실 전 2~5분**, 실제 시험과 같은 센서 위치·채널 계획으로 측정
- 복도·옆 교실 신호가 섞이므로 **약한 신호(RSSI 임계값 이하)는 기본 "참고" 등급**

**전원(대략치·추정)**
| 장비 | 전원 | 비고 |
| --- | --- | --- |
| ESP32 보드 | USB 5 V. 수신 상태에서 대략 0.5 W 이하로 추정 [확인 필요: 보드별 데이터시트] | 10,000 mAh 보조배터리로 한 시험일 충분할 것으로 추정 |
| Raspberry Pi 5 | 공식 27 W(5.1 V/5 A) USB-C 전원 권장 | USB 장치에 충분한 전류를 주려면 정격 전원 필요 |
| MT7612U 어댑터 | 허브 USB 버스 전원 | USB 3.0 포트 권장 |
| HackRF One | USB 버스 전원, 대략 2.5~3.5 W ([homelabinsider](https://homelabinsider.com/difference-between-rtlsdr-v4-and-hackrf-one/)) | 전원 공급 USB 허브 권장 |
| RTL-SDR V4 | USB, 250~270 mA ([데이터시트](https://www.rtl-sdr.com/wp-content/uploads/2024/12/RTLSDR_V4_Datasheet_V_1_0.pdf)) | — |

케이블은 USB 2.0 기준 5 m 이내, 통로를 지나는 케이블은 고정(안전).

---

## 6. 전파법·KC(적합성평가) 메모

> 법률 자문이 아니다. 기관 도입·판매 전에는 국립전파연구원 확인 또는 전문가 검토가 필요하다.

1. **수신 전용 사용.** exam-uncheat 펌웨어·드라이버는 송신 API를 쓰지 않는다(CI의 No-TX lint로 강제). BLE는 패시브 스캔이라 스캔 요청(SCAN_REQ)도 보내지 않는다. HackRF의 송신 기능은 사용 금지.
2. **재밍 장비와 연동하지 않는다.** 전파법 제29조③의 전파차단장치 사용 예외(경호·군사·대테러·공항·원자력시설 방호 등)에 시험장은 없다. 제29조⑧·제84조 1의2호: 인가 없이 전파차단장치를 제조·수입·판매하면 3년 이하 징역 또는 3천만원 이하 벌금([LawPlayer 제29조](https://lawplayer.com/kr/article/001732/002900), [LBOX 제84조](https://lbox.kr/statute/%EC%A0%84%ED%8C%8C%EB%B2%95/%EB%B3%B8%EB%AC%B8%20%3E%20%EC%A0%9C9%EC%9E%A5%20%3E%20%EC%A0%9C84%EC%A1%B0)).
3. **KC 적합성평가.** 적합성평가를 받지 않은 기자재를 판매하거나 판매 목적으로 제조·수입하면 제84조 5호 처벌 대상. 
   - 개인이 판매 목적 없이 쓰려고 반입하는 기자재는 **모델당 1대** 면제(반입 후 1년 내 판매하면 면제 안 됨). 시험·품질검사용, 연구개발용은 별도 수량·서류 면제 제도가 있다([국립전파연구원 FAQ](https://www.rra.go.kr/ko/notice/D_e_faq2_1.do?fa_category=compt&fa_type=b), [요건면제 안내](https://www.rra.go.kr/ko/popup/popup_100430.jsp)).
   - **실무 권고:** 기관·학교는 **국내 정식 유통·KC 표시 제품**을 산다. 해외 직구·구매대행 어댑터(예: 다나와 "해외" 리스팅)는 개인 실험용으로만.
   - ESP32-S3-WROOM-1 **모듈**은 적합등록(R-R-es5-ESP32S3WROOM1)이 있으나, 모듈 인증이 **완제품(개발보드·키트) 판매까지 자동으로 덮는지는 별개** [확인 필요]. EDUONEQ가 키트를 묶어 판매하려면 완제품 기준 적합성평가 검토가 먼저다.
   - 각 제품의 등록 여부는 [국립전파연구원 인증현황 검색](https://www.rra.go.kr/ko/license/A_b_popup_keyno.do?key_no=N)에서 모델명으로 확인.
4. **시험장 반입 규정.** 수능 고사장은 감독관도 전자기기 반입·소지가 금지된다는 보도가 있다([매일경제 2023-11-17](https://www.mk.co.kr/news/society/10877949)). 센서·허브 설치는 **시험 시행기관의 사전 승인**이 전제다.

---
