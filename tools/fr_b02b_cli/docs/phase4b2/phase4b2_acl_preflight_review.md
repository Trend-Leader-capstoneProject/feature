# Phase 4B-2 ACL 하네스 소스 안전성 재검토·읽기 전용 Preflight

> 2026-11-10 KST / 실행 승인 전 검토 기록
> 브랜치: `feat/phase4b2-protected-review-registration`
> 로컬 및 읽기 전용 원격 조회 HEAD: `b133b494f8258eea603243f8f07191a33290084a`
> **실제 SYN-01·02·05 미실행. 운영 ACL/Store I/O PASS 또는 보호 등록 성공 아님.**

기준은 [4B-2 FROZEN](../../../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md), [운영 DRAFT v0.2 §2.1·§4.1·§6.1](../../../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.2_DRAFT_20261110.md), AGENTS.md v1.1 및 AI 개발/GitHub Write 지침이다. [이전 182개 준비 보고](phase4b2_acl_harness_review.md)는 당시 기록으로 보존한다.

## A. 실제 코드 리뷰 발견 사항

검토한 범위는 하네스 4개 소스와 핵심 테스트 2개다. **Critical/High 결함 또는 Preflight의 변경 API 도달 경로는 발견하지 않았다.** 아래 중간 결함은 기본 CLI의 plan/preflight에서 도달하지 않는 내부 직접 호출 경계였으며, 실제 Preflight 전에 수정했다. 위치는 수정 후 코드 기준이다.

| 심각도/ID | 근거 파일·위치 | 재현 조건 | 영향 | 최소 수정 |
|---|---|---|---|---|
| 중간 M-01 | `phase4b2_acl_harness.py:17`, `phase4b2_acl_lab.py:435`, `phase4b2_acl_process.py:36`·`:63` | worker 함수를 직접 호출하거나 승인/변경 capability 없는 Processes에서 spawn 호출 | CLI 검사와 달리 worker가 Native 조회에 도달하고, 프로세스 경로는 Native 변경 검사보다 Popen이 먼저 실행될 수 있었음 | worker/child_main의 approved 기본 False, Processes의 명시적 의사·Native capability 검사를 Popen/종료 전에 수행 |
| 중간 M-02 | `phase4b2_acl_process.py:170` | 자신이 시작한 hold 자식을 인증된 PARTIAL_READY처럼 제시 | 기존 PID/생성 시각/nonce/소유 목록 검사는 있었으나 P3의 crash 역할·지정 객체 자체가 명시되지 않음 | 생성 mode와 단일 crash_child를 결속. 둘 다 일치해야 종료. crash 시작 시도는 실패해도 소비하고 재시도 금지. 기존 종료 재요청 금지 유지 |
| 낮음 L-01 — 진단 누락 | `phase4b2_acl_lab.py:200` | preflight 실행 | 기존 구현이 토큰을 조회하지 않고 부분 실패 사실을 구분해 출력하지 못함 | TOKEN_QUERY 추가, 비승격/대상 특권·Known Folder/조상/루트 상태를 bool 또는 null로만 보고. 예상 Native 실패도 HOLD와 부분 사실로 반환 |

M-01은 임의 Python 코드를 실행하는 계정으로부터의 독립 보안 경계를 뜻하지 않는다. `approved=True` 및 실행 플래그는 실행 의사 표현이며 외부 사용자 승인 증명이 아니다. 같은 계정이 코드를 수정하는 위협의 한계는 유지한다. 실제 SYN 실행 승인은 여전히 별도다.

### 부작용·경로·출력 검토 근거

