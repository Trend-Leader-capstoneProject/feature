# Trend Leader — Responses `web_search` Gate C1 설계 최종 검토 v0.1

> **승인 상태:** 2026-11-13 KST 현재 채팅에서 **Gate C1 구현 기준 설계로 승인**. **Gate C 전체 FROZEN 또는 검증 PASS 선언이 아니다.**  
> **작성 범위:** C1 SDK 응답 객체 → 내부 `dict` 변환, 필드 보존, 오프라인 검증 계약.  
> **원격 코드 기준:** `Trend-Leader-capstoneProject/feature`의 `dev` HEAD `434ce7876efca8183cc0fe25009427b8e7708ccb` (2026-11-13 확인). 이후 구현 시 최신 HEAD 재확인 필수.  
> **실험 환경:** 사용자가 별도 가상환경에서 `openai==3.50.0` 확인. 프로젝트 Backend의 `requirements.txt`에는 아직 `openai` 미선언.  
> **변경 통제:** S1 v0.2.2 **Gate A/B 합성 계약만 FROZEN**. Gate C1 실제 SDK 호환성·Gate C/D 전체는 **미검증**. G5/G6 **HOLD**, P4 **NOT FROZEN**, `publish_authorization=NONE`.  
> **본 문서의 승인 범위:** 설계 및 C1의 오프라인 Red/Green 구현 기준에 한함. 실제 유료 `web_search`, 운영 저장·게시, PR·병합, 기존 FROZEN 수정은 별도 승인 대상.

## 1. 문제 정의 및 목표

현재 S0 Parser/Validator와 S1 Normalizer는 제한된 **합성 `dict` 계약**에 따라 작동한다. 반면 OpenAI Python SDK는 `Response` 객체를 반환한다. C1은 이 두 경계의 차이를 연결하되 **검색·메시지·인용 증거를 만들어내거나 숨기지 않고** S1으로 전달해야 한다.

**C1의 성공 조건은 `Response`가 `dict`로 변환되는 데 그치지 않는다.** SDK 수신·직렬화 과정에서 원본에 존재하는 중요한 필드와 누락 여부가 보존되는지 독립된 합성 입력과 비교해야 한다. Normalizer가 허용하지 않는 구조를 변환기가 임의로 수정해 통과시키지 않는다.

### 1.1 포함 범위

- 확인된 `openai==3.50.0`의 공식 객체 직렬화 계약 확인.
- SDK 타입으로 만든 합성 객체 및 `httpx2.MockTransport`를 통한 **네트워크 없는 SDK 수신 경로** 검사.
- `response.status`, 순서 있는 `output`, `web_search_call`, `message`, `reasoning`, `output_text`, `url_citation`의 보존 검증.
- 누락 필드와 명시적 `null`의 차이 검증, 특히 `reasoning.status`.
- 변환 실패 시 성공 형태의 `dict`를 반환하지 않는 제한된 실패 계약.
- 기존 S1 Normalizer → S0 Parser/Validator의 **오프라인** 연계 및 회귀 확인.

### 1.2 제외 범위

- 실제 Responses API 요청·유료 `web_search` 실행 및 실제 검색 응답을 이용한 통과율 판정.
- 라이브 호출 설정·Timeout·재시도(E-08)·실제 CLI/로그·실시간 Preview 오류 매핑(C2 이후).
- Source Matching 알고리즘, 기존 RSS/뉴스 URL 검증 경로 통합, S2 독립 원출처 확인.
- 운영 DB·Redis·Writer, G4/G5/G6·P4, 보호 저장소 및 앱 공개 API.
- 모델이 생성한 정보의 진위·순위·인기도·게시 시각 승인.

## 2. 확정된 상위 설계 방향과 책임

사용자는 기존 Trend와 기사(Source)의 **의미적 Matching을 장기적 기능 목표**로 두고, 공급 전략은 **기존 확보 URL 우선 + 근거가 부족할 때 `web_search` 보강**하는 혼합 방향에 동의했다. 그러나 이는 C1의 구현 범위를 넓히는 결정이 아니다.

