# Trend Leader — Responses `web_search` S1 Normalizer Acceptance Criteria v0.2.2 (Gate A/B Limited FROZEN)

> **문서 상태:** **v0.2.2 — S1 Gate A/B 합성 계약 한정 FROZEN** (2026-11-12 사용자 명시 승인). **Gate C/D, S1 실응답 호환성·전체 S1 구현은 NOT FROZEN / NOT VERIFIED**. 본 동결은 AC 기대동작의 변경 통제이며 테스트 통과 또는 구현 완료 판정이 아니다.  
> **작성 기준:** 2026-11-12 KST. **확인한 원격 코드:** `Trend-Leader-capstoneProject/feature` / `dev` / HEAD `8a3f7e4418c1d85e4ffa504827440f098328e615`.  
> **범위:** S1 합성 응답 정규화 계약, S0 Parser/Validator 연계, S1 합성 비게시 Preview 및 Mock 실행 경계의 Acceptance Criteria. **Gate A/B만 제한적으로 FROZEN**. Gate C/D의 SDK·모델·실응답·유료 호출 동작은 동결 대상 밖이다.  
> **최종 실응답 호환성:** **미검증**. 특정 모델·SDK 버전·계정으로 실제 Responses 요청을 수행하지 않았다.  
> **후속 작업 브랜치:** `feat/responses-web-search-s1-normalizer` (문서와 후속 구현 동일 브랜치, `dev`에서 분기). **원격 승인 범위는 본 문서 생성·커밋/푸시까지**이며 PR/merge, Red/Green 코드 변경, SDK 설치, 실제 API 호출은 미승인.  
> **최우선 제약:** S0 Fixture-only 기존 계약 및 RSS/Phase 4 FROZEN 유지. G5/G6 **HOLD**, P4 **NOT FROZEN**. 서비스 DB에 미승인 후보를 `HIDDEN`으로도 저장하지 않음.

## 변경 요약 — v0.2 → v0.2.1 (기존 AC 61건 보존)

- **G-01**: Gate A(합성 정규화/S0 통합), B(모의 실행·Preview·회귀), C(선정 SDK 호환·재시도), D(별도 승인된 실제 유료 호출)를 분리한다. 기존 `E-08`은 **Gate C로 이관**하고 합성 Gate A/B PASS의 전제에서 제외한다.
- **G-02**: **Gate A/B용 `S1_SYNTHETIC` Preview 최소 필드/값/UNKNOWN 표현**을 정의한다. 실제 호출용 모드·SDK 진단·비용·시각의 세부값은 Gate C/D 전 별도 확정한다. S0 `FIXTURE_ONLY`를 재사용하지 않는다.
- **G-03**: **합성 프로필 초기 방어 상한** `output` 16항목, `output_text.text` UTF-8 32 KiB, `url_citation`을 포함한 Annotation 배열 32항목을 제안하고, 초과 시 **부분 절단 없이 전체 거부**하는 `L` 그룹 AC를 추가한다. 이 수치는 **OpenAI 공식 상한이 아니며**, Gate A/B용으로만 사용자 승인·동결되었다. Gate C에서 실측 호환성을 별도 검토한다.
- **`P` 그룹 AC**를 신설해 응답 미수신의 `UNKNOWN`과 관찰된 0건을 구분하고, 검색 실행/응답 검증/후보 확보의 분리(S1-D01)를 실제 Preview 출력으로 검증한다.
- v0.2의 `A/B/C/D/E/F/X` **61개 AC ID·기존 기대값은 보존**한다. 인용 offset·복수 메시지·Structured Outputs의 실응답 호환성은 계속 미검증이다.

## 변경 요약 — v0.2.1 → v0.2.2 (제한 동결 승인 반영)

- 사용자 최종 승인: **G-01/G-02/G-03 A안 채택**, 아래 **P-07/P-08 추가**, S0·비게시·미승인·G5/G6 경계 유지. 이에 따라 **Gate A/B의 합성 AC 기대동작만 FROZEN**으로 기록한다.
- 기존 v0.2.1 **73개 AC 전부 보존**, `P-07`, `P-08` 두 건 추가 → 문서상 **75개 AC** (`Gate A/B 74개`, `Gate C 전용 E-08 1개`). AC 수는 pytest 함수 수나 실행·통과 건수가 아니다.
- `P-07`: 검색이 완료되고 Parser가 정상이어도 후보가 모두 탈락한 경우 `NO_VALID_CANDIDATES`, 검색 `CONFIRMED`, 응답 `VALID`, 후보 0건, 개별 issue 보존.
- `P-08`: `response.output` 구조 파손 시 호출 수는 `null`(관찰 불가), 검색 `UNKNOWN`, 응답 `INVALID`, 후보 0건. **0건 관측과 미관찰을 혼동하지 않는다.**
- **동결 제외:** 모델·SDK 선택, 실제 `web_search` 응답/인용 호환성, Structured Outputs 조합, 인용 offset 의미, 실제 Live Preview, 요금·권리·S2 원출처 검증, 게시·운영 승인. Gate C/D에서 증거에 따라 별도 결정한다.
- 이번 원격 반영은 **기능 브랜치의 문서 커밋**으로 한정한다. Codex Red/Green, PR 및 `dev` 병합은 별도 승인이다.

## 0. 목적, 선행 결정, 용어

### 0.1 목적

- 실제 Responses API 출력과 S0의 제한된 합성 응답 계약 사이의 차이를, **검색·인용 증거를 조작하지 않고** 연결할 수 있는지를 합성 데이터로 검증한다.
- **잘못된 통과(False Acceptance)** 방지를 최우선으로 하되, 정상적인 보조 출력(`reasoning` 등)을 무조건 오류 취급하는 **잘못된 거부(False Rejection)**도 검사한다.
- 실제 연동을 가장 중요한 검증 지점인 **Step 5**로 남긴다. 합성 계약 PASS는 실제 OpenAI 응답 호환성 PASS가 아니다.

### 0.2 이 채팅에서 선택한 방향

| 결정 ID | 사용자와 합의한 방향 | 본 명세에서의 적용 |
|---|---|---|
| S1-D01 | 검색 실행 성공과 후보 확보 성공을 분리(B안) | `EMPTY_RESULT`와 `NO_VALID_CANDIDATES`, 응답 실패를 구분 |
| S1-D02 | 엄격한 S0 인용 URL 직접 일치 기준 유지, 실응답 호환성 선검증 | `sources`는 `url_citation`을 대체할 수 없음 |
| S1-D03 (Gate A/B 동결) | 제한된 Normalizer 추가, S0 Parser·Validator 우선 재사용 | 안전한 형식 투영만 수행, S0 `run_preview()`는 실제 실행용으로 재사용하지 않음 |
| S1-D04 (Gate A/B 동결) | 단일 Assistant 후보 메시지·단일 `output_text`만 허용 | 복수 메시지·텍스트 자동 병합 및 마지막 메시지 자동 선택 금지 |
| S1-D05 (사용자 동결 승인) | **A안: 합성 계약에 한정한 동결 범위** | Gate A/B 합성 계약 FROZEN. SDK·실응답 Gate C/D와 운영 승인 불포함 |

`S1-D03`, `S1-D04`, 아래 합성 Preview 최소 필드와 입력 상한은 **Gate A/B의 합성 계약으로 동결**되었다. 이는 실응답 호환성이나 SDK 세부 구현을 동결하지 않으며, 검증 결과에 따른 변경 시 사용자 승인 및 회귀 분석이 필요하다.

### 0.3 용어 및 상태 혼동 방지

- **Normalizer 결과** `NORMALIZED` / `REJECTED`: S1에서 제안하는 **내부 판정**, S0에 존재하는 상태 코드가 아니다.
- **S0 Parser** `status=None`: 파싱 성공. `SEARCH_NOT_EXECUTED`, `INVALID_OR_INCOMPLETE_RESPONSE` 등은 파싱 결과 상태다.
- **S1 Preview** `PREVIEW_READY`, `EMPTY_RESULT`, `NO_VALID_CANDIDATES`, `SEARCH_NOT_EXECUTED`, `INVALID_OR_INCOMPLETE_RESPONSE`, `UPSTREAM_ERROR`: 사용자가 검토하는 **비게시 처리 결과**다.
- **검색 실행 증거**: `response.output` 안에 존재하는 `status=completed`이며 `action.type=search`인 `web_search_call`. 단지 요청에 도구를 설정했다는 사실, `sources`나 모델 본문의 주장만으로 대체하지 않는다.
- **URL 일치**: S0 Validator의 후보 `source_url`과 `url_citation.url`의 **원문 문자열 직접 일치**. 후보의 사실성·원문 최신성·후보별 의미적 지지 관계를 증명하지 않는다.
- **인용 위치**: 원본 `url_citation`의 `start_index`, `end_index`. 문자열 중 어디에 인용이 붙는지에 대한 메타데이터이며, 후보별 의미 연결의 증거로 바로 승격하지 않는다.

