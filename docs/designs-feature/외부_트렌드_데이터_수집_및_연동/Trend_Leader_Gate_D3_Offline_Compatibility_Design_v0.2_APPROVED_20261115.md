# Trend Leader — Responses Web Search Gate D3 오프라인 실응답 호환성 설계 검토안 v0.2

> **문서 상태:** **FINAL REVIEW PASS (설계 문서 한정) / USER DESIGN APPROVED / NOT FROZEN / NOT AUTHORIZED FOR CODE OR LIVE EXECUTION**
> **작성 기준:** 2026-11-15 KST  
> **대상 브랜치:** `feat/responses-web-search-gate-c1`  
> **검토 기준 원격 HEAD:** `a43ff67c8eafe177c73fcc7b30b74d2d29a9cfd3` (2026-11-15 읽기 전용 확인, 새로운 코드 변경 확인 없음)
> **선행:** D2 v0.2 설계 APPROVED, D2 재관찰 결과 `SUFFICIENT / REJECTED / NOT_EVALUATED`, S1 Gate A/B 합성 FROZEN v0.2.2.  
> **사용자 승인 기록:** 2026-11-15 KST D3 v0.2 설계 승인 및 D2 Closeout·D3 v0.2 문서 기능 브랜치 반영 승인. D3 FROZEN, 코드·테스트 구현, 추가 유료 API 요청, 게시 권한은 승인 범위 밖이다.  
> **변경 통제:** `Trend_Leader_AI_Development_Guidelines.md` 및 `Trend_Leader_GitHub_Write_Safety_Policy.md` 준수. 이 문서는 기존 정책 **유지 권고의 설계 리뷰 결과**이며, 사용자 승인에 따라 **본 문서 2건의 GitHub 반영만 허용**된다. S0/S1/C2 코드, Frozen AC, 새로운 유료 호출, 추가 GitHub 쓰기 또는 서비스 게시의 승인은 아니다. v0.1은 변경 이력으로 보존한다.

## 0. 이번 D3에서 해결할 질문

**최상위 `response.status=completed`인데 `web_search_call.status=searching` 항목이 존재하는 실응답을, 현재의 증거 보존·Fail-Closed·단일 호출 계약하에서 어떻게 해석하고 어떤 정책 변경을 검토할 것인가?**

현재 추천: **`KEEP FAIL-CLOSED / NO POLICY OR CODE CHANGE / DOCUMENT INCOMPLETE TOOL ITEM / NO PAID RETRY`**.

검색 도구 호출 수만 완화하는 작업, `searching`을 완료로 승격하는 작업, 다른 항목을 누락하는 작업은 모두 이번 범위에서 제외한다.

## 1. 문제 정의와 증거 수준

### 1.1 재관찰된 상태 — D2

```text
Responses 최상위 상태: completed
원본 출력 유형 개수: reasoning=4, web_search_call=2, message=1
web_search_call[output_index=1]: status=completed, action.type=search
web_search_call[output_index=3]: status=searching, action.type=search
search_execution: CONFIRMED
S1: INVALID_OR_INCOMPLETE_RESPONSE / TOOL_CALL_LIMIT_EXCEEDED
S0 Parser / Validator: 미호출
후보: [] (미평가)
```

이 데이터는 사용자가 공유한 **D1 안전 진단 Preview**이다. 검색어·원본 message·citation payload·응답 ID를 포함하지 않으며, 서버 raw 응답/청구 원장의 독립 검증을 의미하지 않는다.

### 1.2 확인된 코드 동작

- `c2_transport.py`: `tool_choice="required"`, `tools=[{"type":"web_search"}]`, `max_tool_calls=1`, `max_retries=0`, `store=False`, `stream=False`.
- `d1_live_preview.py`: SDK 응답을 받은 뒤 C1보다 먼저 안전한 호출별 필드를 관찰. `searching`은 허용된 상태 문자열이며 `UNKNOWN`으로 숨기지 않는다.
- `normalizer.py`: 전체 응답 완료·목록 구조 검사 → **원본 Web Search 항목 개수 상한 검사** → 각 도구의 `status=completed` 검사 → 기타 구조 검사/투영.
- `parser.py`와 `types.py`: S0 합성 계약에서도 `max_tool_calls=1`이 고정. 복수 호출 허용 시 `searched = action["type"] == "search"` 반복 대입의 순서 의존 위험이 존재한다(현재 계약에서 미발현).
- Frozen A-04/P-06/X-01/X-06: 복수 호출의 무음 삭제·1개로 투영·성공 처리 금지.