| 계층 | 책임 | C1에서 하지 않는 일 |
|---|---|---|
| **C1 변환 Adapter** | SDK 객체 입력·직렬화·구조 보존·제한된 변환 실패 | 검색 성공 판정, URL 보정, 후보 채택 |
| **기존 S1 Normalizer** | 전체 출력 항목 검사, 도구 실행 증거 집계, 허용된 `reasoning`만 투영 | SDK 전송, 실제 기사 확인 |
| **기존 S0 Parser** | 후보 JSON/Annotation 구조 파싱 | SDK 객체 수신 |
| **기존 S0 Validator** | 필수 3필드, URL 형식, `source_url` ↔ `url_citation.url` 원문 직접 일치, 중복 검사 | 후보별 의미적 지지 관계·원출처 사실성 확인 |
| **후속 C2 조정 계층** | 실제 호출 실패·재시도·후속 단계 호출 차단·안전한 Preview 상태 매핑 | 게시 권한 부여 |
| **후속 Gate D** | 별도 승인 하의 실검색 구조·비용·인용 관찰 | 자동 등록·게시 승인 |

### 2.1 처리 흐름

```text
[SDK 3.50.0의 합성 Response 객체 / 모의 HTTP 수신]
             ↓
[C1: 공식 SDK 직렬화 → JSON 호환 dict]
       ├─ 변환 실패: 제한된 내부 실패 → 후속 전달 금지
       └─ 변환 성공: 원본 증거를 보존한 전체 dict
             ↓
[기존 S1 normalize_response()]
       ├─ REJECTED: S0 미호출
       └─ NORMALIZED
             ↓
[기존 S0 parse_response() → validate_candidates()]
             ↓
[비게시 검증 결과]       ╳ 운영 DB / Redis / Writer / 게시
```

**중요:** C1 자체는 Preview를 생성하거나 후속 호출을 조정하지 않는다. C1의 실패로 S0를 호출하지 않는다는 사실은 오프라인 테스트 조정 코드로 검사할 수 있지만, **실제 라이브 조정 계층의 책임·완료**로 주장하지 않는다.

## 3. C1 핵심 불변조건

1. 원본에 **없는 필드는 만들지 않고**, 원본에 **명시적 `null`인 필드는 임의 삭제하지 않는다**. 둘의 의미를 구분한다.
2. `response.status`, `response.output` 전체 개수·순서·항목 타입, 검색 호출의 `action`·`status`, 메시지 `phase`·`content`, 후보 텍스트·인용 URL·offset을 **고치거나 잘라내지 않는다**.
3. `action.sources`에서 `url_citation`을 생성하거나, 검색 호출을 새로 만들거나, 복수 메시지/텍스트를 병합하지 않는다.
4. 변환 실패는 비정상 값을 정상 `dict`로 반환해 숨기지 않는다. 오류 식별자는 안전하고 제한적이어야 하며 원본 본문·API Key·인증 헤더·SDK 예외 원문을 담지 않는다.
5. S0/S1의 합성 FROZEN 경로와 모듈 import 격리를 **변경하지 않는다**.
6. 실제 검색·운영 영속화·게시를 일으킬 수 있는 I/O를 C1에 추가하지 않는다.
7. SDK 타입에서 이미 일어난 변환의 영향을 놓치지 않도록 **독립적으로 작성한 원래의 합성 입력**을 기대값으로 사용한다.

### 3.1 생략과 명시적 `null`의 차이

기존 `normalizer.py`는 `reasoning` 항목에 `status`가 생략되면 허용할 수 있으나, `status`가 명시적으로 존재하며 `completed`가 아니면 거부한다(B-02/B-03).

```json
{"id":"rs_demo","type":"reasoning","summary":[]}
```

위 입력은 `status` 부재를 보존해야 한다. 반면 아래는 명시적 `null`을 보존해야 하며, 현재 S1 Normalizer에 의해 거부된다.

```json
{"id":"rs_demo","type":"reasoning","summary":[],"status":null}
```

전자가 변환 후 후자로 바뀌어 정상 입력이 거부된다면 **C1 Adapter의 필드 보존 계약 위반**으로 분류한다. 외부 SDK의 내부 동작이 원인일 수 있더라도, 입력 경계에 무엇을 허용할지 관리하는 책임은 C1에 있다. 단, 실제 서버 원본에 `null`이 있었다면 허용을 위해 삭제하지 않는다.

