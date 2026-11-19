# Phase 4B-2 운영 보호 저장소·Windows ACL 운영 최소 계약 DRAFT v0.2

> **DRAFT — ProgramData 우선 검증 방향 / 물리 경로·책임자·권한 마스크 미확정 / 운영 PASS 아님**  
> 작성일: 2026-11-10 KST  
> 저장소: `Trend-Leader-capstoneProject/feature`  
> 브랜치: `feat/phase4b2-protected-review-registration`  
> 최초 읽기 전용 실측 기준 HEAD: `8d49cb33e91b7a09def95084d54810b92132b32a`  
> SYN-01·02·05 준비 보완 시 로컬/원격 HEAD: `b133b494f8258eea603243f8f07191a33290084a` (AGENTS.md v1.1 개정 반영)  
> 기준: [4B-2 FROZEN v1.0](Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md) §4.1·§4.2·§5.2·§6.1·§6.2. 기존 4A·4B-1 계약 불변.

## 1. v0.1에서 유지하는 사실과 이번 보완

[v0.1](Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.1_DRAFT_20261110.md)은 검토 기록으로 보존한다. 그 문서의 공유 A1 검증기·Service 재검증 분석, A/B/C 비교, Native 핸들·경로 교체 방어 요구와 OP-01~12는 유지한다. 이 문서는 그 내용을 재구현하지 않고 Config/Store 책임, 객체별 권한 후보, 잠금 실패 절차 및 읽기 전용 실측을 보완한다.

| 구분 | 내용 |
|---|---|
| 사용자 설계 판단 | ProgramData 중심 A안과 **단일 전역 Gate**를 MVP 우선 시험 후보로 선택한다. Config는 관리자 관리/R 읽기 전용, Store는 승인 개인 SID의 필요한 작업만 허용한다. 전용 절대 경로·마스크·담당자 채택 승인은 아니다. |
| 기존 코드에서 확인된 사실 | 공유 검증기가 bytes 타입·20 MiB 상한을 검사한다. Service는 동일 세 입력 바이트·현재 SID·Allowlist·필요 시각 조건을 재검증한다. 중복 구현 없음. |
| 유지되는 신뢰 한계 | 같은 개인 계정이 관리자 상승도 가능하다. 일반 CLI 작성 파일과 C/E 해시 대조는 그 계정 또는 관리자에 대한 독립 불변 증명이 아니다. |
| 이번 새 제안 | 아래 객체별 접근권·Config 변경 조정·잠금 수명·합성 시험 범위. 모두 검증·승인 전 후보이며 실제 설정에 반영하지 않았다. |

독립 계정/서비스/서명/관리자 봉인 도구를 도입하지 않는다. `PendingReviewDecision`, 합성 HOLD 스테이징 또는 이 DRAFT는 보호 등록 완료가 아니다. 실제 CLI는 계속 Fail-Closed이며 유효 등록 ID·`PROTECTED_REVIEW_RECORDED`를 반환하지 않는다.

## 2. Config와 Store의 책임 경계

다음 이름은 조회·시험 논의를 위한 후보다. 현재 앱 설정이나 자동 생성 기본값이 아니다.

```text
<ProgramData Known Folder>\TrendLeader\ProtectedReview\
  Config\settings.json       # 관리자 관리: 승인된 경로/객체·볼륨 식별 연결 후보
  Config\reviewers.json      # 관리자 관리: 비공개 Allowlist 후보
  Store\locks\               # 일반 CLI의 제한된 조정 작업
  Store\.review-staging-...  # 합성 스테이징과 향후 운영 스테이징은 별개
  Store\registrations\...    # 향후 등록 경계, 현재 미구현
E:\TrendLeaderProtectedReview\...  # 독립 검증할 백업 루트 후보
```

| 책임 | 업무 | 경계 |
|---|---|---|
| 초기 설정 관리자 | 승인된 새 전용 위치의 소유자·DACL·상속·루트/볼륨 ID 설정 및 대조 | 기존 객체 충돌 시 자동 덮어쓰기·소유권 회수 금지. ProgramData 전체/프로필 전체/E: 전체 ACL 변경 금지 |
| Allowlist 변경 책임자 | 추가·비활성·변경·폐기 승인/적용 사유와 전후 상태 비공개 기록 | 일반 검토 사건과 구분. 담당자·승인/적용 겸임·긴급 비활성화 절차 미확정 |
| 일반 검토자 | 비승격 CLI로 토큰 SID 인증, 보호 설정 읽기, 명시적 판단과 허용된 Store 작업 | Config 쓰기·ACL 수리·자동 승격·임의 설정 경로/허용 SID 입력 금지 |
| 사고 조사/복구 책임자 | 충돌·중단·부분 자료를 HOLD로 조사하고 후속 수동 조치 승인 | 잠금/잔여 자료의 자동 회수·삭제·등록 승격 금지. 담당자와 보존 기간 미확정 |

동일인이 관리자와 검토자를 맡을 수 있다. 업무·실행 토큰·변경 사유를 구분하지만 독립적인 보안 승인 또는 새로운 앱 역할이라고 주장하지 않는다. 관리자 그룹 소속만으로 `EVIDENCE_REVIEWER`를 부여하지 않는다. 일반 CLI의 승격 실행을 강제 거절할지에 관한 새 정책은 아직 확정하지 않는다.

Config는 관리자 관리 영역, Store는 일반 CLI의 제한 작업 영역으로 나눈다. 사용자 판단에 따라 **관리자 변경과 모든 Store 작업이 동일한 단일 전역 Gate에 참여**하는 방식을 우선 시험한다. 관측 ID별 Gate를 추가하지 않는다. 잠금 경로·이름·볼륨/객체 식별 연결은 신뢰 부트스트랩에 결속하고 settings의 변경 가능한 Store 경로에서 실행마다 새 Gate를 파생하지 않는다. Gate 이동/교체는 라이브 설정 변경으로 처리하지 않고 작업 중지·별도 관리 승인 대상으로 둔다.

고정하여 대조할 정체성은 부트스트랩/locks 컨테이너의 볼륨·객체 ID다. 배타 생성·정상 해제로 교체되는 `global.gate` 자체의 File ID를 영구 고정하지는 않는다. 새 Gate ID는 각 취득 때 기록하고 그 핸들을 해제할 때까지 동일성을 확인한다.

### 2.1 설정 신뢰 부트스트랩 — 자기 증명 금지

