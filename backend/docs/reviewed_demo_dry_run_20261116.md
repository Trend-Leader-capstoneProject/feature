# Reviewed Demo Dry-run 및 격리 MariaDB 구성 제안

2026-11-16 KST. 기준은 기능 Worktree의 a8dc2d0135f86052045138e91fb010ab543786d2다.
작업 시작 시 clean이었다. 원격 최신 SHA는 이번 작업에서 별도 재조회하지 않았다.

## 격리 환경 준비 완료 — 최신 실행 결과

사용자가 3310 격리 환경 생성·기존 Migration·Category Master 최초 적용을 승인한 뒤
실행했다. 기존 미커밋 Dry-run 6개 파일의 Git 상태를 보존하며, 이번 저장소 내 보완은
실제 조회값을 반영한 입력 JSON과 이 보고서다. 설정·인증정보는 저장소 밖에 보관한다.

| 항목 | 실제 확인값 |
| --- | --- |
| Host·Port | 127.0.0.1:3310 |
| DATABASE() | trend_leader_demo_review_20261117 |
| CURRENT_USER() | trend_demo_review@% |
| Compose project | trend-leader-demo-review-20261117 |
| 컨테이너 | trend-leader-db-demo-review-20261117, running/healthy |
| 포트 바인딩 | 127.0.0.1:3310 → 3306/tcp |
| 독립 볼륨 | trend_leader_demo_review_20261117_data |
| 이미지 | mariadb:12.3.2, 기존 로컬 이미지 사용 |
| Alembic | b7f2c81d9e04 |
| Category Master | 44건, 기존 CATEGORY_MASTER 정의의 총 건수와 일치 |
| IT_DIGITAL 부모 | 38 |
| 활성 Child 기타 | 44, 신규 격리 DB에서 실제 조회 |
| Trend / TrendSource / TrendCategoryMap | 각각 0건 |
| Dry-run | DRY_RUN_READY, blockers=[], schema_issues=[], 중복 0건 |
| DML 허용 상태 | dml_allowed=false, 후보 등록 승인 대기 |

실행 전 Docker Compose의 최종 JSON 설정을 메모리에서 검증했다. 서비스 1개,
프로젝트·컨테이너 이름, 포트, DB 이름·계정, 독립 볼륨이 승인된 값과 일치했다.
설정 원문의 credential은 출력하지 않았다. 기존 db/backend 서비스가 포함된 Compose는
실행하지 않았다. 새 서비스만 `up -d --pull never db-demo`로 생성했다.

Migration 전에는 MIGRATION_DB_HOST/PORT/NAME/USER/PASSWORD_FILE만 지정한
기존 MigrationDbSettings로 연결 URL을 구성했다. DATABASE()·CURRENT_USER() 일치 및
신규 DB에 테이블이 0개임을 확인한 후 기존 `alembic upgrade head`를 적용했다.
종료 코드 0과 버전 b7f2c81d9e04를 확인했다.

Category Master 적용 전 동일 격리 연결의 identity와 categories 0건을 다시 확인했다.
기존 seed_category_master를 한 번 호출했고, 실행 경계에서 categories INSERT만
허용했다. 총 44개 INSERT 문장을 확인했다. 적용 후 실제 부모 코드·Child 이름·활성
상태를 조회해 IT_DIGITAL → 기타를 선택했다. 결과 ID가 개발 DB의 44와 같지만,
부모는 격리 DB의 38이며 개발 DB의 2와 다르다. 실제 조회값을 사용했다.

설정 디렉터리는 다음과 같다. 이 경로는 Git Worktree 밖이다.

`C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-demo-20261117/`

- compose.demo.yml / compose.env — 전용 Compose 및 별도로 생성한 credential
- backend.env — Windows 127.0.0.1:3310 전용 DB 설정
- migration_db_password — MigrationDbSettings의 절대 경로 credential 파일
- baseline.json / existing_surfaces_after.json — 비밀값 없는 기존 컨테이너 비교 기록
- verification.json — 격리 identity·버전·Category·Trend 0건 검증 결과