### 1.3 공식 문서가 확인하는 범위

- Responses `max_tool_calls`는 **응답에서 처리할 수 있는 내장 도구 호출 횟수의 총 상한**이며, 추가 호출 시도는 무시된다고 문서화되어 있다. 이는 `response.output`의 `web_search_call` 객체 개수가 반드시 상한 이하라는 보장은 아니다.
- Web Search의 `action.type`은 `search`, `open_page`, `find_in_page`이다.
- OpenAI Python SDK 3.50.0의 `ResponseFunctionWebSearch.status`는 `in_progress`, `searching`, `completed`, `failed`, `incomplete`를 허용한다.
- **미확정:** 최상위 완료 상태와 개별 `searching` 공존의 서버 내부 원인, 해당 항목이 처리/청구됐는지, 이 응답만으로 메시지·인용이 유효한지.

> **원인 가설 (증거가 아님):** (H1) 처리 상한 이후의 추가 시도가 output에 잔존, (H2) 서버 응답 조립 시 중간 상태 항목 잔존, (H3) SDK 객체와 실제 API 응답 간 표현 차이. 현재 안전 진단만으로 H1~H3을 식별할 수 없다. 이 가설을 바탕으로 런타임 성공 규칙을 만들지 않는다.

## 2. 목표·비목표·책임 경계

### 목표

1. D2 결과를 **실제 관찰 / 코드로 확정 / 공식 문서 / 가설**로 나누어 설명한다.
2. S1/S0를 변경하지 않은 상태에서 **기존 거부의 안전성**과 **향후 실응답 호환성 검토 필요성**을 각각 판정한다.
3. 무과금 합성 반례와 기존 테스트 커버리지를 대조하고, 후속 승인 필요 여부를 판단한다.
4. 향후 제품 공급 후보를 정상 수용하려면 어떤 추가 근거와 변경 범위가 필요한지 문서화한다.

### 비목표

- 추가 API 호출, 재시도, 서버 raw 응답 또는 비밀정보 수집·저장
- D2 승인된 단일 요청의 반복 실행 또는 비용 허용액 잔액 활용
- `max_tool_calls`, `SearchRunConfig`, Frozen AC, Preview 필드 임의 변경
- `searching → completed` 변환, 도구 항목 무음 삭제, 결과 일부만 선택해 Parser에 제출
- 원본 후보·인용을 확인하지 않은 상태에서 **False Rejection 확정** 또는 후보 복원 주장
- DB/Redis/Writer/P4/G5/G6/AWS 배포, 실제 게시·승인

### 책임 경계

| 구성 요소 | 현재 책임 | D3에서 변경 가능 여부 |
|---|---|---|
| C2 | API 요청·timeout·재시도 0, 원본 SDK Response 반환 | 변경하지 않음 |
| D1 | 별도 승인 확인, 안전한 관찰·비게시 Preview | 변경하지 않음 |
| C1 | SDK 객체의 의미 보존 변환 | 변경하지 않음 |
| S1 | 원본 검증·완료/호출 증거 집계·안전한 S0 투영 | 변경하지 않음 |
| S0 | 합성 응답 JSON·인용·후보 제한 검사 | 변경하지 않음 |
| D3 문서 | 관찰값 해석·대안·반례·승인 조건 | 이번 작업 범위 |

## 3. 핵심 설계 긴장과 트레이드오프

### 문제 1 — `completed`는 어떤 완료인가?

최상위 `response.status=completed`와 도구별 `status=searching`은 서로 다른 값이다. 현재 S1은 응답 전체 및 관련 도구 항목이 모두 완료되기를 요구한다. **최상위 완료를 개별 도구 항목의 완료로 승격하지 않는다.**

### 문제 2 — 처리 상한과 기록 상한을 하나로 볼 수 있는가?

공식 API 처리 상한은 원본 출력 항목의 개수와 동일하다고 보장되지 않는다. 프로젝트 S1/S0는 지금까지 1개 원본 항목만 수용하는 **독자적인 합성 안전 정책**을 가지고 있다. 현재의 거부는 계약대로이지만, 이것만으로 정상 후보에 대한 False Rejection이라고 확정할 수 없다.

### 문제 3 — 미완료 도구 항목을 어떻게 보존할 것인가?

