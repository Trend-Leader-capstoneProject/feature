# Trend Leader — 실데이터 공급원 선정 Final Review v0.1

> **상태:** FINAL REVIEW / **선정 권고안** / **NOT FROZEN** / 구현·외부 API 호출·실데이터 게시 승인 아님  
> **기준일:** 2026-11-12 (KST)  
> **코드 기준:** `Trend-Leader-capstoneProject/feature`, `feat/phase4b2-protected-review-registration`, HEAD `2c2ea11c75c81d80c577a8435153b4352c757083` (확인 시점)  
> **직접 전제:** 2026-11-12 `Trend_Leader_Real_Data_API_Pipeline_Design_First_Pass_v0.1_DRAFT_20261112.md`; 기존 실데이터 사전 결정 기록; P4 Addendum v0.2 DRAFT; 4B-2 FROZEN; Google RSS Gate v0.3; G5 P1 HOLD. 외부 API 실제 호출·계정/요금제 테스트는 이 리뷰에서 실시하지 않음.  
> **시연 기준:** 사용자 실기기 E2E-00~05 수동 검증에 근거한 `[DEMO]` 앱 시연 GO. 실제 콘텐츠 자동 수집/게시 및 운영 G5·G6는 HOLD.

## 0. 핵심 결론

1. **MVP 첫 공급원 실험은 OpenAI Responses API + `web_search`를 ‘트렌드 주제/원문 후보 발굴’에 사용하는 하이브리드 경로를 1순위로 권고**한다. OpenAI가 자체적으로 ‘급상승 순위/관측량’을 제공한다고 주장하지 않는다. 사용자가 선택하는 구체 모델·비용 상한·테스트 범위는 구현 전 확정한다.
2. **검증된 원 출처가 진실의 기준**이다. 검색 모델의 요약·인용·검색 스니펫이 원문 열람/권리 증거가 아니다. 검색 결과와 앱 게시값 사이에 사람의 사실·권리·위험 검토(G0/G4) 및 P4 G5/G6 운영 Gate를 유지한다.
3. **GDELT Cloud v2는 2순위 뉴스/사건 공급원**이지만 요금제/API 접근과 재배포 권리 확인이 선결이다. 특히 source-native 필드와 GDELT Cloud 생성 Stories/Events/분류·요약은 권리가 다르다. 요금제별 *Academic & Research* 등 예외 가능성도 있어 모든 재배포를 일률적으로 금지한다고 단정하지 않는다. 프로젝트의 구독/면허 조건은 미확인.
4. YouTube Data API는 인기 **동영상** 관찰 도구로 검토하고 이를 임의의 인기 **주제**·파생 점수로 변환하지 않는다. GitHub Releases는 IT 분야 연결 검증용 저위험 대안이며 범용 유행 주제 공급원은 아니다.
5. **Google Trends RSS-OPS 계속 HOLD.** 회신이 없다는 것은 허가가 아니다. NAVER API HUB 검색어 트렌드는 기존 사용자 고객지원 회신에 따른 **내부 보조 판단용**만 유지하고 원본/파생 지표를 외부 OpenAI 입력으로 보내거나 앱에 게시하지 않는다.
6. 11월 17일 이전의 실현 가능한 새 증거 목표는 **실제 후보 1~3건의 읽기 전용 수집·출처 검증·검토 자료 생성**, 운영 게시 0건이다. 기존 시연 DB·앱은 그대로 보존한다. 진짜 앱 게시를 목표로 계속 유지하려면 G0/G4/G5/G6의 별도 실증·승인이 선행되어야 한다.

## 1. 문제 정의와 평가 기준

제품 목표: ‘관심사별 트렌드 주제’를 지속적으로 발굴하고 관련 원문을 검증한 뒤 API로 공급. 단순 기사/동영상/릴리스 항목을 트렌드 주제로 가장하지 않음. 주기적 무인 후보 발굴은 장기 목표이며 초기 운영자 검토는 임시 검증 단계.

평가 축: (A) Trend Leader의 6개 내외 관심 분야 범위와 **주제 발견** 적합성, (B) 출처 추적·재검증 가능성, (C) 자동 호출·저장·공개 이용 권리, (D) 비용·Quota·계정 의존성, (E) 11/17 전 격리 PoC 가능성, (F) 기존 FROZEN·G0~G6 경계 준수. 특정 소스 하나가 모든 축에서 우월하다고 단정하지 않음.

