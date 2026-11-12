# Responses Web Search S0 Phase 2 Green 실행 보고

> 실행일: 2026-11-12 KST
> 판정: **R-01/R-02 보완 및 S0 Fixture-only 로컬 구현·검증 완료**.
> 실제 검색·독립 원출처 확인·게시·S1 검증 완료가 아니다.

## 1. 시작 상태와 승인 범위

- 재사용 브랜치: `feat/responses-web-search-s0-fixtures`.
- HEAD: `000bceca8a03e7c7c83b9daee16b8a965553a258`.
- 시작 시 tracked 변경 없음. 기존 미추적 `docs/infra/`는 접근·수정하지 않았다.
- 원격 S0 이름의 ref 조회는 실패했고 로컬 remote-tracking ref도 없었다.
  별도 읽기 전용 조회로 **원격 dev 최신 HEAD가 위 SHA와 동일**함을 확인했다.
- 브랜치 전환·reset·clean·커밋·푸시·PR·원격 쓰기를 하지 않았다.
- 외부 조회는 시작 시 GitHub 메타데이터 확인뿐이다. 아래 제품 테스트의
  네트워크 0 결과와 구분한다.

## 2. 변경 파일과 책임

| 파일 | 변경 |
|---|---|
| `backend/app/responses_web_search/types.py` | 검증된 불변 설정, 파싱 결과, 후보, 진단 타입 |
| `backend/app/responses_web_search/fixture_adapter.py` | 메모리 입력/합성 오류와 읽기 횟수. 재시도 없음 |
| `backend/app/responses_web_search/parser.py` | 제한된 응답 구조·완료·검색·인용·자체 JSON·상한 검사 |
| `backend/app/responses_web_search/validator.py` | 필수 필드·URL 문자열·인용 연결·중복 검사 |
| `backend/app/responses_web_search/service.py` | 한 번 읽기, 조정, 허용 필드만 비게시 Preview로 투영 |
| `backend/app/responses_web_search/__init__.py` | 기존 공개 이름 3개 export |
| `backend/tests/responses_web_search/test_contract.py` | R-01/R-02 보완과 빈 URL 기대 사유 정합성 수정 |
| 같은 디렉터리의 `Trend_Leader_Responses_Web_Search_S0_Minimal_Contract_v0.1_20261112.md` | Phase 1 기록 보존, Phase 2 승인·검증 세칙 추가 |
| 본 문서 | 실행 결과·검증 한계 |

## 3. Red → Green 증거

| 실행 | 실제 결과 |
|---|---|
| R-01/R-02 보완 후 Red | **102 failed, 14 passed**, exit 1 |
| Red 원인 집계 | 102건 모두 call 단계 `ModuleNotFoundError: No module named 'app.responses_web_search'` |
| 최초 구현 후 | **1 failed, 115 passed** |
| 해당 실패 | 공백 후보 URL을 Fixture가 인용에도 복제해 annotation 구조 오류까지 만든 R-01 테스트 문제 |
| 수정 | R-01이 후보 JSON만 변경하고 유효 인용 구조를 유지하도록 분리. 제품의 구조 검증을 완화하지 않음 |
| 최종 전체 S0 | **116 passed in 0.32s**, exit 0 |
| 격리 단독 | **14 passed in 0.10s**, exit 0 |
| 대상 Ruff | **All checks passed**, exit 0 |

기존 빈 URL 테스트의 `SOURCE_URL_INVALID` 기대는 계약의 빈 필수 값 규칙과 달랐다.
해당 항목을 R-01의 `CANDIDATE_FIELDS_INVALID` 검증으로 통합했다.
이는 전체 실패 처리 규칙이나 FROZEN 도메인 정책 변경이 아니다.
R-02에서는 구조가 부정한 인용의 혼재와 구조가 정상인 비일치 URL의 혼재를 구분했다.

## 4. 재현 명령 — Windows PowerShell

저장소 루트에서 시작한다. 이전 Red 보고서의 격리 옵션을 유지한다.

```powershell
Set-Location backend
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
./venv/Scripts/python.exe -m pytest tests/responses_web_search --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q
./venv/Scripts/python.exe -m pytest tests/responses_web_search/test_isolation.py --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q
./venv/Scripts/python.exe -m ruff check --no-cache app/responses_web_search tests/responses_web_search
git diff --check
git diff --cached --check
```

Red 원인 집계에는 위 pytest 옵션과 같은 격리 옵션에 메모리 내 reporting plugin을
더해 실패 단계·예외 메시지를 집계했다. 실행 로그 파일을 제품에서 저장하지 않았다.
신규 파일도 별도 `git diff --no-index --check`로 공백 오류를 검사했다.

## 5. 계약 정합성과 외부 영향

- 공개 이름 `SearchRunConfig`, `FixtureAdapter`, `run_preview` 유지.
- 모의 검색 증거와 실제 검색을 구분한다. `searched_at_utc=null`이며
  주입한 Fixture 기준시각만 별도 출력한다. 현재시각을 검색 증거로 만들지 않는다.
- 모든 Preview·남은 후보는 REVIEW_REQUIRED, NOT_FOR_PUBLICATION,
  publish_authorization=NONE, independent_source_verified=false다.
- 입력 추가 키로 승인·날짜·순위·점수를 승격하지 않는다. 원 응답을 변경하지 않는다.
- 제품 코드와 import는 외부 I/O 차단 가드 아래 실제 실행됐다.
  제품 경로에서 실제 OpenAI 호출 0회, 외부 네트워크 0회, DB 접근·DML 0회,
  키 조회·사용 0회, 파일 영속화 0회다.
- OpenAI SDK 설치, 기존 RSS·Router·ORM·Frontend 변경 없음.
- 기존 S0 가드·격리 테스트는 수정 없이 유지했고, 독립 실행도 통과했다.
- 기존 Final Review·FROZEN 문서와 G0~G6 정책 변경 없음.
  G5/G6 HOLD 및 P4 NOT FROZEN 유지. G4/A1/4A/4B-1/4B-2/P4 자동 연결 없음.

## 6. 남은 위험과 미검증

- 실제 API/SDK 응답 호환성, 실제 생성 JSON·annotation 형태는 S1 미검증이다.
  S0는 단일 message/단일 output_text 및 url_citation만 받는 제한된 프로필이다.
- annotation title/offset의 정확성, URL 도달성·DNS·redirect·권리·사실·최신성은
  검증하지 않는다. Unicode 도메인 지원과 의미 기반 사건 중복 판단도 보장하지 않는다.
- Python 가드는 일반 호출 경로의 차단 증거이며 악의적인 native code의 모든
  우회를 막는 OS 수준 보증이 아니다.
- 기존 Backend 전체·DB 통합·모바일 테스트는 미실행/미검증이다.
  이번에는 해당 제품 경로를 변경하지 않았다.
- `git status`의 기존 cache 디렉터리 접근 경고는 유지된다. 그 내용을 조사하지 않았다.
- 추가 작업은 별도 승인 경계다. 특히 S1 모델·SDK/전송 방식·prompt·비용·권리·키 환경·
  실제 연결 검증과 S2 원출처 확인을 이번 S0 결과로 승인하지 않는다.
