# Gate C2 Red Phase Slice 1 — 2026-11-13 KST

이번 변경은 테스트와 이 실행 기록뿐이다. `app/responses_web_search/c2_transport.py`나
성공용 대체 구현을 만들지 않았다. C2 기능 PASS 또는 Gate C 전체 완료를 뜻하지 않는다.

## 작업 기준과 상태

- 브랜치: `feat/responses-web-search-gate-c1`
- HEAD: `bb842d07665996f0b4846800ac8370fd5c2c1881` (사용자 마지막 확인값과 일치)
- 시작 시 추적 파일 변경·staged 변경 없음. 기존 pytest cache 디렉터리 열람에는
  권한 경고가 있어 내부 상태는 확인하지 않았다. 테스트에서는 cacheprovider를 껐다.
- `git ls-remote origin refs/heads/feat/responses-web-search-gate-c1`은 GitHub 443
  연결 실패. 원격 최신 HEAD는 확인하지 못했으며 로컬 기준으로 진행했다.
- 다른 worktree 두 곳은 각각 `545c390` / `feat/p4-fr-b02b-pure-binding`,
  `434ce78` / `feat/p4-readonly-handoff`. 각 `git status --short` 출력 없음.
  소유권 검사에는 명령 한정 `-c safe.directory=<해당 경로>`를 사용했고 전역 설정은
  변경하지 않았다. 다른 worktree를 수정하지 않았다.
- Backend `venv/Scripts/python.exe`: Python 3.14, `openai==3.50.0`,
  `httpx2==2.16.0`. 설치나 의존성 파일 변경 없음.

## 제안한 최소 내부 인터페이스

아래는 테스트가 요구하는 인터페이스의 설명이며 제품 코드는 아니다.

```python
def request_response(
    *, api_key: str, model: str, input_text: str,
    timeout: float, http_client: httpx2.Client,
) -> openai.types.responses.Response: ...

class C2TransportError(Exception):
    code: C2ErrorCode
```

`C2ErrorCode`는 다음 문자열로 제한하는 안이다:
`INVALID_CONFIGURATION`, `TIMEOUT`, `CONNECTION_ERROR`,
`AUTHENTICATION_FAILED`, `PERMISSION_DENIED`, `RATE_LIMITED`,
`UPSTREAM_SERVER_ERROR`, `REQUEST_REJECTED`, `SDK_RESPONSE_INVALID`.
사용자가 지정한 HTTP 분류를 그대로 쓰고, 나머지는 내부 오류 이름의 제안이다.
공개 API Schema나 Frozen Preview 계약을 새로 정의하는 것이 아니다.

C2가 SDK Client를 생성하거나 요청 옵션에서 `max_retries=0`을 직접 보장한다.
외부 SDK Client는 입력으로 받지 않는다. 호출자가 모델·입력·양수 유한 Timeout을
명시하며 `60.0`은 테스트 값이다. 별도 `2.5` 테스트로 전달값 반영도 요구한다.
`store=False`, `stream=False`, `tools=[{"type": "web_search"}]`,
`tool_choice="required"`, `max_tool_calls=1`,
`include=["web_search_call.action.sources"]`를 요청 JSON에서 검사한다.
성공 시 SDK에서 받은 동일 `Response`를 반환하고 `output`을 보존한다.
C1 직렬화·S1 정규화·S0 후보 검증·Preview 조정은 여기서 수행하지 않는다.

SDK 소스/실행에서 `APITimeoutError`가 `APIConnectionError`의 하위 타입임을 확인했다.
따라서 예외 분류 시 Timeout을 먼저 검사해야 한다.
`APIResponseValidationError`는 `APIStatusError` 하위 타입이 아니다.
기본 수신 경로는 관대한 객체 구성이고 strict 경로에서 검증 오류가 발생한다.
strict 옵션은 검증 오류 경계 테스트에서만 주입하며 C2 운영 설정으로 요구하지 않는다.

## 테스트 대응

지정 문서와 저장소에서 C2-01~12의 원문 정의는 발견하지 못했다.
다음 ID는 **이번 요청을 추적하기 위한 로컬 임시 매핑**이며 승인된 AC 원문을
대체하거나 새 정책을 동결하지 않는다.

