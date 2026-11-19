# Trend Leader — 현재 작업 인수인계 (단일 갱신 문서)

> 2026-11-19 KST | AI-Led Delivery Mode | 재평가 핵심 기능: 실제 자동 데이터 공급.
> 기준 dev: 102f50a10b6398b4c74cab6e1d9c8c616f2e4188 (원문 연결 정책 및 인수인계 반영).
> 현재 작업: Stage 1 실제 자동 공급 연결 코드, feat/auto-supply-stage1 검증용 브랜치. 실제 HEAD/PR 상태는 재개 시 GitHub에서 조회한다.
> 역할: 진행 상태 및 다음 작업의 인덱스. 승인 증거/설계 계약 자체를 대체하지 않음.

## 새 채팅 재개 규칙

1. 이 문서의 최신 dev 및 열린 작업 PR 버전, 실제 dev/feature HEAD, 관련 확정안 및 변경 코드를 먼저 확인한다. 열린 작업 PR을 이어가며 중복 브랜치/설계/PoC를 생성하지 않는다.
2. 개발 가이드 v1.3 (§2.4.1, §13.6, §16.4, §17.9~10), GitHub Write Safety Policy, AP-3C FROZEN v1.0을 우선한다. 충돌하면 실제 사용자 결정과 구체 계약을 확인하고 보고한다.
3. 이 문서의 완료/검증 항목은 새 증거 또는 변경 영향이 있을 때만 재검증한다. 채팅 원문을 확보하지 못했다는 이유로 동일한 작업을 초기화하지 않는다. 이전 원문에만 있는 판단이 필요하면 정확한 근거를 확인한다.
4. 단계 종료 및 통합 시 AI가 이 파일을 같은 작업 PR에 최소 갱신한다. 이력을 무한 누적하지 않는다. 작업 시작용 별도 프롬프트, 복사, 새 Worktree를 강제하지 않는다. 기존 깨끗한 dev 작업 디렉터리에서 feature switch, 로컬 검증 후 dev 복귀(다른 작업 보존). merge/dev 직접 쓰기 별도 승인.

5. Backend 회귀 실행은 S0/S1 격리 시험과 구분한다. `backend/`에서 일반 회귀는 `python -m pytest -q --ignore=tests/responses_web_search --ignore=tests/responses_web_search_s1` 또는 변경 영향에 맞춘 명시적 테스트 경로를 사용한다(다른 특수 격리 모음도 해당 계약에 따라 별도 실행). 경로 미지정 전체 `python -m pytest -q`를 일반 회귀 명령으로 안내하지 않는다. S0/S1 관련 변경 시 각 모음을 독립 Python 프로세스에서 `python -m pytest tests/responses_web_search --confcutdir=tests/responses_web_search --import-mode=importlib -p no:cacheprovider --tb=short -q`와 `python -m pytest tests/responses_web_search_s1 --confcutdir=tests/responses_web_search_s1 --import-mode=importlib -p no:cacheprovider --tb=short -q`로 각각 검증한다. 각 conftest의 금지 import/I/O 경계와 S0 Phase 2 Green 보고의 격리 옵션을 보존한다. S0/S1 미변경 시 기존 완료 증거 보존, 별도 실행하지 않은 시험을 PASS로 합산 금지.

## 목표와 사용자 확정 사항

