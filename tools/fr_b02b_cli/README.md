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
- `docs/history/validation_report.md`와 아래 v0.3 이력은 **과거 원본 PoC 검증 기록**입니다. 이번 실행 증거로 사용하지 않습니다.

## Phase 4B-2 최소 연결 — 등록 기능 미완료

`review-register --zip <A1 ZIP> --record-dir <LOCAL-OBS 폴더>`는 현재
기존 4A 입력의 읽기 전용 재검증 → Windows 프로세스 토큰 SID 조회 → 허용 목록 검증 → 명시적 검토 결정을 연결합니다.
`fr_b02b_review_service.py`가 실패 정책을 소유하고,
`fr_b02b_windows_auth.py`가 `TokenUser` SID를 조회하며,
`fr_b02b_reviewer_allowlist.py`가 허용 목록 검증을 담당합니다. 추가 의존성은 없습니다.

SID 조회 실패/누락은 stderr의 `BLOCKED: reviewer identity unavailable`과 종료 코드 `1`로
차단합니다. 원시 예외·SID·개인 경로를 오류에 출력하지 않습니다. SID 조회가 성공해도
사전 관리되는 운영 허용 목록 설정·실제 ACL 검증기는 아직 미확정이므로
`BLOCKED: protected review registration is not configured`와 종료 코드 `1`을 반환합니다.
필수 인자 누락은 argparse 종료 코드 `2`입니다.

2026-11-10 사용자 결정에 따라 운영 허용 목록의 물리 경로·관리 책임은 이 단위에서 정하지
않습니다. `managed_allowlist_source()`는 항상 설정 미완료로 차단하며 경로를 추측하지 않습니다.
합성 테스트에서만 내부 `AllowlistSource`에 절대 경로와 보호 검증 대역을 주입합니다.
CLI에는 SID·허용 목록 경로·ACL 우회 옵션을 제공하지 않으며 `USERNAME`을 인증에 사용하지 않습니다.
설정 공급자 자체의 접근 오류도 `BLOCKED: reviewer allowlist unavailable`로 차단하며 원시 예외를 출력하지 않습니다.

현재 내부 입력 형식은 65,536바이트 이하 UTF-8 JSON이며 최상위 키는 정확히
`schema=FR_B02B_REVIEWER_ALLOWLIST_V1`, `reviewers`입니다. 각 항목은 정확히
`sid`(SID 문자열), `active`(JSON boolean), `role=EVIDENCE_REVIEWER`를 가집니다.
중복 JSON 키·중복 SID·미정의/누락 필드·잘못된 타입/역할/형식은 차단합니다.
등록되지 않거나 비활성인 SID는 차단합니다. 보호 검증은 파일 및 상위 경로를 소유하는
내부 의존성의 책임이며, 정확한 `True`가 아닌 결과나 예상 가능한 운영 오류는 차단합니다.
프로그래밍 오류는 Allowlist/Service에서 권한 오류로 변환하지 않습니다. CLI의 최외곽에서만
`BLOCKED: internal review failure (<예외 종류>)`와 종료 코드 1로 구분하며 원시 진단은 출력하지 않습니다.
파일 읽기 전후 보호 상태와 열린 파일/경로의 식별자·크기·수정 시각을 대조합니다.
이 검사는 실제 Native ACL·잠금 기반 보호 읽기의 실증을 대체하지 않습니다.

허용 목록 검증 이후에는 검증된 제목·요약·출처 URL·기존 확인/생성 시각·관측자 미인증 수준을
표시하고 `ACCEPTED`/`HOLD`/`REJECTED`를 명시적으로 선택받습니다. 대소문자·앞뒤 공백은
정규화하되 기본 선택은 없고 `YES`는 검토 결정으로 처리하지 않습니다. 사유는 최대 500자이고
HOLD/REJECTED에서 비공백 필수, ACCEPTED에서 선택입니다. 사유 앞뒤 공백은 저장 전 내부 값에서 제거합니다.
빈 선택·EOF·Ctrl+C는 `CANCELLED`/2, 잘못된 선택·사유·시계는 `BLOCKED`/1입니다.
기존 4A의 정확한 YES 입력 정책에는 이 정규화를 적용하지 않습니다.

Service의 `PendingReviewDecision`은 검증된 원본 바이트와 사람의 판단을 메모리에서만 연결합니다.
결정 이후 측정한 로컬 UTC를 reviewed_at_utc로 사용하고, 입력 전 시각/4A 생성 시각보다 빠르면 차단합니다.
등록 ID 발급, Store 등록, 백업·철회는 아직 없습니다. ACCEPTED도 보호 등록 완료가 아니므로
검토 입력 이후 CLI는 여전히 `BLOCKED: protected review registration is not configured`/1로 종료합니다.
4A·4B-1 공개 계약을 유지하며 게시 권한을 부여하지 않습니다.
운영 설정이 없는 실제 CLI는 미리보기/검토 입력 전 차단됩니다. 합성 테스트의 보호 검증 성공은
운영 접근통제 완료 증거가 아닙니다. 운영 경로, 초기 등록 담당자, 변경·폐기 책임,
실제 ACL·보호 저장·C/E 복원 검증은 Protected Store 통합 및 Windows 시험 대상입니다.