| 로컬 ID | 검증 내용 | 시나리오 / 테스트 |
|---|---|---|
| C2-01 | SDK 버전·실제 Mock HTTP 수신·Response | R-01 / `test_sdk_success_control`, `test_r01_original_sdk_response_and_request` |
| C2-02 | store=false 명시 | R-01 / 공통 `assert_request` |
| C2-03 | web_search·required·1회 상한·sources include | R-01 / 공통 `assert_request` |
| C2-04 | 비스트리밍 단일 요청 | R-01 / 공통 `assert_request` |
| C2-05 | SDK 원본 객체·output 보존, 후보 판정 없음 | R-01 / 원본 identity·독립 output 비교; 후보 JSON이 아닌 텍스트 사용 |
| C2-06 | SDK/앱 재시도 없음, E-08 | R-02 / HTTP 파라미터화, R-03 / 연결 오류; 재시도 탐지 대조군 |
| C2-07 | Timeout과 일반 연결 실패 구분 | R-03 / SDK 예외 계층 통제·C2 오류 코드 |
| C2-08 | 401/403/429/5xx/기타 4xx 분류 | R-04 / HTTP 파라미터화 |
| C2-09 | SDK Response 검증 오류 별도 분류 | R-04 / default·strict 통제 및 strict 주입 경계 |
| C2-10 | 모델·입력·Timeout 사전 검증, 전송 0회 | R-05 / 빈 값·공백·0·음수·±inf·NaN·None |
| C2-11 | 키·본문·원문 예외 비노출 | R-02~05 / str·repr·표준 traceback·수집 로그·stdout/stderr 합성 마커 검사 |
| C2-12 | SDK 허용·외부 I/O/비밀/DB 차단, 기존 격리 보존 | `test_isolation_controls`, 패키지 import 통제, 별도 회귀 실행 |

## 최초 Slice 실행 명령과 결과

모든 pytest는 `backend/`에서 Backend 가상환경으로 별도 프로세스 실행했다.

```powershell
.\venv\Scripts\python.exe -m pytest tests/responses_web_search_c2 --confcutdir=tests/responses_web_search_c2 -q -p no:cacheprovider --tb=no
.\venv\Scripts\python.exe -m ruff check tests/responses_web_search_c2
.\venv\Scripts\python.exe -m pytest tests/responses_web_search --confcutdir=tests/responses_web_search -q -p no:cacheprovider --tb=short
.\venv\Scripts\python.exe -m pytest tests/responses_web_search_s1 --confcutdir=tests/responses_web_search_s1 -q -p no:cacheprovider --tb=short
.\venv\Scripts\python.exe -m pytest tests/responses_web_search_c1 --confcutdir=tests/responses_web_search_c1 -q -p no:cacheprovider --tb=short
```

- C2: **19 controls PASS / 26 intended Red FAIL**. 별도 `--tb=line` 실행에서
  26건 모두 `ModuleNotFoundError: app.responses_web_search.c2_transport`임을 확인했다.
- Ruff: 대상 C2 Python 파일 전체 PASS.
- S0: **116 PASS** / S1: **152 PASS** / C1: **13 PASS**.
- 각 pytest에 기존 anyio plugin의 `CallSpec2` 폐기 예정 경고 1건이 있다.
  테스트 실패나 환경 장애는 아니며 이번 의존성 변경 범위 밖이다.

통제 테스트에서 실제 SDK Mock 전송은 정상 1회, 각 HTTP 오류 1회,
ReadTimeout/ConnectError 각각 1회, default/strict 수신 각각 1회였다.
HTTP 오류는 400/401/403/404/408/409/418/422/429/500/503을 확인했다.
기본 SDK `max_retries=2` 대조군은 429에 3회 전송했다(대기만 테스트에서 생략).
실행별 SDK 통제 Mock 전송 합계는 19회이며 실제 네트워크 요청은 아니다.
요청 JSON과 HTTP timeout extension을 독립적으로 검사했다.
C2 자체는 미구현이라 26건 모두 전송 전에 실패한다. **C2의 E-08·오류 분류·
비노출은 아직 PASS가 아니며 Green에서 검증해야 한다.**

초기 테스트 작성 중 다음 두 구성 오류를 발견·수정했다. 이 결과는 정상 Red로
인정하지 않는다: pytest의 `PYTEST_CURRENT_TEST`까지 차단한 빈 환경 자체검사,
기존 패키지 `__init__`의 순수 S0 재수출 import까지 막은 가드.
현재는 pytest 메타데이터를 허용하고 정상 패키지 import와 파일 읽기를 보존한다.

## 격리, 변경 통제, 다음 단계