`searching`이 단순 노이즈라고 가정해 삭제하면 X-01/X-06 및 증거 보존 계약에 충돌한다. 수용 정책을 변경하려면 원본과 투영의 관계, 완료 검색 1개가 후보 텍스트/인용을 충분히 뒷받침하는지, 미완료 항목이 실질적으로 무엇을 뜻하는지의 증거가 필요하다.

## 4. 대안 비교

| 대안 | 개념 | 장점 | 핵심 위험·비용 | D3 권고 |
|---|---|---|---|---|
| **A. 현행 Fail-Closed 유지** | 원본 항목 2개면 S1 거부. 미완료를 성공으로 승격하지 않음 | 코드/Frozen 변경 없음, 증거 무결성 유지 | 현재 실응답 후보 공급 계속 0건일 수 있음 | **채택 권고 (현 단계)** |
| **B. 진단·결정 기록만 확장** | D2 결과와 원인 가설을 기록하되 런타임 수용 조건은 보존 | 무과금, 관찰 근거 축적 | 실제 후보 공급 문제를 즉시 해결하지 못함 | **A의 보완책으로 진행** |
| **C. 별도 Live 수용 프로필 설계** | 미완료·복수 항목을 구별하는 새로운 정책 및 투영 경계 검토 | 특정 정상 응답의 잘못된 거부를 줄일 가능성 | S1/S0/Frozen/테스트/보안·인용 계약 변경 필요, 미완료 무시 위험 | **현 단계 보류** |
| **D. 요청 정책·모델 변경 실험** | 출력 패턴을 바꾸도록 모델·도구/프롬프트 설정 변경 | 미완료 항목 재발을 줄일 수도 있음 | 신규 요금·재현성·지원 버전·설계 변경 심사 필요, 효과 미확정 | **현 단계 보류** |

**주의:** C와 D는 구현 제안 또는 승인된 해결책이 아니다. 기존 실험 2건만으로 어느 대안이 실제 후보 유효성을 향상하는지 판단할 수 없다.

## 5. 오프라인 반례 및 검증 조건 (D3-AC 초안)

D3-AC는 **문서·합성 Fixture 검토 기준**이며 S1 Gate A/B Frozen AC가 아니다. 기존 테스트에서 이미 검증한 사례는 우선 재사용하고, 명시적 구현 승인 없이 새 테스트/코드를 작성하지 않는다.

| ID | 합성 반례 또는 증거 | 현행 예상 처리 | 필요한 검증/보존 조건 |
|---|---|---|---|
| D3-01 | `completed/search` 1개 + `searching/search` 1개 + 유효해 보이는 메시지 | **코드 기반 예상:** `TOOL_CALL_LIMIT_EXCEEDED`, S0 미호출 | S1 호출 수 검사 우선순위·`completed_search_actions=1`·후보 미평가·비게시를 검증할 것. **정확한 두 상태의 조합을 통과한 테스트는 아직 확인하지 못했으며**, 이번 D2 실응답은 해당 단위 테스트를 대신하지 않음 |
| D3-02 | 위 사례에서 호출 수 상한만 2로 넓혔다고 **가정** | 도구 `searching` 때문에 이후 상태 검사 거부 | 정적 경로 분석으로만 제시. 실제 Frozen/설정 변경 수행 금지 |
| D3-03 | `completed/search` 2개 | `TOOL_CALL_LIMIT_EXCEEDED` | 과금/처리 2회로 승격 금지, A-04/P-06/X-01 보존 |
| D3-04 | `completed/search` + `completed/open_page` | `TOOL_CALL_LIMIT_EXCEEDED` | 호환성 우려이지 후보 False Rejection 증명은 아님 |
| D3-05 | `completed/search` 1개 | 조건부 S1 정상화 → S0 검증 | S0 통과·인용 일치·원출처 사실 검증은 별개의 조건 |
| D3-06 | `searching/search`만 1개 | S1 구조 거부 | 최상위 completed를 도구 완료로 오인하지 않음 |
| D3-07 | `failed/search`만 1개 | S1 구조 거부 | 상태 변환·삭제 금지 |
| D3-08 | 완료 검색 + 미지원 output 타입 | **S1에 정상 dict가 전달되고 C1이 성공했다면:** 미지원 출력 유형으로 S1 구조 거부. **실 SDK 경로에서는:** C1 변환이 먼저 실패할 수도 있음 | 합성 S1 거부와 실제 SDK→C1 선행 실패 가능성을 분리하고, 실제 확인되지 않은 경로의 `reason_codes`를 단정하지 않음 |
| D3-09 | 두 호출 중 `searching` 하나를 임의 삭제한 1개짜리 투영 | 원본 기준으로는 **허용 금지** | Frozen X-06: 변조 투영 결과로만 PASS 판단 금지 |
| D3-10 | 응답 미수신·구조 파손 / `web_search_call_details=null` | A축 관찰 `INCONCLUSIVE` | `0`과 `UNKNOWN` 구분, 재호출 금지 |
| D3-11 | 원본 메시지·인용 미확인 상태 | 후보·인용 유효성 미평가 | `candidates=[]`를 정당한 빈 결과로 표기하지 않음 |
| D3-12 | `response.status=completed`와 `web_search_call.status=searching` 공존 | 각 상태의 의미를 별도 기록 | SDK enum 허용 사실과 서버 내부 처리 원인을 혼동하지 않음 |

