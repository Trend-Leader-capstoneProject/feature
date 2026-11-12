# Trend Leader — API Runtime DB 권한 심화 리뷰 v0.3 (DRAFT)

> **2026-11-12 이후 채팅 결정 반영 안내 (본 문서에 우선 적용):**
> - 사용자는 **M-A1(운영 Compose의 선택적 일회성 Migration Profile) + Alembic의 DB 전용 Settings 분리**를 구현 방향으로 선택했다. 실행 차단 메커니즘, DB 계정·Secret, 권한 SQL, 이미지 Digest, 테스트는 **NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**이다.
> - 위 선택은 P4/G4/G5/G6 기존 HOLD 및 데이터 게시 승인 정책을 변경하지 않는다.
> - 원문에 `M-A NOT SELECTED`, `M-A/M-B 미선택` 또는 `GitHub 미변경`과 같은 표현이 있으면 **과거 초안 작성 시점의 기록**이다. 현재 선택 상태와 원격 반영 사실은 이 안내와 README를 우선한다.
> - `dev` HEAD SHA 표기는 해당 DRAFT 작성 당시 근거 버전이며, 최신 원격 상태의 증명이 아니다.

> 작성일: 2026-11-12 (KST)  
> 저장소 기준: `Trend-Leader-capstoneProject/feature` / `dev` / `b133b494f8258eea603243f8f07191a33290084a` (2026-11-12 확인)  
> 계승 문서: `Trend_Leader_API_Runtime_DB_Privilege_Matrix_v0.1_DRAFT.md`, `Trend_Leader_API_Runtime_DB_Privilege_Review_v0.2_DRAFT.md`  
> 상태: **DRAFT / NOT FROZEN**. 사용자 선택: **독립 운영 Compose + B안(Bootstrap / Migration / Account Provisioning 분리)**. 실제 SQL 생성·실행, 권한 부여, Docker/AWS 배포, 원격 GitHub 변경 **미실행**.  
> 변경 원칙: **v0.1 및 v0.2 원본은 수정하지 않고 보존**. v0.2의 P0-01~07 및 P1 항목을 대체하지 않고 이번 보완을 누적한다.

## 0. 이번 v0.3에서 반영한 보완 7개

| ID | 보완 사항 | 반영 위치 | 판정 |
|---|---|---|---|
| R-01 | 사용자 소유권 검증이 실제로 어디에서 성립하는지 명시 (`/me`, `CurrentUser`, 전달 `user_id`) | §2, §4 | 문서화 |
| R-02 | G4/G5/G6 **운영 정책/HOLD**와 **구현·실제 검증** 구분 | §3 | 문서화 |
| R-03 | G6 HOLD로 인해 금지되는 **트렌드 게시**와 독립 배포·Migration·Category Seed 구분 | §3.2 | 문서화 |
| R-04 | Runtime 탈취에 따른 `users`/관심사 INSERT 우회 위험 추가 | §4 | 문서화 |
| R-05 | 무인증/A·B 사용자 정방향 테스트와 소유권 회귀 테스트 분리 | §7 | 미실행 |
| R-06 | `SELECT ... FOR UPDATE`와 최소 GRANT의 실제 버전·트랜잭션 동작 검증 | §5, §7 | 미실행 |
| R-07 | 고권한 DB URL/계정 불일치 시 **공개 시작 이전** 차단 및 증거 검증 | §6, §7 | 미구현·미실행 |

> **판정 표현 기준:** ‘설계에서 요구’와 ‘코드에 구현’과 ‘실제 DB에서 시험 통과’를 각각 구별한다. 이 문서의 매트릭스는 GRANT 적용 결과가 아니다.

## 1. 범위, 불변조건, 권한 표의 근거

- **대상:** 일반 HTTP FastAPI Runtime (`auth`, `category`, `interest`, `trend`, `health` Router). API 기능과 DB 접근 연결은 기준 커밋의 Router → Dependency → Service → Repository → ORM 경로에서 검토했다.
- **비대상:** 관리자·Migration·Category/Demo Seed·P4 Writer·Backup 계정의 최종 GRANT. 별도 설계가 필요하다.
- **불변조건:** 일반 Runtime은 트렌드 게시 테이블의 DML을 할 수 없고, 일반 회원 기능에 필요한 최소한의 DML만 가진다. SQL 계정 권한과 엔드유저 인가는 분리한다.
- **추가 유의:** `Trend.status=ACTIVE`는 G4 승인이나 G6 운영 승인을 나타내지 않는다. 실제 운영 콘텐츠 게시 경로는 별도 Gate 및 Writer 통제 대상이다.