1. Known Folder API(flags=0)로 ProgramData를 조회하고 **사전에 승인된 고정 상대 Config/조정 경계** 후보를 찾는다. 사용자 입력·USERNAME·환경변수 경로·settings 내부 경로를 이 첫 신뢰 근거로 사용하지 않는다. 정확한 상대 이름 및 부트스트랩 검사 정책은 승인 전 후보이고 런타임에는 아직 연결하지 않는다.
2. 실제 조상/Config/설정 파일을 Native 핸들로 열어 재분석 지점·최종 경로·볼륨/객체 ID·소유자·DACL·상속을 확인한다. 허용 소유자/ACE 정책은 읽으려는 settings가 아닌 신뢰된 실행 코드/초기 관리 기준에서 와야 한다. 그 기준을 아직 공급하지 못하면 BLOCKED다. settings에 적힌 자기 해시나 자기 File ID로 해당 settings를 승인하지 않는다.
3. 검증한 **같은 핸들**에서 설정/Allowlist를 제한 크기로 읽고 형식·중복 키 등을 검증한다. 읽기 전후 객체 정체성·설명자·바이트의 안정성을 대조한다. 경로만 확인한 뒤 일반 open으로 무검증 재개방하는 것은 이 요구를 충족하지 않는다. 초기 조회는 신뢰 확보를 위한 읽기이며 Store 변경 허용을 뜻하지 않는다.
4. 신뢰가 확인된 설정의 승인된 Store/백업 경로 및 볼륨/루트 ID와 실제 대상 핸들을 대조한다. 운영 루트는 누락 시 자동 생성하지 않는다. 미검증 새 경로·장치·소유자·DACL이면 차단한다. E: 관련 검증은 후속 통합 조건이며 이번 C: 합성 시험에서 충족했다고 보지 않는다.
5. 고정 조정 경계를 검증해 전역 Gate를 취득한 뒤 Config/Allowlist 바이트·객체/정책 버전과 현재 SID를 **다시** 확인한다. 초기 읽기와 달라졌으면 진행하지 않는다. Store 작업 직전·각 민감 작업 경계·반환 직전에도 입력/설정/권한을 재검증한다. Config를 계속 읽기 전용 핸들로 유지할 때의 write/delete 공유 제한과 관리자 변경의 양립 가능성은 실환경 시험 대상이다.

관리자는 같은 Gate를 먼저 취득하고 승인된 Config 변경·전후 Native 대조·비공개 변경 기록 후 정상 해제하는 절차를 우선 시험한다. R은 Config를 고치지 않는다. 변경자는 자기 작업에만 참여하고 검토의 ACCEPTED 결정을 대신하지 않는다.

**한계:** 로컬 관리자 도구/탐색기/보안 제품 등은 협력적 Gate 규칙을 따르지 않을 수 있다. Gate는 이들의 강제 보안 경계가 아니다. 객체/설명자/Allowlist 바이트 또는 설정 버전 변화를 탐지하면 BLOCKED, 생성 자료가 있으면 사용 불가 HOLD로 남긴다. 변경 후 되돌리는 ABA 경합이나 관리자에 의한 양 사본 변조까지 이 검사만으로 배제하지 않는다. Gate에 참여하지 않는 계획된 관리 변경은 작업을 중지하고 별도 검증 후 재개해야 한다. 이런 한계가 수용되지 않으면 운영 연결을 보류한다.

## 3. 객체별 최소 접근권 후보

R은 토큰에서 얻은 개인 검토자 SID, A/S는 Administrators/SYSTEM이다. 실제 개인 SID는 공개 문서에 기록하지 않는다. 아래는 **요구 작업과 권한의 대응표이며 배포할 ACE/SDDL 확정표가 아니다.** 수치 마스크·상속 플래그 조합은 실제 일반 토큰의 I/O와 대조 후 확정한다.

공통 조회 Q는 객체에 맞는 내용 읽기/목록·탐색, `FILE_READ_ATTRIBUTES`, `READ_CONTROL`이다. 현재 Python 파일 I/O와의 후보 호환성은 `FILE_GENERIC_READ`/`FILE_GENERIC_WRITE` 기준으로 시험하고, Native 구현에서 더 좁힐 수 있는지 별도로 측정한다. `SYNCHRONIZE` 등 실제 open이 요청하는 비트도 포함해 확인한다. 쓰기/flush가 필요한 핸들의 권한을 읽기 권한만으로 대체하지 않는다. [파일 접근권](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants), [FlushFileBuffers 요구사항](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).

| 객체·단계 | 필요한 작업 | R의 최소 접근권 후보 | 부여하지 않을 접근권·동작 | 소유자·DACL·상속 검사 후보 |
|---|---|---|---|---|
| 전용 공통 루트 | 하위 Config/Store 탐색, 설명자 조회 | Q 중 디렉터리 탐색/필요 목록·속성·`READ_CONTROL` | 루트 삭제·이름 변경, `FILE_DELETE_CHILD`, 자식 임의 생성, `WRITE_DAC`/`WRITE_OWNER` | A/S 소유 후보, 보호 DACL. Config/Store별 규칙을 분리하며 R의 포괄 Modify 상속 금지 |
| Config 디렉터리 | 설정 파일 열기·경계 조회 | Q | 파일/디렉터리 추가, 내용 쓰기, 삭제·`FILE_DELETE_CHILD`, 권한/소유자 변경 | A/S 소유 후보. 승인된 제한 ACE만 사용, Store 쓰기 ACE 유입 금지 |
| settings/Allowlist 파일 | 내용·설명자 읽기 | `FILE_GENERIC_READ` 후보 | 쓰기/append/삭제/권한·소유자 변경 | A/S 소유 후보. 제한된 Config 상속 또는 승인된 명시 ACE를 정확히 대조 |
| Store 루트/registrations 컨테이너 | 목록·검증, 지정한 새 하위 디렉터리 생성 | Q + 필요한 위치의 `FILE_ADD_SUBDIRECTORY` | 컨테이너 교체·삭제·포괄 `FILE_DELETE_CHILD`, Config 변경 | 컨테이너 A/S 소유 후보. 단계별 자식 생성 권한만 분리, 기존 자료 쓰기로 포괄 상속하지 않음 |
| 신규 스테이징 디렉터리 | 새 파일 생성·목록·검증, 향후 같은 볼륨 내 확정 이동 시험 | Q + `FILE_ADD_FILE`, 필요 시 해당 디렉터리의 `DELETE` 및 목적 컨테이너의 추가 권한 | 기존 경로 덮어쓰기, 컨테이너 전체 자식 삭제 | 생성 소유자가 R일 수 있음. 생성 직후 실제 소유자/제한 ACE/상속 대조. rename 권한은 별도 실측 |
| 신규 스테이징 파일 | 배타 신규 생성, 쓰기·flush·동일 바이트 읽기 | 신규 파일에 한정한 `FILE_GENERIC_READ`/`FILE_GENERIC_WRITE` 후보 | 기존 파일 열어 덮어쓰기, 불필요한 DELETE/명시적 `WRITE_DAC`·`WRITE_OWNER` 부여 | 초기 설명자·소유자·파일 ID 확인. 부모 제한 상속만 허용. R 소유자의 암묵적 권한 한계는 아래와 같음 |
| 향후 완료 원본·검토 파일 | 조회·바이트/설명자 대조 | 조회 Q 방향. 생성 중 권한과 완료 후 권한을 별도로 시험 | 완료 후 덮어쓰기·삭제·일괄 재해시 복구 | 완료 시 권한 전환 방법 미확정. R 소유 파일을 읽기 전용으로 바꿔 독립 봉인됐다고 판단하지 않음 |
| 향후 철회 사건 컨테이너/신규 파일 | 새 사건 추가 및 기존 이력 조회 | 컨테이너 Q + `FILE_ADD_FILE`, 신규 사건 쓰기/검증 | 기존 사건 변경·삭제, 무조건 재수락 | 기존 원본과 구분. append 비트만으로 사건의 추가 전용 의미를 보장하지 않음 |
| locks 컨테이너 | 고정 규칙의 신규 잠금 생성·경계 조회 | Q + `FILE_ADD_FILE` | 컨테이너 삭제·`FILE_DELETE_CHILD`·타 잠금 삭제 | A/S 소유 후보. 신규 잠금만 제한 ACE 상속 |
| 현재 프로세스가 새로 만든 잠금 파일 | 배타 핸들 유지·식별/상태 대조, 정상 종료 시 자기 객체 해제 | 신규 파일 `GENERIC_READ`/`GENERIC_WRITE` + 자기 객체 `DELETE` 후보 | 기존 잠금 열어 재사용/초기화, 임의 파일 삭제, `DELETE_ON_CLOSE` | R 소유 가능. 초기 DACL/ID 검증·share mode 0 후보. 해제도 같은 객체 핸들로 검증 |
| E: 전용 컨테이너/신규 사본 | 향후 지정한 새 사본 생성·flush·대조 | 원본의 생성/조회 단계에 대응하는 제한 권한을 별도 시험 | E: 전체 쓰기/권한 변경으로 단순화, 기존 사본 덮어쓰기 | 전용 컨테이너 A/S 소유 후보. C: 결과를 복제해 PASS하지 않고 별도 볼륨·ACL 검증 |

