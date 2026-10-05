# Trend Leader 전체 트렌드 목록 화면 설계 확정안 v1.0.10

> 상태: 화면 설계 확정 / Phase 4-A~G 구현·자동 검증·실기기 Acceptance 완료 / TL-UI-001 RESOLVED
> 최초 확정일: 2026-10-02 (Asia/Seoul)
> 개정일: 2026-10-05 (Asia/Seoul)
> Repository: Trend-Leader-capstoneProject/feature
> 기준 브랜치: feat-trend-list
> v1.0 작성 시 확인 HEAD: 0650c7448483654df6f0e25990f3aaf344d09103
> v1.0.1 Phase 4-B 반영 확인 HEAD: 2ad5eaf044c1b64c6bc6839271aefcf835dd6640
> v1.0.2 Phase 4-C1 반영 확인 HEAD: 0479190d342453114bc3b0fd39250901ac362b81
> v1.0.3 Phase 4-C 완료 반영 확인 HEAD: ce043d0e511b22bb31bbd1be649462f05ad33c76
> v1.0.4 Phase 4-D1/D2 반영 확인 HEAD: db83e63ce7d7c80f9b18208d835266346c2c0586
> v1.0.5 Phase 4-D3 반영 확인 HEAD: 6b033f5b2d700f037293cf7ead1a40b8e14814f1
> v1.0.6 Phase 4-E1 반영 확인 HEAD: e06e0a4a36cab1182e1edfb8bc49f5a314568e88
> v1.0.7 Phase 4-E2 반영 확인 HEAD: 60a90bdfbc7f378ee9b8c5ba7375844673823dc5
> v1.0.8 Phase 4-E3 반영 확인 HEAD: 18d3f52a04a71f49f14532e065b4a0f62e6ab6ea
> v1.0.9 Phase 4-F 반영 확인 HEAD: 2b0fde695b56b9b38dd2e32ddc74e5bf6be3ad42
> v1.0.10 Phase 4-G·UI 확정 반영 확인 HEAD: 58feaa635575e633526a415ab17be96b30c286a5
> 상위 설계: `Trend_Leader_전체_트렌드_목록_조회_설계_확정안_v1.0.13.md`
> 대상 화면: `LatestTrendScreen` / 전체 최신 트렌드 목록

## 0. 문서 역할과 우선순위

이 문서는 전체 트렌드 목록 기능의 Phase 4 Frontend 구현에서 화면 표현, 상태, 상호작용을 고정하는 하위 설계 확정안이다.

API, Cursor, Category 의미, nullable, 공개 접근, Source 정책 등 기능 계약은 상위 `Trend Leader 전체 트렌드 목록 조회 설계 확정안 v1.0.13`을 따른다. 이 문서가 상위 기능 계약을 변경하지 않는다.

구현 우선순위는 다음과 같다.

1. 현재 채팅에서 명시적으로 확정한 결정
2. 이 화면 설계 확정안
3. 상위 전체 트렌드 목록 조회 설계 확정안
4. 프로젝트 개발 가이드라인
5. 과거 Figma 초안과 참고 이미지

과거 Figma 초안은 브랜드 분위기와 카드 중심 레이아웃의 참고자료로 사용한다. 현재 API 또는 기능 범위와 충돌하는 표현은 복원하지 않는다.

## 1. 화면 목적

화면 제목은 **`최신 트렌드`**로 확정한다.

사용자는 로그인 여부와 관계없이 다음을 수행할 수 있어야 한다.

- 최근 관측된 ACTIVE Trend를 최신순으로 탐색한다.
- 대분류 또는 세부분류 Category로 목록을 좁힌다.
- 무한 스크롤로 다음 Cursor 페이지를 조회한다.
- Trend에 연결된 Category와 최근 업데이트 시각을 확인한다.
- 최신 Source가 있으면 원문을 외부에서 연다.

이 화면은 인기 순위 화면이 아니다. 실제 Rank, 점수, 순위 변동, 사용자 주목도 의미를 부여하지 않는다.

권장 상단 설명 문구:

> 최근 업데이트된 다양한 트렌드를 확인해 보세요.

문구는 표현 수정이 가능하지만 `인기`, `순위`, `전체 사용자가 주목한`처럼 현재 데이터가 보장하지 않는 의미를 추가하지 않는다.

## 2. 포함·제외 범위

### 2.1 이번 화면에 포함

