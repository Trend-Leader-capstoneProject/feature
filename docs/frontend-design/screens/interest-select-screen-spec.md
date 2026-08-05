# InterestSelectScreen Screen Specification

## 문서 정보

```text
문서명: Trend Leader InterestSelectScreen Screen Specification
문서 유형: Screen Specification
대상 화면: InterestSelectScreen
대상 기능: Interest
버전: 0.1
상태: Candidate
예상 구현 모드: REFACTOR
플랫폼: React Native + Expo, Android 우선
화면 방향: Portrait
최종 수정일: 2026-08-05
승인자: TBD
관련 Backend Endpoint: GET /api/categories
관련 Frontend API Function: getCategories
관련 Hook: useCategories
관련 Navigation Route: InterestSelect
관련 Design System: Design System Snapshot v0.1 Candidate
검증 목적: Design System Candidate의 첫 번째 대표 화면 검증
```

---

## 1. 화면 요약

`InterestSelectScreen`은 사용자가 Trend Leader에서 우선 보고 싶은 대분류 관심 분야를 선택하는 화면이다.

Candidate v0.1의 구현 범위는 다음과 같다.

```text
카테고리 목록 조회
→ 대분류 관심 분야 표시
→ 로컬 선택 및 선택 해제
→ 선택 상태 시각화
→ 로딩·오류·빈 데이터 처리
→ 임시 완료 Action
→ Design System Candidate 검증
```

이번 버전에서는 선택 결과를 서버에 저장하거나 다음 화면으로 이동시키지 않는다.

현재 `handleComplete()`의 Alert 동작은 개발 중 선택 결과를 확인하기 위한 임시 동작으로 유지할 수 있지만, 실제 관심사 저장이나 완료 처리로 간주하지 않는다.

---

## 2. 결정 상태 요약

| 분류 | 내용 |
|---|---|
| Confirmed | `GET /api/categories`로 카테고리 목록을 조회한다. |
| Confirmed | Frontend API Function은 API Client 기준 상대 경로 `/categories`를 사용한다. |
| Confirmed | `useCategories()`가 React Query로 조회 상태를 관리한다. |
| Confirmed | 화면은 `data.categories`에 포함된 최상위 카테고리 목록을 표시한다. |
| Confirmed | 선택값은 `selectedCategoryIds: number[]` 로컬 상태로 관리한다. |
| Confirmed | 같은 카테고리를 다시 누르면 선택이 해제된다. |
| Confirmed | 선택값이 없으면 현재 완료 버튼은 disabled 상태가 된다. |
| Confirmed | 현재 완료 Action은 선택 ID를 Alert로 표시하는 임시 동작이다. |
| Confirmed | 현재 Root Navigator에는 `InterestSelect` Route만 존재하며 parameter는 없다. |
| Derived | 현재 화면은 `CategoryItem.children`을 표시하지 않으므로 대분류 선택 화면으로 동작한다. |
| Candidate | 대분류 카테고리를 2열 FlatList로 표시한다. |
| Candidate | 선택 가능한 항목은 Feature Local `InterestOption`으로 분리한다. |
| Candidate | 화면 Shell, 버튼과 피드백 상태는 Design System Candidate를 적용한다. |
| Candidate | 선택 상태는 배경색뿐 아니라 Strong Border와 “선택됨” 표시로 구분한다. |
| Candidate | 최초 로딩과 오류 상태에서도 화면 제목 영역은 유지한다. |
| TBD | 정식 관심사 저장 Endpoint와 Request Schema |
| TBD | 저장 Mutation Hook |
| TBD | 관심사 최소·최대 선택 개수의 최종 제품 정책 |
| TBD | 저장 성공 후 Navigation 목적지와 Stack 처리 |
| TBD | 회원가입 직후 진입인지, 마이페이지 수정에서도 재사용할지 |
| TBD | 기존 관심사 조회 후 초기 선택값을 주입하는 방식 |
| Out of Scope | 세부분류 `children` 선택 |
| Out of Scope | 관심사 저장 API 구현 |
| Out of Scope | 저장 성공 후 추천 화면 이동 |
| Out of Scope | 관심사 검색 및 필터 |
| Out of Scope | 관심사별 이미지 또는 기능 아이콘 |
| Out of Scope | Dark Mode |
| Out of Scope | 가로 화면 |

---

## 3. Source of Truth

충돌이 있을 경우 다음 순서를 적용한다.

```text
1. Backend Category Endpoint와 Response Schema
2. frontend/src/features/interest/types/category.ts
3. docs/frontend-design/design-system/design-system-snapshot.md
4. 본 interest-select-screen-spec.md
5. 현재 Interest 관련 코드
6. docs/frontend-design/art-direction.md
7. 기존 Figma와 UI/UX 참고 자료
8. Prompt Template
9. Archive 문서
```

### 3.1 실제 Backend 기준

```text
Endpoint:
GET /api/categories

Frontend API Client 상대 경로:
GET /categories
```

API Client의 base URL에 `/api`가 포함되므로 Frontend API Function에서 `/api/categories`를 중복 작성하지 않는다.

### 3.2 실제 Frontend Type 기준

```text
CategoryListData
└── categories: CategoryItem[]

CategoryItem
├── category_id: number
├── category_code: CategoryCode | null
├── category_name: string
├── parent_id: number | null
├── sort_order: number
└── children: CategoryItem[]
```

### 3.3 Design System 기준

```text
Art Direction:
Signal Editorial + Trend Radar

우선 플랫폼:
Android

우선 너비:
360~412dp

화면 배경:
backgroundCanvas

화면 좌우 gutter:
screenGutter = 20dp

기본 타이포그래피:
screenTitle
body
itemTitle
button
caption

선택 Surface:
backgroundSelected
borderSelected
borderWidthStrong
radiusMedium

Primary Action:
actionPrimary
actionPrimaryPressed
actionDisabled
```

### 3.4 현재 코드 기준

```text
Screen
→ useCategories
→ getCategories
→ apiRequest
→ GET /api/categories
```

이 구조는 유지한다.

---

## 4. 현재 구현 상태

### 4.1 현재 파일 구조

```text
frontend/src/
├── app/
│   ├── navigation/
│   │   └── RootNavigator.tsx
│   └── providers/
│       └── QueryProvider.tsx
│
├── features/
│   └── interest/
│       ├── api/
│       │   └── getCategories.ts
│       ├── hooks/
│       │   └── useCategories.ts
│       ├── screens/
│       │   └── InterestSelectScreen.tsx
│       └── types/
│           └── category.ts
│
└── shared/
    └── api/
        └── apiClient.ts
```

### 4.2 정상 동작

