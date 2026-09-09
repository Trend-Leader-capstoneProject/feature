# Trend Leader 일반 회원가입 설계 확정안 v1.0.1

- 문서명: 일반 회원가입 설계 확정안
- 프로젝트: Trend Leader
- 기준 Repository: `Trend-Leader-capstoneProject/feature`
- 기준 브랜치: `dev`
- 기준일: 2026-09-09
- 상태: 설계 확정 / 문서 정합성 보강
- 기반 문서: `Trend_Leader_일반_회원가입_설계_확정안_v1.0.md`
- 보강 범위: `SignupRequest.email` 최대 길이 정책과 관련 Validation / 테스트 기준

---

## 1. 문서 목적

본 문서는 `v1.0`의 일반 회원가입 설계를 새로 재설계하지 않는다.

`v1.0` 확정 이후 실제 Backend 구현에서 확정된 `SignupRequest.email` 최대 길이 정책을 문서와 일치시키기 위한 **정합성 보강 문서**다.

본 문서에서 명시적으로 변경하는 사항을 제외한 회원가입 API 계약, 인증 흐름, Transaction 정책, 중복 처리, Navigation 정책은 `v1.0`을 그대로 유지한다.

충돌 시 다음 순서를 적용한다.

```text
현재 채팅의 명시적 확정 사항
→ 본 v1.0.1 보강 사항
→ v1.0 기존 확정안
→ 현재 dev 코드와 테스트는 실제 구현 상태 확인 자료
```

---

## 2. email 최대 길이 정책

일반 회원가입의 `email`은 기존과 동일하게 **선택값**으로 유지한다.

최종 Validation 정책은 다음과 같다.

```text
필드 누락 / null / 빈 문자열 / 공백 문자열
→ None

실제 값 존재
→ trim
→ 소문자 정규화
→ 이메일 형식 검증
→ 최대 255자 검증
```

실제 이메일 값이 존재하는 경우 최대 길이는 다음과 같이 확정한다.

```text
최대 길이: 255자
```

255자를 초과하는 이메일은 Request Validation 실패로 처리한다.

```text
HTTP 422 Unprocessable Entity
```

현재 Backend 계약은 다음과 같다.

```text
SignupRequest.email
→ EmailStr | None
→ max_length = 255
```

현재 DB 계약은 다음과 같다.

```text
users.email
→ VARCHAR(255)
→ nullable
→ UNIQUE
```

이번 보강은 DB 제약을 새로 추가하거나 이메일 정책 자체를 변경하는 작업이 아니다.

이미 구현된 Backend Schema Validation과 DB 길이 계약을 설계 문서에 명시적으로 반영하는 정합성 보강이다.

---

## 3. v1.0 Section 4.1 필드 정책 해석 보강

`v1.0` Section 4.1의 기존 `email` 정책:

```text
email
→ 선택
→ 누락/NULL/공백은 None
→ 값이 있으면 이메일 형식 검증
```

은 본 문서 이후 다음과 같이 해석한다.

```text
email
→ 선택
→ 누락/NULL/공백은 None
→ 값이 있으면 이메일 형식 검증
→ 최대 255자
```

따라서 회원가입 Request의 최종 `email` Validation 정책은 다음과 같다.

| 필드 | 필수 여부 | Validation 정책 |
| --- | ---: | --- |
| `email` | 선택 | 누락/NULL/공백은 `None`, 값이 있으면 이메일 형식 검증 및 최대 255자 |

---

## 4. v1.0 Section 8 email 정책 해석 보강

기존 정책은 그대로 유지한다.

```text
필드 누락
null
""
"   "
→ None
```

실제 이메일 문자열이 있을 경우의 처리 흐름은 다음과 같이 보강한다.

```text
trim
→ 소문자 정규화
→ 이메일 형식 검증
→ 최대 255자 검증
→ 저장
```

별도 `/check-email` API를 추가하지 않는 기존 정책도 그대로 유지한다.

이메일 중복 여부는 회원가입 요청 시 Backend에서 최종 확인한다.

---

## 5. v1.0 Section 12 Validation / HTTP Status 정책 보강

`v1.0`의 다음 항목:

```text
email 형식 오류
→ 422
```

은 본 문서 이후 다음 두 경우를 포함한다.

```text
email 형식 오류
→ 422

email 최대 길이 255자 초과
→ 422
```

따라서 email 관련 Request Validation 실패는 공통 `RequestValidationError → 422` 정책을 유지한다.

중복 오류와 혼동하지 않는다.

```text
형식 또는 길이 오류
→ 422

기존 email 중복
→ 409 DUPLICATED_EMAIL
```

---

## 6. Backend 테스트 기준 보강

Backend Schema Validation에서는 다음 동작을 유지한다.

```text
유효한 이메일
→ 허용

잘못된 이메일 형식
→ Validation 실패 / 422 경로

255자 초과 이메일
→ Validation 실패 / 422 경로

email 필드 누락
→ None

null / 빈 문자열 / 공백 문자열
→ None
```

현재 Backend 테스트에는 255자를 초과하는 이메일을 거부하는 Schema Validation 검증이 존재한다.

따라서 `v1.0` Section 25.1의 Backend Schema / Router 테스트 범위는 다음 항목을 포함하는 것으로 보강한다.

```text
email 형식 오류 → 422
email 255자 초과 → 422
```

---

## 7. 변경하지 않는 사항

이번 정합성 보강으로 다음 정책은 변경하지 않는다.

```text
email 선택 여부

email 누락 / null / 공백
→ None

email 정규화
→ trim
→ 소문자 통일

email 중복
→ 409 Conflict
→ field = email
→ reason = DUPLICATED_EMAIL

별도 /check-email API
→ 추가하지 않음

Signup 성공
→ Access Token + Session 응답
→ 자동 로그인 흐름 유지

Frontend Client
→ publicApiClient

회원가입 Transaction
→ AuthService가 최종 경계 소유

AuthProvider / RootNavigator 기반 Navigation
→ 유지
```

비밀번호, `login_id`, `name`, 중복 Race Condition, Access Token, Session 계약 역시 본 문서의 변경 범위가 아니다.

---

## 8. 최종 정합성 기준

일반 회원가입 `email` 정책의 최종 기준은 다음과 같다.

```text
선택값

누락 / null / 빈 문자열 / 공백 문자열
→ None

실제 값 존재
→ trim
→ 소문자 정규화
→ EmailStr 형식 검증
→ 최대 255자

형식 오류 또는 255자 초과
→ 422

중복 email
→ 409 DUPLICATED_EMAIL

DB
→ users.email VARCHAR(255)
→ nullable
→ UNIQUE
```

본 보강 이후 `v1.0`에서 최대 길이를 명시하지 않은 표현은 설계 당시 문서 누락으로 해석하며, 현재 일반 회원가입의 `email` API 계약은 본 `v1.0.1`을 함께 기준으로 사용한다.
