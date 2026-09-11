# InterestSelectScreen Screen Specification

## 문서 정보

```text
문서명: Trend Leader InterestSelectScreen Screen Specification
문서 유형: Screen Specification
대상 화면: InterestSelectScreen
대상 기능: Interest / 최초 관심사 선택 Onboarding
버전: 0.2
상태: Candidate
구현 상태: Current dev 구현 정합성 반영
플랫폼: React Native + Expo, Android 우선
화면 방향: Portrait
기준 브랜치: dev
기준 커밋: 40fbd54825d8e17ffb3fd17a42f98e05af9788b8
기준일: 2026-09-10
관련 Backend Endpoint:
- GET /api/categories
- POST /api/users/me/interests
관련 Frontend API Function:
- getCategories
- saveUserInterests
관련 Hook:
- useCategories
- useSaveInterests
관련 인증 상태:
- AuthProvider
- completeInterestSelection()
- revalidateSession()
관련 Navigation:
- RootNavigator
- OnboardingNavigator
- InterestSelect
- AppNavigator
관련 Design System:
- Design System Snapshot v0.1 Candidate
이전 문서:
- docs/frontend-design/archive/interest-select-v0.1-candidate-screen-spec.md
```

---

## 1. 문서 목적

본 문서는 현재 `dev` 브랜치에 구현된 `InterestSelectScreen`의 실제 화면 책임, API 연결, 인증 상태와 Navigation 흐름을 기준으로 현행 Screen Specification을 정의한다.

기존 v0.1 Candidate 문서는 Category 조회와 로컬 선택, Design System 적용을 검증하기 위해 작성된 구현 전·중간 단계 문서이며, 현재는 Archive에서 역사 자료로 보존한다.

본 v0.2는 새로운 기능을 설계하지 않는다. 현재 구현과 최신 확정 설계에서 확인되는 다음 흐름을 문서화한다.

```text
Category 조회
→ 활성 대분류 관심 분야 표시
→ 로컬 선택 및 선택 해제
→ 최초 관심사 저장
→ 저장 결과 처리
→ AuthProvider 상태 갱신 또는 Session 재검증
→ RootNavigator 재평가
→ MAIN 흐름 진입
```

본 문서의 범위는 **최초 관심사 선택 Onboarding**이다. 기존 관심사 조회·수정 UI는 별도 기능 범위로 취급한다.

---

## 2. 화면 요약

`InterestSelectScreen`은 인증된 사용자가 최초 개인화에 사용할 활성 대분류 관심사를 선택하고 서버에 저장하는 Onboarding 화면이다.

화면은 `GET /api/categories` 응답의 최상위 Category를 선택 대상으로 사용하며, 세부분류 `children`을 직접 선택하지 않는다.

사용자가 하나 이상의 대분류를 선택하고 최초 저장에 성공하면 화면 자체가 Main Route로 직접 이동하지 않는다.

```text
POST 관심사 저장 성공
→ completeInterestSelection()
→ AuthProvider Session 상태 갱신
→ has_selected_interests = true
→ next_step = MAIN
→ RootNavigator 재평가
→ AppNavigator
```

최초 관심사가 이미 저장된 상태에서 `409 Conflict`가 발생하면 화면은 같은 저장 요청을 자동 재시도하지 않고 `revalidateSession()`으로 서버의 현재 Session 상태를 다시 확인한다.

---

## 3. 결정 상태 요약

