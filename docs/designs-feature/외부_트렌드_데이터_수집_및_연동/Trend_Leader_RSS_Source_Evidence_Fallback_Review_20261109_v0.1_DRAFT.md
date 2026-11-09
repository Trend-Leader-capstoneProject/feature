# Trend Leader — RSS / 원문 출처 / 관측 근거 Fallback 검토안 v0.1

> 상태: **REVIEW DRAFT (미동결 / 미구현 / 미게시)**  
> 작성 기준: 2026-11-09 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`  
> 검토 브랜치/HEAD: `dev` / `c1f1dc874b54e59f7a7c86d5886324de3a2e9cb6`  
> 작업 범위: **기존 문서·코드의 읽기 전용 대조**. GitHub, 데이터베이스, 배포 설정, 외부 서비스에 쓰기 작업 없음. 자동 테스트/실기기 테스트 수행하지 않음.

## 1. 현재 채팅에서 합의된 방향

1. 트렌드 발견 주 소스로 Google Trends RSS를 **구상**한다. 다만 실제 자동 접근·저장·게시에는 별도의 권한 확인과 Gate 통과가 필요하다.
2. RSS에 관련 기사 URL이 있다면 우선 사용하고, 부족할 때만 OpenAI 웹 검색을 통한 관련 기사 탐색을 **후속 설계 후보**로 검토한다.
3. 시연 MVP에서 AI가 탐색할 콘텐츠는 **뉴스 기사 중심**으로 한정한다. SNS·커뮤니티·공식 자료 등을 광범위하게 자동 탐색하는 것은 후속 확장으로 둔다.
4. 기사 원문이 없다는 이유만으로 **발견된 트렌드 사실 자체를 없애지는 않는다**는 방향에 합의했다.
5. 다만 원문 링크가 없으면 관측 근거 등 검증 가능한 정보를 보여주며, 확인되지 않은 유행 원인은 생성하지 않는다.
6. 이 합의는 **제품 지향점**이며, 기존 FROZEN 후보 검증 계약이나 운영 Gate의 자동 변경·게시 허가가 아니다.

## 2. 2026-11-09 dev 코드·문서에서 확인한 사실

| 영역 | 현재 확인 결과 | 주요 근거 |
|---|---|---|
| RSS Parser | `ParsedCandidate`에 트렌드 제목, `rss_published_at`, RSS의 `ht:news_item` 제목·URL·출처 제공자 파싱. 트래픽/검색량 필드는 현 `ParsedCandidate` 계약에 없음 | `backend/app/external_trends/types.py`, `rss_parser.py` |
| RSS P3 Validator | 적격 기사 출처가 0건이면 `DEFERRED(NO_ELIGIBLE_SOURCE)`; `WOULD_ACCEPT`는 출처 1건 이상 필수. 실데이터 저장/게시 금지 | `candidate_validator.py`, RSS P0~P3 v1.1 FROZEN §6.3~6.5 |
| 목록 Backend DTO | `TrendListItem.latest_source: TrendLatestSource | None`, `summary`도 nullable. DB 조회 Service/Builder가 Source 없으면 `None` 제공 | `backend/app/schemas/trend_schema.py`, `trend_list_item_builder.py` |
| 프론트 카드 | Source 없으면 `출처 정보가 없습니다.` 안내, `원문 보기` 버튼 미표시. 관련 테스트 구현 확인 | `frontend/src/features/trend/components/TrendSourceSection.tsx`, `frontend/__test__/trend/TrendCard.test.tsx` |
| 출처 ORM | `trend_sources.source_url`은 각 **행에서는** non-null. 트렌드에 Source 행이 반드시 있어야 하는 제약은 없음 | `backend/app/models/trend_source.py`, 전체 목록 v1.0.14 |
| 시연용 콘텐츠 | MVP-A는 권리 확인·자체 작성/수동 확보·개별 G4 승인 자료 기반. G6 운영 프로필 HOLD | `docs/operations/trend-publication/policy/...v0.3_POLICY_CONFIRMED.md` |
| 실 RSS | Google RSS 반복 요청·보존·앱 공개에 필요한 권한 아직 미확인, **RSS-OPS HOLD** | 같은 운영 Gate v0.3 |
| P4 Writer | 전체 P4 설계 **NOT FROZEN**. A1 v0.2 출처 안내 검증은 HTTPS 원문 URL을 필수로 하며 실제 게시는 HOLD | `docs/operations/trend-publication/README.md`, G5 A1 v0.2 DESIGN_REVIEW, P4 Final Review Addendum DRAFT |

**중요한 개념 구분:** `RSS 파서가 기사 0건을 읽어들일 수 있다` ≠ `P3가 해당 후보를 채택한다` ≠ `게시 Writer가 DB에 게시한다` ≠ `목록 API가 Source 없는 기존 Trend를 표시할 수 있다`.

## 3. 충돌/미정합 및 영향

### C-01. Source 0건의 검증 계약과 표시 방향

- 이번 지향점: 기사 미확보라도 관측 근거가 검증되면 트렌드를 표시하고 싶다.
- RSS P3 v1.1 FROZEN: 적격 Source가 0건이면 `DEFERRED` 및 유효 저장 후보 아님.
- 전체 목록 v1.0.14: **이미 DB에 존재하는** Source 없는 Trend는 표시 가능.
- **판단:** 목록 조회의 nullable 계약은 보존할 수 있다. P3 `DEFERRED`를 무단으로 `WOULD_ACCEPT`로 변경하면 FROZEN을 침해한다. 별도 발견 후보/관측 근거/게시 자격 경계가 필요하다.

### C-02. Google RSS 관측값 활용과 운영 이용 권한

- 이전 대화에서 RSS의 관측 시각·검색량을 근거 UI로 표시하는 방향을 검토했다.
- 운영 Gate v0.3: Google RSS 파생 데이터의 자동 접근·DB 보존·앱 공개 권한은 **HOLD**.
- 현재 Parser `ParsedCandidate`에는 RSS 트래픽 수치 필드가 없으며, `rss_published_at`은 별도의 실제 수집·관측 시각으로 자동 간주할 수 없다.
- **판단:** 시연 MVP-A에 Google RSS 관측값을 바로 노출하지 않는다. 별도 승인이나 독립 근거 없이 Google Trends 공식 관측으로 가장하지 않는다.

### C-03. 링크 없는 콘텐츠와 기존 A1/P4 게시 통제

- 이번 지향점: 기사 원문 링크 없을 때도 근거 정보를 표시한다.
- A1 v0.2 출처 안내 검사: HTTPS 원문 링크 필수, `source_title` 자체 작성 안내 문구는 제한적 조건에서만 허용. **실제 G5/G6 HOLD**.
- P4 최신 DRAFT: 첫 연결 경로는 Source **정확히 1건**을 요구하는 제안; P4 전체 NOT FROZEN.
- **판단:** 링크 없는 트렌드를 자동 게시하도록 확장하는 것은 단순 UI 변경이 아니라 게시 적격성/승인/배치 계약 변경이다. 기존 보호 경로를 우회하는 임시 Seed·INSERT·API를 만들지 않는다.

## 4. 설계 선택지

| 대안 | 구현/시연 방법 | 장점 | 한계 및 비용 |
|---|---|---|---|
| A. 현재 MVP-A 엄격 유지 (**추천**) | 실제 시연 카드에는 개별 검토·권리 확인·유효 링크를 가진 콘텐츠만 게시 후보로 취급. 소스 없는 상태/근거 표시 UI는 합성 Fixture·오프라인 사전 검증에서 다룬다. | 기존 G4/G5/G6 통제 보존, 마감 전 회귀 범위 최소 | 라이브 RSS 자동 공개 및 링크 없는 카드의 실제 게시 불가. 운영 Gate 통과는 별도 과제 |
| B. '관측 근거만 존재하는 콘텐츠' 게시 경로 신규 설계 | 독립 관측 증거의 유형/진위/사용 권리/화면 데이터/API/개별 승인 계약을 새로 확정한 뒤 P4·G5·UI에 연결 | 원문 기사 부재에도 게시 가능 | FROZEN/게시 계약 변경, 운영 권리·승인·테스트 부담 큼. 현 MVP 마감 기준 위험 |

**권고:** A안으로 시연 안정성을 우선하고, B안은 별도 설계 변경 요청으로 취급한다. 이는 사용자 합의한 장기 제품 방향을 폐기하는 것이 아니라 실제 운영 승인 경계를 구분하는 조치다.

## 5. 화면 요구 조건 후보 (아직 API 계약 변경 아님)

| 확인된 상태 | 자료 출처 표시 | 링크/UI | 실제 앱 게시 전제 |
|---|---|---|---|
| 개별 검토된 관련 기사 URL 있음 | 검증된 출처 안내 문구 또는 허용된 정보 | `원문 보기` | 콘텐츠 승인 + 게시 Gate 통과 |
| 뉴스는 없지만 적법하게 확보·검증된 **다른** 근거 URL 있음 | 자료 성격 명시, 뉴스 원문이라고 오인시키지 않음 | `근거 보기` 등 별도 표기 **후속 후보** | 해당 자료의 이용권한·표시 정책 및 A1/P4 승인 필요. 시연 MVP의 뉴스 중심 범위와 충돌 여부 검토 |
| 기사·외부 URL 없음, 독립 검증된 관측 증거 있음 | 근거 종류·관측 주체·시각 의미 구분 | 임의의 `원문 보기` 버튼 금지. 오프라인 UI 검토 가능 | 현 A1/P4 게시 자격을 자동 통과하지 못함. **실제 게시 HOLD** |
| 검증 근거 자체 없음 | '관측 확인'이라는 문구 금지 | 인용/링크 생성 금지 | 게시 후보에서 제외/HOLD |

시각은 `RSS pubDate`, `기사 발행일`, `수집·관측 일시`, `G4 승인일`, `DB 기록 시각`을 서로 대체하지 않는다.

## 6. 책임 분리 원칙

```text
[합성 RSS 데이터 / 향후 허가된 RSS]
  └─ Parser → 정규화 → P3 Candidate Validation (FROZEN)
        ├─ WOULD_ACCEPT → 기술적 후보 (게시 승인 아님)
        ├─ DEFERRED     → 검토/근거 보완 필요 (DB Writer 직행 금지)
        └─ SKIPPED      → 해당 조건의 후보 제외

[개별 검토한 자체 작성·수동 확보 콘텐츠: MVP-A]
  └─ G4 개별 승인 → A1 자료 대조 → G5 실행 통제 → G6 운영 승인
        └─ 실제 승인 조건 충족 후에만 게시 (현재 HOLD)

[기존 GET /api/trends 목록]
  └─ DB에 적격하게 저장된 Trend 조회
        ├─ latest_source != null → 원문 URL 버튼
        └─ latest_source == null → 기존 안내 문구, 추가 근거 UI는 별도 계약/자료 필요
```

**외부 AI 웹 검색**은 P0~P3에 포함되어 있지 않다. 후속 P4+ 또는 독립 연구용 외부 검색 어댑터에서만 API 접근·데이터 권리·비용·재시도·출처 검증 계약을 결정한다. OpenAI가 검색에 사용한 URL과 검증된 기사 원문은 동일시하지 않는다.

## 7. 검증할 Acceptance Criteria 후보

- AC-01. `ParsedCandidate.source_candidates = ()`는 현재 P3 FROZEN 정책대로 `DEFERRED(NO_ELIGIBLE_SOURCE)`다.
- AC-02. Source 0건 입력도 Parser에서 입력 형식 자체의 오류로 처리하지 않는다.
- AC-03. DB에 적격하게 존재하는 Source 없는 `Trend`는 공개 조회 DTO에서 `latest_source = null`로 표현할 수 있다.
- AC-04. 프론트 Source 없음 상태에서 `원문 보기` 클릭 대상이 존재하지 않는다.
- AC-05. 권한 미확인 Google RSS 데이터를 MVP-A 게시/저장/응답/로그에 섞지 않는다.
- AC-06. 기사 URL이 있더라도 실제 링크/표시 자격/G4 승인/G5/G6 Gate가 미충족이면 게시하지 않는다.
- AC-07. 추후 독립 관측 증거 표시를 도입할 때는 근거 ID·원천·관측 시각 의미·조회 권리와 화면 라벨을 검증한다. 시각이 없으면 임의 생성하지 않는다.
- AC-08. AI가 기사 부재를 자체 추론으로 메우지 않으며, 유행 원인을 원문 근거 없이 사실처럼 반환하지 않는다.

> **검증 상태:** 현재 파일의 소스/테스트 코드를 읽어 수용 기준을 제시했을 뿐이며, 이번 단계에서 자동 테스트를 실행하지 않았다. AC-05~08은 향후 추가 검증이 필요하다.

## 8. 바로 이어갈 작업

1. 현 동결 계약은 그대로 두고 이번 충돌 기록을 **REVIEW DRAFT**로 보존한다.
2. MVP-A 시연에 사용할 자체 작성 트렌드와 검증 링크 및 G4 검토 증거를 기준으로 **1개 콘텐츠의 end-to-end 출처 추적**부터 점검한다.
3. 링크 없는 근거 표시가 꼭 실제 공개 앱에 필요한지, 아니면 후속 제품 요구인지를 운영 승인 책임자와 구분한다. 필요하다면 A1/P4에 대한 **명시적 변경 제안**으로 분리한다.
4. RSS/OpenAI 실데이터 연동은 권한과 수집·저장·공개 범위를 확정하기 전 **실제 외부 API 호출·영속 저장·자동 게시 금지**를 유지한다.

## 9. 근거 문서/코드 링크

- [게시 운영 README](https://github.com/Trend-Leader-capstoneProject/feature/tree/dev/docs/operations/trend-publication)
- [RSS P0~P3 v1.1 FROZEN](https://github.com/Trend-Leader-capstoneProject/feature/tree/dev/docs/designs-feature/%EC%99%B8%EB%B6%80_%ED%8A%B8%EB%A0%8C%EB%93%9C_%EB%8D%B0%EC%9D%B4%ED%84%B0_%EC%88%98%EC%A7%91_%EB%B0%8F_%EC%97%B0%EB%8F%99)
- [RSS parser](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/backend/app/external_trends/rss_parser.py)
- [RSS candidate validator](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/backend/app/external_trends/candidate_validator.py)
- [Trend schema](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/backend/app/schemas/trend_schema.py)
- [Trend Source UI](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/frontend/src/features/trend/components/TrendSourceSection.tsx)