- `useCategories()`로 카테고리 목록을 조회한다.
- React Query Query Key로 `["categories"]`를 사용한다.
- Query stale time은 30분이다.
- 조회 실패 시 React Query retry를 1회 수행한다.
- 조회 중 `ActivityIndicator`와 로딩 문구를 표시한다.
- 조회 실패 시 오류 메시지와 재시도 버튼을 표시한다.
- 성공 응답의 `data.categories`를 목록 데이터로 사용한다.
- `FlatList`에 안정적인 `category_id` key를 사용한다.
- 목록은 2열로 표시된다.
- 카테고리를 누르면 ID가 선택 상태에 추가된다.
- 이미 선택된 카테고리를 누르면 ID가 제거된다.
- 선택 항목은 `accessibilityState.selected`를 제공한다.
- 카테고리가 비어 있으면 빈 데이터 문구를 표시한다.
- 선택값이 없으면 완료 버튼이 비활성화된다.

### 4.3 임시 동작

현재 완료 버튼은 서버 저장을 수행하지 않는다.

```text
선택 완료
→ handleComplete()
→ Alert
→ 선택한 category_id 목록 표시
```

이 Alert는 개발 확인용이며 다음을 의미하지 않는다.

- 서버 저장 성공
- 온보딩 완료
- 관심사 등록 완료
- 추천 데이터 생성 완료
- 다음 화면 Navigation 완료

### 4.4 미구현

- 관심사 저장 API Function
- 관심사 저장 Mutation Hook
- Mutation loading
- Mutation error
- 저장 성공 처리
- 완료 후 Navigation
- 기존 관심사 초기값 조회
- 선택 개수 정책 검증
- 인증 상태 연결
- Design Token TypeScript 파일
- Design System 공통 컴포넌트

### 4.5 개선이 필요한 부분

- 색상, 간격, 글자 크기와 radius가 Screen StyleSheet에 직접 작성되어 있다.
- 최초 로딩 시 화면 제목과 설명까지 사라진다.
- 오류 상태에서 `error.message`를 사용자에게 직접 노출한다.
- 선택 상태가 주로 배경색과 텍스트 색상 변화에 의존한다.
- 완료 버튼의 접근성 상태를 명시적으로 검토해야 한다.
- 현재 category Surface의 radius와 배경색이 Design System Candidate와 다르다.
- 현재 화면은 모든 UI 책임을 하나의 Screen 파일에 포함한다.
- 정식 완료 조건과 Navigation이 없다.

---

## 5. 화면 목적

사용자가 Trend Leader에서 보고 싶은 대분류 관심 분야를 선택하여 개인화 트렌드 추천에 사용할 선택값을 준비하도록 한다.

### 5.1 Candidate v0.1의 실제 목표

Candidate v0.1에서는 서버 저장까지 완료하지 않는다.

이번 버전의 핵심 목표는 다음과 같다.

```text
실제 Category API를 통해 관심 분야를 조회하고,
사용자가 여러 대분류를 명확하고 접근 가능하게 선택하며,
Design System Candidate가 실제 선택 화면에 적절한지 검증한다.
```

### 5.2 핵심 사용자 목표

- 관심 분야 목록을 확인한다.
- 원하는 대분류 관심 분야를 하나 이상 선택하거나 선택 해제한다.
- 현재 어떤 항목이 선택되었는지 명확히 확인한다.
- 선택 결과 확인용 완료 Action을 실행한다.

### 5.3 보조 사용자 목표

- 조회 실패 시 다시 시도한다.
- 카테고리 목록이 비어 있음을 이해한다.
- 긴 카테고리명에서도 항목의 의미를 확인한다.

---

## 6. 진입·완료·이탈 조건

### 6.1 진입 조건

| 항목 | Candidate v0.1 |
|---|---|
| Route Name | `InterestSelect` |
| Navigation Parameter | 없음 |
| Stack Header | 숨김 |
| 현재 진입 구조 | Root Navigator의 유일한 Screen |
| 인증 필요 여부 | TBD |
| 회원가입 완료 필요 여부 | 제품 방향상 예상되지만 현재 코드에서 강제하지 않음 |
| 사전 데이터 | 없음 |
| API 호출 | 화면 진입 시 `useCategories()` 실행 |

### 6.2 완료 조건

#### Candidate v0.1

```text
사용자가 하나 이상의 대분류 카테고리를 선택하고
임시 완료 Action을 실행하면 현재 선택 ID를 개발용 Alert로 확인한다.
```

이는 화면 UI 검증 완료 조건이며 제품 기능 완료 조건이 아니다.

#### 최종 제품

다음 사항이 확정된 후 별도 개정한다.

```text
1. 선택 개수 정책 충족
2. 관심사 저장 Mutation 성공
3. 서버 상태 반영
4. 다음 Route 이동 또는 현재 화면 종료
```

### 6.3 이탈 조건

| 이탈 방식 | 현재 상태 | Candidate 처리 |
|---|---|---|
| Android Back | Root Screen이므로 앱 종료로 이어질 수 있음 | 현재 Navigation 기본 동작 유지 |
| 완료 후 이동 | 미구현 | TBD |
| 취소 | 미구현 | 이번 버전 Out of Scope |
| 앱 Background | React Navigation Screen이 유지되면 로컬 선택 유지 가능 | 별도 영속화 없음 |
| 앱 프로세스 종료 | 로컬 선택 초기화 | 현재 범위에서 허용 |
| 인증 만료 | 인증 연결 미구현 | Out of Scope |

---

## 7. 화면 책임과 비책임

### 7.1 Screen이 담당할 책임

- 화면 전체 레이아웃 조립
- Header, Category List와 Bottom Action 구성
- `useCategories()`의 조회 상태에 따른 UI 분기
- `selectedCategoryIds` 로컬 상태 관리
- 카테고리 선택과 선택 해제 이벤트
- 임시 완료 이벤트 연결
- 재시도 이벤트 연결
- 화면 단위 접근성 구조
- Feature 전용 Component에 props 전달

### 7.2 Screen이 담당하지 않을 책임

- HTTP 요청 구현
- API base URL 구성
- Backend Response Schema 정의
- React Query Query Function 구현
- 서버 캐시 정책 직접 관리
- 인증 토큰 저장
- 관심사 저장 Mutation 구현
- 추천 생성
- 전역 Design Token 정의
- 공통 컴포넌트 내부 스타일 정의
- Navigation Route 임의 생성
- 최소·최대 선택 개수 정책 확정

### 7.3 Feature Local 책임

```text
InterestOption
- 카테고리 이름 표시
- 선택·해제 Press 이벤트 전달
- selected 상태 시각화
- accessibilityRole
- accessibilityState.selected
- 긴 항목명 처리
```

### 7.4 Shared 책임

Candidate 구현 시 다음 공통 책임을 사용할 수 있다.

```text
ScreenContainer
- Safe Area
- Canvas
- Screen gutter
- 기본 top/bottom spacing

PrimaryButton
- Primary Action 상태
- disabled
- pressed
- loading 확장 가능 구조
- 접근성 상태

LoadingView
- 공통 로딩 표시

ErrorView
- 사용자용 오류 문구
- Retry Action

EmptyView
- 빈 데이터 안내
```

기존 공통 컴포넌트가 없으면 첫 번째 검증 화면에서 Candidate로 생성할 수 있다.

