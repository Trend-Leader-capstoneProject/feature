# Trend Leader Design System Snapshot

## 문서 정보

```text
문서명: Trend Leader Design System Snapshot
문서 유형: Design System
버전: 0.1
상태: Candidate
대상: MVP
플랫폼: React Native + Expo, Android 우선
화면 방향: 세로 화면 우선
기준 아트 디렉션: Signal Editorial + Trend Radar
최종 수정일: 2026-08-05
승인자: TBD
검증 화면:
- InterestSelectScreen
- RecommendedTrendsScreen
```

---

## 1. 문서 목적

이 문서는 Trend Leader 프론트엔드 전체 화면에서 반복해서 사용하는 디자인 원칙, 토큰, 공통 상태와 컴포넌트 정책을 정의한다.

이 문서는 React Native 구현 전에 사용하는 Candidate 기준이다. 아직 대표 화면 검증과 팀 승인이 완료되지 않았으므로 Frozen 상태가 아니다.

개별 화면은 이 문서를 공통 기준으로 사용하되, 화면 목적·정보 순서·API 필드·Navigation·비즈니스 정책은 각 Screen Specification에서 별도로 정의한다.

---

## 2. Source of Truth

자료가 충돌할 경우 다음 우선순위를 적용한다.

```text
1. 팀이 최종 승인한 브랜드·제품 정책
2. docs/frontend-design/design-system/art-direction.md
3. 본 Design System Snapshot
4. 최신 Backend API Schema와 Frontend Type
5. 검증된 공통 프론트엔드 코드
6. 최신 화면 명세
7. 기존 Figma 및 UI/UX 산출물
8. 이전 화면 구성 조언과 Archive 문서
```

기존 Figma와 화면 코드는 시각적 연속성을 위한 참고 자료로 사용하지만, 하드코딩된 값을 자동으로 전역 토큰으로 승격하지 않는다.

---

## 3. 결정 상태

이 문서의 항목은 다음 상태로 구분한다.

| 상태 | 의미 |
|---|---|
| Confirmed | 현재 프로젝트 범위 또는 아트 디렉션에서 확정된 방향 |
| Candidate | 대표 화면에 적용하고 검증할 구체적인 제안값 |
| TBD | 팀 결정이나 추가 검증이 필요한 항목 |
| Out of Scope | MVP 범위에서 구현하지 않는 항목 |

### 3.1 Confirmed

- React Native + Expo 기반 모바일 앱
- Android 우선
- TypeScript strict
- Signal Editorial을 주요 시각 언어로 사용
- Trend Radar를 데이터 변화 상태에만 사용하는 보조 시각 언어로 사용
- 정보 계층은 제목·순위·변화량·요약·메타데이터 순으로 명확하게 표현
- 모든 콘텐츠를 동일한 rounded card로 구성하지 않음
- 상태를 색상만으로 구분하지 않음
- 의미 없는 레이더·파동·가짜 차트·무한 애니메이션을 사용하지 않음
- 이모지를 기능 아이콘으로 사용하지 않음
- 화면별 API 필드와 비즈니스 정책은 Screen Specification에서 관리

### 3.2 Candidate

- 이 문서에 정의한 정확한 색상, 간격, 타이포그래피, radius, 크기와 motion 값
- 기존 Figma에서 사용한 인디고·페리윙클 계열을 브랜드 후보로 유지
- 기존 Figma에서 사용한 노란색을 경고색이 아닌 신호 강조색으로 분리
- MVP는 light mode만 지원
- 외부 폰트 없이 플랫폼 시스템 폰트를 우선 사용

### 3.3 TBD

- 브랜드 색상 최종 승인
- 공식 로고 원본과 사용 규정
- 아이콘 패밀리
- 별도 한글 폰트 도입 여부
- 상태 색상 최종 승인
- dark mode 도입 시점

---

## 4. 적용 범위

### 4.1 포함

- 화면 공통 배경과 surface
- 색상 체계
- 타이포그래피 역할
- 간격과 레이아웃 기준
- 크기, radius, border와 elevation
- 아이콘 사용 원칙
- 공통 인터랙션 상태
- 공통 버튼과 피드백 화면 정책
- 데이터 상태 표현
- 접근성
- motion
- 실제 프론트엔드 경로 매핑
- 변경 및 검증 정책

### 4.2 포함하지 않음

- 특정 화면의 섹션 순서
- 특정 API 요청·응답 필드
- 관심사 최소·최대 선택 개수
- 화면별 버튼 문구
- 화면별 Navigation 목적지
- 특정 목록의 노출 개수
- 특정 화면의 이미지 높이
- mock data
- 화면 전용 컴포넌트 파일명
- 로그인·저장·검색 등의 비즈니스 규칙

---

## 5. 핵심 디자인 원칙

### 5.1 Information First

장식보다 정보 이해를 우선한다.

사용자는 화면을 짧게 훑어도 다음 내용을 구분할 수 있어야 한다.

1. 현재 보고 있는 주제
2. 핵심 항목
3. 순위와 변화 상태
4. 요약
5. 출처·카테고리·시각 등의 메타데이터
6. 저장과 이동 등의 보조 Action

### 5.2 Editorial Hierarchy

편집 디자인처럼 타이포그래피, 여백과 정렬로 정보의 중요도를 표현한다.

카드와 그림자는 기본 구분 수단이 아니다.

```text
타이포그래피
→ 여백
→ Divider
→ 배경 명도 차이
→ 필요한 경우에만 Surface와 Elevation
```

### 5.3 Signal with Meaning

선, 점, 화살표와 강조색은 실제 데이터 변화가 있을 때만 사용한다.

