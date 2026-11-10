# Trend Leader — Codex Repository Instructions

> 적용 범위: `Trend-Leader-capstoneProject/feature` 저장소 전체
> 지침 버전: v1.1 (2026-11-10)
> 목적: 확정된 설계에 따라 빠르고 안전하게 구현·검증한다.
> 이 파일은 실행 지침의 진입점이며 상세 개발 가이드라인을 대체하지 않는다.

## 1. Repository context

- 프로젝트: 관심사 기반 개인화 트렌드 큐레이션 모바일 앱.
- Backend: Python, FastAPI, SQLAlchemy, Alembic, MariaDB.
- Frontend: React Native, Expo, TypeScript, TanStack Query.
- 사용자가 지정한 브랜치를 우선하며, 별도 지정이 없으면 `dev`를 기본 비교 기준으로 삼는다.
- 현재 작업 브랜치와 미커밋 변경을 먼저 확인한다. 명시적 요청 없이 브랜치 전환·reset·clean을 수행하지 않는다.
- 원격 최신 상태를 확인하지 못하면 로컬 상태와 구분해 보고한다.
- 실제 코드 및 의존성 버전은 현재 체크아웃된 브랜치의 파일을 확인한다. 오래된 README나 이전 채팅을 최신 구현 상태로 간주하지 않는다.

## 2. Source of truth and conflict handling

요청과 관련된 문서만 읽는다. 모든 작업마다 문서 전체를 무조건 읽지 않는다.

- 신규 설계는 관련 도메인·설계 문서, 확정안 구현은 해당 확정안과 관련 코드·테스트부터 확인한다.
- 버그는 재현 경로·관련 코드·회귀 테스트, 문서 수정은 대상 문서와 직접 참조 자료부터 확인한다.
- 단순 질문에는 불필요한 Repository 전체 탐색을 하지 않는다. 영향이 확인되면 탐색 범위를 확장한다.

1. 현재 작업에서 사용자가 명시적으로 승인한 범위·결정
2. `docs/designs-feature/` 내 해당 기능의 최신 승인된 설계 확정안
3. 동결된 스키마 결정 및 명시된 API 계약
4. `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`
5. 대상 브랜치의 실제 코드·테스트(현재 구현 상태의 증거)
6. README 및 일반 참고 문서

- 설계 문서와 코드가 충돌하면 조용히 한쪽을 바꾸지 않는다. 충돌 항목·영향·가능한 해법을 보고한다.
- 새 도메인 규칙·API 계약·인증 정책·Transaction·DB Schema를 사용자의 승인 없이 확정하거나 변경하지 않는다.
- 이미 승인된 설계의 구현이나 단순 수정에는 새로운 설계 토론을 반복해 강제하지 않는다.
- GitHub Connector를 통한 파일 쓰기에는 `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`를 적용한다.

## 3. Start of task

- 작업 목적, 포함/제외 범위, 완료 기준을 짧게 확인한다.
- 코드 변경이나 현재 구현에 의존하는 작업은 브랜치·HEAD·`git status` 및 관련 파일·테스트를 확인한다.
- 단순 개념 질문이나 경미한 문서 수정에는 불필요한 전체 점검을 강제하지 않는다.
- 변경 전 로컬 작업이나 팀원의 변경을 덮어쓰지 않는다.
- 여러 파일·계층에 영향을 주는 작업에는 짧은 계획을 세우고, 명확한 단순 작업은 별도 계획을 생략할 수 있다.
- 중요 사실이 빠져 안전하게 구현할 수 없으면 그 부분을 명시한다.
- 제공되지 않은 파일·클래스·API·환경변수·패키지 동작을 추측하여 생성하지 않는다.
- 중요한 신규 도메인·아키텍처 설계는 사용자 Design First Pass → AI Review → 사용자 최종 판단을 따른다. Codex는 전제·반례·불변조건·대안을 검토하고, 확정된 설계 구현에는 이 절차를 반복 강제하지 않는다.
- 불필요한 코드 포맷 변경, 대규모 리팩터링, 새로운 라이브러리, 인프라 변경을 요청 범위에 섞지 않는다.

## 4. Engineering boundaries

### Backend
- 기본 흐름: Router → Service → Repository → Database.
- Router: HTTP 경계와 Dependency 및 Schema 연결.
- Service: 비즈니스 규칙, 유스케이스 조정, Transaction 경계.
- Repository: 조회·영속화; 임의로 HTTP 응답이나 최종 commit 책임을 갖지 않는다.
- ORM Model, Alembic Migration, API Schema를 서로 다른 책임으로 구분한다.
- DB 무결성·동시성·권한·401/403/404/409/422 의미를 보존한다.

