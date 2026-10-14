# Trend Leader 인증 비밀번호 정책 및 표시 UI 변경 확정안 v1.1

- 프로젝트: Trend Leader
- 결정일: 2026-10-14
- 상태: **설계 확정 / 구현 및 최종 테스트 검증 별도**
- 대상 브랜치: `dev` 기준 신규 기능 브랜치
- 기존 기준: [일반 회원가입 설계 확정안 v1.0](./Trend_Leader_일반_회원가입_설계_확정안_v1.0.md)
- 변경 이유: MVP 발표 시 회원가입 입력 부담 완화 및 로그인 비밀번호 오입력 확인 지원
- 우선 적용: 본 문서의 변경 항목은 일반 회원가입 설계 확정안 v1.0의 해당 항목보다 우선한다. 그 외 v1.0 설계는 유지한다.

## 1. 변경 이력과 충돌 해결

기존 확정안 v1.0의 **4.1 필드 정책**, **6. password Validation 정책**은 최소 15자, 최대 128자였다. 사용자가 2026-10-14에 **최소 8자**로 변경을 명시적으로 승인했다. 따라서 이 문서에서는 비밀번호 최소 길이에 한해 기존 v1.0을 개정한다.

본 변경은 가입 정책을 실제로 완화하는 것이므로 **시연 전용 플래그나 인증 우회가 아니다.** 변경된 백엔드를 사용하는 모든 신규 일반 회원가입 요청에 적용된다. 공개 배포 전에는 별도의 비밀번호 보안 정책 및 악성 로그인 시도 방어 등을 재검토한다.

## 2. 확정 정책

| 구분 | 확정 규칙 |
| --- | --- |
| 일반 회원가입 비밀번호 | **8~128자** |
| 길이 경계 | 7자 거부 / 8자 허용 / 128자 허용 / 129자 거부 |
| 비밀번호 문자 구성 | 숫자, 특수문자, 대문자 필수 조건 추가하지 않음 |
| 입력값 정규화 | 비밀번호 원문 trim 금지 |
| 비밀번호 확인 | `password_confirm`은 `password`와 정확히 같아야 함 |
| 오류 계약 | 회원가입 비밀번호 길이 오류는 기존과 동일하게 HTTP 422 |
| 비밀번호 보관 | 기존 `pwdlib PasswordHash.recommended()` 해시를 유지, 평문 저장/로그 출력 금지 |
| 기존 로그인 | 저장된 해시로 검증하며 `LoginRequest.password`에 신규 길이 제한 추가 금지 |
| 로그인 비밀번호 표시 | 기본 마스킹, 사용자가 `보기` / `숨기기`를 직접 전환 가능 |
| 회원가입 비밀번호 표시 | 기존 비밀번호 / 비밀번호 확인 표시·숨김 구현 유지 |
| 토글 보안·동작 | 화면의 `secureTextEntry`만 변경하며 입력값 및 로그인 요청 데이터 불변 |

비밀번호 표시 토글은 사용자가 입력한 내용을 단말 화면에 노출할 수 있으므로, 기본값을 숨김으로 유지한다. 버튼 접근성 이름은 **비밀번호 보기/비밀번호 숨기기**로 현재 상태에 따라 변경하고, 로그인 요청 중에는 토글을 비활성화한다.

## 3. 변경 범위와 책임

### Backend

`backend/app/schemas/auth_schema.py`의 `SignupRequest.validate_password_length()`에서 `8 <= len(password) <= 128`로 검증하며 사용자 안내 메시지 역시 8자로 일치시킨다. 기존 `SecretStr`, 확인값 검증, `AuthService`/Hasher/JWT/API 응답 계약은 그대로 둔다.

### Frontend

- `frontend/src/features/auth/screens/SignupScreen.tsx`: 로컬 최소 길이 조건과 화면 도움말, 422 대응 메시지를 **8자**로 맞춘다.
- `frontend/src/features/auth/screens/LoginScreen.tsx`: `isPasswordVisible` UI 상태와 표시/숨김 버튼을 추가하여 `secureTextEntry={!isPasswordVisible}`를 적용한다. 회원가입 화면과 동일한 접근성/텍스트 버튼 패턴을 재사용한다.
- 로그인 입력값과 `useLogin` 요청 `login_id` / `password`, 로그인 성공 후 세션 확립, 401 처리, 화면 전환은 변경하지 않는다.
- 외부 패키지 추가 및 공통 컴포넌트 대규모 리팩터링은 포함하지 않는다.

## 4. 의도적으로 유지하는 기존 설계

- DB 스키마 / Alembic 변경 없음
- `POST /api/auth/signup`, `POST /api/auth/login`의 경로와 응답 계약 변경 없음
- 비밀번호 해시 및 `verify_password()` 로직 변경 없음
- JWT, SecureStore, AuthProvider, RootNavigator, Session Restore, 공통 401 및 Logout 변경 없음
- 비밀번호 변경/찾기 및 Rate Limiting 신설은 이번 작업에서 제외

## 5. 필수 검증 항목

| 검증 대상 | 시나리오 | 예상 결과 |
| --- | --- | --- |
| Backend Schema | 7/8/128/129자 | 거부 / 허용 / 허용 / 거부 |
| Backend Router | 7자 가입 요청 | 422, Service 미호출 |
| Backend Schema | 비밀번호 앞뒤 공백 | 임의 제거하지 않음 |
| Backend Schema | 확인 비밀번호 불일치 | 기존 ValidationError 유지 |
| Signup UI | 7자 및 8자 입력 | 로컬 거부 및 정상 요청 |
| Signup UI | 안내 문구 | 모든 안내가 8~128자로 일치 |
| Login UI | 최초 표시 | 마스킹 `true` |
| Login UI | 보기→숨기기 | 마스킹 `false`→`true`, 입력값 동일 |
| Login UI | 토글 후 로그인 | API 요청 비밀번호 동일 |
| Expo Android 실기기 | 입력 중 전환, 키보드, 로그인/가입 | 수동 Acceptance Test 필요 |

자동화 테스트가 통과하더라도 실제 Android 기기 시연 검증을 마치기 전에는 전체 작업을 완료로 판정하지 않는다.

## 6. 배포·문서 관리

- 원래 일반 회원가입 확정안 **v1.0은 당시 결정에 대한 기록**으로 보존하고, 최상단에서 본 문서를 참조하도록 한다.
- 이후 회원가입 관련 문서, Notion 명세, 화면 안내에서 현재 비밀번호 최소 길이를 다룰 때는 **본 v1.1을 최신 기준**으로 삼는다.
- 배포 환경에서 정책 완화가 허용되는지 별도 보안 검토를 진행한다.
- GitHub PR에서 Backend pytest / Frontend Jest / TypeScript typecheck 및 실기기 점검 결과를 기록한다.

## 7. 설계 결정 요약

> Trend Leader MVP의 일반 회원가입 비밀번호는 8~128자로 검증하되, 기존 안전한 해시/인증 흐름을 유지한다. 로그인 화면에는 기본 마스킹과 사용자 제어형 표시/숨김 기능만 추가한다.
