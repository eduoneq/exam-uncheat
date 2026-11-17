# exam-uncheat 보안 정책

## 신고
보안 취약점이나 개인정보 노출 문제는 공개 이슈로 올리지 말고 **GitHub Security Advisories(비공개 취약점 제보)** 로 알려 주세요.
저장소의 **Security → Report a vulnerability** 메뉴에서 제보할 수 있습니다: https://github.com/eduoneq/exam-uncheat/security/advisories/new

## 범위
- 허브 API·콘솔의 취약점 (v0.1 허브는 인증이 없으며 기본적으로 127.0.0.1에만 바인딩합니다)
- 가명화 우회, 원장 위변조 탐지 우회
- 송신·공격 기능이 들어갈 수 있는 경로 (No-TX 정책 위반)

## 알려진 제한 (v0.1)
- 허브에 인증·TLS가 없습니다. 교실 안 단일 기기 또는 격리된 유선망에서만 쓰세요.
- 원장은 위변조 *탐지*용이며, 서명·타임스탬프 기관 연동은 아직 없습니다.
