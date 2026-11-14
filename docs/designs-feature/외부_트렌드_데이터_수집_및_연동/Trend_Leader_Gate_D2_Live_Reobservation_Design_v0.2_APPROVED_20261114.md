# Trend Leader — Responses Web Search Gate D2 실응답 재관찰 설계 검토안 v0.2

> 문서 상태: **DESIGN APPROVED / NOT FROZEN / NOT AUTHORIZED FOR LIVE EXECUTION**
>
> 작성 기준: 2026-11-14 KST
>
> 기능 브랜치: `feat/responses-web-search-gate-c1`
>
> 최초 작성 기준 HEAD: `3086f366a44fb6032d13ebb4d108fd91a95203c2`
> v0.2 리뷰 기준 HEAD: `84efa2985d34fb3c2780306d366e6005ecd07950` (D2 v0.1 문서 2건 추가 이후, 구현 변경 없음)
>
> 적용 우선순위: 현재 채팅 결정 → 해당 기능 Frozen → 프로젝트 AI 개발 가이드라인 → 실제 코드
>
> **승인 범위:** 2026-11-14 KST 사용자가 Gate D2 v0.2 설계를 승인하고 기능 브랜치 문서 반영을 요청했다. 이 승인은 **이 설계 문서의 GitHub 반영에 한정**하며, D2 FROZEN, 추가 GitHub/코드 변경, 유료 API 실행, 기존 Frozen 변경 또는 실데이터 게시를 승인하지 않는다.

## 0. 한 줄 결정

**KEEP CURRENT POLICY / OBSERVE BEFORE CHANGE / PAID REQUEST HOLD**

기존 D1-B.1의 안전한 `web_search_call_details` 관찰을 재사용한다. S1/S0의 원본 호출 수 1개 제한과 비게시 정책은 유지한다. 신규 실호출은 사전 점검·명시적 별도 승인 후 사용자가 직접 수동으로 **Responses API 요청을 최대 1회 시도**하도록 계획하며, 이번 설계 단계에서는 **0회**이다. 요청의 서버 처리·응답 수신·후보 획득은 보장하지 않는다.

## 1. 문제 정의와 근거

### 1.1 사용자 제공 첫 Live Preview (2026-11-14 KST)

- 실제 API 응답 수신: `response_status=completed`
- 요청/응답 모델 일치: `requested_model=response_model=gpt-6-luna`, `model_match=MATCH`
- 출력 구성: `reasoning=4`, `web_search_call=2`, `message=1`
- `search_execution=CONFIRMED`, `tool_calls_observed=2`
- 거부: `status=INVALID_OR_INCOMPLETE_RESPONSE`, `reason_codes=[TOOL_CALL_LIMIT_EXCEEDED]`
- `response_validation=INVALID`, `candidates=[]`
- SDK 사용량: 입력 `13,381`, 출력 `1,120`, 합계 `14,501` tokens
- 요청 시작 `2026-11-14T06:24:33.003051+00:00`, 응답 수신 `2026-11-14T06:24:52.940944+00:00`
- 이 출력에서 두 검색 항목 각각의 `status` 및 `action.type`은 **관찰되지 않음**. 실제 처리 횟수와 청구 횟수 **미확정**.

### 1.2 공식 동작과 프로젝트 의미 차이

- 공식 Responses `max_tool_calls`: 응답 전체에서 **처리할 수 있는 내장 도구 호출의 최대 횟수**. 문서상 모델의 추가 도구 호출 시도는 **무시된다**. 이 설명만으로 초과 시도의 `output` 표현, 개별 응답의 실제 처리 횟수 또는 청구 횟수를 확정할 수 없다.
- 프로젝트 `S1/S0 max_tool_calls=1`: 원본 `response.output`에서 관찰된 **`web_search_call` 항목 개수**를 집계하여 2개 이상이면 거부한다.
- SDK Web Search `action.type`: `search`, `open_page`, `find_in_page`.
- 따라서 응답의 `web_search_call=2`만으로 `search` 완료 2회 또는 청구 2회를 확정하지 않는다.

### 1.3 근거 수준

| 항목 | 근거 | 상태 |
|---|---|---|
| 요청·모델·출력 개수·사용량 | 사용자가 제공한 첫 Live Preview | **관찰됨** |
| S1의 거부 위치와 처리 | `normalizer.py`, `parser.py`, Frozen A-04/P-06/X-01/X-06 | **코드·문서 확인됨** |
| D1-B.1 호출별 구조 진단 추가 | 기능 브랜치 HEAD, 사용자 `96 passed` 보고 | **원격 코드 확인 / 테스트 재실행 안 함** |
| 첫 응답 두 항목의 세부 `status/action.type` | 기존 기록에 없음 | **미확정** |
| API 내장 처리 횟수와 실제 결제 금액 | Preview에 근거 없음 | **미확정** |
| 정상 후보 JSON·개별 인용 여부 | S1 상한에서 단락됐고 원문 저장하지 않음 | **미확정** |

**구현에 근거한 제한적 추론:** 첫 Preview의 `search_execution=CONFIRMED`가 당시 D1→S1 코드에서 생성됐다는 전제하에, 적어도 1개 항목은 `status=completed`이면서 `action.type=search`였다고 판단할 수 있다. 어느 위치의 항목인지는 알 수 없다. 두 번째 항목의 상태·동작 및 실제 처리·청구 횟수는 여전히 미확정이다.

## 2. 목표 / 비목표

### 목표

1. **추가 과금 없이** 기존 코드·합성 Fixture·Frozen AC에서 결론을 도출한다.
2. 다음에 **별도 승인된 단일 실제 요청**이 있을 경우, D1-B.1 필드로 모든 `web_search_call`의 관찰 상태 및 동작 종류를 구분할 수 있도록 준비한다.
3. **구조 관찰 충분성**, **현재 파이프라인 판정**, **후보 확보 결과**를 별도 축으로 기록한다. 보조 동작을 관찰해도 후보 JSON·인용 검증이 선행 차단되었다면 **후보를 잘못 거부했다는 의미의 False Rejection은 입증되지 않았다**고 표시한다.
4. 정책 변경 여부를 하나의 결정 기록으로 남긴다.

### 비목표

- 이번 단계에서 실제 유료 API 호출·재시도·실제 검색 실행
- C2 `max_tool_calls=1` 확대 또는 변경
- S1/S0 호출 1개 제한과 기존 Frozen AC 수정
- 검색 항목 일부 삭제·병합·성공 상태 강제 변환
- 후보 JSON/인용을 만들어 내거나 검증 우회
- 모델·SDK·프롬프트·시간 창 정책 임의 변경
- DB/Redis/Writer, P4, G5/G6, 서비스 게시, AWS B-2 및 Lightsail 작업
- API Key·원본 응답·요청 검색어·원출처 URL과 쿼리값의 비승인 로그/파일 저장

## 3. 기준 구현과 변경 통제

현재 D0 고정 설정:

| 항목 | 값 |
|---|---|
| model | `gpt-6-luna` |
| profile | `IT_DIGITAL` |
| lookback_days | `7` (서울 날짜 양끝 포함) |
| max_candidates | `3` |
| timeout | `60.0` |
| max_output_tokens | `4096` (reasoning 포함) |
| max_tool_calls | `1` |
| max_retries | `0` |
| store / stream | `False / False` |
| tool | `web_search`, `tool_choice=required` |
| include | `web_search_call.action.sources` |

> 실행일이 달라지면 D0의 최근 7일 날짜 구간도 달라진다. 이 날짜 구간은 **요청 프롬프트 조건**이며 API가 검색 결과의 게시일을 강제 필터링한다는 보장이 아니다. 따라서 D2는 D1 응답의 완전 재현이 아니라 **동일 설정·변하는 날짜/웹 환경 하에서의 재관찰**이다. `model_match=MATCH`는 요청/응답 모델 식별자 문자열 일치만 나타내며 **동일 snapshot·동일 출력·결정성**을 보장하지 않는다.

관련 파일:

- `backend/app/responses_web_search/gate_d_preflight.py`
- `backend/app/responses_web_search/d1_cli.py`
- `backend/app/responses_web_search/d1_live_preview.py`
- `backend/app/responses_web_search/c2_transport.py`
- `backend/app/responses_web_search/c1_adapter.py`
- `backend/app/responses_web_search/normalizer.py`
- `backend/app/responses_web_search/parser.py`
- `backend/tests/responses_web_search_c2/test_d1_live_boundary_red.py`
- Frozen `Trend_Leader_Responses_Web_Search_S1_Normalizer_Acceptance_Criteria_v0.2.2_Gate_AB_FROZEN_20261112.md`

**선호 대안 A (현재):** 구현 변경 없이 기존 D1 CLI·안전 진단을 재사용.

**대안 B (별도 보완 후보):** 실응답에서 진단 자체가 `null` 또는 `UNKNOWN`이 반복되어 목표를 충족하지 못하는 경우, 그 근거를 보고한 뒤 별도 오프라인 진단 코드 보완을 설계한다. 현재 선제 구현하지 않는다.

## 4. 데이터 계약: 출력 범위와 의미

기존 Live Preview에서 확인할 필드:

- 통제: `mode`, `review_status`, `publication_status`, `publish_authorization`, `independent_source_verified`
- 결과: `status`, `reason_codes`, `issues`, `candidates` (정책 및 내용은 노출 주의)
- 실행 증거: `search_execution`, `response_validation`, `tool_calls_observed`
- 모델/시간: `requested_model`, `response_model`, `model_match`, `request_started_at_utc`, `response_received_at_utc`, `response_status`
- 형태: `output_type_counts`, `web_search_call_details`
- 비용 정황: `usage` (실제 결제액 아님)

`web_search_call_details`의 각 항목은 `output_index`, `status`, `action_type`만 포함한다. 해당 필드가 `null`이면 세부 구조를 **관찰할 수 없었다**는 뜻이며 호출이 없었다고 추정하지 않는다. 빈 배열 `[]`도 `output_type_counts`와 대조 없이 검색이 없었다는 확증이 아니다.

**관찰 증거의 한계:** `web_search_call_details`는 후보 JSON 유효성, `url_citation` 적합성, 청구 횟수, 원출처 사실성을 알려주지 않는다. `output_type_counts`에서 메시지가 1개라고 하여 그 메시지가 S0를 통과한다는 근거도 없다. D2에서 아래에 정의하는 관찰 충분성은 **진단 데이터의 내부 일관성** 판정이며, 저장하지 않은 원본 응답과의 독립적인 동일성 검증은 아니다.

## 5. 오프라인 판단표 (D2-AC, 신규 Frozen 아님)

**D2-AC는 설계 검토·사후 기록용 판정 기준이다.** S1/S0 합성 Gate A/B Frozen AC 또는 런타임 수용 조건을 추가·변경하지 않는다. 구조 관찰 성공과 후보 수용 성공은 독립적이다.

| ID | 관찰 시나리오 | 현행 파이프라인 처리 | D2 해석 / 후속 결정 |
|---|---|---|---|
| D2-01 | 완료 `search` 1개, 다른 도구 항목 없음 | S1 통과 시 S0 후보·인용 검증 진행 | 구조 관찰에 성공해도 검토 후보 확보는 별도 판정 |
| D2-02 | 완료 `search` 1개 + `incomplete/failed/searching/in_progress` 항목 | 원본 호출 2개 → 먼저 `TOOL_CALL_LIMIT_EXCEEDED`, S0 미호출 | 실패 항목까지 진단하되 첫 번째 대표 거부 사유와 혼동하지 않음. 일부를 삭제해 성공 처리 금지 |
| D2-03 | 완료 `search` + 완료 `open_page` **또는** `find_in_page` | 원본 호출 2개 → 전체 거부, S0 미호출 | 실응답 구조와 **현 계약의 호환성 검토 근거**. 후보 JSON·인용이 미검증이므로 *False Rejection 확정 불가* |
| D2-04 | 완료 `search` 2개 | 원본 호출 2개 → 전체 거부 | 실제 처리·청구 2회라고 추정 금지, 상한 변경 미승인 |
| D2-05 | 완료 `open_page`/`find_in_page`만 1개, 완료 `search` 없음 | S1 정상화·필요 구조 충족 시 S0 `SEARCH_NOT_EXECUTED` | 보조 동작을 `search`로 승격 금지. **보조 동작만 2개 이상**이면 먼저 상한 위반으로 거부하며 일반화 금지 |
| D2-06 | `web_search_call_details=null`, 항목 개수 불일치, 또는 상태/동작 `UNKNOWN` | 기존 결과를 그대로 보존 | **구조 관찰 축만 `INCONCLUSIVE`**. 파이프라인 결과와 후보 결과를 임의로 바꾸거나 재호출하지 않음 |
| D2-07 | C1 오류 또는 타임아웃·네트워크 오류 | 기존 오류 상태·미관찰 처리 유지 | 전송·응답 수신 여부와 실제 서버 처리 여부를 구분. 자동 재호출 금지 |
| D2-08 | `PREVIEW_READY`와 검토 후보 존재 | 비게시·검토 필요 | 후보 확보 축만 `READY_FOR_REVIEW`; 독립 출처 검증 및 P4 승인 전 서비스 공급 금지 |
| D2-09 | S1 `TOOL_CALL_LIMIT_EXCEEDED` | `parser_input=None`, S0/Validator 미호출 | 검색 도구가 관찰돼도 후보 JSON·인용 적합성을 검증했다고 표시 금지 |

### 5.1 진단 수집 순서와 실제 반환 사유 우선순위

- **진단 수집 흐름:** C2가 SDK 응답을 반환 → D1 `_response_observations()`에서 모델/상태/출력 유형/안전한 호출별 메타데이터 관찰 → 필요 시 모델 불일치로 즉시 종료. 이 관찰값은 C1/S1 결과가 나와야만 존재하는 정보가 아니다.
- **후보 처리 흐름:** 모델 문자열 일치 확인 → C1 변환 → S1의 최상위 `response.status=completed` 및 `output` 목록 구조 확인 → **원본 `web_search_call` 항목 수 상한 검사** → 각 도구/메시지 상태 검사 → 출력 크기·텍스트·annotation 상한과 나머지 구조 검사 → S0 Parser → Validator.
- **오류 우선순위:** 정상적인 목록에 완료 `search` + 실패/미완료 항목이 함께 있어 원본 검색 항목이 2개라면, S1은 현재 개별 상태 검증보다 먼저 `TOOL_CALL_LIMIT_EXCEEDED`를 반환한다. 대표 사유가 다른 결함의 **부재**를 증명하지는 않는다.
- C1 변환 오류·모델 불일치·전송 실패에는 해당 중단 경로를 적용하며, S1·S0가 실행되지 않았다면 검증되지 않은 후보 본문·인용을 PASS로 기록하지 않는다. 원본 도구 항목을 삭제하거나 재배열하지 않는다.

## 6. 비용·승인 Gate

### 6.1 설계 단계

- 외부 Responses 유료 요청: **0회**.
- 로컬 테스트는 검증된 MockTransport 사용; 단위 테스트로 실제 HTTP를 보내지 않는다.
- 기존 D1-B.1 테스트 `96 passed`는 사용자 실행 보고이며 이번 문서 작성 중 재실행하지 않는다.

### 6.2 향후 단일 실험을 별도로 승인하려면

사용자가 **새로운 명시적 승인**으로 다음을 확인해야 한다.

1. 이번 실험의 고정 범위: **Responses API 요청 최대 1회**, 자동 재시도 0, 오류 시 재실행 HOLD.
2. 실제 프로젝트 및 API Key 소속·버전 고정·동일 터미널의 오프라인 사전 검증 확인. 실제 API Key를 문서·출력에 넣지 않음.
3. 실제 OpenAI Platform Usage에서 첫 실험 금액을 확인하고, **사용자가 허용할 달러 기준 예산을 먼저 정함**. 프로젝트 예산 한도가 단일 요청의 즉시 중단·최대 청구액 보증은 아님.
4. 공식 단가를 실행 직전 재확인: 웹 검색은 도구 호출 과금과 모델/검색 콘텐츠 토큰 과금이 함께 있을 수 있음. 첫 실험의 14,501 tokens는 요금 영수증이 아님.
5. CLI에서 요구하는 TTY/정확한 확인 문구는 별도 운영 승인 자체를 대체하지 못함.
6. 승인하지 않으면 유료 실행 명령이나 `EXECUTE ONE LIVE SEARCH`를 사용하지 않음.

> **주의:** 현재 고정 설정이 `max_tool_calls=1`, `max_output_tokens=4096`, `max_retries=0`이더라도 전체 입력 토큰·내부 도구 검색 처리량·실제 청구액을 달러 기준으로 사전 확정할 수는 없다. 프로젝트 요금 제한도 지연 반영될 수 있으므로 승인 비용은 보수적으로 설정한다.

### 6.3 단일 실험 승인 후 운영 규칙 (이번에는 실행하지 않음)

- 사용자가 직접 기존 대화형 D1 CLI로 **요청을 최대 1회 시도**한다. 응답 수신·완료 여부는 보장하지 않는다. 실행 승인은 이 시도를 대상으로 하며 동일 조건의 후속 호출까지 허용하지 않는다.
- `stdout` 파이프/리다이렉션을 사용하지 않음(TTY 요구).
- **정상 응답·후보 0건·상한 초과·오류·타임아웃·취소·진단 불충분의 모든 결과에서 해당 시도 후 STOP**한다. 재시도는 반드시 새 승인으로 처리한다.
- 결과를 공유할 때는 안전한 구조 정보 중심으로 전달. `candidates`의 출처 URL에는 인증 쿼리 등이 포함될 수 있으므로 원문을 무조건 복사·장기 보관하지 않음.
- 실행 전후 Usage 대시보드 확인은 요금 검증 참고 자료이며 요청별 정확한 청구 분리 여부를 확인하고 근거 수준을 기록.

## 7. D2 결과 기록 — 서로 독립적인 세 축

**D2 평가 결과는 내부 리뷰용 기록이며 CLI/Preview의 신규 응답 필드가 아니다.** 현행 Preview 필드·`status`·`reason_codes`를 바꾸지 않고 기록으로만 분류한다. 두 축 이상이 동시에 성립할 수 있는 상황을 단일 성공/실패 코드로 합치지 않는다.

### 7.1 A축 — 호출별 구조 관찰 충분성

**`SUFFICIENT`**: 아래 조건을 **모두** 충족한다.

1. `web_search_call_details`는 배열이며 `output_type_counts`는 유효한 유형별 개수 객체다. 항목별 세부 수와 `output_type_counts.get("web_search_call", 0)`이 정확히 일치한다.
2. 각 `output_index`는 중복되지 않는 0 이상의 정수이며, 관찰된 전체 출력 항목 수(`output_type_counts`의 개수 합계)보다 작다. 각 항목의 `status`, `action_type`은 허용된 값이고 `UNKNOWN`이 없다.
3. `tool_calls_observed`가 정수로 제공되었다면 세부 항목 수와 같다. `null`이라면 자동으로 0으로 변환하거나 허위 불일치로 처리하지 않는다(C1 실패 등에는 S1 집계를 얻지 못할 수 있음).
4. `search_execution`이 `CONFIRMED` 또는 `NOT_CONFIRMED`로 평가되었다면, 완료된 `search`가 각각 존재/부재한다는 세부 진단과 모순되지 않는다. `UNKNOWN`은 C1/S1 미실행 등의 결과일 수 있으므로 세부 진단 자체가 충분한 경우에도 무조건 모순으로 처리하지 않는다.

**`INCONCLUSIVE`**: 원본 응답 미수신, `web_search_call_details=null`, `output_type_counts=null`, 개수·위치·상태 불일치 또는 허용되지 않은 `UNKNOWN`으로 A축에 필요한 관찰을 완료하지 못했다. **관찰 축에서만** 미확정으로 기록하며 자동 재호출하지 않는다.

`web_search_call_details=[]`와 확인 가능한 Web Search 호출 수 **0개**는 유효한 관찰일 수 있다. 이때 구조 관찰 `SUFFICIENT`와 **완료 `search` 없음**을 함께 기록한다. `output_type_counts`만 있고 호출별 배열이 없으면 충분하다고 판단하지 않는다.

이 기준은 **D1-B.1 진단의 일관성**을 검사한다. 원본 응답을 보존·재검증하지 않았으므로 `output_index`가 원본에 정확히 대응한다는 것을 독립적으로 입증하거나 실제 검색 처리/청구 횟수를 확인하는 기준이 아니다. 또한 A축 `SUFFICIENT`가 나오더라도 `model_match`가 `MATCH`가 아니라면 **승인된 대상 모델에 대한 실응답 증거**로 승격하지 않는다. 모델 적합성은 B축에 원래 Preview 값 그대로 별도 기록한다.

### 7.2 A축 부가 분류 — 검색 동작 패턴 (복수 태그 허용)

| 태그 | 필요한 관찰 | 의미·제약 |
|---|---|---|
| `OBSERVED_ONE_COMPLETED_SEARCH` | 완료 `search` 1개, 다른 Web Search 항목 없음 | S1/S0 후보 검증 가능성만 의미 |
| `OBSERVED_MULTI_COMPLETED_WITH_AUXILIARY` | 완료 `search` 1개 이상 및 완료 `open_page`/`find_in_page` 1개 이상 | 복수 항목 전체 거부 유지, False Rejection 확정 금지 |
| `OBSERVED_MULTI_SEARCH` | 완료 `search` 2개 이상 | 과금·실제 처리 횟수로 승격 금지 |
| `OBSERVED_FAILURE_OR_INCOMPLETE` | `failed`, `incomplete`, `in_progress`, `searching` 항목 존재 | 상태 혼합을 보존, Fail-Closed 변경 금지 |
| `OBSERVED_NO_COMPLETED_SEARCH` | A축 충분하며 완료 `search`가 0개 | 검색 없음과 관찰 불능은 다름. S1의 다른 결함 거부는 별도로 기록 |
| `OBSERVATION_INCONCLUSIVE` | A축 `INCONCLUSIVE` | 항목별 패턴을 확정하지 않음 |

이 태그들은 상호 배타적일 필요가 없으며, `OBSERVED_FAILURE_OR_INCOMPLETE`와 다른 관찰 패턴이 동시에 존재할 수 있다. 서버 요청 시도 횟수·비용을 나타내지 않는다.

### 7.3 B축 — 현행 처리 정책의 결과

D1 Preview의 실제 `status`, `reason_codes`, `search_execution`, `response_validation`, `tool_calls_observed`를 **원형 의미대로 기록**한다. S1의 상한 거부, S0 `SEARCH_NOT_EXECUTED`, 구조/JSON 오류, 후보 검증까지 진행된 정상 결과를 구분하며, 하나를 다른 결과로 덮어쓰지 않는다.

- `TOOL_CALL_LIMIT_EXCEEDED` 및 S1 `REJECTED`: S0·Validator는 **미호출**, 후보·인용 검증 **미평가**.
- `SEARCH_NOT_EXECUTED`: 완료된 `search` 증거가 없어 S0가 단락, 후보 내용 검증 **미평가**.
- `response_validation=VALID`: Normalizer와 S0 파싱 기준 통과(후보별 원출처 사실성이나 게시 승인과는 무관). 후보 검증 결과는 C축에서 별도로 기록한다.
- `UPSTREAM_ERROR`, `C1_CONVERSION_FAILED` 등: 실행·변환 여부의 관찰 가능 범위를 유지, 후속 미호출을 결과로 기록한다.

### 7.4 C축 — 검토 후보 확보 결과

| 후보 결과 | 판정 조건 | 의미 |
|---|---|---|
| `READY_FOR_REVIEW` | `status=PREVIEW_READY`, `candidates` 비어 있지 않음 | 독립 원출처 검증·P4 승인 전 **비게시** |
| `ZERO_CANDIDATES` | `status=EMPTY_RESULT` 또는 `NO_VALID_CANDIDATES`, `candidates=[]` | 0건 원인이 서로 다르므로 기존 상태·`issues`를 함께 기록 |
| `NOT_EVALUATED` | 상한 거부·검색 미실행·파싱 실패·전송/변환 오류 등으로 정상 후보 판정이 진행되지 않음 | 0건을 **유효한 빈 결과**로 승격 금지 |

**D2 구조 관찰 성공의 필수조건에 후보 확보·첫 실응답 재현·정확한 청구액 확인은 포함되지 않는다.** 응답을 못 받았거나 진단값이 부족하면 A축 `INCONCLUSIVE`로 종료할 수 있지만, 어떤 경우에도 예산이 남았다는 이유로 자동 재호출하지 않는다.

### 7.5 평가 축 조합 예시 (실제 실험 결과 아님)

| 합성 상황 | A축 관찰 | B축 현행 파이프라인 | C축 후보 |
|---|---|---|---|
| 완료 `search` 1개 + 유효 후보 | `SUFFICIENT` | `PREVIEW_READY` | `READY_FOR_REVIEW` |
| 완료 `search` 1개 + `candidates=[]` | `SUFFICIENT` | `EMPTY_RESULT` | `ZERO_CANDIDATES` |
| 완료 `search` + `failed/search` | 상태·동작 전부 기록 시 `SUFFICIENT` | `TOOL_CALL_LIMIT_EXCEEDED` | `NOT_EVALUATED` |
| 완료 `open_page` 1개, 완료 `search` 없음 | `SUFFICIENT` | `SEARCH_NOT_EXECUTED` (나머지 구조 정상 전제) | `NOT_EVALUATED` |
| 응답 미수신/출력 구조 파손 | `INCONCLUSIVE` | 실제 오류 코드 그대로 기록 | `NOT_EVALUATED` |

표는 평가 축의 독립성을 설명하기 위한 **합성 해석 예시**다. D2 재호출에서 관찰했다는 뜻이 아니며, `PREVIEW_READY`가 독립 출처 검증이나 게시를 승인하는 것도 아니다.

실행되더라도 **응답 1건으로 모델의 일반적 동작 확률이나 비용 분포를 추정하지 않는다.** 단일 사례 관찰을 검토 근거로 남기되, 범용 정책 변경은 충분한 반례와 사용자 별도 승인 이후 검토한다.

## 8. 의존성과 통합 경계

- **AWS B-2:** CI/CD Migration Guard, 격리 DB/Linux 통합 검증은 별도 채팅·브랜치에서 수행.
- **P4/G5/G6:** 독립 출처 검증, 보호 등록, 운영 승인, Writer/게시 연결은 후속 Gate. Responses Preview `PREVIEW_READY`도 이를 우회하지 못함.
- 기능 브랜치는 현재 `dev`와 분기되어 있으므로 PR/병합 전 최신 HEAD, 파일 목록, Frozen·공통 의존성 확인. 이번 문서에서 PR/병합 수행하지 않음.

## 9. 승인 게이트 및 완료 조건

**D2 v0.2 문서 보완 및 Final Review 대상 조건 (이번 작업):**

- [x] 첫 실응답 관찰/미관찰 사항 분리
- [x] 공식 `max_tool_calls` 의미와 현재 S1/S0 항목 수 정책 비교
- [x] Frozen 영향 항목 A-04/P-06/X-01/X-06 및 S0 순서 의존 위험 확인
- [x] 무과금 재관찰 설계/관찰 필드/중단 기준 작성
- [x] **A축 관찰 충분성, B축 기존 파이프라인 결과, C축 후보 결과 분리**
- [x] **실제 거부 사유 우선순위와 독립 진단 수집 순서 분리**
- [x] **완료 검색 없음·`UNKNOWN`/`null`·복합 항목의 분류 기준 명확화**
- [x] 비게시·P4 운영 HOLD·외부 API 호출 미승인 유지
- [x] **사용자 v0.2 설계 승인 (2026-11-14 KST; D2 FROZEN 여부는 별도 명시적 결정)**
- [ ] **실행 비용·횟수 명시적 승인 (별도)**
- [ ] 실제 D2 재관찰 실행 (미실행)
- [ ] 결과에 기반한 S1/S0 변경 승인 여부 판정 (미확정)

**현 상태:** v0.2 Final Review PASS 및 사용자 **설계 승인 완료 / NOT FROZEN** / 코드 변경 없음 / 신규 테스트 미실행 / 유료 API 요청 0회. 별도 승인 전 실행·실험·게시 HOLD.

## 10. 참고 근거

1. 프로젝트 기준: `Trend_Leader_AI_Development_Guidelines.md`, `Trend_Leader_GitHub_Write_Safety_Policy.md`.
2. Frozen: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S1_Normalizer_Acceptance_Criteria_v0.2.2_Gate_AB_FROZEN_20261112.md`.
3. 기능 브랜치 코드(검토 기준): https://github.com/Trend-Leader-capstoneProject/feature/tree/84efa2985d34fb3c2780306d366e6005ecd07950/backend/app/responses_web_search
4. OpenAI Responses create `max_tool_calls`: https://developers.openai.com/api/reference/resources/responses/methods/create
5. OpenAI Web Search output structure: https://developers.openai.com/api/docs/guides/tools-web-search
6. OpenAI API Pricing: https://developers.openai.com/api/docs/pricing
7. 사용자 제공 2026-11-14 첫 실제 Live Preview 및 D1-B.1 테스트 `96 passed` 보고.
8. Codex D2 v0.1 오프라인 리뷰: `CHANGES REQUESTED` — 관찰 충분성·판정 순서·False Rejection 의미·단일 요청 시도 규정 보완 (2026-11-14 KST).

### v0.1 → v0.2 변경 기록 (기존 v0.1 문서 보존)

- P0: 구조 관찰 / 정책 판정 / 후보 획득의 세 축을 분리하고 충분성 AC 정의.
- P0: D1 독립 진단과 S1/S0 결과 반환 우선순위 구분.
- P1: `search + find_in_page`, 완료 검색 없음, 실패·미완료 복합 사례와 `UNKNOWN` 처리 정밀화.
- P1: 최대 1회 **요청 시도** 및 결과와 무관한 STOP 조건 명시.
- P2: 공식 `max_tool_calls`의 초과 시도 무시 문구 및 `model_match`/기간/청구 증거의 한계 구체화.
- **불변:** S1/S0 Frozen AC, C2/D0 설정, 코드, 유료 호출 승인, 게시 권한에는 변경 없음.

---

> **변경 통제:** D2 v0.2 설계 승인과 FROZEN 결정 및 Live 승인 여부는 별개다. 동결된 Gate A/B AC는 사용자 별도 승인 없이 수정하지 않는다.
