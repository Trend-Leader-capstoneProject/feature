# Trend Leader — Responses `web_search` Gate C1 Red Phase Slice 1 구현 채팅 시작 프롬프트

> **문서 목적:** 승인된 `Gate C1 Design Final Review v0.1`을 기준으로 **Red 테스트만** 작성·검증하기 위한 작업 지시.  
> **상태:** 구현 착수용 프롬프트. **테스트 완료·Green 구현·실검색 승인을 뜻하지 않음.**  
> **기준:** `openai==3.50.0`, S1 v0.2.2 Gate A/B 합성 계약 FROZEN, G5/G6 HOLD, P4 NOT FROZEN, `publish_authorization=NONE`.

## 1. 이번 채팅의 목표와 권한

Trend Leader의 다음 작업은 **Gate C1 SDK 응답 객체 → `dict` 변환의 Red Phase Slice 1**입니다. C1의 승인된 설계 문서를 최우선 기능 기준으로 삼고, 기존 S0 Parser/Validator·S1 Normalizer·합성 서비스의 책임은 변경하지 마세요.

**이번 Slice의 허용 범위는 C1의 오프라인 Red 테스트 작성과 실행 및 결과 보고까지입니다.** Green 구현, 실제 유료 API 호출, DB·Redis·Writer, 앱 공개 API, 기존 Frozen 수정은 포함하지 않습니다. 새 코드 파일을 쓰거나 커밋·푸시·PR을 수행하기 전에는 **현재 구현 채팅에서 허용된 GitHub 쓰기 범위**를 확인하세요. 이 문서를 기능 브랜치에 저장해 둔 사실만으로 Red/Green 코드 변경·커밋 승인이 발생하지는 않습니다.

## 2. 시작 전 읽기 전용 점검

1. 현재 브랜치·HEAD·working tree와 worktree 사용 여부를 확인하고, 사용자 또는 다른 도구의 미커밋 변경을 보존하세요.
2. 원격 `dev`의 최신 HEAD와 구현 브랜치를 비교하세요. 현재 브랜치가 승인된 문서·구현 공용 브랜치인지 확인하세요.
3. 다음 자료를 직접 확인하세요.
   - `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_Gate_C1_Design_Final_Review_v0.1_APPROVED_20261113.md`
   - `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Responses_Web_Search_S1_Normalizer_Acceptance_Criteria_v0.2.2_Gate_AB_FROZEN_20261112.md`
   - `backend/app/responses_web_search/{normalizer,parser,validator,s1_service,types}.py`
   - `backend/tests/responses_web_search/conftest.py`, `backend/tests/responses_web_search_s1/conftest.py`, `backend/tests/conftest.py`
   - `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pyproject.toml`
   - SDK `openai-python`의 공식 `v3.50.0` 소스 및 `httpx2.md`.
4. 실제 사용할 Python 인터프리터와 `openai==3.50.0`, `httpx2` 설치 버전을 확인하세요. 별도 실험 가상환경과 Backend 환경이 같다고 가정하지 마세요.
5. 충돌·의존성 미설치·권한 불명확 시 기존 파일을 덮어쓰거나 범위를 확대하지 말고 해당 이유와 최소 해결안을 먼저 보고하세요.

## 3. 테스트 격리 원칙

기존 S0/S1 테스트 디렉터리에서는 `openai`와 `httpx2` import가 금지되어 있습니다. **기존 `conftest.py`의 금지 목록을 완화하지 마세요.** C1 전용 디렉터리(권고: `backend/tests/responses_web_search_c1/`)를 사용하세요.

`backend/tests/conftest.py`는 SQLAlchemy/dotenv 및 `.env.test`를 처리하므로, C1 독립 실행 시 상위 설정 파일을 불러오지 않도록 `--confcutdir`를 적용하세요.

```powershell
# backend 디렉터리에서 실행
python -m pytest tests/responses_web_search_c1 --confcutdir=tests/responses_web_search_c1 -v
```

