# Trend Leader 전체 트렌드 목록 조회 설계 확정안 v1.0

> 상태: 설계 확정 / 구현 및 실행 검증 전
> 확정일: 2026-09-26 (Asia/Seoul)
> Repository: Trend-Leader-capstoneProject/feature
> 기준 브랜치: dev
> 작성 시 재확인한 HEAD: 8c934018b644934aa188501140fecb16d0213051
> 대상: GET /api/trends 및 최신 트렌드 목록 화면

## 0. 문서 사용 기준

사용자가 승인한 Final Review의 11개 관점과 두 주의사항을 구현 기준으로 고정한다. 문서 동결은 구현 완료나 테스트 통과를 뜻하지 않는다. 구현 시작 시 최신 브랜치, HEAD, 작업 트리, 실제 코드와 설치 버전을 다시 확인한다.

기준 문서:

- `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`
- `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`
- `docs/designs-feature/관심사 분류/Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.1.md`
- 인증 세션 관리 및 로그아웃의 최신 확정안, 실제 AuthProvider와 Navigation

현재 채팅 결정과 이 기능 확정안을 우선 적용한다. 실제 코드와 충돌하면 목표 계약과 구현 상태를 구분해 보고한다. 첨부된 과거 `schema_decisions.md`의 대표 Category 규칙 및 category_name 전역 UNIQUE를 복원하지 않는다. 최신 Taxonomy에 따라 `is_primary`는 이번 조회에서 사용하지 않고, Trend는 세부분류에 매핑한다.

### 0.1 작성 시 확인한 사실과 확인 범위

| 확인 대상 | 확인 내용 |
| --- | --- |
| remote dev | 위 HEAD와 tree 확인. 로컬 사용자 작업 트리는 접근·검증하지 않음 |
| Trend ORM | summary/thumbnail_url nullable, last_collected_at non-null, status/last_collected_at 인덱스 |
| TrendSource ORM | source_title nullable, source_url non-null, collected_at non-null. Trend마다 Source가 최소 1개라는 제약은 없음 |
| Category ORM/Taxonomy | 2단계 도메인 정책, 부모 관계, nullable category_code, 대표 Category 미사용 |
| Category Router | 기존 GET /api/categories는 활성 대분류·세부분류 계층 조회용 |
| 공통 오류 처리 | ApplicationException.data 전달, 422 공통 envelope, 예기치 않은 오류 500 |
| DB Session | 요청 단위 Session, 예외 시 rollback, finally에서 close |
| Navigation | AuthNavigator: Login/Signup. AppNavigator: Main/InterestEdit |
| Frontend 의존성 선언 | @tanstack/react-query ^5.101.2. 실제 설치·lock 버전과 옵션 동작은 구현 시 확인 |

이번 작업에서는 DB에 접속하거나 앱을 실행하지 않았다. 파일 트리상 전용 Trend 목록 계층은 확인되지 않았으며, 실제 Router 등록과 호출 관계는 구현 착수 시 다시 추적한다.

## 1. 문제, 범위, 성공 조건

사용자는 로그인 여부와 관계없이 최근에도 관측되는 트렌드를 훑어보고, Category로 좁히며, 대표 출처의 원문을 열 수 있어야 한다.

포함 범위:

- 공개 GET /api/trends, ACTIVE 목록, 최신 수집 시각 정렬
- Cursor Pagination, limit, 대분류·세부분류 필터
- 기본 summary/thumbnail, 전체 Category, 최신 Source 1개
- 무한 스크롤, 새로고침, loading/error/empty, 원문 외부 이동
- 비로그인·로그인 진입, 기존 인증 정책 보존
- Demo Trend Seed, Backend/Frontend 테스트와 실기기 검증

제외 범위:

- 맞춤 추천, 검색, 상세 API 및 상세 데이터 화면
- 북마크 저장/해제/상태, 실제 Rank·점수·순위 변동
- 외부 수집 Pipeline, AI Provider 호출·분석 생성
- Refresh Token, 새 GUEST 인증 상태, 전역 인증 재설계
- Snapshot Feed, 선제적 스키마/인덱스 변경

성공 조건은 위 범위의 API와 화면이 함께 동작하고 §12의 완료 기준을 충족하는 것이다. 관련 요약 버튼의 실제 상세 연결은 후속 기능이다.

## 2. 핵심 결정과 대안