검토 입력 JSON의 category_id=44와 expected_target을 실제 값으로 갱신했다.
원래 CITATION_URL_MISMATCH, 사람 검토 provenance, 게시 승인 대기는 보존한다.
현재 Dry-run 실행 명령은 다음과 같다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -m scripts.reviewed_demo_dry_run --input docs/reviewed_demo_ict_20261116.json --env-file 'C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-demo-20261117/backend.env'
```

기존 trend-leader-db, trend-leader-db-test, trend-leader-db-check, trend-leader-api의
컨테이너 ID·StartedAt·마운트를 전후 비교해 모두 동일함을 확인했다. 기존 DB 3개는
healthy이고 API는 running이다. 메인 3309의 DATABASE()=trend_leader,
CURRENT_USER()=trend_user@%, Category 44건, Alembic a4d7c9e21f3b를 읽기 전용으로
확인했다. 이 기존 버전은 그대로 보존했다. 기존 8000 GET /api/trends?limit=1은
HTTP 200과 정상 data 객체로 응답했다.

검증은 실제 격리 Migration·Category 최초 적용 후 SELECT 확인 및 Dry-run과,
입력 갱신 후 Mock 21 passed (2.42초), 대상 Ruff All checks passed다.
후보 등록의 남은 절차는 검토 입력 최종 확정 및 Trend/Source/CategoryMap 1건 묶음의
별도 DML 승인이다. 실제 등록 코드·실행은 다음 범위다. 이번 Trend 후보 INSERT,
기존 DB DML, 기존 API 재시작, 기존 Demo Trend Seed, 유료 호출·게시·Git 쓰기는
각각 0건이다. S0/S1 FROZEN, D2 PARTIAL, G5/G6 HOLD를 유지한다.

아래 절은 이전 읽기 전용 검증과 구성 제안의 이력이다.

## 이전 3309 복구 후 재검증

재검증 시작 시 기능 Worktree에는 앞서 만든 Dry-run 신규 파일 6개가 미추적 상태로
남아 있었다. 같은 a8dc2d0 HEAD에서 해당 작업을 보완했으며 커밋은 수행하지 않았다.

사용자가 복구한 trend-leader-db의 Windows 대상 127.0.0.1:3309/trend_leader에
프로젝트 루트 .env.compose의 실제 DB_USER·DB_PASSWORD로 읽기 전용 접속했다.
컨테이너 healthy 상태와 127.0.0.1:3309 → 3306 매핑을 확인했다.
기존 3306의 인증 오류는 아래 새 대상의 인증 결과에 적용하지 않는다.

Dry-run 코드의 3306은 포트가 생략됐을 때의 기본값이었다. 이번 CLI에 --host·--port
명시 오버라이드를 추가했다. DATABASE_URL을 사용할 때도 같은 오버라이드가 적용된다.
기존 .env.compose와 Docker 내부 db:3306 설정 파일은 보존했다.
실제 실행 명령은 backend 디렉터리에서 다음과 같다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -m scripts.reviewed_demo_dry_run --input docs/reviewed_demo_ict_20261116.json --env-file 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/.env.compose' --host 127.0.0.1 --port 3309
```

최초 새 대상 조회에서 CURRENT_USER의 별칭 current_user가 MariaDB 예약어와 충돌해
1064 오류가 발생했다. 기존 Seed 가드와 같은 authenticated_user 별칭으로 수정한 후
동일 읽기 전용 Dry-run을 완료했다. Mock에서 드러나지 않았던 실제 SQL 호환성 오류다.

| 확인 항목 | 현재 결과 |
| --- | --- |
| 연결·인증 | 성공, START TRANSACTION READ ONLY 및 종료 rollback |
| DATABASE() | trend_leader |
| CURRENT_USER() | trend_user@% |
| 연결 대상 | local, 127.0.0.1:3309 |
| 직접 제목 일치 | 0건 |
| normalized_title 일치 | 0건 |
| source_key 또는 원본/정규화 Source URL 일치 | 0건 |
| 관련 기존 CategoryMap | 0건 |
| 모델 필드 검사 | schema_issues=[] |
| Dry-run 최종 상태 | BLOCKED |
| 현재 차단 사유 | ISOLATED_TARGET_UNCONFIRMED, ACTIVE_IT_CHILD_SELECTION_REQUIRED |

실제 활성 IT_DIGITAL 부모 ID는 2이며, 조회된 활성 Child는 다음과 같다.

| ID | 이름 |
| ---: | --- |
| 39 | 인공지능 |
| 40 | 모바일·스마트폰 |
| 41 | PC·하드웨어 |
| 42 | 소프트웨어·앱 |
| 43 | 플랫폼·서비스 |
| 44 | 기타 |

