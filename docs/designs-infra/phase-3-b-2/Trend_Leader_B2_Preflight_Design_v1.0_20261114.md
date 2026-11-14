# Trend Leader — Phase 3-B-2 Migration Preflight(B-2) 설계 확정안 v1.0

> 작성: 2026-11-14 (KST)  
> 저장소: `Trend-Leader-capstoneProject/feature`  
> 확인한 `dev` HEAD: `aca8c5155ff548bcec97b750be642ce816a730d4` (문서 작성 시점, 구현 시작 전 재조회)  
> **상태: B-2 POLICY FROZEN / 부분 구현(순수 분류) / DB 관찰·Evidence·Guard 연동 NOT IMPLEMENTED / 격리 DB NOT TESTED / DEPLOYMENT NOT APPROVED**
> 상위 기준: `docs/designs-infra/phase-3-b-2/Trend_Leader_Phase_3-B-2_M-A1_Design_Decision_v1.0_20261113.md`  
> 사용자 확정 선택: **Migration 전용 계정 재사용(A안)**, **B-2는 관찰·감사 / B-3가 승인값 대조(A안)**.  
> 2026-11-14 사용자 P0-A~D 승인에 따라 실행·보고 정책 동결. 순수 상태 분류 코드는 PR #103으로 병합되었으나 B-2 CLI/DB 관찰/Evidence 기능과 운영 배포의 완료를 뜻하지 않는다.

## 1. 문제와 목표

운영 Alembic 적용 전에, **Migration 전용 계정이 연결하는 실제 MariaDB의 관찰 가능한 상태**를 기록한다. DB 변경, 승인, Migration, 운영 서비스 공개는 하지 않는다. 다음 작업인 B-3는 독립적인 승인 Manifest와 Preflight 증거를 대조하며, L-2는 Lock 획득 후 같은 DB Connection에서 적용 직전 다시 검사한다.

**성공의 의미:** 검사와 기록이 완료되었다는 뜻이며, *안전한 배포 승인*이나 *정확한 운영 DB의 최종 신원 확인*이 아니다.

## 2. 불변조건과 제외 범위

1. 기본 `deny`/인자 없음은 변경 없이 `DENY_DEFAULT`, 종료 코드 2; `apply`는 `MODE_NOT_ENABLED`, 임의 명령은 `INVALID_MODE`로 거부한다.
2. 새로 허용하는 경로는 정확히 `preflight`이다. 추가 CLI 옵션은 설계·테스트 승인 전 `INVALID_MODE`로 거부한다.
3. 일반 Runtime Settings/DB 계정, root/Writer Secret, JWT를 사용하지 않는다. 기존 `MigrationDbSettings`를 사용하고, `DATABASE_URL`/일반 `DB_*`를 대체 원천으로 사용하지 않는다.
4. 정상 B-2는 DB에 DDL, DML, `alembic upgrade/downgrade/stamp/revision`, `GET_LOCK`, 계정 생성/GRANT 및 승인 사용 기록을 수행하지 않는다.
5. Docker Profile/Guard는 관리자의 EntryPoint 우회를 방어하는 강력한 인증 경계가 아니다. 계정·Secret 접근 제어가 별도로 필요하다.
6. G4/G5/G6, RSS-OPS HOLD, P4 Writer APPLY 미승인 상태 유지. 개발/테스트 Compose, 기능 API, 기존 Alembic Revision 미변경.
7. **Runtime Deployment Preflight**(Runtime GRANT/실제 API/HTTPS/Android E2E)는 B-2 범위 밖이며 운영 공개 전 별도로 수행한다.

## 3. 명령과 책임 분리

- **Guard CLI**: 입력 구문 파싱, `deny`와 `apply` 거부 유지, B-2 작업 조정 및 안전한 종료 코드·Reason Code 전달. 민감 인자·환경값 원문 비출력.
- **Migration Preflight 검사**: 설정 검증, 실제 DB 연결, 허용된 읽기 전용 메타데이터 조회, 모호 상태 분류. SQLAlchemy Connection은 검사를 진행하는 동안 하나를 사용.
- **Evidence 저장**: 구조화된 관찰 보고서 생성 및 영속 기록. 저장 실패, 기존 ID 충돌, 경로 불확실 시 정상 완료 금지. 저장소가 DB가 아니라는 점을 명시.
- 구체 파일명·함수명·패키지 배치는 구현 직전 현재 코드와 충돌 여부를 확인한 뒤 최소 변경으로 정한다. 기존 `backend/alembic/env.py`의 자체 Engine 생성 흐름은 B-2에서 수정하지 않으며 L-2에서 별도 다룬다.

