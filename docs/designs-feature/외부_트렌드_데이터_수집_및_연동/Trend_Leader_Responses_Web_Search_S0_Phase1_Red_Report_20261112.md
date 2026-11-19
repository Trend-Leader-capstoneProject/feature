# Responses Web Search S0 Phase 1 Red 실행 보고

> 실행일: 2026-11-12 KST
> 판정: **Phase 1 문서·실패 테스트 작성과 Red 실행 완료. 제품 기능 미구현.**
> Green 구현·커밋·푸시·PR·원격 쓰기·실제 Responses 호출은 수행하지 않았다.

## 1. 브랜치와 보존 상태

- 브랜치: `feat/responses-web-search-s0-fixtures`.
- HEAD / 생성 기준 `origin/dev`: `5508b78b34658125ba3571662748d3a81e07bf52`.
- 작업 직전 GitHub 읽기 전용 조회의 실제 원격 dev도 동일 SHA였다.
  이전 조사 결과 `b133b49…`와 달리 이번에는 로컬 dev와도 동일했다.
- `git switch -c feat/responses-web-search-s0-fixtures origin/dev`로 생성했다.
  보호된 `.git` 쓰기에 권한 오류가 발생해 승인된 동일 명령을 권한 확장으로 실행했다.
- 최신 dev에 이미 포함된 Phase4B2 코드가 있다. 이번 작업에서 해당 브랜치의
  merge/cherry-pick, 해당 코드 수정·실행은 하지 않았다.
- 세 설계 문서는 이미 기준 커밋과 동일했다. blob SHA는 S0 최소 계약 §1에 기록했다.
  원문과 FINAL REVIEW / NOT FROZEN 상태를 보존했다.
- 기존 미추적 `docs/infra/aws_design_firstpass.md`를 읽거나 수정하지 않았다.
- 최종 tracked unstaged/staged diff 없음. 새 파일만 미추적 상태다.

## 2. 추가 파일과 책임

| 경로 | 책임 |
|---|---|
| `backend/tests/responses_web_search/__init__.py` | 격리된 테스트 패키지 |
| `backend/tests/responses_web_search/conftest.py` | 금지 import, 외부 I/O·설정 읽기 차단, 상위 conftest 격리 확인 |
| `backend/tests/responses_web_search/fixtures.py` | 독립 합성 Responses 형태와 자체 후보 JSON 작성 |
| `backend/tests/responses_web_search/test_contract.py` | 제품의 S0 수용 기준 58건; 실행 시 제품 import |
| `backend/tests/responses_web_search/test_isolation.py` | 격리 및 차단 장치 자체 검증 14건 |
| 같은 디렉터리의 `Trend_Leader_Responses_Web_Search_S0_Minimal_Contract_v0.1_20261112.md` | 책임·입출력·진단·S1 유보·FROZEN 경계 |
| 본 보고서 | 실제 Red 결과와 한계 |

`backend/app/responses_web_search/`는 생성하지 않았다. 기존 제품 파일, 의존성,
FastAPI Router, ORM, RSS, Frontend 변경은 없다.

## 3. 실제 실행 명령과 결과

저장소 루트에서 Backend로 이동한 Windows PowerShell 명령이다.
`backend/venv`의 Python 3.14.0 / pytest 9.2.0 / Ruff 0.16.0을 사용했다.
아래 환경변수는 pytest 프로세스의 격리용 설정이며 API Key와 무관하다.

```powershell
Set-Location backend
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
./venv/Scripts/python.exe -m pytest tests/responses_web_search --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=line -q
```

최종 파일 기준 **58 failed, 14 passed** / 종료 코드 1.
추가로 메모리 내 pytest reporting plugin으로 실패 원인·단계를 집계했다.

```text
58 failed, 14 passed in 0.23s
FAILURE_AUDIT:
  ('call', "ModuleNotFoundError: No module named 'app.responses_web_search'"): 58
```

- 58건 모두 실행 단계에서 아직 없는 **프로젝트 제품 모듈** 때문에 실패했다.
- 테스트 수집 오류 0, setup/teardown 오류 0. pytest·SDK·DB 패키지 누락으로
  실패한 것이 아니다. OpenAI SDK는 의도적으로 설치·import하지 않는다.