- import는 상수/함수/타입 정의만 한다. Win32 생성은 시스템 DLL 로드·함수 선언 연결만 하며 파일 생성/보안 setter/자식 실행을 호출하지 않는다. Processes 생성도 Popen을 호출하지 않는다. 검토·시험 명령은 `-B`를 사용해 Python bytecode cache 쓰기도 억제했다.
- `plan`은 Native를 생성하지 않는다. `preflight`는 플래그를 함께 주더라도 **allow_changes=False**다. process factory/worker 경로에 진입하지 않는다.
- Preflight는 TOKEN_QUERY, Known Folder flags=0, C:/ProgramData 조상의 OPEN_EXISTING(READ_CONTROL|FILE_READ_ATTRIBUTES), 동일 핸들의 ID/최종 경로/설명자 조회, 후보 GetFileAttributes와 메모리/핸들 해제로 한정된다. 보안 설명자 공급 포인터 NULL, DELETE/WRITE 요청 및 DELETE_ON_CLOSE 없음. close가 파일 삭제로 이어지는 경로 없음.
- 고정 루트 외 입력/임의 SID/경로/환경변수 우회 옵션이 없다. 초기 생성은 충돌 시 재사용하지 않는다. reparse·최종 경로/ID·SID/owner/DACL/상속 불일치는 HOLD다. 조상 교체 방어의 적대적 경합 시험은 미실행이다.
- 신규 파일에 제한 설명자를 공급하고 실제 설명자를 확인한 뒤 private 값을 쓴다. 인벤토리를 읽기 전에 고정 코드의 owner/ACE 정책을 대조하고, 같은 핸들로 읽은 후 실제 ID/Config 바이트를 대조한다. 인벤토리의 자기 주장만 믿지 않는다.
- 정상 Gate 해제는 자기 생성 동일 핸들의 ID/설명자를 확인한 뒤 삭제 예약→close다. 실패는 자동 경로 삭제/ACL 수리 없이 HOLD다. 삭제 예약 이후 중단이면 Gate 부재 가능성이 있으므로 부재만으로 완료를 추정하지 않는다.
- 종료는 명시적 실행 의사·변경 capability·자기 목록·단일 지정 P3·crash mode·인증된 phase·PID·생성 시각을 모두 요구한다. Native 호출 전 TERMINATION_REQUESTED로 바꿔 불확실한 결과에서도 재종료하지 않는다.
- 공개 출력은 고정 상태/범주·숫자 오류 코드와 사전 검사 bool/null whitelist뿐이다. SID·SDDL·실제 nonce/PID/개인 경로·원시 예외는 공개 출력하지 않는다. worker의 식별 자료는 캡처된 private IPC이며 공개 stdout 결과와 구분한다. 시험 로그에 쓰는 SID는 합성 값이다.

### Native 계약 재대조

CreateFileW는 HANDLE/INVALID_HANDLE_VALUE, BOOL API는 0/비0, GetSecurityInfo는 반환 DWORD 오류로 구분한다. 가변 버퍼 길이·포인터 수명·ACE 경계를 확인하고 SID 문자열/보안 설명자는 LocalFree, Known Folder 문자열은 CoTaskMemFree, 토큰/파일/프로세스 핸들은 CloseHandle로 해제한다. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation), [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo).

Mock ABI 검사에서 FILE_DISPOSITION_INFO의 BOOLEAN=1바이트, FILE_ID_INFO=24바이트, BY_HANDLE_FILE_INFORMATION=52바이트, WIN32_FIND_DATAW=592바이트, SECURITY_ATTRIBUTES 크기 및 FILE_RENAME_INFO 이름 offset을 확인했다. rename은 no-replace·UTF-16 바이트 길이·NUL 종료, 정상 삭제 예약은 같은 핸들의 DELETE 접근이 전제다. 이 변경 API들은 실제 호출하지 않았다. [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info), [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle).

기존 Native 어댑터에서 새로 수정해야 할 선언/자원 해제 결함은 찾지 못했다. Native 소스 본문은 이번에 바꾸지 않았다. 미지원 ACE/API는 HOLD이며 대체 경로·자동 수리하지 않는다.

## B. 최소 수정과 Red → Green

