# Trend Leader 화면 명세 작성 프롬프트

## 문서 정보

```text
문서 유형: Prompt Template
실행 시점: 개별 화면 구현 전
출력: 독립적으로 저장 가능한 Screen Specification Markdown 문서
주의: 이 단계에서는 React Native 구현 코드를 작성하지 않음
```

아래의 Trend Leader 제품 정책, Design System Snapshot, 실제 API 계약, Frontend Type과 현재 프로젝트 구조를 기준으로 `[TARGET_SCREEN_NAME]` 화면의 Screen Specification을 작성해주세요.

이 프롬프트의 목적은 화면을 예쁘게 묘사하는 것이 아니라, 구현 전에 화면의 목적, 책임, 정보 계층, 데이터 계약, 상태, 인터랙션, Navigation과 변경 범위를 명확히 동결하는 것입니다.

---

## 1. 작업 정보

```text
대상 화면:
[TARGET_SCREEN_NAME]

화면 명세 파일명:
[TARGET_SCREEN_SPEC_FILENAME]

대상 기능:
[TARGET_FEATURE_NAME]

명세 작업 모드:
[CREATE_DRAFT | REVISE | PROMOTE_CANDIDATE | FREEZE]

현재 문서 상태:
[NOT_CREATED | DRAFT | CANDIDATE | FROZEN]

목표 문서 상태:
[DRAFT | CANDIDATE | FROZEN]

예상 구현 모드:
[EXISTING_API | MOCK_API | UI_ONLY | REFACTOR]
```

### 1.1 명세 작업 모드 정의

#### CREATE_DRAFT

기존 Screen Specification이 없을 때 최초 명세를 작성합니다.

입력 자료가 부족하거나 제품 정책이 확정되지 않은 항목은 추정하지 않고 `TBD`로 남깁니다.

#### REVISE

기존 Screen Specification을 현재 API, Type, 코드, Design System 또는 변경된 제품 정책에 맞게 수정합니다.

기존 결정 중 유지한 내용, 변경한 내용과 변경 이유를 구분합니다.

#### PROMOTE_CANDIDATE

Draft 상태의 명세를 실제 구현 기준으로 사용할 수 있는 Candidate 상태로 승격합니다.

필수 데이터 계약, 화면 책임, 핵심 상태, 주요 인터랙션과 구현 범위가 충분히 결정되었는지 검증합니다.

핵심 미결정 사항이 남아 구현 결과가 크게 달라질 수 있다면 Candidate로 승격하지 않습니다.

#### FREEZE

실제 화면 구현과 검증, 팀 검토가 완료된 Candidate를 Frozen 상태로 전환합니다.

실기기 또는 Emulator 검증 결과와 팀 승인 정보가 없으면 Frozen으로 표시하지 않습니다.

---

## 2. 문서 상태 판단 기준

### Draft

다음 중 하나라도 해당하면 Draft를 유지합니다.

- 필수 API 계약이 확정되지 않음
- 핵심 사용자 행동이 확정되지 않음
- 완료 조건 또는 Navigation 목적지가 불명확함
- 화면의 책임과 비책임을 나눌 수 없음
- 대표 상태를 구현할 수 있을 정도의 정보가 부족함
- 중요한 비즈니스 정책이 `TBD`임

### Candidate

다음 조건을 충족하면 Candidate로 작성할 수 있습니다.

- 화면 목적과 핵심 사용자 목표가 명확함
- 실제 구현에 사용할 데이터 계약 또는 명시적인 UI_ONLY 범위가 있음
- 화면 책임과 비책임이 구분됨
- 정보 계층과 주요 인터랙션이 결정됨
- 필수 로딩·오류·빈 데이터 상태가 정의됨
- 기존 구조 유지 범위와 수정 범위가 구분됨
- 남은 `TBD`가 구현 핵심을 바꾸지 않음

### Frozen

다음 조건을 모두 충족해야 합니다.

- Candidate 구현 완료
- Screen Specification과 구현 결과가 일치함
- 주요 상태 검증 완료
- 우선 화면 너비에서 검증 완료
- 접근성 검토 완료
- 팀 승인 완료
- 변경 영향 기록 완료

요청된 목표 상태와 실제 입력 자료의 완성도가 충돌하면, 상태를 억지로 승격하지 말고 가능한 상태로 작성한 뒤 승격을 막는 항목을 정리해주세요.

---

## 3. Source of Truth

다음 자료를 우선순위에 따라 사용합니다.

```text
1. 실제 Backend Endpoint와 Response Schema
2. 실제 Frontend Type
3. Design System Snapshot
4. 기존 확정 Screen Specification
5. 현재 프로젝트 코드와 폴더 구조
6. 팀이 명시적으로 확정한 제품 정책
7. 현재 Figma 또는 승인된 시각 자료
8. Prompt Template
9. Archive 또는 과거 제안 문서
```

Prompt Template과 Archive 문서는 실제 API 계약, Frontend Type, Design System 또는 현재 코드보다 우선하지 않습니다.

자료가 충돌할 경우 충돌을 숨기거나 임의로 하나를 선택하지 말고 다음 형식으로 기록해주세요.

