# Trend Leader — Phase 3-B-2 M-A1 실행 설계 확정안 v1.0

> 결정일: 2026-11-13 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`, `dev` HEAD `8a3f7e4418c1d85e4ffa504827440f098328e615`  
> 상태: **ARCHITECTURE / POLICY DECISIONS FROZEN** · 실제 구현 **NOT IMPLEMENTED** · MariaDB/Compose/운영 검증 **NOT TESTED** · 운영 배포 **NOT APPROVED**  
> 계승 문서: v0.7 실행 Guard·DB Settings DRAFT, v0.8 상세 실행 계약 DRAFT, v0.9 승인·잠금 리뷰 DRAFT, 원격 PR #94의 Phase 3-B-2 인덱스.  
> 사용자 결정: **M-A1, S-A, G-B, A-2, L-2 채택**. 세부 값·운영 증거 형식 가운데 아래에서 후보로 표시한 것은 실제 시험 후 확정한다. 기존 스키마·API·기능별 FROZEN 계약은 변경하지 않는다.

## 1. 문제 정의와 성공 판정

- 필요한 일: 승인한 *정확한* Alembic Revision을 올바른 MariaDB DB에, 해당 작업 전용 계정으로, 중복 실행 없이 적용한다.
- 하지 않을 일: 상주 FastAPI가 Migration 권한/비밀번호를 갖게 하거나, 일반 `up`에서 자동 변경하거나, G6 HOLD 중 트렌드 Writer APPLY를 활성화하거나, 별도 승인 웹서비스를 구축한다.
- **중요한 구별:** 설계 확정(FROZEN)은 작동 검증(PASS)이 아니다. 아래 배포 Gate가 전부 통과하기 전 운영 실행을 허용하지 않는다.

## 2. 확정된 책임 분리

| 선택 | 확정 계약 | 구현 시 확인 |
|---|---|---|
| M-A1 | 독립 `compose.prod.yaml` 안에 `migration` 일회성 서비스와 `maintenance` Profile | Profile 활성화/직접 서비스 지정은 실행할 수 있음; Profile만으로 승인되지 않음 |
| S-A | Alembic 전용 DB Settings. 일반 `app.core.config.Settings`와 `app.db.session` 기본 보존 | JWT 없는 실행, 별도 접속 값, 테스트 Fixture 회귀 |
| G-B | 허용 명령만 처리하는 Guard EntryPoint, 기본 동작은 `deny` | `command` 및 `entrypoint` 우회 가능성을 Docker 관리자 권한 통제로 보완 |
| A-2 | 실행 명령과 분리된 읽기 전용 운영자 승인 Manifest를 검증 | Manifest 자체는 인증/서명 증거 아님; 승인자·파일 접근 통제 필수 |
| L-2 | Guard가 획득한 MariaDB `GET_LOCK`과 Alembic이 **동일 SQLAlchemy Connection** 사용 | 실제 MariaDB DDL/암묵 COMMIT/연결 장애/재검증 시험 |

### 유지할 불변 조건

- DB 관리자 Bootstrap은 MariaDB DB 컨테이너 내 **명시적 수동 작업**. 최초 DB 생성 시 `utf8mb4`/`utf8mb4_unicode_ci`.
- Runtime / Migration / root / 미승인 Writer 자격 증명·권한 별도. Runtime에게 DDL, `alembic_version` 변경 권한 없음.
- G4/G5/G6 및 RSS-OPS HOLD 유지. P4 Writer 게시 APPLY 금지. 일반 회원·관심사 쓰기는 별도의 정상 서비스 계약.
- 개발용 Compose, 테스트용 Compose, 기존 기능 Router/인증 흐름은 이 작업에서 변경하지 않음.
- Google Drive는 **APK 파일 배포**만 담당. AWS는 HTTPS API/DB 운영. 유료 도메인 구매 보류와 HTTPS 완화는 전혀 다른 문제.

## 3. 실행 인터페이스 (운영 코드 구현 전 계약)

| 모드 | 계약 | 실패 시 |
|---|---|---|
| `deny` 또는 인자 없음 | DB 접속/DDL 없이 실패 종료. Profile 오활성 시에도 기본 경로는 거부 | `DENY_DEFAULT` |
| `preflight` | 대상·연결 계정·Collation·기존 Revision을 **읽기 전용으로** 감사하고 별도 보고서 생성. 승인·Migration 수행 안 함 | 오류 코드 출력, 비밀정보 미출력 |
| `apply` | A-2 Manifest 검증 → 실제 대상 감사 → L-2 Lock → 잠금 보유 중 재검증 → 승인한 정확한 Revision → 사후 검증 | 실패·결과 불명 시 재실행 자동화 금지 |
| 그 외 CLI, `upgrade head`, `downgrade`, `stamp`, `revision`, 쉘 실행 요청 | Guard 정상 경로에서 거부 | `INVALID_MODE` |

- Migration 서비스에 `restart: "no"`, 기본 Guard 진입점·거부 명령, `db-net`만 제공하고 `ports`, DB 데이터 볼륨, Docker socket, Runtime JWT/관리자/Writer Secret 전달 금지.
- Backend/Proxy는 Migration에 `depends_on`하지 않는다. 최초 배포는 DB 단독 기동과 준비 증명 후 Backend/Proxy 공개를 단계적으로 진행한다.
- Docker 관리자에게는 EntryPoint/명령 우회 권한이 남는다. G-B는 **실수 방지 및 표준 경로 검증**이지 공격자를 막는 인증 수단이 아니다.

## 4. S-A Migration Settings 계약

**운영 환경 입력 후보(이름은 구현 전 테스트 확정):**

- 필수: `MIGRATION_DB_HOST`, `MIGRATION_DB_PORT`, `MIGRATION_DB_NAME`, `MIGRATION_DB_USER`, `MIGRATION_DB_PASSWORD_FILE`
- 타임아웃은 유한값을 사용하되 실제 후보 환경 시험으로 상한 확정.
- `backend/.env`, `DATABASE_URL`, 일반 `DB_*`, `JWT_SECRET_KEY`, 관리자/Writer 자격 증명을 자동 대체 원천으로 삼지 않는다. 운영 Guard는 충돌·누락을 실패로 처리한다.
- DB 비밀번호는 운영 파일 기반 Secret으로 읽고 URL 문자열·시크릿 원문·파싱 오류를 로그에 출력하지 않는다. 비밀번호 특수문자 처리는 구조화된 SQLAlchemy URL 빌더로 처리한다.
- 일반 App Settings 및 `backend/app/db/session.py`는 Phase A에서 수정하지 않는다.
- `backend/tests/conftest.py`의 `TEST_DATABASE_URL` → `DATABASE_URL` 직접 주입은 Migration 전용 계약으로 바꿔야 한다. `trend_leader_test` 이름 검증을 보존하고 격리 DB Host/Port/권한 검증을 강화한다.
- 현재 `pydantic-settings`는 범위가 고정되지 않았으므로 실제 설치 버전을 확인하고 로딩 우선순위를 테스트한다.

## 5. A-2 최소 승인 Manifest 계약

**목표: 새 승인 UI/서버를 만들지 않는다.** 단일 파일 기반 검토·실행으로 범위 제한.

- 권장 포맷: JSON 1개(`schema_version`을 둬 스키마를 명시) — 표준 라이브러리 기반으로 새 YAML 파서 의존성 없이 구현 가능. 이는 v0.9 YAML 예시의 **비본질적 표현 방식 단순화**이며, 필수 정보는 동일하다. 포맷·필드명을 사용자가 최종 동결하지 않았다면 구현 테스트 시 그대로 유지/변경 기록 필요.
- 필수 의미 필드: `approval_id`(고유 식별자), `environment`, `deployment_project`, `db_host`, `db_port`, `db_name`, `expected_db_account`, `expected_from_revision`, `target_revision`, `backend_image_digest`, `preflight_evidence_id`, `backup_or_empty_db_evidence_id`, `approved_by`, `approved_at`, `expires_at`.
- `target_revision`은 `'head'` 문자열이 아닌 실제 승인된 Revision ID. 코드 이미지 식별·서버/DB 식별을 Manifest와 실측 Preflight 증거로 대조한다. `@@hostname`/`@@server_id`는 보조 자료일 뿐 단독으로 DB 고유성을 보장하지 않음.
- 승인 파일에 실제 비밀번호, DB 접속 URL, 토큰, JWT, 개인 사용자 데이터 없음.
- 승인 파일은 호스트의 운영자 전용 보호 경로에 저장하고 **Migration 컨테이너에 읽기 전용 마운트**. Guard가 Manifest를 자동 생성 후 곧바로 승인 처리하는 경로는 금지.
- **한 사람이 발급·승인·실행할 수 있는 현재 MVP:** 승인 절차의 증거와 실행 변경의 추적은 가능하지만, 독립된 이중 승인 또는 위변조 방지는 보장하지 않는다.
- 최초 *검증된 빈 DB*는 기존 데이터가 없어 백업 대신 빈 DB/Bootstrap 증거를 허용. 기존 데이터가 있는 DB는 승인된 백업·복원 증거 없으면 APPLY 금지.
- 운영 감사 기록은 Manifest와 별도로 보호된 영속 위치에 저장하고 **APPLY 시작 전 사용 기록을 남긴다**. 사용 ID가 이미 기록되거나 감사 저장소가 불가하면 자동 APPLY 거부. 결과 미상인 경우 ID를 재사용하지 않고 조사·새 승인 발급. 파일 저장소는 호스트 관리자 권한으로 변경 가능하며, 영구적 위변조 방지 저장소로 주장하지 않는다.
- 승인 파일 형식의 정확한 키·경로·권한과 사용 기록의 원자적 저장 구현은 Phase B에서 코드 테스트를 거쳐 확정한다.

## 6. L-2 잠금과 실제 적용 흐름

```text
[Guard apply]
  1. 명령 인자/설정/Manifest/실행 이미지/기존 실행 기록 정적 검증
  2. 현재 실행 ID를 영속 감사 위치에 기록(쓰기 실패 시 중단)
  3. 전용 Migration DB Connection 생성 → 대상·계정·Revision 관찰
  4. SELECT GET_LOCK('<DB별 협력적 잠금 이름>', <유한 timeout>)
     - 1만 성공 / 0, NULL, 예외는 APPLY 중단
  5. 잠금 보유 중 DB 실측, 승인 이전 Revision, 대상 객체 상태 재검증
  6. Alembic Config.attributes['connection']로 **같은 Connection** 전달
  7. command.upgrade(cfg, <manifest.target_revision>) 실행
  8. 같은 Connection으로 잠금/Revision/객체 상태 사후 감사
  9. 결과를 영속 기록. RELEASE_LOCK 및 Connection 종료
