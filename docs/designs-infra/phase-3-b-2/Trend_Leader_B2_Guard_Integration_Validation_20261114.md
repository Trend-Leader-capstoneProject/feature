# B-2 Guard Integration 오프라인 구현·검증 기록

2026-11-14 KST. **Guard Integration 오프라인 구현·회귀 검증 완료**.
실제 MariaDB/Linux 운영 검증, B-3 승인, L-2 Apply 및 배포 승인은 아니다.

## 기준과 Git 상태

- Worktree: `trend-leader.worktrees/feat-phase-3-b-2-preflight-integration`
- Branch: `feat/phase-3-b-2-preflight-integration`
- 시작 및 완료 HEAD: `56e15d81399dd3f24b06308848a0c0f66cf4f04b`.
- `git ls-remote origin refs/heads/dev refs/heads/feat/phase-3-b-2-preflight-integration`으로 원격 재확인:
  - 작업 브랜치: `56e15d81399dd3f24b06308848a0c0f66cf4f04b`
  - dev: `cd079ed3886234e6f9df21613f31613f13c8bdd2`
- 로컬 `origin/dev`도 위 SHA와 일치. `origin/dev...HEAD`는 dev 2 / 작업 브랜치 2 커밋.
- 시작 시 미커밋 변경 없음. Worktree 목록 확인 후 이 Worktree만 변경했다.
- 체크아웃 B-2 문서는 이전 후보안이었다. 해당 파일만 `origin/dev`의 FROZEN 버전으로 정합화했다. 추가 차이는 후행 공백 한 줄 제거와 파일 끝 개행뿐이다. 정책 내용은 변경하지 않았다.
- M-A1 v1.0, B-2 POLICY FROZEN v1.0 P0-A~D, 기존 Observation/Writer 검증 기록 및 개발 가이드라인을 확인했다.
- 브랜치 전환·reset·clean·Git 설정 변경·커밋·Push·PR·병합 없음. staged 변경 없음.

## 변경 파일과 Diff 의미

| 파일 | 변경 |
|---|---|
| `backend/scripts/migration_environment.py` | 신규 순수 P0-B 키 감사. 금지 변수는 빈 값도 차단, 미정의 MIGRATION_DB 입력 거부, 필수 입력 검사, 대소문자 정규화·중복 별칭 거부 |
| `backend/scripts/migration_report.py` | 신규 독립 조립 계층. Observation/실제 저장소 계보/Reason/상태 교차 검사, JSON v1 조립 |
| `backend/scripts/migration_integration.py` | 신규 설정·Secret → 루트 사전 검사 → Observation → 조립 → Writer 조정, 저장 실패 exit 4 우선 |
| `backend/scripts/migration_guard.py` | 정확히 preflight만 지연 import로 연결. 기존 거부 계약 유지. 고정 코드 출력, 출력 실패 시 exit 4 |
| `backend/tests/core/test_migration_environment.py` | 신규 환경 감사 테스트 |
| `backend/tests/core/test_migration_report.py` | 신규 상태·Reason·null·모순 테스트 |
| `backend/tests/core/test_migration_integration.py` | 신규 오프라인 조정/실제 Observation+Fake DBAPI+실제 Writer 통합 테스트 |
| `backend/tests/core/test_migration_guard.py` | 비활성 preflight 기대값을 정상 경로로 교체, 기존 거부 회귀 및 입력·I/O 경계 보강 |
| `docs/designs-infra/phase-3-b-2/Trend_Leader_B2_Preflight_Design_v1.0_20261114.md` | dev FROZEN 문서 정합화 |
| 이 문서 | 실행 근거·잔여 Gate 기록 |

기존 DB Observation, Evidence Writer, 순수 Schema 분류, Migration Settings는 수정하지 않았다.
Alembic Revision/Runtime Settings/API/Responses API/P4/Compose/AWS 및 다른 Worktree 변경 없음.

## Phase별 Red → Green → Refactor

