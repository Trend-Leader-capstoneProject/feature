# Trend Leader 디자인 시스템 생성 및 동결 프롬프트

## 문서 정보

```text
문서 유형: Prompt Template
실행 시점: 아트 디렉션이 선택되고 art-direction.md가 작성된 후
출력: 구현 가능한 Design System Snapshot
주의: 대표 화면 검증 전에는 Frozen 상태로 확정하지 않음
```

Trend Leader의 확정된 아트 디렉션과 현재 프론트엔드 환경을 바탕으로, React Native 구현에 사용할 수 있는 전역 Design System Snapshot을 작성해주세요.

이 프롬프트는 새로운 화면을 설계하기 위한 화면 명세가 아닙니다.

특정 화면의 정보 구조, API 응답 필드, Navigation과 비즈니스 정책은 포함하지 말고, 프로젝트 전체 화면에서 반복해서 사용할 수 있는 전역 디자인 원칙과 토큰만 정의해주세요.

---

## 1. 실행 정보

```text
실행 모드:
[CREATE_CANDIDATE | REVISE_CANDIDATE | FREEZE]

목표 버전:
[TARGET_VERSION]

현재 상태:
[DRAFT | CANDIDATE | FROZEN]

검증 화면:
[VALIDATION_SCREENS]

검증 결과:
[VALIDATION_RESULTS]
```

### CREATE_CANDIDATE

최초 Design System Candidate를 생성합니다.

* 출력 상태는 `Candidate`로 작성합니다.
* 확정되지 않은 내용을 팀 결정으로 표현하지 않습니다.
* 제안한 값은 구현 가능한 구체적인 값으로 작성합니다.
* 입력 자료만으로 결정할 수 없는 중요한 항목은 `TBD`로 표시합니다.
* 단순히 내용을 채우기 위해 외부 라이브러리나 제품 정책을 임의로 만들지 않습니다.

### REVISE_CANDIDATE

대표 화면 검증 결과를 반영하여 기존 Candidate를 수정합니다.

* 기존 토큰을 무조건 새로 작성하지 않습니다.
* 유지할 항목과 변경할 항목을 구분합니다.
* 토큰 이름 변경이 필요한 경우 기존 화면에 미치는 영향을 기록합니다.
* 화면 하나만의 특수 요구를 전역 토큰으로 추가하지 않습니다.

### FREEZE

검증이 완료된 Candidate를 Frozen 상태로 승격합니다.

다음 자료가 모두 제공된 경우에만 Frozen 상태로 작성합니다.

```text
- 기존 Design System Candidate
- 최소 2개 성격이 다른 대표 화면의 검증 결과
- 팀 검토 결과
- 남아 있는 필수 TBD 항목이 없음
```

위 조건이 충족되지 않은 경우 Frozen으로 표시하지 말고, 부족한 검증 자료와 남은 결정 사항을 정리한 Candidate를 출력해주세요.

---

## 2. Source of Truth

다음 자료만 디자인 시스템 작성 기준으로 사용합니다.

### 확정된 아트 디렉션

```text
[ART_DIRECTION]
```

다음 파일의 내용을 제공합니다.

```text
docs/frontend-design/design-system/art-direction.md
```

### 기존 Design System Snapshot

```text
[EXISTING_DESIGN_SYSTEM_SNAPSHOT]
```

`CREATE_CANDIDATE` 최초 실행에서는 다음과 같이 표시할 수 있습니다.

```text
해당 없음
```

### 현재 프론트엔드 기술 환경

```text
[FRONTEND_PACKAGE_JSON]
[FRONTEND_TSCONFIG]
[CURRENT_FRONTEND_STRUCTURE]
```

### 현재 공통 디자인 코드

```text
[EXISTING_DESIGN_TOKENS]
[EXISTING_SHARED_COMPONENTS]
[EXISTING_THEME_OR_STYLE_FILES]
```

존재하지 않는 경우 다음과 같이 표시합니다.

```text
해당 없음
```

### 대표 화면 또는 기존 구현

```text
[VALIDATION_SCREEN_CODE]
```

