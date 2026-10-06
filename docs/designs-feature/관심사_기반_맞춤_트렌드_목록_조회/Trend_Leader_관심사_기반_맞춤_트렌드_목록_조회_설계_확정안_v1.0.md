# Trend Leader 관심사 기반 맞춤 트렌드 목록 조회 설계 확정안 v1.0

> 문서 상태: FROZEN — 사용자 승인된 Refinement와 11개 관점 Final Review 반영
> 문서화 날짜: 2026-10-06 (Asia/Seoul)
> 대상 기능: GET /api/trends/personalized 및 Personalized Main
> 기준 브랜치: dev
> 기준 HEAD: 이번 문서화 환경에서 저장소 미제공으로 확인하지 못함. 구현 시작 시 실제 SHA를 기록한다.
> 구현 상태: 이번 작업은 설계 문서화이다. 코드 구현·자동 테스트·MariaDB·실기기 검증 완료를 의미하지 않는다.

## 1. 문서 목적과 근거

로그인 사용자의 관심 대분류에 연결된 활성 세부분류를 기준으로 ACTIVE Trend를 선별하고 최신순으로 제공한다. 로그인 이후 Main에서 이 목록을 바로 보여준다.

이번 채팅에서 사용자가 확정한 결정과 Final Review를 기능 계약으로 동결한다. 설계상 구현을 막는 문제가 발견되지 않았다는 판정이며, 실제 구현의 취약점 부재나 성능을 보증하는 판정은 아니다.

### 1.1 대조한 자료

- 사용자 승인된 Design Refinement 및 11개 관점 Final Review.
- `Trend_Leader_AI_Development_Guidelines.md` v1.2, 최종 개정 2026-10-01.
- `schema_decisions.md`: 카테고리 2단계, 사용자 관심 대분류, Trend M:N 매핑, 수집 시각, 조회 인덱스.
- 관심사 조회 및 수정 설계 확정안 v1.0.2: 저장·조회·전체 교체, 정상 수정과 Session 분리, 오류 복구.
- 인증 세션 관리 및 로그아웃 설계 확정안 v1.0: 인증 Client, 공통 401, stale 401 방어, Session Cleanup, 선언적 Navigation.
- API 상세 기능명 템플릿 수정안: 공통 응답과 machine-readable 오류 명세 방식.

첨부 README는 일반 참고자료다. 실제 최신 코드나 확정안보다 우선하지 않는다. 전체 최신 목록의 최신 확정안·실제 코드·테스트·의존성 버전은 구현 시작 시 추가로 대조한다. 과거 대화의 dev 검증 결과를 이번 문서화에서 재실행한 결과로 기록하지 않는다.

### 1.2 기존 문서와의 관계

관심사 확정안 v1.0.2의 31절은 향후 맞춤 Trend Query를 stale/invalidate하는 확장 지점으로 기록했다. 이번 기능에서는 이를 **진행 중 Personalized Query 취소 및 Infinite Pagination Context 전체 Reset**으로 구체화한다. 단순 invalidate만으로는 이번 계약을 충족하지 않는다.

관심사 확정안의 Main 임시 기능 추가 금지와 인증 확정안의 실제 Trend 기능 제외는 각 과거 기능의 범위 제한이다. 이번 기능에서는 사용자가 Main 전환을 명시적으로 승인했으므로 실제 맞춤 목록을 추가한다. 기존 관심사 PUT의 전체 교체, 정상 성공 시 Session 재검증 생략, 관심사 응답 캐시 반영 원칙은 유지한다.

## 2. 범위와 제품 의미

### 2.1 포함

- 로그인 필수 맞춤 목록 API, 관심사 상태 판단, Root → Active Child 확장.
- ACTIVE Trend 선별, 다중 카테고리 일치 시 중복 제거, 기존 최신순 정렬.
- 기존 `CommonResponse[TrendListData]` 및 Trend 목록 응답 조립 재사용.
- Personalized Cursor의 사용자·유효 세부분류 Context 검증.
- Frontend API/Hook/Query Key 분리, 관심사 변경 후 페이지 초기화.
- Main 전환, 번호 없는 TrendCard, 기존 관심사 수정·전체 최신 목록 진입점.
- 초기 조회, 추가 페이지, 새로고침, 도메인 오류 복구 및 관련 검증.

### 2.2 제외

AI/ML 추천, 행동 기반 추천, 관심도 가중치, 일치 수 가중치, 추천 점수, 인기순/추천순, 검색, 북마크, 상세 기능 신규 구현, 외부 수집, AI Provider, Refresh Token, OAuth, 관리자 기능, 카테고리 운영 정책 고도화는 별도 범위다.