상승·하락·신규·변화 없음은 색상과 함께 아이콘 또는 텍스트를 제공한다.

### 5.4 Controlled Density

넓은 빈 공간만으로 고급스러움을 표현하지 않는다.

360dp 화면에서도 정보가 답답하지 않으면서 실제 서비스 수준의 밀도를 유지해야 한다.

### 5.5 Reusable, Not Generic

여러 화면에서 같은 의미로 반복되는 항목만 전역 토큰이나 공통 컴포넌트로 승격한다.

특정 화면 하나에 필요한 값을 전역 시스템으로 만들지 않는다.

---

## 6. 플랫폼과 레이아웃

| 항목 | Candidate 기준 |
|---|---|
| 우선 플랫폼 | Android |
| 프레임워크 | React Native + Expo |
| 기본 방향 | Portrait |
| 우선 화면 너비 | 360~412dp |
| 화면 배경 | `backgroundCanvas` |
| 기본 좌우 gutter | 20dp |
| 기본 상단 간격 | 24dp |
| 기본 하단 간격 | 24dp |
| 기본 섹션 간격 | 32dp |
| Safe Area | 모든 최상위 화면에서 반영 |
| 가로 화면 | MVP Out of Scope |
| Dark Mode | MVP Out of Scope |

### 6.1 Screen Layout

- 최상위 화면은 Safe Area를 반영한다.
- 콘텐츠는 왼쪽 정렬을 기본으로 한다.
- 화면 제목과 핵심 콘텐츠가 첫 화면에서 지나치게 아래로 밀리지 않도록 한다.
- 단순 정보 화면에서 모든 요소를 중앙 정렬하지 않는다.
- 긴 목록은 `FlatList` 사용을 우선 검토한다.
- 가로 스크롤은 카테고리 필터처럼 의미가 명확한 경우에만 사용한다.
- 고정 하단 Action이 있는 화면은 목록 마지막 콘텐츠가 버튼에 가려지지 않도록 하단 여백을 확보한다.
- 키보드 입력 화면은 키보드가 주요 Action과 현재 입력 필드를 가리지 않도록 구성한다.

### 6.2 Layout Units

```text
기본 미세 단위: 4dp
주요 시각 리듬: 8dp
화면 좌우 semantic gutter: 20dp
```

20dp gutter는 4dp 단위에 포함되며, 360dp 화면에서 정보 밀도와 가독성을 함께 확보하기 위한 semantic 예외값으로 사용한다.

---

## 7. Color System

색상은 Primitive Color와 Semantic Color로 구분한다.

화면과 컴포넌트에서는 가능한 한 Semantic Color만 사용한다.

### 7.1 Primitive Colors

#### Neutral

| Token | HEX | 상태 | 용도 |
|---|---:|---|---|
| `neutral0` | `#FFFFFF` | Candidate | Surface, 흰색 콘텐츠 영역 |
| `neutral50` | `#FAF9F7` | Candidate | 따뜻한 기본 Canvas |
| `neutral100` | `#F4F2EE` | Candidate | Subtle background |
| `neutral200` | `#E5E1DA` | Candidate | 기본 Border, Divider |
| `neutral300` | `#CDC8BF` | Candidate | Strong border |
| `neutral400` | `#A39E95` | Candidate | Disabled text |
| `neutral500` | `#767168` | Candidate | Secondary text |
| `neutral700` | `#47433D` | Candidate | Secondary strong text, icon |
| `neutral900` | `#171612` | Candidate | Primary text |

#### Brand Indigo

기존 Figma의 TL 워드마크, 버튼, 탭과 선택 영역에서 사용된 계열을 Candidate로 유지한다.

| Token | HEX | 상태 | 용도 |
|---|---:|---|---|
| `indigo100` | `#E4E8FF` | Existing reference | Brand subtle surface |
| `indigo200` | `#BCC5FF` | Existing reference | Selected muted surface |
| `indigo400` | `#8E9DFF` | Existing reference | Primary Action |
| `indigo500` | `#7789F6` | Candidate | Primary pressed |
| `indigo700` | `#3B4CA8` | Existing reference | TL 워드마크, brand text |
| `indigo900` | `#1414BC` | Existing reference | Active icon, link, strong focus |

#### Signal

노란색은 경고가 아니라 새롭게 포착된 정보나 특별히 주목할 신호를 나타낸다.

| Token | HEX | 상태 | 용도 |
|---|---:|---|---|
| `signalYellow` | `#FFDD55` | Existing reference | Signal highlight |
| `signalYellowSubtle` | `#FFF5C2` | Candidate | Signal subtle background |

#### Status

| Token | HEX | 상태 | 용도 |
|---|---:|---|---|
| `positive100` | `#E8F6EF` | Candidate | Positive subtle background |
| `positive700` | `#147A52` | Candidate | 상승·성공 text/icon |
| `negative100` | `#FDECEA` | Candidate | Negative subtle background |
| `negative500` | `#FF543E` | Existing reference | 하락 signal icon |
| `negative700` | `#B42318` | Candidate | 오류 text/border |
| `warning100` | `#FFF4D6` | Candidate | Warning subtle background |
| `warning700` | `#8A5A00` | Candidate | 경고 text/icon |
| `information100` | `#EAF2FC` | Candidate | Information subtle background |
| `information700` | `#2F6FBE` | Candidate | 정보 text/icon |

### 7.2 Semantic Colors

#### Background

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `backgroundCanvas` | `neutral50` | 앱 기본 화면 배경 |
| `backgroundSurface` | `neutral0` | 독립 Surface |
| `backgroundSubtle` | `neutral100` | 약한 영역 구분 |
| `backgroundSelected` | `indigo100` | 선택 상태 |
| `backgroundBrandMuted` | `indigo200` | 강한 선택 또는 강조 Surface |
| `backgroundSignal` | `signalYellow` | 중요한 신호 강조 |
| `backgroundDisabled` | `neutral100` | 비활성 Control |

