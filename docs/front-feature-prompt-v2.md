아래의 확정된 Trend Leader 디자인 시스템과 프로젝트 구조를 기준으로 RecommendedTrends 화면을 React Native + TypeScript로 구현해주세요.

## 1. Source of Truth

다음 자료만 구현 기준으로 사용합니다.

### Design System Snapshot

[확정된 Design System Snapshot을 여기에 붙여넣습니다.]

### Screen Specification

[확정된 RecommendedTrendsScreen 명세를 여기에 붙여넣습니다.]

### API Response Contract

[확정된 맞춤 트렌드 API TypeScript 타입 또는 JSON 응답 예시를 여기에 붙여넣습니다.]

### Current Project Structure

[현재 frontend/src 폴더 구조를 여기에 붙여넣습니다.]

### Existing Related Code

[package.json, tsconfig.json, navigation type, apiClient, 공통 타입과 기존 컴포넌트를 붙여넣습니다.]

제공된 자료와 충돌하는 구조나 필드를 임의로 만들지 마세요.

## 2. 기술 조건

* Expo 기반 React Native
* TypeScript strict 기준
* StyleSheet.create() 사용
* 인라인 스타일 사용 금지
* 서버 응답 필드는 snake_case 유지
* React Native 기본 컴포넌트를 우선 사용
* 제공된 package.json에 없는 외부 라이브러리 사용 금지
* 새로운 라이브러리가 필요하면 코드에 추가하지 말고 마지막에 별도 제안으로만 기록
* 하드코딩된 색상, 간격, 폰트 크기, radius 사용 금지
* Safe Area 고려
* Android 우선 구현
* 화면 너비 360~412dp 대응

## 3. 책임 분리

다음 흐름을 유지합니다.

User
→ Screen
→ Hook
→ API Function 또는 Mock Data Source

* Screen은 화면 구성, 사용자 이벤트, Navigation만 담당
* Component는 재사용 가능한 UI만 담당
* Hook은 조회 상태와 새로고침 상태를 담당
* API Function은 서버 통신만 담당
* Type은 API 요청·응답과 Component props를 정의
* Component 내부에서 Navigation이나 API 호출 금지
* Screen에서 API Function 직접 호출 금지

현재 mock 단계에서도 Screen이 mock 데이터를 직접 import하지 않도록 합니다.

useRecommendedTrends Hook이 mock data source를 호출하도록 구성하고, 이후 실제 React Query API Hook으로 교체하기 쉽게 작성해주세요.

## 4. 화면 범위

RecommendedTrendsScreen에서는 다음만 구현합니다.

* 관심 카테고리 전환
* 대표 트렌드 1개
* 맞춤 트렌드 순위 목록
* 관심사 밖의 상승 트렌드 일부
* 트렌드 상세 이동 이벤트
* 북마크 입력 이벤트
* 로딩, 오류, 빈 데이터, 새로고침 상태

목록 화면에서 상세 AI 분석 영역은 구현하지 않습니다.

* trends.summary만 목록 요약으로 사용
* one_line_summary
* reason_text
* detail_text
* related_keywords

위 필드는 TrendDetailScreen의 책임이므로 임의로 추가하지 마세요.

## 5. 디자인 유지 조건

* 모든 항목을 rounded card로 만들지 않음
* 구분선, 여백, 타이포그래피 대비를 우선
* 대표 트렌드와 일반 목록의 레이아웃을 다르게 구성
* 순위 숫자와 변화량을 핵심 시각 요소로 사용
* 상승·하락·신규 상태는 색상, 아이콘, 부호를 함께 사용
* 그림자와 그라데이션 최소화
* 제공된 디자인 토큰 외의 값을 임의로 추가하지 않음
* 긴 한글 제목은 최대 두 줄과 말줄임 처리
* 모든 주요 Pressable은 최소 44×44dp 터치 영역 확보
* 아이콘 버튼에는 accessibilityRole과 accessibilityLabel 제공

## 6. 생성 파일

프로젝트의 실제 경로 구조에 맞춰 다음 파일을 생성해주세요.

* RecommendedTrendsScreen.tsx
* FeaturedTrend.tsx
* TrendRankingItem.tsx
* CategorySwitcher.tsx
* TrendSignalBadge.tsx
* useRecommendedTrends.ts
* recommendedTrendTypes.ts
* recommendedTrendMockData.ts
* colors.ts
* spacing.ts
* typography.ts
* radius.ts
* LoadingView.tsx
* ErrorView.tsx
* EmptyView.tsx

기존 프로젝트에 동일한 공통 토큰 또는 상태 컴포넌트가 있다면 새 파일을 중복 생성하지 말고 기존 파일을 재사용하세요.

## 7. 코드 작성 규칙

* 각 파일 경로를 먼저 표시한 후 전체 코드를 제공
* 생략 기호 사용 금지
* 의사 코드 사용 금지
* 누락된 import 금지
* 암시적 any 금지
* 사용하지 않는 import와 변수 금지
* props 타입 명시
* FlatList item 타입 명시
* 안정적인 keyExtractor 작성
* 긴 목록은 ScrollView의 map보다 FlatList 우선
* 이벤트 함수는 handle{대상}Press 형식 사용
* 타입 전용 import는 import type 사용
* path alias는 제공된 tsconfig 설정만 사용
* 존재하지 않는 경로와 파일을 임의로 가정하지 않음

## 8. 자체 검증

코드를 생성한 후 다음을 점검해주세요.

1. 모든 import 대상 파일이 실제 생성 목록 또는 기존 코드에 존재하는가
2. export와 import 이름이 일치하는가
3. TypeScript strict 환경에서 타입 오류 가능성이 없는가
4. 사용하지 않는 변수와 import가 없는가
5. Screen이 mock data나 API Function을 직접 호출하지 않는가
6. 컴포넌트 내부에 Navigation과 API 로직이 없는가
7. 디자인 토큰 외의 색상, 간격, 폰트 크기, radius가 하드코딩되지 않았는가
8. 설치되지 않은 패키지를 사용하지 않았는가
9. 긴 한글 제목과 null summary를 안전하게 처리하는가
10. 로딩, 오류, 빈 데이터, 새로고침 상태가 모두 연결되어 있는가

마지막에는 다음만 간단히 정리해주세요.

* 생성 또는 수정한 파일
* 기존 코드와 연결해야 하는 위치
* 실제 API 연동 시 교체할 부분
* 추가 의존성이 필요한지 여부