## 4. 실행 순서

```text
Guard(preflight)
 → CLI 검증 (정확히 preflight만)
 → Migration 전용 설정/Secret 및 혼입·충돌 조건 감사
 → Evidence 영속 경로 가용성·비밀정보 노출 위험 확인
 → 전용 Engine / 단일 Connection 연결 (자동 재연결·자동 재시도 금지)
 → **검사 전** MariaDB 읽기 전용 트랜잭션 시작
 → 데이터베이스·실제 계정·버전·기본 문자셋/Collation 관찰
 → Alembic 버전 테이블·현재 heads 및 업무 객체 상태 관찰
 → 설정과 관찰값의 명백한 모순 분류 (승인 대조가 아님)
 → rollback/close/engine dispose, 실패도 안전하게 처리
 → 비밀정보 없는 보고서 고유 ID로 영속 기록
 → 관찰 완료/불확실/실패 결과 반환 (apply는 여전히 금지)
```

**트랜잭션 관련 구현 전제:** MariaDB `START TRANSACTION READ ONLY`는 공식 지원되지만 `START TRANSACTION`은 기존 트랜잭션을 암묵 COMMIT할 수 있다. 따라서 다른 조회·쓰기나 `connection.begin()` 이후에 임의로 실행하지 않는다. SQLAlchemy 2.x autobegin/DBAPI 설정과 정확한 실행 순서는 격리 MariaDB 통합시험으로 확정한다. READ ONLY가 관리자/DDL 우회나 전체 시스템 읽기 전용을 보장한다고 주장하지 않는다. 일반 SQL 인젝션 경로가 생기지 않도록 동적 SQL 입력을 금지한다.

## 5. 관찰 데이터와 판정의 한계

| 확인 대상 | B-2 관찰값 | 책임 한계 |
|---|---|---|
| 설정 | `MIGRATION_DB_HOST/PORT/NAME/USER/PASSWORD_FILE` 및 제한된 timeout | 다른 환경변수 자동 대체 금지; 충돌 탐지 규칙은 운영 Compose에서 테스트 |
| 실제 DB | `DATABASE()` | 설정 DB명과 다르면 실패; 설정값과 같다는 사실만으로 승인된 서버라고 판단하지 않음 |
| 인증된 계정 | `CURRENT_USER()` | 사용자명/Host의 실제 인증값 관찰; 정확한 승인된 `user@host` 비교는 B-3 |
| 서버 버전 | `VERSION()` 및 서버 식별 보조값 | 서버 식별 보조값만으로 유일한 DB 신원 증명 불가 |
| DB 설정 | `information_schema.SCHEMATA`의 문자셋/Collation | DB 기본값 관찰; 전체 테이블/컬럼 Collation 검증으로 오인 금지 |
| 현재 Revision | `alembic_version`/Alembic current heads | 적용 승인이나 전체 Schema 무결성 보증으로 오인 금지 |
| DB 객체 | schema 내 가시적인 업무 테이블·뷰 등 | 권한과 가시성 한계 있음. 객체를 못 봤다고 빈 DB로 단정 금지 |

**빈 DB 후보 구분:**

- Revision이 한 개이고 현재 저장소 Revision 계보에 속함 → `VERSIONED_OBSERVED` (관찰만 성공)
- 버전 테이블이 보이지 않고 현재 권한 범위에서 업무 객체가 확인되지 않음 → `UNVERSIONED_EMPTY_CANDIDATE` (빈 DB *확정 아님*, B-3에서 별도의 빈 DB/Bootstrap 증거 필요)
- 버전 테이블 없음+기존 객체 존재, 비어 있는 version 테이블, 잘못된/미식별 Revision 또는 예기치 않은 다중 heads → `INDETERMINATE` (자동 승인 불가)
- DB 조회·설정·연결·증거 기록 실패 → `ERROR` (자동 승인 불가)

