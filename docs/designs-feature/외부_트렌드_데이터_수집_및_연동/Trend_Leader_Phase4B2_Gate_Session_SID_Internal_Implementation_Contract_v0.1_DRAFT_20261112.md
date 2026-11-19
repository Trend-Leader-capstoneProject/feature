# Trend Leader — Phase 4B-2 Gate·Session·SID 내부 구현 계약 v0.1

> **INTERNAL IMPLEMENTATION CONTRACT / 2026-11-12 C1-A 범위 사용자 승인 / NOT FROZEN / H1 관리자 Helper 운영 채택 미승인**  
> 작성 기준: 2026-11-12 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`  
> 기준 브랜치: `feat/phase4b2-protected-review-registration`  
> 검토 시점 원격 HEAD: `b5abba4ffbdd621a6a4c06422692c76eec8261a7` (구현 전 재확인)  
> 최상위: `Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md`의 §4.2, §5~§8  
> 직접 선행: `Trend_Leader_Phase4B2_H1_Gate_Session_SID_Final_Review_v0.1_DRAFT_20261111.md`  
> 작업 분담: **설계·확정·변경 심사는 ChatGPT 채팅에서 / 확정된 최소 코드 구현·테스트는 Codex에서**.  
> 이 문서는 구현 코드를 생성하지 않고, 현재 존재하지 않는 클래스/함수를 실제 API로 주장하지 않는다. 신규 개념·이름은 내부 설계 표현이며 실제 구현 API명을 강제하지 않는다.

## 0. 결론과 명시적 비승인 사항

**사용자가 승인한 내부 기술 원칙: G1(진입점별 단일 Gate Owner) + S1(생명주기·Native 보호 경계에 결속된 내부 Session) + I1(검토자 R·생성 주체 C의 책임 분리). 승인된 구현 착수 범위는 C1-A뿐이다.**

- G1과 S1은 **기존 standalone 호출을 유지하면서 내부 중첩 획득을 막는 구조**로 제한해 실제 합성 테스트·최소 리팩터링의 후보로 삼는다.
- I1은 **각 신원을 독립 검증한다는 요구사항**만 확정 후보로 삼고, 실제 다른 프로세스/토큰을 통한 Creator 실행·관리자 상승·IPC 구현은 범위 밖으로 둔다.
- FROZEN §4.2의 “관리자 상승은 ACL 초기 구성·관리 업무 한정”과 매번 고권한 Helper를 호출하는 H1은 **충돌 가능성이 남아 있다**. 내부 리팩터링이 이 운영 정책을 묵시적으로 변경하지 않는다.
- 실제 Native 최종 객체 생성·인벤토리 authority는 비활성 상태다. Mock 결과는 운영 PASS가 아니다. `publish_authorization=NONE`, G5/G6 HOLD, P4 Writer NOT FROZEN 유지.

## 1. 실제 구현 사실과 현재 공백

| 코드 위치 | 현재 확인한 책임 | 설계 공백 |
|---|---|---|
| `fr_b02b_helper_core.HelperRequestCore.execute` | 인증 Scope → `ProtectedCreationBoundary.exclusive_section()` → `CreationSession.apply/verify` → Scope 종료 후 `BoundaryReceipt` | 실제 OS Authenticator/CreationSession 구현 없음 |
| `fr_b02b_protected_store.MirroredEvidenceStore.stage` | Gate를 자체 획득하고 그 안에서 검사·스테이징·C/E 복원·`RegistrationCore.preflight/finish`를 호출 | Helper 보유 Gate 내부에서 안전하게 실행하는 신뢰된 내부 진입점 없음 |
| `fr_b02b_registration._history_operation` | 자체 Gate, 매 체크포인트에서 현재 프로세스 SID+Allowlist, C/E·철회 이력 검증 | Helper의 인증 R과 실제 Creator C가 다르면 직접 호출 불가능 |
| `fr_b02b_native_store.NativeStoreBoundary` | Native anchor·Config·SID·ID·볼륨 확인, Gate 생성·정상 해제, 실패 시 HOLD | R/C 분리된 운영 보안 컨텍스트에 대한 대체 검증 미설계 |
| `fr_b02b_inventory.FinalObjectInventory` | owner/ACL·최종 객체 인벤토리 검사 | 실제 Creator authority 없음 |
| `tests/test_fr_b02b_helper_gate_composition.py` | 기존 Gate-owning `stage/revoke`를 Helper 아래 직접 호출 시 합성 중첩 거부, 부작용 0 | 정상 경로·OS 실패 잔재 검증 아님 |

**시험 근거:** 사용자/Codex 보고: Helper 14, 신규 H1-04 2, 전체 386 tests OK; 이 문서 작업 중 Python 회귀를 새로 실행한 것은 아니다. 원격 `b5abba4` 커밋에는 신규 테스트 파일 하나가 추가되었다.

## 2. G1: Gate 획득 책임과 내부 작업 분리

### 2.1 진입점별 계약

1. **Standalone 등록:** 기존 공개 또는 내부 `stage(...)` 호출 경로가 지금처럼 안전한 `exclusive_section()`을 취득한다. 획득 전 신뢰된 설정·입력 사전검증을 유지하고, 획득 이후에도 모든 기존 경계 검증과 `preflight/finish`를 수행한다. 완료·예외 처리는 기존과 동일하다.
2. **Standalone 조회/철회:** 기존 `verify_current(...)`, `revoke(...)` → `_history_operation(...)`은 여전히 그 작업의 Gate 소유자다. 기존 `require_process_sid()`와 Allowlist 정책을 보존한다. 읽기 전용 조회의 정상 결과/오류 계약은 변경하지 않는다.
3. **Helper 경로(향후):** `ProtectedCreationBoundary.exclusive_section()`이 *해당 요청의 Gate*를 단 한 번 취득하고, 그 보호 Scope에 결속된 내부 등록 또는 철회 연산을 호출한다. 이 경로에서 standalone Gate-owning `stage()/revoke()/_history_operation()`을 다시 호출하지 않는다.
4. **공통 내부 작업:** 자체 Gate 취득/해제를 하지 않고, 이미 신뢰된 Gate/Native Boundary 아래에서 기존 C/E·인벤토리·이력 재검증과 쓰기/조회만 수행한다. 호출 전후에 보호 Scope를 재검증한다.
5. **다른 작업/프로세스:** 동일한 *전역* Gate에 경쟁한다. 단일 소유 원칙은 *논리 작업 단위*이며 전역적으로 한 종류의 클래스만 소유해야 한다는 의미가 아니다.

### 2.2 내부 추출 범위 제안 (코드 이름은 Codex가 현 소스에 맞춰 최소 제안)

- `MirroredEvidenceStore.stage()`의 **검사·계획/경계 재검증·스테이징·복원·`RegistrationCore.preflight/finish`**의 실행 본문을 보호 Scope 내부의 작업 단위로 추출한다. 기존 `stage()`는 자신의 Gate를 잡고 **동일 내부 단위**에 위임하는 Wrapper로 남긴다.
- `fr_b02b_registration._history_operation()`의 **등록 이력 스캔·중복/철회 판단·철회 사건 추가·인벤토리·C/E 최종 검증** 본문을 보호 Scope 내부의 작업 단위로 추출한다. 기존 `_history_operation()`은 `require_process_sid()` 검증을 계속 수행하면서 자체 Gate를 잡는 standalone Wrapper로 남긴다.
- 현재 `RegistrationCore.preflight()`와 `finish()`는 이미 Gate 안에서 호출되지만 Gate 소유 사실을 자체 증명하지 않는다. 신규 내부 경계의 보호 Scope 검증 아래에서만 사용한다.
- **최소 변경 우선순위:** 1차 `stage()` Wrapper/내부 추출과 standalone 회귀 → 2차 `_history_operation()` Wrapper/내부 추출과 철회 회귀 → 3차 합성 Helper 정상 조립. 각 단계 종료에 테스트 결과가 있어야 하며 하나의 큰 리팩터링으로 합치지 않는다.
- 허용되는 새 private 이름/도우미 수는 기존 코드를 확인한 뒤 최소화한다. 이 문서는 `*_locked` 같은 특정 API 이름이나 파일 경로를 새 공식 계약으로 강제하지 않는다.

**안전상 핵심:** `stage()`의 `with self.exclusive_section()`만 삭제하거나, 호출자의 `already_locked=True`만으로 내부 권한을 부여하지 않는다.

## 3. S1: Gate-bound Session 계약

### 3.1 상태와 책임

```text
NOT_ISSUED
   └─ [신뢰된 Boundary의 Gate 획득·검증 성공] → ACTIVE
