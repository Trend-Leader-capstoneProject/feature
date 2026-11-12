# Trend Leader — Phase 3-B-2 운영 Compose / DB 실행 경계 Design Review v0.5 (DRAFT)

> **2026-11-12 이후 채팅 결정 반영 안내 (본 문서에 우선 적용):**
> - 사용자는 **M-A1(운영 Compose의 선택적 일회성 Migration Profile) + Alembic의 DB 전용 Settings 분리**를 구현 방향으로 선택했다. 실행 차단 메커니즘, DB 계정·Secret, 권한 SQL, 이미지 Digest, 테스트는 **NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**이다.
> - 위 선택은 P4/G4/G5/G6 기존 HOLD 및 데이터 게시 승인 정책을 변경하지 않는다.
> - 원문에 `M-A NOT SELECTED`, `M-A/M-B 미선택` 또는 `GitHub 미변경`과 같은 표현이 있으면 **과거 초안 작성 시점의 기록**이다. 현재 선택 상태와 원격 반영 사실은 이 안내와 README를 우선한다.
> - `dev` HEAD SHA 표기는 해당 DRAFT 작성 당시 근거 버전이며, 최신 원격 상태의 증명이 아니다.

> 작성 기준: 2026-11-12 KST  
> 기준 저장소: `Trend-Leader-capstoneProject/feature` / `dev` HEAD `b133b494f8258eea603243f8f07191a33290084a`  
> 상태: **REVIEW DRAFT / NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**  
> 목적: 독립 운영 Compose, 명시적 DB Bootstrap, 별도 Alembic, 계정 최소 권한, Preflight의 책임과 실행 순서 정합성 검토  
> 변경 범위: 이 로컬 리뷰 문서만 새로 작성. 기존 DRAFT, GitHub, AWS, DB·Docker 리소스 미변경.

## 0. 보존할 결정 / 아직 선택하지 않은 것

**사용자 선택 유지**
- 기존 `docker-compose.yml`, `docker-compose.test.yml`을 보존하고 독립 `compose.prod.yaml`로 운영.
- DB Bootstrap / Migration / Account Provisioning 책임 분리.
- 최초 Bootstrap 관리자 작업은 **기존 MariaDB 컨테이너 내부에서 명시적 수동 실행(A안)**.
- 새 운영 DB는 `utf8mb4` / `utf8mb4_unicode_ci` 유지.
- 일반 API Runtime 권한은 API Runtime Privilege Review v0.3 6개 테이블의 최소 권한 후보.
- G4/G5/G6 실제 운영 Gate HOLD, RSS-OPS HOLD, P4 Writer APPLY 미승인.

**아직 미확정**
- 운영 이미지 Digest(12.3.3은 후보일 뿐), Caddy 버전, 실제 무료 DNS 이름 및 TLS 발급 성공.
- DB Runtime Host `@'%'` 또는 더 좁은 호스트 패턴(현재 `@'%'`는 검증 후보).
- Migration 전용 계정의 정확한 권한·비밀정보 전달·실행 방식.
- 운영 Secret 원본 경로·파일 권한, 백업 저장소·복구(3-B-3).
- Caddy에 의한 `/docs`, `/openapi.json`, `/health/ready` 공개 범위.

## 1. 소스 근거 및 확인된 코드

| 소스 파일 | 확인된 사실 | 운영 영향 |
| --- | --- | --- |
| `docker-compose.yml` | DB 이미지 기본 `latest`, `MARIADB_DATABASE`/`MARIADB_USER` 사용, DB init.sql 마운트, API 포트 호스트 게시, 고정 `container_name` | 운영 파일에 복제하지 않음 |
| `.env.compose.example` | 초기 생성 사용자 `DB_USER`, 별도 `API_DB_USER`를 정의 | 초기 생성 사용자에게 이미지가 부여하는 광범위 권한과 Runtime을 혼용하지 않음 |
| `backend/sql_script/init.sql` | `trend_leader` DB를 생성 시도하며 `utf8mb4_unicode_ci` 선언 | 운영에서는 별도 Bootstrap에서 DB 생성/Collation을 보장 |
| `backend/app/core/config.py` | `DATABASE_URL`이 개별 DB_* 우선, `app_env=local`, `debug=True`, `secrets_dir` 없음 | Runtime 환경/DB 자격 증명 Preflight 필수 |
| `backend/Dockerfile` | `WORKDIR /app`, Python 3.12, 코드 COPY, 일반 실행 CMD는 uvicorn | 동일 Python 코드로 Alembic 실행은 가능하나 독립 자격 증명 필수 |
| `backend/alembic/env.py` / 3개 버전 스크립트 | Alembic은 ORM·Settings·DB URL 사용; 초기 생성·인덱스·ALTER/제약 변경 수행 | Migration 권한은 Runtime DML과 다름; 실제 DDL 권한/실행 검증 필요 |
| `backend/app/api/routes/health.py` | `/api/health`는 프로세스 확인, `/api/health/ready`는 DB `SELECT 1` 확인 | 권한/스키마/업무 기능 완성을 대체하지 않음 |