최초 Candidate 작성 시에는 현재 구현된 대표 화면을 참고 자료로 사용할 수 있지만, 기존 화면의 하드코딩된 스타일을 자동으로 전역 디자인 기준으로 승격하지 마세요.

### 브랜드 자료

```text
[BRAND_ASSETS_AND_CONSTRAINTS]
```

다음 자료가 존재하면 제공합니다.

* 로고
* 기존 브랜드 색상
* 앱 아이콘
* 발표 자료
* 포스터
* Figma
* 팀이 확정한 색상이나 글꼴

브랜드 자료가 제공되지 않았다면 임의의 값을 최종 확정값처럼 표현하지 마세요.

---

## 3. Source of Truth 적용 원칙

자료가 충돌할 경우 다음 우선순위를 적용합니다.

```text
1. 팀이 확정한 브랜드 자료와 제품 정책
2. art-direction.md
3. 기존 Frozen Design System Snapshot
4. 검증된 공통 프론트엔드 코드
5. 대표 화면 검증 결과
6. 기존 화면의 임시 스타일
```

기존 화면에 작성된 하드코딩 색상, 간격, radius와 폰트 크기는 참고 자료일 뿐이며, 자동으로 디자인 시스템의 정답으로 간주하지 마세요.

제공되지 않은 외부 라이브러리, 폰트와 아이콘 패키지를 설치된 것으로 가정하지 마세요.

---

## 4. Design System의 범위

Design System Snapshot에는 프로젝트 전체에서 반복해서 사용할 다음 내용을 포함합니다.

* 디자인 원칙
* 플랫폼과 화면 기준
* 레이아웃 기반 규칙
* 색상 토큰
* 타이포그래피 토큰
* 간격 토큰
* 크기 토큰
* radius 토큰
* border 토큰
* elevation 규칙
* 아이콘 규칙
* 공통 인터랙션 상태
* 공통 컴포넌트 정책
* 로딩·오류·빈 데이터 상태 원칙
* 콘텐츠 표시 원칙
* 애니메이션 원칙
* 접근성
* 실제 React Native 코드 구조 매핑
* 변경 정책

---

## 5. Design System의 비범위

다음 내용은 Design System Snapshot에 포함하지 마세요.

* 특정 화면의 정보 표시 순서
* 특정 API 요청 또는 응답 필드
* 특정 화면의 Navigation 목적지
* 화면별 버튼 문구
* 관심사 최소·최대 선택 개수
* 특정 목록의 개수
* 특정 화면 전용 컴포넌트명
* 대표 트렌드의 높이
* 특정 이미지 URL
* 특정 화면의 mock data
* 로그인·회원가입·북마크 등의 비즈니스 정책

이러한 항목은 Screen Specification에서 정의합니다.

---

## 6. 작성 원칙

### 구현 가능한 값 사용

다음과 같이 모호한 표현만 작성하지 마세요.

```text
부드러운 여백을 사용한다.
적당한 radius를 사용한다.
가독성 좋은 크기를 사용한다.
브랜드에 어울리는 색을 사용한다.
```

대신 실제 React Native 토큰으로 변환할 수 있는 값을 작성해주세요.

```text
screenGutter: 20dp
sectionGap: 32dp
radiusMedium: 12dp
bodyFontSize: 15sp
bodyLineHeight: 22sp
```

### 과도한 토큰 생성 금지

MVP에서 실제로 사용하지 않을 수십 단계의 토큰을 만들지 마세요.

다음 기준을 따릅니다.

* 의미가 구분되는 최소 토큰만 생성
* 같은 역할의 토큰 중복 금지
* 숫자가 다르다는 이유만으로 토큰을 추가하지 않음
* 특정 화면 하나를 위한 전역 토큰 생성 금지
* primitive token과 semantic token의 책임 구분

### 토큰 명명 규칙

토큰 이름은 영어 camelCase를 사용합니다.

```text
올바른 예:
backgroundCanvas
textPrimary
borderDefault
screenGutter
sectionGap
radiusMedium

잘못된 예:
white
gray1
space20
bigRadius
mainColor2
```

