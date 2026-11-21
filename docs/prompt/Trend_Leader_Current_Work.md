# Trend Leader — 현재 작업 인수인계 (단일 갱신 문서)

> 2026-11-21 KST | AI-Led Delivery Mode | 재평가 핵심 기능: 실제 자동 데이터 공급.
> 최근 통합 기준: PR #137 merge commit de08d2f3f7e0586deebd0683cab935e15b7c572a. 최신 dev HEAD는 재개 시 조회한다.
> 현재 작업: PR #137 IGDB 공통 수집 코드 통합 완료. PR #138 개발 전용 Expo Preview는 사용자 결정으로 미병합 종료. 후속은 기존 Writer → MariaDB → FastAPI → 기존 TrendCard 실데이터 공급. IGDB 운영 등록·실제 DB 쓰기·배포는 미승인.
> 역할: 진행 상태 및 다음 작업의 인덱스. 승인 증거/설계 계약 자체를 대체하지 않음.

## 새 채팅 재개 규칙

1. 이 문서의 최신 dev 및 열린 작업 PR 버전, 실제 dev/feature HEAD, 관련 확정안 및 변경 코드를 먼저 확인한다. 열린 작업 PR을 이어가며 중복 브랜치/설계/PoC를 생성하지 않는다.
2. 개발 가이드 v1.3 (§2.4.1, §13.6, §16.4, §17.9~10), GitHub Write Safety Policy, AP-3C FROZEN v1.0을 우선한다. 충돌하면 실제 사용자 결정과 구체 계약을 확인하고 보고한다.
3. 이 문서의 완료/검증 항목은 새 증거 또는 변경 영향이 있을 때만 재검증한다. 채팅 원문을 확보하지 못했다는 이유로 동일한 작업을 초기화하지 않는다. 이전 원문에만 있는 판단이 필요하면 정확한 근거를 확인한다.
4. 단계 종료 및 통합 시 AI가 이 파일을 같은 작업 PR에 최소 갱신한다. 이력을 무한 누적하지 않는다. 작업 시작용 별도 프롬프트, 복사, 새 Worktree를 강제하지 않는다. 기존 깨끗한 dev 작업 디렉터리에서 feature switch, 로컬 검증 후 dev 복귀(다른 작업 보존). merge/dev 직접 쓰기 별도 승인.

5. Backend 회귀 실행은 S0/S1 격리 시험과 구분한다. `backend/`에서 일반 회귀는 `python -m pytest -q --ignore=tests/responses_web_search --ignore=tests/responses_web_search_s1` 또는 변경 영향에 맞춘 명시적 테스트 경로를 사용한다(다른 특수 격리 모음도 해당 계약에 따라 별도 실행). 경로 미지정 전체 `python -m pytest -q`를 일반 회귀 명령으로 안내하지 않는다. S0/S1 관련 변경 시 각 모음을 독립 Python 프로세스에서 `python -m pytest tests/responses_web_search --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q`와 `python -m pytest tests/responses_web_search_s1 --confcutdir=tests/responses_web_search_s1 --import-mode=importlib -p no:cacheprovider --tb=short -q`로 각각 검증한다. 각 conftest의 금지 import/I/O 경계와 S0 Phase 2 Green 보고의 격리 옵션을 보존한다. S0/S1 미변경 시 기존 완료 증거 보존, 별도 실행하지 않은 시험을 PASS로 합산 금지.

6. DB 통합 회귀는 `.env.test`의 `TEST_DATABASE_URL` 외에 `TEST_MIGRATION_ALLOWED_{HOST,PORT,DATABASE,USER}`와 `DEMO_SEED_ALLOWED_{HOST,PORT,DATABASE,CURRENT_USER}`가 필요하다. `.env.test.example`와 환경 가이드 참조. 승인된 격리 대상만 수동 확인하며 URL에서 승인값을 생성하지 않는다. 기존 3307/3308 데이터 보존 및 동시 사용 여부 확인; 3309 및 Writer 시험 DB에 일반 회귀 금지.

## 목표와 사용자 확정 사항

