# Phase 4B-2 운영 보호 저장소 및 Windows ACL 구성 후보안 v0.1

> **상태: DRAFT — 후보 검토 전용 / 경로·관리 책임·ACL 정책 미확정 / 운영 검증 미실행**  
> 작성일: 2026-11-10 KST  
> 저장소: `Trend-Leader-capstoneProject/feature`  
> 작업 브랜치: `feat/phase4b2-protected-review-registration`  
> 로컬 및 읽기 전용 원격 조회 HEAD: `8d49cb33e91b7a09def95084d54810b92132b32a`  
> 기준: [Phase 4B-2 FROZEN v1.0](Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md) §4.1·§4.2·§6.1·§6.2, 기존 4A·4B-1 계약 불변  
> 이 문서는 운영 디렉터리/ACL/Allowlist 생성·변경이나 등록·게시 승인이 아니다. 기존 FROZEN을 개정하지 않는다.

## 1. 이번 실제 코드 확인 결과

### 1.1 archive_bytes 타입·크기 검사

`tools/fr_b02b_cli/fr_b02b_protected_store.py`의 `_validated_files()`는 A1Snapshot 타입을 확인한 뒤 내부 A1 검증기를 호출한다. 검사 흐름은 다음과 같다.

```text
ProtectedEvidenceStore.stage
  → _validated_files
    → _load_a1_snapshot_bytes(evidence.a1_snapshot.archive_bytes)
      → isinstance(raw, bytes) 검사
      → len(raw) <= MAX_ARCHIVE_BYTES 검사
      → 그 이후에만 BytesIO/ZipFile 파싱
```

`MAX_ARCHIVE_BYTES = 20 * 1_048_576 = 20,971,520`바이트(20 MiB)다. 비-bytes 값은 단락 평가로 len() 호출 전에 거절된다. 오류는 A1InspectionError를 거쳐 Store의 StagingError로 변환되고 원시 값은 메시지에 포함하지 않는다. 같은 검사를 Store에 중복 구현할 필요는 발견하지 못했다.

`None`, 정수, 문자열, bytearray, memoryview, 20 MiB+1 bytes를 주입하는 회귀 테스트 1개(6개 하위 사례)를 추가했다. ZIP 파서·원본 재검증 콜백이 호출되지 않고 스테이징 루트가 비어 있음을 확인했다. 테스트는 처음부터 Green이었다. 기존 방어가 이미 있어 수정 전 Red나 런타임 결함을 주장하지 않는다.

### 1.2 Service 콜백의 실제 호출 흐름

```text
stage_pending_review
  → _revalidate_pending_review(초기 검증)
  → 같은 검증 바이트로 pending 메타데이터 구성
  → Store.stage(..., revalidate_input=closure)
       → 디렉터리 예약 전 closure
       → 각 4개 파일 쓰기 직전 closure
       → 복사본·보호 상태 대조 후 반환 직전 closure

closure → 매번 _revalidate_pending_review(decision, archive_path, record_dir, allowlist_source)
```

정상 경로에는 초기 1회와 Store 내부 6회가 있다. 각 호출은 다음 작업을 실제로 다시 수행하며, 이전 PASS 값만 재사용하지 않는다.

- 현재 ZIP·observation.json·index.json을 읽기 전용으로 재검증한다. 새 VerifiedObservation 전체와 검토 당시 객체를 비교하므로 세 원시 바이트 및 검증된 표시값의 차이를 거절한다. JSON/인덱스를 함께 일관되게 재해시해도 검토 당시 바이트와 다르면 거절한다.
- 프로세스 토큰 SID를 다시 얻고 Allowlist 파일·활성 역할·보호 경계를 다시 검사한다. 현재 SID와 검토 결정 SID가 다르면 거절한다.
- NONE, 유효 결정·사유·local_evidence_id 연결을 재검사한다. reviewed_at_utc는 원본 4A 생성 시각 이상이고 현재 UTC보다 늦지 않아야 한다. 앞선 결정 단계는 입력 전/후 시계 역행도 별도로 검사한다.

콜백은 요구된 현재 조건을 충족하므로 Service 재구현은 하지 않았다. 이 검사는 모든 검사 사이의 적대적 경합이나 독립 시각 인증을 보증하지 않는다. 단계 전체 UTC 표본의 단조성, 향후 registration_recorded_at_utc와의 순서·재시작 시각 처리는 운영 통합 시험에서 별도로 확정해야 한다.