| 항목 | 채택 | 대안과 트레이드오프 |
| --- | --- | --- |
| 최신성 | last_collected_at DESC, trend_id DESC | 최초 발견순은 재관측 이슈를 위로 올리지 못함. 실제 Rank는 별도 데이터·정책 필요 |
| 페이지 | Cursor, 기본 20, 1~50 | Offset보다 경계 키로 다음 범위를 표현하기 적합. 임의 페이지 번호 이동은 제공하지 않음 |
| 일관성 | 실시간으로 바뀌는 목록 허용 | Snapshot은 세션 간 고정 상태·이력 설계 비용이 있음 |
| 출처 | 최신 Source 1개, nullable 방어 | non-null 즉시 강제는 기존 데이터 보장과 불일치. Source 없는 Trend를 숨기는 정책도 이번에는 채택하지 않음 |
| 조회 | Trend Page 후 Source/Category 일괄 조회 | 모든 1:N 관계 JOIN 후 LIMIT은 행 증식으로 Trend 단위 페이지가 흐트러질 수 있음 |
| Category | 전체 반환, UI 가로 스와이프 | 서버가 3개로 자르면 나머지 Category를 보여줄 수 없음 |
| 비로그인 | Public 화면을 기존 AuthNavigator에 추가 | 새 인증 상태는 이 기능에 필요하지 않음 |
| 표시 번호 | 화면 누적 항목의 index + 1 | API rank 필드는 실제 순위로 오해될 수 있음 |

도메인 책임은 Service에, 조회 최적화는 Repository에, 표현과 스와이프는 UI에 둔다. 조회용 DTO 조립에 불필요한 Aggregate나 Domain Event를 도입하지 않는다.

## 3. API 계약

### 3.1 요청

`GET /api/trends` — 인증 불필요. 로그인 여부와 관계없이 `publicApiClient` 사용.

| Query | 타입 | 기본값 | 규칙 |
| --- | --- | --- | --- |
| cursor | string | 생략 | 서버가 발급한 opaque cursor. 빈 문자열 포함 잘못된 값은 400 |
| limit | integer | 20 | 1 이상 50 이하. 범위·타입 오류 422 |
| category_id | integer | 생략 | 양수. 활성 대분류 또는 활성 세부분류. 형식 오류 422 |

```http
GET /api/trends?limit=20
GET /api/trends?category_id=12&limit=20&cursor=<opaque-cursor>
```

검색어·정렬 방식·북마크 여부 Query는 추가하지 않는다.

### 3.2 성공 응답

HTTP 200, message는 `전체 트렌드를 조회했습니다.`로 고정한다. 아래 ID·문구·URL은 설명용 가상 값이다. timestamp 예시는 DB 저장 시간대 확정의 근거가 아니다(§13 참조).

```json
{
  "success": true,
  "statusCode": 200,
  "message": "전체 트렌드를 조회했습니다.",
  "data": {
    "items": [
      {
        "trend_id": 101,
        "title": "갤럭시 AI 기능 화제",
        "summary": "갤럭시 AI 기능이 최근 관심을 받고 있습니다.",
        "thumbnail_url": "https://example.com/image.jpg",
        "last_collected_at": "2026-09-26T15:30:00",
        "categories": [
          {
            "category_id": 42,
            "category_name": "모바일·스마트폰",
            "parent": {
              "category_id": 6,
              "category_code": "IT_DIGITAL",
              "category_name": "IT/디지털"
            }
          }
        ],
        "latest_source": {
          "source_id": 501,
          "platform": "YOUTUBE",
          "source_title": "갤럭시 AI 기능 공개",
          "source_url": "https://example.com/source"
        }
      }
    ],
    "next_cursor": "<opaque-cursor>",
    "has_next": true
  }
}
```

| 필드 | 타입 / null | 의미 |
| --- | --- | --- |
| items | array, non-null | Trend별 1개, 비어 있으면 [] |
| trend_id | integer, non-null | Trend 식별자 |
| title | string, non-null | 표시 제목 |
| summary | string 또는 null | trends.summary. AI 분석 요약과 다름 |
| thumbnail_url | string 또는 null | 대표 이미지 |
| last_collected_at | datetime string, non-null | 가장 최근 관측 시각 |
| categories | array, non-null | 연결된 Category 전체. 없으면 [] |
| categories[].category_id/name | integer/string, non-null | 연결된 세부분류 |
| categories[].parent | object | 정상 2단계 매핑에서 부모 대분류 |
| parent.category_id/name | integer/string, non-null | 부모 식별자·표시명 |
| parent.category_code | string 또는 null | ORM nullable 계약 보존. 정상 Master 대분류는 코드 있음 |
| latest_source | object 또는 null | 가장 최근 Source 1개 |
| latest_source.source_id | integer, non-null | 출처 식별자 |
| latest_source.platform | string, non-null | 현재 enum: GOOGLE/YOUTUBE/SNS/ETC |
| latest_source.source_title | string 또는 null | 출처 제목 |
| latest_source.source_url | string, non-null | 출처가 존재할 때 원문 URL |
| next_cursor | string 또는 null | 다음 페이지가 없으면 null |
| has_next | boolean | 다음 페이지 존재 여부 |