### 기존 테스트 근거

- `backend/tests/responses_web_search_s1/test_gate_a.py`: A-04 복수 호출, A-05 명시적 `failed`, X-06 원본 항목 은닉 위험, A-03/A-09 보조 동작만 존재하는 사례.
- `backend/tests/responses_web_search_c2/test_d1_live_boundary_red.py`: D1-B.1의 `completed/search + incomplete/search`, `completed/search + completed/search`, `completed/search + completed/open_page`, **단독 `searching/search`** 등을 합성 경로로 검증. C1 실패에서도 안전한 진단값 유지, 비밀정보 비노출 검증. **실제 D2의 `completed/search + searching/search` 정확한 조합은 기존 파라미터 목록에서 확인되지 않음**.
- `backend/tests/responses_web_search_s1/test_gate_a.py`: A-04 및 X-06은 **복수 완료 검색**의 상한·은닉 방지 예시이며, `searching` 혼합의 직접 검증이라고 주장하지 않음.
- 사용자 보고 2026-11-15 D1 테스트 **96 passed**. 이는 기존 suite 실행 결과이며 **D3-01 신규 조합의 테스트 통과 근거도, 이번 설계 리뷰의 재실행 결과도 아님**.

**후속 Codex 테스트 인계 후보 (별도 구현·테스트 승인 후):** D3-01의 `completed/search` + `searching/search` 두 호출, 구조상 정상 후보 메시지/인용을 가진 **합성 Fixture**를 구성한다. 현재 S1 정책 그대로 `TOOL_CALL_LIMIT_EXCEEDED`, `completed_search_actions=1`, 호출별 진단 보존, S0/Validator 미호출, `response_validation=INVALID`, 후보 `[]`, 비게시를 확인한다. 이 테스트는 새로운 수용 정책을 만드는 것이 아니라 기존 정책의 실제 관찰 패턴 회귀를 보강한다. **이번 설계 단계에서는 테스트 파일을 작성·실행하지 않는다.**

## 6. 변경 영향 및 거부/승인 경계

### 당장 변경하지 않을 것

- `S1_SYNTHETIC`의 `A-04/P-06/X-01/X-06`, 원본 호출 상한 1, `S0 SearchRunConfig.max_tool_calls=1`.
- `C2 max_tool_calls=1`, 재시도 0, 실험 승인 범위/비게시/원문 비노출.
- `url_citation` 직접 URL 일치 기준. `sources`를 인용으로 복원·대체하는 행위.
- 서비스 DB에 `HIDDEN` 형태로도 미승인 후보 저장 금지, P4/G5/G6 HOLD.

### 향후 C안(별도 Live 수용 프로필)을 열려면 필요한 증거

1. 정상 원본 후보/인용과 추가 `searching` 항목의 연관성을 안전하게 검증할 방법; 현재 D1 안전 진단만으로 **불충분**.
2. 공식 API/SDK에서 상한 이후 상태 및 output 보존에 대한 명시적 보증 또는 충분한 독립 증거. 없는 경우 `UNVERIFIED`로 유지.
3. 원본 증거를 버리지 않는 새로운 S1→S0 데이터 계약 및 실패·정합성 평가 방법.
4. S0 반복 대입·상한 제약·인용 검증 로직의 변경 영향 분석, Red/Green 테스트, C2/D1 회귀 및 SDK 호환성 증명.
5. Frozen AC 변경 제안서(원본 AC, 새 기대, 근거, 회귀, 하위 호환)와 사용자 **별도 명시 승인**.
6. 지출·저장·소스 권한·독립 원출처 검증·게시 안전 경계 보존.