#### Text

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `textPrimary` | `neutral900` | 제목과 본문 |
| `textSecondary` | `neutral500` | 설명과 메타데이터 |
| `textStrongSecondary` | `neutral700` | 강조된 보조 정보 |
| `textDisabled` | `neutral400` | 비활성 상태 |
| `textInverse` | `neutral0` | 어두운 배경 위 텍스트 |
| `textBrand` | `indigo700` | 브랜드 텍스트 |
| `textLink` | `indigo900` | 텍스트 링크 |
| `textOnPrimary` | `neutral900` | Primary Action 위 텍스트 |
| `textOnSignal` | `neutral900` | Signal 배경 위 텍스트 |

#### Border and Divider

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `borderDefault` | `neutral200` | 일반 Border |
| `borderStrong` | `neutral300` | 입력창과 강조 Border |
| `borderSelected` | `indigo700` | 선택 상태 |
| `borderError` | `negative700` | 오류 상태 |
| `dividerDefault` | `neutral200` | 목록과 섹션 구분 |
| `focusRing` | `indigo900` | 키보드·접근성 Focus |

#### Action

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `actionPrimary` | `indigo400` | Primary Button |
| `actionPrimaryPressed` | `indigo500` | Primary pressed |
| `actionPrimaryText` | `neutral900` | Primary Button text |
| `actionSecondary` | `neutral0` | Secondary Button background |
| `actionSecondaryText` | `indigo700` | Secondary Button text |
| `actionDisabled` | `neutral200` | Disabled Action |
| `actionDisabledText` | `neutral400` | Disabled Action text |

#### Status and Signal

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `statusPositive` | `positive700` | 상승·성공 |
| `statusPositiveSubtle` | `positive100` | 상승·성공 배경 |
| `statusNegative` | `negative700` | 하락·오류 |
| `statusNegativeSubtle` | `negative100` | 하락·오류 배경 |
| `statusWarning` | `warning700` | 주의 |
| `statusWarningSubtle` | `warning100` | 주의 배경 |
| `statusInformation` | `information700` | 정보·신규 |
| `statusInformationSubtle` | `information100` | 정보·신규 배경 |
| `signalHighlight` | `signalYellow` | 주목할 트렌드 신호 |
| `signalHighlightSubtle` | `signalYellowSubtle` | 약한 신호 배경 |

### 7.3 Contrast Rules

- 일반 텍스트는 배경과 최소 4.5:1 명도 대비를 목표로 한다.
- 큰 텍스트와 큰 숫자는 최소 3:1을 목표로 한다.
- `actionPrimary` 위에는 흰색이 아니라 `textOnPrimary`를 사용한다.
- `#8E9DFF`와 `#171612` 조합은 약 7.26:1로 일반 텍스트 AA 기준을 충족한다.
- `#3B4CA8`와 `#FFFFFF` 조합은 약 7.54:1로 일반 텍스트 AA 기준을 충족한다.
- 상태 색상은 텍스트·아이콘·형태를 함께 사용한다.

---

## 8. Typography

MVP에서는 별도 외부 폰트를 설치하지 않고 플랫폼 시스템 폰트를 사용한다.

```text
fontFamily: Platform System Default
Android 기본 예상: Roboto 계열
별도 폰트: TBD
```

### 8.1 Typography Tokens

| Token | Size | Line Height | Weight | Letter Spacing | 기본 용도 |
|---|---:|---:|---:|---:|---|
| `display` | 32 | 40 | 700 | -0.4 | 매우 제한적인 대표 제목 |
| `screenTitle` | 26 | 34 | 700 | -0.2 | 화면 제목 |
| `sectionTitle` | 20 | 28 | 700 | -0.1 | 섹션 제목 |
| `itemTitle` | 17 | 24 | 600 | 0 | 목록·카드 핵심 제목 |
| `body` | 15 | 22 | 400 | 0 | 일반 본문 |
| `bodyStrong` | 15 | 22 | 600 | 0 | 강조 본문 |
| `caption` | 13 | 18 | 400 | 0 | 보조 설명과 메타데이터 |
| `label` | 13 | 18 | 600 | 0.1 | 짧은 상태와 Control label |
| `button` | 16 | 22 | 700 | 0 | 주요 버튼 |
| `dataRank` | 28 | 34 | 700 | -0.3 | 순위 숫자 |
| `dataDelta` | 14 | 20 | 600 | 0 | 변화량 |
| `input` | 16 | 22 | 400 | 0 | 입력 필드 |

React Native의 숫자 정보에는 가능한 경우 `fontVariant: ["tabular-nums"]`를 적용한다.

### 8.2 Text Hierarchy Rules

- `display`는 화면마다 반복 사용하지 않는다.
- 일반 화면 제목은 `screenTitle`을 사용한다.
- 목록 항목 제목은 `itemTitle`을 기본으로 한다.
- 모든 텍스트를 600~700 weight로 만들지 않는다.
- `caption`은 핵심 정보를 전달하는 유일한 수단으로 사용하지 않는다.
- 버튼 라벨은 한 줄을 기본으로 한다.
- 한글 제목은 단어 단위 줄바꿈이 어색하지 않도록 너비와 최대 줄 수를 검토한다.

### 8.3 Default Line Limits

