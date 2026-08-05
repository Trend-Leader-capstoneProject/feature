앞서 확정한 Trend Leader 디자인 시스템을 기반으로 React Native + TypeScript 화면을 구현해주세요.

## 구현 조건

* Expo 기반 React Native를 사용한다.
* StyleSheet.create()를 사용한다.
* 인라인 스타일을 사용하지 않는다.
* 색상, 간격, 폰트 크기, radius는 공통 디자인 토큰으로 분리한다.
* Screen은 화면 구성과 사용자 이벤트만 담당한다.
* 재사용 UI는 별도 Component로 분리한다.
* Screen에서 API를 직접 호출하지 않는다.
* 현재 단계에서는 mock data를 사용하되 실제 API 응답 타입과 같은 구조로 작성한다.
* 서버 필드명은 snake_case를 유지한다.
* 로딩, 오류, 빈 데이터 상태를 고려한다.
* 컴포넌트 props 타입을 명시한다.
* 바로 프로젝트에 붙여넣을 수 있는 완성 코드로 작성한다.

## 디자인 유지 조건

* 모든 항목을 rounded card로 만들지 않는다.
* 구분선, 여백, 타이포그래피 대비를 우선한다.
* 대표 트렌드와 일반 트렌드의 레이아웃을 다르게 한다.
* 순위 숫자와 변화량을 핵심 시각 요소로 사용한다.
* AI 분석 영역은 일반 콘텐츠와 명확히 다른 시각 문법을 사용한다.
* 그림자와 그라데이션 사용을 최소화한다.
* 기존 디자인 토큰에 없는 색상과 간격을 임의로 추가하지 않는다.

## 생성 파일

* RecommendedTrendsScreen.tsx
* FeaturedTrend.tsx
* TrendRankingItem.tsx
* CategorySwitcher.tsx
* TrendSignalBadge.tsx
* trendTypes.ts
* trendMockData.ts
* colors.ts
* spacing.ts
* typography.ts

각 파일은 파일 경로를 먼저 표시한 후 전체 코드를 제공할 것.
생략 기호나 의사 코드를 사용하지 말아주세요.
