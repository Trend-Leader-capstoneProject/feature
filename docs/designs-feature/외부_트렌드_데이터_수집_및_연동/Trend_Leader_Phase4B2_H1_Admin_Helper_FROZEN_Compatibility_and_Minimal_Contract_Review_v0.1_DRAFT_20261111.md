# Trend Leader — Phase 4B-2 H1 관리자 Helper FROZEN 정합성·최소 구현 가능성 Review v0.1

> **DRAFT / NOT FROZEN / 설계 검토 전용 / 작성 당시 코드 수정·Windows 실측 없음**  
> 기준일: 2026-11-11 (KST)  
> 저장소: `Trend-Leader-capstoneProject/feature`  
> `dev`: `b133b494f8258eea603243f8f07191a33290084a`  
> `feat/phase4b2-protected-review-registration`: `8eed59cdc9b7d6a2e76184c6bc9e4d241cfe99d7`  
> 우선 기준: **Phase 4B-2 FROZEN v1.0 §4.2, §5–§8**. Phase 4A/4B-1 FROZEN, 운영 Gate v0.3, P4 Addendum DRAFT/DEC 보존.  
> 이 문서는 H1 제안을 검토할 뿐, H1 채택·FROZEN 변경·운영 ACL 적용·실제 등록/게시 승인이 아니다. `publish_authorization=NONE`, G5/G6 HOLD 유지.

## 0. 판정 요약

**판정: H1 조건부 기술 후보 / FROZEN 정합성은 미확정 / 운영 사용 BLOCKED.**

1. `HelperRequestCore`는 호출자 인증과 요청/생성 경계를 추상화하지만 운영 OS 인증 Provider·IPC·Native 생성 Session은 구현하지 않았다.
2. 현 `Win32StoreNative`는 `final_creation_available()`과 `inventory_creation_available()`이 `False`, `create_final`/`create_inventory`가 `NativeError(50)`이다. 합성 테스트의 Fake authority 성공은 운영 성공이 아니다.
3. FROZEN §4.2는 “일반 권한 CLI 사용을 기본으로 하며 관리자 상승은 ACL 초기 구성·관리 업무에 한정”한다. **매 검토 등록의 고권한 Helper**가 승인된 '관리 업무'인지 불명확하며, 실제 권한 상승 범위의 확장이라면 별도 변경 승인이 필요하다. **충돌 가능성을 해소하기 전 구현 활성화 금지.**
4. `NativeStoreBoundary._checkpoint()`의 현재 프로세스 SID == `policy.reviewer_sid` 검사와 `fr_b02b_registration._history_operation()`의 현재 프로세스 SID/허용목록 검사·Gate 소유는, Helper가 검토자와 다른 토큰으로 실행될 때 그대로 조립할 수 없다. **SID 조건 해제, Helper SID를 검토자로 기록, Gate 중첩은 모두 금지.**
5. `FinalObjectInventory._readonly_acl`의 현 구현은 최종 보호 객체/인벤토리의 소유자에 Administrators/SYSTEM SID를 요구하고 검토자 쓰기/삭제/ACL 권한을 배제한다. Windows에서 *실제 생성*에 사용된 토큰으로 승인 owner와 DACL을 부여할 수 있는지는 미실측이다.
6. 이미 존재하는 합성 시험 R01 및 잔재는 HOLD 보존한다. 최근 `ROOT_COLLISION`은 루트 존재 사실과 차단을 나타내며 실제 최종 봉인 생성 가능성의 증명이 아니다.

**권고:** H1 채택/변경 승인 전에 아래 최소 책임 분리·권한 정책·반례를 설계 Gate로 두고, 먼저 **운영 파일을 건드리지 않는 합성 Unit/Mock 계약 시험**으로 검증한다. 그다음 신규 격리 Windows 합성 루트 실험을 별도 승인한다.

## 1. 출처·사실/추론 구분

### 1.1 기존 FROZEN에서 그대로 보존할 것