| 역할 | 기본 최대 줄 수 |
|---|---:|
| `display` | 2 |
| `screenTitle` | 2 |
| `sectionTitle` | 2 |
| `itemTitle` | 2 |
| `caption` | 2 |
| `label` | 1 |
| `button` | 1 |
| `dataRank` | 1 |
| `dataDelta` | 1 |

`body`의 최대 줄 수는 Screen Specification에서 결정한다.

---

## 9. Spacing

### 9.1 Primitive Spacing

| Token | Value |
|---|---:|
| `space0` | 0 |
| `space1` | 4 |
| `space2` | 8 |
| `space3` | 12 |
| `space4` | 16 |
| `space5` | 20 |
| `space6` | 24 |
| `space8` | 32 |
| `space10` | 40 |
| `space12` | 48 |

### 9.2 Semantic Spacing

| Token | Primitive 참조 | 용도 |
|---|---|---|
| `screenGutter` | `space5` | 화면 좌우 여백 |
| `screenTopSpacing` | `space6` | 화면 상단 기본 여백 |
| `screenBottomSpacing` | `space6` | 화면 하단 기본 여백 |
| `sectionGap` | `space8` | 큰 섹션 사이 |
| `itemGap` | `space4` | 반복 항목 사이 |
| `contentGap` | `space3` | 한 콘텐츠 내부 요소 사이 |
| `inlineGap` | `space2` | 아이콘·텍스트와 인라인 요소 |
| `controlGap` | `space3` | 입력창·버튼 등 Control 사이 |
| `bottomActionGap` | `space4` | 콘텐츠와 고정 하단 Action 사이 |
| `feedbackGap` | `space4` | 상태 아이콘·문구·Action 사이 |

숫자 차이만을 이유로 새로운 spacing token을 추가하지 않는다.

---

## 10. Size Tokens

| Token | Value | 용도 |
|---|---:|---|
| `touchTarget` | 44 | 최소 터치 영역 |
| `buttonHeight` | 52 | Primary·Secondary Button |
| `inputHeight` | 48 | 한 줄 입력 필드 |
| `compactControlHeight` | 40 | 작은 Filter·Control |
| `iconSmall` | 16 | 메타데이터·작은 상태 |
| `iconMedium` | 20 | 일반 Action |
| `iconLarge` | 24 | 주요 Action·Navigation |
| `dividerHeight` | 1 | Divider |

텍스트 확대에 대응하기 위해 버튼과 입력 필드는 고정 `height`보다 `minHeight` 사용을 우선한다.

---

## 11. Radius

| Token | Value | 용도 |
|---|---:|---|
| `radiusSmall` | 8 | 입력창, 작은 상태 영역 |
| `radiusMedium` | 12 | 버튼, 선택 가능한 Surface |
| `radiusFull` | 999 | 원형 버튼, 상태 점, 의미 있는 pill |

### 11.1 Radius Rules

- 일반 정보 섹션에 radius를 자동 적용하지 않는다.
- 큰 콘텐츠 영역을 모두 둥근 카드로 만들지 않는다.
- `radiusFull`은 선택 Chip, 상태 Badge 또는 원형 아이콘 버튼처럼 형태에 의미가 있을 때만 사용한다.
- `radiusLarge`는 Candidate v0.1에 포함하지 않는다.
- 두 개 이상의 대표 화면에서 필요성이 확인될 때만 새로운 radius를 추가한다.

---

## 12. Border and Elevation

### 12.1 Border

| Token | Value |
|---|---:|
| `borderWidthDefault` | 1 |
| `borderWidthStrong` | 2 |

- 일반 구분은 `borderWidthDefault`를 사용한다.
- 선택, Focus와 오류처럼 상태 전달이 필요한 경우에만 `borderWidthStrong`을 사용한다.
- Divider는 목록 전체 너비 또는 콘텐츠 시작선에 맞춰 일관되게 정렬한다.
- Divider와 카드 Border를 같은 화면에서 과도하게 중첩하지 않는다.

### 12.2 Elevation

| Token | Android 기준 | 사용 범위 |
|---|---:|---|
| `elevationNone` | 0 | 기본 |
| `elevationRaised` | 2 | 떠 있는 Action 또는 명확한 계층이 필요한 제한된 Surface |

Elevation보다 여백, 타이포그래피, Divider와 배경 명도 차이를 우선한다.

다음에는 Elevation을 사용하지 않는다.

- 모든 목록 항목
- 일반 메타데이터
- 화면의 모든 버튼
- 단순한 섹션 구분
- 장식 목적

---

## 13. Iconography

### 13.1 Current Status

```text
아이콘 패밀리: TBD
현재 package.json에 별도 아이콘 라이브러리 없음
기존 Figma: Outline 중심의 인디고 아이콘 사용
```

### 13.2 Rules

- 한 화면에서 여러 아이콘 패밀리를 혼용하지 않는다.
- 이모지를 기능 아이콘으로 사용하지 않는다.
- 일반 상태는 outline을 기본으로 한다.
- 선택·저장 완료처럼 명시적 활성 상태에서만 filled 아이콘을 검토한다.
- 실제 아이콘 크기와 터치 영역을 분리한다.
- `iconMedium` 아이콘 버튼도 최소 `touchTarget` 영역을 확보한다.
- 아이콘만 있는 버튼은 `accessibilityLabel`을 제공한다.
- 장식 아이콘은 스크린 리더 탐색에서 제외한다.
- 플랫폼 브랜드 색상을 전역 아이콘 색상으로 확장하지 않는다.

### 13.3 Color

| 상태 | Color |
|---|---|
| Default | `neutral700` |
| Inactive navigation | `neutral500` |
| Active navigation | `indigo900` |
| Brand | `indigo700` |
| Disabled | `neutral400` |
| Positive | `positive700` |
| Negative | `negative700` |
| Warning | `warning700` |
| Information | `information700` |

