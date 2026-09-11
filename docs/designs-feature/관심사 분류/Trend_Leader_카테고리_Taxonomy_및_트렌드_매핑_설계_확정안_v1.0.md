# Trend Leader 카테고리 Taxonomy 및 트렌드 매핑 설계 확정안 v1.0

- 프로젝트: Trend Leader
- 기준 Repository: `Trend-Leader-capstoneProject/feature`
- 기준 브랜치: `dev`
- 기준일: 2026-09-09
- 상태: 설계 확정
- 범위: Category Taxonomy, Category Master Seed v1.0, 관심 대분류와 세부분류의 역할, Trend-Category Mapping, 맞춤 추천의 Category Matching, AI Hashtag 경계
- 별도 설계 보류: Trend Attribute, 실제 Source Hashtag 저장 구조, 대표 Category Use Case

---

## 1. 문서 목적

이 문서는 Trend Leader에서 `categories`, `user_interest_categories`, `trend_category_map`이 각각 어떤 의미를 가지는지 명확히 하고, 계층형 Category Taxonomy와 맞춤 Trend 추천이 일관된 규칙으로 동작하도록 설계를 확정한다.

핵심 문제는 다음과 같다.

- 사용자의 관심사는 6개 대분류 중심인데 Trend는 더 구체적인 세부분류가 필요하다.
- 하나의 Trend가 여러 주제에 걸칠 수 있다.
- `category_name` 전역 UNIQUE는 `음식 > 기타`, `게임 > 기타`처럼 자연스러운 계층형 분류를 방해한다.
- `업데이트`, `신제품`, `밈`, `이벤트`처럼 현상의 성격과 주제 Category가 혼합될 위험이 있다.
- 기존 맞춤 Trend 명세는 사용자 관심 Category ID와 Trend Category ID의 직접 매칭을 전제로 하고 있어, 대분류 관심사와 세부분류 Trend의 관계를 명시적으로 보완해야 한다.
- Category Master Seed의 초기 기준과 이후 운영 변경 정책을 명확히 할 필요가 있다.

---

## 2. Category 역할

Category는 **`무슨 주제 영역인가`**만 표현한다.

예:

```text
게임
├─ 모바일 게임
├─ PC 게임
├─ 콘솔 게임
├─ e스포츠
├─ 게임 플랫폼·서비스
└─ 기타
```

다음과 같은 값은 Category에 넣지 않는다.

```text
신제품
업데이트
이벤트
밈
논란
콜라보
출시
```

위 값들은 주제가 아니라 Trend의 현상/상태/유형을 설명하는 후보이므로 `Trend Attribute` 별도 설계 대상으로 보류한다.

---

## 3. 계층 구조

Category는 2단계까지만 사용한다.

```text
parent_id IS NULL
→ 대분류

parent_id IS NOT NULL
→ 세부분류
```

3단계 이상의 Category는 MVP에서 허용하지 않는다.

대분류는 사용자 관심 선택의 단위이고, 세부분류는 Trend를 더 구체적으로 분류하기 위한 단위다.

---

## 4. 대분류

MVP의 대분류는 다음 6개를 유지한다.

| category_code | category_name | sort_order |
| --- | --- | ---: |
| `FASHION` | 패션 | 1 |
| `BEAUTY` | 뷰티 | 2 |
| `GAME` | 게임 | 3 |
| `FOOD` | 음식 | 4 |
| `ENTERTAINMENT` | 엔터테인먼트 | 5 |
| `IT_DIGITAL` | IT/디지털 | 6 |

대분류의 `category_code`는 안정적인 시스템 식별자다.

세부분류는 `category_code = NULL`을 허용한다. 세부분류의 DB Identity는 `category_id`이고 소속 대분류는 `parent_id`로 판별한다.

---

## 5. 초기 Category Master Seed v1.0

본 절은 Trend Leader MVP에서 사용하는 초기 Category Master Seed를 확정한다.

초기 Seed는 다음 원칙을 따른다.

