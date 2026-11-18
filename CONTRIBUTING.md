# exam-uncheat에 기여하기

이슈 하나, 시그니처 한 줄, 오탐 제보 하나도 큰 도움이 됩니다. PR을 보내기 전에 아래 규칙만 확인해 주세요.

## No-TX 정책

이 프로젝트는 듣기만 합니다. 전파 송신, 재밍과 교란, 디인증(deauth), 프레임 주입, 가짜 AP나 가짜 광고는 어떤 형태로도 받지 않습니다. BLE 능동 스캔(스캔 요청 송신)과 광고, 기기 연결 시도, 프로브 요청을 보내는 Wi-Fi 능동 스캔도 마찬가지입니다. 통신 내용 복호화, 데이터 프레임 페이로드 저장, 얼굴 인식, 클라우드 업로드를 기본값으로 켜는 변경도 받지 않습니다.

코드에서 이런 구조가 보이면 `python tools/no_tx_check.py`가 CI를 실패시킵니다. 문서(`*.md`)에서 개념을 설명하는 것은 괜찮습니다. 난독화나 문자열 조합으로 검사를 피해 가려는 PR은 닫습니다.

## 시그니처 제보

시그니처는 `signatures/*.yaml`에 추가하고 `spec/signature.schema.json` 검사를 통과해야 합니다. `sources`에는 출처 URL을 꼭 넣어 주세요. 회사 ID와 UUID는 [Bluetooth SIG 등록부](https://bitbucket.org/bluetooth-SIG/public/src/main/assigned_numbers/)와 맞춰 봅니다.

AGPL이나 GPL 프로젝트의 코드와 데이터 파일은 복사하지 말고 회사 ID 같은 사실값만 직접 적어 주세요. `verified_by`에는 확인한 방법을 `literature`(문헌), `heuristic`(관행), `bench`(실험실), `field`(현장) 가운데 하나로 쓰고 근거는 PR 설명에 남겨 주세요. 기여한 시그니처는 CC BY 4.0으로 배포됩니다.

## 샘플 데이터

실제 기기 주소가 담긴 녹화 파일은 올리지 마세요. 전역(벤더 할당) MAC이 보이면 `tools/check_samples.py`가 실패합니다.

## 개발 환경

```bash
pip install -e ".[dev]"
pytest -q
python tools/no_tx_check.py
```

## 이름 바꾸기

포크해서 이름을 바꾸려면 `python tools/rename.py NEW-NAME` 한 번으로 패키지, CLI, 문서의 이름을 함께 바꿀 수 있습니다.