새로운 Personalized Repository나 Recommendation Engine, 대규모 Query Engine 추상화, 성능 근거 없는 선행 인덱스 추가도 이번 기본 범위에 포함하지 않는다.

### 2.3 사용자 경험

`AUTHENTICATED + next_step = MAIN`이면 Main의 기본 콘텐츠가 관심사 맞춤 트렌드다. Main에서 별도 Personalized 화면으로 한 번 더 진입시키지 않는다.

Main에는 관심사 수정 및 전체 최신 트렌드 보기 진입점을 제공하며 기존 로그아웃 동작을 보존한다. 전체 최신 목록은 별도 화면으로 유지한다.

표현 예시:

- 제목: “관심사 맞춤 트렌드”
- 설명: “선택한 관심 분야의 최신 트렌드를 확인해 보세요.”
- 정상 빈 목록: “선택한 관심사에 맞는 최신 트렌드가 아직 없습니다.”

Personalized TrendCard는 표시 순번을 사용하지 않는다. 전체 최신 화면의 기존 표시 순번은 이번 변경의 제거 대상이 아니다. “AI 추천”, “TOP 20”, “추천 순위”, “인기순”처럼 현재 계약에 없는 의미를 사용하지 않는다.

## 3. 도메인 용어와 불변조건

| 용어 | 의미 |
| --- | --- |
| Root Interest | 사용자에게 저장된 관심 대분류. `parent_id IS NULL` |
| Active Root | 기존 Category 정책에 따라 조회에 사용할 수 있는 활성 대분류 |
| Effective Child Category Set | Active Root의 활성 직속 세부분류 ID를 중복 제거한 집합 |
| Personalized Context | 현재 인증 사용자 및 위 유효 세부분류 집합 |
| Context Fingerprint | 사용자 ID와 정렬된 유효 세부분류 ID의 SHA-256 값 |
| Personalized Pagination Context | 해당 사용자·관심 범위에서 누적한 페이지와 커서 상태 |

핵심 불변조건:

1. 사용자 식별과 검색 범위는 서버의 현재 인증 사용자로부터 결정한다.
2. 관심사는 대분류, Trend 매핑은 세부분류라는 기존 Taxonomy 정책을 따른다.
3. 한 요청에서 유효 세부분류 집합을 한 번 결정해 Fingerprint와 검색에 동일하게 사용한다.
4. Trend가 여러 선택 관심사에 일치해도 결과에는 한 번만 등장한다.
5. 정렬은 `last_collected_at DESC, trend_id DESC`다. 일치 개수는 정렬에 영향을 주지 않는다.
6. 맞춤 기준 부재와 정상 검색 결과 0건은 서로 다른 상태다.
7. 관심사 수정 성공 후 이전 Personalized 페이지·커서는 재사용하지 않는다.
8. 기존 Public 목록 API와 Public Cursor 계약을 변경하지 않는다.

## 4. API 상세 계약

### 4.1 기본 정보

| 항목 | 계약 |
| --- | --- |
| Method / Endpoint | `GET /api/trends/personalized` |
| 인증 | 필수, `Authorization: Bearer <access_token>` |
| Backend 사용자 | 기존 `CurrentUserDep` 및 ACTIVE 사용자 정책 |
| Frontend Client | `authenticatedApiClient` |
| Path Parameter / Body | 없음 |
| 성공 | `200 OK` |

### 4.2 Query Parameter

| Key | 의미상 타입 | 필수 | 정책 |
| --- | --- | --- | --- |
| `cursor` | string | 아니오 | Personalized Cursor. 미지정 시 첫 페이지 |
| `limit` | integer | 아니오 | 기본 20, 허용 1~50 |

`category_id`는 지원하는 필터가 아니다. 요청값으로 Personalized Scope를 바꾸지 않는다. 미정의 Query Parameter의 무시/거부 여부는 기존 요청 검증 정책을 확인하며, 이번 문서가 별도 공통 정책을 만들지 않는다.

요청 예시:

```http
GET /api/trends/personalized?limit=20
Authorization: Bearer <access_token>
```

### 4.3 Response

`CommonResponse[TrendListData]`를 기존 전체 최신 목록과 동일하게 재사용한다.

| 필드 | 계약 |
| --- | --- |
| `success`, `statusCode`, `message`, `data` | 기존 공통 응답 계약 |
| `data.items` | 기존 `TrendListItem[]` |
| `data.next_cursor` | 다음 페이지의 Personalized Cursor. 마지막 페이지 표현은 기존 목록 계약 |
| `data.has_next` | 기존 목록 계약의 다음 페이지 여부 |