- Header와 T&L 브랜드 영역
- 화면 제목과 설명
- 대분류 1열 Category Filter
- 선택 대분류의 세부분류 2열 Category Filter
- 최신 Trend 무한 목록
- 화면 표시 순번
- nullable Thumbnail / Summary
- 전체 Category 표시
- 최근 업데이트 시각
- Latest Source 표시와 원문 열기
- Initial Loading / Empty / Initial Error
- Pull-to-refresh
- Next Page Loading / Next Page Error / Retry
- 비로그인·로그인 양쪽 Navigation 진입

### 2.2 이번 화면에서 제외

- 실제 Rank / Rank Delta / Score
- 빨간 ▲ / 파란 ▼ 순위 변동 표현
- `인기 이슈`, `내 관심사 급상승` 등 실제 데이터가 없는 평가 표현
- `오늘`, `어제`, `이번 주` 날짜 범위 Dropdown
- AI 분석 화면 이동
- Trend 상세 화면 이동
- Bookmark
- Search
- 전체 Bottom Tab Navigation
- 동작하지 않는 메뉴 버튼
- Category Chip을 눌러 즉시 Filter하는 기능
- 맞춤 추천 전용 UI

후속 기능이 구현되면 별도 설계 변경으로 추가한다.

## 3. 전체 화면 정보 구조

기본 구조는 다음과 같다.

```text
LatestTrendScreen

├─ Header
│  ├─ Future Menu Slot
│  └─ T&L Logo
│
├─ Intro
│  ├─ "최신 트렌드"
│  └─ 설명 문구
│
├─ Category Filter
│  ├─ Root Category Row
│  └─ Child Category Row (조건부)
│
├─ Trend Infinite List
│  └─ TrendCard *
│
└─ 상태 UI
   ├─ Initial Loading
   ├─ Empty
   ├─ Initial Error
   ├─ Pull-to-refresh
   ├─ Next Page Loading
   └─ Next Page Error / Retry
```

하단 Bottom Tab은 이번 Phase에서 화면 구조에 포함하지 않는다.

## 4. Header

### 4.1 T&L 브랜드

기존 Figma의 중앙 T&L 브랜드 방향을 유지한다.

Header는 화면 콘텐츠와 시각적으로 구분되되, 과도한 높이를 사용해 첫 화면의 Trend 노출량을 줄이지 않는다.

### 4.2 Future Menu Slot

좌측에는 미래 메뉴 기능을 위한 자리만 확보한다.

현재 메뉴 기능이 구현되지 않았으므로 Phase 4에서는 다음을 금지한다.

- 눌러도 아무 동작이 없는 `⋮`, `☰` Pressable 노출
- 임시 Alert만 띄우는 메뉴
- 구현되지 않은 메뉴 항목

레이아웃 정렬을 위한 좌측 슬롯은 유지할 수 있다. 실제 메뉴 기능이 도입되면 아이콘 종류와 메뉴 구조를 별도 확정한다.

## 5. Category Filter

Category Filter는 **대분류 1열 + 선택 시 세부분류 2열** 구조로 확정한다.

### 5.1 대분류 1열

항상 표시한다.

예시:

```text
[전체] [패션] [뷰티] [게임] [음식] [엔터테인먼트] [IT/디지털]
```

- 가로 스크롤을 사용한다.
- Chip 폭은 텍스트 길이에 맞춘다.
- 긴 이름을 고정 폭으로 잘라내지 않는다.
- `전체` 선택 시 `category_id`를 API에 보내지 않는다.
- 실제 대분류 ID는 `GET /api/categories` 응답을 사용하며 하드코딩하지 않는다.

### 5.2 세부분류 2열

대분류가 선택된 경우에만 표시한다.

예: 게임 선택

```text
[게임 전체] [모바일 게임] [PC 게임] [콘솔 게임]
[e스포츠] [게임 플랫폼·서비스] [기타]
```

- 첫 Chip은 `{대분류명} 전체` 의미다.
- `{대분류명} 전체`는 선택한 대분류 ID로 `GET /api/trends?category_id=<root_id>`를 호출한다.
- 나머지 Chip은 해당 세부분류 ID를 사용한다.
- 세부분류 역시 가로 스크롤을 사용한다.

### 5.3 필터 상태 전환

- 초기 상태는 `전체`다.
- 대분류 선택 시 해당 대분류의 `전체`가 기본 필터가 된다.
- 세부분류 선택 시 해당 세부분류 ID로 조회한다.
- 다른 대분류를 선택하면 이전 세부분류 선택은 폐기한다.
- `전체`로 돌아오면 2열은 숨긴다.
- 필터 변경 시 이전 Cursor를 재사용하지 않는다.
- 새 필터의 첫 페이지부터 조회한다.
- 화면 표시 순번은 `#1`부터 다시 시작한다.
- 느린 이전 Filter 응답이 새 Filter 결과를 덮어쓰지 않도록 Query 책임에서 방어한다.

