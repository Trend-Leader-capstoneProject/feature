# Trend Leader 프론트엔드 디자인 문서

이 디렉터리는 Trend Leader 프론트엔드의 디자인 방향, 디자인 시스템, 화면 명세와 AI 기반 화면 설계·구현 프롬프트를 관리합니다.

이곳의 문서는 단순한 참고 자료가 아니라, 화면마다 서로 다른 디자인과 코드 구조가 생성되는 것을 방지하기 위한 공통 작업 기준입니다.

---

## 1. 디렉터리 구조

```text
docs/frontend-design/
├── README.md
│
├── prompts/
│   ├── 01-art-direction-exploration-prompt.md
│   ├── 02-design-system-freeze-prompt.md
│   ├── 03-screen-specification-prompt.md
│   ├── 04-screen-implementation-prompt.md
│   └── 05-screen-review-prompt.md
│
├── design-system/
│   ├── art-direction.md
│   └── design-system-snapshot.md
│
├── screens/
│   ├── interest-select-screen-spec.md
│   └── recommended-trends-screen-spec.md
│
└── archive/
    ├── front-feature-prompt-v1.md
    ├── selected-art-direction-input.md
    └── recommended-trends-design-freeze-input.md
```

아직 생성되지 않은 문서는 해당 작업 단계에서 순차적으로 추가합니다.

---

## 2. 문서 종류

### Prompt Template

AI에게 특정 결과물을 생성하도록 요청할 때 사용하는 재사용 가능한 입력 문서입니다.

```text
prompts/
```

Prompt Template은 프로젝트의 최종 결정 사항을 보관하지 않습니다.

프롬프트를 실행하여 생성된 결과는 검토 후 `design-system/` 또는 `screens/`에 별도로 저장합니다.

### Design System

프로젝트 전체 화면에서 반복해서 적용해야 하는 공통 디자인 결정을 보관합니다.

```text
design-system/
```

다음과 같은 항목을 포함합니다.

* 아트 디렉션
* 색상 토큰
* 타이포그래피
* 간격
* 크기
* radius
* border
* 아이콘
* 공통 인터랙션 상태
* 접근성
* 공통 컴포넌트 정책

특정 화면의 정보 구조나 API 필드는 포함하지 않습니다.

### Screen Specification

개별 화면의 목적, 책임, 정보 계층, 상태와 인터랙션을 정의합니다.

```text
screens/
```

다음과 같은 항목을 포함합니다.

* 화면 목적
* 진입 조건
* 화면 책임과 비책임
* 정보 계층
* API 데이터
* 로딩·오류·빈 데이터 상태
* 사용자 인터랙션
* Navigation
* 화면 전용 컴포넌트
* Acceptance Criteria

### Archive

더 이상 현재 작업 기준으로 사용하지 않는 이전 프롬프트와 설계 입력을 보관합니다.

```text
archive/
```

Archive 문서는 변경 과정 확인을 위한 참고 자료이며, 새로운 화면 구현의 Source of Truth로 사용하지 않습니다.

---

## 3. Source of Truth 우선순위

문서와 코드 내용이 서로 충돌할 경우 다음 우선순위를 적용합니다.

```text
1. 실제 Backend API Schema
2. 실제 Frontend Type
3. Design System Snapshot
4. 개별 Screen Specification
5. 현재 프로젝트 코드와 폴더 구조
6. Prompt Template
7. Archive 문서
```

Prompt Template은 결과를 생성하기 위한 도구이므로, 실제 API 계약이나 확정된 화면 명세보다 우선하지 않습니다.

AI가 제공된 자료와 다른 필드, 라이브러리, 경로 또는 제품 정책을 임의로 추가하지 않도록 합니다.

---

## 4. 디자인 작업 순서

### 프로젝트 단위 작업

다음 작업은 프로젝트 전체에서 최초 한 번 수행합니다.

```text
아트 디렉션 탐색
→ 아트 디렉션 선택
→ Design System Candidate 작성
→ 대표 화면에서 검증
→ Design System Frozen
```

사용 문서:

```text
01-art-direction-exploration-prompt.md
02-design-system-freeze-prompt.md
```

### 화면 단위 작업

각 화면은 다음 순서로 작업합니다.

```text
현재 코드와 API 점검
→ 화면 명세 작성
→ 화면 명세 검토 및 확정
→ 화면 구현
→ 명세와 구현 결과 검증
```

사용 문서:

```text
03-screen-specification-prompt.md
04-screen-implementation-prompt.md
05-screen-review-prompt.md
```

한 화면의 설계와 구현은 가능한 한 동일한 AI 채팅에서 진행합니다.

---

## 5. 화면별 새 채팅 사용 방법

