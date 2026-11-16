# Responses 전시 검색 Phase 2 구현·사용·검증

2026-11-16 KST. 승인 기준은 `responses_six_category_demo_search_design_v0.1_20261116.md`다.
구현 직전 로컬·원격 기능 브랜치 HEAD는 모두
`c6fb53a254afb05327027401971240b7495d537e`이며 Worktree는 clean이었다.
기본 네트워크의 원격 조회 실패 후 읽기 전용 재조회로 확인했다.

구현 전 아래 HEAD blob SHA와 Worktree 파일 해시가 일치함을 확인했다.

| 파일 | SHA |
| --- | --- |
| 승인 설계 | dd058743ca43a7a1b0e6f3ca81cb6c6465099b3f |
| demo_search.py | e7a458a56fa4611f523ac52a4fdb7e04ff82c31c |
| demo_cli.py | b8df2ccb2b489f0114c5fe5f7f2890dc36286e26 |
| Daily Service | a66eca9dbb75c5ce5106c4c9f50b5dafb73887b6 |
| 기존 ICT Service | 0f7a70dab9dd53a5c178b7402175f96f26d0f3d8 |
| 기존 ICT CLI | 4dfd4840cb38efd37d63c70b05ac1334080a81fe |
| 기존 ICT JSON | 19b28e2c6be9b00ce0b3ae841cd163e7036c5d7a |

## 변경과 입력 계약

- `draft_export.py`는 Phase 1 Preview에서 허용된 진단·후보 필드만 복사한다.
  실제 검색 분야, 원본 index, 후보별 인용 결과, AI URL과 실패를 보존한다.
- 전시 CLI의 명시적 `--draft-dir` 옵션으로 요청 전에 파일을 배타적으로 생성하고
  flush/fsync를 확인한다. 현재 저장소와 다른 Git checkout 내부, 미존재 디렉터리는 거부한다.
  경로의 symlink/junction은 resolve한 대상 기준으로 검사한다.
- 파일은 `responses_demo_<UUID hex>.json`이며 UUID는 해당 로컬 실행 준비에서 생성한다.
  OpenAI 응답 ID로 표현하지 않는다. 파일은 같은 핸들로 한 번만 쓰고 덮어쓰지 않는다.
- 최상위는 기존 Daily 입력 형식이며 `search_runs` 배열에 보존 증거를 함께 둔다.
  단일 검색은 하나의 run을 가진다. 하루치 파일에는 여러 run과 선택한 records를 담을 수 있다.
- `reviewer_alias=null`, `approved_record_count=0`, `source_review=NOT_REVIEWED`,
  `operator_approved=false`, `child_name=null`, `review_note=null`로 생성한다.
  검토·분류·승인 전에는 기존 Daily 검증에서 DB 연결 전에 차단된다.

| 기록 | 값·의미 |
| --- | --- |
| `parent_code` | 초안 생성 시 실제 검색 profile. 사람은 등록용 분류를 검토 |
| `search_profile` | 최초 검색 profile. provenance로 보존 |
| `candidate_index` | 원본 candidates의 0-based index. 필터링 후 재번호 부여 없음 |
| `original_ai_source_url` | 최초 AI URL. 사람이 수정한 `source_url`과 별개 |
| `original_citation_validation` | 후보별 MATCHED 또는 MISMATCH |
| `original_failure` | MATCHED는 null, MISMATCH는 CITATION_URL_MISMATCH |
| `original_response_citation_validation` | 응답 전체 citation 집계. 후보별 값과 별개 |
| `original_response_validation` | VALID/PARTIAL 등 실제 응답 검증 상태 |
| `search_run_id` | 실제 로컬 실행 준비에서 생성한 UUID hex |
| `search_evidence_sha256` | 함께 보존한 허용 필드 evidence의 실제 SHA-256 |

해시 입력은 `search_runs[].evidence`를 `json.dumps(ensure_ascii=False, sort_keys=True,
separators=(',', ':'), allow_nan=False)`로 직렬화한 UTF-8 bytes다.
run ID·해시 필드 자체와 검토 중 편집하는 records는 이 해시 입력에 포함하지 않는다.
원시 SDK/HTTP 응답 전체의 해시라고 주장하지 않는다. 해시는 로컬 자료 일관성 검사이며
원출처 사실성·사용자 신원·서버 응답의 인증 증명은 별도다.

Daily 검증은 새 참조 필드가 있으면 search_runs에서 실제 해시를 다시 계산하고,
원본 index·AI URL·검색 분야·인용 상태·실패·응답 상태와 대조한다.
등록 직전 재검증을 위해 Candidate에 해당 run 자료를 전달하며, 성공 영수증에는
검증된 새 provenance 필드를 보존한다. 원시 evidence 전체를 영수증에 복사하지 않는다.
기존 참조 없는 CITATION_URL_MISMATCH/NOT_VALIDATED 입력·영수증은 호환한다.
새 MATCHED는 `original_citation_validation=MATCHED`, 명시적 `original_failure=null`을 요구한다.

