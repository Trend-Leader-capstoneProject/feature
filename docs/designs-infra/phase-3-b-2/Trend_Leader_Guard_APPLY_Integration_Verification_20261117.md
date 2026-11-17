# Guard APPLY 내부 통합 구현 및 검증 기록

기준: `origin/dev` `641cde6b748a69d54930dc3415ed71e5955fac9a`.
GitHub PR #119의 `merged=true`, `base=dev`, merge SHA 및 fetch한 로컬 참조를 확인했다.
작업 브랜치: `feat/phase-3-b-2-guard-apply`. 시작 작업 트리는 깨끗했다.

**판정: 내부 실행 경로 구현 / 오프라인 회귀 PASS / 격리 MariaDB APPLY 통합 미검증.
운영 CLI apply는 MODE_NOT_ENABLED, 운영 적용 불가.**

## 범위와 사용자 추가 결정

- M-A1, B-2, B-3, L-2 최종 기술 검증 보고서를 기준으로 구현했다.
- 추가 운영 확정안 없음: 운영 승인 어댑터, 파일 형식/경로/ACL, 계정 최소 권한,
  감사 저장소 배치를 임의로 확정하거나 안전하다고 판정하지 않는다.
- 기존 D-2는 APPLY 대상이 아니다. 기존 D-2 DB/볼륨/네트워크/Secret,
  `trendleader-prod-bootstrap`, `trend_leader_prod_db`, Caddy에 접근·변경하지 않았다.
- 완료된 L-2 독립 시험을 반복하지 않았다. 신규 MariaDB 자원을 생성하지 않았다.
- 초기 로컬 Docker 조회는 sandbox의 Docker config/API 접근 거부로 실패했다.
  SSH 가용성은 검증하지 않았다. 사용자 추가 지시에 따라 DB 없는 검사에 한정했다.
- 기존 Revision, Alembic env, API, 개발/테스트 Compose, G5/G6 Writer는 변경하지 않았다.

## 변경 파일과 실행 계약

| 파일 | 내용 |
|---|---|
| `backend/scripts/migration_apply.py` | 내부 `ApplyRequest`와 `run_authorized_apply`, 운영용 `run_apply()`는 무조건 거부 |
| `backend/scripts/migration_apply_audit.py` | 별도 영속 파일 감사 저장소 후보, 원자적 ID 소비와 배타적 결과 기록 |
| `backend/scripts/migration_environment.py` | 기존 혼입 검사를 순수 공통 함수로 추출, B-2 필수 입력/결과 계약 유지 |
| `backend/scripts/migration_guard.py` | 차단 이유를 설명하는 주석/모듈 설명만 변경, 실행 동작 유지 |
| `backend/tests/core/test_migration_apply.py` | 합성 승인·실측/장애 주입·재연결 차단·Alembic 전달 검사 |
| `backend/tests/core/test_migration_apply_audit.py` | 실제 파일 생성/동시 ID 소비/부분 실패/동기화 실패/결과 불변 검사 |
| 본 문서 | 결과, 잔여 Gate, 신규 격리 검증 준비 및 PR 설명 |

운영 Guard의 인자 없음/deny, 정확한 preflight 및 다른 명령 거부 계약은 유지한다.
apply는 내부 모듈을 import하지 않고 exit 2 / MODE_NOT_ENABLED로 거부한다.
환경변수/파일을 제출하는 방식의 새 승인 CLI나 우회 옵션은 추가하지 않았다.

내부 실행 순서는 다음과 같다.

1. 환경 혼입 거부 및 B-3 검증을 수행한다. 독립 Manifest/Evidence 바이트 pin,
   실행 이미지 검증, 복구 증거, 사용 ID 조회 사실이 없으면 거부한다.
2. 정확한 설정 대상과 계정을 비교한다. root는 검토값이 일치하더라도 거부한다.
   독립 검토한 적용 전/후 구조 pin, 계정 GRANT pin과 유한 Lock timeout을 요구한다.
3. DB 연결 전에 감사 저장소에서 승인 ID를 원자적으로 소비한다.
4. 전용 Engine의 단일 Connection으로 DB/실제 계정/MariaDB/문자셋/Collation/
   Revision/객체 구조/검토된 GRANT를 확인한다.
5. DB별 고정 이름으로 GET_LOCK을 한 번 호출한다. 정수 1만 성공이다.
   잠금 대기 이전 조회의 snapshot을 commit한 뒤 같은 Connection에서 재검사한다.
6. 잠금 소유 세션과 승인 유효시각을 재확인하고, Alembic에 같은 Connection과
   승인된 정확한 target_revision을 전달한다. ini/접속 URL/logging 설정을 전달하지 않는다.