```text
충돌 항목:
자료 A:
자료 B:
우선 적용한 자료:
적용 근거:
후속 확인 필요 여부:
```

---

## 4. 입력 자료

### 4.1 제품 및 기능 정책

```text
[PRODUCT_AND_FEATURE_POLICIES]
```

확정되지 않은 정책은 다음처럼 표시합니다.

```text
해당 없음
```

또는:

```text
TBD
```

### 4.2 Art Direction

```text
[ART_DIRECTION]
```

### 4.3 Design System Snapshot

```text
[DESIGN_SYSTEM_SNAPSHOT]
```

### 4.4 기존 Screen Specification

신규 작성이라면 다음과 같이 표시합니다.

```text
해당 없음
```

기존 명세가 있다면 전체 내용을 제공합니다.

```text
[EXISTING_SCREEN_SPECIFICATION]
```

### 4.5 Backend API Contract

```text
[BACKEND_ENDPOINT]
[HTTP_METHOD]
[REQUEST_SCHEMA]
[RESPONSE_SCHEMA]
[ERROR_RESPONSE]
[AUTH_REQUIREMENT]
```

API가 필요하지 않은 `UI_ONLY` 화면이면 다음과 같이 표시합니다.

```text
해당 없음
```

API가 아직 구현되지 않았지만 계약만 확정되었다면 구현 여부와 계약 상태를 구분해주세요.

### 4.6 Frontend Type

```text
[FRONTEND_REQUEST_TYPES]
[FRONTEND_RESPONSE_TYPES]
[DOMAIN_TYPES]
[NAVIGATION_TYPES]
```

### 4.7 현재 프로젝트 구조

```text
[CURRENT_PROJECT_STRUCTURE]
```

### 4.8 현재 관련 코드

```text
[EXISTING_SCREEN]
[EXISTING_COMPONENTS]
[EXISTING_HOOKS]
[EXISTING_API_FUNCTIONS]
[EXISTING_TYPES]
[EXISTING_NAVIGATION]
[SHARED_COMPONENTS]
[SHARED_DESIGN_TOKENS]
[API_CLIENT]
```

존재하지 않는 항목은 `해당 없음`으로 표시합니다.

### 4.9 프로젝트 기술 조건

```text
[PACKAGE_JSON]
[TSCONFIG_JSON]
[FRONTEND_CODING_CONVENTION]
```

### 4.10 시각 참고 자료

```text
[APPROVED_FIGMA_OR_VISUAL_REFERENCE]
```

승인되지 않은 과거 시안은 다음처럼 상태를 명시합니다.

```text
참고 자료이며 Source of Truth가 아님
```

---

## 5. 사실과 결정의 분류

명세에 포함하는 중요한 항목은 다음 상태 중 하나로 판단합니다.

| 상태 | 의미 |
|---|---|
| Confirmed | 실제 API, Type, 코드 또는 팀 정책에서 확인됨 |
| Derived | 확인된 자료들을 조합하면 직접 도출할 수 있음 |
| Candidate | 구현 및 검증을 위한 화면 단위 제안 |
| TBD | 자료 부족 또는 팀 결정 필요 |
| Out of Scope | 이번 화면 또는 MVP에서 다루지 않음 |

### 5.1 분류 원칙

- 실제 자료에서 확인되지 않은 내용을 `Confirmed`로 표시하지 않습니다.
- `Derived`는 근거 자료를 함께 설명합니다.
- `Candidate`는 확정된 전역 Design System과 충돌하지 않아야 합니다.
- 핵심 제품 정책을 임의로 `Candidate`로 만들어 확정하지 않습니다.
- `TBD`가 있어도 작성 가능한 범위는 끝까지 작성합니다.
- `TBD`를 숨기기 위해 가짜 API, 필드, Navigation 또는 정책을 만들지 않습니다.

---

## 6. 현재 상태 분석

명세 작성 전에 현재 상태를 먼저 분석해주세요.

### 6.1 현재 구현 구조

다음을 실제 입력 자료 기준으로 정리합니다.

```text
Screen
→ Hook
→ API Function 또는 Data Source
→ API Client
→ Backend
```

현재 구조가 다르다면 실제 구조를 그대로 기록합니다.

### 6.2 현재 구현된 동작

다음을 구분합니다.

- 정상 동작
- 임시 동작
- 미구현
- 사용하지 않는 코드
- 화면 명세와 충돌하는 동작
- 변경하면 안 되는 동작

### 6.3 유지 가능한 요소

다음을 구분합니다.

- API Function
- Hook
- Type
- Navigation
- 로컬 상태
- 오류 처리
- 로딩 처리
- 화면 구조
- Feature 전용 Component
- Shared Component
- 테스트 또는 fixture

### 6.4 개선이 필요한 요소

다음을 구분합니다.

- 하드코딩된 디자인 값
- 과도한 Screen 책임
- 중복 UI
- 잘못된 데이터 흐름
- 접근성 누락
- 작은 화면 문제
- 상태 처리 누락
- 임시 Alert 또는 mock 동작
- 확정되지 않은 Navigation