새로운 화면을 작업할 때는 먼저 다음 자료를 제공합니다.

```text
1. design-system/design-system-snapshot.md
2. 해당 화면의 기존 Screen
3. 관련 Component
4. 관련 Hook
5. 관련 API Function
6. 관련 Type
7. Backend Endpoint와 Response Schema
8. Navigation Type
9. frontend/package.json
10. frontend/tsconfig.json
```

첫 요청에서는 코드를 작성하지 않고 현재 상태와 화면 명세만 점검합니다.

화면 명세가 확정되면 같은 채팅에서 `04-screen-implementation-prompt.md`를 사용합니다.

구현 완료 후에는 TypeScript 검사 결과와 변경 파일을 기준으로 `05-screen-review-prompt.md`를 실행합니다.

---

## 6. 구현 모드

`04-screen-implementation-prompt.md`를 사용할 때 다음 중 하나의 구현 모드를 지정합니다.

### EXISTING_API

이미 구현된 API, Hook과 Type을 유지하면서 화면을 구현합니다.

사용 예:

* 기존 API가 완성된 화면
* Category 조회 화면
* 실제 서버 연동 화면

### MOCK_API

아직 실제 API가 없을 때 확정된 응답 계약과 동일한 mock data source를 사용합니다.

사용 예:

* Backend 구현 전 화면
* API 계약만 확정된 화면

### UI_ONLY

API와 상태 관리를 제외하고 순수한 화면 및 프레젠테이션 컴포넌트만 구현합니다.

사용 예:

* 초기 디자인 검증
* UI 프로토타입

### REFACTOR

기존 기능과 API 연결을 유지하면서 화면 구조, 컴포넌트 분리와 디자인을 개선합니다.

사용 예:

* InterestSelectScreen 디자인 시스템 적용
* 기존 하드코딩 스타일 토큰화
* Screen 내부 UI 컴포넌트 분리

---

## 7. 문서 상태

Design System과 Screen Specification은 다음 상태 중 하나를 가집니다.

### Draft

초기 작성 상태입니다. 아직 구현 기준으로 사용하지 않습니다.

### Candidate

구현 및 화면 검증에 사용할 수 있지만 변경 가능성이 있습니다.

### Frozen

팀 검토와 대표 화면 검증이 완료된 상태입니다. 새로운 화면의 구현 기준으로 사용합니다.

### Deprecated

더 이상 사용하지 않는 문서입니다. 필요한 경우 Archive로 이동합니다.

각 문서 상단에 다음 정보를 작성합니다.

```text
문서 유형:
버전:
상태:
최종 수정일:
관련 화면:
검증 화면:
```

---

## 8. 파일명 규칙

모든 문서 파일명은 소문자 kebab-case를 사용합니다.

```text
올바른 예:
recommended-trends-screen-spec.md
interest-select-screen-spec.md
screen-implementation-prompt.md

잘못된 예:
RecommendedTrends-feature.md
designSystem.md
interest_screen.md
```

프롬프트는 파일명 끝에 `-prompt.md`를 사용합니다.

```text
03-screen-specification-prompt.md
04-screen-implementation-prompt.md
```

화면 명세는 파일명 끝에 `-screen-spec.md`를 사용합니다.

```text
interest-select-screen-spec.md
recommended-trends-screen-spec.md
```

---

## 9. 구현 원칙

* Screen에서 API Function을 직접 호출하지 않습니다.
* Screen은 화면 구성, 사용자 이벤트와 Navigation을 담당합니다.
* Hook은 조회·변경 상태를 담당합니다.
* API Function은 서버 통신만 담당합니다.
* 재사용 가능한 UI는 Component로 분리합니다.
* API 응답 필드는 snake_case를 유지합니다.
* TypeScript strict 기준을 준수합니다.
* 색상, 간격, 타이포그래피와 radius를 임의로 하드코딩하지 않습니다.
* 현재 `package.json`에 없는 외부 라이브러리를 임의로 추가하지 않습니다.
* 로딩, 오류, 빈 데이터와 처리 중 상태를 고려합니다.
* 접근성 상태와 터치 영역을 고려합니다.

---

## 10. 변경 정책

Design System Snapshot을 변경할 때는 다음을 기록합니다.

```text
- 변경 이유
- 변경된 토큰 또는 정책
- 영향받는 화면
- 기존 화면 수정 필요 여부
- 문서 버전
```

특정 화면 하나에서만 필요한 값을 곧바로 전역 디자인 토큰으로 추가하지 않습니다.

다음 조건을 만족할 때만 전역 토큰 또는 공통 컴포넌트로 승격합니다.

```text
- 여러 화면에서 반복되는가
- 의미가 있는 공통 역할인가
- 기존 토큰 조합으로 해결할 수 없는가
```