## 1. 기준 코드 및 변경 경계

| 기준 파일 | 실제 확인 사항 | S1에서 유지할 계약 |
|---|---|---|
| `backend/app/responses_web_search/types.py` | S0 `SearchRunConfig`는 `IT_DIGITAL`, 7일, 후보 1~3개, 도구 호출 1회, 선택적 UTC Fixture 시각만 허용 | SDK/모델/API Key 설정을 S0 타입에 추가하지 않음 |
| `backend/app/responses_web_search/parser.py` | 합성 dict, 완료된 output, 단일 assistant message·단일 output_text, `url_citation` 배열, 자체 후보 JSON, 호출/후보 상한 | S1은 안전하게 투영한 입력만 전달. JSON 검사 중복 구현 금지 |
| `backend/app/responses_web_search/validator.py` | 필수 3필드→URL→인용 직접 일치→중복. `citation_urls`는 전체 응답 URL 집합 | `sources`로 인용 우회 금지. 원문 사실성 검증했다고 표시 금지 |
| `backend/app/responses_web_search/service.py` | `FIXTURE_ONLY`, `simulated_web_search_executed`, `searched_at_utc=None`, 비게시 Preview 고정 | S1의 실제 검색 메타데이터는 별도 조정 계층에서 구성 |
| `backend/tests/responses_web_search/conftest.py` | SDK/DB import, socket/DNS/파일 쓰기/비밀 설정 접근 차단 | S1 테스트는 별도 경계. S0 test import 시 Live SDK 로딩 금지 |
| S0 Phase2 Green 보고 | **116 passed** 등은 과거 보고서의 수행 결과 | 이번 문서 작성에서 재실행한 결과라고 표현하지 않음 |

**코드상 주의:** S0 Parser의 `searched = action["type"] == "search"`는 반복 대입이지만 현재 S0의 `max_tool_calls=1` 아래에서는 복수 호출을 허용하지 않는다. S1은 **모든 원본 호출을 먼저 집계·검증**해 이 구현 특성에 기대거나 검색 호출을 숨기면 안 된다. 장차 상한을 확대한다면 별도 설계 변경이다.

### 1.1 포함·제외

**포함:** 순수 합성 Fixture, Normalizer의 원본 검증·투영, S0 Parser/Validator 연계 AC, 모의 Adapter 오류·1회 호출·비게시·로그 경계, 합성 Preview 최소 계약과 입력 상한, 실제 연동 호환성 Gate의 정의.

**제외:** OpenAI 실제 호출/요금 지출, SDK 설치·버전 변경, 실제 SDK 객체 직렬화 PASS, 새로운 공개 Router/API, 스케줄러, DB/Redis, 운영 Writer/Journal, G5/G6·G4 자동 승인, 원문 HTTP 접근·독립 사실 확인, 소스 콘텐츠 재배포, RSS/NAVER 수집 변경, 앱 시연 데이터 변경.

## 2. 책임·데이터 흐름 및 최소 논리 계약

```text
[수동 1회 실행 승인 / 명시된 테스트 설정]
    └─ [S1 Live Adapter (합성 단계에서는 Mock)]
         ├─ 호출 실패 → S1 조정 계층: UPSTREAM_ERROR
         └─ 원본 Responses 응답
               ↓
         [S1 Response Normalizer]
         ① 전체 output의 검색 호출 수/상태 및 위험 항목 확인
         ② 허용된 보조 항목과 단일 최종 후보 메시지 식별
         ③ 원본 정보 훼손 없이 S0 호환 입력으로 투영
               ├─ REJECTED → S0 미호출 / 후보 0건
               └─ NORMALIZED
                      ↓
              [S0 parse_response()]
                      ├─ 오류 → Validator 미호출 / 후보 0건
                      └─ 파싱 성공
                            ↓
              [S0 validate_candidates()]
                            ↓
              [S1 Preview 조정 계층: 비게시·미승인·진단]
                            ╳ DB / Redis / G5 / G6 / P4 Writer / 앱 공개 게시
```

### 2.1 Normalizer 입력

- **논리 입력:** Live Adapter가 전달한 **응답 전체**. API Key, 인증 헤더, SDK 클라이언트, 검색 프롬프트, 현재시각은 Normalizer 입력 계약에 포함하지 않는다.
- 합성 테스트에서는 Python `dict`로 공식 Responses의 관찰 가능한 출력 모양을 표현한다. 실제 SDK Pydantic 객체를 어떻게 직렬화할지는 Step 5 전에 **선택한 SDK 버전**을 기준으로 검증한다.
- 전체 응답과 모든 `output` 항목을 조사하기 **전에 일부 메시지·검색 호출을 필터링하지 않는다**.

### 2.2 Normalizer 출력 (타입·필드명은 구현 전 제안)

```text
NormalizationResult
  outcome: NORMALIZED | REJECTED
  execution_evidence:
    response_status: 원본 상태 또는 UNKNOWN
    web_search_calls_observed: 원본에서 관찰된 호출 수 또는 UNKNOWN
    completed_search_actions: 확인된 완료 search 수 또는 UNKNOWN
    assistant_messages_observed: 확인된 수 또는 UNKNOWN
  parser_input: S0 호환 dict | None      # NORMALIZED일 때만 존재
  citation_trace: 인용 URL·원본 message/content/annotation 위치의 비영속 진단
  reason_codes: 원문 텍스트와 비밀을 제외한 제한된 식별자
```

**강제조건**

1. `REJECTED`라면 `parser_input=None`, S0 Parser/Validator **미호출**, 후보 0건.
2. `NORMALIZED`는 **정규화만 성공**했다는 뜻이다. S0 Parser가 JSON·인용 문제로 실패할 수 있다.
3. 원본에 없는 `web_search_call`, `status=completed`, `url_citation`, 후보 텍스트를 만들지 않는다.
4. 원본 도구 호출 수가 상한을 초과하면 **어떤 투영도 성공으로 반환하지 않는다**.
5. 인용 URL과 후보 텍스트를 정합성 확보 목적으로 수정·정규화·잘라내지 않는다.
6. 정상 `reasoning`은 유형별 검사 후 S0 Parser가 이해하지 못하는 보조 항목으로 **투영에서 제외 가능**하다. 다만 이를 모든 미지원 항목에 적용하는 범용 삭제 규칙은 금지한다.
7. `action.sources`를 `url_citation`으로 변환하지 않는다. 출처 목록은 후보별 인용을 대체하지 못한다.
8. 인용 위치·URL의 출처 추적 정보를 보존하더라도 **독립 사실 검증 완료**나 **후보별 의미 연결 완료**라고 표시하지 않는다.
9. UNKNOWN과 0건은 다르다. API 예외로 응답을 받지 못한 경우 관찰하지 못한 도구 호출 수를 사실처럼 `0`으로 기록하지 않는다.

### 2.3 S1 Preview 최소 출력 계약 — Gate A/B 전용 (G-02)

**범위:** Mock Adapter 및 합성 Response에서 생성하는 **내부 검토용** JSON 호환 Preview다. 아래 필드명과 값은 사용자 승인된 **Gate A/B의 합성 Red Phase 계약(FROZEN)**이다. 실제 유료 호출의 `mode`, 사용량, SDK/모델, 청구·시각 메타데이터는 Gate C/D에서 별도 결정한다.