**보수적 대안:** 현재 계약 아래에서 허용되는 단일 완료 `search` 응답만 정상 후보 검증 경로로 인정한다. 이 선택이 MVP 공급량을 충분히 달성하는지는 아직 데이터가 없어 평가 불가.

## 7. D3 설계 완료 조건 및 판정안

**설계 분석의 종료와 제품 후보 공급의 완료는 서로 독립된 게이트다.** D3의 `PASS`는 기존 정책 유지 판단과 후속 검증 범위의 문서화에 한정하며, S1 Live 호환성·실데이터 공급·운영 승인을 의미하지 않는다.

| 항목 | 판정 | 설명 및 다음 책임 |
|---|---|---|
| D2 결과의 A/B/C 분리 | **설계 검토 PASS** | `SUFFICIENT / REJECTED / NOT_EVALUATED` 기록과 일치 |
| 최상위/개별 상태 구분 | **설계 검토 PASS** | `completed`와 `searching`은 서로 다른 관찰 상태 |
| 공식 `max_tool_calls`와 출력 항목 수 구분 | **설계 검토 PASS** | 처리 상한을 반환 item 수·청구 횟수로 치환하지 않음 |
| 현행 S1 거부 경로 | **정적 코드 확인** | 호출 수 검사 우선; 상한을 가정상 늘려도 `searching` 거부. **상한 변경 실행은 미실시** |
| D3-01 정확한 혼합 상태 합성 회귀 | **미검증 / 후속 Codex 검토 후보** | `completed/search + searching/search` 테스트 존재·통과를 주장하지 않음; 별도 테스트 범위 승인 필요 |
| D3-08 거부 계층 | **구분 완료** | S1 합성 입력과 실제 SDK→C1 변환 실패 가능성 구분 |
| 보안·비게시·비밀정보 보호 | **유지** | Frozen·S0·C2·D1 코드 변경 없음 |
| 후보 False Rejection 및 원본 인용 유효성 | **미확정** | 메시지/인용 미검증, S1 선행 거부 |
| 서버 내부 원인·과금 횟수 | **미확정** | 안전 Preview만으로 증명 불가 |
| MVP-A 실데이터 후보 공급 | **미완료 / 별도 제품 결정 필요** | D3 문서 검토 성공과 무관. 승인된 다른 공급 경로 또는 신규 Live 호환성 계약의 별도 설계 판단 |
| D3 v0.2 사용자 설계 승인 및 Frozen | **설계 승인 / NOT FROZEN** | 2026-11-15 사용자 설계 승인 완료. 동결·코드 구현·실호출·운영 승인은 별도 |
| S1/S0/C2 정책 변경·코드·새 API 요청 | **HOLD** | D2 유료 단일 승인 소진, 신규 승인 전 실행 금지 |

**D3 v0.2 Final Review 판정:** `OFFLINE DESIGN REVIEW PASS / KEEP CURRENT FAIL-CLOSED / NO CODE CHANGE JUSTIFIED / PRODUCT CANDIDATE PATH NOT COMPLETE / LIVE HOLD`.

**D3 설계 완료 조건:** (1) D2 관찰과 코드·공식 문서·가설을 분리, (2) 현행 거부 순서·Frozen 영향 확인, (3) 반례와 기존 테스트의 직접 커버 여부 분리, (4) 대안 보류 근거 및 후속 구현·테스트 인계 조건 정리. 이 네 조건은 **설계 문서 평가의 범위**이며, 실제 후보 수용·원출처 검증·게시·S1 Live 호환성 검증을 포함하지 않는다.

**후속 제품 의사결정 트리거:** 기존 정책에서 정상 후보 공급이 계속 차단된다면, 사용자와 별도 채팅에서 (A) **승인된 다른 데이터 공급 경로**의 현재 가용성·제품 목표 충족 여부와 (B) **새 Live 수용 프로필**의 증거 확보 방법·Frozen 변경 위험을 비교한다. 재실험이나 API/모델 변경은 자동으로 뒤따르지 않으며, D3에서 AWS/P4/RSS 범위를 무단 변경하지 않는다.