이 단계에서는 개선 코드를 작성하지 않습니다.

---

## 7. 화면 정의

### 7.1 화면 목적

한 문장으로 작성합니다.

```text
사용자가 [무엇을] 하여 [어떤 결과]를 얻도록 한다.
```

### 7.2 핵심 사용자 목표

사용자가 이 화면에서 반드시 완료해야 하는 핵심 행동을 정의합니다.

### 7.3 보조 사용자 목표

핵심 목표를 방해하지 않는 범위에서 필요한 보조 행동을 정의합니다.

### 7.4 진입 조건

다음을 명확히 구분합니다.

- 어떤 사용자 상태에서 진입하는가
- 어떤 이전 화면 또는 경로에서 진입하는가
- 필요한 인증 상태가 있는가
- 필요한 Navigation parameter가 있는가
- 필요한 사전 데이터가 있는가

근거가 없으면 `TBD`로 표시합니다.

### 7.5 완료 조건

사용자가 어떤 상태가 되면 화면의 핵심 작업이 완료되는지 정의합니다.

### 7.6 이탈 조건

다음을 구분합니다.

- 뒤로 이동
- 완료 후 이동
- 취소
- 앱 종료 또는 Background
- 인증 만료
- 오류로 인한 이탈

명세 근거가 없는 이동은 만들지 않습니다.

---

## 8. 화면 책임

### 8.1 구현할 책임

화면이 직접 책임지는 항목을 작성합니다.

예:

- 화면 레이아웃 조립
- 서버 상태에 따른 UI 분기
- 로컬 선택 상태
- 사용자 이벤트를 Hook 또는 callback에 연결
- Navigation 호출
- 화면 단위 접근성 구조

### 8.2 구현하지 않을 책임

화면이 책임지지 않는 항목을 작성합니다.

예:

- HTTP 요청 구현
- API Response 변환 규칙을 화면에 중복 작성
- 인증 토큰 저장
- 서버 데이터 캐시 정책 직접 관리
- 전역 Design Token 정의
- 다른 화면의 비즈니스 정책
- Backend Validation 대체

### 8.3 Feature 책임과 Shared 책임

다음을 구분합니다.

```text
Feature Local:
[FEATURE_LOCAL_RESPONSIBILITIES]

Shared:
[SHARED_RESPONSIBILITIES]
```

특정 화면 하나에만 필요한 UI를 성급하게 Shared로 승격하지 않습니다.

---

## 9. 사용자 시나리오

핵심 사용자 흐름을 순서대로 작성합니다.

### 9.1 정상 흐름

```text
1.
2.
3.
4.
```

### 9.2 대체 흐름

예:

- 이미 선택된 데이터가 있음
- 사용자가 선택을 취소함
- 일부 선택적 데이터가 없음
- 재진입
- Refresh
- Back navigation

### 9.3 실패 흐름

예:

- 최초 조회 실패
- Mutation 실패
- 인증 만료
- 네트워크 단절
- 유효하지 않은 Navigation parameter

화면에 해당하지 않는 흐름은 넣지 않습니다.

---

## 10. 데이터 계약

### 10.1 사용 API

| 구분 | 값 |
|---|---|
| Endpoint | `[ENDPOINT]` |
| Method | `[METHOD]` |
| 인증 | `[AUTH]` |
| API Function | `[API_FUNCTION]` |
| Hook | `[HOOK]` |
| Request Type | `[REQUEST_TYPE]` |
| Response Type | `[RESPONSE_TYPE]` |

API가 없다면 이유와 현재 구현 모드를 기록합니다.

### 10.2 화면에서 사용하는 필드

| 필드 | Type | nullable | 화면 사용 위치 | fallback | 근거 |
|---|---|---:|---|---|---|
| `[FIELD]` | `[TYPE]` | `[YES/NO]` | `[LOCATION]` | `[FALLBACK]` | `[SOURCE]` |

실제 Type과 Schema에 없는 필드를 만들지 않습니다.

### 10.3 화면에서 사용하지 않는 응답 필드

응답에 존재하지만 이 화면에서 노출하지 않는 필드를 기록합니다.

### 10.4 정렬과 필터

정렬·필터가 Backend 보장인지 Frontend 처리인지 구분합니다.

```text
Backend 보장:
[BACKEND_SORTING_AND_FILTERING]

Frontend 처리:
[FRONTEND_SORTING_AND_FILTERING]
```

근거가 없으면 화면에서 임의로 정렬하지 않습니다.

### 10.5 null, 빈 문자열과 누락 데이터

각 필드의 처리 규칙을 작성합니다.

- 생략
- fallback 문구
- 화면 상태 전환
- placeholder
- 오류 처리

의미 없는 `N/A`, `null`, `undefined`를 사용자에게 노출하지 않습니다.

### 10.6 임시 데이터와 mock

Mock이 필요하다면 실제 계약과 동일한 구조를 사용합니다.

Screen이 mock data를 직접 import하지 않도록 합니다.

---

## 11. 기존 기능 구조 유지 조건

현재 관련 코드가 이미 존재하면 다음 내용을 반드시 작성합니다.

### 11.1 유지할 구조