가능하면 실제 값보다 역할이 드러나는 이름을 사용해주세요.

---

## 7. 필수 디자인 결정

### 7.1 디자인 원칙

확정된 아트 디렉션을 다음 항목으로 정리합니다.

* 서비스가 사용자에게 주어야 하는 인상
* 주요 시각 언어
* 보조 시각 언어
* 정보 우선순위
* 카드 사용 기준
* 이미지 사용 기준
* 데이터 상태 표현 기준
* 장식 사용 기준
* 공통 금지 사항

아트 디렉션을 새롭게 재해석하거나 전혀 다른 디자인 방향으로 변경하지 마세요.

---

### 7.2 플랫폼과 레이아웃 기반

다음을 구체적으로 정의합니다.

* 우선 플랫폼
* 기준 화면 너비
* 세로·가로 화면 지원 범위
* Safe Area 처리
* 화면 좌우 gutter
* 화면 상단과 하단 기본 여백
* 섹션 간 기본 간격
* 화면 스크롤 원칙
* 고정 하단 버튼 처리
* 키보드가 필요한 화면의 기본 처리 원칙

Trend Leader의 기본 레이아웃 단위는 다음 방향을 검토합니다.

```text
기본 미세 단위: 4dp
주요 시각 리듬: 8dp
화면 좌우 semantic gutter: 20dp
```

더 적절한 값이 있다면 근거와 함께 Candidate로 제시해주세요.

---

### 7.3 색상 토큰

색상은 Primitive와 Semantic 두 계층으로 나눕니다.

#### Primitive Color

다음 범위에서 실제 필요한 최소 색상만 정의합니다.

* Neutral
* Brand
* Positive
* Negative
* Warning
* Information

각 토큰에 HEX 값을 작성합니다.

#### Semantic Color

화면과 컴포넌트에서는 가능한 한 Semantic Color를 사용하도록 합니다.

최소한 다음 역할을 검토합니다.

```text
backgroundCanvas
backgroundSurface
backgroundSubtle
backgroundSelected

textPrimary
textSecondary
textDisabled
textInverse
textBrand

borderDefault
borderStrong
borderSelected
borderError

actionPrimary
actionPrimaryPressed
actionDisabled

statusPositive
statusNegative
statusWarning
statusInformation
```

각 Semantic Color가 어떤 Primitive Color를 참조하는지 표시해주세요.

색상만으로 상태를 구분하지 않도록 별도의 형태, 아이콘 또는 텍스트 규칙도 함께 정의해주세요.

브랜드 강조 색상이 자료에서 확정되지 않았다면 다음을 작성합니다.

1. 후보 색상
2. 추천 후보
3. 추천 이유
4. 확정 전 상태임을 나타내는 `TBD` 또는 `Proposed`

---

### 7.4 타이포그래피 토큰

최소한 다음 역할을 검토합니다.

```text
display
screenTitle
sectionTitle
itemTitle
body
bodyStrong
caption
label
button
dataRank
dataDelta
```

각 토큰에 다음 값을 작성합니다.

* fontFamily
* fontSize
* fontWeight
* lineHeight
* letterSpacing
* 사용 목적
* 기본 최대 줄 수 또는 줄 수 결정 위치

현재 프로젝트에서 사용할 수 없는 외부 폰트를 설치된 것으로 가정하지 마세요.

폰트가 확정되지 않았다면 시스템 기본 폰트를 Candidate 기본값으로 사용하고, 별도 폰트 도입 여부를 TBD로 분리해주세요.

---

### 7.5 간격 토큰

4dp 기반의 최소 spacing scale을 제안합니다.

다음 값의 필요성을 검토합니다.

```text
0
4
8
12
16
20
24
32
40
48
```

단순 숫자 토큰 외에 다음 semantic layout token을 정의해주세요.

```text
screenGutter
screenTopSpacing
screenBottomSpacing
sectionGap
itemGap
inlineGap
contentGap
bottomActionGap
```

각 semantic token이 어떤 spacing 값을 참조하는지 표시해주세요.

---

### 7.6 크기 토큰

다음을 검토합니다.