A/S의 관리권은 승인된 전용 경계에 한정해 설정·복구 절차로 사용한다. 광범위 그룹의 보호 데이터 읽기/쓰기·권한 변경은 허용하지 않는 방향이다. 소유자 집합·SID·Allow/Deny·마스크·ACE 유형·전파/상속 플래그를 객체별로 대조한다. 루트의 DACL 보호 비트 하나만 보거나 R ACE 하나를 찾는 것으로 판정하지 않는다. NULL/누락 DACL, 필요한 동작이 불가능한 빈 DACL, 읽지 못한 설명자, 미지원 ACE는 차단한다.

자식은 검증된 제한 부모의 상속을 허용할 수 있다. OS 공통 조상은 정당한 소유자/탐색 권한과 프로젝트 경계를 구분하고, 부모 `FILE_DELETE_CHILD`에 의한 교체 가능성도 검증한다. 유효 접근권은 실제 토큰 그룹/Deny-only/권한/generic mapping까지 포함해 확인해야 하므로 이 표만으로 OS 접근 허용·거절을 증명하지 않는다.

**신뢰 한계:** R이 만든 파일의 소유자 권한을 명시 ACE에서 `WRITE_DAC`만 빼서 제거했다고 주장하지 않는다. 같은 계정/관리자의 악의적 재권한 부여·양 사본 변조는 현 FROZEN의 독립 방어 범위 밖이다. 표의 금지 항목은 최소 부여·앱의 동작 제한 후보이지 그 계정으로부터의 독립 불변성 약속이 아니다.

## 4. 보호된 잠금 파일의 수명과 HOLD

