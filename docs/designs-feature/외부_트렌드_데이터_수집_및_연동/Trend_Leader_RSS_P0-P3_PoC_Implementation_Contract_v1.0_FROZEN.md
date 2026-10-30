# Trend Leader — RSS Parser·Normalizer·Candidate Validator PoC 구현 계약 v1.0 (설계 확정안)

> **상태: FROZEN — P0~P3 합성 Fixture 기반 순수 기술 PoC 구현 계약 (P4/운영은 미동결)**  
> 작성·검토: 2026-10-30 (Asia/Seoul)  
> 기준 Repository: `Trend-Leader-capstoneProject/feature`, `dev` HEAD `723294bd6a702c2a1bdb4d2618fa23b7332f01d0` (읽기 전용 확인)  
> 선행 자료: `Trend_Leader_AI_Development_Guidelines.md` v1.2, Category Taxonomy v1.0.1, 전체 Trend 목록 v1.0.14, 개인화 Trend 목록 v1.0/v1.1, 외부 실데이터 사전 설계 기록 v0.1 (NOT FROZEN), 2026-10-30 사용자 수동 RSS 관찰 화면 2건  
> **변경 통제:** 사용자가 2026-10-30 동결 직전 최종 검토·반영을 요청하여, 11개 관점 검토 후 안전성·결정성 보완을 포함한 P0~P3 기술 계약을 동결했다. 본 문서의 동결 당시에는 GitHub·Notion·DB·프로젝트 소스에 반영하지 않았다. P4 이후 Writer 및 외부 이용 허가는 동결 대상이 아니다.

## 0. 결정 및 범위 요약

### 0.1 사용자 명시 결정 (유지)

1. **후보 선별 C안:** RSS 검색어 예비 판정 → 기사 메타데이터 교차 검증 → 활성 Child Category 확정.
2. **1차 제외 A안:** 명백히 관심 범위 밖인 경우만 조기 제외. 모호하거나 사전에 없는 주제는 2차 검증.
3. **출처 도메인 C안:** 승인 도메인은 나머지 검증 대상, 미확인 도메인은 보류, 차단 도메인은 채택 불가.
4. **MVP A안:** 11월 중순까지 적법하게 자체 작성·확보한 실제 Trend를 기존 전체·개인화 목록에 연결하는 것이 우선. Google RSS 자동 발굴·게시 기능은 이용 권한 검증에 종속.
5. 최초 PoC는 **수동 관찰 + 독립 작성 Fixture**, 외부 자동 호출/공개 서비스 DB 저장/자동 게시 없음.

### 0.2 동결 효력과 선행 합의

- 본 동결은 **P0~P3의 독립 합성 XML Fixture 기반 구현·테스트 계약**에만 적용한다. Live RSS 다운로더, 원문 URL 접속, 실제 기사 검증, 데이터베이스 Writer, 앱 공개는 동결·구현 권한에 포함하지 않는다.
- 2026-10-30에 사용자가 선택한 **후보 선별 C안 + 1차 보수적 제외 A안**, 기존 출처 도메인 C안, 기존 Frozen Taxonomy·조회 계약의 우선순위를 보존한다.
- 이번 최종 검토로 추가한 보안·판정 우선순위·소스별 문제 기록 규칙은 P0~P3 구현의 **구속력 있는 테스트 계약**이다. 수치 상한과 Normalizer 세칙은 §4~§5에 명시된 값으로 동결한다.
- 본 문서에서 `P4 후속`, `추가 검증`, `미확정`이라 명시한 정책(실제 외부 이용 허가, 운영 도메인 목록, DB Writer, 기존 `HIDDEN` 처리 등)은 **동결에 포함되지 않는다**. 별도 승인 없이 현재 기능의 권한이나 범위를 확대하지 않는다.

### 0.3 이번 계약 포함 / 제외

| 포함 (P0~P3) | 제외 (후속 P4+) |
|---|---|
| 안전한 XML 바이트 파싱, 구조·부분 실패 기록 | Google RSS 주기적 HTTP 다운로드 / 스케줄러 |
| RSS 검색어·기사 후보의 보수적 정규화 | 기사 본문 크롤링·리디렉션 추적·외부 AI 분석 |
| 2단계 주제 판정과 메타데이터 수준 관련성 검증 | 실제 기사 본문 사실검증과 게시 사용 권한 대행 판정 |
| 주입된 가상 Category·도메인·주제 규칙 검증 | 실제 Category 조회·DB Writer·Transaction·Migration |
| 독립 합성 Fixture, pytest, Ruff 검증 | 기존 `GET /api/trends*` / Frontend / Demo Seed 수정 |

> **비목표:** P0~P3의 `WOULD_ACCEPT`는 **합성 입력에 대한 기술적 판정**이며, 실제 원문을 방문해 기사 사실을 확인했다는 의미도, Google/NCP/원문 제공자의 저장·게시 허가도 아니다.

## 1. 기존 확정안 및 충돌 관리