- C1 테스트에서는 `openai`, `httpx2`의 정상 import와 Mock HTTP 처리를 허용합니다.
- 실제 소켓·DNS·DB·Redis·Writer·게시·비밀 파일 읽기와 외부 HTTP 요청은 차단합니다.
- 사용자 API Key를 읽지 않습니다. 필요하면 `test-only-key`처럼 무효한 테스트 문자열을 SDK 객체에 직접 주입합니다.
- SDK 3.50.0의 공식 [HTTPX2 Mock 가이드](https://github.com/openai/openai-python/blob/v3.50.0/httpx2.md)에 나온 `httpx2.MockTransport`를 우선 검토하세요. 현재 설치된 버전에서 정확한 인터페이스를 확인한 뒤 사용하세요.
- SDK 모듈 import나 테스트 라이브러리의 정상 파일 읽기까지 막는 과도한 격리를 추가하지 마세요. **실제 외부 효과가 발생하는 경계**를 우선 차단하세요.

## 4. Red Phase Slice 1 — 최소 구현 대상

기존 F-BASE는 합성 Normalizer용 입력이므로 변경하지 마세요. SDK의 필수 필드가 포함된 **별도 C1용 합성 HTTP Response/SDK Fixture**를 작성하세요. 테스트 기대값은 SDK 직렬화 결과가 아니라 독립적으로 작성한 원래 합성 입력을 기준으로 세우세요.

### R-01 정상 수신·직렬화·연계

- 모의 HTTP 200 응답을 SDK 3.50.0 `client.responses.create()` 경로로 받아 `Response` 객체를 얻습니다.
- 단일 완료 `web_search_call(action.type="search")` 및 완료된 Assistant 메시지의 단일 `output_text`를 포함합니다.
- JSON 후보 1건과 일치하는 `url_citation.url` 및 원래의 offset을 그대로 보존하는지 확인합니다.
- C1 변환 결과가 JSON 호환 dict인지 확인하고, **실제 기존** `normalize_response()` → `parse_response()` → `validate_candidates()` 경로에서 정상 후보 1건이 채택되는지 확인합니다.
- 대상: GC1-01/02/03/04/07/10/11/13/14.

### R-02 생략 vs 명시적 `null`

아래 세 변형을 독립 원본 Fixture로 검사합니다.

- `reasoning.status` 생략 → 변환 후에도 키가 없음 → 기존 S1에서 허용.
- `reasoning.status: null` → 변환 후에도 `null`이 명시됨 → 기존 S1에서 거부.
- `reasoning.status: "completed"` → 값 유지 → 기존 S1에서 허용.

선택 필드가 원래 없었는데 SDK 또는 C1 설정으로 `null`이 생겨 정상 사례가 거부된다면, **C1 필드 보존 계약 위반**으로 분류합니다. 기존 Frozen 기대값을 수정하지 마세요.

### R-03 검색 호출 2건 보존

모의 HTTP 출력에 `web_search_call` 2건을 넣고, C1이 이를 1건으로 줄이지 않았음을 검증합니다. 기존 S1은 `TOOL_CALL_LIMIT_EXCEEDED`로 거부해야 합니다. 호출 수 제한을 맞추려고 정렬·필터링·삭제하지 마세요.

### R-04 변환 실패의 안전성

잘못된 입력 타입 또는 직렬화 실패가 정상 dict처럼 보이지 않고 **제한된 실패 결과**로 처리되는지 검사합니다. 실제 오류 원문·응답 본문·비밀 문자열은 공개 진단에 포함하지 않습니다. C1은 Preview를 만들지 않으며 실제 조정 계층의 S0 미호출 및 Preview 오류 매핑은 C2의 책임입니다.

## 5. Red의 유효성 판정

- C1 모듈/변환 함수가 아직 존재하지 않아서 의도한 Red 실패가 발생해야 합니다. 테스트에 임시 성공용 가짜 Converter를 작성하지 마세요.
- `openai` 미설치, 잘못 만든 SDK Fixture, 모의 HTTP 응답 형식 오류, 상위 `conftest.py` 충돌, 실수로 발생한 외부 네트워크 요청은 **유효한 Red가 아닙니다.** 해당 환경·테스트 설정 문제를 먼저 분리하세요.
- 처음부터 모든 GC1 AC에 독립 테스트 파일이나 추상 계층을 만들 필요는 없습니다. 우선 4~7개 수준의 핵심 테스트와 파라미터화를 사용하고, 남은 AC는 후속 Slice로 관리하세요.
- C1의 잠정 변환 옵션은 `to_dict(mode="json", use_api_names=True, exclude_unset=True, exclude_defaults=False, exclude_none=False)`입니다. 옵션 존재만 확인하고 동작을 테스트하지 않은 상태를 PASS라고 주장하지 마세요.
- SDK 내부 기본 경로와 Pydantic 엄격 검증 경로는 구별하며, `Response.model_validate()`만으로 실수신 호환성을 증명하지 마세요.

## 6. 이번 Slice의 금지 사항

- 기존 S0/S1 FROZEN 문서·코드·Fixture·격리 가드 변경.
- Green 구현으로 자동 진행, 광범위한 리팩터링, 공통 Provider 프레임워크 신설.
- 실제 OpenAI API Key 접근·출력·저장, `web_search` 유료 호출, 임의 모델 Fallback.
- 보호 저장소·G5/G6·P4 Writer·서비스 DB·Redis 연결, `HIDDEN` 준비 INSERT 또는 자동 게시.
- RSS/기존 뉴스 URL 경로와 Source Matching의 사전 통합.
- CLI/로그 렌더러를 E-10 완료 명목으로 추가.
- GitHub PR/병합 또는 승인 범위 외 커밋·푸시.

## 7. 결과 보고 형식

**Red Phase 종료 시 다음을 간결하게 보고하세요.**

1. 대상 브랜치·HEAD·working tree 상태, 작업 전후 변경 파일 목록 및 diff 요약.
2. 확인된 실제 Python 인터프리터·`openai`/`httpx2` 버전.
3. 제안한 최소 변환 인터페이스(함수명·입력·출력·실패 정책)와 채택 근거.
4. R-01~R-04와 GC1 AC의 대응표, 각 테스트의 실제 독립 Assert 내용.
5. 실행한 PowerShell 명령, 정확한 PASS/FAIL 결과, **정상적인 Red와 환경/Fixture 오류 구분**.
6. 실제 네트워크/요금/DB/Redis/Writer/게시 호출이 발생하지 않았음을 확인할 수 있는 테스트 격리 증거 및 남은 한계.
7. 정상 SDK 응답의 불필요한 거부(False Rejection) 여부, Frozen과의 충돌, 별도 CR 필요 여부.
8. **Green 진행 가능 여부**만 권고하고, Green 코드나 운영 연결은 수행하지 않음.

> **최종 원칙:** C1은 외부 SDK가 무엇을 반환하든, 내부 S1/S0가 검사할 **원본 증거를 보존하는 경계**입니다. 안전을 이유로 정상 출력을 불필요하게 배척하거나, 통과를 위해 증거를 수정하는 양극단을 모두 피하세요.