`MigrationContext.get_current_heads()`는 버전 테이블 자체가 없을 때도 빈 튜플을 반환하므로, 해당 반환값만으로 초기 빈 DB를 증명하지 않는다. 현 저장소의 Revision 파일 3개는 `2f29fa23597c`, `7e9d740c5df1`, `a4d7c9e21f3b`이며, 구현 착수 시 실제 계보를 다시 검증한다. 향후 브랜칭이 합법적인 변경으로 들어오면 다중 Revision 정책을 별도 재검토한다.

## 6. Evidence 및 실행 운영 계약 (P0-A~D FROZEN, 2026-11-14)

> 사용자 승인: P0-A 영속 Evidence, P0-B 위험 환경변수 차단, P0-C JSON/Reason/Exit, P0-D 단일 Connection READ ONLY. **운영 호스트 절대 경로와 UID/GID 및 실제 DB/드라이버 검증 결과는 운영 Compose·격리 MariaDB 후속 Gate에서 결정**하며, 이 값들을 임의로 확정하지 않는다.

### P0-A. Evidence 보호·영속 저장

- B-2 설정 입력명: `MIGRATION_PREFLIGHT_EVIDENCE_DIR`. 필수, **절대 경로**. 운영자가 사전 생성한 호스트 보호 영속 디렉터리를 운영 Compose에서 지정하여 Migration 컨테이너에 필요한 범위만 마운트한다. 경로가 없거나 불확실하거나 쓰기 불가하면 DB 접속 전 거부한다. 운영용 루트 경로를 Guard가 임의 생성하지 않는다.
- 실행별 고유 `evidence_id`(표준 라이브러리 기반 고유 ID)로 **배타적 신규 하위 디렉터리 생성**, 디렉터리가 이미 존재하면 실패하며 기존 Evidence를 덮어쓰거나 ID를 재사용하지 않는다. 하위 디렉터리는 실행 도중 충돌 없이 예약된다.
- JSON은 같은 하위 디렉터리의 새 임시 파일에 독점 생성하여 UTF-8로 완성, flush 및 파일 동기화 후 최종 `report.json`으로 게시한다. **최종 경로 선점·중복 여부를 검사하고 덮어쓰기는 금지**한다. 같은 파일시스템 내 게시/디렉터리 동기화 및 OS별 실제 내구성은 테스트로 입증해야 하며, 단순 `rename` 또는 `os.replace`만으로 무조건 무손실·무덮어쓰기를 보증한다고 표현하지 않는다.
- 오류 또는 프로세스 비정상 종료로 미완성 임시 파일이나 디렉터리가 남으면 **완료된 Evidence가 아닌 불완전 기록**으로 분류한다. 자동 삭제/재사용 금지; 별도 조사.
- Linux 컨테이너에서 Evidence 디렉터리 `0700`, 파일 `0600`을 기본 권한 후보로 두고, 실제 UID/GID·umask·마운트·심볼릭 링크/경로 바꿔치기 위험은 운영 Compose·격리 시험에서 검증한다. Backend/Runtime 서비스에는 해당 디렉터리 및 Secret을 제공하지 않는다.
- Evidence 저장 실패·ID 충돌·권한/경로 문제는 성공 처리 금지. 설정/경로를 확보하지 못해 보고서를 만들 수 없는 경우에도 **안전한 종료 코드 4**로 처리하되, 완료되지 않은 보고서를 성공 증거처럼 출력하지 않는다.
- 호스트 DB 밖의 파일 기록이므로 **DB 읽기 전용과 양립**한다. 파일 보호 정책과 ID는 독립적인 전자서명·변조 방지·승인 증거가 아니다. B-3가 별도의 승인 Manifest와 비교한다.

### P0-B. 환경변수 혼입 차단