### 1.3 실제 검증과 변경 범위

Python 3.14, `tools/fr_b02b_cli/`:

| 실행 | 실제 결과 |
|---|---|
| 시작 전 `python -B -m unittest discover -s tests -q` | 144개 OK |
| `python -B -m unittest discover -s tests -p test_fr_b02b_protected_store.py -q` | 16개 OK |
| 최종 `python -B -m unittest discover -s tests -q` | 145개 OK |
| Ruff 사용 가능 여부 | 미설치, 미실행 |

런타임 소스 수정은 없다. 테스트 파일 1개에 회귀 1개 추가, 이 DRAFT와 README 안내만 추가했다. 기존 스테이징 patch는 144개 단계의 검토 기록으로 보존했으며 이번 테스트 추가까지 포함한 최신 patch라고 주장하지 않는다.

실제 Windows 임시 파일/링크 테스트는 기존 회귀의 일부로 실행됐다. 이번 작업에서 운영 경로를 열거·선택하거나 실제 운영 ACL/Allowlist를 조회·생성·변경하지 않았다. SID/보호 판정 대역의 성공은 운영 PASS가 아니다.

## 2. 보호 목표와 승인 경계

보호 대상은 비공개 설정·Allowlist·원본·검토/철회 사건·조정용 잠금과 C/E 사본이다. 일반 타 사용자 접근, 우발적 파일 교체, 권한 변경, 경합, 부분 저장·백업 불일치를 차단/탐지하는 것이 목표다.

검토자 SID가 관리자 승격도 가능한 개인 계정이라는 FROZEN의 신뢰 한계를 유지한다. ACL·해시만으로 같은 계정 또는 로컬 관리자의 악의적 양 사본 변조를 독립적으로 증명할 수 없다. 일반 사용자가 수정 가능한 Python 실행 코드 역시 별도의 신뢰 전제다. 독립 불변 저장이 필요해지면 별도 계정/서비스/서명 등은 추가 설계·승인 대상이며 이 후보안으로 도입하지 않는다.

이하 경로·권한 표는 **검토 후보**다. 실측·승인 전에는 managed_allowlist_source와 Store 설정을 연결하지 않고 현재 CLI의 BLOCKED/HOLD/NONE을 유지한다.

## 3. ProgramData·LocalAppData 및 E: 후보 비교

Windows는 ProgramData와 LocalAppData를 서로 다른 Known Folder로 정의한다. 실제 경로는 Known Folder API로 확인할 수 있지만 폴더 이름이나 위치 자체는 보호 ACL의 증명이 아니다. 아래 표의 비교는 이 구분과 본 프로젝트의 권한 분리 목표에서 도출한 설계 판단이다. [Known Folder 정의](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid), [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath).

