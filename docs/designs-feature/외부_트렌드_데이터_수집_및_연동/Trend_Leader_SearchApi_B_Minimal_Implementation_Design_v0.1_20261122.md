# Trend Leader — SearchApi B안 최소 구현 계약 v0.1

> 2026-11-22 사용자 결정: 검색어를 직접 게시하지 않고 관련 근거 검증 후 자체 작성 카드로 게시(B안). 개발 시간 단축은 기존 검증·Writer·조회 계약 재사용으로 달성하며 필수 안전성은 생략하지 않는다.

## 목표와 현재 범위

- 한국(KR) Google Trends Trending Now 24시간 후보로 게임·IT 외 패션·뷰티·음식·엔터테인먼트의 실제 화제 후보를 발견한다.
- SearchApi Trending Now → news_token으로 관련 News API 조회 → 근거 출처 확인 및 사건 일치 → 기존 활성 Child Category 판정 → 기존 Writer/Journal → MariaDB → 기존 API/TrendCard.
- 현재 구현 범위는 **읽기 전용 HTTP Client와 Parser**다. 뉴스 메타데이터는 사실 검증 증거가 아니다. 운영 Source Adapter 등록·DB 쓰기·공개·Scheduler 변경/승인은 아직 없다.

## 2026-11-23 읽기 전용 KR 실측 승인 및 실행 경계

- 사용자 명시 승인: SearchApi 실제 KR 데이터 조회 **최대 3회**, 오직 읽기 전용. 1회 Trending Now + 관련 News 최대 2회; 승인한 것은 API 호출이지 자동 게시·운영 프로필 변경·DB 쓰기가 아니다.
- 사용자 WSL 실행 결과 **실제 조회 3회 완료**(Trending 1 + News 2), 추가 승인 없이 실측 재실행 금지. API 키는 채팅·GitHub에 전달되지 않았고, 읽기 전용 출력만 공유됨. 실측용 3회 예산은 전체 서비스의 영구 공급량 제한이 아니다.
- 구현: `backend/scripts/probe_searchapi_kr.py --live`는 1+최대2 HTTP GET 후 검색어·Category Root 힌트·미검증 기사 메타데이터만 stdout JSON에 출력한다. `news_token` 일치 검증 필수, 뉴스 내용·본문을 확인한 것으로 처리 금지. DB/Journal/Timer/승인 프로필과 인터페이스 없음.
- 초기 격리 Python 단위 시험: 기존 30건 + Probe 7건 = **37 PASS**, 테스트용 Stub 사용. 이후 진단 출력 및 회귀 테스트 변경은 GitHub 반영했으나 해당 최신 Commit의 실제 pytest 재실행 결과는 아직 없음. 저장소 실제 의존성 기반 통합 회귀·Writer/E2E는 미수행.

- **WSL KR 실측**: `READ_ONLY_DISCOVERY`, `total_eligible_leads=4`, `news_queries=2`, `requests_executed=3`; News 2개 후보 모두 엔터테인먼트(지드래곤, 심진화). 이는 원본 반환 총 건수가 아니라 `is_active=True` 및 3개 허용 Google 분야의 자체 필터 결과다. 실제 Google 검색어 원본 총량은 출력하지 않았으므로 미확인. 뉴스/검색어가 사실 검증·게시 적격이라는 뜻은 아님.
- **관측성 최소 개선(같은 PR)**: 비게시 Probe JSON에 `total_trends_returned`, `active_trends_returned`, 전체 `eligible_leads`(토큰 없는 쿼리·Root 힌트) 추가. News API 2개 제한과 DB/Writer/Timer 경계는 동일. 이미 종료한 실측 결과를 사후 복원할 수는 없음.

## 2026-11-23 KR 실측 기반 최소 보완