초기 후보의 `source` 대신 최종 필드명 `latest_source`만 사용한다. `source`를 별칭으로 함께 반환하지 않는다.

빈 목록도 200이며 `items=[]`, `next_cursor=null`, `has_next=false`다. nullable 필드는 생략하지 않고 null로 반환한다.

반환하지 않는 값: normalized_title, status, first_collected_at, updated_at, rank/rank_delta/score, AI one_line_summary/reason_text/detail_text/related_keywords, bookmark state, is_primary.

### 3.3 오류

| 상황 | HTTP | data.reason |
| --- | --- | --- |
| 잘못된 Cursor, 지원하지 않는 Cursor 버전, 필터 문맥 불일치 | 400 | INVALID_CURSOR |
| 비활성 또는 2단계 정책상 필터 불가능한 Category | 400 | CATEGORY_NOT_AVAILABLE |
| 존재하지 않는 Category ID | 404 | CATEGORY_NOT_FOUND |
| limit/category_id의 타입·범위 오류 | 422 | 기존 공통 ValidationErrorData 형식 사용 |
| 예기치 않은 서버 오류 | 500 | 기존 공통 오류 처리 사용 |

400/404는 기존 ApplicationException 계열과 공통 envelope를 사용한다. 사용자 메시지는 오류 구분의 키로 쓰지 않는다.

```json
{
  "success": false,
  "statusCode": 400,
  "message": "페이지 정보가 올바르지 않습니다.",
  "data": { "reason": "INVALID_CURSOR" }
}
```

위 오류 message는 표현 예시이며 분기 계약은 HTTP와 data.reason이다. 401/403/409를 목록 기능의 업무 오류로 추가하지 않는다. OpenAPI의 400/404/422 응답과 실제 Handler 응답을 맞춘다.

## 4. 관점 1 — Category 필터와 반환

1. 생략하면 Category 조건 없는 전체 ACTIVE Trend를 조회한다.
2. 활성 대분류는 활성 직계 세부분류 ID로 확장하고 하나 이상 매칭되는 Trend를 조회한다.
3. 활성 세부분류는 해당 ID로 직접 매칭한다.
4. 같은 Trend가 여러 Category에 매칭돼도 한 번만 반환한다.
5. 활성 하위 Category가 없거나 매칭 Trend가 없으면 정상 빈 목록이다.

필터용 Category 검증과 응답용 Category 목록은 구분한다. 응답은 실제 연결된 Category 전체를 반환하며, 비활성이라는 이유만으로 연결 정보를 잘라내지 않는다. 필터에 맞지 않는 다른 Category도 해당 Trend의 연결 정보로 반환한다. UI는 서버가 반환한 목록을 가로 스와이프로 보여준다.

필터 선택지는 기존 Category 조회를 재사용하며 ID를 하드코딩하지 않는다. `기타`처럼 이름이 중복될 수 있으므로 식별과 UI 문맥에 부모 정보를 사용한다. 응답용 Chip을 누르면 바로 필터되는 기능은 이번 필수 범위가 아니다.

정상 매핑은 세부분류와 부모 1개다. 과거 데이터의 대분류 직접 매핑, 3단계 매핑, 부모 비활성 처리의 미정 경계는 §13에서 별도 확인한다. 이를 정상 데이터인 것처럼 DTO를 만들어 감추지 않는다.

## 5. 관점 2 — Cursor와 변경 가능한 목록

정렬은 `last_collected_at DESC, trend_id DESC`다. 다음 페이지의 경계 조건은 다음 의미를 가진다.

```text
last_collected_at < cursor.last_collected_at
OR
(last_collected_at = cursor.last_collected_at AND trend_id < cursor.trend_id)
```

Cursor 내부에는 version, last_collected_at, trend_id, category_id 문맥을 포함한다. 필터 생략은 일관된 null 문맥으로 정규화한다. Client는 Cursor를 해석·수정하지 않는다. limit은 위치의 의미를 바꾸지 않으므로 Cursor 필터 문맥에 포함하지 않는다.

