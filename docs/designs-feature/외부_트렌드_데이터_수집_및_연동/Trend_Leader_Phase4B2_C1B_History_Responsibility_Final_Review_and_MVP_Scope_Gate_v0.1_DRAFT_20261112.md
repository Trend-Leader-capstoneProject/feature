# Trend Leader — Phase 4B-2 C1-B 철회·조회 책임 분리 Final Review + MVP 범위 Gate v0.1

> **원격 보관 이력(2026-11-12): 사용자 요청에 따라 이 DRAFT 문서만 작업 브랜치에 커밋. C1-B 구현·FROZEN 변경·운영 게시 승인은 아님. 아래 '원격 수정 없음' 표현은 최초 초안 작성 당시의 기록입니다.**


> **FINAL REVIEW / DRAFT / NOT FROZEN / C1-B 구현 승인 아님**  
> 기준일: 2026-11-12 (KST)  
> 저장소: `Trend-Leader-capstoneProject/feature`  
> 확인한 작업 브랜치: `feat/phase4b2-protected-review-registration`, HEAD `ffed44436a4886ae19359152bbd92c6e17f8d3b3`  
> 최우선 기준: Phase 4B-2 Design FROZEN v1.0 (§4.2, §5~§9)  
> 후속 내부 구현 계약: `Trend_Leader_Phase4B2_Gate_Session_SID_Internal_Implementation_Contract_v0.1_DRAFT_20261112.md` (승인 범위 C1-A)  
> 검토 증거: C1-A 커밋 변경 3개 파일; `_history_operation`·`MirroredEvidenceStore`·`HelperRequestCore`·관련 테스트 원격 읽기. 사용자/Codex 보고 전체 `390 tests OK`는 이번 문서 작성 시 재실행하지 않음.  
> **이번 작업:** 설계 검토 문서 생성만. 실제 코드·원격 GitHub·Windows ACL/계정·DB·G5/G6 변경 없음.

## 0. 결론 — 기술적 조건부 수용 / 지금 구현 우선순위는 보류

1. C1-B의 본질은 `fr_b02b_registration._history_operation(...)`가 담당한 **Gate 획득·검토자 신원 확인·조회/철회 본문**의 책임을 분리할 수 있는지 확인하는 것이다. 기존 동작 변경이 목표가 아니다.
2. **기술 설계 후보:** standalone Wrapper가 Gate를 획득하고, 해당 Scope 내부에서 기존 `environment()` 재검증과 `RegistrationHistory` 조회·철회 수행을 그대로 유지한다. 향후 Helper 경로는 동일 Gate를 중복 획득하지 않고 신뢰된 Session에서만 접근해야 한다. 해당 Helper 내부 진입점은 아직 확정하거나 노출하지 않는다.
3. **C1-B 구현에 대한 즉시 GO는 권고하지 않는다.** 현재 4B-2 운영 Helper/Creator authority가 비활성이고 FROZEN §4.2 권한 충돌도 미해결이다. `_history_operation()`을 로컬 클로저로만 분리하면 C1-A와 마찬가지로 향후 Helper가 재사용 가능한 실행 경로까지 생기지는 않으며, 실질적 MVP 기능 증가는 없다.
4. **기능 후퇴는 금지:** 4B-2 FROZEN의 철회·유효성 조회 필수 요구는 유지한다. 구현 보류는 기능 완료 선언이 아니라 **해당 Phase를 HOLD로 두는 일정·우선순위 판단**이다.
5. **MVP 시연 우선:** 기존 MVP-A 문서는 2026-11-17에 관심사별 실데이터 트렌드 카드 노출을 목표로 하지만, 현재 실제 4B-2→P4 게시 경계와 G5/G6가 검증되지 않았다. 다른 성격의 목표인 **기존/합성 데이터 모바일 시연**은 별도 안전 경로로 검증하고, 운영 실데이터 게시 PASS로 오인하지 않아야 한다.

## 1. 코드와 기존 증거 대조

