# Trend Leader — FR-B02b Phase 4A 기록·Phase 4B-1 검토 후보 CLI

Phase 4A FROZEN v1.0의 **로컬 확인 진술·무결성 검증**과
Phase 4B-1 FROZEN v1.0의 **읽기 전용 검증·검토 후보 연결**을 구현합니다.
G5/G6는 HOLD이며 모든 신규 성공 결과의 `publish_authorization`은 `NONE`입니다.
운영 P4 Evidence·권리/신원 인증·게시 도구가 아닙니다.

## 실행 환경과 파일 책임

- Python 3.12 이상, 표준 라이브러리만 사용합니다. 패키지 설치·가상환경·DB·`.env`가 필요하지 않습니다.
- 저장소 루트 `tools/fr_b02b_cli/`에서 실행합니다. 현재 Docker 빌드 문맥 밖에 있습니다.
- `fr_b02b_a1_adapter.py`: A1 v0.2 검사 및 동일 ZIP 바이트에 결속한 안전 표시값.
- `fr_b02b_observation.py`: 로컬 기록·시각·ID·JSON·해시·경로·저장·읽기 검증.
- `fr_b02b_review_candidate.py`: 동일 검증 스냅샷의 연결 필드·로컬 시각을 검토 후보로 반환.
- `fr_b02b_cli.py`: 명령·브라우저·한 번의 확인 입력·출력/종료 코드 연결.
- `validation_report.md`와 아래 v0.3 이력은 **과거 원본 PoC 검증 기록**입니다. 이번 실행 증거로 사용하지 않습니다.

## 자동 테스트

PowerShell, 저장소 루트에서:

```powershell
Push-Location .\tools\fr_b02b_cli
py -3.12 -B -m unittest discover -s tests -v
Pop-Location
```

2026-11-09 구현 당시 기록: Python 3.12.10 **87 tests / OK**.
원본 unittest 51개(어댑터 36, 합성 CLI 15)는 파일 내용까지 그대로 보존했습니다.
신규 36개는 RO-01~11·13~14의 합성 ZIP·취소·상태·시간·변조·경로·저장 실패를 검증합니다.
브라우저/시각은 mock이며 테스트 임시 폴더는 정리됩니다. 실제 관측·승인 증거가 아닙니다.
**RO-12 실제 원문 열람·YES·재검증은 미실행**이며 사용자가 별도로 수행해야 합니다.
위 내용은 4A 구현 당시 기록입니다. 이후 RO-12 성공은 사용자 실행 보고로 확인했으며,
이번 작업에서 실제 원문 열람이나 사용자 관측 기록 검사를 다시 수행한 것은 아닙니다.

2026-11-10 Phase 4B-1 검증: **Python 3.12·3.14 각각 104 tests / OK**.
구현 전 최신 브랜치에서 기존 **90개 / OK**를 재확인했습니다. 이전 README 87개와의 차이는
이미 반영된 Windows junction 2건·rename 경합 1건이며 기존 테스트 파일은 수정하지 않았습니다.
신규 14개는 아래 B41-01~08을 검증합니다. 모두 합성 입력만 사용합니다.

## Phase 4B-1 읽기 전용 검토 후보

원본 A1 ZIP과 **명시적인 기존 `LOCAL-OBS-...` 폴더**를 지정합니다.
최신 기록 자동 선택, 브라우저 실행, 추가 `YES` 입력은 없습니다.

```powershell
Push-Location .\tools\fr_b02b_cli
$a1Zip = Join-Path $env:USERPROFILE 'Downloads\trend_leader_g5_p1_hold_gate_v01.zip'
$recordDir = Join-Path $env:USERPROFILE 'Documents\TrendLeaderLocalObservations\LOCAL-OBS-<기존 UUID4 hex>'
py -3.12 -B .\fr_b02b_cli.py review-candidate --zip $a1Zip --record-dir $recordDir
Pop-Location
```

`-B`는 Python 바이트코드 캐시 파일 생성을 막습니다. ZIP·관측 JSON·인덱스는 읽기만 하며,
별도 실행 기록·후보 파일을 생성하지 않습니다. DB·외부 HTTP·추가 의존성은 사용하지 않습니다.

성공 시 stdout에는 아래 **10개 필드의 JSON 한 개**만 출력하며 종료 코드는 `0`입니다.