---

## 8. 사용자 시나리오

### 8.1 정상 흐름

```text
1. 사용자가 InterestSelect Route에 진입한다.
2. 화면은 Category API 조회를 시작한다.
3. 화면 제목과 설명을 유지한 채 목록 영역에 로딩 상태를 표시한다.
4. 조회 성공 시 Backend가 제공한 순서대로 대분류 카테고리를 표시한다.
5. 사용자가 관심 카테고리를 누른다.
6. 해당 category_id가 selectedCategoryIds에 추가된다.
7. 항목은 선택 Surface와 “선택됨” 표시로 변경된다.
8. 사용자가 다시 누르면 해당 category_id가 제거된다.
9. 하나 이상의 항목이 선택되면 완료 버튼이 활성화된다.
10. 사용자가 완료 버튼을 누른다.
11. Candidate v0.1에서는 선택 ID를 개발용 Alert로 확인한다.
```

### 8.2 대체 흐름

#### 여러 항목 선택

- 각 항목은 독립적으로 선택할 수 있다.
- 선택 순서와 관계없이 ID 중복은 허용하지 않는다.
- 선택 배열은 현재 사용자가 선택한 ID만 포함한다.

#### 선택 해제

- 선택된 항목을 다시 누르면 선택이 해제된다.
- 모든 항목을 해제하면 완료 버튼은 disabled 상태로 돌아간다.

#### 재진입

- Screen이 Stack에서 unmount되지 않았다면 현재 로컬 선택값이 유지될 수 있다.
- Screen이 unmount되거나 앱 프로세스가 종료되면 선택값은 초기화된다.
- 영속화 정책은 저장 API 도입 후 결정한다.

### 8.3 실패 흐름

#### 최초 조회 실패

```text
API 조회 실패
→ Header 유지
→ ErrorView 표시
→ 사용자용 오류 문구
→ 다시 시도 Action
```

#### Retry 실패

- ErrorView를 유지한다.
- 개발자용 원본 오류 메시지를 직접 노출하지 않는다.
- 재시도 버튼은 중복 실행을 방지할 수 있어야 한다.

#### 빈 배열 응답

```text
HTTP 성공
+ categories.length === 0
→ 오류가 아닌 Empty 상태
→ 완료 버튼 disabled
```

---

## 9. 데이터 계약

### 9.1 사용 API

| 구분 | 값 |
|---|---|
| Server Endpoint | `GET /api/categories` |
| Frontend API 상대 경로 | `/categories` |
| Request Body | 없음 |
| Query Parameter | 없음 |
| Frontend API Function | `getCategories()` |
| Hook | `useCategories()` |
| Query Key | `["categories"]` |
| staleTime | 30분 |
| retry | 1회 |
| Response Type | `CategoryListData` |
| 인증 | 현재 Category 조회 코드에서 별도 인증 정책 확인 안 됨 |

### 9.2 Response Wrapper

```text
CommonResponse<CategoryListData>
├── success: true
├── statusCode: number
├── message: string
└── data: CategoryListData
```

`getCategories()`는 Wrapper 전체를 Screen에 전달하지 않고 `response.data`만 반환한다.

### 9.3 화면 사용 필드

| 필드 | Type | nullable | 화면 사용 위치 | fallback | 근거 |
|---|---|---:|---|---|---|
| `categories` | `CategoryItem[]` | 아니요 | FlatList data | `[]` | `CategoryListData` |
| `category_id` | `number` | 아니요 | key, 선택 상태 | 없음 | `CategoryItem` |
| `category_name` | `string` | 아니요 | 항목 Label | 빈 문자열을 별도 생성하지 않음 | `CategoryItem` |

### 9.4 화면에서 사용하지 않는 필드

| 필드 | 현재 처리 | 이유 |
|---|---|---|
| `category_code` | 표시하지 않음 | 사용자 Label은 `category_name` 사용 |
| `parent_id` | 표시하지 않음 | Backend가 최상위 목록 구조를 제공 |
| `sort_order` | Frontend 재정렬에 사용하지 않음 | Backend 제공 순서를 유지 |
| `children` | 표시하지 않음 | Candidate v0.1은 대분류 선택만 검증 |

### 9.5 정렬

```text
Backend:
활성 카테고리를 화면 노출 순서에 맞춰 반환

Frontend:
추가 정렬하지 않음
data.categories 순서를 그대로 사용
```

### 9.6 null과 누락 데이터

- `category_id` 또는 `category_name`은 Type상 필수이므로 정상 데이터로 간주한다.
- `category_code`가 null이어도 화면 렌더링에는 영향이 없다.
- `children`이 빈 배열이어도 화면 렌더링에는 영향이 없다.
- `categories`가 빈 배열이면 Empty 상태를 표시한다.
- API 응답 구조가 Type과 다르면 Error 상태로 처리하며 화면에서 보정하지 않는다.

---

## 10. 기존 기능 구조 유지 조건

### 10.1 유지할 데이터 흐름

```text
InterestSelectScreen
→ useCategories
→ getCategories
→ apiRequest
→ GET /api/categories
```

### 10.2 유지할 파일

| 파일 | 현재 책임 | 유지 이유 | 수정 허용 범위 |
|---|---|---|---|
| `frontend/src/features/interest/api/getCategories.ts` | Category API 호출 | API 책임이 분리되어 정상 동작 | Type import 정리와 formatting만 허용 |
| `frontend/src/features/interest/hooks/useCategories.ts` | React Query 조회 상태 | Screen과 서버 상태가 분리됨 | formatting, 명시적 반환 타입 검토 |
| `frontend/src/features/interest/types/category.ts` | API Response Type | 실제 계약 기준 | CommonResponse 위치 재검토는 별도 작업 |
| `frontend/src/shared/api/apiClient.ts` | 공통 HTTP 요청 | API base URL와 오류 처리의 공통 책임 | 이번 화면 작업에서 기능 변경 금지 |
| `frontend/src/app/providers/QueryProvider.tsx` | Query Client 제공 | 현재 조회 Hook 실행에 필요 | 이번 화면 작업에서 기능 변경 금지 |
| `frontend/src/app/navigation/RootNavigator.tsx` | Route 등록 | 현재 진입 구조 | 새 목적지가 확정되기 전 Route 추가 금지 |

### 10.3 변경 가능한 파일

| 파일 | 변경 목적 | 변경 범위 | 변경하지 않을 내용 |
|---|---|---|---|
| `frontend/src/features/interest/screens/InterestSelectScreen.tsx` | 디자인 시스템 적용과 책임 분리 | Layout, 상태 분기, 선택 UI, 접근성 | `useCategories()` 사용, 로컬 선택 동작 |
| `frontend/src/app/navigation/RootNavigator.tsx` | 필요 시 Screen options 정리 | `InterestSelect` 기존 Route 유지 | 임의 Route 생성 금지 |

### 10.4 신규 파일 후보