- 공개·개인화 목록의 요청·응답·Cursor·ACTIVE 필터·정렬을 보존한다. `summary`, `thumbnail_url`, `latest_source`의 nullable 조회 계약도 변경하지 않는다.
- Trend에는 활성 **세부분류**만 매핑한다. 사용자의 관심사는 대분류이고, 복수 매핑 허용, `is_primary=false` 정책 유지.
- 현재 Frozen Taxonomy/Seed: 대분류 6, Child 38. 기존 합의된 `엔터테인먼트 > 스포츠`는 **미반영**이므로 P0~P3 기본 Category Fixture에서는 기존 세부분류만 사용한다. 실제 스포츠 매핑은 별도 Taxonomy/Seed 개정 후 가능.
- `trends.normalized_title` UNIQUE, `trend_sources`의 `(trend_id, source_key)` UNIQUE는 P4에서 실제 DB와 함께 검증한다. P0의 정규화 결과가 DB 충돌을 완전히 증명하지 않는다.
- **미정리 기존 결정**: 초기 `schema_decisions.md`의 동일 정규화 제목 재수집 원칙(SD-009), Source Key 조합 선택지(SD-011), 대표 Category(SD-012)와 본 채팅의 최신 Writer 정책·Frozen Taxonomy 간 차이는 P4 확정 전 명시적으로 정리한다. P0~P3에서 기존 DB 결정을 암묵적으로 변경하지 않는다.
- `source.platform`이 RSS 발견 플랫폼과 원문 제공자 중 무엇을 뜻하는지는 P4에서 정한다. P0~P3의 출력 모델에는 DB용 `platform`을 강제하지 않는다.
- 외부 실데이터 사전 설계 기록 v0.1의 NCP 무인 게시 회신 대기 문구는 최신 고객지원 회신보다 오래되었다. **NCP의 판단 결과에 영향을 받은 무인 자동 채택·앱 게시는 금지**한다. P0~P3에서는 NCP 데이터를 아예 사용하지 않는다.

## 2. 실측 RSS 구조와 필드 경계

**사용자 수동 관찰로 확인한 사실**: `rss version="2.0"`, `channel/item`, `ht` 네임스페이스 URI `https://trends.google.com/trending/rss`, `item/title`, `pubDate`, `ht:approx_traffic`, `ht:picture`, `ht:picture_source`, 반복 `ht:news_item` 아래 `ht:news_item_title`, `ht:news_item_snippet`, `ht:news_item_url`, `ht:news_item_picture`, `ht:news_item_source`. `description`과 `ht:news_item_snippet`에 빈 값 사례 존재. `pubDate`에 `-0700` 오프셋 확인. 표본 전체 또는 미래 RSS 필드 안정성까지 보증하지 않는다.

| 실측 필드 | P0~P3 취급 | 기존 DB 연결 (P4 후속) |
|---|---|---|
| `item/title` | 검색어 원본, 없거나 공백이면 ItemIssue | 유효할 때 `title`, `normalized_title` 후보 |
| `item/pubDate` | aware datetime 또는 `None` + Warning | `first_collected_at` / `last_collected_at`으로 그대로 사용하지 않음 |
| `ht:news_item_title` | nullable 원문 기사 제목 후보 | 새 Writer 정책상 채택 Source에는 비어 있지 않은 제목 요구 (ORM 자체는 nullable) |
| `ht:news_item_url` | nullable 기사 URL 후보 | 안전성 검증 후 `source_url`, `source_key` 후보 |
| `ht:news_item_source` | nullable 출처명, 도메인 검증 보조 | 현재 별도 매체명 DB 필드 없음 |
| `item/link` | 피드/Google Trends 링크 | 원문 Source로 사용하지 않음 |
| `description`, `ht:news_item_snippet` | 빈 값 허용, 관련성 근거로 의존하지 않음 | `summary` 자동 복제 금지 |
| `ht:approx_traffic` | P0~P3 판정·점수에서 제외 | 공개 ranking/score로 전용 금지 |
| 이미지 관련 필드 | PoC 출력에서 제외 | `thumbnail_url`/이미지 복제에 자동 이용 금지 |

네임스페이스는 `ht` 문자열이 아니라 **URI**로 판별한다. 미지의 선택 필드는 무시할 수 있지만, 필요한 `news_item` 구조의 URI가 달라 인식 불가한 경우 조용히 빈 기사 목록으로 성공 판정하지 않는다.

## 3. 모듈과 의존성

### 3.1 예상 위치 (구현 시 실제 Tree 재검증)

```text
backend/app/external_trends/
  types.py
  rss_parser.py
  normalizer.py
  candidate_validator.py
backend/tests/external_trends/
  fixtures/valid_feed.xml
  fixtures/missing_fields.xml
  fixtures/malformed_feed.xml
  fixtures/ambiguous_feed.xml
  test_rss_parser.py
  test_normalizer.py
  test_candidate_validator.py
```

- P1 Parser: `bytes -> ParsedFeed`, 파일·URL·DB 읽기 없음.
- P2 Normalizer: 제목 문자열, Source URL 문자열의 순수 변환.
- P3 Validator: `ParsedCandidate + 주입한 DomainPolicy/CategoryCatalog/TopicRules -> CandidateEvaluation`; 네트워크/DB/시간 호출 없음.
- P0~P3를 연결하는 얇은 오케스트레이션은 구현 단계에서 필요할 때만 추가한다. 공개 Router / SQLAlchemy Repository / 영속 상태는 추가하지 않는다.

### 3.2 출력 타입 의미 (언어 중립 계약)

```text
ParsedFeed:
  candidates: tuple[ParsedCandidate, ...]         # RSS 등장 순서 유지
  item_issues: tuple[ItemIssue, ...]              # 유효하지 않은 항목의 위치와 사유

ParsedCandidate:
  item_index: int                                 # 0부터 시작하는 RSS 내 위치
  raw_title: str                                 # 비어 있지 않은 값만 생성
  rss_published_at: datetime | None              # timezone-aware, 원본 변환 의미 보존
  source_candidates: tuple[ParsedSource, ...]    # 순서·반복 유지, 0개 허용
  warnings: tuple[WarningCode, ...]

ParsedSource:
  item_news_index: int                           # Item 내부 기사 위치
  raw_title: str | None
  raw_url: str | None
  publisher_name: str | None

ItemIssue:
  item_index: int
  code: ItemIssueCode

CandidateEvaluation:
  decision: WOULD_ACCEPT | DEFERRED | SKIPPED
  reason_codes: tuple[ReasonCode, ...]            # 정의된 순서, 중복 없음
  normalized_title: str | None
  valid_sources: tuple[NormalizedSource, ...]     # 확인된 *메타데이터* 적합 Source
  category_ids: tuple[int, ...]                  # 정렬된 활성 Child ID, 중복 없음
  warnings: tuple[WarningCode, ...]
  source_issues: tuple[SourceIssue, ...]            # 제외·보류한 기사 위치와 사유

SourceIssue:
  item_news_index: int
  code: SourceIssueCode
```

