# Trend Leader — 실데이터 API 공급 파이프라인 Design First Pass v0.1

> **DRAFT / NOT FROZEN / 외부 API 실행·운영 게시 승인 아님**
> 작성 기준: 2026-11-12 KST
> 코드 기준: `Trend-Leader-capstoneProject/feature` / `feat/phase4b2-protected-review-registration` / `2c2ea11c75c81d80c577a8435153b4352c757083`
> 근거: 기존 실데이터 연결 사전 설계 기록, P4 Addendum v0.2 (DRAFT), 4B-2 FROZEN, Google RSS 운영 Gate v0.3, G5 P1 HOLD 계약, README 및 실제 Backend Trend 모델·조회 API. 공식 외부 문서는 2026-11-12 조회.
> 이번 문서 생성 및 분석으로 GitHub, 로컬 DB, Docker 컨테이너, 외부 API 또는 앱 코드에 변경을 가하지 않았다.

## 0. 최우선 판정 — MVP 실기기

- E2E-00~E2E-05의 사용자 수동 보고에 근거하여 **[DEMO] 데이터 기반 실기기 발표 시연 GO**. E2E-05는 6/6 PASS.
- E2E-02 새로고침 시각적 피드백은 UX 개선 후보; 장애 차단 증거 아님.
- 실데이터 공급·무인 자동화는 구현 완료가 아니며, G0/G4/G5/G6 운영 PASS도 아님.
- 기존 발표 환경은 동결된 테스트 기준선으로 보존하고 P4·4B-2 실험으로 개발 DB 또는 데모 앱을 깨뜨리지 않는다.

## 1. 목표·비목표·경계

**문제:** 기존 `GET /api/trends` 및 `/api/trends/personalized`는 `ACTIVE` Trend를 읽지만 외부 API 후보의 적법한 취득 → 검증 → 승인 → 실제 게시 경로는 아직 완결되지 않았다. 현재 앱은 `[DEMO]` 목록 기반이다.

**제품의 장기 목표(기존 결정):** 운영자 개입 없는 주기적 후보 발굴·검증·공급. 초기 운영자 개별 검토는 단계적 검증 수단이지 수동 등록 앱으로 제품 목표를 변경한 것이 아니다.

**이번 P0(첫 구현 패키지의 목표):** 이용조건을 확인한 공급원 한 곳의 공개·허용된 API 경계로부터 1~3개 **실제 후보를 읽기 전용으로 취득·검증·구분된 결과로 출력**한다. 후보가 트렌드 주제인지, 단순 기사·영상인지 구분해 기록한다. 성공 시 원문 응답/개별 출처 권리·G4 승인 없이 서비스에 게시하지 않는다.

**비목표:** `ACTIVE/HIDDEN` 포함 개발/서비스 DB 쓰기, 기존 Demo Seed 재실행, 신규 public Trend API/DB 테이블/관리자 UI, G5/G6 PASS 승격, P4 APPLY·Writer·영속 Journal 구현, 승인 우회, Google RSS 실요청, NAVER 지표의 공개·외부 AI 전송, 무인 게시 스케줄러, AI 상세 분석 자동 생성.

## 2. 현재 확인한 기술 계약

- `backend/app/api/routes/trend_router.py`: `GET /api/trends`(비로그인), `GET /api/trends/personalized`(인증·관심사), Cursor/limit.
- `backend/app/repositories/trend_repository.py`: `Trend.status == ACTIVE` 조건으로 `(last_collected_at DESC, trend_id DESC)` 조회. G4/G6 승인이 조회 단계에서 별도 검증되는 구조가 아님.
- `backend/app/models/trend.py`: `normalized_title` UNIQUE, `status` ORM·서버 기본 `ACTIVE`(게시 우회 위험), `summary`/`thumbnail_url` nullable.
- `backend/app/models/trend_source.py`: `(trend_id, source_key)` UNIQUE, `source_url`, nullable `source_title`, `collected_at`, 플랫폼 열거형, optional 외부 ID.
- `backend/app/models/trend_category_map.py`: `(trend_id, category_id)` UNIQUE.
- `backend/app/external_trends/`: Google RSS **합성 Fixture 중심** Parser·Normalizer·Validator. 실사용 API Client·스케줄러·운영 Writer로 승격하지 않는다.
- `backend/app/db/seeds/demo_trends.py`: `[DEMO]` ACTIVE 25건·HIDDEN 1건의 로컬 시연 데이터. 이를 실제 수집·승인과 혼동하지 않는다.
- P4 Addendum v0.2: A1 v0.2 승인 원본 보존 + 참조 Envelope, 독립 Writer/Journal/실제 G4/G6 증거, 관측시각·권한·철회·Batch 전체 커밋/롤백, 현재 NOT FROZEN.
- 4B-2 FROZEN: 로컬 보호 검토·등록·철회는 P4의 게시 권한을 대신하지 않으며 `publish_authorization=NONE`, G5/G6 HOLD.

## 3. 공급원 결정 후보 — 확정 전 검토