## 2. 파일별 책임 제안

| 파일/영역 | 내용 | 버전 관리 |
| --- | --- | --- |
| `compose.prod.yaml` (신규) | 운영 3개 상주 서비스(`db`,`backend`,`proxy`), 네트워크·볼륨·Secret 마운트 | Git 가능(실제 Secret 절대 금지) |
| 운영 Caddy 설정(경로 미정) | 공개 호스트명, HTTPS, `backend:8000` 프록시, 프록시 경로/로그 정책 | Git 가능(비밀 토큰 제외) |
| 운영 변수 예시(파일명 미정) | 허용되는 변수명·의미만; 샘플 비밀번호 사용 금지 | Git 가능 |
| 운영 Secret 원본 | root 비밀번호, Runtime DB 비밀번호, JWT Secret 등 역할별 보호 | Git 제외; 서버 접근 제한 |
| Bootstrap SQL(신규 검토) | 새 DB 생성/Collation 및 Migration 계정 준비, **수동 실행** | 비밀값 없는 템플릿만 Git 가능 |
| Migration 실행 계약 | Alembic 전용 단발 실행, 전용 DB 계정, 실행 전 승인·백업 | 실행 절차 문서; 실제 값 보호 |
| Runtime Provisioning SQL(신규 검토) | Migration 후 테이블별 GRANT, 계정/Host/기존 GRANT 감사 | 비밀값 없는 템플릿만 Git 가능 |
| Preflight(신규 검토) | DB/계정/역할/권한/Schema/Collation/API 경로 검사 | 판정표와 증거 형식은 Git 가능 |
| 백업·복원 | 별도 외부 저장소와 복원 리허설 | Phase 3-B-3 상세 설계 |

**중요:** `compose.prod.yaml`을 사용할 때 개발 파일과 섞는 복수 `-f`를 사용하지 않음. 고정 프로젝트 이름(예: `trendleader-prod`, **가칭**)과 배포 명령에서 `-f`를 명시. 사용자 로컬 개발 Compose 및 운영 Compose가 같은 호스트에 있어도 고정 container_name·volume name 충돌이 없도록 설계.

## 3. 실행되는 서비스와 네트워크 불변조건

| 서비스 | 네트워크 | 외부 포트 | 저장 데이터 / Secret |
| --- | --- | --- | --- |
| `db` | `db-net`(`internal: true` 우선 검토) | **없음** | 고정 운영 전용 DB 볼륨; root 비밀번호 파일은 `db`에만 |
| `backend` | `db-net` + `api-net` | **없음** | Runtime 전용 DB/JWT 설정만; 고권한 비밀번호 금지 |
| `proxy` (Caddy 후보) | `api-net` | TCP 80/443(방화벽은 별도) | Caddy 인증서/설정 영속 볼륨; DB 접속 불가 |

- DB hostname `db`, 포트 `3306`은 Docker 내부 연결. FastAPI `8000`은 프록시의 내부 접속 대상으로 유지.
- `depends_on: condition: service_healthy`는 DB Healthcheck 통과까지 기다릴 뿐 **Alembic, GRANT, 데이터 시드, 핵심 API 검증 완료를 보장하지 않는다**.
- Caddy 이미지, HTTPS DNS, 운영 이미지 Digest, 실제 방화벽은 아직 미검증. QR APK 내부 API URL은 최종 DNS/TLS 확정 후 검증.
- 내부 네트워크는 외부 공격을 완벽하게 차단하는 독립 안전 장치가 아님. Host 접근 및 Docker 관리 권한도 분리.

## 4. P0 보완 — 최초 배포를 단일 `up`으로 처리하면 안 됨