`NormalizedSource`: `source_title`, `canonical_url`, `source_key`, `publisher_name`을 포함한다. `source_key`는 P0에서 SHA-256 문자열이며 P4의 DB 저장 계약과 별도 확인한다. `publisher_name`은 RSS의 자기 신고성 메타데이터로 간주하고 호스트 소유자 증명으로 사용하지 않는다.

Parser가 제목 없는 Item을 `ParsedCandidate`로 억지로 만들지 않으므로 `raw_title` 비어 있음과 타입 계약의 모순이 제거된다. 기사 제목/URL 누락은 Parser에서 탈락시키지 않고 Validator에서 판단한다. 필드가 빈 문자열·공백뿐이면 `None`으로 표현하되, 그 외 원문 문자열은 P2 이전에 내용 변경하지 않는다. `item_index`와 `item_news_index`는 RSS의 **직접 자식 항목 순서**를 0부터 세며, 오류 Item을 제외해도 기존 위치를 재번호 매기지 않는다.

`SourceIssue`는 P3가 검증 과정에서 제외하거나 보류한 기사별 원인을 남긴다. 특정 기사가 실패해도 다른 기사 평가를 계속한다. Source 관련 출력 배열은 **RSS 기사 최초 등장 순서**를 유지하고, `category_ids`는 **오름차순**으로 반환한다. 사유 코드 배열은 **문서에서 정의한 우선순위**를 유지한다. `source_key`가 같은 기사가 한 후보 안에서 반복되면 첫 발생만 `valid_sources`에 남기고 중복을 `DUPLICATE_SOURCE`로 기록한다.

## 4. P1 Parser 형식·안전 계약

### 4.1 정상 / 부분 실패

| 조건 | 기대 동작 |
|---|---|
| 정상 RSS 2.0 + `channel` + 0~200 Item | 정상 후보와 ItemIssue 반환 |
| Item 제목 없음/공백 | 해당 Item 제외, `MISSING_ITEM_TITLE` 문제 기록 |
| 기사 제목·URL·출처 누락 | ParsedSource의 `None`으로 표현; 검증 책임은 P3 |
| Item에 `ht:news_item` 0개 | 구조적으로 허용, P3에서 Source 부족 판단 |
| `description`/`snippet` 빈 태그 | 정상, 오류 아님 |
| 유효하지 않은 `pubDate` | `None` + `INVALID_PUB_DATE` Warning |
| RSS 버전 누락/불일치, Channel 없음/복수, 비정상 루트 | FeedParseError로 전체 실패 |
| malformed XML / 엔터티·DTD / 상한 초과 | FeedParseError로 전체 실패 |

### 4.2 자원 상한 (P0~P3 동결값)

| 항목 | 동결값 | 초과 시 |
|---|---:|---|
| XML **파싱 전 bytes** | 2 MiB (2,097,152 bytes) | FeedParseError `INPUT_TOO_LARGE` |
| `item` 수 | 200 | `TOO_MANY_ITEMS` |
| Item당 `ht:news_item` | 20 | `TOO_MANY_NEWS_ITEMS` |
| XML 요소 중첩 깊이 | 32 | `XML_DEPTH_LIMIT` |

상한 초과를 조용히 자르거나 일부만 성공 처리하지 않는다. XML **파싱 전** 바이트 크기를 먼저 검사하고, 파싱 후 Item 수·기사 수·깊이 상한을 검사한 다음 후보를 조립한다. 크기는 UTF-8 문자 수가 아닌 **실제 입력 bytes**이며 상한값 이하를 허용한다. 대용량/압축 응답의 네트워크 다운로드와 압축 해제 제한은 **P4 이후** 별도 조건이다.

Parser는 `bytes`만 입력받는다. 문자열·파일 경로·URL을 내부에서 자동 변환하거나 열지 않는다. 입력 타입이 `bytes`가 아니면 `INVALID_INPUT_TYPE`, 빈 바이트열이면 `EMPTY_INPUT`으로 FeedParseError를 발생시킨다. 직접 자식인 `rss > channel > item`과 `item > {ht URI}news_item`만 후보로 인식한다. 예상치 못한 URI를 가진 `news_item` 계열 태그가 있으면 **구조 미지원 오류**로 처리한다. 모든 Item에 뉴스가 0건인 정상 입력 자체는 허용하며, 이를 원문 검증 성공으로 오인하지 않는다.

### 4.3 XML 파서

`defusedxml.ElementTree.fromstring(..., forbid_dtd=True, forbid_entities=True, forbid_external=True)` 사용을 **권고**한다. `defusedxml`은 현재 `backend/requirements.txt`에 없으므로, P1 구현 승인을 받은 뒤 **의존성 추가와 잠금·환경 적합성 확인**이 필요하다. 표준 라이브러리만으로 동일한 방어를 확보했다고 가정하지 않는다. Python 런타임의 Expat 버전(`pyexpat.EXPAT_VERSION`)도 구현 환경에서 확인하고, Python·Expat의 보안 업데이트 상태를 검증한다. `defusedxml`을 도입했다고 입력 상한 또는 런타임 패치 검증을 생략하지 않는다.