Personalized 전용 응답 필드, 사용자 관심 ID 배열, 추천 점수는 추가하지 않는다. `TrendListItem`의 필드·null 허용·Source 선택·Category 반환 규칙은 기존 목록의 확정안과 실제 Schema에서 확인해 재사용한다. 이 문서에서 보이지 않는 상세 타입을 추측하여 재정의하지 않는다.

### 4.4 오류와 상태

| 조건 | HTTP / 의미 | Frontend |
| --- | --- | --- |
| 정상 관심 범위, 결과 있음 | 200 | 목록 |
| 정상 관심 범위, Trend 없음 | 200, 빈 목록 | 정상 Empty |
| 인증 실패 | 기존 401 | 공통 인증 실패 처리 |
| Cursor 형식/버전/Context 오류 | 400, `INVALID_CURSOR` | 추가 페이지에서 1회 첫 페이지 재시작 |
| 저장된 Interest row 0개 | 409, `INTERESTS_NOT_INITIALIZED` | Session 재확인 및 Onboarding 복구 |
| row는 있으나 유효 Child Scope 0개 | 409, `INTERESTS_NOT_AVAILABLE` | 관심사 수정 및 전체 최신 목록 안내 |
| limit 등 요청 Schema 위반 | 기존 Query Validation 계약, 422 | 입력 계약 오류 |
| 예상하지 못한 서버/DB 오류 | 기존 서버 오류 계약 | 재시도 가능한 일반 오류 |

Frontend는 메시지 문자열이나 HTTP 409만으로 분기하지 않고 machine-readable 이유를 사용한다. 기존 관심사 오류 계약의 `data.reason`을 따른다. `INVALID_CURSOR`의 실제 응답 위치는 기존 Public Cursor 오류 계약을 확인하여 맞추고, 필요 시 Backend·Frontend·OpenAPI·테스트를 함께 정렬한다.

예시 — 관심 범위를 사용할 수 없음:

```json
{
  "success": false,
  "statusCode": 409,
  "message": "현재 관심사로 맞춤 트렌드를 조회할 수 없습니다.",
  "data": {
    "reason": "INTERESTS_NOT_AVAILABLE"
  }
}
```

메시지는 UX 예시이며 문자열을 오류 판정 조건으로 사용하지 않는다. HTTP 계약과 런타임 오류 처리뿐 아니라 OpenAPI의 공개 응답 선언도 확인한다.

## 5. Category Matching과 상태 판정

현재 사용자 Interest row를 조회한 뒤 기존 유효성 정책을 만족하는 활성 Root를 고른다. 각 Root의 활성 직속 Child를 확장하고 ID 집합을 만든다. 이후 그 Child에 `trend_category_map`으로 연결된 ACTIVE Trend를 조회한다.

- Interest row가 아예 없으면 `INTERESTS_NOT_INITIALIZED`다.
- 비활성 Root는 검색 범위에서 제외한다.
- 활성 Root라도 활성 Child가 없으면 그 Root는 검색 범위를 만들지 못한다.
- 일부 Root만 사용 가능하면 가능한 Child 집합으로 200 조회한다.
- 전체 유효 Child 집합이 비면 `INTERESTS_NOT_AVAILABLE`이다.
- 유효 Child는 있으나 Trend가 없으면 200 정상 Empty다.
- Category 삭제로 FK가 깨진 상태는 정상 도메인 상태로 포장하지 않는다. 데이터 무결성 이상으로 조사한다.
- 읽기 API가 관심사 row를 임의 삭제하거나 자동 수정하지 않는다.

예시: 사용자 관심 Root가 게임과 IT/디지털이고, Trend 하나가 양쪽 세부분류에 매핑되어 있어도 Trend는 1개만 반환한다. 매칭 수에 따라 순위를 올리지 않는다.

중복 제거는 페이지 경계와 `limit` 적용 전에 논리적으로 보장해야 한다. 중복된 JOIN row를 먼저 제한하고 응답 조립 단계에서만 제거하여 페이지 크기나 `has_next`를 왜곡하지 않는다. 실제 Query 방식은 기존 Repository와 실행 계획을 확인해 선택한다.

## 6. 정렬과 Personalized Cursor v1

### 6.1 정렬

기존 최신 목록과 동일한 `last_collected_at DESC, trend_id DESC` 및 Keyset 경계를 사용한다. 다음 페이지는 마지막 항목보다 정렬상 뒤에 있는 항목을 조회한다. 시각의 정밀도·직렬화·timezone 처리와 동일 시각 tie-break를 기존 구현과 대조한다.

### 6.2 논리 필드

