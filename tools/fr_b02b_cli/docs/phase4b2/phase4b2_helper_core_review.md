# Phase 4B-2 B안 인증·요청 경계 Core

2026-11-11 KST. 기준: `feat/phase4b2-protected-review-registration`,
`9570efc515d22144bbf424b23df98f24113f7a42`, AGENTS.md v1.1,
Phase 4B-2 FROZEN v1.0 및 이번 작업에서 승인된 B안 Core 격리 구현 범위.
이 문서는 설계 동결 변경 또는 운영 활성화 승인이 아니다.

## 구현 범위

- `fr_b02b_helper_core.py`는 공개 CLI에서 호출하지 않는 내부 경계다.
  등록은 검토 메타데이터와 A1/4A 세 파일의 불변 바이트만,
  철회는 등록 ID·등록 지문·철회자 SID 주장·사유만 받는다.
  임의 작업명·경로·ACL·보호 루트·최종 ID 지정·복구 명령은 받지 않는다.
  이 Python 객체 계약은 IPC wire format 확정안이 아니다.
- 등록 입력은 기존 A1/4A·pending 검증기를 재사용하여 전체 바이트와
  증거 ID·다이제스트·판단·시각 연결을 검사한다. HOLD/REJECTED를 보존하고
  게시 권한은 NONE이다. 일반 프로세스의 사람 판단 수집은 변경하지 않는다.
- 본문의 SID는 신원 주장일 뿐이다. 신뢰된 bootstrap에서 주입한
  `RequestAuthenticator`가 별도 인증 scope의 `AuthenticatedPeer`를 제공해야 한다.
  SID 문자열 또는 helper 자체 프로세스 SID를 인증 대체값으로 받지 않는다.
  OS 인증을 수행하는 구체 provider·생성자·fallback·환경변수는 없다.
- 실제 요청자 SID와 본문 SID의 정확한 일치, 보호 허용 목록, live peer,
  입력 연결 및 시계를 생성 전후 재검증한다. helper 실행 계정은 검토자로
  기록하지 않는다. 인증 실패와 중간 실패는 범주 오류 BLOCKED/HOLD이며,
  명시적 취소는 ReviewCancelled다. 부분 결과는 삭제·복구·자동 승격하지 않는다.
- `ProtectedCreationBoundary.exclusive_section()`만 전역 Gate를 소유한다.
  `CreationSession`은 추가 Gate를 획득하지 않고 apply/verify를 수행한다.
  Core의 Lock은 인스턴스 재진입/재사용 방지용이며 Native Gate 대체가 아니다.
  실패·취소 시에도 인스턴스는 재사용하지 않는다.
- 성공 반환은 apply, 독립 verify, 모든 checkpoint, Gate 및 인증 scope 해제가
  끝난 뒤 내부 BoundaryReceipt로만 한다. 공개 등록 성공이나 운영 등록 ID가 아니다.

## 향후 adapter가 반드시 구현할 책임

이 책임은 추상 인터페이스와 Double의 상호작용으로만 시험했다. 현재 파일이
실제 보호 저장이나 OS 인증을 보장한다고 해석하면 안 된다.

1. 인증 provider: OS 인증된 연결/token의 생명주기 유지, 요청과 동일 연결에
   결속, 연결 종료·취소·신원 변경 감지. 본문 SID와 관리자 token을 요청자
   인증에 사용하지 않는다.
2. 생성 session: 단독 Native Gate 아래 전체 이력·중복·철회 상태 재조회,
   동일 증거/바이트 재사용, 다른 증거 충돌 차단, 철회된 관측 자동 재활성화 금지.
   Core의 일회성 인스턴스는 프로세스 간 replay 방어를 대신하지 않는다.
3. 철회: 보호 이력에서 유효 ACCEPTED 등록을 읽고 요청 등록 지문과 정확히
   결속한 후 추가 전용 사건을 생성한다. 요청 지문만으로 등록을 신뢰하지 않는다.
4. 보호 생성 및 검증: 각 변경 전후 checkpoint, 원본/백업·복원 검증,
   최종 객체와 신뢰 인벤토리의 보호 생성 및 독립 재대조. 잔재는 HOLD로 보존한다.
   verify는 요청과 실제 결과의 결속까지 검사해야 한다.

## Blocking 및 미실측 항목

- FROZEN §4.2의 관리자 상승 범위 변경 통제 및 운영 활성화 승인.
- Named Pipe의 실제 OS 인증·token/연결 수명·메시지 framing/크기 제한·
  연결과 요청 결속·전송 중 교체/재전송/단절/취소 정책. wire format은 미확정이다.
- helper 실행 주체의 승인된 SID/ACL/경로와 신뢰 bootstrap.
  기존 `StorePolicy.reviewer_sid` 및 Native checkpoint는 helper 실행자와
  검토자를 분리하지 않는다. 이를 그대로 B안 adapter로 사용하면 안 된다.
- 기존 등록/철회 Core는 프로세스 SID 획득과 Gate 소유를 포함한다.
  이를 HelperRequestCore 내부에서 그대로 호출하면 신원 혼동 또는 Gate 중첩이
  생길 수 있으므로 실제 연결 전 책임 분리·통합 검증이 필요하다.
- 실제 C/E·SYN-05, Windows IPC/UAC, 일반/관리자 계정, ACL 생성 권한,
  final inventory, 경쟁 요청·재시작·크래시·부분 쓰기 후 재검증 실측.

실제 IPC/UAC/Native 생성 adapter, 공개 CLI, 운영 설정 및 FROZEN 문서는
변경하지 않았다. 이 Core 시험 통과는 Phase 4B-2 기능 완료 또는 운영 PASS가 아니다.

## 검증 기록

작업 디렉터리: `tools/fr_b02b_cli/`, Python 3.14.

- 최초 신규 9개 실행: 인증 SID와 본문 SID가 서로 다르지만 둘 다 허용된 경우의
  테스트가 `ReviewBlocked not raised`로 실패했다. 정확한 SID 일치 검사 후 9개 통과.
- `python -B -m unittest discover -s tests -q`: **379개 / 357.914초 / OK**.
  기존 370개와 당시 신규 9개를 포함한다.
- 이후 재진입·HOLD/REJECTED·중복 JSON 키·늦은 취소·scope 예외 억제·
  인증 scope 해제 실패 사례를 추가하고 인터페이스 타입을 명시했다.
  최종 `python -B -m unittest discover -s tests -p test_fr_b02b_helper_core.py -q`:
  **14개 / OK**. 최종 전체 384개를 다시 실행한 것으로 보고하지 않는다.
- tracked unstaged/staged `git diff --check` 통과. 새 파일 3개는 별도로
  Python AST 및 줄 끝 공백/마지막 개행 검사 통과.
- Ruff는 현재 Python에 설치되지 않아 미실행(`No module named ruff`).
- `git ls-remote --heads origin feat/phase4b2-protected-review-registration`은
  GitHub 연결 실패로 원격 최신 상태 미확인. 로컬 기준 커밋으로 검증했다.
- 기존 미추적 `docs/infra/` 보존. 기존 tracked 파일 변경 및 staged 변경 없음.
  신규 Core/테스트/이 메모 3개만 추가했으며 commit/push는 수행하지 않았다.