- 3회 읽기 전용 호출은 이미 모두 실행(Trending Now 1, News 2). 새 검색 재실행은 이번 승인 범위가 아니므로 중단. 최초 Probe의 `total_eligible_leads=4`는 전체 원본 공급량을 의미하지 않는다.
- 원본 확인: SearchApi Search History API(https://www.searchapi.io/docs/search-history-api)는 최근 90일 기록 조회에 **구독을 요구**하며, 해당 권한이 있는 경우 호출 비용이 별도로 청구되지 않는다고 명시한다. 성공 기록의 `json_url`을 반환한다. `python -m scripts.audit_searchapi_history --day 2026-11-23`는 해당 날짜의 KR `past_24_hours` 단일 기록을 선택한 다음, 고정 SearchApi 호스트·경로의 저장된 JSON만 다시 읽는다(History 1 + JSON 1, **신규 Trending/News 호출 0회**). JSON 링크를 외부에 공유하거나 출력하지 않고 Key를 터미널에서 숨김 입력하며, 다른/다수 기록·HTTP 리디렉션은 거부한다. 실제 History 응답은 사용자가 아직 실행하지 않아 미확인.
- 필터 수정: `games → GAME`, `technology → IT_DIGITAL` 힌트를 추가하고 `is_active=False`(최근 24시간 범위 내 상승이 끝난 현상)를 **읽기 전용 후보**에 포함한다. Active 후보부터 News 조회를 우선한다. `shopping`/`other` 등은 실제 분야 근거 없이 FASHION/BEAUTY/FOOD로 추정하지 않고 원본 카테고리 분포에만 남긴다. 세부 Category와 게시 적격 판정은 기존 독립 검증 및 Writer의 책임이다.
- 실제 카드 검증 사례(수동 교차확인, **운영 게이트 미충족**): 검색어 `지드래곤`, 관측 시작 2026-11-22T13:30:00Z. 제목 제안 `지드래곤·김태호 PD '굿데이' 시즌2 제작 확정`; 요약 제안 `제작사 TEO가 2026년 11월 23일 음악 예능 '굿데이' 시즌2 제작과 2027년 상반기 공개 계획을 발표했다.`; 대분류 ENTERTAINMENT, 세부분류 `예능`; 링크 예시 https://www.yna.co.kr/view/AKR20261123042700005. 추가 근거: https://mobile.newsis.com/view/NISX20261123_0003878761. 두 보도는 제작사 발표에 대한 교차 보도이며 **프로그램 자체의 공식 게시 원문이나 자동 독립 사실 확인 구현 증거는 아님**. `trend_id/category_id`를 위조하지 않고, `source_title`·`thumbnail_url`은 NULL 제안. 출처의 연결 플랫폼은 실제 뉴스 원문 기준 `ETC`.
- 아직 미구현: 자동 본문/공식 원출처 확인 및 출처 동일성, SourceAdapter의 Writer-side 재조회, ID/TTL 최종 정책, DB INSERT, FastAPI/Expo 실기기 E2E. 이번 패치는 이들을 완료한 것으로 주장하지 않는다.

- **2026-11-23 실제 장애**: 사용자 WSL 실행에서 `SEARCHAPI_HISTORY_BLOCKED:HISTORY_HTTP_403` 발생. History API 공식 문서의 `Requires Subscription` 조건을 이전에 누락했음. 엔드포인트와 Bearer 방식은 맞지만, HTTP 403의 정확한 계정별 사유는 검증되지 않음. History 진단 도구는 **보조 기능으로만 유지**하고 반복 실행·추가 계정 설정 요구를 하지 않음. `HISTORY_ACCESS_FORBIDDEN`으로 구분·무재시도 처리. 원본 총량 복구는 현재 HOLD이며, 이미 수신한 3/3회 KR 뉴스 메타데이터 및 교차확인된 '굿데이' 발표 사건의 **비게시** 경로 검증으로 전환.

## 2026-11-23 통합 계약 첫 구현 증거 (비운영)

- PR #140에 `tests/api/test_searchapi_trend_card_integration.py` 추가: 기사 형태의 제목·자체 요약·YNA 원문 URL을 **격리 DB 트랜잭션에서만** 기존 `insert_trend_item` 공통 DML로 저장한 다음, 실제 `GET /api/trends`의 제목·요약·ENTERTAINMENT 카테고리·`ETC` 원문 링크와 `inspect_snapshot`의 중복 SKIP 계약을 확인한다. `trend_id`/`category_id`/`source_id`는 임의 수치가 아니라 **격리 DB 자동 발급 ID**를 사용한다. `HIDDEN` 행이 공개 API에 보이지 않는지도 검증한다.
- `frontend/__test__/trend/TrendCard.test.tsx`에 같은 실제 기사 모양의 API 데이터에 대한 컴포넌트 계약 검증 추가: 엔터테인먼트/예능 표시, NULL 이미지·출처 제목 수용, 원문 보기 클릭 시 지정 YNA 링크만 전달. Jest fixture ID는 테스트 식별자로, 실제 DB 레코드가 아니다.
- 위 변경은 **테스트 코드만 추가/보강**한 것으로, 자동 SourceAdapter/독립 기사 사실 확인/운영 Writer 허가/운영 DB 게시의 구현이나 성공 증거가 아니다. 이 환경에는 저장소 실행용 테스트 DB 및 Expo 의존성·CI 실행 환경이 없어 두 신규 테스트의 실제 PASS 결과는 미확보. 해당 테스트는 승인된 `trend_leader_test` 대상과 설치된 Frontend 의존성에서 추후 실행해야 한다.
- 다음 기능 구현을 가로막는 확정 전 정책: Google 검색어가 아닌 **뉴스 사건 단위 source identity와 중복 기준**, 기사 원문 독립 검증이 가능한 근거 수준, 게시/노출 신선도. 이를 보장하지 않고 News 메타데이터를 `ACTIVE` Snapshot으로 변환하는 코드는 생성하지 않는다. 기존 독립 Writer 경계·G6·OS Timer는 그대로 유지.

## 2026-11-23 독립 원출처 교차검증 후속 결정 및 비게시 구현

- **사용자 확정**: 서로 다른 언론사/원출처 2건의 실제 기사 본문과 핵심 주장 교차확인을 우선한다(기존 B안). 두 URL 또는 검색 결과 제목만 있다는 이유로 게시하지 않는다. 동일 언론사의 별도 호스트/URL은 1개로 취급하고, 동일 본문의 재배포는 차단한다. 서로 다른 언론사의 공통 보도자료 전재도 완전한 독립 사실 확인으로 간주하지 않는다.
- `backend/app/trend_collection/searchapi_evidence.py` 신규: 검색 후보·관련 뉴스 메타데이터와 별도 원문 관측값 2건을 대조하는 **순수 검토용 평가기** `assess_cross_source_evidence`. 비정상 URL, 동일 발행 조직 도메인, 원문 미제공, 본문 주장 문구 부재, 날짜·관측 시각 불일치, 동일 본문을 HOLD하고, 형식 검증 성공해도 **REVIEW_REQUIRED + publish_authorization=NONE**만 반환한다. 기사 본문 원문은 보존·출력하지 않으며 증거 fingerprint에 본문 해시를 포함한다. 본문 내 문구 존재는 부정/맥락/인용·배포자료 전재를 판별할 수 없으므로 사실 확인이나 권리 검증을 대신하지 않는다.
- `backend/tests/trend_collection/test_searchapi_evidence.py` 신규: 정상 검토 후보 / 뉴스 메타데이터만 전달 / 원문 없는 경우 / 동일 발행사 / 동일 본문 / 단순 제목 / 내용 불일치 / 만료 관측 / 부적절 URL / Negation 포함 문구 / 본문 변경 시 Digest 변경 등의 격리 테스트 추가. **GitHub 코드 반영 및 줄 길이 정적 검사만 수행**, 실제 pytest·Ruff PASS는 아직 미확보.
- **현재 미구현(동작 경계)**: 외부 뉴스 원문 HTML을 독립적으로 읽고 출처·기사 본문을 추출/검증하는 안전한 Reader, 보도 출처의 실질적 독립성·주장 의미 검증, 자동 게시 승인 근거, News Event stable identity와 보존/노출 TTL, SearchApi용 운영 SourceAdapter 등록, 실제 게시·DB·APK E2E. 현재 작성한 `ArticleObservation`은 원문 Reader가 반환해야 할 값의 계약일 뿐, 생성 자체가 증거의 진위를 증명하지 않는다. 이 단계를 넘어서기 전에 허위 검증 성공을 게시 Snapshot으로 승격하지 않는다.
- **사건 동일성 정정**: 2025-12-10 뉴시스는 이미 지드래곤·김태호 PD의 `굿데이` 시즌2 계획을 보도했다(https://www.newsis.com/view/NISX20251210_0003435791). 따라서 2026-11-23 카드 샘플의 신규 사실은 단순 '시즌2 최초 제작 확정'이 아니라 **2027년 상반기 공개 계획 발표 및 신규 출연진 관련 발표**로 구분해야 한다. 이전 카드 테스트 제목·요약도 이 구분에 맞게 수정. 과거 보도 링크는 사건 동일성 점검용이지 현재 SearchApi 조회 또는 원문 자동 확인의 실행 증거는 아니다.

## 단계와 성공 조건 — 추가 우회 인프라 없음

1. Discovery: `geo=KR`, `time=past_24_hours`; Engine/지역/기간 확인, 1회 조회, 주요 20후보 상한. SearchApi 분야는 Root 힌트에 불과하며 beauty_and_fashion은 패션·뷰티 양쪽 가능성이므로 확정하지 않는다. 저위험 범위에 속하는 후보만 다음 단계로 전달한다.
2. Evidence: 후보 News API를 필요한 경우 최대 2건 조회(요청 전체 3건/Cycle). 기사 제목/URL/게시시각은 '발견'만 뜻하며 기사 본문·공식 출처의 사실과 일치 여부는 별도 확인한다. 증명되지 않는 주장·부정확한 분류·위험한 주제는 자동 게시하지 않는다. 사용자 열람 링크는 실제 검증한 출처에 연결한다.
3. Publication: 기존 SourceAdapter 패턴으로 독립 수집/Writer 재검증, 현재 `CategoryCatalog` 및 DB Parent/Child 검증, Journal과 중복 차단을 재사용. 기존 `trends`, `trend_sources`, `trend_category_map` 외 Schema 변경 없음. Source/Trend 중복 식별은 실측 응답 안정성과 기존 normalized_title UNIQUE를 대조해 Writer 연결 직전에 확정한다.
4. Delivery: 기존 `GET /api/trends`, `/api/trends/personalized`, `TrendListItem`, `TrendCard` 재사용. 새로운 React Native 화면·공개 API·추가 서비스·AI 호출 없음. Source의 `platform`은 실제 연결 대상 플랫폼 기준으로 저장하고 Google Trends는 발견 경로/출처 표시로 구분한다.
5. Operations: 기존 승인 프로필/G5/G6, 역할 분리, 보호 Secret, Journal 불확실 커밋 시 HOLD, 6시간 **전역** 간격·Batch 1 유지. **Godot Timer는 현재 중지**, 운영 복구와 SearchApi 활성화는 별도 승인. 기존 3309와 `/opt` 비변경.

## 가장 작은 검증 게이트

- 단위 테스트: KR 응답/잘못된 필드/빈 결과/신뢰할 수 없는 URL/중복/쿼리 상한/인증 헤더만, 네트워크 Mock.
- 단건 실제 요청(사용자 제공 서버측 Key, 노출·저장 금지): KR 후보와 관련 뉴스 필드, `news_token` 안정성, 지역/시간 확인. 권리·이용조건과 API 사용량 준수.
- 독립 증거 검증: 최소 실제 근거 1건과 출처 일치·카테고리 Child 검증. URL은 현재 단계에서 **구문만 확인**하므로 향후 내용 접근 시 DNS/IP/Redirect 재검증 필수.
- 실제 게시 허가 후: 신규 후보 1건 → MariaDB → API → 실기기 TrendCard/원문 보기, 동일 항목 재실행 SKIP 및 실패 HOLD.

## 제외/미확정

- Google Trends 원본 검색량 표/이미지/기사 본문 재게시, 실제 검색 순위를 자체 정확한 랭킹으로 제시, 미검증 AI 생성 주장, 대규모 크롤링·신규 DB·인프라·관리자 UI.
- SearchApi의 데이터 보유/표시 허용 회신은 Google·원문 제공자의 권리를 대체하지 않는다. 실제 사용하는 최소 데이터의 출처 표시·저장·공개 범위만 검토하고, 불명확한 행위/소스에 한해 HOLD 한다.
- `start_date`의 유효한 고유 사건 ID 여부, 동일 검색어 재상승/제목 충돌, 카드 노출 만료와 6시간 Batch 1 공급량은 Writer 연결 시 실제 응답과 기존 설계 대조 후 최소 확정. 임의 UNIQUE 변경·Cooldown 완화 금지.

## 근거

- SearchApi Trending Now 공식 문서: https://www.searchapi.io/docs/google-trends-trending-now-api
- SearchApi Trending Now News 공식 문서: https://www.searchapi.io/docs/google-trends-trending-now-news-api
- SearchApi Terms (Data Licensing): https://www.searchapi.io/legal/terms
- 프로젝트 `Trend_Leader_Current_Work.md`, `Trend_Leader_IGDB_Supply_Design_FROZEN_v1.0_20261120.md`, `Trend_Leader_AI_Development_Guidelines.md` §2.4.1.