| 분류 | 내용 |
|---|---|
| Confirmed | Category 조회는 `GET /api/categories`를 사용한다. |
| Confirmed | Category 조회 Frontend 상대 경로는 `/categories`이다. |
| Confirmed | Category 조회는 `publicApiClient`를 사용한다. |
| Confirmed | `useCategories()`가 React Query 조회 상태를 관리한다. |
| Confirmed | 최초 관심사 저장은 `POST /api/users/me/interests`를 사용한다. |
| Confirmed | 최초 관심사 저장 Frontend 상대 경로는 `/users/me/interests`이다. |
| Confirmed | 관심사 저장은 `authenticatedApiClient`를 사용한다. |
| Confirmed | `useSaveInterests()`가 최초 저장 Mutation 상태를 관리한다. |
| Confirmed | 사용자는 활성 최상위 대분류 `category_id`를 선택한다. |
| Confirmed | `children` 세부분류는 이 화면에서 직접 선택하지 않는다. |
| Confirmed | 선택값은 `selectedCategoryIds: number[]` 로컬 상태로 관리한다. |
| Confirmed | 같은 Category를 다시 누르면 선택이 해제된다. |
| Confirmed | 최소 하나 이상의 Category가 필요하다. |
| Confirmed | 로컬 선택 배열은 중복 ID를 생성하지 않는다. |
| Confirmed | 저장 중, 저장 성공 후, 최초 저장 `409` 상태에서는 선택 변경을 잠근다. |
| Confirmed | 저장 성공 시 `completeInterestSelection()`을 호출한다. |
| Confirmed | `409` 발생 시 `revalidateSession()`으로 서버 Session을 다시 확인한다. |
| Confirmed | `401`은 Screen 자체 인증 Alert가 아니라 공통 인증 실패 처리 흐름에 맡긴다. |
| Confirmed | `InterestSelect`는 `OnboardingNavigator`에 속한다. |
| Confirmed | 완료 후 Screen이 직접 Main Route로 Navigation하지 않는다. |
| Candidate | Design System Snapshot v0.1 Candidate의 Token과 공통 Component를 현재 화면에 적용한다. |
| Not Defined | 별도의 고정 최대 관심사 선택 개수는 현재 API 계약에 정의되어 있지 않다. |
| Out of Scope | `GET /api/users/me/interests` 기반 기존 관심사 조회 UI |
| Out of Scope | `PUT /api/users/me/interests` 기반 관심사 수정 UI |
| Out of Scope | 기존 관심사 초기 선택값 주입 |
| Out of Scope | 세부분류 직접 선택 |
| Out of Scope | 관심사 검색 및 필터 |
| Out of Scope | 관심사별 이미지 또는 기능 아이콘 |
| Out of Scope | Dark Mode |
| Out of Scope | Landscape |

---

## 4. Source of Truth

프로젝트 전체 문서 간 충돌은 `Trend_Leader_AI_Development_Guidelines.md`와 기능별 최신 확정안의 우선순위 규칙을 따른다.

Screen 수준에서는 다음 자료를 함께 확인한다.

```text
1. 최신 기능별 설계 확정안과 Category Taxonomy 확정안
2. 최신 Backend API Schema와 실제 Endpoint
3. 실제 Frontend Type / API Function / Hook 계약
4. 현재 Auth / Navigation 계약
5. Design System Snapshot
6. 본 Screen Specification
7. 현재 dev 구현
8. Archive 문서
```

Archive의 v0.1 Candidate는 변경 과정 확인을 위한 역사 자료이며, 현재 구현 판단의 Source of Truth로 사용하지 않는다.

### 4.1 관련 Backend 계약

```text
GET /api/categories
→ 활성 Category 계층 조회

POST /api/users/me/interests
→ 인증 사용자의 최초 관심사 저장
```

### 4.2 관련 Frontend 흐름

```text
Category 조회
InterestSelectScreen
→ useCategories
→ getCategories
→ publicApiClient
→ GET /categories

최초 관심사 저장
InterestSelectScreen
→ useSaveInterests
→ saveUserInterests
→ authenticatedApiClient
→ POST /users/me/interests
```

### 4.3 Design System 상태

현재 `Design System Snapshot v0.1`은 Candidate이다.

`InterestSelectScreen`에 Candidate Token과 공통 Component가 실제 적용되어 있지만, 이 사실만으로 Design System 전체를 Frozen으로 간주하지 않는다.

---

## 5. 화면 진입 조건과 Navigation

### 5.1 Route

| 항목 | 값 |
|---|---|
| Route Name | `InterestSelect` |
| Navigation Parameter | `undefined` |
| Stack | `OnboardingNavigator` |
| Stack Header | 숨김 |
| 인증 필요 | 예 |
| 진입 상태 | `AUTHENTICATED + next_step=INTEREST_SELECTION` |

