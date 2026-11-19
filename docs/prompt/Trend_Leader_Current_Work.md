# Trend Leader — 현재 작업 인수인계 (단일 갱신 문서)

> 2026-11-19 KST | AI-Led Delivery Mode | 재평가 핵심 기능: 실제 자동 데이터 공급.
> 기준 dev: 858cb08f8a395f50e94dc83f4046db9ce5364e5d (PR #133 병합).
> 현재 작업 브랜치: feat/ap3c2-writer-integration. 실제 HEAD/PR 상태는 재개 시 GitHub에서 조회한다.
> 역할: 진행 상태 및 다음 작업의 인덱스. 승인 증거/설계 계약 자체를 대체하지 않음.

## 새 채팅 재개 규칙

1. 이 문서의 최신 dev 및 열린 작업 PR 버전, 실제 dev/feature HEAD, 관련 확정안 및 변경 코드를 먼저 확인한다. 열린 작업 PR을 이어가며 중복 브랜치/설계/PoC를 생성하지 않는다.
2. 개발 가이드 v1.3 (§2.4.1, §13.6, §16.4, §17.9~10), GitHub Write Safety Policy, AP-3C FROZEN v1.0을 우선한다. 충돌하면 실제 사용자 결정과 구체 계약을 확인하고 보고한다.
3. 이 문서의 완료/검증 항목은 새 증거 또는 변경 영향이 있을 때만 재검증한다. 채팅 원문을 확보하지 못했다는 이유로 동일한 작업을 초기화하지 않는다. 이전 원문에만 있는 판단이 필요하면 정확한 근거를 확인한다.
4. 단계 종료 및 통합 시 AI가 이 파일을 같은 작업 PR에 최소 갱신한다. 이력을 무한 누적하지 않는다. 작업 시작용 별도 프롬프트, 복사, 새 Worktree를 강제하지 않는다. 기존 깨끗한 dev 작업 디렉터리에서 feature switch, 로컬 검증 후 dev 복귀(다른 작업 보존). merge/dev 직접 쓰기 별도 승인.

## 목표와 사용자 확정 사항

- P0 첫 실제 공급 수직 통합: 수집 → Rule-first → 정책 → 독립 Writer → MariaDB → 기존 API → 실제 APK → 6시간 무인 실행. P1 여러 분야 및 실제 관심도 신호, P2 AI 및 구조 개선.
- AUTO-TREND-MVP만 자동 개별 판정. Batch 1, is_primary=true, 6시간, AI API 0, 동일 Release ID 무변경 SKIP, HIDDEN 자동 복구 금지. 기존 MVP-A/P4/DB Schema/API 유지.
- 권리 확인은 실제 사용 필드/행위에 한정, 미확인 소스만 HOLD하고 대체 공급원 검토와 연결 개발을 병행. 명시적 금지 우회 금지; 새 외부 서비스 선택 및 G6 운영 승인 별도. 실제 권리와 운영 권한을 지어내지 않는다.
- 실제 운영 게시 HOLD 유지. 합성 성공을 운영 완료 또는 인기 트렌드 검증으로 승격 금지.

## 완료 증거 (재실행 불필요)

| 범위 | 증거 |
|---|---|
| AP-1/2 | PR #126/#132 병합. Godot 공식 Release ID 450611675 실제 수집 3 Cycle(신규 1/프로세스 중복 2), Rule-first AI 0, DB 0. 공식 최신 출시 이벤트이지 화제성 미검증. |
| AP-3A/B | PR #127~131 병합. 사용자 실제 3307 Writer 격리 DB 직접 GRANT, PUBLIC empty, InnoDB 4개, Windows ACL 사용자+SYSTEM. pytest 63/Ruff PASS. 실제 rollback/commit/재실행 HOLD, 합성 HIDDEN 2건, tables 2/2/2, Journal integrity ok 및 ROLLED_BACK/COMMITTED. |
| AP-3C-1 | PR #133 병합, 사용자 pytest 39 passed in 0.18s, Ruff PASS, 실제 --policy-preview DEFERRED(SOURCE_RIGHTS_UNVERIFIED, ACTIVE_CATEGORY_UNVERIFIED, INDEPENDENT_AUTHORITY_UNVERIFIED), writer boundary BLOCKED, AI/DB 0. |
| 재평가 | 기존 APK/배포/조회 기반 보존. 실제 자동 외부 데이터 게시 및 무인 Scheduler/다양성은 아직 입증되지 않음. |

## 진행 중 / 바로 다음 작업

- AP-3C-2: 기존 MariaDB fixture와 Journal/SQL 재사용. 고정 정책 Snapshot 단건(HIDDEN)만 기존 격리 DB에 연결; 실제 후보 및 위조 적격은 connector 전 차단. 변경 개발 검증 112 PASS (격리 사본, conftest 제외; Ruff/실제 MariaDB 추가 단건 미실행). 기존 2/2/2 보존하고 3/3/3 목표. 사용자가 전달한 기존 Journal ID 파일을 재사용; 초기화/삭제/컨테이너 재시작 금지. 3307은 tmpfs, root/migration 경로와 분리. 실제 시험 실패/HOLD 시 원인 확인 전 재실행 금지. 실제 보호된 권리·G6 근거 연결, 철회 조정, 실제 영속 중복/공개중단 및 운영 대상 검증은 미완료.
- Source 권리 검토 (2026-11-19 공식 원문): GitHub 공개 API 비인증 접근 가능(60/hour/IP; https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api). 약관 H는 과도한 요청/제한 우회/스팸 목적 수집 제한(https://docs.github.com/en/site-policy/github-terms/github-terms-of-service). Godot 공식 builds https://github.com/godotengine/godot-builds/blob/main/README.md, 엔진 MIT는 모든 재게시 권한이 아님(https://godotengine.org/license/). 한국 판례 https://www.law.go.kr/LSW/precInfoP.do?evtNo=2004%EB%8F%845350 는 사실과 표현 구분. 사실 메타데이터·자체 작성 제목/설명·원문 링크 한정 검토 권장; 운영 저장/공개 권리 아직 승인되지 않음. 원문 Release Note/이미지/개인정보/AI 전달 제외.
- Wikimedia Analytics 공식 Access Policy https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html : API 제공 데이터 CC0 1.0, 식별 가능한 User-Agent, 요청 순차화/제한 준수. https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html : most-viewed pages 제공. 권리 근거가 명확한 대체/확장 공급원 권장; 통계 데이터 한정, 본문/이미지 별도 라이선스. 언어판 조회수는 한국 전체 검색 인기도와 다름. 신규 공급원 채택, 필드/분류/위험 제외 및 운영 프로필은 별도 확정. 이번에는 호출/코드 도입하지 않음.
- 다음: AP-3C-2 실제 연결 필수 경계만 해결하며 소스 권리 범위/공개중단·운영 승인 근거 확정. AP-4 실제 승인된 후보 DB→API→APK, 무인 Scheduler. 그 후 최소 3개 대분류·관심도 신호(프로젝트 제안 목표, 공식 평가 합격 기준 아님). 크롤링/API 비교 근거 유지.

## 설계 원본

- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_AP3C_Automatic_Publication_Design_FROZEN_v1.0_20261119.md
- docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_Automated_Trend_Publication_Policy_Revision_v0.1_DRAFT_20261119.md
- docs/prompt/Trend_Leader_AI_Development_Guidelines.md 및 Trend_Leader_GitHub_Write_Safety_Policy.md