- `status=REVIEW_CANDIDATE_HOLD`, `local_evidence_id`
- `trend_ref`, `content_ref`, `review_evidence_id`, `source_url`
- `confirmed_at_utc`, `record_created_at_utc`
- `review_result=HOLD`, `publish_authorization=NONE`

실패 시 stdout은 비우고 stderr에 `BLOCKED: <category>` 한 줄과 종료 코드 `1`을 반환합니다.
범주는 `A1 ZIP validation failure`, `local observation integrity failure`, `local input failure`이며
원시 예외·개인 경로·입력 내용은 오류 메시지에 포함하지 않습니다. 필수 인자 누락은 기존 argparse의
사용 오류/종료 코드 `2`를 유지합니다.

검증 함수가 읽은 같은 ZIP/JSON 바이트의 값만 사용합니다. 마지막 ZIP 재읽기는 변경 감지용이며,
후보 값 추출용으로 JSON을 다시 열지 않습니다. 반환된 시각은 **기존 로컬 시계 기록 문자열 그대로**입니다.
실제 관측자/권한·독립 시각·권리·`ACCEPTED`·운영 Evidence·보호 저장소 등록을 인증하지 않습니다.
`observed_at`, DB `collected_at`, P4 `observation_evidence_ref`를 만들지 않으며 **G5/G6 HOLD**를 유지합니다.
기존 `verify-observation` 결과와 4A 확인 입력 정책은 그대로입니다.

### Phase 4B-1 검증 증거와 인계

기준 브랜치 `feat/phase4b1-review-candidate`, 원격 확인 HEAD
`2e0b530245c85e193f3719d84efaec2943af1eb3`에서 FROZEN v1.0과 기존 코드를 대조했고 충돌은 없었습니다.
새 명령 미구현으로 실패하는 테스트를 먼저 확인한 뒤 내부 검증 결과 공유·후보 어댑터·CLI를 구현했습니다.

| 기준 | 자동 검증 내용 |
|---|---|
| B41-01 | 정확한 단일 후보 필드, 검증 후 JSON 교체 시 기존 검증 값 사용, 4A 공개 결과 유지 |
| B41-02 | 네 바인딩 필드 각각 불일치 시 재해시해도 차단 |
| B41-03 | 기록/인덱스 누락·손상·해시·ID·ZIP 지문·시간·미승인 상태 차단, 자동 복구 없음 |
| B41-04 | 잘못된 ZIP·검증 중 ZIP 변경 차단, 입력 보존 |
| B41-05 | 반복 조회 결과·ID·기록 시각 동일, 새 UUID/시계 호출 없음 |
| B41-06 | HOLD/NONE·미인증/로컬 시계 의미 유지, 운영 필드 승격 없음 |
| B41-07 | 성공/실패 입력 바이트·수정 시각 보존, 별도 프로세스 audit로 파일 변경·네트워크·DB 연결 경로 차단 |
| B41-08 | 프롬프트/브라우저 없음, 공백 포함 경로 지원, 간결한 오류와 개인 경로/입력 비노출 |

실행 명령(위 CLI 디렉터리에서):

```powershell
py -3.14 -B -m unittest discover -s tests -p test_fr_b02b_review_candidate.py -v
# 14 tests / OK
py -3.14 -B -m unittest discover -s tests
# 104 tests / OK
py -3.12 -B -m unittest discover -s tests
# 104 tests / OK
```

새 명령의 별도 프로세스 성공/실패 실행도 합성 입력으로 검증했습니다. 실제 RO-12 원본에 대한
이 명령 실행은 미실행이며 위 PowerShell 명령으로 별도 확인할 수 있습니다. 실제 기록은 Git에 추가하지 않습니다.
Ruff는 검증 환경에 설치되어 있지 않아 정적 검사를 실행하지 않았습니다.

PR 준비 제목: `feat: 실데이터 출처 확인 기록 자동 검증·연결 (Phase 4B-1)`.
기존 설계 문서와 이번 CLI·검증·README 변경을 **같은 기능 브랜치의 단일 PR**로 통합합니다.
4B-2 신원·권한/수락·보호 저장소 등록과 P4 Writer·게시·DB 쓰기는 후속 범위입니다.

## 신규 명령과 사용자 Windows Acceptance (RO-12)