### 5.2 Root Navigation 구조

```text
RootNavigator
├─ RESTORING
│  └─ SessionRestoreScreen
├─ RESTORE_ERROR
│  └─ SessionRestoreErrorScreen
├─ UNAUTHENTICATED
│  └─ AuthNavigator
└─ AUTHENTICATED
   ├─ next_step = INTEREST_SELECTION
   │  └─ OnboardingNavigator
   │     └─ InterestSelectScreen
   └─ next_step = MAIN
      └─ AppNavigator
```

### 5.3 완료 후 이동

`InterestSelectScreen`은 다음과 같은 직접 Navigation을 수행하지 않는다.

```text
navigation.navigate("Main")
navigation.replace("Main")
```

정상 완료 흐름은 다음과 같다.

```text
POST /users/me/interests 성공
→ completeInterestSelection()
→ AuthProvider의 현재 Session 갱신
→ has_selected_interests = true
→ next_step = MAIN
→ RootNavigator가 인증 상태를 다시 평가
→ AppNavigator mount
```

### 5.4 Android Back

`InterestSelectScreen`은 Onboarding Stack의 현재 Screen이다.

완료 후 `AuthNavigator` 또는 `InterestSelectScreen`을 History에 남겨 직접 복귀시키는 imperative Navigation을 추가하지 않는다.

---

## 6. 사용 API와 데이터 계약

### 6.1 Category 조회

| 구분 | 값 |
|---|---|
| Server Endpoint | `GET /api/categories` |
| Frontend 상대 경로 | `/categories` |
| API Function | `getCategories()` |
| Hook | `useCategories()` |
| Client | `publicApiClient` |
| Request Body | 없음 |
| Query Parameter | 없음 |
| Query Key | `["categories"]` |
| staleTime | 30분 |
| retry | 1회 |
| Response Data Type | `CategoryListData` |

`getCategories()`는 공통 Response Wrapper 전체가 아니라 `response.data.data`의 `CategoryListData`를 반환한다.

### 6.2 최초 관심사 저장

| 구분 | 값 |
|---|---|
| Server Endpoint | `POST /api/users/me/interests` |
| Frontend 상대 경로 | `/users/me/interests` |
| API Function | `saveUserInterests()` |
| Hook | `useSaveInterests()` |
| Client | `authenticatedApiClient` |
| Mutation retry | 0 |
| Request Type | `InterestSaveRequest` |
| Success Type | `InterestSaveResponse` |

Request:

```json
{
  "category_ids": [1, 2]
}
```

Success Data:

```json
{
  "selected_category_ids": [1, 2],
  "selected_count": 2
}
```

### 6.3 선택 개수 계약

Backend 공통 관심사 선택 Request는 다음을 요구한다.

```text
category_ids
→ 최소 1개
→ Strict Integer 배열
→ 배열 내부 중복 금지
```

별도의 고정 최대 선택 개수는 현재 Request Schema에 정의되어 있지 않으므로 Screen에서 임의 최대값을 추가하지 않는다.

---

## 7. Category 표시 정책

화면은 `GET /categories` 결과의 최상위 `categories` 배열을 직접 선택 대상으로 사용한다.

### 7.1 화면 사용 필드

| 필드 | 사용 | 역할 |
|---|---:|---|
| `category_id` | 예 | FlatList key, 로컬 선택값, 저장 Request |
| `category_name` | 예 | 사용자 표시 Label |
| `category_code` | 아니요 | 화면 Label로 직접 표시하지 않음 |
| `parent_id` | 아니요 | 최상위 목록 판별을 Screen에서 다시 수행하지 않음 |
| `sort_order` | 직접 사용 안 함 | Frontend에서 재정렬하지 않음 |
| `children` | 직접 표시 안 함 | 최초 관심사 선택은 대분류만 대상 |

### 7.2 정렬

```text
Backend
→ 활성 Category를 계층과 노출 순서에 맞춰 반환

Frontend
→ data.categories 순서를 그대로 사용
→ 추가 정렬하지 않음
```