### 1.1 일반 Runtime의 테이블 권한 후보 (v0.1/v0.2 유지)

`Y` = 현재 공개 API에서 요구되는 권한 후보, `—` = 부여하지 않음. **실제 GRANT 성공을 뜻하지 않음.**

| 테이블 | SELECT | INSERT | UPDATE | DELETE | 근거 |
|---|:---:|:---:|:---:|:---:|---|
| `users` | Y | Y | — | — | 회원가입 중복 조회·INSERT, 로그인·세션·CurrentUser |
| `user_interest_categories` | Y | Y | — | Y | 관심사 확인·조회·INSERT·전체 교체 DELETE |
| `categories` | Y | — | — | — | 활성/대분류 검증, 목록·필터 |
| `trends` | Y | — | — | — | ACTIVE 트렌드 조회 |
| `trend_sources` | Y | — | — | — | 최신 Source 조회 |
| `trend_category_map` | Y | — | — | — | EXISTS/JOIN |
| `user_profiles` | — | — | — | — | 현재 API 접근 경로 미확인 |
| `oauth_accounts` | — | — | — | — | 현재 API 접근 경로 미확인 |
| `user_trend_bookmarks` | — | — | — | — | 현재 API 접근 경로 미확인 |
| `search_logs` | — | — | — | — | 현재 API 접근 경로 미확인 |
| `trend_ai_analyses` | — | — | — | — | 현 목록 API 미조회 |
| `trend_related_keywords` | — | — | — | — | 현 목록 API 미조회 |
| `trend_rank_snapshots` | — | — | — | — | 현 목록 API 미조회 |
| `alembic_version` | — | — | — | — | Migration 계정만 대상 |

#### 현재 API 별 직접 경로

| API | 일반 Runtime 권한 사용 |
|---|---|
| `POST /api/auth/signup` | `users` SELECT/INSERT, `user_interest_categories` SELECT (가입 후 세션 확인) |
| `GET /api/auth/check-login-id`, `POST /api/auth/login`, `GET /api/auth/session` | `users` SELECT; 로그인/세션은 `user_interest_categories` SELECT |
| `GET /api/categories` | `categories` SELECT |
| `POST /api/users/me/interests` | `users` SELECT(CurrentUser), `categories` SELECT, 관심사 SELECT/INSERT |
| `GET /api/users/me/interests` | `users` SELECT(CurrentUser), 관심사 SELECT |
| `PUT /api/users/me/interests` | `users` SELECT(CurrentUser), `categories` SELECT, 관심사 SELECT/FOR UPDATE/INSERT/DELETE |
| `GET /api/trends` | `trends`, `trend_sources`, `trend_category_map`, `categories` SELECT |
| `GET /api/trends/personalized` | `users`, `user_interest_categories`, `categories`, `trends`, `trend_sources`, `trend_category_map` SELECT |
| `GET /api/health/ready` | `SELECT 1` (업무 테이블 직접 권한 불필요) |

## 2. R-01 — 사용자 소유권은 어느 계층에서 보장되는가

### 2.1 현재 구현에서 성립하는 경계

```text
JWT Bearer
  → get_current_user: JWT subject 파싱, 사용자 행 조회, ACTIVE 검사
  → /api/users/me/interests Router: current_user.user_id 사용
  → InterestService: 전달받은 user_id를 신뢰해 도메인 규칙/트랜잭션 제어
  → InterestRepository: WHERE user_id = :user_id로 조회·삭제 대상을 선택
  → DB: 단일 Runtime DB 계정 권한으로 SQL 처리
```

`interest_router.py`는 요청자가 임의의 `user_id`를 제출하도록 하는 엔드포인트가 아니며, `current_user.user_id`를 서비스에 전달한다. 그러나 **Service가 JWT를 재검증하거나 임의 ID 호출을 자체적으로 거절하는 구현은 아님**. 추후 새 Router, 관리자 기능, 배치에서 동일 Service를 호출할 때 **신뢰할 수 있는 호출자/소유권 경계**를 재검토해야 한다.

### 2.2 DB가 담당하는 것과 담당하지 않는 것

- **DB GRANT:** 계정이 `user_interest_categories`에서 SELECT/INSERT/DELETE할 수 있는지 결정한다.
- **DB 제약:** FK, UNIQUE, NOT NULL 등 관계·중복·널 규칙의 일부를 강제한다.
- **FastAPI/Service:** JWT 주체, 활성 대분류만 선택, 현재 사용자 범위, 전체 교체 정책, 409 등 도메인 오류를 검증한다.
- **잔여 위험:** Runtime DB 자격 증명으로 직접 SQL을 실행할 수 있으면 API의 `WHERE user_id = JWT 주체` 제한을 우회할 수 있다. 현재 테이블 GRANT 방식만으로 행 단위 소유권은 보장하지 못한다.

