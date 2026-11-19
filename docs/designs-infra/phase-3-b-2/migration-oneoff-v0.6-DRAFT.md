# Trend Leader — Phase 3-B-2 M-A 일회성 Migration 서비스 Design Review v0.6 (DRAFT)

> **2026-11-12 이후 채팅 결정 반영 안내 (본 문서에 우선 적용):**
> - 사용자는 **M-A1(운영 Compose의 선택적 일회성 Migration Profile) + Alembic의 DB 전용 Settings 분리**를 구현 방향으로 선택했다. 실행 차단 메커니즘, DB 계정·Secret, 권한 SQL, 이미지 Digest, 테스트는 **NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**이다.
> - 위 선택은 P4/G4/G5/G6 기존 HOLD 및 데이터 게시 승인 정책을 변경하지 않는다.
> - 원문에 `M-A NOT SELECTED`, `M-A/M-B 미선택` 또는 `GitHub 미변경`과 같은 표현이 있으면 **과거 초안 작성 시점의 기록**이다. 현재 선택 상태와 원격 반영 사실은 이 안내와 README를 우선한다.
> - `dev` HEAD SHA 표기는 해당 DRAFT 작성 당시 근거 버전이며, 최신 원격 상태의 증명이 아니다.

> 작성: 2026-11-12 KST  
> 근거 코드: `Trend-Leader-capstoneProject/feature` `dev` HEAD `b133b494f8258eea603243f8f07191a33290084a` (이번 검토 시 재확인)  
> 상태: **REVIEW DRAFT · M-A1 DIRECTION SELECTED / DETAILS NOT FROZEN · NOT IMPLEMENTED · NOT TESTED**  
> 보존: 기존 v0.5 운영 Compose 리뷰 / Account Provisioning SQL·Preflight v0.1 / 관련 앞선 DRAFT는 수정하지 않음. GitHub·AWS·실제 DB 불변.

## 1. 목적과 결정 경계

- **목적:** 승인된 Alembic 작업만 운영 DB에 실행하고, 상주 API에는 Migration 계정·DDL 권한·Secret을 절대 주지 않는다.
- **기존 사용자 결정:** 개발용과 독립된 운영 Compose, DB Bootstrap / Migration / Account Provisioning 책임 분리, Bootstrap은 운영 DB 컨테이너 내부에서 운영자가 수동으로 수행, `utf8mb4_unicode_ci` 유지, API Runtime 최소 권한, G4/G5/G6 운영 HOLD 유지.
- **이번에 아직 결정하지 않은 것:** M-A 서비스 구조 최종 선택, 안전한 기본 실행 방식, Migration 자격 증명·Host·GRANT, 운영 Secret 공급, 이미지 Digest, 배포 전 백업과 승인 증거 방식.
- 본 문서는 검토·테스트 전략. 운영 배포 명령서나 실제 실행 가능한 Compose 파일이 아니다.

## 2. 실코드에서 확인한 위험

| ID | 확인한 사실 | 영향 |
| --- | --- | --- |
| E-01 | `backend/Dockerfile` 기본 CMD는 Uvicorn. Python 3.12, Alembic·ORM 소스/패키지는 이미지 안에 포함됨 | 같은 애플리케이션 이미지에서 Migration 실행은 가능하나 `migration` 서비스에 명시적인 안전 기본 명령/진입점이 없으면 `up`에서 Uvicorn 실행 위험 |
| E-02 | `backend/alembic/env.py`는 `get_settings()`를 사용 | Migration용으로 독립 DB 자격 증명을 제공해야 함 |
| **E-03 / P0** | `backend/app/core/config.py`: `jwt_secret_key: str = Field(..., min_length=32)` | 지금 구조에서는 **Migration이 JWT를 사용하지 않아도** Settings 생성 시 JWT Secret이 필요. 운영 실제 JWT Secret을 공유해서는 안 됨; DB-only 설정 분리 또는 안전한 일회성 비운영 값 사용을 실증해야 함 |
| **E-04 / P0** | 같은 Settings에서 `DATABASE_URL`이 `DB_*`보다 우선 | 마이그레이션이 잘못된 DB나 계정으로 연결될 위험. 사전 검증 대상은 effective URL의 호스트·DB·계정이어야 함 |
| E-05 | `backend/.dockerignore`는 `.env`, `.env.*` 제외 | 현 이미지 빌드 컨텍스트에서 이 파일들이 복사되지 않는 것은 장점. 다만 실행 시 `env_file`/CLI/볼륨의 혼입은 별도 통제 |
| E-06 | `backend/alembic.ini`의 `sqlalchemy.url`은 unused placeholder, 실제 값은 env.py Settings | ini URL만 검사해 DB 연결 대상을 확인했다고 판단 불가 |
| E-07 | Alembic 3개 리비전이 테이블·인덱스·제약을 생성/변경 | DDL과 `alembic_version` 쓰기 권한이 필요. 실제 MariaDB 후보에서 최소 GRANT 검증 전까지 권한 확정 금지 |
| E-08 | `/api/health/ready`는 `SELECT 1`만 사용 | Migration·GRANT·업무 기능 완료 Gate가 아님 |