### 1.1 확인된 기술 상태

- 기존 공개 `/api/trends`와 인증 `/api/trends/personalized`는 `ACTIVE` DB Trend를 조회. 데이터 공급이나 G4 승인을 책임지지 않음.
- ORM `Trend.status` 기본값은 `ACTIVE`: 무단 INSERT가 공개로 이어질 수 있어 미승인 실제 후보는 개발/서비스 DB에 `ACTIVE`는 물론 `HIDDEN`으로도 준비 INSERT하지 않는 **기존 G5 P1 계약**을 준수.
- `Trend.summary`, `Trend.thumbnail_url`, `TrendSource.source_title`은 nullable. 첫 실데이터 후보의 썸네일·AI 요약을 필수로 만들지 않음.
- `backend/app/external_trends/`는 Google RSS **합성 Fixture 기반** Parser/Normalizer/Validator. OpenAI/GDELT의 실사용 Adapter가 이미 있다는 증거가 아님.
- 4B-2 FROZEN은 **Windows 로컬 보호 검토·철회**에 한정되며 운영 P4 Writer/Journal 완성을 의미하지 않음.

## 2. 외부 공식 문서 검증과 공급원 비교

| 후보 | 공식적으로 가능한 것 | 제품 적합성 | 확인된 제약·미검증 | 권고 |
|---|---|---|---|---|
| **OpenAI Responses `web_search`** | 최신 웹 검색, `web_search_call`, 인용 URL/제목, 참조 URL 목록(`include`), 검색 도메인 필터 | 분야횡단 후보 발견 및 공식 원출처 탐색에 높음 | 구조화된 급상승 순위·빈도·원문 소유권·검색 포괄성 보장 없음. 모델 출력과 원문 별도 검증, 사용량 비용 | **1순위 읽기 전용 후보 발견 실험** |
| **GDELT Cloud v2** | REST API로 생성 Events·Stories·Entities 등 조회, API 키·요금제 기반 | 세계 뉴스·사건 중심에서 높음, 생활·게임·패션 불균형 가능 | generated 필드의 고객 공개는 요금제/별도 서면 허가에 좌우됨. source-native도 원 발행자 약관 준수. 무료 계정 API 권한 제한 가능 | **2순위, 이용조건/요금제/필드별 권리 확인 후** |
| **YouTube Data API** | `videos.list`의 `chart=mostPopular`, 지역·카테고리, Quota 1 unit/call | 게임·엔터테인먼트 영상 관찰에 좋음 | 영상 인기도 ≠ 주제 인기도. API 데이터 저장·표시·파생 지표에 정책 제한 | **별도 영상 후보 PoC** |
| **GitHub REST Releases** | 공개 Repo `GET /repos/{owner}/{repo}/releases` 조회 (공개 리소스는 무인증 가능) | 공식 릴리스 이벤트 검증은 쉬움 | IT 편향, 릴리스 = 인기 트렌드 아님. Repo 선정 편향·API/재사용 조건 점검 | **첫 직접 HTTP Adapter의 대체 검증용** |
| **NAVER API HUB 검색어 트렌드** | 지정 검색어 그룹의 상대 관심도 (프로젝트 기존 고객지원 기록) | 이미 정한 후보의 보조 교차검증 | 공개/외부 AI 제공 제한, 무인 자동 채택 허용 여부 미확정 | **내부 검증 전용** |
| **Google Trends RSS** | 주제별 급상승 후보의 제품 적합성 높음 (기술 PoC는 합성 XML) | 높음 | 자동 요청·보관·게시 권한 미확정; 사용자 회신 부재 | **RSS-OPS HOLD** |

### 2.1 OpenAI Responses API: 검증된 기능과 잘못 해석하기 쉬운 것

