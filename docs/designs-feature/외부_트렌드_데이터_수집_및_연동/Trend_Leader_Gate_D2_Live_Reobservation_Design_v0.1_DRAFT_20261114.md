# Trend Leader — Responses Web Search Gate D2 실응답 재관찰 설계 검토안 v0.1

> 문서 상태: **DRAFT / NOT FROZEN / NOT AUTHORIZED FOR LIVE EXECUTION**
>
> 작성 기준: 2026-11-14 KST
>
> 기능 브랜치: `feat/responses-web-search-gate-c1`
>
> 원격 기준 HEAD: `3086f366a44fb6032d13ebb4d108fd91a95203c2`
>
> 적용 우선순위: 현재 채팅 결정 → 해당 기능 Frozen → 프로젝트 AI 개발 가이드라인 → 실제 코드
>
> **본 문서는 추가 유료 API 실행, GitHub 쓰기, 기존 Frozen 변경 또는 실데이터 게시를 승인하지 않는다.**

## 0. 한 줄 결정

**KEEP CURRENT POLICY / OBSERVE BEFORE CHANGE / PAID REQUEST HOLD**

기존 D1-B.1의 안전한 `web_search_call_details` 관찰을 재사용한다. S1/S0의 원본 호출 수 1개 제한과 비게시 정책은 유지한다. 신규 실호출은 사전 점검·명시적 별도 승인 후 사용자가 직접 수동으로 **최대 1회** 수행하도록 계획하며, 이번 설계 단계에서는 **0회**이다.

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

- 공식 Responses `max_tool_calls`: 응답 하나에서 **처리 가능한 내장 도구 호출의 최대 횟수**. 초과 시도는 무시될 수 있다.
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

## 2. 목표 / 비목표

### 목표

1. **추가 과금 없이** 기존 코드·합성 Fixture·Frozen AC에서 결론을 도출한다.
2. 다음에 **별도 승인된 단일 실제 요청**이 있을 경우, D1-B.1 필드로 모든 `web_search_call`의 관찰 상태 및 동작 종류를 구분할 수 있도록 준비한다.
3. 동작 상태와 후보 검증 결과를 분리하여, **False Rejection 가능성**과 **Fail-Closed가 필요한 입력**을 구별한다.
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

> 실행일이 달라지면 D0의 최근 7일 날짜 구간도 달라진다. 따라서 D2는 D1 응답의 완전 재현이 아니라 **동일 설정·변하는 날짜/웹 환경 하에서의 재관찰**이다. 모델 결정성도 보장되지 않는다.

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

**관찰 증거의 한계:** `web_search_call_details`는 후보 JSON 유효성, `url_citation` 적합성, 청구 횟수, 원출처 사실성을 알려주지 않는다. `output_type_counts`에서 메시지가 1개라고 하여 그 메시지가 S0를 통과한다는 근거도 없다.

## 5. 오프라인 판단표 (D2-AC, 신규 Frozen 아님)

| ID | 관찰 시나리오 | 유지해야 할 처리 | 의미 / 후속 결정 |
|---|---|---|---|
| D2-01 | 완료 `search` 1개, 다른 도구 항목 없음 | 기존 S1/S0 검증 계속 | 인용/후보 결과는 별도 평가 |
| D2-02 | 완료 `search` 1개 + `incomplete/failed/searching/in_progress` 항목 | 기존 원본 상한 및 실패 보호로 전체 거부 | 미완료 항목을 버려 성공 처리 금지 |
| D2-03 | 완료 `search` + 완료 `open_page` | 현재 전체 거부 | 정상 후속 열기 동작이라면 **실응답 False Rejection 가능성 검토**, 계약 변경 승인 전 수용 금지 |
| D2-04 | 완료 `search` 2개 | 현재 전체 거부 | API 처리·관찰 항목·청구 의미 차이 조사. 상한 변경 미승인 |
| D2-05 | `open_page` 또는 `find_in_page`만 관찰, 완료 `search` 없음 | `SEARCH_NOT_EXECUTED` 또는 기존 구조 거부 | 보조 동작을 `search`로 승격하지 않음 |
| D2-06 | `web_search_call_details=null` / `UNKNOWN` | 후보 수용 판정에 사용 금지 | 관찰 한계로 **INCONCLUSIVE**, 재시도 자동 금지 |
| D2-07 | C1 오류 또는 타임아웃·네트워크 오류 | 기존 상태/미관찰 유지 | 요청 처리 유무 불명; 자동 재호출 금지 |
| D2-08 | `PREVIEW_READY` 후보가 존재 | 여전히 비게시·검토 필요 | 독립 출처 검증 및 P4 승인 전 서비스 공급 금지 |
| D2-09 | S1 `TOOL_CALL_LIMIT_EXCEEDED` | `parser_input=None`, S0/Validator 미호출 | 결과 메시지·인용 적합성을 이미 검증했다고 표기 금지 |

**검사 우선순위:** 모델 일치 및 응답 구조 → 항목 전체 상태/유형 관찰 → 기존 S1 상한/실패 차단 → S0 후보/인용 (S1 정상이면) → 별도 출처 검증 및 운영 승인. 거부된 구조를 통과시키려고 임의 삭제·순서 재배치하지 않는다.

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

- 사용자가 직접 기존 대화형 D1 CLI를 실행하고 최대 1회 응답을 받음.
- `stdout` 파이프/리다이렉션을 사용하지 않음(TTY 요구).
- 응답이 느리거나 예외·취소·`UNKNOWN`이 발생해도 즉시 **STOP**, 재시도는 별도 승인.
- 결과를 공유할 때는 안전한 구조 정보 중심으로 전달. `candidates`의 출처 URL에는 인증 쿼리 등이 포함될 수 있으므로 원문을 무조건 복사·장기 보관하지 않음.
- 실행 전후 Usage 대시보드 확인은 요금 검증 참고 자료이며 요청별 정확한 청구 분리 여부를 확인하고 근거 수준을 기록.

## 7. D2 결과 분류 및 의사결정

- **OBSERVED_ONE_COMPLETED_SEARCH:** 도구 항목 1개이며 완료 `search`. 결과 상태와 인용 검증을 별도 판단. 이는 D2 구조 관찰 달성이지 게시 승인이 아님.
- **OBSERVED_MULTI_COMPLETED_WITH_AUXILIARY:** 완료 `search` 뒤 완료 `open_page/find_in_page` 등 존재. 정책 완화 가능성만 제기. Frozen 변경 제안과 회귀 영향 정리 필요.
- **OBSERVED_MULTI_SEARCH:** 완료 `search` 2개 이상. 처리/청구 의미 추론 금지. 현재 전체 거부.
- **OBSERVED_FAILURE_OR_INCOMPLETE:** 미완료/실패 항목 존재. Fail-Closed 유지.
- **OBSERVATION_INCONCLUSIVE:** 구조 손상, `UNKNOWN`, 수신 실패 등. 다시 유료 호출한다는 결론으로 직행하지 않음.
- **CANDIDATE_READY_FOR_REVIEW:** S1/S0 구조·인용 기준을 통과한 검토 후보 존재. 원출처 독립 검증 전 비게시·미승인.

실행되더라도 **응답 1건으로 모델의 일반적 동작 확률이나 비용 분포를 추정하지 않는다.** 단일 사례 관찰을 결정 근거로 남기되, 범용 정책 변경은 충분한 반례와 사용자 승인 후 진행한다.

## 8. 의존성과 통합 경계

- **AWS B-2:** CI/CD Migration Guard, 격리 DB/Linux 통합 검증은 별도 채팅·브랜치에서 수행.
- **P4/G5/G6:** 독립 출처 검증, 보호 등록, 운영 승인, Writer/게시 연결은 후속 Gate. Responses Preview `PREVIEW_READY`도 이를 우회하지 못함.
- 기능 브랜치는 현재 `dev`와 분기되어 있으므로 PR/병합 전 최신 HEAD, 파일 목록, Frozen·공통 의존성 확인. 이번 문서에서 PR/병합 수행하지 않음.

## 9. 승인 게이트 및 완료 조건

**D2 설계 검토 완료 조건 (이번 작업):**

- [x] 첫 실응답 관찰/미관찰 사항 분리
- [x] 공식 `max_tool_calls` 의미와 현재 S1/S0 항목 수 정책 비교
- [x] Frozen 영향 항목 A-04/P-06/X-01/X-06 및 S0 순서 의존 위험 확인
- [x] 무과금 재관찰 설계/관찰 필드/중단 기준 작성
- [x] 비게시·P4 운영 HOLD·외부 API 호출 미승인 유지
- [ ] **사용자 설계 승인 및 FROZEN 결정 (별도)**
- [ ] **실행 비용·횟수 명시적 승인 (별도)**
- [ ] 실제 D2 재관찰 실행 (미실행)
- [ ] 결과에 기반한 S1/S0 변경 승인 여부 판정 (미확정)

**현 상태:** 설계 초안 작성 완료 / 코드 변경 없음 / 테스트 재실행 없음 / GitHub 쓰기 없음 / 유료 API 요청 0회.

## 10. 참고 근거

1. 프로젝트 기준: `Trend_Leader_AI_Development_Guidelines.md`, `Trend_Leader_GitHub_Write_Safety_Policy.md`.
2. Frozen: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S1_Normalizer_Acceptance_Criteria_v0.2.2_Gate_AB_FROZEN_20261112.md`.
3. 기능 브랜치 코드: https://github.com/Trend-Leader-capstoneProject/feature/tree/3086f366a44fb6032d13ebb4d108fd91a95203c2/backend/app/responses_web_search
4. OpenAI Responses create `max_tool_calls`: https://developers.openai.com/api/reference/resources/responses/methods/create
5. OpenAI Web Search output structure: https://developers.openai.com/api/docs/guides/tools-web-search
6. OpenAI API Pricing: https://developers.openai.com/api/docs/pricing
7. 사용자 제공 2026-11-14 첫 실제 Live Preview 및 D1-B.1 테스트 `96 passed` 보고.

---

> **변경 통제:** 본 DRAFT의 승인 여부와 Live 승인 여부는 별개다. 동결된 Gate A/B AC는 사용자 별도 승인 없이 수정하지 않는다.