**권고 단계(모두 수동 승인/검증)**
1. 운영용 프로젝트 이름·볼륨·이미지·Secret 경로를 식별하고, 사전 설정 검증. 기존 볼륨이 있으면 최초 설치 절차 중단.
2. `db` 서비스만 실행, MariaDB 버전·root 내부 Unix Socket/Host·볼륨·3306 비공개 확인.
3. 관리자 수동 Bootstrap으로 DB(`trend_leader`, `utf8mb4_unicode_ci`)를 명시적으로 생성하고 검증. **Migration 계정은 Migration 실행 전에** 별도 준비.
4. Migration 전용 **일회성 작업**에서 승인된 Alembic `upgrade head` 실행. 평시 일반 API에 Migration Secret을 주입하지 않음.
5. 스키마/`alembic_version` 검증 후 관리자 승인 Provisioning: Runtime 계정의 적격 Host·권한을 확인하고 필요한 최소 GRANT 적용.
6. 격리 검증 및 실제 Runtime 접속 Preflight: `DATABASE()`, `CURRENT_USER()`, 유효 GRANT, DB 버전/Collation, 정상/금지 DML. 비밀정보 출력 금지.
7. 내부 Backend로 `/api/health/ready`와 핵심 서비스 기능 검증. **단순 SELECT 1만으로는 합격 아님.**
8. 마지막으로 `proxy` 공개 후 DNS/TLS·Android APK 실기기 연결 확인. G4/G5/G6 HOLD에서 미승인 트렌드 게시 경로는 계속 비활성.

**재배포:** 기존 볼륨이 있으면 init env/script 재실행을 가정하지 않는다. 기존 데이터/계정/Collation/스키마/권한을 읽기 감사하고, 승인된 차이만 적용. `down -v`, 임의 `DROP`/`REVOKE`/재초기화 금지. 변경 전 별도 백업 및 복원 시험 조건 준수.

## 5. Migration 실행 방식 — 이 단계에서는 두 후보 유지

| 후보 | 장점 | 위험 및 전제 |
| --- | --- | --- |
| M-A. `compose.prod.yaml`의 선택적 일회성 Migration 서비스(`profiles` 활용 후보) | 별도 계정/환경·DB 전용 네트워크 구성 명시 가능 | 프로필을 잘못 활성화한 `up`에서 자동 실행 위험. 실행 명령·시크릿 분리·단회 실행 보장 필요 |
| M-B. 검토된 별도 수동 one-off 실행 절차(별도 설정/명령) | 기본 상주 3서비스 설정에 Migration 비포함 | 네트워크/이미지·실행 변수/권한 전달 누락, 운영 명령 복잡성 |

**금지:** 일반 `backend` 서비스의 Runtime 자격 증명으로 `alembic upgrade head` 실행하거나, Alembic을 위해 일반 Backend에 DDL/관리 Secret을 주입하는 것. MariaDB `db` 컨테이너는 Python ORM/Alembic 실행 책임을 갖지 않음.

현행 3개 Alembic revision은 CREATE TABLE, CREATE INDEX, ALTER/DROP 제약 작업을 수행. `alembic_version` 유지에 필요한 DML은 별도 검증 대상. 정확한 Migration GRANT는 격리 MariaDB에서 버전별로 확정. 필요한 권한을 예측해 임의로 넓히지 않음.

## 6. Secret·변수 Preflight

- DB root는 이미지가 지원하는 `MARIADB_ROOT_PASSWORD_FILE` + `MARIADB_ROOT_HOST=localhost` 후보; 신규 볼륨 테스트 후 적용.
- 일반 Backend는 현재 Pydantic Settings 구조에서 환경파일 방식이 변경 최소. 운영 전용 파일은 권한 제한, Git·이미지·로그에서 제외.
- Runtime 필수 DB 설정 `DB_HOST=db`, `DB_PORT=3306`, 승인된 DB명·계정·최소 GRANT 검증. `DATABASE_URL`이 개별 설정보다 우선하는 현재 코드의 위험을 별도 차단.
- 개발용 `APP_ENV=local`, `DEBUG=true`가 운영으로 유입되지 않도록 공개 전 검증. `JWT_SECRET_KEY` 실제 값과 관리자/Writer/Migration Secret 공개 금지.
- Compose의 `--env-file`(설정 치환)과 서비스의 `env_file`(컨테이너 주입)은 별개. 최종 렌더링 검증 시 `docker compose config -q`처럼 출력 없는 검증을 우선 사용하고, 설정 원문/환경 파일을 공개하지 않음.
- 서비스 설정에 프로세스 상주용 Migration/Writer Secret이 들어가면 검증 실패. P4 Writer 계정/서비스는 G6 HOLD 중 활성화 금지.