| 필드 | 합성 Preview 타입·값 | 근거·불변조건 |
|---|---|---|
| `mode` | 문자열 `S1_SYNTHETIC` | 실제 API 요청이 없었음을 표시. `FIXTURE_ONLY`와 다른 S1 모드 |
| `status` | 기존 S0와 같은 대표 처리 상태 문자열 | `PREVIEW_READY`, `EMPTY_RESULT`, `NO_VALID_CANDIDATES`, `SEARCH_NOT_EXECUTED`, `INVALID_OR_INCOMPLETE_RESPONSE`, `UPSTREAM_ERROR` |
| `search_execution` | `CONFIRMED` / `NOT_CONFIRMED` / `UNKNOWN` | 완료 `search`의 **관찰** 여부. 응답 자체가 미수신이면 `UNKNOWN`; 호출 초과라도 관찰된 완료 search를 숨기지 않음 |
| `response_validation` | `VALID` / `INVALID` / `NOT_EVALUATED` | `VALID`: Normalizer·S0 Parser가 구조/JSON 파싱까지 통과. `INVALID`: 둘 중 하나가 실패. Adapter 오류 및 검색 미실행 단락은 `NOT_EVALUATED` |
| `tool_calls_observed` | `int ≥ 0` 또는 `null` | 원본 `output`을 신뢰 가능한 list로 확인해 집계한 수; 응답 미수신/출력 목록 파손은 `null`이지 0 아님 |
| `reason_codes` | 안전한 짧은 문자열의 `list` | 기존 S0 이유 보존. 신규 상한 위반 코드 §5.L 참조. 예외 원문·응답 텍스트 금지 |
| `issues` | `{candidate_index: int, code: str}` 리스트 | 후보별 오류. Normalizer 거부/Parser 전체 실패 시 `[]` |
| `candidates` | 검토용 후보 리스트, 최대 3건 | 정상 유지 후보만; 실패 시 `[]`. 후보별 비게시 안전값 유지 |
| `review_status` | `REVIEW_REQUIRED` | 고정 |
| `publication_status` | `NOT_FOR_PUBLICATION` | 고정 |
| `publish_authorization` | `NONE` | 고정 |
| `independent_source_verified` | `false` | 고정 |
| `request_started_at_utc`, `response_received_at_utc` | 합성 모드에서는 `null` | 실제 관측 시각을 가짜 생성하지 않음. 실연동 시각 채움 정책은 Gate C/D에서 결정 |

**`search_execution` 규칙:** `CONFIRMED`는 구조적으로 관찰된 완료 search가 1건 이상일 때만 사용한다. 실행이 없거나 실패했다는 정보가 **정상 output에서 확인**되면 `NOT_CONFIRMED`; 응답이 없거나 신뢰성 있게 판단할 수 없다면 `UNKNOWN`. `CONFIRMED`라도 도구 호출 초과·Refusal·JSON 실패로 `status`가 실패할 수 있다. 즉 **검색 증거 ≠ 응답 유효성 ≠ 후보 확보**다.

**`response_validation` 규칙:** `NORMALIZED` 자체는 `VALID`의 근거가 아니다. S0 Parser가 `status=None`이어야 `VALID`다. `SEARCH_NOT_EXECUTED`의 경우 S0 Parser가 후보 JSON 검증 전에 단락되므로 `NOT_EVALUATED`로 둔다. Adapter 오류도 `NOT_EVALUATED`. `REJECTED` 또는 Parser의 구조·JSON 오류는 `INVALID`다.

**검토 후보 필드:** `topic_draft`, `source_url`, `source_title_reference`, `source_published_at=null`, `proposed_category_ref=IT_DIGITAL`과 후보별 공통 안전값을 포함한다. 모델의 임의 추가 필드를 복사하지 않는다. `candidate_count` 등 중복 저장 필드는 이 최소 계약에 추가하지 않고 `len(candidates)`로 판단한다.

**진단:** `citation_trace`는 Normalizer의 **내부 비영속 진단**일 뿐 이 Preview의 필수 필드가 아니다. 원본 URL에 인증 파라미터 등이 있을 수 있으므로 로그/CLI 진단에 전체 URL을 무차별 출력하지 않는다. SDK/HTTP 예외의 텍스트도 reason_codes로 복사하지 않는다.

### 2.4 S1 Preview 공통 불변조건

- `review_status=REVIEW_REQUIRED`
- `publication_status=NOT_FOR_PUBLICATION`
- `publish_authorization=NONE`
- `independent_source_verified=false`
- `source_published_at`은 독립 확인 전 `null` (모델 생성 값으로 채우지 않음)
- 모델의 `rank`, `popularity_score`, `observed_at`, `collected_at` 등은 권한·사실로 승격하지 않음
- **S0 전용** `mode=FIXTURE_ONLY`, `simulated_web_search_executed`를 S1의 실검색 결과 표기로 재사용하지 않음
- 요청 시작·응답 수신 시각이 필요하면 S1 실행 계층이 실제로 관찰한 시각으로 기록. 웹 원문 게시 시각·A1 관측 시각과 혼동 금지
- **합성 Preview의 최소 필드·상수는 §2.3에서 Gate A/B 계약으로 동결**했다. **실제 Live Preview의 모드/SDK 진단·과금·시각 계약은 여전히 Gate C/D 미결정**이다.

### 2.5 합성 입력 상한 및 초과 처리 — Gate A/B 전용 (G-03)

| 검사 대상 | Gate A/B 동결 상한 | 측정 방법 | 초과 시 대표 `reason_codes` |
|---|---:|---|---|
| 원본 `response.output` 항목 수 | **16개** | 알려진/미지원 모든 output 항목 수를 **필터링 전** 셈 | `S1_OUTPUT_ITEMS_LIMIT_EXCEEDED` |
| 단일 후보 메시지의 `output_text.text` | **32 KiB = 32,768 bytes** | 원문 텍스트의 **UTF-8 인코딩 byte 길이** (Python 문자 수가 아님) | `S1_TEXT_BYTES_LIMIT_EXCEEDED` |
| 후보 메시지의 `output_text.annotations` 항목 수 | **32개** | 유효/무효 Annotation을 포함한 원본 list 길이 | `S1_ANNOTATIONS_LIMIT_EXCEEDED` |

- **경계값은 허용(≤), 초과값은 거부(>)**한다. 제한 초과 시 Normalizer는 `REJECTED`, `parser_input=None`, Preview `status=INVALID_OR_INCOMPLETE_RESPONSE`, `candidates=[]`로 끝낸다. S0 Parser/Validator를 호출하거나 일부 항목을 절단해서 재시도하지 않는다.
- 이 한도는 사용자 승인으로 **Gate A/B 합성 PoC에 동결된 초기 방어값**이며 OpenAI SDK/Responses의 공식 제한이 아니다. 실제 정상 응답의 구조/크기를 관찰한 Gate C 결과가 이 값과 충돌하면 변경 사유·False Rejection 영향·회귀 테스트를 보고하고 **별도 승인 후** 조정한다.
- 잘못된 `output` 타입, 텍스트 타입, Annotation 타입은 기존 구조 오류 계약에 따른다. **구조를 신뢰할 수 없어 개수를 셀 수 없다면 임의로 0으로 기록하지 않는다**.
- `output` 항목 수에는 `reasoning`도 포함한다. Annotation 수에는 중복 URL 인용도 모두 포함하며 중복 제거 후 개수를 세지 않는다. 텍스트 길이를 맞추려고 JSON을 재직렬화하거나 자르지 않는다.
- 이 방어는 **이미 메모리에 들어온 응답의 부분 구조에 대한 상한**이다. SDK 수신 이전의 HTTP body 크기·메모리 상한을 증명하지 않는다. 그 부분은 Gate C에서 별도 검토한다.
- 확인 가능한 복수 위반의 대표 사유는 `OUTPUT_ITEMS` → `TEXT_BYTES` → `ANNOTATIONS` 순서로 결정하고, 원문·민감정보는 출력하지 않는다. **상위 응답 미완료·도구 호출 초과·명시적 실패는 §3.1의 안전 우선순위**가 적용된다.

## 3. 정규화 판정 규칙 및 실패 우선순위

### 3.1 계층별 실패 처리

| 계층 | 조건 | 최종 처리 상태 | 다음 계층 호출 |
|---|---|---|---|
| Adapter | API 오류/timeout | `UPSTREAM_ERROR` | Normalizer 미호출 |
| Normalizer | 응답 미완료·출력 안전 위반·메시지 모호성·거절 | `INVALID_OR_INCOMPLETE_RESPONSE` | S0 미호출 |
| Normalizer → S0 Parser | 완료 search 증거 없음, 나머지 구조 해석 가능 | `SEARCH_NOT_EXECUTED` | Validator 미호출 |
| S0 Parser | 후보 JSON 형식/상한/Annotation 구조 오류 | `INVALID_OR_INCOMPLETE_RESPONSE` | Validator 미호출 |
| S0 Validator | 구조 정상, 후보 모두 제외 | `NO_VALID_CANDIDATES` | 후보 0건 / issues 유지 |
| S0 Parser + Validator | 구조 정상, 빈 후보 배열 | `EMPTY_RESULT` | 후보 0건 / issues 0건 |
| S0 Parser + Validator | 검증 통과 후보 1~3건 | `PREVIEW_READY` | 검토용 후보만 반환 |