| 파일 후보 | 책임 | 범위 | 필요한 이유 |
|---|---|---|---|
| `frontend/src/features/interest/components/InterestOption.tsx` | 선택 가능한 카테고리 Surface | Feature Local | 반복 UI와 selected 접근성 책임 분리 |
| `frontend/src/shared/constants/colors.ts` | Color Token | Shared | Design System의 색상 하드코딩 제거 |
| `frontend/src/shared/constants/spacing.ts` | Spacing Token | Shared | 전역 간격 적용 |
| `frontend/src/shared/constants/typography.ts` | Typography Token | Shared | 전역 텍스트 역할 적용 |
| `frontend/src/shared/constants/radius.ts` | Radius Token | Shared | Surface shape 통일 |
| `frontend/src/shared/constants/borders.ts` | Border Token | Shared | selected·default border 통일 |
| `frontend/src/shared/constants/sizes.ts` | Control과 Touch 크기 | Shared | 최소 터치 영역 통일 |
| `frontend/src/shared/constants/index.ts` | Token export | Shared | import 경로 정리 |
| `frontend/src/shared/components/ScreenContainer.tsx` | Safe Area와 Canvas | Shared Candidate | 최상위 화면 반복 책임 |
| `frontend/src/shared/components/PrimaryButton.tsx` | 공통 Primary Action | Shared Candidate | disabled·pressed·접근성 정책 통일 |
| `frontend/src/shared/components/LoadingView.tsx` | 공통 로딩 상태 | Shared Candidate | 화면 상태 중복 방지 |
| `frontend/src/shared/components/ErrorView.tsx` | 오류와 Retry | Shared Candidate | 원본 오류 노출 방지 |
| `frontend/src/shared/components/EmptyView.tsx` | 빈 데이터 | Shared Candidate | 공통 Empty 정책 적용 |

### 10.5 생성하지 않을 파일

- 범용 `Card.tsx`
- 범용 `Badge.tsx`
- 관심사 전용 API를 우회하는 mock data 파일
- Screen 내부 Type을 다시 정의하는 파일
- 확인되지 않은 저장 API Function
- 확인되지 않은 Mutation Hook
- 확인되지 않은 다음 Screen

---

## 11. 정보 계층

| 우선순위 | 정보 | 사용자에게 필요한 이유 | Typography Token | 최대 줄 수 |
|---:|---|---|---|---:|
| 1 | `관심 분야를 선택해 주세요` | 화면의 핵심 행동 설명 | `screenTitle` | 2 |
| 2 | 선택한 관심 분야를 기반으로 맞춤 트렌드를 추천한다는 설명 | 선택 결과의 의미 설명 | `body` | 3 |
| 3 | 각 대분류 `category_name` | 실제 선택 대상 | `itemTitle` | 2 |
| 4 | 선택 상태 표시 | 현재 선택 결과 확인 | `label` | 1 |
| 5 | 로딩·오류·빈 데이터 문구 | 현재 시스템 상태 이해 | `body` 또는 `caption` | 3 |
| 6 | `선택 완료` | 선택 결과 확인 Action | `button` | 1 |

### 11.1 계층 원칙

- 화면 제목이 카테고리 Surface보다 먼저 인식되어야 한다.
- 설명은 제목보다 약하게 표현한다.
- 카테고리 이름은 모든 항목에서 동일한 역할을 가진다.
- 선택 상태는 이름보다 과도하게 강조하지 않는다.
- 완료 버튼은 화면의 유일한 Primary Action이다.
- 장식 이미지, 환영 문구와 설명용 이모지를 추가하지 않는다.

---

## 12. 콘텐츠 구조

| 순서 | 영역 | 내용 | 표시 조건 | 스크롤 |
|---:|---|---|---|---|
| 1 | Screen Container | Safe Area, Canvas, gutter | 항상 | 아니요 |
| 2 | Header | 화면 제목과 설명 | 항상 | 목록과 함께 유지 |
| 3 | Feedback Area | Loading, Error 또는 Empty | 상태에 따라 | 목록 영역 |
| 4 | Primary Content | 2열 대분류 선택 목록 | 조회 성공 및 데이터 존재 | 예 |
| 5 | Bottom Action | 선택 완료 버튼 | 항상 | 목록 밖 |

### 12.1 정상 구조

```text
ScreenContainer
├── Header
│   ├── Screen Title
│   └── Description
├── Content Region
│   └── FlatList
│       └── InterestOption[]
└── Bottom Action
    └── PrimaryButton
```

### 12.2 상태 구조

```text
ScreenContainer
├── Header
├── LoadingView | ErrorView | EmptyView | FlatList
└── PrimaryButton
```

Header와 Bottom Action의 기본 위치는 상태에 따라 불필요하게 이동하지 않아야 한다.

---

## 13. Layout Specification

### 13.1 화면 컨테이너

| 항목 | Candidate |
|---|---|
| Safe Area | 적용 |
| Background | `backgroundCanvas` |
| 좌우 gutter | `screenGutter` |
| 상단 간격 | `screenTopSpacing` |
| 하단 간격 | `screenBottomSpacing` |
| 기본 정렬 | 왼쪽 정렬 |
| 방향 | Portrait |
| Keyboard | 입력 요소 없음 |
| Status Bar | dark content |
| Scroll | Category FlatList만 스크롤 |

### 13.2 검증 화면 너비

```text
최소:
360dp

추가:
412dp
```

### 13.3 Header

```text
Title
→ contentGap
→ Description
→ sectionGap
→ Category Content
```

- Title은 최대 2줄을 허용한다.
- Description은 최대 3줄을 허용한다.
- Header를 과도하게 크게 만들지 않는다.
- 화면 상단에 로고나 일러스트를 필수로 추가하지 않는다.

### 13.4 Category Grid

| 항목 | Candidate |
|---|---|
| Component | `FlatList<CategoryItem>` |
| 열 수 | 2 |
| Row gap | `space3` |
| Column gap | `space3` |
| 항목 최소 높이 | 112dp 화면 전용 Candidate |
| 항목 너비 | FlatList 열 배치에 따라 균등 |
| Radius | `radiusMedium` |
| Default Border | `borderWidthDefault`, `borderDefault` |
| Selected Border | `borderWidthStrong`, `borderSelected` |
| Default Background | `backgroundSurface` 또는 `backgroundSubtle` |
| Selected Background | `backgroundSelected` |
| Label 정렬 | 왼쪽 정렬 Candidate |
| 선택 표시 | 오른쪽 상단 또는 Label 하단의 `선택됨` 표시 |

### 13.5 화면 전용 값

```text
값:
InterestOption minHeight 112dp

사용 위치:
대분류 선택 Surface

전역 Token으로 추가하지 않는 이유:
현재 InterestSelectScreen의 2열 선택 UI에서만 검증된 값이며
다른 화면의 Surface 높이로 일반화할 근거가 없음

검증 조건:
360dp와 412dp 화면
긴 카테고리명
텍스트 확대
터치 영역
```

### 13.6 Bottom Action