ACTIVE
   ├─ [모든 검증 + 내부 작업 + 정상 scope 종료] → CLOSED_SUCCESS
   └─ [예외·취소·권한/ID 변경·해제 불확실] → FAILED_HOLD
CLOSED_SUCCESS 또는 FAILED_HOLD → 재활성화/재사용 금지
```

이것은 **논리 상태 모델**이다. 실제 Python 클래스/enum/생성자 정의가 아니다. FAILED_HOLD의 물리 Gate 파일/핸들은 기존 Native 정책과 오류 시점에 따르며, 테스트 Fake처럼 자동 제거하거나 정상 해제했다고 주장하지 않는다.

### 3.2 반드시 유지할 불변조건

| ID | 규칙 | 반례/차단 |
|---|---|---|
| S-01 | 한 논리 작업당 Gate 취득 한 번, 소유자만 정상 해제 | Helper → standalone 중첩 금지 |
| S-02 | Session은 신뢰된 Gate 획득 Scope 안에서만 발급되고 동일 Native Boundary·Config·Anchor·Gate ID/핸들에 결속 | 직접 만든 Session, 다른 Boundary 주입 거절 |
| S-03 | 활성 구간 밖, 완료·실패·취소·전달 Scope 종료 후 Session 사용 불가 | 늦은 호출·재시도 차단 |
| S-04 | 변경 전·후, C/E 이력 검사, 완료/철회 검증 때마다 Gate·Native object ID/ACL/볼륨/Config와 입력 스냅샷·R 인증을 재검증 | 체크포인트 생략 차단 |
| S-05 | 출처 바이트·완료 표식·복원 증거·별도 최종 인벤토리 및 철회 상태 중 누락 또는 불일치 시 등록·철회 성공 0회 | 부분 C/E 성공은 HOLD |
| S-06 | 새 등록/철회 시 중복 이력·충돌·철회를 Gate 내부에서 최신 검사; UUID·재수락 우회 금지 | 기존 ACCEPTED 중복 시 검증 후 재사용 |
| S-07 | 정상 Scope·인증 Scope 종료, Gate 정상 해제까지 완료하기 전에는 외부 성공 Receipt 반환 금지 | 해제/연결 실패 후 성공 금지 |
| S-08 | 모든 기존 standalone 경로의 동등한 auth·Gate·원본 불변성·오류 의미 보존 | Wrapper 제거·테스트 통과 숫자만 보고 완료 선언 금지 |

### 3.3 보안 경계의 실제 의미

- Python의 Session 객체는 **애플리케이션 내부의 오용 방지 계약**이지 OS 권한을 부여하는 보안 토큰이 아니다. 검증 근거는 실제 유효 Gate와 핸들, 동일 Boundary, 보호 owner/ACL 및 별도 OS 토큰/Allowlist에 있다.
- 내부 함수에 사용자 제공 `scope`, `locked`, `sid` 문자열을 주입해 보안 근거를 만드는 것은 금지한다. 신뢰된 호출 경계가 보유한 검증 상태로만 호출한다.
- Native에서 실패 시 Gate 잔재 보존은 별도 보안 정책이다. 합성 Fake의 `release` 호출을 Native에서 허용된 보안 정리와 동일하게 취급하지 않는다.
- 인증 종료와 Gate 정상 종료 뒤에도 현재 철회 상태는 미래에 변경될 수 있다. `review-verify` 또는 P4 사용 시 현재 이력을 재검증한다. P4의 철회–DB Commit 경쟁 제어는 여기서 결정하지 않는다.

## 4. I1: Reviewer R / Creator C 권한 증명 분리

| 경계 | 검증 책임 | 현재 동결 범위와의 관계 |
|---|---|---|
| R(Reviewer/Revoker) | 명시적 사람 판단을 요청한 OS-인증 사용자 SID, 보호 Allowlist, 요청과 인증 연결·입력 바이트·철회 지문 결속 | `registration.json.reviewer_sid`, `revocations/*.json.revoker_sid`는 오직 R |
| C(Creator/Executor) | 실제 Native 객체 생성 I/O 시 사용되는 토큰의 SID 외 그룹·권한·제한 상태/승격, 승인된 owner·DACL·범위 및 생성 객체 실제 결과 확인 | C의 SID를 R로 기록하거나 R의 문자열 SID만으로 최종 생성 승인하지 않음 |
| Standalone | 기존 `require_process_sid()` 및 Native `policy.reviewer_sid` 검사 유지 | 기존 동작을 의도 없이 변경하지 않음 |
| Helper(향후) | 별도 OS AuthenticatedPeer로 R 검증, 다른 실행 토큰 C는 독립 검증. 실제 I/O 시 스레드 가장 토큰과 프로세스 토큰의 사용을 확인 | 실제 IPC/Token API와 운영 관리자 모델은 **미승인·미구현** |

Windows의 스레드 가장 동안 OS 파일 접근 검사는 가장 토큰을 이용할 수 있다. 따라서 **R을 인증하려고 가장하는 단계와 C의 권한으로 파일을 생성하는 단계가 보안적으로 같은 작업이 아니다**. 가장 성공/종료/권한 반환이 확인되지 않으면 고권한 파일 작업 금지. 단, 구체 Named Pipe·서비스 계정·토큰 생성/전환 방식은 여기서 선택하지 않는다.

**FROZEN §4.2 Design Decision Required:** 매 등록·철회에 고권한 Creator를 사용하는 모델은 기존 ‘관리자 상승은 최초 ACL 설정·관리 업무 한정’과 충돌할 수 있다. 해당 운영 모델을 선택하려면 원문 변경 없이 별도 변경안/승인 과정을 먼저 거친다. **이번 Gate 분리 TDD에서는 운영 R/C 분리를 구현하지 않는다.**

## 5. Codex에 전달할 첫 구현 패키지 — 승인 범위 제한

**C1-A (1차): Standalone 등록 Gate 책임 분리 및 합성 회귀**

목적: 기존 `MirroredEvidenceStore.stage()`의 Gate-owning Wrapper와 재사용 가능한 Gate-bound 내부 연산을 최소 분리한다. 코드 변경을 수반할 수 있다. 관리자 Helper나 Native 최종 생성·SID 정책은 건드리지 않는다.

- 포함: 변경 전 브랜치/HEAD/status, 기존 테스트 기준선, 호출 경로 확인, 기존 standalone `stage()` 동일 동작을 고정하는 특성 테스트, 분리로 인해 검증 순서/오류·ID·잔재가 달라지지 않는지 검증, 최소 내부 리팩터링.
- 제외: 실제 Helper와 조립, `_history_operation()`의 광범위한 변경, 프로세스/토큰 SID 우회, C/E 실제 파일, OS ACL/IPC/관리자 상승, 기존 FROZEN, 외부 CLI/API/DB 변경.
- Red: 신규 변경 규칙이 있으면 의도한 이유의 Red를 먼저 확인. 단순 구조 분리로 관찰 가능 동작이 동일한 경우 기존 특성 테스트의 Green + 최소 리팩터링과 회귀를 허용(불필요한 Red 조작 금지).
- 완료: `stage()` 호출 시 Gate 획득 1회, checkpoint/C/E/복원·인벤토리/중복/RegistrationCore 통합 보존, 기존 오류·Gate release 실패에서 성공 0회; 테스트 결과 재현 가능. Helper 정상 조립 성공은 이번 완료 기준에서 제외.
- 차단: 신뢰된 내부 보호 Scope 설계 없이 `already_locked`/skip gate로 우회해야만 분리 가능한 경우 → **Design Decision Required**, 임의 구현 금지.

**C1-B (2차, 별도 승인):** 철회/조회 `_history_operation()`의 standalone Wrapper와 동일 Gate-bound 핵심 분리. 반드시 기존 SID 검사·철회 지문·append-only·중복 사건·C/E 이력 검증을 보존한다.

**C1-C (3차, 별도 승인):** H1-G01 정상 합성 Helper 조립, S-02/03 무효 Session 주입, 기존 H1-04 중첩 차단 유지. 실제 R/C 운영 프로세스 분리는 여전히 HOLD.

## 6. 테스트/Acceptance 계약

| ID | Given / When | Then / 증거 수준 |
|---|---|---|
| H1-G01 | 신뢰된 합성 Gate-bound Context를 가진 Helper 정상 경로 | Gate 획득 1회·정상 scope 종료 후에만 내부 Receipt. **C1-C에서** |
| H1-G02 | 위조·종료·타 Boundary Session | 내부 연산 0, HOLD, 생성·UUID 발급 0. **C1-C에서** |
| H1-G03 | 기존 standalone `stage`, `revoke`, `verify` 경로 실행 | Gate·SID·C/E·철회·상태 의미 보존. **C1-A 및 C1-B별** |
| H1-G04 | Native Gate 취득/해제 실패·부분 쓰기·권한 바뀜 | 성공 0, 운영 Native 잔재 자동 정리 0. 기존 합성/Native 차이를 명시 |
| H1-I01 | R과 C가 다른 가상 신원, 또는 동일 SID지만 다른 권한 | R 기록에 C 대입 금지, Creator 권한 별도 검증. **운영 방식 승인 이후** |
| H1-R01 | 기존 ACCEPTED 등록 지문+인증 R의 철회 요청 | Gate 1회·append-only·SID R·C/E 최신 이력·반복 요청 불변. **C1-B~C** |
| H1-COMPAT | 4A/4B-1 및 전체 `fr_b02b_cli` 관련 회귀 | 기존 FROZEN 상태·출력·동작 불변, 실행한 테스트만 PASS로 보고 |

실행 예 (Windows PowerShell, 작업 디렉터리 `tools/fr_b02b_cli`):

```powershell
python -B -m unittest discover -s tests -p test_fr_b02b_helper_core.py -q
python -B -m unittest discover -s tests -p test_fr_b02b_helper_gate_composition.py -q
python -B -m unittest discover -s tests -q
```

Ruff는 설치 여부를 확인한 후에만 실행하고 미설치면 미실행으로 기록한다. 가상 파일/Mock/합성 테스트 통과를 실제 OS/ACL PASS로 승격하지 않는다.

## 7. Codex 작업보고 요구·쓰기 안전

- `AGENTS.md` v1.1, GitHub Write Safety Policy, 4B-2 FROZEN, **이 문서 및 직접 관련 코드만 우선 탐색**. 중복된 긴 역사 문서 전부를 컨텍스트에 넣지 않는다.
- 시작 시 브랜치/HEAD와 `git status --short` 확인; 사용자의 기존 미추적 `docs/infra/aws_design_firstpass.md` 등은 보존. `git restore/reset/clean` 또는 다른 사람 변경 덮어쓰기 금지.
- 변경 범위는 승인된 단일 패키지의 관련 내부 코드·테스트에 한정. 새 모듈/클래스/공개 API/사용자 입력 옵션을 불필요하게 추가하지 않는다.
- 수정 전/후 최소 diff, 기존/신규 테스트·실제 로그, 실패 원인, 기존 보안 조건 보존 증거, 미검증 항목을 간결하게 보고.
- Secret, 실제 SID/개인 경로, 운영 Evidence 원본을 출력/커밋하지 않는다.
- **Codex의 코드 변경에 대한 Commit/Push/PR은 별도 승인 전 수행 금지.** 이 문서의 원격 반영은 사용자의 별도 명시 승인에 따른 문서 커밋일 뿐, 코드·FROZEN·운영 권한에 대한 쓰기 허가가 아니다.

## 8. 승인 상태·다음 의사결정

**2026-11-12 사용자 승인: G1/S1 내부 기술 계약 및 I1 책임 구분 원칙, C1-A 최소 구현 착수에 한정. 기존 FROZEN 변경·H1 운영 Helper 도입 승인이 아니다.**

- 승인된 C1-A 범위만 Codex에서 구현·테스트 가능. C1-B/C는 C1-A 결과를 채팅에서 검토한 뒤 별도 승인한다.
- C1-A 보고 후 ChatGPT에서 API/책임 분리와 회귀 결과를 리뷰하고 C1-B/C로 순차 확대할지 결정한다.
- 관리자 H1, FROZEN §4.2 승격 정책, OS IPC, 최종 Creator 권한·ACL/owner, 실 C/E, P4는 각각 별도 Design Decision이 필요하다.

## 9. 근거

- 원격 브랜치 HEAD: `b5abba4ffbdd621a6a4c06422692c76eec8261a7` (2026-11-12 조회)
- `tools/fr_b02b_cli/fr_b02b_helper_core.py`
- `tools/fr_b02b_cli/fr_b02b_protected_store.py`
- `tools/fr_b02b_cli/fr_b02b_registration.py`
- `tools/fr_b02b_cli/fr_b02b_native_store.py`
- `tools/fr_b02b_cli/fr_b02b_inventory.py`
- `tools/fr_b02b_cli/tests/test_fr_b02b_helper_gate_composition.py`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md`
- Microsoft Learn: https://learn.microsoft.com/en-us/windows/win32/secauthz/impersonation-tokens
- Microsoft Learn: https://learn.microsoft.com/en-us/windows/win32/secauthz/owner-of-a-new-object
- Microsoft Learn: https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient