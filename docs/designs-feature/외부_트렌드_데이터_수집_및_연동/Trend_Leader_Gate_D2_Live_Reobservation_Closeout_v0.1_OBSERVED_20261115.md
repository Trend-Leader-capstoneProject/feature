# Trend Leader — Responses Web Search Gate D2 실응답 재관찰 결과 기록 v0.1

> **문서 상태:** OBSERVED / USER REVIEWED / OFFLINE ASSESSMENT COMPLETE / NOT FROZEN / NOT A LIVE OR PUBLICATION APPROVAL  
> **관찰일:** 2026-11-15 KST  
> **대상:** `Trend-Leader-capstoneProject/feature` / `feat/responses-web-search-gate-c1`  
> **검토한 원격 HEAD:** `a43ff67c8eafe177c73fcc7b30b74d2d29a9cfd3`  
> **상위 기준:** D2 v0.2 APPROVED (2026-11-14), S1 Gate A/B Limited FROZEN v0.2.2, 현재 코드, 프로젝트 AI Development Guidelines v1.2, GitHub Write Safety Policy v1.0.  
> **자료의 성격:** 사용자가 공유한 D1 Live Preview를 근거로 작성한 관찰 기록이며 API 원본 응답이나 결제 영수증을 독립적으로 입수·재검증한 결과가 아니다. 2026-11-15 KST 사용자가 D2 Closeout의 기능 브랜치 문서 반영을 승인했으며, 원자료 독립 검증·Frozen 결정·추가 유료 실행·코드 변경·서비스 게시 승인은 아니다. 

## 0. Closeout 요약

**`D2 OBSERVATION SUFFICIENT / S1 REJECTED AS DESIGNED / CANDIDATES NOT_EVALUATED / ONE APPROVED LIVE ATTEMPT CONSUMED / LIVE STOP`**

- **관찰 목표 달성:** Web Search 출력 2개 각각의 `output_index`, `status`, `action_type`을 관찰했다.
- **서비스 후보 확보 미달성:** 정상 후보 생성 여부는 검증하지 못했다. `candidates=[]`는 유효한 빈 후보 결과가 아니라 **S1 조기 거부 이후의 결과**이다.
- **현행 안전 계약 정상 작동:** `TOOL_CALL_LIMIT_EXCEEDED`로 S0 Parser·Validator 미호출, 비게시·미승인 유지.
- **다음 권고:** 추가 유료 호출 없이 Gate D3 오프라인 호환성 설계 검토. 변경 승인 전 S0/S1/C2 및 Frozen 미수정.

## 1. 관찰값 — 사용자 제공 D2 Preview

### 1.1 실행 및 응답 메타데이터

| 필드 | 관찰값 | 해석 범위 |
|---|---|---|
| `mode` | `LIVE` | D1 Live Preview 모드 |
| `requested_model`, `response_model` | `gpt-6-luna` | 요청/응답 모델 문자열이 일치. 동일 모델 snapshot 또는 결과 재현성을 보장하지 않음 |
| `model_match` | `MATCH` | 문자열 일치 |
| `response_status` | `completed` | 최상위 Responses 상태 |
| `request_started_at_utc` | `2026-11-15T04:46:55.895018+00:00` | D1이 기록한 요청 시작 시각 |
| `response_received_at_utc` | `2026-11-15T04:47:10.964376+00:00` | D1이 기록한 응답 수신 시각 |
| `output_type_counts` | `reasoning=4`, `web_search_call=2`, `message=1` | 총 7개 항목. 메시지 본문·인용의 유효성은 미검증 |
| `tool_calls_observed` | `2` | 원본 `web_search_call` 항목 수. 처리/과금 횟수 아님 |
| `search_execution` | `CONFIRMED` | S1에 의해 집계된 완료 `search` 항목이 1개 이상 |
| `usage` | input `13,455`, output `928`, total `14,383` | SDK 사용량 관찰값. 달러 청구 증명 아님 |
| `status` | `INVALID_OR_INCOMPLETE_RESPONSE` | D1 Preview의 전체 처리 결과 |
| `reason_codes` | `TOOL_CALL_LIMIT_EXCEEDED` | S1 조기 거부 대표 사유 |
| `response_validation` | `INVALID` | S1 정책을 통과하지 못함. 후보 텍스트 자체가 잘못됐다는 판정과 다름 |
| `candidates` / `issues` | `[]` / `[]` | S0/Validator 미실행으로 후보 내용 검증 결과 없음 |

### 1.2 Web Search 출력 항목 — 원본 위치 보존 진단

| `output_index` | `status` | `action_type` | D2 해석 |
|---:|---|---|---|
| 1 | `completed` | `search` | 완료 검색 항목 **1개가 관찰됨** |
| 3 | `searching` | `search` | 두 번째 검색 항목이 `completed`가 아닌 상태로 관찰됨 |

`searching`은 SDK 3.50.0 타입에서 허용하는 도구 상태 문자열이지만 **완료 상태는 아니다**. 이것만으로 서버 내부의 미처리·실패·실제 추가 처리·청구 횟수 중 하나를 확정하지 않는다. 최상위 `response_status=completed`와 개별 항목 `searching`은 서로 다른 필드의 관찰값이다.

### 1.3 보존한 안전 경계

- `review_status=REVIEW_REQUIRED`
- `publication_status=NOT_FOR_PUBLICATION`
- `publish_authorization=NONE`
- `independent_source_verified=false`
- DB/Redis/Writer/게시 연결 및 독립 원출처 검증: **미실행·미승인**.
- D2 유료 요청: 사용자 승인에 따른 **단일 요청 시도 1회 수행 보고**. 더 이상의 호출은 자동 허용되지 않는다.

## 2. D2 v0.2 §7 세 축 판정

| 축 | 판정 | 판정 근거 |
|---|---|---|
| **A — 구조 관찰 충분성** | **`SUFFICIENT`** | 출력 유형별 총 7개, Web Search 2개, 세부 진단 2개, 서로 다른 정수 인덱스 1·3, `UNKNOWN` 없음, `tool_calls_observed=2`, 완료 `search`와 `CONFIRMED` 정합 |
| **B — 현행 파이프라인** | **`INVALID_OR_INCOMPLETE_RESPONSE` / `TOOL_CALL_LIMIT_EXCEEDED`** | S1이 원본 Web Search 항목 수 `2 > 1`로 조기 거부. S0/Validator 미호출 |
| **C — 후보 확보** | **`NOT_EVALUATED`** | S1 거부 후 후보·JSON·인용 검증에 도달하지 않음 |

**A축 패턴 태그:** `OBSERVED_FAILURE_OR_INCOMPLETE`. 여기서 `searching`은 *non-completed*이며 `failed`라고 단정하지 않는다. `OBSERVED_MULTI_SEARCH`는 **완료된 `search`가 2개 이상일 때** 부여하므로 해당하지 않는다.

**중요한 구분:** A축 관찰 성공은 B축 수용이나 C축 후보 확보의 성공을 뜻하지 않는다. 특히 이번 `candidates=[]`를 `EMPTY_RESULT` 또는 `NO_VALID_CANDIDATES`로 바꾸어 기록하지 않는다.

## 3. 기존 계약에서 실제로 일어난 일

현재 S1 `normalizer.py`는 (1) 최상위 `completed`/`output` 구조 검사 → (2) `web_search_call` 원본 항목 수 검사 → (3) 각 항목의 완료 상태 검사를 수행한다.

```text
response.status = completed
output = reasoning 4 + web_search_call 2 + message 1
completed_search_actions = 1
          ↓
원본 web_search_call 2 > config.max_tool_calls 1
          ↓
REJECTED / TOOL_CALL_LIMIT_EXCEEDED
          ↓
S0 Parser·Validator 미호출 / candidates=[] / 비게시
```

이는 Frozen **A-04/X-01/X-06의 원본 항목 상한·은닉 금지 원칙** 및 D2-02/D2-09의 기대와 정합적이다. 다만 **P-06은 완료 `search` 2개와 정상 후보를 둔 합성 사례**이므로, 실제 D2의 `completed + searching` 조합을 직접 재현한 AC라고 주장하지 않는다. 추가로 코드상 **상한을 2로 늘린다는 가정만으로도 `status=searching`은 이후 상태 검사에서 다시 거부**된다. 이는 가상 경로에 대한 정적 분석으로서 실제 변경·실행 결과가 아니다. S0의 `SearchRunConfig.max_tool_calls=1` 자체도 별도 고정 조건이다.

## 4. 첫 실험과 비교 — 재현성과 증거 한계

| 비교 항목 | 2026-11-14 첫 실험 | 2026-11-15 D2 |
|---|---|---|
| 최상위 응답 | `completed` | `completed` |
| `web_search_call` 항목 수 | 2 | 2 |
| 개별 상태·동작 | 기록되지 않음 | `completed/search` + `searching/search` |
| S1 거부 | `TOOL_CALL_LIMIT_EXCEEDED` | `TOOL_CALL_LIMIT_EXCEEDED` |
| 입력/출력 토큰 | 13,381 / 1,120 | 13,455 / 928 |
| 후보 검증 | 미실행 | 미실행 |

두 번 모두 같은 출력 항목 수로 거부됐지만, **첫 실험의 두 번째 검색 상태도 `searching`이었다고 소급해서 단정하지 않는다.** 검색 웹 환경·날짜·응답의 비결정성에 유의한다.

## 5. 결정 기록과 남은 불확실성

### 현재 보존할 결정

1. 기존 `max_tool_calls=1`, S1/S0 원본 항목 상한·Fail-Closed 및 Frozen AC를 **유지**한다.
2. `searching` 항목을 `completed`로 바꾸거나, 목록에서 제거·병합하거나, 호출 증거를 줄여서 S0에 전달하지 않는다.
3. D2의 완료 조건은 **관찰 충분성**으로 한정하며, 게시 가능 후보 확보·실제 과금액 확인으로 승격하지 않는다.
4. 추가 실호출은 **HOLD**. Gate D3는 **오프라인 분석만** 승인된 범위로 취급한다.

### 여전히 확인할 수 없는 사항

- 원본 메시지의 후보 JSON·인용 URL 일치 여부와 독립 사실성.
- 두 번째 `searching` 항목이 왜 `completed` 최상위 응답에 나타났는지의 서버 내부 원인.
- 그 항목의 실제 처리·청구 횟수 및 정확한 D2 요청별 달러 비용.
- 더 많은 실응답에서 동일 현상이 얼마나 자주 발생하는지.

### 후속 비용 확인

사용자가 OpenAI Platform에서 **D2 실험 후** 지출 변화를 별도로 확인할 수 있다. 프로젝트 합계와 단일 요청 청구를 혼동하지 않고, 확정할 수 없으면 `UNVERIFIED`로 남긴다. 요청/도구 개수만으로 비용을 역산해 확정하지 않는다.

## 6. 완료 및 변경 통제

- **본 문서 작성 단계:** 기존 사용자 제공 Preview 및 원격 코드·공식 계약의 **읽기 전용** 검토. 추가 API 요청·코드 변경 없음. 2026-11-15 사용자 승인에 따른 **문서 파일 반영만 별도 진행**.
- **테스트 상태:** D2 실행 전 사용자가 보고한 `96 passed`가 최신 실행 증거이며 본 Closeout 작성 중 테스트를 재실행하지 않음.
- **문서 성격:** D2 실행 결과에 대한 **사용자 검토·반영 승인 기록**. D2 정책 또는 Frozen 계약을 새로 승인·동결한 것으로 처리하지 않음.
- **후속 단계 현황:** Gate D3 오프라인 호환성 설계 v0.2의 Final Review PASS 및 사용자 설계 승인 완료. 구현·합성 회귀 테스트, 추가 실호출·실데이터 게시에는 별도 승인 필요.

## 7. 근거

- D2 v0.2 APPROVED: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Gate_D2_Live_Reobservation_Design_v0.2_APPROVED_20261114.md`.
- S1 Gate A/B Limited FROZEN v0.2.2 (2026-11-12): 동일 `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/` 경로.
- 코드: `backend/app/responses_web_search/{normalizer.py,parser.py,d1_live_preview.py,c2_transport.py,types.py}` / HEAD `a43ff67c8eafe177c73fcc7b30b74d2d29a9cfd3`.
- OpenAI 공식 Responses `max_tool_calls`: https://developers.openai.com/api/reference/resources/responses/methods/create
- OpenAI 공식 Web Search 출력·동작: https://developers.openai.com/api/docs/guides/tools-web-search
- OpenAI Python SDK `ResponseFunctionWebSearch` (v3.50.0): https://github.com/openai/openai-python/blob/v3.50.0/src/openai/types/responses/response_function_web_search.py
- 관찰 원자료: 현재 대화에 사용자가 제공한 2026-11-15 D2 Live Preview (raw response 파일이 아닌 안전 필드 집합).