| Phase | 실제 Red | Green 및 최종 검증 |
|---|---|---|
| 1 환경 감사 | 첫 `DATABASE_URL=""` 테스트 수집 시 신규 migration_environment ImportError, 1 error | 39 passed. 최종도 39 passed |
| 2 결과 조립 | 첫 정상 JSON 테스트 수집 시 신규 migration_report ImportError, 1 error | 최초 23 passed. Phase 1 포함 62 passed. 최종 26 passed |
| 3 Writer 연결 | 첫 저장 완료 테스트 수집 시 신규 migration_integration ImportError, 1 error | 최초 44 passed. Fake DBAPI 전체 흐름·Secret 실패 등 보강 후 최종 63 passed |
| 4 CLI 연결 | 기존 Guard가 preflight를 MODE_NOT_ENABLED/exit 2로 거부: 1 failed, 16 passed | 연결 후 Guard+조정 72 passed. 최종 Guard 28 passed |

최종 검토에서 접속 실패+Schema 관찰 등 불가능한 단계 Reason 조합을 추가해 **3 failed, 23 passed**를 재현했다. 정리 실패가 기존 결과에 OBSERVATION_FAILED를 추가한 조합만 허용하도록 보강했다. 최종 조립 26 passed에 포함된다.

Refactor: 감사/조립/조정/CLI 책임을 분리하고 기존 분류와 Writer를 재사용했다. 수정·신규 Python 파일에 한정해 Ruff format을 적용했다. 최초 lint의 긴 줄 30건은 포맷 후 해소했다.

## 동결 계약과의 일치

- 잘못된 CLI는 환경 검사와 preflight import 이전에 exit 2. 무인자/deny=DENY_DEFAULT, apply=MODE_NOT_ENABLED, 나머지=INVALID_MODE.
- 환경 충돌은 Secret 파일 읽기·Evidence 루트 검사·Observation·Writer 호출 전에 exit 4/ENV_CONFLICT. 일반 OS 변수는 허용한다. 키·환경값·예외를 출력하지 않는다.
- 유효한 MigrationDbSettings와 Secret을 확인하고, 기존 evidence_root_available로 사전 생성된 보호 루트를 검사한 다음 DB 관찰을 수행한다. 루트를 임의 생성하지 않는다.
- 정상 Revision과 제한적 빈 후보는 OBSERVED/exit 0, Schema 불확실·관찰된 대상 불일치는 INDETERMINATE/exit 3. 둘 다 Writer 성공 반환 후에만 완료한다. 빈 후보는 빈 DB 확증·승인이 아니다.
- 설정/접속/READ ONLY/조회/정리 실패는 ERROR/exit 4. 보고서를 안전하게 조립할 수 있는 관찰 오류는 오류 Evidence를 저장한다. 환경·설정·루트 오류로 안전한 보고 경로를 확보하지 못한 경우는 파일 없이 고정 코드로 종료한다.
- 상태 모순/예기치 않은 관찰 예외는 OBSERVATION_FAILED로 대체하여 성공 Evidence를 남기지 않는다. 저장 실패/중복 ID/동기화 오류는 기존 관찰 상태와 무관하게 EVIDENCE_WRITE_FAILED/exit 4.
- observed_target·schema_state의 미관찰 값은 null. current_revisions는 기존 Writer의 list 계약을 유지하며 미완료 시 []다. null Schema/가시성/Reason과 함께 표현하며 빈 DB 관찰로 해석하지 않는다. 실제 관찰된 NULL Revision은 [null]로 보존한다.
- checks에는 실제 반환된 version_table_visible/business_objects_visible만 기록하며 미관찰은 null. READ ONLY·cleanup·이미지 검증을 임의로 성공 표시하지 않는다.
- 모든 보고서는 image_identity_verification_status=NOT_VERIFIED. B-3 Manifest, 승인 Host 비교, GET_LOCK 및 Apply는 추가하지 않았다.
- Windows directory_synced=False는 기존 Writer 의미대로 취급하며 새 운영 승인 정책을 만들지 않았다. 실제 sync 예외는 Writer 실패로 전달된다. 이 로컬 성공을 Linux 운영 내구성 PASS로 해석하지 않는다.
- 완료 출력은 저장 후에만 수행한다. 출력 실패는 exit 4이며 이미 저장한 Evidence를 삭제·재사용하거나 관찰을 재시도하지 않는다.
- 미완성/중복/게시 후 sync 실패 기록은 Writer 성공 반환이 없으므로 성공 Evidence로 인정하지 않는다. report.json 이름이나 내부 상태만으로 완료를 추론하지 않는다.

