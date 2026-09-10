# Trend Leader 화면 구현 검토 프롬프트

## 문서 정보

```text
문서 유형: Prompt Template
실행 시점: 개별 화면 구현 또는 Refactor 완료 후
출력: 구현 정합성 검토 결과와 후속 수정 필요 사항
기본 모드: Review Only
주의: 검토 단계에서는 사용자 요청 없이 코드나 확정 설계를 임의로 변경하지 않음
```

이 프롬프트는 `[TARGET_SCREEN_NAME]`의 실제 구현 결과가
확정된 Screen Specification, Design System, API 계약과 현재 프로젝트 구조에
일치하는지 검토하기 위한 문서입니다.

이 단계의 목적은 새로운 화면을 다시 설계하는 것이 아니라,
구현 누락, 계약 불일치, 회귀 위험과 검증 부족을 실제 근거를 통해 찾는 것입니다.

---

## 1. 작업 정보

```text
대상 화면:
[TARGET_SCREEN_NAME]

대상 기능:
[TARGET_FEATURE_NAME]

검토 모드:
[IMPLEMENTATION_REVIEW | REFACTOR_REVIEW | FREEZE_READINESS]

대상 브랜치:
[TARGET_BRANCH]

대상 HEAD:
[TARGET_HEAD]

기준 Screen Specification:
[SCREEN_SPECIFICATION_FILENAME_AND_VERSION]
```

### IMPLEMENTATION_REVIEW

새로 구현하거나 기능 연결을 완료한 화면이
명세와 계약에 맞게 구현되었는지 검토합니다.

### REFACTOR_REVIEW

기존 기능 동작을 유지하면서 구조나 디자인을 변경한 경우,
기존 계약과 사용자 동작에 회귀가 없는지 검토합니다.

### FREEZE_READINESS

Candidate 상태의 Screen Specification 또는 Design System을
Frozen으로 승격할 수 있는 충분한 구현·검증 근거가 있는지 확인합니다.

Frozen 승격 자체를 자동으로 수행하지 않습니다.

---

## 2. Source of Truth

프로젝트 전체 자료가 충돌하면
`Trend_Leader_AI_Development_Guidelines.md`의 최신 우선순위를 따릅니다.

화면 검토에서는 다음 자료를 함께 확인합니다.

```text
1. 현재 채팅에서 사용자가 명시적으로 확정한 범위와 결정
2. 해당 기능의 최신 설계 확정안과 확정된 제품 정책
3. 실제 Backend API 계약
4. 실제 Frontend Type / API Function / Hook / Auth / Navigation 계약
5. Design System Snapshot
6. 해당 Screen Specification
7. 현재 대상 브랜치의 실제 구현과 테스트
8. Prompt Template
9. Archive 문서
```

실제 구현은 현재 상태의 사실이고,
확정안과 Screen Specification은 의도한 목표 상태의 기준입니다.

충돌이 있으면 한쪽을 조용히 정답으로 선택하지 말고
충돌 원인과 영향을 먼저 보고합니다.

---

## 3. 입력 자료

다음 자료를 가능한 범위에서 제공합니다.

### 3.1 Screen Specification

```text
[SCREEN_SPECIFICATION]
```

### 3.2 Design System Snapshot

```text
[DESIGN_SYSTEM_SNAPSHOT]
```

### 3.3 실제 구현 코드

```text
[TARGET_SCREEN]
[RELATED_COMPONENTS]
[RELATED_HOOKS]
[RELATED_API_FUNCTIONS]
[RELATED_TYPES]
[AUTH_OR_PROVIDER_CODE]
[NAVIGATION_CODE]
[SHARED_COMPONENTS_AND_TOKENS]
```

### 3.4 Backend 계약

```text
[BACKEND_ENDPOINT]
[REQUEST_SCHEMA]
[RESPONSE_SCHEMA]
[ERROR_CONTRACT]
[AUTH_REQUIREMENT]
```