**우선순위 제안:** Adapter 실패 → 응답 최상위 완료 여부 → 원본 전체의 도구 호출 상한·명시 실패/미완료 → **§2.5 입력 상한 위반** → 거절·미지원 항목·메시지 모호성 → 검색 실행 증거 → 후보 JSON/인용 구조 → 개별 후보 유효성. 단 상한 검사만을 위해 미지원/미완료 내용을 정상으로 취급하지 않는다.

이 순서는 **S1 조정 계층의 대표 사유 선택 원칙**이다. S0 Parser의 내부 검증 순서를 임의로 재작성하지 않는다. 둘 이상 동시에 잘못된 복합 오류 테스트는 대표 사유를 해당 상위 실패로 판정하고, 안전한 진단 정보만 추가한다.

### 3.2 정상으로 취급하지 말아야 할 경우

- `response.status != completed` / 명시적 tool failed / 명시적 reasoning incomplete
- response 구조·출력 타입이 해석 불가능한 경우
- 둘 이상의 Assistant 후보 메시지 또는 `output_text`가 존재하는 경우
- Refusal이 어떤 content에든 존재하는 경우
- 후보 텍스트가 JSON 문법 오류인 경우 (후보 0건 정상 결과가 **아님**)
- 정상 `web_search_call`이 없어 모델 본문에만 “검색 완료”라고 쓰인 경우
- 인용 URL을 `sources`에서만 발견한 경우

### 3.3 실제 응답 수용 정책의 제한

- S1 초기 프로필: Assistant 후보 메시지 **정확히 1개**, `output_text` **정확히 1개**. `phase`가 존재하더라도 복수 메시지를 자동 선택하지 않는다.
- `reasoning`은 공식 SDK 정의의 `status`가 **선택적**이므로 누락 자체만으로 실패시키지 않는다. 명시적 `incomplete`/`in_progress`는 초기 계약에서 거부한다.
- `web_search_call`의 `action.type`: `search`, `open_page`, `find_in_page`를 구분한다. 이 S1 실험에서는 `completed search`만 검색 실행 증거다.
- `url_citation` 외의 annotation 타입은 현재 S0와 호환되지 않는다. 새 유형이 나타나면 **무음 삭제/변환 금지**, 실패 및 호환성 재검토 대상으로 남긴다.
- `start_index`/`end_index`가 후보의 원문 주장이나 source URL 문자열을 가리킨다고 가정하지 않는다. **위치 검증 범위는 별도 Gate**를 둔다(§7).

## 4. 합성 Fixture 제작 규칙

### 4.1 F-BASE (기준 정상 Fixture)

```json
{
  "id": "resp_synthetic_s1",
  "status": "completed",
  "output": [
    {
      "id": "ws_synthetic_s1",
      "type": "web_search_call",
      "status": "completed",
      "action": {"type": "search", "query": "합성 IT 최근 7일"}
    },
    {
      "id": "msg_synthetic_s1",
      "type": "message",
      "status": "completed",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "{\"candidates\":[{\"topic_draft\":\"가상 기기 출시\",\"source_url\":\"https://vendor.example.test/releases/1\",\"source_title_reference\":\"가상 공식 발표\"}]}",
          "annotations": [
            {
              "type": "url_citation",
              "url": "https://vendor.example.test/releases/1",
              "title": "합성 인용",
              "start_index": 55,
              "end_index": 93
            }
          ]
        }
      ]
    }
  ]
}
```

위 F-BASE의 `start_index=55`, `end_index=93`은 표시된 합성 JSON 문자열의 URL 시작·끝 위치에 맞춘 값이다(문자열 인덱스 계산으로 재확인). 다만 **이것은 합성 Fixture에서 인용을 URL 위치에 의도적으로 붙인 것일 뿐**, 실제 Responses 모델이 자체 후보 JSON에도 같은 형태로 인용한다는 증거는 아니다. 위치 검증 테스트는 이 값을 재사용하지 않고 원본 Fixture별 독립 기대값으로 판정한다.

### 4.2 Fixture 설계 원칙

1. 기준 F-BASE를 깊은 복사해 **하나의 조건만** 바꾸되 복합 오류는 X 그룹으로 구분한다.
2. 후보 필드/JSON을 바꾼다고 인용을 자동 재생성하지 않는다. **단일 결함의 기대 상태가 다른 결함 때문에 가려지지 않게** 한다. 예: 후보 URL 공백 테스트 시 기존 유효 Annotation은 그대로 유지한다.
3. 실제 API 응답을 기록한 자료라고 표기하지 않는다. 토큰·키·원문·개인정보 미포함.
4. 테스트 기대값은 **원본 Fixture**를 기준으로 독립 작성한다. Normalizer 출력과 Normalizer가 만든 S0 입력을 서로 비교하는 자기확인 테스트만으로 합격 처리하지 않는다.
5. 정상 Fixture를 일부러 다양한 공식 지원 형태(허용 `reasoning` 유무, `phase` 유무, `sources` 유무)로 만든다. 단, **선택한 SDK 버전과 실제 호환은 별도 검증**이다.

## 5. Acceptance Criteria — 단위·통합·실행 경계

아래 표의 `N`은 Normalizer 결과, `S0`는 Parser·Validator 통합 결과, `Preview`는 S1 최종 비게시 처리 상태를 뜻한다. `S0 미호출`은 mock/spy로 **실제로 호출되지 않았음**을 검사한다.

### 5.A — 검색 실행과 호출 상한

| ID | 입력 변형(F-BASE 대비) | N 기대 | S0·Preview 기대 | 실패 시 금지 행동 |
|---|---|---|---|---|
| A-01 | 원형 유지 | NORMALIZED, 원본 호출=1 | S0 정상·`PREVIEW_READY` 1건 | 증거 임의 변경 |
| A-02 | `web_search_call` 없음 | NORMALIZED, 호출=0 | `SEARCH_NOT_EXECUTED`, 0건 | 가짜 search 생성 |
| A-03 | `action.type=open_page` | NORMALIZED, 호출=1, 완료 search=0 | `SEARCH_NOT_EXECUTED`, 0건 | open_page를 search로 간주 |
| A-04 | 검색 호출을 하나 추가, 총 2건 | REJECTED, 관찰=2 | S0 미호출·`INVALID_OR_INCOMPLETE_RESPONSE`, `TOOL_CALL_LIMIT_EXCEEDED` | 하나를 숨기거나 잘라내기 |
| A-05 | 도구 `status=failed` | REJECTED | S0 미호출·`INVALID_OR_INCOMPLETE_RESPONSE` | failed → completed 변조 |
| A-06 | 전체 `response.status=incomplete` | REJECTED | S0 미호출·`INVALID_OR_INCOMPLETE_RESPONSE` | `EMPTY_RESULT`로 치환 |
| A-07 | 도구 action.type 누락 | REJECTED | S0 미호출·구조 오류 | `search` 추정 |
| A-08 | 미지원 output 타입 추가 | REJECTED | S0 미호출·구조 오류 | 알 수 없는 항목 무음 삭제 |
| A-09 | `find_in_page`만 있고 search 없음 | NORMALIZED, 완료 search=0 | `SEARCH_NOT_EXECUTED` | 페이지 내 탐색을 검색 실행 증거로 간주 |

**AC-A 공통:** 도구 호출 수는 **원본 전체**에서 집계한다. 호출 상한은 S0와 일치하게 1이며, 도구 실행이 없거나 실패한 결과를 성공한 search처럼 투영하지 않는다.

### 5.B — 메시지 선택·보조 출력·Refusal