---

## 14. Interaction States

공통 인터랙티브 요소는 필요한 범위에서 다음 상태를 지원한다.

```text
default
pressed
focused
selected
disabled
loading
error
```

### 14.1 State Matrix

| 상태 | Background | Border | Text/Icon | 동작 |
|---|---|---|---|---|
| Default | 기본 semantic color | 기본 | 기본 | 입력 가능 |
| Pressed | pressed semantic color | 유지 또는 강화 | 유지 | 짧은 시각 피드백 |
| Focused | 기본 | `focusRing`, strong width | 유지 | 접근성 Focus 표시 |
| Selected | `backgroundSelected` | `borderSelected` | `textBrand` 또는 selected icon | 선택됨 |
| Disabled | `backgroundDisabled` | `borderDefault` | `textDisabled` | 입력 차단 |
| Loading | 기본 또는 pressed | 유지 | Spinner + label 유지 | 중복 입력 차단 |
| Error | `statusNegativeSubtle` 필요 시 | `borderError` | `statusNegative` | 오류 정보 제공 |

### 14.2 State Rules

- 선택 상태는 배경색만 변경하지 않는다.
- 선택 상태는 Border, Check icon 또는 명시적인 텍스트 상태를 함께 사용한다.
- 오류 상태는 색상뿐 아니라 오류 문구를 제공한다.
- Loading 중 Action은 중복 실행을 막는다.
- Loading 상태에서도 버튼 너비가 갑자기 바뀌지 않도록 라벨 공간을 유지한다.
- Disabled opacity만으로 상태를 표현하지 않는다.
- Pressed feedback은 빠르고 절제되게 사용한다.

---

## 15. Data Signal Rules

Trend Radar는 실제 데이터 변화 상태에만 적용한다.

| 상태 | 기본 표현 | Color | 보조 표현 |
|---|---|---|---|
| 상승 | `↑ +n` 또는 `↑ +n%` | `statusPositive` | “상승” 텍스트 |
| 하락 | `↓ -n` 또는 `↓ -n%` | `statusNegative` | “하락” 텍스트 |
| 신규 | `신규` | `statusInformation` | Badge 또는 label |
| 변화 없음 | `—` | `textSecondary` | “변동 없음” |
| 주목 신호 | 강조 배경 | `signalHighlight` | 실제 의미가 있는 label |

### 15.1 Rules

- 화살표만 표시하지 않는다.
- 빨강과 초록만으로 상태를 구분하지 않는다.
- 변화량의 단위는 Screen Specification과 API 계약을 따른다.
- 순위와 변화량에는 tabular 숫자를 적용한다.
- `signalHighlight`는 경고나 오류에 사용하지 않는다.
- 의미 없는 불꽃 이모지 대신 아이콘 패밀리 확정 후 vector icon 또는 텍스트 label을 사용한다.

---

## 16. Common Component Policies

### 16.1 ScreenContainer

**상태:** 공통 컴포넌트 후보 확정

책임:

- Safe Area
- `backgroundCanvas`
- 화면 좌우 gutter
- 화면 상·하단 기본 여백
- 고정 하단 Action이 있는 화면의 콘텐츠 여백

금지:

- 화면별 API 상태 관리
- Navigation 직접 처리
- 화면별 제목 문구 보유

### 16.2 PrimaryButton

**상태:** 공통 컴포넌트 후보 확정

기본 토큰:

```text
minHeight: buttonHeight
background: actionPrimary
pressed: actionPrimaryPressed
text: actionPrimaryText
radius: radiusMedium
horizontalPadding: space5
```

필수 상태:

```text
default
pressed
disabled
loading
```

접근성:

- `accessibilityRole="button"`
- disabled·busy 상태 제공
- 최소 터치 영역 확보
- 라벨 한 줄 기본

### 16.3 SecondaryButton

**상태:** 공통 컴포넌트 후보 확정

기본 토큰:

```text
minHeight: buttonHeight
background: actionSecondary
border: borderStrong
text: actionSecondaryText
radius: radiusMedium
```

Primary Action과 같은 시각적 강도로 표현하지 않는다.

### 16.4 IconButton

**상태:** Candidate

아이콘 패밀리가 결정되기 전에는 공통 구현을 동결하지 않는다.

필수 조건:

- 최소 `touchTarget`
- `accessibilityLabel`
- selected·disabled 상태
- 실제 아이콘 크기와 터치 영역 분리

### 16.5 Divider

**상태:** 공통 컴포넌트 후보 확정

```text
height: dividerHeight
color: dividerDefault
```

목록 항목과 섹션 구분에 사용하되 모든 콘텐츠 사이에 반복 삽입하지 않는다.

### 16.6 LoadingView

**상태:** 공통 컴포넌트 후보 확정

책임:

- ActivityIndicator
- 선택적 상태 문구
- 화면 전체 또는 섹션 단위 로딩 지원

장식용 무한 애니메이션이나 레이더 효과를 사용하지 않는다.

### 16.7 ErrorView

**상태:** 공통 컴포넌트 후보 확정

책임:

- 오류 요약
- 필요한 경우 재시도 Action
- 접근 가능한 오류 안내

개발자용 원본 오류 메시지를 사용자에게 그대로 노출하지 않는다.

### 16.8 EmptyView

**상태:** 공통 컴포넌트 후보 확정

책임:

- 현재 데이터가 없는 이유를 짧게 설명
- 사용자가 취할 수 있는 다음 행동이 있을 때만 Action 제공

반드시 일러스트를 포함하지 않는다.

### 16.9 SectionHeader

**상태:** Candidate