### 3.5 변경 범위

```text
[GIT_DIFF_OR_CHANGED_FILES]
```

### 3.6 검증 결과

```text
[TYPESCRIPT_RESULT]
[LINT_OR_FORMAT_RESULT]
[FRONTEND_TEST_RESULT]
[BACKEND_CONTRACT_TEST_RESULT]
[MANUAL_OR_DEVICE_TEST_RESULT]
```

제공되지 않았거나 직접 확인하지 못한 검증 결과는
통과했다고 추정하지 않습니다.

---

## 4. 검토 순서

다음 순서로 확인합니다.

### 4.1 작업 범위와 Diff

* 변경 파일이 승인된 작업 범위 안에 있는지
* 관련 없는 코드나 포맷 변경이 섞이지 않았는지
* 삭제되거나 우회된 기존 동작이 없는지
* 임시 코드, mock, TODO가 의도치 않게 남아 있지 않은지

### 4.2 Screen Specification 정합성

* 화면 목적과 책임이 명세와 일치하는지
* 명세의 Out of Scope 기능을 임의로 추가하지 않았는지
* 필수 화면 상태와 인터랙션이 구현되었는지
* Navigation 결과가 명세와 일치하는지

### 4.3 API 및 데이터 계약

* Method와 Endpoint가 Backend와 일치하는지
* Request와 Response Type이 실제 계약과 일치하는지
* 인증 API에 올바른 API Client를 사용하는지
* 오류 상태와 machine-readable 오류 데이터를 계약대로 처리하는지
* Screen에서 API Function을 직접 호출하지 않는지

### 4.4 상태와 비동기 흐름

* 조회와 Mutation 상태가 Hook에서 적절히 관리되는지
* 로딩, 성공, 오류, 빈 데이터와 처리 중 상태가 구분되는지
* 중복 입력이 방지되는지
* Mutation 후 Query Cache가 계약에 맞게 갱신되는지
* Auth State와 Navigation State의 책임이 섞이지 않는지
* 오래된 비동기 응답이나 중복 요청으로 인한 Race 위험이 없는지

### 4.5 책임 분리

```text
Screen
→ 화면 구성 / 사용자 이벤트 / Navigation

Hook
→ Server State / Mutation / Cache 연결

API Function
→ 서버 통신

Component
→ 재사용 가능한 표현과 상호작용

Provider
→ 여러 화면이 공유하는 앱 수준 상태
```

책임이 한 계층으로 과도하게 몰리지 않았는지 확인합니다.

### 4.6 Design System

* Design System Snapshot의 공통 토큰을 재사용하는지
* 임의 색상, 간격, 타이포그래피, radius가 추가되지 않았는지
* 화면 전용 값을 전역 토큰으로 불필요하게 승격하지 않았는지
* 상태 표현이 색상 하나에만 의존하지 않는지
* 금지된 장식, 아이콘 또는 반복적인 Card 패턴을 추가하지 않았는지

Design System Snapshot이 Candidate이면
검토 결과가 좋다는 이유만으로 자동 Frozen 처리하지 않습니다.

### 4.7 접근성

* 주요 터치 영역이 최소 44×44dp 기준을 만족하는지
* 필요한 accessibilityRole, accessibilityLabel,
  accessibilityState가 제공되는지
* 긴 한글 텍스트와 작은 화면에서 주요 정보가 잘리지 않는지
* Disabled 또는 처리 중 상태를 사용자가 인지할 수 있는지

### 4.8 코드와 의존성

* TypeScript strict 기준에 맞는지
* 암시적 any와 불필요한 type assertion이 없는지
* 사용하지 않는 import와 변수가 없는지
* 실제 존재하지 않는 파일, export, path alias를 참조하지 않는지
* package.json에 없는 라이브러리를 임의로 추가하지 않았는지
* 기존 Shared Component와 Token을 불필요하게 중복 생성하지 않았는지