- FlatList 밖에 배치한다.
- 버튼이 목록 마지막 항목을 가리지 않아야 한다.
- 목록에 충분한 `contentContainerStyle` 하단 padding을 제공한다.
- `minHeight: buttonHeight`를 사용한다.
- 선택값이 없으면 disabled 처리한다.
- 현재 Mutation이 없으므로 loading 상태는 표시하지 않는다.
- 저장 Mutation 도입 시 `busy`와 중복 입력 방지를 추가한다.

---

## 14. Design System 적용

### 14.1 Color Mapping

| 화면 역할 | Semantic Token | 사용 위치 |
|---|---|---|
| Canvas | `backgroundCanvas` | 화면 전체 |
| Surface | `backgroundSurface` | 기본 InterestOption |
| Subtle Surface | `backgroundSubtle` | 필요 시 기본 옵션 배경 |
| Selected Background | `backgroundSelected` | 선택된 InterestOption |
| Primary Text | `textPrimary` | 제목, 항목 이름 |
| Secondary Text | `textSecondary` | 설명, 상태 문구 |
| Brand Text | `textBrand` | 선택 상태 보조 Label |
| Default Border | `borderDefault` | 기본 InterestOption |
| Selected Border | `borderSelected` | 선택된 InterestOption |
| Error | `statusNegative` | ErrorView |
| Error Background | `statusNegativeSubtle` | ErrorView 필요 시 |
| Primary Action | `actionPrimary` | 완료 버튼 |
| Primary Pressed | `actionPrimaryPressed` | 완료 버튼 pressed |
| Disabled Action | `actionDisabled` | 완료 버튼 disabled |
| Disabled Text | `actionDisabledText` | 완료 버튼 disabled label |

`signalHighlight`는 트렌드 데이터 신호가 아니므로 이 화면에서 사용하지 않는다.

### 14.2 Typography Mapping

| 화면 역할 | Token | 최대 줄 수 |
|---|---|---:|
| Screen Title | `screenTitle` | 2 |
| Description | `body` | 3 |
| Category Name | `itemTitle` | 2 |
| Selected Label | `label` | 1 |
| State Message | `body` | 3 |
| Secondary State | `caption` | 2 |
| Button | `button` | 1 |

### 14.3 Spacing Mapping

| 화면 역할 | Token |
|---|---|
| Screen Gutter | `screenGutter` |
| Screen Top | `screenTopSpacing` |
| Screen Bottom | `screenBottomSpacing` |
| Title과 Description | `contentGap` |
| Header와 목록 | `sectionGap` |
| Grid 항목 | `space3` |
| 상태 내부 | `feedbackGap` |
| 목록과 Bottom Action | `bottomActionGap` |
| 선택 표시와 이름 | `inlineGap` |

### 14.4 Shape and Size Mapping

| 화면 역할 | Token |
|---|---|
| InterestOption Radius | `radiusMedium` |
| Default Border | `borderWidthDefault` |
| Selected Border | `borderWidthStrong` |
| Button Height | `buttonHeight` |
| 최소 Touch Target | `touchTarget` |
| Loading Indicator | React Native 기본 `ActivityIndicator` |
| 아이콘 | 사용하지 않음 |

### 14.5 Elevation

InterestOption과 완료 버튼에 기본 Elevation을 사용하지 않는다.

구분은 다음 순서로 처리한다.

```text
Background
→ Border
→ Spacing
→ Typography
```

---

## 15. 화면 전용 컴포넌트

### 15.1 InterestOption

| 항목 | 명세 |
|---|---|
| 책임 | 대분류 카테고리 이름과 선택 상태 표시 |
| 범위 | Feature Local |
| API 호출 | 금지 |
| Navigation | 금지 |
| 상태 | default, pressed, selected |
| 최소 높이 | 112dp Candidate |
| 최소 터치 영역 | 44×44dp 이상 |
| Label 최대 줄 | 2 |
| 접근성 Role | `button` |
| 접근성 State | `selected` |
| 주요 Props | `category`, `selected`, `onPress` |

개념적 Props:

```text
category: CategoryItem
selected: boolean
onPress: (categoryId: number) => void
```

실제 TypeScript 코드는 구현 단계에서 작성한다.

### 15.2 PrimaryButton

공통 Candidate를 사용하는 경우 다음 상태를 지원한다.

```text
default
pressed
disabled
```

저장 Mutation이 도입되면 다음을 추가한다.

```text
loading
accessibilityState.busy
```

### 15.3 LoadingView

- ActivityIndicator
- 사용자용 로딩 문구
- Content Region 안에서 표시
- Header 유지

### 15.4 ErrorView

- 사용자용 오류 요약
- 다시 시도 Action
- 개발자용 `error.message` 직접 노출 금지
- Retry 중복 입력 방지 검토

### 15.5 EmptyView

- `표시할 관심 분야가 없습니다.` 문구
- 오류와 구분
- 현재 별도 Action 없음
- 완료 버튼 disabled 유지

---

## 16. 사용자 인터랙션

| Trigger | 대상 | 사전 조건 | 처리 | 성공 결과 | 실패 결과 | 중복 입력 방지 |
|---|---|---|---|---|---|---|
| Press | InterestOption | Category 존재 | category_id toggle | selected 상태 변경 | 해당 없음 | React state updater |
| Press | 선택된 InterestOption | selected | category_id 제거 | default 상태 변경 | 해당 없음 | React state updater |
| Press | 완료 버튼 | selected ID 1개 이상 | 임시 `handleComplete` | 개발용 Alert | 해당 없음 | 현재 동기 동작 |
| Press | 완료 버튼 | selected ID 없음 | 실행하지 않음 | disabled 유지 | 해당 없음 | `disabled` |
| Press | 다시 시도 | Query Error | `refetch()` | Loading 후 성공 또는 오류 | ErrorView 유지 | Retry 상태 검토 |

### 16.1 선택 로직

```text
현재 ID가 배열에 없음:
추가

현재 ID가 배열에 있음:
제거
```

- ID 중복을 허용하지 않는다.
- Backend 데이터 자체를 변경하지 않는다.
- `CategoryItem` 객체 전체를 선택 상태에 저장하지 않는다.
- 선택 순서는 제품 의미로 사용하지 않는다.

### 16.2 완료 로직

Candidate v0.1에서는 현재 임시 동작을 보존한다.

```text
selectedCategoryIds.length === 0
→ disabled

selectedCategoryIds.length > 0
→ enabled
→ 개발용 Alert
```

정식 저장 API가 추가되면 별도 Screen Specification 개정이 필요하다.

---

## 17. 인터랙션 상태

### 17.1 InterestOption

| 상태 | 시각 변화 | 텍스트·표시 | 동작 | 접근성 |
|---|---|---|---|---|
| default | 기본 Surface와 Border | category_name | 선택 가능 | `selected: false` |
| pressed | 짧은 pressed Surface 변화 | 유지 | Press feedback | button |
| selected | selected 배경 + Strong Border | category_name + `선택됨` | 선택 해제 가능 | `selected: true` |
| disabled | 현재 사용하지 않음 | 해당 없음 | 해당 없음 | 해당 없음 |