| 대상 | 확인된 사실 | 설계 영향 |
|---|---|---|
| `MirroredEvidenceStore.verify_current/revoke` | `_history_operation`으로 위임; 조회 `reason=None`, 철회는 비공백 사유 필수 | 현 standalone 공개 내부 진입점 보존 |
| `_history_operation` | 환경 구성 검증 → `with gate():` → `environment()` → C/E 이력·인벤토리 검사 → 조회 또는 추가 전용 철회 → Scope 종료 후 결과 | **Gate Owner는 현재 이 함수**. Wrapper/본문 분리 시에도 검증 순서·오류 의미 변경 금지 |
| `environment()` | 내부에서 `require_process_sid()`→`require_authorized_sid` 재조회; SID 불변·시간 역행·루트·Provider·Layout 재검증 | 로컬 프로세스 SID 정책을 유지; 본문에서 검사 삭제 금지 |
| 철회 분기 | `ACCEPTED`만 철회 가능, 기존 철회 사건 재사용, 신규 이벤트 시 C/E 각각 append, final inventory 및 재스캔 검증 | 철회에서만 write/UUID; 조회는 read-only, 반복 철회 시 재발급 금지 |
| `NativeStoreBoundary.exclusive_section` | 정상 종료 시 Gate 처리, 실패 시 HOLD/잔재 보존, 단일 사용 | 합성 Fake의 자동 release를 운영 Native 의미로 일반화 금지 |
| `HelperRequestCore` | 인증 Scope와 `CreationSession.apply/verify` 추상 계약만 존재 | 실제 OS IPC 인증이나 Helper용 trusted Session 구현 없음 |
| C1-A `stage_in_scope()` | 로컬 클로저 추출, 기존 `stage` Gate 유지, 390개 전체 테스트 OK라는 Codex 보고 | 비공개 로컬 함수는 **재사용 가능한 별도 Session API가 아님** |
| H1-04 테스트 | 잘못된 Helper→standalone 재진입이 합성 Gate에서 HOLD | 정상 Helper→Gate-bound 철회 성공은 미입증 |

현재 실제 C1-B 프로덕션 구현 변경은 확인되지 않는다. 원격 `ffed444...`에는 C1-A만 반영되었다.

## 2. C1-B 책임 계약 — 기능 의미는 불변

### 2.1 소유권

- **standalone `verify_current()/revoke()`**: 기존 `_history_operation` 경로의 **단일 Gate Owner 유지**. 보호 구간 정상 종료 후에만 유효 결과를 반환한다.
- **조회/철회 본문**: Gate 획득 이후에만 기존 `environment()`와 `RegistrationHistory` 기반 작업을 수행한다. 내부에서 추가 Gate 획득 금지.
- **향후 Helper**: 허가된 생성 경계의 Gate-bound Session을 통해서만 접근한다. 기존 Gate-owning `_history_operation()` 자체를 Helper 안에서 호출하지 않는다. 단, 신뢰된 Session 발급·만료·Boundary 결속 방식은 C1-C/보안 설계 이후 결정한다.
- **중복 호출·다른 프로세스**: 동일 Global Gate 경합은 현재 정책을 유지하며 실패 잔재/불확실 상태에 대한 수동 조사 HOLD를 약화하지 않는다.

### 2.2 검사 위치와 실패 의미

1. Gate 획득 전: 등록 ID 형식, 필수 Store/Provider/FinalInventory·구성 및 요청 사유/필요 capability를 기존과 동등하게 확인한다. 실제 쓰기 권한을 확인하지 못하면 미리 HOLD한다.
2. Gate 보유 중: `environment()`로 실제 현재 프로세스 SID·Allowlist·Root/Provider·Gate·시간을 확인한다. 등록 이력·C/E 원본·현재 철회 집합을 최신 재검증한다. 외부에서 전달한 `revoker_sid` 문자열만으로 인증하지 않는다.
3. 조회(`reason is None`): 이력·현재 상태 계산 및 검증만 수행. UUID 생성/파일 쓰기/인벤토리 변경 0회.
4. 철회(`reason` 있음): 유효 `ACCEPTED`와 결속된 지문 확인. 이미 철회되었으면 기존 이벤트 재검증 및 재사용. 신규 사건은 C/E와 별도 인벤토리 등 **기존 FROZEN 조건**을 유지한 상태에서 append-only.
5. Gate/하위 검증/인증/시간 오류 시 성공 결과 없음. 부분 쓰기·Gate 잔재 자동 삭제/복구/재시도/재수락 금지. Native 실패 시 보존 정책을 기존과 동일하게 유지한다.
6. Gate Scope 종료 후에만 결과 반환. 철회 이벤트가 과거에 정상적으로 생성되어 있어도 종료가 불확실하면 해당 시도는 성공이 아니다.

### 2.3 구현 선택지 및 판단

| 대안 | 방법 | 장점 | 한계/판정 |
|---|---|---|---|
| **B-L: 로컬 클로저 추출** | `_history_operation` 안에서 Gate 본문만 로컬 내부 함수로 분리 | 기존 C1-A와 유사, 외부 접근 우회면 최소, 변경량 적음 | Helper 재사용 API 미생성. **리팩터링만 위한 선행 구현은 보류 권고** |
| **B-T: 신뢰된 Session 기반 내부 경계** | Gate Owner가 만든 유효 Session만 받는 내부 작업으로 등록/철회 호출 분리 | 나중에 Helper 정상 연결 가능 | 위조·만료·다른 Boundary 금지 방식과 I1 신원 처리 계약 선행 필요. **이번에는 새 API 확정·구현 금지** |

