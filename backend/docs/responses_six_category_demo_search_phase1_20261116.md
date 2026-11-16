# 6개 분야 전시 검색 Phase 1 구현·검증 기록

2026-11-16 KST. 승인 설계는 `responses_six_category_demo_search_design_v0.1_20261116.md`다.
시작 브랜치는 `feat/responses-live-mvp-20261116`이며 로컬·원격 HEAD를 모두
`1217765860ddbef37430b7240b21dfceb23861e0`으로 확인했다. 시작 Worktree는 clean이었다.
원격 조회는 기본 네트워크에서 실패한 뒤 읽기 전용 재조회로 확인했다.
승인 설계의 HEAD blob과 Worktree 파일 해시는 모두
`dd058743ca43a7a1b0e6f3ca81cb6c6465099b3f`로 일치했다.

## 구현과 책임

- `demo_search.py`의 별도 frozen 설정·계획은 6개 분야 중 하나를 명시적으로 받는다.
  모델과 모든 요청 설정은 기존 D0 승인값과 값·타입이 같아야 한다.
  D0의 서울 날짜 계산을 재사용하고 전시용 프롬프트는 별도로 생성한다.
- 실행 전 계획 전체를 재생성해 비교한다. 실제 전송의 과거 계획은 차단하고,
  합성 날짜는 기존과 같이 MockTransport 경로에서만 사용한다.
- D1의 기존 승인·설정·계획 검사는 유지하고, 검증 이후의 요청·응답 처리를
  `_run_validated_preview()`로 추출했다. 전시 진입점도 자체 검증 이후 이 함수를 호출한다.
- Parser·Normalizer·D2 함수는 실제로 사용하는 상한만 정의한 `ValidationLimits`
  Protocol을 타입 주석으로 받는다. 기존 검증 로직과 S0/D0 설정 조건은 유지한다.
- C1/C2, 후보 Validator, 제한적 mismatch 검토 자료와 D2 호환 처리를 재사용한다.
  요청은 최대 한 번이며 실패·부족·중복에서 재시도하지 않는다.
- `demo_cli.py`는 D1의 준비 진단·오류 출력을 재사용하고 동일한 입출력 TTY 검사와
  정확한 `EXECUTE ONE LIVE SEARCH` 확인 문구를 요구한다.

## 사용 방법

