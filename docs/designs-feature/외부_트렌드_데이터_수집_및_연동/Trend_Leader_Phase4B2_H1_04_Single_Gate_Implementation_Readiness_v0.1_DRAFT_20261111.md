# Trend Leader — Phase 4B-2 H1-04 단일 Gate 합성 계약 Implementation Readiness v0.1

> **DRAFT / Codex 작업 인수인계 / H1 운영 채택 미승인 / FROZEN 변경 없음**
>
> 기준일: 2026-11-11 KST
> 기준 브랜치: feat/phase4b2-protected-review-registration
> 기준 HEAD(작성 당시): 8eed59cdc9b7d6a2e76184c6bc9e4d241cfe99d7. 작업 시작 시 재확인한다.
> 사용자 직접 실행한 Helper Core 기준선: 14 tests / OK (1.067s).
> 위 기준선은 이 문서 반영 과정에서 새로 실행한 테스트가 아니다.

## 1. 이번 단일 목표

**H1-04:** Helper가 ProtectedCreationBoundary.exclusive_section()에서 단 하나의 Gate를 소유할 때, 기존 등록·철회 Core와의 조립 과정에서 Gate를 중복 획득할 가능성과 책임 경계를 확인한다. 필요한 경우 **합성 계약 테스트만** 최소 추가한다.

이는 H1 관리자 Helper 채택이나 운영용 Windows 권한 구현 승인이 아니다. 기존 4B-2 FROZEN §4.2의 관리자 상승 범위는 미확정 상태로 유지한다.

## 2. 필요한 자료만 읽기

1. 저장소 루트 AGENTS.md v1.1 — 반복 지침을 이 문서에 복제하지 않는다.
2. 같은 폴더의 Phase 4B-2 Design FROZEN v1.0 (§4.2, §5~8): 외부 동결 계약의 최우선 기준.
3. 같은 폴더의 Trend_Leader_Phase4B2_H1_Admin_Helper_FROZEN_Compatibility_and_Minimal_Contract_Review_v0.1_DRAFT_20261111.md: §0, §3.2, §4, §6만 우선. DRAFT는 FROZEN보다 우선하지 않는다.
4. tools/fr_b02b_cli/ 아래 fr_b02b_helper_core.py, fr_b02b_registration.py, fr_b02b_native_store.py, fr_b02b_protected_store.py, fr_b02b_review_service.py 및 직접 관련 테스트.

P4 Writer 문서·전체 Repository 탐색은 현재 작업의 기본 입력이 아니다.

## 3. 확인된 사실과 테스트 공백

- HelperRequestCore.execute()는 인증 scope 안에서 ProtectedCreationBoundary.exclusive_section()을 사용하며, CreationSession.apply()/verify()를 호출한다.
- 기존 _history_operation()에는 독립적인 Gate 진입과 프로세스 SID 재검사가 있다. MirroredEvidenceStore.stage() 역시 Gate를 소유하는 경로가 있다.
- 기존 test_reentrant_attempt_cannot_enter_second_gate는 **같은 Helper Core 인스턴스의 재진입 방어**를 확인한다. 기존 Registration/Revocation Core를 조립해 Gate가 중복되지 않는지까지 입증하지 않는다.
- 현재 Helper와 실제 Registration/Revocation Core의 운영 조립 경로는 없다. 발생 가능성과 실제 재현을 구분한다.
- 운영 최종 객체 생성과 인벤토리 Creator는 비활성 상태다. Mock 성공은 실제 Windows OS 보안 실증이 아니다.

## 4. H1-04 Given / When / Then

**Given:** 합성 인증 Peer, 합성 등록·철회 요청, 단일 진입 Fake Gate와 기존 Core의 실제 호출 구조.

**When:** Helper가 이미 Gate를 보유한 상태에서 등록·철회 경계에 위임하려는 경로를 분석하거나 합성 테스트한다.

**Then:**
1. Gate 획득 및 해제 소유자가 정확히 한 주체인지 추적 가능해야 한다.
2. 기존 Core가 Gate를 재획득하려는 경우 성공이나 유효 등록을 반환하지 않고 BLOCKED/HOLD한다.
3. 하위 Core가 이미 획득된 Session에서 동작하게 하려면 새 책임 인터페이스가 필요한지 식별한다.
4. 인증된 검토자 SID·철회자 SID, C/E 원본 및 이력, 실패 잔재 HOLD, publish_authorization=NONE을 보존한다.
5. 실제 Core가 아직 연결되지 않은 Mock만으로 운영 통합 PASS라고 주장하지 않는다.

## 5. 단계·중단 조건

**A. 분석 전용:** 실제 브랜치·HEAD·git status 확인. Helper → CreationSession → Registration/Revocation 및 Mirrored Store의 Gate 진입 경로를 추적하고, 기존 테스트와 중복 여부를 보고한다. 아직 수정하지 않는다.

**B. 한정된 합성 테스트:** 기존 규칙으로 기대 결과를 정할 수 있고 누락된 테스트가 확인된 경우에만 Fake/Mock 테스트를 최소 추가한다. **프로덕션 코드는 수정하지 않는다.** 임의의 신규 Gate Owner 인터페이스, 신원/권한 정책 또는 통합 API를 구현해야 한다면 즉시 중단한다.

**C. 검증:** tools/fr_b02b_cli/에서 가장 가까운 unittest부터 실행하고 필요 시 영향 범위로 확장한다. 실제 Red의 원인과 기존 테스트 정상 동작을 구분한다. 실행하지 않은 테스트를 PASS라고 보고하지 않는다.

**중단 사유:** FROZEN 정책 변화, Caller/Creator 신원 분리 정책 결정, 새로운 운영 Adapter, Native/ACL/IPC/서비스 실행, Gate 재설계가 필요한 경우 → BLOCKED / Design Decision Required로 보고한다.

**금지:** Git reset/clean/restore, 임의 브랜치 전환, 미커밋 사용자 변경 덮어쓰기, 관리자 상승, 실제 Windows ACL/저장소/기존 R01 잔재 변경, 운영 CLI 연결, DB·P4 게시, Commit/Push/PR.

## 6. 결과 보고 최소 형식

- HEAD 및 기존 Git 상태
- 실제 Gate 소유·중첩 가능 경로(관련 함수 위치)
- 기존 테스트로 확인된 범위 / 신규 테스트 필요 여부
- 변경한 테스트 파일 및 실행 명령·결과
- 설계 결정이 필요한 점과 다음 최소 구현 단위

**완료 의미:** H1-04 합성 계약 검증 또는 명확한 Design Decision Required 판정에 한함. H1 운영 채택 미확정, 4B-2 운영 등록 HOLD, G5/G6 및 P4 실제 게시 HOLD.