## 3. M-A 프로필 서비스와 대안 비교

| 후보 | 구성 | 운영상 장점 | 위험/추가 비용 |
| --- | --- | --- | --- |
| **M-A1** | `compose.prod.yaml`에 `migration` 서비스 + `profiles: [maintenance]`; `docker compose run`으로 명시적 호출 | 네트워크·이미지·Secret 책임 한 파일에서 점검 가능 | `--profile maintenance up`, `COMPOSE_PROFILES`로도 대상에 포함될 수 있음. Profile은 권한·승인·실행 차단 보안 경계가 아님 |
| **M-A2** | 기본 운영 Compose 외에 운영 전용 별도 maintenance Compose 파일/프로젝트 절차 | 기본 `up`에서 Migration 서비스 정의 자체를 분리하기 쉬움 | Compose 파일 병합/프로젝트·네트워크·Secret 경로 운영 실수 가능, 설명·검증 작업 증가 |
| **M-B (비교 기준)** | 관리자가 임시 컨테이너에 직접 CLI·환경을 지정 | 상주 설정 최소 | 자격 증명/이미지/네트워크 재현성 취약 |

**잠정 권고:** 전시 MVP 일정에서는 **M-A1 + 기본 실행 거부(Fail-safe command 또는 guard entrypoint) + 명시적 운영자 runbook + Preflight**를 우선 상세 설계. 단, `profiles`만으로 실수·악의적 실행을 막을 수 있다고 주장하지 않는다. 기본 실행 거부 로직의 실효성은 구현·시험 전 미확정. 호스트 Docker 관리 권한자는 명령·entrypoint를 교체할 수 있으므로 절대적인 보안 장벽이 아니다.

## 4. Migration 서비스의 최소 계약

1. **별도 Service:** `migration`(가칭)은 평시 상주하지 않는 `maintenance` profile에 배치. `restart: "no"`. `backend`/`proxy`는 이 서비스에 `depends_on` 걸지 않음.
2. **동일 코드 아티팩트:** Backend와 동일하게 검증된 이미지 ID/버전에서 Alembic 실행하되, 별도 컨테이너와 프로세스·환경·DB 계정을 사용. `EXPOSE 8000` 이미지 메타데이터는 포트 게시가 아님; 서비스에 `ports` 금지.
3. **DB 접속만:** `db-net`에만 연결(필요 시 Docker DNS/내부 서비스 확인), 운영 DB 데이터를 담은 named volume 마운트 금지, 외부 네트워크·root Secret·Runtime JWT Secret·Writer Secret 미공유.
4. **전용 환경:** `DB_HOST=db`, `DB_PORT=3306`, 승인된 `DB_NAME`, Migration DB 사용자와 비밀번호. `DATABASE_URL`의 effective priority 검증. Runtime `env_file`·운영 JWT Secret 재사용 금지.
5. **JWT Settings 결합 해결:** (권고) Alembic에서 DB-only Settings/연결 설정으로 분리하여 운영 JWT Secret이 필요 없도록 할지 먼저 검토. Deadline 우선 대안은 Migration 전용으로 매 실행 생성한 비운영 임의값을 JWT 필수 검증에만 전달하되, 실제 Production JWT Secret과 혼동·재사용하지 않으며 해당 방법의 범위/테스트를 기록. 설정 변경은 사용자 동결·회귀 검증 후.
6. **명시 실행:** 기본 `up` 또는 프로필을 잘못 활성화한 `up`에서는 Migration이 실행되지 않는 실패형 기본 명령/가드 필요. `docker compose run`으로 별도 명시된 승인 명령만 실행되도록 운영 절차 정의. 서비스 기본 명령을 단순 `alembic upgrade head`로 두지 않음.
7. **DB 준비 전제:** root Bootstrap, Migration 계정/권한 사전 준비, DB 식별, schema revision 및 백업 복원 확인 후 운영자 승인. `depends_on: service_healthy`로 이를 대체하지 않음.
8. **단회·중복 실행:** 동시 Migration 실행을 금지하고, 실행 시작/완료·DB revision을 사후에 기록. `--rm`로 컨테이너가 없어지므로 로그·증거는 별도 비밀정보 없는 영속 기록에 보관. Alembic revision만으로 승인·시도 이력을 대체하지 않음.
9. **비정상 종료:** MariaDB DDL은 일부 암묵 커밋/비트랜잭션 가능. Alembic `transaction_per_migration=True`만으로 전체 업그레이드 원자성/롤백 보장 불가. 실패 시 즉시 정지, 현재 Schema·revision·적용 객체 조사, 자동 재시도 금지, 복구·재승인 판단.
10. **상주 Runtime 보호:** Runtime 컨테이너·환경에는 Migration 계정/DDL 권한·Secret 없음. `docker compose exec backend alembic upgrade head`는 허용 실행 계약이 아님.
11. **초기 배포 공개 순서:** DB만 시작→Bootstrap→Migration 승인/실행→Runtime 계정 Provisioning→Preflight→Backend 내부 검증→Proxy 외부 공개. 이미 승인된 운영 재시작과 신규 설치/Schema 변경을 구분함.