| 후보 | 경로 표기 예시 — 현재 채택 아님 | 보호 가능성과 장점 | 운영 비용·한계 |
|---|---|---|---|
| A: ProgramData 중심 | `<ProgramData Known Folder>\TrendLeader\ProtectedReview\`에 Config/Store 분리 | 관리자 소유 설정과 일반 검토자의 쓰기 영역을 같은 관리 경계 아래 분리하기 편리. 사용자 프로필 변경 의존성이 작음 | 관리자 초기 설정·세부 ACE·부모 경로 검증 필요. ProgramData 기본 ACL을 신뢰할 수 없고 기존 경로 선점도 조사해야 함 |
| B: LocalAppData 중심 | `<운영자 LocalAppData Known Folder>\TrendLeader\ProtectedReview\` | Phase 0에서 확인한 상위 경로 후보를 이어가기 편리. 개인 계정의 로컬 사용과 위치가 잘 맞음 | 사용자 소유 프로필/부모 경로의 교체 권한과 계정·프로필 이동을 더 주의해야 함. 초기 관리자 설정과 E: 제한 ACL 비용은 여전히 필요함 |
| C: 혼합 | 관리자 Config는 ProgramData, 원본은 LocalAppData, 백업은 E: | 설정 변경 책임을 분리하면서 기존 개인 경로 후보를 유지 가능 | 보호 경계·루트 식별자가 늘고 LocalAppData 부모 경로 위험은 남음. 단순함을 위해 선택하기에는 검증 항목이 더 많음 |
| 공통 E: 백업 | `E:\TrendLeaderProtectedReview\` 등 승인된 새 전용 루트 | C:와 다른 디스크 사본 구성 후보 | 문자 E:만으로 장치 동일성·독립성 판단 불가. 실제 볼륨/파일 ID·DiskNumber·NTFS·쓰기/복원 가능성·ACL을 다시 확인해야 함 |

**우선 검토 방향은 A다. 자동 채택은 아니다.** 설정 관리자와 일반 CLI의 권한을 설명하기 쉽다는 판단 때문이다. A가 실제 일반 권한 생성·복사·잠금 요구를 충족하지 못하면 B/C와 비용을 다시 비교한다. 어느 경우에도 Windows 시스템 루트/ProgramData 전체/사용자 프로필 전체의 ACL을 프로젝트 편의로 일괄 변경하지 않는다.

FROZEN의 LocalAppData와 E: Phase 0 결과는 과거 후보 실측이다. ProgramData는 그 시험을 통과한 것으로 간주하지 않는다. 원본을 C:에 둘지, Known Folder가 다른 볼륨에 있는 경우 어떻게 처리할지도 최종 물리 위치와 함께 확정해야 한다. E: 누락·다른 장치 연결·동일 디스크로의 매핑이면 차단하며 C: 임시 백업으로 조용히 대체하지 않는다. 같은 PC의 별도 디스크는 오프사이트 백업이 아니다.

## 4. 비공개 설정·Allowlist 위치와 책임 후보

후보 A의 예시 구조는 다음과 같다. 부트스트랩 위치·이름과 새 settings 형식은 미확정이며 현재 코드에 추가하지 않는다.

```text
<ProgramData Known Folder>\TrendLeader\ProtectedReview\
  Config\settings.json       # 원본/백업 루트와 승인된 객체·볼륨 식별 정보 후보
  Config\reviewers.json      # 기존 내부 Allowlist 형식 후보
  Store\registrations\...
  Store\locks\...
  Store\.review-staging-...