InterestSelectScreen과 RecommendedTrendsScreen에서 반복되는 책임이 확인된 후 공통 컴포넌트로 승격한다.

### 16.10 SelectionSurface

**상태:** Feature Local 우선

Interest feature 안에서 먼저 구현하고 다음 조건을 만족할 때 공통으로 승격한다.

- 두 개 이상의 feature에서 사용
- selected·disabled·error 상태의 의미가 동일
- 동일한 토큰과 접근성 정책 사용

### 16.11 Badge

**상태:** Feature Local 우선

상태 Badge와 카테고리 Chip을 하나의 범용 컴포넌트로 합치지 않는다.

### 16.12 Generic Card

**상태:** 생성 금지

책임이 불분명한 범용 `Card` 컴포넌트를 만들지 않는다.

구체적인 의미가 있는 Surface만 별도 컴포넌트로 정의한다.

---

## 17. Feedback States

### 17.1 최초 로딩

- 가능한 경우 화면 Shell과 제목은 유지한다.
- 콘텐츠를 아직 표시할 수 없다면 `LoadingView`를 사용한다.
- 장시간 로딩이 예상될 때만 문구를 함께 제공한다.
- Skeleton은 반복 구조가 확정된 이후 검토한다.

### 17.2 부분 로딩

- 전체 화면을 교체하지 않는다.
- 로딩 중인 섹션 안에서만 상태를 표시한다.
- 이미 표시된 다른 데이터는 유지한다.

### 17.3 Pull-to-refresh

- 기존 콘텐츠를 유지한다.
- 상단 Refresh indicator를 사용한다.
- 화면 중앙을 전체 LoadingView로 교체하지 않는다.

### 17.4 빈 데이터

- 오류와 구분한다.
- “데이터가 없음”과 “조건에 맞는 결과가 없음”을 구분한다.
- 다음 행동이 명확할 때만 Action을 제공한다.

### 17.5 API 오류

- 캐시된 데이터가 있으면 가능한 한 유지한다.
- 전체 데이터를 표시할 수 없을 때 `ErrorView`를 사용한다.
- 재시도가 가능한 경우 재시도 Action을 제공한다.

### 17.6 오프라인

- 기존 콘텐츠가 있으면 유지하고 inline 상태를 우선한다.
- 네트워크 연결이 필수이고 표시할 데이터가 없을 때만 화면 전체 상태를 사용한다.
- 네트워크 감지 인프라는 별도 기술 결정 사항이다.

### 17.7 Mutation 처리 중

- 실행한 Action을 disabled 또는 busy 상태로 전환한다.
- 중복 입력을 막는다.
- 성공 전 화면 전체 구조를 불필요하게 변경하지 않는다.

### 17.8 Mutation 실패

- 실패한 Action 가까이에 오류를 표시한다.
- 데이터가 실제로 변경되지 않았음을 명확하게 전달한다.
- 별도 Toast 인프라가 확정되기 전에는 inline 피드백을 우선한다.

---

## 18. Content and Data Display

### 18.1 Korean Text

- 기본 정렬은 왼쪽 정렬이다.
- 화면 제목과 항목 제목은 자연스러운 한글 줄바꿈을 고려한다.
- 지나치게 작은 글자 크기로 정보를 압축하지 않는다.
- 모든 제목과 라벨을 굵게 처리하지 않는다.

### 18.2 Truncation

- 화면 제목은 기본 2줄까지 허용한다.
- 목록 항목 제목은 기본 2줄까지 허용한다.
- 긴 메타데이터는 우선순위가 낮은 항목부터 생략한다.
- 말줄임으로 핵심 의미가 사라지는 경우 Screen Specification에서 별도 규칙을 정의한다.

### 18.3 Null and Empty Values

- 선택적 메타데이터가 없으면 해당 항목을 생략한다.
- 일반 콘텐츠에서 의미 없는 `-`, `null`, `N/A`를 노출하지 않는다.
- 순위처럼 고정 슬롯이 필요한 경우에만 `—`를 사용한다.

### 18.4 Date and Time

Candidate 기본 형식:

```text
날짜: YYYY.MM.DD.
시간: HH:mm
날짜와 시간: YYYY.MM.DD. HH:mm
```

“오늘”, “어제”, “방금” 등의 상대 표현은 실제 시간 데이터와 갱신 정책이 확정된 화면에서만 사용한다.

### 18.5 Number and Rank

- 순위는 정수로 표시한다.
- 변화량에는 부호를 포함한다.
- 퍼센트 변화량은 `+32%`, `-8%`처럼 표시한다.
- 숫자는 가능한 한 tabular 정렬을 사용한다.
- 단위가 다른 숫자를 같은 열에서 직접 비교하지 않는다.

### 18.6 Metadata

- 카테고리, 플랫폼, 출처와 시각은 핵심 제목보다 약하게 표현한다.
- 인라인 메타데이터 구분자는 `·`를 기본 후보로 사용한다.
- 메타데이터 노출 순서는 Screen Specification에서 정의한다.
- 플랫폼 브랜드 색상을 화면 전체로 확장하지 않는다.

### 18.7 Keywords

- 단순 정보 키워드와 선택 가능한 키워드를 시각적으로 구분한다.
- 모든 키워드를 같은 pill 모양으로 만들지 않는다.
- 선택 가능한 키워드만 button role과 selected state를 가진다.
- 정보 키워드는 텍스트, 구분자 또는 낮은 강조 Surface를 사용할 수 있다.

### 18.8 Images