| ID | 입력 변형 | N 기대 | S0·Preview 기대 | 실패 시 금지 행동 |
|---|---|---|---|---|
| B-01 | 정상 `reasoning(status=completed)` 추가 | NORMALIZED | S0 정상·`PREVIEW_READY` | 지원된 보조 항목을 무조건 오류로 취급 |
| B-02 | `reasoning.status`만 생략 | NORMALIZED | `PREVIEW_READY` | 없는 상태 필드를 원본에 생성 |
| B-03 | `reasoning.status=incomplete` | REJECTED | S0 미호출·구조/미완료 오류 | 명시적 미완료 무시 |
| B-04 | Assistant 메시지 2개 | REJECTED | S0 미호출·메시지 모호성 | 마지막 메시지 임의 선택 |
| B-05 | 한 메시지에 `output_text` 2개 | REJECTED | S0 미호출·content 모호성 | 텍스트/Annotation 임의 병합 |
| B-06 | `refusal`을 content에 추가 | REJECTED | S0 미호출·전체 실패 | 유효 후보 부분 반환, 거절 원문 로그 |
| B-07 | Assistant 메시지 없음 | REJECTED | S0 미호출·구조 오류 | 정상 빈 후보로 치환 |
| B-08 | 알 수 없는 content 타입 | REJECTED | S0 미호출·구조 오류 | unknown content 무음 삭제 |
| B-09 | 단일 정상 메시지에 `phase=final_answer` 추가 또는 phase 생략 | NORMALIZED | `PREVIEW_READY` | phase 생략을 실패 또는 임의 완료의 근거로 삼기 |

`B-01/B-02`에서 추가하는 합성 `reasoning`은 공식 SDK 타입의 기본 필수 필드(`type=reasoning`, `id`, `summary=[]`)를 갖도록 구성하며, **`status`만 변화시키는 대조 테스트**로 만든다. `reasoning` 본문·암호화 콘텐츠를 로그에 전재하지 않는다.

**AC-B 공통:** 알려진 보조 출력은 **검사 후 제거 가능한 구조**다. 알려지지 않은 출력은 **제거 가능한 노이즈가 아니다**. 복수 메시지 처리는 실응답 증거 전까지 별도 정책으로 확대하지 않는다.

### 5.C — 인용·출처·추적 관계

| ID | 입력 변형 | N 기대 | S0·Preview 기대 | 실패 시 금지 행동 |
|---|---|---|---|---|
| C-01 | 후보 URL = `url_citation.url` | NORMALIZED | `PREVIEW_READY` | 인용을 새로 만들기 |
| C-02 | `url_citation.url`을 다른 유효 URL로 변경 | NORMALIZED | `NO_VALID_CANDIDATES`, `CITATION_URL_MISMATCH` | 후보 URL 자동 맞춤 |
| C-03 | Annotation 빈 배열 + 동일 URL의 `action.sources` | NORMALIZED | `NO_VALID_CANDIDATES`, `CITATION_URL_MISMATCH` | `sources`→`url_citation` 승격 |
| C-04 | 스킴/host 문자 대소문자 또는 fragment 차이만 있는 다른 URL 인용 | NORMALIZED | 원문 문자열 불일치면 `CITATION_URL_MISMATCH` | URL 정규화 후 인용 통과 |
| C-05a | `url_citation.url` 누락 또는 문자열이 아님, Annotation 배열 자체는 유지 | **원칙상 NORMALIZED** | S0 Parser `INVALID_OR_INCOMPLETE_RESPONSE` (`ANNOTATION_STRUCTURE_INVALID`) | 구조 오류 인용 삭제 후 성공 처리 |
| C-05b | `annotations` 필드 누락 또는 리스트 아님 | **원칙상 NORMALIZED** | S0 Parser `INVALID_OR_INCOMPLETE_RESPONSE` | 누락 필드에 `[]` 생성 |
| C-05c | `start_index`/`end_index`가 후보 URL 위치와 불일치하지만 형식상 정상 | NORMALIZED | URL 일치 시 `PREVIEW_READY` 가능, **후보별 위치 검증은 미완료** | URL 일치를 후보별 의미 연결 검증으로 주장 |
| C-06 | 후보 2건, 한 건만 인용 URL 일치 | NORMALIZED | `PREVIEW_READY`, 1건 유지·1건 `CITATION_URL_MISMATCH` | 실패 후보/issue 은폐 |
| C-07 | URL은 일치하지만 후보의 주장을 인용이 지지하지 않음 | NORMALIZED | S0 통과 가능, `REVIEW_REQUIRED`/`independent_source_verified=false` | 원문 사실/권리 검증 완료 표시 |
| C-08 | Annotation에 유효 `url_citation`과 미지원 다른 타입 혼재 | REJECTED (S1 지원 프로필 밖) | S0 미호출·구조 오류 | 다른 타입을 조용히 버리기 |

**C-05a/b 경계:** 실제 SDK가 이 데이터의 역직렬화 자체를 막는다면 Adapter/SDK 입력 검증 오류로 종료한다. **dict 기반 Normalizer 테스트**에서는 S0가 담당하는 기존 인용 URL 구조 검증을 중복 구현하지 않는 방향을 시험한다. `C-08`은 S1에서 미지원 Annotation을 무음 제거하지 않는 **호환성 경계 검사**이므로 C-05와 구분한다.

**인용 offset 미확정:** 음수·역순·범위 밖·non-int 등 명백한 위치 데이터 이상을 **S1에서 실패로 강제할지, 별도 진단만 남길지**는 SDK/실응답 인덱스 의미를 확인한 뒤 최종 결정한다. 첫 합성 계약은 offset을 **후보별 의미 검증 증거로 인정하지 않는 것**까지를 불변조건으로 둔다.

### 5.D — JSON·후보·상태 분리

| ID | 입력 변형 | N 기대 | S0·Preview 기대 | 실패 시 금지 행동 |
|---|---|---|---|---|
| D-01 | `text`의 `candidates=[]` | NORMALIZED | `EMPTY_RESULT`, issues 0건 | 검색 실패로 기록 |
| D-02 | 후보 URL만 `file:///private`로 변경, 유효한 기존 인용 유지 | NORMALIZED | `NO_VALID_CANDIDATES`, `SOURCE_URL_INVALID` | 파일 URL 사용 |
| D-03 | 검증 통과 1건 + 필드 오류 후보 1건 | NORMALIZED | `PREVIEW_READY` 1건 + 탈락 issue | 부분 실패 사실 누락 |
| D-04 | 후보 4건 | NORMALIZED | S0 Parser `INVALID_OR_INCOMPLETE_RESPONSE`, `CANDIDATE_LIMIT_EXCEEDED` | 상위 3건으로 절단 |
| D-05 | 후보 JSON 문법 오류 | NORMALIZED | S0 Parser `INVALID_OR_INCOMPLETE_RESPONSE` | `EMPTY_RESULT`나 후보 부분 반환 |
| D-06 | 후보에 `publish_authorization=APPROVED`, 날짜·순위 추가 | NORMALIZED | S0 유효 후보는 남되 모든 권한·날짜 검증 승격 금지 | 모델 메타데이터 신뢰 |
| D-07 | URL/정규화 주제 중복 후보 2건 | NORMALIZED | `PREVIEW_READY` 최초 유효 1건, `DUPLICATE_CANDIDATE` | 중복 이중 계수 |
| D-08 | `candidates`가 객체 또는 `null` | NORMALIZED | S0 Parser `INVALID_OR_INCOMPLETE_RESPONSE` | 임의 리스트화 |
| D-09 | 후보 개수 0이지만 응답 구조/인용 리스트 누락 | NORMALIZED 가능 | S0 Parser 구조 오류 (**`EMPTY_RESULT` 아님**) | 후보 0건이라는 이유로 선검증 생략 |

**AC-D 공통:** Normalizer는 모델 생성 후보 JSON을 보정·파싱해 `candidates`를 재구성하지 않는다. S0 Parser가 기존 책임을 수행하도록 원형 그대로 전달한다.

### 5.E — Adapter·비게시·보안·회귀