해독 실패, 필수 값 누락, 잘못된 타입·시각·ID, 미지원 버전, 요청 category_id 불일치는 INVALID_CURSOR다. Cursor의 값으로 SQL 문자열을 조립하지 않는다. opaque는 암호화나 위변조 방지 보장을 뜻하지 않는다. codec·입력 길이 한도·서명 필요성은 현재 공통 유틸을 검토해 구현 기록에 남긴다.

조회는 limit+1개의 Trend를 먼저 구한다. 초과 1개는 has_next 판정에만 사용하고, 반환할 마지막 Trend의 정렬 키로 next_cursor를 만든다. 초과 행으로 Cursor를 만들면 한 건을 건너뛰므로 금지한다. has_next=false이면 next_cursor=null이다.

경계 Trend가 삭제되더라도 Cursor의 값으로 범위를 조회할 수 있어야 하며, 경계 행의 재조회 성공을 필수 전제로 삼지 않는다.

### 5.1 허용하는 live-feed 동작

페이지 사이에서 last_collected_at이 갱신되면 아직 보지 않은 Trend가 Cursor 앞쪽으로 이동해 해당 스크롤에서 빠질 수 있다. 새로고침 또는 재진입 후 새 조회로 확인한다. 모든 페이지가 동일 시점의 목록이라는 보장은 하지 않는다.

Frontend의 중복 제거가 필요하면 trend_id 기준으로 처리하지만, 이는 누락을 복구하거나 Snapshot을 만드는 기능이 아니다. 현재 스키마에 이력 없이 시각 상한만 붙이는 것으로 Snapshot 문제가 해결됐다고 판단하지 않는다.

## 6. 관점 3 — Nullable와 원문

| 상태 | 화면 동작 |
| --- | --- |
| summary=null | 요약 영역 생략 |
| thumbnail_url=null 또는 이미지 로드 실패 | 기존 디자인 시스템 기반 Placeholder |
| source_title=null | 플랫폼명과 원문 보기로 표현 가능 |
| latest_source=null | 출처 없음 표시, 원문 이동 액션 제공하지 않음 |
| categories=[] | Category 영역 생략 |

Source 선정은 `collected_at DESC, source_id DESC`다. 가장 최근 Source만 반환한다. AI 요약 유무로 Source를 선택하지 않는다.

정상 Demo·향후 수집 데이터에는 Source가 있어야 한다. 다만 기존 데이터에서 Source가 없다는 이유로 목록 전체를 500으로 만들지 않는다. nullable 계약을 non-null로 바꾸려면 §14의 해결 절차를 거친다.

원문 이동은 외부 URL 열기 결과와 실패를 처리한다. DB non-null만으로 URL 유효성이나 안전한 스킴을 보장한다고 가정하지 않는다. 외부 웹 원문용 http/https를 검증하고 실패 안내를 제공한다. 실제 API는 현재 React Native 버전에서 확인한다.

## 7. 관점 4·5 — Repository, Batch 조회, N+1

조회 순서:

1. 필요 시 Category 검증 및 필터 범위 조회.
2. ACTIVE, Category EXISTS, Cursor 조건으로 limit+1개의 Trend 조회.
3. 실제 응답할 Trend ID들에 대한 최신 Source를 일괄 조회.
4. 동일 ID들의 Category와 Parent를 일괄 조회.

Source와 Category를 동시에 다대다로 펼친 결과에 LIMIT을 적용하지 않는다. Service/응답 직렬화에서 Trend별 lazy relationship 접근으로 추가 SQL을 유발하지 않도록 한다. 비어 있는 페이지는 불필요한 관련 조회를 생략한다.

최신 Source 조회 대안은 trend_id별 window ranking 또는 동등한 상관 조회다. 실제 SQLAlchemy·MariaDB 버전, 실행 계획, 명료성을 기준으로 구현에서 선택하고 근거를 남긴다. 공개 API 계약을 바꾸는 선택은 아니다.

항목 수에 비례해 Query 수가 늘지 않도록 검증한다. 테스트가 SQL 문자열 전체나 사소한 호출 순서를 고정하지 않게 하고, 조회 수 상한·결과 정확성을 확인한다.

새 인덱스는 자동 추가하지 않는다. 기존 인덱스와 실제 Migration을 확인한 뒤 MariaDB EXPLAIN으로 정렬, 필터, 최신 Source 조회를 점검한다. 필요성이 입증되면 별도 Migration 영향과 함께 제안한다.

## 8. 관점 6 — 계층 책임과 Transaction

