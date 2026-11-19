# Trend Leader — 로컬 개발환경과 AWS Lightsail 배포환경 가이드

> 버전: v1.0 | 작성일: 2026-11-19
> 대상: 팀원, ChatGPT, Codex 등 개발·검증 담당자
> 상태: 개발 및 배포 참고 가이드 (운영 적용 승인서 아님)
> 소스 확인 기준: dev `cc969371ac65d4f808bec88a22812b172c98df2b`
> 로컬 복구 검증 기준: fix/app-adjustments-20261118 `cdb524fc0958a897a77ce471410bad4825152d46`

## 1. 목적과 문서 사용 기준

이 문서는 환경 설정, 실행 프로세스, DB Schema 및 배포 산출물의 차이를 이해하고, 기존 인프라를 재사용하여 기능 개발·통합을 마무리하기 위한 참고 자료다. 신규 설치의 전체 절차는 [Windows 신규 개발자 온보딩 가이드](Trend_Leader_Windows_Developer_Onboarding_Guide_v1.0.md)를 참고한다.

[AGENTS.md](../../AGENTS.md), [AI Development Guidelines](../prompt/Trend_Leader_AI_Development_Guidelines.md), 기능별 최신 승인 확정안 및 운영 승인 정책을 유지한다. 문서의 커밋과 버전은 작성 당시 확인 기준이며 현재 상태를 대신하지 않는다.

**기존 문서와의 차이:** 기존 온보딩 가이드 3.2·5.1·11절 및 README의 일부 Migration 예시는 일반 관리 계정 또는 `backend/.env`를 기반으로 직접 Alembic을 실행하던 이전 구조를 설명한다. 현재 `alembic/env.py`는 별도 `MigrationDbSettings`를 사용하므로 그 예시를 그대로 실행하지 않는다. 현재 소스·승인된 실행 계약을 먼저 확인한다. 이 문서는 기존 운영 Guard를 대체하거나 변경하지 않는다.

## 2. 환경별 역할과 접속 구조

| 구분 | 로컬 개발 | Lightsail 배포 기준 |
|---|---|---|
| 실행 목적 | 기능 개발, 디버깅, 실기기 검증 | 외부 사용자 및 전시 서비스 |
| 호스트 | Windows / Docker Desktop | Linux 인스턴스 |
| Frontend | Expo Metro, 개발 번들 | 설치된 배포 APK |
| Backend | 호스트 Uvicorn 또는 Docker Backend 중 하나 | 검증된 릴리스 이미지 |
| MariaDB | 개인 개발 DB, 테스트 DB 분리 | 서비스 DB 및 영속 저장소 |
| API 진입점 | PC LAN IP 및 외부 API 포트 | HTTPS 도메인, Reverse Proxy |
| DB 연결 | 호스트에서 공개 포트, 컨테이너에서 서비스명·내부 포트 | 승인된 내부 접속 경로 |
| 비밀값 | 개인 개발용 Secret | 별도의 배포용 Secret |
| 변경 기준 | 영향 범위 검증 | 배포 대상·승인·호환성·복구 가능성 확인 |

기존 배포 설계에 대한 개념적 요청 경로:

~~~text
Local: Android (Expo) -> PC LAN IP:8000 -> Host FastAPI
                                           -> 127.0.0.1:3309 -> MariaDB :3306
       Android -> Metro (일반적으로 8081)
       Docker FastAPI를 선택하면 -> db:3306

AWS:   Android (APK) -> HTTPS 도메인:443 -> Reverse Proxy
                                           -> 내부 FastAPI:8000 -> 내부 MariaDB:3306
~~~

AWS 그림은 기존 배포 방향(Caddy 기반 HTTPS 등)을 설명하기 위한 논리 구조다. 현재 Lightsail의 실행 이미지, 실제 도메인, Proxy 배치, DB 버전·Revision·권한·방화벽·저장소 및 전체 API 건강 상태는 이번 문서 작성에서 SSH/콘솔로 재검증하지 않았다. 실제 운영 작업 전에 승인된 배포 자료와 실측값을 확인한다. 로컬 Compose를 운영 Compose로 간주하지 않는다.