7. commit 이후 같은 Connection으로 Lock/대상/Revision/구조/GRANT를 사후 검사한다.
8. RELEASE_LOCK의 정수 1 및 자기 세션의 소유 해제를 확인한다. 다른 실행이 즉시
   재획득할 수 있으므로 해제 뒤 전역적으로 영원히 FREE일 것을 요구하지 않는다.
9. 연결/Engine 정리까지 성공한 경우만 APPLIED 결과를 기록하고 exit 0을 반환한다.
   결과 기록 실패도 성공으로 반환하지 않는다.

테이블/열/인덱스/FK/제약 및 뷰/트리거/루틴/이벤트 catalog의 hash를 비교하며
실제 사용자 데이터나 SQL 원문을 기록하지 않는다. 구조 pin은 데이터 무결성,
서버 고유 신원, 백업 복원, 권한의 적정성을 독자적으로 증명하지 않는다.
SHOW GRANTS는 credential hash를 포함할 수 있어 원문은 메모리에서만 hash한다.
검토 pin과의 일치는 최소 권한 정책을 새로 확정한 것이 아니다.

SQLAlchemy do_connect에서 최초 연결 이후 DBAPI 연결 시도를 차단한다.
handle_error의 disconnect 표식과 invalidated 상태를 확인하며 끊긴 Connection으로
Lock SQL을 시도하지 않는다. DDL 시작 후 예외/중단/사후 불일치/Lock 해제·정리 실패는
UNKNOWN이다. 재접속, Migration 재시도, 승인 ID 환급은 없다.

## 감사 저장소 후보의 경계

- 운영자가 별도로 사전 생성한 절대 경로만 받으며 기본 경로를 만들지 않는다.
  B-2 Evidence와는 별개의 저장소다.
- 승인 ID의 SHA-256을 디렉터리 이름으로 쓰고 배타적 mkdir로 경쟁을 해결한다.
  사전 존재 확인 결과만으로 소비를 판단하지 않는다. 부분 디렉터리도 사용한 ID다.
- root directory sync → mkdir → root directory sync → started 파일 write/flush/fsync →
  hardlink 배타 게시 → 실행 디렉터리 sync가 성공해야 DB 연결을 시작한다.
- started/result는 서로 별도 파일이다. 기존 파일을 교체하지 않는다. 임시 hardlink와
  불완전 기록은 자동 삭제하지 않는다. 결과의 status/reason 모순도 거부한다.
- 기록 내용은 승인 ID hash, Manifest/Evidence hash, UTC 시각, 고정 상태/Reason뿐이다.
  원본 ID/Manifest/Evidence/URL/비밀번호/JWT/예외를 쓰지 않는다.
- POSIX 소유자/0700 디렉터리, 0600 파일, symlink/reparse 거부와 fsync를 사용한다.
  보호된 ancestor/UID/GID/마운트/내구성/정규 저장소의 단일성은 외부 Gate다.
  host 관리자에 대한 위변조 방지 저장소로 주장하지 않는다.
- Windows는 디렉터리 fsync를 입증하지 못하므로 실제 소비를 거부한다. 단위 시험의
  동기화 모의 성공은 저장 내구성의 증거가 아니다. 실제 POSIX 검사는 이번에 SKIP이다.

## 실제 실행한 검사

Windows / Python 3.14.0 / SQLAlchemy 2.0.51 / Alembic 1.18.5 / PyMySQL 1.2.0 /
pytest 9.1.1 / Ruff 0.16.0 / Pydantic 2.13.4 / pydantic-settings 2.14.2.
현재 Python에서 기존 공유 venv 패키지를 PYTHONPATH로 읽었다. 설치/의존성 변경 없음.

`backend/`에서 실행:

```powershell
$env:PYTHONPATH = (Resolve-Path ../../trend-leader/.venv/Lib/site-packages).Path
python -m pytest tests/core/test_migration_apply.py tests/core/test_migration_apply_audit.py tests/core/test_migration_guard.py tests/core/test_migration_approval.py tests/core/test_migration_preflight.py tests/core/test_migration_environment.py tests/core/test_migration_evidence.py tests/core/test_migration_observation.py tests/core/test_migration_report.py tests/core/test_migration_integration.py tests/core/test_migration_db_config.py tests/core/test_migration_fixture_env.py tests/core/test_alembic_env.py tests/core/test_account_migration_apply_guard.py -q -rs --tb=short --maxfail=3 --basetemp=.venv/apply-final-catalog
python -m ruff check .
```

- 최종 영향 범위 **517 PASS / 2 SKIP / 0 FAIL·ERROR**, Backend 전체 Ruff PASS.
  SKIP은 실제 POSIX 감사 fsync와 기존 Evidence POSIX 소유자/권한 검사다.
