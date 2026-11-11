# Phase 4B-2 Allowlist 리뷰 및 B42-04 구현 검증

2026-11-10 KST. 저장소 `Trend-Leader-capstoneProject/feature`, 브랜치 `feat/phase4b2-protected-review-registration`.
로컬 및 읽기 전용 재조회한 원격 HEAD: `8d49cb33e91b7a09def95084d54810b92132b32a`.

## A. 코드 리뷰

### 발견 사항 — 중간 심각도, 수정 완료

| 항목 | 내용 |
|---|---|
| 근거 위치 | `fr_b02b_reviewer_allowlist.py`의 `_require_protection()`(현재 43행), `require_authorized_sid()`의 설정 공급자 처리(현재 136행). 기존 `except Exception` 두 곳 및 파일 조회의 RuntimeError 변환. |
| 재현 | 보호 검증 또는 설정 공급자가 TypeError/AssertionError/RuntimeError를 발생시키면 프로그래밍 오류가 `AllowlistError`로 변환됐다. 추가 테스트에서 6개 하위 사례 오류로 재현했다. |
| 영향 | 권한이 부여되지는 않지만 코드 결함을 접근통제/설정 장애로 오인하여 진단과 회귀 방어를 어렵게 한다. 권한 우회나 FROZEN의 중대한 충돌은 아니므로 수정 후 B42-04 진행 가능으로 판단했다. |
| 수정 | 내부 변환 범위를 OSError/ValueError로 좁혔다. 프로그래밍 오류는 단위 호출자에게 전파한다. CLI 최외곽은 별도 `internal review failure (<종류>)`/1로 구분해 원시 예외·SID·개인 경로를 출력하지 않는다. 예상 가능한 운영 오류의 BLOCKED 정책은 유지했다. |

### 그 외 검토 근거와 한계

- SID 식별은 `fr_b02b_windows_auth.py`, SID/활성 역할 대조는 Allowlist, 유스케이스 조정은 Service에 분리되어 있다.
- 누락/손상/미등록/비활성·보호 실패·설정 공급자 오류는 각각 범주 오류로 차단된다. 현재 기본 운영 공급자는 설정 미확정 오류를 낸다. CLI는 임의 SID/허용 목록/ACL 우회 인자를 받지 않고 USERNAME을 인증에 사용하지 않는다.
- `ctypes` HANDLE/DWORD/LPWSTR 포인터 선언, TokenUser 크기 조회/조회 성공 검사, 변환 성공 검사, LocalFree/CloseHandle 반환값과 중첩 finally를 검토했다. 확인 가능한 추가 결함이 없어 Native 코드는 수정하지 않았다.
- 공식 대조 자료: [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation), [ConvertSidToStringSidW](https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertsidtostringsidw), [LocalFree](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-localfree), [CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle).
- Native 성공·6개 장애 경로의 자원 해제는 합성 대역 테스트다. 실제 Windows TokenUser SID도 whoami 결과와 메모리에서 대조하여 일치를 확인했으며 값은 출력/파일 보관하지 않았다. 실제 ACL·경로 소유권·보호 읽기/잠금·적대적 경합·운영 역할 지정의 실증은 하지 않았다.
- 운영 접근통제의 미완료와 Mock 검증은 코드·문서에서 구분된다. 현재 상태에서 B42-04 진행을 차단할 중대한 보안/FROZEN 충돌은 발견하지 못했다.

## B. 구현 및 Red → Green

### 책임과 변경 범위