- **공식 기능**: 새로운 Responses 통합에는 `tools: [{"type":"web_search"}]`; 인용 annotations, `include: ["web_search_call.action.sources"]`; 도메인 허용/차단 필터, live/cached access 제어 제공. `tool_choice:"auto"`는 검색 생략 가능하므로 실제 검색 필수 테스트에서는 공식 문서의 `required` 또는 구체적 tool-choice 지원을 확인해 적용할 것. 사용할 모델의 `web_search` 지원·버전을 고정해 테스트한다.
- **요금(2026-11-12 문서 조회)**: 기본 Web search **$10/1,000 tool calls** + 검색 컨텍스트 토큰은 모델 요금 적용. 다른 모델 input/output 비용, 추가 tool 호출, 환율·세금은 별도. 무료/무제한 검색이라 추정하지 않음.
- **정확성**: 출처 인용은 검색한 웹페이지에 관한 provenance 단서이지 기사 내용의 독립 검증·트렌드 급상승의 계량 증명이 아니다. 모델 생성 제목/설명은 운영자가 원출처에 근거해 재검토해야 한다.
- **저작권/권리**: OpenAI 서비스 계약은 고객 출력 사용의 정확성·적절성 평가 책임, 제3자 서비스 약관 적용을 명시. 모델 출력 소유 조항이나 링크의 존재가 제3자 기사 제목·사진·본문의 재배포 권리를 양도하지 않는다.
- **보안**: API 키는 Backend 관리 환경에만 저장. 휴대전화/Expo/공개 API 응답에 전달 금지. 외부 웹페이지 텍스트는 prompt injection 위험을 가진 **비신뢰 입력**이다. 내부 NAVER 지표·승인 비밀·API Key·개인정보를 검색 입력으로 보내지 않는다.
- **구분**: Responses `web_search`는 ‘검색·조사 도구’이지 ‘역사적인 검색량 시계열’이나 ‘공식 급상승 랭킹 피드’가 아니다. `rank`, `popularity_score` 등 없는 값을 만들어 DB에 저장하거나 UI에 표시하지 않는다.

### 2.2 GDELT Cloud: 원천 데이터와 생성 데이터의 권리 분리

- GDELT Cloud v2는 GDELT DOC 2.0(기존 공개 검색 API)과 **다른 API·인증·상품**이다.
- 공식 약관은 source-native 원천 사실·자료와 GDELT Cloud-generated Events/Stories/분류·요약·점수를 구분. 원천 사실은 원 발행자의 조건을 따르며, GDELT가 생성한 필드나 데이터셋을 고객에게 재배포하려면 별도 계약 또는 사용 중인 플랜에 명시된 예외가 필요할 수 있다.
- **Academic & Research 등 요금제별 특별 권리 문구도 존재**하므로, 대학 캡스톤이라는 사실만으로 허가가 생긴다고 단정하지 말고 실제 계정의 플랜/라이선스 조건을 확인한다.
- 가격·무료 평가/API key 사용 기간은 변동 가능. 공식 요금 페이지의 현재 계정 권한을 실제 연결 전 확인한다.
- 기사 링크만 얻었다 해도 원문 기사 제목·본문·사진 게시권한은 별도다.

### 2.3 YouTube / GitHub / Google / NAVER 경계

- YouTube `mostPopular`는 ‘동영상’ 반환. YouTube 데이터에서 임의의 검색 관심도/순위·자체 인기 점수를 계산·게시하는 것은 정책과 충돌할 수 있으므로 금지 또는 별도 법적/계약 검토. Non-Authorized Data의 저장 기간·갱신 제한도 별도 점검.
- GitHub Releases는 공식 제품 이벤트 검증용 직접 API로 단순하다. 공개 이벤트라도 실사용 제목/이미지/본문 활용 시 해당 저장소 라이선스 및 출처 조건 별도 확인.
- Google RSS: 회신이 없으므로 권한 승인 추정 금지. 기존 PoC의 `WOULD_ACCEPT`는 합성 시험 결과.
- NAVER: 기존 회신에서 제한된 내부 트렌드 분석값은 OpenAI 등 외부 AI에 제공하지 않는다. 해당 지표로 계산한 파생 점수도 앱에 게시하지 않는다.

## 3. 후보 아키텍처 2안과 최종 권고

### A. 직접 소스 API 우선

`Official Provider API → 구조적 레코드 → 후보 분류 → G4/A1 → (P4 G5/G6 별도) → DB`.