- 외부 DTD/Entity/파일/네트워크 접근 금지.
- XML 원본 텍스트를 운영 로그에 그대로 넣지 않는다.
- 구조 파싱 과정에서 URL을 열거나 RSS에 포함된 문서를 따라가지 않는다.
- XML 네임스페이스 URI/루트 구조가 예상과 불일치하면 `UNSUPPORTED_FEED_STRUCTURE`를 반환한다. 알 수 없는 **선택적** 태그 자체는 전체 실패 사유가 아니다.

FeedParseError 코드: `INVALID_INPUT_TYPE`, `EMPTY_INPUT`, `INVALID_XML`, `UNSUPPORTED_FEED_STRUCTURE`, `XML_SECURITY_REJECTED`, `INPUT_TOO_LARGE`, `TOO_MANY_ITEMS`, `TOO_MANY_NEWS_ITEMS`, `XML_DEPTH_LIMIT`. 예외 메시지에는 전체 RSS 원문/주소 토큰을 노출하지 않는다.

## 5. P2 Normalizer 계약

### 5.1 제목

1. 입력이 문자열인지 확인, Unicode NFC로 변환.
2. 선행·후행 공백 제거, 연속 Unicode 공백을 일반 공백 하나로 변경.
3. 사용자 표시용 `display_title`은 원래 영문 대소문자를 보존한다.
4. 중복키 `normalized_title`은 **ASCII A~Z만 소문자화**한다. 한글·숫자·의미 있는 기호·로마 숫자는 임의 삭제·번역·치환하지 않는다.
5. `display_title`/`normalized_title`이 비어 있거나 DB 목표 길이 255자를 초과하면 후보 검증 불가(저장하지 않음). P0에서는 Python Unicode 코드포인트 길이로 검사하며, MariaDB 인코딩·Collation 검증은 P4에서 별도 수행한다. Alias Map은 제목 정규화가 아니라 P3 별도 규칙이다.

> ASCII만 소문자화하는 범위는 **P0~P3 동결 정규화 규칙**이다. 다른 언어의 casefold와 과도한 동음의어/의미 치환은 별도 개정 없이 추가하지 않는다. MariaDB Collation이 만드는 동일성은 P4 DB 통합에서 재확인한다.

### 5.2 URL

- 절대 `http://` 또는 `https://` URL만 허용. 유저정보(`user:password@`), 제어문자·원시 공백, 호스트 누락, localhost·IP 직접 주소, 비표준 포트는 P0~P3에서 거부한다.
- scheme/호스트의 ASCII 대소문자는 정규화한다. 기본 포트(HTTP 80/HTTPS 443)는 제거 가능하나 **다른 포트는 거부**한다. 호스트의 승인 판단은 정규화된 **정확한 hostname** 기준이며, 부분 문자열/단순 접미사 매칭을 하지 않는다.
- 유니코드 도메인·Punycode는 우선 `UNKNOWN_DOMAIN`으로 보류하고, 별도 검토를 통해 정확한 허용 호스트로만 등록한다. URL 파서가 자동으로 신뢰를 부여하지 않는다.
- URL 파서가 호스트/포트 해석에 실패하거나 호스트가 인코딩·역슬래시·끝 점(`example.org.`) 등으로 모호하면 **유효하지 않은 URL**로 취급한다. 사용자 정보(`@`)를 통한 사칭, 퍼센트 인코딩된 호스트, 빈 포트·비정상 포트, 제어문자·개행 등도 거부한다. 승인 호스트 판정은 파서가 추출한 정규화 hostname의 **정확한 동등성 비교**만 허용한다.
- 경로·쿼리 순서·중복 쿼리 키·의미 있는 `id`, `article`, `page` 파라미터와 fragment는 보존한다. 경로의 대소문자 및 인코딩을 임의로 변경하지 않는다.
- 제거해도 된다고 **명시적으로 선정한 키** `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`만 **리터럴 키 이름이 정확히 일치할 때** 제거한다. URL 디코딩된 키나 비슷한 이름을 추측하여 제거하지 않는다. 나머지 미확인 파라미터는 보존하고, 제거하지 않은 쿼리의 표현·순서·반복 키·빈 값을 그대로 유지한다. 모든 쿼리가 제거된 경우 `?` 구분자 처리도 결정적으로 수행한다.
- SHA-256의 입력은 canonical URL의 UTF-8 byte sequence이며 출력은 64자 소문자 16진수. 해시값만으로 URL의 사실 여부·이용 권한을 보증하지 않는다.
- PoC URL 길이 상한은 **4,096 Unicode 코드포인트(입력 문자열 기준)**로 동결한다. 초과 시 해당 Source 후보를 제외한다. 이는 DB `Text` 컬럼의 기술적 최대 길이가 아니며, P4에서 인코딩·저장 한계를 다시 검증한다.

> URL 정규화는 **동등성이 증명되지 않은 두 URL을 강제로 합치지 않는** 보수적 규칙이다. 실제 네트워크 리디렉션·canonical 태그 확인·DNS·인증·HTTPS 인증서는 P0~P3에서 다루지 않는다.

## 6. P3 Candidate Validator 및 결과 계약

### 6.1 주입 정책