확인한 실행기는 아래 기존 venv다. 명령의 작업 디렉터리는 이 Worktree의 `backend/`다.
실행기를 공유해도 Python 모듈은 현재 Worktree에서 읽는다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -B -m app.responses_web_search.demo_cli --check-readiness
& $responsesPython -B -m app.responses_web_search.demo_cli --profile FASHION
```

분야는 `FASHION`, `BEAUTY`, `GAME`, `FOOD`, `ENTERTAINMENT`, `IT_DIGITAL` 중 하나다.
인수 없이 실행하면 `PROFILE_REQUIRED`와 선택 가능한 분야를 출력하고 종료 코드 1을 반환한다.
분야만 지정하면 오프라인 계획을 출력한다. 준비 진단은 계정·예산을 조회하지 않으며
`READINESS_INCOMPLETE`, 접근·비용 제한 `UNCONFIRMED`, 유료 승인 false를 유지한다.

별도 유료 호출 승인 후 사용 가능한 문법은 다음과 같다. 이번 검증에서는 실행하지 않았다.

```powershell
& $responsesPython -B -m app.responses_web_search.demo_cli --profile FASHION --execute-live
& $responsesPython -B -m app.responses_web_search.demo_cli --profile FASHION --execute-live --review-local
```

분야 플래그를 먼저 쓰는 고정 문법이다. stdin/stdout이 TTY여야 하며 자동 확인 입력이나
파이프·출력 캡처를 사용하지 않는다. 키는 확인 문구 수락 후 프로세스 환경에서 읽는다.
`.env`를 자동 로딩하지 않는다. CLI 확인은 별도 유료 실행 승인을 대신하지 않는다.

정상·PARTIAL·빈 결과·전부 탈락 결과는 기존 D1처럼 진단 출력 성공으로 종료 코드 0을
반환할 수 있다. 이 코드를 후보 확보·등록 승인으로 해석하면 안 된다.

## Phase 2 연결용 내부 데이터 계약

Phase 1은 JSON 호환 메모리 Preview와 콘솔 출력을 제공한다.

| 위치 | 필드와 의미 |
| --- | --- |
| 최상위 | 기존 D1 진단·안전 필드, 검증된 계획의 `search_profile` |
| `candidates` | 기존 세 후보 문자열·안전 필드·`proposed_category_ref`, 원본 `candidate_index`, 후보별 `citation_validation=MATCHED` |
| `review_only_candidates` | 기존 제한적 검토 자료·원본 index·실패 사유, 실제 `proposed_category_ref`, 후보별 `citation_validation=MISMATCH` |
| `issues` | 원본 후보 배열 기준 index와 기존 진단 코드 |
| 최상위 `citation_validation` | 응답 전체 후보의 집계 상태. 후보별 값과 구분 |

`candidate_index`는 원본 candidates 배열의 0-based 위치다. 각 후보를 수용하거나
issue 하나로 제외하는 기존 Validator 결과에서 원본 순서대로 연결한다. 필터링 후
배열을 재번호 매기지 않는다. 요청 분야는 계획에서 가져오며 모델의 분류 필드를 복사하지 않는다.
사람이 실제 내용의 분야·최신성·원문 근거를 확인해야 한다.

승인·설정 차단처럼 계획 검증 전 실패한 결과에는 `search_profile`을 부여하지 않는다.
검증된 계획의 전송 실패에는 분야가 남는다. 후보 검사에 도달하지 못한 결과의 index나
citation 상태를 추측하지 않는다. 원본 응답·키·전체 프롬프트를 결과에 복사하지 않는다.

일반 CLI 출력은 기존처럼 `review_only_candidate_count`만 표시한다.
`--review-local`을 명시한 콘솔 출력에서만 mismatch 후보 내용을 제공한다.

Phase 2는 이 자료를 검토 전 초안으로 변환하고 `source_review=NOT_REVIEWED`,
`operator_approved=false`, `approved_record_count=0`을 적용해야 한다.
`source_url`은 최초 AI URL로 보존할 수 있으며 사람이 채택한 최종 URL과 구분한다.
원래 실패와 후보별 citation 결과를 그대로 연결해야 한다.
검색 실행 식별자·보존 파일·증거 해시는 Phase 2에서 실제 보존 대상과 함께 정의한다.
이번 출력에 임의 해시·가상 시각을 넣지 않는다.

현재 Daily 검증의 정상 MATCHED provenance 수용과 영수증 확장은 Phase 2 작업이다.
Phase 1 Preview 전체를 기존 Daily 등록 입력으로 전달할 수 없다.

## 검증

Python 3.14.0, openai 3.50.0, httpx2 2.16.0, pytest 9.2.0, Ruff 0.16.0을 확인했다.
테스트는 기존 C2 socket/HTTP/DB import/환경/파일 격리 가드와 MockTransport를 사용한다.
신규 모듈 구현 전 첫 테스트는 `ModuleNotFoundError`로 1 failed를 확인했다.

회귀 실행은 각 suite를 별도 프로세스로 분리하고 다음 옵션을 사용한다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $responsesPython -B -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search tests/responses_web_search
& $responsesPython -B -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_s1 tests/responses_web_search_s1
& $responsesPython -B -m pytest -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c1 tests/responses_web_search_c1
& $responsesPython -B -m pytest -x -q --tb=short -p no:cacheprovider --confcutdir=tests/responses_web_search_c2 tests/responses_web_search_c2
& $responsesPython -B -m ruff check --no-cache app/responses_web_search tests/responses_web_search_c1 tests/responses_web_search_c2
```

| 검증 | 실제 결과 |
| --- | --- |
| S0 | 116 passed, 0.46초 |
| S1 Gate A/B | 152 passed, 19.87초 |
| C1 | 13 passed, 9.09초 |
| C2/D0/D1/전시 검색 전체 | 342 passed, 190.99초; 신규 93개 포함 |
| 합계 | 623 passed |
| 위 범위 Ruff | All checks passed |
| 변경 Python 8개 구문 검사 | `compile()` 성공, bytecode 생성 없음 |
| 실제 모듈 오프라인 실행 | `--profile GAME`, PREFLIGHT_VALIDATED, live_request_allowed=false |

초기 전체 C2 실행에서는 기존 D1 테스트가 모듈에 직접 남긴 합성 ObservationClock으로
인한 테스트 순서 의존 실패 1건을 확인했다. 신규 테스트의 시계를 monkeypatch fixture로
격리한 후 위 전체 342개를 재실행했다. 기존 D1 테스트 기대값과 제품의 시계 처리는 유지했다.

6개 분야 계획, 잘못된 설정, 변조·불완전 계획, 실제 전송의 비현재 계획, 승인·TTY 경계,
단일 직렬화 요청과 후보 상한, citation 불일치, 원본 index 보존, D2 PARTIAL·거부,
모델 불일치와 timeout/429/503 무재시도를 검증했다.
기존 ICT 진입점의 실행·출력·검증 회귀는 위 C2/D1 전체에 포함된다.
전체 Backend·Frontend 테스트와 실제 DB·기기 검증은 이번 범위에서 실행하지 않았다.

현재 단계는 **Phase 1 MOCK_TESTED**다. Phase 2 초안 변환·파일 보존·Daily provenance 확장은
후속 작업이며, 실제 후보 품질·원출처 검토·DB 등록·기기 표시는 별도 검증이 필요하다.
실제 유료 API 호출, DB DML, Migration, Commit/Push/Merge는 수행하지 않았다.
