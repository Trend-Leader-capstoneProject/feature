# B-2 DB Observation 구현·검증 기록

2026-11-14 KST. DB Observation 오프라인 구현 단계의 기록이며 B-2 기능 완료, MariaDB 검증 완료 또는 배포 승인이 아니다.

## 기준과 변경 범위

- Worktree: `trend-leader.worktrees/feat-phase-3-b-2-preflight-integration`
- Branch: `feat/phase-3-b-2-preflight-integration`
- HEAD: `0a731da4b38f8be808400711ec635982cea3a76c` (변경 전후 동일)
- [PR #104](https://github.com/Trend-Leader-capstoneProject/feature/pull/104): `dev` 병합 확인. 병합 SHA 및 확인 시점 원격 `dev`: `cd079ed3886234e6f9df21613f31613f13c8bdd2`. Connector compare 결과 identical.
- Git 직접 원격 접속은 실패했다. GitHub Connector로 병합·원격 문서를 확인했다.
- 체크아웃된 B-2 문서는 이전 후보안이다. 병합된 동일 경로의 FROZEN 문서(blob `4a3ea1e67665e8b925bfc86b5fb2c96dbbf9a5a4`)와 M-A1을 구현 기준으로 사용했다. 브랜치 전환·병합·기존 설계 파일 덮어쓰기는 하지 않았다.
- 시작 시 미커밋 변경 없음. Responses API 및 다른 Worktree의 파일은 수정하지 않았다.
- 신규 코드: `backend/scripts/migration_observation.py`
- 신규 테스트: `backend/tests/core/test_migration_observation.py`
- 기존 순수 분류, Guard, Migration Settings, Alembic env/Revision, Schema, Runtime API, Compose는 변경하지 않았다. CLI의 모든 기존 거부 정책을 유지한다.

## 구현 계약

- `observe_database(MigrationDbSettings)`는 내부 관찰 결과만 반환한다. Evidence JSON, inspection_status, exit code, 승인 상태를 만들지 않는다. Evidence 저장 전 OBSERVED 성공을 선언하지 않는다.
- Migration Settings와 Secret 검증 → 저장소의 실제 Revision 계보 확인 → 전용 NullPool Engine → 새 Connection 1개 → 첫 애플리케이션 SQL `START TRANSACTION READ ONLY` → 고정 메타데이터 SQL → rollback/close/dispose.
- 관찰: DATABASE(), CURRENT_USER(), VERSION(), SCHEMATA 기본 문자셋/Collation, 가시적인 테이블·뷰·루틴·이벤트·트리거, 실제 alembic_version 행. 업무 데이터 조회 없음.
- 실제 DB명/인증 사용자명과 설정이 다르면 TARGET_MISMATCH. 인증 Host는 관찰만 하며 B-3의 승인된 user@host 비교를 대체하지 않는다. MariaDB가 아닌 버전·불완전 메타데이터는 실패한다.
- 버전 테이블 없음과 빈 테이블을 구분한다. NULL Revision은 원값을 보존하고 INDETERMINATE로 분류한다. 동일 이름의 뷰는 버전 테이블로 조회하지 않는다. 빈 후보는 권한 범위의 후보일 뿐 빈 DB 확증이 아니다.
- 재시도/재접속/사전 ping 없음. 허용 목록 밖 SQL 거부. 시작/조회 실패 후 추가 관찰 SQL 없음. cleanup 실패는 성공 결과를 폐기한다.
- 예외 원문·URL·비밀번호를 반환하거나 출력하지 않는다. SQLAlchemy Pool이 원래 삼키며 원시 예외를 기록하는 물리 close 오류도 포착한다. 이를 위해 버전 의존적인 private close hook을 최소 확장하고 해당 Pool의 로그만 격리한다. SQLAlchemy 변경 시 오프라인 및 격리 DB 재검증이 필요하다.
- P0-B 환경변수 감사는 동결 문서대로 후속 Guard 책임이다. P0-A Evidence 경로 사전 검증도 후속 조정 계층의 책임이다. 현재 모듈을 운영 CLI로 직접 연결하지 않는다.

## 이번 실행 결과

- 설치 패키지: SQLAlchemy 2.0.51, PyMySQL 1.2.0, Alembic 1.18.5, pytest 9.1.1, Ruff 0.16.0.
- 기본 python은 다른 Worktree의 깨진 venv launcher를 가리켰다. 해당 venv를 수정하지 않고 `C:/Python314/python.exe` (3.14.0)에 기존 설치 site-packages를 PYTHONPATH로 연결했다. 운영 이미지 환경 검증은 아니다.
- Red: 신규 모듈 미존재로 테스트 수집 실패 확인. 후속 NULL Revision 보존 테스트도 FAIL 확인 후 수정했다.
- 최종 PASS: 신규 관찰 테스트 40개 + 관련 기존 회귀 50개 = **90 passed / 0 failed / 0 skipped**.
- PASS: Backend 전체 `ruff check .`.
- PASS: tracked/staged diff 공백 검사 및 신규 파일의 no-index 공백 검사. Windows 긴 경로 문제는 명령별 `-c core.longpaths=true`로 재검사했다. Git 설정은 변경하지 않았다.
- 실제 MariaDB 시험: **NOT RUN** (별도 승인 없음). pytest SKIP로 집계한 것이 아니다. Backend 전체 pytest는 실행하지 않았으며 DB 자동 Migration Fixture를 사용하는 시험을 호출하지 않았다.

최종 명령은 `backend/`에서 실행했다.

```powershell
$env:PYTHONPATH = (Resolve-Path ../../../trend-leader/.venv/Lib/site-packages).Path
& C:/Python314/python.exe -m pytest tests/core/test_migration_observation.py tests/core/test_migration_preflight.py tests/core/test_migration_guard.py tests/core/test_migration_db_config.py tests/core/test_migration_fixture_env.py -q --basetemp=C:/Users/Public/Documents/ESTsoft/CreatorTemp/b2-observation-final
& C:/Python314/python.exe -m ruff check .
```

## READ ONLY 근거와 한계

설치된 SQLAlchemy의 MySQL/PyMySQL Dialect `do_begin()`은 SQL을 전송하지 않는 구현이다. 실제 SQLAlchemy Engine/Connection/autobegin/Pool + Fake DBAPI 시험에서 같은 Connection·물리 연결을 사용하고 첫 애플리케이션 SQL이 READ ONLY임을 확인했다. 초기화 SET NAMES/rollback은 구분했다. 실제 PyMySQL의 끊긴 query 경로에서도 connect가 호출되지 않음을 오프라인으로 확인했다.

[SQLAlchemy autobegin 설명](https://docs.sqlalchemy.org/en/20/core/connections.html#commit-as-you-go)과 [MariaDB START TRANSACTION 문서](https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction)는 이러한 구현 검토의 근거다. START TRANSACTION은 기존 트랜잭션을 암묵 commit할 수 있으므로 관찰 SELECT나 명시적인 begin을 선행하지 않는다. 이는 실제 서버의 쓰기 차단을 증명한 결과가 아니다.

미검증: MariaDB 12.3.x에서 전체 DBAPI/Dialect 초기화, READ ONLY 쓰기 부정 시험, 권한별 메타데이터 가시성, 실제 연결 단절·rollback·close, 실제 Revision 상태별 결과. 실제 접속·권한·데이터 변경 시험은 별도 승인된 격리 DB에서만 수행한다.

## Evidence Writer 후속 조건

1. 원격 FROZEN 설계가 현재 체크아웃의 후보안보다 최신임을 유지·반영하고 이 내부 결과 계약을 확인한다.
2. P0-A 보호된 절대 경로 사전 확인, 실행 ID 배타 예약, 신규 파일·무덮어쓰기 게시·동기화·중단 기록·저장 실패를 TDD로 구현한다. 운영 절대 경로/UID/GID를 추정하지 않는다.
3. Writer/Guard 조정 시 P0-B 환경 감사와 P0-C 상태·Reason·exit 매핑을 구현한다. 관찰 또는 정리 실패를 정상 Evidence로 승격하지 않고, 영속 저장 전 OBSERVED/exit 0을 반환하지 않는다.
4. Writer 오프라인 구현은 진행 가능하다. B-2 실제 검증 완료에는 별도 승인된 격리 MariaDB 시험이 필요하다. Guard 활성화·B-3·L-2·운영 적용은 이번 범위 밖이다.

커밋·Push·PR·병합은 수행하지 않았다. 권장 커밋 메시지: `[feat/infra] B-2 DB 관찰 기능 추가`.
