# Trend Leader — Phase 3-B-2 인프라 설계 DRAFT 인덱스

> 등록일: 2026-11-12 (KST)
> 상태: **설계 중 / NOT FROZEN / NOT IMPLEMENTED / NOT TESTED**
> PR 목적: 구현 전 검토 기록과 현재 사용자 선택의 기준점 보존. 기존 개발·테스트 Compose, DB, AWS, 게시 Gate는 변경하지 않음.
> 문서 원본 작성 당시 검증 기준: `dev` SHA `b133b494f8258eea603243f8f07191a33290084a`; PR 브랜치 생성 기준: `dev` SHA `000bceca8a03e7c7c83b9daee16b8a965553a258`.

## 이번에 선택한 방향 (세부 계약은 미동결)

- 개발/테스트 Compose 유지, 운영용 `compose.prod.yaml` 독립 관리.
- DB Bootstrap / Alembic Migration / Account Provisioning 분리.
- Bootstrap은 실행 중인 MariaDB 컨테이너 안에서 관리자가 **명시적으로 수동 실행(A안)**.
- 운영 DB 문자셋 `utf8mb4`, Collation `utf8mb4_unicode_ci` **유지 결정**.
- **M-A1**: 운영 Compose의 선택적 일회성 Migration 서비스(Profile) 방향 채택. **DB 전용 Settings 분리**도 함께 채택.
- API Runtime 테이블별 최소 권한표는 DRAFT; 실제 GRANT 및 MariaDB 기능 시험 전 확정하지 않는다.
- G4/G5/G6 실제 운영 Gate 및 RSS-OPS **HOLD**, P4 Writer APPLY **미승인** 유지.

## 우선 읽을 순서

1. [API Runtime DB 최소 권한 리뷰 v0.3](api-runtime-privileges-v0.3-DRAFT.md): 현재 실제 API의 테이블 권한 및 계정 침해 위험.
2. [운영 Compose 구성 리뷰 v0.5](production-compose-v0.5-DRAFT.md): 서비스·파일·네트워크·Secret·기동 순서.
3. [일회성 Migration 서비스 리뷰 v0.6](migration-oneoff-v0.6-DRAFT.md): M-A1 선택 방향, 오작동 방지, Alembic 설정 분리.
4. [Account Provisioning SQL·Preflight v0.1](account-provisioning-sql-preflight-v0.1-DRAFT.md): 검토용 GRANT, 운영 시작 전 확인 및 실패 차단.

## 검증 전 해결해야 하는 항목

- MariaDB 운영 이미지/Digest, Caddy 이미지 및 DNS/TLS 실제 검증.
- MariaDB `root@localhost` Socket 접근, API Runtime `@'%'` 후보 및 Migration 계정 Host/권한 검증.
- DB 전용 Settings 설계의 정확한 코드 영향 및 회귀 테스트.
- Profile만으로는 Migration 무단 실행이 차단되지 않으므로 **승인 및 Preflight 강제 경로** 설계와 검증.
- `DATABASE_URL` 우선순위로 인한 고권한/잘못된 대상 접속 방지.
- 백업·복원/실기기 APK 기능 시험과 API 공개 Gate.

## 기존 정책/설계 관계

- 기존 기능별 FROZEN 계약 및 `docs/operations/trend-publication/`의 G5/G6 정책이 이 초안보다 우선한다.
- 실제 GitHub `dev`의 코드 상태는 문서 작성 시점과 다를 수 있다. 구현 전에 HEAD/관련 파일을 다시 확인한다.
- 초기 사용자 문제 정의 문서 `aws_design_firstpass(1).md`는 **별도 보존하는 초기 가설 원본**이며, 운영 정책/비용/기간의 최신 확정안이 아니다. 이번 PR에는 포함하지 않는다.
- 하위 문서의 "원격 변경 미실행" 표기는 **초기 DRAFT 작성 당시 이력**이다. 이번 PR에서 문서만 신규 추가한다.

## 적용 범위 및 안전

- 이 PR에서는 **Markdown 신규 파일만 추가**한다. 운영 Compose, SQL, 코드, Secret, DB, AWS 변경 없음.
- SQL 예시는 운영 실행 명령이 아니라 **검토용 초안**이다.
- 원격 문서 반영 및 PR 머지는 인프라 구현 완료나 운영 게시 승인과 다르다.
