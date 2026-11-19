# Codex 구현 채팅 시작 프롬프트 — Demo Seed 실제 DB 대상 검증 가드 보강

> **용도:** Trend Leader 기능별 분리 기준의 **별도 구현 채팅**에 복사하여 사용.  
> **설계 기준:** 원격 `dev`의 `docs/designs-feature/전체_트렌드_목록_조회/Trend_Leader_Demo_Seed_DB_Target_Guard_Design_FROZEN_v1.0_20261109.md` (FROZEN 확정안).

---

같은 Trend Leader 프로젝트의 `채팅 기능별 구분 방법` 채팅에서 정리한 **기능별 채팅 분리 기준**을 적용해주세요.

이번 채팅은 **`Demo Seed 실제 DB 대상 검증 가드 보강 구현`** 채팅입니다.

## 0. 작업 전제

원격 `dev`에서 **`docs/designs-feature/전체_트렌드_목록_조회/Trend_Leader_Demo_Seed_DB_Target_Guard_Design_FROZEN_v1.0_20261109.md`**를 먼저 읽고 이번 기능의 최우선 구현 계약으로 사용해주세요. 첨부된 사본이 있으면 원격 최신본과 비교하세요. 해당 FROZEN 원문을 읽을 수 없다면 구현을 시작하지 말고 사용자에게 파일을 요청하세요. 기억으로 재구성하여 구현하지 마세요.

2026-11-09 설계 확인 당시 원격 `dev` HEAD는 `1e98b59cd9762971686facb866ce13288b363651`였습니다. **이 SHA는 참고값입니다.** 구현 채팅 시작 시 원격 `dev` 최신 HEAD와 로컬 브랜치/작업 트리 변경 내역을 다시 확인하고, 실제 코드를 최종 근거로 삼아주세요. GitHub의 파일 내용과 사용자 로컬 작업 트리는 다를 수 있습니다.

우선 확인 파일:

- `AGENTS.md`
- `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`
- `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md` (GitHub 쓰기가 별도 승인된 경우)
- `backend/scripts/seed_demo_trends.py`
- `backend/app/db/seeds/demo_trends.py`
- `backend/app/db/session.py`
- `backend/app/core/config.py`
- `backend/tests/db/seeds/test_demo_trends.py`
- `backend/tests/api/test_trend_demo_seed_integration.py`
- `backend/tests/conftest.py`
- `backend/.env.example`, `backend/.env.test.example`
- `docs/onboarding/Trend_Leader_Windows_Developer_Onboarding_Guide_v1.0.md`
- 전체 트렌드 목록 조회 FROZEN 확정안 v1.0.14 §12.1·§13
- Category Taxonomy v1.0.1 확정안 및 현재 필요한 DB 권한 정책 문서

## 1. 구현 목표

Demo Trend Seed가 승인되지 않은 MariaDB 접속 목적지·DB·인증 계정에서 실행되는 것을 **첫 번째 Seed DML 이전에 Fail Closed**하도록 보강합니다. `APP_ENV=local`만으로 허용하지 않습니다. 별도 Codex 구현 작업이므로 **이번 채팅에서는 설계 재논쟁보다 확정안 구현과 실패 경로 검증을 우선**합니다.

- 실행 환경: **Windows 호스트 Python CLI + 명시 승인된 격리 MariaDB 테스트 DB**.
- Docker 컨테이너 안에서 CLI를 직접 실행하는 경로는 후속 범위. 그 경로에 우회 허용을 만들지 마세요.
- 가드 소유 위치: `seed_demo_trends()` 자체의 실행 경계(**CLI 전용 가드 아님**).
- 검증 조건: 기존 `APP_ENV=local` + 독립 승인 설정 + 실제 Seed Session의 Host·Port + 같은 연결에서 `DATABASE()`와 `CURRENT_USER()`.
- 모든 필수 정보 누락/불일치/조회 실패/다중 bind 불확실/검증 연결 불일치 → DML 없이 차단.
- 승인 설정 4개는 확정안에 명시된 **신규 키**이며 현행 코드에 존재한다고 간주하지 마세요: `DEMO_SEED_ALLOWED_HOST`, `DEMO_SEED_ALLOWED_PORT`, `DEMO_SEED_ALLOWED_DATABASE`, `DEMO_SEED_ALLOWED_CURRENT_USER`.
- 이 설정은 실제 DB 접속 URL이나 `DB_*`에서 자동 생성하지 않고 별도로 승인된 기대값을 사용합니다. API 일반 실행에서 미설정은 가능하나 Seed 실행 시에는 필수입니다.

## 2. 우선적으로 피할 설계 오류

1. **CLI에서만 검증하고 Seed 함수를 직접 호출하면 우회되는 구조**는 허용하지 않습니다.
2. `DATABASE_URL`이 있으면 `DB_*`보다 우선하므로, 사전 검사에서 `DB_HOST`/`DB_PORT`만 확인한 것으로 완료하지 마세요. Seed에 전달된 Session의 **실제 바인딩 Engine URL**을 확인하세요.
3. 별도 임시 Engine/Session에서 검사하고 다른 Session에 Seed를 실행하지 마세요. Session의 현재 트랜잭션 연결과 ORM DML 연결이 같아야 합니다. `Session(bind=Engine)`와 `Session(bind=Connection)` 및 테스트 `create_savepoint`를 구분하세요.
4. 검증 도중 자동 Flush가 일어나면 DML 전 차단 계약이 깨집니다. 미반영 pending ORM 변경 여부와 Connection 수준 읽기 전용 조회를 고려하세요. 과거에 이미 Flush된 타 호출자의 DML까지 검증한다고 과장하지 마세요.
5. CLI 초기 import/Engine 생성 및 Settings Validation의 오류가 무방비 상태로 노출되는 경로도 점검하세요. 비밀번호/URL 원문/원시 SQLAlchemy·DBAPI 예외를 출력하지 마세요.
6. 관리용 DB 계정과 FastAPI API 전용 계정을 혼동하지 마세요. 임의 GRANT 확대, root 권한 부여, 테스트 목적으로 운영/공유 DB 사용은 금지합니다.