**보안 주장의 범위:** 정상 API 경로에서 A의 요청이 B의 데이터를 바꾸지 않는다는 시험과, 탈취된 DB 자격 증명으로 임의 SQL이 가능한지는 서로 다른 위협 모델이다.

## 3. R-02/R-03 — 게시 Gate의 정책·구현·적용 범위를 구분

### 3.1 상태의 분리

| 대상 | 현재 확인한 기준 | 판정 제한 |
|---|---|---|
| G4/G5/G6 정책 | RSS 운영 Gate v0.3 정책 확정, G6 HOLD | 정책 확정 ≠ 운영 시험 완료 |
| G5 P1 HOLD 경계 | 보호 대상 연결 전 차단에 대한 격리 SQLite 시험 기록 | 실운영 DB의 모든 쓰기 우회 차단을 증명하지 않음 |
| P4 독립 Writer·영속 Journal | 2026-11-08 DRAFT에 A1/B2 검토 | 실제 Writer APPLY 미구현·미승인 |
| 일반 FastAPI | 조회 Router 및 사용자 기능 구현, 공개 게시 Router 연결 미확인 | 공개 Router만 없다는 사실은 관리 계정 직접 SQL 우회까지 막지 않음 |
| G5/G6 실제 운영 | HOLD | 게시 허가로 간주 금지 |

`Trend.status=ACTIVE`와 A1 적격성/`WOULD_ACCEPT`는 게시 승인 증거가 아니다. **G6 HOLD는 미승인 트렌드의 운영 게시 APPLY를 금지하는 정책이지 회원가입 및 관심사 같은 통상적인 서비스 쓰기 전체를 금지하는 규칙이 아니다.**

### 3.2 HOLD 중 작업의 구분

| 작업 | 현재 취급 및 별도 Gate |
|---|---|
| 미승인 Trend/Source/Map 게시, P4 Writer 실제 APPLY | **불허** (G4/G5/G6 게시 Gate) |
| 미승인 Google RSS 접근·보존·공개 | **불허** (RSS-OPS 별도 HOLD) |
| 운영 DB Demo Trend Seed | 기존 정책과 직접 충돌 가능; 기본 비활성. 운영 승인·권리 검토 없이 실행 금지 |
| Category Master Seed | 트렌드 게시와는 별도; 운영 DBA·콘텐츠·카테고리 정책/데이터 영향 및 별도 실행 승인 필요 |
| Alembic Migration | 게시와는 별도; Schema 영향·백업·DB 권한·배포 승인 필요 |
| 일반 FastAPI 배포 | 코드/Secret/접근 경계·회귀 검사 별도 통과 필요. 게시 승인과 자동 연동하지 않음 |
| 일반 회원가입·관심사 변경 | 정상 앱 기능 범위에서 Runtime 허용 권한을 사용하며, G6 HOLD라는 이유만으로 차단하지 않음 |

**문서 충돌 처리:** P4 세부 계약이 DRAFT이므로 여기서 Writer의 실제 실행 정책이나 GRANT를 새로 동결하지 않는다. P4보다 구체적인 최종 확정안이 생기면 해당 확정안을 우선한다.

## 4. R-04 — Runtime 탈취 시 남는 INSERT·DELETE 위험

| 직접 SQL 또는 침해 시도 | 현 Runtime GRANT에서의 예상 | 애플리케이션 인가 적용 여부 |
|---|---|---|
| `INSERT users` | 허용 가능 (DB 제약조건은 적용) | 직접 SQL이면 회원가입 입력 검증·비밀번호 정책 우회 가능 |
| `SELECT users` | 허용 가능 | 직접 SQL이면 이메일·비밀번호 해시 등 전체 ORM 조회권 노출 위험 |
| `UPDATE/DELETE users` | 권한 거부 목표 | 해당 DB 계정에 금지. 관리자/다른 계정까지 의미하지 않음 |
| `INSERT user_interest_categories` | 허용 가능 | 직접 SQL이면 임의 user_id/비활성·하위 카테고리 등 도메인 규칙 우회 시도 가능 (FK/UNIQUE는 적용) |
| `DELETE user_interest_categories` | 허용 가능 | 직접 SQL이면 다른 사용자 행 제거 시도 가능 |
| `INSERT/UPDATE/DELETE trends`, `trend_sources`, `trend_category_map` | 권한 거부 목표 | 일반 API 계정만의 방어선; 다른 쓰기 권한 계정과 DEFINER 경로는 별도 검사 |
| 일반 Runtime의 DDL/GRANT | 권한 거부 목표 | 연결된 DB 계정의 실제 유효 권한 검증 필요 |