| 계층 | 책임 |
| --- | --- |
| Router/Schema | Query 형태·범위 검증, Dependency, Service 호출, 공통 응답·OpenAPI |
| Service | 필터 의미와 업무 오류, Cursor 문맥 검증, Page/관련 데이터 조합, DTO, has_next/next_cursor |
| Cursor helper | codec·형식 검증 같은 순수 변환. HTTP나 DB 접근에 의존하지 않음 |
| Repository | 정렬·경계·EXISTS·Batch SQL, DB 결과 조회 |
| 공통 Handler/Dependency | 업무 오류 envelope, 예외·Session 정리 |

이 기능은 쓰기를 하지 않는다. 업무용 commit, FOR UPDATE, 관심사 수정용 1020 재시도 정책을 추가하지 않는다. 단, 읽기 전용을 Transaction 부재로 해석하지 않는다. 기존 요청 단위 Session의 예외 rollback과 close는 보존한다. 요청 내 Batch Query와 페이지 간 여러 HTTP 요청의 일관성은 다른 문제다.

Source 존재를 보장하는 미래의 생성·삭제 규칙은 수집/관리 유스케이스가 소유한다. 목록 Service가 조회 중 누락 Source를 생성하거나 데이터 복구를 수행하지 않는다.

## 9. 관점 7 — Frontend Query

새 기능은 기존 구조에 맞춰 `frontend/src/features/trend/` 아래 api, hooks, types, components, screens, queryKeys로 분리한다. 아직 없는 파일명·함수 시그니처는 구현 사실로 단정하지 않는다.

- Key의 의미: `["trends", "list", { categoryId, limit }]`
- 필터 없음은 한 값으로 정규화한다.
- Cursor는 Query Key가 아닌 Infinite Query의 pageParam으로 다룬다.
- 첫 pageParam은 null 의미, 요청에서는 cursor를 생략한다.
- 다음 pageParam은 next_cursor를 사용하고 마지막 페이지에서는 추가 요청을 중단한다.
- fetch 중 중복 onEndReached 호출과 새로고침 동시 실행을 제어한다.

Category 전환 시 이전 필터의 Cursor를 재사용하지 않는다. 이미 방문한 Query Key에는 Cache가 남을 수 있으므로 Key 변경만으로 언제나 빈 Cache와 1페이지 조회가 보장된다고 설명하지 않는다. Pull-to-refresh·재진입·기존 필터 재선택 시 첫 페이지부터 새 목록을 구성하는 동작을 구현·검증한다. 구체적인 Cache reset/refetch 방식은 설치된 v5 버전에서 확인한다.

여러 페이지는 화면에서 합쳐 표시하며 안정적인 key는 trend_id다. 화면 번호는 최종 표시 배열 index+1이고 필터 전환 후 1부터 시작한다. 검색어·사용자 ID·토큰을 이 Public 목록 Key에 미리 추가하지 않는다.

첫 로딩 오류는 전체 오류·재시도로, 추가 페이지 오류는 기존 목록을 유지한 footer 재시도로 구분한다. INVALID_CURSOR는 동일 Cursor를 자동으로 반복 요청하지 않고 처음부터 다시 불러오는 경로를 제공한다. Category 오류는 선택지를 갱신하고 전체 목록으로 돌아갈 수 있게 한다.

## 10. 관점 8·9 — UI와 Navigation

| 구성 요소 | 책임 |
| --- | --- |
| LatestTrendScreen | Filter, Query 연결, loading/error/empty, 새로고침/추가 조회, Navigation 이벤트 |
| TrendCard | 표시 번호·제목·기본 요약·이미지·시각·Category 가로 스크롤, Source 영역 조립 |
| SourceCard | 플랫폼·출처 제목·원문 보기 callback |
| 향후 Trend 상세 액션 | trend_id로 관련 요약/상세 이동. 이번에는 상세 API 구현 안 함 |

Category는 화면 너비에 따라 한 번에 약 2~3개가 보이고 가로 스와이프로 나머지를 확인한다. 글자 크기·접근성 설정 때문에 정확히 3개가 항상 보여야 한다는 조건은 두지 않는다. Card는 직접 API를 호출하지 않는다.

원문 보기와 관련 요약 보기는 디자인상 같은 영역에 놓일 수 있다. 그러나 전자는 Source, 후자는 Trend의 책임이다. 이번 버전에서 동작하지 않는 상세 버튼을 활성 상태로 노출하지 않는다. 기본은 숨김이며 디자인상 유지가 필요하면 명확한 준비 중 표시로 처리한다.

Navigation 목표:

- AuthNavigator: Login, Signup에 LatestTrend 추가. Login에서 비로그인 최신 이슈 보기 진입.
- AppNavigator: Main, InterestEdit에 LatestTrend 추가. Main에서 진입.
- 같은 화면을 재사용하되 특정 Stack 전용 props에 결합되지 않도록 타입을 확인한다.
- GUEST Auth State를 만들지 않는다. Session Restore, 401 정리, 로그아웃, 관심사 Onboarding 분기를 보존한다.
- Public 목록 오류로 인증 세션을 종료하지 않는다.

## 11. 관점 10 — 테스트 및 실제 Acceptance

### 11.1 Backend

| 수준 | 핵심 검증 |
| --- | --- |
| Repository/MariaDB 통합 | ACTIVE만, HIDDEN 제외, 시각/ID 내림차순, 동률, Cursor 경계, 중복 없는 Category 매칭 |
| Repository/MariaDB 통합 | 최신 Source와 동률 source_id, Category/Parent 전체 조회, 빈 목록, N+1 방지 |
| Service/순수 로직 | Cursor round-trip·오류·문맥 불일치, has_next/next_cursor, nullable 조립 |
| Service | 대/세부분류, 미존재 404, 비활성/비정상 400, 하위 없음 200 |
| API 계약 | 무인증 200, 기본 20, limit=1/50, 0/51/타입 오류 422, category_id 오류, 공통 envelope |
| API 계약 | 응답 이름 latest_source, null·빈 배열, 종료 Cursor, OpenAPI 오류 구조 |

페이지 검증은 데이터 0개, limit-1개, limit개, limit+1개를 포함한다. 동일 timestamp의 여러 Trend에서 누락·중복이 없는지 확인한다. Source 없는 Trend가 목록 전체 오류를 만들지 않는지 검증한다. 페이지 사이 재관측으로 이동하는 사례는 §5.1의 허용된 의미를 재현한다.

Service 분기와 Cursor 순수 로직은 TDD를 우선한다. Repository는 실제 MariaDB 조회 결과가 핵심이다. Mock만으로 SQL의 정확성을 완료 판정하지 않는다.

### 11.2 Frontend

- publicApiClient 사용, 첫 페이지/다음 Cursor, 마지막 페이지 호출 중단.
- 페이지 합치기·번호 1~N, 중복 요청 제어, 필터 변경과 느린 이전 응답.
- 방문했던 필터 Cache 재사용 및 refresh/reentry의 첫 페이지 재시작.
- 첫 로딩/빈 목록/전체 오류/추가 페이지 오류·재시도.
- nullable summary/thumbnail/source_title/latest_source, 이미지 실패.
- 가로 Category 목록, 원문 callback·URL 열기 실패.
- 비로그인·로그인 진입, 공통 401/세션/로그아웃/관심사 흐름 회귀.

### 11.3 실기기 Acceptance 기록

각 항목은 환경, 절차, 기대, 실제 결과, PASS/FAIL/미실행을 기록한다.

1. 비로그인 최신 목록 진입 → 로그인 요구 없이 조회.
2. 로그인 Main 진입 → 동일 Public 목록 조회.
3. ACTIVE 25개 → 첫 페이지 20, 다음 5, 이후 요청 중단.
4. Pull-to-refresh·재진입 → 갱신된 최신 목록 확인.
5. 대/세부분류 전환 → 해당 목록, 순번 1부터, 이전 Cursor 혼입 없음.
6. 세로 스크롤과 가로 Chip 스와이프 → 제스처 충돌 없음.
7. 원문 이동·앱 복귀 → 정상 동작, 외부 열기 실패 안내.
8. Android Back → 진입 경로에 맞는 복귀.
9. 네트워크 끊김·복구 → 기존 목록 유지와 재시도 가능.
10. 로그아웃·토큰 만료·Onboarding → 기존 인증 정책 유지.

## 12. 관점 11 — Demo Seed, 구현 순서, 완료 기준

### 12.1 Seed

Category Master Seed, Demo Trend Seed, pytest Fixture는 분리한다. Demo는 명시적으로 실행하는 개발용 데이터이며 앱 시작·일반 Migration에서 자동 실행하지 않는다.

Pagination 검증용 기본 데이터는 **Source가 있는 ACTIVE 25개 + 별도 HIDDEN 1개 이상**으로 한다. 총 25개 안에 HIDDEN을 섞어 20+5 시나리오가 달라지지 않게 한다.

복수 Category, 복수 Source, 동일 Trend 시각, 동일 Source 시각, nullable summary/thumbnail/source_title을 포함한다. Source 없는 방어 사례는 독립 Fixture로 검증한다. AI 분석과 Rank Snapshot은 만들 필요가 없다.