- P0 첫 실제 공급 수직 통합: 수집 → Rule-first → 정책 → 독립 Writer → MariaDB → 기존 API → 실제 APK → 6시간 무인 실행. P1 여러 분야 및 실제 관심도 신호, P2 AI 및 구조 개선.
- AUTO-TREND-MVP만 자동 개별 판정. Batch 1, is_primary=true, 6시간, AI API 0, 동일 Release ID 무변경 SKIP, HIDDEN 자동 복구 금지. 기존 MVP-A/P4/DB Schema/API 유지.
- 서비스 정의(사용자 채택, 2026-11-19): 외부 원문을 대체하는 재게시 서비스가 아니라 최신 정보·트렌드를 자동 발견하고 Category별로 분류하여 원출처로 연결하는 큐레이션. 기존 TrendCard에서 허용된 사실/메타데이터·제목·Category·공식 링크를 제공한다. 원문 전체 및 이미지/로고 복제는 기본 제외, Summary/Thumbnail/Source title은 필요한 경우 NULL, AI API 기본 0회. 허용된 원본 필드·의미·원출처 URL을 보존하며 금지된 가공은 하지 않는다. 원본 보존이나 링크 제공만으로 저장/자동 선별/공개 제한이 해소되지는 않는다.
- 권리 확인은 실제 사용 필드·행위·목적에 한정한다. 공식 근거와 조건 준수로 판단 가능한 경우 별도 서면 문의를 필수화하지 않는다. 명시적 금지와 단순 미명시를 구분하고, 제한 필드/행위 제외·허용 방식 적용·대체 소스 검토를 우선한다. 중대한 미확인 권리는 해당 행위/소스만 HOLD하고 다른 공급원 및 연결 개발은 진행한다. 명시적 금지 우회 금지; 실제 권리와 운영 권한을 지어내지 않는다. NCP의 자동 채택·앱 제공 제한에 관한 기존 제외 결정 및 Google RSS HOLD는 유지하되 다른 소스에 일괄 적용하지 않는다. 새 외부 서비스 채택과 G6 운영 승인 별도.
- 우선순위 판단: Category 적합성·실제 최신 데이터·지속 공급을 권리 조건과 함께 평가한다. 권리만 명확하고 서비스 적합성이 낮은 소스를 강제 채택하지 않는다. 불필요한 자체 승인 단계/문의 대기/검증 전용 도구를 추가하지 않는다. 필수 보안·무결성·권리 검증은 생략하지 않는다.
- DEC-11~16 사용자 승인: Godot 제한된 사실/원문 링크를 첫 실제 공급 범위로 채택, 독립 운영 승인 및 실제/Preview 경로 분리, Writer 독립 상세 단건 추가 확인(전체 최대 3회/Cycle), OS Scheduler 단회, 기존 로컬→Lightsail. Stage 4를 위해 소스별 Adapter와 복수 승인 목록, 공통 Writer 유지. 실제 운영 게시 HOLD 유지; 합성 성공을 운영 완료 또는 인기 트렌드 검증으로 승격 금지.

## 완료 증거 (재실행 불필요)

| 범위 | 증거 |
|---|---|
| AP-1/2 | PR #126/#132 병합. Godot 공식 Release ID 450611675 실제 수집 3 Cycle(신규 1/프로세스 중복 2), Rule-first AI 0, DB 0. 공식 최신 출시 이벤트이지 화제성 미검증. |
| AP-3A/B | PR #127~131 병합. 사용자 실제 3307 Writer 격리 DB 직접 GRANT, PUBLIC empty, InnoDB 4개, Windows ACL 사용자+SYSTEM. pytest 63/Ruff PASS. 실제 rollback/commit/재실행 HOLD, 합성 HIDDEN 2건, tables 2/2/2, Journal integrity ok 및 ROLLED_BACK/COMMITTED. |
| AP-3C-1 | PR #133 병합, 사용자 pytest 39 passed in 0.18s, Ruff PASS, 실제 --policy-preview DEFERRED(SOURCE_RIGHTS_UNVERIFIED, ACTIVE_CATEGORY_UNVERIFIED, INDEPENDENT_AUTHORITY_UNVERIFIED), writer boundary BLOCKED, AI/DB 0. |
| AP-3C-2 합성 연결 | PR #134 병합. 사용자 pytest 112 PASS, Ruff PASS, 실제 MariaDB policy 실행 POLICY_FIXTURE_COMMITTED (synthetic_only=true, publication_authorized=false). 기존 trend_id 3/4 HIDDEN, is_primary=0 유지; 신규 trend_id 5 Synthetic AP3 policy fixture HIDDEN, is_primary=1 확인. 추가 policy 재실행 HOLD 및 최종 Journal 대조 결과는 미보고(기존 AP-3B 실증과 구분). 신규 합성 PoC 반복 불필요. |
| 재평가 | 기존 APK/배포/조회 기반 보존. 실제 자동 외부 데이터 게시 및 무인 Scheduler/다양성은 아직 입증되지 않음. |

## 진행 중 / 바로 다음 작업