## 파일과 민감정보 경계

모델의 추가 키, 원시 응답, 프롬프트, 예외 본문, 인증 헤더, 환경변수는 저장하지 않는다.
복사할 후보 문자열의 길이·URL·제어문자·credential 패턴을 검사하고,
현재 API Key와 프롬프트가 포함된 문자열도 차단한다. URL percent encoding을 풀어
credential query와 userinfo, 일반적인 token·password·JWT 패턴도 검사한다.
검출되면 전체 초안 저장을 거부하며 문자열을 잘라 승인된 자료로 만들지 않는다.

요청 전 쓰기 검사는 이후 디스크 오류까지 보장하지 않는다.
저장·flush·fsync·close 오류는 `DRAFT_WRITE_FAILED_NO_RETRY` 등 고정 코드로 보고한다.
예약 파일이 빈 파일 또는 일부 JSON으로 남을 수 있으며 이를 등록 입력으로 사용하면 안 된다.
검색을 이미 전송했을 수 있으므로 출력 실패를 이유로 자동 재호출하지 않는다.
검색 실패 자체를 정상 저장한 파일은 records가 비어 있고 관측된 실패·UNKNOWN 상태가 남는다.

## CLI 사용

작업 디렉터리는 현재 Worktree의 `backend/`다. 저장 폴더는 사용자가 만든 기존의
저장소 밖 보존 폴더를 지정한다. CreatorTemp를 영구 보관 위치로 전제하지 않는다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -B -m app.responses_web_search.demo_cli --profile FASHION
```

별도 단일 유료 호출 승인 후 아래 문법으로 사용할 수 있다. 이번 구현 검증에서는
실제 유료 명령을 실행하지 않았다.

```powershell
$draftDirectory = Read-Host '기존 저장소 외부 보존 폴더 경로'
& $responsesPython -B -m app.responses_web_search.demo_cli --profile FASHION --execute-live --draft-dir $draftDirectory
```

분야는 6개 승인 값 중 하나이며 `--draft-dir <경로>`는 마지막에 둔다.
stdin/stdout TTY와 정확한 `EXECUTE ONE LIVE SEARCH` 직접 입력이 필요하다.
파이프·자동 확인 입력을 사용하지 않는다. `--review-local`을 쓸 경우 `--draft-dir`보다 먼저 둔다.
`--review-local`은 콘솔의 mismatch 자료 표시를 제어한다. 명시적 `--draft-dir` 저장에는
제한적 mismatch 검토 자료도 포함된다.

## 실제 하루치 JSON을 구성하는 예

다음은 **이미 생성된 실제 검색 파일 두 개**를 골라 2026-11-17 하루치 미승인 파일로
묶는 PowerShell 예다. 검색·DB 호출을 수행하지 않으며 원래 run ID·해시·evidence를 보존한다.
파일 경로는 실행 결과의 `draft_file` 값을 사용한다. 서로 다른 실행 파일을 선택한다.

```powershell
$sourceFiles = @(
    (Read-Host '첫 번째 실제 draft_file 전체 경로'),
    (Read-Host '두 번째 실제 draft_file 전체 경로')
)
$dailyPath = Join-Path $draftDirectory 'reviewed_demo_daily_20261117_DRAFT.json'
@'
import json
import os
import sys
from pathlib import Path

inputs = [json.loads(Path(name).read_text(encoding="utf-8-sig"))
          for name in sys.argv[2:]]