## 6. Trend Infinite List

목록 정렬은 Backend가 보장하는 다음 순서를 그대로 사용한다.

```text
last_collected_at DESC
→ trend_id DESC
```

Frontend가 임의로 인기순, 이름순 또는 다른 정렬을 다시 적용하지 않는다.

기본 동작:

```text
첫 진입
→ 첫 20개

목록 끝 접근
→ has_next=true + next_cursor 존재 시 다음 요청

다음 페이지
→ 기존 목록 뒤에 누적

has_next=false
→ 추가 요청 중단
```

Demo 기준 Acceptance는 20 → 5 → 종료다.

중복 페이지 요청을 방지하고, 다음 페이지 요청 중 동일 Cursor를 중복 호출하지 않는다.

## 7. 화면 표시 순번

표시 번호는 API Rank가 아니라 **현재 화면의 누적 배열 index + 1**이다.

표현은 작은 보조 텍스트 `#1`, `#2`, ... 형태를 기본으로 한다.

```text
1페이지: #1 ~ #20
2페이지 누적: #21 ~ #25
```

다음 표현은 사용하지 않는다.

- 1위 / 2위 / 3위
- 상승 / 하락
- ▲ / ▼
- Rank Delta

Pull-to-refresh 또는 Filter 변경으로 첫 페이지부터 다시 조회하면 `#1`부터 다시 계산한다.

## 8. TrendCard 정보 구조

TrendCard의 논리적 정보 우선순위는 다음과 같다.

```text
# 표시 순번
Thumbnail (optional)
Title
Summary (optional)
Category Chips
최근 업데이트 시각
Latest Source
원문 보기
```

구체적인 배치는 실제 모바일 폭 Prototype에서 조정할 수 있지만 위 정보 의미와 우선순위는 유지한다.

### 8.1 Title

- Trend 제목을 Card의 핵심 정보로 강조한다.
- 지나치게 긴 제목은 화면을 무한히 늘리지 않도록 합리적인 line limit을 둔다.
- 정확한 line 수는 실제 Prototype에서 결정할 수 있다.

### 8.2 Summary

- 존재하면 Title 아래에 표시한다.
- `summary=null`이면 영역 자체를 제거한다.
- 빈 Placeholder를 강제로 만들지 않는다.
- 표시 시 2~3줄 수준을 기본 방향으로 한다.

### 8.3 Thumbnail

Thumbnail의 정확한 배치는 **Phase 4 Prototype 확인 후 확정**한다.

현재 후보:

1. Card 오른쪽 소형 이미지
2. Card 상단 Wide 이미지

이 결정은 현재 유일한 주요 시각 배치 OPEN 항목이다.

다만 다음 원칙은 확정한다.

- `thumbnail_url=null`이면 이미지 영역 자체를 제거한다.
- 이미지 실패 시에도 레이아웃을 깨뜨리는 빈 큰 영역을 남기지 않는다.
- Thumbnail 유무가 Trend 데이터 의미나 목록 정렬을 바꾸지 않는다.

### 8.4 Card 전체 터치

현재 Trend 상세 화면이 범위 밖이므로 Card 전체에는 상세 이동 `onPress`를 제공하지 않는다.

동작하지 않는 Card press feedback도 제공하지 않는다.

상세 기능이 구현되면 별도 계약으로 추가한다.

## 9. Trend Category Chips

Card에는 서버가 반환한 `categories[]` 전체를 보존한다.

UI에서는 화면 폭상 2~3개 정도가 자연스럽게 보이도록 하고, 나머지는 가로 스와이프로 확인한다.

표시 문맥은 다음 형태를 기본으로 한다.

```text
게임 · PC 게임
IT/디지털 · PC·하드웨어
음식 · 기타
```

세부분류 이름만 표시하지 않고 부모 대분류 문맥을 함께 제공한다. 특히 여러 부모 아래 동일 이름 `기타`가 존재하므로 부모 문맥을 생략하지 않는다.

Category Chips의 순서는 Backend 응답 순서를 따른다.

이번 Phase에서 Card 내부 Category Chip은 표시 전용이다. Chip을 누르면 즉시 필터가 바뀌는 동작은 추가하지 않는다.

## 10. 최근 업데이트 시각

