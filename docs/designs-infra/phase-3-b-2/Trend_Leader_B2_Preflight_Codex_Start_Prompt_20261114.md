# Trend Leader — Phase B-2 Migration Preflight 구현 준비 / Codex 시작 프롬프트

이번 작업의 목표는 M-A1 FROZEN v1.0의 Phase B-2 **읽기 전용 Migration Preflight**를 구현하기 위한 안전한 최소 변경 경계를 확정하고, 승인된 설계 범위 내에서 TDD로 구현하는 것입니다.

## 기준

- 저장소: `Trend-Leader-capstoneProject/feature`
- 대상 기준: 최신 `dev` HEAD 확인, 문서 작성 당시 `aca8c5155ff548bcec97b750be642ce816a730d4`
- 최상위: `docs/designs-infra/phase-3-b-2/Trend_Leader_Phase_3-B-2_M-A1_Design_Decision_v1.0_20261113.md`
- 이번 B-2 설계: 저장소의 `docs/designs-infra/phase-3-b-2/Trend_Leader_B2_Preflight_Design_v1.0_20261114.md` (FROZEN 후보; **세부 미동결 계약이 남아 있는 경우 코드를 추측해 확정하지 말고 짧게 보고**)
- 사용자 선택: 기존 Migration 전용 DB 계정 재사용, B-2는 관찰·감사, B-3는 승인값 대조
- 프로젝트 `AGENTS.md`, `Trend_Leader_AI_Development_Guidelines.md`, GitHub Write Safety Policy 준수

## 시작 전 확인

1. 현재 worktree/브랜치/HEAD/미커밋 변경, 기능·테스트 충돌 확인. 사용자 작업 보존. 브랜치 전환·reset·stash·clean 임의 수행 금지.
2. `backend/scripts/migration_guard.py`, `backend/app/core/migration_db_config.py`, `backend/alembic/env.py`, `backend/alembic/versions/*`, `backend/tests/core/test_migration_guard.py`, `backend/tests/conftest.py`를 읽고 실제 버전 확인.
3. B-1 거부 정책과 B-2 신규 Preflight 동작의 최소 diff, 변경 영향 및 테스트 목록 제시.
4. **운영 Evidence 영속 경로·환경변수 금지/허용 목록·Reason Code/exit code가 미동결**이면 확정 후보와 트레이드오프만 보고하고, 무단으로 운영 계약을 고정하지 말 것.

## 구현 안전 경계

- `deny` / 무인자 exit 2, `apply` 비활성, 미승인 Alembic/쉘 명령 거부 유지.
- `preflight` 외 실행 명령 허용하지 않음. Migration 전용 계정과 `MigrationDbSettings`만 사용.
- 정상 경로: DB 이름·CURRENT_USER·서버 버전·DB 기본 Collation·현재 Revision·가시적 객체 상태만 읽기 전용 관찰. 일회 검사에 단일 Connection.
- MariaDB `START TRANSACTION READ ONLY`의 안전한 시작 순서를 실제 설치 SQLAlchemy 2.x/DB 드라이버와 대조하고, 격리 DB에서 재검증 전 보안 성질을 단정하지 말 것.
- `get_current_heads()`가 비었더라도 DB가 비었다고 단정하거나 자동 승인하지 않음.
- Evidence는 고유 ID와 안전한 구조화된 보고서. 실패·중복·저장 불능 시 성공 처리 금지. 비밀번호·URL·JWT·원시 예외 노출 금지.
- B-3 Manifest 승인, L-2 Lock/Apply, 운영 Compose, 계정 생성·GRANT, API/Schema/기존 Migration 변경, AWS 배포는 이번 범위에서 제외.
- 기존 테스트의 별도 격리 DB Fixture가 자동 Alembic 업그레이드를 수행함을 유의. '빈 DB' 실험에 무심코 재사용하지 말 것.

## 검증과 보고

- Red → Green → Refactor. 정상/오류/부정/비밀정보/보고서/기존 거부 계약을 별도로 검증.
- 기존 사용자가 검증한 비통합 Backend 회귀와 S0/S1 분리 사유는 보존. 새 변경에 대해 필요한 테스트 재실행 결과만 구별해 보고.
- 격리 MariaDB·운영·AWS·Docker 볼륨에 파괴적 또는 자격 증명 작업을 절대 승인 없이 수행하지 말 것.
- GitHub 원격 쓰기/PR/병합도 사용자 별도 승인 없이 실행하지 말 것.
- 완료 보고: 정확한 HEAD/변경 파일/diff/실제 PASS·SKIP·FAIL/미실행 이유/남은 B-3·L-2 위험.

우선 이번 설계 초안과 실제 소스를 비교하여 추가 결정을 필요로 하는 P0 항목이 있는지 보고한 뒤, 명확히 확정된 최소 범위부터 진행해주세요.