## 실제 명령과 결과

Windows Python 3.14.0과 기존 설치 패키지를 사용했다. 기본 python launcher가 다른 Worktree의 기존 venv를 가리키므로 이를 변경하지 않고 C:/Python314/python.exe를 명시했다. 운영 Python 3.12 컨테이너 검증은 아니다.

backend/에서 최종 실행:

```powershell
$env:PYTHONPATH = (Resolve-Path ../../../trend-leader/.venv/Lib/site-packages).Path
& C:/Python314/python.exe -m pytest tests/core/test_migration_environment.py tests/core/test_migration_report.py tests/core/test_migration_integration.py tests/core/test_migration_guard.py tests/core/test_migration_observation.py tests/core/test_migration_evidence.py tests/core/test_migration_preflight.py tests/core/test_migration_db_config.py tests/core/test_migration_fixture_env.py -q -rs --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/b2-guard-final
& C:/Python314/python.exe -m ruff check .
```

- 최종 pytest: **275 passed / 0 failed / 1 skipped**, exit 0.
- SKIP: test_migration_evidence.py의 POSIX 소유권/모드 실측. Windows ACL 검증으로 대체 수행한 것은 아니다.
- Backend 전체 Ruff: **All checks passed**, exit 0.
- git diff --check, git diff --cached --check: 긴 경로 지원을 명령별 적용해 PASS. 신규 파일도 별도 no-index diff 공백 검사 대상으로 포함했다.
- 환경 충돌 시 관찰 0회, 잘못된 CLI 환경/파일/네트워크 접근 0회, 정상/불확실/오류 저장, 저장 실패 우선, 중복 보존, 민감정보 비노출 및 기존 Observation/Writer 회귀를 포함한다.
- 전체 Backend pytest는 실행하지 않았다. tests/conftest.py의 test_engine → migrated_test_database가 실제 Alembic upgrade를 수행할 수 있음을 사전 확인했다. 선택한 테스트는 해당 DB Fixture를 요청하지 않는다. fixture_env 테스트의 subprocess는 Mock으로 대체된다.

## 미검증과 후속 Gate

- 실제 MariaDB 12.3.x의 READ ONLY 쓰기 부정 시험, 드라이버 초기화·연결 유지·권한별 메타데이터·단절/정리·Revision 상태별 검증: **NOT RUN**, 별도 승인 필요.
- Linux 운영 후보 마운트의 UID/GID/0700·0600/ACL/하드 링크/fsync/전원 장애·재부팅 내구성 및 운영 Python 3.12 컨테이너: **NOT RUN**.
- 운영 루트·상위 경로 보호, Compose 최소 환경 주입·Secret 분리: 운영 Gate 유지. 알려진 금지 키 감사만으로 임의의 모든 Secret 혼입 차단을 보장하지 않는다.
- 실제 AWS/운영 데이터 연결·변경, B-3 승인, L-2 Apply 및 운영 배포: **NOT RUN / NOT APPROVED**.
- 기존 Observation의 SQLAlchemy private Pool close hook 버전 의존성과 Writer의 경로 바꿔치기/관리자 위변조 방어 한계는 기존 검증 기록대로 유지한다.

권장 커밋 메시지: `[feat/infra] B-2 Guard Preflight 통합`.
