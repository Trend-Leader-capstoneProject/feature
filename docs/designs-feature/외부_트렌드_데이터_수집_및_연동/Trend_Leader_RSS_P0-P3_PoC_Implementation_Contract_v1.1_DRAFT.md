# Trend Leader — RSS Parser·Normalizer·Candidate Validator PoC 구현 계약 v1.1 (통합 개정 초안)

> **상태: DRAFT — 미승인 개정안. 원본 v1.0 FROZEN은 그대로 유효하며 이 문서는 아직 FROZEN이 아니다.**  
> 개정 초안 작성: 2026-11-02 (Asia/Seoul) / 원본 v1.0 작성·동결: 2026-10-30  
> 기준 Repository: `Trend-Leader-capstoneProject/feature` / 원본 v1.0: `dev` / 검토 코드: `feat-rss-p1-parser` HEAD `4213954ed6dbaf59c72a2c42ffe7738f4cfaf2bf`  
> 기반 문서: v1.0 FROZEN + R-03 제목 계약 + R-04A~C 안전·판정 계약 + R-04D Category 입력 타입 계약(각각 별도 DRAFT)  
> 선행 자료: `Trend_Leader_AI_Development_Guidelines.md` v1.2, 기존 Frozen Taxonomy·조회 계약, 외부 실데이터 사전 설계 기록(NOT FROZEN), 사용자 수동 RSS 관찰 기록.  
> **변경 통제:** 기존 v1.0을 덮어쓰지 않는 별도 파일로 작성했다. 사용자 최종 검토·승인 전에는 개정안을 동결하거나 `dev`로 병합하지 않는다. P4 Writer·실데이터 접근·외부 게시 권한은 여전히 별도 범위다.

### 이 문서의 해석 원칙

- §§0~11의 기존 v1.0 범위·상한·명시 정책을 최대한 보존하고, R-03·R-04A~D에서 검증한 조항만 보완했다.
- **최신 판정 계약**은 본 개정안의 §6.3을 기준으로 제안하며, 과거 R-03 문서의 Scope 혼합 사유 `EVENT_AMBIGUOUS`는 R-04C에 의해 `TOPIC_SCOPE_UNCLEAR`로 대체된다.
- 최신 전체 테스트 `411 passed`와 Ruff PASS는 2026-11-02 사용자의 로컬 실행 보고다. F-02 신규 Fixture·테스트의 GitHub 원격 반영은 확인했으나 원격 CI 성공을 이 문서만으로 증명하지 않는다.
- 기존 FROZEN §7.1의 `ambiguous_feed.xml`은 F-02에서 작업 브랜치에 추가됐고 Parser → Validator 연결 테스트 5개가 포함됐다(코드 체크포인트 `b3abc2d8bafee1ea42f55575f0137361a53213f4`). 문서 동결 및 `dev` 병합은 별도 승인이 필요하다.

## 0. 결정 및 범위 요약

### 0.1 사용자 명시 결정 (유지)

1. **후보 선별 C안:** RSS 검색어 예비 판정 → 기사 메타데이터 교차 검증 → 활성 Child Category 확정.
2. **1차 제외 A안:** 명백히 관심 범위 밖인 경우만 조기 제외. 모호하거나 사전에 없는 주제는 2차 검증.
3. **출처 도메인 C안:** 승인 도메인은 나머지 검증 대상, 미확인 도메인은 보류, 차단 도메인은 채택 불가.
4. **MVP A안:** 11월 중순까지 적법하게 자체 작성·확보한 실제 Trend를 기존 전체·개인화 목록에 연결하는 것이 우선. Google RSS 자동 발굴·게시 기능은 이용 권한 검증에 종속.
5. 최초 PoC는 **수동 관찰 + 독립 작성 Fixture**, 외부 자동 호출/공개 서비스 DB 저장/자동 게시 없음.

### 0.2 동결 효력과 선행 합의

- **원본 v1.0 FROZEN의 동결 범위는 P0~P3의 독립 합성 XML Fixture 기반 구현·테스트 계약**에 한정된다. 이 v1.1은 같은 범위를 유지하는 개정 초안이며 아직 동결된 문서가 아니다. Live RSS 다운로더, 원문 URL 접속, 실제 기사 검증, 데이터베이스 Writer, 앱 공개는 기존 동결·구현 권한에 포함되지 않는다.
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

### 3.1 구현 모듈 위치 (기준 브랜치에서 재확인)

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
  fixtures/ambiguous_feed.xml   # F-02 합성 RSS Fixture, 원격 체크포인트 반영 확인
  test_rss_parser.py
  test_normalizer.py
  test_candidate_validator.py