이 ID는 개발 DB에서 실제 조회한 값이다. 새 격리 DB 생성 후에는 그 DB에서 다시
조회해야 한다. 현재 입력 category_id는 null로 유지해 사람의 분류 선택을 기다린다.
개발 DB가 격리 시연 DB로 승격된 것으로 처리하지 않는다.

입력의 필수 문자열·길이·URL 안전성·ETC enum 값·원래 CITATION_URL_MISMATCH는
검증을 통과했다. 기존 세 모델에 대해 실제 필수 컬럼 존재, 필수 nullability,
문자열 수용 길이를 information_schema.COLUMNS로 점검했다. 조회된 기존 데이터에
제목·정규화 제목·출처 중복은 없으며 등록 직전 같은 검사를 다시 수행해야 한다.

이번 재검증 테스트는 Mock 21 passed (1.17초), 대상 Ruff All checks passed다.
추가 회귀는 예약어 SQL 별칭, DB_* 및 DATABASE_URL의 Windows host/port 오버라이드,
설정 파일 원형 보존, 모델 필드 누락·길이 부족 검출을 포함한다.
후속 격리 포트는 3310으로 갱신했으며 현재 리스너가 조회되지 않았다.
컨테이너·볼륨 생성/재시작, Migration·Category Seed, DML, 유료 호출, 게시,
Commit·Push·PR·Merge는 이번 재검증에서 각각 0건이다.

아래 기존 3306 및 테스트 DB 점검 결과는 복구 전 이력으로 보존한다.

## 후보 및 별도 입력

사용자가 원문을 확인해 지정한 후보 1건을 `reviewed_demo_ict_20261116.json`에 작성했다.
제목은 「2026년 10월 정보통신산업(ICT) 수출입 동향」이다. 공식 페이지의 본문에서도
11월 15일 발표 사실을 확인했다. 기존 CITATION_URL_MISMATCH 판정은 입력 및
Dry-run 출력에 보존한다. reviewer는 현재 채팅의 사용자 확인을 나타내는 표식이며
실명·정확한 검토 시각을 추측하지 않았다.
[산업통상부 공식 자료](https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172408/view)

platform=ETC는 일반 웹 출처의 제안값이다. category_id와 expected_target은 null로
남겨 실제 조회·확인 전 임의의 ID나 격리 대상이 입력되지 않도록 했다. 최종 표시 제목,
ETC 분류, 검토 기록, 실제 Child Category는 등록 승인 시 확정할 항목이다.

## 구현과 실제 점검

- `scripts/reviewed_demo_dry_run.py`는 입력 JSON과 명시적인 DB env 파일을 받는다.
  DB 설정만 읽고 별도 Engine을 사용한다. FastAPI JWT·DEBUG 값은 필요하지 않다.
  URL·비밀번호·DB 오류 원문을 오류 로그에 표시하지 않는다.
- `app/services/reviewed_demo_preflight.py`는 개발 환경, 연결 URL의 host·port·database,
  CURRENT_USER, 별도 기대 대상, 활성 IT_DIGITAL 하위 분류와 중복을 확인한다.
- `app/repositories/reviewed_demo_repository.py`는 기존 ORM 모델의 Table을 사용한
  SELECT만 실행한다. 제목 normalized_title, 출처 source_key 및 원본/정규화 URL,
  관련 기존 CategoryMap을 조회한다.
- 실제 연결은 `START TRANSACTION READ ONLY`로 시작하고 finally에서 rollback한다.
  Session·autoflush·commit·DML 경로가 없다. 동일 연결에서 모든 조회를 수행한다.
- 출력의 plan은 향후 한 트랜잭션으로 Trend 1건 → ID 확보 → TrendSource 1건 →
  TrendCategoryMap 1건 → 최종 commit하는 계획이다. 실패 시 전체 rollback하는 안이다.
  현재 dml_allowed는 항상 false다. DRY_RUN_READY도 쓰기 승인을 의미하지 않는다.

복구 전 기존 개발 설정을 사용한 실제 실행 결과는 BLOCKED였다.