- `TopicRules`: 명시적 주제·동음이의어·별칭 및 **명백한 범위 밖** 규칙. 사전 비등록 검색어는 자동 제외 금지.
- `DomainPolicy`: `APPROVED`, `UNKNOWN`, `BLOCKED`; 테스트는 가상의 허용/차단 호스트만 사용. RSS `publisher_name`만으로 승인하지 않는다.
- `CategoryCatalog`: root code/ID + 활성 여부, child ID/parent ID/활성 여부. **실제 DB 접근 없는 값 객체**. 초기 Fixture는 Frozen Child 38개 범위에서 구성, 스포츠 미반영 상태를 보류로 테스트.
- 동일 입력과 동일 주입 설정에 대해 결과는 결정적이어야 한다. Fixture에서 날짜·네트워크·DB 등 외부 상태 참조 금지.

### 6.2 2단계 선별

**1차:** 검색어를 보고 명시적 근거로 `CLEAR_OUT_OF_SCOPE`라 확정할 수 있으면 `SKIPPED(OUT_OF_SCOPE)`; `POSSIBLE_IN_SCOPE` 또는 `AMBIGUOUS`면 반드시 2차 진행. 기본값은 `AMBIGUOUS`, 미등록 검색어 조기 제외 금지.

**2차:** 각 기사별 유효 제목, 안전한 URL, 승인 도메인, 검색어-제목의 명시적 관련성 근거를 검증. RSS 기사 제목만으로 기사 본문 진위나 실제 URL 접속 성공을 주장하지 않는다. 관련성은 단어의 단순 부분 문자열 일치가 아니라 **경계·별칭·문맥을 명시한 테스트 가능한 규칙**으로 판정한다. 지원하지 않는 한국어 의미 추론은 `DEFERRED`.

- 승인되고 관련된 Source 1개 이상이어야 기술적 채택 후보가 된다.
- 일부 승인/관련 Source가 있으면 부적합·미확인 Source는 제외/보류하고 유효한 Source만 결과에 포함할 수 있다. 미확인 Source가 하나라도 있다는 이유로 전체 후보를 일률적으로 보류하지 않는다.
- 다른 사건을 명백히 나타내는 Source가 섞이면 그 Source는 채택하지 않는다. 그러나 어떤 사건을 트렌드의 중심으로 삼아야 하는지 모호하거나 동일 제목 재관측 여부 판단이 불충분하면 `DEFERRED(EVENT_AMBIGUOUS)`.
- 범위 밖 주제/Category이면 `SKIPPED(OUT_OF_SCOPE)`; 범위는 맞지만 **활성 Child를 확정할 수 없으면** `DEFERRED(CATEGORY_UNCLEAR)`.
- `기타`는 기존 Frozen Taxonomy대로 대분류가 확실하고 **다른 세부분류에 자연스럽게 포함되지 않을 때**만 허용한다. 단순 정보 부족을 `기타`로 해결하지 않는다.
- 증거 있는 여러 활성 Child Category를 허용하되 동일 Child 중복 금지, parent root를 직접 매핑하지 않는다. `is_primary` 지정 없음.

### 6.3 최종 상태 우선순위 (사유 포함)

최종 상태는 **1차 주제 → Source별 기초·관련성 검사 → 사건 일관성·활성 Child 검증 → 기술 판정**으로 결정한다. 단순히 아래 표의 위쪽 사유부터 반환하지 않는다. 먼저 1차에서 `OUT_OF_SCOPE`로 **명확히 확정**된 후보는 `SKIPPED`이며, 나머지는 Source별로 검증한 뒤 최종 후보 판정을 내린다.

Source와 최종 판정의 우선순위는 다음과 같다.

1. RSS 검색어 또는 2차 기사 근거에서 **명백히 관심 범위 밖**이라고 입증되면 `SKIPPED(OUT_OF_SCOPE)`.
2. 승인 도메인·정상 제목·안전한 URL·명시적 관련성을 모두 만족하는 Source가 **0건**인 경우, 검토 가능한 Source가 전부 명백한 차단 도메인이면 `SKIPPED(BLOCKED_SOURCES_ONLY)`; 그 외에는 `DEFERRED(NO_ELIGIBLE_SOURCE)` 및 미확인 출처·관계 불충분·필드 누락 등의 근거를 기록한다. 따라서 Source가 0건이면 Category 부재보다 `NO_ELIGIBLE_SOURCE`가 우선한다.
3. 적합한 승인 Source가 **1건 이상** 있더라도, 중심 사건 또는 Source 간 사건 일관성을 확정할 수 없으면 `DEFERRED(EVENT_AMBIGUOUS)`.
4. 중심 주제/사건이 명확한 상태에서도 활성 Child Category를 근거 있게 확정할 수 없으면 `DEFERRED(CATEGORY_UNCLEAR)`.
5. 위 모든 조건을 통과한 경우에만 `WOULD_ACCEPT`를 반환한다. 부적합·미확인 Source는 포함하지 않고, 기사별 사유는 `source_issues`에 보존한다.

서로 다른 사건의 메타데이터가 혼합된 경우 **관련 기사 1건만 존재한다는 이유로 사건 하나를 자의적으로 선택하지 않는다**. 중심 사건이 명시적 규칙으로 식별될 때만 부적합 기사를 분리하고, 그렇지 않으면 `DEFERRED(EVENT_AMBIGUOUS)`로 판정한다. 모든 코드 배열은 안정적인 순서로 반환하며 `reason_codes`는 최종 판정의 근거, `source_issues`는 개별 기사 제외·보류 근거이다.