```text
[CURRENT_DATA_FLOW_TO_KEEP]
```

### 11.2 유지할 파일

| 파일 | 현재 책임 | 유지 이유 | 수정 허용 범위 |
|---|---|---|---|
| `[PATH]` | `[RESPONSIBILITY]` | `[REASON]` | `[ALLOWED_CHANGE]` |

### 11.3 변경 가능한 파일

| 파일 | 변경 목적 | 변경 범위 | 변경하지 않을 내용 |
|---|---|---|---|
| `[PATH]` | `[PURPOSE]` | `[SCOPE]` | `[PROTECTED_BEHAVIOR]` |

### 11.4 신규 파일 후보

새 파일이 꼭 필요한 경우에만 작성합니다.

| 파일 후보 | 책임 | Feature/Shared | 필요한 이유 | 기존 파일로 대체 불가 이유 |
|---|---|---|---|---|
| `[PATH]` | `[RESPONSIBILITY]` | `[SCOPE]` | `[REASON]` | `[WHY_NOT_EXISTING]` |

이 단계에서는 파일을 생성하지 않습니다.

### 11.5 구조 보존 금지 사항

- Screen에서 API Function을 직접 호출하지 않음
- Hook을 불필요하게 삭제하지 않음
- API Response Type을 화면 안에서 다시 정의하지 않음
- 실제 API를 임의로 mock으로 교체하지 않음
- 기존 정상 동작을 디자인 변경과 함께 제거하지 않음
- Feature 전용 컴포넌트를 검증 없이 Shared로 이동하지 않음
- 임시 동작을 최종 정책처럼 문서화하지 않음

---

## 12. 정보 계층

화면에 나타나는 정보를 중요도 순서대로 작성합니다.

```text
1. Primary
2. Secondary
3. Supporting
4. Metadata
5. Action
```

각 항목에 다음 내용을 작성합니다.

| 우선순위 | 정보 | 사용자에게 필요한 이유 | Typography Token | 최대 줄 수 |
|---:|---|---|---|---:|
| 1 | `[CONTENT]` | `[REASON]` | `[TOKEN]` | `[LINES]` |

### 12.1 정보 계층 원칙

- 핵심 정보가 장식과 보조 Action보다 먼저 인식되어야 합니다.
- 모든 텍스트를 굵게 처리하지 않습니다.
- 이미지가 핵심 정보보다 먼저 인식되지 않도록 합니다.
- 메타데이터는 내용 이해에 필요한 범위만 표시합니다.
- 화면 상단을 일반적인 환영 문구로 과도하게 사용하지 않습니다.

---

## 13. 콘텐츠 구조

화면을 위에서 아래 순서로 작성합니다.

```text
1. Screen Container
2. Header
3. Primary Content
4. Secondary Content
5. Feedback Area
6. Bottom Action 또는 Navigation
```

각 영역에 다음을 작성합니다.

| 영역 | 내용 | 표시 조건 | 스크롤 여부 | Design Token | 비고 |
|---|---|---|---|---|---|
| `[AREA]` | `[CONTENT]` | `[CONDITION]` | `[YES/NO]` | `[TOKENS]` | `[NOTE]` |

화면에 존재하지 않는 영역은 만들지 않습니다.

---

## 14. Layout Specification

### 14.1 화면 컨테이너

다음을 정의합니다.

- Safe Area
- 배경
- 좌우 gutter
- 상단 간격
- 하단 간격
- 스크롤 방식
- 고정 영역
- 키보드 처리
- 상태 표시 위치

### 14.2 우선 화면 크기

```text
최소 검증 너비:
360dp

추가 검증 너비:
412dp

방향:
Portrait
```

Design System Snapshot이 다른 값을 정의하면 Snapshot을 따릅니다.

### 14.3 화면 전용 배치 규칙

다음을 명확하게 작성합니다.

- 열 개수
- 항목 간격
- 최소 높이
- 텍스트 정렬
- 고정 Action 위치
- 목록 content padding
- 긴 텍스트 처리
- 동적 데이터 수 대응

### 14.4 화면 전용 값

화면 전용 값이 필요하면 다음 형식으로 작성합니다.

```text
값:
사용 위치:
전역 Token으로 추가하지 않는 이유:
검증 조건:
```

화면 하나에서만 필요한 값을 Design System에 즉시 추가하지 않습니다.

---

## 15. Design System 적용

화면에서 사용할 Design System Token을 역할별로 연결합니다.

### 15.1 Color Mapping

| 화면 역할 | Semantic Token | 사용 위치 |
|---|---|---|
| Canvas | `[TOKEN]` | `[LOCATION]` |
| Surface | `[TOKEN]` | `[LOCATION]` |
| Primary Text | `[TOKEN]` | `[LOCATION]` |
| Secondary Text | `[TOKEN]` | `[LOCATION]` |
| Primary Action | `[TOKEN]` | `[LOCATION]` |
| Selected | `[TOKEN]` | `[LOCATION]` |
| Error | `[TOKEN]` | `[LOCATION]` |

### 15.2 Typography Mapping

