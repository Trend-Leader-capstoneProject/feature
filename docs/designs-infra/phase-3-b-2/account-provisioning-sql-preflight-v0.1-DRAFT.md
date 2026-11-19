# Trend Leader — Account Provisioning SQL + Preflight 계약 v0.1 (DRAFT)

> **2026-11-12 이후 채팅 결정 반영 안내 (본 문서에 우선 적용):**
> - 사용자는 **M-A1(운영 Compose의 선택적 일회성 Migration Profile) + Alembic의 DB 전용 Settings 분리**를 구현 방향으로 선택했다. 실행 차단 메커니즘, DB 계정·Secret, 권한 SQL, 이미지 Digest, 테스트는 **NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**이다.
> - 위 선택은 P4/G4/G5/G6 기존 HOLD 및 데이터 게시 승인 정책을 변경하지 않는다.
> - 원문에 `M-A NOT SELECTED`, `M-A/M-B 미선택` 또는 `GitHub 미변경`과 같은 표현이 있으면 **과거 초안 작성 시점의 기록**이다. 현재 선택 상태와 원격 반영 사실은 이 안내와 README를 우선한다.
> - `dev` HEAD SHA 표기는 해당 DRAFT 작성 당시 근거 버전이며, 최신 원격 상태의 증명이 아니다.

> 날짜: 2026-11-12 KST · 기준: GitHub `dev` `b133b494f8258eea603243f8f07191a33290084a`  
> 상태: **검토용 SQL / 운영 실행 금지 / NOT FROZEN / NOT TESTED**  
> 범위: `trend_api_runtime`의 권한 제안, 생성·검증 순서, 계정 보안, 실패 차단 계약. 사용자 비밀번호·실제 `CREATE USER` 자동화·서버 반영 없음.

## 0. 고정 불변조건과 미결정

- 고정: **독립 운영 Compose**, DB 컨테이너 내부 수동 Bootstrap, Migration·Provisioning·Runtime 자격 증명 분리, `trend_leader` DB의 `utf8mb4_unicode_ci` 유지, G4/G5/G6 HOLD.
- 미결정: Runtime 계정 Host(`'%'`는 후보), Migration 계정의 Host/DDL 권한, 인증 Secret의 안전한 공급 및 회전 방법, 이미지 Digest, 운영 배포 환경 검증.
- **주의: 아래 SQL은 비밀정보를 포함하지 않는 최소 GRANT 검토용으로, 실제 운영 적용 명령서가 아니다.**

## 1. 최초 DB 준비 계약

1. 격리된 빈 운영 볼륨에서 MariaDB 기동, root Socket 인증 확인. root 비밀번호는 이미지의 `_FILE` 방식으로 전달 후보.
2. DB 관리자 전용 Bootstrap 단계에서 `trend_leader`를 문자셋 `utf8mb4`, COLLATE `utf8mb4_unicode_ci`로 **명시적 생성**하고 실제 값을 조회. 기존 DB이면 무조건 CREATE/ALTER 금지, 충돌 시 중단.
3. **Migration 실행 전에** 관리자가 Migration용 계정과 인증/Host/필요 최소 DDL 권한을 준비. 이 계정의 실제 GRANT는 확정 전까지 작성·실행 보류.
4. 별도 Migration 실행 환경에서 Alembic을 적용하고 `alembic_version` 및 테이블·인덱스 정합성 확인. MariaDB DDL의 비트랜잭션 동작·실패 복구 계획 검토.
5. 이후 Runtime 계정 생성/GRANT 및 최소 권한 검증. Runtime DB 비밀번호와 root/Migration 비밀번호는 구분.
6. Runtime Preflight와 정상/금지 API 시험 통과 이후에만 HTTPS를 공개.

**계정 생성 전 필수 조건:** 기존 `user@host` 계정 존재 여부와 기존 GRANT를 먼저 조회. 이미 권한이 과도한 계정에 `GRANT`만 다시 하면 추가 권한이 사라지지 않는다. `CREATE OR REPLACE USER`·무분별한 `REVOKE`·비밀번호의 명령행·히스토리·로그 기록은 금지. 안전한 Secret 공급 방식은 별도 시험 후 승인한다.