## 8. 이 채팅의 독립 설계 리뷰 체크리스트와 Codex 인계 경계

**역할 분리:** ChatGPT는 이 채팅에서 설계·근거·대안·반례·Final Review를 검토한다. **사용자**는 정책 선택·설계 승인·변경 범위를 결정한다. **Codex는 승인된 범위의 구현 및 테스트만 수행**한다. 기존에 생성한 `Trend_Leader_Gate_D3_Codex_Offline_Review_Prompt_v0.1_20261115.md`는 작업 이력으로 보존하지만 **이번 설계 리뷰의 실행 프롬프트로 사용하지 않는다**.

| 독립 리뷰 질문 | 이 채팅의 검토 결과 |
|---|---|
| `searching` 상태를 보존하면서 현행 거부 순서·`search_execution=CONFIRMED`를 왜곡하지 않았는가? | **PASS** — 완료 `search` 1개를 근거로 확인, 미완료 항목은 성공으로 승격하지 않음 |
| D3-01~D3-12의 예상 결과가 S1/S0/D1 코드·테스트와 일치하는가? | **PASS with limitation** — 기존 테스트는 유사 사례를 포함하나 D3-01 정확한 혼합 조합은 미검증. D3-08은 S1 vs C1 계층 분리 |
| 공식 처리 상한과 출력 항목 수·청구 횟수를 구분했는가? | **PASS** — 공식 설명과 실제 진단의 근거 수준 분리 |
| C안의 Frozen·S0 영향 및 원본 보존 요구를 식별했는가? | **PASS** — §6의 별도 승인 요건 유지, 원본 은닉 우회 금지 |
| 신규 안전 진단 구현이 당장 필요한가? | **현재는 불필요** — D1-B.1 관찰 충분. 정확한 혼합 상태 합성 회귀는 별도 Codex 테스트 후보 |

**Codex 인계 조건:** 사용자가 후속 테스트를 명시 승인하는 경우에만 D3-01의 **Mock·합성 Fixture 전용 회귀 검사**를 구현·실행 범위로 넘긴다. 제품 코드·Frozen·설정·실 API 호출 변경은 이 인계에 포함되지 않으며, 변경 전 승인된 범위·기준 HEAD를 다시 확인한다.

## 9. 참고 근거

1. D2 관찰 Closeout v0.1 (2026-11-15) — 현재 채팅 사용자가 제공한 안전 Preview.
2. D2 v0.2 APPROVED 및 S1 Gate A/B FROZEN v0.2.2 — 해당 설계 MD.
3. 구현 및 테스트 (검토 HEAD `a43ff67c8eafe177c73fcc7b30b74d2d29a9cfd3`): `backend/app/responses_web_search/`, `backend/tests/responses_web_search_s1/`, `backend/tests/responses_web_search_c2/`.
4. OpenAI Responses `max_tool_calls`: https://developers.openai.com/api/reference/resources/responses/methods/create
5. OpenAI Web Search action/output: https://developers.openai.com/api/docs/guides/tools-web-search
6. OpenAI Python SDK 3.50.0 `ResponseFunctionWebSearch`: https://github.com/openai/openai-python/blob/v3.50.0/src/openai/types/responses/response_function_web_search.py

---

### v0.1 → v0.2 변경 이력

- **P0:** §8 Codex 독립 설계 리뷰 지시를 이 채팅의 독립 설계 검토와 후속 Codex 구현·테스트 인계 경계로 교체.
- **P1:** D3-01 정확한 `completed/search + searching/search` 조합은 기존 테스트 미확인으로 명시; 사용자 보고 `96 passed`와 구분.
- **P1:** D3-08의 S1 합성 구조 거부와 실제 SDK→C1 선행 변환 실패 가능성을 분리.
- **P1:** §7 D3 설계 분석 완료, 정확한 합성 회귀, 실제 제품 후보 공급, 추가 유료 승인 네 게이트 분리.
- **불변:** A+B 권고, C/D 보류, D3-AC 12개, S0/S1/C2/Frozen 코드·설정 및 모든 비게시/비밀정보 보호 정책.

---

> **변경 통제:** 이 채팅의 Final Review PASS와 사용자의 설계 승인, Frozen 정책 변경, 새 코드·테스트 승인, 새로운 유료 호출 승인, 운영 게시 승인은 **각각 별개의 결정**이다. 어느 단계에서도 D2 재실험을 자동 재수행하지 않는다.