Lightsail 방화벽(IPv4/IPv6 각각), 호스트 방화벽 및 Docker 포트 공개는 다른 제어 계층이다. HTTPS 443과 필요한 HTTP 80만 공개하는 방향을 기본으로 하며, SSH 22는 관리자 접근 범위로 제한한다. DB 3306 및 Backend 8000의 직접 인터넷 공개와 Metro 8081 공개는 피한다. 실제 Proxy 연결 방식은 배포 설정을 확인한다.

## 3. 로컬 개발 실행 및 설정

### 3.1 확인된 개인 개발 환경 예시

다음은 2026-11-19 복구 기준의 한 개발 PC에서 확인된 값이다. **팀 전체의 포트나 가상환경 경로를 강제하는 규칙이 아니다.**

| 항목 | 확인값 / 용도 |
|---|---|
| 일반 DB | trend-leader-db, 127.0.0.1:3309 -> 3306, MariaDB 12.3.2 |
| 일반 DB 저장소 | trend-leader_trend_leader_db (named volume) |
| API | Windows Uvicorn :8000 또는 Docker Backend :8000 |
| 테스트 DB | 3307 (docker-compose.test.yml, tmpfs) |
| Check DB | 3308 (docker-compose.check.yml, tmpfs); 기존 목적 확인 후 사용 |
| 기타 특수 검증 환경 | Demo Review, B2, Reference, 3311 등 기존 리소스; 일상 개발 대상 아님 |

현재 dev의 기본 Compose는 DB 호스트 포트를 `DB_EXTERNAL_PORT`로 주입하고 컨테이너 내부 포트는 3306을 사용한다. `MARIADB_IMAGE_TAG`는 미지정 시 latest이며, 개인 환경에서 12.3.2로 고정한 것은 팀 공통 설정 변경을 의미하지 않는다. 검증된 이미지 버전/ID를 확인하고 임의 업그레이드를 피한다.

### 3.2 환경변수 책임과 연결 경로

| 파일 또는 설정 | 역할 |
|---|---|
| .env.compose | Compose 변수 치환: DB 이미지, 외부 포트, 계정 등 |
| backend/.env | 런타임 FastAPI Settings |
| .env.test.compose / backend/.env.test | 테스트 DB 및 별도 테스트 승인 설정 |
| MIGRATION_DB_* | Alembic 전용 연결; 런타임 설정과 독립 |
| frontend/.env | Expo 개발 API 주소 관련 값 |
| 배포 빌드용 환경변수 | 명시적인 HTTPS API Base URL, 서버 측 Secret은 포함 금지 |

개인 Windows 예시(기존 파일에서 해당 항목만 확인, 나머지 값은 유지):

~~~dotenv
# .env.compose
MARIADB_IMAGE_TAG=12.3.2
DB_EXTERNAL_PORT=3309
BACKEND_EXTERNAL_PORT=8000
~~~

~~~dotenv
# backend/.env (호스트 Uvicorn용)
DB_HOST=127.0.0.1
DB_PORT=3309
DB_NAME=trend_leader
DATABASE_URL=
~~~

~~~dotenv
# frontend/.env (LAN 개발)
EXPO_PUBLIC_API_PORT=8000
EXPO_PUBLIC_API_PREFIX=/api
~~~