- 최종 origin/dev 재조회 SHA는 기준과 동일하다. tracked/staged diff 및 untracked
  파일을 별도로 검토했다. 변경은 위 7개 파일뿐이며 staged 변경은 없다.
- root를 검토된 Migration 계정으로 허용하던 부정 시험 1 FAIL을 확인한 후 수정했다.
  감사 결과의 성공/실패 모순을 허용하던 시험 3 FAIL도 확인한 후 수정했다.
- 최초 수집의 미구현 ImportError는 행동 Red로 집계하지 않았다. 실제 SQLAlchemy의
  재접속 차단 예외가 StatementError로 포장된 1건은 기대 예외를 수정했다.
- 16개 동시 파일 소비 중 단 1개 성공, 재시작/불완전 기록/오래된 미사용 snapshot을
  통한 승인 ID 재사용 거부, 실패 후 새 store 인스턴스를 통한 재시도 차단을 검사했다.
- 두 번째 DBAPI 연결 생성 차단은 실제 SQLAlchemy+메모리 SQLite에서 검사했다.
  MariaDB의 DDL/암묵 commit/Lock 통합 검증 또는 L-2 재시험으로 집계하지 않는다.
- 실제 Alembic command 전달과 기존 env의 외부 Connection 재사용 계약은 오프라인으로
  검사했다. 실제 Revision 함수 실행/DDL 성공을 주장하지 않는다.
- Backend 전체 DB/API 회귀와 Frontend 검사는 미실행: 변경은 Migration scripts와
  관련 테스트/문서뿐이며 신규 격리 MariaDB가 아직 준비되지 않았다.

## 신규 격리 MariaDB 검증 준비 — 아직 실행하지 않음

기존 D-2를 복제하거나 그 Secret을 공유하지 않는다. 다음은 신규 자원 후보이며
실제 배치 승인·이미지 digest·UID/GID·권한/복구 절차 확인 전 provisioning하지 않는다.

| 자원 | 신규 후보 |
|---|---|
| Compose project | `trendleader-apply-integration-test` |
| DB container | `trendleader-apply-integration-test-db-1` |
| Internal network | `trendleader-apply-integration-test_apply_net` |
| 전용 DB volume | `trendleader-apply-integration-test_apply_db_data` |
| DB / 계정 | `trend_leader_apply_integration_test` / `apply_test_migrator` |
| endpoint / 포트 | 신규 network의 `db:3306`, host 포트 미게시 |
| Secret | 신규 전용 Secret 파일, 컨테이너 `/run/secrets/apply_db_password`에 읽기 전용 |
| Evidence / 감사 | 서로 다른 신규 host 보호 영속 디렉터리, 감사는 POSIX fsync 필요 |
| 테스트 컨테이너 | 새 backend digest pin, 신규 network만 연결, restart=no, Runtime/JWT/Writer Secret 없음 |

Ubuntu에서 신규 자원이 별도 승인으로 준비된 뒤에만 다음 **읽기 전용** 명령으로 확인한다.
실제 전체 inspect/config/env/logs 출력은 Secret 노출 우려가 있어 사용하지 않는다.

```sh
sudo -n docker container inspect trendleader-apply-integration-test-db-1 --format '{{json .NetworkSettings.Ports}}'
sudo -n docker container inspect trendleader-apply-integration-test-db-1 --format '{{json .HostConfig.PortBindings}}'
sudo -n docker container inspect trendleader-apply-integration-test-db-1 --format '{{json .NetworkSettings.Networks}}'
sudo -n docker container inspect trendleader-apply-integration-test-db-1 --format '{{range .Mounts}}{{println .Type .Name .Destination .RW}}{{end}}'
sudo -n docker container inspect trendleader-apply-integration-test-db-1 --format '{{.Image}}'
sudo -n docker network inspect trendleader-apply-integration-test_apply_net --format '{{.Internal}} {{range .Containers}}{{println .Name}}{{end}}'
sudo -n docker volume inspect trendleader-apply-integration-test_apply_db_data --format '{{.Name}} {{.Driver}} {{.Mountpoint}}'
```

기대값은 host 포트 없음, 신규 internal network만 연결, 신규 volume만 DB 데이터에 마운트,
기존 D-2/운영/Caddy 컨테이너 참여 없음이다. 추가로 신규 테스트 컨테이너의 동일한 검사와
Secret RO 마운트·소유자/권한·별도 생성 증거, 보호된 Manifest/Evidence/감사 경로 및
검토한 실행 이미지 pin을 확인해야 한다. 위 출력만으로 DB 신원이나 최소 권한을 확정하지 않는다.

