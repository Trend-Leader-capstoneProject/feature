# Trend Leader — CI/CD v1 구성 및 운영 가이드

> 2026-11-23 | 범위: 캡스톤 2학기 산출물에 필요한 최소 CI
> 운영 배포 자동화(CD)는 **구축하지 않음**. CI 성공은 운영 배포 승인이 아님.

## 구성

- Workflow: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) (1개)
- 실행: `dev`·`main` 대상 PR, `dev` push, 수동 실행
- 실행 환경: GitHub-hosted `ubuntu-24.04`, 기본 `contents: read` 권한, 동일 PR의 이전 실행 취소
- `backend`: Python 3.12, Ruff, 일반 pytest 회귀, Runner 내부 MariaDB 12.3.2
- `frontend`: Node 22, `npm ci`, TypeScript, Jest
- `s0-s1`: pytest만 설치하고 S0/S1을 별도 Python 프로세스로 검증. 외부 I/O 금지 Fixture 및 격리 옵션 유지
- 캐시: Python pip, Frontend npm. Backend 의존성은 일부 범위 지정이므로 완전 Lockfile 재현성은 아직 보장되지 않음

## 데이터·권한 안전 경계

- MariaDB는 **각 Backend Job의 임시 Runner**에서만 실행하며 `trend_leader_test`에만 연결한다.
- `TEST_DATABASE_URL`과 `TEST_MIGRATION_ALLOWED_*`, `DEMO_SEED_ALLOWED_*`는 CI 전용 고정 테스트값이다. 운영 비밀값이 아니다. URL로부터 승인값을 계산하지 않는다.
- 기존 `tests/conftest.py`의 대상/계정/Migration/Seed 검증을 변경하지 않는다.
- 일반 회귀에서는 S0/S1과 opt-in `tests/l2_lock`을 제외한다. S0/S1은 서로 독립적인 pytest 프로세스로 실행한다.
- 기존 로컬 3307/3308/3309, Writer, Journal, Scheduler, Lightsail과 연결하지 않는다.
- 운영 Secret, 외부 API Key, EAS Token, AWS 자격증명은 CI에 등록하거나 사용하지 않는다.
- `pull_request_target` 이벤트, 서버 배포, DB 운영 Migration, 게시 자동화는 사용하지 않는다.

## PR 검사 및 실패 대응

1. 기능 브랜치에서 `dev`를 대상으로 PR을 생성/갱신하면 CI가 실행된다.
2. GitHub PR의 **Checks**에서 Backend / Frontend / S0-S1 결과를 확인한다.
3. 실패 시 해당 Job 로그의 첫 실패 원인을 코드 회귀 / 환경 오류 / 격리 위반으로 구분하고 최소 변경으로 수정한다. 테스트 Skip·안전 검증 완화로 GREEN을 만들지 않는다.
4. 각 Job이 통과해도 실기기·Lightsail 운영 검증을 의미하지 않는다. PR Merge는 사용자 별도 승인 대상이다.
5. Required Status Checks는 현재 `dev`에 강제되어 있지 않다. 안정화 후 별도 보호 정책 결정이 필요하다.

## 배포 범위 및 가이드

- Backend 서버: [로컬/Lightsail 환경 가이드](../onboarding/Trend_Leader_Local_and_Lightsail_Environment_Guide.md)를 따른다. 배포 이미지·DB Revision·운영 권한·HTTPS·롤백 가능성을 실제 대상에서 확인한 후 **별도 승인**받아 배포한다.
- 모바일: 기존 `frontend/eas.json`의 `exhibition` 내부 APK 빌드 프로필을 보존한다. EAS 자동 빌드·업데이트·스토어 배포는 이번 CI에 포함하지 않는다.
- 롤백: 이전 검증 이미지 또는 APK로의 복귀 절차와 데이터 스키마 호환성은 배포 전 별도 확인한다. CI는 운영 DB를 복원하거나 변경하지 않는다.
- 기존 PR #139(IGDB), #140(SearchApi)와 자동 공급 운영 HOLD는 본 변경으로 해제되지 않는다.

## 완료 증거 기록

- **설계/Workflow 작성**: `.github/workflows/ci.yml` 및 이 문서
- **정적 검증**: Workflow YAML 검사 결과와 GitHub 변경 Diff
- **자동 검증**: CI 기능 PR의 Checks/Workflow Run URL에서 최종 HEAD의 실제 결과 확인
- **운영 검증**: Lightsail CD 및 EAS 자동 배포 미구축·미검증

2학기 제출 시에는 PR/Actions 화면에서 Job별 실행·성공/실패 결과와 실행 시각을 캡처한다. 설계 완료, 코드 구현, CI 실행 PASS, 운영 배포 완료를 섞어 표기하지 않는다.