| 조건 | 결과 | 사유 코드 예시 |
|---|---|---|
| 1차 명백히 범위 밖 또는 2차 명백히 범위 밖 | `SKIPPED` | `OUT_OF_SCOPE` |
| Source 후보 전부 명백한 차단 출처 | `SKIPPED` | `BLOCKED_SOURCES_ONLY` |
| Source가 없음, 누락·형식 오류만 있음 | `DEFERRED` | `NO_ELIGIBLE_SOURCE` |
| 출처가 미승인인 Source뿐임 | `DEFERRED` | `UNKNOWN_SOURCE_DOMAIN` |
| 기사/주제 관련성 확인 불충분 | `DEFERRED` | `RELEVANCE_UNCLEAR` |
| 같은 제목 아래 사건 또는 Category 불분명 | `DEFERRED` | `EVENT_AMBIGUOUS`, `CATEGORY_UNCLEAR` |
| 최소 1개 승인·관련 Source, 활성 Child 근거 있음, 충돌 없음 | `WOULD_ACCEPT` | `VALIDATED_BY_FIXTURE_RULES` |

Source별 문제는 `SOURCE_TITLE_MISSING`, `SOURCE_URL_INVALID`, `BLOCKED_SOURCE_DOMAIN`, `UNKNOWN_SOURCE_DOMAIN`, `SOURCE_UNRELATED`, `DUPLICATE_SOURCE` 등의 **명시적인 SourceIssueCode**로 기록한다. **Source 수준에서 제외되었다고 후보 전체가 자동으로 같은 결과가 되지는 않는다.** 여러 결과가 혼재하면 **바로 위의 4단계 판정 순서**를 우선하며, 표는 대표 예시를 설명한다. 판정 사유는 선언된 순서로 중복 없이 기록한다.

기술적 예외는 정상 판정값이 아니라 `ValidationExecutionError` 또는 FeedParseError 등으로 다룬다. 테스트/실행 집계에서만 `FAILED`로 표시한다. `DEFERRED`를 기술 실패로 계산하지 않는다.

### 6.4 판정 결과 불변조건

- `WOULD_ACCEPT`이면 `normalized_title`은 비어 있지 않고 255자 이내이며, `valid_sources`에는 승인 호스트의 정규화된 원문 URL과 제목이 있는 **서로 다른 Source 최소 1건**, `category_ids`에는 부모·자식 활성 여부를 검증한 Child ID **최소 1개**가 반드시 존재한다. 해당 데이터는 합성 Fixture의 정책 통과 결과이며 실제 기사 방문·사실 검증·권리 확보는 뜻하지 않는다.
- `DEFERRED` 및 `SKIPPED`는 **유효한 저장 가능 후보**가 아니다. `valid_sources`와 `category_ids`를 포함하더라도 후속 Writer가 이를 사용해 저장하면 안 되며, 구현 편의상 해당 결과에서 `valid_sources=()` 및 `category_ids=()`로 반환하도록 고정한다. 개별 실패 근거는 `source_issues`와 `reason_codes`로만 전달한다.
- `FAILED`는 `CandidateEvaluation.decision`에 넣지 않는다. Feed 형식·보안 실패는 FeedParseError, 코딩 버그·정책 설정 오류는 별도 실행 실패로 기록한다. 오류가 발생한 후보를 정상 `DEFERRED`로 바꾸지 않는다.
- `CategoryCatalog`의 root/child 식별자 관계, Child 활성 여부 및 중복 제거는 주입값을 대상으로 검증한다. **오염된 테스트 정책 데이터**는 정상 후보 판정이 아니라 설정 오류로 처리한다. Category가 실제 DB에 있는지는 P4의 책임이다.

### 6.5 게시/DB 안전 경계

- `WOULD_ACCEPT`는 P3 결과일 뿐 `ACCEPTED`가 아니다. 실데이터 저장과 사용자 공개를 수행하지 않는다.
- P0~P3은 기존 Trend 검색·상태 조회가 없으므로 `normalized_title` 충돌·`HIDDEN` 여부·기존 Source 중복·실제 COMMIT 결과를 판정하지 않는다. P4 Writer의 **필수 재검증 항목**이다.
- `HIDDEN` 자동 갱신·복구 금지, 동일 제목 다른 사건 보류 등 이전 권고는 P4 Writer 동결 시 최종 확인한다.
- NCP 데이터를 이용한 무인 자동 채택/공개는 금지. Google RSS의 자동 접근·반복 수집·보관·가공·게시, 기사 제목/URL/본문/이미지 재사용은 별도 이용 권한 검증이 완료되기 전까지 서비스 실행 경로에서 차단한다.
- 독립 합성 Fixture의 기술 테스트는 외부 제공 데이터의 저작권·계약상 이용 허가를 대체하지 않는다.

## 7. 테스트 계약 (TDD, deterministic)

### 7.1 Fixture

1. `valid_feed.xml`: 3개 항목, 서로 다른 기사 수(0/1/3), 유효·빈 선택 필드, `-0700` 시간대, 임의 가상 제목/도메인.
2. `missing_fields.xml`: 제목 없는 Item + 정상 Item, 기사 제목·URL 누락, invalid `pubDate`.
3. `malformed_feed.xml`: 잘못된 XML; DTD·엔터티는 테스트에서 별도 합성 문자열로 조립하여 파일 수를 늘리지 않는다.
4. `ambiguous_feed.xml`: 중의 검색어, 관심 분야 밖 주제, 혼합 사건과 기사, 명시 별칭 매칭.

모든 Fixtures는 자체 작성한 가상 제목·URL·내용으로 구성하며 원본 Google 기사 본문·제목·이미지를 복제하지 않는다.

### 7.2 인수 테스트 매트릭스

