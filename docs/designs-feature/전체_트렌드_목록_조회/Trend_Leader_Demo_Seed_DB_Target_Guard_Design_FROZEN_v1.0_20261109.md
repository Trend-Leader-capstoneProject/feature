# Trend Leader — Demo Seed 실제 DB 대상 검증 가드 보강 설계 확정안 v1.0

> **상태:** FROZEN — 설계 확정 / 구현·검증 미실시  
> **확정 기준일:** 2026-11-09 (Asia/Seoul)  
> **대상 Repository:** `Trend-Leader-capstoneProject/feature`  
> **기준 브랜치:** 원격 `dev`  
> **조회 시점 HEAD:** `1e98b59cd9762971686facb866ce13288b363651`  
> **문서 범위:** Demo Trend Seed의 DML 이전 DB 실행 대상 검증 가드  
> **구현 상태:** 설계만 확정. Demo Seed 가드 코드 수정·실제 DB 검증·테스트는 별도 구현 단계에서 수행.

## 1. 설계 목적 및 위험 정의

기존 Demo Seed는 `seed_demo_trends(db_session, *, app_env)`의 `local` 검사만으로 시작을 허용한다. `Settings.sync_database_url`은 `DATABASE_URL`이 있으면 개별 `DB_*` 값보다 우선하며, `SessionLocal`은 해당 값으로 만든 Engine에 바인딩된다. 따라서 `APP_ENV=local`만으로 실제 MariaDB 서버·데이터베이스·인증 계정이 승인된 대상이라는 사실을 보장하지 않는다.

**목표 불변조건:** 승인되지 않았거나 신뢰할 수 있게 식별되지 않은 연결에서는 **Demo Seed가 유발하는 첫 DML 이전에** 실패한다. 일반적인 설정 실수에 대한 방어이며, 운영 DB 오염 사고가 실제로 발생했다는 주장은 아니다.

- **Goal:** 승인된 Windows 호스트 CLI의 로컬 개발 DB, 그리고 승인된 격리 MariaDB 테스트 DB에서만 실행한다. 비허용 대상·설정 누락·식별 조회 실패 시 Fail Closed한다. 인증정보를 출력하지 않는다.
- **Non-Goal:** 운영·배포 환경의 전반적인 보안 인증, 악의적 관리자·설정 변조 방어, 서버의 암호학적 신원 증명, 임의의 이전 DB 작업 보호, Category Master Seed 보강, 테스트용 Alembic 실행 가드 전체 개편.
- **실행 환경:** Windows PowerShell에서 `backend/`의 `python -m scripts.seed_demo_trends`를 사용한다. Docker **컨테이너 내부에서 CLI를 직접 실행하는 경로는 지원·Acceptance 대상이 아니며 후속으로 분리**한다. 해당 경로가 자동으로 허용되지는 않는다.

## 2. 기준 자료와 충돌 처리

1. 이 채팅에서 확정한 Goal·Non-Goal·Phase 2/3 결정과 본 설계 계약.
2. `docs/designs-feature/전체_트렌드_목록_조회/Trend_Leader_전체_트렌드_목록_조회_설계_확정안_v1.0.14.md` §12.1, §13 (기존 Demo 데이터·Seed 동작).
3. `docs/designs-feature/관심사 분류/Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.1.md` (Category Master·매핑).
4. `AGENTS.md`, `docs/prompt/Trend_Leader_AI_Development_Guidelines.md` (공통 실행 지침).
5. `docs/onboarding/Trend_Leader_Windows_Developer_Onboarding_Guide_v1.0.md` (Windows 호스트, 관리용·API 실행용 계정 분리, 테스트 DB 운영 절차; **팀 배포용 초안**).
6. 현재 대상 HEAD의 실제 코드·테스트. `design/docs/DB/schema_decisions_v2.1.md`는 **Working Update**이며 과거 `schema_decisions.md`의 구식 Category 글로벌 UNIQUE나 대표 카테고리 사용 규칙을 복원하지 않는다.

**계약 충돌 여부:** 기존 `local` 전용이라는 규칙을 폐기하지 않고 추가 검증을 강화한다. 변경된 것은 **실행 허가 조건 및 호출부의 승인 정보 전달 계약**이다. Trend/Source/Category 데이터 생성 규칙, HTTP API 계약, Schema와 Migration은 불변.