| 화면 역할 | Typography Token | 최대 줄 수 |
|---|---|---:|
| Screen Title | `[TOKEN]` | `[LINES]` |
| Description | `[TOKEN]` | `[LINES]` |
| Item Title | `[TOKEN]` | `[LINES]` |
| Metadata | `[TOKEN]` | `[LINES]` |
| Button | `[TOKEN]` | 1 |

### 15.3 Spacing Mapping

| 화면 역할 | Spacing Token |
|---|---|
| Screen Gutter | `[TOKEN]` |
| Header Gap | `[TOKEN]` |
| Section Gap | `[TOKEN]` |
| Item Gap | `[TOKEN]` |
| Content Gap | `[TOKEN]` |
| Bottom Action Gap | `[TOKEN]` |

### 15.4 Shape and Size Mapping

| 화면 역할 | Token |
|---|---|
| Button Height | `[TOKEN]` |
| Touch Target | `[TOKEN]` |
| Surface Radius | `[TOKEN]` |
| Border | `[TOKEN]` |
| Icon Size | `[TOKEN_OR_TBD]` |

Snapshot에 없는 값을 임의로 생성하지 않습니다.

---

## 16. 화면 전용 컴포넌트

각 컴포넌트의 책임을 작성합니다.

| 컴포넌트 | 책임 | 주요 Props | 상태 | API 호출 | Navigation |
|---|---|---|---|---|---|
| `[COMPONENT]` | `[RESPONSIBILITY]` | `[PROPS]` | `[STATES]` | 금지 | callback 우선 |

### 16.1 분리 기준

다음 중 하나 이상을 만족하면 화면 전용 Component 분리를 검토합니다.

- 동일한 UI가 반복됨
- 선택·오류·비활성 등 상태가 복잡함
- Screen의 정보 구조를 가림
- 독립적인 접근성 책임이 있음
- props 기반으로 표현 가능함

### 16.2 분리하지 않는 기준

- 한 번만 사용하는 단순 View 묶음
- 파일만 늘고 책임이 명확하지 않음
- API 또는 Navigation에 과도하게 결합됨
- 범용 `Card`처럼 역할이 모호함

---

## 17. 사용자 인터랙션

각 인터랙션을 표로 작성합니다.

| Trigger | 대상 | 사전 조건 | 처리 | 성공 결과 | 실패 결과 | 중복 입력 방지 |
|---|---|---|---|---|---|---|
| `[ACTION]` | `[TARGET]` | `[PRECONDITION]` | `[HANDLER_OR_HOOK]` | `[SUCCESS]` | `[FAILURE]` | `[RULE]` |

다음을 검토합니다.

- Press
- Long Press
- 선택
- 선택 해제
- 완료
- 재시도
- Refresh
- 뒤로 이동
- 입력
- 제출
- 저장
- 삭제

화면에 없는 인터랙션은 추가하지 않습니다.

---

## 18. 인터랙션 상태

필요한 항목만 선택하여 정의합니다.

```text
default
pressed
focused
selected
disabled
loading
error
```

각 상태에 다음 내용을 작성합니다.

| 상태 | 시각 변화 | 텍스트·아이콘 변화 | 동작 | 접근성 State |
|---|---|---|---|---|
| `[STATE]` | `[VISUAL]` | `[CONTENT]` | `[BEHAVIOR]` | `[A11Y]` |

### 18.1 상태 원칙

- 선택 상태는 색상만으로 표현하지 않습니다.
- 오류 상태에는 사용자에게 이해 가능한 문구를 제공합니다.
- Loading 중 중복 입력을 막습니다.
- Disabled opacity만으로 상태를 표현하지 않습니다.
- Pressed 상태는 짧고 절제되게 표현합니다.

---

## 19. 화면 상태

화면에 실제로 필요한 상태만 정의합니다.

### 19.1 상태 목록

```text
initial_loading
success
empty
error
refreshing
partial_loading
mutation_loading
mutation_error
offline
partial_data
```

### 19.2 상태 명세

| 상태 | 진입 조건 | 유지할 UI | 변경할 UI | 사용자 문구 | 가능한 Action |
|---|---|---|---|---|---|
| `[STATE]` | `[CONDITION]` | `[KEEP]` | `[CHANGE]` | `[COPY]` | `[ACTION]` |

### 19.3 최초 로딩

- 화면 전체를 대체하는지
- Header를 유지하는지
- ActivityIndicator 또는 공통 LoadingView를 사용하는지
- 로딩 문구가 필요한지

### 19.4 빈 데이터

다음을 구분합니다.

- 서버 응답은 성공했지만 목록이 비어 있음
- 필터 결과가 없음
- 필수 데이터가 누락됨
- 사용자가 아직 설정하지 않음

### 19.5 오류

다음을 구분합니다.

- 최초 조회 실패
- Refresh 실패
- Mutation 실패
- 인증 오류
- 데이터 일부 실패

개발자용 오류 메시지를 그대로 사용자에게 노출하지 않습니다.

---

## 20. Navigation

### 20.1 진입

