# Responses API MVP 구현·검증 기록

2026-11-16 KST. 구현 및 무과금 검증 결과와 격리 시연 DB 연결 검토안.

## 최신 구현 — Live 수동 검토 자료

시작 시 로컬·원격 기능 브랜치 SHA는 모두 1ef09e72bea93bd0bbd501fa20e6b0cf0a445e9e,
Worktree는 clean이었다. 최초 원격 조회의 연결 실패 후 읽기 전용 재조회에 성공했다.

Live 결과에 review_only_candidates를 추가했다. 기본값은 빈 배열이며 전체 응답 검사와
후보 JSON 파싱을 통과한 뒤 기존 Validator가 CITATION_URL_MISMATCH를 부여한 후보만
검토한다. 정상 단일 검색과 승인된 D2 PARTIAL 경로 모두 같은 규칙을 사용한다.
파손된 JSON·불안전 URL·미지원 D2 패턴에서는 검토 후보를 생성하지 않는다.
기존 candidates, status, citation_validation, candidate_validation, issues는 원래
판정을 그대로 유지한다. 수동 검토 후보가 있어도 NO_VALID_CANDIDATES일 수 있다.

자료는 최대 3개이며 제목·참고 제목 각각 255자, 원출처 후보 URL 4096자로 정했다.
초과 항목은 제외한다. URL은 기존 canonical_url 안전성 검사를 재사용하고 같은
canonical URL의 검토 자료는 먼저 나온 한 건만 남긴다. 잘라낸 URL을 생성하지 않는다.
원본 candidate_index, 세 필수 문자열, rejection_reason=CITATION_URL_MISMATCH와
content_trust=UNTRUSTED_MODEL_OUTPUT만 복사한다. 부가 모델 지시문 필드는 복사 대상 밖이다.

현재 요청 전문·현재 API 키의 포함 여부, 제어/서식 문자, 알려진 credential 표현,
system/developer 지시문 표식을 검사해 해당 검토 항목을 제외한다. 모델이 작성한
자유 문장은 사람의 검토 대상이며 어떤 필드도 실행할 명령이나 등록 승인으로 해석하지 않는다.
sources는 기존 집계 참고값으로만 유지한다. 검토 자료 생성 여부에 사용하지 않는다.

각 검토 항목은 REVIEW_REQUIRED, NOT_FOR_PUBLICATION, publish_authorization=NONE,
independent_source_verified=false를 가진다. 생성 함수는 메모리 표시 자료만 반환하며
DB·파일 writer와 연결되지 않는다. 기존 S0/S1 공개 진입점과 Gate A/B 출력은 보존했다.

CLI의 일반 실행 출력에는 review_only_candidate_count만 추가한다. URL·검토 제목이
담긴 review_only_candidates는 기본 stdout 진단에서 제외한다. 로컬 TTY에서 명시적으로
`--execute-live --review-local`을 선택했을 때만 별도 필드로 출력한다.
이 출력은 사람의 로컬 검토 자료이며 일반 진단 로그 수집에 전달하면 안 된다.
별도 파일 저장·자동 내보내기 동작은 없다. 기존 유료 호출 승인과 확인 문구 절차를 적용한다.

```powershell
# 별도로 승인된 다음 실측에서 로컬 검토를 함께 할 때 사용
& $responsesPython -m app.responses_web_search.d1_cli --execute-live --review-local
```

### 향후 사람이 검토를 완료한 후보의 최소 입력 계약 제안

등록 입력은 사람이 확인한 값으로 별도 작성하는 Reviewed Demo 입력으로 제안한다.
review_only_candidates나 Live Preview 전체 dictionary는 등록 입력에 해당하지 않는다.
기존 자동 인용 실패 기록은 provenance로 보존하며 자동 검증 PASS로 변경하지 않는다.

| 최소 입력 | 사람이 확인할 내용·기존 모델 연결 |
| --- | --- |
| reviewed_title | 표시 제목, 255자 이내, Trend.title에 사용하며 normalized_title은 기존 정규화로 계산 |
| reviewed_source_url | 사람이 연 원출처의 최종 URL, 안전성 재검증 후 TrendSource.source_url·source_key 산출 |
| reviewed_source_title | 원문과 대조한 제목, 255자 이내, TrendSource.source_title |
| platform | 기존 GOOGLE/YOUTUBE/SNS/ETC 중 명시 선택, TrendSource.platform |
| child_category_id | 실제 활성 Child와 IT_DIGITAL 부모를 확인, TrendCategoryMap.category_id, 대표 여부 명시 |
| reviewer·reviewed_at_utc·review_note | 누가 언제 원문과 제목·URL·후보 내용을 대조했는지의 수동 확인 기록 |
| original_failure | CITATION_URL_MISMATCH 및 원래 candidate_index·검토 후보 내용의 연결 |
| approval_scope | 사람이 승인한 ISOLATED_DEMO_ONLY, 게시할 후보와 최대 3건의 구체적 값 지정 |
| approved_target_reference | 별도 승인된 격리 DB 대상의 참조. 실제 host/port/database/CURRENT_USER 확인과 DML은 다음 승인 범위 |

summary·thumbnail은 최소안에서 NULL, 등록 시각은 실제 UTC를 사용한다. Trend·Source·
CategoryMap의 기존 UNIQUE/FK, 제목·source_key 중복 확인과 전체 승인 배치의 단일
Service 트랜잭션을 적용하는 안이다. 대상 확인이나 DML 실패 시 전체 rollback한다.
검토 자료 생성 함수에는 등록 API·DB Session·commit 권한을 추가하지 않았다.
후속 등록 구현은 명시적으로 작성된 Reviewed Demo 입력과 별도 DB 대상 승인을 요구한다.