### 17.2 PrimaryButton

| 상태 | 시각 변화 | 동작 | 접근성 |
|---|---|---|---|
| disabled | `actionDisabled` | Press 차단 | `disabled: true` |
| default | `actionPrimary` | 완료 실행 | `disabled: false` |
| pressed | `actionPrimaryPressed` | 짧은 feedback | button |
| loading | 저장 API 도입 전 사용 안 함 | 중복 입력 차단 | `busy: true` |

### 17.3 선택 상태 비색상 표현

선택 상태는 다음 중 두 가지 이상을 함께 사용한다.

```text
- Strong Border
- “선택됨” 텍스트
- 향후 아이콘 패밀리 확정 후 Check icon
```

Candidate v0.1에서는 아이콘 라이브러리를 추가하지 않으므로 Strong Border와 텍스트를 사용한다.

---

## 18. 화면 상태

### 18.1 상태 목록

```text
initial_loading
success_unselected
success_selected
empty
error
retrying
```

다음 상태는 이번 버전에서 사용하지 않는다.

```text
refreshing
mutation_loading
mutation_error
offline 전용 화면
partial_data
```

### 18.2 상태 명세

| 상태 | 진입 조건 | 유지할 UI | 변경할 UI | 사용자 문구 | Action |
|---|---|---|---|---|---|
| `initial_loading` | Query pending | Header, Bottom Action | Content에 LoadingView | `관심 분야를 불러오고 있습니다.` | 없음 |
| `success_unselected` | 데이터 존재, 선택 0개 | 전체 | 기본 옵션, disabled 버튼 | Header 문구 | 카테고리 선택 |
| `success_selected` | 데이터 존재, 선택 1개 이상 | 전체 | selected 옵션, enabled 버튼 | 필요 시 선택 상태 | 선택·해제·완료 |
| `empty` | Query 성공, categories 빈 배열 | Header, Bottom Action | EmptyView, disabled 버튼 | `표시할 관심 분야가 없습니다.` | 없음 |
| `error` | Query 실패 | Header, Bottom Action | ErrorView | 사용자용 오류 문구 | 다시 시도 |
| `retrying` | refetch 진행 | Header, Error 영역 | Retry Action busy | `다시 불러오고 있습니다.` Candidate | 중복 차단 |

### 18.3 사용자용 오류 문구

현재 `error.message` 직접 출력 대신 다음 Candidate 문구를 사용한다.

```text
관심 분야를 불러오지 못했습니다.
잠시 후 다시 시도해 주세요.
```

Retry Label:

```text
다시 시도
```

### 18.4 Offline

별도 네트워크 감지 인프라가 없으므로 Candidate v0.1에서는 API Error 상태로 처리한다.

오프라인 전용 UI는 네트워크 상태 관리 정책이 도입된 후 정의한다.

---

## 19. Navigation

### 19.1 진입

| 항목 | 내용 |
|---|---|
| Route Name | `InterestSelect` |
| Parameter | `undefined` |
| 현재 이전 화면 | 없음 |
| 현재 Stack 위치 | 유일한 Root Screen |
| Header | 숨김 |
| 인증 Guard | 없음 |
| 진입 시 조회 | `useCategories()` |

### 19.2 이탈

| 사용자 행동 | 목적지 | 전달 데이터 | Stack 처리 |
|---|---|---|---|
| 완료 | TBD | 선택 ID 또는 서버 저장 결과 TBD | TBD |
| Android Back | 현재 Root 기본 동작 | 없음 | 현재 기본 동작 |
| 취소 | 정의되지 않음 | 없음 | Out of Scope |

### 19.3 금지

- `RecommendedTrends` Route를 존재한다고 가정하지 않는다.
- 저장 성공 전 Navigation을 실행한다고 가정하지 않는다.
- 임시 Alert를 Navigation 완료로 문서화하지 않는다.
- 확인되지 않은 회원가입 Route를 추가하지 않는다.

---

## 20. 콘텐츠 문구

| 위치 | 문구 | 상태 | 비고 |
|---|---|---|---|
| Screen Title | `관심 분야를 선택해 주세요` | Existing / Candidate 유지 | 현재 코드 문구 |
| Description | `선택한 관심 분야를 바탕으로 맞춤 트렌드를 추천합니다.` | Existing / Candidate 유지 | 줄바꿈은 화면 너비에 맡김 |
| Loading | `관심 분야를 불러오고 있습니다.` | Existing / Candidate 유지 | Content Region |
| Empty | `표시할 관심 분야가 없습니다.` | Existing / Candidate 유지 | 오류 아님 |
| Error Title | `관심 분야를 불러오지 못했습니다.` | Candidate | 원본 error.message 대체 |
| Error Description | `잠시 후 다시 시도해 주세요.` | Candidate | 기술 용어 금지 |
| Retry | `다시 시도` | Existing 유지 | Action |
| Primary Action | `선택 완료` | Existing 유지 | 정식 저장 전 임시 Action |
| Selected Label | `선택됨` | Candidate | 비색상 상태 표현 |

### 20.1 문구 원칙

- “많이 선택할수록 좋아요”와 같은 근거 없는 유도 문구를 추가하지 않는다.
- 최소 선택 개수를 확정하기 전 “3개 이상” 등의 문구를 추가하지 않는다.
- 선택 완료 버튼이 실제 저장을 수행한다고 오해시키는 성공 메시지를 표시하지 않는다.
- Error에 URL, HTTP Status와 원본 Exception을 표시하지 않는다.

---

## 21. 접근성

### 21.1 화면 제목

- `accessibilityRole="header"` 적용을 검토한다.
- 화면 제목은 시각적으로도 최상위 Text Role을 사용한다.

### 21.2 InterestOption

```text
accessibilityRole:
button

accessibilityLabel:
{category_name}

accessibilityState:
selected: boolean
```

필요 시 Hint:

```text
두 번 탭하여 관심 분야를 선택하거나 해제합니다.
```

Hint는 기본 동작이 충분히 명확하지 않은 경우에만 사용한다.

### 21.3 완료 버튼

```text
accessibilityRole:
button

accessibilityState:
disabled: selectedCategoryIds.length === 0
```

저장 Mutation 도입 후:

```text
busy: isSaving
```

### 21.4 Retry

- `accessibilityRole="button"`
- Label은 `다시 시도`
- Retry 중 disabled 또는 busy 상태 제공

### 21.5 터치 영역

- InterestOption 전체가 터치 영역이다.
- 최소 44×44dp보다 크게 구성한다.
- 완료 버튼은 최소 `buttonHeight`를 사용한다.
- 인접한 Grid 항목 사이에 `space3` 간격을 유지한다.

### 21.6 글자 확대

- InterestOption은 고정 `height` 대신 `minHeight`를 사용한다.
- 카테고리 이름은 최대 2줄을 기본으로 하되 핵심 의미가 잘리지 않는지 검증한다.
- 완료 버튼은 `minHeight`를 사용한다.
- Description은 화면 너비에 따라 최대 3줄까지 확장한다.