| 항목 | 내용 |
|---|---|
| Route Name | `[ROUTE_NAME]` |
| 진입 화면 | `[SOURCE_SCREEN]` |
| Parameter | `[PARAMETERS]` |
| 인증 필요 | `[YES/NO/TBD]` |

### 20.2 이탈

| 사용자 행동 | 목적지 | 전달 데이터 | Stack 처리 |
|---|---|---|---|
| `[ACTION]` | `[DESTINATION]` | `[DATA]` | `[PUSH/REPLACE/GO_BACK/TBD]` |

Navigation Type과 현재 Navigator에 없는 경로를 만들지 않습니다.

목적지가 확정되지 않았다면 `TBD`로 기록하고 임시 `Alert`와 최종 Navigation을 구분합니다.

---

## 21. 콘텐츠 문구

화면에서 사용할 핵심 문구를 정리합니다.

| 위치 | 문구 | 상태 | 비고 |
|---|---|---|---|
| Screen Title | `[COPY]` | `[CONFIRMED/CANDIDATE]` | `[NOTE]` |
| Description | `[COPY]` | `[STATUS]` | `[NOTE]` |
| Primary Action | `[COPY]` | `[STATUS]` | `[NOTE]` |
| Empty | `[COPY]` | `[STATUS]` | `[NOTE]` |
| Error | `[COPY]` | `[STATUS]` | `[NOTE]` |
| Retry | `[COPY]` | `[STATUS]` | `[NOTE]` |

제품 정책에서 확정되지 않은 문구는 Candidate로 표시합니다.

문구는 다음 원칙을 따릅니다.

- 사용자가 해야 할 행동을 명확히 설명
- 불필요하게 친근한 환영 문구를 추가하지 않음
- 기술 오류 용어를 노출하지 않음
- 같은 행동에 다른 용어를 혼용하지 않음
- 버튼은 짧고 행동 중심으로 작성

---

## 22. 접근성 명세

### 22.1 터치

- 주요 터치 영역 최소 크기
- 인접 터치 영역 간격
- 아이콘과 실제 Pressable 영역 분리

### 22.2 Role

필요한 항목을 지정합니다.

```text
button
header
text
image
adjustable
tab
```

React Native에서 실제 지원 가능한 Role만 사용합니다.

### 22.3 Label과 Hint

아이콘만 있는 버튼에는 `accessibilityLabel`을 정의합니다.

동작 결과가 명확하지 않은 경우에만 `accessibilityHint`를 사용합니다.

### 22.4 State

필요한 항목을 지정합니다.

```text
selected
disabled
busy
checked
expanded
```

### 22.5 색상 외 상태 표현

선택·오류·상승·하락 등의 상태가 색상 없이도 이해 가능한지 정의합니다.

### 22.6 글자 확대

- 고정 높이가 텍스트를 자르지 않는지
- 최대 줄 수가 핵심 의미를 제거하지 않는지
- 버튼 라벨이 잘리지 않는지
- 목록 항목 높이가 확장 가능한지

---

## 23. 작은 화면과 긴 콘텐츠

다음 조건을 검토합니다.

```text
360dp 화면
412dp 화면
긴 한글 화면 제목
긴 항목명
긴 오류 문구
많은 목록 항목
빈 선택적 데이터
텍스트 확대
Safe Area
고정 하단 Action
```

각 위험과 대응을 작성합니다.

| 위험 | 발생 조건 | 대응 |
|---|---|---|
| `[RISK]` | `[CONDITION]` | `[MITIGATION]` |

특정 기기 크기에 맞춘 절대 위치 배치를 사용하지 않습니다.

---

## 24. 이미지와 아이콘

화면에 이미지 또는 아이콘이 실제로 필요한 경우에만 작성합니다.

### 24.1 이미지

| 이미지 | 목적 | 필수 여부 | 비율 | fallback | 접근성 |
|---|---|---|---|---|---|
| `[IMAGE]` | `[PURPOSE]` | `[YES/NO]` | `[RATIO]` | `[FALLBACK]` | `[A11Y]` |

의미 없는 장식용 이미지와 가짜 placeholder를 추가하지 않습니다.

### 24.2 아이콘

| 아이콘 역할 | 상태 | 크기 Token | 색상 Token | Label |
|---|---|---|---|---|
| `[ROLE]` | `[STATE]` | `[TOKEN]` | `[TOKEN]` | `[LABEL]` |

아이콘 패밀리가 확정되지 않았다면 구체적인 패키지 이름을 만들지 않습니다.

이모지를 기능 아이콘으로 사용하지 않습니다.

---

## 25. 구현 영향 범위

### 25.1 수정 대상 후보

| 파일 | 수정 여부 | 수정 목적 | 구조 유지 여부 |
|---|---:|---|---:|
| `[PATH]` | `[YES/NO]` | `[PURPOSE]` | `[YES/NO]` |

### 25.2 생성 대상 후보

| 파일 | 생성 여부 | 책임 | 생성 조건 |
|---|---:|---|---|
| `[PATH]` | `[YES/NO]` | `[RESPONSIBILITY]` | `[CONDITION]` |

### 25.3 변경하지 않을 파일

| 파일 | 유지 이유 |
|---|---|
| `[PATH]` | `[REASON]` |