2026-11-10 SID 조회 실패 단위의 Python 3.14 검증은 **107 tests / OK**였습니다(기존 104개 + 신규 3개).
최소 연결 후 SID 실패 대역의 미처리 `OSError`로 Red를 확인하고, Service의 차단 처리 후
기존 CLI 테스트와 Service 독립 테스트를 Green으로 확인했습니다. SID 실패 시 프롬프트·Store
등록·UUID 생성 0회와 합성 원본 바이트·HOLD/NONE 불변을 검사했습니다. 실제 프로세스 토큰 SID도
로컬 `whoami /user` 결과와 메모리에서 대조하여 일치를 확인했으며 SID 값은 출력·보관하지 않았습니다.
이후 허용 목록 단위에서 **118 tests / OK**를 확인했습니다(기존 107개 + 허용 목록 9개 + Native 경계 2개).
허용 목록 미구현/미연결로 Red를 확인한 뒤, 합성 파일 기반 허용 SID·미등록/비활성 SID·목록 누락/
손상·보호 검증 실패를 각각 Green으로 확인했습니다. Native 경계 테스트는 성공 및 6개 장애
지점의 반환값·타입·메모리/토큰 해제를 대역으로 검증합니다. 실제 SID 조회 코드는 수정하지 않았습니다.
Windows 경로/핸들의 `st_ctime_ns` 차이에 따른 정상 파일 오탐은 파일 식별자·크기·수정 시각
대조로 수정하고 회귀 테스트를 추가했습니다. 실제 운영 ACL/권한 시험은 아직 수행하지 않았습니다.
Ruff는 미설치로 실행하지 않았으며, unittest 통과를 정적 검사 완료로 간주하지 않습니다.

2026-11-10 B42-04 단위: Python 3.14 전체 **129 tests / OK**(기존 118개 + 리뷰 회귀 1개 + 결정 10개).
기존 Allowlist 테스트의 허용 SID 사례만 새 검토 프롬프트 동작에 맞게 갱신했고,
인증 실패 시 프롬프트 0회·모든 Store/ID 생성 차단 검사는 유지했습니다.
상세 리뷰, Red 출력, 검증 범위는 [B42-04 검토·검증 보고서](docs/phase4b2/phase4b2_b42_04_review.md)에 기록합니다.

## 저장 직전 재검증·합성 HOLD 스테이징 — 운영 등록 아님

운영 최소 계약 보완과 Windows 읽기 전용 실측은
[운영 보호 저장소·ACL DRAFT v0.2](../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.2_DRAFT_20261110.md)에 기록합니다.
ProgramData는 우선 검증 방향이며 경로·책임자·권한 마스크는 미확정입니다.
`diagnostics/phase4b2_environment_readonly.py`와 `diagnostics/phase4b2_storage_readonly.ps1`는 비식별 조회 전용이며
운영 CLI에 연결되지 않습니다. 조회 성공은 실제 ACL·등록·백업/복원 PASS가 아닙니다.

`stage_pending_review()`는 내부 합성 시험 진입점입니다. 실제 CLI에는 Store 설정이 없으므로
기존처럼 Fail-Closed하며 임의 루트/ACL 우회 옵션을 제공하지 않습니다.
Service는 현재 ZIP·관측 JSON·인덱스를 재검증하고 검토 당시의 바이트/표시값과 정확히 대조합니다.
현재 SID·Allowlist·시계·판단 필드도 재검증하며, 중간 입력/권한 변경을 복사 전후에 다시 확인합니다.

신규 `fr_b02b_protected_store.py`는 합성 임시 루트와 명시적인 보호 검증 대역을 받아
`.review-staging-<LOCAL-OBS ID>/`를 배타 생성합니다. 같은 ID의 기존 디렉터리는 재사용하지 않습니다.
`a1_archive.zip`, `observation.json`, `index.json`, `pending_review.json`만 신규 배타 쓰기하고
flush/fsync 후 파일 목록·저장 바이트·보호 경계를 재검사합니다. Store는 전달된 객체의 이름만
신뢰하지 않고 A1·4A 검증기와 내부 메타데이터 지문 연결을 독립적으로 재검증합니다.

`pending_review.json`은 임시 내부 판단/세 입력 해시 연결이며 FROZEN의 `registration.json`이 아닙니다.
반환값은 항상 `StagedReview(state=HOLD, publish_authorization=NONE)`입니다.
등록 ID, 등록 매니페스트, `registration_complete.json`, 유효 등록 성공을 생성하지 않습니다.
실패 잔재는 조사 대상 HOLD로 남기며 자동 삭제·복구·재해시·승격하지 않습니다.