**권고:** 현 시점은 B-L과 B-T 중 하나를 즉시 채택하는 단계가 아니다. C1-C(운영 Helper가 아닌 합성 정상 조립)를 실제로 진행하기로 결정할 때, 안전한 Scope 발급·검증 계약과 함께 구현한다. 새 `already_locked` 플래그, 공개 `_history_operation_locked` 진입점, 자의적 `sid=` 인자로 우회 금지.

## 3. 기존 standalone 보존을 위한 Acceptance (필요한 경우에만 신규 테스트)

| ID | Given / When | Then | 기존 재사용 가능 근거 |
|---|---|---|---|
| B-01 | `verify_current` 성공 | 한 Gate 획득·정상 종료 후 최신 상태 반환, 쓰기/UUID 0 | history·Native registration 조회 테스트 |
| B-02 | 최초 유효 `ACCEPTED` 철회 | R SID, 올바른 manifest SHA, C/E append-only, 변경 전 원본 불변 | `test_registration_restart_and_revocation_preserve_original_bytes` |
| B-03 | 동일 ID 철회 재요청 | 이전 철회 사건 재검증·재사용, 새 이벤트/UUID 0 | 기존 Native 등록/철회 통합 테스트 |
| B-04 | 비활성 SID·Allowlist/Root·Provider 변경 | 권한/환경 차단, 성공 0, 노출 정보 최소화 | Helper, Native, 등록 History 테스트 |
| B-05 | Gate 취득 거절·해제 실패/한쪽 철회 부분 실패 | BLOCKED/HOLD, 기존 잔재/원본 보존, 자동 정리 없음 | `test_one_sided_revocation_write...`, `test_gate_release_failure...` |
| B-06 | 기존 단독 코드의 조회/철회 시 Gate 진입 이벤트 | 정상 작업에서 취득 1회, 완료·실패 시 결과 반환 순서 보존 | **직접적인 소유 순서 보완 테스트 후보(필요 시 1~2개)** |
| B-07 | Helper가 기존 Gate-owning 철회 호출을 중첩 시도 | 차단·변경 0 | H1-04 신규 2개 중 철회 사례 |

- 테스트 390개 중 실제 실행을 직접 확인한 것은 사용자/Codex 보고다. C1-B 구현 뒤 숫자만 늘리는 목표를 설정하지 않는다.
- FROZEN 공개 CLI·JSON·상태·오류·`publish_authorization=NONE`, G5/G6 HOLD를 보존한다.
- `review-verify/review-revoke` 운영 CLI가 연결되지 않은 현상은 C1-B 책임 분리만으로 해결되지 않는다.

## 4. 반드시 분리할 'MVP 시연' 판단

### 4.1 현재 근거

- 사용자 기획서 `interest_based_trend_app_plan.md`는 회원가입·관심사 선택·트렌드 목록/상세/최신 이슈를 핵심 우선순위에 둔다.
- 기존 MVP-A 단계 연결 문서에는 **2026-11-17 관심사별 실제 트렌드 카드 노출 목표**가 있지만, 동일 문서의 G5/G6·P4·4B-2 신뢰 경계는 **DRAFT/HOLD**이다. 현재 운영 PASS나 실제 게시를 입증하지 못한다.
- 원격 코드에 `backend/scripts/seed_demo_trends.py`와 제한적인 Demo Seed guard 테스트가 존재한다. 즉 **합성 데이터 기반 별도 앱 시연 검증 후보는 존재**하지만, 실기기 E2E 시연이 완료되었다는 증거는 아니다. 해당 Seed의 로컬 DB 접근·허용 대상을 바꾸거나 실제 운영 데이터인 척해서는 안 된다.
- 전체 UI 흐름의 최신 실기기 시연 합격 여부, 현재 기능별 누락·담당자·데이터 출처 승인 현황은 이번 C1-B 코드 리뷰만으로 확정할 수 없다.

### 4.2 우선순위 판단 (시연 목표 변경은 사용자·팀 결정 필요)

| 범주 | 우선순위 | 예시/판단 | 종료/차단 조건 |
|---|---|---|---|
| **앱 시연 최소 사용자 흐름** | P0 / 즉시 진단 | 로그인 → 관심사 확인·수정 → 트렌드 목록 → 상세/출처; 실제 기기·API·DB 연결 여부 확인 | 화면 전환/데이터 누락 시 기능 중심 수정 |
| **시연 데이터 출처와 라벨** | P0 | 합성 Demo Seed면 합성임을 명확히 설명; 운영 실데이터면 독립 Gate·승인 증거 확인 | G5/G6 미충족 시 실제 게시 성공이라고 소개 금지 |
| **4B-2 기존 FROZEN의 보안 필수 계약** | 운영 게시 기준 P0 | 실제 게시를 선택한다면 C/E 보호, ACL, 최신 철회, Registry/Writer 조정과 승인 등 미충족 해소 필요 | 요건 미충족 시 게시 HOLD·기능 미완료, 단순 리팩터링으로 PASS 금지 |
| **C1-B Gate 책임 분리 리팩터링** | 기술 부채 P2 / 조건부 | 기존 안전 동작이 보호되고 Helper 정상 조립 계획이 실제 실행될 때에만 도움 | 테스트만 늘거나 Helper 채택이 HOLD라면 중단 가능 |
| **H1 운영 Helper·IPC·새 계정·범용 Session 프레임워크** | 보류 | FROZEN §4.2와 권한 실측·운영 정합성 미해결 | 운영 방식 별도 승인 전 구현 금지 |