### 25.4 의존성

새 외부 라이브러리가 필요한지 판단합니다.

```text
추가 의존성:
[없음 | TBD | 제안]

근거:
[REASON]
```

`package.json`에 없는 라이브러리를 당연히 사용할 것으로 가정하지 않습니다.

---

## 26. 미결정 사항

결정이 필요한 항목을 우선순위별로 작성합니다.

| 우선순위 | 항목 | 현재 상태 | 필요한 결정 | 결정 전 가능한 작업 | 영향 |
|---:|---|---|---|---|---|
| 1 | `[DECISION]` | `[STATUS]` | `[NEEDED]` | `[POSSIBLE_WORK]` | `[IMPACT]` |

다음처럼 구분합니다.

```text
Blocking:
구현 시작을 막는 결정

Non-blocking:
Candidate 구현 후 검증 가능한 결정

Future:
MVP 이후 결정
```

Blocking 항목이 있으면 Candidate 또는 Frozen으로 승격하지 않습니다.

---

## 27. Acceptance Criteria

검증 가능한 문장으로 작성합니다.

좋은 예:

```text
- API 조회 중에는 완료 버튼이 중복 실행되지 않는다.
- 선택된 항목은 색상 외 Border 또는 아이콘으로도 구분된다.
- 360dp 화면에서 마지막 목록 항목이 하단 버튼에 가려지지 않는다.
- 빈 배열 응답은 오류가 아니라 Empty 상태로 표시된다.
```

나쁜 예:

```text
- 화면이 예쁘다.
- UX가 좋다.
- 적절하게 동작한다.
```

### 27.1 기능

```text
[FUNCTIONAL_ACCEPTANCE_CRITERIA]
```

### 27.2 상태

```text
[STATE_ACCEPTANCE_CRITERIA]
```

### 27.3 디자인 시스템

```text
[DESIGN_SYSTEM_ACCEPTANCE_CRITERIA]
```

### 27.4 접근성

```text
[ACCESSIBILITY_ACCEPTANCE_CRITERIA]
```

### 27.5 구조 유지

```text
[ARCHITECTURE_ACCEPTANCE_CRITERIA]
```

---

## 28. 검증 계획

### 28.1 정적 검토

- API Schema와 Frontend Type 일치
- 화면 책임과 파일 책임 일치
- Design System Token 매핑
- Navigation Type 존재 여부
- 명세 내 용어 일관성
- `TBD`와 확정 사항 구분

### 28.2 구현 후 검증

- TypeScript strict 검사
- Expo 의존성 검사
- 360dp 화면 확인
- 412dp 화면 확인
- Loading
- Error
- Empty
- 긴 텍스트
- 선택·비활성·처리 중 상태
- 접근성 State
- Background 복귀 또는 재진입이 중요한 화면이면 해당 흐름

### 28.3 Design System Candidate 검증

이 화면이 Design System 대표 검증 화면이라면 다음을 기록합니다.

```text
검증 대상 Token:
[VALIDATED_TOKENS]

검증 대상 Component Policy:
[VALIDATED_COMPONENT_POLICIES]

검증 후 Snapshot 수정 가능 항목:
[POSSIBLE_SNAPSHOT_CHANGES]
```

화면 하나의 문제를 해결하기 위해 전역 Design System을 즉시 변경하지 않습니다.

---

## 29. 화면 명세 출력 형식

최종 결과는 다른 문서 없이도 이해 가능한 하나의 완성된 Markdown 문서로 작성해주세요.

다음 순서를 사용합니다.

```text
# [TARGET_SCREEN_NAME] Screen Specification

## 문서 정보
## 1. 화면 요약
## 2. 결정 상태 요약
## 3. Source of Truth
## 4. 현재 구현 상태
## 5. 화면 목적
## 6. 진입·완료·이탈 조건
## 7. 화면 책임과 비책임
## 8. 사용자 시나리오
## 9. 데이터 계약
## 10. 기존 기능 구조 유지 조건
## 11. 정보 계층
## 12. 콘텐츠 구조
## 13. Layout Specification
## 14. Design System 적용
## 15. 화면 전용 컴포넌트
## 16. 사용자 인터랙션
## 17. 인터랙션 상태
## 18. 화면 상태
## 19. Navigation
## 20. 콘텐츠 문구
## 21. 접근성
## 22. 작은 화면과 긴 콘텐츠
## 23. 이미지와 아이콘
## 24. 구현 영향 범위
## 25. 미결정 사항
## 26. Acceptance Criteria
## 27. 검증 계획
## 28. 변경 이력
```

### 29.1 문서 정보 형식

```text
문서명:
문서 유형: Screen Specification
대상 화면:
대상 기능:
버전:
상태:
예상 구현 모드:
플랫폼:
최종 수정일:
승인자:
관련 API:
관련 Hook:
관련 Design System:
```

### 29.2 결정 상태 요약

다음 표를 포함합니다.

| 분류 | 내용 |
|---|---|
| Confirmed | |
| Derived | |
| Candidate | |
| TBD | |
| Out of Scope | |

### 29.3 변경 이력