```

- `GET_LOCK`은 DB Connection 단위의 협력적 잠금이고 COMMIT으로 해제되지 않지만 연결이 끊기면 해제된다. Guard를 통하지 않는 관리자 SQL을 차단하지 않는다.
- `GET_LOCK`/`RELEASE_LOCK` 결과와 연결 유지 여부를 실제 MariaDB 후보에서 확인해야 한다. SQLAlchemy 2.x와 Alembic `transaction_per_migration` + DDL 암묵 COMMIT이 상호작용할 때, 문서의 `engine.begin()` 예시를 무조건 그대로 복사하지 않는다.
- 연결 끊김·Lock 소유 불명·DDL 중단은 `UNKNOWN` 또는 `FAIL`; **자동 재접속/자동 재실행 금지**. Schema 객체, Revision, 감사 기록을 점검한 후 새 승인으로 복구.
- `RELEASE_LOCK` 응답 실패를 단순 성공으로 간주하지 않는다. 연결 종료에 따른 자동 해제와 명시적 해제 성공을 구별한다.

## 7. 2026-11-17 범위와 단계별 Delivery 계획

> 아래 일정은 우선순위 계획이며 **기한 내 완료 보장이 아니다**. 필요 테스트가 통과하지 못하면 위험한 우회 대신 공개를 보류한다.

| 날짜(KST) | 우선 목표 | 완료를 가르는 증거 |
|---|---|---|
| 11/13 (금) | 구조적 결정 동결, Phase A 작업 구간 확정 | 본 문서와 테스트 목록, 변경 영향 파악 |
| 11/14 (토) | S-A 구현: Migration DB Settings, Alembic env, 테스트 Fixture | JWT 없이 Migration 설정 로딩, 기존 API 단위/통합 회귀 |
| 11/15 (일) | G-B 기본 deny/preflight 및 A-2 최소 Manifest 검증 | 비승인 경로 DDL 0, 독립 승인 파일 검증·민감정보 미노출 |
| 11/16 (월) | M-A1 Compose, L-2 Lock, 격리 MariaDB 시험 | `maintenance` 기본/오활성 거부, 동시 실행·오류 주입·Revision 검증 |
| 11/17 (화) | Account Provisioning/Preflight 및 AWS 연결 평가 | 최소 GRANT, Backup/빈 DB 증거, HTTPS/API E2E; 미통과 항목 명시 |

**최소 완료선(11/17):** M-A1 + S-A + G-B + A-2 + L-2가 **격리 환경에서 계약 테스트**를 통과하고, 재현 가능한 명령/증거/남은 이슈가 남아 있음. 실제 AWS 프로덕션 공개는 아래 별도 Gate를 모두 통과할 때만.

**전체 전시 데모 완료선:** AWS DB/HTTPS/API 배포, APK의 해당 API 주소·빌드·설치·실기기 인증/관심사/조회 통과, 공개 게이트 PASS. M-A1 작업만 끝나서는 달성한 것으로 기록하면 안 됨.

**기한 압박이 생길 때 줄일 항목:** 승인 웹 UI, 자동 서명/다중승인, 자동 승격 파이프라인, 운영 퍼포먼스 튜닝, 일반 DB 설정 전면 리팩터링, 유료 도메인, APK 파일 호스팅 서버.  
**줄일 수 없는 항목:** HTTPS 인증, Runtime/Migration/root 분리, 실제 DB 대상/권한 검증, 실패 후 자동 재시도 금지, 기존 운영 DB 보존, G6 HOLD.

## 8. 완료 기준과 회귀/장애 시험

- **SET**: JWT 부재 시 Migration 설정 성공; Migration 필수값 누락·JWT/일반 URL 혼입 거부; Secret 파일 내용 비노출; 기존 API 설정/세션/인증 테스트 영향 없음.
- **GUARD**: 인자 없음·임의 CLI·Profile 오활성 `deny` 실행, DDL 0; preflight 읽기만; 만료/누락/불일치 Manifest APPLY 거부.
- **APPROVAL**: 실행 ID 기록 후 실제 APPLY; 중복 ID 거부; 감사 저장 실패 거부; 이전/목표 Revision·이미지·DB/계정·증거 참조 검증.
- **LOCK**: 두 동시 Guard 중 단일 변경, `GET_LOCK` 세션 보유/COMMIT, 연결 상실/재연결 차단, 객체·Revision 사후 일치.
- **DB**: 격리 MariaDB 12.3.x 후보에서 Alembic 전개·테이블/인덱스 확인; Migration 최소 권한 성공, Runtime 직접 DDL/트렌드 게시 DML 거부.
- **OPS**: DB 3306/API 8000 외부 게시 금지, 관리자/Writer/Runtime/Migration Secret 교차 노출 없음, MariaDB/백업 증거/HTTPS 및 APK E2E 구별.

모든 시험 **현재 NOT TESTED**. 파괴적/권한 SQL 시험은 실제 운영 볼륨이나 기존 데이터가 아닌 **분리된 테스트 DB·볼륨**에서만 수행.

## 9. 구현 시작을 위한 변경 범위(Phase A)

- 신규 후보: `backend/app/core/migration_db_config.py` (Migration-only Settings와 연결 URL 조합), 별도 단위 테스트.
- 변경 후보: `backend/alembic/env.py` — 일반 `get_settings()` 제거, Migration Settings 사용, 추후 `Config.attributes['connection']` 경로 지원. `backend/tests/conftest.py` — 명시적 테스트 환경을 Migration 설정으로 전달.
- 초기 비대상: `backend/app/core/config.py`, `backend/app/db/session.py`, 기존 인증/관심사/트렌드 Router, 기존 Alembic Revision 원본.
- 소스 변경 전 해당 파일 HEAD 및 blob SHA 재조회, 최소 diff 방식 사용, 테스트 Red → Green → Refactor. 별도 기능 PR에서 작업, 본 대화는 설계 기록.

## 10. 결정 범위 및 잔여 미확정

**사용자 승인으로 동결된 선택:** M-A1, S-A, G-B, A-2, L-2 및 상위 보안·HOLD 불변조건.  
**구현 검증 후 확정할 값:** Guard 파일 경로·명령 구문, Pydantic-Settings 버전/비밀번호 파일 규약, JSON 포맷 채택 및 필드명, Manifest 보호·감사 파일 영속성, Lock 이름·timeout, MariaDB 필요 최소 DDL/시드 GRANT, 실제 이미지 Digest·Caddy DNS/TLS, 운영 계정 Host, 복구 증거 방법.  
**운영 실행 금지 조건:** 위 핵심 검증 미완료, 운영 DB 대상 불확실, 권한/Secret 결함, 백업·복원 미검증(기존 데이터), Schema Revision 불일치, Guard 우회, G6 HOLD 게시 경로 위험.

## 11. 기술 근거

- 프로젝트 소스: `backend/alembic/env.py`, `backend/app/core/config.py`, `backend/app/db/session.py`, `backend/tests/conftest.py`, `backend/Dockerfile`, `backend/.dockerignore`, `docker-compose.yml` (`dev` 확인).
- Docker Compose Profiles: https://docs.docker.com/compose/how-tos/profiles/
- Docker Compose Run: https://docs.docker.com/reference/cli/docker/compose/run/
- Alembic shared connection: https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands
- MariaDB GET_LOCK: https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/miscellaneous-functions/get_lock
- MariaDB implicit commit: https://mariadb.com/docs/server/reference/sql-statements/transactions/sql-statements-that-cause-an-implicit-commit
- Docker Secrets: https://docs.docker.com/compose/how-tos/use-secrets/