아래는 사람이 실행할 절차입니다. 자동 테스트나 Codex가 실제 원문 확인을 대신하지 않습니다.
`$a1Zip`은 원본 ZIP, `$recordRoot`는 **어떤 Git 작업 트리에도 속하지 않는** 개인 폴더로 지정합니다.
예시 폴더가 실제로 Git 외부인지 CLI가 다시 검사하며 symlink·junction 등 재분석 지점 경로는 차단합니다.

```powershell
Push-Location .\tools\fr_b02b_cli
$a1Zip = Join-Path $env:USERPROFILE 'Downloads\trend_leader_g5_p1_hold_gate_v01.zip'
$recordRoot = Join-Path $env:USERPROFILE 'Documents\TrendLeaderLocalObservations'
py -3.12 -B .\fr_b02b_cli.py observe-a1-zip --zip $a1Zip --output-dir $recordRoot

# 위 명령이 출력한 LOCAL-OBS-... ID를 직접 지정합니다. 잔재를 자동 선택하지 않습니다.
$recordDir = Join-Path $recordRoot 'LOCAL-OBS-<출력된 UUID4 hex>'
py -3.12 -B .\fr_b02b_cli.py verify-observation --zip $a1Zip --record-dir $recordDir
Pop-Location
```

1. 승인된 제목·설명·출처 안내·HTTPS URL을 확인하고 열린 브라우저에서 대상과 내용을 직접 확인합니다.
2. **지금 새 출처 근거로 확인·채택**할 때만 대문자 `YES`를 한 번 입력합니다.
   단순 링크 재확인, 내용 변경, URL 불일치, 의심스러운 리디렉션은 취소합니다.
   `yes`, `Yes`, 공백이 붙은 입력, EOF, Ctrl+C는 승인으로 바꾸지 않습니다.
3. 생성 결과 `LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD`와 검증 결과 `PASS_LOCAL_INTEGRITY_ONLY`,
   두 결과의 `publish_authorization=NONE`을 확인합니다. 원본 ZIP은 수정되지 않아야 합니다.
4. 실제 실행 Python/Windows 버전, 성공/실패 상태, 사용자 수행 여부를 별도로 기록합니다.
   아직 하지 않은 RO-12를 완료로 표시하지 않으며 실제 기록·전체 승인 자료·개인 경로는 Git에 올리지 않습니다.

| 종료 코드 | 의미 |
|---|---|
| 0 | 로컬 확인 기록 저장·재검증 또는 읽기 전용 무결성 검사 성공. 운영 승인 아님 |
| 1 | `BLOCKED`: 입력·ZIP·브라우저·시각·경로·저장·검증 실패 |
| 2 | `CANCELLED`: 정확한 YES 미입력/EOF/Ctrl+C, 또는 필수 인자 사용 오류 |

`observation.json`과 `index.json`은 정확한 FROZEN 스키마·canonical UTF-8 JSON + LF 1개를 사용합니다.
기존 A1 `content_ref`와 기존 합성 기록의 해시/스키마는 변경하지 않습니다.
신규 기록 ID는 `LOCAL-OBS-<uuid4-hex>`이며 `review_result=HOLD`입니다.

## 실패·신뢰 경계

- ZIP은 제한 크기로 읽기만 하며, 알려진 JSON 2개만 파싱합니다. 추출·내부 Python 실행·HTTP 수집을 하지 않습니다.
- 브라우저 성공 반환은 열람 성공이 아닙니다. 시각은 YES 직후 로컬 시스템 시계이며 독립 타임스탬프가 아닙니다.
- 확인 중/기록 확정 전 ZIP 변경을 차단하고, 검증 때 다시 ZIP·스키마·참조·해시·상태·시간을 대조합니다.
- 입력 ZIP 밖의 철회 사실은 자동 발견하지 못합니다. 철회/변경을 알고 있다면 취소하고 승인 자료를 별도 재검토해야 합니다.
- 기존 ID를 덮어쓰지 않습니다. 저장 실패의 `.obs-staging-*` 또는 최종 디렉터리는 **수동 조사 대상 HOLD**입니다.
  오류 종료 시 성공한 기록으로 사용하거나 자동 재개·승격·수정하지 않습니다.
- `GIT_DIR`·`GIT_WORK_TREE`·`GIT_COMMON_DIR`이 지정돼 경로 소속을 확정할 수 없는 실행 문맥도 차단합니다.
  CLI가 환경변수를 수정하지는 않습니다.