- 상위 `tests/conftest.py`가 로딩되지 않았음을 fixture에서 검사한다.
- 실제 환경값을 읽거나 복사하지 않고 테스트 동안 `os.environ`을 빈 매핑으로
  교체한다. SDK에는 무효한 합성 키만 명시한다. `.env*`, `.aws`, `.ssh` 파일
  읽기를 차단한다. 정상 패키지 파일 읽기는 허용한다.
- DNS·소켓 전송·subprocess·DB/Redis/dotenv/운영 모듈 import를 차단한다.
  가드 시도 횟수는 teardown에서 확인하여 삼켜진 I/O 시도도 실패시킨다.
  자기검사만 의도한 차단 시도를 허용한다. DB/Writer/게시 경로 호출 없음.
- 제품 코드, S0/S1/C1 테스트 및 Frozen 문서 변경 없음. 기존 계약과 충돌 없음.
  C1 문서의 후속 C2 Preview 표현은 이번 사용자 지시에 따라 후속 연결 Slice로
  남겨두며, 이번 전송 함수에 Preview 계약을 추가하지 않는다.
- `requirements.txt`에 `openai==3.50.0` 선언이 없는 재현성 문제는 **Green 후속 과제**다.
- 최종 변경은 이 디렉터리의 신규 파일 5개뿐이며 staged 변경 없음.
  커밋·푸시·PR·병합·실 API 호출·과금·설치 없음.
- **Red Slice 준비 완료, 별도 승인된 Green으로 진입 가능**.
  C2 기능 완료나 Gate D 실검색 승인은 아니다. Green에서는 모든 C2 단언이 실제로
  실행된 뒤 결과를 확인해야 한다. 원격 상태는 작업 재개 시 재확인한다.

## Red Slice 1 정합성 보완 결과 — 2026-11-13 KST

- 작업 브랜치는 동일하며 시작 HEAD는 `98bc1a5ffe6341d07662157bdb58a20acf6131f8`이다.
  시작 시 미커밋 변경 없음. 다른 worktree 두 곳도 변경 없음.
  원격 HTTPS 연결은 실패하여 최신 원격 HEAD는 미확인이다.
- 설치된 SDK 3.50.0의 `SyncAPIResource._client`와 Client의 수신 검증 경로를
  재확인했다. R-04 주입을 리소스 자체의 속성 설정에서
  `resource._client._strict_response_validation = True`로 수정했다.
  제품 SDK 기본 설정은 변경하지 않았다.
- 독립 통제 테스트 1건을 추가했다. 기본 strict=False에서 같은 리소스 wrapper를
  통해 실제 Client를 strict=True로 바꾸고, HTTP 200 Mock 응답이 실제
  `APIResponseValidationError`를 발생시킴을 확인했다. HTTP 상태 예외와 구별되며
  Mock 전송은 정확히 1회다.
- 연결 오류 코드는 `CONNECTION_ERROR`, SDK 수신 검증 오류는 `SDK_RESPONSE_INVALID`로
  테스트·설명을 통일했다. `INVALID_CONFIGURATION` 등 다른 코드는 유지했다.

Backend 가상환경에서 별도 프로세스로 실행한 명령:

```powershell
.\venv\Scripts\python.exe -m pytest tests/responses_web_search_c2/test_sdk_controls.py --confcutdir=tests/responses_web_search_c2 -q -p no:cacheprovider --tb=short
.\venv\Scripts\python.exe -m pytest tests/responses_web_search_c2/test_transport_red.py --confcutdir=tests/responses_web_search_c2 -q -p no:cacheprovider --tb=line
.\venv\Scripts\python.exe -m ruff check tests/responses_web_search_c2
git diff --check
git diff --cached --check
```

- SDK·Mock 통제: **20 PASS** (기존 19건 + strict 주입 통제 1건).
- C2 Red: **26 FAIL**, 모두 정확히 `app.responses_web_search.c2_transport` 부재.
  환경·Fixture·Mock 오류로 발생한 실패는 없다.
- Ruff·공백 검사 PASS. 각 pytest의 기존 anyio `CallSpec2` 경고 1건은 유지된다.
- 변경 파일은 `test_transport_red.py`, `test_sdk_controls.py`, `support.py`,
  이 README의 4개다. 기존 격리·S0/S1/C1·Frozen·의존성·제품 코드는 변경하지 않았다.
  S0/S1/C1은 이번 최소 보완에서 재실행하지 않았으며 위 수치는 최초 실행 기록이다.
- 정상 Red 재확인 후 중단한다. 별도 Green 승인·검토로 진행 가능하며,
  Green 구현·실 API·DB/Redis/Writer/게시·커밋·푸시·PR·병합은 수행하지 않았다.