현재 수정 파일은 manual_review.py, d1_live_preview.py, d1_cli.py, 관련 Mock 테스트와
이 보고서다. 기존 모델·공개 API·DB Schema·프롬프트 변경은 없다.

검증 결과는 S0 116 passed, S1 152 passed, 수동 검토·기존 MVP Mock 52 passed다.
credential 표현 검사를 좁힌 마지막 수정 후 해당 수동 검토 테스트 18개를 재실행해
18 passed (20.19초)를 확인했다. 대상 Ruff는 All checks passed다.
일반 Token 문구를 비밀값으로 분류하지 않도록 credential 검사는 bearer 또는
명시적인 key/password/token 할당 표현을 대상으로 한다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search tests/responses_web_search
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_s1 tests/responses_web_search_s1
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2 tests/responses_web_search_c2/test_manual_review.py tests/responses_web_search_c2/test_mvp_preview.py
& $responsesPython -m ruff check --no-cache app/responses_web_search tests/responses_web_search_c2/test_manual_review.py
```

Mock에서는 정상 후보 불변, 인용 불일치 자료 분리, 중복·3건 상한, 길이·URL·지시문·
비밀정보 제외, 원본 불변, 파손 JSON·미지원 D2 차단, CLI 기본 진단과 명시적 로컬
검토 출력을 확인했다. 실제 검토 자료 확보의 유료 실측과 사람 원문 확인은 대기 상태다.
이번 유료 호출·DB 쓰기·게시·Commit·Push·PR·Merge는 각각 0건이다.

## 최신 보완 — 인용 불일치 집계

이번 시작 HEAD는 f717269df0af05af966ede87ddcf6d2347eee91d이며 Worktree는 clean이었다.
사용자 제공 실측에서 PARTIAL 응답의 세 후보가 CITATION_URL_MISMATCH로 제외됐다.
해당 실측에는 인용 개수 정보가 없어 인용 0건과 직접 URL 불일치 중 원인을 확정할 수 없다.

현재 citation_validation은 후보별 source_url의 직접 citation URL 포함 여부로 계산한다.
후보가 있고 일치 후보가 0개이면 citation 배열이 비어 있거나 다른 URL만 있어도 MISMATCH다.
EMPTY는 후보 0개를 뜻한다. Validator는 필드·URL 검사 후 정확한 URL 문자열을 비교한다.
추적 query, fragment, trailing slash 차이도 직접 일치에는 영향을 줄 수 있다.
이번 수정은 이 검증 결과와 PARTIAL 수용 정책을 보존한다.

Live Preview에 citation_diagnostics를 추가했다. 전체 envelope와 후보 JSON의 검증에
도달하지 못한 경우 null이다. 정상·PARTIAL 경로 모두 같은 집계를 사용한다.

| 집계 필드 | 의미 |
| --- | --- |
| candidate_count | Validator 제외 전의 후보 수 |
| url_citation_count | 해당 assistant output_text의 실제 url_citation 항목 수, 중복 포함 |
| direct_matched_candidate_count | 원본 source_url과 citation URL이 직접 일치한 후보 수 |
| action_sources_matched_candidate_count | 모든 원본 웹 도구 항목의 관측된 action.sources URL과 직접 일치한 후보 수, 참고용 |

source metadata가 일부 누락·파손되면 sources 일치 개수는 null이다. 완전한 빈 sources
배열은 관측된 0건이다. sources에는 searching 항목의 값도 포함할 수 있으므로 검색
완료·출처 인용의 증거로 승격할 수 없다. 이 집계는 Validator의 판단에 사용되지 않는다.
집계값에 URL·검색어·요청/응답 원문·키·개인정보를 복사하지 않는다.

공식 Responses 문서는 output_text와 별도 annotations의 url_citation을 정의하며,
기본적으로 본문에 인라인 인용을 생성한다고 설명한다. sources는 검색 중 참고한
전체 URL 목록으로 인용과 별도의 구조다. JSON-only 요청에서 네이티브 인용이 반드시
생성된다는 보장은 확인하지 못했다. JSON-only 지시가 인용 생성을 어렵게 할 수 있다는
설명은 추론이며 이번 실측에서 인용이 없었다는 확정 원인은 아니다.
[공식 Web search 문서](https://developers.openai.com/api/docs/guides/tools-web-search#output-and-citations),
[공식 Sources 문서](https://developers.openai.com/api/docs/guides/tools-web-search#sources)

최소 프롬프트 수정안은 기존 필수 후보 필드와 단일 JSON 객체를 유지하면서, 각 후보에
선택적 citation_reference 문자열을 넣어 네이티브 인라인 인용의 위치를 제공하는 것이다.
현재 Parser는 추가 후보 필드를 무시하므로 기존 필수 계약을 재사용할 수 있다.
실제 D0 프롬프트 변경은 이번 작업에서 제시안으로 기록한다.

교체할 인용 지시의 제안 문구는 다음과 같다.

> 각 후보에 citation_reference 문자열을 추가하고, 그 안에 해당 출처를 뒷받침하는
> 짧은 설명과 웹 검색 도구의 네이티브 인용을 포함하세요. 단일 유효 JSON 객체를
> 반환하고 인용은 JSON 문자열 값 안에 배치하세요. source_url에는 해당 인용 대상의
> URL을 그대로 복사하세요. URL의 query·fragment·trailing slash를 임의로 바꾸지 마세요.
> 인용을 붙일 수 없는 후보는 제외하세요.

이 제안도 실제 annotations 생성이나 JSON 유효성을 보장하지 않는다. 모델이 JSON의
annotations 필드를 스스로 작성해도 API가 반환한 네이티브 annotations 검증을 통과한
것으로 취급할 수 없다. 기존 파싱·URL·직접 인용·중복 검증 결과가 최종 기준이다.

관련 Mock 검증은 인용 0건·다른 URL 인용·정확 일치·반복 인용·sources 누락·query 차이를
D2 PARTIAL 경로에서 재현한다. sources만 일치해도 NO_VALID_CANDIDATES를 유지하며
원본 불변·단일 요청·집계 및 로그의 비밀정보 비출력을 확인한다.

실행 결과는 test_mvp_preview.py 34 passed (48.93초), 대상 Ruff All checks passed다.
pytest는 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, PYTHONDONTWRITEBYTECODE=1,
`-q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2`로 실행했다.
테스트 대상은 `tests/responses_web_search_c2/test_mvp_preview.py`로 한정했다.
이번 변경 파일은 d1_live_preview.py, test_mvp_preview.py, 이 보고서다.
실제 API 호출·DB 쓰기·게시·Commit·Push는 이번 작업에서 각각 0건이다.

## 최신 구현 상태 — 승인된 Gate C D2 PARTIAL

후속 사용자 승인에 따라 정확한 D2 패턴의 검토 Preview를 구현했다.
아래 이전 정책 제안 절은 결정 이력이며, 현재 동작은 이 절을 기준으로 한다.

- 새 `app/responses_web_search/live_compatibility.py`가 최상위 completed,
  원본 도구 항목 정확히 2개, completed/search 1개와 searching/search 1개,
  실제 직렬화 요청 상한 1, 단일 완료 assistant 메시지를 검사한다.
- 오류·미완료 응답, 미지원 항목·상태, refusal, 크기 상한 초과를 거부한다.
  원본 dictionary와 도구 항목·상태는 그대로 보존한다.
- `parser.py`에서 후보 JSON·annotation 파싱을 `parse_candidate_content`로 추출했다.
  기존 S0 진입점과 Gate C가 이 함수를 공유하며 후보 Validator도 재사용한다.
- 기존 S1 Normalizer는 원본 2개를 계속 REJECTED로 판정한다. Live 조정 계층은
  그 결과의 원인을 보존한 채 별도로 승인된 Gate C 검사를 수행한다.
- 유효 후보가 있으면 status는 `PARTIAL_PREVIEW_READY`, response_validation은
  `PARTIAL`이다. 정상 단일 완료 검색의 `PREVIEW_READY`·`VALID`와 구분한다.
  빈 후보는 EMPTY_RESULT, 전부 제외되면 NO_VALID_CANDIDATES로 보고하며 후보 0건이다.
- 검토·게시·독립 출처 확인 상태는 기존 REVIEW_REQUIRED,
  NOT_FOR_PUBLICATION, NONE, false를 유지한다. CLI는 PARTIAL_PREVIEW_READY의
  진단 출력 성공에 종료 코드 0을 반환한다.

이번 변경 파일은 live_compatibility.py, parser.py, d1_live_preview.py, d1_cli.py,
기존 test_d1_live_boundary_red.py의 D3-01 기대값, test_mvp_preview.py의 직접 경계
반례 및 이 보고서다. 기존 D3-01은 S1의 REJECTED·parser_input=None과 Gate C의
PARTIAL 후보 생성을 함께 검증한다. 도구 원본의 불변성도 검증한다.

실제 호출 준비 명령은 앞의 CLI 사용 절과 동일하다. 현재 실행 세션의 무과금
readiness 결과는 API 키·선택 프로젝트 변수 설정 false, SDK 3.50.0이다.
기존 모델 접근·예산 이력을 참고하고 현재 잔액·RPM/TPM·키 설정을 확인한 후,
별도 단일 유료 호출 승인이 있어야 `--execute-live`를 실행한다.
이번 실제 유료 요청·DB 쓰기·게시·Commit·Push·Merge는 각각 0건이다.

검증은 Parser 분리의 직접 영향 범위인 S0 116 passed, S1 152 passed를 확인했다.
Live 영향 범위 실행 중 기존 공통 테스트 Helper가 반드시 S0 Parser를 거친다고
가정하던 단언과 CLI 테스트의 합성 키 설정 누락을 발견해 해당 테스트를 수정했다.
Gate C 후보 파싱은 공유 함수에 직접 진입하므로 기존 S0 envelope Parser 호출과
구분해 호출 순서를 검증한다. 최종 변경 경계 실행은 48 passed, 77 deselected
(23.01초), Ruff All checks passed다. 해당 명령은 다음과 같다.

```powershell
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2 tests/responses_web_search_c2/test_mvp_preview.py tests/responses_web_search_c2/test_d1_live_boundary_red.py -k 'd2 or d3_01 or d1b1'
& $responsesPython -m ruff check --no-cache app/responses_web_search tests/responses_web_search_c2/test_mvp_preview.py tests/responses_web_search_c2/test_d1_live_boundary_red.py
```

신규 경계는 두 번째 항목의 완료·실패·open_page, 세 번째 도구 항목, 응답/메시지
미완료, refusal, 부정 JSON, 인용 불일치, 텍스트·annotation·output·후보 상한,
중복 후보, 안전하지 않은 URL, CLI PARTIAL 성공과 요청 상한 미관찰·2 거부다.

## 작업 기준

- `git fetch origin dev` 성공. 확인한 `origin/dev`는 `ecaf9e3d3ce0543f3ccc874c038f8b4a5239c44d`.
- Worktree는 `C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-responses-mvp`.
- 브랜치는 `feat/responses-live-mvp-20261116`, 시작 HEAD는 `72ae583`.
  최신 dev를 포함하는 기존 FastAPI ZIP 호환성 커밋을 기반으로 선택했다.
- 기존 `feat/responses-web-search-gate-c1`의 `3c07c09`에서 C1/C2/D0/D1 및
  SDK Mock 코드와 해당 테스트를 재사용했다. 이 파일들은 기준 dev에 아직 포함되지 않아
  이번 Worktree에서는 신규 파일로 표시된다.
- S0/S1 Normalizer·Parser·Validator 및 공개 API 계약의 기존 blob을 보존했다.
  Preview 후보의 `REVIEW_REQUIRED`, `NOT_FOR_PUBLICATION`, `NONE`,
  `independent_source_verified=false`를 유지한다. G5/G6 상태는 HOLD다.

## 변경 파일과 실행 경로

| 파일 | 역할 |
| --- | --- |
| `backend/requirements.txt` | 기존 의존성에 `openai==3.50.0` 추가 |
| `app/responses_web_search/c2_transport.py` | 공식 SDK Responses 단일 요청, 재시도 0, 안전한 오류 코드 |
| `app/responses_web_search/c1_adapter.py` | SDK Response를 원본 의미를 보존한 dictionary로 변환 |
| `app/responses_web_search/gate_d_preflight.py` | 현재 서울 날짜 기준 7일 검색 계획 |
| `app/responses_web_search/d1_live_preview.py` | C2 → C1 → 기존 S1 → 기존 S0 Parser·Validator → 메모리 Preview |
| `app/responses_web_search/d1_cli.py` | 기본 오프라인 계획, 준비 상태 확인, 별도 승인된 단일 실행 진입점 |
| `app/responses_web_search/sdk_mock_preview.py` | 기존 SDK Mock 전용 경로와 테스트 지원 |
| `tests/responses_web_search_c1/`, `tests/responses_web_search_c2/` | 재사용 회귀 및 신규 MVP 진단 테스트 |

이번 보완은 Live Preview의 `citation_validation`, `candidate_validation`, CLI의
`--check-readiness`, 신규 `test_mvp_preview.py`다. C2 테스트 Helper는 D0의
모듈 reload 이후 현재 preflight 함수를 조회하도록 수정했다. 통합 실행에서 재현된
이전 dataclass 기본값과 재로딩된 클래스의 identity 불일치를 해결한다.

요청 설정은 `gpt-6-luna`, `tools=[{"type":"web_search"}]`,
`tool_choice="required"`, `max_tool_calls=1`, `max_output_tokens=4096`,
`store=false`, `stream=false`, timeout 60초, SDK 재시도 0이다.
`web_search_call.action.sources`를 include한다. 검색 결과의
`web_search_call.action`, `message.content[].text`, `annotations[].url_citation`을
각각 처리한다. 현재 공식 요청·응답 구조와 설치 SDK 3.50.0에서 확인했다.
[Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create),
[Web search](https://developers.openai.com/api/docs/guides/tools-web-search)

`max_tool_calls`는 처리할 내장 도구 호출의 상한이다. 반환 항목 개수의 의미는
프로젝트 Normalizer가 별도로 검사한다. 원본 도구 항목 2개나 미완료 상태는 기존 계약에
따라 거부된다. `action.sources`와 `url_citation`은 별도로 검사되며, 후보 URL은
동일 응답의 citation URL과 문자열이 일치해야 한다.
[Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create),
[Web search sources](https://developers.openai.com/api/docs/guides/tools-web-search#sources)

## CLI 사용

아래 PowerShell 명령은 이 Worktree의 `backend/`에서 실행한다. 현재 확인한 실행기는
기존 작업 폴더의 `backend/venv/Scripts/python.exe`다. 아래 `$responsesPython`에는
그 실행기의 절대 경로 또는 같은 의존성을 설치한 실행기를 지정한다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -m app.responses_web_search.d1_cli
& $responsesPython -m app.responses_web_search.d1_cli --check-readiness
```