따라서 정상 API에 필요한 `users` INSERT·관심사 INSERT/DELETE를 제거하지는 않되, 자격 증명 노출·DB 직접 접속·백엔드 SQL 인젝션 방지, 사용자별 인가 회귀 검증을 **별도 보안 요구사항**으로 둔다. `users` 컬럼별 SELECT/프로젝션 축소는 현재 ORM 쿼리 변경을 수반하므로 급한 운영 전에 임의 적용하지 않는다.

## 5. R-06 — `SELECT ... FOR UPDATE`와 권한 검증

`InterestRepository.find_by_user_id_for_update()`는 실제 트랜잭션에서 행 잠금 조회를 수행하며, 관심사 수정은 DELETE/INSERT 및 재시도 정책을 함께 사용한다. 현재 제안 권한은 `SELECT + INSERT + DELETE`; **UPDATE, LOCK TABLES를 추정으로 추가하지 않는다.**

다음 조건의 **격리 MariaDB 실험**을 완료해야만 ‘이 권한 조합이 지원된다’고 결론낼 수 있다.

1. 운영 후보와 동일한 MariaDB **이미지 버전/다이제스트** 선택, `CURRENT_USER()` 확인.
2. Runtime 최소 권한만 부여한 사용자로 관심사 초기 저장·전체 교체·동일 요청·경합 상황을 실행.
3. `SELECT ... FOR UPDATE`를 명시적 트랜잭션에서 수행하고 잠금/대기/충돌/재시도 및 오류 코드를 기록.
4. 기존 ER_CHECKREAD(1020) 재시도·409 계약이 바뀌지 않는지 확인.
5. 부족한 권한 오류가 있다면 정확한 SQL/버전/필요 권한을 먼저 조사하고, **권한 확대 전에 설계 변경 검토**.

## 6. R-07 — 운영 계정/DB 사전 검증 게이트

운영 배포 중 Caddy를 공개하거나 FastAPI를 Ready로 선언 **하기 전에** 다음을 검사하는 별도 배포 단계가 필요하다.

| 체크 | 기대 결과 | 실패 시 처리 |
|---|---|---|
| 예상 접속 대상 | DB_HOST/PORT/DB_NAME 및 필요시 DATABASE_URL 최종 우선순위 일치 | 배포 중단·공개 차단 |
| 실제 인증 계정 | DB 접속 후 `CURRENT_USER()`가 승인된 `user@host` 식별과 일치 | 배포 중단 |
| 실제 DB | `DATABASE()` 및 필수 Schema/Alembic 버전 확인 | 배포 중단 |
| 권한 | `SHOW GRANTS` + 역할·PUBLIC(버전 지원 시)·글로벌/DB 권한·DEFINER 경로 감사 | 과도한 권한이면 배포 중단 |
| Secret 경계 | 일반 Backend 환경에 root/Migration/Writer 자격 증명 없음 | 배포 중단 |
| Readiness | `/api/health/ready` 와 실제 핵심 요청 경로 확인 | 공개 승인 보류 |

현재 `backend/app/core/config.py`에서 `DATABASE_URL`이 다른 `DB_*` 값보다 우선하며, `DEBUG` 기본값은 `true`다. **표의 사전 검사/공개 차단 기능이 이미 구현돼 있다고 주장하지 않는다.** 구현 시에는 민감한 DB URL/비밀번호를 결과 로그로 출력하지 않고, 사용자 승인 하에 안전한 순서로 확인한다. `SHOW GRANTS` 출력에는 인증 관련 정보가 포함될 수 있으므로 외부 공유 전 가린다.

## 7. R-05 및 전체 회귀·부정 시험 Acceptance Criteria

**시험 환경:** 운영·로컬 개발 DB가 아닌 전용 격리 MariaDB DB/볼륨과 시험용 계정. 기존 테스트 DB(`3307`)도 파괴적 시험에 사용하려면 데이터 보존·격리 계약을 먼저 확인. 부정 시험 전후 데이터 스냅샷 확인.