API의 `last_collected_at`은 UTC-aware ISO 8601 `Z` 값이다.

Frontend는 필요 시 사용자 Local Time으로 변환해 표시한다.

예시:

```text
최근 업데이트 10월 1일 18:00
```

정확한 표현 formatter는 pure function으로 분리하는 방향을 권장한다.

화면 전체에 특정 날짜를 크게 표시하거나 `오늘 ▼` Dropdown을 두어 목록이 날짜 Snapshot인 것처럼 표현하지 않는다.

## 11. Latest Source와 원문 열기

### 11.1 latest_source 존재

Card 하단에 Source 영역을 제공한다.

예:

```text
YouTube
출처 제목
[원문 보기 ↗]
```

- Platform과 Source Title을 구분해 표시할 수 있다.
- `원문 보기`는 `latest_source.source_url`을 OS 외부 Browser 또는 지원 앱으로 연다.
- 외부 URL 열기 실패는 사용자에게 안내한다.
- Card 전체 press와 Source 원문 press를 혼합하지 않는다.

### 11.2 source_title=null

Platform과 `원문 보기`만 표시 가능하다.

```text
YouTube
[원문 보기 ↗]
```

### 11.3 latest_source=null

```text
출처 정보가 없습니다.
```

정도의 비상호작용 안내만 제공하고 `원문 보기` 버튼을 만들지 않는다.

Demo 정상 데이터에 Source가 모두 있어도 API 계약은 nullable을 유지한다.

## 12. Nullable과 실패 Fallback

| 데이터 | 정상 표시 | null/실패 시 |
| --- | --- | --- |
| summary | 2~3줄 요약 | 영역 제거 |
| thumbnail_url | Prototype 확정 배치 | 이미지 영역 제거 |
| source_title | Source 제목 | 제목만 생략 |
| latest_source | Platform/제목/원문 | 출처 없음 안내, 버튼 제거 |
| categories | Horizontal Chips | 빈 경우 Chips 영역 제거 |

nullable 데이터 때문에 Card 전체가 오류 상태가 되어서는 안 된다.

## 13. 화면 상태

기존 공통 `LoadingView`, `ErrorView`, `EmptyView`, `ScreenContainer`를 우선 재사용한다.

### 13.1 Initial Loading

목록 데이터가 아직 없고 첫 요청이 진행 중일 때:

> 최신 트렌드를 불러오고 있습니다.

### 13.2 Empty

전체 필터:

> 표시할 트렌드가 없습니다.

Category 필터 중:

> 이 분야에 표시할 트렌드가 없습니다.

필터 UI는 유지하여 사용자가 다른 Category로 이동할 수 있어야 한다.

### 13.3 Initial Error

기존 목록 데이터가 없는 첫 요청 실패:

> 최신 트렌드를 불러오지 못했습니다.

`다시 시도`를 제공한다.

### 13.4 Next Page Loading

기존 목록을 유지한 채 리스트 하단에서 작은 Loading 상태를 표시한다.

전체 화면 Loading으로 기존 20개를 가리지 않는다.

### 13.5 Next Page Error

기존 목록을 유지한다.

리스트 하단에 다음 페이지 실패와 Retry를 제공한다.

> 다음 트렌드를 불러오지 못했습니다.

첫 페이지 오류와 다음 페이지 오류를 같은 전체 Error 화면으로 처리하지 않는다.

### 13.6 Pull-to-refresh

현재 선택 Category 기준 첫 페이지를 다시 조회한다.

새 조회는 현재 서버의 최신 목록을 반영한다. live-feed 특성상 기존 Scroll 세션과 동일 Snapshot을 보장하지 않는다.

## 14. Query와 Cache 경계

TanStack Query의 실제 설치 버전과 동작을 기준으로 구현한다.

Query Key에는 최소한 현재 Category 문맥이 반영되어야 한다.

필터 변경 시 다른 Category Cache와 Cursor가 섞이지 않아야 한다.

다음 세부 정책은 상위 문서의 기존 OPEN 항목을 이어받는다.

### TL-FE-001 — Query 재시작 / Cache 재사용

