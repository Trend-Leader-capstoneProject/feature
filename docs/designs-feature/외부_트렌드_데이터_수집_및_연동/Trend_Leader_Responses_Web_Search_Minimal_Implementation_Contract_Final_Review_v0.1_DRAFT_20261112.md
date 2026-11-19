# Trend Leader — OpenAI Responses `web_search` 후보 발굴 최소 구현 계약 Final Review v0.1

> **상태:** FINAL REVIEW / **A안(Responses + 독립 원출처 검증) 사용자 방향 선택 반영** / 조건부 수용 / **NOT FROZEN** / 구현 실행·유료 API 호출·외부 게시 승인 아님  
> **기준일:** 2026-11-12 (KST)  
> **기준 저장소:** `Trend-Leader-capstoneProject/feature` / `feat/phase4b2-protected-review-registration` / HEAD `2c2ea11c75c81d80c577a8435153b4352c757083` (검토 시 읽기 전용 확인)  
> **작업 범위:** 실제 웹 검색을 통한 **비게시 후보 1~3건** 발굴 및 원출처 독립 검증 자료 준비  
> **시연 상태:** E2E-00~05 사용자 실기기 검증으로 `[DEMO]` 앱 시연 GO. 실데이터 자동 공급·P4 실제 게시·G5/G6는 **HOLD**.

## 0. 결론 및 승인 경계

1. 사용자가 고른 **A안(OpenAI Responses API `web_search` + 원 출처 독립 검증)**을 첫 공급원 실험 방향으로 채택한다. 검색 결과는 독립적인 급상승 순위/빈도 증거가 아니다.
2. 본 계약의 유일한 새 코드 목표는 **1회성 Backend 내부 CLI/Service 실험 → 후보 검증용 Preview 출력**이다. **DB의 `trends`, `trend_sources`, `trend_category_map`을 포함하여 모든 서비스 DB DML 금지**. 미승인 콘텐츠를 `HIDDEN`으로라도 서비스 DB에 준비 INSERT하지 않는다.
3. **API에서 수집 가능한 발견(discovery) / 원 출처 확인(verification) / G4 사람 승인(review) / P4 게시(write)**는 서로 다른 책임이다. 앞 단계의 성공은 뒤 단계의 PASS를 암시하지 않는다.
4. 단계 A는 Fixture/Mock으로 비용 없이 구현·검증한다. 단계 B **실제 유료 API 요청**은 사용자 별도 실행 승인, 계정 모델 접근, 키·지출 한도 확인 후에만 1회 수행한다. 단계 C는 그 결과의 사람에 의한 원문 검증이다.
5. P0~P3 RSS FROZEN, Phase 4A·4B-1·4B-2 FROZEN, 기존 A1·P4 설계와 운영 Gate v0.3 **전부 유지**. P4 `NOT FROZEN`, G0/G4/G5/G6 운영 실증 `HOLD`; C1-B/Helper 후속 범위를 이 작업에 섞지 않는다.
6. **현재 Final Review 판정: 최소 PoC 설계 조건부 수용.** 비용·모델·보안 설정·기계 판별 기준은 실측 전에 제한값을 확인한다. 이 문서만으로 Codex의 쓰기/커밋/유료 호출을 승인하지 않는다.

## 1. 확정된 사실과 선행 설계의 연결

| 출처 | 확인 사실 / 보존 정책 | 영향 |
|---|---|---|
| `Trend_Leader_Real_Data_Source_Selection_Final_Review_v0.1_DRAFT_20261112.md` | A안 권고, 사용자 후속 발언으로 **A안 선택 확정**; 검색 근거 ≠ 원출처 독립 확인 | 공급원 실험만 확정; 게시 미확정 |
| 실데이터 연결 사전 설계 결정 기록 v0.1 | 최종 목표는 **주기적 무인 후보 발굴·공급**; 초기 인적 검토는 과도기; AI 목록 기본 요약과 상세 분석 분리 | 이번 1회성 실험을 제품의 최종 자동화 구현으로 오인 금지 |
| Google Trends RSS 운영 Gate v0.3 | MVP-A 자체 작성 표시 콘텐츠와 검토된 원문 링크, G4 개별 승인, G6 독립 승인, RSS-OPS HOLD | Google RSS 요청·재배포 불가; Google 무응답은 승인 아님 |
| G5 P1 최소 실행 계약 | G6 HOLD 또는 독립 G6 승인 증거 부재 → DB 접근 이전 차단; 실제 APPLY 미구현 | PoC는 승인 게이트에 닿지 않음 |
| P4 Addendum v0.2 DRAFT | A1 스냅샷 및 `content_ref`, 관측·승인·게시 시각 구분, 독립 Writer | AI 검색 시각을 `collected_at`·`observed_at`으로 날조 금지 |
| 4B-2 FROZEN | Windows 로컬 검토/보호등록/철회에 한정, 실제 게시 인증 아님 | Provider 어댑터가 4B-2를 직접 호출하지 않음 |
| 원격 코드 | `GET /api/trends*`는 `ACTIVE` 조회; `Trend.status`의 ORM·서버 기본값 `ACTIVE` | 기존 API 및 DB Schema 수정 금지, 미승인 INSERT 금지 |
| 원격 `backend/requirements.txt` | `openai` SDK가 의존성 목록에 없음 | 구현 시 SDK 추가 또는 공식 HTTP 사용 여부 먼저 결정, 설치됐다고 가정 금지 |