| ID | 실험 | 기대 결과 및 한계 |
|---|---|---|
| DB-01 | Runtime 접속 계정/DB/역할/GRANT/PUBLIC/DEFINER 감사 | 유효 권한이 매트릭스 범위 내, 우회 경로 없음(관찰 범위 한정) |
| DB-02 | 회원가입→로그인→세션·중복 검사 | 정상 기능, `users` SELECT/INSERT만으로 수행 |
| DB-03 | 관심사 최초 저장·전체 교체·no-op·동시 수정 | SELECT/INSERT/DELETE 및 `FOR UPDATE` 정상, 계약 유지 |
| DB-04 | 카테고리·전체·맞춤 트렌드 목록·최신 Source | SELECT 전용으로 정상 |
| DB-05 | `trends`, `trend_sources`, `trend_category_map` 직접 DML 부정 시험 | 모든 시도가 DB 권한 오류, 시험 데이터 불변 |
| DB-06 | `users` UPDATE/DELETE, 미사용 테이블 DML/SELECT, DDL/GRANT 부정 시험 | 거부; 모든 경로·상속 권한 확인 |
| APP-01 | 무토큰/만료 토큰 접근 | 현재 인증 API 계약상 거부, 데이터 불변 |
| APP-02 | **A와 B 각자 정상 JWT로 조회/수정**; A 변경 전후 B 관심사 재조회 | A는 자기 관심사만 바뀌고 B 데이터 불변. API에 타인 ID를 지정하는 경로가 없음도 확인 |
| APP-03 | Service에 다른 `user_id`를 전달하는 새 호출 경로 가정/모의 검토 | 호출 경계에 권한 재확인이 없다면 위험으로 기록. 현 API 보호를 과장하지 않음 |
| OPS-01 | `DATABASE_URL` 충돌, 운영 DB명/계정/Host 불일치, 고권한 자격 증명 유입 | Caddy 공개/Ready 이전 Gate에서 **차단** (기능 구현 전에는 기대 조건) |
| OPS-02 | G6 HOLD에서 게시 실행 시도 | 기존 확정 범위의 차단만 PASS 주장; 미구현 Writer 전체 보장 금지 |
| OPS-03 | 운영/개발 Compose 분리, Secret/볼륨 경계 | 일반 API 환경에 운영자·Writer·Migration 자격 증명 비포함, DB 3306 비공개 |

**주의:** DB 권한 거부를 HTTP 403과 혼동하지 않고, 실패 원인을 매핑해 조사한다. 계정 탈취 시 관심사 행 단위 보호를 이 표만으로 PASS 처리하지 않는다.

## 8. 이번 검토의 판정 및 다음 설계

| 영역 | 결과 |
|---|---|
| v0.1 테이블별 권한표 | **변경 없음 / 권한 설계 후보** |
| R-01~R-04 문서 보완 | **반영됨** (실행 결과가 아니라 명세 보완) |
| R-05~R-07 테스트/기동 게이트 | **요구사항 작성됨, 미실행·일부 미구현** |
| G4/G5/G6 | **실운영 HOLD 유지** |
| 실제 `CREATE USER`/`GRANT` SQL | **미작성·미적용** (Account Provisioning 설계에서 분리) |
| 설계 동결 | **NOT FROZEN** |

**다음:** `Trend_Leader_Account_Provisioning_Design_v0.1_DRAFT.md`를 기준으로 계정 생명주기/실행 주체, 최초 설치 vs 재배포, 권한 부여 방법 및 검증 순서를 결정한다. 실제 적용 전 운영 DB 버전·계정 Host·Secret 전달·현재 데이터 상태·P4 계약 최신본을 재확인한다.

## 9. 소스·근거

### 저장소 코드/정책

- `backend/app/api/routes/auth_router.py`, `interest_router.py`, `trend_router.py`, `category_router.py`, `health.py`
- `backend/app/api/dependencies/auth_dependency.py`, `backend/app/db/session.py`, `backend/app/core/config.py`
- `backend/app/services/auth_service.py`, `interest_service.py`, `personalized_trend_service.py`
- `backend/app/repositories/user_repository.py`, `interest_repository.py`, `trend_repository.py`, `category_repository.py`
- `backend/app/models/*.py`, `backend/alembic/versions/`, `.env.compose.example`, `docker-compose.yml`, `backend/sql_script/init.sql`
- `docs/operations/trend-publication/g5-publish-control/Trend_Leader_MVP_A_G5_P1_최소실행계약_확정_HOLD_차단시험_v0.1.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_P4_Final_Review_Addendum_v0.2_A1_Aligned_DRAFT_20261108.md`

### 공식 참고

- MariaDB GRANT: https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant
- MariaDB Docker 초기화: https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables
- MariaDB CURRENT_USER(): https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/information-functions/current_user
- MariaDB SELECT ... FOR UPDATE: https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/selecting-data/for-update

> **주의:** 본 문서는 설계/검증 계획이며, 실제 SQL 권한/시드/배포 실행을 승인하거나 대신하지 않는다.