기준 코드 확인 경로:
- `backend/scripts/seed_demo_trends.py`: `get_settings()` → `SessionLocal()` → `seed_demo_trends(..., app_env=...)`.
- `backend/app/db/seeds/demo_trends.py`: 기존 환경 검사 후 Category 조회, 기존 Demo 검증·신규 INSERT, 마지막 `commit()`/예외 시 `rollback()`.
- `backend/app/core/config.py`: 기본 `app_env='local'`, `database_url` 우선.
- `backend/app/db/session.py`: 모듈 수준 Engine과 `SessionLocal(autoflush=False, expire_on_commit=False)`.
- `backend/tests/conftest.py`: `TEST_DATABASE_URL`의 DB 이름 `trend_leader_test` 검사 → **그 후 Alembic `upgrade head`** → 별도 DB Engine·외부 Transaction·`join_transaction_mode='create_savepoint'`.
- `backend/tests/db/seeds/test_demo_trends.py`, `backend/tests/api/test_trend_demo_seed_integration.py`: CLI 없이 Seed 함수를 직접 호출.

**유의:** HEAD는 설계 시점의 근거이지 구현 시점의 최신 상태가 아니다. Codex 구현 시작 시 원격 `dev` HEAD·작업 트리·관련 파일을 재조회한다.

## 3. Design Rationale: 가드의 책임 위치

| 후보 | 장점 | 한계 | 결정 |
| --- | --- | --- | --- |
| A. CLI 전용 검사 (`scripts/seed_demo_trends.py`) | 파일 변경량이 작음 | 기존 직접 호출(통합 테스트 등)은 CLI 검사를 우회 | **미채택** |
| B. Seed 실행 경계 검사 (`app/db/seeds/demo_trends.py`) | CLI·직접 호출에 공통 강제, 기존 업무 규칙과 같은 실행 허가 경계 | 승인 정보 전달 및 테스트 보강 필요 | **채택** |

**최소 구현 원칙:** Demo Seed 전용 작은 가드로 제한한다. 범용 DB 보안 프레임워크, Service/Repository 신규 계층, 별도 승인 DB 테이블, 외부 비밀관리 시스템, 새 라이브러리, Schema Migration을 추가하지 않는다. CLI는 설정 해석·안전한 오류 출력만 소유하고, **실행 허가 판정은 Seed 함수가 소유**한다.

## 4. 승인 대상 설정 계약 — 신규 항목

아래 항목은 **현행 코드에 없는 신규 설계 계약**이다. 구현 전 존재한다고 가정하지 않는다. 명칭은 본 v1.0에서 구현 시 사용할 이름으로 정한다.

| 신규 설정 키 | 타입·필수 조건 | 의미 |
| --- | --- | --- |
| `DEMO_SEED_ALLOWED_HOST` | 실행 시 비어 있지 않은 문자열 | 승인된 **Windows 호스트에서 접근할** TCP 접속 Host |
| `DEMO_SEED_ALLOWED_PORT` | 실행 시 명시적 1~65535 정수 | 승인된 접속 Port |
| `DEMO_SEED_ALLOWED_DATABASE` | 실행 시 비어 있지 않은 문자열 | 승인된 DB 이름 |
| `DEMO_SEED_ALLOWED_CURRENT_USER` | 실행 시 비어 있지 않은 `user@host` 전체 문자열 | MariaDB `CURRENT_USER()`와 정확히 비교할 기대 인증 계정 |