daily = {
    "input_kind": "REVIEWED_DEMO_DAILY_BATCH",
    "approval_scope": "ISOLATED_DEMO_ONLY",
    "expected_target": inputs[0]["expected_target"],
    "reviewer_alias": None,
    "approved_record_count": 0,
    "records": [item for batch in inputs for item in batch["records"]],
    "search_runs": [run for batch in inputs for run in batch["search_runs"]],
}
with Path(sys.argv[1]).open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(daily, stream, ensure_ascii=False, indent=2, allow_nan=False)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
'@ | & $responsesPython -B - $dailyPath @sourceFiles
```

JSON 묶기에는 기존 Python을 사용해 UTC 시각 문자열을 그대로 보존한다.
확인한 PowerShell 7.6.10의 기본 ConvertFrom-Json은 ISO 시각을 DateTime으로 변환하므로
그 결과를 다시 JSON으로 저장하면 원래 evidence 해시가 달라질 수 있다.

이 예제의 records는 MATCHED와 검토용 MISMATCH 모두 미승인 상태로 묶인다.
운영자는 각 URL을 열어 원제목과 핵심 주장을 대조한 후 실제 제목·채택 URL·
source_title·child_name·짧은 review_note를 편집한다.
제외할 후보는 records에서 제거하고 search_runs의 증거는 보존한다.
원본 provenance와 search_runs는 편집하지 않는다. 실제 검토를 완료한 레코드만
`source_review=URL_TITLE_KEY_CLAIMS_VERIFIED`, `operator_approved=true`로 사람이 변경하고,
검토자 별칭과 승인 대상 records.length에 정확히 맞는 approved_record_count를 기입한다.
한 번의 Daily 입력은 최대 36건이며 같은 배치·DB의 제목·URL 중복 검사를 적용한다.

검토 후 읽기 전용 확인은 기존 Daily 명령을 사용한다.

```powershell
$passwordFile = Read-Host '저장소 외부 격리 DB password-file 경로'
& $responsesPython -B -m scripts.register_reviewed_demo_daily --input $dailyPath --password-file $passwordFile
```

초안 그대로 전달하면 DB 연결 전에 BLOCKED다. 검토된 입력의 DB Dry-run에는 로컬 격리
MariaDB가 필요하다. 실제 등록은 기존의 별도 `--execute`·영수증·TTY 건수 확인 절차를 따른다.

## 검증 기록

설치 버전은 Python 3.14.0, openai 3.50.0, httpx2 2.16.0, SQLAlchemy 2.0.51,
pytest 9.2.0, Ruff 0.16.0이다. 최초 신규 exporter 테스트는 모듈 미구현으로 1 failed를 확인했다.

각 테스트 suite는 별도 프로세스로 실행하고 아래 격리 옵션을 사용한다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
# suite는 responses_web_search, responses_web_search_s1, responses_web_search_c1,
# responses_web_search_c2, reviewed_demo 중 하나다. 임시 경로는 저장소 밖의 신규 경로다.
& $responsesPython -B -m pytest -x -q --tb=short -p no:cacheprovider --basetemp $externalTestTemp --confcutdir="tests/$suite" "tests/$suite"
& $responsesPython -B -m ruff check --no-cache app/responses_web_search app/services/reviewed_demo_daily_registration.py tests/responses_web_search_c1 tests/responses_web_search_c2 tests/reviewed_demo
```

Reviewed Demo의 트랜잭션 회귀는 메모리 SQLite와 테스트 대역을 사용한다.
상위 DB/dotenv conftest를 로딩하지 않으며 실제 MariaDB에 연결하거나 DML을 수행하지 않는다.
실제 OpenAI 유료 호출, MariaDB DML, Migration, Commit/Push/Merge는 수행하지 않았다.

| 검증 | 실제 결과 |
| --- | --- |
| S0 | 116 passed, 1.24초 |
| S1 Gate A/B | 152 passed, 26.07초 |
| C1 | 13 passed, 14.29초 |
| C2/D0/D1/전시 검색/초안 전체 | 367 passed, 313.59초 |
| Reviewed Demo 전체 | 97 passed, 4.72초 |
| 위 전체 회귀 합계 | 745 passed |
| 마지막 민감정보 필터 보완 후 exporter 재검증 | 27 passed, 15.50초; 새 보안 반례 2개 포함 |
| 위 범위 Ruff | All checks passed |
| 변경 Python 5개 구문·공백 검사 | 통과, bytecode 생성 없음 |
| 문서 PowerShell 예제 5개 | 구문 검사 통과 |
| 하루치 묶기 예제 | MockTransport 합성 파일 2개로 실행, 두 evidence 해시·미승인 상태 보존 |

전시 profile/index 보존, 후보별·응답 전체 citation 구분, 명시적 null 실패값,
허용 필드 해시, 배타적 파일 예약·재저장 거부, 승인 전 HTTP·파일 생성 0,
저장 오류 후 단일 요청 유지, timeout 빈 후보 보존을 검증했다.
Daily는 미승인 초안·변조 provenance·증거 누락을 DB 연결 전에 차단했고,
MATCHED/MISMATCH 검토 입력의 Dry-run·SQLite 등록·성공 영수증과 이전 두 실패 상태를 검증했다.

현재 단계는 **Phase 2 MOCK_TESTED**다. 실제 검색 후보·파일 보존 환경·원출처 검토,
로컬 격리 MariaDB Dry-run/등록, API·실기기 표시는 별도 실행 증거가 필요하다.
최종 Git 상태는 기존 파일 2개 수정·신규 파일 4개이며 staged 변경은 없다.
기존 ICT Service/CLI/JSON, S0/D0 설정, 승인 설계 문서의 변경은 없다.