- 승인된 Migration 연결 입력은 `MIGRATION_DB_HOST`, `MIGRATION_DB_PORT`, `MIGRATION_DB_NAME`, `MIGRATION_DB_USER`, `MIGRATION_DB_PASSWORD_FILE`, `MIGRATION_DB_CONNECTION_TIMEOUT`(선택, 기존 유한 범위)만이다. 다른 `MIGRATION_DB_*` 이름은 거부한다. 비밀번호 평문 변수 `MIGRATION_DB_PASSWORD`는 명시적으로 금지한다.
- `MIGRATION_PREFLIGHT_EVIDENCE_DIR`를 B-2 전용 필수 입력으로 허용한다. 타인의 `.env`/일반 Settings/Runtime URL을 대체 설정으로 읽지 않는다.
- `DATABASE_URL`, 일반 `DB_*`, `API_DB_*`, `JWT_SECRET_KEY`, `MARIADB_ROOT_PASSWORD`가 **존재하면 값이 비었더라도 차단**한다. `DB_ROOT_PASSWORD`는 `DB_*`에 포함된다. 키 이름을 정규화해 플랫폼 대소문자 차이를 고려하고, Secret 원문이나 환경 덤프를 출력하지 않는다.
- `PATH`, `HOME`, `LANG` 등 일반 OS 변수 전체를 차단하지 않는다. 새롭게 도입되는 Writer/관리자 Secret 이름은 기존 코드에 없으면 추측해서 등록하지 않으며, **운영 Compose/새 Secret 도입 시 실제 변수를 검토해 차단 규칙을 보강**한다. 이 목록만으로 다른 모든 비밀 혼입이 배제됐다고 선언하지 않는다.
- 해당 환경 감사는 **B-2 Guard CLI에만 적용**하며, 별도 테스트 Fixture와 기존 직접 Alembic 경로를 무단 변경하지 않는다. 운영 Compose의 최소 환경 주입·Secret 분리 검사를 별도 Gate로 유지한다.

### P0-C. Evidence JSON v1과 결과 계약

- 실행별 보고서는 UTF-8 JSON **`schema_version: 1`**. 필수 키: `schema_version`, `evidence_id`, `observed_at_utc`, `inspection_status`, `schema_state`, `configured_target`, `observed_target`, `current_revisions`, `reason_codes`, `checks`, `image_identity_verification_status`.
- `configured_target`: `host`, `port`, `database`, `user`(비밀번호 불포함). `observed_target`: `database`, `current_user`, `server_version`, `database_charset`, `database_collation`. 미관찰 값은 추측하지 않고 `null` 및 해당 Reason Code로 표현한다.
- `schema_state`는 기존 순수 분류 계약 `VERSIONED_OBSERVED`, `UNVERSIONED_EMPTY_CANDIDATE`, `INDETERMINATE` 중 하나이며, 분류가 불가능할 때는 `null`. 초기 빈 DB 후보는 **관찰 가능 범위의 후보일 뿐** 빈 DB 확증 또는 Migration 승인이 아니다.
- `inspection_status`는 `OBSERVED`, `INDETERMINATE`, `ERROR` 세 값. `OBSERVED`는 절차와 영속 기록 완료만 뜻하며 `APPROVED`, `SAFE_TO_APPLY`, `DEPLOYMENT_APPROVED`를 사용하지 않는다. B-3 승인 및 L-2 적용 직전 재검증은 필수.
- `image_identity_verification_status`는 검증하지 않았다면 정확히 `NOT_VERIFIED`. 이미지 Digest/DB 고유 신원을 구성·관찰값으로부터 추정하지 않는다.
- 허용된 안정 Reason Code 초안 확정값: `SETTINGS_INVALID`, `ENV_CONFLICT`, `DB_CONNECTION_FAILED`, `READ_ONLY_NOT_ESTABLISHED`, `TARGET_MISMATCH`, `SCHEMA_INDETERMINATE`, `OBSERVATION_FAILED`, `EVIDENCE_WRITE_FAILED`. Reason Code 및 `checks`에는 원본 예외·접속 URL·비밀번호·JWT·환경 변수 덤프·개인 사용자 데이터 없음.
- 프로세스 종료 코드: **0 = `OBSERVED`**(영속 기록 완료, 승인 아님), **2 = 기존 Guard 거부**(무인자/deny/apply/임의 명령; DB/파일 접근 0), **3 = `INDETERMINATE`**(보고서 저장 완료, 불일치·모호함), **4 = `ERROR`**(설정·접속·읽기·저장 실패). 저장 실패가 동반되면 0이나 3이 아닌 **4**를 우선한다.
- CLI 종료 원인은 고정 코드로만 출력하며 자격 증명이나 원본 예외를 표시하지 않는다. 유효한 관찰이나 불확실 판정이 있더라도, 보고서 기록을 완료하기 전 성공 상태를 반환하지 않는다.