| 필드 | 의미 |
| --- | --- |
| `version` | Personalized Cursor 해석 버전 |
| `last_collected_at` | 마지막 Trend의 수집 시각 |
| `trend_id` | 동일 시각 정렬을 위한 경계 ID |
| `context_fingerprint` | 현재 사용자 및 유효 Child Scope 요약 |

기존 Public Cursor의 구조를 변경하지 않는다. Personalized 해석에서 Fingerprint 없는 Public Cursor나 미지원 버전을 정상 Cursor로 취급하지 않는다. 실제 인코딩과 Codec 배치는 기존 코드 확인 후 결정한다.

### 6.3 Fingerprint

입력은 현재 `user_id`와 오름차순으로 정렬한 중복 없는 `effective_child_category_ids`다. 한 가지 명확한 직렬화 규칙을 고정해 SHA-256으로 계산한다. 개념 예시는 `user:15|categories:3,5,8,14`다. 입력 순서가 달라도 같은 집합이면 같은 값이어야 한다.

Raw 사용자 ID나 Category 배열을 Cursor에 별도 노출할 필요는 없다. `limit`은 범위를 바꾸지 않으므로 Fingerprint 입력에 포함하지 않는다.

첫 페이지는 현재 Context로 조회하고 그 Fingerprint를 다음 Cursor에 넣는다. 후속 페이지는 현재 Context를 다시 해석해 Cursor Fingerprint와 비교한다. 다르면 `400 INVALID_CURSOR`다. 이전 Cursor의 Category를 신뢰해 검색하지 않는다.

| 변화 | 판정 |
| --- | --- |
| 사용자 ID가 달라짐 | Context 불일치 |
| 유효 Child 집합이 달라짐 | Context 불일치 |
| 관심 ID 입력 순서만 달라짐 | 동일 집합이면 동일 Context |
| limit만 달라짐 | 동일 Context |
| 관심 변경 후에도 유효 Child 집합이 같음 | 동일 Context일 수 있음. 클라이언트 PUT 성공 Reset은 그대로 수행 |

**정확성 메모:** Fingerprint는 실제 조회 범위의 변경을 감지한다. 모든 관심사 저장 행위나 Trend 데이터 변경을 감지하는 Revision 번호가 아니다. 앞선 Review의 “관심사 변경이면 Fingerprint 변경”은 유효 Child 집합이 바뀌는 경우에 성립한다.

### 6.4 보안과 한계

Fingerprint는 인증·인가 수단, 비밀값, HMAC 서명 또는 익명화 보장이 아니다. 인증은 JWT와 현재 사용자 Dependency가 담당한다. 서버가 매 요청 사용자 Scope를 재결정하며 Cursor 경계값을 변조해도 다른 사용자 Scope로 조회해서는 안 된다.

v1에서 Cursor 서명을 새로 추가하지 않는다. 그렇더라도 잘못된 인코딩·타입·필수 필드·버전을 안전하게 검증하며 파싱 예외를 서버 오류로 흘리지 않도록 테스트한다.

유효 Child 집합이 같아도 Trend의 수집 시각·상태·매핑은 페이지 사이에 바뀔 수 있다. 따라서 이 Cursor는 전체 Dataset Snapshot을 보장하지 않는다. 기존 live-feed 최신 목록과 동일하게 이동·누락·중복 가능성을 허용하고 새로고침으로 다시 구성한다. 이 한계를 Fingerprint로 해결했다고 표현하지 않는다.

## 7. Backend 책임과 Transaction

| 계층 | 책임 |
| --- | --- |
| TrendRouter | HTTP, Query 검증, CurrentUserDep, 응답/OpenAPI 연결 |
| PersonalizedTrendService | 관심사 상태, 유효 Scope, Fingerprint, Cursor 검증, 목록 조회 조정 |
| Interest / Category Repository | 기존 경계 내 저장 관심사 및 Category 사실 조회 |
| TrendRepository | Scope와 정렬 경계에 맞는 page 조회, Source·Category batch 조회 |
| 기존 Schema / 목록 조립 | TrendListData와 TrendListItem 계약 재사용 |

`find_page()`, `find_latest_sources_by_trend_ids()`, `find_categories_by_trend_ids()`는 Review에서 사용한 책임 이름이다. 실제 존재 여부·시그니처를 확인하여 재사용 또는 최소 확장한다. 보이지 않는 함수를 존재한다고 가정하지 않는다.

Personalized 전용 Service로 Public 조회와 다른 시작 조건을 분리한다. ORM/SQL을 Service·Router에 직접 넣지 않는다. 목록 조립 중복이 실제로 커질 경우에만 작은 공통 조립 책임을 추출한다.