- 대분류 6개와 세부분류 38개를 사용한다.
- 전체 초기 Category Row 수는 44개다.
  - 대분류 6개
  - 세부분류 38개
- 모든 초기 Seed는 `is_active = true`로 생성한다.
- `category_code`는 대분류에만 사용한다.
- 세부분류의 `category_code`는 `NULL`이다.
- 대분류의 `parent_id`는 `NULL`이다.
- 세부분류의 `parent_id`는 해당 대분류의 `category_id`를 사용한다.
- `category_id`는 Seed 정의에 하드코딩하지 않는다.
- 세부분류의 `sort_order`는 동일 부모 안에서의 노출 순서를 의미한다.
- 모든 `기타` 세부분류의 `sort_order`는 `99`로 고정한다.
- 서로 다른 부모 아래 동일한 `category_name`은 허용한다.
- 같은 부모 아래 동일한 `category_name`은 허용하지 않는다.

### 5.1 대분류 Seed

| category_code | category_name | sort_order | parent_id | is_active |
| --- | --- | ---: | --- | --- |
| `FASHION` | 패션 | 1 | `NULL` | `true` |
| `BEAUTY` | 뷰티 | 2 | `NULL` | `true` |
| `GAME` | 게임 | 3 | `NULL` | `true` |
| `FOOD` | 음식 | 4 | `NULL` | `true` |
| `ENTERTAINMENT` | 엔터테인먼트 | 5 | `NULL` | `true` |
| `IT_DIGITAL` | IT/디지털 | 6 | `NULL` | `true` |

대분류의 `category_code`는 환경과 표시명 변경에 영향을 받지 않는 안정적인 시스템 식별자로 사용한다.

### 5.2 패션 세부분류

상위 Category:

```text
FASHION / 패션
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 의류 | 1 | `NULL` | `true` |
| 신발 | 2 | `NULL` | `true` |
| 가방 | 3 | `NULL` | `true` |
| 주얼리·액세서리 | 4 | `NULL` | `true` |
| 패션 스타일 | 5 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `의류`: 상의, 하의, 아우터, 원피스 등 의류 자체가 중심인 Trend
- `신발`: 운동화, 구두, 부츠 등 신발 관련 Trend
- `가방`: 백팩, 핸드백, 크로스백 등 가방 관련 Trend
- `주얼리·액세서리`: 귀걸이, 목걸이, 반지, 모자, 벨트 등 패션 액세서리 관련 Trend
- `패션 스타일`: 특정 스타일링, 코디, 패션 미학 자체가 중심인 Trend
- `기타`: 패션 영역임은 명확하지만 위 세부분류에 자연스럽게 포함되지 않는 Trend

`Y2K`, `고프코어`, `스트릿`처럼 빠르게 변화하는 스타일 표현은 별도 Category로 확장하지 않고 `패션 스타일`에 연결한 뒤 Keyword/Hashtag로 표현하는 것을 우선한다.

### 5.3 뷰티 세부분류

상위 Category:

```text
BEAUTY / 뷰티
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 스킨케어 | 1 | `NULL` | `true` |
| 메이크업 | 2 | `NULL` | `true` |
| 헤어 | 3 | `NULL` | `true` |
| 향수 | 4 | `NULL` | `true` |
| 네일 | 5 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `스킨케어`: 피부 관리, 기초 화장품, 피부 관련 제품/루틴
- `메이크업`: 색조 화장품, 화장법, 메이크업 Trend
- `헤어`: 헤어스타일, 헤어케어, 헤어 제품
- `향수`: 향수와 향 관련 제품
- `네일`: 네일아트 및 네일 제품
- `기타`: 뷰티 영역임은 명확하지만 위 세부분류로 분류하기 어려운 Trend

### 5.4 게임 세부분류

상위 Category:

```text
GAME / 게임
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 모바일 게임 | 1 | `NULL` | `true` |
| PC 게임 | 2 | `NULL` | `true` |
| 콘솔 게임 | 3 | `NULL` | `true` |
| e스포츠 | 4 | `NULL` | `true` |
| 게임 플랫폼·서비스 | 5 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `모바일 게임`: 스마트폰/태블릿을 중심 플랫폼으로 하는 게임 Trend
- `PC 게임`: PC를 중심 플랫폼으로 하는 게임 Trend
- `콘솔 게임`: PlayStation, Xbox, Nintendo 등 콘솔 중심 게임 Trend
- `e스포츠`: 프로 리그, 대회, 선수, 팀, 경기 중심 Trend
- `게임 플랫폼·서비스`: Steam, Epic Games Store, Xbox Game Pass, PlayStation Plus, 클라우드 게이밍 등 게임 유통·구독·플랫폼·서비스 자체가 중심인 Trend
- `기타`: 게임 영역임은 명확하지만 위 세부분류로 분류하기 어려운 Trend

다음과 같은 순수 산업 이슈는 MVP 초기에는 별도 `게임 산업` Category를 만들지 않는다.

```text
게임사 실적
게임사 인수합병
게임 산업 규제
게임업계 고용/구조조정
게임 시장 규모
```

해당 유형이 실제 수집 데이터에서 반복적으로 나타날 경우 `게임 산업`을 신규 세부분류 후보로 재검토한다.

### 5.5 음식 세부분류

상위 Category:

```text
FOOD / 음식
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 한식 | 1 | `NULL` | `true` |
| 중식 | 2 | `NULL` | `true` |
| 일식 | 3 | `NULL` | `true` |
| 양식 | 4 | `NULL` | `true` |
| 카페·디저트 | 5 | `NULL` | `true` |
| 식품·음료 | 6 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `한식`: 한국 음식/요리 자체가 중심인 Trend
- `중식`: 중국 음식/요리 자체가 중심인 Trend
- `일식`: 일본 음식/요리 자체가 중심인 Trend
- `양식`: 서양 음식/요리 자체가 중심인 Trend
- `카페·디저트`: 카페 메뉴, 커피, 베이커리, 디저트 중심 Trend
- `식품·음료`: 편의점/마트 상품, 가공식품, 라면, 과자, 포장 음료, 식품 브랜드 상품 등
- `기타`: 음식 영역임은 명확하지만 위 세부분류로 분류하기 어려운 Trend

음식 세부분류는 음식 문화권과 제품 유형이라는 서로 다른 관점이 일부 혼합되어 있다.

MVP에서는 실제 Trend 분류 Coverage를 우선하여 위 구조를 사용하고, 실제 수집 데이터에서 반복적인 분류 충돌이 확인되면 후속 Taxonomy 개편 대상으로 검토한다.

### 5.6 엔터테인먼트 세부분류

상위 Category:

```text
ENTERTAINMENT / 엔터테인먼트
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 음악 | 1 | `NULL` | `true` |
| 영화 | 2 | `NULL` | `true` |
| 드라마 | 3 | `NULL` | `true` |
| 예능 | 4 | `NULL` | `true` |
| 웹툰·애니메이션 | 5 | `NULL` | `true` |
| 연예인·스타 | 6 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `음악`: 음원, 앨범, 공연, 음악 콘텐츠 중심 Trend
- `영화`: 영화 작품 및 영화 관련 콘텐츠 중심 Trend
- `드라마`: TV/OTT 드라마 작품 중심 Trend
- `예능`: 예능 프로그램 및 예능 콘텐츠 중심 Trend
- `웹툰·애니메이션`: 웹툰, 만화, 애니메이션 작품 중심 Trend
- `연예인·스타`: 특정 연예인, 아이돌, 배우 등 인물 자체가 중심인 Trend
- `기타`: 엔터테인먼트 영역임은 명확하지만 위 세부분류에 포함되기 어려운 Trend

특정 연예인이 특정 콘텐츠와 함께 화제가 되는 경우 하나의 Trend에 복수 Category를 연결할 수 있다.

예:

```text
아이돌 신곡 무대 화제
→ 엔터테인먼트 > 음악
→ 엔터테인먼트 > 연예인·스타
```

### 5.7 IT/디지털 세부분류

상위 Category:

```text
IT_DIGITAL / IT/디지털
```

| category_name | sort_order | category_code | is_active |
| --- | ---: | --- | --- |
| 인공지능 | 1 | `NULL` | `true` |
| 모바일·스마트폰 | 2 | `NULL` | `true` |
| PC·하드웨어 | 3 | `NULL` | `true` |
| 소프트웨어·앱 | 4 | `NULL` | `true` |
| 플랫폼·서비스 | 5 | `NULL` | `true` |
| 기타 | 99 | `NULL` | `true` |

분류 기준:

- `인공지능`: 생성형 AI, AI 모델, AI 기능 및 AI 기술 자체가 중심인 Trend
- `모바일·스마트폰`: 스마트폰, 태블릿, 모바일 기기 및 모바일 생태계 Trend
- `PC·하드웨어`: PC, CPU, GPU, 주변기기 등 하드웨어 중심 Trend
- `소프트웨어·앱`: 특정 프로그램, 애플리케이션, 소프트웨어 제품 중심 Trend
- `플랫폼·서비스`: 웹 서비스, 클라우드, 온라인 플랫폼 및 디지털 서비스 생태계 중심 Trend
- `기타`: IT/디지털 영역임은 명확하지만 위 세부분류로 분류하기 어려운 Trend

하나의 Trend가 여러 IT 세부분류에 자연스럽게 포함되는 경우 복수 매핑을 허용한다.

예:

```text
갤럭시 AI 기능 화제
→ IT/디지털 > 인공지능
→ IT/디지털 > 모바일·스마트폰
```

### 5.8 `기타` Category 운영 규칙

`기타`는 해당 대분류 영역에 속하는 것은 확실하지만 현재 Taxonomy의 세부분류로 자연스럽게 표현하기 어려운 Trend의 fallback이다.

`기타`를 다음 용도로 사용하지 않는다.

```text
분류하기 귀찮은 Trend
대분류 자체가 불명확한 Trend
6개 대분류 범위 밖의 Trend
```

동일하거나 유사한 주제가 반복적으로 `기타`에 분류되면 신규 세부분류 후보로 기록하고 Taxonomy 개편 시 재검토한다.

### 5.9 Seed 관리 방식

Category Master Seed는 Alembic Schema Migration과 분리하여 별도의 Seed 로직으로 관리한다.

Seed는 반복 실행해도 동일한 Category Row를 중복 생성하지 않는 idempotent 동작을 목표로 한다.

식별 기준은 다음과 같다.

```text
대분류
→ category_code

세부분류
→ 부모 대분류 + category_name
```

`category_id`는 DB에서 생성되는 Identity이므로 Seed 정의에 고정값으로 저장하지 않는다.

Seed의 기본 동작 범위:

```text
존재하지 않는 초기 Category
→ 생성

이미 존재하는 동일 Category
→ 중복 생성하지 않음