### P0-D. MariaDB READ ONLY 관찰

- Migration 전용 Settings와 Secret 및 환경 충돌 검증 → 전용 SQLAlchemy Engine/새 Connection → B-2 코드의 **첫 애플리케이션 SQL**로 `START TRANSACTION READ ONLY` → 같은 Connection에서 허용된 고정 SQL로 메타데이터·Revision 관찰 → rollback 및 Connection 종료/Engine dispose → 별도 Evidence 파일 기록.
- `engine.begin()`, 사전 애플리케이션 조회, 일반 DDL/DML, `GET_LOCK`, 직접 Alembic 변경 명령을 B-2에 사용하지 않는다. 동적 SQL이나 임의 스크립트/SQL 입력 경로를 만들지 않는다.
- SQLAlchemy 2.x의 autobegin과 DBAPI·Dialect 초기화 SQL은 구별한다. 물리적 연결의 첫 SQL이라는 보장은 주장하지 않는다. 연결 해제·조회 실패 시 자동 재연결/재시도 금지; cleanup 이상이 생기면 성공 완료로 기록하지 않는다.
- 트랜잭션의 실제 쓰기 차단, 초기화 SQL, 연결 유지, 불완전 Revision과 객체 상태, rollback/close는 **승인된 별도 격리 MariaDB 12.3.x + 실제 SQLAlchemy/PyMySQL 버전**에서 시험한 뒤 검증 완료로 판정한다. B-2 정책 동결은 해당 기능의 실증 완료가 아니다.

## 7. 구현 시 변경 경계

**우선 수정:** `backend/scripts/migration_guard.py`, `backend/tests/core/test_migration_guard.py` (이전 `preflight` 거부 테스트를 새 정상 경로 테스트로 대체).  
**신규 후보:** B-2 DB 관찰 모듈, 증거 저장 모듈, 각 단위·부정 시험. 경로와 구조는 기존 패키지/테스트에 맞춰 결정.  
**참조만:** `backend/app/core/migration_db_config.py`, `backend/alembic/env.py`, `backend/alembic/versions/*`, `backend/tests/conftest.py`.  
**보존:** 기존 Runtime Settings/세션, Router/Service/Repository API, 기존 Migration Revision, 개발·테스트 Docker Compose, 데이터/스키마, AWS 자원. B-2 명령에서 직접 Alembic CLI 호출 금지.

향후 L-2가 같은 Connection으로 Alembic을 실행할 수 있도록 읽기 전용 관찰 책임을 재사용 가능하게 분리하되, **B-2 실행 중에는 Lock이나 DDL 연결을 추가하지 않는다.** 후속 사용성만을 이유로 큰 프레임워크를 만들지 않는다.

## 8. Acceptance Criteria / 테스트 계획