### 7.3 세부분류

`children` 데이터가 응답에 존재하더라도 `InterestSelectScreen`은 이를 선택 Surface로 렌더링하지 않는다.

최초 사용자 관심사에는 활성 최상위 대분류 Category만 저장한다.

---

## 8. 화면 상태 모델

화면에는 Query, Local Draft, Mutation, Auth 네 종류의 상태가 결합된다.

### 8.1 Server Query State

`useCategories()`가 관리한다.

```text
isPending
isError
isFetching
data
refetch()
```

### 8.2 Local Draft State

```text
selectedCategoryIds: number[]
```

아직 서버에 저장되지 않은 현재 사용자의 선택 Draft를 의미한다.

Screen은 `CategoryItem` 전체 객체를 선택 상태로 저장하지 않는다.

### 8.3 Mutation State

`useSaveInterests()`가 관리한다.

```text
isPending
isSuccess
error
mutate()
```

### 8.4 Auth State

Screen은 `useAuth()`를 통해 다음 기능만 사용한다.

```text
completeInterestSelection()
revalidateSession()
```

Screen은 Access Token을 직접 읽거나 저장하지 않고 Session Storage를 직접 수정하지 않는다.

---

## 9. 선택 Interaction

### 9.1 기본 선택

```text
현재 category_id가 selectedCategoryIds에 없음
→ 배열에 추가

현재 category_id가 selectedCategoryIds에 있음
→ 배열에서 제거
```

동일한 ID는 배열에 중복 저장하지 않는다.

### 9.2 최소 선택 조건

```text
selectedCategoryIds.length === 0
→ PrimaryButton disabled

selectedCategoryIds.length > 0
→ 저장 가능
```

### 9.3 Selection Lock

다음 상태에서는 Category 선택 변경을 차단한다.

```text
saveInterestsMutation.isPending
saveInterestsMutation.isSuccess
저장 Error의 statusCode === 409
```

이 상태에서는 `InterestCategoryOption`에도 `disabled`를 전달한다.

### 9.4 최대 선택 개수

현재 별도 제품 최대값이 API 계약에 존재하지 않으므로 Screen은 고정 최대 선택 개수를 적용하지 않는다.

---

## 10. 정상 저장 흐름

```text
1. 사용자가 InterestSelectScreen에 진입한다.
2. useCategories()가 Category 목록을 조회한다.
3. Backend가 제공한 순서대로 활성 대분류를 표시한다.
4. 사용자가 하나 이상의 대분류를 선택한다.
5. PrimaryButton이 활성화된다.
6. 사용자가 "선택 완료"를 누른다.
7. useSaveInterests().mutate()를 실행한다.
8. POST /users/me/interests를 호출한다.
9. HTTP 201 성공 응답을 받는다.
10. completeInterestSelection()을 호출한다.
11. AuthProvider Session의 has_selected_interests를 true로 변경한다.
12. next_step을 MAIN으로 변경한다.
13. RootNavigator가 상태를 다시 평가한다.
14. AppNavigator로 전환한다.
```

저장 성공 후 별도의 `GET /api/auth/session`을 화면에서 추가 호출하지 않는다.

---

## 11. 저장 오류 처리

### 11.1 Network Error

서버 Response가 존재하지 않는 경우:

```text
현재 선택값 유지
→ Alert
→ 네트워크 상태 확인 후 재시도 안내
```

### 11.2 HTTP 400

현재 구현은 Category 규칙 오류 응답을 다음과 같이 처리한다.

```text
selectedCategoryIds 초기화
→ Category refetch
→ "관심 분야를 다시 선택해 주세요" Alert
→ Backend message 표시
```

### 11.3 HTTP 401

Screen 자체에서 인증 만료 Alert를 표시하지 않는다.

```text
authenticatedApiClient
→ 공통 401 처리
→ 인증 Session 종료/복원 정책 적용
```

Screen의 `handleComplete()`에는 401 전용 Alert 분기를 추가하지 않는다.

### 11.4 HTTP 404