<승인된 E: 전용 백업 루트>\registrations\...
```

Config 부모·파일은 관리자/SYSTEM 관리, 검토자는 읽기만 가능한 구성이 우선 후보이다. settings에는 경로뿐 아니라 승인된 볼륨/루트 File ID, 보호 정책 버전/소유자 범위 등의 연결을 검토한다. 개인 SID·개인 경로·실제 Allowlist/기록은 공개 Git에 넣지 않는다. JSON 자체의 해시는 접근통제의 대체물이 아니다.

| 운영 책임 | 후보 작업 | 아직 지정할 사항 |
|---|---|---|
| 초기 설정 관리자 | 명시적으로 승인된 새 전용 루트·설정·DACL 초기 구성 및 충돌/선점 조사 | 실제 담당자·관리 계정·승인 증거 보관 위치 |
| Allowlist 변경 승인자/적용자 | SID/활성 역할 확인, 추가·비활성·변경·폐기 사유 기록, 변경 전후 대조 | 동일 담당자 겸임 여부·긴급 비활성화 절차·최종 책임자 |
| 일반 검토자 | 일반 권한 CLI에서 개인 SID 인증·명시적 판단·허용된 파일 작업 | 허용 개인 SID, 필수 파일 동작별 권한 |
| 사고/복구 담당자 | 잔여 잠금·부분 등록·C/E 불일치를 HOLD로 격리하고 수동 조사 | 조사·복구 승인자 및 기록 보존·폐기 기준 |

위 책임 구분은 운영 절차 후보이며 EVIDENCE_REVIEWER 이외의 새 앱 역할을 확정하는 것이 아니다. 관리자 그룹 구성원이라는 이유만으로 검토 권한을 주지 않는다. 관리자도 실제 개인 SID의 Allowlist 검증을 거쳐야 한다.

## 5. 관리자 초기 설정과 일반 권한 CLI 분리

1. 향후 관리자가 승인된 경로만 초기 구성한다. 이미 존재하는 경로의 소유자·ACL·파일 ID가 예상과 다르면 덮어쓰기/소유권 회수로 자동 복구하지 않고 차단·조사한다.
2. 초기 구성에서 Config와 Store/백업을 분리하고, 상속 차단·명시적 규칙과 필요한 자식 상속을 설정한 뒤 실제 보안 설명자를 다시 읽는다. 임시 자료만으로 일반 권한 검토자의 필요한 쓰기/잠금·다른 사용자의 접근 거절을 확인한다.
3. 운영 CLI는 읽기 전용으로 설정과 Native ACL을 검증한다. 디렉터리 생성 fallback, ACL 수리, Allowlist 수정, 관리자 자동 상승을 하지 않는다.
4. ACL/설정 변경과 검토/등록 작업은 같은 보호된 조정 규칙 아래 처리하여 검사 후 변경을 방어한다. 변경 중·변경 탐지·시각/정체성 불명확이면 HOLD한다.

SHGetKnownFolderPath는 환경변수 문자열에만 의존하지 않는 경로 탐색 후보이다. 그러나 이 API가 돌려준 경로도 승인된 설정·부모 경로·객체 식별자와 대조해야 한다. `%USERNAME%`, Git 사용자명, 매 실행의 임의 SID/경로 인자를 인증·설정 대체물로 쓰지 않는다.

관리자 권한으로 실행한 검토 CLI를 강제 거절할지, 운영상 경고·중단 안내로 할지는 미확정이다. 기존 FROZEN의 일반 권한 기본 원칙을 새로운 인증 정책으로 조용히 확장하지 않는다.

## 6. Native ACL 검증 후보

### 6.1 주체·소유자·상속

검토자 R은 토큰에서 얻은 실제 개인 SID이며 여기에는 값을 적지 않는다. OS 관리 주체 후보는 SYSTEM(`S-1-5-18`)과 BUILTIN Administrators(`S-1-5-32-544`)다. 표시 이름/지역화 문자열 대신 SID를 비교한다. Windows의 well-known SID 정의는 [공식 자료](https://learn.microsoft.com/en-us/windows/win32/secauthz/well-known-sids)를 따른다.

- Config 및 보호 루트의 소유자 후보는 관리자/SYSTEM이다. 객체 종류별 허용 소유자 집합을 별도로 확정한다. OS 상위 경로의 정당한 소유자와 보호 루트의 소유자 정책을 무조건 같은 목록으로 검사하지 않는다.
- 보호 루트/Config 경계는 부모에서 넓은 권한을 물려받지 않도록 DACL 보호 비트를 확인하는 후보이다. 자식은 승인된 보호 부모의 제한 규칙 상속을 허용할 수 있지만 SID·마스크·전파/상속 플래그가 기대값과 같아야 한다. 상속이 꺼졌다는 사실만으로 PASS하지 않는다. [SECURITY_DESCRIPTOR_CONTROL](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-control).
- DACL의 존재 여부와 포인터를 확인한다. NULL DACL은 전체 접근 허용이므로 거절한다. 빈 DACL도 필요한 일반 CLI 작업이 불가능한 설정으로 차단한다. 읽지 못한 설명자, 미지원 ACE/조건부 규칙은 안전하다고 추측하지 않는다. [GetSecurityDescriptorDacl](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getsecuritydescriptordacl).
- 일반 Users/Everyone/Authenticated Users 등의 광범위 그룹에 보호 데이터 읽기·쓰기나 권한 변경을 허용하지 않는 후보이다. 단, C: 같은 OS 공통 조상에서 필요한 일반 탐색/읽기 권한까지 무조건 결함이라고 보거나 전역 ACL을 고치지는 않는다.

### 6.2 작업별 최소 권한 후보 — 적용할 ACE 확정표 아님

| 객체/단계 | 검토자 R 후보 | 관리자/SYSTEM 후보 | 주의점 |
|---|---|---|---|
| Config/Allowlist | 내용·속성·보안 설명자 읽기, 필요한 디렉터리 탐색만 | 초기 설정·변경·복구 관리 | R의 설정 내용 변경·삭제·WRITE_DAC·WRITE_OWNER를 허용하지 않는 방향 |
| 보호 루트 컨테이너 | 필요한 탐색/조회, 승인된 자식 영역 작업 | 경계 관리 | 루트/형제 경로의 광범위 삭제·소유권 변경 권한으로 단순화하지 않음 |
| 임시 스테이징 | 승인된 컨테이너 안 신규 생성·읽기·쓰기·검증 | 장애 조사 | 기존 파일 덮어쓰기 금지, 신규 객체의 초기 DACL/소유자를 즉시 확인 |
| 등록 원본 | 조회·무결성 확인, 확정에 필요한 제한 동작만 | 수동 사고 처리 | 생성/rename/완료 표식 작성과 완료 후 권한을 단계별로 실측해야 함 |
| 철회 사건 영역 | 향후 별도 신규 사건 추가에 필요한 권한 | 사고 처리 | NTFS 파일 append 권한이 사건 파일의 추가 전용·연결 무결성을 자동 보장하지 않음 |
| E: 백업 | 지정한 등록 사본의 생성·읽기·검증 | 복원/장치 관리 | 원본과 별도로 ACL·볼륨·필수 동작을 검증 |

READ_CONTROL, WRITE_DAC, WRITE_OWNER, DELETE와 파일/디렉터리별 생성·쓰기 권한은 별개다. 부모 FILE_DELETE_CHILD는 자식 교체 위험에 영향을 주므로 상위 경로도 검사한다. 새 객체와 이동된 객체의 보안 설명자 취급을 동일하다고 가정하지 않는다. [표준 권한](https://learn.microsoft.com/en-us/windows/win32/secauthz/standard-access-rights), [파일별 권한](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants), [파일 보안 설명자](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights).

**독립 불변성의 한계:** 일반 CLI가 만든 파일의 소유자가 R이면 소유자의 DACL 관리 능력까지 고려해야 한다. ACE에서 WRITE_DAC만 빼거나 파일을 읽기 전용으로 표시했다고 R 본인의 재권한 부여를 독립적으로 막았다고 주장하지 않는다. 이 원칙은 Windows의 소유자 중심 DACL 모델에서 나온다. [Microsoft ACL 설명](https://learn.microsoft.com/en-us/archive/msdn-magazine/2004/november/manage-access-to-windows-objects-with-acls-and-the-net-framework).

완료된 각 원본을 관리자로 소유권 이전·봉인하는 대안은 권한 분리를 강화할 수 있지만 매 등록 시 특권 작업/도구 비용이 생긴다. 일반 CLI만으로 완결하려는 현재 방향과의 비용을 다시 승인받아야 한다. 이 후보안은 관리자 helper/서비스/새 역할을 자동 도입하지 않는다. 신뢰된 운영자의 우발적 변경 방어와 SHA/C/E 대조를 유지하면서 같은 계정·관리자 악의적 변조의 한계를 명시하는 방향이 현재 FROZEN과 맞는다.

### 6.3 API·오류·토큰 검사 후보

핸들 기반 GetSecurityInfo로 소유자/DACL을 읽고 GetSecurityDescriptorControl/GetAclInformation/GetAce 등의 구조·플래그를 검증하는 후보이다. 반환 코드·포인터 수명·할당 해제를 명시하고 실패는 HOLD로 처리한다. [GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo).

필요 작업의 유효 권한은 실제 토큰의 그룹·Deny-only·권한과 generic mapping을 반영해 검증해야 한다. AccessCheck를 쓰면 문서가 요구하는 impersonation token과 반환된 AccessStatus/GrantedAccess를 올바르게 취급한다. 단순히 이름이 같은 SID ACE 하나를 찾거나 API 호출 성공만 보고 접근 허용으로 판단하지 않는다. [AccessCheck](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck).

SACL 감사 설정을 이번 최소 DACL 판정과 혼합해 불필요한 관리자 권한을 요구하지 않는다. 상세 감사 정책은 별도 운영 결정이다. 프로그래밍 오류는 개발 계층에서 드러내되 CLI에는 현재처럼 범주·예외 종류만 표시하고 실제 SID·개인 경로·비밀은 출력하지 않는다.

## 7. 경로 교체·볼륨·핸들 검증 후보

1. 관리자가 승인한 루트의 최종 경로와 볼륨/파일 ID를 사전 보호 설정에 결속하는 후보이다. 같은 문자열 경로를 삭제·재생성한 새 디렉터리를 자동 신뢰하지 않는다.
2. 루트뿐 아니라 관련 조상도 재분석 태그·소유자·교체 권한을 확인한다. FILE_FLAG_OPEN_REPARSE_POINT는 그것만으로 모든 조상의 안전을 보장한다고 해석하지 않는다. 필요한 디렉터리를 열고 조상 핸들의 삭제 공유를 제한해 유지하는 방안을 실제 Windows에서 검증한다.
3. GetFinalPathNameByHandle와 볼륨/파일 ID를 함께 비교한다. 정규화 문자열 일치만으로 동일 객체라고 단정하지 않는다. C/E 장치·DiskNumber 검사도 파일 ID 검사의 대체물이 아니다. [최종 경로 조회](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew), [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info).
4. 실제 I/O에서 필요한 권한·공유 모드·OPEN_EXISTING/CREATE_NEW를 고정한다. FILE_SHARE_DELETE를 허용하지 않는 핸들의 교체 방어 가능성과 경합 결과를 시험한다. 디렉터리에는 필요한 BACKUP_SEMANTICS를 고려하고 reparse/알 수 없는 객체는 차단한다. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
5. 경로 기반 사전 검사 후 일반 open을 하는 현재 합성 구현은 운영용 원자적 경로 보호의 증명이 아니다. Native 핸들 유지·ACL 재대조·잠금의 조합이 실제 조상 교체/rename/권한 변경을 차단하지 못하면 운영 연결을 보류한다. UNC/네트워크·장치 경로·Git/입력 중첩·별칭 우회의 허용 범위도 명시적으로 확정한다.

## 8. 단일 호스트 배타 구간 후보

같은 local_evidence_id에 대해 원본 C: 쪽의 승인된 조정 경계 하나를 사용하고, C/E 복사·완료 판정·철회/이력 대조가 같은 규칙에 참여해야 한다. 작업 디렉터리나 사용자 프로필마다 다른 잠금이 생기면 직렬화가 아니다. 등록 ID를 새로 발급해 경쟁을 숨기지 않는다.

| 방법 | 장점 | 비용·실패 의미 |
|---|---|---|
| 보호 루트의 잠금 파일 배타 생성·핸들 유지 | 일반 파일/루트 신뢰 경계를 재사용, 중단 흔적을 남기기 쉬움 | 소유자/ACL·파일 ID·링크·공유 모드·정상 해제 절차 필요. 남은 파일/부분 작업은 자동 삭제하지 않고 HOLD 조사 |
| 기존 조정 파일 + LockFileEx | OS 배타 잠금/즉시 실패 기능 활용 | byte-range 잠금과 파일 정체성·작업 잔여 상태를 별도로 검증해야 함 |
| 보호된 named mutex | 프로세스 간 조정에 적합 | 이름 선점·기존 객체의 DACL·세션/Global 범위·abandoned 처리 비용. 이름만으로 신뢰하면 안 됨 |

우선 검토는 보호된 잠금 파일의 배타 생성이다. 이름은 검증된 관측 ID에서만 만들고 경로를 입력받지 않는다. 정상 해제와 실패 잔재를 구별하는 절차를 확정하기 전에는 자동 잠금 회수·lease 만료·재시도를 도입하지 않는다. 현재 배타 스테이징 디렉터리만으로 운영 조회·철회까지 조정됐다고 판단하지 않는다.

배타 구간은 최소한 최신 이력/중복 확인 → 입력·권한 재검증 → C/E 필수 바이트 보존·복원 기준 확인 → 완료/철회 대조와 반환 전 재검증을 포괄하는 방향이다. 이는 후속 통합 후보이며 이번에 C/E 완료 흐름을 구현하는 것이 아니다. 프로세스가 죽어 OS 핸들이 풀려도 남은 단계 자료는 HOLD다.

LockFileEx의 배타/즉시 실패 동작과 mutex 기존 객체의 보안 설명자 취급은 각각 문서 계약을 따라 검증한다. [LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex), [CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw).

## 9. 실제 운영 검증의 최소 실패 테스트 후보 — 현재 미실행

모두 실제 승인 ZIP/SID 공개를 피한 별도 합성 시험으로 수행한다. 필요한 관리 작업/계정 준비는 별도 사용자 승인 후 진행한다.

| ID | 실패/반례 | 기대 결과 |
|---|---|---|
| OP-01 | 설정/Allowlist 누락·손상·검증 불가, 환경변수/임의 인자로 대체 시도 | BLOCKED/1, 프롬프트/등록 0, 자동 경로·ACL 생성 없음 |
| OP-02 | 미등록/비활성 개인 SID, 관리자 그룹만으로 권한 주장 | 검토/등록 차단, 실제 SID 미노출 |
| OP-03 | Config를 일반 검토자 또는 다른 일반 사용자가 변경/삭제/소유권 변경 시도 | OS 거절 및 Native 재검증으로 부적격 탐지 |
| OP-04 | 넓은 그룹 ACE·상속·NULL DACL·잘못된 소유자·미지원 ACE 주입 | 작업 전 BLOCKED/HOLD, 자동 ACL 수리 없음 |
| OP-05 | 일반 토큰에서 필요한 생성/rename/잠금·설명자 읽기 권한이 하나라도 없음 | 성공 0, 어느 단계가 부족한지 비민감 범주로 식별 |
| OP-06 | 보호 루트/조상 교체, 동일 경로 재생성, junction/symlink/하드링크·다른 볼륨 우회 | Native 핸들·객체/볼륨 ID 또는 공유 제한으로 차단, 잘못된 대상 쓰기 없음 |
| OP-07 | 두 프로세스가 같은 관측 ID를 동시 처리, 다른 cwd/세션·사용자로 잠금 우회 | 한 배타 구간만 진행, 중복 유효 수락 0 |
| OP-08 | 프로세스 중단 후 잠금/스테이징/부분 C/E 자료 잔여 | 자동 새 ID/삭제/승격 없이 HOLD, 수동 조사 |
| OP-09 | 검토 후 ZIP/JSON/index 교체·SID/Allowlist/ACL 변경·시계 이상 | 저장 전후/반환 전 차단, 원본 자동 수정 없음 |
| OP-10 | E: 누락·다른 장치·동일 DiskNumber·읽기 전용·NTFS 아님·부분 백업 | 완료 표식/등록 성공 0, 다른 경로로 자동 우회하지 않음 |
| OP-11 | C/E 파일/다이제스트/ACL/철회 이력 불일치 또는 복원 검증 실패 | 참조 사용 불가 HOLD, 한 사본으로 자동 원본 교체 없음 |
| OP-12 | 일반 토큰/승격 토큰·다른 일반 계정의 예상 권한 대조, 모든 공개 CLI 오류 출력 | 필요한 정상 동작과 불필요한 권한 거절을 모두 증명, 개인 경로/SID/비밀 출력 0 |

단순 ACE 모양 검사, 같은 계정 Mock, 읽기 전용 파일 속성만으로 OP-03/04/06을 통과시킬 수 없다. 실제 Windows 접근 거절과 Native API 조회 결과를 교차 확인한다. 다른 일반 사용자·계정 환경이 없으면 미실행으로 남기며 새 계정을 자동 생성하지 않는다.

## 10. 미확정 사항과 다음 승인 단위

- A/B/C 선택, 원본 및 백업의 최종 절대 경로·볼륨/루트 ID와 운영 설정 부트스트랩 위치.
- 초기 설정 담당자, Allowlist 승인/적용/비활성화·폐기 책임자, 장애 조사/복원 승인자.
- 객체 종류·단계별 소유자/ACE/SID/상속·공유 모드와 실제 일반 토큰의 필요 권한 표.
- 일반 CLI가 만든 파일의 소유자 권한 한계를 수용하는 증거 수준, 추가 봉인 대안의 필요 여부.
- Native 핸들 기반 경로 보호와 잠금 파일/LockFileEx/mutex 중 선택 및 중단 흔적·해제 절차.
- C/E 장치 식별·복원 가능성·재시작·시간 이상 시험과 비공개 증거 보관 방식.

다음 단계는 후보 선택과 검증 기준 승인이다. 이후 별도 합성 Windows 시험 계획을 검토하고, 승인된 새 전용 위치에 한해 초기 구성/실패 시험을 진행한다. 이 문서 작성만으로 생성·권한 변경·운영 CLI 활성화·FROZEN 변경을 승인하지 않는다.