기본 명령은 검색 계획을 출력한다. 준비 확인은 프로세스 환경변수의 설정 유무와 패키지
버전만 출력한다. 종료 코드 0은 진단 명령의 성공을 뜻한다. `.env` 자동 로딩은 없으며
`OPENAI_API_KEY`와 선택적인 `OPENAI_PROJECT_ID`를 Backend 실행 세션에서 전달한다.
키 값과 프로젝트 식별값은 진단에 포함하지 않는다.

별도 유료 실행 승인을 받은 뒤의 명령은 다음과 같다.

```powershell
& $responsesPython -m app.responses_web_search.d1_cli --execute-live
```

입출력 TTY 확인과 `EXECUTE ONE LIVE SEARCH` 입력 후 단일 요청을 보낸다.
CLI 확인 문구와 별도 사용자 유료 호출 승인은 각각 필요하다. 타임아웃·실패 시 결과를
진단하고 종료한다. 타임아웃의 원격 처리 상태는 UNKNOWN이다.

## 유료 호출 준비 상태

| 항목 | 2026-11-16 확인 근거와 상태 |
| --- | --- |
| 프로젝트·모델 | 사용자 제공 이력상 Trend Leader 프로젝트 생성, gpt-6-luna 접근 가능 |
| 이전 기본 호출 | 사용자 제공 2026-11-13 기록상 completed, 146 tokens |
| 프로젝트 예산 | 사용자 제공 이력상 월 $3, Limit enforced |
| 알림·충전 | 50%·100% 확인, 80% 미확인, 자동 충전 OFF |
| 잔액 | 사용자 제공 2026-11-13 $4.84, 현재 잔액 재확인 필요 |
| Rate limit | 현재 RPM/TPM 미확인 |
| 현재 실행 세션 | 준비 명령 실측상 `api_key_configured=false`, `project_configured=false` |
| 설치 패키지 | Python 3.14.0, openai 3.50.0, httpx2 2.16.0 |
| 신규 유료 승인 | 대기 |
| 이번 실제 API 요청 | 0회 |