| ID | 입력/조건 | N 기대 | 통합 기대 | 실패 시 금지 행동 |
|---|---|---|---|---|
| E-01 | Mock Adapter timeout | 미호출 | `UPSTREAM_ERROR`, 후보 0, 응용 재시도 0 | 자동 재호출 |
| E-02 | Mock Adapter 401/403/429/5xx | 미호출 | `UPSTREAM_ERROR`, 후보 0 | 오류를 정상 검색으로 전환 |
| E-03 | 원본 dict의 실행 전후 깊은 복사 비교 | 정상 케이스 처리 | 원본 변경 0건 | 원본 inplace 수정 |
| E-04a | 비밀 API 키·Authorization 헤더를 모의 환경에 주입 | Normalizer 입력 대상 아님 | Preview/로그/진단에 비밀 없음 | 인증 정보 출력 |
| E-04b | Refusal·실패한 JSON 원문에 비밀 마커 포함 | 상황별 실패 | `reason_codes`·진단·오류 로그에 원문 마커 없음 | 원본 오류 텍스트 복사 |
| E-04c | 검토 후보 제목/URL에 비신뢰 텍스트 존재 | 정상 URL 등 통과 가능 | **내부 Preview에는 후보 원문이 포함될 수 있음**, 공개 앱 전달 0건 | '모든 후보 텍스트 자동 비밀 제거'라고 과장 |
| E-05 | 기존 S0 격리 테스트 별도 실행 | S1 미개입 | 기존 S0 공개 API/Fixture-only 동작 유지 | S0 import 때 SDK·네트워크 접근 |
| E-06 | 모의 실행에 DB/Redis/Writer spy 설치 | 정상 처리 | DB DML/Redis/게시 호출 0 | `HIDDEN` 포함 사전 INSERT |
| E-07 | S1 Preview 구성 | 정상 처리 | S0 `FIXTURE_ONLY`·`simulated_web_search_executed` 의미 재사용 금지 | 합성 증거를 실검색으로 표시 |
| E-08 **[Gate C]** | SDK 재시도 설정 검사 (선정 버전 기준) | 해당 없음 | SDK 내부 자동 재시도 비활성화·예외시 재호출 없음 | 429/timeout 자동 반복 |
| E-09 | 모델이 인기/최근성/원문 시각을 주장 | NORMALIZED 가능 | 독립 확인 없는 랭크·최신성·게시일 승격 0건 | `rank`, `source_published_at`, A1 관측 시각 날조 |
| E-10 | 웹 출처의 제어문자·터미널 제어 시퀀스가 후보 텍스트에 포함 | 후보 검증은 기존 범위 | CLI 출력·로그에서 제어 시퀀스 **원형 실행/해석 금지**(안전한 JSON 이스케이프 등) | 비신뢰 텍스트를 터미널 제어로 실행 |

**E-08 주의:** **Gate C 전용**이다. 모의 Adapter 호출 1회와 SDK 내부 네트워크 재시도 0회는 서로 다른 테스트다. 합성 Gate A/B 통과 여부에 E-08의 실행 여부를 섞지 않는다. SDK 버전 확정 전에는 **테스트 항목**만 정의하고 실제 통과를 주장하지 않는다.

**E-04 책임:** S0 후보 문자열은 내부 검토를 위해 유지된다. 로그와 Preview의 보안 경계는 구분하고, 출력 대상/권한/보존 정책은 실사용 전에 확인한다.

### 5.F — 실제 응답 가정을 깨는 반례 (합성만으로 호환성 완료 주장 금지)

| ID | 원본 합성 사례 | N/S0 기대 | 특별히 검증하는 위험 |
|---|---|---|---|
| F-01 | JSON 유효·인용 URL 일치 | 정상 처리 | 지나치게 이상적인 기본 Fixture 편향 |
| F-02 | JSON 유효·Annotation 빈 배열 | 후보 탈락 | 검색 실행 ≠ 후보 증거 |
| F-03 | JSON 유효·Annotation 필드 누락 | Parser 구조 실패 | 정상 빈 인용과 잘못된 구조 구분 |
| F-04 | 유효 JSON 뒤에 인용 표기·설명문이 붙음 | Parser JSON 오류 | 임의 JSON 부분 추출·문자열 잘라내기 금지 |
| F-05 | 인용 URL 일치·인용 위치는 후보 URL span과 무관 | URL 기준 통과 가능, 위치 관계는 미검증 | 오프셋을 후보 의미 연결의 근거로 오인 금지 |
| F-06 | 같은 URL이 여러 후보에 등장·인용 위치는 한 곳 | S0 중복 규칙만 적용, 나머지 관계 미검증 | URL 집합이 후보별 관계를 표현하지 못함 |

### 5.L — 입력 크기·항목 수 방어 (v0.2.1 추가, G-03)

| ID | 원본 Fixture의 단일 변형 | N 기대 | S0·S1 Preview 기대 | 금지 행동 |
|---|---|---|---|---|
| L-01 | 유효 후보 JSON의 원문 UTF-8 크기가 정확히 **32,768 bytes** (별도 무시 가능한 JSON 필드의 패딩 사용) | NORMALIZED | S0 성공·`PREVIEW_READY` | 경계값 32,768을 초과로 간주 |
| L-02 | L-01 대비 **32,769 bytes** | REJECTED | S0 미호출, `INVALID_OR_INCOMPLETE_RESPONSE`, `S1_TEXT_BYTES_LIMIT_EXCEEDED` | 텍스트를 32 KiB에서 자르기 |
| L-03 | 1 search + 1 message + 14 valid reasoning = **16 output** | NORMALIZED | S0 성공·`PREVIEW_READY` | 보조 항목을 먼저 필터링해 원본 수를 바꿈 |
| L-04 | L-03에 정상 reasoning 1건을 추가해 **17 output** | REJECTED | S0 미호출, `S1_OUTPUT_ITEMS_LIMIT_EXCEEDED` | 초과 출력 항목 1건 삭제 |
| L-05 | 유효 URL 인용을 중복해 **32 annotations** | NORMALIZED | S0 성공·`PREVIEW_READY` | 중복 인용을 임의 오류로 단정 |
| L-06 | L-05에 정상 인용 1개를 추가해 **33 annotations** | REJECTED | S0 미호출, `S1_ANNOTATIONS_LIMIT_EXCEEDED` | 인용을 32개로 잘라내기 |

**Fixture 작성 주의:** L-01/02의 문자열 패딩은 **JSON 문법을 유지**해야 하고, UTF-8 **bytes**로 정확히 경계값을 만들어야 한다. 한국어 등의 다중바이트 문자를 넣은 변형도 `len(text)`가 아니라 byte 수로 판정하는 독립 검증을 포함한다. L-03/04의 `reasoning`은 §5.B에서 정의한 **정상 형식**으로 만든다. L-05/06의 Annotation은 S0 Parser가 허용하는 유효 `url_citation`으로 구성한다.

### 5.P — S1 합성 Preview 최소 계약 (v0.2.1 신설, v0.2.2 P-07/P-08 추가, G-02)

| ID | 입력/상황 | N/S0 기대 | **S1 Preview에서 독립적으로 검증할 결과** | 실패 시 금지 행동 |
|---|---|---|---|---|
| P-01 | F-BASE | NORMALIZED / S0 검증 성공 | `mode=S1_SYNTHETIC`, `status=PREVIEW_READY`, `search_execution=CONFIRMED`, `response_validation=VALID`, `tool_calls_observed=1`, 후보 1건·비게시 | `FIXTURE_ONLY` 표기, 모델의 승인 필드 복사 |
| P-02 | Mock Adapter timeout (원본 응답 없음) | N/S0 미호출 | `UPSTREAM_ERROR`, `search_execution=UNKNOWN`, `response_validation=NOT_EVALUATED`, `tool_calls_observed=null`, 후보 `[]` | 미관찰 호출 수를 0이라고 기록 |
| P-03 | F-BASE에서 search call 삭제 | N 정상 / S0 `SEARCH_NOT_EXECUTED` | `search_execution=NOT_CONFIRMED`, `response_validation=NOT_EVALUATED`, `tool_calls_observed=0`, 후보 `[]` | search 실행·후보 확보를 추정 |
| P-04 | search 완료, 잘못된 후보 JSON | N 정상 / S0 Parser 구조 실패 | `search_execution=CONFIRMED`, `response_validation=INVALID`, `tool_calls_observed=1`, 후보 `[]` | 파싱 실패를 정상 빈 후보로 표기 |
| P-05 | search 완료, 정상 `candidates=[]` | N 정상 / S0 Parser 성공 | `EMPTY_RESULT`, `search_execution=CONFIRMED`, `response_validation=VALID`, 후보 `[]`, issues `[]` | 검색 실패/구조 실패로 승격 |
| P-06 | 완료 검색 호출 2건 + 정상 후보 | N 거부 / S0 미호출 | `INVALID_OR_INCOMPLETE_RESPONSE`, `search_execution=CONFIRMED`(관찰한 완료 검색 증거), `response_validation=INVALID`, `tool_calls_observed=2`, 후보 `[]` | 도구 1건을 숨겨 정상 처리 |
| P-07 | 완료 검색 1건, 유효 JSON 후보 1건의 `source_url`과 `url_citation.url`이 불일치 | N 정상 / S0 Parser 성공, Validator `CITATION_URL_MISMATCH` | `status=NO_VALID_CANDIDATES`, `search_execution=CONFIRMED`, `response_validation=VALID`, `tool_calls_observed=1`, `candidates=[]`, `issues=[{candidate_index: 0, code: CITATION_URL_MISMATCH}]` | 후보 전부 탈락을 `EMPTY_RESULT` 또는 구조 실패로 바꾸기, issue 누락 |
| P-08 | `response.status=completed`, `response.output`을 list 대신 dict로 변형 | N `REJECTED`, S0 Parser/Validator 미호출 | `status=INVALID_OR_INCOMPLETE_RESPONSE`, `search_execution=UNKNOWN`, `response_validation=INVALID`, `tool_calls_observed=null`, `candidates=[]`, `issues=[]` | 관찰할 수 없는 호출 수를 `0`으로 기록, 출력 일부를 임의 복원 |