- `verify-observation`은 파일을 고치거나 누락 파일을 다시 만들지 않습니다. 해시가 일치해도 신원·권리·진짜 열람을 인증하지 않습니다.
- SHA-256은 서명이 아닙니다. 두 파일을 함께 일치하게 재작성한 공격, 모든 TOCTOU·다중 프로세스 경쟁,
  크래시 일관성·디렉터리 fsync·ACL·백업·운영 보호 저장소를 보증하지 않습니다.
- P4 `observation_evidence_ref`, DB `collected_at`, Writer 및 G5/G6 PASS 연결은 범위 밖입니다.

## v0.3 원본 README 이력

이하 내용은 편입 전 v0.3의 범위·검증 이력입니다. 현재 신규 명령·미실행 항목은 위 설명을 기준으로 합니다.

> **검토용 / P4 NOT FROZEN / G5·G6 HOLD / 게시 기능 없음**
> 기준: 2026-11-09. Python 표준 라이브러리만 사용. Docker/DB/네트워크/앱 설정 불필요.

## 0. 이번 수정의 이유와 검증 근거

실제 `trend_leader_g5_p1_hold_gate_v01(2).zip`의 `trend_leader_g5_a1_approval_reconcile_v02.py`, Python 3.15 승인 매니페스트와 Batch 후보를 **원본 그대로 확인**했다.

**v0.2의 잘못된 가정:** `batch.items[]`에 `content_ref`, `review_evidence_id`가 들어 있다고 간주했다. 원본 A1 v0.2에서는 이 두 필드가 **`approvals.records[]`에만** 있고, Batch item은 `trend_ref`, `content`, `source_title_origin`의 세 키만 가진다.

**v0.3:** 실제 파일 구조에 맞게 읽기 전용 어댑터와 합성 Fixture를 변경했다. 원본 A1 입력을 보정·변환·재저장하지 않는다. G4 실승인 판단, 권리 확인, 관측 증거, G6 승인은 어떤 경우에도 자동 승격하지 않는다.

### 원본과의 직접 비교 (실제 실행)

- 원본 A1 검사기 `--self-test`: 합성 16건 및 안전 중단 자체 시험 **PASS**.
- 원본 A1 검사기 `--check` + 첨부된 실제 Python 3.15 두 JSON: **`ELIGIBLE_FOR_REVIEW_ONLY`, 잠재 적격 1건, 게시 허가 0건**.
- 본 CLI의 같은 실제 두 JSON `inspect-a1`: **`A1_STRUCTURE_MATCH_REVIEW_ONLY`, `a1_reconcile_reason=ELIGIBLE_FOR_REVIEW_ONLY`, 게시 허가 `NONE`**.
- 본 CLI의 원본 ZIP 직접 입력 `inspect-a1-zip`: 위와 동일한 결과. ZIP 추출·ZIP 안의 `.py` 실행·파일 변경 없음.
- 자동화된 PoC 단위 테스트: **51건 PASS**, 원본 형식을 재현한 **합성 Fixture만** 테스트 패키지에 포함.

**정확한 의미:** 이 PoC는 A1 전체 대조기를 복제하지 않는다. Batch **1건·적격 후보**만 검사하고 부적격 항목은 `BLOCKED`로 종료한다. 원본 대조기의 다건 후보별 `EXCLUDE` 상세 보고까지 1:1로 재현하지 않는다. 원본 대조기보다 엄격한 입력 안전 검사(중복 JSON 키/URL fragment 금지/문자 제한 등)도 있어 모든 예외 사례에서 판정 일치를 보장하지 않는다. 따라서 운영용 A1 검증기의 대체물이 아니다.

## 1. Windows PowerShell에서 최소 확인

새 ZIP을 `trend_leader_fr_b02b_cli_poc_v03` 폴더에 압축 해제한 뒤 해당 폴더에서:

```powershell
# 테스트 (실제 A1 파일 필요 없음)
python -m unittest discover -s tests -v

# 원본 ZIP 하나만 지정: 별도 압축 해제 불필요
$g5zip = Join-Path $env:USERPROFILE 'Downloads\trend_leader_g5_p1_hold_gate_v01(2).zip'
python .\fr_b02b_cli.py inspect-a1-zip --zip $g5zip
```

정상 결과의 주요 필드:

```json
{
  "status": "A1_STRUCTURE_MATCH_REVIEW_ONLY",
  "a1_reconcile_reason": "ELIGIBLE_FOR_REVIEW_ONLY",
  "a1_potentially_eligible": 1,
  "a1_authorized_to_publish": 0,
  "publish_authorization": "NONE",
  "g4_authenticity_verified": false,
  "rights_verified": false,
  "observation_evidence_verified": false
}
```

위 출력은 *구조·해시·입력 필드의 일치*만 뜻한다. 해당 원본 ZIP은 재배포 ZIP에 **포함하지 않았다**. 로컬 ZIP 이름이 다르면 `$g5zip`에 해당 파일의 실제 이름을 입력한다.

### 원본 검사기 명령과 따로 대조하려면 (선택)

원본 G5 ZIP을 이미 풀어 `g5_p1_hold_v01` 폴더가 있을 때에만:

```powershell
$g5 = Join-Path $env:USERPROFILE 'Downloads\g5_p1_hold_v01'
python .\fr_b02b_cli.py inspect-a1 `
  --approvals (Join-Path $g5 'python315_approval_manifest_RECONFIRMED_v02.json') `
  --batch (Join-Path $g5 'python315_batch_candidate_REVIEW_ONLY_v02.json')
```

필요하지 않다면 이 단계는 생략 가능하다. 두 경로의 원본 JSON을 읽을 뿐이다.

## 2. 기존 합성 관측 기능 (v0.1부터 유지)

```powershell
python .\fr_b02b_cli.py inspect --fixture .\fixtures\synthetic_approval.json
python .\fr_b02b_cli.py simulate --fixture .\fixtures\synthetic_approval.json --output-dir .\sim_results
# 질문에 대문자 YES 입력 시에만 SIMULATION_ONLY 기록 생성

$recordDir = Get-ChildItem .\sim_results -Directory |
  Where-Object { $_.Name -like 'SIM-OBS-*' } |
  Sort-Object LastWriteTimeUtc -Descending |
  Select-Object -First 1
python .\fr_b02b_cli.py verify --fixture .\fixtures\synthetic_approval.json --record-dir $recordDir.FullName
```

이 기능은 `https://example.test/...` 합성 입력만 허용한다. 진짜 Python 3.15 출처를 열거나 실제 관측·공식 승인·게시 기록을 생성하지 않는다. `PASS_SIMULATION_ONLY`도 실제 증거 적격 판정이 아니다.

## 3. 파일과 책임 범위

| 구성 | 책임 |
|---|---|
| `fr_b02b_cli.py` | `inspect`, `simulate`, `verify` 및 A1 읽기 전용 명령 라우팅 |
| `fr_b02b_a1_adapter.py` | 원본 A1 v0.2의 단일 Batch item 구조·승인 레코드·해시 대조 및 ZIP의 특정 JSON 파일만 읽기 |
| `fixtures/` | 합성 입력만 포함. 실제 승인자/콘텐츠 사본 미포함 |
| `tests/` | 원본 구조 합성 Fixture와 안전 중단 검증, 기존 시뮬레이션 회귀 |
| `validation_report.md` | 실제 입력과 단일 후보 판정 대조, 원본 파일 해시·범위 기록 |

`inspect-a1` / `inspect-a1-zip`는 파일을 쓰거나 외부 URL로 요청하지 않는다. ZIP 내부 Python 코드는 실행하지 않는다. 관련 권한·원본 증거를 **인증한 것이 아니며**, 신규 시점·권리·G4/G6 상태를 만들어내지 않는다. 두 기능은 `observation_evidence_ref` 자체를 생성하거나 P4 Writer로 넘기지 않는다.

## 4. 인프라 통합과 별개의 남은 작업

- **이번에 확인:** 실제 A1 v0.2 입력 형식과 SHA-256 기준, Python 3.15 사례에 대한 읽기 전용 호환성.
- **미확인:** 신뢰 가능한 관측 증거 시각 및 인간 확인, 독립 보호 저장소·권한·검토자, Writer와 FR-B04 철회 경계, 실제 운영 G5/G6.
- **다음 단계:** `inspect-a1-zip`의 결과를 실제 관측 도구의 *읽기 전용 입력 어댑터*로 재사용할 수 있으나, 관측/검토/영속 저장/추가 권한 검증은 별도 설계·테스트 후 연결한다.

팀원의 **설정 화면 UI/기능 작업**과 무관하다. `.env`, Docker Compose, DB, GitHub 프로젝트 파일은 변경하지 않았다.