## 3. 보존 계약

기존 Demo 데이터와 Seed 규칙은 그대로 유지합니다.

- ACTIVE 25 + HIDDEN 1, Source 29.
- `demo-trend-list-001`~`025`, `demo-trend-list-hidden-001` 정확한 식별자.
- 기존 Category Master 참조, Source/Category Mapping, nullable 경계, UTC-naive 시각과 정렬 tie-break.
- 동일 데이터 재실행 멱등성, drift 시 실패, 비-Demo 보존, 정상 Commit/오류 Rollback.
- 전체 목록 20+5 Cursor API, 개인화 목록, Router/Schema/Frontend 계약 변경 금지.

## 4. 권장 작업 순서

### Phase I — 현행 확인

- 원격 최신 `dev`/작업 트리/파일 SHA 및 실제 호출부 확인.
- 새 설정이 없다는 점, 현재 Seed 가드·트랜잭션·Fixture·Docker/Windows 구성을 코드로 재검증.
- 이미 존재하는 기능별 FROZEN 설계와 충돌 여부 보고. 특정 함수·타입·설정은 실제 파일을 보지 않고 추측 생성하지 않기.

### Phase II — 테스트 우선

- 기존 테스트를 통해 데이터 생성/멱등성·Rollback/20+5 계약을 고정.
- 비허용 `APP_ENV`, 잘못된 `DATABASE_URL`, 잘못된 Host/Port/DB, 잘못된 `CURRENT_USER`, 조회 오류, 승인 설정 누락, Session 바인딩 불확실, pending 변경, 로그 정보 노출에 대해 Fail Closed 테스트 작성.
- **거절되는 호출 이후 데이터 개수만 확인하는 것으로 DML 0을 증명하지 말고**, Seed 호출 경계 이후 DML/Flush/Commit을 이벤트/스파이 등으로 관측.
- 운영 DB나 실제 비승인 서버에 접속해 실패를 재현하지 말고 모의 연결과 격리 테스트 DB 사용.

### Phase III — 최소 구현

- `config.py`: 신규 승인 설정. 서버 일반 실행은 기존대로 유지.
- `demo_trends.py`: 단일 Seed 진입 경계의 검증과 기존 예외/Transaction 구조의 조화.
- `scripts/seed_demo_trends.py`: 설정 해석·전달, 초기 import부터 안전한 오류 경계, 비밀정보 없는 종료 메시지.
- 기존 직접 호출 테스트·필요한 Fixture·예시 설정·Windows 온보딩 문서 최소 수정.
- 다른 Seeder·Migration·Schema·API·Frontend·P4 Writer는 수정하지 않기.

### Phase IV — 검증 및 인수인계

- FROZEN의 AC-01~AC-15를 체크하며 PASS/FAIL/미실행 분리.
- 실제 격리 MariaDB 테스트 실행 전 승인 대상(Host/Port/DB/인증 계정)을 별도 확인. `conftest.py`는 **Demo Seed보다 먼저 Alembic upgrade를 수행**하므로 테스트 DB 이름 검사만 믿고 무조건 pytest를 실행하지 마세요.
- Windows PowerShell 명령어를 제공하고, Bash 줄 연속 문법을 섞지 마세요.
- 관련 테스트, 필요 범위 전체 회귀, Ruff, `git diff`/예상 외 파일 변경 확인.
- 테스트가 수행되지 않았다면 결과를 PASS로 표현하지 마세요.

## 5. 안전 및 GitHub 정책

- 기존 사용자 변경·미추적 `docs/infra/`·실제 `.env`·`.env.test`와 비밀값을 보존합니다.
- DB 실행/쓰기, Migration, Volume 삭제/재설정, 운영 DB 연결, GRANT 변경은 명시 승인 없이 하지 마세요. **테스트 코드 작성은 가능하더라도 실제 DB 통합 테스트는 격리 대상 승인을 확인한 후 수행**하세요.
- 구현 채팅에서 코드 변경 자체가 허용되더라도 **커밋·Push·PR·원격 문서 변경은 별도 사용자 승인 전 금지**합니다.
- GitHub Contents API 쓰기가 허용되면 최신 SHA 재조회, Patch-first, 충돌 검증 등 저장소 Write Safety Policy 준수.
- 문제가 있으면 단정하거나 임의로 대규모 설계를 확장하지 말고 해당 근거/영향과 최소 대안만 제시하세요.

## 6. 완료 보고 형식

1. 기준 브랜치/HEAD/작업 트리 확인 내역.
2. 변경 파일과 가드 책임·Session 연결 동일성·인증정보 차단 방법.
3. Acceptance Criteria별 테스트 결과(실제로 실행한 명령, PASS/FAIL/미실행).
4. 기존 Seed 데이터·API/테스트 회귀 여부.
5. 남은 위험: 서버 신원 증명 한계, 미검증 관리용 계정 GRANT, 기존 테스트 Alembic Migration 가드 범위 밖, Docker 직접 CLI 후속.
6. 사용자 승인 없이 수행하지 않은 작업(커밋/Push/PR/실 DB 쓰기 등)을 명시.

이 확정안에서 벗어나는 중요한 설계 변경이 필요하면 임의로 수정하지 말고 **변경 이유·기존 결정·대안·영향 범위**를 보고한 후 사용자 결정을 받으세요.