| ID | 계약 검증 | 기대 결과 |
|---|---|---|
| P-01 | RSS 2.0, namespace URI, 서로 다른 namespace prefix | 정상 파싱 |
| P-02 | news_item 0/1/3건 | 반복 기사 보존, 0건 구조적으로 허용 |
| P-03 | Item 제목 없음 | 나머지 정상 Item 유지 + `ItemIssue` |
| P-04 | description/snippet 빈 값, 기사 제목·URL 누락 | Parser 성공, Validator에 누락 전달 |
| P-05 | RFC 822 형식 `-0700`, invalid date | aware datetime / `None` + Warning |
| P-06 | malformed XML / 잘못된 RSS 루트 | Feed 수준 명시적 실패 |
| P-07 | 정상 Item과 오류 Item 혼합 | 문제 위치·사유 정확, 정상 후보 유지 |
| P-08 | DTD, 엔터티, 외부 참조 | Feed 보안 거부 |
| P-09 | 2MiB/200 Item/20기사/깊이 32 경계값 및 초과 | 상한 포함 허용, 초과 시 명시적 전체 실패 |
| P-10 | 미지 URI의 `news_item` 태그, 직접 자식 아닌 Item, 복수 Channel | 미지 URI/복수 Channel은 구조 오류, 중첩 Item은 수집하지 않음 |
| P-11 | 유효한 bytes 외의 입력, 비어 있는 bytes, Expat 환경 확인 | 명시적 입력 오류·환경 점검 |
| N-01 | NFC, 공백·ASCII 대소문자 | 같은 정규화 키, 표시 제목 보존 |
| N-02 | 로마숫자·숫자·기호 차이 | 불필요한 병합 없음 |
| N-03 | 정확한 추적 파라미터와 임의 파라미터 | 승인된 키만 제거 |
| N-04 | `?id=`·쿼리 순서·fragment | 의미 있는 부분 보존 |
| N-05 | 비ASCII casefold 차이와 DB Collation 잠재 충돌 | 범위 밖 변환 없음, P4 검증 항목 표시 |
| N-06 | 위험 scheme, userinfo, 사칭 도메인, IP·localhost | URL/도메인 안전성 거부 |
| N-07 | 빈 포트·제어문자·역슬래시·호스트 끝 점·인코딩 호스트 | 모호한 URL 안전하게 거부 |
| N-08 | 중복 추적 키·인코딩된 추적 키·전체 추적 쿼리·반복 값 | 정확한 리터럴 5종만 제거하고 나머지 순서·표현 보존 |
| V-01 | 명백한 범위 밖 검색어 | `SKIPPED` |
| V-02 | 모호·미등록 검색어 | 2차까지 이동, 미등록 이유로 제외 금지 |
| V-03 | 유효 Source 1건 + 부적합 2건 | 유효 1건만 남겨 채택 후보 가능 |
| V-04 | 승인 도메인 0, 미확인만 존재 | `DEFERRED` |
| V-05 | Source 0건 또는 제목·URL 유효 Source 0건 | `DEFERRED(NO_ELIGIBLE_SOURCE)`; Category가 불명확해도 Source 부족 우선 |
| V-06 | 활성 Child 1개/복수 | 올바른 ID와 정렬, 부모 직접 매핑 없음 |
| V-07 | 같은 검색어가 서로 다른 사건을 의미 | 명확히 합칠 근거 없으면 `DEFERRED` |
| V-08 | TopicRules 사전에 없는 명백한 관련 사례 | 1차 조기 제외 안 함, 최종 검증 근거 없으면 `DEFERRED` |
| V-09 | 승인 + 미확인 + 차단 도메인 혼합 | 승인된 관련 기사만 결과에 포함 |
| V-10 | 가짜 서브도메인·접두어 사칭 | 승인으로 오인하지 않음 |
| V-11 | `기타`를 정보 부족 우회로 사용하는 사례 | `DEFERRED`; 진짜 기타 의미만 허용 |
| V-12 | 같은 Fixture + 설정 재실행 | 판정·사유·소스 순서·카테고리 순서 동일 |
| V-13 | 미반영 스포츠 / 비활성 Child | 임의 신설·활성화 없음, `DEFERRED` |
| V-14 | `WOULD_ACCEPT`라도 게시 권한 미확정 | DB Writer·라이브 RSS·외부 게시 호출 없음 |
| V-15 | 승인 관련 1건 + 미확인/차단/무관 기사 혼합 | 유효한 기사만 남고 `SourceIssue`가 기사 위치별로 기록됨 |
| V-16 | 미확인+차단 도메인만 있고 승인 Source 없음 | `DEFERRED` (전체 `BLOCKED_SOURCES_ONLY` 아님) |
| V-17 | 승인 Source가 있어도 사건 또는 Child가 불명확 | `DEFERRED`, 유효 후보 출력 배열 비움 |
| V-18 | 중복 원문 URL·상이한 기사 제목 | 동일 `source_key` 한 건만 유지, 중복 문제 기록 |
| V-19 | `WOULD_ACCEPT`의 출력 불변조건 및 비정상 정책 주입 | 제목·Source·Child 필수 조건 검증, 정책 오류는 실행 실패 |

단위 테스트는 프로젝트의 `backend/pyproject.toml`에 정의된 pytest/Ruff 환경을 따른다. PowerShell 실행 예시: `python -m pytest tests/external_trends -q`; `python -m ruff check app/external_trends tests/external_trends`. **현재 실행된 테스트는 0개이며, 명령은 구현 후 검증용**이다.

## 8. P0~P3 Done / Not Done 정의

| 단계 | 완료 기준 | 완료로 오인하면 안 되는 것 |
|---|---|---|
| P0 | 사용자가 이 문서의 기술 범위·검증 규칙·상한·출력 타입을 승인하여 FROZEN 표시 | 문서가 존재한다는 이유로 동결 |
| P1 | Parser 단위 테스트와 보안/부분 실패 경계 PASS | 라이브 RSS 자동 수집 성공 |
| P2 | 제목/URL 정규화·중복 안정성 테스트 PASS | MariaDB UNIQUE/Collation 충돌 완전 해결 |
| P3 | C+A안 선별, 관련성·Category·도메인·결정성 테스트 PASS | 실제 기사 검증, DB 저장, 공개 권한 승인 |
| P4+ | 별도 Writer 확정안에 따라 격리 테스트 DB, UNIQUE/COMMIT/ROLLBACK/HIDDEN/동시성 검증 | Google RSS 자동 게시 권리 확보 |