- 상태: **RESOLVED (Phase 4-B)**
- Query Key는 Category와 limit 문맥을 포함하고 Cursor는 Infinite Query `pageParam`으로 관리한다.
- 방문했던 Filter로 돌아오면 기존 Cache를 즉시 재사용할 수 있으며, `staleTime: 0`과 `refetchOnMount: true`로 stale 상태를 background revalidation한다.
- `restart()`는 현재 Infinite Cache를 첫 페이지 하나로 축소한 뒤 refetch하여 기존 후속 Page/Cursor를 폐기하고 Cursor 없는 첫 페이지부터 새 탐색을 시작한다.
- Category 전환 전의 느린 응답은 서로 다른 Query Key에 격리되어 현재 Filter 결과를 덮지 않는다.
- 사용자 로컬 환경에서 `useTrends` 최종 5 tests와 `npm run typecheck` 통과로 검증했다.
- 화면 재진입·Pull-to-refresh의 실제 사용감과 네트워크 복구는 실기기 Acceptance에서 다시 확인하되 Query/Cache 계약 자체는 재설계하지 않는다.

## 15. Navigation

같은 `LatestTrendScreen`을 로그인 여부에 관계없이 재사용한다.

목표 구조:

```text
AuthNavigator
├─ Login
├─ Signup
└─ LatestTrend

AppNavigator
├─ Main
├─ InterestEdit
└─ LatestTrend
```

### 15.1 비로그인

Login 화면에서 Public 최신 트렌드로 진입할 수 있는 명확한 Entry를 제공한다.

예:

> 최신 트렌드 둘러보기

새 GUEST Auth State를 만들지 않는다.

### 15.2 로그인

현재 Main에서 최신 트렌드 화면으로 진입할 수 있는 Entry를 제공한다.

### 15.3 Screen 결합도

`LatestTrendScreen`은 특정 Stack 전용 props에 강하게 결합하지 않는다.

Public API는 `publicApiClient`를 사용하며 Trend 목록 오류가 인증 세션을 로그아웃시키지 않는다.

## 16. Bottom Navigation과 후속 기능

기존 Figma의 다음 Bottom Navigation은 장기 방향 참고로 보존할 수 있다.

```text
내 트렌드
최신 이슈
저장
검색
```

그러나 Phase 4에서는 구현하지 않는다.

맞춤 추천, 저장, 검색 기능이 실제로 준비된 뒤 Tab Navigator 도입 시점에 별도 설계한다.

현재 화면 구현을 위해 미래 Tab 구조를 가정해 Navigation을 과도하게 추상화하지 않는다.

## 17. 맞춤 추천 화면과 재사용

맞춤 추천 화면은 후순위다.

향후 구조는 다음처럼 Trend Feature Component를 재사용할 수 있어야 한다.

```text
LatestTrendScreen
└─ TrendCard

RecommendedTrendScreen
└─ TrendCard
```

다만 아직 존재하지 않는 추천 API를 가정해 추상화를 과도하게 만들지 않는다.

`TrendCard`는 전체 목록 Screen 내부 전용이 아니라 `features/trend/components` 수준의 Feature Component로 두는 방향을 권장한다.

## 18. Phase 4 권장 Frontend 구조

구현 시작 시 현재 Repository를 다시 확인하고 필요 최소 파일만 추가한다.

권장 구조:

```text
frontend/src/features/trend/
├─ api/
│  └─ getTrends.ts
├─ components/
│  ├─ TrendCard.tsx
│  ├─ TrendCategoryFilter.tsx
│  ├─ TrendCategoryChips.tsx
│  └─ TrendSourceSection.tsx
├─ hooks/
│  └─ useTrends.ts
├─ screens/
│  └─ LatestTrendScreen.tsx
├─ types/
│  └─ trend.ts
└─ queryKeys.ts
```

실제 구현 중 하나의 작은 Component가 독립 파일을 필요로 하지 않으면 억지로 분리하지 않는다.

Screen은 API를 직접 호출하지 않는다.

```text
Screen
→ Hook
→ API Function
→ publicApiClient
```

구조를 유지한다.

## 19. 시각·접근성 원칙

- 기존 프로젝트의 colors, spacing, typography, radius, elevation Token을 우선 재사용한다.
- 과거 Figma 색상을 새 하드코딩 값으로 그대로 복제하지 않는다.
- 텍스트 대비와 터치 Target을 실제 기기에서 확인한다.
- Horizontal Scroll과 Vertical List가 함께 있을 때 제스처 충돌을 실기기에서 검증한다.
- Chip은 긴 텍스트를 불필요하게 잘라내지 않는다.
- 정보 의미를 색상 하나에만 의존하지 않는다.
- Pressable이 아닌 요소에 버튼처럼 보이는 affordance를 주지 않는다.
- 원문 보기에는 의미 있는 accessibility label을 제공한다.
- Loading / Error / Empty 상태를 색상 차이만으로 구분하지 않는다.