- 테스트 전체가 동일한 첫 미구현 경계에서 멈춘 상태다. 각 후속 assertion의
  정확성과 실제 제품 분기 처리는 Green 승인 후 검증해야 한다.
- 정상/검색 없음/refusal/incomplete/구조 오류/인용 불일치/URL/중복/상한/
  정상 빈 배열/전부 제외/혼재/합성 오류/안전 상태를 테스트로 명세했다.

추가로 실제 실행한 명령:

```powershell
./venv/Scripts/python.exe -m pytest tests/responses_web_search/test_isolation.py --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q
./venv/Scripts/python.exe -m pytest tests/responses_web_search/test_contract.py::test_normal_response_and_no_input_mutation --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q
./venv/Scripts/python.exe -m ruff check --no-cache tests/responses_web_search
git diff --check
git diff --cached --check
```

| 검사 | 실제 결과 |
|---|---|
| 격리 테스트 단독 | **14 passed** |
| 정상 응답 테스트 단독 원인 확인 | **1 failed**, 제품 모듈 부재 재확인 |
| 새 테스트 Ruff | **All checks passed** |
| tracked unstaged/staged 공백 검사 | 오류 없음. tracked diff 자체가 없음 |
| 신규 파일 공백 검사 | 별도 `git diff --no-index --check`로 확인 |
| 기존 Backend 전체·DB 통합·모바일 테스트 | **미실행/미검증**. Phase 1 범위이며 DB 접근 금지 |

## 4. 격리 증거와 한계

- 상위 `backend/tests/conftest.py`와 dotenv/DB/SDK/HTTP/기존 RSS 모듈이
  로딩되지 않았음을 확인했다.
- 금지 모듈 import를 실제 모듈 실행 전에 차단하는 자체 테스트 7건이 통과했다.
- DNS, 네트워크 연결, 하위 프로세스, 파일 쓰기, 키 환경변수 값 조회,
  `.env` 파일 읽기는 원래 함수에 도달하기 전에 차단하는 자체 테스트 6건이 통과했다.
  키 차단 probe는 실제 키 값을 조회하지 않는다.
- 제품 테스트에서 허용한 외부 I/O 시도는 0건이다. 차단 예외를 무시한 시도도
  teardown에서 실패하도록 했다. 자체 테스트의 의도한 차단 probe와 구분한다.
- 이 실행에서 OpenAI 실제 호출 0회, 외부 네트워크 호출 0회, DB 접근·DML 0회,
  제품 파일 영속화 0회, 모바일 변경 0건이다.
- 작업 전 원격 dev 확인을 위한 **GitHub 메타데이터 읽기**는 수행했다.
  이는 S0 테스트 실행의 네트워크 0 결과와 별도로 기록한다.
- 제품 미구현 상태이므로 향후 제품 코드가 가드 아래 안전하게 동작하는지는 미검증이다.
  Python 가드는 OS 수준 native code의 모든 우회까지 증명하지 않는다.
- `git status`는 기존 pytest cache 디렉터리 일부에 접근 경고를 냈다.
  해당 경로의 내용은 미확인이다. 이번 실행에서는 cache/bytecode 생성을 비활성화했다.

## 5. 확인된 설계 제한과 다음 단계

1. 실제 OpenAI 응답과 SDK 호환성은 미검증이다. 단일 message/단일 output_text,
   자체 JSON이라는 제한된 S0 프로필을 실제 API 보장으로 확대하지 않는다.
2. 인용 URL 문자열 연결은 내용·권리·최근성·인용 위치의 독립 확인이 아니다.
3. 모의 검색 시각은 실검색 시각으로 만들지 않는다. Child Category는 확정하지 않는다.
4. Red는 모든 요구사항의 구현 실패 원인을 각각 증명한 상태가 아니라,
   테스트 수집·격리는 유효하고 첫 제품 모듈이 미구현임을 보여 주는 상태다.
5. 사용자 검토 및 Green 별도 승인 후에만 내부 타입 → 메모리 Adapter → Parser →
   URL/인용/중복 Validator → Preview 순으로 최소 구현하고 관련 테스트를 검증한다.
6. S1 모델·SDK/전송 방식·프롬프트·비용·키 환경·응답 라이선스·실제 호출은 별도 승인이다.
   G4/A1/4A/4B-1/4B-2/P4 자동 인계 미구현, G5/G6 HOLD, P4 NOT FROZEN을 유지한다.