### 4.3 과잉 설계 중단 규칙

1. **사용자에게 보여줄 흐름 또는 승인된 실데이터 게시의 필수 경로와 직접 연결되지 않으면 새 내부 추상화 작업을 시작하지 않는다.**
2. 기존 테스트가 같은 차단 의미를 보장하면 이름만 바꾼 중복 테스트를 추가하지 않는다. 새 반례만 추가한다.
3. 한 단계에서 한 책임 경계만 다루고, 변경 코드·새 클래스·새 문서·OS 실측 범위를 임의 확장하지 않는다.
4. 장애가 생겨도 FROZEN 안전 요건을 임의로 줄이지 않는다. 미달이면 해당 운영 경로를 HOLD하고 **합성 시연을 별도 성과로 분리**한다.
5. **시연 체크포인트(1페이지):** 기능(화면→API→DB), 데이터 종류(합성/실데이터), 실제 기기 테스트, G5/G6, 마지막 정상 실행 증거, 막힌 항목만 기록. 기술 리팩터링 개수는 시연 성공 지표가 아니다.

## 5. 권고 진행 및 완료 판정

**이번 C1-B Final Review 판정:** 내부 책임 분리 설계 자체는 **조건부 수용**, **즉시 Codex 구현은 DEFER**가 더 합리적이다. 사용자 승인 없이 C1-B 구현 범위를 넓히지 않는다. 이유는 현재 운영 Helper/Session이 도입되지 않아 클로저 추출의 실효성이 낮고, 기존 동작 테스트가 상당하며, MVP 실기기·데이터 시연 경로의 상태 확인이 더 직접적이기 때문이다.

**다음 권고 작업:** C1-B 프로덕션 구현 전에 짧은 **MVP 시연 Readiness Audit**: 이미 있는 로그인·관심사·트렌드 목록·상세/출처의 기기 E2E, 합성 Seed 실행 환경, 실데이터 게시 승인 상황, 남은 작업의 필수/후속 구분. 이것은 승인된 기획 범위를 임의 축소하거나 실데이터 게시 FROZEN을 변경하는 행위가 아니다.

**C1-B를 다시 GO할 트리거:** (i) 실제 4B-2 운영 등록/철회를 MVP에 연결할 별도 권한·Gate 설계가 승인됨, (ii) 기존 코드에 리팩터링 없이 해결 불가능한 중첩 Gate가 실 재현됨, (iii) C1-C 정상 조립을 진행하기로 결정하고 Session 불변조건·SID 검증 분리 정책을 승인함. 이때도 위 B-01~07 중 누락된 반례만 테스트한다.

**유지 상태:** Phase 4B-2 전체 구현 완료 아님 / H1 운영 채택 미승인 / P4 NOT FROZEN / G5·G6 HOLD / 게시 허가 `NONE` / `dev` 변경 없음(이번 문서 작업에서는 원격 쓰기 없음).

## 6. 직접 검토한 근거

- `tools/fr_b02b_cli/fr_b02b_registration.py`: `_history_operation`, `RegistrationHistory`, 철회 상태·지문/사건 검증
- `tools/fr_b02b_cli/fr_b02b_protected_store.py`: `verify_current`, `revoke`, `stage` 및 C1-A `stage_in_scope`
- `tools/fr_b02b_cli/fr_b02b_native_store.py`: `NativeStoreBoundary.exclusive_section`, Native Gate 실패 HOLD
- `tools/fr_b02b_cli/fr_b02b_helper_core.py`: `ProtectedCreationBoundary`, `CreationSession`, `HelperRequestCore`
- `tools/fr_b02b_cli/tests/test_fr_b02b_registration_history.py`, `test_fr_b02b_native_registration.py`, `test_fr_b02b_helper_gate_composition.py`
- 4B-2 Design FROZEN v1.0; 내부 Gate·Session·SID Implementation Contract v0.1 (승인 범위 C1-A)
- 프로젝트 기획서 `interest_based_trend_app_plan.md`; MVP-A 연결 계약/Final Review v0.1 (2026-11-11)
- 원격 `backend/scripts/seed_demo_trends.py`, `backend/tests/db/seeds/test_demo_seed_guard.py`