```text
selectedCategoryIds 초기화
→ Category refetch
→ "관심 분야 정보를 갱신합니다" Alert
→ Backend message 표시
```

### 11.5 HTTP 409

최초 관심사가 이미 존재하는 상태 충돌로 처리한다.

```text
저장 요청 자동 재시도 금지
→ Selection Lock
→ revalidateSession()
→ 서버의 최신 Session 상태 확인
→ RootNavigator가 최신 next_step 반영
```

`revalidateSession()` 자체가 실패하면 다음 Alert를 표시한다.

```text
제목: 로그인 상태 확인 실패
본문: 서버의 현재 상태를 확인하지 못했습니다.
Action:
- 취소
- 다시 시도
```

`다시 시도`는 관심사 POST 재전송이 아니라 Session 재검증을 다시 수행한다.

### 11.6 HTTP 422

```text
현재 선택값 유지
→ "선택 정보를 확인해 주세요" Alert
→ Backend message 표시
```

### 11.7 HTTP 500

```text
현재 선택값 유지
→ "관심사를 저장할 수 없습니다" Alert
→ Backend message 표시
```

---

## 12. Category 조회 상태

### 12.1 Initial Loading

Header는 유지한다.

Content Region에는 `LoadingView`를 표시한다.

```text
관심 분야를 불러오고 있습니다.
```

### 12.2 Initial Error

`isCategoryError === true`이고 아직 `data`가 없는 경우:

```text
Header 유지
→ ErrorView
→ Title: 관심 분야를 불러오지 못했습니다.
→ Message: 잠시 후 다시 시도해 주세요.
→ Retry: refetch()
```

재시도 중에는 `isCategoryFetching`을 `retrying` 상태로 전달한다.

### 12.3 Empty

조회는 성공했지만 `categories.length === 0`인 경우:

```text
EmptyView
→ 표시할 관심 분야가 없습니다.
```

선택값이 없으므로 PrimaryButton은 비활성 상태를 유지한다.

---

## 13. 화면 구조

```text
ScreenContainer
├─ Header
│  ├─ Screen Title
│  └─ Description
├─ Content Region
│  └─ LoadingView
│     | ErrorView
│     | FlatList
│       ├─ InterestCategoryOption[]
│       └─ EmptyView (ListEmptyComponent)
└─ PrimaryButton
```

Header와 Bottom Action의 기본 위치는 Query 상태에 따라 제거되지 않는다.

### 13.1 정보 계층

| 우선순위 | 정보 | 역할 |
|---:|---|---|
| 1 | `관심 분야를 선택해 주세요` | 화면 목적과 행동 안내 |
| 2 | `선택한 관심 분야를 바탕으로 맞춤 트렌드를 추천합니다.` | 선택 결과의 의미 설명 |
| 3 | 각 `category_name` | 실제 선택 대상 |
| 4 | `선택됨` | 현재 선택 상태의 비색상 표시 |
| 5 | Loading / Error / Empty 문구 | 시스템 상태 |
| 6 | Primary Action | 최초 관심사 저장 실행 |

---

## 14. Component 책임

### 14.1 InterestSelectScreen

담당:

```text
화면 전체 Layout 조립
Category 조회 상태 분기
selectedCategoryIds 관리
Category 선택/해제
최초 저장 Mutation 실행
저장 Error 분기
completeInterestSelection() 연결
revalidateSession() 연결
```

담당하지 않음:

```text
HTTP Client 구현
API base URL 구성
Access Token 직접 주입
SecureStore 직접 접근
Backend Validation 규칙 재구현
Session Storage 직접 수정
Main Route 직접 Navigation
기존 관심사 GET/PUT 수정 기능
```

### 14.2 InterestCategoryOption

Feature Local Component로 다음을 담당한다.

```text
category_name 표시
selected 상태 시각화
disabled 상태
Press 이벤트 전달
accessibilityRole
accessibilityLabel
accessibilityState.selected
accessibilityState.disabled
accessibilityHint
```

주요 Props:

```text
category: CategoryItem
selected: boolean
disabled?: boolean
onPress: (categoryId: number) => void
style?: StyleProp<ViewStyle>
```