## 5. 운영 명령 개념(구현 명령 확정 아님)

- `docker compose up`: profile 서비스는 기본 제외되지만 다른 경로로 활성화할 수 있으므로 단독 방어가 아니다.
- `docker compose run --rm SERVICE COMMAND`: 지정 서비스 설정으로 신규 단발 컨테이너 실행, 별도 명령으로 서비스 `command`를 덮어쓸 수 있다. `--rm`은 컨테이너 정리이지 Migration 변경 취소가 아니다.
- `--no-deps`: 의존 서비스를 자동 시작하지 않으려는 경우 사용 가능. 이 경우 DB 서비스의 기동/건강 상태를 운영자가 사전 확인해야 한다.
- 프로필 이름과 승인 플래그는 권한·인증 자체가 아니다. 일반 문자열/환경변수만으로 Preflight가 확정되었다고 간주하지 않음.
- 구현 전 `docker compose config -q`를 사용하여 설정 유효성 검사. 출력이 있는 설정 덤프 및 터미널 비밀번호 기록 주의.

## 6. Preflight 설계(쓰기 없는 단계 → 실제 적용 단계 엄격 구분)

| Gate | 확인 내용 | 실패 시 |
| --- | --- | --- |
| MIG-01 | 운영 프로젝트 이름, Compose 파일, Backend와 Migration 이미지 해시 일치 | 중단 |
| MIG-02 | `db` 외부 포트 없음, `migration` 네트워크가 `db-net`만, ports·DB volume 없음 | 중단 |
| MIG-03 | root/Runtime/Writer Secret은 migration에 없고, migration Secret은 backend에 없음 | 중단 |
| MIG-04 | `DATABASE_URL` 우선순위와 DB host/port/name/current_user 검증 | 중단 |
| MIG-05 | DB 인스턴스/Collation `utf8mb4_unicode_ci` 및 기대 schema revision, 이력 확인 | 중단 |
| MIG-06 | 현재 계정의 유효 GRANT는 검증된 Migration 필요 권한과 일치 | 중단 |
| MIG-07 | 백업과 복원 증거, 승인된 변경 내용, 운영자 확인, 중복 실행 여부 | 중단 |
| MIG-08 | 기본 `up`·`--profile maintenance up`에서 실제 Alembic Upgrade 0회 | 중단 |
| MIG-09 | 명시 승인된 단회 실행 성공 시 schema revision 및 객체 확인; 별도 실행 증거 보존 | 실패 시 운영 공개 중단 |
| MIG-10 | DDL 중간 실패/강제 종료/재실행 시 자동 반복하지 않으며 손상·부분 적용 상태를 탐지 | 공개 중단 |
| MIG-11 | 이전 Runtime 최소 GRANT 계정으로 Alembic 시도 시 권한 거부 | 중단 |
| MIG-12 | 최초 공개와 재배포, 서버 재시작에서 Migration이 자동 실행되지 않음 | 중단 |

위 검증은 이번 문서 작성 시 **전부 NOT TESTED**. 파괴적 시험은 별도 격리 MariaDB 인스턴스·볼륨에서만 수행.

## 7. 검토 판정 / 다음 의사결정

- **M-A1은 구현 가능성이 높으나, 기본 profile만으로 승인 통제 불가.** 위험한 기본 명령과 설정 결합을 제거해야 함.
- **최우선 보완:** `Settings`가 JWT Secret을 Migration에서도 필수로 읽는 의존성, DB 접속 우선순위(`DATABASE_URL`), 기본 CMD(uvicorn) 처리, 실제 migration GRANT 시험, 부분 DDL 실패 시 대응.
- **다음 선택:** M-A1/M-A2 중 운영 구조 결정 및 DB-only Settings 분리(최소 리팩터링 vs 임시 비운영 값) 방법 결정 후 서비스 계약/실행 검증 전략 동결.
- 실제 SQL/Compose/DB/GitHub/AWS 변경 없음.

## 근거(코드 및 공식 문서)

프로젝트: `backend/Dockerfile`, `backend/.dockerignore`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/app/core/config.py`, `backend/app/api/routes/health.py`, `backend/alembic/versions/{2f29fa23597c,7e9d740c5df1,a4d7c9e21f3b}_*.py`, `Trend_Leader_Phase_3-B-2_Production_Compose_Review_v0.5_DRAFT.md`, `Trend_Leader_Account_Provisioning_SQL_Preflight_v0.1_DRAFT.md`.

Docker Compose profiles: https://docs.docker.com/compose/how-tos/profiles/  
Docker Compose run: https://docs.docker.com/reference/cli/docker/compose/run/  
Docker startup order: https://docs.docker.com/compose/how-tos/startup-order/  
Docker secrets: https://docs.docker.com/compose/how-tos/use-secrets/  
Docker environment precedence: https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/  
Alembic tutorial/runtime: https://alembic.sqlalchemy.org/en/latest/tutorial.html  
MariaDB implicit commit reference: https://mariadb.com/docs/server/reference/sql-statements/transactions/sql-statements-that-cause-an-implicit-commit