Seed 정의에서 제거된 Category
→ 자동 DELETE 하지 않음
```

Category rename, deactivate, merge가 필요해진 경우 초기 Seed 재실행으로 암묵적으로 처리하지 않고 별도의 명시적인 변경 절차로 수행한다.

Category Master Seed와 테스트용 Fixture 데이터는 서로 분리한다.

### 5.10 Seed v1.0 변경 정책

본 Seed 목록은 MVP의 초기 기준 데이터다.

실제 Trend 수집 및 분류가 시작된 이후 다음 상황이 반복적으로 확인되면 Taxonomy 변경을 검토할 수 있다.

- 특정 대분류의 `기타` 사용 비율이 지속적으로 높음
- 동일한 신규 주제가 반복적으로 `기타`로 분류됨
- 두 세부분류 사이의 경계 충돌이 반복됨
- 실제 수집 가능한 Trend와 현재 세부분류 구조가 지속적으로 맞지 않음

Taxonomy 변경 시 기존 Category ID를 불필요하게 삭제하거나 재생성하지 않고 기존 Trend/관심사 참조 영향을 먼저 검토한다.

---

## 6. category_name 중복 정책

`category_name`은 표시명이며 전역 식별자가 아니다.

서로 다른 부모 아래 같은 이름을 허용한다.

```text
음식 > 기타
게임 > 기타
→ 허용
```

같은 부모 아래 같은 이름은 도메인 중복으로 간주한다.

```text
음식 > 기타
음식 > 기타
→ 금지
```

정확한 MariaDB Constraint 구현 방식은 별도 DB Migration 설계에서 확정한다. MVP에서는 Seed/Migration 검증과 Service 규칙으로 우선 방어한다.

`game_other_game`, `food_other_food`처럼 표시명에 시스템 구분자를 섞지 않는다.

---

## 7. 사용자 관심사 규칙

사용자가 저장/수정할 수 있는 관심사는 다음 조건을 모두 만족하는 대분류만 허용한다.

```text
존재함
AND is_active = true
AND parent_id IS NULL
```

세부분류는 사용자 관심사로 직접 저장하지 않는다.

따라서 기존 관심사 저장/조회/수정 API의 대분류 선택 정책은 유지한다.

---

## 8. Trend-Category Mapping

`trend_category_map`은 Trend와 Category의 M:N 관계를 표현한다.

하나의 Trend에는 여러 세부분류를 연결할 수 있다.

예:

```text
Trend: 갤럭시 AI 기능 화제

연결 Category
- IT/디지털 > 인공지능
- IT/디지털 > 모바일·스마트폰
```

또한 서로 다른 대분류에 속한 세부분류를 하나의 Trend에 함께 연결할 수도 있다.

예:

```text
Trend: 게임 × 인기 애니메이션 콜라보

연결 Category
- 게임 > 모바일 게임
- 엔터테인먼트 > 웹툰·애니메이션
```

### 부모 대분류 중복 매핑 금지

Trend가 세부분류에 연결된 경우 그 부모 대분류를 `trend_category_map`에 다시 저장하지 않는다.

```text
Trend: 신작 모바일 RPG

허용
- 모바일 게임

저장하지 않음
- 게임 + 모바일 게임 동시 중복 매핑
```

대분류 관계는 `categories.parent_id`를 통해 추론한다.

---

## 9. 대표 Category 정책

하나의 Trend에 여러 Category를 연결하는 것은 허용하지만, MVP에서는 대표 Category의 비즈니스 의미를 확정하지 않는다.

현재 정책:

- `is_primary` 사용처를 만들지 않는다.
- 기존 DB 컬럼은 즉시 제거하지 않는다.
- 실제 Use Case가 생기기 전까지 일반 매핑은 `is_primary = false`로 취급한다.
- UI에서 Category를 2~3개 표시하는 정책은 대표 Category 선정 규칙과 별개의 표시 정책이다.

향후 카드에 Category 하나만 표시하거나, 대표 Category별 통계/그룹핑이 필요해질 경우 별도 설계로 다시 연다.

---

## 10. 맞춤 Trend 추천 Category Matching

사용자의 관심사는 대분류이고 Trend에는 구체적인 세부분류가 연결되므로 단순 `category_id = category_id` 직접 매칭을 사용하지 않는다.

맞춤 추천의 Category Matching 흐름은 다음과 같다.

```text
user_interest_categories
→ 사용자의 활성 관심 대분류 조회
→ 각 대분류의 활성 세부분류 ID 집합 조회
→ trend_category_map.category_id와 매칭
→ ACTIVE Trend 조회
→ trend_id 기준 중복 제거
```

예:

```text
사용자 관심사
GAME

활성 하위 Category
- 모바일 게임
- PC 게임
- 콘솔 게임
- e스포츠
- 게임 플랫폼·서비스
- 기타

Trend
- 신작 모바일 RPG → 모바일 게임