```text
touchTarget
iconSmall
iconMedium
iconLarge
buttonHeight
inputHeight
compactControlHeight
```

Android 우선 모바일 앱과 접근성을 고려하여 실제 dp 값을 작성해주세요.

---

### 7.7 Radius 토큰

최대 세 종류의 일반 radius만 사용하도록 검토합니다.

```text
radiusSmall
radiusMedium
radiusFull
```

필요하지 않은 경우 토큰을 줄여도 됩니다.

`radiusFull`은 다음과 같은 경우에만 사용합니다.

* 원형 아이콘 버튼
* 상태 점
* 작은 badge
* 완전한 pill 형태가 의미상 필요한 선택 요소

모든 콘텐츠 영역을 같은 rounded card로 만들기 위해 사용하지 않습니다.

---

### 7.8 Border와 Elevation

Border에 대해 다음을 정의합니다.

* 기본 두께
* 강조 두께
* 기본 색상
* 선택 색상
* 오류 색상
* Divider 규칙

Elevation은 최소 단계만 정의합니다.

```text
elevationNone
elevationRaised
```

기본 정보 구분에는 그림자보다 여백, 타이포그래피와 border를 우선합니다.

그림자가 허용되는 컴포넌트와 금지되는 사용 사례를 명시해주세요.

---

### 7.9 아이콘 규칙

다음을 정의합니다.

* 아이콘 기본 크기
* 작은·중간·큰 아이콘 사용 기준
* outline과 filled 사용 기준
* active와 inactive 상태
* 아이콘과 텍스트 라벨 조합 기준
* 터치 영역과 실제 아이콘 크기의 분리
* accessibilityLabel
* 이모지 기능 아이콘 사용 금지
* 여러 아이콘 패밀리 혼용 금지

현재 `package.json`에 아이콘 라이브러리가 없다면 특정 라이브러리를 사용한다고 확정하지 마세요.

아이콘 패밀리 선택을 TBD로 남기고, 필요한 선택 조건을 작성해주세요.

---

### 7.10 인터랙션 상태

공통 인터랙티브 컴포넌트는 필요한 경우 다음 상태를 지원합니다.

```text
default
pressed
focused
selected
disabled
loading
error
```

각 상태에서 다음 중 어떤 속성이 변경되는지 정의해주세요.

* background
* border
* text
* icon
* opacity
* 입력 가능 여부
* accessibilityState

처리 중인 Action은 중복 입력을 방지해야 합니다.

선택과 오류 상태는 색상만으로 표현하지 않습니다.

---

### 7.11 공통 컴포넌트 정책

다음 공통 컴포넌트 후보의 책임과 공통 규칙을 정의합니다.

```text
ScreenContainer
SectionHeader
PrimaryButton
SecondaryButton
IconButton
SelectionSurface
Divider
Badge
LoadingView
ErrorView
EmptyView
```

각 컴포넌트에 대해 다음을 작성해주세요.

* 공통 컴포넌트로 필요한지 여부
* 책임
* 허용되는 상태
* 사용하는 토큰
* 접근성
* 금지 사용
* 특정 feature 내부 컴포넌트로 유지해야 하는 기준

이번 단계에서는 React Native 구현 코드를 생성하지 마세요.

---

### 7.12 피드백 상태

다음 전역 상태의 공통 원칙을 정의합니다.

```text
최초 로딩
부분 로딩
Pull-to-refresh
빈 데이터
API 오류
오프라인
Mutation 처리 중
Mutation 실패
```

공통으로 정의할 내용:

* 레이아웃 위치
* 사용자에게 제공할 정보 수준
* 재시도 Action의 기본 원칙
* 기존 콘텐츠 유지 여부
* 화면 전체를 교체할지 부분 상태로 표시할지에 대한 기준

화면별 문구와 구체적인 재시도 동작은 Screen Specification에서 정의하도록 남겨주세요.

---

### 7.13 콘텐츠와 데이터 표시 원칙

다음을 정의합니다.

