# Phase 4B-2 SYN-01·02·05 합성 Windows ACL 하네스 준비 보고

> **준비 완료 범위: 별도 하네스 구현 + Mock/메모리 검증. 실제 SYN/Windows ACL 시험은 모두 미실행.**
> 2026-11-10 KST / `feat/phase4b2-protected-review-registration`
> 로컬 및 읽기 전용 원격 조회 HEAD: `b133b494f8258eea603243f8f07191a33290084a`
> 운영 보호 등록 완료·FROZEN 변경·운영 보안 PASS 아님.

기준: [4B-2 FROZEN v1.0](../../../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md), [DRAFT v0.2 §2.1·§4.1·§6.1](../../../../docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.2_DRAFT_20261110.md), AGENTS.md v1.1. DRAFT/FROZEN/기존 런타임은 수정하지 않는다.

## A. 생성 파일과 책임

| 신규 파일 | 책임 |
|---|---|
| [phase4b2_acl_lab.py](../../labs/phase4b2_acl/phase4b2_acl_lab.py) | 고정 경로/권한 정책, 신뢰 부트스트랩, 인벤토리/Config 동일성, Gate 수명, SYN-01/02/05 조정 및 private worker |
| [phase4b2_acl_native.py](../../labs/phase4b2_acl/phase4b2_acl_native.py) | ctypes Win32 호출/구조체/오류/자원 해제. 기본 `allow_changes=False`. 새 객체에만 초기 보안 설명자 공급 |
| [phase4b2_acl_process.py](../../labs/phase4b2_acl/phase4b2_acl_process.py) | 명시적 자식 시작, 5초 단위 제한 IPC, nonce/PID/생성 시각/phase 검증, P3만 한 번 종료, 실패 시 자동 kill/삭제 없음 |
| [phase4b2_acl_harness.py](../../labs/phase4b2_acl/phase4b2_acl_harness.py) | 독립 실행 경계. 기본 plan, 읽기 전용 preflight와 명시적 변경 모드 분리, 고정 필드의 비식별 출력 |
| [tests/test_phase4b2_acl_lab.py](../../tests/test_phase4b2_acl_lab.py) | 24개 메모리 정책·CLI·프로세스 대역 테스트. 실제 파일/자식 프로세스 없음 |
| [tests/test_phase4b2_acl_native.py](../../tests/test_phase4b2_acl_native.py) | 13개 Win32 DLL 대역/ctypes ABI·실패·할당/해제 검사. 실제 DLL API 호출 없음 |
| 이 보고서 | 명령/증거 구분, Native 계약, 승인 대상·잔재 정책·한계 |

기존 CLI/Allowlist/Protected Store를 import하거나 연결하지 않는다. 새 의존성 없음. SID·SDDL·개인 경로를 공개 출력하지 않고 고정 상태/범주·선택적 숫자 Win32 코드만 출력한다. argv 오류도 argparse의 원시 값 반사를 막는다. 프로그래밍 오류는 내부 계층에서 드러나며 실행 최외곽에서만 `INTERNAL_ERROR`로 비식별 출력한다.

### 고정 경계와 생성 순서