- FROZEN §4.2: OS 실제 SID 기반 `EVIDENCE_REVIEWER` 인증. Git 사용자명·USERNAME·본문 `reviewer_sid`만으로 인증하지 않는다. 관리 승격은 최초 ACL 구성/관리 업무에 한정.
- FROZEN §4.3~§5: 검토자의 명시적 `ACCEPTED/HOLD/REJECTED`; 입력 A1 ZIP+4A `observation.json`+`index.json`의 동일 바이트 결속; `REG-OBS-<uuid4-hex>`, `registration.json`, `registration_complete.json`; `review_result`와 별도 REVOKED 사건. 소스·관측자 의미 변경 금지.
- FROZEN §5.2, §6: C/E 보호 원본·백업 및 복원 검증; 미완료·이력 충돌·부분 쓰기·권한 차이 즉시 HOLD. 두 볼륨을 단일 원자 트랜잭션으로 주장 금지.
- FROZEN §7~§8: 검토 및 철회의 권한자, 재검증, 공개 `review-register/review-verify/review-revoke` 계약 및 실패 코드. 모든 4B-2 결과 `publish_authorization=NONE`.
- P4 Writer/G4/G6/DB DML은 4B-2 업무 범위 밖. H1 결정으로 P4 Writer의 A/B Evidence 접근·S1/S2 철회-Commit 순서를 확정하지 않는다.

### 1.2 실제 구현에서 확인한 사실

| 지점 | 코드상 사실 | H1에 미치는 영향 |
|---|---|---|
| `fr_b02b_helper_core.py` | `RegisterRequest`는 pending/A1/4A/index 바이트만, `RevokeRequest`는 등록 ID·지문·철회 주장 SID·사유만; `RequestAuthenticator`, `AuthenticatedPeer`, `ProtectedCreationBoundary`, `CreationSession` 추상 인터페이스 | 명령·경로·ACL·ID를 IPC 클라이언트가 결정하도록 확대하지 않는 코어는 재사용 후보 |
| `HelperRequestCore.execute` | Peer SID와 본문 주장 SID 일치·허용목록 검증·신원/시계/요청 재검증, 하나의 생성 Scope, 일회성 인스턴스 | 이 검사들은 실제 OS 인증을 제공하지 않는다; Native Adapter 필수 |
| `NativeStoreBoundary._checkpoint` | `api.sid() == policy.reviewer_sid`, 고정 앵커/ACL/ID/볼륨 재확인 | Helper 프로세스 자신의 SID와 진짜 요청자 SID를 혼동할 위험 |
| `NativeStoreBoundary.exclusive_section` | Gate를 획득하고 민감 작업·종료 전 검증, 실패 잔재 HOLD | Helper가 유일한 Gate owner여야 하고, 기존 Core의 추가 Gate 진입 금지 |
| `_history_operation` | 현재 프로세스 SID 재인증 및 내부 Gate 진입 | Helper 경유 철회 시 인증/잠금 중복의 구체적인 통합 차단점 |
| `Win32StoreNative` | 제한 스테이징 Native 생성 존재, 최종/인벤토리 생성 기능은 명시적으로 disabled | 하네스/Mock만으로 생성 가능 PASS 주장 금지 |
| `FinalObjectInventory` | `create_final`, `create_inventory`라는 신뢰된 authority를 요구. 최종 객체는 관리자/SYSTEM 소유·검토자 읽기 제한 및 별도 인벤토리 | 최종 생성 주체/실제 owner·ACL 실측 필요 |
| `fr_b02b_cli.py`, `review_service.review_register` | 공개 review-register가 최종 등록 반환 전에 BLOCKED, review-verify/review-revoke 미연결 | 운영 경계 미완료. 이 단계에서 공개 CLI 연결 금지 |

소스: 위 GitHub 브랜치의 `tools/fr_b02b_cli/` 실제 코드 및 Phase 4B-2 FROZEN/Helper Core 검증 보고. 현재 로컬 작업 트리·실제 Windows 계정/권한을 원격 GitHub만으로 확인한 것은 아니다.

## 2. H1이 성립하려면 누구를 구분해야 하나?

논리 신원은 서로 다른 세 개다.