### 21.7 색상

- 선택 상태를 색상만으로 구분하지 않는다.
- disabled 상태를 opacity만으로 표현하지 않는다.
- Error 상태에는 문구와 Action을 제공한다.

---

## 22. 작은 화면과 긴 콘텐츠

| 위험 | 발생 조건 | 대응 |
|---|---|---|
| 카테고리 이름 잘림 | 긴 한글 이름 | 최대 2줄, `minHeight`, 자연스러운 줄바꿈 |
| 마지막 항목 가림 | 항목 수 증가 | FlatList 하단 padding |
| 버튼 가림 | 작은 화면과 많은 항목 | 버튼을 목록 밖에 배치 |
| 열 너비 부족 | 360dp | 20dp gutter + 12dp column gap 검증 |
| 텍스트 확대 시 Surface 잘림 | 접근성 글자 확대 | 고정 height 금지, minHeight 사용 |
| 제목 영역 과대 | 제목·설명 줄 증가 | sectionGap 유지, 불필요한 이미지 금지 |
| 한 개의 홀수 항목 폭 문제 | 2열 마지막 단독 항목 | FlatList 열 규칙과 빈 column 처리 검증 |
| 상태 문구 중앙 정렬 과다 | 긴 오류 문구 | Feedback Area에서 읽기 쉬운 정렬 |
| Safe Area 침범 | Android 기기별 inset | ScreenContainer에서 처리 |

### 22.1 360dp 기준 폭 계산 검토

```text
전체 너비:
360dp

좌우 gutter:
20dp × 2

열 간격:
12dp

가용 열 너비:
(360 - 40 - 12) / 2
= 154dp
```

154dp 폭에서 2줄 카테고리명과 selected 표시가 읽기 가능한지 검증한다.

### 22.2 412dp

동일한 2열 구조를 유지한다.

화면이 넓어졌다는 이유만으로 3열로 변경하지 않는다.

---

## 23. 이미지와 아이콘

### 23.1 이미지

Candidate v0.1에서는 사용하지 않는다.

이유:

- 카테고리 이름만으로 선택 의미를 전달할 수 있다.
- 승인된 카테고리 이미지 자산이 없다.
- 이미지 중심 피드 인상을 피한다.
- 네트워크 이미지 실패 상태를 추가할 필요가 없다.

### 23.2 아이콘

Candidate v0.1에서는 외부 아이콘 라이브러리를 추가하지 않는다.

선택 상태는 다음으로 표현한다.

```text
Strong Border
+ Selected Background
+ “선택됨” Text
```

공식 아이콘 패밀리가 확정되면 selected 상태에 Check icon을 추가할 수 있다.

이모지는 기능 아이콘으로 사용하지 않는다.

---

## 24. 구현 영향 범위

### 24.1 수정 대상

| 파일 | 수정 | 목적 | 구조 유지 |
|---|---:|---|---:|
| `frontend/src/features/interest/screens/InterestSelectScreen.tsx` | 예 | Design System과 상태 구조 적용 | 예 |
| `frontend/src/app/navigation/RootNavigator.tsx` | 필요 시 최소 수정 | 기존 Route 옵션 정리 | 예 |

### 24.2 유지 대상

| 파일 | 처리 |
|---|---|
| `frontend/src/features/interest/api/getCategories.ts` | 기능 유지 |
| `frontend/src/features/interest/hooks/useCategories.ts` | 기능 유지 |
| `frontend/src/features/interest/types/category.ts` | API Type 유지 |
| `frontend/src/shared/api/apiClient.ts` | 기능 유지 |
| `frontend/src/app/providers/QueryProvider.tsx` | 기능 유지 |

### 24.3 생성 후보

| 파일 | 생성 | 책임 |
|---|---:|---|
| `frontend/src/features/interest/components/InterestOption.tsx` | 권장 | Feature 전용 선택 Surface |
| `frontend/src/shared/constants/colors.ts` | 필요 | Color Token |
| `frontend/src/shared/constants/spacing.ts` | 필요 | Spacing Token |
| `frontend/src/shared/constants/typography.ts` | 필요 | Typography Token |
| `frontend/src/shared/constants/radius.ts` | 필요 | Radius Token |
| `frontend/src/shared/constants/borders.ts` | 필요 | Border Token |
| `frontend/src/shared/constants/sizes.ts` | 필요 | Size Token |
| `frontend/src/shared/constants/index.ts` | 필요 | Token export |
| `frontend/src/shared/components/ScreenContainer.tsx` | 권장 | Screen Shell |
| `frontend/src/shared/components/PrimaryButton.tsx` | 권장 | Primary Action |
| `frontend/src/shared/components/LoadingView.tsx` | 권장 | Loading |
| `frontend/src/shared/components/ErrorView.tsx` | 권장 | Error + Retry |
| `frontend/src/shared/components/EmptyView.tsx` | 권장 | Empty |

### 24.4 추가 의존성

```text
추가 의존성:
없음
```

근거:

- React Native 기본 컴포넌트로 구현 가능하다.
- `react-native-safe-area-context`가 이미 설치되어 있다.
- React Query와 React Navigation이 이미 설치되어 있다.
- 아이콘과 외부 폰트를 사용하지 않는다.

---

## 25. 미결정 사항

### 25.1 Blocking for Frozen

| 우선순위 | 항목 | 현재 상태 | 필요한 결정 | Candidate에서 가능한 작업 | 영향 |
|---:|---|---|---|---|---|
| 1 | 관심사 저장 Endpoint | 미구현 | Method, URL, Request, Response | 조회·선택 UI 검증 | 최종 완료 처리 |
| 2 | 완료 후 Route | 미구현 | 목적지와 Stack 처리 | 임시 Alert 유지 | Navigation |
| 3 | 선택 개수 정책 | 미확정 | 최소·최대 개수 | 현재 1개 이상 활성화 유지 | 버튼 조건·문구 |
| 4 | 초기 선택값 | 미구현 | 기존 관심사 조회·주입 | 빈 선택으로 시작 | 수정 화면 재사용 |
| 5 | 인증·진입 정책 | 미확정 | 회원가입 직후/설정 화면 구분 | 현재 Root 진입 유지 | 사용자 흐름 |

이 항목은 Candidate v0.1 UI 구현을 막지는 않지만 Frozen 전환을 막는다.

### 25.2 Non-blocking Candidate

| 항목 | Candidate |
|---|---|
| InterestOption 높이 | 112dp로 검증 |
| Label 정렬 | 왼쪽 정렬 검증 |
| 선택 표시 | Border + `선택됨` |
| Shared Component 생성 범위 | 첫 대표 화면에서 검증 |
| Error 문구 | 사용자용 Candidate 문구 사용 |

### 25.3 Future

- 세부분류 선택
- 관심사 검색
- 관심사 추천
- 관심사별 이미지
- Dark Mode
- Tablet Layout
- 애니메이션 고도화