## 20. Figma 초안에서 유지·변경하는 요소

### 20.1 유지

- T&L 브랜드 방향
- 파란 계열 브랜드 분위기
- 카드 중심 목록
- Horizontal Category
- 명확한 화면 제목과 Section 구분

### 20.2 제거·후순위

- `전체 사용자가 주목한 이슈`
- `🔥 인기 이슈`
- `내 관심사 급상승`
- ▲ / ▼
- `오늘` Dropdown
- 화면 상단의 고정 날짜
- `클릭 시 AI 분석을 볼 수 있어요!`
- AI 상세 이동
- Bookmark / Search
- 전체 Bottom Tab
- 기능 없는 Header Menu Button

이 변경은 Figma 초안의 시각 방향을 폐기하는 것이 아니라 현재 구현 가능한 계약과 사용자 기대를 일치시키기 위한 것이다.

## 21. Phase 4 구현 순서

Delivery Mode에서 다음 순서를 권장한다.

| 단계 | 산출·검증 |
| --- | --- |
| 4-A | **완료** — Trend Type, API Function, Query Key 구현 및 typecheck 통과 |
| 4-B | **완료** — Infinite Query Hook, Cursor/Filter/Cache 핵심 테스트 5 passed, TL-FE-001 RESOLVED, typecheck 통과 |
| 4-C | **완료** — 4-C1 Category Filter 5 tests + 4-C2 Initial Loading/전체·Filtered Empty/Initial Error+Retry 4 tests + typecheck 통과. Next Page Loading/Error 및 Pull-to-refresh는 4-E 범위 유지 |
| 4-D | **완료**. TrendCard 기본 정보/표시 순번/nullable summary/Category Chips, Latest Source nullable/source_title nullable, 원문 callback, 외부 URL 성공·실패 안내, Thumbnail 존재/null/error 제거를 구현. TrendCard 11 tests + URL helper 2 tests + typecheck 통과. Phase 4-G 실기기 검증 후 오른쪽 96×96 Thumbnail을 최종 확정 |
| 4-E | **완료**. LatestTrendScreen 기본 통합, `onEndReached` pagination, Category+Cursor 중복 요청 lock, hasNextPage=false 중단, 기존 목록 유지형 Next Loading/Error Footer와 Retry, 현재 Category 유지 Pull-to-refresh + `restart()` + Refresh indicator까지 구현. LatestTrendScreen 누적 11 tests + typecheck 통과 |
| 4-F | **완료** — AuthNavigator/AppNavigator 양쪽에 동일 `LatestTrendScreen`을 `LatestTrend`로 등록. Login `최신 트렌드 둘러보기`, Main `최신 트렌드 보기` Entry 연결, 별도 GUEST 상태 없음. Navigation Entry 2 tests, 관련 회귀 35 tests + typecheck 통과 |
| 4-G | **완료** — 실제 Demo 25개로 비로그인/로그인 진입, 20→5 Pagination, Filter, Pull-to-refresh, External URL, Gesture, nullable/장문 Card, Local Time, 비-Rank 순번, Public API 장애 시 인증 유지/복구를 실기기 검증. Thumbnail 96×96와 Trend Leader Logo 배치 확정 |

Thumbnail 배치는 Phase 4-G 실제 모바일 화면에서 오른쪽 96×96 소형 이미지로 확정했다. 추후 팀 UI 피드백으로 크기·위치 변경 요청이 발생하면 TL-UI-001을 다시 열어 재검토한다.

## 22. 화면 Acceptance 기준

Phase 4 완료 전 최소 확인 항목:

- [x] 화면 제목이 `최신 트렌드`로 표시됨
- [x] 비로그인/로그인 양쪽에서 동일 Public 목록 접근 가능 — 4-G-1/2 실기기
- [x] 대분류 1열이 가로 스크롤됨
- [x] 대분류 선택 시 해당 세부분류 2열이 표시됨
- [x] `전체` 복귀 시 2열이 사라짐
- [x] 필터 변경 시 새 첫 페이지와 `#1`부터 시작
- [x] Demo 25개가 20 → 5로 누적되고 추가 요청이 중단됨 — 4-G-3
- [x] 화면 순번이 Rank처럼 표현되지 않음 — 4-G-9
- [x] summary/thumbnail/source_title/latest_source nullable에서 화면이 깨지지 않음 — summary/thumbnail 실기기, Source nullable 자동 테스트
- [x] Category 전체를 가로 스와이프로 확인 가능
- [x] 부모+자식 Category 문맥이 식별 가능
- [x] API UTC `Z`를 사용자 Local Time으로 표시 — 4-G-9
- [x] Latest Source 원문 열기 성공 — 4-G-6
- [x] Source 없음에서 원문 버튼 미노출 — 자동 테스트
- [x] URL 열기 실패 안내 — URL helper 자동 테스트
- [x] Initial Loading/Empty/Error 정상 — 자동 테스트
- [x] Next Page Loading/Error가 기존 목록을 제거하지 않음 — 자동 테스트
- [x] Pull-to-refresh 정상 — 4-G-5
- [x] Horizontal Category/Chip Scroll과 Vertical List 제스처 충돌 없음 — 4-G-7
- [x] Public API 오류가 인증 상태를 종료하지 않음 — 4-G-10, Backend 중지/복구 실기기 확인
- [x] 기존 Login/Signup/Main/InterestEdit 흐름 회귀 없음 — Frontend 전체 17 suites / 92 tests
- [x] 실제 기기에서 주요 폭/폰트/터치 영역 확인
- [x] Thumbnail 배치 OPEN 항목 해소 — TL-UI-001 RESOLVED, 오른쪽 96×96
- [x] TL-FE-001 Query 재시작/Cache 정책 해소
- [x] Header Brand를 실제 Trend Leader Logo asset으로 표시 — 44×44 중앙 배치 실기기 확정

## 23. 미확정 및 해결 항목

### TL-UI-001 — Thumbnail 배치

- 상태: **RESOLVED (Phase 4-G, 2026-10-05)**
- 최종 결정: Card 오른쪽 **96×96** 소형 이미지 배치를 유지한다.
- 실제 Demo 25개를 모바일 화면에서 연속 스크롤하며 Title/Summary 가독성, 목록 정보 밀도, Card 높이와 이미지 비율을 확인했다.
- summary가 없거나 thumbnail이 null/실패인 경우에도 기존 자동 테스트와 실기기 화면에서 레이아웃 안정성을 확인했다.
- 추후 팀 UI 피드백으로 크기·위치 변경 요청이 생기면 이 항목을 다시 OPEN하고 실제 화면 기준으로 재검토한다.

### UI-POLISH-001 — Instagram-like Pull-to-refresh Indicator

- 상태: **BACKLOG / NON-BLOCKING**
- 현재 기본 React Native Pull-to-refresh는 기능·자동 테스트·실기기 Acceptance를 통과했다.
- Instagram처럼 상단 중앙 원형 indicator의 시각 표현을 커스텀하는 것은 후속 UI Polish 후보로 남긴다.
- 이 작업은 현재 목록 기능 완료를 막지 않으며, 적용 시 Android/iOS 제스처와 Refresh 상태 테스트를 다시 확인한다.

### TL-FE-001 — Query 재시작 / Cache 재사용

- 상태: **RESOLVED (Phase 4-B)**
- §14의 확정 정책을 따른다.
- 구현·검증 기준 HEAD: `2ad5eaf044c1b64c6bc6839271aefcf835dd6640`.
- 최종 자동 검증: `useTrends` 5 tests passed, `npm run typecheck` passed.

Header Menu는 기능 자체를 이번 범위에서 구현하지 않는 것으로 확정했으므로 미확정 항목으로 두지 않는다. Phase 4에서는 자리만 확보하며 기능 도입 시 별도 설계한다.