이번 API는 읽기 유스케이스다. 관심사 PUT의 Lock/commit/전체 Transaction 재시도 정책을 그대로 복사하지 않는다. 한 요청의 Scope 계산 및 페이지·batch 조회가 기존 Request Session/Transaction 경계에서 일관되게 수행되는지 확인한다. Context 계산 직후 다른 트랜잭션의 변경을 모두 막는 직렬화 보장을 추가하지 않는다.

Source와 Category는 batch로 조회한다. 항목별 Repository 호출이나 lazy loading으로 N+1을 만들지 않는다. 향후 `/trends/{trend_id}`와 `/trends/personalized`가 함께 등록되면 정적 Route가 의도한 Handler로 연결되는지 확인한다.

## 8. Frontend API, Query, Cache

| 목록 | API / Hook 책임 | Client | Query 의미 |
| --- | --- | --- | --- |
| Public 전체 최신 | 기존 getTrends / useTrends | publicApiClient | 기존 목록 Namespace |
| Personalized | getPersonalizedTrends / usePersonalizedTrends | authenticatedApiClient | Personalized 전용 Namespace |

함수 이름은 책임 표현이며 실제 파일 위치·현재 export를 확인한다. 응답 타입과 카드 UI는 공유하되 Query Lifecycle은 분리한다. Key의 개념은 `['trends', 'personalized', ...]`이며 정확한 모양은 기존 Key 컨벤션과 실제 요청 변수에 맞춘다.

사용자 ID를 Query Key에 강제 추가하지 않는 기존 MVP 결정을 유지한다. 이는 로그아웃/인증 실패/계정 전환 시 진행 중 사용자 Query 취소와 사용자 Cache 제거가 실제로 보장된다는 전제다. 구현 시작 시 이 경로를 검증하고 계정 A의 결과가 B에게 나타나지 않는 테스트를 포함한다.

### 8.1 관심사 PUT 성공

1. 기존 계약대로 PUT 응답의 최종 관심사 상태를 관심사 Query Cache에 반영한다.
2. 진행 중 Personalized Query를 취소한다.
3. 이전 Personalized pages와 pageParams/Cursor를 폐기한다.
4. 다음 Main 조회는 Cursor 없이 현재 관심사 기준 첫 페이지에서 시작한다.
5. 정상 관심사 수정은 Session 상태를 바꾸거나 세션 재검증을 호출하지 않는다. 기존 성공 Navigation 흐름을 유지한다.

Public 최신 목록 및 Category Master Cache는 이 Reset의 대상이 아니다. PUT 실패 시 Personalized 목록을 성공한 것처럼 초기화하지 않는다.

`removeQueries`, `resetQueries` 등 정확한 API는 설치된 TanStack Query 버전, 활성 Observer, 기존 Hook을 확인한 뒤 선택한다. 취소 후 Context 폐기라는 계약과 Main의 재조회 결과를 검증한다. 취소 호출만으로 Race 방어가 끝났다고 단정하지 않고 AbortSignal 전달, 늦은 응답·Callback, 활성 Query 재시작 타이밍을 함께 확인한다.

### 8.2 INVALID_CURSOR 자동 복구

추가 페이지에서 `400 INVALID_CURSOR`를 받으면 기존 pages·Cursor를 폐기하고 Cursor 없는 첫 페이지를 **1회** 자동 요청한다. 복구 중 추가 load-more/새로고침의 중복 실행을 막는다.

복구 첫 페이지도 실패하면 해당 오류의 UI로 전환하며 자동 Restart를 반복하지 않는다. 409나 401이면 각각 도메인/인증 정책으로 처리한다. 일반적인 네트워크 Retry와 Cursor Restart 횟수를 혼동하지 않는다. 400 INVALID_CURSOR와 409 도메인 오류를 일반 Retry로 반복하지 않는다.

### 8.3 Pull-to-refresh

이전 페이지와 Cursor를 폐기하고 현재 관심사 기준 첫 페이지를 조회한다. 기존 모든 페이지를 같은 Cursor Chain으로 순차 refetch하는 것만으로 이번 계약을 충족했다고 판단하지 않는다. 추가 페이지 요청과 경합하는 경우 늦은 응답이 새 목록에 합쳐지지 않아야 한다.

## 9. Main 상태표와 Navigation

