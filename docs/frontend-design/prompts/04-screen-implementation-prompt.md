# Trend Leader 화면 구현 프롬프트

## 문서 정보

```text
문서 유형: Prompt Template
실행 시점: 개별 화면 명세가 확정된 후
출력: React Native + TypeScript 구현 코드
주의: Screen Specification이 확정되지 않은 상태에서는 실행하지 않음
```

아래의 확정된 Trend Leader 디자인 시스템, 화면 명세와 현재 프로젝트 구조를 기준으로 `[TARGET_SCREEN_NAME]` 화면을 React Native + TypeScript로 구현해주세요.

---

## 1. 작업 정보

```text
대상 화면:
[TARGET_SCREEN_NAME]

대상 기능:
[TARGET_FEATURE_NAME]

구현 모드:
[EXISTING_API | MOCK_API | UI_ONLY | REFACTOR]

작업 범위:
[NEW_IMPLEMENTATION | PARTIAL_UPDATE | FULL_REFACTOR]
```

### 구현 모드 정의

#### EXISTING_API

이미 구현된 API Function, Hook과 Type을 유지하며 실제 API를 사용하는 화면을 구현합니다.

#### MOCK_API

확정된 API 계약과 동일한 구조의 mock data source를 사용합니다.

Screen이 mock data를 직접 import하지 않도록 하며 Hook 또는 별도 data source를 통해 접근합니다.

#### UI_ONLY

API 호출과 서버 상태 관리를 구현하지 않고, 화면 및 프레젠테이션 컴포넌트만 구현합니다.

데이터는 Screen props 또는 명시적으로 제공된 fixture를 사용합니다.

#### REFACTOR

현재 기능과 API 동작을 유지하면서 디자인 시스템 적용, 책임 분리와 컴포넌트 구조를 개선합니다.

기존 동작을 임의로 제거하거나 변경하지 않습니다.

---

## 2. Source of Truth

다음 자료만 구현 기준으로 사용합니다.

### Design System Snapshot

```text
[DESIGN_SYSTEM_SNAPSHOT]
```

### Screen Specification

```text
[SCREEN_SPECIFICATION]
```

### API Contract

```text
[API_CONTRACT]
```

API가 없는 `UI_ONLY` 모드라면 다음과 같이 표시합니다.

```text
해당 없음
```

### Current Project Structure

```text
[CURRENT_PROJECT_STRUCTURE]
```

### Existing Related Code

다음 중 실제 작업과 관련된 코드를 제공합니다.

```text
[EXISTING_SCREEN]
[EXISTING_COMPONENTS]
[EXISTING_HOOKS]
[EXISTING_API_FUNCTIONS]
[EXISTING_TYPES]
[NAVIGATION_TYPES]
[SHARED_COMPONENTS]
[SHARED_DESIGN_TOKENS]
[PACKAGE_JSON]
[TSCONFIG_JSON]
```

제공된 자료와 충돌하는 필드, 파일, 경로, 의존성과 제품 정책을 임의로 만들지 마세요.

필수 자료가 없어 올바른 구현이 불가능하면 코드를 추정하여 생성하지 말고, 누락된 자료와 그로 인해 결정할 수 없는 항목만 먼저 정리해주세요.

---

## 3. 화면 책임

### 구현할 책임

```text
[SCREEN_RESPONSIBILITIES]
```

### 구현하지 않을 책임

```text
[OUT_OF_SCOPE_RESPONSIBILITIES]
```

### 사용자 인터랙션

```text
[USER_INTERACTIONS]
```

### Navigation

```text
[NAVIGATION_INPUTS_AND_OUTPUTS]
```

Screen Specification에 없는 기능이나 화면 이동을 임의로 추가하지 마세요.

---

## 4. 기술 조건

* Expo 기반 React Native를 사용합니다.
* TypeScript strict 기준을 준수합니다.
* `StyleSheet.create()`를 사용합니다.
* 인라인 스타일을 사용하지 않습니다.
* API 응답 필드는 snake_case를 유지합니다.
* React Native 기본 컴포넌트를 우선 사용합니다.
* 제공된 `package.json`에 없는 외부 라이브러리를 사용하지 않습니다.
* 새로운 라이브러리가 필요하면 코드에 추가하지 않고 마지막에 별도 제안으로만 기록합니다.
* 제공된 `tsconfig.json`에 정의되지 않은 path alias를 사용하지 않습니다.
* 색상, 간격, 폰트 크기, line height, radius와 border 값을 임의로 하드코딩하지 않습니다.
* 기존 공통 디자인 토큰이 있다면 중복 생성하지 않고 재사용합니다.
* Safe Area를 고려합니다.
* Android 화면 너비 360~412dp를 우선 대응합니다.
* 긴 한글 텍스트와 null 데이터가 레이아웃을 깨뜨리지 않도록 처리합니다.