**P 공통:** 모든 합성 Preview의 `mode=S1_SYNTHETIC`, `request_started_at_utc=null`, `response_received_at_utc=null` 및 최상위/후보별 안전 필드를 검사한다. `status`가 실패해도 정상적으로 관찰된 완료 검색의 존재 사실을 지우지 않는다. 실제 서비스 외부 공개 API나 장기 저장 파일의 계약이 아니다.

### 5.X — 복합 오류 우선순위 및 원본 증거 독립 검증

| ID | 복합 입력 | 기대 대표 결과 | 반드시 금지할 구현 |
|---|---|---|---|
| X-01 | 검색 호출 2건 + 정상 후보 | `INVALID_OR_INCOMPLETE_RESPONSE`, `TOOL_CALL_LIMIT_EXCEEDED` | 1건을 버리고 정상 후보 반환 |
| X-02 | 검색 호출 failed + 정상 JSON/인용 | 응답 실패, 후보 0 | 본문만으로 성공 반환 |
| X-03 | Refusal + 유효 후보 | 응답 실패, 후보 0 | 정상 후보만 부분 반환 |
| X-04 | 메시지 2개 + 각자 유효 인용 | 메시지 모호성, 후보 0 | 마지막 메시지 선택/병합 |
| X-05 | 잘못된 JSON + 인용 URL 일치 | Parser 오류, 후보 0 | 인용 존재만으로 성공 |
| X-06 | 원본 호출 2건 vs Normalizer 투영 1건 | **반드시 실패** | 투영 결과끼리만 비교해 PASS |

## 6. 테스트 책임과 검증 방법

### 6.1 테스트 계층

| 테스트 계층 | 입력 | 독립 검증할 관찰값 | 결과 |
|---|---|---|---|
| Normalizer 단위 **[Gate A]** | 합성 전체 Response | 원본 호출 수, 항목 상태, NormalizationResult, 입력 불변, 미지원 항목 처리, §2.5 상한 | NORMALIZED/REJECTED |
| S0 계약 통합 **[Gate A]** | 정규화 성공 결과 | `parse_response()` 반환값, `validate_candidates()` 후보와 issues, 호출 여부 | 구조 및 후보 유효성 |
| S1 조정 계층 **[Gate B]** | Mock Adapter + 합성 응답/오류 | 호출 횟수, §2.3 최소 Preview, 권한 값, 비게시, 로그 | S1 Preview |
| 회귀·격리 **[Gate B]** | 기존 S0 테스트 | 외부 import/I/O 없음, S0 공개 이름 보존 | S0 영향 없음 |

**테스트 독립성:** S0의 `tests/responses_web_search/conftest.py`는 강력한 격리 가드다. S1은 예컨대 **별도 테스트 디렉터리**에 배치하도록 권고하나 정확한 경로명은 구현 브랜치 구조 확인 후 확정한다. S0 테스트의 기존 분리 실행 옵션을 유지한다.

### 6.2 Red Phase 시작 전 검사 (향후 별도 승인 필요)

1. 첫 실행에서 S1 제품 코드가 없어서 실패하는 **의도한 Red**인지, 잘못된 테스트 수집·import·네트워크 오류인지를 분리한다.
2. F-BASE, A-04, B-06, C-03, C-05a, C-07, D-01, D-05, **L-02/L-04/L-06, P-02/P-04**, E-04a/b, X-06을 우선 구현 대상으로 권고한다.
3. 기대값을 Normalizer 출력으로 역산하지 않는다. `web_search_calls_observed=2` 같은 원본 기준 값을 테스트에 **별도로 명시**한다.
4. `S0 미호출` 조건은 spy로 검증하고, 모의 SDK/HTTP 호출·DB DML·파일 영속화는 0건임을 검증한다.
5. 변경 전후에 S0의 기존 116개 테스트 **재실행 결과를 새로 기록**한다. 이전 보고의 PASS를 재실행 증거로 대체하지 않는다.

### 6.3 Gate A/B/C/D 분리 및 판정 기준 (G-01)

| Gate | 범위 | 이번 v0.2.2의 상태 | 다음 단계로 인정할 수 있는 증거 |
|---|---|---|---|
| **S1-GATE-A** | 합성 Normalizer + S0 Parser/Validator 통합, `A/B/C/D/F/X/L`(관련 책임 기준) | **FROZEN — 합성 계약 한정** | 합의된 합성 AC PASS, 원본 불변, 단일/복합 오류 차단 및 상한 경계 검증 |
| **S1-GATE-B** | Mock Adapter, `E`(단 **E-08 제외**), `P`, 비게시·로그·S0 회귀/격리 | **FROZEN — 합성 계약 한정** | Mock 1회, Preview 필드·UNKNOWN, 게시/DB/Redis 0, S0 회귀 및 Ruff PASS |
| **S1-GATE-C** | 특정 SDK 버전·모델과 실제 SDK 객체·전송 설정·자동 재시도, `E-08`, 인용 offset 해석·Structured Outputs 조합 | **NOT FROZEN / NOT VERIFIED** | 선정 버전 타입/직렬화 및 공식 지원 확인, 네트워크 호출 없이 가능한 경계 테스트; 실호환 결론은 Gate D 유보 |
| **S1-GATE-D** | **사용자 별도 승인 후** 실제 유료 Responses `web_search` 1회 소량 실험 | **NOT AUTHORIZED / NOT VERIFIED** | 실제 output/인용/비용/후보 통과율 관찰, 원출처 독립 검증은 별도 S2 |

**동결 의미:** 사용자는 Gate A/B 합성 계약을 명시적으로 승인했으며, 그 **기대 동작만** FROZEN 상태로 변경 통제한다. Gate C/D의 모델·SDK·실제 응답 구조, 요금·권리·원출처 검증, 자동 게시를 동결 또는 승인했다는 뜻이 아니다. 실응답에서 충돌이 나면 조용히 S0 인용 기준을 낮추지 않고 변경 요청·반례·회귀 영향을 보고한다.

### 6.4 Synthetic Gate A/B PASS 기준 (동결된 수용 기준, 실행 미검증)

- **Gate A/B로 분류한 합성 AC만** 전부 통과하고, 도구 호출/정규화 실패/인용 우회/게시 권한 승격/모의 Adapter 재호출/격리의 필수 반례가 통과해야 한다. **E-08은 Gate C 전용**이므로 A/B 통과를 막는 미실행 항목으로 세지 않는다.
- S0 회귀 PASS, 선택 범위 Ruff PASS, 기존 공개 이름 보존.
- 정규화 결과가 `NORMALIZED`여도 실제 Response에서 해당 형태가 반환된다는 주장 금지.
- 미확정인 offset 정책·SDK 객체 직렬화 등은 **NOT VERIFIED**로 명확히 남기고 임의로 PASS 처리하지 않는다.
- 테스트 실패를 수용 기준 완화로 해결할 수 없다. 재현·원인 분석→설계 변경 승인→테스트·구현 변경 순서를 지킨다.

## 7. Step 5 — 실응답 호환성 Gate 및 미확정 항목

### 7.1 실응답 Gate에서 실제로 확인할 사항

1. 선정 모델·SDK 고정 버전과 Responses `web_search` 지원·계정 접근 확인.
2. API 요청 설정·호출 상한·자동 재시도 0·timeout·비용 상한 확인. **실제 호출은 사용자 별도 승인 후에만**.
3. `response.output`에 어떤 유형이 실제로 나타나는지, `web_search_call.status`/`action.type` 및 메시지 `phase`/`status`의 실제 조합 확인.
4. 자체 `{"candidates": [...]}` JSON과 `url_citation`이 **함께** 제공되는지 확인. Structured Outputs와 Web Search 조합은 사전에 확정된 지원으로 가정하지 않음.
5. 인용 `url`, 제목, `start_index`, `end_index`가 실제 텍스트에서 어떤 의미인지 확인. 인용 위치가 JSON의 후보 필드와 연결된다고 추정하지 않음.
6. `sources`만 나오거나 `url_citation`이 없으면 **후보 검증 기준 완화 없이** 진단·비게시 후보 0건 처리.
7. Normalizer가 정상 응답을 과도하게 거부한다면 원인(복수 메시지, offset, annotation 등)을 유형별로 보고하고 **계약 변경을 별도 승인**받음.
8. 사용량·실제 도구 호출 수·요금과 독립 원출처 확인 가능성을 분리해 보고. `PREVIEW_READY`는 게시 GO가 아님.