Category는 대분류 code와 부모+세부분류 이름으로 식별하며 ID를 고정하지 않는다. Master가 없거나 식별이 모호하면 명확히 실패하고 임의 Category를 추가하지 않는다. 재실행 시 중복 방지, 한 실행의 원자성, 기존 비-Demo 데이터 보존을 검증한다. 개발 환경 차단 조건과 안전한 Demo 식별 방식은 기존 설정·Seed 구조를 확인한 뒤 기록한다.

### 12.2 구현 순서

| 단계 | 산출 및 검증 |
| --- | --- |
| 0. 현재 상태 | HEAD/작업 트리/버전/설계 차이 확인, §13의 계약 경계 확정 |
| 1. Backend 계약 | Schema, Cursor, Service 규칙의 행동 테스트와 구현 |
| 2. 조회·연결 | Repository 통합, Dependency/Router 등록, 실제 OpenAPI 계약 |
| 3. 개발 데이터 | Demo Seed, MariaDB 목록/필터/Pagination 확인 |
| 4. Frontend 데이터 | Type/API/Key/Infinite Hook, 상태·Cache 테스트 |
| 5. 화면·진입 | Screen/Card/원문/Navigation, 기존 인증 회귀 |
| 6. 완료 | 실기기, 관련 전체 회귀, 문서/API 명세, diff 검토 |