| 상태 | Main 동작 |
| --- | --- |
| 최초 Loading | Skeleton 또는 기존 Loading UI |
| 성공 | 번호 없는 Personalized TrendCard 목록 |
| 정상 Empty | 관심사에 맞는 트렌드가 아직 없다는 안내 |
| INTERESTS_NOT_INITIALIZED | 기존 Session 재확인 → RootNavigator의 Onboarding 복구 |
| INTERESTS_NOT_AVAILABLE | 관심사 수정 안내 + Interest Edit CTA + 전체 최신 목록 진입점 |
| 401 | 기존 공통 인증 실패 처리 |
| 최초 일반 오류 | Error Feedback 및 Retry |
| 추가 페이지 Loading | 기존 목록 유지 + Footer Loading |
| 추가 페이지 일반 오류 | 기존 목록 유지 + Footer Retry |
| 추가 페이지 INVALID_CURSOR | 기존 Pagination 폐기 → 첫 페이지 1회 자동 재시작 |
| Pull-to-refresh | 현재 관심사로 첫 페이지부터 새 구성 |

`INTERESTS_NOT_INITIALIZED`에서 Screen이 직접 Onboarding으로 강제 이동하지 않는다. 서버 Session을 Source of Truth로 삼아 기존 선언적 Root Navigation을 활용한다. Session 재확인 실패나 불일치가 계속되는 경우 무한 재검증/재조회 대신 기존 복구 오류·사용자 재시도 경로를 사용한다.

`INTERESTS_NOT_AVAILABLE`은 관심사 설정 여부를 false로 만드는 상태가 아니다. 정상 관심사 데이터가 남아 있으므로 Interest Edit 경로를 제공한다. 순번 제거를 위한 TrendCard 변경은 Public 화면의 기존 렌더링을 보존하는 최소 변경으로 수행한다.

## 10. 주요 대안과 선택 이유

| 논점 | 선택 | 대안 및 트레이드오프 |
| --- | --- | --- |
| Main | 맞춤 목록을 기본 콘텐츠로 전환 | 별도 Personalized 화면은 핵심 기능 진입 단계를 늘림 |
| Service | 별도 유스케이스 Service, Repository 재사용 | Public Service에 모든 사용자 분기를 합치면 책임이 섞임. 새 Repository는 SQL 책임 중복 |
| Cursor | 사용자 + 유효 Child Scope Fingerprint | Context 없는 Cursor는 변경된 관심 범위에 이전 페이지 경계를 적용할 수 있음 |
| 변경 감지 | 실제 조회 범위 집합 | 관심사 Revision은 모든 저장 행위를 감지하지만 추가 상태·Schema 관리가 필요 |
| 관심사 변경 Cache | 취소 후 Pagination 전체 Reset | invalidate만으로 기존 pageParams가 사라짐을 보장할 수 없음 |
| 복구 | 첫 페이지 1회 Restart | 즉시 오류는 UX 부담, 무한 Restart는 반복 요청·오류 은폐 |
| 번호 | Personalized에서 생략 | 최신순 번호는 추천 순위로 오해될 수 있음 |

선택은 현재 MVP의 정확성과 유지보수성을 위한 설계 판단이다. 특정 Library의 공식 권고라는 뜻은 아니다.

## 11. 테스트 전략과 Acceptance Criteria

새 Service 분기·Fingerprint·Cursor 검증은 TDD 우선 후보다. Router/Query/Screen은 실패 위험에 맞는 계약·통합 테스트를 사용한다. 테스트 수를 목표로 삼지 않는다.

### 11.1 Backend

| 영역 | 반드시 검증할 행동 |
| --- | --- |
| Auth / Router | 비로그인 401, 올바른 정적 Route, limit 기본값과 경계·거부 |
| Interest 상태 | row 0 → INITIALIZED 오류, Scope 0 → AVAILABLE 오류, 일부 유효 → 200 |
| Taxonomy | 활성 Root → 활성 Child, 비활성 Root/Child 제외 |
| Matching | Cross-root 일치, 동일 Trend 1회, ACTIVE만, 정상 Empty 200 |
| Pagination | 정렬과 tie-break, 중복 Match에도 page 크기·has_next·다음 경계 정확 |
| Cursor | 정상 이동, 잘못된 인코딩/필드/버전, Public Cursor 오용 거부 |
| Fingerprint | 같은 집합·다른 순서 동일, 사용자 변경·유효 Child 변경 불일치, limit 변경 동일 |
| Response | 기존 TrendListData와 Source/Category 규칙, 오류 reason와 OpenAPI 일치 |
| DB 통합 | 실제 ORM 결과, 일정한 batch 조회, 예상하지 못한 DB 오류를 409로 오분류하지 않음 |

### 11.2 Frontend