오프라인 준비 명령은 계정 상태를 조회할 수 없어 모델 접근과 비용 제한을
UNCONFIRMED로 표시한다. 위 이력은 사용자가 제공한 기존 증거로 기록한다.
새 실측 전에는 현재 잔액·RPM/TPM·실행 세션 키 설정과 단일 호출의 비용 허용 범위를
확인해야 한다. 검색에는 도구 요금과 모델 토큰 요금이 적용된다.
[공식 요금표](https://developers.openai.com/api/docs/pricing)

기존 2026-11-14 검색 실험에서는 도구 항목 2개가 관찰되어
`TOOL_CALL_LIMIT_EXCEEDED`로 거부되었다는 사용자 기록이 있다.
이 사유는 내부 검증 계약의 거부를 뜻한다. 새 실측에서도 같은 거부가 발생할 수 있다.
과거 기본 호출·검색 실험의 재실행은 이번 검증에 포함되지 않았다.

## Gate D 도구 항목 2개 관찰에 대한 추가 확인

2026-11-16 추가 확인 요청에 따라 기존 기록과 전송 코드·합성 회귀를 대조했다.
근거 문서는 원래 `feat/responses-web-search-gate-c1` Worktree의 다음 파일이다.

- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Gate_D2_Live_Reobservation_Design_v0.2_APPROVED_20261114.md` §1.1~1.3
- 같은 디렉터리의 `Trend_Leader_Gate_D2_Live_Reobservation_Closeout_v0.1_OBSERVED_20261115.md` §1·§4

| 확인 항목 | 2026-11-14 첫 실험 | 2026-11-15 D2 재관찰 |
| --- | --- | --- |
| 과거 직렬화 요청 본문 | 보존 증거 미확인 | 보존 증거 미확인 |
| 요청 상한 | 당시 C2 코드 `max_tool_calls=1`, 과거 전송 본문 직접 검증은 미확인 | 같은 코드 설정, 과거 전송 본문 직접 검증은 미확인 |
| 최상위 상태·도구 항목 수 | completed, 2개 | completed, 2개 |
| 항목별 status/action.type | 기록 없음, 미확인 | index 1 completed/search, index 3 searching/search |
| 완료된 검색 수 | 당시 S1의 CONFIRMED에 근거해 최소 1개로 추론 | 기록상 1개 |
| 조합 | 두 항목의 조합 미확인 | search 동작 2항목, 그중 완료 1개·searching 1개 |
| 후보·인용 검증 | S1 상한에서 차단, 미평가 | 동일하게 미평가 |

11월 15일 기록은 사용자가 공유한 안전 Preview의 문서화다. 원본 HTTP 응답·요청
파일을 독립 재검증한 증거로 승격할 수 없다. 11월 14일 두 항목의 상태를
11월 15일 관찰로 소급해 채우면 날짜가 다른 실험을 혼동하게 된다.

현재 C2 코드와 SDK MockTransport의 실제 직렬화 요청에서 `max_tool_calls=1`을
검사했다. 과거 전송 요청도 같은 코드를 사용했다는 전제에서는 1이 적용됐을 것으로
추론할 수 있다. 해당 과거 요청의 body 캡처가 없어 실제 전송값을 확정할 수는 없다.

공식 API는 `max_tool_calls`를 응답에서 처리 가능한 내장 도구 호출 횟수로 정의한다.
S1은 원본 `web_search_call` 항목 수를 검사한다. 두 기준의 의미 차이가 확인되며,
D2 관찰 응답은 현 FROZEN 프로필과 호환되지 않아 계약대로 거부된다.
서버가 추가 항목을 반환한 원인과 실제 처리·청구 횟수는 미확인이다.
[Responses create](https://developers.openai.com/api/reference/resources/responses/methods/create)

다음 승인된 실측을 위해 Live Adapter에 `request_max_tool_calls`를 추가했다.
HTTP request hook에서 SDK가 직렬화한 body를 메모리로 읽고 해당 정수만 남긴다.
기본값 null은 미관찰을 나타낸다. 이 값은 전송 직전의 클라이언트 관측이며,
서버 수신·처리 확인은 별도의 증거가 필요하다.

기존 `web_search_call_details`는 모든 원본 항목의 index·허용된 status·action_type만
관측한다. C1/S1의 거부가 발생해도 메타데이터를 보존한다. 검색 질의·URL·요청/응답
본문·키·개인정보는 이 진단에 복사하지 않는다. 상한 검사는 원래 항목 전체를 대상으로 한다.

추가 검증은 전송 직전 상한 1 관측, 타임아웃 후 상한 관측 유지, 테스트에서만 상한을
2로 주입했을 때 실제 직렬화값 2 관측, 비밀정보 비출력 및 기존 D3-01 혼합 상태
거부 경로를 대상으로 했다. 관련 135개 테스트와 Ruff가 통과했다.

## Preview 진단과 합성 예시

### D2 두 차단 조건 및 Gate C Live 최소 정책 제안

2026-11-16 후속 요청의 대상으로 11월 15일 D2의 상태 조합을 고정한다.
아래 제안은 Gate C Live 검토용이며 사용자 채택 전 런타임 수용 조건은 기존과 같다.

| 구분 | D2 기록 | 합성 재현·현재 코드 |
| --- | --- | --- |
| 실제 직렬화 요청 상한 | 과거 body 증거 미확인, 당시 코드 1 | MockTransport body에서 1 확인 |
| 전체 응답 상태 | completed | completed |
| 원본 web_search_call 수 | 2 | 2 |
| 완료 search 수 | 1 | ExecutionEvidence.completed_search_actions=1 |
| 미완료 웹 도구 항목 수 | searching/search 1개 | 원본 index 3의 searching/search 1개 |
| 서버 실제 처리·청구 횟수 | 미확인 | 합성으로 확정할 수 없음 |

첫 차단은 원본 항목 수 2 > 1이다. 두 번째 차단은 searching 항목의 완료 상태 검사다.
두 번째 검사는 첫 차단 때문에 현재 D2 경로에서는 실행되지 않는다. 따라서 상한만
변경한다는 가정에서도 상태 검사에서 거부된다. 기존 단독 searching/search 합성
사례는 상한 1 이내에서 상태 검사가 독립적으로 거부함을 보여준다.
같은 D2 원본에 임의 설정을 주입하여 상한 검사를 통과시키는 실험은 수행 이력 0건이다.

기존 D3-01 Fixture는 D2의 두 도구 상태·동작·위치를 재현한다. reasoning 수와
메시지·인용 내용은 합성이므로 과거 원본 응답의 완전 복원으로 해석할 수 없다.

Gate C Live에서 필요한 최소 정책 변화는 아래 두 조건을 함께 명시하는 것이다.

1. 원본 항목 수와 완료 검색 수를 별도 수용 기준으로 정의한다. 이 D2 패턴에 한해
   원본 2개, completed/search 정확히 1개, searching/search 정확히 1개를 검토 대상으로 한다.
   요청의 max_tool_calls는 1로 유지한다. 완료 search 2개와 다른 동작·상태 조합은
   이 제안의 수용 범위 밖이다.
2. 최상위 completed와 미완료 도구 항목의 공존을 별도 Live 상태로 표현한다.
   searching은 원형으로 보존하며 응답 검증 결과를 PARTIAL로 표시하는 안을 제시한다.
   이 경로의 후보는 검토 전용 Preview로 제한하고 도구 전체 완료와 독립 출처 확인은
   미확정으로 기록한다. 기존 VALID/PREVIEW_READY의 의미를 확대하지 않는다.

위 두 변화에 더해 후보를 표시하는 최소 전제는 다음과 같다.

- 원본 전체에서 모델 일치, 최상위 completed, 오류·refusal 부재, 지원하는 구조·방어 상한,
  단일 완료 assistant message와 output_text를 검증한다.
- 기존 후보 JSON 계약과 최대 3건, URL 안전성·중복·직접 url_citation 일치 검증을 적용한다.
- 원본 항목 전체와 각 상태·동작·위치를 보존하고, 표시한 후보가 사용한 message/citation/
  완료 search의 원본 위치를 메모리에서 구분한다. message/citation에서 어느 search가
  실제 근거를 제공했는지는 미확정으로 남긴다. searching 항목의 처리 여부는 UNKNOWN이다.

PARTIAL 검토 Preview는 이번에 제안한 Live 조건이다. 사용자 승인된
기존 계약으로 취급할 수 없다. D2의 메시지·인용 원자료가 없어 위 후보 조건의
충족 여부는 미확인이다. 이 조건을 채택해도 D2 후보 확보 성공을 소급 판정할 수 없다.

최소 구현 영향은 Gate C 전용 전체 응답 검사와 기존 후보 Validator 재사용이다.
기존 S0 Parser도 원본 항목 수·완료 상태를 검사하므로 그 진입점에 두 항목을 그대로
넣으면 다시 차단된다. 승인 후에는 후보 JSON 파싱 부분을 순수 함수로 추출해 기존
Parser와 Gate C 경로에서 함께 사용하는 방식이 필요하다. 원본 도구 목록을 가공한
가짜 단일 완료 응답을 기존 Parser에 제출하는 방식은 이 제안에 포함되지 않는다.
예상 변경 지점은 Gate C 전용 모듈, parser.py의 동작 보존 추출, d1_live_preview.py의
명시적 경로 선택이다. Gate A/B의 진입점·기대값·SearchRunConfig는 유지한다.

정책 채택 시 결정할 항목은 이 D2 패턴의 PARTIAL 검토 Preview 허용이다.
서버가 미완료 항목을 반환한 원인의 확정은 현재 증거로 불가능하다.
기존 135 PASS를 근거로 사용했고, 신규 테스트는 추가하지 않았다. 직접 관련된 기존
합성 재현만 재실행한 결과는 23 passed, 74 deselected (9.40초)다.
명령은 기존 D1 테스트 파일에 `-k 'd3_01 or d1b1_call_details_are_bounded'`를
적용했으며 나머지 격리 옵션은 앞선 실행과 동일하다.

| 필드 | 의미 |
| --- | --- |
| `search_execution` | 완료 search 증거를 CONFIRMED / NOT_CONFIRMED / UNKNOWN으로 표시 |
| `response_validation` | S1·Parser의 구조·완료·JSON 검증 |
| `citation_validation` | 후보 URL의 직접 인용 연결을 MATCHED / PARTIAL / MISMATCH / EMPTY로 표시 |
| `candidate_validation` | Validator 결과를 VALID / PARTIAL / INVALID / EMPTY로 표시 |
| `NOT_EVALUATED` | 해당 검증 단계에 도달하기 전의 실패 |
| `issues` | 후보 index별 URL·필드·인용·중복 사유 |
| `request_max_tool_calls` | 전송 직전 SDK 직렬화 요청에서 관측한 정수, 미관찰 null |

아래는 기존 합성 payload를 실제 SDK `MockTransport` 경로로 실행해 얻은 결과의 발췌다.
원출처 사람 검토와 실제 검색 검증은 대기 상태다.

```json
{
  "status": "PREVIEW_READY",
  "search_execution": "CONFIRMED",
  "response_validation": "VALID",
  "citation_validation": "MATCHED",
  "candidate_validation": "VALID",
  "review_status": "REVIEW_REQUIRED",
  "publication_status": "NOT_FOR_PUBLICATION",
  "candidates": [{
    "topic_draft": "SDK Mock 연결 검토 후보",
    "source_url": "https://vendor.example.test/releases/sdk-mock",
    "source_title_reference": "원래 제목 — 내부 검토용",
    "source_published_at": null,
    "proposed_category_ref": "IT_DIGITAL",
    "review_status": "REVIEW_REQUIRED",
    "publication_status": "NOT_FOR_PUBLICATION",
    "publish_authorization": "NONE",
    "independent_source_verified": false
  }]
}
```

## 격리 시연 DB 연결 검토안

다음 매핑과 등록 흐름은 사용자 검토용 제안이다. DB 연결 계약 승인은 대기 상태다.

| 입력·검토 결과 | 기존 DB 필드 | 등록 시 확인 |
| --- | --- | --- |
| 사람이 승인한 `topic_draft` | `Trend.title`, `normalized_title` | 기존 `external_trends.normalizer.normalize_title` 재사용, NFC·공백·ASCII 소문자·255자 확인 |
| 사람이 원문과 대조한 `source_url` | `TrendSource.source_url`, `source_key` | 승인된 URL 정규화와 SHA-256 사용 |
| 사람이 확인한 원제목 | `TrendSource.source_title` | 참고 제목을 원문과 대조, 255자 확인 |
| 확정한 출처 플랫폼 | `TrendSource.platform` | 기존 GOOGLE/YOUTUBE/SNS/ETC 중 승인, 일반 웹은 ETC 제안 |
| 사람이 고른 활성 Child Category | `TrendCategoryMap.category_id` | IT_DIGITAL 부모 관계·활성 상태·Child 여부 확인 |
| 대표 Child 선택 | `TrendCategoryMap.is_primary` | 최대 3건의 후보별 대표 분류 검토 |
| 승인된 시연 게시 상태 | `Trend.status` | 격리 시연 DB에서 ACTIVE 등록을 명시 승인 |
| 실제 등록 UTC 시각 | `first_collected_at`, `last_collected_at`, `collected_at` | DB의 UTC-naive 규칙 사용 |
| 별도 검토한 요약·이미지 | `summary`, `thumbnail_url` | 최소안은 NULL |

`proposed_category_ref=IT_DIGITAL`에서 Child ID를 자동 결정할 수 없다.
후보 `source_published_at=null`은 원문 게시일 확인 전 상태다.
기존 URL 정규화는 UTM·fragment 처리에서 S0 URL 비교와 차이가 있으므로,
검토된 원본 URL과 등록용 canonical URL·source_key를 함께 확인하는 계약이 필요하다.

### 최소 후속 파일 제안

- `backend/scripts/register_reviewed_demo_trends.py`가 명시 승인된 최대 3건과 격리 DB 대상을 입력받는다.
- `backend/app/services/demo_trend_registration_service.py`가 승인 입력 검증과 전체 등록 트랜잭션을 관리한다.
- `backend/app/repositories/demo_trend_registration_repository.py`가 중복 조회와 add/flush를 담당한다.
- 관련 테스트에서 대상 DB 불일치, 미승인 입력, 중복, 중간 실패 rollback, 정상 3개 모델 연결을 확인한다.

등록 흐름의 최소 검토안은 다음과 같다.

1. 검토자·검토 시각·승인된 후보 내용과 원출처 확인 결과를 결합하고, 최대 3건의 등록 대상을 확정한다.
2. 격리 DB host/port/database/CURRENT_USER와 실제 연결을 검증한다.
   기존 `app/db/seeds/demo_trends.py`의 `_verified_seed_connection`은 동일 연결을
   commit까지 유지하는 참고 구현이다. 재사용 방식은 DB 계약 승인 시 정한다.
3. Service에서 단일 트랜잭션을 열고 제목·URL·Child Category를 재검증한다.
4. 배치 내·DB의 `normalized_title`, 같은 trend의 `source_key`, category map 중복을 확인한다.
   충돌 시 전체 rollback하는 안을 제시한다. MariaDB UNIQUE/FK를 최종 무결성 방어로 사용한다.
5. `Trend` add/flush로 ID를 확보하고, 해당 ID로 `TrendSource`와 `TrendCategoryMap`을 추가한다.
   최대 3건 전체 성공 시 Service가 한 번 commit한다. 중간 실패·동시성 UNIQUE 충돌은
   rollback 후 안전한 원인 코드를 보고한다. 기존 행 갱신·재시도 정책은 승인 시 확정한다.

동일 URL이 다른 제목의 trend에 연결되는 경우까지 막을지는 별도 계약 항목이다.
현재 source UNIQUE는 `(trend_id, source_key)`다. DB 전체 URL 유일성을 가정할 수 없다.

승인 후 등록 코드의 핵심 ORM 작성 형태는 다음과 같다. 이 예시는 위 사전 검증과
중복 검사를 통과한 입력을 전제로 하는 코드 조각이다.

```python
with session.begin():
    trend = Trend(
        title=reviewed_title,
        normalized_title=normalized_title,
        status=TrendStatus.ACTIVE,
        summary=None,
        thumbnail_url=None,
        first_collected_at=registered_at_utc_naive,
        last_collected_at=registered_at_utc_naive,
    )
    session.add(trend)
    session.flush()
    session.add(TrendSource(
        trend_id=trend.trend_id,
        source_key=reviewed_source_key,
        source_url=reviewed_canonical_url,
        source_title=reviewed_source_title,
        platform=reviewed_platform,
        collected_at=registered_at_utc_naive,
    ))
    session.add(TrendCategoryMap(
        trend_id=trend.trend_id,
        category_id=reviewed_child_category_id,
        is_primary=True,
    ))
```

기존 `GET /api/trends`는 ACTIVE를 최신 `last_collected_at`, trend_id 순으로 읽고,
최근 출처와 Child/Parent Category를 조립한다. `TrendCard`는 title, nullable
summary/thumbnail, categories, last_collected_at, latest_source를 이미 처리한다.
현재 코드 근거상 DB·앱 연결의 최소 후속 변경은 등록 진입점·Service·Repository 및
해당 테스트다. 실제 API 조회와 Expo 기기 표시 검증은 격리 DB 승인·등록 이후 수행한다.

남은 차단 조건은 신규 단일 유료 요청 승인, 현재 실행 세션의 키·계정 제한 확인,
FROZEN을 통과하는 실제 후보 확보, 원출처 사람 검토, 격리 시연 DB 대상·승인 입력·
중복 처리·트랜잭션 최소 계약 확정과 DB 쓰기 승인이다.

## 검증 기록

신규 테스트는 구현 전 9 failed를 확인했고 진단 필드·준비 명령 추가 후 9 passed다.
정상 1~3개, 4개 초과 거부, 검색 부재, 타임아웃 단일 요청, 인용 불일치·부분 일치,
부정 JSON, 준비 명령 무과금·비밀정보 비출력을 포함한다.

테스트 실행 시 다음 환경과 pytest 옵션을 사용했다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $responsesPython -m pytest -q -p no:cacheprovider --confcutdir=tests/responses_web_search tests/responses_web_search
& $responsesPython -m pytest -q -p no:cacheprovider --confcutdir=tests/responses_web_search_s1 tests/responses_web_search_s1
& $responsesPython -m pytest -q -p no:cacheprovider --confcutdir=tests/responses_web_search_c1 tests/responses_web_search_c1
& $responsesPython -m pytest -x -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2 tests/responses_web_search_c2
& $responsesPython -m ruff check --no-cache app/responses_web_search tests/responses_web_search_c1 tests/responses_web_search_c2
```

| 검증 | 실제 결과 |
| --- | --- |
| S0 | 116 passed |
| S1 Gate A/B 및 관련 회귀 | 152 passed |
| C1 | 13 passed |
| C2/D0/D1/MVP 통합 | 206 passed, 304.71초 |
| Ruff | All checks passed |
| 오프라인 계획·준비 명령 | 종료 코드 0, 신규 HTTP 요청 0회 |
| MockTransport Preview 예시 | PREVIEW_READY, 인용 MATCHED, 후보 VALID |
| 공백·staged 공백 검사 | 통과 |

추가 확인 요청 전 구현의 관련 테스트 합계는 487 passed다.
신규 파일 19개의 공백도 별도 검사했다.

2026-11-16 Gate D 추가 확인에서는 신규 진단의 실패 테스트 2 failed를 확인한 뒤
전송 직전 request hook을 구현했다. 이후 아래 영향 범위만 다시 실행했다.

```powershell
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2 tests/responses_web_search_c2/test_mvp_preview.py tests/responses_web_search_c2/test_d1_live_boundary_red.py tests/responses_web_search_c2/test_transport_red.py
& $responsesPython -m ruff check --no-cache app/responses_web_search tests/responses_web_search_c2/test_mvp_preview.py tests/responses_web_search_c2/test_d1_live_boundary_red.py
```

결과는 135 passed (86.82초), Ruff All checks passed다. 신규 진단 시나리오 3개를
포함한다. 기존 S0/S1 코드와 C2 요청 상한의 변경은 0건이다.

초기 C2 통합 실행에서 기존 D0 reload와 D1 Helper 참조의 불일치를 발견했다.
최소 재현은 1 failed / 2 passed였고, Helper 수정 후 동일 재현은 6 passed다.
실제 API Preview는 신규 유료 호출 승인 대기다. DB·앱 통합 및 전체 프로젝트 테스트는
이번 검증 범위에서 실행 대상에 포함되지 않았다.

Git 작업 결과는 이 Worktree의 requirements 변경과 신규 패키지 파일·테스트·이 기록이다.
기존 사용자 Worktree의 미추적 GitHub Releases 및 Frontend 테스트 파일은 보존했다.
Commit·Push·PR·Merge와 서비스 DB 저장은 실행 이력 0건이다.