### 외부 공식 문서의 확인 범위

- [Responses Web search 공식 가이드](https://developers.openai.com/api/docs/guides/tools-web-search): 신규 통합은 `tools=[{"type":"web_search"}]`; 검색 결과에 `web_search_call`과 메시지 내 `url_citation`이 포함될 수 있고, `include=["web_search_call.action.sources"]`로 참조 URL 정보를 요청할 수 있다. `tool_choice="auto"`는 검색 생략이 가능하므로 검색 필수 실험에는 `tool_choice="required"` 사용을 검토한다.
- [Responses Create API](https://developers.openai.com/api/reference/resources/responses/methods/create): `max_tool_calls`는 응답 전체에 허용할 내장 도구 호출의 수를 제한한다. `max_output_tokens`도 별도 제한 가능하다.
- [GPT-5.6 Luna 모델 페이지](https://developers.openai.com/api/docs/models/gpt-5.6-luna): Responses·web search를 지원하는 **저비용 후보 모델**. 실제 사용 가능한 모델인지는 해당 API 프로젝트에서 확인해야 하며, 미지원/미승인 모델을 자동 대체하지 않는다. 성능 적합성은 실측 전 미확정이다.
- [OpenAI API 가격표](https://developers.openai.com/api/docs/pricing): 조회 시점 일반 `web_search` 도구 호출 요금 **$10 / 1,000회** + 검색 컨텍스트/선택 모델 토큰 요금; 실제 한 Response에서 다수 도구 호출 가능성이 있으므로 응답 1회 = 검색 1회라고 가정하지 않는다. 가격·요금제 변경 가능.
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs): JSON Schema 기반 출력 제약은 지원하지만 별도 유효성 검증/거절·미완료 처리는 여전히 필요. `web_search` 결합 및 선정 모델의 실제 동작은 통합 테스트 전 단정하지 않음.
- [OpenAI Services Agreement](https://openai.com/policies/services-agreement/): 외부 웹자료의 재배포 가능 여부는 원출처·권리·서비스 약관을 개별 검토. API 출력 생성과 원문 저작권 허가를 동일시하지 않는다.

## 2. 기능 Goal / Non-goal

**Goal:** IT/디지털 1개 분야를 첫 실험 범위로 삼아 최근 7일(실행 시점·대한민국 현지 날짜 명시) 내 실제 확인 가능한 사건/주제 **최대 1~3건을 후보**로 수집한다. 단일 기사/릴리스 단서가 나와도 모델이 인기·급상승을 보장한다고 표기하지 않는다. 후보의 출처 식별·카테고리 후보·미검증 사유를 사람이 확인할 수 있다.

**Non-goal:** 주기적 스케줄러, 검색량·랭킹 산정, 트렌드 자동 채택, AI 요약 게시, 사용자용 검색 API, 관리자 UI, DB/Redis/새 테이블, Docker·AWS 변경, 신규 P4 Writer/Journal, G5/G6 운영 승인, 외부 페이지 스크래핑 자동화, Google RSS, NAVER 분석값의 AI 전송.

### 명시적 설계 선택 비교

| 구분 | ① 내부 CLI 단일 실행 (**채택 제안**) | ② FastAPI 관리용 API 또는 스케줄러 |
|---|---|---|
| 이점 | 격리·호출 통제·비게시 보장, 개발량 최소 | 운영 자동화에 연결 쉬움 |
| 위험/비용 | 사람의 1회 실행 필요 | 인증·네트워크·타이밍·중복·비용 폭증 위험 |
| MVP | **PoC 완료 판정에 적합** | 이번 범위 제외. 제품 최종 목표에서는 재검토 |

## 3. 신뢰 경계와 계층별 책임

```text
[명시적 관리자 로컬 실행]                  (실데이터 게시 작업 아님)
          ↓
[SearchRunConfig 검증: 한 분야, 기간, 1회, 비용·모델 승인]
          ↓
[OpenAI WebSearch Adapter: Responses 호출 및 원본 메타데이터 읽기]
          ↓
[DiscoveryCandidate Parser: 허용된 필드만 로컬 정규화]
          ↓
[Preview Validator: URL·인용·중복·과장된 인기도 표현 검증]
          ↓
[NOT_FOR_PUBLICATION Preview: 비공개 출력/검토]
          ↓
[별도 사람 확인: 공식 원출처 직접 열람·사실·날짜·권리 검토]
          ↓
[기존 G4 → A1/4A/4B-2 → P4 승인 경계] (이번 구현 범위 아님)
          ↓
[서비스 DB → /api/trends* → Expo]        (이번 구현에서 호출/쓰기 금지)
```

- **Adapter:** 전송·타임아웃·공식 응답 구조 및 tool call 관찰. 검색 결과와 모델 자유서술을 독립적인 사실로 신뢰하지 않는다.
- **Parser/Validator:** 모델 출력이 JSON 형태여도 타입/개수/URL/길이·중복·출처 연결을 로컬 검증. 검색되지 않았으면 `SEARCH_NOT_EXECUTED`로 실패 처리.
- **Review:** 사람의 원출처 확인이 완료되기 전에는 모든 후보를 `REVIEW_REQUIRED`로 유지. 사용자에게 받은 검토 승인도 자동 G4 PASS로 승격하지 않는다.
- **Persistence/DB:** 이번 범위 없음. 비공개 로컬 Preview 텍스트/JSON을 남길 경우 위치·민감값·수명·Git ignore를 사용자와 확인한다. 출력은 등록 원장·A1 승인 스냅샷이 아니다.
- **보안:** OpenAI API 키는 로컬 Backend/CLI의 비공개 환경만 사용. CLI 인자·로그·Traceback·공개 Git/Expo에 포함하지 않는다. 외부 검색 내용은 prompt injection 가능성이 있는 비신뢰 입력. 키·내부 NAVER 지표·개인정보·보호 Evidence를 검색 입력에 넣지 않는다.

## 4. 최소 기능 계약 — Phase S0 / S1 / S2

### S0. Fixture-first (유료 API 호출 없음)

- 한 분야 `IT_DIGITAL`, 최근 7일이라는 검색 의도, 후보 최대 3건, 모델 후보와 호출 제한을 `SearchRunConfig` 수준에서 명시 검증.
- 공식 Responses 응답 형태를 흉내 낸 최소 Fixture로 **도구 호출 존재/부재, 인용 URL 연결, 중복, 빈 후보, 거절, 미완료, 부적절한 링크**를 재현.
- 외부 API URL/응답 계약의 미확인 사항이 나오면 고정 필드/SDK 메서드를 임의 발명하지 않고 공식 문서/버전으로 다시 검증.
- 테스트에서 실제 API 키·외부 요청·DB 세션 생성이 0건인지 확인. 기존 FastAPI 테스트와 import 경계 분리.

### S1. 실제 Responses `web_search` 1회 — **사용자 별도 승인 후에만**

- 1회 CLI 실행 → **최대 1개의 Responses 요청**. 처음에는 `max_tool_calls=1` 제안, `tool_choice="required"`, `include=["web_search_call.action.sources"]`; 검색 결과에 실제 `web_search_call`이 존재하는지 검사. `tool_choice`와 도구 호출 상한은 공급원 실측 시 적용 가능성 재확인.
- 모델 후보는 `gpt-5.6-luna`(문서상 Responses·web search 지원). 계정에서 미지원이면 자동 상위 모델 전환 금지. 성능 부족 여부는 실제 후보 근거를 보고 판단하며 모델 교체는 별도 승인.
- 서버 호출용 API Key·결제/Usage 제한·타임아웃이 준비되지 않으면 `BLOCKED_CONFIG`; 개인 키를 채팅에 제출하도록 요구하지 않음.
- 검색 Prompt는 분야/기간/지역만 전달. 예: `2026-11-06~12 대한민국 IT/디지털에서 공식 원출처로 확인할 수 있는 최근 기술 이벤트 또는 주제 후보를 최대 3개 찾아 URL을 제시. 인기도 수치/랭킹을 만들어내지 말고 불확실성 표현.` 날짜는 실제 실행일 기준 갱신. 약관이 불명확한 원문 본문 전송/재게시 요구 금지.
- 완성 응답/사용량 정보를 확인. 결과가 부족하면 **0건도 유효한 조사 결과**이며 자동 추가 요청하지 않는다.

### S2. 독립 원출처 검증 및 검토용 내보내기

- 최초 범위는 **사용자 수동 원문 열람**. 자동 링크 접속·스크래핑·리다이렉트 추적을 새로운 네트워크 도구로 서둘러 구현하지 않는다.
- 사람이 각 URL에서 **동일 사건/주장, 실제 접근 가능, 원문 날짜·출처, 표시 재사용 권리, 우리 카테고리와의 관련성**을 검토·기록한다. 검색 인용과 원문 일치 여부의 확인 시각을 남기되, 원문 전체 본문·이미지는 복사/저장하지 않는다.
- `source_published_at`은 출처가 보여 준 게시일, `searched_at_utc`는 검색 실행시각, `observed_at`은 별도 4A 계약을 충족하는 관측 증거가 있을 때만 존재한다. 셋은 서로 대체 불가.
- 수동 검증을 통과하더라도 `G4_APPROVED`/`A1_ELIGIBLE`로 자동 승격하지 않는다. G4 카드 작성과 기존 보호 등록은 별도 단계.

## 5. 내부 Preview의 최소 논리 형태(현재는 예시, 공개 API/영속 Schema 아님)

```json
{
  "run_status": "REVIEW_REQUIRED",
  "not_for_publication": true,
  "provider": "OPENAI_RESPONSES_WEB_SEARCH",
  "model": "<사용자 승인 후 확정 모델 식별자>",
  "searched_at_utc": "<실제 실행 시각>",
  "web_search_executed": true,
  "tool_calls_observed": 1,
  "usage": "<검증 가능한 사용량 메타데이터 또는 null>",
  "candidates": [
    {
      "topic_draft": "<자체 작성 검토용 주제 초안>",
      "source_url": "https://example.org/original",
      "source_title_reference": "<검토용 자료; 외부 원제목을 앱에 재사용하지 않음>",
      "source_published_at": null,
      "proposed_category_ref": "IT_DIGITAL / <현재 DB에서 확인할 Child 표시명>",
      "independent_source_verified": false,
      "review_status": "REVIEW_REQUIRED",
      "publish_authorization": "NONE"
    }
  ]
}
```

- URL, 제목, 날짜, 카테고리, 사용량 값은 플레이스홀더다. 이 JSON이 이번 작업에서 실제로 생성되었다는 뜻이 아니다.
- `source_title_reference`는 **검토 전용**이며 현재 앱 `TrendSource.source_title`에 자동 복사하지 않는다. Preview 내 인용 URL·모델 주장 역시 실제 원문을 독립 확인했다는 증거가 아니다.
- JSON 모델 출력은 **불신**하며 로컬 Validator가 검증한 허용 데이터만 다음 단계에 넘긴다. Structured Outputs는 향후 포맷 안정화 옵션이지만 최초 필수 의존으로 강제하지 않는다.
- 내부 정책 상태(`REVIEW_REQUIRED`)와 HTTP/API 실패 코드, 실제 운영 G4/G5/G6 판정은 별도 개념이다.

## 6. 실패·중단 계약

| 조건 | 권고 처리 | 외부 영향 |
|---|---|---|
| API Key/요금/모델 접근 미확인 | `BLOCKED_CONFIG`; 요청 0 | DB/앱 영향 0 |
| `web_search_call` 없음, 검색하지 않은 모델 서술만 존재 | `SEARCH_NOT_EXECUTED` | 승인 후보 0 |
| 401/403/429, API 5xx/timeout, SDK 예외 | `UPSTREAM_ERROR` 종류별 진단; **자동 재호출 없음** | DB 영향 0 |
| 완료 전 중단·refusal·출력 타입 불일치 | `INVALID_OR_INCOMPLETE_RESPONSE` | 검토 후보 0, 민감 원문 로그 금지 |
| 출처/인용 없음, URL 불안전, 중복, 최신성 불명확 | 후보별 `REVIEW_REQUIRED` 또는 제외, **자동 PASS 금지** | DB 영향 0 |
| 과거 자료/단일 기사만 보고 '급상승' 주장 | `TREND_SIGNAL_UNVERIFIED` | 인기/랭킹 표기 금지 |
| 실제 예산 상한/요청 상한 초과 위험 | `BUDGET_BLOCKED` / 사용자 승인 후 재실행 | 추가 요청 금지 |
| 원문 권리 또는 G4 미승인, G6 HOLD | 후보 보존/검토만, **실제 게시 0** | 서비스 DB DML 0 |

과도한 안전 코드 방지: 제어되지 않는 웹 크롤러, 범용 에이전트 오케스트레이터, 새 비밀 관리 서버, 자체 권한 DB, 네트워크 관리자 API는 만들지 않는다. PoC에서는 API 응답의 **URL 문자열 검증만** 수행하고 임의 원문 다운로드 기능을 추가하지 않는다. 나중에 자동 검증용 Fetcher를 만든다면 SSRF/리다이렉트/내부망 접근 차단을 별도 설계한다.

## 7. Acceptance Criteria (계약 IDs: `SRC-A-*`)

| ID | 시험 | PASS 조건 |
|---|---|---|
| SRC-A-01 | 현재 브랜치·FROZEN 정합성 | `GET /api/trends*`, DB Schema, 시연 Seed, G0~G6 정책에 변경 0 |
| SRC-A-02 | 비용 0 Fixture | 실제 OpenAI/웹/DB 호출 0; 정상/비정상 API 형태 검증 |
| SRC-A-03 | 검색 실행 증거 | 실호출 승인 시 `web_search_call` 존재/도구 호출 상한 준수; 단순 생성 텍스트만으로 성공 금지 |
| SRC-A-04 | 후보의 출처 | 각 후보에 검증할 URL과 출처 관계 존재; URL 누락·중복·출처 없는 주장 거부/HOLD |
| SRC-A-05 | 주제와 기존 Taxonomy | IT/디지털 주제 후보, 기존 활성 Child 매핑 **제안만**; DB 매핑 쓰기 없음, 인기도 추정 금지 |
| SRC-A-06 | 시각 정합성 | 검색 시각/발행일/4A 관측 시각을 구분하고 없는 시간 조작 금지 |
| SRC-A-07 | 독립 검증 | 원문 수동 확인 안 됐으면 모든 후보 `REVIEW_REQUIRED`, 승인 상태 `NONE` |
| SRC-A-08 | 오류 처리 | 401/403/429/5xx/timeout/no-search/refusal/empty/invalid → 무한 재시도·승인 없이 안전 종료 |
| SRC-A-09 | 비밀·비게시 | 키·민감 원문·NAVER 수치 외부 노출 0, 모든 DB DML 0, 앱 노출 0 |
| SRC-A-10 | 비용·실측 | 요청·도구 호출·토큰 사용량 분리 기록, 승인한 횟수 이외 자동 추가 호출 0 |
| SRC-A-11 | 모바일 회귀 | 실제 실기기 `[DEMO]` 시연 baseline 유지; 이번 신규 Adapter로 앱 경로 변경하지 않음 |

**증거 기준:** Mock 테스트의 PASS는 S0에 한정. 실제 유료 검색 성공은 S1, 사람이 원출처를 확인한 결과는 S2에 한정. 어떤 단계도 G4/G5/G6 운영 승인 PASS가 아니다.

## 8. 남은 사용자 승인 게이트·권고 다음 순서

| 미확정 사항 | 최소 권고 / 수행 기준 |
|---|---|
| 모델 | `gpt-5.6-luna`를 **저비용 기술 후보**로 검토. 계정 접근 및 품질 실측 후 고정; 임의 fallback 금지 |
| API 비용 | 프로젝트 API 결제/Usage budget 준비 여부 확인. 1 Responses 요청, `max_tool_calls=1`, 실제 요금 사후 확인. 월/일 한도는 사용자 지정 필요 |
| 구체 기간·주제 | **초기 제안:** 대한민국 IT/디지털, 최근 7일, 최대 3건 (다른 분야 추가는 별도 단계) |
| 실행 시점 | S0 Fixture/Mock 구현 승인을 별도로 받고, S1 유료 검색은 따로 승인 |
| 로컬 Preview | 처음에는 민감 내용을 최소화한 표준출력/사용자 검토 자료만. 로컬 영속 JSON 저장 위치·보존 수명은 필요할 때 결정 |
| 실데이터 게시 | S0/S1/S2 성공과 독립. 기존 P4/G5/G6 Gate 통과 전 **항상 HOLD** |

**권고 단계:** 문서 검토/사용자 확정 → Codex S0 Fixture-only 구현(자동 테스트) → 사용자 유료 검색 승인/사용 모델 확인 → S1 1회 실행·비용/출처 확인 → S2 수동 원문 확인 및 G4 자료 준비 → 별도 게시 경계 검토.

**GitHub 안전:** 이번 Final Review는 문서 작성만 수행. 원격 GitHub/Notion/DB·서비스 코드에 쓰지 않는다. 향후 Codex는 작업 시작 전에 HEAD·working tree를 확인하고 사용자의 비관련 변경을 보존하며, 코드 변경·커밋/푸시는 별도 승인에 따른다.