- Compose Backend는 `DB_HOST=db`, `DB_PORT=3306`, API 계정값을 주입한다. 일반 DB 초기 관리자, API Runtime, Migration 전용 계정을 혼동하지 않는다. 개인 개발 환경에서 기존 trend_user 계정으로 연결에 성공한 사실은 운영 Runtime 권한 정책 변경을 승인한 것이 아니다.
- Runtime은 비어 있지 않은 `DATABASE_URL`을 개별 DB 설정보다 우선한다. 프로세스 환경변수도 확인한다. 환경변수 파일만 수정하면 기존 컨테이너의 실행 값이 자동으로 바뀌는 것은 아니다.
- 현재 Frontend 코드는 개발 모드에서 Expo hostUri의 hostname과 API 포트·prefix를 우선하고, hostUri를 얻지 못하면 명시적인 Base URL을 사용한다. 배포 모드에서는 `EXPO_PUBLIC_API_BASE_URL`이 필요하다(예: `https://<approved-domain>/api`). 도메인은 실제 승인된 배포 주소를 사용한다.
- `EXPO_PUBLIC_*` 값은 앱 번들에 포함된다. 배포 주소 변경 시 해당 값이 반영된 번들/빌드가 필요하다. DB·JWT·크롤링·AI API Secret은 Backend에서만 관리한다.

### 3.3 이미 구성된 로컬 DB로 일상 개발하기

저장소 루트의 PowerShell에서 현재 브랜치와 환경을 확인한다.

~~~powershell
git status -sb
git log -1 --oneline
docker compose --env-file .env.compose config --quiet
docker ps -a
docker port trend-leader-db
~~~

기존 DB가 중지 상태라면 `docker start trend-leader-db`로 시작한다. 호스트 Uvicorn을 사용할 경우 이미 실행 중인 `trend-leader-api`만 중지하고 DB는 유지한다. 같은 호스트의 8000 포트를 두 Backend가 동시에 점유하지 않도록 한다.

아래는 이번 복구에서 사용한 가상환경 경로 예시다. 다른 PC에서는 실제 승인된 Python 경로로 대체한다.

~~~powershell
& .\backend\venv\Scripts\python.exe -B -m uvicorn `
  app.main:app --app-dir backend --host 0.0.0.0 --port 8000
~~~

Swagger는 `http://localhost:8000/docs`로 확인한다. 별도 터미널에서 `frontend/`로 이동하여 현재 기기에 설치된 앱에 맞는 Expo 실행 방식을 사용한다(Expo Go 호환 여부 또는 Development Client 확인). 예를 들어 설치된 Development Client를 사용할 때:

~~~powershell
npm run start:dev-client
~~~

호스트·실기기 LAN 연결과 실제 API 주소를 확인하고 환경변수 변경 후 Metro를 재시작한다. Uvicorn의 0.0.0.0 바인딩은 실기기 접근을 위한 것으로 신뢰하는 개발 네트워크와 Windows 방화벽 범위에서만 사용한다.

Docker Backend 방식은 기존 온보딩 가이드의 해당 실행 절차를 참고하되 최신 계정·Migration 계약을 먼저 확인한다. 기존 DB가 정상이라면 불필요한 재생성·재빌드·초기화를 하지 않는다.

## 4. 코드와 DB Schema 동기화

Git 코드, Python 의존성, Docker 이미지, 실행 중인 컨테이너, 환경변수, DB Revision, APK는 각각 독립 상태다. Git pull 또는 dev 병합만으로 DB나 배포 프로세스가 갱신되지 않는다.

### 4.1 연결 및 Revision의 최소 점검

Backend 디렉터리에서 현재 선택한 가상환경을 사용한다. 아래 조회는 런타임 DB 접속과 실제 Revision 확인을 목적으로 한다.

~~~powershell
python -c "import sys; print(sys.executable)"
python -m alembic heads
python -c "from app.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT VERSION(), DATABASE(), CURRENT_USER()')).one()); print(c.execute(text('SELECT version_num FROM alembic_version')).all()); c.close()"
~~~

대상 DB와 계정을 먼저 확인하며 새 DB에 version 테이블이 없거나 조회가 실패하면 상태부터 조사한다. 필요한 경우 실제 테이블·컬럼과 예상 구조까지 비교한다. Revision 일치만으로 Schema 무결성이나 전체 기능 성공을 보장하지 않는다.