## 4. 직렬화 정책과 대안

SDK v3.50.0의 `BaseModel.to_dict()`에는 아래 옵션이 존재한다. **적용 후보**이며, 아직 로컬 실행으로 PASS한 것은 아니다.

```python
response.to_dict(
    mode="json",
    use_api_names=True,
    exclude_unset=True,
    exclude_defaults=False,
    exclude_none=False,
)
```

| 옵션 | 의도 |
|---|---|
| `mode="json"` | JSON 호환 값 출력 |
| `use_api_names=True` | API 응답 필드명 유지 |
| `exclude_unset=True` | SDK 객체에서 설정되지 않은 필드 자동 생성 방지 |
| `exclude_defaults=False` | 명시적인 기본값을 불필요하게 제외하지 않음 |
| `exclude_none=False` | 명시적으로 설정된 `null` 유지 |

| 선택지 | 장점 | 위험 및 결정 |
|---|---|---|
| **A. 공식 `to_dict()` + 독립 증거 비교** | SDK 기능 재사용, 낮은 구현 비용, 기존 S1 재사용 가능 | **우선 권고**. SDK 객체 생성 이전에 달라진 값도 확인 필요 |
| **B. 필드 선택·새 dict 직접 조립** | 입력을 세밀하게 통제 | 도구 호출과 인용 증거의 무음 삭제 위험, 유지보수 부담. C1에서는 비권고 |
| **C. SDK 응답 객체를 우회해 원시 HTTP JSON 파싱** | 원래 응답 구조를 더 직접 관찰 가능 | 별도 네트워크·검증 경계 필요. 현재 C1 범위 제외 |

`Response.output_text`와 같이 텍스트를 모아 주는 편의 속성으로 원본 `output` 전체를 대체하지 않는다. SDK의 현재 타입 소스에 필드가 존재한다는 사실과 **특정 실제 검색 응답에 해당 필드가 반환된다**는 사실도 구별한다.

## 5. 검증 설계에서 발견한 누락·충돌

### 5.1 S0/S1 테스트 격리와 C1 SDK import의 충돌

- `backend/tests/responses_web_search/conftest.py` 및 `backend/tests/responses_web_search_s1/conftest.py`는 `openai`와 `httpx2` import 자체를 금지한다.
- **기존 테스트의 금지 목록을 완화하지 않는다.** C1은 신규 `backend/tests/responses_web_search_c1/` 등 독립 디렉터리를 사용한다.
- `backend/tests/conftest.py`는 로딩 시 DB/dotenv와 `.env.test`를 다루므로, C1 전용 테스트에서 상위 `conftest` 로딩을 차단한다.

```powershell
# backend 디렉터리에서 실행; 실제 C1 디렉터리 생성 후 사용
python -m pytest tests/responses_web_search_c1 --confcutdir=tests/responses_web_search_c1 -v
```

C1의 별도 격리 가드는 SDK/HTTPX2 import와 Mock Transport는 허용하되, 실제 소켓 연결·비밀 설정 읽기·DB/Redis/Writer·영속화·게시를 금지해야 한다. 로컬 의존성 import에 필요한 정상적인 파일 읽기나 테스트의 메모리 동작까지 불필요하게 차단하지 않는다.

### 5.2 기존 F-BASE와 SDK `Response` 타입의 구조 차이

기존 S1의 F-BASE는 **Normalizer용 최소 합성 dict**다. SDK v3.50.0의 `Response`는 `created_at`, `model`, `object`, `parallel_tool_calls`, `tool_choice`, `tools` 등 추가 필수 필드를 선언한다. 기존 F-BASE를 바꾸지 말고 C1 전용 SDK/모의 HTTP Fixture를 작성한다.

### 5.3 SDK 타입 검증과 실제 SDK 수신 경로 차이