---

## 26. Acceptance Criteria

### 26.1 기능

- 화면 진입 시 `useCategories()`를 통해 실제 Category API를 조회한다.
- Screen에서 `getCategories()` 또는 `apiRequest()`를 직접 호출하지 않는다.
- Backend가 제공한 `data.categories` 순서를 그대로 표시한다.
- 카테고리를 누르면 해당 `category_id`가 선택 배열에 추가된다.
- 선택된 카테고리를 다시 누르면 해당 ID가 배열에서 제거된다.
- 선택 배열에는 같은 ID가 중복되지 않는다.
- 선택값이 없으면 완료 버튼이 disabled 상태다.
- 선택값이 하나 이상이면 완료 버튼이 활성화된다.
- Candidate v0.1의 완료 Action은 서버 저장 성공으로 표현하지 않는다.
- `children`은 Candidate v0.1에서 렌더링하지 않는다.

### 26.2 상태

- 최초 조회 중에도 화면 제목과 설명이 유지된다.
- 최초 조회 중 목록 영역에 로딩 상태가 표시된다.
- 조회 실패 시 `error.message` 원문을 직접 사용자에게 보여주지 않는다.
- 조회 실패 시 `다시 시도` Action을 제공한다.
- 빈 배열 응답은 오류가 아닌 Empty 상태로 표시된다.
- Empty 상태에서는 완료 버튼이 disabled 상태다.
- Retry 중 중복 입력을 방지할 수 있는 구조를 가진다.

### 26.3 디자인 시스템

- Screen 배경은 `backgroundCanvas`를 사용한다.
- 화면 좌우 gutter는 `screenGutter`를 사용한다.
- 제목, 설명, 항목과 버튼은 지정된 Typography Token을 사용한다.
- InterestOption은 `radiusMedium`을 사용한다.
- 선택 상태는 `backgroundSelected`, `borderSelected`와 `borderWidthStrong`을 사용한다.
- 선택 상태를 색상만으로 표현하지 않는다.
- 모든 카테고리 항목에 그림자를 적용하지 않는다.
- 범용 Card 컴포넌트를 만들지 않는다.
- `signalHighlight`를 장식 목적으로 사용하지 않는다.
- 디자인 값을 Screen에 임의로 중복 하드코딩하지 않는다.

### 26.4 접근성

- InterestOption은 `accessibilityRole="button"`을 가진다.
- InterestOption은 실제 선택 상태를 `accessibilityState.selected`로 제공한다.
- 완료 버튼은 disabled 상태를 접근성 State로 제공한다.
- Retry는 button Role과 명확한 Label을 가진다.
- 모든 주요 터치 영역은 최소 44×44dp 이상이다.
- 선택 상태는 색상을 보지 못해도 구분할 수 있다.
- 360dp에서 긴 카테고리명이 잘리지 않고 최대 2줄로 표시된다.
- 텍스트 확대 시 InterestOption과 버튼의 내용이 잘리지 않는다.

### 26.5 구조 유지

- `getCategories.ts`의 API 책임을 Screen으로 이동하지 않는다.
- `useCategories.ts`를 삭제하거나 Screen에 합치지 않는다.
- `category.ts` Type을 Screen 내부에 중복 정의하지 않는다.
- 실제 API를 mock data로 교체하지 않는다.
- `apiClient.ts`의 base URL 정책을 화면 작업에서 변경하지 않는다.
- Feature 전용 `InterestOption`을 검증 없이 Shared로 이동하지 않는다.
- 확인되지 않은 저장 API와 Navigation Route를 생성하지 않는다.

---

## 27. 검증 계획

### 27.1 정적 검토

```text
- Backend Endpoint와 Frontend 상대 경로 구분
- CategoryItem Type 일치
- categories 순서 유지
- Screen→Hook→API Function 구조 유지
- Design Token mapping
- Navigation Route 존재 여부
- 임시 Alert와 최종 완료 처리 구분
- TBD와 Candidate 구분
```

### 27.2 구현 후 명령

```powershell
Set-Location frontend

npx tsc --noEmit
npx expo-doctor
```

프로젝트에 별도 lint script가 추가되었다면 해당 명령도 실행한다.

### 27.3 화면 검증

#### 360dp

- Header가 과도하게 크지 않은지
- 2열 항목 너비가 충분한지
- 긴 카테고리명이 2줄 안에서 읽히는지
- 마지막 항목이 완료 버튼에 가려지지 않는지
- 홀수 개 항목의 마지막 Row가 깨지지 않는지

#### 412dp

- 2열 구조가 지나치게 넓거나 성기지 않은지
- gutter와 항목 간격이 적절한지
- 완료 버튼의 폭과 위치가 안정적인지

### 27.4 상태 검증

```text
1. initial_loading
2. success_unselected
3. success_selected
4. empty
5. error
6. retrying
```

### 27.5 접근성 검증

- Screen Reader에서 카테고리 이름을 읽을 수 있는지
- 선택됨·선택 안 됨 상태가 전달되는지
- 완료 버튼 disabled 상태가 전달되는지
- Retry Action이 명확히 읽히는지
- 텍스트 확대 시 레이아웃이 깨지지 않는지

### 27.6 Design System Candidate 검증

검증 대상 Token:

```text
backgroundCanvas
backgroundSurface
backgroundSelected
textPrimary
textSecondary
textBrand
borderDefault
borderSelected
actionPrimary
actionPrimaryPressed
actionDisabled
screenGutter
screenTopSpacing
screenBottomSpacing
sectionGap
contentGap
space3
radiusMedium
buttonHeight
touchTarget
screenTitle
body
itemTitle
label
button
```

검증 대상 Component Policy:

```text
ScreenContainer
PrimaryButton
LoadingView
ErrorView
EmptyView
Feature Local SelectionSurface
```

검증 후 Snapshot 수정 가능 항목:

```text
- screenGutter 20dp 적절성
- radiusMedium 12dp 적절성
- actionPrimary 대비와 브랜드 인상
- InterestOption minHeight 112dp
- ErrorView와 EmptyView의 정보 밀도
- Shared Component 분리 수준
```

화면 하나의 선호만으로 Snapshot을 즉시 수정하지 않는다.

---

## 28. 변경 이력

| 버전 | 날짜 | 상태 | 변경 내용 | 작성·검토 |
|---|---|---|---|---|
| 0.1 | 2026-08-05 | Candidate | 현재 Category API와 Interest 구조를 유지한 첫 화면 명세 작성 | ChatGPT 작성, 팀 검토 필요 |

### Frozen 전환 조건

다음을 모두 충족해야 한다.

```text
- Candidate 구현 완료
- 360dp와 412dp 검증 완료
- Loading·Error·Empty·선택 상태 확인
- 접근성 상태 확인
- Design System Candidate 검증 결과 기록
- 관심사 저장 API 확정
- 완료 후 Navigation 확정
- 선택 개수 정책 확정
- 팀원 2인 검토
```