---

## 5. 책임 분리

다음 데이터 흐름을 유지합니다.

```text
User
→ Screen
→ Hook
→ API Function 또는 Data Source
→ Backend
```

### Screen

Screen은 다음만 담당합니다.

* 화면 구성
* 화면 상태에 따른 UI 분기
* 사용자 이벤트 연결
* Navigation
* 화면 단위 상태 조합

Screen에서 API Function을 직접 호출하지 않습니다.

Screen에서 mock data를 직접 import하지 않습니다.

### Hook

Hook은 다음을 담당합니다.

* 서버 상태 조회
* Mutation 상태
* 로딩 상태
* 오류 상태
* 새로고침
* 캐시 무효화
* 화면에 필요한 데이터 조합

### API Function

API Function은 다음만 담당합니다.

* 요청 URL
* HTTP Method
* Request Body 또는 Query Parameter
* API Client 호출
* Response 반환

API Function 안에 화면 표시 로직을 작성하지 않습니다.

### Component

Component는 다음을 담당합니다.

* 재사용 가능한 UI
* props 기반 렌더링
* 사용자 이벤트를 callback으로 전달

Component 내부에서 API를 호출하지 않습니다.

화면 전용 Component가 전역 Navigation을 직접 사용하지 않도록 합니다.

### Type

Type은 다음을 구분합니다.

* API Request Type
* API Response Type
* Screen 또는 Component Props Type
* Navigation Type

동일한 구조를 이름만 바꾸어 중복 정의하지 않습니다.

---

## 6. 기존 코드 처리 원칙

구현 모드가 `EXISTING_API` 또는 `REFACTOR`인 경우 다음 원칙을 지킵니다.

* 기존 API Function을 임의로 mock data로 교체하지 않습니다.
* 기존 Hook을 불필요하게 삭제하지 않습니다.
* 현재 정상 동작하는 API 계약을 변경하지 않습니다.
* 기존 선택값, 오류 처리와 Navigation 동작을 유지합니다.
* 변경이 필요한 경우 변경 이유를 먼저 설명합니다.
* 같은 역할의 공통 토큰과 컴포넌트를 중복 생성하지 않습니다.
* 화면 전체를 다시 작성하기 전에 유지 가능한 코드를 구분합니다.

---

## 7. 디자인 시스템 적용 조건

* `Design System Snapshot`을 화면 디자인의 유일한 공통 기준으로 사용합니다.
* Snapshot에 없는 색상과 간격을 임의로 추가하지 않습니다.
* 화면 전용 값이 필요하면 전역 토큰에 즉시 추가하지 않고 화면 명세에 근거가 있는지 확인합니다.
* 모든 콘텐츠를 같은 모양의 rounded card로 만들지 않습니다.
* 구분선, 여백과 타이포그래피 대비를 우선 사용합니다.
* 그림자와 그라데이션은 Snapshot에서 허용한 범위에서만 사용합니다.
* 선택, 상승, 하락, 오류와 같은 상태는 색상에만 의존하지 않습니다.
* 모든 텍스트를 굵게 처리하지 않습니다.
* 이모지를 기능 아이콘으로 사용하지 않습니다.
* 의미 없는 차트, 장식과 무한 애니메이션을 추가하지 않습니다.

### 화면별 디자인 제약

```text
[SCREEN_SPECIFIC_DESIGN_CONSTRAINTS]
```

---

## 8. 접근성 조건

* 주요 터치 영역은 최소 44×44dp를 확보합니다.
* 버튼과 아이콘에는 적절한 `accessibilityRole`을 제공합니다.
* 아이콘 버튼에는 `accessibilityLabel`을 제공합니다.
* 선택 컴포넌트에는 `accessibilityState.selected`를 제공합니다.
* 비활성 컴포넌트에는 `accessibilityState.disabled`를 제공합니다.
* 처리 중인 버튼은 중복 입력을 방지합니다.
* 상태를 색상만으로 구분하지 않습니다.
* 중요한 텍스트가 작은 화면에서 잘리지 않도록 합니다.
* 긴 제목은 Screen Specification의 최대 줄 수와 말줄임 규칙을 따릅니다.

---

## 9. 화면 상태

Screen Specification에서 정의한 상태를 모두 구현합니다.

```text
[SCREEN_STATES]
```

