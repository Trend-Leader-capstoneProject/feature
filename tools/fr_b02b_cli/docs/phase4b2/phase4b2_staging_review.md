# Phase 4B-2 저장 직전 재검증 및 합성 스테이징 검토

2026-11-10 KST. `Trend-Leader-capstoneProject/feature` / `feat/phase4b2-protected-review-registration`.
로컬 및 읽기 전용으로 재조회한 원격 HEAD: `8d49cb33e91b7a09def95084d54810b92132b32a`.

## 1. 선행 실제 코드 검토

| 검토 대상 | 실제 근거와 판정 |
|---|---|
| PendingReviewDecision | Service의 메모리 전용 판단이며 registration_id/완료 상태가 없다. CLI는 이를 받은 뒤에도 BLOCKED/1이다. 보호 등록 완료와 혼동하는 동작은 발견하지 못했다. |
| 시각 | reviewed_at_utc는 입력 이후 새 UTC 표본이다. 4A confirmed_at_utc/record_created_at_utc는 원문 문자열을 유지한다. 입력 전 표본은 역행 검사에만 쓴다. |
| 내부 스냅샷 | observation의 로더가 읽은 ZIP/JSON/index 바이트로 검증하고, 같은 바이트를 VerifiedObservation에 보유한다. MappingProxyType으로 기록 필드를 읽기 전용 제공한다. 마지막 ZIP 읽기는 비교용이다. |
| 4A·4B-1 | 기존 dict 반환 래퍼·상태·정확한 YES·읽기 전용 후보 계약 유지. 시작 시 기존 129개 unittest를 재실행하여 OK 확인했다. |
| Allowlist/CLI 오류 | 운영 공급자는 미설정 오류를 내며 공개 SID/경로/ACL 우회 인자가 없다. 예상 가능한 운영 오류만 내부에서 변환하고, 프로그래밍 오류는 CLI 최외곽에서 별도 내부 오류로 구분해 원시 진단을 출력하지 않는다. |

**선행 판정:** 이번 범위를 차단할 중대한 결함/FROZEN 충돌은 발견하지 못했다. 타입 생성 자체는 검증 증명이 아니므로 신규 저장 경계에서는 바이트와 필드를 독립 재검증해야 한다. 실제 운영 ACL·잠금·관리 책임·모든 적대적 경합은 미확정/미검증이며 안전하다고 판정하지 않는다.

신규 구현 중 `VerifiedObservation(a1_snapshot=None)` 위조가 AttributeError로 거절되는 사례를 추가 재현했다. 새 Store에 명시적 A1Snapshot 타입 검사를 추가하여 안전한 StagingError로 차단했다. 기존 기능의 동결 계약을 변경한 수정은 아니다.

## 2. 책임과 구현 경계

- `fr_b02b_review_service.py`: 저장 직전 세 입력을 재검증하고 검토 당시의 전체 스냅샷과 비교한다. 판단 필드/NONE/시각/ID 연결을 검사하고 현재 SID/Allowlist를 재확인한다. 입력과 루트의 중첩을 거부한다. 이 재검증을 Store의 쓰기 전후 콜백으로 전달한다. Store가 없으면 기존 BLOCKED를 유지한다.
- `fr_b02b_a1_adapter.py`: 기존 ZIP 파싱 본문을 내부 `_load_a1_snapshot_bytes()`로 공유한다. 기존 경로 읽기 안전 검사와 공개 반환값, A1 구조·content_ref 알고리즘은 그대로다.
- 신규 `fr_b02b_protected_store.py`: 전달된 바이트의 A1/4A 검증과 pending 메타데이터 지문 연결을 독립 검사한다. 기존 루트·상위 경로·신규 스테이징·파일의 재분석/링크/타입/보호 판정을 검사하고 배타 디렉터리/파일 생성, short-write 검사, flush/fsync, 바이트 재읽기 및 파일 목록 대조를 한다.
- 신규 `tests/test_fr_b02b_protected_store.py`: 기존 합성 결정 fixture를 조합해 재사용하며 기존 테스트를 중복 수집하거나 수정하지 않는다. 15개 테스트에 핵심 반례를 하위 사례로 묶었다.
- `README.md`, 이 문서, `phase4b2_staging_code_and_tests.patch`: 사용 범위·검증 한계·검토용 diff를 제공한다. 패치는 신규 Store와 신규 핵심 테스트의 전체 추가 diff다. Service와 A1 변경은 현재 코드/추적 diff로 함께 검토한다.

