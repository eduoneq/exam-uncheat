# exam-uncheat 보안 정책

## 제보 방법

보안 취약점이나 개인정보가 새는 문제를 찾았다면 공개 이슈 대신 GitHub Security Advisories로 비공개 제보를 해 주세요. 저장소의 Security 탭에서 Report a vulnerability를 누르거나 아래 주소로 바로 들어가면 됩니다.

https://github.com/eduoneq/exam-uncheat/security/advisories/new

## 제보 대상

허브 API와 콘솔의 취약점, 가명 처리나 원장 위변조 탐지를 우회하는 방법, 송신이나 공격 기능이 끼어들 수 있는 경로(No-TX 정책 위반)를 받습니다. v0.1 허브에는 인증이 없고 기본으로 127.0.0.1에만 바인딩합니다.

## v0.1에서 알고 있는 제한

허브에 인증과 TLS가 없습니다. 교실 안 단일 기기나 격리된 유선망에서만 써 주세요. 원장은 위변조를 찾아내는 용도이고 전자서명이나 타임스탬프 기관 연동은 아직 없습니다.