- 이미지는 정보 이해를 돕는 보조 요소다.
- 의미 없는 stock image나 장식용 placeholder를 사용하지 않는다.
- 이미지가 없어도 제목과 상태의 계층이 유지되어야 한다.
- 의미 있는 이미지는 접근 가능한 설명을 검토한다.
- 이미지 비율과 실제 크기는 Screen Specification에서 정의한다.
- 공통 이미지 비율은 두 개 이상의 화면에서 반복될 때만 전역 토큰으로 승격한다.

---

## 19. Logo Direction

기존 Figma의 TL 워드마크를 브랜드 자산 기준으로 유지한다.

### Candidate Rules

- 기본 색상은 `indigo700`을 사용한다.
- 밝은 배경에서 사용하는 것을 기본으로 한다.
- 임의의 그라데이션을 적용하지 않는다.
- 상태 색상으로 로고를 변경하지 않는다.
- 비율을 변형하거나 회전하지 않는다.
- 작은 화면에서 워드마크가 Navigation과 경쟁하지 않도록 크기를 제한한다.
- 정확한 최소 크기, 여백과 단색 버전은 원본 로고 자산 확인 후 확정한다.

```text
공식 원본 파일: TBD
최소 크기: TBD
Clear Space: TBD
Monochrome Version: TBD
```

---

## 20. Motion

### 20.1 Tokens

| Token | Value | 용도 |
|---|---:|---|
| `motionFast` | 120ms | Pressed, 선택 상태 |
| `motionNormal` | 200ms | 상태 전환, 콘텐츠 갱신 |
| `easingStandard` | cubic-bezier(0.2, 0, 0, 1) | 기본 easing |

### 20.2 Allowed

- 버튼 pressed feedback
- 선택 상태 전환
- 로딩에서 콘텐츠로 전환
- 데이터 갱신 상태
- 기본 Navigation 전환

### 20.3 Prohibited

- 의미 없는 무한 애니메이션
- 장식용 레이더 회전
- 지속적인 pulse
- 정보 확인을 지연하는 큰 이동
- 모든 항목의 연속 등장 효과
- 과도한 bounce
- 사용자의 주의를 반복적으로 빼앗는 배경 motion

Reduce Motion 환경을 확인할 수 있는 경우 motion을 최소화한다.

---

## 21. Accessibility

### 21.1 Touch

- 모든 주요 터치 영역은 최소 44×44dp를 확보한다.
- 아이콘이 20dp여도 부모 Pressable은 최소 터치 영역을 제공한다.
- 인접한 터치 영역 사이에 충분한 간격을 둔다.

### 21.2 Text

- 일반 본문은 15sp를 기본으로 한다.
- 13sp는 메타데이터와 보조 Label에만 사용한다.
- 글자 확대 시 텍스트가 잘리지 않도록 고정 높이보다 `minHeight`를 사용한다.
- 중요한 정보는 한 줄 고정에 의존하지 않는다.

### 21.3 Color and State

- 일반 텍스트는 최소 4.5:1 대비를 목표로 한다.
- 큰 텍스트는 최소 3:1 대비를 목표로 한다.
- 상승·하락·선택·오류 상태를 색상만으로 구분하지 않는다.
- Disabled 상태를 opacity만으로 표현하지 않는다.

### 21.4 React Native Accessibility

필요한 위치에 다음 속성을 제공한다.

```text
accessibilityRole
accessibilityLabel
accessibilityHint
accessibilityState.selected
accessibilityState.disabled
accessibilityState.busy
```

장식 요소는 접근성 탐색에서 제외한다.

---

## 22. Implementation Mapping

이번 단계에서는 TypeScript 파일을 구현하지 않고 책임과 경로만 정의한다.

### 22.1 Design Tokens

```text
frontend/src/shared/constants/
├── colors.ts
├── spacing.ts
├── typography.ts
├── radius.ts
├── borders.ts
├── sizes.ts
├── motion.ts
└── index.ts
```

책임:

| 파일 | 책임 |
|---|---|
| `colors.ts` | Primitive·Semantic Color |
| `spacing.ts` | Primitive·Semantic Spacing |
| `typography.ts` | Text role |
| `radius.ts` | Radius token |
| `borders.ts` | Border width와 Divider |
| `sizes.ts` | Touch target, Control, Icon size |
| `motion.ts` | Duration과 easing |
| `index.ts` | 공통 export |

### 22.2 Shared Components

```text
frontend/src/shared/components/
```

Candidate 우선순위:

```text
1. ScreenContainer
2. PrimaryButton
3. SecondaryButton
4. Divider
5. LoadingView
6. ErrorView
7. EmptyView
8. IconButton
```

### 22.3 Feature Components

```text
frontend/src/features/{feature}/components/
```

다음 컴포넌트는 먼저 Feature 내부에서 검증한다.

```text
SelectionSurface
TrendListItem
TrendSignal
CategoryFilter
MetadataRow
```

두 개 이상의 feature에서 같은 의미와 상태를 가질 때만 `shared/components`로 이동한다.

---

## 23. Validation Plan

### 23.1 InterestSelectScreen

검증 대상:

- 360dp와 412dp 화면 너비
- `screenTitle`, `body`, `button` 계층
- `screenGutter`와 `sectionGap`
- 선택 가능한 Surface의 default·pressed·selected·disabled
- 색상 외 선택 표시
- PrimaryButton default·disabled·loading
- 최초 로딩
- 오류와 재시도
- 빈 카테고리
- 긴 카테고리명
- 글자 확대
- 하단 Action과 목록 겹침

검증 질문:

```text
1. 선택 항목이 일반 정보 카드와 명확히 구분되는가
2. 20dp gutter가 2열 또는 유동 배치에서 충분한가
3. radiusMedium 12dp가 과도하게 둥글지 않은가
4. brandPrimary와 textOnPrimary의 대비가 적절한가
5. 선택 상태가 색상 없이도 이해되는가
6. 로딩·오류·빈 상태가 같은 화면 체계를 유지하는가
```