- P0 첫 실제 공급 수직 통합: 수집 → Rule-first → 정책 → 독립 Writer → MariaDB → 기존 API → 실제 APK → 6시간 무인 실행. P1 여러 분야 및 실제 관심도 신호, P2 AI 및 구조 개선.
- AUTO-TREND-MVP만 자동 개별 판정. Batch 1, is_primary=true, 6시간, AI API 0, 동일 Release ID 무변경 SKIP, HIDDEN 자동 복구 금지. 기존 MVP-A/P4/DB Schema/API 유지.
- 서비스 정의(사용자 채택, 2026-11-19): 외부 원문을 대체하는 재게시 서비스가 아니라 최신 정보·트렌드를 자동 발견하고 Category별로 분류하여 원출처로 연결하는 큐레이션. 기존 TrendCard에서 허용된 사실/메타데이터·제목·Category·공식 링크를 제공한다. 원문 전체 및 이미지/로고 복제는 기본 제외, Summary/Thumbnail/Source title은 필요한 경우 NULL, AI API 기본 0회. 허용된 원본 필드·의미·원출처 URL을 보존하며 금지된 가공은 하지 않는다. 원본 보존이나 링크 제공만으로 저장/자동 선별/공개 제한이 해소되지는 않는다.
- 권리 확인은 실제 사용 필드·행위·목적에 한정한다. 공식 근거와 조건 준수로 판단 가능한 경우 별도 서면 문의를 필수화하지 않는다. 명시적 금지와 단순 미명시를 구분하고, 제한 필드/행위 제외·허용 방식 적용·대체 소스 검토를 우선한다. 중대한 미확인 권리는 해당 행위/소스만 HOLD하고 다른 공급원 및 연결 개발은 진행한다. 명시적 금지 우회 금지; 실제 권리와 운영 권한을 지어내지 않는다. NCP의 자동 채택·앱 제공 제한에 관한 기존 제외 결정 및 Google RSS HOLD는 유지하되 다른 소스에 일괄 적용하지 않는다. 새 외부 서비스 채택과 G6 운영 승인 별도.
- 우선순위 판단: Category 적합성·실제 최신 데이터·지속 공급을 권리 조건과 함께 평가한다. 권리만 명확하고 서비스 적합성이 낮은 소스를 강제 채택하지 않는다. 불필요한 자체 승인 단계/문의 대기/검증 전용 도구를 추가하지 않는다. 필수 보안·무결성·권리 검증은 생략하지 않는다.
- 2026-11-21 사용자 추가 결정: 비상업 대학 캡스톤으로서 시연 서버를 1개월 넘게 운영할 계획이 없으며, IGDB 데이터 개별 수집 후 **최대 30일 보존 상한**을 채택한다. 더 짧은 외부 조건·시연 종료·이용 종료·정정/삭제 요구가 우선한다. 서버 중지 자체가 DB/백업/캐시의 삭제를 보장하지 않으므로 실제 만료 처리 및 종료 절차는 별도 구현·확인한다. 30일은 법적 이용 허가가 아니다.
- **G6 비병목 결정**: G6는 소스/대상/기한에 대한 최초 운영 프로필 승인 1회로 한정하고, 유효기간 안의 6시간 주기는 무인으로 실행한다. 매 Cycle의 기존 승인·권리·중복·Journal 검증은 유지하되 사람의 매회 재승인을 요구하지 않는다. 구현·테스트·PR 작업은 G6 때문에 보류하지 않는다. 만료·철회·승인 범위 변경 및 불명확 Writer 결과의 HOLD는 유지한다. 자동 승인 발행/연장은 금지한다.
- DEC-11~16 사용자 승인: Godot 제한된 사실/원문 링크를 첫 실제 공급 범위로 채택, 독립 운영 승인 및 실제/Preview 경로 분리, Writer 독립 상세 단건 추가 확인(전체 최대 3회/Cycle), OS Scheduler 단회, 기존 로컬→Lightsail. Stage 4를 위해 소스별 Adapter와 복수 승인 목록, 공통 Writer 유지. 실제 운영 게시 HOLD 유지; 합성 성공을 운영 완료 또는 인기 트렌드 검증으로 승격 금지.

## 완료 증거 (재실행 불필요)