FROZEN §5.2/§6.2의 통제된 임시 스테이징만 구현했다. `.review-staging-<LOCAL-OBS ID>` 배타 디렉터리 생성이 이 임시 루트 안에서 같은 관측 ID의 경쟁/재실행을 차단한다. 기존/실패 디렉터리가 있으면 새 이름으로 우회하지 않는다. 운영 등록 이력·다중 호스트 잠금 구현으로 일반화하지 않는다.

임시 파일은 정확히 `a1_archive.zip`, `observation.json`, `index.json`, `pending_review.json`이다. 마지막 파일은 local_evidence_id, reviewer_sid, review_result, decision_reason, reviewed_at_utc, publish_authorization=NONE 및 세 원본 SHA-256을 결속하는 내부 canonical JSON이다. 등록 매니페스트 스키마나 실제 registration_id를 생성하지 않는다.

정상 합성 복사가 끝나도 반환값은 HOLD/NONE이다. Store 확정·등록 성공·registration_complete.json·C/E 백업·복원·철회는 없다. 실패 시 원본에 쓰지 않고 잔재를 자동 삭제/복구/승격하지 않는다. 외부 교체를 테스트가 주입한 경우에는 그 교체 바이트를 되돌리지 않고 사용을 차단한다.

## 3. 실제 Red → Green

1. 인터페이스만 연결한 최초 실행: `Ran 14 tests ... FAILED (failures=35)`.
   - `AssertionError: ReviewBlocked not raised`: 세 원본 변경, 일관되게 재해시한 관측 기록 교체, 위조 판단·권한 상실·경로 충돌이 차단되지 않음.
   - `AssertionError: StagingError not raised`: Store가 미검증 바이트를 거절하지 않음.
   - `AssertionError: unexpectedly None : validated bytes must reach HOLD staging`: 복사·검증 결과가 미구현.
   - Import/fixture 오류는 없었고 정상 합성 A1/4A·결정 생성 뒤 기대 행동 assertion으로 실패했다.
2. 최소 구현 후 신규 14개 OK, 전체 143개 OK.
3. 경계 보완: 짧은 쓰기 반환·파일 생성 직전 충돌·현재 SID 변경을 추가 확인하고, a1_snapshot=None 위조가 `AttributeError: 'NoneType' object has no attribute 'archive_bytes'`로 전파되는 Red 1건을 확인했다. 명시적 타입 검사 후 신규 15개 OK.
4. 최종 전체 회귀: 기존 129개를 그대로 포함한 144개 OK. 기존 테스트 파일은 이번 단위에서 수정하지 않았다.

## 4. 실행 명령과 검증의 의미

작업 디렉터리 `tools/fr_b02b_cli/`, Python 3.14:

```powershell
python -B -m unittest discover -s tests -p test_fr_b02b_protected_store.py -v
# Ran 15 tests ... OK
python -B -m unittest discover -s tests -q
# Ran 144 tests ... OK
```

- 실제 Windows 임시 파일/디렉터리 생성, 배타 쓰기, flush/fsync, 재읽기·동일 바이트 대조, 실제 symlink 및 NTFS junction 차단을 실행했다. 링크 정리는 테스트가 만든 링크만 비재귀로 제거한다. 두 링크 테스트는 최종 실행에서 skip되지 않았다.
- SID·Allowlist 보호 판정·루트/파일 ACL 판정은 합성 대역이다. 쓰기/부분 쓰기/fsync/권한 변화/입력 교체 장애도 주입했다. 실제 운영 SID/ACL과 C/E 다른 디스크의 내구성·복원 검증 결과가 아니다.
- 기존 4A·4B-1 공개 동작·원본 바이트 불변·실제 CLI Fail-Closed 회귀가 통과했다. DB/HTTP/RSS/Writer 코드는 변경하지 않았다.
- Ruff는 미설치로 미실행이다. 공백/구문 검사는 정적 분석 완료로 간주하지 않는다. Python 3.12는 이번 범위에서 미실행이다.