| 버전 | 날짜 | 상태 | 변경 내용 | 작성·검토 |
|---|---|---|---|---|
| `[VERSION]` | `[DATE]` | `[STATUS]` | `[CHANGE]` | `[AUTHOR]` |

기존 문서를 수정하는 경우 변경 전후와 변경 이유를 기록합니다.

---

## 30. 작성 규칙

- 결과 문서는 한국어로 작성합니다.
- API 필드명과 코드 식별자는 실제 이름을 유지합니다.
- API Response 필드가 snake_case라면 그대로 유지합니다.
- 제공된 파일 경로와 식별자의 대소문자를 변경하지 않습니다.
- 화면 구현 코드를 작성하지 않습니다.
- TypeScript 코드 블록을 결과물에 포함하지 않습니다.
- 필요할 때만 JSON 또는 Type 구조를 인용합니다.
- 제공되지 않은 API, 필드, 경로, 라이브러리와 Navigation을 만들지 않습니다.
- 확정되지 않은 문구와 디자인 결정은 Candidate로 표시합니다.
- 화면에 필요하지 않은 상태와 기능을 과도하게 추가하지 않습니다.
- 문서만 보고 `04-screen-implementation-prompt.md`를 실행할 수 있을 정도로 구체적으로 작성합니다.
- 설명이 반복되면 표와 참조를 사용하여 중복을 줄입니다.
- 특정 화면 하나에 필요한 값을 전역 Design Token으로 승격하지 않습니다.
- 현재 정상 동작하는 구조를 변경하려면 변경 이유와 영향 범위를 먼저 기록합니다.

---

## 31. 금지 사항

다음을 하지 마세요.

- Screen 구현 코드 생성
- API 계약 추측
- 존재하지 않는 Backend Endpoint 생성
- Frontend Type에 없는 필드 추가
- 임시 Alert를 확정 Navigation으로 해석
- mock 동작을 실제 API 연동으로 표현
- 제품 근거 없이 최소·최대 선택 개수 확정
- 현재 코드 구조를 이유 없이 전면 재설계
- 모든 UI를 공통 Component로 승격
- 범용 `Card` Component 생성 전제
- 모든 콘텐츠를 rounded card로 설계
- 색상만으로 상태 표현
- 이모지를 기능 아이콘으로 사용
- 설치되지 않은 폰트와 아이콘 패키지 가정
- 과거 Archive 문서를 현재 정책보다 우선
- Blocking `TBD`가 있는데 Candidate 또는 Frozen으로 승격
- 팀 승인과 구현 검증 없이 Frozen 표시

---

## 32. 자체 검증

결과를 출력하기 전에 다음 항목을 확인해주세요.

### Source of Truth

1. 실제 API Schema와 Frontend Type을 우선했는가
2. Prompt 또는 Archive가 실제 계약보다 우선하지 않았는가
3. 충돌 사항을 숨기지 않았는가
4. 입력에 없는 필드나 정책을 만들지 않았는가

### 화면 정의

5. 화면 목적이 한 문장으로 명확한가
6. 핵심 사용자 목표가 하나로 수렴하는가
7. 진입·완료·이탈 조건이 구분되는가
8. 화면 책임과 비책임이 구분되는가

### 데이터

9. 모든 화면 필드가 실제 Type 또는 Schema에 존재하는가
10. nullable과 빈 데이터 처리가 정의되었는가
11. 정렬과 필터의 처리 주체가 구분되는가
12. 임시 데이터와 실제 데이터를 구분했는가

### 구조 유지

13. 현재 Screen→Hook→API 흐름을 정확히 기록했는가
14. 유지할 파일과 수정할 파일이 구분되는가
15. 신규 파일이 필요한 이유가 명확한가
16. Feature Local과 Shared 책임을 구분했는가

### UI와 상태

17. 정보 계층이 명확한가
18. Design System Token 매핑이 있는가
19. Loading·Error·Empty 상태가 필요한 범위에서 정의되었는가
20. 인터랙션별 성공·실패·중복 입력 방지가 정의되었는가
21. 작은 화면과 긴 한글 콘텐츠를 고려했는가

### 접근성

22. 최소 터치 영역을 고려했는가
23. Role, Label과 State가 필요한 위치에 정의되었는가
24. 선택·오류 등의 상태가 색상에만 의존하지 않는가
25. 글자 확대 시 위험을 고려했는가

### 문서 상태

26. Draft·Candidate·Frozen 판단이 입력 자료와 일치하는가
27. Blocking `TBD`가 명확히 표시되었는가
28. Acceptance Criteria가 검증 가능한 문장인가
29. 구현 영향 범위가 구체적인가
30. 결과 문서만으로 다음 구현 단계에 진입할 수 있는가

문제가 발견되면 결과를 출력하기 전에 문서에 바로 반영해주세요.

---

## 33. 최종 응답 형식

다음 순서로 응답해주세요.

1. 명세 상태 판단
2. 핵심 확인 사항
3. 충돌 또는 Blocking `TBD`
4. 완성된 Screen Specification 전체 문서
5. 구현 단계 진입 가능 여부
6. 구현 전에 필요한 후속 결정