검토 대상 예시는 다음과 같습니다.

* 최초 로딩
* 부분 로딩
* Pull-to-refresh
* 빈 데이터
* API 오류
* 오프라인
* Mutation 처리 중
* Mutation 실패
* 일부 데이터만 없는 상태

화면에 필요하지 않은 상태를 임의로 추가하지 않습니다.

공통 상태 컴포넌트가 이미 있다면 기존 컴포넌트를 재사용합니다.

---

## 10. 생성 또는 수정 파일

다음 파일만 생성하거나 수정합니다.

```text
[TARGET_FILES]
```

기존 프로젝트에 같은 역할의 파일이 있다면 새 파일을 중복 생성하지 마세요.

새 파일이 추가로 필요하다고 판단되면 즉시 생성하지 말고 다음 내용을 먼저 설명해주세요.

```text
- 필요한 파일
- 파일의 책임
- 기존 파일로 대체할 수 없는 이유
- 예상 import 관계
```

---

## 11. 코드 작성 규칙

* 각 파일 경로를 먼저 표시한 후 전체 코드를 제공합니다.
* 생략 기호를 사용하지 않습니다.
* 의사 코드를 사용하지 않습니다.
* 바로 프로젝트에 붙여넣을 수 있는 완성 코드로 작성합니다.
* 모든 import 대상이 실제 생성 파일 또는 기존 파일에 존재해야 합니다.
* 누락된 import를 만들지 않습니다.
* 사용하지 않는 import와 변수를 남기지 않습니다.
* 암시적 `any`를 사용하지 않습니다.
* 모든 Component props 타입을 명시합니다.
* 타입 전용 import는 `import type`을 사용합니다.
* 이벤트 함수는 `handle{Target}{Action}` 형식을 우선 사용합니다.
* 목록에는 안정적인 `keyExtractor`를 사용합니다.
* 긴 목록은 `ScrollView`의 `map`보다 `FlatList`를 우선 검토합니다.
* `FlatList`의 item 타입을 명확하게 지정합니다.
* API Response Type과 화면 표시용 Type을 무분별하게 중복 정의하지 않습니다.
* 의미 없는 주석을 반복하지 않습니다.
* 파일 책임을 벗어나는 코드를 작성하지 않습니다.

---

## 12. 자체 검증

코드 생성 후 다음 항목을 자체 점검해주세요.

### 파일 및 Import

1. 모든 import 대상 파일이 실제 존재하는가
2. export와 import 이름이 일치하는가
3. 파일 경로의 대소문자가 일치하는가
4. 순환 의존성이 생기지 않는가

### TypeScript

5. TypeScript strict 환경에서 암시적 `any`가 없는가
6. null 또는 undefined 데이터를 안전하게 처리하는가
7. Component props 타입이 실제 사용 방식과 일치하는가
8. API Request와 Response Type이 API 계약과 일치하는가

### 책임 분리

9. Screen이 API Function을 직접 호출하지 않는가
10. Screen이 mock data를 직접 import하지 않는가
11. Component가 API 또는 Navigation에 과도하게 의존하지 않는가
12. Hook과 API Function의 책임이 섞이지 않았는가

### 디자인 시스템

13. 색상, 간격, 폰트 크기, radius와 border가 임의로 하드코딩되지 않았는가
14. 기존 공통 토큰을 중복 생성하지 않았는가
15. Design System Snapshot의 금지 사항을 위반하지 않았는가

### 화면 상태와 접근성

16. Screen Specification의 모든 필수 상태가 구현되었는가
17. 주요 Pressable이 최소 터치 영역을 확보했는가
18. 접근성 Role, Label과 State가 필요한 위치에 제공되었는가
19. 긴 한글 텍스트와 빈 값이 레이아웃을 깨뜨리지 않는가
20. 처리 중 중복 입력이 방지되는가

### 의존성

21. `package.json`에 없는 라이브러리를 사용하지 않았는가
22. 제공되지 않은 path alias를 사용하지 않았는가

자체 점검 중 문제가 발견되면 문제를 설명만 하지 말고 생성 코드에 바로 반영해주세요.

---

## 13. 최종 응답 형식

다음 순서로 결과를 제공합니다.

1. 구현 판단 요약
2. 유지한 기존 파일과 이유
3. 생성 또는 수정한 파일별 전체 코드
4. 기존 코드와 연결해야 하는 위치
5. 실제 API 연동 또는 후속 작업에서 교체할 부분
6. 추가 의존성 필요 여부
7. 자체 검증 결과

코드를 생략하거나 일부 파일만 제공하지 마세요.