### 4.2 Migration의 현재 연결 계약

`backend/alembic/env.py`는 `MigrationDbSettings(_env_file=None)`를 생성한다. 필수 입력:

- MIGRATION_DB_HOST / MIGRATION_DB_PORT / MIGRATION_DB_NAME / MIGRATION_DB_USER
- MIGRATION_DB_PASSWORD_FILE (보호된 UTF-8 비밀번호 파일의 절대경로)
- MIGRATION_DB_CONNECTION_TIMEOUT (선택)

`backend/.env`, 일반 DB_* 및 DATABASE_URL은 이 계약의 대체 입력이 아니다. 별도 계정과 환경을 사용하며 비밀번호를 명령행·채팅·커밋에 포함하지 않는다.

아래는 **대상 및 변경 범위가 별도 승인된 로컬 개발 DB에만** 적용하는 명령의 형태다. 바로 실행할 일상 기동 명령이 아니다. 실제 승인 계정·Secret·Python 경로를 먼저 준비하고, 검토한 목표 Revision을 고정한다.

~~~powershell
$env:MIGRATION_DB_HOST = '127.0.0.1'
$env:MIGRATION_DB_PORT = '3309'
$env:MIGRATION_DB_NAME = 'trend_leader'
$env:MIGRATION_DB_USER = '<approved-local-migration-user>'
$env:MIGRATION_DB_PASSWORD_FILE = '<protected-absolute-path>'

