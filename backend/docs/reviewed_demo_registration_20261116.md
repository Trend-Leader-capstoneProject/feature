# Reviewed Demo 단일 후보 등록 준비 결과

2026-11-16 KST. 기능 브랜치 feat/responses-live-mvp-20261116, HEAD a8dc2d0.
기존 미커밋 Dry-run 6개 파일을 보존하고 등록 전용 Repository·Service·CLI·테스트를 추가했다.

## 최종 승인에 따른 실제 등록 완료

운영자의 후속 명시 승인에 따라 격리 시연 전용 검토 기록만 최소 변경했다.
review_policy=ISOLATED_DEMO_OPERATOR_APPROVAL에서 공식 페이지 제목·날짜·핵심 수치에
대한 기존 Codex 확인과 운영자 별칭 trend-leader-demo-operator의 명시적 등록 승인을
검증한다. 기존 엄격 검토 경로와 ISOLATED_DEMO_ONLY 범위는 유지한다.
최초 AI PDF의 본문 전체 일치 확인은 승인 필수 조건에 포함하지 않았다.

승인 시각은 메시지 수신 직후 최초 도구 확인 시각인
2026-11-16T17:37:43+09:00으로 기록했다. 이 시각의 근거도 입력에 명시했다.
사람의 실제 원문 검토 완료 시각은 null, review_confirmed=false다.
PDF는 HTTP 200·PDF 형식만 확인했으며 full_content_match_verified=false다.
정부 발표일·공식 페이지 등록일·AI 검색 시각·운영자 승인 시각·DB 등록 시각을 구분했다.

| 항목 | 실제 결과 |
| --- | --- |
| 대상 | 127.0.0.1:3310/trend_leader_demo_review_20261117 |
| CURRENT_USER | trend_demo_review@% |
| Alembic | b7f2c81d9e04, 필수 Schema 검사 통과 |
| 등록 전 | trends=0, trend_sources=0, trend_category_map=0 |
| 실행 | 기존 CLI --execute를 한 번 실행, 종료 코드 0 |
| Commit | COMMITTED, 후속 검증 VERIFIED |
| 등록 후 | trends=1, trend_sources=1, trend_category_map=1 |
| ID | trend_id=1, source_id=1, trend_category_id=1 |
| 실제 DB 등록 시각 | 2026-11-16T08:40:09+00:00, 서울 2026-11-16T17:40:09+09:00 |
| 대표 Category | 활성 IT_DIGITAL 부모 38 → 활성 기타 Child 44, is_primary=true |
| 표시값 | 승인된 [DEMO] 제목, ACTIVE, Summary/Thumbnail NULL |
| 출처 | 공식 보도자료 페이지, 원제목 및 ETC 일치 |
| FK | Source·CategoryMap의 trend_id가 등록 Trend 1과 일치 |
| 원래 자동 판정 | CITATION_URL_MISMATCH 보존 |
| 재등록 검사 | DUPLICATE_REGISTRATION_BLOCKED, 추가 DML 시도 0건 |

쓰기 직전 동일 가드 연결·트랜잭션에서 실제 identity, 검토 입력, Schema·Alembic,
활성 Category 및 제목·Source 중복을 다시 확인했다. Commit 후 읽기 전용 트랜잭션에서
세 ID·FK·제목·정규화 제목·Source Key·출처·상태·시각·대표 분류를 확인했다.
추가 중복 검사는 실제 등록 Service에 DML 사전 차단 가드를 붙여 실행했으며,
중복 검사에서 종료되어 INSERT/UPDATE/DELETE 시도는 0건이었다.

실제 사용한 승인 입력의 SHA-256은
c5c616ea087e1c6fb85ea5ee3e6e24c2876fa8551849a4d4854b3d9bfefb6dd3이다.
저장소 밖 기존 격리 설정 디렉터리에 registration_receipt.json과
registration_verification.json을 저장했다. 앞의 기록에는 Commit 결과·ID·입력 해시가,
뒤의 기록에는 읽기 전용 검증과 기존 환경 비교 결과가 있다. credential은 포함하지 않는다.

기존 3309 메인, 3307 테스트, 3308 Check, API 8000의 컨테이너 ID·StartedAt·마운트는
등록 직전 기록과 모두 같다. 메인 DB의 identity, 기존 Alembic a4d7c9e21f3b 및 Category
44건을 읽기 전용으로 확인했고 기존 API GET /api/trends?limit=1은 HTTP 200이다.
기존 환경 DML·컨테이너 변경·Migration·Seed 실행·유료 호출·운영 게시·Git 쓰기는 0건이다.

