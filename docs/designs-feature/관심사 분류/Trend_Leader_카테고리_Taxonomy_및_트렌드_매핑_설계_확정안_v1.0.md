# Trend Leader 카테고리 Taxonomy 및 트렌드 매핑 설계 확정안 v1.0

- 프로젝트: Trend Leader
- 기준 Repository: `Trend-Leader-capstoneProject/feature`
- 기준 브랜치: `dev`
- 기준일: 2026-09-07
- 상태: 설계 확정
- 범위: Category Taxonomy, 관심 대분류와 세부분류의 역할, Trend-Category Mapping, 맞춤 추천의 Category Matching, AI Hashtag 경계
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

---

## 2. Category 역할

Category는 **`무슨 주제 영역인가`**만 표현한다.

예:

```text
게임
├─ 모바일 게임
├─ PC·온라인 게임
├─ 콘솔 게임
├─ e스포츠
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

| category_code | category_name |
| --- | --- |
| `FASHION` | 패션 |
| `FOOD` | 음식 |
| `IT_DIGITAL` | IT/디지털 |
| `ENTERTAINMENT` | 엔터테인먼트 |
| `BEAUTY` | 뷰티 |
| `GAME` | 게임 |

대분류의 `category_code`는 안정적인 시스템 식별자다.

세부분류는 `category_code = NULL`을 허용한다. 세부분류의 DB Identity는 `category_id`이고 소속 대분류는 `parent_id`로 판별한다.

---

## 5. 세부분류 Seed 후보 v0.1

아래 목록은 MVP 초기 Seed 후보이며, 실제 Seed 확정 전 팀 최종 확인을 거친다.

| 대분류 | 세부분류 후보 |
| --- | --- |
| 게임 | 모바일 게임 / PC·온라인 게임 / 콘솔 게임 / e스포츠 / 게임 산업·비즈니스 / 기타 |
| IT/디지털 | 인공지능 / 모바일·스마트폰 / PC·하드웨어 / 소프트웨어·앱 / 인터넷·플랫폼 / 기타 |
| 패션 | 스타일·코디 / 의류 / 신발 / 가방·액세서리 / 브랜드·컬렉션 / 기타 |
| 음식 | 한식 / 양식 / 중식 / 일식 / 카페·디저트 / 식품·음료 / 기타 |
| 엔터테인먼트 | 음악 / 영화 / 드라마 / 예능 / 웹툰·애니메이션 / 연예·스타 / 기타 |
| 뷰티 | 스킨케어 / 메이크업 / 헤어 / 향수 / 네일 / 기타 |

### 세부분류 선정 기준

- 비교적 오래 유지되는 주제 영역이어야 한다.
- 유행에 따라 빠르게 바뀌는 표현은 Category보다 Keyword/Hashtag로 둔다.
- 대분류별 개수를 억지로 동일하게 맞추지 않는다.
- 실제 수집 Trend를 분류할 만큼만 둔다.
- `기타`는 현재 Taxonomy가 표현하지 못하는 항목의 fallback이다.
- `기타`에 반복적으로 쌓이는 주제가 생기면 신규 세부분류 후보로 재검토한다.

예를 들어 `스트릿`, `Y2K`, `고프코어`처럼 빠르게 바뀌는 패션 표현은 초기에는 `패션 > 스타일·코디` 아래 관련 Keyword/Hashtag로 다루는 것을 우선한다.

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
- PC·온라인 게임
- 콘솔 게임
- e스포츠
- 게임 산업·비즈니스
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
- Seed 추가

Backend
- Category ORM / Migration
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
- Seed
- Category API 계약
- 관심사 API 회귀 테스트
- 향후 Trend 추천 구현의 descendant matching 정책

Trend Attribute와 Source Hashtag는 별도 완료 기준을 가진다.