구현 시작 시 `dev` HEAD·현재 파일 구조·의존성·Category Master·관련 테스트와 DB 테스트 환경을 다시 확인한다. 현재 승인되지 않은 기존 Frozen 문서나 DB 모델의 수정은 별도 변경 요청이 필요하다.

## 9. 11개 관점 Final Review 보완 추적

| Review 보완 항목 | v1.0 반영 위치 |
|---|---|
| Parser 부분 실패 반환 모델 | §3.2, §4.1 |
| XML 보안 및 자원 상한 | §4.2~§4.3 |
| 제목·URL 정규화 세칙 | §5.1~§5.2 |
| 후보 결과·사유 코드 | §6.1~§6.3 |
| Fixture·경계·결정성 테스트 | §7 |
| 이용 권한 및 P4 이후의 분리 | §0.2, §6.4, §8 |

## 10. 사용자 동결 결정 및 변경 기록

### 10.1 승인된 기술 계약

2026-10-30 사용자가 v1.0 후보를 확인한 후 **동결 전 최종 허점 검토 및 반영**을 요청함에 따라, 본 파일을 P0~P3의 **설계 확정안(FROZEN)**으로 정리한다. 동결 범위는 해당 기술 PoC만이며 운영·실데이터·P4 권한을 포함하지 않는다.

| 항목 | 동결 내용 |
|---|---|
| XML 상한 | 2MiB, Item 200, Item별 기사 20, XML 깊이 32 |
| 원문 URL 길이 | 입력 문자열 기준 4,096 코드포인트 |
| 파서 | `defusedxml.ElementTree.fromstring` + DTD/Entity/외부 참조 거부 (`requirements.txt` 수정은 구현 승인 후) |
| 제목 정규화 | NFC, 공백 정리, ASCII 영문 소문자화, 의미 있는 문자 보존 |
| URL 추적 키 | 리터럴 `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`만 제거 |
| 채택 의미 | 가상 승인 Source + 규칙 기반 관련성 + 활성 Child에 한정된 메타데이터 기술 판정 |
| 판정 예외 | Source별 실패 기록, 혼합 기사 판정 우선순위, 정상 결과와 실행 실패 분리 |

### 10.2 Final Safety Review 반영 이력

| 확인한 허점 | 최종 반영 위치 |
|---|---|
| Parser의 제목 누락·부분 오류 표현과 기사별 문제 추적 부족 | §3.2, §4.1, §6.3, V-15 |
| RSS 구조 변경 시 빈 기사 목록으로 조용히 수용할 위험 | §4.1~§4.2, P-10 |
| URL의 모호한 호스트·잘못된 포트 및 추적 파라미터 처리 | §5.2, N-07~N-08 |
| 혼합 도메인·사건 모호함과 Source 부족·Category 검증의 판정 우선순위 충돌 | §6.3, V-05, V-16~V-17 |
| `WOULD_ACCEPT` 출력값의 불완전성 및 Source 중복 | §3.2, §6.4, V-18~V-19 |
| XML 보안 패키지와 런타임의 별도 검증 필요 | §4.3, P-11 |

### 10.3 동결되지 않은 사항

- 실제 Google Trending now RSS의 주기적 자동 접근, 보관·가공, 앱 게시, 원문 기사 제목·본문·이미지 재사용 권한 및 운영 도메인 승인 목록.
- P4 Writer의 Source 플랫폼 의미, 동일 제목/다른 사건 판정, `HIDDEN` 보호, 재관측/동시성, Source 중복·트랜잭션과 실제 MariaDB Collation 검증.
- `엔터테인먼트 > 스포츠` 실제 Taxonomy/Seed 반영과 기존 데이터 마이그레이션·회귀 검증.
- 사용자에게 공개된 기존 API·화면·데모 Seed, GitHub/Notion/DB/프로젝트 코드 변경. **본 로컬 문서의 Freeze가 원격 저장소 반영 허가는 아니다.**

> **구현 시작 조건:** 별도 구현 요청과 최신 `dev` 재확인, P1 TDD 시작. 이 문서는 PoC 개발 방향을 정하는 계약이며 현재 테스트 PASS 또는 기능 완료의 증빙이 아니다.

## 11. 근거와 한계

- 프로젝트 근거: 최신 `dev`의 지침 v1.2, Frozen Taxonomy·전체 목록·개인화 목록, ORM(`trend.py`, `trend_source.py`, `category.py`, `trend_category_map.py`), `requirements.txt`, `pyproject.toml` 및 사용자 RSS 관찰 화면.
- 일반 보안 근거: [Python XML security](https://docs.python.org/3/library/xml.html#xml-vulnerabilities), [OWASP XXE Prevention](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html), [defusedxml 문서](https://pypi.org/project/defusedxml/) 및 [defusedxml.ElementTree 구현](https://github.com/tiran/defusedxml/blob/main/defusedxml/ElementTree.py). XML 관련 공식 설명은 기술 권고로만 인용하며 Google RSS 사용 허가의 근거로 쓰지 않는다.
- 현재 미검증: PoC 코드 작성, 실행 테스트, 실제 Google RSS 자동 호출·저장·게시 권리, 원문 기사의 라이브 접속/사실 검증, MariaDB Collation 영향, Writer/스포츠 Seed 변경.