| 확인 항목 | 결과 |
| --- | --- |
| 개발 설정 | local, 127.0.0.1:3306/trend_leader |
| 개발 DB 인증 | MariaDB 오류 1045, DATABASE_AUTHENTICATION_FAILED |
| 격리 대상 | ISOLATED_TARGET_UNCONFIRMED, 사용자도 미구성 상태로 확인 |
| CURRENT_USER·실제 Category ID·개발 DB 중복 | 인증 실패로 미확인 |
| 기존 테스트 설정 | 127.0.0.1:3307/trend_leader_test |
| 기존 테스트 DB 조회 | DATABASE_INSPECTION_FAILED, identity·Category·중복 미확인 |
| 실제 선택 Category ID | null, 추측값 입력 0건 |

실행 명령은 기능 Worktree의 backend 디렉터리에서 다음과 같다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -m scripts.reviewed_demo_dry_run --input docs/reviewed_demo_ict_20261116.json --env-file 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/.env'
```

후속 격리 DB 생성 후에는 env 파일을 해당 격리 설정 파일로 바꾸어 재실행한다.
조회된 활성 Child ID 중 사람이 선택한 값과 독립적으로 확인한 expected_target
{host, port, database, current_user}를 입력한다. 이때 DB identity를 다시 검증한다.
Dry-run 이후 동시 변경이 가능하므로 실제 등록 트랜잭션에서도 동일 검사를 반복해야 한다.

## 기존 구성 읽기 전용 점검

기본 docker-compose.yml은 db와 backend를 함께 정의하고 기본 DB 볼륨 및
backend/sql_script 초기화 mount를 사용한다. 테스트 Compose는 3307을, check Compose는
127.0.0.1:3308을 사용하며 둘 다 tmpfs DB를 사용한다.
실행 중 컨테이너 trend-leader-db-test와 trend-leader-db-check의 포트를 확인했다.
check의 관측된 이미지는 mariadb:12.3.2다. 복구 후 3309는 개발 DB가 사용한다.
3310 리스너는 재검증 시 조회되지 않았다. 사용 시점에 포트·이름 충돌을 다시 확인한다.

기존 Alembic head는 b7f2c81d9e04다. `python -m alembic heads`만 실행했으며 migration
적용은 0회다. Alembic은 API 설정과 분리된 MIGRATION_DB_* 및 절대 경로의
MIGRATION_DB_PASSWORD_FILE을 사용한다. 테스트의 자동 migration fixture는
trend_leader_test와 3307/3308 전용이므로 시연 DB 초기화에 재사용할 수 없다.
Category 마스터는 기존 seed_category_master(Session)에 정의되어 있다. 아직 빈
시연 DB를 만들지 않았으므로 Category 마스터의 최초 구성도 별도 DML 승인 항목이다.

## 격리 시연 DB 제안값

| 항목 | 제안 |
| --- | --- |
| Compose project | trend-leader-demo-review-20261117 |
| 컨테이너 | trend-leader-db-demo-review-20261117 |
| 이미지 | 기존에 관측한 mariadb:12.3.2 |
| Host·Port | 127.0.0.1:3310 → 컨테이너 3306 |
| Database | trend_leader_demo_review_20261117 |
| DB 계정 | trend_demo_review, 해당 시연 DB에만 권한 부여 |
| 예상 CURRENT_USER | trend_demo_review@%, 생성 후 실제 조회로 확인 |
| 볼륨 | trend_leader_demo_review_20261117_data, 기존 볼륨과 분리 |
| 설정 디렉터리 | C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-demo-20261117/ |
| Compose 설정 | 위 디렉터리의 compose.demo.yml 및 compose.env |
| Backend/Dry-run 설정 | 위 디렉터리의 backend.env |
| Migration 비밀번호 파일 | 위 디렉터리의 migration_db_password |

다음 YAML은 승인 검토용이다. 아직 실제 파일·컨테이너·볼륨·DB를 생성하지 않았다.
새 비밀번호는 다음 승인 후 별도로 생성하며 기존 개발·테스트 비밀번호를 재사용하지 않는다.

```yaml
services:
  db-demo:
    image: mariadb:12.3.2
    container_name: trend-leader-db-demo-review-20261117
    ports:
      - "127.0.0.1:3310:3306"
    environment:
      MARIADB_DATABASE: trend_leader_demo_review_20261117
      MARIADB_USER: trend_demo_review
      MARIADB_PASSWORD: ${DEMO_DB_PASSWORD:?required}
      MARIADB_ROOT_PASSWORD: ${DEMO_ROOT_PASSWORD:?required}
    volumes:
      - demo-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 20
volumes:
  demo-data:
    name: trend_leader_demo_review_20261117_data