우선 시험 후보는 보호된 고정 전역 Gate의 `CREATE_NEW` 배타 생성 + share mode 0 + 핸들 유지다. 실행마다 CLI 경로를 받지 않는다. `CREATE_ALWAYS`/기존 파일 재사용/타임스탬프 기반 만료/자동 재시도·회수는 사용하지 않는다. 생성 시 `FILE_FLAG_DELETE_ON_CLOSE`를 사용하지 않아 삭제 예약 전 중단 흔적을 남긴다. share mode 0은 읽기/쓰기/삭제 접근의 공유 제한이며 속성 조회 등 모든 접근이나 ACL 변경을 봉쇄한다는 뜻은 아니다. [CreateFileW 계약](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

| 사건 | 후보 처리 | 수동 조사·해제 조건 |
|---|---|---|
| 신규 취득 | 보호 조상·루트 ID/ACL 확인 → 배타 신규 생성 → 생성 객체 ID/설명자 대조 → 핸들 유지 | 실패하면 성공·유효 ID 없음. 만들어진 자료가 있으면 HOLD |
| 파일 존재·공유 충돌·ID/ACL 불일치 | 즉시 차단, 기존 내용/이름/소유자 변경 없음 | 다른 프로세스 실행 여부·보호 경계·해당 이력 조사. 오래됐다는 이유만으로 해제 금지 |
| 정상 종료 | 배타 구간의 필수 검증·결과 일관성 확인 후 **자기가 새로 취득한 동일 객체만** 핸들 기반 해제하는 방식 시험 | 정상 해제 실패도 HOLD. close 후 경로 이름으로 무조건 삭제하지 않음 |
| 입력 오류/취소·쓰기 실패·부분 저장·권한/시각 변화 | 유효 등록 없음. 핸들 닫기와 잔여 파일 삭제를 구분하고, 생성된 잠금/스테이징은 사용 불가 HOLD 유지 | 원본·부분 자료·잠금 객체/이력·활성 작업을 확인한 지정 담당자의 별도 수동 조치 필요 |
| 강제 종료·전원 장애·재시작 | 삭제 예약 전 중단이면 Gate를 남기는 방향. 삭제 예약 후에는 파일이 사라질 수도 있으므로 부재만으로 정상 완료를 추정하지 않음 | 새 등록 ID로 회피하거나 잔여를 자동 삭제하지 않음. 보호 설정·현재 권한·자료 연결/바이트·필요 시 C/E 불일치를 조사 |

정상 해제도 장애 직전의 성공 여부를 추측해 복구하는 기능이 아니다. 부팅·재실행 시 잔여 발견은 HOLD다. 담당자는 조사 사유·대상 객체/이력·조치 전후를 비공개 기록하고, 승인된 잔여에 대해서만 격리/해제를 결정한다. 복구/폐기 명령은 아직 구현하지 않는다.

같은 `local_evidence_id`의 최신 이력/중복 확인부터 재검증·향후 C/E 처리·반환 전 대조까지 같은 전역 배타 구간에 포함해야 한다. 관리자 설정 변경도 §2의 같은 Gate에 참여하는 우선 시험 방향이다. 경로/조상 핸들 유지·볼륨/파일 ID·ACL 재대조 없이는 잠금 파일만으로 경로 교체가 해결됐다고 판단하지 않는다.

### 4.1 정상 해제 API와 중단 경계

시험할 순서는 `CreateFileW(GENERIC_READ | GENERIC_WRITE | DELETE, share=0, CREATE_NEW)` → 생성 핸들로 객체 ID/설명자 확인 및 필요한 동작 → 정상 결과·자료 일관성 확인 → **그 핸들**로 `SetFileInformationByHandle(FileDispositionInfo, FILE_DISPOSITION_INFO.DeleteFile=TRUE)` → `CloseHandle`이다. `DELETE` 접근이 필요하고 각 BOOL/오류 코드를 확인한다. `FILE_DISPOSITION_INFO`의 DeleteFile은 Win32 `BOOLEAN` 크기로 선언해야 하며 `BOOL`과 혼동하지 않는다. 경로로 DeleteFile/remove를 호출하거나 share 충돌 때문에 먼저 닫고 재개방하지 않는다. 이 순서는 문서와 대조한 후보이며 아직 시험/구현하지 않았다. [해제 API·DELETE 요구사항](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle), [FILE_DISPOSITION_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info).

정상 검증을 마치기 전에는 삭제 예약을 하지 않는다. 실패/취소/부분 쓰기에서는 삭제 예약 없이 핸들만 닫고 HOLD를 보존한다. 삭제 예약 또는 CloseHandle 실패 시에도 자동 경로 삭제로 보상하지 않는다. 해제 후 같은 이름이 나타나도 다음 프로세스의 새 객체일 수 있으므로 지우지 않는다.

**삭제 예약과 CloseHandle 사이의 한계:** 이 사이에 프로세스가 죽어 OS가 핸들을 닫으면 Gate 파일이 없어질 수 있다. 이는 위 API 계약에서 도출한 실패 경계이며 그 창의 강제 종료를 실측한 결과는 아니다. 따라서 모든 강제 종료에서 Gate 파일이 반드시 남는다는 보장은 할 수 없다. 남은 작업 자료/미확정 이력을 별도로 확인하고, 결과 미확인은 Gate 유무와 무관하게 HOLD다. 이번 SYN-05의 강제 종료는 삭제 예약 전, 부분 쓰기 후라는 제어된 지점에서만 시험한다. 삭제 예약 전후의 추가 크래시·전원 손실·내구성은 후속 통합 검증이며 잠금 취득/해제 성공으로 등록 성공을 만들지 않는다.

## 5. Windows 읽기 전용 실측 — v0.2 최초 작성 단위의 실행 기록

### 5.1 실행한 PowerShell 명령과 부작용 경계

저장소 루트에서 실행했다. PowerShell **7.6.9 Core, 64-bit Windows**. 다음 명령과 조회 도구는 파일/디렉터리·Allowlist·DACL·소유권·디스크 구성·토큰 권한을 변경하지 않는다.

```powershell
$PSVersionTable.PSVersion
Get-Command Get-Volume, Get-Partition, Get-Disk, Get-Acl, Get-CimInstance
python -B .\tools\fr_b02b_cli\diagnostics\phase4b2_environment_readonly.py
.\tools\fr_b02b_cli\diagnostics\phase4b2_storage_readonly.ps1
git ls-remote --heads origin feat/phase4b2-protected-review-registration
```

`Get-Acl`/`Get-CimInstance`는 사용 가능 여부만 조회했다. 실제 보안 설명자는 아래 Native 도구로 읽었다. 두 도구는 앱의 인증/설정 공급자에 연결되지 않은 별도 진단 도구이며 `operational_approval=NONE`을 출력한다.

| 도구 | 실제 읽기 전용 호출 | 출력/자원 처리 |
|---|---|---|
| [Native 진단](../../../tools/fr_b02b_cli/diagnostics/phase4b2_environment_readonly.py) | `SHGetKnownFolderPath` flags=0(KF_FLAG_CREATE 없음), 조상 `lstat`, `GetNamedSecurityInfoW` OWNER+DACL만, `GetSecurityDescriptorControl`; `OpenProcessToken(TOKEN_QUERY)`·`GetTokenInformation`·`EqualSid` | 설명자/토큰/폴더 메모리 해제. 실제 SID 문자열·계정명·SDDL·ACE 내용 미출력. 표준 ProgramData 위치만 공개, 비표준 위치는 마스킹. 재분석 조상 발견 시 하위 조회 중단 |
| [저장장치 진단](../../../tools/fr_b02b_cli/diagnostics/phase4b2_storage_readonly.ps1) | C/E 각각 `Get-Volume -DriveLetter`, `Get-Partition -DriveLetter`, `Get-Disk -Number` | 원시 볼륨/디스크 UniqueId는 메모리에서 존재·상이 여부만 비교. 일련번호/레이블/장치 경로 미출력. Set/New/Initialize/Format/ACL setter 없음 |

실행 도구의 제한된 샌드박스에서는 Storage 조회가 C/E 모두 `CimException`으로 미검증이었다. 같은 읽기 전용 명령을 실행 샌드박스 밖에서 재조회해 아래 결과를 얻었다. **UAC RunAs/관리자 상승·토큰 활성화는 하지 않았다.** 그 컨텍스트의 실제 프로세스 토큰은 아래처럼 비승격이었다. 진단 도구 작성 중 고정 크기 토큰 정보의 0바이트 크기 질의가 `ERROR_BAD_LENGTH(24)`로 실패해 해당 종류만 고정 출력 버퍼로 수정한 뒤 재실행했다. 운영 CLI 소스 변경은 없다.

### 5.2 비식별 출력 요약

| 조회 항목 | 실제 결과 | 이 결과로 판정할 수 없는 것 |
|---|---|---|
| ProgramData Known Folder | `C:/ProgramData`, C: 위치 확인 | 운영 전용 루트 승인·보호 검증 아님. API 경로 반환은 ACL 보증이 아님 |
| 제안된 전용 경로 | ProgramData 하위 `TrendLeader` 부모 없음. 따라서 `ProtectedReview/Config/Store/settings.json/reviewers.json` 후보도 부모 부재 상태. `E:/TrendLeaderProtectedReview` 없음 | 후보 하위 각각에 기존 객체가 있는 것처럼 설명자 검사하지 않았음. 조회 시점 이후 선점/교체·최종 경로 승인 미검증 |
| C: | NTFS / Fixed / NVMe / DiskNumber 0, 파티션 매핑 1개. 볼륨/디스크 ID 존재 | 일반 검토자의 쓰기·flush·rename·잠금 가능성 미시험 |
| E: | NTFS / Fixed / NVMe / DiskNumber 1, 파티션 매핑 1개. 볼륨/디스크 ID 존재 | 백업·복원 가능성/운영 보호 ACL 미시험 |
| C/E 대조 | DiskNumber·볼륨 ID·디스크 ID가 서로 다름. 두 디스크 IsOffline=false, IsReadOnly=false | OS가 구분하는 장치임을 확인했을 뿐 오프사이트/독립 불변성·파일 쓰기 성공은 증명하지 않음 |
| ProgramData 기존 루트 설명자 | 조회 성공, owner 존재, DACL 존재/non-NULL, ACE 5개, DACL protected=true | owner가 승인된 주체인지·ACE 전체 마스크/유효 접근권은 이번 범위에서 판정하지 않음 |
| E: 기존 루트 설명자 | 조회 성공, owner 존재, DACL 존재/non-NULL, ACE 8개, DACL protected=false | E: 전체 ACL을 결함으로 판정하거나 변경하지 않음. 향후 새 전용 경계를 별도 검증해야 함 |
| 실제 비승격 프로세스 토큰 | `is_elevated=false`, `elevation_type=Limited` | 이 토큰의 생성·삭제·권한 변경 거절 여부는 쓰기 시험 전까지 미검증 |
| 연결된 토큰 속성 | `is_elevated=true`, `elevation_type=Full`, 메모리 SID 비교 `same_user=true` | 연결 토큰을 사용해 프로세스를 시작하지 않았고 실제 승격 I/O·그룹/특권·유효 권한 전체를 비교하지 않았음 |
| 제한된 실행 샌드박스 토큰 | 비승격 `Default`, 연결 토큰 조회 불가 | 위 비승격 Limited 컨텍스트와 구분. 이 실패를 실제 사용자 계정에 연결 토큰이 없다는 증거로 사용하지 않음 |

폴더 경로 조회, 연결 토큰과 일반 토큰의 구분, Storage 조회는 각각 공식 API 의미에 맞춰 해석했다. [Known Folder 조회](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath), [TOKEN_ELEVATION_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_elevation_type), [TOKEN_LINKED_TOKEN](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_linked_token), [Get-Disk](https://learn.microsoft.com/en-us/powershell/module/storage/get-disk).

## 6. 다음 합성 ACL 시험의 정확한 범위 — 이번에는 미실행

다음은 **별도 승인 후** 수행할 합성 시험 전체 후보 목록이다. 현재 준비 범위는 §6.1의 **C: 단독 SYN-01·02·05**이며 E: 생성/쓰기와 나머지 시험은 후속 범위다. 운영 디렉터리나 실제 Allowlist를 만드는 승인으로 해석하지 않는다.

| ID | 승인 후 수행할 시험 | 확인할 결과 |
|---|---|---|
| SYN-01 | 충돌하지 않는 C: 새 시험 루트에 관리자 초기 구성. Config/Store/locks 분리, 초기 소유자/ACE/상속·ID 읽기 대조. E: 시험 루트는 후속 별도 승인 | 기존 객체·상위 전역 ACL 변경 0. 실제 일반 토큰에 필요한 조회·설명자 읽기 가능 |
| SYN-02 | 비승격 R로 Config 읽기와 내용 변경·삭제·권한/소유자 변경 시도; 합성 Store 신규 생성·쓰기·flush·읽기·제한 rename·정상 잠금 해제 | 필요한 동작 성공 + 불필요한 작업 OS 거절을 모두 확인. 마스크가 부족하거나 넓으면 후보표 수정, 자동 수리 없음 |
| SYN-03 | 시험 객체에만 잘못된 소유자·넓은 그룹/상속·NULL/빈 DACL·미지원 ACE·부모 DELETE_CHILD 반례 구성 | Native 설명자 검증과 실제 접근 결과 교차 대조, 부적격이면 BLOCKED/HOLD. 임의 ACL을 정답으로 Mock하지 않음 |
| SYN-04 | 시험 조상/루트 재생성·rename·junction/symlink·동일 경로 다른 ID 교체, 핸들 공유 제한 대조 | 잘못된 객체 쓰기 0, Native 핸들/ID/ACL 검사 또는 OS 거절로 탐지. 링크 생성 권한이 없으면 그 사례 미실행 |
| SYN-05 | 독립 두 프로세스로 같은 잠금 경쟁, 다른 cwd에서도 동일 gate 확인. 정상 해제·생성 직후/부분 쓰기 직후 프로세스 중단 후 재실행 | 단일 진입, 충돌 및 중단 잔여 HOLD, 자동 삭제/만료/새 ID 우회 0. 설정 변경 gate를 선택하면 관리자 변경 경쟁도 포함 |
| SYN-06 | 기존 다른 일반 계정이 있으면 Config/Store 접근 거절 비교. 승격 관리 컨텍스트의 설정 작업과 비승격 검토 작업을 별도 실행·기록 | 같은 계정의 연결 토큰 속성 조회를 독립 사용자 검증으로 대신하지 않음. 계정/승격 시험 미준비면 미검증, 계정 자동 생성 없음 |
| SYN-07 | 후보 C/E 시험 루트의 볼륨/객체 ID 바인딩·E 설정 누락/오지정 차단 및 비식별 오류 출력 | 운영 CLI 활성화·실제 C/E 등록/백업/복원/완료 표식 없이 설정 부적격 차단만 시험 |

실제 E: 분리/오프라인 전환·포맷·드라이브 문자 변경·E: 전체 ACL 변경은 이 시험 계획에 포함하지 않는다. 실제 승인 ZIP·관측 기록·비밀은 사용하지 않는다. 실제 계정 SID가 필요한 합성 ACL 증거는 비공개 위치에 두고 공개 Git에는 반영하지 않는다. 모든 실패에서 원본 불변·유효 등록 없음·잔재 사용 불가 HOLD를 확인한다.

정상 정리는 승인된 시험 객체임을 ID/경계로 확인한 후만 수행하는 별도 절차로 정한다. 크래시/실패 잔재를 시험 종료 편의로 자동 삭제하지 않는다. 이 시험에 통과해도 C/E 등록·백업/복원·완료 판정·철회 전체의 운영 PASS는 아니다. v0.1의 나머지 OP-09~11 통합 조건은 후속 범위에 남는다.

### 6.1 SYN-01·02·05 실행 승인용 계획 — 미실행

**시험 루트 후보:** `C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01` 하나만 사용한다. Native Known Folder가 `C:\ProgramData`와 다르거나 후보가 이미 존재/재분석/식별 불명확이면 중단한다. 기존 루트를 재사용하거나 R02 등으로 자동 우회하지 않는다. 운영 후보 `TrendLeader\ProtectedReview`와 분리된 새 형제 영역이며 E:에는 객체를 만들지 않는다. 이 절대 경로는 승인 전 시험 후보이고 운영 설정이 아니다.

승인 대상 객체는 아래 상대 이름으로 제한한다. 미정의 파일/디렉터리가 나타나면 HOLD다. 합성 settings/Allowlist는 실제 CLI에 연결하지 않는다. 가짜 콘텐츠와 현재 토큰에서 얻은 R의 비공개 SID만 사용하며 실제 A1 ZIP/4A 기록은 읽거나 복사하지 않는다.

```text
<시험 루트>\
  Config\settings.synthetic.json
  Config\reviewers.synthetic.json
  Control\inventory.private.json
  Store\work\SYN02\io.bin             # 성공 시 io-renamed.bin으로 이동
  Store\work\SYN05-crash\partial.bin  # 중단 후 보존
  Store\locks\global.gate             # 모든 프로세스/관리자 변경의 단일 조정 객체
  Evidence\syn01.public.json
  Evidence\syn02.public.json
  Evidence\syn05.public.json
  Evidence\native.private.json
```

`Control/inventory.private.json`은 승인된 시험 루트/객체·볼륨 ID, 초기 Config 실제 바이트 SHA-256, 소유자·DACL/상속 상태를 기록하는 **시험 인벤토리**다. 처음 신뢰를 이 인벤토리의 자기 경로/해시에 의존하지 않는다. 관리자 초기 보호 검증 후 생성하고 Store 프로세스는 읽기만 한다. Evidence는 시험 기록일 뿐 FROZEN의 `registration_complete.json` 같은 완료 표식이 아니다.

#### 시험 ACL 후보 — 운영 확정표 아님

새 시험 객체만 아래 후보로 구성한다. 기존 ProgramData/E:/사용자 프로필/Git 객체의 ACL·소유자는 변경하지 않는다. 초기 관리 작업은 명시적 승격 토큰에서만, SYN-02/05 작업 프로세스는 `TokenElevation=false`인 R에서만 실행한다. 필요한 특권이 부족하면 중단하며 자동 상승/특권 부여/계정 생성은 하지 않는다.

기호의 시험 마스크는 `D_READ=FILE_GENERIC_READ|FILE_TRAVERSE (0x001200A9)`, `F_READ=FILE_GENERIC_READ (0x00120089)`, `F_WRITE=FILE_GENERIC_WRITE (0x00120116)`이다. generic 비트의 파일별 매핑을 전제로 한 후보이며 실제 요청/부여 마스크를 Native 조회와 대조해야 한다. A/S에는 새 시험 객체의 관리용 `FILE_ALL_ACCESS` 후보, R에는 표의 Allow만 둔다. 포괄 그룹 Allow나 Everyone Deny를 추가하지 않는다. [generic 권한 매핑](https://learn.microsoft.com/en-us/windows/win32/secauthz/generic-access-rights), [파일 비트](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants).

| 새 시험 객체 | 소유자 후보 | R Allow 후보 | DACL/상속 기대 |
|---|---|---|---|
| 시험 루트, Config, Control, Store | A | D_READ | 보호 DACL, A/S와 R의 명시 ACE만, 부모의 넓은 ACE 유입 없음 |
| 합성 Config 파일, inventory.private.json | A | F_READ | 보호 DACL, R 쓰기/삭제/WRITE_DAC/WRITE_OWNER 없음 |
| Store/work | A | D_READ + FILE_ADD_FILE + FILE_ADD_SUBDIRECTORY | 보호 DACL, R의 컨테이너 DELETE/FILE_DELETE_CHILD/WRITE_DAC/WRITE_OWNER 없음 |
| Store/locks, Evidence | A | D_READ + FILE_ADD_FILE | 보호 DACL, 컨테이너 삭제/FILE_DELETE_CHILD 없음 |
| R이 새로 만드는 SYN02/SYN05-crash 디렉터리 | R | D_READ + FILE_ADD_FILE + FILE_ADD_SUBDIRECTORY + DELETE | 생성 시 제한 설명자 명시, 생성 후 같은 객체 대조 |
| 신규 io/partial/증거 파일 | R | F_READ + F_WRITE, io rename 시험 파일에만 DELETE 추가 | 생성 시 보호 DACL과 명시 ACE, 미승인 상속 ACE 0 |
| 새 global.gate | R | F_READ + F_WRITE + DELETE | 생성 시 보호 DACL과 명시 ACE, share=0. 기존 Gate 수정 권한을 앱의 재사용 허가로 해석하지 않음 |

시험에서는 각 객체에 명시적 보호 DACL을 주는 단순한 후보부터 확인한다. 제한 부모 상속을 쓰는 운영 대안은 배제하지 않지만 이번 시험의 상속 기대값과 섞지 않는다. 객체 생성 시 `SECURITY_ATTRIBUTES`로 제한 설명자를 공급하고 생성 후 확인한다. 보호 상태가 확인되기 전 실제 SID를 담은 파일을 쓰지 않는다. 새 R 소유 파일의 암묵적 소유자 권한은 남으므로 WRITE_DAC가 독립적으로 거절된다고 주장하지 않는다. Config 거절 시험은 A 소유 객체에서 수행한다.

#### SYN-01 — 새 루트 초기 구성

- 사전 확인: 승인된 경로/작업자, Native Known Folder, 현재 관리자 토큰, 기존 후보 부재, 조상 재분석/교체 위험 및 볼륨 상태를 읽기 전용 확인한다. 충돌이면 생성 0, 기존 객체 변경 0으로 중단한다.
- 생성/변경: 관리자가 위 루트와 Config/Control/Store/work/Store/locks/Evidence 및 초기 합성 Config/인벤토리만 새로 만든다. 소유자·DACL 변경은 이 **새 객체**에만 한정한다. SYN02/SYN05-crash 디렉터리, Gate, 작업/증거 파일은 해당 후속 단계에서만 생성한다.
- 검증: 핸들 기반 소유자·DACL 존재/non-NULL·보호 비트·ACE SID/마스크/유형/플래그·상속 ACE 0·볼륨/파일 ID를 확인한다. 미지원 ACE/예상 외 소유자/마스크/부분 생성이면 즉시 HOLD, 자동 ACL 수리/삭제/재실행 없음. 새 파일 private 값 기록 전 보호 상태를 확인한다.
- 정리/증거: 성공해도 루트를 자동 삭제하지 않는다. public에는 객체 상대 이름·정책 일치 boolean·오류 범주만, private에는 실제 SID/SDDL/ID/바이트 해시를 제한 보관한다. 다른 사용자 접근 거절까지 SYN-01만으로 인증하지 않는다.

#### SYN-02 — 비승격 Config 거절·Store 작업

- 사전 확인: SYN-01 검증 완료, R 토큰 비승격·SID 연결·초기 Config 바이트/설명자 일치 확인. 랩의 합성 권한 모델이며 실제 CLI Allowlist/Store 성공 대역에 연결하지 않는다. 같은 전역 Gate를 취득/검증한 뒤 작업한다.
- Config는 같은 API/플래그의 대조군으로 정상 읽기가 가능해야 한다. 디렉터리는 `OPEN_EXISTING` + `FILE_FLAG_BACKUP_SEMANTICS`를 사용하고 재분석 지점은 열어서 판정한 뒤 거절한다. 토큰의 활성 backup/restore/take-ownership 특권으로 거절 시험을 우회하지 않으며 그런 특권이 활성 상태면 일반 토큰 시험을 중단한다. 특권은 자동 변경하지 않는다.
- 파일의 `FILE_WRITE_DATA`, `FILE_APPEND_DATA`, `DELETE`, `WRITE_DAC`, `WRITE_OWNER` 및 디렉터리의 `FILE_ADD_FILE`, `FILE_ADD_SUBDIRECTORY`, `FILE_DELETE_CHILD`, `DELETE`, `WRITE_DAC`, `WRITE_OWNER` 접근을 **각각 별도 OPEN_EXISTING 핸들 요청**으로 시험한다. 기대값은 `ERROR_ACCESS_DENIED(5)`다. 다른 오류는 ACL 거절 PASS가 아니다. 예상 외 핸들 획득 시 즉시 닫고 FAIL/HOLD로 중단하며 실제 Config 내용/ACL을 바꾸지 않는다. 속성/EA 쓰기 권한도 별도 거절 대상으로 기록한다.
- Store에서는 SYN02 디렉터리와 `io.bin`을 새로 생성해 고정 합성 바이트 쓰기 → FlushFileBuffers → 같은 바이트 읽기/해시 → 덮어쓰기 없는 `io-renamed.bin` 이동을 시험한다. 기존 경로면 중단한다. 필요한 접근권/Native 반환값/설명자/동일 객체 ID를 대조한다. Config 바이트·객체/설명자는 전후 불변이어야 한다.
- 성공 시 자기 Gate만 §4.1 순서로 정상 해제하고 작업/증거 파일은 보존한다. 단계 실패 시 생성 Gate/부분 자료는 HOLD, 자동 삭제/권한 완화/폴더 재생성 없음. public에 실제 SID/개인 경로/SDDL/원시 예외를 내보내지 않는다.

#### SYN-05 — 독립 프로세스·정상 해제·중단

1. 선행 정상 Gate가 해제되고 SYN-01/02가 충족된 뒤 시작한다. R의 독립 P1/P2를 다른 cwd에서 실행하되 같은 절대 전역 Gate를 사용한다. 부모 제어기는 자신이 시작한 자식만 PID/생성 시각/시험 nonce로 식별한다. UI 창/관리자 상승/다른 프로세스 종료는 하지 않는다.
2. P1이 `CREATE_NEW`로 취득하고 획득 사실을 IPC로 알린 상태에서 P2가 같은 취득을 시도한다. 하나만 진입해야 한다. P2의 파일 존재/공유 충돌(예: 80/183/32)은 차단/HOLD로 기록하고 기존 Gate를 수정하지 않는다. 접근 거부 5 등 다른 원인은 경쟁 검증 PASS가 아니다. 타임아웃도 미검증/HOLD이며 자동 재시도하지 않는다.
3. P1이 같은 핸들의 ID/설명자와 작업 상태를 확인한 후 §4.1로 정상 해제한다. 정상 해제 확인 후에만 P2의 **별도 명시적 새 시도**가 신규 객체로 취득/정상 해제되는지 확인한다. 해제 중 이름으로 다른 객체를 삭제하지 않는다. 이 정상 순서가 실패하면 중단 시험으로 넘어가지 않는다.
4. 마지막에 별도 자식 P3이 Gate 취득 → `Store/work/SYN05-crash/partial.bin`에 합성 일부 바이트 쓰기/flush → 삭제 예약 전 IPC 대기 지점까지 진행한다. 부모는 일치가 확인된 그 자식만 강제 종료한다. Gate와 partial 파일/바이트·객체 ID가 남고, 새 프로세스의 취득/자료 사용은 HOLD여야 한다. Gate/partial을 삭제·승격하거나 새 이름으로 우회하지 않는다. 이 잔재 때문에 이후 시험은 수동 조사 전까지 멈춘다.
5. 이 최소 중단 사례는 **부분 쓰기 후·삭제 예약 전 한 지점**이다. 생성 직후 별도 중단, 삭제 예약 이후 크래시, 전원 장애는 이번 시험 결과에 포함하지 않는다. 다른 일반 계정/세션·Gate 비참여 관리 도구의 강제 변경도 후속 검증이다. 동일인 관리자 변경 참여를 시험하려면 별도 승인된 관리자 절차가 같은 Gate를 취득해야 하며, 바쁜 동안 Config 변경 0인지를 확인한다.

증거는 자식별 취득/임계 구간 진입/삭제 예약/close/종료 phase와 Win32 코드·단일 진입 횟수·객체 동일 여부·Config 전후 동일 여부를 비식별 JSON으로 남긴다. 실제 PID/nonce·SID·SDDL·File ID는 private 기록에만 둔다. 부분 자료는 실제 등록 파일이 아니며 유효 registration_id/성공 응답/완료 표식 생성은 항상 0이다.

#### 공통 종료·정리 및 승인 경계

정상 Gate 해제 외에는 전체 시험 루트/증거를 자동 정리하지 않는다. 승인된 새 객체 목록과 private 인벤토리의 정체성을 대조한 **추가 수동 정리 승인** 후에만 해당 시험 루트 안의 확인된 객체를 정리한다. 경계 불명확·재분석·ID 변경·미정의 자식이면 정리 중단이다. 실패/크래시의 Gate/partial은 조사·보존 승인 전 삭제하지 않는다. ProgramData/E:/사용자 프로필/Git에 대한 재귀 ACL/소유권 변경·삭제는 허용하지 않는다.

현재 승인 요청 범위는 위 **C: 신규 시험 객체와 그 객체의 초기 ACL/소유자, 관리자 초기 구성, R의 I/O·자기 Gate 정상 삭제, 식별된 시험 자식의 한 번 강제 종료**다. 구체 경로·R의 비공개 SID·후보 ACE/마스크·담당자·증거 보관/보존·정리 조건 확인 후 별도 실행 승인이 필요하다. 실제 실행용 하네스는 이 경계의 승인/검토 후 준비한다. 이번에는 문서 계획만 보완하며 기존 읽기 전용 진단 도구와 앱 코드는 바꾸지 않는다.

## 7. 미확정 결정과 v0.2 최초 작성 단위의 검증 기록

사용자 결정이 필요한 사항:

- ProgramData 원본·Config 부트스트랩·E 백업의 최종 절대 경로와 승인된 루트/볼륨 ID, 시험 전용 위치.
- 초기 설정 담당자, Allowlist 승인/적용/비활성·폐기 책임자, 사고 조사/복구·잔재 정리 승인자. 겸임 여부와 비공개 증거 보관/보존 기간.
- 객체·생성/완료 단계별 소유자·SID·ACE 유형·마스크·상속·공유 모드. R 소유 파일의 신뢰 한계 수용과 추가 봉인 필요 여부.
- 단일 전역 Gate의 고정 물리 위치/식별 연결, 정상 자기 잠금 삭제 방식의 실측, 중단 자료 수동 조사/해제 책임·절차.
- 승격 검토 CLI 처리 정책, 다른 일반 계정 사용 가능 여부 및 관리자 합성 시험 실행 승인.

이번에는 런타임·테스트 소스 및 FROZEN을 수정하지 않았다. `archive_bytes` 및 Service 재검증 중복 구현 없음. v0.1과 기존 patch·미추적 자료는 보존했다. 새 문서·읽기 전용 진단 도구 2개와 README 안내만 추가했다.

| 실행 | 결과 |
|---|---|
| `python -B -m unittest discover -s tests -q` (`tools/fr_b02b_cli`에서 Python 3.14) | 145개, OK. 기존 4A·4B-1·4B-2 합성 회귀이며 운영 ACL 시험 아님 |
| Ruff 모듈 사용 가능 여부 | 미설치, Ruff 미실행. 정적 검사 PASS로 보고하지 않음 |
| 새 진단 도구 | 위 Windows 실제 읽기 전용 조회 실행. ACL 변경/쓰기/AccessCheck·승격 실행·운영 보호 검증 없음 |
| 새 도구 구문 검사 | Python `ast.parse` 성공, PowerShell Parser 오류 0. PowerShell CommandAst 목록은 Get-Volume/Get-Partition/Get-Disk/ConvertTo-Json뿐. 구문 검사이며 보안·정적 분석 완료 아님 |
| `git diff --check` | 종료 코드 0, 공백 오류 없음. 기존 AGENTS.md 줄바꿈 경고는 수정하지 않음 |

GitHub 커밋·푸시·PR, 운영 디렉터리/Allowlist/ACL/소유권 변경, C/E 등록·백업/복원·완료 표식·철회·실제 CLI 활성화는 수행하지 않았다. 본 문서는 FROZEN을 개정하거나 운영 보안을 인증하지 않는다.

### Git 작업 트리 상태

`git -c core.quotepath=false status --short`의 결과다. 긴 문서 디렉터리만 `<설계문서>/`로 축약했다. 네 개 M 경로는 작업 시작 시부터 존재했고, 이번에는 README 안내만 추가했다. 이번 신규 파일은 v0.2와 읽기 전용 진단 도구 두 개다. 나머지 미추적 자료는 기존 사용자 작업으로 보존했다.

```text
 M tools/fr_b02b_cli/README.md
 M tools/fr_b02b_cli/fr_b02b_a1_adapter.py
 M tools/fr_b02b_cli/fr_b02b_cli.py
 M tools/fr_b02b_cli/fr_b02b_observation.py
?? <설계문서>/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.1_DRAFT_20261110.md
?? <설계문서>/Trend_Leader_Phase4B2_운영_보호_저장소_Windows_ACL_구성_후보안_v0.2_DRAFT_20261110.md
?? docs/infra/
?? tools/fr_b02b_cli/fr_b02b_protected_store.py
?? tools/fr_b02b_cli/fr_b02b_review_service.py
?? tools/fr_b02b_cli/fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/fr_b02b_windows_auth.py
?? tools/fr_b02b_cli/phase4b2_b42_04_review.md
?? tools/fr_b02b_cli/phase4b2_environment_readonly.py
?? tools/fr_b02b_cli/phase4b2_implementation_plan.md
?? tools/fr_b02b_cli/phase4b2_staging_code_and_tests.patch
?? tools/fr_b02b_cli/phase4b2_staging_review.md
?? tools/fr_b02b_cli/phase4b2_storage_readonly.ps1
?? tools/fr_b02b_cli/tests/test_fr_b02b_protected_store.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_decision.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_registration.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_review_service.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_reviewer_allowlist.py
?? tools/fr_b02b_cli/tests/test_fr_b02b_windows_auth.py
```

상태 조회는 루트/backend/frontend의 기존 `.pytest_cache/` 열람 거부 경고를 냈다. 해당 캐시를 수정하거나 접근권을 변경하지 않았고, 그 내부는 이 status로 확인하지 못했다. 추적 파일 diff는 기존 구현 변경을 포함하므로 이번 문서 작업만의 diff로 오인하지 않는다.

## 8. SYN 준비 보완 단위의 검증 기록 — 실행 승인 전

현재 브랜치는 `feat/phase4b2-protected-review-registration`, 로컬 HEAD와 `git ls-remote --heads origin feat/phase4b2-protected-review-registration`의 원격 HEAD는 `b133b494f8258eea603243f8f07191a33290084a`다. 이전 실측 기준 이후의 커밋은 AGENTS.md v1.1 개정이다. 최초 원격 조회는 샌드박스 네트워크에서 실패했고 읽기 전용 재조회로 확인했다. 원격 쓰기는 없다.

| 이번 실행 | 실제 결과 |
|---|---|
| `python -B -m unittest discover -s tests -q` (`tools/fr_b02b_cli`에서) | Python 3.14.0, 145개 / 5.437초 / OK. 기존 합성 회귀이며 SYN-01·02·05 실행 아님 |
| Ruff 사용 가능 여부 | 미설치, 미실행. 테스트 통과와 정적 검사 완료를 구분 |
| `git diff --check`, `git diff --cached --check` | 모두 종료 코드 0. 미추적 대상 DRAFT는 별도 본문/변경 대조로 검토 |
| `Test-Path -LiteralPath 'C:\ProgramData\TrendLeaderPhase4B2AclLab-20261110-R01' -ErrorAction Stop` | 읽기 전용 존재 조회, false. 경로 승인/조상 보호/향후 선점 방어 PASS가 아님. 실제 생성 전 다시 확인 필요 |
| 변경 전후 보존 확인 | 기록한 25개 파일의 SHA-256 비교에서 이 v0.2만 변경, 나머지 24개 동일. 기존 미추적 자료·코드·검사 대상 FROZEN 포함. 열람 거부 캐시 내부는 이 검증 범위 밖 |
| SYN-01·02·05 | **모두 미실행**. 관리자 상승·새 시험 디렉터리/파일·Gate 생성·ACL/소유권 변경·자식 강제 종료 0 |

이번 변경 파일은 이 DRAFT v0.2 하나다. §2.1 부트스트랩·§4.1 Native 정상 해제·§6.1 승인용 시험 계획과 현재 검증 기록을 보완했다. §5·§7의 이전 실측/작성 기록은 이번 실행과 구분한다. 기존 조회 도구·README·런타임/테스트·v0.1·FROZEN·미추적 docs/infra 및 다른 사용자 파일은 수정하지 않는다. 작업 트리의 M/?? 경로 목록은 §7 기록과 같으며, 작업 시작 때 이미 v0.2도 미추적 상태였다. 커밋·푸시·PR·실제 운영 CLI 활성화는 수행하지 않는다.

ProgramData A안·Config/Store 분리·단일 전역 Gate·실패 잔재 HOLD는 우선 시험 방향으로 정리할 수 있다. 실제 절대 운영 경로·비공개 SID/관리 책임자·배포 ACE·부트스트랩 정책 공급·비참여 관리자 변경 통제·내구성/추가 크래시 및 복원 조건은 아직 미확정/미검증이다. 이 문서 보완과 기존 145개 회귀는 FROZEN 변경이나 운영 보안 PASS가 아니다.