SDK v3.50.0의 `_base_client.py`는 기본 응답 처리에서 `construct_type()` 경로를 사용하며, 별도의 엄격한 검증 경로가 존재한다. 따라서 `Response.model_validate()`만 테스트했다고 해서 기본 SDK 수신 경로를 검증했다고 주장하지 않는다. 공식 `httpx2.md`에 안내된 `httpx2.MockTransport`로 `client.responses.create()`를 모의 HTTP 응답에 연결해 **실제 네트워크 없이** 점검한다.

### 5.4 과도한 검증 방지

- 다음 AC **14개의 의도를 보존**하지만, 각각 테스트 파일·함수 1개씩을 요구하지 않는다. 우선 4~7개의 핵심 시나리오와 파라미터화로 충분히 검증한다.
- SDK가 임의 메타데이터를 타입에 맞춰 변환할 수 있으므로 **전체 HTTP JSON과 직렬화 dict의 바이트 단위 일치**를 요구하지 않는다. 검색·메시지·후보 텍스트·인용·누락/null·순서라는 핵심 증거에 집중한다.
- C1에 CLI·로그 렌더러·일반적인 공급원 Provider 추상화·범용 에이전트 프레임워크를 추가하지 않는다.
- 기존 Gate B의 `E-04c/E-06/E-10`은 **현재 연결된 외부 출력·Writer·실제 로그/CLI 경계가 없어 부분 검증 상태**임을 유지한다. C1의 메모리 전용 테스트가 이 항목들을 완료 처리하지 않는다.
- 실제 Network Mock이 가능한 도구 버전은 `openai==3.50.0`에 대응하는 `httpx2` 설치 상태를 구현 시 확인한다. 미확인 실행 결과를 PASS로 작성하지 않는다.

## 6. Gate C1 Acceptance Criteria v0.1 (구현 기준 승인·실행 미검증)

| ID | 수용 기준 | 확인할 증거 |
|---|---|---|
| GC1-01 | 실제 SDK 버전 확인 | 실행 인터프리터의 `openai==3.50.0` |
| GC1-02 | 기본 SDK Response 직렬화 | JSON 호환 dict, 기존 S1에 전달 가능 |
| GC1-03 | 원본 `output` 보존 | 도구·메시지·보조 항목의 순서·개수·유형 유지 |
| GC1-04 | 검색·응답·메시지 상태 보존 | 원래 `status`/`action` 값 유지 |
| GC1-05 | 생략된 선택 필드 보존 | `reasoning.status` 없음 → 변환 결과에도 없음 |
| GC1-06 | 명시적 `null` 보존 | `reasoning.status: null` 그대로 유지, S1에서 정책대로 거부 |
| GC1-07 | 인용 보존 | `url_citation.url`·제목·offset·배열 순서·문자열 보존 |
| GC1-08 | 미지원/초과 항목의 무음 삭제 금지 | 기존 S1의 거부·상한 검사 유지 |
| GC1-09 | 안전한 변환 실패 | 성공 dict로 위장하지 않음, 제한된 오류만 노출 |
| GC1-10 | 객체 불변 | 변환 전후 SDK 객체의 관찰 가능한 자료 변경 없음 |
| GC1-11 | S1/S0 연계 | Frozen 정상/실패 기대값 유지, S0 기존 코드 변경 없음 |
| GC1-12 | 격리·비게시 | 실제 API 호출·DB/Redis/Writer·게시 0, 실제 비밀 미사용 |
| GC1-13 | SDK 오프라인 수신 경로 | 모의 HTTP → 실제 SDK 수신 처리 → dict |
| GC1-14 | 독립 원본 증거 비교 | 모의 HTTP JSON과 결과의 **핵심 증거 필드**를 독립 검증 |

**완료 판정:** 해당 AC의 의미 있는 정상·반례를 테스트하고, 실행 명령·PASS/FAIL·환경을 기록해야 한다. 문서의 승인, 타입 확인, 과거 Gate A/B 테스트의 PASS만으로 GC1을 완료 처리하지 않는다.

### 6.1 우선 반례