### 14.3 Shared Component

현재 화면은 다음 공통 Component를 재사용한다.

```text
ScreenContainer
PrimaryButton
LoadingView
ErrorView
EmptyView
```

Screen은 이 Component 내부의 공통 스타일 책임을 다시 구현하지 않는다.

---

## 15. Layout / Design System 적용

현재 화면은 `Design System Snapshot v0.1 Candidate`를 구현에 적용한 상태다.

### 15.1 화면 Layout

| 항목 | 정책 |
|---|---|
| 플랫폼 | Android 우선 |
| 방향 | Portrait |
| Category Layout | 2열 `FlatList` |
| Header | 상단 고정 구조 |
| Content | 남은 영역 사용 |
| Bottom Action | `FlatList` 밖의 `PrimaryButton` |
| Scroll Indicator | 숨김 |

### 15.2 Header

```text
Title
→ contentGap
→ Description
→ sectionGap
→ Content Region
```

현재 코드의 최대 줄 수:

```text
Title
→ textLineLimits.screenTitle

Description
→ 최대 3줄
```

### 15.3 Category Grid

`InterestCategoryOption`의 현재 구현 기준:

```text
2열
minHeight = 112
padding = spacing.space4
Row/Column gap = spacing.space3
Default Border
Selected Strong Border
Default Surface
Selected Surface
Selected Label = "선택됨"
```

`112`는 현재 Interest 선택 Surface에서 사용하는 화면 전용 값이며, 본 명세만으로 전역 Design Token 승격을 결정하지 않는다.

### 15.4 사용 중인 Shared Design 값

현재 Screen과 Feature Component에서 다음 공통 영역을 사용한다.

```text
colors
spacing
typography
radius
borders
textLineLimits
```

화면 하나를 이유로 Candidate Design System 전체를 Frozen으로 변경하지 않는다.

### 15.5 Elevation / 장식

Interest Category Surface에 기본적인 장식용 그림자나 의미 없는 데이터 시각화를 추가하지 않는다.

선택 상태는 다음 조합으로 구분한다.

```text
Background
+ Strong Border
+ "선택됨" Text
```

---

## 16. PrimaryButton 상태

| 상태 | 조건 | Label | disabled | loading |
|---|---|---|---:|---:|
| 선택 전 | 선택 ID 0개 | `선택 완료` | true | false |
| 저장 가능 | 선택 ID 1개 이상 | `선택 완료` | false | false |
| 저장 중 | Mutation pending | `선택 완료` | true | true |
| 저장 성공 | Mutation success | `저장 완료` | true | false |
| 이미 저장됨 | Mutation error statusCode 409 | `이미 저장됨` | true | false |

저장 중, 성공 후, 409 상태에서는 Category 선택 변경도 함께 잠근다.

---

## 17. 사용자 인터랙션 표

| Trigger | 대상 | 사전 조건 | 처리 | 결과 |
|---|---|---|---|---|
| Press | 미선택 Category | Selection Lock 아님 | ID 추가 | selected 상태 |
| Press | 선택 Category | Selection Lock 아님 | ID 제거 | default 상태 |
| Press | PrimaryButton | 선택 1개 이상, 저장 가능 | `mutate()` | 저장 시작 |
| Press | PrimaryButton | disabled 상태 | 실행하지 않음 | 상태 유지 |
| Press | ErrorView Retry | Category 초기 조회 실패 | `refetch()` | 재조회 |
| Press | 409 재검증 Alert `다시 시도` | Session 재검증 실패 | `revalidateSession()` 재실행 | 최신 Session 재확인 |

---

## 18. 접근성

### 18.1 Screen Title

```text
accessibilityRole = header
```

### 18.2 InterestCategoryOption

```text
accessibilityRole = button
accessibilityLabel = category.category_name
accessibilityState.selected = selected
accessibilityState.disabled = disabled
```

Hint는 상태에 따라 구분한다.

```text
미선택
→ 두 번 탭하여 관심 분야로 선택합니다.

선택됨
→ 두 번 탭하여 관심 분야 선택을 해제합니다.

잠김
→ 현재는 관심 분야 선택을 변경할 수 없습니다.
```

