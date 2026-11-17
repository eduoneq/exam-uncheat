# exam-uncheat 기여 안내

## No-TX 정책
이 프로젝트는 **수신 전용**입니다. 다음은 어떤 형태로도 받지 않습니다.
- 전파 송신·재밍·교란, 디인증(deauth), 프레임 주입, 가짜 AP/광고
- BLE 능동 스캔(스캔 요청 송신), 광고, 기기 연결 시도 / Wi-Fi 능동 스캔(프로브 요청 송신)
- 통신 내용 복호화, 데이터 프레임 페이로드 저장
- 얼굴인식, 클라우드 업로드 기본값

`python tools/no_tx_check.py`가 코드에서 위 구조를 찾으면 CI가 실패합니다. 문서(`*.md`)에서 개념을 설명하는 것은 괜찮습니다. 검사를 우회하는 PR(난독화·문자열 조합 등)은 닫습니다.

## 시그니처 제보
- `signatures/*.yaml`에 추가하고 `spec/signature.schema.json`을 통과해야 합니다.
- **출처 URL 필수**(`sources`). 회사 ID·UUID는 [Bluetooth SIG 등록부](https://bitbucket.org/bluetooth-SIG/public/src/main/assigned_numbers/)와 대조하세요.
- AGPL/GPL 프로젝트의 코드나 데이터 파일을 복사하지 마세요. 사실값(회사 ID 등)만 직접 기재합니다.
- `verified_by`: `literature`(문헌) / `heuristic`(관행) / `bench`(실험실 확인) / `field`(현장 확인). 확인 근거를 PR에 적어 주세요.
- 기여된 시그니처는 CC BY 4.0으로 배포됩니다.

## 샘플 데이터
- 실제 기기 주소가 담긴 녹화 파일을 올리지 마세요. `tools/check_samples.py`가 전역(벤더 할당) MAC을 찾으면 실패합니다.

## 개발
```bash
pip install -e ".[dev]"
pytest -q
python tools/no_tx_check.py
```

## 이름 변경
포크해서 이름을 바꿀 때는 `python tools/rename.py NEW-NAME`으로 패키지·CLI·문서 이름을 한 번에 바꿀 수 있습니다.
