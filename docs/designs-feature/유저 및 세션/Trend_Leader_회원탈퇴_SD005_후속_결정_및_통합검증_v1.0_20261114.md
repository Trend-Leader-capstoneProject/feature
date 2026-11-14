# Trend Leader 회원 탈퇴 정책 — SD-005 후속 결정 및 통합 검증

> 정책 상태: **MVP 물리 삭제 확정 (2026-11-14)**
> 통합 상태: **정적 검토 진행 / dev 머지·실행 검증 미완료**
> 초기 설계 출처: 프로젝트 첨부 schema_decisions.md의 SD-005 (Frozen for Initial Migration)
> 기능 기준: feat/my-info-account-auth @ 3a370e02a9f9e4d2167c265a853cd890159934c8
> 작성 당시 dev: cd079ed3886234e6f9df21613f31613f13c8bdd2

## 1. 정책 변경과 효력

- 이전 SD-005는 소프트 삭제(사용자 상태 WITHDRAWN, withdrawn_at, 선택적 withdraw_reason)와 탈퇴 후 인증 거부, 연결 정보 보존·익명화 정책의 후속 결정을 규정했다.
- **2026-11-14 사용자 확정**: 현행 MVP에서는 사용자 계정 **물리 삭제(Hard Delete)** 를 적용한다. 초기 SD-005 원문은 초기 Migration 설계의 역사적 기록으로 보존하되, 현재 MVP 탈퇴 정책으로 적용하지 않는다.
- 변경의 배경은 MVP에서 게시글·댓글 등 커뮤니티 기능을 제외하고 관심사 기반 트렌드 제공에 집중한 것이다. 초기 소프트 삭제의 동기가 커뮤니티였다는 해석은 사용자 회고에 근거한 **추정**이며 SD-005 원문에 명시된 이유는 아니다.
- 이 결정은 다른 도메인의 데이터 삭제 정책을 변경하지 않는다. 향후 커뮤니티 도입 시 콘텐츠 보존, 작성자 익명화, 삭제 연계 정책을 별도 설계한다.

## 2. 현재 기능 계약

1. 사전 확인: POST /api/users/me/withdrawal/verify-password — 현재 비밀번호 확인. 이 결과는 최종 탈퇴 성공을 보증하지 않는다.
2. 최종 실행: POST /api/users/me/withdrawal — 사용자·세션 재검증, 현재 비밀번호 재확인 후 users 물리 삭제. 현재 코드의 성공 상태는 200이다.
3. DB 연결 데이터: user_profiles, oauth_accounts, user_interest_categories, user_trend_bookmarks, search_logs, auth_sessions와 그 하위 auth_refresh_tokens 등이 외래 키 CASCADE 대상이다. 공유 trends/categories 자체는 삭제하지 않는다.
4. 인증: 탈퇴 완료 후 기존 Access/Refresh Token은 유효한 사용자·세션에 연결되지 않으므로 인증에 사용할 수 없다. 앱은 로컬 인증 묶음과 사용자 종속 캐시를 정리한다.
5. 재가입: 기존 로그인 ID·이메일·닉네임 재사용 가능. 재가입 시 새로운 user_id를 부여받는 신규 계정이며 기존 계정 복원이 아니다.
6. 사진 파일: 삭제 의도를 durable cleanup job으로 기록한 뒤 DB commit 후 실제 파일 삭제를 시도한다. 장애 시 재시도하므로 DB 삭제 성공과 파일의 즉시 삭제 완료를 동일시하지 않는다.
7. 기존 users.status/withdrawn_at/withdraw_reason 컬럼은 이번 기록만으로 제거하지 않는다. Schema 정리는 별도 결정 및 Migration이 필요하다.
8. 백업, 운영 로그, 외부 연동, 법정 보존 대상의 처리 정책은 현재 구현만으로 확정할 수 없으며 별도 운영·개인정보 검토가 필요하다.

## 3. UI 및 장애 시 처리