1. **R: Reviewer** — 검토 의사결정을 내린 실제 Windows 요청자. 인증된 토큰 SID를 `reviewer_sid` 또는 `revoker_sid`로 기록. 이 ID는 Helper가 승인 내용에 임의 주입하면 안 된다.
2. **C: Creator Authority** — 최종 객체와 인벤토리를 생성하는 프로세스·토큰·승인된 접근 범위. R과 물리 SID가 같아도 **승격 여부·활성 특권·그룹·실행 역할**은 별개다.
3. **O: Operation/Bootstrap Administrator** — Config/Allowlist/부트스트랩·ACL 초기 구성/복구의 승인과 변경을 소유하는 업무 책임. R 또는 C와 동일인이 될 수 있으나 그 사실을 독립 승인으로 해석하지 않는다.

### 2.1 왜 SID 일치만으로 부족한가?

Windows UAC에서 동일 사용자의 제한/승격 토큰은 사용자 SID가 같을 수 있다. 그렇지만 부여되는 관리자 그룹·특권·무결성 수준은 다를 수 있다. 따라서 `SID_R == SID_C`라는 사실만으로 비승격 검토가 이루어졌거나 최종 봉인 권한이 안전하게 제한된다고 말할 수 없다.

새 파일의 owner는 생성에 사용되는 기본/가장 토큰 및 보안 설명자/특권과 관련된다. 소유자가 일반적으로 DACL 수정권을 가지므로 **R이 소유자인 최종 봉인을 단순히 '읽기만 허용'으로 선언할 수 없다**. `Administrators`를 owner로 설정하는 SDDL만으로 실 OS 생성 허가를 증명하지 못한다.