| 후보 | 외부 문서에서 확인한 API | 제품 적합성 | 이번 잠정 판정 |
|---|---|---|---|
| YouTube Data API | `videos.list`의 `chart=mostPopular`, `regionCode`, `videoCategoryId` 사용 가능. 공식 문서상 호출 비용 1 quota unit. | 플랫폼 인기 **영상** 발견에 적합. 개별 영상을 독립 트렌드 **주제**·인기도 지표로 바꾸는 것은 별도 정책·도메인 검증이 필요. API 데이터 수명·표시·파생 지표·권리 및 표시 귀속 의무 주의. | **읽기 전용 API PoC 후보**, 게시·파생 이용 별도 검토 |
| GDELT | 기존 GDELT DOC 2.0 문서에서 기사 목록·검색·JSON/JSONFeed 제공 설명. 별도 **GDELT Cloud v2**는 `/api/v2/stories`, `/api/v2/events` 등 키 인증형 API로 문서화. | 뉴스·사건 연결에는 유용. 뉴스 출처 원문 권리·주제 중복·카테고리 편향 주의. **구 DOC 2.0과 Cloud v2를 동일 API로 취급하지 않음.** | **API 표면/현재 접근·조건 확인 후 후보** |
| GitHub REST Releases | 공개 저장소의 릴리스 목록은 공식 REST API로 인증 없이도 조회 가능(공개 리소스 한정). | IT/디지털 이벤트 출처 PoC는 쉬우나 범용 ‘유행 주제 탐색’과는 다름. 릴리스가 곧 트렌드 인기의 증거는 아님. | **기술 연결 대체 후보**, 제품 적합성 낮음 |
| NAVER API HUB 검색어 트렌드 | 프로젝트의 기존 고객지원 회신은 내부 추이 분석·저장 범위와 외부 공개/AI 이용을 제한. | 사전 지정 키워드의 **보조 검증**이지 자동 트렌드 발굴 아님. | **내부 판단용만** |
| Google Trends RSS | 기술 PoC는 합성 XML로 존재. | 급상승 검색어 관찰에 적합. 자동 요청/영속 저장/앱 게시 권한 미확정. | **RSS-OPS HOLD** |

**선정 권고(아직 결정 아님):** 소스 하나를 우선 결정하고 (1) API 요청 가능 조건, (2) 필드 보존/표시/파생 허용 범위, (3) 카테고리 적합성, (4) 1~3건의 정합성 및 재현성을 시험한다. YouTube는 영상을 Trend로 가장하지 않는 **동영상 후보 PoC**만 검토한다. 범용 트렌드 탐색의 공급원으로 확정하지 않는다. GDELT는 구 DOC 2.0과 현행 Cloud v2의 사용 가능성·인증·권리 경계를 먼저 분리하여 평가한다.

## 4. 단계적 파이프라인 (신규 API/타입명 확정 아님)

```text
선정된 외부 API (호출 조건·이용권한 별도 확인)
  -> 제한된 읽기 전용 Provider Adapter
  -> 후보 파싱/정규화/형식·URL·중복·기간·분류 검증
  -> 검토 대상 Candidate Preview (게시권한 NONE)
  -> 기존 G0/G4 + A1/4A/4B-1/4B-2 승인·증거 계열과 적법하게 인계
  -> P4 Writer (NOT FROZEN / G5·G6 HOLD)
  -> 승인된 경우에만 MariaDB의 Trend / TrendSource / TrendCategoryMap
  -> 기존 GET /api/trends / personalized -> Expo 앱
```

**책임 분리:** Adapter는 원격 조회와 응답 구조를 책임짐. Candidate Normalizer는 도메인 중립 형식·중복·분류 **후보**만 계산함. Reviewer는 출처 진위·표현·권리·내용·시간·범위를 사람/정책에 따라 판단함. Writer는 이후 별도 보호된 실행 경계에서 실제 승인·철회·배포·트랜잭션을 독립 재검증함. API 읽기 성공/HTTP 200은 승인 근거가 아님.

### 최소 Candidate Preview 정보(설계 후보, 실제 코드/API 계약 아님)

- `provider` 및 provider endpoint/버전·실행 시간(UTC, 타임존 포함)·조회 범위·데이터 취득 방식
- 공급원 항목 식별자, 항목 종류(`video`, `news_article`, `release`, `topic` 등), 원문 URL 및 출처 표시의 실제 허용 상태
- 원문 메타데이터의 제공 가능/제약 여부 (저장 금지라면 원문을 저장하지 않음), 후보 제목/주제 후보, 출처 확인 결과
- **원문 콘텐츠의 발행일**과 **우리 쪽 관측/수신 시각**을 분리; 필요 시 관측 증거로만 인계하고 가짜 `collected_at` 생성 금지
- 활성 Child Category 연결 **후보**(기존 Taxonomy 기반), 불명확하면 보류, 자동 Category 신설 금지
- 후보별 `REVIEW_REQUIRED`/`BLOCKED` 등 *내부 임시 검토 상태*와 사유; 현재 기존 FROZEN의 공개 상태명으로 가장하지 않음
- 비밀키, 세션 쿠키, 유료 보호 본문, 미검증 사진·썸네일, 권리 미검증 원제목 등은 앱 게시값으로 넘기지 않음

## 5. 시연 전 최소 Acceptance (별도 구현 승인 후)

| ID | 증명할 내용 | 기준 |
|---|---|---|
| ING-01 | 공급원 선정 | 공식 Endpoint·인증·요청 제한·권리/보존/표시 범위 문서와 적용 앱 목적 일치, 불명확하면 결정 보류 |
| ING-02 | 읽기 전용 호출 | 사전에 승인된 공급원에서 1~3개 **실제** 후보 구조 검증 (허용된 데이터만 취급) |
| ING-03 | 데이터 정합성 | 부정 URL·필수 필드 누락·중복·시간 역행·미지원 분류 → 검토 보류, 게시 0 |
| ING-04 | 실패 경계 | 401/403/429/5xx·Timeout·응답 변경 → 민감정보 노출/자동 게시/무제한 재시도 없이 종료 또는 보류 |
| ING-05 | 쓰기 0 | 개발/서비스 DB DML 0; Demo Seed·`ACTIVE` 데이터 불변; 새로운 public API 0 |
| ING-06 | 기존 시연 영향 0 | 기존 E2E-00~05 시연 경로·Expo·로그인·관심사·목록 동작 보존 |
| ING-07 | 인계 준비 | G4/A1 검토에 필요한 출처·내용·관측시각·이용 범위·책임 구분 목록 작성, **실승인 증거 미확보는 HOLD** |

## 6. 후속 실제 게시의 중단 Gate

1. **G0:** 공급원의 실제 사용·자동화·DB 보관·앱 표시 범위 승인 문서와 개별 콘텐츠의 권리 확인.
2. **G4:** 개별 후보 사실·원문 링크·자체 작성 제목/요약·위험 분류 검증 및 담당 승인.
3. **4A/4B-2 & A1:** 원본·관측 기록과 승인 스냅샷 바인딩, 보호 검토·철회 상태 및 변경 통제. 중간 검증 PASS를 게시 허가로 해석 금지.
4. **P4 G5:** Writer/Journal/DB 권한·실제 배포·중복·부분 실패·철회 경쟁 제어를 실환경에 맞게 검증. 기존 `ACTIVE` 기본값과 일반 API 계정의 직접 쓰기 우회 위험 해결.
5. **G6:** 실제 운영 프로필의 독립 승인 원본 검증. `g6_status` 문자열/유사 플래그로 대체 금지.

현재 모두 충족되었다고 입증되지 않았으므로 서비스 DB 게시·무인 자동 게시 `HOLD`.

## 7. 11월 12~17일 수행 권고와 구현 승인 경계

- **11/12:** E2E-05 수동 GO 기록 및 본 First Pass 작성. 현재 Docker·DB·Repo 변경 없음.
- **11/13:** 공급원 **하나** 선택 전 검증. 허용된 필드·재사용 조건·API key/Quota·제품 의미/카테고리 적합성 확인. 결과가 불명확하면 ING-01 BLOCK.
- **11/14~15:** 사용자 별도 승인 시 Codex에 ING-01~07 **읽기 전용 Adapter/Preview** 최소 구현·Fixture 테스트 위임. 프로덕션 DB, Expo UI, 공개 API 변경 금지.
- **11/16~17:** 기술 후보 1~3건의 격리 실측 및 발표 시연 안정화. 실제 운영 게시 Gate가 미충족이면 합성 앱 시연 + 실데이터 후보 검증을 **분리하여** 발표.
- **시연 이후:** P4의 독립 Writer/Journal/권한/G5/G6 실증 및 자동 주기 수집·채택 정책. 필요할 때만 C1-B·Helper 변경 재검토.

### 결정 필요 사항

**결정 A(공급원):** YouTube(인기 영상 후보), GDELT(뉴스·스토리 후보), GitHub Releases(IT 릴리스 기술 후보) 가운데 첫 실제 API 대상 하나. 무승인 자동 수집·공개 권한을 미리 추정하지 않는다.

**결정 B(완료 정의):** 11/17 시연 목표를 `합성 앱 시연 + 실데이터 후보 수집 검증`으로 한정할지, `승인된 실제 기사/주제 게시`까지 목표에 유지할지. 후자라면 G0/G4/G5/G6를 모두 충족해야 하며 시한만으로 우회하지 않는다.

## 8. 외부 1차 자료

- YouTube Data API `videos.list`: https://developers.google.com/youtube/data/reference/rest/v3/videos/list
- YouTube API Services Developer Policies: https://developers.google.com/youtube/terms/developer-policies
- GDELT DOC 2.0 소개/기능: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- GDELT Cloud API Documentation Guide (v2 키 인증형과 레거시 v1): https://docs.gdeltcloud.com/API_DOCUMENTATION_GUIDE
- GitHub REST Releases: https://docs.github.com/en/rest/releases/releases

> 본 문서는 **설계 초안**. 기능별 FROZEN 또는 승인된 공급원·운영 규칙에 충돌할 경우 기존 계약 우선. GitHub 원격 반영, Codex 구현 착수, 운영 게시/외부 API 호출 모두 이번 First Pass만으로 승인되지 않음.