장점: 재현 가능한 필드·식별자·시간·쿼터; 공식 원본의 provenance. 단점: 각 공급원마다 분류·편향·권리/요금제 제한; 분야횡단 후보 발견이 어렵다.

### B. OpenAI 검색 우선 + 1차 출처 검증 (**권고**) 

`Responses web_search → 검색 후보와 URL 목록 → 독립 원출처 확인(공식/API/수동) → 자체 작성 제목/설명 초안 → G4 검토·승인 → A1/4A/4B-2 참조 → (P4 별도 승인) → 기존 Trend DB/API`.

장점: 분야횡단 발견, 새 UI/DB 테이블 없이 첫 후보 PoC 가능, 특정 검색 플랫폼 종속성 완화. 단점: 비용·비결정성·검증 노동, 모호한 주제/AI 오류, 웹 원문 접근 실패와 재배포 권리 제약.

**결정 권고:** `B`를 **실데이터 후보 발견 실험의 첫 출발점**으로 제한 채택하고, 검증 가능한 공식 API가 발견되면 해당 주제는 A 방식의 직접 데이터로 교차검증한다. 두 방식을 Provider 규칙 없이 합쳐 ‘AI가 모든 허가와 게시를 결정’하게 만들지 않는다. B가 실패하거나 비용/권리/정확성이 허용치 미달이면 A(제한된 공식 공개 릴리스 PoC)로 전환한다.

## 4. 최소 구현 범위와 비범위

### 포함 (사용자 구현 승인 전에는 설계만)

1. 하나의 Backend 전용 Responses API 웹 검색 호출에 한정해 실제 후보 **최대 1~3건**을 발굴. 요청 성공·결과·비용 확인. 모델·쿼리 전략·횟수 상한은 구현 승인 때 고정.
2. 각 후보의 `discovery_method`, `provider`, `searched_at_utc`, `source_url`, 원문 출처/항목 종류, `source_published_at`(있는 경우), `verified_observed_at_utc`(독립 관측이 있을 때만), 후보 자체 작성 주제, `category_candidate`, `reason`, `review_status=HOLD` 등의 **논리 Preview**를 정의. 실제 코드 필드/스키마를 지금 확정하지 않음.
3. 검색 결과 URL의 출처 식별·HTTP 접근/원문 근거(허용되는 접근 방식에 한함)·인용 일치·사실 검증·출처 표현의 이용 조건 확인. 원문이 접근 불가하거나 날짜가 모호하면 보류.
4. 기존 대분류/세부분류에 엄격 매핑; 주제 vs 단순 기사/영상 구별. 불명확하면 Review Required.
5. `401/403/429/5xx`, timeout, 빈 검색, citation 없음, 품질 미달, 모델 변경, 중복 주제/URL, 예산 초과는 HOLD·안전 종료. 재시도 제한.
6. 검증/비용/실행 시각/모델/출처 URL/결과 상태를 **권리와 비밀정보를 지키는 최소 메타데이터로 기록**. 원문 웹페이지 전체, 검색 스니펫, API 비밀, 개인정보, 미검증 이미지의 장기 저장 금지 또는 명시 권리 확인 전 보류.
7. 기존 E2E-00~05 `[DEMO]` 시연 경로 유지, 별도 검토용 로컬 출력에 `NOT_FOR_PUBLICATION` 명시. 실제 DB DML 0건.

### 제외

- P4 Writer/Journal/실제 G5/G6 구현 및 운영 승인.
- Google RSS 자동 접근 또는 비공식 검색/스크래핑 우회.
- NAVER 원본/파생 지표를 OpenAI에게 전송하거나 앱에 노출.
- OpenAI 검색 결과를 사실 검증 없이 자동 `ACTIVE` 게시.
- 모바일 앱에 OpenAI API Key 탑재, 사용자마다 직접 무제한 검색 호출.
- 새로운 공개 Trend API/DB Schema/관리자 대시보드, 24시간 스케줄러, 인기 점수/랭킹 조작.

## 5. 최소 Acceptance 검증

| ID | 검증 | 합격 기준 |
|---|---|---|
| SRC-01 | 모델과 API 계약 | 실제 지원되는 `Responses web_search`, 출처 포함 기능 및 비용/Quota 확인 |
| SRC-02 | 실제 후보 발견 | 사용자 승인된 소규모 호출로 후보 1~3건과 실제 URL 확보; 후보가 없으면 사실대로 FAIL/HOLD |
| SRC-03 | 독립 원문 확인 | URL 접근·주장·게시일/관측일 구분; 근거 불충분 시 `REVIEW_REQUIRED` |
| SRC-04 | 권리 분리 | 원문 제목/본문/이미지·AI 생성 요약/타사 생성 지표 사용조건을 따로 기록, 승인되지 않은 필드는 앱으로 전달 0 |
| SRC-05 | 도메인 유효성 | 실제 주제 vs 단일 기사/영상 판별, 기존 Taxonomy Child 매핑 실패 시 HOLD |
| SRC-06 | 안전 실패 | 401/403/429/5xx/타임아웃/출처 없음/모델 오류 → 앱·DB 영향 없이 중단, 무제한 재시도 없음 |
| SRC-07 | 비용 통제 | 호출 횟수·선택 모델·토큰·예산 상한을 명시하고 초과 차단; 키 유출 없음 |
| SRC-08 | 비게시 보장 | 원격 서비스 DB/개발 DB DML 0, Demo Seed 변경 0, 공개 API 변경 0, E2E baseline 유지 |
| SRC-09 | 정책 바인딩 | G0/G4/A1/4B-2/P4/G5/G6 상태 분리; `G6 HOLD`가 게시 시도 0건을 보장 |

## 6. 다음 행동 / 사용자 결정 Gate

1. 이 문서의 **‘Responses web_search 우선, 공식 원문 교차검증’ 방향을 사용자 승인**하면, 한 개 모델과 한 개 한정된 검색 시나리오(예: IT/디지털 공식 공개 자료, 또는 분야 2개)에 대한 **읽기 전용 구현 계약**을 Finalize한다.
2. API 계정/프로젝트 키·결제/예산·동작 모델 지원 여부를 사용자 환경에서 검증한다. ChatGPT Plus 구독은 OpenAI API 호출 크레딧과 동일하지 않다. 개인 API key 값은 공유하지 않는다.
3. Codex에 허용된 범위만 위임하고 Fixture 테스트 → 실제 API 1회 소량 검증 → 원문 수동 검증 → 결과 보고 순으로 실시. GitHub 커밋/푸시 및 다른 브랜치 변경은 기존 GitHub Write Safety Policy와 사용자 추가 승인 준수.
4. 발표까지는 합성 앱 데모 GO와 실제 후보 발견 PoC를 **독립적으로** 기록한다. 실데이터 실제 게시 GO가 필요하면 별도 P4 G5/G6 승인·정합성 검증 후 진행.
5. Google에 신규 회신이 오면 RSS-OPS 허용범위 재심사. 무응답을 승인으로 해석하지 않음.

**문서 상태:** 본 문서는 공급원 선정에 대한 **Final Review 권고**이며, `FROZEN` 설계·실 API 실행/영속 저장/게시·GitHub 문서 커밋·Codex 구현 승인을 대신하지 않는다.

## 7. 공식 참고 문헌 (2026-11-12 조회)

- OpenAI Responses web search: https://developers.openai.com/api/docs/guides/tools-web-search
- OpenAI API Pricing: https://developers.openai.com/api/docs/pricing
- OpenAI Services Agreement (API usage, 3rd party, output): https://openai.com/policies/services-agreement/
- OpenAI API Service Terms: https://openai.com/policies/service-terms/
- GDELT Cloud API v2: https://gdeltcloud.com/product/api
- GDELT Cloud Pricing: https://gdeltcloud.com/pricing
- GDELT Cloud Terms (2026-10-22로 노출된 검색 결과, 페이지 버전/계정에 따라 재확인): https://gdeltcloud.com/terms
- GDELT Cloud Acceptable Use & API Terms: https://gdeltcloud.com/acceptable-use
- YouTube videos.list: https://developers.google.com/youtube/data/reference/rest/v3/videos/list
- YouTube Developer Policies: https://developers.google.com/youtube/terms/developer-policies
- GitHub REST Releases: https://docs.github.com/en/rest/releases/releases