## 7. Preflight 판정 / 테스트 계약

| ID | 정상 조건 | 실패 시 동작 |
| --- | --- | --- |
| CPF-01 | 운영 파일 한 개·프로젝트 이름·볼륨 식별 일치 | 배포 중단 |
| CPF-02 | 3306/8000 호스트 포트 미게시, 프록시만 80/443 | 외부 공개 중단 |
| CPF-03 | DB 버전/이미지 Digest·`utf8mb4_unicode_ci`·기존 데이터 식별 일치 | Bootstrap/Migration 중단 |
| CPF-04 | root Socket 접속 가능, 원치 않는 root 원격 계정 없음 | 공개 중단 |
| CPF-05 | Migration/Runtime/root Secret 분리; `DATABASE_URL` 혼입 없음 | 공개 중단 |
| CPF-06 | Alembic revision 기대값·테이블 세트 일치 | Provisioning/공개 중단 |
| CPF-07 | Runtime 실제 DB/계정/GRANT/역할/PUBLIC/DEFINER 영향 확인 | 공개 중단 |
| CPF-08 | Runtime 정상 인증·관심사·트렌드 조회 및 직접 트렌드 DML 거부 | 공개 중단 |
| CPF-09 | 인증서 상태, 프록시 경로, Android 실기기 네트워크 테스트 | APK 배포 보류 |
| CPF-10 | G6 HOLD의 게시 경로와 Demo Trend Seed 비활성 | 공개/게시 승인 분리, 미승인 게시 금지 |
| CPF-11 | 데이터 영속성/백업 복구(3-B-3), 최소 로그·자원 모니터링 | 실제 회원 데이터 운영 보류 |

모든 시험 현재 NOT TESTED. 리스크 큰 부정 DML, 계정 CREATE/GRANT, Migration은 **별도 격리 테스트 DB와 볼륨**에서만 실행한다. 기존 사용자 데이터 DB에서 시험용 쓰기 금지.

## 8. 현재 리뷰 결론

- 독립 운영 Compose의 **파일 책임과 실행 순서**는 작성 가능한 수준.
- 결정 보완 필요: Migration 단회 실행 방식(M-A/M-B), 계정별 실제 Host 매칭, Secret 경로, 정확한 Migration 권한, 이미지 Digest 및 DNS 이름, 백업 복원 계약.
- 따라서 `compose.prod.yaml` 실제 완성 구현/자동 배포/최종 동결은 아직 보류.
- 관련 SQL·Preflight 초안은 별도 `Trend_Leader_Account_Provisioning_SQL_Preflight_v0.1_DRAFT.md` 참고.

## 9. 1차 근거

프로젝트 실제 코드: GitHub `dev` HEAD `b133b494f8258eea603243f8f07191a33290084a`; `docker-compose.yml`, `.env.compose.example`, `backend/sql_script/init.sql`, `backend/app/core/config.py`, `backend/Dockerfile`, `backend/alembic/env.py`, `backend/alembic/versions/*`, `backend/app/api/routes/health.py`.  
기존 설계: `Trend_Leader_API_Runtime_DB_Privilege_Review_v0.3_DRAFT.md`, `Trend_Leader_Account_Provisioning_Design_v0.1_DRAFT.md`, `Trend_Leader_Account_Provisioning_Bootstrap_Review_v0.2_DRAFT.md`, `Trend_Leader_MariaDB_Production_Image_Bootstrap_Review_v0.3_DRAFT.md`, `Trend_Leader_Account_Provisioning_Host_Secrets_Review_v0.4_DRAFT.md`.

공식 참고:
- Docker Compose CLI/프로젝트 이름: https://docs.docker.com/reference/cli/docker/compose/ , https://docs.docker.com/compose/how-tos/project-name/
- Docker Compose 네트워크: https://docs.docker.com/reference/compose-file/networks/
- Docker Compose Secrets: https://docs.docker.com/compose/how-tos/use-secrets/
- MariaDB 이미지 초기화: https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables
- MariaDB GRANT: https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant
- Alembic runtime: https://alembic.sqlalchemy.org/en/latest/api/runtime.html