테스트 명령은 실제 설정에서 확인한다. 사용자에게 전달할 명령은 Windows PowerShell 문법을 사용한다. Bash 줄 연속 `\`를 붙이지 않는다.

### 12.3 기능 완료 체크

- [ ] API/Backend/Frontend/실제 응답 계약 일치
- [ ] 정상·실패·경계 조건의 자동 테스트 및 정적 검사 통과
- [ ] MariaDB 쿼리 결과·실행 계획 검토
- [ ] 실기기 Acceptance 수행 및 결과 기록
- [ ] 인증·관심사 기존 기능 회귀 검증
- [ ] Demo와 Master/테스트 데이터 분리
- [ ] §13 확인 항목 해소 또는 별도 합의·문서 기록
- [ ] §14 주의사항의 상태와 실제 동작 일치
- [ ] API 명세·구현 안내·최종 diff 점검

문서만 바꾼 현재 단계에서는 앱 테스트를 실행·통과했다고 기록하지 않는다.

## 13. 구현 착수 시 확인해야 할 경계

아래는 기존 Final Review에서 확정되지 않았거나 코드·환경 확인이 필요한 세부 사항이다. 핵심 제품 결정을 다시 질문할 이유로 사용하지 않는다. 확인 가능한 항목은 코드로 해소하고, 새로운 계약 판단이 필요한 항목만 좁혀 결정한다. 실제 동작을 확정할 때 이 절과 해당 본문을 함께 갱신한다.

| 항목 | 필요한 근거 / 처리 |
| --- | --- |
| 시각 의미 | ORM DateTime만으로 UTC/KST가 결정되지 않음. DB/session/server 설정, 저장 경로, 직렬화 확인 후 응답·Cursor·UI 시간대와 정밀도를 기록. 임의 Z 첨부 금지 |
| 비활성 부모 + 활성 자식 필터 | Final Review는 요청 Category 활성만 명시. 기존 Category 조회 정책과 정합성을 확인하고 이 조합의 200/400을 계약·테스트에 확정 |
| 과거 비정상 Category 매핑 | 대분류 직접 매핑/3단계/부모 이상 데이터 존재 여부 확인. 발견 시 정리 또는 방어 DTO 정책을 합의. 전체 반환 약속을 조용히 필터링으로 바꾸지 않음 |
| Category 표시 순서 | 현 sort_order 규칙을 확인하고 부모/자식 동률 보조 ID까지 결정적으로 정렬. 대표 Category 선정으로 해석하지 않음 |
| Cursor codec | 기존 helper, 최대 입력 길이, 시간 round-trip, 변조 검증 필요성 확인. opaque를 보안 보장으로 표기하지 않음 |
| Query 재시작 | 설치·lock 버전 확인 후 refresh/reentry/Cache 재사용 동작을 테스트로 고정 |
| Demo 경계 | 실제 환경 설정 이름, 실행 명령, 재실행 식별·실패 rollback 확인. 존재하지 않는 환경변수/명령 추정 금지 |

이 항목들은 문서 전체를 미확정으로 되돌리지 않지만, 관련 구현과 완료 판정 전에 해소해야 한다.

## 14. 주의사항 추적과 해결 시 문서 갱신

### TL-LIST-001 — Source 필수라는 제품 의도와 데이터 보장 차이

- 상태: **OPEN — v1.0에서 nullable 방어를 승인함**.
- 현재 결정: latest_source는 object 또는 null. 정상 생성 데이터는 Source 포함.
- 근거: TrendSource→Trend FK는 존재하지만 Trend→Source 최소 1개 제약은 없음.
- 후속 책임: 수집/관리의 생성·활성화·Source 삭제 경로 설계.
- 해결 판정: 모든 ACTIVE 생성·활성화 경로 및 마지막 Source 삭제 경로가 규칙을 지키고, 기존 데이터 점검·정비와 실패/동시성 테스트로 검증됨.
- 단순히 Demo에 Source를 채운 것만으로 RESOLVED로 바꾸지 않는다.
- Source 존재와 안전한 URL은 별도 조건으로 검증한다.
- 생성 불변조건이 해결돼도 API nullable 제거는 별도 계약 변경이다. 호환성을 위해 nullable을 유지할 수도 있으며 이유를 기록한다.

### TL-LIST-002 — 변경 가능한 정렬 키로 인한 페이지 간 누락

- 상태: **ACCEPTED LIMITATION — v1.0 live-feed 동작으로 승인함**.
- 현재 결정: 재관측으로 Cursor 앞에 이동한 항목은 현재 스크롤에서 누락될 수 있고 새 조회로 확인한다.
- 후속 검토 계기: 전체 목록을 한 시점 기준으로 빠짐없이 탐색해야 하는 요구가 생김.
- 해결 후보: 불변 정렬 키로 의미 변경, 이력·Snapshot 기반 목록 또는 동등한 검증 가능한 구조.
- 해결 판정: 합의한 일관성 수준이 갱신·동일 시각·신규/삭제·필터 조건에서도 충족되고 회귀·동시성 테스트로 입증됨.
- 중복 제거, Pull-to-refresh, timestamp 상한만으로 RESOLVED라고 기록하지 않는다.

### 14.1 해결과 동시에 수행할 문서 작업

후속 구현에서 위 항목을 건드리면 동일 PR 또는 변경 묶음 안에서 다음을 수행한다.

1. 항목 ID와 상태, 해결 날짜, 연결 commit/PR, 검증 증거를 갱신한다.
2. 이전 결정·새 결정·변경 이유·마이그레이션/호환성 영향을 이력에 남긴다.
3. 본문의 API 타입, Cursor 의미, UI fallback, 테스트 Matrix, 완료 기준을 함께 바꾼다.
4. Backend Schema/OpenAPI/API 명세와 Frontend Type/Hook/Screen을 함께 확인한다.
5. 단순 설명 보강은 patch 버전, 계약 의미 변화는 그 영향에 맞춰 문서 버전을 올린다. 문서 버전과 API 버전은 같은 개념이 아니다.
6. 기존 승인 내용과 해결 근거를 삭제하지 않는다. 새 버전을 만들면 최신 기준을 프롬프트에서도 갱신한다.

이 문서는 미래 변경을 자동 감시하지 않는다. 해당 후속 작업의 완료 조건에 위 절차를 포함하여 즉시 반영한다.

### 14.2 갱신 기록 양식

| 날짜 | 항목 ID | 이전 → 새 상태 | 변경 이유·새 결정 | 코드/문서 영향 | 검증 증거 | commit/PR |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-26 | TL-LIST-001 | 신규 → OPEN | nullable 방어 승인 | API/Source fallback | 설계 및 ORM 확인, 실행 전 | 문서 커밋 참조 |
| 2026-09-26 | TL-LIST-002 | 신규 → ACCEPTED LIMITATION | live-feed 한계 승인 | Cursor/refresh/테스트 | 설계 검토, 실행 전 | 문서 커밋 참조 |

## 15. 변경 이력과 설계 소유권

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-09-26 | 승인된 Final Review 11개 관점 동결. 주의사항 ID·해결 기준·동시 문서 갱신 절차 추가. 실제 코드 확인과 미확인 경계 분리 |

추후 자신의 언어로 점검할 질문:

1. Cursor를 사용해도 last_collected_at이 바뀌면 누락이 생기는 이유와, 우리 MVP가 허용한 범위는 무엇인가?
2. Source 최소 1개 규칙은 어느 쓰기 경로가 보장해야 하며, 조회 API의 nullable 제거와 왜 별도로 검토해야 하는가?

설명 숙련도는 기능 완료 여부와 별도 축으로 기록한다.