* 한글 텍스트 기본 정렬
* 화면 제목의 줄 수
* 일반 목록 제목의 기본 최대 줄 수
* 말줄임 처리
* null 또는 빈 문자열 표시
* 숫자 정보 정렬
* 날짜와 시각 표기 원칙
* 메타데이터 구분 방식
* 플랫폼명 표시 방식
* 모든 텍스트를 bold로 만들지 않는 기준
* 기능 아이콘으로 이모지를 사용하지 않는 기준

특정 API 필드명이나 화면별 실제 문구는 포함하지 마세요.

---

### 7.14 Motion

MVP에서 필요한 최소 애니메이션 토큰만 정의합니다.

다음을 검토합니다.

```text
motionFast
motionNormal
easingStandard
```

각 duration은 ms 단위로 작성해주세요.

허용 사례:

* 선택 상태 전환
* 버튼 pressed 상태
* 로딩과 콘텐츠 상태 전환
* 데이터 갱신 상태

금지 사례:

* 의미 없는 무한 애니메이션
* 장식용 배경 파동
* 지속적으로 반복되는 레이더 효과
* 정보 이해를 방해하는 큰 이동
* 과도한 카드 등장 효과

---

### 7.15 접근성

다음을 전역 규칙으로 정의합니다.

* 최소 터치 영역
* 본문 최소 폰트 크기
* 텍스트와 배경의 명도 대비
* 상태를 색상만으로 구분하지 않음
* accessibilityRole
* accessibilityLabel
* accessibilityState
* 버튼 disabled와 loading 상태
* 긴 한글 텍스트
* 작은 화면 대응
* 글자 확대 시 고려 사항
* 스크린 리더에서 의미 없는 장식 숨김

---

### 7.16 구현 경로 매핑

Design System Snapshot의 각 영역을 실제 프로젝트 파일에 어떻게 매핑할지 작성해주세요.

기본 후보는 다음과 같습니다.

```text
frontend/src/shared/constants/
├── colors.ts
├── spacing.ts
├── typography.ts
├── radius.ts
├── borders.ts
├── sizes.ts
└── motion.ts
```

공통 UI 후보:

```text
frontend/src/shared/components/
```

기능 전용 UI:

```text
frontend/src/features/{feature}/components/
```

현재 프로젝트 구조와 충돌한다면 실제 구조를 우선하며, 충돌 내용을 설명해주세요.

이번 단계에서는 위 TypeScript 파일을 구현하지 말고 책임과 매핑만 정의해주세요.

---

## 8. 대표 화면 검증 계획

Candidate를 다음과 같이 성격이 다른 최소 두 화면에서 검증하도록 계획을 작성해주세요.

### InterestSelectScreen

검증 대상:

* 화면 제목과 본문
* 선택 가능한 surface
* selected와 disabled 상태
* Primary Action
* 최초 로딩
* API 오류
* 빈 데이터
* 화면 하단 Action
* 비교적 낮은 데이터 밀도

### RecommendedTrendsScreen

검증 대상:

* 높은 정보 밀도
* 화면·섹션·항목의 타이포그래피 계층
* 순위와 변화량 숫자
* 상승·하락·신규 상태
* Divider
* 메타데이터
* 이미지와 텍스트의 우선순위
* 목록과 대표 콘텐츠의 차이

각 검증 화면에서 어떤 토큰과 정책을 확인해야 하는지 체크리스트로 작성해주세요.

---

## 9. 출력 형식

다음 순서로 작성해주세요.

### 1. 입력 자료 점검

* 충분한 자료
* 누락된 자료
* 서로 충돌하는 자료
* 확정할 수 없는 항목
* 이번 실행에서 제안 가능한 항목

### 2. 주요 디자인 결정 요약

* 유지한 아트 디렉션
* 핵심 토큰 전략
* 전역 컴포넌트 전략
* 가장 중요한 금지 사항
* 구현 시 주의점

### 3. 팀 결정이 필요한 항목

각 항목을 다음 형태로 작성해주세요.

```text
결정 항목:
현재 상태:
선택지:
추천:
추천 이유:
결정하지 않았을 때의 영향:
```

### 4. Design System Snapshot

다음 문서에 그대로 붙여넣을 수 있는 완전한 형태로 작성해주세요.