### 23.2 RecommendedTrendsScreen

검증 대상:

- 화면 제목, 섹션 제목, 항목 제목의 위계
- 높은 정보 밀도
- 순위와 변화량 숫자
- 상승·하락·신규·변화 없음
- Signal highlight
- Divider 중심 목록
- 메타데이터
- 이미지가 있는 항목과 없는 항목
- 저장 Action
- 긴 한글 제목
- null 메타데이터
- 최초 로딩, Refresh, 오류, 빈 데이터

검증 질문:

```text
1. 모든 항목이 rounded card처럼 보이지 않는가
2. 순위와 변화량이 제목보다 과도하게 강조되지 않는가
3. signalYellow가 경고색으로 오해되지 않는가
4. 상태를 색상 외 표현으로 구분할 수 있는가
5. 이미지 유무와 관계없이 정보 계층이 유지되는가
6. 작은 화면에서 메타데이터가 지나치게 복잡하지 않은가
```

---

## 24. Candidate에서 Frozen으로 전환하는 조건

다음 조건을 모두 충족해야 한다.

```text
- InterestSelectScreen 적용 및 검증 완료
- RecommendedTrendsScreen 적용 및 검증 완료
- 360dp와 412dp 실기기 또는 Emulator 확인
- 주요 텍스트 대비 확인
- 선택·상승·하락·신규 상태의 비색상 표현 확인
- 브랜드 색상 팀 승인
- 아이콘 패밀리 결정
- 남아 있는 필수 TBD 제거
- 팀원 2인 검토
- 변경 영향 기록
```

조건을 충족하지 못하면 상태는 Candidate를 유지한다.

---

## 25. Open Decisions

| 결정 항목 | 현재 Candidate | 필요한 결정 | 영향 |
|---|---|---|---|
| 브랜드 Primary | `#8E9DFF` | 기존 Figma 색상 유지 여부 | 버튼·선택·Focus |
| 브랜드 Strong | `#3B4CA8` | 공식 로고 원본과 일치 여부 | Logo·Brand text |
| Active Indigo | `#1414BC` | Active icon에 계속 사용할지 | Navigation·Link |
| Signal Yellow | `#FFDD55` | 전역 신호 강조색 승인 | Trend signal |
| 시스템 폰트 | 사용 | 별도 한글 폰트 도입 여부 | 번들·Typography |
| 아이콘 패밀리 | TBD | 하나의 패밀리 선택 | 전체 Action |
| Dark Mode | Out of Scope | 이후 버전 도입 여부 | Color architecture |
| Logo 규정 | TBD | 원본·최소 크기·여백 | Header·Auth |

---

## 26. Change Policy

Design System을 변경할 때 다음 내용을 기록한다.

```text
- 변경 이유
- 변경된 Token 또는 Policy
- 기존 값
- 새로운 값
- 영향받는 화면
- 코드 수정 필요 여부
- 문서 버전
- 검증 결과
```

### 26.1 Token 추가 조건

다음 조건을 모두 검토한다.

```text
1. 여러 화면에서 반복되는가
2. 의미가 있는 공통 역할인가
3. 기존 Token 조합으로 해결할 수 없는가
4. 특정 화면 하나의 편의를 위한 값은 아닌가
```

### 26.2 Version

```text
0.1 → 최초 Candidate
0.2 → 대표 화면 검증 반영
0.x → Frozen 이전 Candidate 수정
1.0 → 팀 승인 및 Frozen
1.x → 기존 의미를 유지하는 추가·수정
2.0 → 기존 화면 마이그레이션이 필요한 구조 변경
```

---

## 27. Global Prohibitions

- 모든 콘텐츠를 흰색 rounded card로 구성하지 않는다.
- 모든 컴포넌트에 그림자를 사용하지 않는다.
- glassmorphism을 사용하지 않는다.
- 보라색·파란색 그라데이션을 기본 테마로 사용하지 않는다.
- 실제 데이터가 없는 가짜 차트를 만들지 않는다.
- 의미 없는 레이더, 파동, 점과 pulse를 사용하지 않는다.
- 이모지를 기능 아이콘으로 사용하지 않는다.
- 모든 텍스트를 굵게 처리하지 않는다.
- 모든 요소를 중앙 정렬하지 않는다.
- SNS 피드나 금융 대시보드를 그대로 복제하지 않는다.
- 설치되지 않은 폰트와 아이콘 라이브러리를 가정하지 않는다.
- 기존 화면의 하드코딩 값을 검토 없이 전역 토큰으로 승격하지 않는다.
- 화면별 API 필드와 비즈니스 정책을 이 문서에 추가하지 않는다.

---

## 28. Candidate v0.1 요약

```text
Art Direction:
Signal Editorial + Trend Radar

Platform:
React Native + Expo
Android 우선
Portrait
360~412dp
Light Mode

Layout:
4dp micro unit
8dp visual rhythm
20dp screen gutter
24dp top/bottom
32dp section gap

Brand:
Primary #8E9DFF
Strong #3B4CA8
Active #1414BC
Subtle #E4E8FF
Signal #FFDD55

Typography:
System font
Screen Title 26/34/700
Body 15/22/400
Button 16/22/700
Rank 28/34/700

Shape:
Radius 8 / 12 / Full
Border 1 / 2
Elevation 0 / 2

Accessibility:
44dp touch target
4.5:1 normal text contrast target
No color-only state

Validation:
InterestSelectScreen
RecommendedTrendsScreen
```