| ID | Given/When | Then |
|---|---|---|
| B2-01 | `preflight` 정확한 인자 | 설정·단일 읽기 관찰 경로만 실행 |
| B2-02 | 인자 없음·`deny` | 기존 `DENY_DEFAULT`, exit 2 유지 |
| B2-03 | `apply`, 임의 Alembic/쉘/추가 인자 | 기존 거부 유지, DB/네트워크 접근 0 |
| B2-04 | 필수 환경변수·Secret 누락/불량 | DB 연결 전 안전하게 거부 |
| B2-05 | Runtime URL/DB 설정의 위험한 충돌·혼입 | 우회 연결 없이 거부; 실제 차단할 환경변수 목록은 운영 배포 계약에서 검증 |
| B2-06 | 예상 DB명 불일치·인증 계정 관찰 불능 | 불확실/오류 기록, 승인으로 처리하지 않음 |
| B2-07 | 최초 후보/정상 Revision/미확인/비어 있음/다중 Revision | 상태를 구분하고 초기 후보 자동 승인 금지 |
| B2-08 | 연결·읽기 중 오류 또는 끊김 | 재연결·재시도 금지, 오류 은닉·안전 종료 |
| B2-09 | Evidence ID 중복, 기록 실패, 영속 경로 부재 | 성공 처리 금지·기존 보고서 보존 |
| B2-10 | 관찰 성공 | DDL/DML/`GET_LOCK`/Alembic 실행 0, `apply` 계속 거부 |
| B2-11 | 읽기 전용 트랜잭션 검사 | 실제 MariaDB에서 쓰기 부정 시험과 rollback/close 검증 |
| B2-12 | 비밀정보가 인자·환경·DB 예외에 포함 | 표준출력/로그/보고서에 원문 비노출 |
| B2-13 | Preflight 이후 DB 상태 변경 | 과거 Evidence를 실행 시점 상태로 신뢰하지 않음, L-2 재검증 필요 |
| B2-14 | 테스트 DB의 기존 Fixture가 Alembic 자동 업그레이드 | '빈 DB 후보' 시험은 그 Fixture를 재사용하지 않고 별도 승인된 격리 DB/볼륨 사용 |
| B2-15 | Evidence ID·중복 디렉터리·파일 선점·중단·저장 실패 | 기존 증거 불변, 임시 파일은 미완료, exit 4 우선 |
| B2-16 | 금지 환경변수 존재(빈 값 포함)·알 수 없는 MIGRATION_DB_* | 사전 거부, 원문 비노출, DB 접속 0 |
| B2-17 | OBSERVED / INDETERMINATE / ERROR, 초기 빈 DB 후보 | JSON v1 필드와 exit 0/3/4 일치, 운영 승인 0건 |
| B2-18 | READ ONLY 시작 전 SQL·재연결·정리 실패 주입 | 검사 차단/실패, 쓰기 0 및 자동 재시도 0 |

**테스트 단계:** (1) Guard CLI Red/Green 및 단위·계약 테스트, (2) 로컬 기존 핵심 테스트/정적 검사 및 영향 범위 회귀, (3) 별도 승인된 격리 MariaDB에서 실제 READ ONLY·Revision 상태·보고서 부정 시험, (4) Docker/운영 Compose 및 AWS 통합은 후속 단계. 기존 통과 기록을 최신 HEAD의 새 실행으로 둔갑시키지 않는다.

## 9. 단계 완료와 잔여 Gate

- **설계 동결 완료(2026-11-14):** P0-A~D 및 사용자 선택 A+A를 **B-2 POLICY FROZEN**으로 확정. 운영 실제 호스트 경로·UID/GID·드라이버 시험 결과는 환경 배치·격리 검증 Gate에 남긴다. FROZEN은 구현·PASS·배포 승인과 다르다.
- **B-2 구현 완료:** 허용 경로와 모든 Fail-Closed 테스트, 비밀정보 보호, 보고서 영속성, 기존 거부 정책 회귀 검증.
- **B-2 실제 검증 완료:** 격리 MariaDB에서 DB 무변경·READ ONLY 및 빈/기존 Revision 시험 PASS 증거.
- **운영 Migration 승인:** B-3 승인 Manifest, L-2 동일 Connection Lock/재검증, 최소 권한, 백업/빈 DB 증거, 운영 Compose·AWS 공개 Gate 모두 별도 필요.
- **서비스 배포 완료:** HTTPS API + Android APK 실기기 인증·관심사·트렌드 조회 확인 등은 이 작업과 별도이다.

## 10. 구현 시 반드시 참조할 1차 자료

- MariaDB `START TRANSACTION`: https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction
- MariaDB implicit commit: https://mariadb.com/docs/server/reference/sql-statements/transactions/sql-statements-that-cause-an-implicit-commit
- SQLAlchemy 2.0 Connection/autobegin: https://docs.sqlalchemy.org/en/20/core/connections.html
- Alembic Runtime `MigrationContext.get_current_heads()`: https://alembic.sqlalchemy.org/en/latest/api/runtime.html
- Python 파일 원자적 게시·동기화: https://docs.python.org/3/library/os.html#os.replace
- 소스 저장소 `dev`의 Guard/Settings/Alembic env/테스트 Fixture와 M-A1 FROZEN v1.0을 기준으로 재검증한다.