수정 파일은 `phase4b2_acl_harness.py`, `phase4b2_acl_lab.py`, `phase4b2_acl_process.py`, `tests/test_phase4b2_acl_lab.py`, `tests/test_phase4b2_acl_native.py`다. 기존 worker 정상 흐름 테스트는 명시적 approved=True로 호출 의사를 표시하도록 조정했으며 원래 검증 항목을 제거하지 않았다.

먼저 5개 반례를 추가한 테스트 실행에서 29개 중 failures=4/errors=2를 관찰했다(하위 사례 포함). 핵심 출력은 다음과 같다. 실제 OS 자식 생성/종료를 실행한 것이 아니며 Popen 자체도 대역이었다.

```text
test_direct_worker_entries_require_explicit_execution_intent
  AssertionError: worker reached Native without intent
test_process_start_requires_intent_and_write_capability_before_popen
  AssertionError: unapproved child start
test_a_non_crash_worker_cannot_be_terminated_as_p3
  AssertionError: Hold not raised
test_preflight_queries_token_and_only_reports_safe_facts
  KeyError: 'preflight'
test_preflight_native_failure_reports_partial_facts_without_mutation
  NativeFailure: NATIVE_FAILURE
```

최소 수정 후 위 반례와 추가 P3 재시도 금지·Preflight 충돌·실행 플래그 무효화·읽기 전용 Native 호출 경로를 검증했다.

| 실행 명령/검사 | 실제 결과 |
|---|---|
| `python -B -m unittest discover -s tests -q` (`tools/fr_b02b_cli`) | **Python 3.14.0 / 190개 / 8.609초 / OK**. 기존 182개 사례 + 신규 8개 |
| 하네스 테스트 구성 | 정책/CLI/프로세스 메모리 31개 + Native DLL 대역/ABI 14개 = 45개. 종전 145개와 합계 190개 |
| Ruff 모듈 사용 가능 여부 | 미설치·미실행. unittest/AST를 Ruff PASS로 표현하지 않음 |
| AST/공백/로컬 링크 및 패치 원문 대조 | 성공. 6개 파일 전체 복원/현재 본문·manifest SHA 일치. `git apply --numstat`로 6개/2,065줄 파싱 확인(실제 적용 없음). 미추적 소스는 tracked git diff만으로 검토하지 않음 |

신규 8개는 실제 Windows 파일/ACL/프로세스 변경 없이 실행했다. 기존 전체 회귀에는 종전의 Windows 임시 파일·링크 합성 검사가 포함되므로 전체 190개가 모두 Mock인 것은 아니다.

## C. 실제 읽기 전용 Preflight

수정·Mock 검증과 호출 경로 재검토 후 **실행 도구의 현재 비승격 Windows 컨텍스트**에서 다음 명령을 실제 실행했다. UAC/RunAs/승격 재실행은 하지 않았다. 별도 데스크톱 일반 콘솔 또는 Full 토큰의 SYN 실행 결과와 혼동하지 않는다.

```powershell
# 작업 디렉터리: tools/fr_b02b_cli
$aclAuditBefore = Test-Path -LiteralPath 'C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01' -ErrorAction Stop
python -B .\labs\phase4b2_acl\phase4b2_acl_harness.py preflight
$aclAuditExit = $LASTEXITCODE
$aclAuditAfter = Test-Path -LiteralPath 'C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01' -ErrorAction Stop
# 비교값을 비식별 JSON으로 출력, preflight exit code 보존
```

실제 하네스 출력(종료 코드 **0**):

```json
{"status":"PREFLIGHT_ONLY","code":"PREFLIGHT_ONLY","case":"PREFLIGHT","operational_approval":"NONE","win32_error_code":null,"preflight":{"token_elevated":false,"token_dangerous_privileges":false,"known_folder_matches":true,"ancestors_checked":true,"root_exists":false,"native_read_checks_completed":true}}
```

전후 비교 출력:

```json
{"before_exists":false,"after_exists":false,"existence_changed":false,"preflight_exit_code":0,"operation":"read_only"}
```

- Known Folder가 코드의 `C:\ProgramData` 기준과 일치하고, C: 루트·ProgramData 조상이 열려 ID/최종 경로/owner/DACL 조회를 완료했다. 조상 reparse 검사를 통과했으나 **운영용 owner/ACE 정책을 승인한 것이 아니다.**
- 현재 토큰은 비승격이다. dangerous_privileges=false는 활성 SeBackupPrivilege/SeRestorePrivilege/SeTakeOwnershipPrivilege를 찾지 못했다는 한정된 뜻이며 모든 권한이나 향후 승격 가능성의 부재를 뜻하지 않는다.
- 후보 루트는 전후 모두 부재다. 실제 기존 객체 충돌·후보 junction 주입은 하지 않았고, 그 부정 경로는 Mock 검사다. 이후 실제 생성 직전 다시 검사해야 하며 이번 부재가 선점/교체 방어 증거는 아니다.
- 실제로 사용한 읽기 전용 API 경로는 이 호스트에서 완료됐다. DLL에 변경 API export가 연결된 사실 또는 읽기 구조체 성공은 CreateDirectory/ACL 설정/Store I/O/rename/Gate/강제 종료의 성공 증명이 아니다.
- 코드 경로에 파일·ACL 쓰기/삭제 예약/자식 실행 호출이 없고, Native capability는 False였다. 시험 경로의 존재 비교도 변하지 않았다. 실제 SID/SDDL/개인 경로는 출력·보고서·패치에 기록하지 않았다.

## D. 검증 수준과 미실행 범위

| 구분 | 이번 근거 | 판정 범위 |
|---|---|---|
| Mock/메모리 | 45개 하네스 테스트, DLL 대역·ctypes 합성 버퍼·Popen 대역 | 안전 차단/실패/타입·자원 계약. 실제 NTFS 접근 허용·거절 아님 |
| 실제 Native 읽기 | 위 preflight 출력, 전후 루트 부재 | 토큰·Known Folder·조상 metadata/SD 및 필요한 읽기 호출의 현재 호스트 동작 |
| 미실행 Windows ACL/SYN | SYN-01·02·05 전부 | 객체 생성/owner 부여/설명자 설정/OS 접근 거절·Store I/O·Gate 경쟁/해제·자식 시작/종료·중단 잔재는 아직 판정 불가 |

ProgramData 객체/Allowlist/Gate 생성, ACL·소유권 변경, 관리자 상승, 실제 자식 시작/강제 종료, 잔재 삭제를 하지 않았다. 운영 CLI 활성화·C/E 등록/백업/복원/철회·FROZEN 변경·GitHub 커밋/푸시/PR도 없다.

## E. SYN-01 이전 남은 별도 승인

1. **시험 경로 및 수정 대상:** `C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01` 하나와 DRAFT §6.1의 Config/Control/Store/Evidence 신규 객체만 승인해야 한다. 기존 객체 재사용/ACL 수리, E: 생성/쓰기는 제외한다.
2. **실행 담당자·토큰:** SYN-01 초기 관리자와 동일 개인 SID의 Full/Limited 사용을 비공개 확인하고, 관리자는 사용자가 별도 준비한다. SYN-02/05는 승인된 일반 R이어야 한다. 실제 개인 SID·담당자·합성 ACE/owner/마스크는 실행 전 확인 대상이다.
3. **증거·보존:** 비공개 인벤토리/프로세스 기록의 보관 위치·담당자·보존 기간을 정한다. 보호 상태를 확인하기 전 private 값을 기록하지 않는다. 공개 증거는 독립 승인/불변 증명이 아니다.
4. **중단·정리:** 충돌/부적격 토큰·권한/미지원 API·ACE/ID·바이트 변화/부분 쓰기/해제·IPC 오류는 HOLD다. 정상 자기 Gate 외에는 자동 삭제하지 않는다. 실패/중단 잔재 및 전체 시험 루트 정리는 조사 후 추가 수동 승인 대상이다.
5. **후속 시험 범위:** SYN-05의 단일 지정 P3 한 번 종료는 별도 승인해야 한다. 관리자 변경 Gate 참여, 다른 계정, 적대적 조상 교체, 삭제 예약 이후 크래시/전원 장애, C/E 복원 등은 이번 읽기 조회로 충족되지 않았다.