## 2. Runtime의 권한 전용 SQL 스케치

아래는 **이미 승인된 Host/자격 증명으로 적합한 Runtime 계정이 존재하고, Alembic이 전체 테이블을 생성한 후**의 GRANT 표현만 보여 준다. Host `%`는 현 단계의 후보 표기이며, 최종 Host가 달라지면 전체 SQL이 바뀐다.

```sql
-- REVIEW ONLY. NO REAL EXECUTION. 해당 계정의 선행 생성/GRANT 감사 필요.
GRANT SELECT, INSERT
    ON `trend_leader`.`users`
    TO 'trend_api_runtime'@'%';

GRANT SELECT, INSERT, DELETE
    ON `trend_leader`.`user_interest_categories`
    TO 'trend_api_runtime'@'%';

GRANT SELECT
    ON `trend_leader`.`categories`
    TO 'trend_api_runtime'@'%';

GRANT SELECT
    ON `trend_leader`.`trends`
    TO 'trend_api_runtime'@'%';

GRANT SELECT
    ON `trend_leader`.`trend_sources`
    TO 'trend_api_runtime'@'%';

GRANT SELECT
    ON `trend_leader`.`trend_category_map`
    TO 'trend_api_runtime'@'%';
```

**미부여**: `users` UPDATE/DELETE, 관심사 UPDATE, 트렌드 3테이블 DML, 미사용 7테이블, `alembic_version` DML/SELECT, 전역/DB 단위 ALL, CREATE/ALTER/DROP/GRANT OPTION 등. `GRANT`의 문법 유효성과 실제 부정 시험은 고정된 MariaDB 이미지에서 확인한다.

SQL 자체는 **추가 권한을 취소하지 않으므로**, 적용 전후 실제 유효 권한 감사와 차이 분석이 필수다. `FLUSH PRIVILEGES`는 정상 `GRANT` 사용 뒤 통상 필요하지 않지만, 수동으로 시스템 권한 테이블을 변경하지 않는다.

## 3. Preflight 읽기 전용 SQL 검토 초안

```sql
-- 연결된 Runtime 계정으로 수행: 예상 DB명과 실제 인증 계정 대조
SELECT DATABASE(), USER(), CURRENT_USER(), CURRENT_ROLE(), VERSION();

-- DB 생성 시 합의한 문자셋 / Collation 확인
SELECT SCHEMA_NAME, DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME = 'trend_leader';

-- 승인된 관리자/감사 경로에서 확인: 출력의 민감 내용·계정 정보 보호
SHOW GRANTS FOR 'trend_api_runtime'@'%';
```

별도 승인된 감사에서 계정 Host 우선순위, 역할 상속, PUBLIC 권한(버전 지원 여부 확인), routines / DEFINER / 전역 권한 우회 가능성까지 확인. `SHOW GRANTS` 문자열 비교만으로 모든 유효 권한·실제 데이터 격리를 증명하지 않는다. 검사 결과에는 DB 비밀번호, 접속 URL 원문, JWT가 포함되지 않도록 한다.

**Preflight에서 SELECT 1만으로 PASS 금지**: MariaDB 버전/이미지, DB/계정 실체, 기대 Alembic revision, 업무 테이블, 실제 API 정상 경로, 권한 부정 시험의 별도 결과까지 확인.

## 4. 정상·부정 시험 계획 — 격리 DB에서만