### Frontend
- 기본 흐름: Screen → Hook → API Function → API Client → Backend.
- Screen에서 직접 HTTP 요청이나 인증 토큰 제어를 중복 구현하지 않는다.
- 기존 SecureStore / AuthProvider / Navigation / Query Cache 계약을 보존한다.
- 로딩·오류·빈 상태·재시도와 오래된 비동기 응답의 영향을 검토한다.
- API 계약 변경 시 Backend Schema와 Frontend Type/Hook/Screen 및 테스트를 교차 확인한다.

## 5. Implement and verify

- 기존 패턴을 재사용하고, 변경에 필요한 최소 범위부터 구현한다.
- 비즈니스 규칙이나 재발 가능 버그에는 위험에 맞게 실패 테스트 → 최소 구현 → 회귀 검증을 적용한다.
- 변경과 가장 가까운 테스트를 먼저 실행하고, Phase·기능 완료 또는 Merge 전에는 영향 범위에 맞는 회귀 검사까지 확장한다.
- 긴 테스트 로그는 결과 요약과 실패 원인에 필요한 구간부터 확인하고, 필요할 때 상세 로그를 추가 확인한다.
- 일부 테스트만 실행했다면 전체 회귀가 통과했다고 보고하지 않는다.
- 실행하지 않은 테스트를 통과했다고 보고하지 않는다.
- 정확한 작업 디렉터리와 설치된 도구를 확인한 후 다음 명령을 활용한다.

### Frontend (from `frontend/`)
- 타입 검사: `npm run typecheck`
- 테스트: `npm test -- --runInBand` (현재 테스트 환경에 맞게 범위 조정)
- 추가 환경 검증: `npm run verify` (Expo/의존성 확인이 필요할 때)

### Backend (from `backend/`)
- 테스트: `python -m pytest` (필요시 관련 테스트 파일로 제한)
- 정적 검사: `python -m ruff check .` (Ruff가 현재 환경에 설치되어 있을 때)
- MariaDB 의존 통합 테스트는 별도 DB 및 환경변수 구성을 확인한 후 실행한다.
- Docker/DB 환경 설정은 `docs/onboarding/Trend_Leader_Windows_Developer_Onboarding_Guide_v1.0.md`에서 해당 절을 참고한다.
- 사용자가 Windows PowerShell을 사용한다면 Bash 줄 연결 문자나 Unix 전용 명령을 그대로 제시하지 않는다.

## 6. Safety and delivery

- 실제 `.env`, API Key, DB Password, JWT, 토큰 및 개인 정보는 출력·커밋하지 않는다.
- DB 초기화, Docker Volume 삭제(`docker compose down -v`), 대량 삭제, 강제 reset, force push, 배포 및 원격 쓰기는 명시적 승인 없이 수행하지 않는다.
- 로컬 코드는 최소 patch/diff로 수정하고 `git status --short`로 변경 파일 전체를 확인한다.
- unstaged 변경은 `git diff`, staged 변경은 `git diff --cached`로 검토하고, untracked 파일은 별도로 확인한다.
- 공백 오류는 `git diff --check` 및 필요시 `git diff --cached --check`로 확인한다.
- GitHub Contents API 쓰기 작업은 별도 GitHub Write Safety Policy의 SHA/context 검사까지 적용한다.
- 커밋·푸시·PR 생성은 별도 승인을 받는다.
- 납기 중심 Delivery Mode에서도 승인된 핵심 사용자 흐름의 완성과 검증을 우선하고, 완료 기준을 낮추지 않는다.
- Feature Freeze 및 MVP 범위 변경은 사용자가 승인한 경우에만 적용한다.

## 7. Completion report

코드·테스트·설정·문서 변경 작업의 최종 응답에는 해당하는 항목을 간결하게 포함한다.

- 변경 파일과 핵심 내용
- 확정 설계 및 API 계약과의 일치 여부
- 실행한 명령과 실제 결과 (미실행은 이유 명시)
- 남은 위험·수동 검증·다음 단계
- 의도하지 않은 변경 유무 및 Git 상태

단순 질문이나 읽기 전용 분석은 결론·근거·미확정 사항 중심으로 보고한다. 상세 로그는 요청되거나 원인 진단에 필요할 때만 포함한다.

코드 작성만 완료된 상태를 '기능 완료'라고 부르지 않는다.