```

- P1 Parser: `bytes -> ParsedFeed`, 파일·URL·DB 읽기 없음.
- P2 Normalizer: 제목 문자열, Source URL 문자열의 순수 변환.
- P3 Validator: `ParsedCandidate + 주입한 DomainPolicy/CategoryCatalog/TopicRules -> CandidateEvaluation`; 네트워크/DB/시간 호출 없음.
- P0~P3를 연결하는 얇은 오케스트레이션은 필요할 때만 별도 승인한다. 현재 PoC 구현은 Parser·Normalizer·Validator와 독립 테스트를 중심으로 한다. 공개 Router / SQLAlchemy Repository / 영속 상태는 추가하지 않는다.

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

**v1.1 추가 — 후보 제목과 Category 출력 타입 불변조건**

- `CandidateEvaluation.normalized_title=None`은 문자열 후보 제목을 정규화할 수 없어 `DEFERRED(CANDIDATE_TITLE_INVALID)`가 된 경우 허용한다. 이때 Source 검사는 수행하지 않는다.
- `category_ids`는 실제 `int` 타입 Child 식별자만을 가진 오름차순·중복 없는 튜플이어야 한다. `bool`·`float`가 값 비교상 동일하더라도 허용하지 않는다.
- `NormalizedSource`의 저장 후보 목록과 Scope 판정에 사용하는 메타데이터 근거 목록은 같지 않을 수 있다. `DUPLICATE_SOURCE`는 저장 후보에서는 제외하지만, 기존 Source Screening을 통과했던 중복 기사 제목은 Scope 판정 근거로 사용한다.
- `CategoryCatalog.select_active_child_ids()`의 입력 타입은 `tuple[int, ...]`이다. `None`은 이 메서드의 입력이 아니며 P3 호출부에서만 근거 미제공으로 해석한다.

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

`defusedxml.ElementTree.fromstring(..., forbid_dtd=True, forbid_entities=True, forbid_external=True)`를 **현재 P1 구현에서 사용한다**. 작업 브랜치 `backend/requirements.txt`에는 `defusedxml==0.7.1`이 추가되어 있다. Python 런타임·의존성 잠금·Expat 보안 업데이트 적합성은 실제 배포 환경에서 별도로 검증해야 하며, 표준 라이브러리만으로 동일한 방어를 확보했다고 가정하지 않는다. Python 런타임의 Expat 버전(`pyexpat.EXPAT_VERSION`)도 구현 환경에서 확인하고, Python·Expat의 보안 업데이트 상태를 검증한다. `defusedxml`을 도입했다고 입력 상한 또는 런타임 패치 검증을 생략하지 않는다.

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

**v1.1 추가 — R-03 문자열 후보 제목 실패 판정**

- P1은 제목 없음·공백 Item을 `ItemIssue(MISSING_ITEM_TITLE)`로 제외한다. 반면 P3에 직접 들어온 후보의 `raw_title`이 `str`이면서 정규화 결과가 비거나 255 코드포인트를 초과하면 `DEFERRED(CANDIDATE_TITLE_INVALID)`로 처리한다.
- 제목이 정규화되지 않으면 Topic·Source·Event·Category 정책을 호출하지 않으며, `normalized_title=None`, `valid_sources=()`, `category_ids=()`, `source_issues=()`를 반환하고 `warnings`를 보존한다.
- 비문자열 후보 제목은 입력 타입 계약 위반이다. 정상 `DEFERRED`로 오인하지 않으며 실행 오류가 발생한다.

## 6. P3 Candidate Validator 및 결과 계약

### 6.1 주입 정책

- `TopicRules`: 명시적 주제·동음이의어·별칭 및 **명백한 범위 밖** 규칙. 사전 비등록 검색어는 자동 제외 금지.
- `DomainPolicy`: `APPROVED`, `UNKNOWN`, `BLOCKED`; 테스트는 가상의 허용/차단 호스트만 사용. RSS `publisher_name`만으로 승인하지 않는다.
- `CategoryCatalog`: root code/ID + 활성 여부, child ID/parent ID/활성 여부. **실제 DB 접근 없는 값 객체**. 초기 Fixture는 Frozen Child 38개 범위에서 구성, 스포츠 미반영 상태를 보류로 테스트. R-04A에 따라 Root/Child 식별자·parent ID는 정확한 `int`, 활성 상태는 정확한 `bool`로 검사하며 컨테이너·중복 식별자/코드·부모 참조 오류는 `ValidationExecutionError`로 처리한다. 정상 비활성 Category는 설정 오류가 아니다.
- 동일 입력과 동일 주입 설정에 대해 결과는 결정적이어야 한다. Fixture에서 날짜·네트워크·DB 등 외부 상태 참조 금지.

**v1.1 추가 — Category 선택 입력과 Evidence 정책**

- `CategoryCatalog.select_active_child_ids(evidence_child_ids)`: 컨테이너 타입은 정확히 `tuple`, 각 요소 타입은 정확히 `int`여야 한다. `bool`, `float`, 문자열, 리스트, 해시 불가능 요소 등은 조회 전에 `ValidationExecutionError("invalid category selection")`로 구분한다. 정상 빈 튜플이나 미등록·비활성 정수 ID는 `None`을 반환한다. 정상 ID 중복은 제거하고 오름차순으로 반환한다.
- `proposed_child_ids=None`은 P3 호출부에서만 정상적인 '선택 근거 미제공'으로 처리해 `()`로 변환한다. `[]`, `""`, `0`을 `or ()`로 조용히 바꾸지 않는다. 이 검증은 **Category Gate에 실제 도달한 경우**에만 일어나며 앞선 Topic·Source·Event 판정 우선순위는 유지된다.
- R-02A: 단순히 활성 Child가 제안됐다는 이유만으로 채택하지 않고, 후보 제목과 `valid_sources`를 기반으로 주입된 `CategoryEvidenceRules`가 제안 Child 모두를 뒷받침하는지 확인한다. 반환 정책 타입 오류는 정상 후보 보류가 아니다.
- R-01: `기타` Child는 해당 Root가 명확하고 '구체적 세부분류 어느 것에도 해당하지 않는다'는 명시적 근거가 필요하며, 같은 Root의 구체 Child와 동시 채택하지 않는다.

### 6.2 2단계 선별

**1차:** 검색어를 보고 명시적 근거로 `CLEAR_OUT_OF_SCOPE`라 확정할 수 있으면 `SKIPPED(OUT_OF_SCOPE)`; `POSSIBLE_IN_SCOPE` 또는 `AMBIGUOUS`면 반드시 2차 진행. 기본값은 `AMBIGUOUS`, 미등록 검색어 조기 제외 금지.

**2차:** 각 기사별 유효 제목, 안전한 URL, 승인 도메인, 검색어-제목의 명시적 관련성 근거를 검증. RSS 기사 제목만으로 기사 본문 진위나 실제 URL 접속 성공을 주장하지 않는다. 관련성은 단어의 단순 부분 문자열 일치가 아니라 **경계·별칭·문맥을 명시한 테스트 가능한 규칙**으로 판정한다. 지원하지 않는 한국어 의미 추론은 `DEFERRED`.

- 승인되고 관련된 Source 1개 이상이어야 기술적 채택 후보가 된다.
- 일부 승인/관련 Source가 있으면 부적합·미확인 Source는 제외/보류하고 유효한 Source만 결과에 포함할 수 있다. 미확인 Source가 하나라도 있다는 이유로 전체 후보를 일률적으로 보류하지 않는다.
- 다른 사건을 명백히 나타내는 Source가 섞이면 그 Source는 채택하지 않는다. 그러나 어떤 사건을 트렌드의 중심으로 삼아야 하는지 모호하거나 동일 제목 재관측 여부 판단이 불충분하면 `DEFERRED(EVENT_AMBIGUOUS)`.
- 범위 밖 주제/Category이면 `SKIPPED(OUT_OF_SCOPE)`; 범위는 맞지만 **활성 Child를 확정할 수 없으면** `DEFERRED(CATEGORY_UNCLEAR)`.
- `기타`는 기존 Frozen Taxonomy대로 대분류가 확실하고 **다른 세부분류에 자연스럽게 포함되지 않을 때**만 허용한다. 단순 정보 부족을 `기타`로 해결하지 않는다.
- 증거 있는 여러 활성 Child Category를 허용하되 동일 Child 중복 금지, parent root를 직접 매핑하지 않는다. `is_primary` 지정 없음.

**v1.1 추가 — 2차 기사 범위 근거와 중복 기사 분리**

- R-02B: 1차에서 명백한 범위 밖으로 제외되지 않았고 적합 Source가 존재할 때, `ArticleTopicScopeRules`로 기사 제목의 2차 Scope 근거를 별도 판정한다. 명백한 범위 밖 근거가 하나도 없으면 Event Gate로 진행한다.
- R-04B: 승인 도메인·정상 제목·안전 URL·명시 관련성 검사를 모두 통과했지만 동일 `source_key`로 제거된 `DUPLICATE_SOURCE`의 기사 제목은 **Scope 판정에만** 포함한다. `valid_sources`에는 최초 Source 한 건만 유지한다. 차단·미확인·관련성 미충족·메타데이터 오류 기사는 Scope 판단 근거에 포함하지 않는다.
- R-04C: 이 범위 근거가 일부만 `CLEAR_OUT_OF_SCOPE`이면 `DEFERRED(TOPIC_SCOPE_UNCLEAR)`로 보류한다. 같은 상황에 `EVENT_AMBIGUOUS`를 사용하지 않는다.

### 6.3 최종 상태 우선순위 (사유 포함)

최종 상태는 **후보 제목의 타입·정규화 → 1차 Topic → Source별 기초·관련성·중복 검사 → 2차 기사 Scope → Event Consistency → Category·근거 → 기술 판정** 순서로 결정한다. 앞 단계가 최종 결과를 반환하면 뒤 단계 정책을 호출하지 않는다. 모든 Gate는 검증된 **합성 Fixture**만을 다루며 실제 네트워크·DB를 사용하지 않는다.

1. **제목 전제 검사(R-03):** P3가 전달받은 `raw_title`이 문자열인데 정규화 결과가 없으면 `DEFERRED(CANDIDATE_TITLE_INVALID)`이고 Source 검사도 하지 않는다. 비문자열은 정상 후보 판정이 아니라 입력 타입 오류이다.
2. **1차 Topic:** 제목이 유효하고 명시적 근거로 `CLEAR_OUT_OF_SCOPE`라 판정되면 `SKIPPED(OUT_OF_SCOPE)`. `POSSIBLE_IN_SCOPE`, `AMBIGUOUS`, 미등록 검색어는 조기 제외하지 않는다.
3. **Source Screening:** 제목·URL·승인 도메인·명시 관련성 조건을 만족하는 Source가 **0건**이면, 전부 명백히 차단된 출처일 때 `SKIPPED(BLOCKED_SOURCES_ONLY)`, 그 외는 `DEFERRED(NO_ELIGIBLE_SOURCE)` 및 미확인 도메인·관계 불충분 등의 추가 근거를 기록한다. Source 0건이면 Event·Category 검증으로 진행하지 않는다.
4. **2차 기사 Scope(R-02B, R-04B/C):** 적합 Source와 승인·관련성을 통과한 `DUPLICATE_SOURCE`의 제목을 범위 근거로 평가한다. 모든 평가 대상이 `CLEAR_OUT_OF_SCOPE`면 `SKIPPED(OUT_OF_SCOPE)`; 일부만 `CLEAR_OUT_OF_SCOPE`면 `DEFERRED(TOPIC_SCOPE_UNCLEAR)`; 그런 근거가 없으면 Event로 진행한다.
5. **사건 일관성:** 주입된 Event 규칙이 `AMBIGUOUS` 또는 `UNDETERMINED`이면 `DEFERRED(EVENT_AMBIGUOUS)`. 다르게 확인된 사건을 관련 기사 1건만으로 임의 선택하지 않는다. 이 단계의 입력과 정책 구현은 P0~P3의 **보수적 합성 Fixture 규칙**이며 실데이터 신뢰성·사건 판별 엔진을 뜻하지 않는다.
6. **Category 및 근거(R-01, R-02A, R-04A/D):** `CategoryCatalog` 오염 설정 또는 잘못된 선택 ID 타입은 `ValidationExecutionError`로 구분한다(해당 Gate에 도달한 경우). 정상 입력 `None`·빈 튜플·미등록·비활성 Child, 제안 Child의 기사 근거 부족 또는 `기타`의 구체 Child 배제 근거 부족은 `DEFERRED(CATEGORY_UNCLEAR)`로 보류한다.
7. **채택 가능:** 모든 조건이 충족될 때만 `WOULD_ACCEPT(VALIDATED_BY_FIXTURE_RULES)`; `valid_sources`에는 적합하고 서로 다른 Source만 담고 `category_ids`에는 근거가 있는 실제 `int` 활성 Child만 담는다.

| 조건 | 결과 | 최종 사유 |
|---|---|---|
| 후보 제목 문자열이 비거나 정규화 후 255자 초과 | `DEFERRED` | `CANDIDATE_TITLE_INVALID` |
| 1차 명백히 범위 밖 / 2차 모든 근거가 범위 밖 | `SKIPPED` | `OUT_OF_SCOPE` |
| Source 후보가 모두 명백히 차단 출처 | `SKIPPED` | `BLOCKED_SOURCES_ONLY` |
| 적합 Source 0건 | `DEFERRED` | `NO_ELIGIBLE_SOURCE` (+ 조건별 추가 사유) |
| 일부만 명백히 범위 밖으로 확인된 기사 근거 | `DEFERRED` | `TOPIC_SCOPE_UNCLEAR` |
| Event 불확정 또는 사건 충돌 | `DEFERRED` | `EVENT_AMBIGUOUS` |
| 활성·유효 Child 또는 기사·기타 근거 부족 | `DEFERRED` | `CATEGORY_UNCLEAR` |
| 부적합 Category 정책 데이터/선택 입력 타입 | 실행 실패 | `ValidationExecutionError` |
| 모든 합성 정책 통과 | `WOULD_ACCEPT` | `VALIDATED_BY_FIXTURE_RULES` |

`reason_codes`는 후보의 최종 판정 근거이고 `source_issues`는 기사별 제외·보류 근거이다. 승인된 적합 Source가 있어도 나머지 Source의 명시적 문제를 기록한다. `DEFERRED`는 기술 실패가 아니며 `FAILED`라는 `CandidateDecision`은 추가하지 않는다. 예외를 정상 결과로 변환하지 않는다.

### 6.4 판정 결과 불변조건

- `WOULD_ACCEPT`이면 `normalized_title`은 비어 있지 않고 255자 이내이며, `valid_sources`에는 승인 호스트의 정규화된 원문 URL과 제목이 있는 **서로 다른 Source 최소 1건**, `category_ids`에는 부모·자식 활성 여부를 검증한 Child ID **최소 1개**가 반드시 존재한다. 해당 데이터는 합성 Fixture의 정책 통과 결과이며 실제 기사 방문·사실 검증·권리 확보는 뜻하지 않는다.
- `DEFERRED` 및 `SKIPPED`는 **유효한 저장 가능 후보**가 아니다. `valid_sources`와 `category_ids`를 포함하더라도 후속 Writer가 이를 사용해 저장하면 안 되며, 구현 편의상 해당 결과에서 `valid_sources=()` 및 `category_ids=()`로 반환하도록 고정한다. 개별 실패 근거는 `source_issues`와 `reason_codes`로만 전달한다.
- `FAILED`는 `CandidateEvaluation.decision`에 넣지 않는다. Feed 형식·보안 실패는 FeedParseError, 코딩 버그·정책 설정 오류는 별도 실행 실패로 기록한다. 오류가 발생한 후보를 정상 `DEFERRED`로 바꾸지 않는다.
- `CategoryCatalog`의 root/child 식별자 관계, Child 활성 여부 및 중복 제거는 주입값을 대상으로 검증한다. **오염된 테스트 정책 데이터**는 정상 후보 판정이 아니라 설정 오류로 처리한다. Category가 실제 DB에 있는지는 P4의 책임이다.

**v1.1 추가 — R-03·R-04 결과 불변조건**

- `DEFERRED(CANDIDATE_TITLE_INVALID)`: `normalized_title=None`, `valid_sources=()`, `category_ids=()`, `source_issues=()`, `warnings` 보존. Source가 정상이라는 증명이 아니라 Source 검사를 수행하지 않았다는 뜻이다.
- `DEFERRED(TOPIC_SCOPE_UNCLEAR)`: 제목·적합 Source는 존재하지만 기사별 Scope 증거가 혼재한다. 선택 Source와 Category 출력은 비우고, `DUPLICATE_SOURCE`를 포함해 이미 발생한 `source_issues`를 보존한다.
- `DEFERRED(EVENT_AMBIGUOUS)`: 사건 규칙에 의한 사건 충돌 또는 불확정에 한정한다. Scope 혼재를 대신 나타내지 않는다.
- `WOULD_ACCEPT`의 `category_ids`에는 정확히 `int`인 Child ID만 포함한다. 선택 타입 오류가 우연히 정수 ID와 값이 같거나 해시 가능하다는 이유로 수용하지 않는다.
- `CategoryCatalog` 정책값 오염은 `ValidationExecutionError`; Category 선택 입력의 잘못된 컨테이너·ID 타입도 `ValidationExecutionError`. 정상 정수 ID의 미등록·비활성·근거 부족은 `CATEGORY_UNCLEAR`이다.

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
4. `ambiguous_feed.xml`: F-02에서 신규 등록. 4개 합성 Item으로 서로 다른 사건 혼합, 명백한 관심 범위 밖 주제, 명시적으로 주입된 별칭·관련성 근거, 중복 URL에서 기사 Scope 충돌을 검증한다. Parser → Validator 연결 테스트 5개에서 사용한다.

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
| R03-01~08 | 후보 제목 공백·길이·255 경계·유효/무효 조합·경고 보존·비문자열 | `CANDIDATE_TITLE_INVALID`와 실행 실패 분리 |
| R04A-01~04 | Root/Child 활성 타입·ID 타입·정상 활성/비활성 | 오염 설정 예외, 정상 선택 규칙 보존 |
| R04B-01~04 | 동일 URL 기사 근거 혼재·사건 충돌·같은 사건·무관 기사 | Scope 근거 보존, `DUPLICATE_SOURCE` 유지 |
| R04C-01~04 | 기존/최종 Scope 혼재, 중복 URL, 불명확/범위 밖 근거, 사건 충돌 | `TOPIC_SCOPE_UNCLEAR`와 `EVENT_AMBIGUOUS` 구분 |
| R04D-01~06 | `float`/`bool`/`str`/unhashable ID, list 컨테이너, `None`·정상 ID 회귀 | 실행 오류와 `CATEGORY_UNCLEAR` 구분 |
| F02-01 | 신규 합성 XML의 Item 4건, 기사 수·순서·URL 원본 보존 | P1 → P3 입력 계약 연결 |
| F02-02 | 동일 검색어의 서로 다른 사건 ID | `DEFERRED(EVENT_AMBIGUOUS)` |
| F02-03 | 명백한 범위 밖 주제 | `SKIPPED(OUT_OF_SCOPE)` |
| F02-04 | 명시적 별칭·관련성·Category 근거 | `WOULD_ACCEPT(VALIDATED_BY_FIXTURE_RULES)` |
| F02-05 | 중복 URL 기사 사이의 Scope 근거 충돌 | `DEFERRED(TOPIC_SCOPE_UNCLEAR)`, `DUPLICATE_SOURCE` 보존 |

단위 테스트는 프로젝트의 `backend/pyproject.toml`에 정의된 pytest/Ruff 환경을 따른다. PowerShell 실행 예시: `python -m pytest tests/external_trends -q`; `python -m ruff check app/external_trends tests/external_trends`. **2026-11-02 F-02 추가 이후 사용자 로컬 실행 결과는 P1~P3 전체 `411 passed`, Ruff `All checks passed!`이다.** 이는 사용자가 보고한 로컬 검증 증거이며, 별도 원격 CI 실행 성공을 의미하지 않는다.

## 8. P0~P3 Done / Not Done 정의

| 단계 | 완료 기준 | 완료로 오인하면 안 되는 것 |
|---|---|---|
| P0 | 사용자가 이 문서의 기술 범위·검증 규칙·상한·출력 타입을 승인하여 FROZEN 표시 | 문서가 존재한다는 이유로 동결 |
| P1 | Parser 단위 테스트와 보안/부분 실패 경계 PASS | 라이브 RSS 자동 수집 성공 |
| P2 | 제목/URL 정규화·중복 안정성 테스트 PASS | MariaDB UNIQUE/Collation 충돌 완전 해결 |
| P3 | C+A안 선별, 관련성·Category·도메인·결정성 테스트 PASS | 실제 기사 검증, DB 저장, 공개 권한 승인 |
| P4+ | 별도 Writer 확정안에 따라 격리 테스트 DB, UNIQUE/COMMIT/ROLLBACK/HIDDEN/동시성 검증 | Google RSS 자동 게시 권리 확보 |

구현 시작 시 `dev` HEAD·현재 파일 구조·의존성·Category Master·관련 테스트와 DB 테스트 환경을 다시 확인한다. 현재 승인되지 않은 기존 Frozen 문서나 DB 모델의 수정은 별도 변경 요청이 필요하다.

### v1.1 DRAFT 작성 시점 구현·검증 상태 (동결·승인과 분리)

| 항목 | 근거 및 현재 상태 |
|---|---|
| P1 Parser, P2 Normalizer, P3 Validator 구현 | 작업 브랜치 `feat-rss-p1-parser`에서 코드·테스트 파일 존재 확인 |
| R-03, R-04A~C, R-04D | 별도 보완안 및 Python 코드 체크포인트의 원격 반영 확인 |
| 전체 자동 테스트 | F-02 통합 테스트 5개 추가 후 사용자가 로컬에서 `411 passed` 보고 (기존 406개 → 411개) |
| 정적 검사 | 사용자가 로컬에서 Ruff `All checks passed!` 보고 |
| 원격 CI / 통합 배포 검증 | **미확인**. 이 초안은 PASS를 새로 실행한 결과가 아니다 |
| `ambiguous_feed.xml` | F-02 체크포인트 `b3abc2d8`로 원격 추가 확인. 합성 XML Item 4개, Parser → Validator 테스트 5개 존재 확인 |
| 실제 수집·저장·게시 | P0~P3 계약에서 제외, 실행·승인 완료 아님 |

**판정:** P1~P3의 사용자 로컬 단위 회귀는 통과했으나 v1.1은 아직 **승인 전 DRAFT**이다. `dev` 병합, 실데이터 사용, P4 Writer·공개 기능 완료를 선언하지 않는다.

## 9. 11개 관점 Final Review 보완 추적

| Review 보완 항목 | v1.0 반영 위치 |
|---|---|
| Parser 부분 실패 반환 모델 | §3.2, §4.1 |
| XML 보안 및 자원 상한 | §4.2~§4.3 |
| 제목·URL 정규화 세칙 | §5.1~§5.2 |
| 후보 결과·사유 코드 | §6.1~§6.3 |
| Fixture·경계·결정성 테스트 | §7 |
| 이용 권한 및 P4 이후의 분리 | §0.2, §6.4~§6.5, §8 |
| R-03 제목 품질과 실행 오류 구분 | §3.2, §5.1, §6.3~§6.4, R03-01~08 |
| R-04A CategoryCatalog 정책값 무결성 | §6.1, §6.3~§6.4, R04A-01~04 |
| R-04B 중복 기사 Scope 근거 보존 | §3.2, §6.2~§6.4, R04B-01~04 |
| R-04C Scope / Event ReasonCode 분리 | §6.2~§6.4, R04C-01~04 |
| R-04D 선택 Child ID 입력 타입 안전성 | §3.2, §6.1, §6.3~§6.4, R04D-01~06 |
| F-02 합성 XML Parser → Validator 연결 검증 | §7.1~§7.2, F02-01~05 |

## 10. 사용자 동결 결정 및 변경 기록

### 10.1 승인된 기술 계약

2026-10-30 사용자가 v1.0 후보를 확인한 후 **동결 전 최종 허점 검토 및 반영**을 요청함에 따라, **당시 원본 v1.0 파일을** P0~P3의 **설계 확정안(FROZEN)**으로 정리했다. 본 v1.1 파일은 그 결정을 계승하는 **미승인 통합 개정 초안(DRAFT)**이다. 기존 동결 범위는 해당 기술 PoC에 한정되며 운영·실데이터·P4 권한을 포함하지 않는다.

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

### 10.2.1 v1.1 통합 개정 제안 이력 (아직 FROZEN 아님)

| 변경 출처 | 이전 문제·계약 | v1.1 제안 | 테스트 및 호환성 |
|---|---|---|---|
| R-03 | 유효하지 않은 문자열 제목이 실행 오류로 분류될 수 있음 | `DEFERRED(CANDIDATE_TITLE_INVALID)`를 정상 품질 보류로 구분 | R03 8개·기존 유효 제목 경로 보존 |
| R-04A | Category 정책 데이터에서 Python truthy/type 혼동 | Root/Child ID·활성 상태 정확 타입·구조 검사 | R04A 10개 사례 |
| R-04B | 중복 URL의 다른 기사 Scope 근거 소실 | 적합 중복 기사는 Scope 근거로만 사용, 저장 후보 중복 제거 유지 | R04B 5개 사례 |
| R-04C | 기사 Scope 혼합과 사건 충돌 모두 `EVENT_AMBIGUOUS`로 반환 | Scope 혼합은 `TOPIC_SCOPE_UNCLEAR`; 사건 모호성은 기존 코드 유지 | R04C 신규 2개 및 기존 R02B/R04B 기대값 수정 |
| R-04D | `101.0`, `True`, `[]` 등이 선택 ID 경계에서 잘못 처리됨 | 정확 `tuple[int,...]` 및 `None` 책임 분리; 잘못된 타입은 실행 실패 | R04D 19개 사례; 전체 406개 회귀 사용자 로컬 PASS |

**하위 호환성 영향:** `ReasonCode`에 `CANDIDATE_TITLE_INVALID`, `TOPIC_SCOPE_UNCLEAR`가 추가되어 판정 소비자가 신규 사유를 처리해야 한다. Category 선택 타입 오류는 기존 잘못된 입력의 동작을 예외로 바꾸므로 테스트·주입 규칙의 입력 계약을 준수해야 한다. 새로운 API Endpoint, DB 마이그레이션 또는 실제 데이터 이용 권한을 부여하지 않는다.

**검토·승인 경계:** 이 문서에서 제안하는 v1.1은 기존 v1.0의 동결 효력을 취소하지 않는다. 각 보완안은 변경 근거의 역사로 보존하며, v1.1을 실제 FROZEN으로 확정하는 것은 별도 사용자 승인 및 검증 후에만 가능하다.

### 10.3 동결되지 않은 사항

- 실제 Google Trending now RSS의 주기적 자동 접근, 보관·가공, 앱 게시, 원문 기사 제목·본문·이미지 재사용 권한 및 운영 도메인 승인 목록.
- P4 Writer의 Source 플랫폼 의미, 동일 제목/다른 사건 판정, `HIDDEN` 보호, 재관측/동시성, Source 중복·트랜잭션과 실제 MariaDB Collation 검증.
- `엔터테인먼트 > 스포츠` 실제 Taxonomy/Seed 반영과 기존 데이터 마이그레이션·회귀 검증.
- 사용자에게 공개된 기존 API·화면·데모 Seed, GitHub/Notion/DB/프로젝트 코드 변경. **v1.0 작성 당시 문서 동결은 원격 소스 반영 허가가 아니었다.** 현재 P0~P3 코드와 R-03~R-04D 보완 문서는 별도 작업 브랜치에 반영돼 있으나, v1.1 DRAFT의 존재 자체가 `dev` 병합 허가를 뜻하지 않는다.

> **v1.0 당시 구현 시작 조건:** 별도 구현 요청·최신 `dev` 확인·P1 TDD 착수였다. **v1.1 현재 상태:** P1~P3 코드는 작업 브랜치에 구현됐고 로컬 테스트 결과가 보고됐으나, 이 DRAFT는 최종 CI·문서 정합성·`dev` 병합 완료를 증명하지 않는다.

### 10.4 v1.1 승인 전 최종 점검 (2026-11-02 갱신)

- [x] 원본 v1.0 FROZEN 텍스트 기준 구조·범위·수치 상한 유지
- [x] R-03 및 R-04A~D 별도 보완안의 최종 코드·사유 계약 반영
- [x] v1.0 원본 파일을 수정하지 않는 별도 신규 DRAFT로 작성
- [x] 사용자 보고 F-02 추가 후 로컬 `411 passed`·Ruff PASS 구분 표기
- [x] `ambiguous_feed.xml` 4개 Item 및 Parser → Validator 통합 테스트 5개 원격 반영 확인 (`b3abc2d8`)
- [ ] 최종 브랜치 HEAD·동결 대상 실제 코드·테스트/CI 최신성 재검증
- [ ] 사용자 v1.1 정책·변경점 명시 승인
- [ ] 승인 후 v1.1 FROZEN 발행 및 `dev` PR·병합 절차 별도 진행

## 11. 근거와 한계

- 프로젝트 근거: 최신 `dev`의 지침 v1.2, Frozen Taxonomy·전체 목록·개인화 목록, ORM(`trend.py`, `trend_source.py`, `category.py`, `trend_category_map.py`), `requirements.txt`, `pyproject.toml` 및 사용자 RSS 관찰 화면.
- 일반 보안 근거: [Python XML security](https://docs.python.org/3/library/xml.html#xml-vulnerabilities), [OWASP XXE Prevention](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html), [defusedxml 문서](https://pypi.org/project/defusedxml/) 및 [defusedxml.ElementTree 구현](https://github.com/tiran/defusedxml/blob/main/defusedxml/ElementTree.py). XML 관련 공식 설명은 기술 권고로만 인용하며 Google RSS 사용 허가의 근거로 쓰지 않는다.
- 현재 미검증: **원격 CI 성공 여부**, 실제 Google RSS 자동 호출·저장·게시 권리, 원문 기사 라이브 접속·사실 검증, MariaDB Collation 영향, P4 Writer/스포츠 Seed 변경. F-02 합성 XML과 통합 테스트의 원격 반영을 확인했으며, 사용자 로컬 `411 passed`·Ruff PASS는 CI 결과와 구분해 기록했다.