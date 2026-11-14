# B-2 Evidence Writer 구현·검증 기록

2026-11-14 KST. 독립 Writer의 Windows 오프라인 검증 기록이다. B-2 전체 완료, Linux 내구성 실증, Migration 또는 운영 배포 승인이 아니다.

## 기준과 변경 범위

- Worktree: `trend-leader.worktrees/feat-phase-3-b-2-preflight-integration`
- Branch: `feat/phase-3-b-2-preflight-integration`
- 정확한 HEAD: `fa93d1d04c7246debf1ba547cd18343a0f467a45` (변경 전후 동일)
- Git 직접 원격 접속 실패. GitHub Connector로 원격 `dev` HEAD `cd079ed3886234e6f9df21613f31613f13c8bdd2` 및 같은 경로의 승인된 B-2 FROZEN 문서를 읽었다. 로컬 `origin/dev` SHA와 일치한다.
- `origin/dev...HEAD`는 dev 쪽 2개 / 작업 브랜치 쪽 1개 커밋이다. 작업 브랜치는 Observation 구현을 추가했지만 FROZEN 문서 커밋은 포함하지 않는다. 체크아웃 문서는 여전히 후보안이며 덮어쓰거나 병합하지 않았다.
- 기준: M-A1 v1.0 및 원격 B-2 v1.0 §6 P0-A/P0-C. 승인 문서의 [dev 커밋 고정본](https://github.com/Trend-Leader-capstoneProject/feature/blob/cd079ed3886234e6f9df21613f31613f13c8bdd2/docs/designs-infra/phase-3-b-2/Trend_Leader_B2_Preflight_Design_v1.0_20261114.md).
- 시작 시 미커밋 변경 없음. 신규 파일은 Writer, 단위 테스트, 이 검증 기록의 3개뿐이다.
- DB Observation/Schema 분류/Guard/Runtime API/Responses API/Settings/Alembic/Compose/AWS 및 다른 Worktree는 수정하지 않았다. 커밋·Push·PR·병합 없음.

## Writer 경계와 저장 순서

`backend/scripts/migration_evidence.py`는 사전 검증된 비밀정보 없는 JSON-compatible dict만 받는다. DB 관찰 결과의 조립, inspection_status 결정, 이미지 검증, 실행 승인 및 CLI 종료 코드는 담당하지 않는다.

- `new_evidence_id()`: 표준 라이브러리 UUID4. `write_evidence(root, data)`에는 보고서와 일치하는 canonical UUID를 전달한다. 파일 경로 입력으로 임의 ID 문자열을 허용하지 않는다.
- `evidence_root_available(root)`: 사전 생성된 절대 경로의 비변경 검사. 루트·상위 경로의 symlink/Windows reparse point, 루트 부재·비디렉터리·쓰기 불가를 거부한다. POSIX에서는 실행 UID 소유이며 group/other 접근 비트가 없어야 한다. 이것만으로 디스크 여유·Windows ACL·영속 마운트가 증명되지는 않는다.
- JSON v1 필수 키/중첩 target 키, 필드 타입, UTC 시각, 상태 enum, 고정 Reason Code를 검사한다. 관찰 불가 `null`은 보존하며 Reason Code가 필요하다. Revision을 재분류하거나 빈 후보를 승인하지 않는다.
- `checks`는 현재 Writer에서 dict/list 안의 boolean/null/동결 Reason Code만 수용한다. 자유 형식 진단 문자열은 받지 않는다. 어떤 검사를 수행하는지는 결정하지 않는다. 향후 조립 계층은 이 입력 형태와 교차 검증해야 하며, 이를 새로운 전체 B-3 checks 계약이 동결된 것으로 해석하지 않는다.
- 임의 추가 키, 비밀번호 필드, URL·JWT·예외/덤프 표식을 거부한다. 이미지 검증을 수행하지 않는 현재 범위에서는 `NOT_VERIFIED`만 수용한다. 메타데이터로 위장한 모든 임의 비밀을 식별할 수 있다는 보장은 없으며 입력을 비밀정보 없이 조립할 책임은 호출자에게 있다. 비밀 원문을 읽어 검사하거나 환경을 덤프하지 않는다.
- I/O 전에 JSON 스냅샷을 만들고 재검증하여 호출자 dict 변경이 저장값에 유입되지 않게 한다.

저장 순서는 다음과 같다.

```text
입력/루트 검증 및 입력 스냅샷
→ <root>/<evidence_id> mkdir(exist_ok=False, mode=0700)
→ 지원 OS에서 root fsync (예약 디렉터리 엔트리)
→ report.tmp O_CREAT|O_EXCL, mode=0600
→ UTF-8 JSON 작성 → flush → 파일 fsync → close
→ os.link(report.tmp, report.json): 대상이 이미 있으면 실패
→ 지원 OS에서 실행 디렉터리 fsync
→ 정상 게시된 임시 링크 unlink
→ 지원 OS에서 실행 디렉터리 재 fsync
→ 최종 파일 bytes 확인 → 완료 결과 반환
```

같은 디렉터리 안에서 하드 링크로 완성된 파일을 게시한다. 최종 경로가 선점되어도 기존 파일을 대체하지 않는다. 하드 링크를 지원하지 않는 파일시스템이나 동기화 오류에서 copy/replace 등으로 우회하지 않는다. 실패한 실행의 파일·디렉터리는 자동 삭제하거나 다시 사용하지 않는다. 정상 게시 후 임시 링크 제거와 실패 기록의 삭제는 구별한다.

반환 `EvidenceWriteResult.success`는 저장 호출 완료만 의미한다. 실패 시 `report_path=None`, 고정 `EVIDENCE_WRITE_FAILED`만 반환하며 예외·경로·입력 원문은 출력하지 않는다. 저장 실패가 기존 관찰 상태를 정상 저장 상태로 승격하지 않는다. Guard가 이를 exit 4로 매핑하는 작업은 이번 범위 밖이다.

## Red → Green → Refactor

1. 첫 정상 기록 테스트를 작성하고 신규 모듈 ImportError로 Red를 확인했다. 저장 실패·중복·중단·민감정보 테스트도 구현 전에 추가하고 같은 수집 실패를 확인했다. 실행 환경 설정 실패(No module named pytest)는 제품 Red로 집계하지 않았다.
2. 최소 구현 후 **36 passed, 1 skipped**. 정상 JSON, 중복/동시 동일 ID, 루트 거부, write/flush/파일 fsync/게시 실패, 최종 경로 선점, 강제 중단, 민감정보 및 CLI 출력 실패를 검증했다.
3. 추가 실패 테스트에서 검증 후 입력 dict 변경이 미검증 URL을 저장하는 결함을 재현했다: **1 failed, 40 passed, 1 skipped**. I/O 전 스냅샷 및 재검증으로 수정 후 **41 passed, 1 skipped**.
4. 게시 후 디렉터리 sync 실패, 임시 파일 선점, 쓰기 불가, UTF-8 비ASCII, POSIX sync 호출/descriptor close 검증을 보강했다. JSON 검증/경로 검사/저장/결과 책임을 분리하고 신규 두 Python 파일만 포맷했다.
5. 최종: Writer **46 passed, 1 skipped** + 관련 기존 회귀 **90 passed** = **136 passed, 1 skipped**. Skip은 Windows에서 POSIX 소유권/0700·0600 실측 시험을 실행할 수 없기 때문이다. POSIX sync syscall mock 테스트는 실제 Linux 실측으로 집계하지 않았다.

## 중단 사례 A/B

| 항목 | A: 임시 JSON 작성 중 프로세스 중단 | B: Writer 완료 반환 뒤 상위 CLI 출력 실패 |
|---|---|---|
| 예시 | `report.tmp`에 `{"schema_version":`까지 쓰고 `os._exit(73)` | 저장 결과 반환 후 출력 함수에서 `BrokenPipeError` |
| 남는 파일 | 예약 디렉터리와 부분 `report.tmp`; `report.json` 없음 | 완성된 `report.json`; 정상 경로의 임시 파일 없음 |
| Evidence 인정 | 불완전 기록, 정상 Evidence 아님 | 저장 완료 Evidence 유지. CLI 실행 성공과는 별도 상태이며 Migration 승인도 아님 |
| 이전 ID 재사용 | 금지. 동일 ID 요청은 디렉터리 충돌로 거부 | 금지. 출력 실패를 이유로 보고서를 삭제·덮어쓰지 않음 |
| 자동 복구/재실행 | Writer는 삭제·복구·재시도하지 않음. 조사 후 필요하면 별도의 새 ID로 새 관찰 실행을 조정 | 출력 전달 실패 조사. 기존 증거 확인 없이 자동 관찰/적용 재실행하지 않음. 별도 새 실행은 새 ID 사용 |
| 시험 | `test_process_exit_leaves_incomplete_record[during_write]`: 실제 자식 프로세스 강제 종료 및 재사용 거부 | `test_cli_output_failure_does_not_undo_persistence`: 출력 실패 뒤 bytes 불변·재사용 거부 |

추가로 최종 게시 직전 중단도 실제 자식 프로세스로 검증했다. 이때 JSON이 완성되어 파일 fsync까지 됐더라도 임시 파일만 있으므로 정상 완료로 인정하지 않는다.

게시 후 sync/정리 오류에서는 `report.json`과 `report.tmp`가 함께 남거나 `report.json`만 남을 수도 있다. Writer는 성공을 반환하지 않는다. **파일 이름 존재나 내부 OBSERVED 값만으로 저장 호출 완료를 추론할 수 없다.** 프로세스 중단으로 완료 반환을 받지 못한 경우도 결과 불명으로 조사해야 한다. 향후 B-3는 이러한 기록을 자동 승인 근거로 채택하면 안 된다. 별도 완료 마커/서명/자동 복구 프로토콜은 이번에 추가하지 않았다.

## 실행 명령과 결과

기본 `python`은 기존의 깨진 venv launcher를 가리킨다. 기존 venv를 수정하지 않고 `C:/Python314/python.exe`와 이미 설치된 site-packages를 사용했다. 운영 Dockerfile은 Python 3.12이며 이번 실행은 Windows Python 3.14.0이다.

`backend/`에서:

```powershell
$env:PYTHONPATH = (Resolve-Path ../../../trend-leader/.venv/Lib/site-packages).Path
& C:/Python314/python.exe -m pytest tests/core/test_migration_evidence.py tests/core/test_migration_observation.py tests/core/test_migration_preflight.py tests/core/test_migration_guard.py tests/core/test_migration_db_config.py tests/core/test_migration_fixture_env.py -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/b2-evidence-final
& C:/Python314/python.exe -m ruff check .
```

- pytest: **136 passed, 1 skipped**, exit 0.
- Backend 전체 Ruff: **All checks passed**, exit 0.
- diff/staged 및 신규 파일 공백 검사: PASS. Windows 긴 파일명 문제로 `git -c core.longpaths=true`를 명령별 적용했으며 Git 설정은 변경하지 않았다.
- Backend 전체 pytest, 실제 MariaDB, Guard 통합 실행, 운영 Compose/AWS, B-3/L-2, 실제 전원 장애·재부팅 시험: **NOT RUN**. 이번 범위 밖이며 DB 자동 Migration Fixture를 호출하지 않았다.

## Windows/Linux 차이와 Guard 연결 전 조건

- Windows 로컬 볼륨에서 실제 배타 디렉터리 생성, 하드 링크 게시·동시 동일 ID, 파일 fsync, 프로세스 중단을 확인했다. Windows에서는 portable 디렉터리 fsync를 수행하지 않고 `directory_synced=False`를 명시한다. 이를 Linux와 동일한 전원 장애 내구성으로 해석하지 않는다. Windows ACL 보호는 운영자가 별도로 검증해야 한다.
- POSIX에서는 root/실행 디렉터리 fsync 실패를 무시하지 않으며 파일 0600/디렉터리 0700 생성 모드를 사용한다. Linux 실제 권한·UID/GID·umask·마운트·하드 링크 지원·sync 및 전원 장애 내구성은 미검증이다. Docker API와 WSL 목록 조회 모두 현재 환경에서 접근이 거부되어 실행하지 못했다.
- 보호된 루트와 상위 경로의 권한은 운영 전제다. symlink/reparse 검사만으로 관리자나 상위 경로 쓰기 권한자의 동시 경로 바꿔치기를 방어한다고 주장하지 않는다. 이 위협과 실제 마운트 구성은 운영 Gate에서 확인해야 한다.
- 파일 fsync와 디렉터리 엔트리 내구성은 별개다: [Python os 문서](https://docs.python.org/3/library/os.html), [Linux fsync 설명](https://man7.org/linux/man-pages/man2/fsync.2.html).
- Guard 연결 전: 승인 문서 기준 정합성 유지, `MIGRATION_PREFLIGHT_EVIDENCE_DIR`의 실제 보호 영속 루트 결정, 사전 경로 검사와 P0-B 환경 감사, Observation 결과→JSON/checks 조립의 비밀정보 제거·상태 교차 검증, 저장 성공 전 완료 출력 금지 및 저장 실패 exit 4 우선 매핑이 필요하다. 완료 불명 기록 처리와 CLI 출력 실패 정책도 통합 테스트해야 한다.
- B-2 실제 검증 완료에는 별도 승인된 격리 MariaDB READ ONLY 시험과 Linux 운영 후보 파일시스템 시험이 필요하다. B-3 Manifest 승인·L-2 적용 및 운영 공개는 계속 별도 Gate다.