- Stage 1: 공급원 Adapter registry 및 복수 승인 목록, collect/write 단회 CLI, 실제 독립 상세 검증, 보호 프로필/잠금, 공통 SQL·Journal·중복 확인 경로 구현. 기존 112 + 신규 31 = 143 PASS(격리 사본, conftest 제외), compileall/CLI help 및 미승인 root 실행 HOLD. 실제 MariaDB/OS/G6/운영 승인·배포·정기 실행 미검증, 사용자 Windows 범위 지정 회귀 700 PASS / 1 FAIL / 2 SKIP(16.71s): test_new_adapter_does_not_change_writer에서 Linux 고정 Journal 경로 생성 오류. 해당 테스트의 OperationalJournal 생성만 Mock으로 격리, 생성 호출 및 Writer 전달 검증 추가. 수정본 격리 회귀 143 PASS(0.81s), CLI help/compileall 성공. 사용자 수정본 이전 범위 지정 pytest 701 PASS 및 신규 CLI --help 정상 출력 확인(정확한 실행 문자열 및 수정본 skip 수 미보고; 전체 무제한 pytest로 간주하지 않음). 수정 후 Ruff 결과 미보고. S0/S1 격리 실행 원칙 유지. 기존 3307 DB 및 Journal 보존(초기화/삭제/컨테이너 재시작 금지). Linux 운영 진입점은 Windows native에서 HOLD하며 로컬 WSL/Linux 활용 가능 여부 확인 필요. 상세 계약은 기존 AP-3C FROZEN §7.
- Source 권리 검토 (2026-11-19 공식 원문): GitHub 공개 API 비인증 접근 가능(60/hour/IP; https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api). 약관 H는 과도한 요청/제한 우회/스팸 목적 수집 제한(https://docs.github.com/en/site-policy/github-terms/github-terms-of-service). Godot 공식 builds https://github.com/godotengine/godot-builds/blob/main/README.md, 엔진 MIT는 모든 재게시 권한이 아님(https://godotengine.org/license/). 한국 판례 https://www.law.go.kr/LSW/precInfoP.do?evtNo=2004%EB%8F%845350 는 사실과 표현 구분. 사실 메타데이터·자체 작성 제목/설명·원문 링크 한정 검토 권장; 운영 저장/공개 권리 아직 승인되지 않음. 원문 Release Note/이미지/개인정보/AI 전달 제외.
- Wikimedia Analytics 공식 Access Policy https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html : API 제공 데이터 CC0 1.0, 식별 가능한 User-Agent, 요청 순차화/제한 준수. https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html : most-viewed pages 제공. 권리 근거가 명확한 대체/확장 공급원 권장; 통계 데이터 한정, 본문/이미지 별도 라이선스. 언어판 조회수는 한국 전체 검색 인기도와 다름. 신규 공급원 채택, 필드/분류/위험 제외 및 운영 프로필은 별도 확정. 이번에는 호출/코드 도입하지 않음.
- 다음 P0: Stage 1 관련 회귀/Ruff 확인 후 실제 기존 로컬 실행 환경 확인, 독립 보호 프로필·계정·Journal 사전 등록 및 필수 G5 실측, 권리 근거/G6 별도 승인. 관리자 철회·공개중단 및 DB 동시성 검증, Scheduler 요청 제한 제어 후 첫 실제 단회 저장 → 기존 API → APK 원문 링크 → 6시간 무인 실행. 공급원별 부적합/제한은 해당 소스만 제외한다. 불필요한 합성 PoC·새 Schema/API·인프라·Worktree 추가 지양.
- E2E 완료 기준: (1) Scheduler 무인 실행, (2) 실제 외부 신규 정보 자동 수집, (3) 허용된 정보 자동 DB 저장, (4) 기존 FastAPI 조회, (5) 실제 APK TrendCard 표시, (6) 원문 보기 버튼에서 실제 공식 원출처 이동, (7) 반복 실행에도 중복 카드 없음. 최초 수직 통합 이후 6시간 정기 실행 실증, 독립 실행 3회 이상 및 최소 3개 대분류·관심도 신호 확보(프로젝트 제안 목표, 공식 평가 합격 기준 아님). 크롤링/API 비교 근거 유지. 실제 E2E 증거 전 완료 선언 금지.

## 설계 원본

- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_AP3C_Automatic_Publication_Design_FROZEN_v1.0_20261119.md
- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Automated_Trend_Publication_Policy_Revision_v0.1_DRAFT_20261119.md
- docs/prompt/Trend_Leader_AI_Development_Guidelines.md 및 Trend_Leader_GitHub_Write_Safety_Policy.md