| 범위 | 증거 |
|---|---|
| AP-1/2 | PR #126/#132 병합. Godot 공식 Release ID 450611675 실제 수집 3 Cycle(신규 1/프로세스 중복 2), Rule-first AI 0, DB 0. 공식 최신 출시 이벤트이지 화제성 미검증. |
| AP-3A/B | PR #127~131 병합. 사용자 실제 3307 Writer 격리 DB 직접 GRANT, PUBLIC empty, InnoDB 4개, Windows ACL 사용자+SYSTEM. pytest 63/Ruff PASS. 실제 rollback/commit/재실행 HOLD, 합성 HIDDEN 2건, tables 2/2/2, Journal integrity ok 및 ROLLED_BACK/COMMITTED. |
| AP-3C-1 | PR #133 병합, 사용자 pytest 39 passed in 0.18s, Ruff PASS, 실제 --policy-preview DEFERRED(SOURCE_RIGHTS_UNVERIFIED, ACTIVE_CATEGORY_UNVERIFIED, INDEPENDENT_AUTHORITY_UNVERIFIED), writer boundary BLOCKED, AI/DB 0. |
| AP-3C-2 합성 연결 | PR #134 병합. 사용자 pytest 112 PASS, Ruff PASS, 실제 MariaDB policy 실행 POLICY_FIXTURE_COMMITTED (synthetic_only=true, publication_authorized=false). 기존 trend_id 3/4 HIDDEN, is_primary=0 유지; 신규 trend_id 5 Synthetic AP3 policy fixture HIDDEN, is_primary=1 확인. 추가 policy 재실행 HOLD 및 최종 Journal 대조 결과는 미보고(기존 AP-3B 실증과 구분). 신규 합성 PoC 반복 불필요. |
| 재평가 | 기존 APK/배포/조회 기반 보존. 실제 자동 외부 데이터 게시 및 무인 Scheduler/다양성은 아직 입증되지 않음. |

## 최신 통합 상태 및 다음 작업 (2026-11-21)