| ID | 시험 | 합격 |
| --- | --- | --- |
| SQL-01 | 새 격리 볼륨 DB Bootstrap/Collation 조회 | 문자셋·Collation 기대값 일치 |
| SQL-02 | Migration 전용 자격 증명·스키마 적용 | 3개 Alembic 리비전 적용 및 `alembic_version` 일치 |
| SQL-03 | Runtime `CURRENT_USER`, GRANT 감사 | 승인 계정·6개 테이블의 필요한 권한만 |
| SQL-04 | 회원가입·로그인·세션 | `users` SELECT/INSERT만으로 통과 |
| SQL-05 | 관심사 최초 저장/수정·`SELECT FOR UPDATE`·동시성 | SELECT/INSERT/DELETE만으로 통과 |
| SQL-06 | 카테고리·전체·맞춤 트렌드 목록 | SELECT만으로 통과 |
| SQL-07 | Runtime 직접 Trend/Source/Map DML | 모두 권한 거부 및 데이터 불변 |
| SQL-08 | Runtime `users` UPDATE/DELETE 및 DDL/GRANT | 모두 권한 거부 |
| SQL-09 | 잘못된 DATABASE_URL/고권한 계정 주입 | Proxy 공개 전 차단 |
| SQL-10 | 마이그레이션 중단·반복/기존 볼륨 재시작 | 상태 불명확 시 자동 재시도 금지, 데이터 보존 |
| SQL-11 | Secret·Host·네트워크 | root/Migration/Writer Secret 일반 Backend 미주입, 3306/8000 미게시 |
| SQL-12 | G6 HOLD / RSS-OPS HOLD | 실 게시 미수행, 미승인 수집·Demo Trend Seed 미실행 |

DDL/GRANT/부정 DML을 포함한 시험은 운영 또는 개발 DB에 실행하지 않음. 후속 단계에서 테스트 데이터와 격리 네트워크·볼륨·비밀 파일을 준비한 후 실행 결과를 기록.

## 5. Migration 계정 계약의 미확정 이유

기존 Alembic 3개 리비전에는 CREATE TABLE/INDEX, ALTER TABLE, 제약조건 제거·추가가 있으며 Alembic 자체가 `alembic_version` 테이블과 버전 레코드를 관리한다. **DB 단위 DDL과 버전 메타데이터 DML을 어떤 GRANT 조합으로 구현할지는 실제 MariaDB 12.3.3 후보에서 검증해야 한다.** `REQUIRE REFERENCES` 등 불확실한 권한을 추측하거나 `ALL PRIVILEGES`를 간편하게 부여하지 않는다.

Migration 자격 증명을 평시 API에 넣지 않고, 일회성 실행 환경에서만 제공한다. 기존 `backend` Runtime 서비스를 대상으로 동일 Secret의 `alembic upgrade head`를 실행하면 분리 목표를 충족하지 못한다.

## 6. 배포 전 Fail Closed 계약

- `DATABASE_URL`이 운영 값과 충돌하거나 관리 계정을 가리키면 중단.
- 운영 `DB_HOST`, `DB_NAME`, `CURRENT_USER`, 실제 Schema/Collation/GRANT 불일치 시 중단.
- 운영용 DB/Proxy의 설정 검사 결과와 실제 서비스를 혼동하지 않음. Proxy는 Preflight PASS 후 공개.
- SQL/DDL/GRANT 작업 도중 실패하면 이전 단계의 적용 여부를 확인하고 수동 재승인; 자동 전체 재실행 금지.
- G6 HOLD는 트렌드 게시 작업에 적용하며 일반 회원가입/관심사 변경을 임의로 막지 않음.
- 기존 `backend/sql_script/init.sql`과 개발 Compose는 운영 최초 설치에서 실행/마운트하지 않음.

## 7. 후속 검토에서 결정할 항목

1. Migration을 기본 Compose의 `profiles` 기반 보호된 일회성 서비스로 정의할지, 별도 수동 작업으로 정의할지.
2. Migration 계정의 정확한 GRANT 범위(실제 리비전 적용으로 결정), 계정 Host, Secret 전달 방식을 어떻게 구현할지.
3. Runtime 계정 Host `@'%'`를 유지할지 실제 네트워크 범위로 제한할지; 고정될 구체값을 시험.
4. Bootstrap SQL의 계정 생성·비밀번호 공급(복사·로그·히스토리 노출 위험 포함)과 Preflight 결과 아카이빙의 책임자.

## 근거

- 실제 코드: GitHub `dev` HEAD `b133b494f8258eea603243f8f07191a33290084a`; 관련 Alembic/Repository/Compose/Settings.
- MariaDB 공식 GRANT: https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant
- MariaDB 공식 CREATE USER: https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/create-user
- MariaDB Docker init 변수: https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables
- Alembic version table: https://alembic.sqlalchemy.org/en/latest/api/runtime.html