Python 3.14에서 신규 15개 테스트와 기존 129개를 포함해 **144 tests / OK**를 확인했습니다.
실제 Windows 임시 파일 생성·배타 쓰기·재읽기·fsync·심볼릭 링크·junction 차단을 실행했습니다.
SID·Allowlist 보호·루트 ACL 판정과 쓰기/권한 장애는 합성 대역입니다. 실제 운영 경로·관리 책임·
Native ACL/잠금, 모든 적대적 경합, C/E 백업·재시작·철회는 검증되지 않았습니다.
fsync와 개별 파일 생성만으로 전원 장애 내구성 또는 C/E 원자성을 주장하지 않습니다.
[검토·검증 보고서](docs/phase4b2/phase4b2_staging_review.md)를 제공합니다. Store·핵심 테스트 diff인 `phase4b2_staging_code_and_tests.patch`는 과거 로컬 검토 산출물로 보존하며 Git 커밋에는 포함하지 않습니다.

후속 후보 검토에서 A1 archive_bytes의 타입·20 MiB 상한이 공유 A1 검증기에 이미 있음을 확인하고,
6개 잘못된 입력을 ZIP 파싱/쓰기 전에 거절하는 회귀 1개를 추가했습니다. Python 3.14 전체
**145 tests / OK**이며 런타임 소스 수정은 없습니다. Service 콜백의 동일 바이트·SID·Allowlist·
시각 재검증도 확인했습니다. [운영 보호 저장소·Windows ACL 후보안](../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.1_DRAFT_20261110.md)은
설계 검토 전용이며 운영 경로·ACL·Allowlist를 생성/변경하지 않습니다. 기존 staging patch는
144개 단계의 검토 기록으로 보존했습니다. 이번 회귀 추가의 최신 diff는 현재 테스트 파일을 기준으로 봅니다.

## 독립 ACL 실험 도구 위치

ACL 하네스 4개는 `labs/phase4b2_acl/`에 있습니다. 기존 CLI·Protected Store에는 연결하지 않습니다.
저장소 루트의 PowerShell에서 기본 계획 출력만 확인하는 명령은 다음과 같습니다.

```powershell
python -B .\tools\fr_b02b_cli\labs\phase4b2_acl\phase4b2_acl_harness.py plan
```

다른 작업 디렉터리에서는 하네스 파일의 절대 경로를 사용합니다. 자식 worker도 `__file__` 기준
같은 폴더의 하네스 절대 경로를 사용하며, 별도 cwd 시험 계약을 유지합니다.
`tools/fr_b02b_cli/`에서는 `python -B -m labs.phase4b2_acl.phase4b2_acl_harness plan`도 사용할 수 있습니다.
기본 plan은 Native를 생성하지 않고, 승인 플래그 없는 SYN 명령은 기존처럼 차단합니다.
실제 ACL/SYN 시험에는 별도 실행 승인이 필요하며 디렉터리 이동으로 승인되지 않습니다.
[하네스 검토 기록](docs/phase4b2/phase4b2_acl_harness_review.md)과
[preflight 검토 기록](docs/phase4b2/phase4b2_acl_preflight_review.md)의 과거 실행 결과·소스 manifest·패치는 당시 기록입니다.

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
| `docs/history/validation_report.md` | 실제 입력과 단일 후보 판정 대조, 원본 파일 해시·범위 기록 |

`inspect-a1` / `inspect-a1-zip`는 파일을 쓰거나 외부 URL로 요청하지 않는다. ZIP 내부 Python 코드는 실행하지 않는다. 관련 권한·원본 증거를 **인증한 것이 아니며**, 신규 시점·권리·G4/G6 상태를 만들어내지 않는다. 두 기능은 `observation_evidence_ref` 자체를 생성하거나 P4 Writer로 넘기지 않는다.

## 4. 인프라 통합과 별개의 남은 작업

- **이번에 확인:** 실제 A1 v0.2 입력 형식과 SHA-256 기준, Python 3.15 사례에 대한 읽기 전용 호환성.
- **미확인:** 신뢰 가능한 관측 증거 시각 및 인간 확인, 독립 보호 저장소·권한·검토자, Writer와 FR-B04 철회 경계, 실제 운영 G5/G6.
- **다음 단계:** `inspect-a1-zip`의 결과를 실제 관측 도구의 *읽기 전용 입력 어댑터*로 재사용할 수 있으나, 관측/검토/영속 저장/추가 권한 검증은 별도 설계·테스트 후 연결한다.

팀원의 **설정 화면 UI/기능 작업**과 무관하다. `.env`, Docker Compose, DB, GitHub 프로젝트 파일은 변경하지 않았다.