- 현재 비밀번호 입력 → 사전 확인 → 되돌릴 수 없음 최종 안내 → 실제 탈퇴 요청.
- 성공 응답 후 기기 인증 정리 및 완료 안내. 기기 저장 실패는 복구 안내 대상으로 남는다.
- 최종 탈퇴 응답 유실 등 성공 여부가 불분명할 때 요청을 자동 재전송하지 않는다. 로그인 실패만으로 탈퇴 완료를 증명하지 않는다.

## 4. 검증 근거 (작성자의 실행 검증과 구분)

- 구현 확인: backend/app/services/account_service.py::withdraw, backend/app/services/session_service.py::authenticate, backend/app/api/routes/account_router.py, frontend/src/features/account/components/WithdrawalModal.tsx.
- 자동 테스트 존재 확인: backend/tests/api/test_account_integration.py::test_withdrawal_rechecks_password_deletes_rows_and_allows_new_account.
- 팀원 인계 문서 보고: 2026-11-14 서버 811 passed, 프론트엔드 27 suites / 187 passed, Expo Go 주요 흐름 점검. 본 후속 결정 문서 작성 과정에서 테스트를 **직접 재실행하지 않았다**.

## 5. dev 통합 검증 게이트

> **운영 Guard와 Alembic의 구분:** 검토 당시 dev의 backend/scripts/migration_guard.py는 preflight·apply를 모두 MODE_NOT_ENABLED로 거부한다. B-2 운영 Preflight/승인/적용은 완료되지 않았다. 신규 Revision이 코드상 연결된 것만으로 운영 적용 승인이 되지 않는다. 최신 dev의 backend/alembic/env.py 및 backend/tests/conftest.py는 MIGRATION_DB_* 설정을 사용하므로 기능 브랜치의 이전 DATABASE_URL 기반 테스트 결과를 통합 후 성공으로 간주하지 않는다.

| 검증 항목 | 현재 판정 | 완료 전 확인 |
| --- | --- | --- |
| 정책 충돌 | **해결** — MVP Hard Delete 확정 | 최초 SD-005는 역사적 기록으로 유지 |
| 코드 통합 | **미완료** — 기능 브랜치 별도 | 최신 dev와 변경·API 계약 비교 및 전체 회귀 |
| Alembic 계보 | **정적 확인** — a4d7c9e21f3b → b7f2c81d9e04 | 격리 DB에서 실제 마이그레이션 검증 |
| 기존 사용자 상태 | **미확인** — 새 Migration이 ACTIVE 외 상태를 거부 | 대상 DB 읽기 전용 상태별 건수 점검; 사용자 데이터 변경 금지 |
| CASCADE 전체 범위 | **정적 확인** — FK 코드 존재 | OAuth·관심사·북마크·검색·세션 값을 채운 격리 DB 통합 테스트 |
| 파일 정리 | **정적 확인** — cleanup job/재시도 코드 존재 | 재시작·장애 복구·영구 Volume 권한 검증 |
| 토큰 차단 | **코드 및 테스트 존재 확인** | 다중 기기·Refresh 경합·탈퇴 후 인증 실제 검증 |
| 기기 UI/UX | **부분 확인** — Expo Go 보고 | 응답 유실/중복 탭/기기 저장 오류/새 Android 빌드 |
| 법정/운영 보존 | **미확정** | 배포 전 별도 정책 검토 |

## 6. 변경 통제 및 출처

- 이 문서는 정책·통합 검증 기준을 기록할 뿐, 실제 운영 DB 삭제·Migration 실행·기능 PR 병합을 수행하지 않는다.
- 최초 schema_decisions.md는 프로젝트 첨부 자료로 확인되었으며 작성 시점의 원격 dev 저장소에는 존재하지 않았다. 이 후속 문서는 저장소에 독립적으로 보관한다.
- 추가 근거: feat/my-info-account-auth의 docs/designs-feature/유저 및 세션/내정보_계정관리/README.md (기능 브랜치 머지 시 저장소에 반영 예정).