공식 근거: Microsoft Learn — [User Account Control works](https://learn.microsoft.com/windows/security/application-security/application-control/user-account-control/how-it-works), [Owner of a New Object](https://learn.microsoft.com/en-us/windows/win32/secauthz/owner-of-a-new-object), [File Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights).

## 3. H1 최소 신뢰 흐름 (제안, 구현된 API 아님)

```text
비승격 Reviewer R : 사람의 명시적 검토·철회 입력
    └─ 기존 A1/4A 검증 결과의 동일 불변 bytes 및 판단 수집
        └─ [운영 인증 Provider 미구현]
             제한된 로컬 IPC (Named Pipe는 후보, 확정 아님)
              - 호출자 연결의 실제 OS identity 검증
              - 본문 SID는 주장일 뿐; authenticated R과 일치해야 함
              - 고정 요청 종류/크기/스키마/단일 연결·수명 검증
                 └─ H1 생성 권한 C (운영 Helper 실행 주체 미확정)
                      ├─ R의 권한은 인증 검증에만 사용
                      ├─ C의 owner/ACL 생성 권한은 별도로 검증
                      ├─ 신뢰된 Bootstrap+Config/Allowlist/볼륨 확인
                      └─ 4B-2 단일 Gate 진입·이력 최신 재검증
                           ├─ C/E 최종 객체 (CREATE_NEW / 핸들·ACL·ID 검증)
                           ├─ C/E 복원 검증과 COMPLETE 표시
                           ├─ 별도 final inventory 생성·검증
                           ├─ 철회는 추가 전용 사건; 이전 원본 불변
                           └─ Gate/IPC 인증 scope 정상 종료 후에만 성공 반환
```

**주의:** H1이란 '관리자가 대신 ACCEPTED를 결정'한다는 뜻이 아니다. 사람 R의 판단과 authenticated peer의 결속은 그대로다. Helpers는 4B-2 보호 생성/철회 실행의 제한된 executor일 뿐 P4 게시 승인자나 Writer가 아니다.

### 3.1 IPC 인증·요청 경계에서 반드시 필요한 조건

- 원시 SID 문자열이나 PID 단독으로 OS 인증을 대체하지 않는다. 연결별 인증된 토큰을 검증하고 **메시지를 읽은 같은 연결의 요청자**와 바이트/판단을 결속한다.
- Named Pipe를 쓰면 기본 DACL을 신뢰하지 않는다. 사전 승인된 제한 접근 정책을 가진 pipe를 생성하고 허용 호출자, 접근 범위, 로컬 전용 범위를 별도 검증한다.
- 요청 프레임/바이트 크기 상한, 중복 키/미정의 필드, 메시지 단절·취소·재전송·경합 정책을 정의한다. 현재 `RegisterRequest`는 내부 Python 객체이지 wire format이 아니다.
- `ImpersonateNamedPipeClient` 같은 OS 기반 인증 방법은 **성공 반환 검증이 필수**이다. 실패 시 Helper 자신의 권한으로 요청 처리 금지. `RevertToSelf` 실패 시 스레드/프로세스 컨텍스트가 불명확하므로 종료/운영 HOLD 방어가 필요하다.
- 인증 scope와 보호 생성 scope의 수명은 서로 결속되어야 한다. 승인 완료 직전 연결이 끊기거나 신원이 변하면 성공 반환 금지 및 미확정 상태 HOLD.
- 보호 원본에 쓰는 `reviewer_sid`/`revoker_sid`는 OS 검증된 R이다. C의 SID를 대신 기록하는 fallback 없음.

공식 근거: [ImpersonateNamedPipeClient](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient), [RevertToSelf](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-reverttoself), [Named Pipe Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights).

### 3.2 현재 Native SID 검사와 통합 시 **절대 하면 안 되는 것**

- `NativeStoreBoundary._checkpoint()`의 SID 비교를 제거한 후 아무 인증도 없는 상태로 쓰기 권한을 활성화하는 것.
- `StorePolicy.reviewer_sid = Helper 현재 SID`로 치환하고 이 값을 `registration.json.reviewer_sid`에 기록하는 것.
- `HelperRequestCore`가 `ProtectedCreationBoundary.exclusive_section()`로 Gate를 잡은 안에서, `_history_operation()`이나 `MirroredEvidenceStore.stage()`가 다시 같은 Gate를 획득하게 만드는 것.
- 관리자(Helper)가 R과 다른 토큰으로 작동할 때, `require_process_sid()`를 R의 신원증명으로 계속 사용하는 것.
- 단순히 `allow_changes=True`, `final_creation_available=True`로 바꾸어 실제 owner/ACL과 쓰기 후 수정 방지 검증 없이 capability를 성공 반환하는 것.
- 원본 변경·C/E 한쪽 실패·인벤토리 누락이 생겼을 때 '편의를 위해' 자동 초기화/ACL 수리/잔재 정리/새 등록 ID 우회하는 것.

### 3.3 책임 분리 리팩터링 후보 (내부 설계 대안, 아직 API 결정 아님)

**R-1: 신뢰된 두 컨텍스트를 별도로 보유하는 방식 — 권고 검토 후보**

- 기존 Human Review Service는 비승격 R의 판단/불변 바이트만 준비.
- OS 인증 Adapter는 R에 대한 peer-token 검증 및 활성 scope 수명만 제공.
- Creator Adapter는 **독립적으로 승인된** C의 실행 토큰/권한 및 고정 저장소 정책을 검증.
- Gate 책임은 오직 Protected Creation Boundary 한곳에 두며, 기존 Registration/Revocation Core는 Gate를 *이미 소유한 Session*에서만 내부 작업하도록 분리하는 방향 검토.
- Native checkpoint는 동일한 protected policy/앵커/볼륨/handle/ACL 검증을 유지하되, **R의 OS 인증 증거와 C의 Creator 권한 증거를 각각 검사**하게 책임 분할하는 설계. 기존 검사만 삭제하는 것은 금지.
- 이 분할이 기존 FROZEN의 OS 인증 뜻과 충돌하지 않는지 확인하고, 전체 회귀로 보존.

**R-2: 신원/잠금 검사를 기존 Core에 유지한 채 외부 wrapper로 묶는 방식 — 단순해 보이지만 권고하지 않음**

- 기존 process SID와 `reviewer_sid` 동일 조건은 고권한 다른 계정 Helper로 이동할 때 모순을 만들 수 있다.
- wrapper가 검토자 SID를 인증해도 Core의 자체 현재 프로세스 재조회가 일치하지 않으면 차단된다.
- 중첩 Gate가 존재하면 별도 helper wrapping만으로 해결되지 않는다.

R-1은 기존 외부 스키마/CLI를 바꾸지 않는 **내부 책임 재배치 가능성**이다. 하지만 관리자 상승 정책이 달라지는 문제까지 자동으로 해소해 주지는 않는다.

## 4. 기존 FROZEN §4.2 정합성 판정

**판정: 기술적 목표와 양립 가능성은 있으나 운영 권한 정책과의 충돌 위험이 크다. 아직 'FROZEN 준수'로 판정할 수 없다.**

| 항목 | FROZEN의 뜻 | H1 검토 결과 |
|---|---|---|
| 검토 판단의 주체 | 실제 Windows 계정 R, 허용 목록 `EVIDENCE_REVIEWER` | OS 인증된 R을 유지하면 원칙상 보존 가능 |
| 관리자 상승 | ACL 초기 구성·관리 업무로 한정 | 매번 등록/철회 때 고권한 Helper 실행은 **관리 업무 범위를 확장할 수 있음** |
| 관리자 변경과 검토 판단 | 구분 | C가 대신 승인 결정을 내리지 않고 R의 인증/불변 bytes만 처리하면 책임 분리 가능 |
| 보호 등록 동일 바이트·C/E | 완료 전 검증 | 기존 Core를 재사용하되 권한자·Gate 경계를 수정/검증해야 함 |
| 공개 CLI/Schema | §5/§8로 고정 | 내부 IPC 도입만으로 변경 불필요. 하지만 CLI 연결을 조건 없이 승인할 수는 없음 |
| 철회 | 실제 R이 요청, 독립 사건 | Helper는 명시적 R 요청만 대리 실행 가능. Process SID 재조회 수정 필요 |
| P4 게시 | 범위 밖 | 그대로 범위 밖·NONE/HOLD 유지 |

**충돌 처리 원칙:**
1. H1을 포함한 '관리 업무' 해석이 단순 실행 토큰/내부 책임 분리에 지나지 않는지, 실제 운영 승격 범위를 확대하는지 문서 수준에서 판단한다.
2. 새로운 권한 범위가 필요하다면 **기존 FROZEN 원문을 무단 수정하지 않고**, 충돌 표와 대체안·기술 검증 증거를 포함한 *명시적 FROZEN 변경 승인*을 별도 요청한다.
3. 승인 전에는 운영 Adapter·CLI를 연결하지 않는다. 필요하면 독립 합성 Unit/Mock 테스트만 진행한다.

## 5. 최소 Windows 생성 권한과 실제 테스트 가능한 질문

현재 공개된 `AclPolicy`·`FinalObjectInventory`가 요구하는 owner/ACE와 달리, **실제로 어떤 Win32 토큰으로 어떤 신규 자식 객체를 생성할지**는 확정되지 않았다. 이 표는 숫자 ACE/SDDL 확정표가 아니다.

| 대상 | C가 최소 수행할 작업 | R에게 금지·제한할 작업 | 확인 방법 |
|---|---|---|---|
| 보호 부트스트랩/Config | 읽기·ID/ACL/해시 재검증, 허용 목록 조회 | Config 수정·복구·ACE 변경 | 각 토큰으로 실제 요청 권한의 OS 거절/허용 확인 |
| C/E 등록 컨테이너 | 승인된 이름의 신규 하위 객체만 생성, 목록·ID/ACL 검증 | 기존 등록 객체 교체·삭제·임의 생성 | 기존 파일 접근 거절 + 새 파일 고정 생성 결과 대조 |
| 최종 registration/complete 원본 파일 | CREATE_NEW, 정확한 원본 bytes 쓰기·flush, 재읽기·owner/ACL/ID 검증 | 기존 파일 쓰기/DELETE/WRITE_DAC/WRITE_OWNER, 보호 owner 우회 | 최초·완료 전/후 Native handle 및 R 실제 OS 거절 테스트 |
| final inventory | 별도 보호 영역에 append-only 새 증명 객체 생성·검증 | R의 인벤토리 변경·삭제, 무승인 인벤토리 생성 | 별도 생성 권한 + 독립 read-only 재시작 테스트 |
| C/E 복원·철회 | 보호 원본은 수정 금지, 새 철회 사건만 append, 양측 대조 | 자동 재수락·임의 복구/철회 삭제 | 부분 쓰기·동일 ID 경합·철회 재조회 테스트 |
| `global.gate` | 승인된 단일 Gate 획득·검증·해제 | 잠금 잔재 삭제·임의 재시도 | 같은 Gate에 서로 다른 토큰/프로세스가 경쟁하는 테스트 |

- Windows에서 SDDL owner만 설정했다고 충분하지 않다. **실제 생성 핸들의 owner/ACL/ID와 사용한 토큰의 capability를 교차 확인**해야 한다.
- 세밀한 파일 권한 비트(`DELETE`, `WRITE_DAC`, `WRITE_OWNER`, `FILE_ADD_FILE`, `FILE_DELETE_CHILD`, `SYNCHRONIZE` 등)는 실제 생성/조회 API가 요청하는 접근 마스크와 독립 대조 후 확정한다. 모든 자식 경로/상위 컨테이너를 `ALL ACCESS`로 설정해서 우회 금지.
- `SeRestorePrivilege` 등 고권한 특권 활성화가 필요한 경우 그 범위·수명·대상 객체를 최소화하고 운영 승인 전 별도 보안 검토. `SeTakeOwnershipPrivilege` 존재만으로 임의 관리자 owner 지정이 가능하다고 단정 금지.
- OS 수준 거절 5와 일반 경로/권한 설정 오류를 구분. Mock으로 `AccessDenied`를 반환한 성공은 실제 거절 실증이 아니다.

## 6. 검증 단계와 Acceptance Criteria

### Stage D0 — 설계 정합성 Gate (이번 단계)

**완료:** 코드와 FROZEN 충돌/미구현점을 문서화. H1의 권한 확장 여부는 미결정. 새로운 시스템·계정·파일 생성 없음.

**D0 통과 의미:** 다음의 *합성 단위 테스트 설계*를 논의할 근거 확보. H1 채택/운영 구현 또는 승인 증거 아님.

### Stage D1 — 운영 영향 없는 계약 테스트 (별도 구현 단계)

사용할 실제 의존 코드는 본문에서 확인한 추상 Core/기존 Fake API뿐. IPC 실제 구현·Native 저장소 변경·신규 계정·Admin 토큰·실데이터 금지.

| ID | Given / When | Then |
|---|---|---|
| H1-01 | 본문 SID=R, 인증 Peer SID=C 또는 인증 없음 | 생성 호출 0회, BLOCKED |
| H1-02 | R/C User SID 같지만 C의 실제 권한 프로필 부족/모호 | 최종 생성 금지; SID 동일만으로 승인 불가 |
| H1-03 | R 인증 연결이 판단 후 끊기거나 요청 payload가 변함 | 성공 응답 없음, 잔재 HOLD, 새 등록 ID 자동 발급 없음 |
| H1-04 | Helper가 단일 Gate 소유 중 기존 Core가 중첩 진입하려고 함 | 중첩 진입 0회(구조/Mock 검증), 실패 시 HOLD |
| H1-05 | `create_final` 또는 `create_inventory`가 불가·오류·owner 불일치 | 등록 성공 0건, 기존 FROZEN 공개 성공 문자열 출력 0회 |
| H1-06 | C/E 중 한쪽 또는 최종 인벤토리 저장 실패 | 완료 표식/레코드가 있어도 최종 유효 등록 불가, HOLD |
| H1-07 | 인증된 R 철회 요청 + Helper SID와 다른 R | 철회자 필드는 R, 기존 원본 불변, 추가 전용 철회 실패 시 HOLD |
| H1-08 | 허용목록/Config/앵커/토큰 변경 또는 Gate 해제 실패 | 성공 없음, 수동 조사 대상 HOLD, 자동 복구/삭제/ACL 수리 없음 |
| H1-09 | 익명/비허가 IPC/임의 경로·ACL·SID 주입 | 불허 작업 0회, 원시 비밀 출력 0회 |
| H1-10 | 사람 결정 이전 및 이후 | 기존 4A 정확한 YES, 4B-1 HOLD/NONE, FROZEN CLI/JSON 스키마 불변 |

**테스트 품질 주의:** 기존 Helper Core 최종 14개 개별 테스트 OK 및 과거 379개 전체 테스트 OK를 신규 H1-01~10 또는 최신 전체 회귀 PASS로 표시하지 않는다.

### Stage D2 — 신규 격리 Windows 생성 권한 실측 (별도 사용자 승인 필수)

- 기존 `C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01` 및 잔재는 그대로 HOLD; `ROOT_COLLISION` 때문에 덮어쓰거나 새 이름 자동 선택하지 않는다.
- *새 실측을 승인할 때에만* 정해진 단일 **새 합성 전용 경로**, 관리자/일반 토큰 종류, 필요한 신규 객체 이름, 승인된 owner/ACE/SDDL 후보, 사전/사후 검증, 실패 잔재 보존·수동 정리 담당자/조건을 문서로 확정한다.
- 테스트할 핵심: 각 토큰의 owner 지정 가능성, 생성 핸들에서 owner/ACL/ID/재분석 상태, 비승격 R의 최종 파일·인벤토리 쓰기/삭제/WRITE_DAC 거절, C의 제한된 생성 허용, 실제 요청자 인증+Gate 경쟁·연결 단절 시 HOLD.
- 실험에 관리자 권한이나 별도 서비스 신원이 필요하다면 자동 상승/계정 생성/권한 부여 하지 않고 별도 검증. C/E 실제 운영 루트 또는 E: 전체 ACL 변경 금지.

### Stage D3 — 4B-2 통합 검증 및 P4 분리

- 운영 정책/실행 주체 승인 이후 4B-2 전체 `B42-01~10` 회귀, C/E 복원/철회/다중 프로세스 경합, 실패 잔재·재시작, CLI 3명령 연결 확인.
- 승인된 유효 4B-2 등록도 P4 게시 자격이 아니다. `observation_evidence_ref`, Writer 계정, Journal, G4/G6 승인, 철회-Commit 조정은 독립된 P4 계약 단계.

## 7. H1 이후의 의사결정 기준

**H1 유지할 조건:**
- FROZEN §4.2의 관리자 상승 범위에 대한 **명시적 승인/변경 심사**가 완료되고, 최소 권한 실제 OS 검증과 인증 연결/단일 Gate 검증에서 위험이 수용 가능한 범위로 축소됨.
- 기존 FROZEN의 CLI·원본 바이트·검토자 SID·철회·이력·C/E 보호 증명이 그대로 유지됨.
- 성능이나 개발 일정이 H2/H3 대비 충분히 유리하다고 데이터로 판단할 수 있음.

**H1 중단·H2/H3 재검토 조건:**
- 고권한 Helper가 운영 시 광범위 임의 파일 작업/수리/삭제까지 요구하거나, 요청자 인증/권한 구분/중첩 Gate 실패를 해소하지 못함.
- FROZEN §4.2를 사실상 변경해야 하는데 팀 차원의 승인 없음.
- owner/ACL의 실 OS 거절/허용을 검증할 수 없거나, 실패를 자동 리커버리하여만 동작함.

**H0 HOLD가 정답인 경우:** 동결 계약의 필수 보호 조건과 권한 경계가 충족되지 않았을 때. 보안 요건을 낮춰 `ACTIVE` 게시로 우회하지 않는다.

## 8. 이번 산출물/미검증 범위

> 아래 실행 이력은 2026-11-11 최초 설계 검토 당시의 기록이다. 이후 이 DRAFT 자체를 원격 브랜치에 저장한 작업과 구분한다.

- **완료한 일:** GitHub 실제 파일·FROZEN·기존 DRAFT의 읽기 전용 코드 감사, Microsoft 공식 Win32/UAC 문서 원문 대조, H1 통합 책임 경계·충돌 매트릭스·H1-01~10 반례 설계.
- **하지 않은 일:** 윈도우/도커 명령 실행, 새로운 시험 루트 생성, ACL 변경·승격, 현재 로컬 Git diff 확인, 운영 권한 확인, 코드 변경, Python 테스트 실행, GitHub 커밋/푸시.
- **상태:** H1 `TECHNICAL_CANDIDATE / POLICY_REVIEW_REQUIRED`; 4B-2 FROZEN 불변; P4 전체 NOT FROZEN; G5/G6 HOLD.