- **PR #137 병합 완료**: `feat/igdb-auto-supply` → `dev`, 검증된 feature HEAD `8668956cd471d34a241bfa0528f8ee9937f52c1d`, merge commit `de08d2f3f7e0586deebd0683cab935e15b7c572a`. 이번 병합은 소스코드 통합이지 운영 배포가 아니다.
- **PR #139 진행 중(Draft)**: `feat/igdb-operational-supply` → `dev`, 실측 검증 HEAD `cd1b29afbb82efe3d456e72593e156ccb197f2d6`. 사용자 보고(2026-11-21): G6 단독 `1 passed`, Backend 지정 회귀 `55 passed in 0.26s`, Ruff/py_compile `All checks passed!`, Git 변경 파일 4개, Backend 일반 회귀 PASS(정확한 명령·건수 미보고). 이 증거는 **정책·테스트 변경에 한정**하며 실제 6시간 Scheduler/IGDB 운영 Adapter·Writer/만료 집행/DB·모바일 E2E가 통과했다는 의미가 아니다. 증거 기록만 갱신하는 후속 문서 Commit은 재시험이 필요한 코드 변경으로 합산하지 않는다.
- **PR #139 IGDB 30일 조회 방어(구현, 신규 검증 대기)**: 기존 `TrendRepository.find_page()`에 UTC `collected_at` 만료 IGDB 출처가 연결된 Trend의 `NOT EXISTS` 공개·맞춤 목록 제외 조건을 추가하고, `find_latest_sources_by_trend_ids()`도 만료 IGDB Source를 배제한다. Cursor/limit 이전 적용, Godot/Legacy ETC·출처 없는 Demo 보존, 혼합 출처는 제목 원천 미확정으로 fail-closed(행 삭제 없음). 신규 `tests/repositories/test_igdb_visibility.py` 격리 MariaDB 통합 5건 작성(만료 경계·혼합 출처·최신 출처·naive 시간 거부 등). **이번 새 코드의 pytest/Ruff/DB 실행 증거 미확보**; 실제 DB/캐시/백업 삭제, HIDDEN 변경, G6 운영 활성화 미구현. FROZEN §6.1.1에 근거·혼합 출처·삭제 경계 반영.
- **PR #139 Phase 4-F 후속 코드 변경 및 사용자 검증(2026-11-21)**: `supply_adapter`의 IGDB 비실행 Registry Descriptor와 기존 `IgdbSnapshotBridge`를 `run_auto_supply.collect_envelope`/독립 `run_writer`에 바인딩. Collector/Writer별 보호 JSON 자격증명(각 root 소유·역할 그룹·0640)만 사용하며, 승인 프로필이 IGDB를 선택하지 않으면 불활성. 미설치·잘못된 권한·변조·후보 없음·Godot 경로 독립성 테스트 추가. 기능 코드 HEAD `5095661245d675bfc5d7ae12a5827de85a0c6ae5` 기준 사용자 지정 회귀 **`157 passed, 13 skipped in 0.72s`**, Ruff **`All checks passed!`**, `py_compile` 오류 없이 종료. 13 skipped의 실행 환경별 원인은 별도 미확인; Linux 권한·실제 DB·운영 스케줄러 시험 완료로 간주하지 않는다. 실제 approval.json·비밀파일 발행/배포·DB/Journal/systemd/API/Frontend 변경은 없음.
- **사용자 검증(2026-11-21)**: feature HEAD 일치; 변경 영향 테스트 `221 passed, 13 skipped`, Ruff PASS; Backend 일반 회귀 `1697 passed, 16 skipped, 2 SAWarning`(기존 Demo Seed close/transaction 비정상 경로, 해당 테스트 PASS). 실제 IGDB 루프백 HTTP 200, Free Fire/Visits 관측 5위/게임·모바일 게임/IGDB 원문 버튼 표시 확인. 원문 버튼 실제 이동은 미확인. S0/S1 별도 미실행은 기존 증거 보존, 이번 PASS에 포함하지 않음.
- **완료된 기존 dev 기반**: IGDB OAuth Client/Visits 적격성 검증/독립 Snapshot 검증, Godot과 공통 Writer·Scheduler의 소스별 계약, Game Cursor와 NO_ELIGIBLE_CANDIDATE, IGDB 30일 *확정 정책 상한*의 읽기 전용 만료 평가, `127.0.0.1` 임시 HTML TrendCard. `dev`에는 IGDB 운영 Adapter가 미등록이며, **PR #139 기능 브랜치에는 비실행 Descriptor와 보호된 역할별 연결 코드만 추가**했다. Writer/DB/API/Expo 실제 공급은 아직 미활성.
- **운영 전 미완료 Gate**: Windows에서 SKIP한 Linux 전용 Scheduler의 상태 원자성·재시작·child UID/소스 ID 검증(실제 배포 이전 WSL/Linux에서 실행), IGDB 최소 사용 필드의 이용 조건 검증, 확정된 30일 상한의 만료 비노출·삭제 및 FK/백업 영향 설계, G6 최초 기간 한정 운영 승인. **승인된 기간의 6시간 Cycle마다 사람의 재승인은 불필요하다.** 30일은 자동 이용 허가가 아니며 기존 Godot systemd/Journal/DB/프로필을 보존한다. PR Merge와 운영 승인은 구분한다.
- **다음 P0 — 실제 공급 수직 통합(기존 경로만)**: IGDB의 검증된 Snapshot과 기존 독립 Writer를 연결해 기존 MariaDB → `GET /api/trends` → `TrendListItem`/`TrendCard`/원문 버튼으로 실제 데이터를 조회한다. 별도 인프라·Preview 서버·새 공개 API·DB Schema·Migration·가짜 ID·AI·원문/이미지 복제는 도입하지 않는다. 기존 Category/Journal/Godot/Scheduler/6시간 전역 주기를 보존한다. 실제 DB 쓰기와 Scheduler 활성화는 권리·만료 처리·최초 G6 및 Linux 검증 후 사용자 별도 승인 대상이다.
- **중단된 우회 경로**: PR #138 `feat/igdb-expo-dev-preview`는 2026-11-21 사용자 결정으로 **Closed / Not Merged**. 자동 테스트 통과 보고는 보존하되 Expo IGDB 실기기 API 요청·원문 이동은 검증 완료로 계산하지 않는다. 이미 dev에 있는 HTML 내부 검토 코드의 존재는 보존하되 해당 경로를 확장·재개하지 않는다.
- **관련 확정안**: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_IGDB_Supply_Design_FROZEN_v1.0_20261120.md`; 앱 연결 방식은 다음 설계에서 확정한다.

## 이전 단계 진행 기록 (2026-11-19 기준, 현재 우선순위는 위 최신 블록 참조)

- Stage 1: 공급원 Adapter registry 및 복수 승인 목록, collect/write 단회 CLI, 실제 독립 상세 검증, 보호 프로필/잠금, 공통 SQL·Journal·중복 확인 경로 구현. 기존 112 + 신규 31 = 143 PASS(격리 사본, conftest 제외), compileall/CLI help 및 미승인 root 실행 HOLD. 실제 MariaDB/OS/G6/운영 승인·배포·정기 실행 미검증, 사용자 Windows 범위 지정 회귀 700 PASS / 1 FAIL / 2 SKIP(16.71s): test_new_adapter_does_not_change_writer에서 Linux 고정 Journal 경로 생성 오류. 해당 테스트의 OperationalJournal 생성만 Mock으로 격리, 생성 호출 및 Writer 전달 검증 추가. 수정본 격리 회귀 143 PASS(0.81s), CLI help/compileall 성공. 사용자 수정본 이전 범위 지정 pytest 701 PASS 및 신규 CLI --help 정상 출력 확인(정확한 실행 문자열 및 수정본 skip 수 미보고; 전체 무제한 pytest로 간주하지 않음). 수정 후 사용자 Ruff PASS 보고 및 PR #135 병합 확인. S0/S1 격리 실행 원칙 유지. 기존 3307 DB 및 Journal 보존(초기화/삭제/컨테이너 재시작 금지). Linux 운영 진입점은 Windows native에서 HOLD하며 로컬 WSL/Linux 활용 가능 여부 확인 필요. 상세 계약은 기존 AP-3C FROZEN §7.
- Source 권리 검토 (2026-11-19 공식 원문): GitHub 공개 API 비인증 접근 가능(60/hour/IP; https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api). 약관 H는 과도한 요청/제한 우회/스팸 목적 수집 제한(https://docs.github.com/en/site-policy/github-terms/github-terms-of-service). Godot 공식 builds https://github.com/godotengine/godot-builds/blob/main/README.md, 엔진 MIT는 모든 재게시 권한이 아님(https://godotengine.org/license/). 한국 판례 https://www.law.go.kr/LSW/precInfoP.do?evtNo=2004%EB%8F%845350 는 사실과 표현 구분. 사실 메타데이터·자체 작성 제목/설명·원문 링크 한정 검토 권장; 운영 저장/공개 권리 아직 승인되지 않음. 원문 Release Note/이미지/개인정보/AI 전달 제외.
- Wikimedia Analytics 공식 Access Policy https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html : API 제공 데이터 CC0 1.0, 식별 가능한 User-Agent, 요청 순차화/제한 준수. https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html : most-viewed pages 제공. 권리 근거가 명확한 대체/확장 공급원 권장; 통계 데이터 한정, 본문/이미지 별도 라이선스. 언어판 조회수는 한국 전체 검색 인기도와 다름. 신규 공급원 채택, 필드/분류/위험 제외 및 운영 프로필은 별도 확정. 이번에는 호출/코드 도입하지 않음.
- Stage 2 실제 로컬 준비(사용자 실측): Ubuntu WSL2, Python 3.14.4, SQLAlchemy 2.0.58/PyMySQL 1.2.4, 3309/trend_leader MariaDB 12.3.2 인증 성공. Collector UID/GID 997/986, Writer 994/985 별도 그룹. trend_auto_writer@172.20.0.1 직접 최소 GRANT 및 Writer Session Verification PASS; Collector secret access DENIED; 보호 /opt/trend-leader-auto-supply 코드·venv, /etc/trend-leader/auto-supply 비활성 프로필, /var/lib/trend-leader/auto-supply 운영 Journal READY 초기 등록(attempts=0). dev 0d264f1의 git archive로 추출, 기존 사용자 로컬 변경 보존. OS 관리자 control.lock 보유 시 양쪽 HOLD, 해제 시 OPERATION_DISABLED PASS. 실제 MariaDB 공유 잠금 부모 2/자식 42 경쟁 SELECT FOR UPDATE 1205 및 rollback 후 해제 PASS. 기존 local demo trend_id=1 ACTIVE→HIDDEN→ACTIVE 및 앱 Refresh 사용자 PASS 보고. 기존 3307/3308·합성 Journal 보존. 재실행 불필요. 앱 재조회 전까지 캐시 잔존 가능; 즉시 원격 캐시 제거 입증 아님.
- Stage 2 운영 제어: scripts/auto_supply_control.py 관리자 단회 run/revoke, 별도 보호 scheduler.lock 및 상태 파일, Collector/Writer 분리 UID/GID 하위 프로세스, 6시간 최소 간격, GitHub Retry-After/remaining=0/reset 준수(https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), 반복 제한 3회 또는 불명확한 Writer 종료/시각 오류 시 조사 HOLD. 실제 operational Adapter만 적용하고 기존 AP1 비게시 경로 유지. revoke는 기존 control.lock 아래 approval.json enabled=false 원자 교체, 기존 잠금/Journal 유지. 공개중단 상태 변경은 별도 기존 관리자 권한. 독립 신규 승인 발행/실제 게시 자동 활성화 없음. 신규 순수 상태/시각 함수 격리 사본 10 PASS(실제 운영 환경 시험 아님); 사용자 일반 회귀 1554 PASS / 5 SKIP / 2 WARN (34.81s), Ruff PASS 보고(검증 당시 feature 5cf8b16, 사용자가 실행한 정확한 명령 및 로컬 HEAD는 미보고). 두 SAWarning은 기존 Demo Seed 연결 close/rollback 강제 시험에서 발생하며 해당 시험 PASS; 별도 개선 후순위. 초기 Migration 102 ERROR 및 Demo Seed 15 ERROR는 독립 테스트 승인 설정 누락으로, 사용자 설정 보완 후 해소. 사용자 실제 WSL 갱신 스크립트(aa4c4e0 고정) 실행: 5/5 runtime blobs MATCH, Revoke lock contention PASS, Revoke on disabled profile PASS, Disabled scheduler entrypoint PASS, 기존 control.lock/secret/journal PRESERVED, NO TREND DML. 비활성 상태에서의 철회/실행 차단만 입증(활성 Writer 실행 중 철회와 실제 공급은 미실증). OS Scheduler 등록 미완료.
- [과거 2026-11-19 시점 계획 — 대체됨] 다음 P0: Stage 2 PR 최종 통합 승인 대기(사용자 일반 회귀/Ruff 및 비활성 경로 배치·철회 PASS 확보; 운영 활성화와 구분). 실제 운영 전 다른 Trend 쓰기 경로 배제 확인, 기존 권리 근거/G5 증거 정리 및 G6 별도 승인, 단회 실제 데이터 등록 → API → APK 원문 링크 → 6시간 정기 실행. 기존 시험·환경 재준비 불필요; 신규 합성 PoC·새 Schema/API/인프라/Worktree 추가 지양. 실제 운영 활성화 전 HOLD 유지.
- E2E 완료 기준: (1) Scheduler 무인 실행, (2) 실제 외부 신규 정보 자동 수집, (3) 허용된 정보 자동 DB 저장, (4) 기존 FastAPI 조회, (5) 실제 APK TrendCard 표시, (6) 원문 보기 버튼에서 실제 공식 원출처 이동, (7) 반복 실행에도 중복 카드 없음. 최초 수직 통합 이후 6시간 정기 실행 실증, 독립 실행 3회 이상 및 최소 3개 대분류·관심도 신호 확보(프로젝트 제안 목표, 공식 평가 합격 기준 아님). 크롤링/API 비교 근거 유지. 실제 E2E 증거 전 완료 선언 금지.

## 설계 원본

- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_AP3C_Automatic_Publication_Design_FROZEN_v1.0_20261119.md
- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Automated_Trend_Publication_Policy_Revision_v0.1_DRAFT_20261119.md
- docs/prompt/Trend_Leader_AI_Development_Guidelines.md 및 Trend_Leader_GitHub_Write_Safety_Policy.md