```

Backend env에는 APP_ENV=local, DB_HOST=127.0.0.1, DB_PORT=3310,
DB_NAME=trend_leader_demo_review_20261117, DB_USER=trend_demo_review와 새 DB_PASSWORD를
지정한다. DATABASE_URL을 지정한다면 해당 값이 개별 DB_*보다 우선하므로 같은 대상을
명시한다. 파일은 저장소 밖의 위 경로에 둔다.

## 승인 후 최소 실행 순서

1. 위 별도 컨테이너·볼륨·DB·계정 생성안을 승인한다. 이후 설정 파일과 새 credential을
   준비하고 이름·포트 충돌을 재확인한다. 기존 Compose project와 DB를 조작하지 않는다.
2. 새 Compose 파일만 지정해 새 db-demo를 시작한다. 승인 후 명령의 형태는 다음과 같다.

```powershell
$demoRoot = 'C:/Users/Public/Documents/ESTsoft/CreatorTemp/trend-leader-demo-20261117'
docker compose -p trend-leader-demo-review-20261117 --env-file "$demoRoot/compose.env" -f "$demoRoot/compose.demo.yml" up -d --pull never db-demo
```

3. healthcheck, CURRENT_USER와 database를 읽기 전용으로 대조한 다음, 새 대상만을 위한
   MIGRATION_DB_HOST=127.0.0.1, PORT=3310, NAME=trend_leader_demo_review_20261117,
   USER=trend_demo_review, PASSWORD_FILE을 지정해 기존 Alembic upgrade head를 적용한다.
   기존 스키마의 적용이며 신규 스키마 설계는 없다.
4. 승인된 새 DB에서만 기존 Category 마스터를 최초 구성한다. 기존 Demo Trend Seed는
   이 후보 등록 경로에 사용하지 않는다. 이 단계까지 DML 승인 범위를 명시한다.
5. 새 시연 설정으로 본 Dry-run을 실행해 실제 활성 IT_DIGITAL 하위 ID, identity, 중복을
   조회한다. 그 조회값을 바탕으로 사람이 Child·표시 제목·플랫폼·검토 기록을 확정한다.
6. 후보 1건의 실제 DML을 별도로 승인한 뒤 등록 Service를 구현·실행한다. 기존 모델
   3개를 단일 트랜잭션으로 등록하며 인용 자동 실패 provenance는 별도로 보존한다.
7. 시연 Backend만 새 DB를 보도록 설정하고 기존 GET /api/trends와 Expo TrendCard에서
   제목·분류·출처 링크를 확인한다. 공개 API·관리자 UI 변경은 필요하지 않다.

## 검증과 현재 차단 조건

Mock 16 passed (1.15초), 변경 대상 Ruff All checks passed다. DB 실제 연결 없이
read-only 시작·SELECT만 실행·rollback, 대상/Category 불일치, 중복, 조회 실패,
production 차단, Live 자료 입력 거부, CLI 비밀정보 비출력을 확인했다.
pytest 기본 임시 폴더 권한 오류가 발생해 CreatorTemp 아래의 새 임시 경로를 명시하고
동일 테스트를 다시 실행했다. 명령은 다음 옵션을 사용했다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $responsesPython -m pytest -q --tb=short -p no:cacheprovider --basetemp <새로운-CreatorTemp-임시경로> --confcutdir=tests/reviewed_demo tests/reviewed_demo
& $responsesPython -m ruff check --no-cache app/services/reviewed_demo_preflight.py app/repositories/reviewed_demo_repository.py scripts/reviewed_demo_dry_run.py tests/reviewed_demo
```

현재는 격리 DB 미구성·대상 Child 미선택으로 등록 준비 판정은 BLOCKED다.
개발 DB의 Child와 중복은 위 3309 재검증에서 확인했다.
다음 승인은 (1) 위 격리 환경 생성 및 기존 migration·Category 마스터 최초 적용,
(2) 조회 후 선택할 실제 Child·검토 입력 확정, (3) 후보 1건의 실제 등록 DML이다.
환경 승인과 후보 DML 승인을 각각 구분한다. 기존 DB의 비밀번호 변경이나 Seed 재실행은
요청하지 않는다. S0/S1 FROZEN, D2 PARTIAL, G5/G6 HOLD를 보존한다.
이번 컨테이너 생성·삭제, DB 생성·수정, DML, Seed 실행, 유료 호출·게시·Commit·Push·
PR·Merge는 각각 0건이다.