- Personalized가 인증 Client를 사용하며 Public과 Key가 분리된다.
- PUT 성공 후 이전 Cursor가 사라지고 Main이 첫 페이지부터 현재 관심사 목록을 조회한다.
- PUT 실패 시 기존 Personalized 상태를 성공 상태로 덮어쓰지 않는다.
- Public 최신 목록과 Category Cache는 그대로 유지된다.
- 늦은 이전 요청, load-more와 refresh 경합, 로그아웃/계정 전환이 기존 목록을 되살리지 않는다.
- INVALID_CURSOR → 첫 페이지 1회 복구, 복구 실패 → 적절한 Error/Domain UI, 무한 Restart 없음.
- INITIALIZED/AVAILABLE/정상 Empty를 구별하며 401은 기존 공통 처리로 위임한다.
- Main 상태표, CTA Navigation, Personalized 번호 생략 및 Public 카드 회귀를 확인한다.

### 11.3 MariaDB와 실제 기기

1. 실제 Backend에 로그인하여 Main 맞춤 목록이 기본으로 나타나는지 확인한다.
2. 관심사 수정 후 Main으로 돌아와 첫 페이지 결과가 바뀌고 이전 Cursor를 쓰지 않는지 확인한다.
3. Pagination, Pull-to-refresh, 앱 재진입, 전체 최신 화면 이동·복귀를 확인한다.
4. 비활성 관심 범위와 정상 Empty를 구별하며 회복 CTA를 확인한다.
5. 계정 전환과 세션 만료에서 이전 사용자 목록이 보이지 않는지 확인한다.
6. 소수 Root와 최대 수준의 Root 선택에 대해 실제 MariaDB Query를 EXPLAIN한다. 데이터 규모·선택도·실행 계획을 기록한다.

Mock만으로 SQL/DB 정확성이나 취소·Interceptor의 실제 동작을 완료 판정하지 않는다. 실기기 또는 DB 검증을 실행하지 못하면 미검증으로 남긴다.

## 12. Performance와 Schema

기존 문서에는 `trend_category_map(category_id, trend_id)`와 Trend 최신순 관련 인덱스가 기록되어 있다. 실제 Migration/DB에 존재하는지는 구현 시 확인한다. 특정 인덱스를 사용하거나 충분히 빠르다고 문서만으로 단정하지 않는다.

페이지 → Source batch → Category batch 패턴을 유지한다. 적은/많은 유효 Child 집합에서 중복 제거와 정렬이 포함된 실제 Query를 EXPLAIN한다. 기존 Latest Source batch의 인덱스 개선 후보는 별도 Observation으로 유지하며 근거 없이 선행 변경하지 않는다.

현재 설계는 신규 Schema 변경을 요구하지 않는다. 실제 구현에서 필요성이 확인되면 이유, Migration, 하위 호환성, 테스트 영향을 별도로 검토한다.

## 13. 구현 순서

| Phase | 작업 | 종료 조건 |
| --- | --- | --- |
| 0 | dev/HEAD/working tree, 기준 문서, 관련 코드·의존성·테스트 확인 | 실제 기준 SHA와 충돌·미확정 목록 기록 |
| 1 | API/오류/Cursor/Fingerprint 계약 연결 | 핵심 Service/Codec 실패 시나리오 확정 |
| 2 | 관심 Context 및 TrendRepository Scope 구현 | 상태·Matching·중복·정렬·Cursor 테스트 통과 |
| 3 | Router/Schema/OpenAPI 연결 | 인증·HTTP 계약·Public 회귀 통과 |
| 4 | Personalized API/Hook/Key, 취소·Reset·복구 | 비동기·Cache 계약 검증 |
| 5 | Main·TrendCard·Navigation 연결 | 상태표와 Public 화면 회귀 검증 |
| 6 | 전체 회귀, MariaDB EXPLAIN, 실제 기기 | Acceptance 및 미검증 상태 기록 |
| 7 | 문서 정합성, diff, Commit 제안 | 구현·검증 증거와 문서의 상태 일치 |

실제 파일 경로·함수 인자·테스트 명령은 Phase 0에서 확인한다. Windows PowerShell 명령은 Bash 줄 연속 문자와 혼합하지 않는다. Library API 선택 등 버전 의존 사실은 설치 버전과 그 버전의 공식 문서로 검증한다.

## 14. Final Review 기록

| 관점 | 설계 판정 | 구현 시 남은 증거 |
| --- | --- | --- |
| 제품 의미 | PASS | 관심 Category 기반 최신 목록, 과장된 UI 표현 없음 |
| API | PASS | 실제 HTTP/Schema/OpenAPI/Frontend 일치 |
| 인증 | PASS | Dependency, 공통 401, 사용자 Cache 격리 |
| Category Matching | PASS | 실제 Root/Child/매핑 Query 결과 |
| 정렬 | PASS | 동일 시각 tie-break 및 페이지 경계 |
| Cursor | PASS | 파싱, Context 검증, 변조·오용 실패 경로 |
| Backend | PASS | 책임 분리와 기존 pipeline 재사용 |
| Frontend | PASS | 취소·Reset·Race·1회 복구 |
| UI / Navigation | PASS | Main 전환과 상태별 복구 |
| Test | PASS | 정의된 핵심 시나리오의 실행 결과 |
| Performance / DB | PASS with Observation | 실제 MariaDB EXPLAIN 및 N+1 검증 |