- 대상은 `C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01` 하나. `--root`, 임의 SID, E: 우회, 자동 R02, cleanup/repair/RunAs 옵션 없음.
- SYN-01은 명시적 실행 의사 + 승격 토큰 확인 후 Known Folder/조상 핸들을 검사한다. 후보 존재 시 `ROOT_COLLISION`; 재사용/덮어쓰기 없음. 객체 생성 시 `SECURITY_ATTRIBUTES`로 제한 DACL/소유자를 공급한다. 기존 객체의 소유권/ACL을 바꾸는 setter는 사용하지 않는다.
- 루트/Config/Control/Store/work/Store/locks/Evidence의 새 경계 → 생성 핸들에서 소유자/ACE/보호/상속·ID 대조 → 새 Config 파일의 보호 확인 → 합성 설정/비공개 SID 기록 → 보호된 Control 인벤토리 → 비식별 SYN-01 증거 순서다. 파일 보호 확인 실패면 private 값은 쓰지 않고 빈/부분 객체를 HOLD로 남긴다.
- A/S는 관리용 Full Control 후보, R은 DRAFT 시험 표의 마스크만 사용한다. 모든 새 객체는 명시적 보호 DACL이며 미승인 상속/ACE를 거절한다. Config/인벤토리 소유자는 A, 새 작업/Gate/증거 소유자는 R 후보다. 현재 같은 개인 계정의 Full/Limited 토큰을 전제로 하며 임의 다른 R 입력은 제공하지 않는다.
- 이후 단계는 고정 코드의 소유자/ACE 정책을 먼저 확인하고 **같은 핸들**에서 인벤토리를 제한 크기로 읽는다. 그 뒤 승인된 초기 객체 ID·Config 바이트 SHA-256과 실제 핸들을 대조한다. 인벤토리의 자기 주장만으로 자신을 신뢰하지 않는다. SYN-01 증거가 없거나 초기화 일부만 존재하면 다음 단계로 진행하지 않는다.
- 디렉터리/Config/인벤토리 핸들을 유지하고 현재 토큰·설명자·ID·Config 바이트를 작업 경계 전후에 재검증한다. Config 관리 변경의 별도 실행기는 이번 하네스에 추가하지 않는다. 운영 설정 변경 참여 절차는 후속 범위다.

SYN-01의 private 인벤토리와 공개 증거는 초기 구성에서 생성한다. `Evidence/native.private.json`은 덮어쓰지 않도록 SYN-05의 전체 진단 기록을 **마지막 한 번 신규 생성**한다. 그 전의 비공개 프로세스 정보는 캡처된 전용 pipe/메모리에만 있다. 공개 증거 파일도 수정 가능한 로컬 진단 자료이며 독립 승인/불변 증명이 아니다.

## B. Native API 계약 검토

아래는 공식 문서와 선언/Mock을 대조한 결과다. 실제 Windows 성공·접근 거절을 측정한 결과가 아니다.