### 18.3 선택 상태의 비색상 표현

선택 여부를 색상 하나에만 의존하지 않는다.

```text
Selected Background
+ Strong Border
+ "선택됨" Text
+ accessibilityState.selected
```

### 18.4 버튼

`PrimaryButton`은 disabled와 loading 상태를 공통 Component 책임으로 표현한다.

### 18.5 긴 텍스트

Category Name은 `textLineLimits.itemTitle`을 사용한다.

Surface는 고정 height가 아니라 `minHeight`를 사용하여 글자 확대와 긴 Label에 대응한다.

---

## 19. 현재 Frontend 파일 구조

```text
frontend/src/
├─ app/
│  ├─ navigation/
│  │  ├─ RootNavigator.tsx
│  │  ├─ OnboardingNavigator.tsx
│  │  └─ AppNavigator.tsx
│  └─ providers/
│     ├─ AuthProvider.tsx
│     └─ QueryProvider.tsx
│
├─ features/
│  └─ interest/
│     ├─ api/
│     │  ├─ getCategories.ts
│     │  └─ saveUserInterests.ts
│     ├─ components/
│     │  └─ InterestCategoryOption.tsx
│     ├─ hooks/
│     │  ├─ useCategories.ts
│     │  └─ useSaveInterests.ts
│     ├─ screens/
│     │  └─ InterestSelectScreen.tsx
│     └─ types/
│        ├─ category.ts
│        └─ interest.ts
│
└─ shared/
   ├─ api/
   ├─ components/
   ├─ constants/
   ├─ handler/
   ├─ storage/
   └─ types/
```

이 파일 트리는 Screen에 직접 관련된 책임을 중심으로 표현하며, 전체 Frontend Repository 파일을 모두 열거하지 않는다.

---

## 20. 현재 자동 테스트에서 확인되는 핵심 흐름

현재 Frontend 테스트에서는 Auth Session 연동 관점에서 최소 다음 동작이 검증되어 있다.

```text
관심사 저장 201 성공
→ completeInterestSelection() 호출
→ revalidateSession() 호출하지 않음

관심사 저장 409
→ revalidateSession() 호출
→ completeInterestSelection() 호출하지 않음

관심사 저장 401
→ Screen 자체 Alert 표시하지 않음
→ completeInterestSelection() 호출하지 않음
→ revalidateSession() 호출하지 않음
```

본 문서는 현재 존재하지 않는 테스트를 통과한 것으로 간주하지 않는다.

---

## 21. Acceptance Criteria

### 21.1 Category 조회

- 화면 진입 시 `useCategories()`를 통해 Category 목록을 조회한다.
- Screen에서 `getCategories()`를 직접 호출하지 않는다.
- `getCategories()`는 `publicApiClient`를 사용한다.
- Query Key는 `["categories"]`를 사용한다.
- staleTime은 30분이다.
- Query retry는 1회다.
- Backend가 제공한 최상위 `categories` 순서를 그대로 표시한다.
- `children`은 선택 대상으로 렌더링하지 않는다.

### 21.2 선택

- 대분류 Category를 선택하거나 해제할 수 있다.
- 선택 배열에는 같은 `category_id`가 중복되지 않는다.
- 선택값이 없으면 Primary Action이 비활성화된다.
- Screen은 별도의 고정 최대 선택 개수를 임의로 적용하지 않는다.
- 저장 중, 저장 성공 후, 409 상태에서는 선택 변경을 차단한다.

### 21.3 최초 저장

- 최초 저장은 `useSaveInterests()`를 통해 실행한다.
- API Function은 `authenticatedApiClient`를 사용한다.
- Request는 `category_ids` 배열을 전송한다.
- Mutation retry는 0이다.
- 저장 중 중복 Submit을 차단한다.
- 저장 성공 시 `completeInterestSelection()`을 호출한다.
- 저장 성공 후 Screen이 직접 Main Route로 navigate하지 않는다.

### 21.4 오류