이번 기록은 실행 승인이 아니며 변경 모드 명령은 실행하지 않는다.

## F. 최신 전체 코드 묶음과 Git 보존

`phase4b2_acl_review_bundle.patch`는 Git 커밋에서 제외하는 과거 로컬 검토 산출물이며, **소스 4개 + 테스트 2개 전체**를 각 `/dev/null` 신규 파일 diff로 담았다. 현재 6개 모두 미추적이므로 이 형식을 사용했다. 변경 부분만 잘라낸 패치가 아니며 기존 파일을 자동 덮어쓰는 용도가 아니다. 기존 동명 파일이 있는 작업 트리에 적용하지 말고, 독립 검토/빈 별도 검토 위치에서 확인한다. 이번에 패치를 적용하지 않았다.

UTF-8 텍스트를 LF로 정규화한 코드 manifest:

| 상대 파일 (`tools/fr_b02b_cli/` 기준) | 줄 수 | SHA-256 (UTF-8/LF) |
|---|---:|---|
| phase4b2_acl_harness.py | 103 | `51a74f91c88a91e8a8ef7fe3b224a7b1ef586dee8e752bbf05573d4729112635` |
| phase4b2_acl_lab.py | 475 | `f623a9b494c22db234ae19be7bd9d9e5f9bb4a8809e42abfaadac1a0d159eddf` |
| phase4b2_acl_native.py | 465 | `700f555d5b79db0b802df5965480921f60eb459c2ec0bcb72aca0fc60fe9ae12` |
| phase4b2_acl_process.py | 186 | `56c16938594ffc50e32dd801e34175947921ee61889f08e6bb50b4a6535a2db4` |
| tests/test_phase4b2_acl_lab.py | 528 | `8cc927d87d4c30bcb1994f029166888e4989371d1d52fedd4d2ddd62c2facaf6` |
| tests/test_phase4b2_acl_native.py | 308 | `2378c8c9a718218f036a72738815417c9073f874c60c81b3cf7102ac35d201e7` |

패치 파일 SHA-256: `405b04ca18cf0012248e765a408892f41f322dc11c0a7c26f6b742739a45fb45`.

이번 수정 5개는 모두 기존 미추적 하네스/테스트 파일이다. 이 보고서와 전체 코드 패치 2개를 새로 추가했다. 작업 시작 시 기록한 37개 파일의 SHA-256 대조에서 위 5개만 변경됐고 **나머지 32개는 동일**했다. 기존 tracked 수정 4개와 사용자 docs/infra·DRAFT·FROZEN·이전 182개 보고/스테이징 patch는 보존했다. 기존 캐시 3곳의 열람 거부는 변경하지 않았으며 그 내부는 보존 검사의 범위 밖이다.

`git status --short`의 경로 목록은 기존 목록에 다음 2개가 추가된다. 코드 수정 5개는 이미 미추적이므로 계속 `??`로 나타난다.

```text
?? tools/fr_b02b_cli/phase4b2_acl_preflight_review.md
?? tools/fr_b02b_cli/phase4b2_acl_review_bundle.patch
```

tracked diff는 기존 4개 파일/173 insertions/3 deletions이며 staged diff는 없다. `git diff --check`, `git diff --cached --check`는 종료 코드 0이며 미추적 파일은 별도 본문/구문/공백·패치로 검토했다. 운영 계약·최종 경로/ACL 정책을 확정하거나 완료 기준을 낮추지 않는다.