### 7.2 명시적 미확정·추가 의사결정

| ID | 미확정 사항 | 현재 임시 정책 / 필요한 증거 |
|---|---|---|
| O-01 | 복수 Assistant 메시지에서 `phase=final_answer`만 선택 가능 여부 | 현재 전체 거부. 정상 실응답 사례 발견 시 타입/문서 대조 후 변경 검토 |
| O-02 | Annotation offset의 정수 범위·형식·문자 인덱스 의미 | 추적은 보존, 후보별 지지 관계 검증은 미승격. 명백한 잘못된 offset을 S1에서 강제 거부할지는 별도 결정 |
| O-03 | 공식 SDK의 response 객체→dict 직렬화 규칙 | 선택 SDK 버전의 실제 모델 타입 대조·단위 테스트 필요 |
| O-04 | **실제 Live Preview**의 모드, 모델/SDK 진단, 호출·시각·비용 세부 표현 | **합성 Preview 최소 계약은 §2.3에서 Gate A/B 한정 FROZEN**. 실제 Live 값은 Gate C/D에서 확정 |
| O-05 | **실제 정상 응답**의 크기 분포와 SDK 수신 body·메모리 상한 | **합성 내부 상한은 §2.5에서 Gate A/B 한정 FROZEN**. 실제 응답과 충돌 시 Gate C에서 근거를 갖춰 변경 승인 |
| O-06 | Structured Outputs + web_search 결합과 7일 검색 범위 충족 | 공식 지원 확인 및 실제 응답 검증. 모델 생성 텍스트만으로 최신성 PASS 금지 |
| O-07 | 어떤 후보가 '트렌드'이며 인기도 근거가 있는가 | S1에서 보장하지 않음, 원출처 검증과 운영 승인에서 별도 판단 |

**주의:** 최종 S1 Live API의 산출이 0건이어도 `검색 완료 + 유효 응답 + 후보 0건`과 `정규화 실패`를 분리한다(S1-D01). 단, 제품 공급원 실험에서 후보 발견이라는 비즈니스 목표 달성 여부는 별도 평가한다.

## 8. 최종 리뷰 체크리스트 / 동결 Gate

- [ ] 모든 AC의 정상/실패 경로, Normalizer vs S0 vs S1 Preview의 책임이 모순 없이 정의됨
- [ ] C-05a/b: S0 Parser 인용 구조 책임 유지. SDK 수신 단계 실패 가능성도 구분됨
- [ ] C-07/F-05: URL 일치와 인용 위치·원문 사실 검증을 별도로 표시함
- [ ] E-04: API Key/실패 원문 비노출과 내부 검토 후보 원문 반환을 분리함
- [ ] 원본 전체 검색 호출 수와 미완료/실패/Refusal 정보가 투영 전에 검증됨
- [ ] 정상 `reasoning` 허용·복수 메시지 초기 거부의 테스트 기대값 정합성 확보
- [ ] S0 격리 유지 및 S1 비게시/No-Retry/No-DB 경계를 수용 기준에 반영
- [x] **G-01:** Gate A/B 합성 계약과 Gate C/D 실제 SDK/호환성·유료 호출을 명확히 분리함 — 사용자 승인
- [x] **G-02:** §2.3 합성 Preview 최소 필드·UNKNOWN/null 정책과 P-01~P-08의 기대값을 승인함 — 사용자 승인
- [x] **G-03:** §2.5 합성 입력 상한 및 L-01~L-06의 경계 테스트를 승인함 — 사용자 승인
- [ ] O-01~O-06 중 **Gate A/B Red Phase에 필수인 항목**에 대한 사용자 결정·자료 확인 완료
- [x] **Gate A/B 합성 계약만 FROZEN**이며 S1 전체 실응답 계약은 NOT VERIFIED — 사용자 승인. 자동 테스트의 완료는 미확인

**현재 판정:** **AC v0.2.2 Gate A/B 합성 계약 제한 FROZEN(사용자 승인) / Gate C/D NOT FROZEN·NOT VERIFIED / Codex Red·Green 미승인 / 실응답 호환성 미검증.** 이는 기대 동작의 확정이며 pytest PASS·실제 API 호환성 완료 선언이 아니다. 문서 원격 반영만 이번 사용자 승인 범위에 포함하고 PR·merge·유료 API 호출은 포함하지 않는다.

## 9. 근거 자료

### 9.1 프로젝트 기준 문서 (동일 저장소 `dev`, 확인 시점)

- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S0_Minimal_Contract_v0.1_20261112.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S0_Phase2_Green_Report_20261112.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_Minimal_Implementation_Contract_Final_Review_v0.1_DRAFT_20261112.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Real_Data_Source_Selection_Final_Review_v0.1_DRAFT_20261112.md`
- `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`
- `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`
- `backend/app/responses_web_search/{types,parser,validator,service,fixture_adapter}.py` 및 `backend/tests/responses_web_search/`

### 9.2 공식 외부 자료 (열람 기준 2026-11-12)

- OpenAI Web Search guide: https://developers.openai.com/api/docs/guides/tools-web-search
- OpenAI Python SDK — `response_output_message.py`: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_output_message.py
- OpenAI Python SDK — `response_reasoning_item.py`: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_reasoning_item.py
- OpenAI Python SDK — `response_function_web_search.py`: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_function_web_search.py
- OpenAI Python SDK — `response_output_text.py`: https://github.com/openai/openai-python/blob/main/src/openai/types/responses/response_output_text.py
- OpenAI Python SDK README — retries: https://github.com/openai/openai-python#retries

> 공식 SDK 저장소 `main`의 타입 정의는 **문서 구조 확인용**으로 사용했다. 프로젝트의 `openai` SDK 버전이 미정이므로, 특정 버전에서 이 구조가 항상 동일하다고 단정하지 않는다.

## 10. v0.2.2 제한 동결 승인 범위와 변경 기록

- **사용자 명시 승인:** 전체 S1 계약을 동결하는 B안 대신 **합성 계약만 제한 동결하는 A안**; G-01 Gate 분리, G-02 합성 Preview, G-03 합성 입력 상한의 A안 및 P-07·P-08 추가를 승인. **Gate A/B 합성 AC의 기대 동작을 FROZEN으로 기록**한다.
- **원격 반영 범위:** `dev`를 기준으로 만든 **동일 기능 브랜치 `feat/responses-web-search-s1-normalizer`**에 이 문서 1건만 커밋/푸시. 후속 Normalizer 구현은 같은 브랜치에서 진행하되 **Codex Red/Green 코드는 미승인**. PR 생성, `dev` 병합, SDK 설치, 실제 유료 호출 등은 별도 승인이다.
- **기존 AC 보존:** v0.2 A/B/C/D/E/F/X **61건**의 테스트 ID 및 기존 기대 결과 보존. v0.2.1의 L-01~L-06·P-01~P-06 **12건** 보존. v0.2.2의 P-07·P-08 **2건** 추가 → 문서상 **총 75건**, **Gate A/B 74건** + **Gate C(E-08) 1건**. 이 수는 pytest 테스트 함수 수/테스트 통과 결과가 아니다.
- **검증 수준:** 본 문서 검토와 원격 코드 대조는 설계 검증이다. 새로운 pytest·Ruff·실제 SDK·실검색 테스트는 실행하지 않았다. 코드 구현 뒤 해당 Gate의 AC 전부 검증할 때만 PASS를 선언한다.
- **변경 통제:** Gate C/D에서 정상 실응답이 이 합성 계약과 충돌할 경우, 기존 인용·비게시 정책을 임의 완화하지 않는다. 재현 증거, 변경할 AC, S0 회귀 영향, 대안을 문서화하고 사용자 별도 승인 후 수정한다.
- **다음 단계:** 사용자 별도 승인된 Codex Red Phase → Green 및 S0 회귀 → Gate C SDK 호환성 → 별도 유료 호출 승인이 있는 Gate D 실응답 관찰.