& .\backend\venv\Scripts\python.exe -B -m alembic `
  -c .\backend\alembic.ini upgrade b7f2c81d9e04
~~~

이 예시의 Revision은 이번 복구 대상이지 미래의 고정 Head가 아니다. 별도 PowerShell 세션에서 실행하고 Runtime 서버를 해당 Migration 환경으로 실행하지 않는다. 계정의 실제 권한 및 대상 신원 검증 없이 진행하지 않는다.

운영 Guard는 확인 기준 dev에서 `apply`를 MODE_NOT_ENABLED로 거부한다. B-2 preflight 관찰 성공은 운영 APPLY 승인과 다르다. 로컬 직접 Alembic 실행을 AWS 운영 Guard 우회 절차로 사용하지 않는다. 기존 `verify_account_migration.py --apply` 차단도 유지한다.

### 4.3 변경 위험에 맞는 최소 절차

1. 대상 DB·소스 Revision·목표 Revision 및 데이터 보존 필요성을 확인한다.
2. 기존 승인된 백업/복구 증거를 재사용할 수 있는지 확인한다. 데이터 보존이 필요한 DDL/DML에는 적절한 백업·복구 검증, 사전 데이터 검사 및 쓰기 중단을 확보한다.
3. 현재 위험에 필요한 검증만 기존 테스트 환경에서 수행한다. 데이터가 있는 기존 DB를 덮어쓰거나 승인된 검증 환경을 초기화하지 않는다.
4. 적용 승인 이후 전용 계정으로 실행하고, Revision·Schema·의도된 변경 외 데이터 보존 및 영향 기능을 확인한다.
5. MariaDB DDL 중 실패하면 부분 적용 가능성을 고려해 상태를 보존하고 조사한다. 자동 재시도, 임의 downgrade/stamp, 수동 CREATE TABLE, Volume 삭제 등으로 오류를 숨기지 않는다.

### 4.4 이번 복구 사례 (2026-11-19, 사용자/Codex 실행 보고)

- Error 1045를 DB 연결 점검으로 해결한 뒤, 로그인에서 Error 1146 (auth_sessions 부재)가 발생했다.
- DB는 a4d7c9e21f3b(14개 테이블), Backend는 b7f2c81d9e04를 요구했다.
- 보호된 논리 백업 및 실제 복원, 기존 3308 서버의 별도 복구 DB에서 Migration·전용 권한을 검증한 후 일반 3309에 별도 승인으로 적용했다.
- 최종 b7f2c81d9e04, 17개 테이블, 사용자 4명 보존, 프로필 4개 Backfill, 변경 대상 외 기존 데이터 보존이 보고되었다. 사용자는 이후 실기기 신규 기능 검증을 수행했다. 전체 회귀 테스트 및 개별 인증 경로 모두의 PASS를 의미하지 않는다.
- 3308 복구 DB 및 3311 임시 환경은 정리 후보이며 삭제 완료가 확인되지 않았다. 실제 백업·Evidence·Secret은 보호된 Git 외부 위치에 유지한다. 원본 데이터/Secret을 문서 저장소에 커밋하지 않는다.

## 5. AWS Lightsail 배포에서 달라지는 판단

dev 병합과 AWS 배포는 서로 다른 승인 작업이다. 실제 배포 대상에서 다음을 확인한다.

1. 승인된 소스 커밋 및 릴리스 이미지 태그/ID(digest), Python 의존성.
2. Docker 프로젝트·실행 컨테이너·DB 신원·버전·Revision·런타임 계정.
3. DB 변경 필요 여부와 앱/DB 호환성, 영속 저장소와 복구 가능성. 필요한 운영 Migration 승인이 없으면 적용하지 않는다.
4. 실제 HTTPS 도달성, Proxy→Backend 연결, Backend 준비 상태와 로그, 해당 APK의 Base URL.
5. 변경한 API 및 실기기 핵심 사용자 흐름. 일부 PASS를 전체 배포 또는 게시 승인으로 확대 해석하지 않는다.

이미지는 특정 시점의 실행 산출물이며, 소스 bind mount가 없는 경우 소스 변경이나 재시작만으로 새 코드가 반영되지 않는다. 이미지 전환 및 Migration 순서는 호환성과 승인된 배포 계획에 따른다. DB 데이터와 사용자 프로필 이미지 저장소는 컨테이너 교체와 분리하여 보존한다. 운영환경과 로컬 데이터/Secret은 독립적이며 운영 데이터 전체를 로컬에 복사할 필요는 없다.

## 6. 오류 진단 순서

| 현상 | 첫 점검 |
|---|---|
| API 연결 실패 | 실제 주소, 포트, 실행 프로세스, LAN/방화벽 |
| 502 / TLS 오류 | Reverse Proxy 연결 / DNS·인증서 |
| 404 / 401 / 403 / 503 | 경로·인증·권한·Maintenance 및 실제 응답 |
| DB 1045 | DB 연결 대상, 계정, 인증 설정 |
| DB 1146 / 1054 | 실제 테이블 / 컬럼 및 Migration Revision |
| 로컬 정상, AWS 실패 | 배포 이미지, 런타임 설정, DB Revision, 권한·네트워크 |
| API 정상, APK 실패 | 번들 API 주소, 앱 버전, 인증 상태 |

Lightsail에서 승인된 읽기 전용 조사 시 예: `docker ps -a`, `docker compose ls`, `docker system df`, `free -h`, `df -h`. 실제 배포 파일·경로를 확인한 뒤 관련 로그만 읽는다. 전체 Compose config, 전체 환경변수 및 토큰·비밀번호 포함 로그를 채팅에 공유하지 않는다.

## 7. Delivery Mode 및 임시 리소스 관리 (현재 마무리 단계)

- 핵심 기능을 막는 오류, 회귀, 실제 보안과 데이터 무결성 문제를 해결한다. 미래 확장용 인프라 고도화·자동화·리팩터링은 Follow-up으로 남긴다.
- 일상 개발 DB와 테스트 DB를 중심으로 기존 구성을 재사용한다. 기존 리소스로 해결 불가능하다는 구체적인 이유와 사용자 승인 없이 신규 Container/Volume/Network/포트 또는 서버를 추가하지 않는다.
- 기존 테스트 DB의 데이터 보존 여부와 동시 사용 여부를 먼저 확인한다. 3307/3308은 tmpfs이므로 중지·재시작 전 필요한 자료를 보존한다.
- 임시 리소스 생성 시 목적·대상·Evidence 위치·종료/정리 조건을 기록한다. 검증 자료와 필요한 이미지·Secret을 보존한 뒤 승인된 리소스만 정리한다. 미사용 상태 자체가 삭제 근거는 아니다. 전역 prune, 무단 down -v, 다른 프로젝트 변경을 금지한다.
- 검증 수준은 유지하되 이미 확보한 동일 조건의 증거를 반복 수집하지 않는다. 문제가 원래 목표와 무관하게 확대되면 중단하고 최소 대안을 보고한다.

남은 크롤링 API 및 트렌드 수집 파이프라인은 기존 Backend와 MariaDB의 활용을 우선한다. 수집 → 정규화/검증 → 중복 제거/분류 → 저장 → 조회의 논리적 책임 분리는 신규 서버나 메시지 큐 도입을 뜻하지 않는다. API Key는 서버 측에서 관리하고 외부 API 접근 권한·호출 제한·실행 주체의 egress·반복 실행 시 중복 방지를 검토한다. 기존 [트렌드 게시 운영 정책](../operations/trend-publication/README.md)의 HOLD 및 Writer/게시 승인 경계는 유지한다.

## 8. 최소 체크리스트 및 Codex 활용

| 시점 | 확인 |
|---|---|
| 로컬 개발 전 | 브랜치·HEAD, 실제 Python, API/DB 주소, DB Revision |
| 병합 전 | 변경 범위·영향 테스트·핵심 실기기 흐름 |
| AWS 배포 전후 | 이미지/대상 DB·Schema·권한·승인, HTTPS 및 실제 APK |
| 오류 발생 | 최초 실패 계층과 실제 상태를 확인한 뒤 해당 범위만 조치 |

Codex 또는 다른 AI에 환경 관련 작업을 요청할 때 다음 내용을 함께 전달한다.

~~~text
AGENTS.md와 docs/onboarding/Trend_Leader_Local_and_Lightsail_Environment_Guide.md
중 현재 요청에 해당하는 절을 참고하세요.
실제 체크아웃된 브랜치와 실행 환경을 먼저 확인하고 로컬/테스트/AWS를 구분하세요.
Delivery Mode를 적용하고 기존 환경을 재사용하세요.
새 인프라, DB의 쓰기/삭제, 운영 배포 및 Git 변경은 별도 승인 없이 하지 마세요.
현재 기능 완료를 직접 막지 않는 개선은 Follow-up으로 기록하세요.
~~~

## 9. 참고 자료 및 검증 범위

저장소 확인 파일:
[Compose](../../docker-compose.yml) · [Test Compose](../../docker-compose.test.yml) · [Check Compose](../../docker-compose.check.yml) · [Dockerfile](../../backend/Dockerfile) · [Runtime Settings](../../backend/app/core/config.py) · [Alembic env](../../backend/alembic/env.py) · [MigrationDbSettings](../../backend/app/core/migration_db_config.py) · [Migration Guard](../../backend/scripts/migration_guard.py) · [계정 기능 Revision](../../backend/alembic/versions/b7f2c81d9e04_add_account_sessions_and_profiles.py) · [Frontend API 설정](../../frontend/src/app/config/apiConfig.ts) · [EAS 설정](../../frontend/eas.json).

공식 문서: [Docker Compose Networking](https://docs.docker.com/compose/how-tos/networking/) · [Docker Volumes](https://docs.docker.com/engine/storage/volumes/) · [AWS Lightsail Firewall](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html) · [Expo Environment Variables](https://docs.expo.dev/guides/environment-variables/).

작성 시점에는 저장소 코드 및 사용자 제공 실행 결과를 검토했으며, 이 문서 작성 자체로 AWS 재배포·실서버 검사·DB 변경·추가 기능 테스트를 수행하지 않았다.