결과
→ GAME 관심 사용자에게 추천 가능
```

하나의 Trend가 같은 대분류 아래 여러 세부분류와 동시에 매칭되더라도 목록에는 한 번만 반환한다.

---

## 11. category_id Query Filter

Trend API의 `category_id` 필터가 대분류와 세부분류 중 무엇을 허용할지는 Trend 목록 API 구현 설계에서 별도로 확정한다.

현재 본 문서에서 확정하는 것은 **사용자 관심 대분류를 기반으로 한 자동 추천 매칭은 하위 세부분류 범위까지 확장한다**는 점이다.

`applied_category_ids` 같은 추천 응답 필드가 사용자 선택 대분류를 의미할지, 내부 확장 세부분류를 의미할지는 맞춤 Trend API 계약 설계에서 별도 확정한다.

---

## 12. Hashtag / Related Keyword 경계

Hashtag는 Category가 아니다.

MVP에서는 AI가 생성/추천한 해시태그를 기존 AI 분석 관련 키워드 구조로 관리한다.

```text
trend_ai_analyses
→ trend_related_keywords
   - RELATED
   - HASHTAG
   - RECOMMENDED
```

`HASHTAG`는 AI가 분석 결과로 생성하거나 추천한 해시태그 표현이며 검색/탐색 보조에 활용한다.

실제 SNS/외부 Source에서 관측된 원본 Hashtag는 AI 분석 결과와 동일한 데이터로 저장하지 않는다. 실제 Source Hashtag 저장 요구가 생기면 `trend_sources`를 기준으로 별도 설계한다.

---

## 13. Trend Attribute 범위 제외

다음 값은 Category에 넣지 않는다.

```text
신제품
업데이트
이벤트
밈
논란
콜라보
출시
```

해당 값들을 실제 필터/추천/통계에 사용할 필요가 확인되면 `Trend Attribute` 별도 설계 채팅에서 다음을 검토한다.

- 구조화 저장 필요 여부
- 하나의 Trend에 복수 Attribute 허용 여부
- 단일 ENUM vs M:N 구조
- Filter UX 복잡도

현재 스키마에는 새 Attribute 컬럼/테이블을 추가하지 않는다.

---

## 14. 구현 영향 범위

본 설계 확정 후 구현 단계에서 확인할 범위:

```text
Database
- categories.category_name 전역 UNIQUE 제거
- 대분류 category_code 계약 유지
- 세부분류 category_code NULL 유지
- Category Master Seed v1.0 반영
- Category Seed는 Alembic Schema Migration과 분리
- 반복 실행 시 중복 생성하지 않는 idempotent Seed 방식 사용
- Seed 정의에서 제거된 Category의 자동 DELETE 금지

Backend
- Category ORM / Migration
- Category Seed 로직
- Category Repository / Service
- GET /api/categories 회귀
- Trend 추천 시 descendant 매칭
- Trend 결과 중복 제거

Frontend
- CategoryItem.category_code nullable 유지
- 관심사 선택은 대분류만 사용
- 세부분류는 Trend 표시/필터 기능 설계 시 사용

Test
- 서로 다른 부모 아래 같은 이름 허용
- 같은 부모 아래 이름 중복 방어
- Category Master Seed 반복 실행 시 중복 생성 방지
- Seed v1.0의 6개 대분류 + 38개 세부분류 구조 검증
- 대분류 관심사 저장 규칙 회귀
- 세부분류가 대분류 관심 추천에 포함됨
- 여러 세부분류 매칭 Trend 중복 제거
```

---

## 15. 완료 조건

다음이 모두 일치해야 Category Taxonomy 구현 완료로 판단한다.

- 본 설계 확정안
- `design/docs/DB/schema_decisions_v2.1.md`
- ERD v2.1
- SQLAlchemy ORM
- Alembic Migration
- Category Master Seed v1.0과 실제 DB Category 계층
- `GET /api/categories` 응답과 Seed 구조
- 관심사 API 회귀 테스트
- 향후 Trend 추천 구현의 descendant matching 정책

Trend Attribute와 Source Hashtag는 별도 완료 기준을 가진다.