- `fr_b02b_reviewer_allowlist.py`: 위 예외 범위 수정.
- `fr_b02b_observation.py`: 내부 `VerifiedObservation`과 읽기 전용 로더를 추가했다. 같은 검증 ZIP·JSON·인덱스 바이트 및 읽기 전용 연결 필드를 유지한다. 기존 4A/4B-1 함수의 반환 필드·상태·검사·읽기 전용 계약을 보존한다.
- `fr_b02b_review_service.py`: 명시적 선택/사유/시계 검증, 인증 이후 미리보기 데이터와 저장 전 PendingReviewDecision 구성. 기존 입력 검증→SID→Allowlist 순서를 유지하고 표시용 스냅샷을 읽기 전용 재검증한다. 원본 4A 시각과 관측자 신뢰 수준을 바꾸지 않는다.
- `fr_b02b_cli.py`: 미리보기, 선택/사유 2회 입력, 취소/오류 출력. 선택은 공백·대소문자를 정규화하되 기본값은 없고 YES를 사용하지 않는다. 기존 observe-a1-zip의 정확한 YES 규칙은 그대로다.
- `tests/test_fr_b02b_review_decision.py`: B42-04 테스트 10개. `tests/test_fr_b02b_reviewer_allowlist.py`: 프로그래밍 오류 회귀 1개 추가 및 허용 SID의 기존 사례 기대 동작 갱신. 기존 테스트를 삭제하지 않았다.
- `README.md`, 이 보고서: 범위·결과·남은 운영 검증 기록.

### 실제 Red 출력과 원인

1. Allowlist 리뷰 재현: `Ran 10 tests ... FAILED (errors=6)`. 프로그래밍 오류를 기대했으나 `AllowlistError: reviewer allowlist protection failure` 또는 `reviewer allowlist unavailable`가 발생했다. 최소 수정 후 같은 10개 테스트 OK.
2. B42-04 최초: `Ran 9 tests ... FAILED (failures=32)`. 대표 출력은 `AssertionError: 1 != 2`, `'invalid review decision' not found in 'BLOCKED: protected review registration is not configured\n'`, `AssertionError: unexpectedly None`. 프롬프트·명시적 결정·취소·시계 검증이 미구현인 행동 실패였고 Import/fixture 실패가 아니었다. 구현 후 9개 OK.
3. 전체 회귀 최초: 128개 중 기존 Allowlist의 허용 SID 사례에서 `AssertionError: no prompt` 1건. 이번 요구로 허용된 검토자에게 입력을 받게 되었으므로 해당 사례를 ACCEPTED/빈 사유 2회 입력으로 갱신했다. 인증 실패 사례의 프롬프트 0회, 원본/Store/ID 불변 검사는 유지했다.
4. CLI 오류/취소 경계 추가: `Ran 10 tests ... FAILED (failures=1, errors=1)`. 예기치 않은 TypeError와 인증 중 KeyboardInterrupt가 CLI 밖으로 전파됐다. 최외곽에서 내부 오류와 취소를 구분하고 원시 진단을 제거한 후 10개 OK.

### 상태별 처리

| 입력/상태 | 내부 결과 / 현재 CLI |
|---|---|
| ACCEPTED | 사유 선택, 최대 500자. 저장 전 판단만 구성하고 등록 미구현 BLOCKED/1 |
| HOLD / REJECTED | 비공백 자체 작성 사유 필수, 최대 500자. 등록 미구현 BLOCKED/1 |
| 빈 선택 / EOF / Ctrl+C | 판단·등록 생성 없이 CANCELLED/2 |
| 알 수 없는 선택 / 사유 누락·길이 초과 | BLOCKED/1; 자동 ACCEPTED 없음 |
| 인증·허용 목록 실패 | 미리보기/프롬프트 전에 BLOCKED/1 |
| 시계 누락·naive 값·역행·조회 실패 | BLOCKED/1 |
| 예기치 않은 프로그래밍 오류 | 단위 계층에서는 전파, CLI에서는 구분된 내부 오류/1, 원시 진단 미출력 |

결정 전 UTC 표본은 역행 검사에만 사용하고, 선택·사유 확인 이후 별도로 측정한 UTC만 reviewed_at_utc로 사용한다. Reviewed 시각은 입력 전 시각 및 4A 생성 시각보다 빠를 수 없다. 독립 시각 인증은 아니다.

PendingReviewDecision은 메모리에만 있으며 등록 매니페스트가 아니다. 원본 ZIP/관측 JSON/인덱스는 수정하지 않고 원래 HOLD/NONE을 유지한다. Protected Store 호출, UUID 발급, 유효 registration_id, PROTECTED_REVIEW_RECORDED, 정상 등록 종료 코드 0을 생성하지 않는다. 운영 설정 미확정인 실제 CLI는 여전히 검토 입력 전 차단된다.