| API/구조 | 구현상 확인한 계약 | 공식 근거 |
|---|---|---|
| CreateFileW/CreateDirectoryW | HANDLE/INVALID_HANDLE_VALUE 및 BOOL 구분. CREATE_NEW, share=0, OPEN_REPARSE_POINT; 디렉터리 BACKUP_SEMANTICS. 새 객체 초기 설명자만 공급 | [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [CreateDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createdirectoryw) |
| SDDL 변환/보안 설명자 | 변환 성공과 non-NULL 포인터를 모두 확인. 소유 메모리 LocalFree, 생성 후 descriptor 해제 실패에도 파일 핸들 닫기·잔재 보존 | [변환 API](https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertstringsecuritydescriptortosecuritydescriptorw) |
| GetSecurityInfo | 반환 DWORD 오류 직접 사용, OWNER/DACL만 조회. 설명자 LocalFree, 하위 owner/DACL 포인터는 따로 해제하지 않음. NULL/누락 DACL 거절 | [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo) |
| GetAclInformation/GetAce | count/사용 바이트·ACE 경계 확인. 현재 명시 ACCESS_ALLOWED_ACE만 지원하며 미지원 유형·잘못된 SID/플래그는 차단. 유형/마스크/상속·owner를 고정 정책과 대조 | [GetAclInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getaclinformation), [GetAce](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getace) |
| FileIdInfo/최종 경로 | 64비트 volume serial + 128비트 File ID 비교. 최종 경로를 같은 핸들에서 확인하고 reparse/파일 hardlink 반례 거절 | [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/desktop/api/winbase/nf-winbase-getfileinformationbyhandleex), [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info) |
| FileDispositionInfo | DELETE로 취득한 **자기 생성 동일 핸들**에만 삭제 예약. BOOLEAN은 1바이트. 정상 검증 뒤 SetFileInformationByHandle→CloseHandle. 실패 시 경로 삭제 fallback 없음 | [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle), [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info) |
| FileRenameInfo | ReplaceIfExists=false, NULL RootDirectory+고정 절대 목적 경로, UTF-16 바이트 길이·NUL 종료·자연 정렬. 같은 핸들 ID와 바이트 재확인 | [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info) |
| Write/Read/Flush | 부분 쓰기는 재시도 없이 HOLD, 읽기 64 KiB 제한. 새 파일의 쓰기 핸들만 사용 | [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers) |
| TokenUser/TokenElevation/TokenPrivileges | TOKEN_QUERY만, 가변 버퍼 크기/122와 실제 반환 길이 검사, 고정 elevation DWORD. SID 문자열/토큰 할당 해제. 일반 토큰의 활성 backup/restore/take-ownership 특권이면 시험 중단 | [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation) |
| 자식 식별/종료 | Popen으로 시작한 자식의 전용 IPC nonce+PID+생성 시각+PARTIAL_READY를 확인. 처음 취득한 process 핸들을 유지해 재사용 PID에 의존하지 않음. 종료 후 wait, WAIT_FAILED와 TIMEOUT 구분 | [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes), [TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess), [Python subprocess](https://docs.python.org/3.14/library/subprocess.html) |

GetFileInformationByHandleEx/해당 파일 ID 클래스·드라이버 지원, 디렉터리/파일의 실제 소유자 부여, 일반 토큰의 실제 마스크·공유 모드 성공 여부는 **미검증**이다. 미지원/실패면 HOLD로 중단하며 다른 API/ID/경로로 조용히 대체하지 않는다. Native 선언 검증을 운영 ACL PASS로 표현하지 않는다. AccessCheck 기반의 일반 유효 권한 계산기는 추가하지 않았으며, 이 시험은 명시 정책 대조와 SYN-02의 실제 OS 접근 요청을 함께 측정하는 범위다.

삭제 예약 후 CloseHandle 전 중단에서는 파일이 사라질 수 있다는 계약상의 한계를 유지한다. Gate 부재만으로 작업 완료를 추정하지 않으며 기존 SYN02 작업/미확정 증거가 있으면 자동 재실행하지 않는다. 이번 종료 대상은 삭제 예약 전 부분 쓰기 후 P3 하나다. 전원 장애·삭제 예약 이후 크래시·ABA·관리자 악의적 변조는 검증하지 않았다.

## C. 실제 실행한 검증

`tools/fr_b02b_cli`에서 Python **3.14.0**으로 실행했다.

| 명령 | 실제 결과/종류 |
|---|---|
| 최초 신규 테스트 실행 | `ModuleNotFoundError: No module named 'phase4b2_acl_lab'`, 1 loader error. 새 모듈 미구현 Red이며 OS SID/ACL 실패를 재현한 것이 아님 |
| `python -B -m unittest discover -s tests -p 'test_phase4b2_acl_*.py' -q` | 최종 37개 OK. 24개 정책/CLI/프로세스 메모리 대역 + 13개 DLL 대역/ctypes ABI |
| `python -B -m unittest discover -s tests -q` | **182개 / 8.954초 / OK** = 기존 145 + 신규 37. 종료 재요청 Red를 수정한 뒤 실행한 최종 회귀. 기존 테스트 파일 수정 없음 |
| `python -B phase4b2_acl_harness.py plan` | 실제 Python 진입점, PLAN_ONLY/0. Native를 생성하지 않음 |
| `python -B phase4b2_acl_harness.py syn01` | 실제 Python 진입점, HOLD/EXECUTION_NOT_APPROVED/1. 실행 플래그 없이 Native 생성/변경 없음 |
| 새 Python 6파일 AST 구문 검사 | 성공. Ruff/정적 분석 완료와 다름 |
| Ruff 모듈 사용 가능 여부 | 미설치·미실행 |
| 고정 시험 루트 Test-Path | 읽기 전용 조회 false. 초기 ACL/경로 교체 방어 PASS 아님 |

초기 정책 테스트 9개 Green 후 메모리 정상/부분 쓰기/변경 입력과 ABI/자원 검사로 확장했다. 작업 디렉터리 오타로 중간 테스트 명령 한 번이 시작되지 않았고(Windows 267), 올바른 위치에서 실행한 결과만 위 PASS에 집계했다.

최종 반례 `test_only_authenticated_owned_partial_child_can_be_stopped`에 같은 자식 종료 재요청 검사를 추가했을 때 `AssertionError: Hold not raised`로 Red를 확인했다. Native 종료 호출 전에 `TERMINATION_REQUESTED` 상태로 이동해 성공/실패/대기 불확실 모두에서 재요청을 금지하도록 최소 수정했다. 이 실패는 프로세스 대역의 상태 검사이며 실제 OS 강제 종료 결과가 아니다.

신규 검사에서 실제 Windows 파일 생성·ACL 변경·프로세스 시작/종료는 없다. DLL 함수는 모두 대역이며 성공한 보안 설명자 파싱도 합성 ctypes 메모리다. 기존 145개에는 종전의 Windows 임시 파일/링크 합성 회귀가 포함되므로 **전체 182개를 모두 Mock 테스트라고 부르지도 않는다.** 이번 하네스의 실제 Native preflight/SYN은 실행하지 않았다.

### 대표 차단/실패 검증

- 잘못된 루트/미승인 실행/기존 루트/일반 토큰의 초기화 요청: 변경 호출 0.
- 5와 32/80/183/112를 구분. Config는 권한별 요청이 5로 거절돼야 하고 정상 읽기 대조군이 필요하다. 다른 오류나 예상 밖 핸들 획득이면 HOLD.
- 인벤토리/초기 증거 누락, 루트 ID/ACL/reparse 변경, 미정의 자식, Config 바이트 변경: 진행 중단. 부분 쓰기·rename 전 실패는 Gate/자료 보존.
- 외부/변경 객체 해제, 자기 생성이 아닌 핸들 삭제, 오류 후 재해제·자동 재시도 방지. descriptor/SID/파일·프로세스 핸들의 해제 계약 검사.
- 비소유 자식·nonce/phase/PID/생성 시각 불일치·이미 종료된 자식은 terminate 0. 정상 경쟁/명시적 재취득 후 부분 중단→HOLD를 메모리로 검증.
- 실제 SID/SDDL/개인 경로가 포함된 예외를 주입해도 공개 출력 없음. 원시 argv도 출력하지 않음.

## D. 실행하지 않은 항목

관리자 상승, ProgramData 시험 루트/Config/Allowlist/Gate 생성, ACL/소유권 변경, Native 실제 파일 I/O·rename·삭제 예약, 자식 시작/강제 종료, 잔재 삭제 모두 미실행이다. E: 객체 생성/백업/복원, 실제 등록/완료 표식/철회/운영 CLI 활성화도 없다. 기존 DRAFT/FROZEN을 수정하거나 GitHub 커밋·푸시·PR을 만들지 않았다.

## E. 실행 전 별도 승인 체크리스트

승인 후에만 아래 변경 명령을 사용한다. **플래그는 의도 확인 장치이며 외부 사용자 승인이나 Windows 권한의 증명이 아니다.** 코드 실행을 자동 승인하지 않는다.

1. 고정 경로 `C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01`와 단일 실행 R01을 승인한다. 실제 생성 직전 Native preflight/조상 검사·기존 부재를 다시 확인한다. 이미 있으면 중단하며 임의 재사용/새 이름 선택 없음.
2. SYN-01 담당자와 같은 개인 계정의 Full/Limited 사용을 비공개 확인한다. 승격 PowerShell은 사용자가 별도로 준비하며 하네스가 RunAs하지 않는다. SYN-02/05는 비승격 R, 초기 인벤토리의 개인 SID와 일치해야 한다. 다른 계정 분리 시험은 이번 범위 밖이다.
3. 생성할 객체는 DRAFT §6.1의 Config/settings.synthetic.json·reviewers.synthetic.json, Control/inventory.private.json, Store/work/SYN02/io.bin→io-renamed.bin, Store/work/SYN05-crash/partial.bin, Store/locks/global.gate 및 명시된 Evidence 파일뿐이다. 새 객체의 A/S 관리권·R 제한 마스크·소유자·명시 보호 DACL을 승인한다. 기존 객체 ACL 수리는 승인 범위가 아니다.
4. SYN-05의 독립 자식과 마지막 P3 한 번 종료, 5초 IPC/wait 제한을 승인한다. 타임아웃/다른 원인/비참여 프로세스는 자동 kill하지 않는다. 필요하면 지정 담당자가 남은 자식을 별도 조사한다.
5. 정상 Gate만 동일 핸들 삭제 예약→close로 해제한다. 그 외 모든 객체/증거, 마지막 stale Gate/partial은 보존한다. 담당자·보존 기간·private 증거 보관을 정한다. 전체 정리/실패 잔재 삭제는 인벤토리 ID·경계 조사 후 **추가 수동 승인** 대상이다.
6. 충돌(80/183/32), Config 접근 오류 5 이외, 부적격 토큰/특권, SD/ID/바이트 변경, 미지원 API/ACE, 부분 생성/쓰기, 해제/IPC/wait 실패는 HOLD 중단 조건이다. 부분 실패에서 자동 복구·재시도·승격 없음. 실제 Native 성공은 앞으로 측정할 항목임을 확인한다.

```powershell
# 저장소의 tools/fr_b02b_cli에서. 아래 세 변경 명령은 아직 실행하지 않음.
python -B .\labs\phase4b2_acl\phase4b2_acl_harness.py preflight  # 읽기 전용, 현재 단위에서는 미실행
python -B .\labs\phase4b2_acl\phase4b2_acl_harness.py syn01 --execute-approved-lab # 별도 승인된 Full 토큰
python -B .\labs\phase4b2_acl\phase4b2_acl_harness.py syn02 --execute-approved-lab # 별도 승인된 일반 R
python -B .\labs\phase4b2_acl\phase4b2_acl_harness.py syn05 --execute-approved-lab # 별도 승인된 일반 R
```

syn01/02의 정상 관측 출력은 `SYNTHETIC_OBSERVED`/0이며 운영 PASS가 아니다. syn05는 마지막 중단 잔재 확인까지 맞더라도 `HOLD`/`EXPECTED_CRASH_RESIDUE`/1을 반환한다. 이 결과 이후 다음 단계/재실행으로 넘어가지 않는다. private pipe/인벤토리는 공개 저장소에 올리지 않는다.

## F. Git과 보존 범위

현재 브랜치/원격 HEAD는 위 기준과 같다. 기존 tracked 수정 4개(README, a1_adapter, cli, observation)와 기존 미추적 사용자 자료는 보존했다. 이번에는 이 보고서를 포함한 **신규 파일 7개만** 추가했다. 코드·DRAFT·FROZEN·docs/infra 포함 작업 전 기록한 **30개 파일의 SHA-256이 모두 동일**하며 기존 파일 수정/삭제는 없다. 기존 `.pytest_cache/` 3곳의 열람 거부는 수정하지 않았고 그 내부는 보존 검사의 범위 밖이다.

`git status --short`에서 추가된 항목:

```text
?? tools/fr_b02b_cli/phase4b2_acl_harness.py
?? tools/fr_b02b_cli/phase4b2_acl_harness_review.md
?? tools/fr_b02b_cli/phase4b2_acl_lab.py
?? tools/fr_b02b_cli/phase4b2_acl_native.py
?? tools/fr_b02b_cli/phase4b2_acl_process.py
?? tools/fr_b02b_cli/tests/test_phase4b2_acl_lab.py
?? tools/fr_b02b_cli/tests/test_phase4b2_acl_native.py
```

미추적 신규 코드는 `git diff`에 나타나지 않으므로 별도 본문·AST·Mock·공백 검사로 검토했다. 기존 tracked diff는 4개 파일/173 insertions/3 deletions로 작업 전과 같고 staged diff는 없다. `git diff --check` 및 `git diff --cached --check`는 종료 코드 0이다. 하네스 준비는 운영용 부트스트랩 정책/ACL/경로/관리 책임/설정 변경 Gate 참여/추가 크래시·복원 검증을 완료하지 않는다.