## 24. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-10-02 | Phase 4 Frontend 화면 설계 동결. 화면 제목 `최신 트렌드`, 대분류 1열+세부분류 2열 Filter, Future Menu Slot, Card/Source/Nullable/상태/Navigation 기준 확정. 실제 Rank·날짜 Dropdown·AI 상세·Bottom Tab 등 미구현 의미 제거. Thumbnail 배치와 Query 재시작 정책은 Phase 4에서 해소할 OPEN 항목으로 분리 |
| v1.0.1 | 2026-10-02 | Phase 4-A/B 결과 반영. Trend Type/API/Query Key 및 `useTrends()` Infinite Query 구현·자동 검증을 기록하고 TL-FE-001을 RESOLVED로 갱신. 방문 Filter Cache 즉시 재사용 + stale background revalidation, restart 첫 페이지 재시작, 느린 이전 Filter 응답 격리를 확정. `useTrends` 5 tests와 typecheck 통과. TL-UI-001 Thumbnail 배치는 OPEN 유지 |
| v1.0.2 | 2026-10-03 | Phase 4-C1 Category Filter 결과 반영. `TrendCategoryFilter`에 대분류 1열 + 선택 대분류 세부분류 2열 Horizontal Chip을 구현하고 전체/Root/Child 선택, Root 변경 시 이전 Child 제거, 전체 복귀 시 2열 숨김을 5 tests + typecheck로 검증. 확정안상 4-C의 상태 UI는 미완료로 유지. TL-UI-001 Thumbnail 배치는 OPEN 유지 |
| v1.0.3 | 2026-10-03 | Phase 4-C2 초기 상태 UI 결과 반영. `TrendListFeedback`으로 공통 Loading/Empty/Error View를 조립하여 Initial Loading, 전체/Filtered Empty, Initial Error + Retry를 4 tests + typecheck로 검증. Phase 4-C 전체 완료. Next Page/Pull-to-refresh는 4-E로 유지하고 TL-UI-001 Thumbnail 배치는 OPEN 유지 |
| v1.0.4 | 2026-10-03 | Phase 4-D1/D2 결과 반영. TrendCard 기본 정보/표시 순번/nullable summary/Category 문맥/최근 업데이트와 Latest Source nullable/source_title nullable/원문 callback을 구현하고, 외부 URL helper의 `Linking.openURL` 성공 및 실패 Alert를 자동 검증. TrendCard 8 tests + URL helper 2 tests + typecheck 통과. 실제 Screen 연결·실기기 링크 검증은 후속 단계이며 TL-UI-001 Thumbnail 배치는 OPEN 유지 |
| v1.0.5 | 2026-10-04 | Phase 4-D3 결과 반영. 오른쪽 96×96 Thumbnail Prototype을 구현하고 `thumbnail_url` 존재/null/로딩 실패 시 제거를 TrendCard 누적 11 tests + typecheck로 검증. 실제 LatestTrendScreen 모바일 폭 확인 전까지 TL-UI-001 최종 배치는 OPEN 유지 |
| v1.0.6 | 2026-10-05 | Phase 4-E1 결과 반영. LatestTrendScreen에서 Screen Shell/Intro/Category Filter/Infinite pages flatten/연속 displayNumber/TrendCard/Source callback과 Initial Loading/Error/전체·Filtered Empty를 통합. Cache가 있는 background 오류는 기존 목록 유지. 5 tests + typecheck 통과. Pagination/Next Page/Pull-to-refresh 및 TL-UI-001 실화면 확정은 후속 단계 유지 |
| v1.0.7 | 2026-10-05 | Phase 4-E2 결과 반영. `onEndReached` pagination, hasNextPage=false 중단, Category+Cursor request lock으로 동일 Cursor 중복 호출 방지, 기존 목록 유지형 Next Loading/Error Footer와 명시적 Retry를 구현. LatestTrendScreen 누적 9 tests 통과. RNTL 14.x async `fireEvent()`는 await하도록 정리. Pull-to-refresh와 TL-UI-001 실화면 확정은 후속 단계 유지 |
| v1.0.8 | 2026-10-05 | Phase 4-E3 결과 반영. 현재 Category 유지 Pull-to-refresh, `restart()` 호출, 기존 Card 유지, Refresh indicator 전환을 구현. LatestTrendScreen 누적 11 tests + typecheck 통과로 Phase 4-E 자동 검증 완료. Navigation과 TL-UI-001 실화면 확정은 후속 단계 유지 |
| v1.0.9 | 2026-10-05 | Phase 4-F 결과 반영. 동일 LatestTrendScreen을 Auth/App Stack 양쪽에 연결하고 Login Public Entry/Main 로그인 Entry를 추가. 별도 GUEST Auth State 없음. Navigation Entry 2 tests, Signup/InterestEdit/LatestTrendScreen 포함 관련 회귀 35 tests + typecheck 통과. 첫 Login 렌더 cold-start 편차 대응으로 Entry 테스트에 20초 timeout 상한 적용. 실기기 Navigation/20→5/Filter/External URL/TL-UI-001 확정은 4-G 유지 |
| v1.0.10 | 2026-10-05 | Phase 4-G 최종 결과 반영. 실기기 4-G-1~10을 완료하고 TL-UI-001을 오른쪽 96×96 Thumbnail로 RESOLVED. `T&L` 텍스트를 기존 Trend Leader Logo asset 44×44 중앙 배치로 교체·실기기 확정. Frontend 전체 17 suites / 92 tests + typecheck 통과. Instagram-like Pull-to-refresh indicator는 NON-BLOCKING UI Polish Backlog로 기록 |