## C. 검증

Python 3.14, 작업 디렉터리 `tools/fr_b02b_cli/`:

| 명령/검사 | 실제 결과 |
|---|---|
| `python -B -m unittest discover -s tests -q` 시작 전 | 118개 OK |
| `python -B -m unittest discover -s tests -p test_fr_b02b_reviewer_allowlist.py -q` 리뷰 수정 후 | 10개 OK |
| `python -B -m unittest discover -s tests -p test_fr_b02b_review_decision.py -q` 최종 | 10개 OK |
| `python -B -m unittest discover -s tests -q` 최종 | 129개 OK: 기존 118개 + 리뷰 회귀 1개 + 결정 10개 |
| 실제 Windows SID 조회 대조 스크립트 | TokenUser와 whoami 일치. 신원 값 미출력·미보관 |
| `git diff --check`, 신규 파일 `git diff --no-index --check` | 공백 오류 없음 |
| Ruff | 미설치로 미실행. unittest/공백 검사를 정적 분석 완료로 표현하지 않음 |
| Python 3.12 | 이번 범위에서 미실행. 환경 문제 확장 작업 없음 |

기존 4A·4B-1 회귀는 통과했다. 실제 Windows에서 Python/임시 파일 읽기는 실행했지만 SID 실패·허용 목록 보호·결정 입력·시계·Native 장애는 합성 대역이다. 운영 ACL/등록/복원 시험은 수행하지 않았다. FROZEN 문서, A1 해시 규칙, DB/HTTP/RSS/Writer는 변경하지 않았다.

## D. Git 및 후속

브랜치와 HEAD는 위 기준 그대로다. 커밋·푸시·PR·원격 파일 쓰기를 수행하지 않았다. 기존 `docs/infra/` 및 다른 미추적 파일을 보존했다. 추적 파일 diff는 README, CLI, observation 세 파일이며 이전 단위 변경도 누적 포함한다. 신규/기존 미추적 파일은 아래 최종 Git 상태에 구분 없이 표시된다.

현재 단위에서 새로 만든 파일은 `tests/test_fr_b02b_review_decision.py`와 이 보고서 2개다. 이전 미추적 Allowlist/Service 테스트와 모듈은 필요한 부분만 수정했다. Native 모듈과 Native 테스트, 기존 계획 문서는 이번 단위에서 변경하지 않았다.

최종 `git status --short`:

```text
 M tools/fr_b02b_cli/README.md
 M tools/fr_b02b_cli/fr_b02b_cli.py
 M tools/fr_b02b_cli/fr_b02b_observation.py
?? docs/infra/
?? tools/fr_b02b_cli/fr_b02b_review_service.py
?? tools/fr_b02b_cli/fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/fr_b02b_windows_auth.py
?? tools/fr_b02b_cli/phase4b2_b42_04_review.md
?? tools/fr_b02b_cli/phase4b2_implementation_plan.md
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_decision.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_registration.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_service.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_windows_auth.py
```

HEAD 대비 추적 diff(이전 작업 누적 포함): README +65행, CLI +40행, observation +23/-3행; 합계 3개 파일 +128/-3행. 미추적 파일은 이 통계에 포함되지 않는다. `.pytest_cache` 조회 권한 경고는 기존 환경 상태이며 이번 작업에서 해당 디렉터리를 변경하지 않았다.

남은 위험: 실제 보호 설정·Native ACL/잠금, 판단 중 입력/권한 변경의 저장 직전 재검증, 부분 쓰기·중복·재시작·C/E 백업·철회는 아직 구현/검증하지 않았다. 메모리의 ACCEPTED를 운영 등록으로 사용하면 안 된다.

다음 최소 단위는 보호 등록 준비 경계다. 먼저 운영 경로·관리 책임과 실제 ACL 검증 기준을 확정하고, 동일 입력 바이트·권한 재검증 실패를 Red로 만든 뒤 제한된 보호 스테이징을 구현한다. 백업·완료 표식·복원 가능성이 검증되기 전 등록 성공은 계속 금지한다.