Review 당시 Blocking Issue는 없음. 실제 구현에서 계약 충돌·보안 결함·데이터 무결성 문제가 확인되면 근거와 영향을 기록하고 해당 문제를 해결한다. 더 좋은 대안이 보인다는 이유만으로 확정안을 다시 열지 않는다.

## 15. 주의사항과 검증 추적

현재 항목은 검증 계획이며 완료 증거가 아니다. 해결 후 같은 문서에서 상태·날짜·기준 SHA·테스트 또는 실행 계획을 갱신한다.

| ID | 항목 | 현재 상태 | 해결 증거 |
| --- | --- | --- | --- |
| OBS-01 | Fingerprint는 인증/서명/Snapshot 보장이 아님 | 계약 기록 완료, 구현 미검증 | 미기록 |
| OBS-02 | PUT 후 invalidate만 하지 않고 pages/pageParams 폐기 | 구현 검증 대기 | 미기록 |
| OBS-03 | 취소와 늦은 응답·활성 Observer Race 방어 | 구현 검증 대기 | 미기록 |
| OBS-04 | INVALID_CURSOR Restart 1회, 복구 실패 UI | 구현 검증 대기 | 미기록 |
| OBS-05 | INITIALIZED / AVAILABLE / Empty 구분 | 구현 검증 대기 | 미기록 |
| OBS-06 | Session 복구와 Interest Edit 책임 분리 | 구현 검증 대기 | 미기록 |
| OBS-07 | Personalized 카드 번호 생략, Public 회귀 보존 | 구현 검증 대기 | 미기록 |
| OBS-08 | MariaDB EXPLAIN, 인덱스 존재·선택도 확인 | DB 검증 대기 | 미기록 |
| OBS-09 | Public API / Public Cursor 계약 보존 | 회귀 검증 대기 | 미기록 |
| OBS-10 | 동적 Trend Route와 정적 personalized 충돌 방어 | 실제 Router 확인 대기 | 미기록 |
| OBS-11 | 페이지 제한 전 논리 중복 제거, N+1 방지 | DB 통합 검증 대기 | 미기록 |
| OBS-12 | 계정 전환·로그아웃·401 후 이전 Cache 노출 방지 | 통합/기기 검증 대기 | 미기록 |
| OBS-13 | 동일 Child Scope의 관심 변경은 Fingerprint 동일 가능 | 정확성 설명 반영, 테스트 대기 | 미기록 |

검증만 추가되면 결정은 유지하고 증거를 덧붙인다. 계약 변경이면 변경 이유, 이전/새 결정, 호환성, 코드·테스트 영향과 버전 변경 여부를 함께 기록한다.

## 16. 기능 완료와 후속 범위

기능 완료는 범위 내 구현, API/Frontend 계약 일치, 핵심 정상·실패 경로, 자동 검증, 필요한 MariaDB·실기기 검증, 회귀 검증, 문서 정합성 및 의도하지 않은 변경 없음이 충족된 상태다.

이번 문서 생성은 설계 문서화 완료다. 구현 완료·자동 검증 완료·실제 동작 검증 완료와 구별한다. 현재 저장소 미제공, 최신 HEAD 미확인, 실행 검증 미수행 상태를 완료로 바꾸지 않는다.

후속 후보는 Snapshot Pagination, 서명 Cursor, 사용자 행동 기반 추천, 카테고리 운영·데이터 무결성 모니터링, 실측 후 인덱스 개선이다. 실제 필요가 발생한 별도 작업에서 설계한다.

선택적 설계 이해 확인: “왜 Fingerprint 집합과 Query 집합이 같아야 하는가?”, “왜 관심사 PUT 성공 뒤 invalidate만으로는 충분하지 않은가?”를 자신의 언어로 설명해 본다. 학습 질문의 답변을 구현 진행의 선행 승인 조건으로 삼지 않는다.

## 17. 변경 이력

| 버전 | 날짜 | 내용 |
| --- | --- | --- |
| v1.0 | 2026-10-06 | 사용자 승인 계약 동결, 11개 관점 Review, 구현 검증 항목과 기존 문서 구체화 관계 기록 |