- 네트워크 Error에서는 현재 선택값을 유지하고 재시도 안내를 표시한다.
- 400/404에서는 현재 선택값을 초기화하고 Category를 다시 조회한다.
- 401에서는 Screen 자체 인증 Alert를 생성하지 않는다.
- 409에서는 관심사 POST를 자동 재시도하지 않고 Session을 재검증한다.
- 422/500에서는 현재 선택값을 유지하고 저장 실패 정보를 안내한다.
- Session 재검증 실패 시 Session 재검증만 다시 시도할 수 있다.

### 21.5 화면 상태

- Loading/Error 상태에서도 Header를 유지한다.
- 초기 조회 실패 시 `ErrorView`와 Retry를 표시한다.
- 빈 Category 배열은 오류가 아닌 Empty 상태로 표시한다.
- Empty 상태에서는 Primary Action이 비활성화된다.

### 21.6 접근성 / Design System

- Category Surface는 `accessibilityRole="button"`을 가진다.
- 실제 selected/disabled 상태를 `accessibilityState`로 제공한다.
- 선택 여부를 색상만으로 구분하지 않는다.
- Category Surface는 현재 Shared Design Token을 재사용한다.
- Screen은 `ScreenContainer`, `PrimaryButton`, `LoadingView`, `ErrorView`, `EmptyView`를 재사용한다.
- Design System Snapshot은 본 화면 구현만으로 Frozen으로 간주하지 않는다.

---

## 22. Out of Scope

본 Screen Specification은 **최초 관심사 선택 Onboarding**만 대상으로 한다.

다음은 포함하지 않는다.

```text
GET /api/users/me/interests를 이용한 기존 관심사 조회 UI
PUT /api/users/me/interests를 이용한 관심사 수정 UI
기존 선택값 초기 주입
마이페이지 Interest Edit 화면
세부분류 직접 선택
개인화 추천 목록 구현
Trend-Category Mapping 구현
Category Seed 구현
Category 관리 UI
관심사 검색 및 필터
Dark Mode
Landscape
Tablet 전용 Layout
```

Backend에 GET/PUT Endpoint가 존재하더라도 해당 기능을 `InterestSelectScreen`에 임의로 통합하지 않는다.

---

## 23. 향후 변경 시 주의사항

다음 변화가 실제로 확정되면 본 Screen Specification을 함께 재검토한다.

```text
고정 최대 관심사 선택 개수 도입
최초 관심사 저장 API 계약 변경
Category API 응답 구조 변경
Onboarding Navigation 구조 변경
AuthProvider Session 계약 변경
Design System Snapshot Frozen 전환 또는 Token 변경
최초 선택과 수정 화면의 Component 재사용 구조 확정
```

본 화면 하나에서 필요한 요구를 이유로 Backend 계약이나 공통 Auth 구조를 임의 변경하지 않는다.

---

## 24. 변경 이력

| 버전 | 날짜 | 상태 | 내용 |
|---|---|---|---|
| 0.1 | 2026-08-05 | Candidate / Archived | Category 조회, 로컬 선택, 개발용 완료 Alert를 중심으로 Design System Candidate 대표 화면 검증 명세 작성 |
| 0.2 | 2026-09-10 | Candidate | 현재 dev 기준 최초 관심사 저장, AuthProvider 연동, 409 Session 재검증, Root Navigation, Shared Component/Token 적용 상태를 반영하여 문서 정합성 갱신 |

### v0.1 Archive

기존 v0.1 원문은 다음 위치에 수정 없이 보존한다.

```text
docs/frontend-design/archive/interest-select-v0.1-candidate-screen-spec.md
```

Archive 문서는 과거 설계와 구현 진행 과정을 확인하기 위한 참고 자료이며 현재 Source of Truth로 사용하지 않는다.

### Candidate 유지 이유

현재 Screen 구현에는 Design System Candidate가 실제 적용되어 있으나 `Design System Snapshot v0.1` 자체가 아직 Frozen 상태가 아니다.

따라서 본 Screen Specification도 이번 문서 정합성 보강만으로 Frozen으로 승격하지 않는다.