읽기 전용 SQL의 허용 검증 항목은 `DATABASE()`, `CURRENT_USER()`, `VERSION()`,
DB 기본 문자셋/Collation, 기존 Revision/객체와 독립 검토한 GRANT digest다.
Secret은 파일로만 전달하고 SHOW GRANTS/URL/비밀번호/원본 오류는 출력하지 않는다.
계정 bootstrap/GRANT의 정확한 SQL은 미확정 최소 권한을 추측해 제공하지 않는다.

신규 전용 통합 harness는 아직 없다. 승인 후 별도 harness에서 다음을 검증해야 한다.
이 단계는 `python -m scripts.migration_guard apply` 차단을 해제하는 작업과 분리한다.

1. 신규 빈 DB/Bootstrap 및 복구 증거를 독립 확인하고 적용 전/후 Schema pin을 검토한다.
   시험 Fixture가 실측을 해시한 뒤 운영 검토 사실이라고 주장하지 않게 한다.
2. FileApplyAudit의 실제 POSIX 파일/디렉터리 내구성, 동시 ID 소비 및 신규 Migration
   최소 계정의 실제 권한을 검증한다. Runtime/root 분리와 DDL 권한 부정 시험도 필요하다.
3. 내부 실행 경로로 정확한 승인 Revision을 적용하고 버전/테이블/열/인덱스/Lock 해제와
   started/result 기록을 확인한다. 빈 DB 및 승인된 이전 Revision의 두 경로가 필요하다.
4. 잠금 대기 중 상태 변경, 두 서로 다른 승인 경쟁, 연결 상실, DDL 중단, 사후 불일치,
   감사 저장/결과 저장/해제 실패에서 성공 및 자동 재접속/재시도가 없음을 확인한다.
5. 실패·UNKNOWN이면 자원과 감사 기록을 보존한다. 자동 재초기화/재실행/volume 삭제 금지.
   DB 상태를 조사하고 복구/새 승인 없이는 다시 APPLY하지 않는다.

## 미완료 차단 조건 / PR 검토용 설명

운영 CLI 활성화를 막는 항목:

1. 승인자/Manifest 형식·보호/독립 pin 전달/실행 이미지·DB 신원/복구 증거의 운영 어댑터.
2. 전용 Migration 계정 최소 권한·Runtime/root 분리와 write pause의 독립 실증.
3. 감사 저장소의 운영 위치·동일 root 강제·ancestor/ACL·UID/GID·영속성·보관 조건 확정.
4. 신규 격리 MariaDB의 실제 Guard APPLY 통합 시험. L-2 PASS를 이 항목의 PASS로 대체하지 않는다.
5. 운영 Compose·AWS/공개 Gate 및 운영 적용에 대한 별도 승인.

PR 제목 후보: `[feat/migration] Guard APPLY 내부 통합과 Fail Closed 차단 유지`

PR 본문 초안:

> B-3의 오프라인 대조를 실제 Migration 실행으로 바로 연결하지 않도록, 별도의 내부
> 실행 요청에 승인/복구/이미지 검토 사실과 감사 기록을 요구하는 경로를 추가합니다.
> 승인 ID 소비 후 동일 Connection에서 대상/계정/Collation/Revision/구조/GRANT를 확인하고,
> GET_LOCK·적용 직전 재검증·정확한 Revision 실행·사후 검사·해제를 조정합니다.
> 연결 상실/DDL 중단/결과 불명은 재접속·재시도 없이 차단합니다.
>
> 운영 승인/계정/감사 조건이 미확정이므로 Guard CLI apply는 MODE_NOT_ENABLED를 유지합니다.
> 영향 범위 517 PASS / 2 SKIP, Backend Ruff PASS. 신규 격리 MariaDB APPLY는 미실행이며
> 실제 운영 적용이 가능한 상태로 보고하지 않습니다. 기존 D-2/운영 DB/Revision/API/
> 개발 Compose/G5·G6 Writer 변경은 없습니다.

본 문서는 로컬 PR 준비 단계의 검증 기록이다. 이후 2026-11-17 사용자 승인에 따라
기능 브랜치 commit/push 및 dev 대상 PR 생성을 진행한다. 운영 CLI APPLY 차단과
자동 병합 금지는 유지한다.

참고: [Alembic shared Connection](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands),
[SQLAlchemy do_connect](https://docs.sqlalchemy.org/en/20/core/events.html#sqlalchemy.events.DialectEvents.do_connect),
[MariaDB GET_LOCK](https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/miscellaneous-functions/get_lock),
[MariaDB COLUMNS](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-columns-table),
[MariaDB CHECK_CONSTRAINTS](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-check_constraints-table).