| 반례 | 기대값 | 관련 Frozen AC |
|---|---|---|
| 정상 search 1건, assistant 1건, `url_citation`과 후보 URL 일치 | 변환 → S1 NORMALIZED → S0 후보 1건 | A-01/C-01 |
| `reasoning.status` 생략 | 생략 보존, 기존 S1 통과 | B-02 |
| `reasoning.status: null` | null 보존, 기존 S1 거부 | 신규 GC1-06 |
| search 2건 | 2건 모두 보존, S1 `TOOL_CALL_LIMIT_EXCEEDED` | A-04 |
| 복수 assistant 또는 output_text | 병합 없이 S1 거부 | B-04/B-05 |
| `sources`만 있고 인용 없음 | 인용 생성 금지, S0 후보 탈락 | C-03 |
| 비정상 annotation 구조 | SDK 수신 오류와 S0 오류를 구분 | C-05a/b |
| 입력 상한 초과 | 부분 절단 없이 S1 거부 | L-01~L-06 |

## 7. 최소 Red/Green 계획 및 완료 보고

### Slice C1-Red-1 (다음 작업)

1. `dev` 최신 HEAD·테스트 격리·파이썬/SDK 실행 환경 확인.
2. C1 전용 테스트 디렉터리와 안전한 모의 HTTP 입력 구축. 기존 S0/S1 Fixture·코드·`conftest.py` 수정 금지.
3. 최소 직렬화 계약을 대상으로 **정상 1건, 누락/null 구분, 검색 호출 2건 보존, 제한된 변환 실패**의 Red 테스트 구성.
4. 현재 C1 모듈/함수 부재 때문에 실패하는지 확인. SDK 미설치, 잘못된 Fixture, 격리 충돌은 **유효한 Red가 아님**.
5. Red 결과·AC 매핑·실행 명령·변경 파일만 보고. **동일 작업에서 자동으로 Green 진행 금지**.

### Slice C1-Green (후속 별도 범위 승인)

- 공식 직렬화 후보에 기반한 **최소 변환 코드만** 구현한다.
- C1 테스트와 기존 S0/S1의 개별 회귀 테스트, Ruff를 실행·기록한다.
- 실제 SDK 검색 요청, Live CLI, 모델 변경, 저장·게시·Source Matching은 수행하지 않는다.
- 정상 SDK 응답이 기존 Frozen에서 거부되는 경우, 원본 증거·대안·회귀 영향·변경 승인 필요 여부를 먼저 보고한다.

### 별도 관리할 후속 미충족 항목

- C2: 전송/예외/타임아웃, SDK 내부 자동 재시도 0회(E-08), 실제 조정 계층의 비게시 Preview 안전성.
- Gate D: **사용자 별도 승인** 후 유료 `web_search` 실응답과 인용 조합·비용 확인.
- S2: 모델 출력과 분리된 원출처 독립 검증, 기존 Trend 의미적 Matching은 별도 도메인 설계.
- Gate B 잔여 `E-04c/E-06/E-10`: 실제 외부 출력/Writer/CLI 연결 시 해당 경계에서 검증.

## 8. 참고 자료 및 변경 기록

- [Trend Leader AI 개발 지침](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/docs/prompt/Trend_Leader_AI_Development_Guidelines.md)
- [S1 Normalizer Gate A/B 합성 FROZEN v0.2.2](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S1_Normalizer_Acceptance_Criteria_v0.2.2_Gate_AB_FROZEN_20261112.md)
- [S1 Normalizer 구현](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/backend/app/responses_web_search/normalizer.py)
- [SDK 3.50.0 BaseModel.to_dict](https://github.com/openai/openai-python/blob/v3.50.0/src/openai/_models.py)
- [SDK 3.50.0 실제 수신 경로](https://github.com/openai/openai-python/blob/v3.50.0/src/openai/_base_client.py)
- [SDK 3.50.0 MockTransport 가이드](https://github.com/openai/openai-python/blob/v3.50.0/httpx2.md)
- [GitHub 쓰기 안전 정책](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md)

**승인 기록:** 사용자는 2026-11-13 채팅에서 C1 설계의 책임 경계·필드 보존 원칙에 동의하고, C1 Design Final Review의 승인을 명시했다. 이후 한글 재작성·검토·원격 문서 반영을 요청했다. 이는 기존 Frozen 수정이나 실제 API 호출을 승인하는 기록이 아니다.