변경 정책 관련 테스트를 포함해 Mock·SQLite 통합 45 passed (1.75초), Ruff 및 공백
검사 통과다. 실제 MariaDB에서는 승인된 세 INSERT의 단일 Commit과 후속 SELECT 검증을
완료했다. 이번 쓰기 트랜잭션 실패나 불명확 Commit은 발생하지 않았다.

다음 단계의 최소 설정은 기존 격리 backend.env의 3310 DB 설정을 사용한 별도 FastAPI
프로세스와 별도 포트(예: 8001)다. API 구동에 필요한 JWT 등 기존 Settings는 별도로
설정하고 기존 8000 프로세스는 유지한다. 별도 API의 기존 GET /api/trends에서 Trend 1을
확인한 뒤 앱의 Backend URL을 해당 시연 API로 지정한다. 이 연동은 이번에 실행하지 않았다.

아래 보류 판정과 원문 검토 필수 정책은 최종 승인 전의 이력이다.

## 현재 판정

DB 읽기 전용 사전검사는 DRY_RUN_READY다. 실제 등록 입력 검증은
OPERATOR_REVIEW_REQUIRED로 BLOCKED다. 운영자는 후속 메시지에서 식별값·실제 검토
완료 시각을 임의로 생성하지 말고 원문 검토·최종 확인 완료까지 INSERT를 보류하도록 했다.
이에 따라 실제 Trend/TrendSource/TrendCategoryMap은 계속 각각 0건이다.
실제 등록 Commit·쓰기 Rollback·등록 ID·MariaDB 등록 후 검증 결과는 아직 없다.
기존 DB 읽기 전용 조회 종료 시 rollback과 테스트 트랜잭션 결과는 별도로 확인했다.

## 원출처 재확인 및 provenance