## 5. 남은 운영 결정과 위험

운영 원본/백업/Allowlist 설정의 물리 경로, 초기 등록 담당자, 허용 목록 변경·철회·폐기 책임, 소유자/허용 SID/상속/권한 범위·부모 경로/Native 핸들 기반 보호 읽기·잠금 정책을 확정해야 한다. 확정 후 실제 Windows 계정의 제한 ACL 및 다른 디스크 백업·재시작/복원 시험이 필요하다.

현재 Path 검사와 파일 재대조는 모든 적대적 TOCTOU 경합을 해결하지 않는다. 보호 검증 콜백의 True는 테스트 전제이며 운영 증명이 아니다. fsync와 개별 파일 생성은 디렉터리 내구성, 전원 손실 또는 C/E 원자적 트랜잭션을 보증하지 않는다. 따라서 실제 CLI에는 Store를 설정하지 않고 계속 차단한다.

다음 최소 단위는 운영 경로/책임/Native ACL·잠금 기준 확정 후 보호 스테이징의 실환경 접근통제 검증이다. 그 뒤에만 등록 매니페스트·C/E 백업·복원 검증·완료 표식·재시작 대조로 확장한다. 현 단계의 HOLD를 유효 등록으로 사용할 수 없다.

## 6. Git 및 검토용 diff

브랜치와 HEAD는 문서 상단 기준 그대로다. 커밋·푸시·PR·원격 쓰기는 없다. 기존 `docs/infra/`와 다른 미추적 파일은 보존했다.
이번 단위의 새 파일은 Store, Store 테스트, 이 보고서, 검토용 patch 4개다. Service/A1/README만 필요한 범위를 수정했고 CLI·observation·기존 129개 테스트 파일은 이번 단위에서 변경하지 않았다.

Protected Store 및 핵심 테스트 추가 diff인 `phase4b2_staging_code_and_tests.patch`는 당시 설계 채팅 검토용으로 만든 과거 로컬 산출물이며 Git 커밋에는 포함하지 않는다. 패치에는 운영 경로·실제 SID·원본 승인 ZIP/관측 자료가 포함되지 않는다.

`git apply --reverse --check tools/fr_b02b_cli/phase4b2_staging_code_and_tests.patch`로 현재 두 파일과 일치함을 확인했다. 확인만 했으며 패치를 적용/되돌리거나 Git index를 변경하지 않았다.

최종 HEAD 대비 추적 diff(이전 단위 누적 포함): README +90, A1 Adapter +7, CLI +40, observation +23/-3; 합계 4개 파일 +160/-3행. 미추적 파일은 이 통계에 포함되지 않는다.

최종 `git status --short`:

```text
 M tools/fr_b02b_cli/README.md
 M tools/fr_b02b_cli/fr_b02b_a1_adapter.py
 M tools/fr_b02b_cli/fr_b02b_cli.py
 M tools/fr_b02b_cli/fr_b02b_observation.py
?? docs/infra/
?? tools/fr_b02b_cli/fr_b02b_protected_store.py
?? tools/fr_b02b_cli/fr_b02b_review_service.py
?? tools/fr_b02b_cli/fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/fr_b02b_windows_auth.py
?? tools/fr_b02b_cli/phase4b2_b42_04_review.md
?? tools/fr_b02b_cli/phase4b2_implementation_plan.md
?? tools/fr_b02b_cli/phase4b2_staging_code_and_tests.patch
?? tools/fr_b02b_cli/phase4b2_staging_review.md
?? tools/fr_b02b_cli/tests/test_fr_b02b_protected_store.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_decision.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_registration.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_service.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_windows_auth.py
```

기존 pytest cache 조회 권한 경고는 유지되며 해당 디렉터리를 변경하지 않았다. 구문 파싱/공백 검사는 변경 Python 파일 4개에 실행했으며 Ruff 정적 분석을 대체하지 않는다.