```text
docs/frontend-design/design-system/design-system-snapshot.md
```

Snapshot은 독립된 문서여야 합니다.

다음과 같은 표현을 사용하지 마세요.

```text
위에서 설명한 대로
앞의 내용을 참고
제공한 자료와 동일
```

Snapshot에는 필요한 내용을 모두 포함해주세요.

### 5. 검증 계획

* InterestSelectScreen 검증 항목
* RecommendedTrendsScreen 검증 항목
* Candidate에서 Frozen으로 전환하기 위한 조건

### 6. 변경 영향

`REVISE_CANDIDATE` 또는 `FREEZE` 모드에서는 다음을 추가합니다.

* 유지한 토큰
* 수정한 토큰
* 삭제한 토큰
* 이름이 변경된 토큰
* 영향받는 화면
* 필요한 코드 마이그레이션

---

## 10. Snapshot 문서 메타데이터

생성되는 Design System Snapshot의 상단에는 다음 정보를 포함해주세요.

```text
문서명: Trend Leader Design System Snapshot
문서 유형: Design System
버전: [TARGET_VERSION]
상태: [Candidate | Frozen]
대상: MVP
플랫폼: React Native + Expo, Android 우선
기준 아트 디렉션: Signal Editorial + Trend Radar
최종 수정일: [DATE]
승인자: [APPROVER_OR_TBD]
검증 화면: [VALIDATION_SCREENS]
```

`CREATE_CANDIDATE`와 `REVISE_CANDIDATE` 모드에서는 상태를 `Candidate`로 작성합니다.

`FREEZE` 모드에서만 검증 조건이 충족된 경우 상태를 `Frozen`으로 작성합니다.

---

## 11. 자체 검증

최종 출력 전에 다음을 자체 점검해주세요.

1. 특정 화면 전용 규칙이 전역 디자인 시스템에 들어가지 않았는가
2. API 필드와 비즈니스 정책을 임의로 추가하지 않았는가
3. 모든 토큰에 실제 구현 가능한 값이 있는가
4. 결정할 수 없는 중요 항목이 임의로 확정되지 않았는가
5. Primitive와 Semantic Color의 책임이 구분되어 있는가
6. 같은 역할의 토큰이 중복되지 않았는가
7. MVP에 불필요한 과도한 토큰이 생성되지 않았는가
8. 화면 전체가 rounded card로 구성되도록 유도하지 않는가
9. 상태 표현이 색상에만 의존하지 않는가
10. 최소 터치 영역과 텍스트 가독성 기준이 포함되어 있는가
11. 설치되지 않은 외부 라이브러리를 가정하지 않았는가
12. React Native 코드 경로와 매핑이 현재 프로젝트 구조와 충돌하지 않는가
13. Candidate와 Frozen 상태가 올바르게 구분되었는가
14. 대표 화면 검증 계획이 포함되어 있는가
15. 출력된 Snapshot이 다른 대화에서도 독립적으로 사용 가능한가

문제가 발견되면 설명만 남기지 말고 최종 Design System Snapshot에 반영해주세요.

---

## 12. 금지 사항

* 아직 검증되지 않은 Candidate를 Frozen으로 표시하지 않습니다.
* 특정 화면 하나의 스타일을 전역 규칙으로 일반화하지 않습니다.
* 모든 콘텐츠를 둥근 카드로 구성하지 않습니다.
* glassmorphism을 사용하지 않습니다.
* 보라색·파란색 그라데이션을 기본 테마로 자동 선택하지 않습니다.
* 모든 컴포넌트에 그림자를 사용하지 않습니다.
* 의미 없는 그래프, 파동과 레이더 장식을 추가하지 않습니다.
* 이모지를 기능 아이콘으로 사용하지 않습니다.
* 일반 금융 대시보드나 SNS 피드 형태를 복제하지 않습니다.
* 제공되지 않은 폰트와 아이콘 라이브러리를 설치된 것으로 가정하지 않습니다.
* React Native 구현 코드를 생성하지 않습니다.
* 화면별 Screen Specification을 작성하지 않습니다.