- 네 항목에는 **실행 가능한 기본 승인값을 두지 않는다**. 일반 API 시작에 이 값들을 필수 요구하지 않도록 미설정 상태를 허용하지만, **Demo Seed 시 미설정·미완성·잘못된 타입·잘못된 포트는 차단**한다. Pydantic Settings 검증 오류도 비밀정보를 포함하지 않도록 CLI에서 출력 방어한다.
- 팀원별 실제 Host·Port·DB·계정은 각자 승인된 로컬/격리 환경에 맞춰 입력한다. 특정 개인 PC 주소·계정·포트를 코드나 FROZEN 정책에 고정하지 않는다.
- 실제 접속용 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DATABASE_URL`을 **승인 기대값으로 자동 복사하지 않는다**. `DATABASE_URL`의 URL 구문에서 추출한 값을 승인 설정으로 사용하는 자기 승인도 금지한다.
- 현재 `DATABASE_URL` 우선순위를 변경하지 않는다. **실제 Session 바인딩의 Engine URL**이 비교 대상이며, `DB_*` 값과의 일치를 강제하지 않는다.
- 승인 프로필은 **한 실행에 대상 1개**다. 로컬 개발 DB와 테스트 DB를 한 번에 OR 허용하는 전역 목록을 만들지 않는다. 테스트 실행 시에는 승인된 테스트 DB에 맞는 **별도 기대값을 명시**한다.
- `localhost`와 `127.0.0.1`을 자동으로 동치로 보거나 DNS를 재해석해 우회 허용하지 않는다. Host 비교의 기본은 설정에서 명시한 리터럴 Host와 URL Host의 일치다. IPv6·유닉스 소켓·다중 Host·공유/원격 DB 등 현재 범위가 아닌 연결 형식은 정확히 판별·승인할 수 없으면 차단한다.
- `.env.example`, `backend/.env.test.example`, Windows 온보딩 가이드에는 **비밀번호·실제 접속정보가 없는 입력 안내**만 추가한다. 실제 `.env`/`.env.test`는 커밋하지 않는다.

## 5. 검증 계약: 필수 조건 및 순서

**전제:** 신규 가드는 Seed의 Category 조회·`add()`·`flush()`·`commit()` 및 다른 Seed DML에 앞서 실행한다. 전체 판정은 **모든 항목 AND**이다.

1. **비접속 사전 검사:** `app_env.strip().lower() == 'local'`, 승인 설정 네 값의 완전성·유효성을 검사한다. 부적합하면 DB 연결을 열지 않고 실패한다.
2. **Session 유효성:** 전달된 Session에 미반영 변경(`new`, `dirty`, `deleted`)이 있다면 실패한다. 이는 가드 전 자동 Flush와 Seed의 마지막 Commit으로 호출자의 pending 변경이 함께 반영되는 위험을 줄이려는 제한이다. 임의로 이미 Flush된 외부 DML까지 소급 판별한다는 뜻은 아니다.
3. **단일 DB 바인딩:** Seed가 사용하는 `Category`, `Trend`, `TrendCategoryMap`, `TrendSource`의 ORM 경로와 검증 연결이 **동일한 바인딩 및 Connection**에서 실행됨을 보장한다. Session이 unbound이거나 다중 바인딩·라우팅으로 일치성을 입증할 수 없다면 실패한다. 현재 `SessionLocal`(Engine bind)과 테스트의 `Session(bind=Connection)` 모두 지원해야 한다.
4. **접속 목적지 비교:** Seed 작업에 사용될 연결의 **Engine URL**에서 Host·Port를 확인한다. 둘 중 하나라도 비어 있거나 비표준/모호한 접속 경로라 판별 불가하면 거절한다. 기대 Host·Port와 정확히 일치해야 한다. 가능하면 URL의 DB 이름도 승인 기대 DB와 함께 일치하도록 검사한다.
5. **실제 MariaDB 인증·DB 검증:** 같은 Session 트랜잭션에 귀속된 동일 Connection으로 읽기 전용 SQL `SELECT DATABASE() AS db_name, CURRENT_USER() AS authenticated_user`를 실행한다. 반환된 DB 이름 및 인증 계정 **전체 문자열**을 각각 승인 기대값과 비교한다. 빈 값·NULL·조회 실패·불일치 모두 거절한다. `USER()`는 인증 계정 비교에 사용하지 않는다.
6. **실행 허가:** 모두 통과한 경우에만 기존 Demo Seed 로직으로 진입한다. 성공 시 기존 Commit, 실패 시 기존 Rollback을 유지한다. 검증 후 연결 유실·교체·재연결 상황에 이전 판정값을 재사용해서는 안 된다. 안전하게 동일 연결임을 유지할 수 없다면 중단한다.

**동일 연결 계약이 중요한 이유:** 별도 Engine/Session으로 먼저 검사하고 실제 Seed는 다른 Session에 실행한다면 TOCTOU(검증 대상과 실행 대상 불일치) 위험이 생긴다. SQLAlchemy `Session.connection()`과 실제 Seed ORM 바인딩의 연결·트랜잭션 동일성을 검증한다. DB 식별 확인은 ORM 객체의 변경을 Flush하지 않는 **Connection 수준의 읽기 전용 SQL**로 수행한다.

**서버 정체성 보장 한계:** URL Host·Port는 클라이언트가 의도한 접속 목적지다. `DATABASE()`·`CURRENT_USER()`는 연결된 서버가 보고하는 값이다. 동일 주소 뒤의 서버 교체, 포트 포워딩, 프록시, 악의적으로 위조한 서버까지 암호학적으로 구별하지는 않는다. 따라서 이 계약은 **승인 설정과 실제 연결의 일반적인 오설정을 차단하는 실용적인 개발 안전장치**이며, 서버 인증서 검증/TLS pinning은 후속 영역이다. `@@hostname`·`@@port`를 강제 비교하지 않는다(Docker 내부 포트·동적 Hostname과 불일치 가능).

## 6. Transaction·오류·로그 정책

- 기존 성공 `db_session.commit()` 및 오류 `db_session.rollback()` 책임은 Seed 함수에 남긴다. **가드 실패도 Seed의 오류 처리 범위에 포함**해 시작된 Session Transaction을 정리한다. 반면 검증 실패가 이미 수행된 타인의 DML을 전부 보호한다고 표현하지 않는다.
- 기존 CLI는 새 Session으로 시작해야 한다. 호출자는 **Seed 전용의 깨끗한 Session** 또는 기존 외부 Transaction/SAVEPOINT에 격리된 테스트 Session만 전달한다. 같은 Session에서 앞서 직접 실행한 DML을 임의로 남긴 상태는 승인 운영 시나리오가 아니다. 자동 테스트의 사전 Fixture 데이터 작성은 외부 격리 Transaction의 보호 범위를 명확히 유지한다.
- 가드 자체는 `add`·`flush`·`commit`·DML·DDL·Migration을 수행하지 않는다. 비허용 환경은 가능한 한 DB checkout 이전에 중단한다.
- `DemoTrendSeedError`를 기존 Seed 실패 유형으로 유지할 수 있다. 필요하다면 구별 가능한 **비밀정보 없는 내부 실패 코드**를 추가한다. 임의로 HTTP 상태 코드나 API Schema에 매핑하지 않는다.
- CLI에서는 설정 로딩, `app.db.session` 모듈 import 및 Engine 초기화, DB checkout, Seed 수행에서 발생 가능한 오류를 안전한 출력 경계로 감싼다. **현재 CLI의 최상위 `SessionLocal` import만 남겨 두면 예외가 `main()`의 방어 전에 발생할 수 있으므로 이동/처리 여부를 검토**한다.
- 오류 출력·로깅·테스트 실패 메시지에는 DB password, URL 원문, 연결 문자열, 인증 토큰, 비밀 키, 비밀정보를 포함할 수 있는 SQLAlchemy/DBAPI 원본 예외 문자열을 그대로 출력하지 않는다. 예기치 못한 오류도 CLI는 비밀정보 없는 일반 메시지와 비정상 종료 코드로 알린다. 성공 메시지는 성공 시에만 표시한다.
- 승인 기대값과 실제 인증 계정이 불일치해도 전체 연결 URL/계정 비밀번호를 노출하지 않는다. 디버깅 정보는 실패 단계·안전한 오류 분류 정도로 제한한다.

## 7. 보존해야 할 기존 데이터 계약

아래는 **이번 변경 금지 대상**이다.

- ACTIVE Demo Trend **25건** + HIDDEN Demo Trend **1건**. 기존 Source **29건**.
- 정확한 `normalized_title`: `demo-trend-list-001`~`025`, `demo-trend-list-hidden-001`. prefix 일괄 삭제·정리 금지.
- 기존 `DEMO_TOPICS`, 날짜·정렬 tie-break, nullable `summary`·`thumbnail_url`·`source_title`, Source URL/키/Platform/시각 및 Source 수, Category mapping, UTC-naive 저장 값 불변.
- Category Master 사전 존재 필수. Category 대분류 code + 부모 문맥의 세부분류 이름 식별. 임의 Category 생성 없음.
- 동일 Demo 재실행 시 기존 Trend·Mapping·Source 정확성 검증, drift면 실패. 중복 INSERT 없음.
- 비-Demo 데이터의 변경·삭제 없음.
- API `GET /api/trends` 20+5 Cursor, 개인화 목록 계약, Frontend/Expo·Router·Schema 변경 없음.

## 8. Acceptance Criteria (구현 후 검증, 현재 미실행)

| ID | Given / When | Then | 수준 |
| --- | --- | --- | --- |
| AC-01 | `APP_ENV=local`, 승인값 완비, 실제 Host·Port·`DATABASE()`·`CURRENT_USER()` 일치 | 정상 Seed 처리 | 단위 + 격리 MariaDB 통합 |
| AC-02 | `APP_ENV=production` 및 기타 비허용값 | DB checkout와 Seed DML 없이 실패 | 단위 |
| AC-03 | `local`이나 `DATABASE_URL`이 다른 Host/Port/DB를 가리킴 | URL 우선 결과 기준으로 DML 없이 실패 | 단위(가짜 대상), 필요 시 격리 DB 통합 |
| AC-04 | 동일 DB 이름이나 승인 Host·Port 불일치 | 실패, DML 0 | 단위 |
| AC-05 | 실제 `DATABASE()` 결과가 승인 DB와 다름/NULL | 실패, DML 0 | 단위/격리 통합 |
| AC-06 | 실제 `CURRENT_USER()` 전체값이 불일치/NULL | 실패, DML 0 | 단위/격리 통합 |
| AC-07 | 승인 키 누락·빈값·잘못된 포트 또는 식별 SQL 예외 | Fail Closed, DML 0, 안전한 오류 | 단위 |
| AC-08 | Session unbound/다중 bind 불명확/검증 연결과 DML 연결 불일치 또는 pending ORM 변경 | 실패, 기존 DML 유발하지 않음 | 단위/구성 테스트 |
| AC-09 | 가드 실패, Seed 중간 INSERT 실패 | 각각 DML 사전 차단 또는 전체 Rollback; 사전 데이터 보존 | SQL 이벤트 단위 + 격리 MariaDB 통합 |
| AC-10 | 승인된 격리 DB에 Category Master 후 1·2차 실행 | ACTIVE 25/HIDDEN 1/Source 29, 중복 생성 없음 | 기존 Seed 통합 회귀 |
| AC-11 | 기존 동일 Demo의 일부 값 변경·Source/Mapping drift | 오류, 해당 Seed 실행의 부분 변경 Rollback | 격리 MariaDB 통합 |
| AC-12 | 비-Demo Trend 존재 | 생성·재실행·실패에서도 비-Demo 원본 보존 | 격리 MariaDB 통합 |
| AC-13 | 승인된 테스트 Session이 `Connection`에 바인딩되고 외부 Transaction/SAVEPOINT를 사용 | 가드 검증·Seed DML 연결이 같고 Fixture rollback 격리 유지 | 통합 |
| AC-14 | 기존 Demo로 조회 API 호출 | 전체 목록 20+5·HIDDEN 제외 및 기존 개인화 API 계약 불변 | 기존 통합 회귀 |
| AC-15 | 잘못된 URL/접속·설정 에러·DB 오류 발생 | 출력에 URL 원문·패스워드·원시 DBAPI 예외 없음, 비정상 종료 | CLI 단위 |

**DML 이전 차단 증명:** 거절 시나리오에서 Seed 호출 **시작 이후** SQLAlchemy 이벤트/스파이로 INSERT·UPDATE·DELETE·DDL 및 Flush/Commit이 실행되지 않았음을 확인한다. 허용되는 동작은 식별 목적의 읽기 전용 SQL과 필요한 Rollback이다. 기존 데이터가 없는지 확인하는 카운트만으로 `DML 0`을 입증했다고 판단하지 않는다.

**테스트 DB 사전 안전 절차:** 기존 `backend/tests/conftest.py`는 `TEST_DATABASE_URL`의 DB 이름만 검사한 후 **Alembic `upgrade head`를 실행**한다. 이 Migration은 Demo Seed 가드가 보호하지 않는다. 따라서 실제 MariaDB 테스트 실행 전에 관리자가 별도로 격리 DB의 Host·Port·DB·인증 계정·데이터 삭제 가능성을 승인한 상태여야 한다. 테스트 URL로부터 승인 기대값을 자동 만들어 자기 승인하지 않는다. 테스트 환경 이관 및 Migration 자체의 별도 자동 가드 보강은 독립 후속 과제다. **운영·공유 DB를 테스트 대상으로 사용하지 않는다.**

## 9. 구현 영향 범위 (최소 변경)

| 대상 | 예상 책임 |
| --- | --- |
| `backend/app/core/config.py` | 4개 신규 승인 설정 필드; 일반 앱 실행 미설정 허용, Seed에서 필수 검사 |
| `backend/scripts/seed_demo_trends.py` | 설정에서 독립 승인값 전달, 오류/초기화 시 안전한 CLI 출력·종료 |
| `backend/app/db/seeds/demo_trends.py` | 기존 Seed 진입점에서 가드 강제 및 예외·Transaction 연결 |
| `backend/tests/db/seeds/test_demo_trends.py` | 기존 직접 호출에 승인된 테스트 값 전달, 거절·보존·멱등성 회귀 |
| `backend/tests/api/test_trend_demo_seed_integration.py` | 테스트 Session 직접 호출에서 승인 전달 및 20+5 유지 |
| `backend/tests/conftest.py` | 필요한 최소한의 독립 승인 Test Fixture; Migration 가드 전면 재설계 금지 |
| `backend/.env.example`, `backend/.env.test.example`, Windows 온보딩 가이드 | 새로운 설정의 목적·승인 절차·테스트 격리 안내 |

신규 공통 파일·전용 데이터 타입이 실제 책임 분리를 돕는 경우 작은 내부 구조를 사용할 수 있으나, **파일명·클래스명·함수 시그니처는 이 문서가 존재한다고 주장하지 않는다.** 기존 `seed_demo_trends()`의 인자 변경이 필요하며, 승인값 생략을 성공 경로로 허용하지 않는다. 변경은 관련 파일에 국한하고 기존 caller 전체를 검색해 갱신한다.

## 10. 구현 순서 및 종료 조건

1. 구현 시작 전 최신 원격 `dev`/작업 트리/관련 파일·버전·caller·FROZEN 충돌 확인.
2. 현행 Seed/테스트 특성 테스트로 기존 동작 고정. 승인 정책 경계·Fail Closed 단위 테스트 작성(Red).
3. 승인 설정 및 Seed 경계 가드 최소 구현(Green). 동일 연결 검사·비밀정보 차단 포함.
4. 기존 직접 caller와 통합 테스트 Fixture를 최소 수정. 잘못된 연결 테스트는 Mock/가짜 Connection으로 시행; 운영 DB 직접 접속 테스트 금지.
5. **명시 승인한 격리 MariaDB**에서 DML 0·Rollback·idempotency·비-Demo 보존·20+5 회귀, Ruff와 필요한 범위의 Backend 회귀를 확인.
6. 변경 diff, URL·비밀번호 로그, `.env` 노출, 불필요한 범위 확장 점검. **Codex 구현 작업의** 커밋/Push/PR/원격 문서 수정은 별도 승인 전 금지. 이 설계 문서의 GitHub 게시 승인이 구현 원격 쓰기 승인으로 확장되지 않는다.

**완료 판정:** AC-01~AC-15에 해당하는 관련 증거가 확보되고, 기존 Seed/API 계약과 diff가 일치하며, 실 DB 검증은 승인된 격리 환경에서만 수행했고, 오류 출력에 비밀정보가 없으며, 미실행 검증을 PASS라고 하지 않았을 때에만 구현 완료·검증 완료를 따로 판정한다.

## 11. 후속 과제·수용 한계

- Docker 컨테이너 내부에서 명시 실행하는 CLI 경로의 별도 승인 정책과 네트워크 주소 계약.
- `backend/tests/conftest.py`의 Alembic Migration 포함 테스트 DB 가드 전면 보강.
- 실제 관리용 DB 계정 권한 정책(C3 문서, `SHOW GRANTS` 등)의 승인 원본 확보·검증. 이번 검토에서 **C3 FROZEN 원본과 실제 GRANT는 검증되지 않았음**. 기존 Windows 가이드의 관리용/API 전용 계정 분리를 존중하며 권한을 자동 확대하지 않는다.
- TLS 서버 인증, DNS/프록시/터널 오연결 방어, 중앙 승인 정책, 다른 Seeder/Writer까지의 범용화.
- 기존 Demo 데이터/Category Master 정책, G4/G5/G6, P4 Writer/Phase 4B 등의 별도 설계는 건드리지 않는다.

## 12. 읽기 자료 (구현 시 재확인)

- SQLAlchemy 2.0 Session API: https://docs.sqlalchemy.org/en/20/orm/session_api.html (`Session.connection`, `Session.get_bind`, `commit`, `join_transaction_mode`)
- SQLAlchemy 2.0 Session Basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html (Autoflush, Flush/Commit, Rollback)
- MariaDB `CURRENT_USER()`: https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/information-functions/current_user
- MariaDB `DATABASE()`: https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/information-functions/database

---

**문서 상태:** FROZEN 설계 기준. GitHub 문서 게시와 Demo Seed 구현·검증·DB 쓰기는 별개이며, Codex 구현 작업의 원격 코드 변경·커밋·Push·PR은 별도 사용자 승인을 따른다.