공식 페이지와 최초 AI PDF 모두 직접 HTTP GET 200, 공식 motir.go.kr 호스트로 확인했다.
페이지에는 703.5·202.0 및 등록일 2026-11-16이 있고, PDF 응답은 application/pdf와
PDF 시그니처를 확인했다. 공식 자료의 검색 가능한 본문은 11월 15일 발표를 명시한다.
[공식 페이지](https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172408/view),
[최초 AI PDF](https://www.motir.go.kr/attach/down/095a2dda9c864e1d90d751f7668a1117/f604a620244b9bf41395655d434b6bf4)

입력 JSON을 다음 승인 내용으로 보완했다.

- 표시 제목은 [DEMO] 2026년 10월 ICT 수출 703.5억 달러, 전년 대비 202% 증가.
- [DEMO]는 격리 시연 환경 표시다. 발견 경로는 OPENAI_RESPONSES_WEB_SEARCH_LIVE다.
- 채택 URL은 공식 보도자료 페이지, original_ai_source_url은 최초 AI PDF다.
- original_failure=CITATION_URL_MISMATCH를 그대로 보존한다.
- 정부 발표일은 2026-11-15, 페이지 등록일은 2026-11-16이다.
- AI 검색의 정확한 시각과 운영자의 실제 검토 시각은 null이다. 가상 시각을 채우지 않았다.
- reviewer의 기존 USER_CONFIRMED_IN_CHAT은 승인된 식별값으로 인정하지 않는다.
  review_confirmed=false, reviewed_at=null을 유지한다.
- 범위는 ISOLATED_DEMO_ONLY, approved_record_count=1이다. 이 범위 설정과 실제 운영자
  검토 완료는 독립 조건이다.

입력 파일은 reviewed_demo_ict_20261116.json이다. 운영자의 실제 식별값·시각·확인 기록을
받아 보완해야 등록 검증을 통과한다. 검토 기록의 진실성은 운영자의 명시적 확인에 근거한다.

## 구현 경계

- reviewed_demo_registration_repository.py는 전달된 검증 연결에서 기존 세 모델의
  Core INSERT만 수행한다. UPDATE·UPSERT 경로는 없다.
- reviewed_demo_registration.py는 이 한 후보의 제목·URL·Category·플랫폼·승인 범위를
  고정된 승인값과 비교한다. 다른 입력, 리뷰 미완료, naive 시각, 미래 시각을 차단한다.
- URL의 host/port/database/user 및 charset 이외 연결 옵션을 실제 연결 전에 확인한다.
  실행 CLI의 Engine은 승인된 127.0.0.1:3310 전용 credential 경로로만 생성한다.
- 기존 _verified_seed_connection의 동일 bind·물리 연결·트랜잭션 유지 가드를 재사용한다.
  기존 Demo Trend Seed 실행 함수는 호출하지 않는다.
- 동일 쓰기 트랜잭션 안에서 검토 입력·identity·Alembic b7f2c81d9e04·모델 필드·
  활성 IT_DIGITAL 부모 38과 기타 Child 44·중복을 재검증한다. Category 행을 잠근다.
- 실제 UTC 현재 시각을 DB DATETIME의 초 단위 정밀도에 맞춰 UTC-naive로 저장한다.
  이 값은 DB 등록 시각이다. 정부 발표일·AI 검색 시각·사람 검토 시각을 대체하지 않는다.
- Trend.status=ACTIVE, summary/thumbnail=NULL, Source.platform=ETC,
  CategoryMap.is_primary=true를 명시한다. 기존 normalize_title 및
  normalize_source_url을 재사용해 제목 및 Source Key를 계산한다.
- 한 트랜잭션에서 세 INSERT 후 Service가 한 번 commit한다. 부분 실패는 전체 rollback,
  중복은 중단이다. DB UNIQUE가 동일 제목의 동시 등록에 대한 최종 무결성 경계다.
- Commit 예외는 COMMIT_OUTCOME_UNKNOWN_NO_RETRY로 보고하며 재시도하지 않는다.
- CLI는 사전 Dry-run 후 실제 등록을 호출하도록 구성했다. Commit 후에는 별도 읽기
  전용 트랜잭션으로 ID·FK·표시값·시각을 대조한다. 검증 실패 시 이미 받은 ID와 Commit
  결과를 보존하고 UNVERIFIED_NO_RETRY로 보고한다.
- 성공 결과에는 승인 입력의 SHA-256, 등록 시각, 3개 ID, 원래 실패·승인 범위를 남긴다.
  원문 검토 provenance는 별도 입력 JSON에 유지한다. 신규 DB Schema·공개 API는 없다.

현재 비실행 입력 검사 명령은 다음과 같으며 실제 결과는 BLOCKED다.

```powershell
$responsesPython = 'C:/Users/KIMHANJAE2/Desktop/assignment/캡스톤_트렌드리더/trend-leader/backend/venv/Scripts/python.exe'
& $responsesPython -m scripts.register_reviewed_demo --input docs/reviewed_demo_ict_20261116.json
```

실제 실행 옵션 --execute는 존재하지만 운영자 보류 지시에 따라 사용하지 않았다.

## 실제 재검증

127.0.0.1:3310의 DATABASE()=trend_leader_demo_review_20261117,
CURRENT_USER()=trend_demo_review@%를 확인했다. schema_issues=[], 제목·정규화 제목·
Source 중복 0건, 활성 부모 38 / 기타 Child 44, 세 대상 테이블 각각 0건이다.
기존 DB·API 컨테이너 4개의 ID·StartedAt이 환경 생성 전 기록과 일치하며 running이다.
기존 8000 GET /api/trends?limit=1은 HTTP 200이다. 기존 DB DML과 컨테이너 변경은 0건이다.

## 테스트

Mock 및 SQLite 트랜잭션 통합 검증 41 passed (1.23초), 대상 Ruff All checks passed다.
SQLite 통합에서는 연결 identity·물리 연결 가드·MariaDB metadata 조회만 테스트 대역으로
바꾸고, 실제 SQLAlchemy INSERT·PK·트랜잭션·rollback·재실행 중복 차단·Commit 후 값
대조를 실행했다. SQLite PK 타입은 테스트용 복제 metadata에서 INTEGER로 조정했다.
검토 기록은 fixture-operator와 합성 과거 시각으로 구성했으며 실제 입력에 복사하지 않았다.

추가 경계는 미완료 리뷰·시각·범위·후보 변조, 3307/3308/3309 checkout 이전 차단,
동일 트랜잭션의 버전·Category·identity·Schema 불일치, Source INSERT 실패 후 전체
rollback, Commit 예외 시 단일 시도다. 실제 MariaDB 등록 DML·재실행·등록 후 확인은
운영자 검토 대기로 실행하지 않았다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $responsesPython -m pytest -x -q --tb=short -p no:cacheprovider --basetemp <새로운-CreatorTemp-임시경로> --confcutdir=tests/reviewed_demo tests/reviewed_demo
& $responsesPython -m ruff check --no-cache app/services/reviewed_demo_registration.py app/repositories/reviewed_demo_registration_repository.py scripts/register_reviewed_demo.py tests/reviewed_demo
```

남은 차단 조건은 실제 운영자의 식별값·검토 완료 시각·원문 확인 기록·최종 확인이다.
그 확인 뒤 실제 입력 검증·Dry-run·쓰기 직전 조건을 다시 확인해 단일 등록을 진행한다.
등록 이후에는 별도 격리 FastAPI 프로세스가 3310 DB를 사용하도록 준비하고 기존
GET /api/trends 응답을 확인한 뒤 React Native TrendCard로 연결한다. 기존 8000 API의
DB 전환과 앱 연결은 후속 승인 범위다. G5/G6 HOLD 및 비게시 범위는 유지한다.