### 4.9 테스트와 실제 검증

* 변경된 사용자 행동을 검증하는 테스트가 있는지
* API 계약과 오류 경로가 검증되는지
* Auth / Navigation / Cache 영향이 필요한 범위에서 검증되는지
* TypeScript, Lint 또는 Format 결과가 실제 실행 결과인지
* 실기기 또는 Emulator 확인이 필요한 항목이 남아 있는지

테스트 개수 자체보다 어떤 회귀를 막는지를 우선합니다.

---

## 5. 발견 사항 등급

발견 사항은 영향도 기준으로 다음과 같이 구분합니다.

### BLOCKER

명세 또는 공개 API 계약을 위반하여
기능 완료 또는 화면 승격을 막는 문제입니다.

### HIGH

주요 사용자 흐름, 인증, Navigation, 데이터 무결성,
핵심 오류 처리 또는 회귀 가능성에 직접 영향을 주는 문제입니다.

### MEDIUM

당장 핵심 흐름을 막지는 않지만
명세 불일치, 유지보수성 또는 일부 상태 처리에 영향을 주는 문제입니다.

### LOW

동작에는 직접 영향이 작지만
가독성, 일관성 또는 후속 정리가 필요한 문제입니다.

심각도를 높게 보이게 하기 위해 형식적으로 문제를 만들지 않습니다.

---

## 6. 발견 사항 보고 형식

각 발견 사항은 다음 형식으로 작성합니다.

```text
심각도:
영향:
근거 파일 / 위치:
현재 구현:
기준 명세 또는 계약:
재현 조건 또는 실패 경로:
권장 수정 방향:
필요한 테스트 또는 재검증:
```

문제가 없다면 억지로 Findings를 만들지 말고
확인한 범위와 아직 검증되지 않은 위험을 구분해 작성합니다.

---

## 7. Freeze Readiness

`FREEZE_READINESS` 모드에서는 다음 증거를 확인합니다.

```text
Candidate 구현 완료
→ Screen Specification과 실제 구현 일치
→ 주요 정상·오류·빈 상태 검증
→ 우선 화면 너비 검증
→ 접근성 검토
→ 관련 자동 검증 통과
→ 필요한 실기기 또는 Emulator 검증
→ 팀 승인
→ 변경 영향 기록
```

필수 증거가 하나라도 확인되지 않았다면
Frozen으로 추정하지 않고 Candidate를 유지하며
부족한 증거를 명시합니다.

---

## 8. 변경 통제

이 프롬프트의 기본 동작은 Review Only입니다.

문제를 발견하더라도 다음을 임의로 수행하지 않습니다.

* API 계약 변경
* Screen Specification 재설계
* Design System Token 변경
* 새로운 라이브러리 추가
* 범위 밖 Refactor
* 사용자 요청 없는 코드 수정

수정이 필요한 경우 먼저 최소 수정 범위와 영향을 설명합니다.

확정된 설계 자체를 변경해야 해결되는 문제라면
구현 수정과 설계 변경을 분리하여 보고합니다.

---

## 9. 최종 응답 형식

다음 순서로 결과를 제공합니다.

1. 검토 결론
2. 검토 기준 Branch / HEAD
3. BLOCKER / HIGH / MEDIUM / LOW 발견 사항
4. Screen Specification ↔ 구현 정합성
5. API / Type / Hook / Auth / Navigation 계약 검증
6. Design System 및 접근성 검토
7. 테스트와 실제 검증 증거
8. Freeze Readiness
9. 수정이 필요한 문서
10. 권장 최소 수정 범위
11. 남은 미확인 사항

검토 결론은 다음 표현을 사용합니다.

```text
검토 통과
조건부 통과
수정 필요
추가 검증 필요
```

자동 테스트나 실기기 검증을 직접 확인하지 못했다면
그 항목을 `검토 통과`의 근거로 사용하지 않습니다.
