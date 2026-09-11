# Trend Leader 관심사 조회 및 수정 설계 확정안 v1.0.2

- 문서명: 관심사 조회 및 수정 설계 확정안
- 프로젝트: Trend Leader
- 기준 Repository: `Trend-Leader-capstoneProject/feature`
- 기준 브랜치: `dev`
- 기준 커밋: `1ba1216b56a14cc7fd6e702d4d5671eb2c492841`
- 기준 시점: 2026-08-30
- 상태: 설계 확정
- 범위: 기존 관심사 조회 및 관심사 수정
- v1.0.1 동시성 보강 검증 기준:
  - 작업 브랜치: `feat-interest`
  - SQLAlchemy: `2.0.51`
  - MariaDB: `12.3.2`
  - Storage Engine: `InnoDB`
  - Transaction Isolation: `REPEATABLE-READ`
  - `innodb_snapshot_isolation=ON`
  - 실제 MariaDB 독립 Transaction Probe에서 `ER_CHECKREAD(1020)` 및 rollback 후 전체 Transaction Retry 검증 완료
- v1.0.2 보강 내용:
  - Section 20 / 21 Transaction 정책 일관성 정리
  - InterestService의 bounded whole-transaction retry 책임 명확화
  - 실제 MariaDB Concurrency Integration Test 범위 구체화
  - Phase 1 Router Contract와 Phase 4 실제 Handler 연결 시점 명확화
- 제외 범위:
  - Trend 조회/추천
  - 북마크
  - 검색
  - 회원정보 조회/수정
  - 비밀번호 변경
  - 회원 탈퇴
  - Google OAuth
  - Refresh Token / Token Rotation / Revocation
  - 관심 키워드 기능
  - 카테고리 관리용 Admin 기능

---

# 1. 문서 목적

이 문서는 Trend Leader의 현재 `dev` 브랜치에 반영된 다음 구조를 기준으로 **기존 관심사 조회와 관심사 수정 기능의 최종 설계**를 확정한다.

기준으로 유지하는 기존 구조:

```text
일반 로그인 / JWT Access Token 인증
인증 세션 관리 및 로그아웃
일반 회원가입
최초 관심사 저장
AuthProvider / RootNavigator 기반 인증 및 관심사 화면 분기
```

이번 설계의 핵심 원칙은 다음과 같다.

1. `POST /api/users/me/interests`는 최초 저장 전용으로 유지한다.
2. `GET /api/users/me/interests`는 현재 사용자의 저장된 관심사 집합을 조회한다.
3. `PUT /api/users/me/interests`는 기존 관심사 집합을 새로운 전체 집합으로 교체한다.
4. API 의미는 전체 교체이지만 DB에서는 기존 Row를 모두 삭제 후 재생성하지 않고 `keep / add / remove` 차이를 계산한다.
5. 관심사는 최소 1개 이상 유지한다.
6. 근거 없는 고정 최대 선택 개수는 새로 만들지 않는다.
7. 저장/수정 가능한 관심사는 **존재하는 활성 대분류 카테고리**로 제한한다.
8. Transaction의 최종 경계는 `InterestService`가 소유한다.
9. Repository는 조회 및 `add/delete/flush`를 담당하고 `commit/rollback`은 수행하지 않는다.
10. 정상적인 관심사 수정은 인증 Session의 `has_selected_interests / next_step`을 변경하지 않는다.
11. Frontend에서는 서버 관심사 상태와 화면의 편집 중 Draft 상태를 분리한다.
12. 관심사 수정 화면은 최초 관심사 선택 화면과 Use Case를 분리한다.
13. 동일 사용자의 동시 PUT은 Interest Row `FOR UPDATE`를 유지하되,
    MariaDB `ER_CHECKREAD(1020)` 발생 시 `InterestService`가 rollback 후
    새 Transaction에서 PUT Use Case 전체를 bounded retry한다.

---

# 2. 설계 기준 시점의 현재 dev 상태

## 2.1 Backend 관심사 API

현재 구현된 관심사 Endpoint는 다음 하나이다.

```http
POST /api/users/me/interests
```

현재 Router는:

```text
CurrentUserDep
→ InterestService.create_interests()
→ 201 Created
```

구조를 사용한다.

`GET /api/users/me/interests`와 `PUT /api/users/me/interests`는 아직 구현되어 있지 않다.

---

## 2.2 InterestService

현재 `InterestService.create_interests()`는 다음 책임을 가진다.

```text
기존 관심사 존재 여부 확인
→ 이미 있으면 409

요청 category_ids 조회
→ 존재하지 않음 검증
→ 비활성 검증
→ 하위 카테고리 검증

UserInterestCategory 생성
→ InterestRepository.save()
→ db.commit()

SQLAlchemyError
→ db.rollback()
→ 상위 전달
```

현재 카테고리 검증 규칙은 이번 GET/PUT 설계의 기반으로 유지한다.

---

## 2.3 InterestRepository

현재 Repository는 다음 메서드를 가진다.

```text
exists_by_user_id()
save()
```

`save()`는:

```text
db.add_all()
→ db.flush()
```

까지만 수행한다.

따라서 현재 프로젝트의 쓰기 책임은 다음처럼 구분되어 있다.

```text
Repository
→ DB 조회 / add / delete / flush

Service
→ Use Case 판단 / Transaction commit / rollback
```

이 원칙을 변경하지 않는다.

---

## 2.4 Interest Request Schema

현재 최초 관심사 저장 Request는 다음 규칙을 가진다.

```text
category_ids
- 정수 배열
- 최소 1개
- 배열 내부 중복 금지
```

PUT에서도 동일한 Request Validation 규칙을 유지한다.

---

## 2.5 DB 제약

`user_interest_categories`에는 다음 제약이 존재한다.

```text
UNIQUE(user_id, category_id)

user_id
→ users.user_id
→ ON DELETE CASCADE

category_id
→ categories.category_id
→ ON DELETE RESTRICT
```

초기 MVP에서는 관심사 `weight`를 사용하지 않는다.

관심사 Row의 `created_at`은 관심 카테고리 선택 시각을 의미한다.

---

## 2.6 Category 구조

현재 카테고리는:

```text
parent_id IS NULL
→ 대분류

parent_id IS NOT NULL
→ 세부분류
```

로 판단한다.

현재 최초 관심사 저장에서도:

```text
존재
AND
is_active = true
AND
parent_id IS NULL
```

인 카테고리만 허용한다.

이 규칙을 관심사 수정에서도 그대로 유지한다.

---

## 2.7 Frontend 관심사 구조

현재 관심사 Feature에는 다음 흐름이 존재한다.

```text
getCategories.ts
saveUserInterests.ts

useCategories.ts
useSaveInterests.ts

InterestSelectScreen.tsx
```

현재 최초 관심사 저장은 `authenticatedApiClient`를 사용한다.

`InterestSelectScreen`은 최초 저장 성공 시:

```text
completeInterestSelection()
```

을 호출하고,

기존 관심사 존재로 `409`가 발생하면:

```text
revalidateSession()
```

을 호출한다.

이 구조는 최초 Onboarding Use Case로 유지한다.

---

# 3. 이번 기능의 최종 API 구성

최종 관심사 API는 다음 세 개로 구성한다.

| Method | Endpoint | 역할 |
|---|---|---|
| `POST` | `/api/users/me/interests` | 최초 관심사 저장 |
| `GET` | `/api/users/me/interests` | 현재 관심사 조회 |
| `PUT` | `/api/users/me/interests` | 기존 관심사 전체 교체 |

세 Endpoint 모두 인증된 사용자 기준으로 동작한다.

Frontend에서는 `authenticatedApiClient`를 사용한다.

`POST`의 기존 의미를 변경하지 않는다.

---

# 4. 관심사 선택 개수 정책

## 4.1 최소 선택 수

최소 1개를 유지한다.

```text
POST 최초 저장
→ 최소 1개

PUT 수정
→ 최소 1개
```

관심사를 0개로 만드는 수정은 허용하지 않는다.

### 이유

현재 인증 Session은 관심사 Row 존재 여부로:

```text
has_selected_interests
next_step
```

을 계산한다.

정상적인 관심사 수정 과정에서 관심사를 0개로 허용하면:

```text
MAIN
→ INTEREST_SELECTION
```

상태 전이가 발생하게 된다.

이번 관심사 수정 기능은 이미 Onboarding을 완료한 사용자의 추천 기준을 변경하는 기능이므로 최소 1개를 유지한다.

---

## 4.2 최대 선택 수

고정 숫자 제한을 추가하지 않는다.

```text
fixed max = 없음
```

실질적인 최대 선택 가능 수는 현재 선택 가능한 활성 대분류 카테고리 수이다.

### 이유

현재 기획 및 코드에는:

```text
최대 3개
최대 5개
```

등의 제품 정책이 존재하지 않는다.

근거 없이 새로운 숫자 제한을 도입하지 않는다.

향후 추천 품질 또는 UX 실험을 통해 최대 개수 정책이 필요해지면 POST / PUT / Frontend를 같은 변경 단위로 재설계한다.

---

# 5. GET /api/users/me/interests

## 5.1 목적

현재 인증된 사용자가 DB에 저장한 관심 카테고리 집합을 조회한다.

---

## 5.2 Request

```http
GET /api/users/me/interests
Authorization: Bearer <access_token>
```

Request Body는 없다.

---

## 5.3 성공 Response

```http
200 OK
```

예시:

```json
{
  "success": true,
  "statusCode": 200,
  "message": "관심사를 조회했습니다.",
  "data": {
    "selected_category_ids": [1, 4, 6],
    "selected_count": 3
  }
}
```

---

## 5.4 관심사가 없는 경우

관심사가 전혀 없는 사용자의 GET은 오류가 아니다.

```http
200 OK
```

```json
{
  "success": true,
  "statusCode": 200,
  "message": "관심사를 조회했습니다.",
  "data": {
    "selected_category_ids": [],
    "selected_count": 0
  }
}
```

### 이유

`/users/me/interests`는 특정 Row 하나를 찾는 API가 아니라 현재 사용자의 관심사 Collection 조회이다.

따라서 빈 Collection은 `404`가 아니라 정상적인 `200 + []`로 처리한다.

---

# 6. GET Response에서 카테고리 상세 객체를 중복 반환하지 않음

GET 관심사 API는 선택된 Category ID 집합만 반환한다.

```text
selected_category_ids
selected_count
```

카테고리 이름, 코드, 표시 순서 등은 기존:

```http
GET /api/categories
```

의 책임으로 유지한다.

Frontend 관심사 수정 화면은 다음 두 데이터 소스를 조합한다.

```text
GET /api/categories
→ 현재 선택 가능한 카테고리 Master Data

GET /api/users/me/interests
→ 현재 사용자의 선택 상태
```

### 이유

관심사 수정 화면에서는 선택 가능한 전체 카테고리 목록이 필요하므로 `/categories` 조회가 어차피 필요하다.

관심사 API가 Category DTO 전체를 다시 복제하면 Category Master Data의 책임이 중복된다.

---

# 7. 관심사 배열의 순서 의미

사용자 관심사는 순서가 있는 목록이 아니라 집합으로 취급한다.

```text
{1, 4, 6}
==
{6, 1, 4}
```

`user_interest_categories`에는 별도 사용자 정렬 순서가 없다.

따라서 Backend의 비교는 집합 기준으로 수행한다.

GET / PUT Response의 `selected_category_ids`는 테스트 안정성을 위해 구현 시 결정적인 순서를 사용한다.

권장 기준:

```text
category_id 오름차순
```

Frontend는 배열 순서 자체에 비즈니스 의미를 부여하지 않는다.

---

# 8. PUT /api/users/me/interests

## 8.1 목적

현재 인증된 사용자의 기존 관심사 집합을 요청된 새로운 전체 집합으로 수정한다.

---

## 8.2 Request

```http
PUT /api/users/me/interests
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "category_ids": [1, 4, 6]
}
```

`category_ids`는 추가할 ID만 의미하지 않는다.

다음 의미로 고정한다.

> 요청 성공 이후 사용자가 최종적으로 가지고 있어야 하는 전체 관심사 카테고리 집합

---

# 9. PUT 전체 교체 방식 채택

관심사 수정 API는 증분 `add/remove` 방식이 아니라 전체 집합 전달 방식을 사용한다.

## 9.1 채택하지 않는 방식

```json
{
  "add": [4],
  "remove": [2]
}
```

이 방식은 Frontend가 서버 상태와 자신의 변경분을 별도로 계산해야 한다.

---

## 9.2 채택 방식

기존:

```text
{1, 2}
```

사용자 편집 결과:

```text
{1, 4}
```

Request:

```json
{
  "category_ids": [1, 4]
}
```

Backend가 내부에서 다음을 계산한다.

```text
current   = {1, 2}
requested = {1, 4}

keep   = {1}
remove = {2}
add    = {4}
```

### 선택 이유

관심사는 소수의 카테고리 ID 집합이며 Frontend는 이미 화면에서 최종 선택 상태 전체를 관리한다.

API 계약을 단순하게 유지하고 Client와 Server의 상태 차이를 Backend에서 계산하는 편이 안정적이다.

---

# 10. API는 전체 교체, DB는 diff 수정

PUT 전체 교체를 다음처럼 구현하지 않는다.

```text
DELETE all existing interests
→ INSERT all requested interests
```

대신:

```text
keep
→ 유지

remove
→ DELETE

add
→ INSERT
```

방식을 사용한다.

### 이유

기존 관심사 Row의 `created_at`은 해당 관심사를 선택한 시각을 의미한다.

예:

```text
기존
패션, 게임

수정
패션, 음식
```

전체 삭제 후 재삽입하면 계속 유지한 `패션`의 `created_at`까지 새 값으로 바뀐다.

따라서 유지되는 Row는 그대로 보존한다.

---

# 11. PUT Request Validation

PUT의 Request Validation은 최초 저장과 동일한 규칙을 사용한다.

```text
category_ids
- list[int]
- 최소 1개
- 배열 내부 중복 금지
```

다음은 `422 Unprocessable Entity`이다.

```text
category_ids 누락
빈 배열
중복 ID
정수가 아닌 값
Request Schema 자체가 거부하는 형식 오류
```

POST와 PUT의 Validator가 서로 달라지지 않도록 공통화 여부를 구현 단계에서 검토한다.

외부 API Contract는 확정하지만 내부 Pydantic Class 이름까지 본 문서에서 강제하지 않는다.

---

# 12. 활성 대분류 카테고리 검증

PUT에서는 요청된 모든 Category가 다음 조건을 만족해야 한다.

```text
① 존재하는 Category
② is_active = true
③ parent_id IS NULL
```

하나라도 규칙을 만족하지 않으면 수정 Transaction을 확정하지 않는다.

---

# 13. 존재하지 않는 Category 처리

예:

```json
{
  "category_ids": [1, 999]
}
```

`999`가 존재하지 않으면:

```http
404 Not Found
```

Machine-readable Data:

```json
{
  "category_ids": [999]
}
```

현재 최초 저장 정책과 동일하게 유지한다.

---

# 14. 비활성 / 하위 Category 처리

## 14.1 비활성 Category

```http
400 Bad Request
```

예시 Data:

```json
{
  "inactive_category_ids": [3],
  "child_category_ids": []
}
```

---

## 14.2 하위 Category

```http
400 Bad Request
```

예시 Data:

```json
{
  "inactive_category_ids": [],
  "child_category_ids": [12]
}
```

---

## 14.3 둘 다 포함된 경우

현재 최초 저장처럼 한 번의 검증 결과에 두 목록을 모두 반환할 수 있다.

Frontend는 문자열 메시지를 파싱하지 않고 Data를 기준으로 현재 Category 목록을 재조회하고 사용자의 선택을 다시 확인하도록 한다.

---

# 15. PUT인데 기존 관심사가 없는 경우

POST와 PUT의 Use Case를 분리한다.

```text
POST
→ 최초 관심사 설정

PUT
→ 이미 설정된 관심사 수정
```

따라서 PUT 요청 시 기존 관심사가 하나도 없다면 Upsert로 새로 만들지 않는다.

```http
409 Conflict
```

권장 응답:

```json
{
  "success": false,
  "statusCode": 409,
  "message": "수정할 기존 관심사가 없습니다.",
  "data": {
    "reason": "INTERESTS_NOT_INITIALIZED"
  }
}
```

### 이유

이 상태는 보통 Frontend Auth Session은 사용자가 이미 `MAIN` 단계라고 생각하지만 Backend DB에는 관심사가 없는 상태 불일치일 수 있다.

따라서 단순 생성으로 숨기기보다 상태를 명확히 드러내고 Session을 재동기화한다.

---

# 16. 동일 관심사 재저장 처리

현재 DB:

```text
{1, 4, 6}
```

Request:

```text
{6, 1, 4}
```

는 동일한 관심사 집합이다.

이 경우:

```text
409 X
DELETE X
INSERT X
```

으로 처리한다.

최종 결과는:

```http
200 OK
```

이다.

즉 PUT은 멱등적으로 동작한다.

### Transaction 주의

PUT 구현에서 `FOR UPDATE` Lock을 획득한 뒤 동일 집합임을 확인한 경우에도 Lock을 의도적으로 열린 채로 두지 않는다.

현재 프로젝트의 명시적 Transaction 스타일을 유지한다면 실제 Row 변경은 없어도 Transaction을 정상 종료한 뒤 응답한다.

---

# 17. PUT 성공 Response

```http
200 OK
```

```json
{
  "success": true,
  "statusCode": 200,
  "message": "관심사를 수정했습니다.",
  "data": {
    "selected_category_ids": [1, 4, 6],
    "selected_count": 3
  }
}
```

Response는 실제 Commit이 완료된 최종 관심사 상태를 의미한다.

---

# 18. InterestRepository 책임 분리

이번 구현 이후 Repository에는 다음 책임이 필요하다.

```text
exists_by_user_id()
→ Auth Session / 최초 저장 존재 확인

find_by_user_id()
→ GET 관심사 조회

find_by_user_id_for_update()
→ PUT 수정 Transaction용 현재 관심사 조회 + Lock

save()
→ 추가 대상 Row add + flush

delete()
→ 제거 대상 Row delete
```

정확한 메서드명은 현재 프로젝트 네이밍 컨벤션을 기준으로 구현 시 확정할 수 있다.

중요한 것은 책임 경계이다.

Repository는 다음 비즈니스 판단을 수행하지 않는다.

```text
활성 카테고리인지
대분류인지
최소 개수를 만족하는지
현재와 같은 집합인지
PUT 가능한 상태인지
```

이 판단은 `InterestService`의 책임이다.

---

# 19. InterestService 책임

`InterestService`는 한 사용자의 관심사 집합에 대한 Use Case와 최종 Transaction 경계를 소유한다.

추가되는 개념적 책임:

```text
get_interests(user_id)
update_interests(user_id, category_ids)
```

정확한 함수명은 현재 코드 컨벤션에 맞춘다.

Service가 담당할 핵심 흐름:

```text
GET
→ Repository 조회
→ selected IDs 구성
→ Response Data 반환

PUT
→ bounded Transaction Attempt 시작
→ Request Category 조회
→ Category 규칙 검증
→ 현재 Interest Row Lock + 조회
→ 기존 관심사 존재 여부 검증
→ current/requested diff 계산
→ 동일 집합 No-op 처리
→ remove / add 실행
→ commit
→ 최종 Response Data 반환
```

MariaDB `ER_CHECKREAD(1020)`이 발생하면 일반 DB 오류와 구분하여 다음 흐름을 적용한다.

```text
ER_CHECKREAD(1020)
→ 현재 Transaction rollback
→ Retry 가능 횟수 확인

Retry 가능
→ 새 Transaction에서 PUT Use Case 전체 재실행
→ Category 조회/검증부터 다시 수행
→ Interest Lock 조회
→ existing-state 검증
→ diff 재계산
→ delete / add / flush / commit

Retry 소진
→ DB 오류 상위 전달
```

Retry는 `FOR UPDATE` 문장만 다시 실행하는 방식이 아니라 **PUT Transaction Attempt 전체를 새 Transaction에서 다시 수행하는 방식**으로 한다.

Repository는 Retry 여부를 판단하지 않으며, `commit()` / `rollback()`도 수행하지 않는다.

---

# 20. Transaction / rollback 정책

최종 결정:

```text
InterestService가 Transaction 경계를 소유한다.
```

Repository는 `commit()` 또는 `rollback()`을 호출하지 않는다.

PUT 변경 작업 중 SQLAlchemy DB 오류가 발생하면 `InterestService`가 현재 Transaction을 rollback한다.

기본 정책:

```text
일반 SQLAlchemy DB 오류
→ rollback
→ 예외 상위 전달
```

예:

```text
delete 중 실패
save/flush 중 실패
commit 중 실패
```

단, Section 21에서 정의한 MariaDB `ER_CHECKREAD(1020)`은 동일 사용자 PUT 동시성 처리 과정에서 실제 환경으로 재현된 특별한 Transaction 충돌이므로 별도 정책을 적용한다.

```text
ER_CHECKREAD(1020)
→ rollback
→ Retry 가능 횟수가 남아 있으면
  새 Transaction에서 PUT Use Case 전체 재실행

Retry 소진
→ 기존 DB 오류를 상위에 전달
```

`1020` 이외의 알 수 없는 DB 오류를 일반 Retry 대상으로 확대하지 않는다.

알 수 없는 DB 오류 또는 Retry 소진 오류를 임의의 Domain `409`로 변환하지 않는다.

Retry는 반드시 bounded 하게 수행하며 무한 반복하지 않는다.

정확한 최대 Retry 횟수와 Retry exhaustion 처리의 세부 구현값은 Phase 3 `InterestService` 구현 전에 별도로 확정한다.

---

# 21. PUT 동시성 / Race Condition

관심사 수정은 같은 사용자의 두 PUT 요청이 동시에 실행될 수 있다.

예:

```text
초기
{1, 2}

Request A
{1, 3}

Request B
{2, 4}
```

두 요청이 같은 이전 상태를 읽고 각각 diff를 적용하면 잘못된 구현에서는 최종 상태가 어느 요청의 의도와도 다르게 합쳐질 수 있다.

따라서 수정 Transaction에서는 일반 GET과 구분하여 현재 사용자의 Interest Row를 잠그는 조회를 사용한다.

개념:

```sql
SELECT ...
FROM user_interest_categories
WHERE user_id = :user_id
FOR UPDATE
```

같은 사용자의 관심사 수정 Transaction은 사용자의 현재 Interest Row에 `SELECT ... FOR UPDATE` 계열 Lock을 사용하여 동시에 같은 이전 상태를 기준으로 diff를 적용하지 않도록 한다.

현재 Trend Leader 테스트 환경은:

- SQLAlchemy `2.0.51`
- MariaDB `12.3.2`
- InnoDB
- `REPEATABLE-READ`
- `innodb_snapshot_isolation=ON`

이다.

실제 MariaDB의 서로 독립된 두 Transaction Probe에서 다음 동작이 확인되었다.

```text
Transaction B
→ 일반 SELECT
→ 기존 read view 형성

Transaction A
→ Interest Row FOR UPDATE
→ 관심사 수정
→ commit

Transaction B
→ 동일 Interest Row FOR UPDATE
→ A의 Lock 때문에 대기
→ A commit 이후 ER_CHECKREAD(1020) 발생
```

실제 오류:

```text
(1020,
 "Record has changed since last read in table
 'user_interest_categories'; try restarting transaction")
```

따라서 `FOR UPDATE`만으로:

```text
A commit
→ B가 자동으로 최신 상태를 읽고 계속 처리
```

한다고 가정하지 않는다.

PUT 실행 중 `ER_CHECKREAD(1020)`이 발생하면 다음 정책을 사용한다.

1. `InterestService`가 현재 Transaction을 rollback한다.
2. 제한된 Retry 횟수가 남아 있으면 새 Transaction에서 PUT Use Case 전체를 다시 수행한다.
3. Retry에서는 요청 Category 조회/검증, 현재 Interest Lock 조회,
   existing-state 검증, current/requested diff 계산, delete/add/flush/commit을
   모두 새 Transaction 기준으로 다시 수행한다.
4. `FOR UPDATE` 문장만 단독 Retry하지 않는다.
5. `1020` 이외의 알 수 없는 DB 오류는 Retry 대상으로 일반화하지 않고
   기존 정책대로 rollback 후 상위에 전달한다.
6. Retry 횟수는 무한으로 두지 않고 bounded 한다.
7. 최대 Retry 횟수의 정확한 값은 Phase 3 `InterestService` 구현 전에 별도로 확정한다.

Probe에서는 `ER_CHECKREAD(1020)` 후:

```text
rollback
→ 새 Transaction
→ 최신 Interest 상태 재조회
→ 최신 상태 기준 diff 재계산
→ 두 번째 PUT 전체 교체
→ commit
```

흐름이 정상적으로 완료되고, 최종 DB 상태가 마지막으로 성공한 PUT 요청의 전체 집합과 정확히 일치함을 확인했다.

정식 완료 판정은 실제 MariaDB의 서로 독립된 Connection / Session / Transaction을 사용한 Concurrency Integration Test로 수행한다.

### 설계 목표

동일 사용자의 동시 PUT은 DB 내부에서 항상 오류 없이 한 번에 이어서 실행되는 것이 목표가 아니다.

최종적으로는 각 성공한 PUT이 **자신보다 먼저 완료된 최신 Commit 상태를 기준으로 전체 교체를 수행하여, 실행 결과가 순차 실행과 동등한 효과를 가져야 한다.**

개념:

```text
A가 현재 상태 Lock
→ A 수정 + commit

B가 Lock 획득을 계속할 수 있는 경우
→ 최신 상태 기준으로 수정

B가 ER_CHECKREAD(1020)을 받은 경우
→ rollback
→ 새 Transaction에서 전체 PUT Retry
→ 최신 상태 다시 Lock + 조회
→ 그 상태 기준으로 diff 재계산
→ B 수정 + commit
```

따라서 성공한 동시 PUT들의 변경이 서로 섞여 어느 요청의 최종 집합과도 일치하지 않는 상태가 만들어져서는 안 된다.

별도의 version 컬럼, ETag, 사용자 관심사 Aggregate 테이블 추가는 현재 MVP 범위에 포함하지 않는다.

---

# 22. GET과 PUT의 Category 상태 불일치

GET 관심사는 DB에 저장된 사용자 선택 ID를 기준으로 반환한다.

반면 `/categories`는 현재 활성 Category를 반환한다.

향후 운영 중 기존 선택 Category가 비활성화되는 경우 두 결과 사이에 일시적인 불일치가 생길 수 있다.

현재 MVP에서는 Category Master가 안정적으로 관리된다는 전제를 유지하되, Frontend 수정 화면은 다음 원칙을 따른다.

```text
현재 /categories에 존재하는 활성 대분류
→ 선택 가능한 항목

기존 selected_category_ids 중 현재 선택 가능 목록에 없는 ID
→ 새 PUT Request에 무조건 그대로 포함하지 않음
→ 사용자가 현재 유효한 관심사를 최소 1개 선택하도록 유도
```

카테고리 비활성화가 사용자 관심사에 미치는 장기 정책과 Admin 기능은 이번 범위 밖이다.

---

# 23. Frontend 관심사 수정 화면 분리

최초 관심사 선택 화면과 수정 화면을 분리한다.

```text
InterestSelectScreen
→ 최초 관심사 설정 / Onboarding 전용

InterestEditScreen
→ 이미 관심사가 있는 사용자의 수정 전용
```

### 이유

최초 설정은:

```text
POST
→ completeInterestSelection()
→ Auth Session next_step MAIN
→ RootNavigator Tree 변경
```

수정은:

```text
GET 기존 상태
→ PUT 수정
→ MAIN 상태 유지
→ 이전 화면으로 복귀
```

로 Use Case가 다르다.

한 Screen에 POST / PUT / Auth 전환 / 일반 Navigation 책임을 모두 섞지 않는다.

---

# 24. 공통 UI Component 재사용

화면은 분리하지만 Category 선택 UI는 재사용할 수 있다.

현재의:

```text
InterestCategoryOption
```

을 유지하고 필요하면 다음과 같은 순수 UI Component를 추가한다.

```text
InterestCategorySelector
```

권장 입력:

```text
categories
selectedIds
disabled
onToggle
```

이 Component는 API, AuthProvider, Navigation을 직접 알지 않는다.

---

# 25. Frontend 초기 조회 방식

InterestEditScreen 진입 시 다음 두 Query를 독립적으로 수행한다.

```text
useCategories()
→ GET /api/categories

useUserInterests()
→ GET /api/users/me/interests
```

두 요청 사이에 의존성이 없으므로 순차 호출로 만들지 않는다.

두 Query가 준비되면:

```text
Category Master Data
+
selected_category_ids
```

를 조합하여 화면의 초기 선택 상태를 만든다.

---

# 26. Server State와 Draft State 분리

관심사 수정 중에는 서버 상태와 편집 중 상태를 분리한다.

```text
Server State
→ TanStack Query의 GET /users/me/interests 결과

Draft State
→ InterestEditScreen의 selectedCategoryIds
```

예:

```text
Server
[1, 4]

화면 초기 Draft
[1, 4]

사용자가 6 추가

Server
[1, 4]

Draft
[1, 4, 6]
```

PUT 성공 전까지 Query Cache를 사용자의 임시 선택값으로 변경하지 않는다.

---

# 27. Draft 초기화 및 Background Refetch 정책

Query Data가 바뀔 때마다 Draft를 무조건 덮어쓰지 않는다.

다음 원칙을 사용한다.

```text
최초 GET 성공
→ Draft 초기화

사용자가 편집 시작
→ Background Refetch 결과로 Draft 자동 덮어쓰기 금지

PUT 성공
→ Server Cache와 Draft를 성공 결과로 동기화

명시적 재시도 / Reset이 필요한 오류
→ 필요한 경우 다시 동기화
```

사용자가 편집 중인데 Background Query가 다시 들어왔다는 이유로 선택이 사라지지 않아야 한다.

---

# 28. 저장 버튼 정책

InterestEditScreen의 저장 버튼은 최소 다음 상황에서 비활성화한다.

```text
선택 0개
Mutation Pending
변경 없음
```

변경 여부는 배열 순서가 아니라 집합 기준으로 비교한다.

Frontend에서 변경 없음 PUT을 막더라도 Backend는 직접 같은 요청이 들어오는 경우 `200 No-op`을 보장한다.

---

# 29. TanStack Query Query Key

사용자 관심사 Query는 사용자 관련 Server State로 관리한다.

권장 개념:

```ts
userInterestQueryKeys = {
  all: ["user-interests"],
  me: ["user-interests", "me"]
}
```

정확한 Object 작성 방식은 현재 프로젝트 Query Key 컨벤션에 맞춘다.

현재 로그아웃에서 Query Cache 전체를 정리하므로 MVP에서 Query Key에 `user_id`를 강제로 포함하지 않는다.

---

# 30. PUT 성공 후 Cache 처리

PUT Response는 Commit 완료 후 서버의 최종 관심사 상태를 반환한다.

따라서 성공 시 별도 GET을 즉시 다시 호출하기보다 Mutation Response를 사용자 관심사 Query Cache에 반영한다.

개념:

```text
PUT 200
→ queryClient.setQueryData(userInterestQueryKey, response)
→ Draft 동기화
→ Navigation goBack()
```

`categories` Query Cache는 수정하지 않는다.

사용자의 관심사를 바꿨다고 Category Master Data가 변경된 것은 아니기 때문이다.

---

# 31. 향후 맞춤 Trend Cache와의 관계

관심사 변경은 향후 관심사 기반 추천 Trend 결과에 영향을 준다.

Trend Query가 구현되면 PUT 성공 시 해당 추천 Query를 stale/invalidate해야 한다.

그러나 Trend 조회는 이번 기능 범위 밖이다.

따라서 이번 구현에서는 존재하지 않는 Trend Query Key를 미리 만들거나 Trend API를 추가하지 않는다.

후속 Extension Point로만 기록한다.

---

# 32. 정상 수정 성공과 AuthProvider 관계

정상 PUT 성공에서는 다음을 호출하지 않는다.

```text
completeInterestSelection() X
revalidateSession() X
AuthState 직접 수정 X
```

이유:

사용자는 이미:

```text
has_selected_interests = true
next_step = MAIN
```

상태이며 최소 1개 정책 때문에 정상 수정 후에도 이 상태가 유지된다.

정상 성공 흐름:

```text
PUT 200
→ 사용자 관심사 Query Cache 갱신
→ goBack()
```

이다.

---

# 33. 409 INTERESTS_NOT_INITIALIZED와 Auth Session

PUT에서:

```text
409
reason = INTERESTS_NOT_INITIALIZED
```

가 발생하면 Frontend와 Backend의 Session 상태가 어긋났을 가능성이 있다.

이 경우:

```text
InterestEditScreen
→ revalidateSession()
→ GET /api/auth/session
→ Backend 상태를 Source of Truth로 재확인
```

한다.

Session 결과가:

```text
next_step = INTEREST_SELECTION
```

이라면 `RootNavigator`가 자동으로 AppNavigator를 제거하고 OnboardingNavigator를 선택한다.

InterestEditScreen이 직접 InterestSelectScreen으로 Navigation하지 않는다.

---

# 34. 401 처리

GET / PUT은 모두 `authenticatedApiClient`를 사용한다.

따라서 인증 실패 `401`은 기존 공통 인증 실패 처리 정책에 위임한다.

InterestEditScreen에서 별도의 인증 Alert나 Login Navigation을 직접 수행하지 않는다.

기존의 다음 정책을 그대로 유지한다.

```text
Authenticated Client 401
→ Request Token == Current Token 검증
→ Stale 401 무시
→ 현재 세션 실패이면 Session Cleanup
→ RootNavigator가 Login Tree 선택
```

---

# 35. 수정 성공 후 Navigation

InterestEditScreen은 일반 AppNavigator 내부 화면으로 취급한다.

정상 성공 시:

```text
Cache 갱신
→ navigation.goBack()
```

을 사용한다.

Auth Session Tree 자체를 교체하지 않는다.

현재 AppNavigator에는 Main Placeholder만 존재하므로 구현 시 `InterestEdit` Route 등록이 필요하다.

마이페이지 또는 회원정보 화면에서 실제 진입 버튼을 제공하는 것은 해당 후속 기능 범위이다.

이번 구현을 위해 MainPlaceholder에 임시 제품 기능을 임의로 추가하지 않는다.

실기기 Acceptance Test 진입 방식이 필요하면 구현 단계에서 테스트용 비영구 접근 방법을 별도로 정하고 커밋 전 제거 여부를 확인한다.

---

# 36. Backend 응답 Schema 내부 이름

외부 API Contract는 다음 두 값으로 고정한다.

```text
selected_category_ids
selected_count
```

현재 `InterestCreateData`가 동일 구조를 사용하고 있다.

GET / PUT 추가 시 내부 Pydantic Schema를:

```text
기존 Create 전용 이름 유지 + Read/Update 별도 타입
```

으로 둘지,

```text
세 Endpoint가 공유 가능한 중립적인 Response Data 타입으로 최소 일반화
```

할지는 구현 시작 시 현재 import 및 테스트 영향 범위를 확인한 뒤 결정한다.

불필요한 대규모 이름 변경은 하지 않는다.

---

# 37. Backend 최종 API 계약

## 37.1 GET

```text
GET /api/users/me/interests

Authentication:
필수

Frontend Client:
authenticatedApiClient

Success:
200 OK
```

Data:

```json
{
  "selected_category_ids": [1, 4],
  "selected_count": 2
}
```

가능한 오류:

```text
401
→ 인증 실패

500
→ 예상하지 못한 서버/DB 오류
→ `ER_CHECKREAD(1020)` bounded retry 소진 후 상위로 전달된 DB 오류 포함
```

관심사 없음은 오류가 아니다.

---

## 37.2 PUT

```text
PUT /api/users/me/interests

Authentication:
필수

Frontend Client:
authenticatedApiClient
```

Request:

```json
{
  "category_ids": [1, 4]
}
```

Success:

```text
200 OK
```

Data:

```json
{
  "selected_category_ids": [1, 4],
  "selected_count": 2
}
```

오류:

```text
400
→ 비활성 / 하위 Category

401
→ 인증 실패

404
→ 존재하지 않는 Category

409
→ INTERESTS_NOT_INITIALIZED

422
→ Request Validation

500
→ 예상하지 못한 서버/DB 오류
```

---

# 38. Backend 테스트 범위

## 38.1 Schema / Router

```text
GET 정상
→ 200

GET 관심사 없음
→ 200 + []

GET 인증 실패
→ 401

PUT 정상
→ 200

PUT 빈 category_ids
→ 422

PUT 중복 category_ids
→ 422

PUT 잘못된 타입
→ 422

PUT 인증 실패
→ 401
```

---

## 38.2 InterestService

```text
GET 기존 관심사 반환

PUT
current {1,2}
requested {1,3}
→ 1 유지
→ 2 삭제
→ 3 추가
→ commit

동일 집합
→ insert/delete 없음
→ 정상 Transaction 종료
→ 200

기존 관심사 없음
→ 409 INTERESTS_NOT_INITIALIZED

존재하지 않는 Category
→ 404

비활성 Category
→ 400

하위 Category
→ 400

삭제 실패
→ rollback

저장/flush 실패
→ rollback

commit 실패
→ rollback

ER_CHECKREAD(1020)
→ rollback
→ Retry 가능 시 PUT Use Case 전체 재실행
→ Category 조회/검증부터 다시 수행

Retry 이후
→ 최신 Interest 상태 다시 조회
→ 최신 상태 기준 diff 재계산
→ 정상 commit

1020 이외 OperationalError / SQLAlchemyError
→ Retry하지 않음
→ rollback
→ 상위 전달

Retry 횟수 소진
→ 무한 Retry 없음
→ rollback
→ 최종 DB 오류 상위 전달

알 수 없는 DB 오류
→ 임의 Domain 409 변환 금지
```

---

## 38.3 Repository Integration

최소 다음을 검증한다.

```text
find_by_user_id()
→ 해당 사용자 Interest만 반환

find_by_user_id_for_update()
→ 현재 사용자 Interest 조회
→ SQLAlchemy FOR UPDATE 조회 사용

save()
→ 추가 Row 저장

delete()
→ 지정 Row 제거

다른 사용자의 Interest에는 영향 없음
```

Repository Integration은 현재 프로젝트의 실제 MariaDB 테스트 환경을 사용한다.

`FOR UPDATE`의 실제 동시 Lock 의미와 `ER_CHECKREAD(1020)` Retry 흐름은 단일 `db_session`만으로 완료 판정하지 않고 별도의 Concurrency Integration Test에서 검증한다.

SQLite 등 실제 Lock 의미가 다른 환경만으로 동시성 완료 판정을 하지 않는다.

---

## 38.4 Transaction Integration

중요 시나리오:

```text
기존 {1,2}
→ 2 삭제
→ 3 추가 중 오류
→ rollback
→ DB는 다시 {1,2}
```

즉 코드상 rollback 호출만 확인하지 않고 실제 DB 최종 상태까지 검증한다.

No-op을 포함한 성공 경로에서도 Transaction이 정상 종료되어 Lock이 불필요하게 유지되지 않는지 확인한다.

---

## 38.5 MariaDB Concurrency Integration

동시 PUT 완료 판정은 실제 MariaDB와 서로 독립된 두 Connection / Session / Transaction을 사용한다.

현재 프로젝트 테스트 구조에서는 일반 `db_session` 하나를 공유하지 않고 `test_engine`을 기반으로 독립 Session A / Session B를 생성하는 방식을 사용한다.

최소 다음 Race 시나리오를 검증한다.

```text
초기
{1,2}

A 목표
{1,3}

B 목표
{2,3}

B에서 기존 read view가 먼저 형성될 수 있는 조건 구성

A
→ Interest FOR UPDATE
→ 수정
→ commit

B
→ FOR UPDATE 대기
→ ER_CHECKREAD(1020) 발생 가능
→ rollback
→ 새 Transaction에서 PUT 전체 Retry
→ A가 commit한 최신 상태 재조회
→ B 목표 기준 diff 재계산
→ commit

Final DB
→ B 요청 전체 집합과 정확히 일치
```

추가 확인:

```text
혼합 최종 집합 없음
중복 Interest Row 없음
keep 대상 Row의 created_at 보존
다른 사용자의 Interest 영향 없음
비-1020 DB 오류는 Retry하지 않음
Retry exhaustion 시 무한 반복 없음
```

탐색 단계의 임시 Probe는 제품 코드 완료 판정의 대체물이 아니며,
Phase 3 구현 후 위 시나리오를 정식 Regression Test로 승격한다.

---

# 39. Frontend 테스트 범위

최소 다음을 검증한다.

```text
GET 기존 관심사
→ 기존 선택 상태 표시

Category Query + Interest Query 로딩 처리

기존 선택 해제
신규 선택 추가

선택 0개
→ 저장 비활성

변경 없음
→ 저장 비활성

PUT Request
→ 최종 전체 category_ids 전송

PUT 200
→ user interests Query Cache 갱신
→ goBack
→ completeInterestSelection 미호출
→ revalidateSession 미호출

동일 집합 200
→ 정상 처리

400 / 404
→ 현재 Category/Interest 상태 재확인 안내

409 INTERESTS_NOT_INITIALIZED
→ revalidateSession

401
→ 화면 자체 인증 Alert 없음
→ 공통 401 처리에 위임

Network / 5xx
→ Draft 선택 유지
→ 재시도 가능

Background Refetch
→ 사용자가 편집 중인 Draft를 임의로 덮어쓰지 않음
```

---

# 40. 실제 기기 Acceptance Test

최소 다음 시나리오를 검증한다.

```text
01. 관심사가 있는 계정으로 Main 진입

02. InterestEdit 화면 진입
    → 기존 관심사 선택 상태 표시

03. 관심사 하나 해제 + 다른 관심사 추가

04. 저장
    → 200
    → 이전 App 화면으로 복귀

05. 다시 InterestEdit 진입
    → 변경된 선택 상태 유지

06. 앱 완전 종료 후 재실행
    → Session Restore는 MAIN 유지

07. 관심사 수정 후 Android Back
    → Login / Signup / InterestSelect로 이동하지 않음

08. 네트워크 실패 중 수정
    → Draft 유지
    → 재시도 가능

09. 잘못된 / 만료 Token
    → 공통 401 Session Cleanup
    → Login

10. 서버 상태가 관심사 없음으로 변경된 상태에서 PUT
    → 409 INTERESTS_NOT_INITIALIZED
    → Session revalidation
    → INTEREST_SELECTION으로 Root Tree 전환
```

동시 PUT Race는 실제 기기 UI만으로 완료 판정하지 않고 Backend Integration Test에서 별도로 검증한다.

---

# 41. 구현 순서 최종 확정

## Phase 1 — Backend Contract

```text
1. GET / PUT Request·Response Schema 정리
2. Router HTTP Contract 확정
   - Method / Path
   - Authentication
   - Request / Response Schema
   - Status Code
   - 실제 Handler-Service 연결은 Phase 4에서 수행
3. 기존 POST Schema와 Validator 중복 여부 최소 정리
```

Phase 1에서는 구현되지 않은 Service 메서드를 Router에 미리 연결하여 Runtime Endpoint를 불완전한 상태로 만들지 않는다.

---

## Phase 2 — Repository

```text
1. 현재 관심사 조회
2. 수정용 FOR UPDATE 조회
3. 제거 메서드
4. 기존 save() 재사용 여부 확인
5. Repository Integration Test
```

Repository 단계에서는 조회 / Lock / add / delete / flush 책임까지만 구현한다.

`ER_CHECKREAD(1020)` 판별, rollback, Retry는 Repository 책임이 아니며 Phase 3 `InterestService`에서 구현한다.

---

## Phase 3 — InterestService

```text
1. GET 관심사 조회
2. PUT Category 검증 재사용
3. 기존 Interest Lock 조회
4. INTERESTS_NOT_INITIALIZED 처리
5. current / requested diff
6. 동일 집합 No-op
7. delete / save
8. commit / rollback
9. ER_CHECKREAD(1020) 판별
10. bounded whole-transaction retry
11. Retry exhaustion 처리
12. Service Unit Test
13. Transaction Integration Test
14. 실제 MariaDB 두 Session Race Condition 검증
```

Phase 3 구현에 들어가기 전에 정확한 최대 Retry 횟수와 Retry exhaustion 정책의 세부 값을 최종 확정한다.

---

## Phase 4 — Router / Backend 회귀 검증

```text
GET /api/users/me/interests
PUT /api/users/me/interests

GET / PUT Router Handler 구현
→ 구현 완료된 InterestService 연결

Router Contract Test
전체 Backend pytest
Swagger / 실제 Endpoint 검증
```

Backend API Contract가 테스트로 확정되기 전에 Frontend 구현으로 넘어가지 않는다.

---

## Phase 5 — Frontend API / Query

```text
1. Interest GET / PUT Type
2. getUserInterests API Function
3. updateUserInterests API Function
4. useUserInterests Query
5. useUpdateInterests Mutation
6. Query Key
7. Mutation 성공 Cache 반영
```

---

## Phase 6 — InterestEditScreen

```text
1. 기존 선택 초기화
2. Category + Interest Query 상태 처리
3. Draft State
4. isDirty 집합 비교
5. 최소 1개 UI 제약
6. 저장 Mutation 연결
7. 400 / 404 / 409 / 401 / Network / 5xx 처리
8. 정상 성공 goBack
9. AuthProvider 정상 성공 미변경 확인
```

---

## Phase 7 — Navigation

```text
AppNavigator에 InterestEdit Route 등록

정상 수정 성공
→ goBack

409 상태 불일치
→ revalidateSession
→ RootNavigator가 필요 시 Onboarding Tree 선택
```

마이페이지 구현은 포함하지 않는다.

---

## Phase 8 — Frontend 검증

```text
Jest
TypeScript typecheck
현재 프로젝트 verify 명령
Expo 실제 기기 Acceptance Test
기존 Login / Session Restore / Logout / 최초 Interest 저장 회귀 검증
```

---

# 42. 예상 변경 파일

정확한 파일은 구현 시작 시 최신 `dev`를 다시 확인한다.

현재 구조 기준 예상 범위:

```text
backend/app/schemas/interest_schema.py
backend/app/repositories/interest_repository.py
backend/app/services/interest_service.py
backend/app/api/routes/interest_router.py
backend/tests/api/test_interest_router.py
backend/tests/services/test_interest_service.py
backend/tests/repositories/test_interest_repository.py
필요 시 backend/tests/schemas/... 및 Integration Test
```

Frontend:

```text
frontend/src/features/interest/types/interest.ts
frontend/src/features/interest/api/getUserInterests.ts
frontend/src/features/interest/api/updateUserInterests.ts
frontend/src/features/interest/hooks/useUserInterests.ts
frontend/src/features/interest/hooks/useUpdateInterests.ts
frontend/src/features/interest/screens/InterestEditScreen.tsx
frontend/src/features/interest/components/... 필요 시 공통 선택 UI
frontend/src/app/navigation/AppNavigator.tsx
frontend/__test__/interest/...
```

AuthProvider는 정상 수정 기능 때문에 변경하지 않는 것을 기본값으로 한다.

409 상태 불일치 재검증은 현재 `revalidateSession()`을 재사용한다.

---

# 43. 이번 범위에서 변경하지 않는 기존 정책

다음을 유지한다.

```text
JWT Access Token 인증
SecureStore Token 저장
Public / Authenticated Client 분리
AuthProvider 인증 상태 관리
Session Restore
공통 401 처리
Stale 401 Race 방어
Client-side Logout
Query Cache Cleanup
Auth State 기반 Root Navigation
최초 관심사 저장 성공 → completeInterestSelection()
```

관심사 수정 때문에 기존 인증 구조를 새로 설계하지 않는다.

---

# 44. 이번 범위 밖 항목

다음은 필요성이 발견되어도 이번 구현에 임의로 포함하지 않는다.

```text
Trend 추천 API 및 Query
Trend Cache 실제 invalidation 구현
북마크
검색
마이페이지 전체 구현
회원정보 조회/수정
비밀번호 변경
회원 탈퇴
Google OAuth
Refresh Token
Token Rotation
Revocation / Blocklist
Server-side Session
Device Session
Interest Keyword
Category Admin 기능
Category 비활성화 장기 사용자 정책
ETag / If-Match
별도 Interest Aggregate version 컬럼
```

범위 밖 개선점은 `제안 사항`으로만 기록한다.

---

# 45. 최종 확정 요약

| 항목 | 최종 결정 |
|---|---|
| GET Endpoint | `GET /api/users/me/interests` |
| PUT Endpoint | `PUT /api/users/me/interests` |
| 인증 | 필수 |
| Frontend Client | `authenticatedApiClient` |
| GET 관심사 없음 | `200 + []` |
| GET Response | `selected_category_ids`, `selected_count` |
| PUT 의미 | 최종 관심사 전체 집합 교체 |
| DB 수정 방식 | `keep / add / remove` diff |
| 최소 선택 수 | 1 |
| 고정 최대 선택 수 | 없음 |
| Request 중복 ID | 422 |
| 존재하지 않는 Category | 404 |
| 비활성 Category | 400 |
| 하위 Category | 400 |
| PUT 기존 관심사 없음 | 409 `INTERESTS_NOT_INITIALIZED` |
| 동일 집합 PUT | 200 No-op |
| Transaction | `InterestService` 책임 |
| Repository commit / rollback | 하지 않음 |
| 수정 동시성 | 사용자 Interest Row `FOR UPDATE` 계열 Lock + MariaDB `ER_CHECKREAD(1020)` 발생 시 bounded whole-transaction retry |
| Retry 책임 | `InterestService` |
| Retry 대상 | 검증된 `ER_CHECKREAD(1020)`만 특별 처리, 기타 알 수 없는 DB 오류로 일반화하지 않음 |
| Retry 범위 | Category 조회/검증부터 Lock·diff·delete/add·flush·commit까지 PUT Use Case 전체 |
| Retry 횟수 | bounded, 정확한 최대 횟수는 Phase 3 구현 전 확정 |
| 정상 PUT 성공 Auth State | 변경하지 않음 |
| 상태 불일치 409 | `revalidateSession()` |
| 수정 Screen | `InterestEditScreen` 별도 |
| 최초 Screen | `InterestSelectScreen` 유지 |
| Query | `useUserInterests` |
| Mutation | `useUpdateInterests` |
| 성공 Cache | Mutation Response로 `setQueryData` |
| 정상 성공 Navigation | `goBack()` |
| Trend Query invalidation | 후속 Trend 구현 시 추가 |

---

# 46. 설계 핵심 문장

이번 관심사 조회 및 수정 설계의 핵심은 다음 한 문장으로 정리한다.

> 관심사 수정은 인증 Session을 다시 만드는 기능이 아니라, 이미 Onboarding을 완료한 사용자의 비어 있지 않은 관심사 집합을 PUT으로 원자적으로 교체하는 기능이며, API는 전체 상태를 전달하되 Backend는 기존 Row를 보존하는 diff 방식으로 수정하고, 동일 사용자 동시 PUT에서는 Interest Row `FOR UPDATE`와 MariaDB `ER_CHECKREAD(1020)`에 대한 bounded whole-transaction retry를 결합하며, Frontend는 Query Server State와 편집 Draft State를 분리한다.

이 원칙을 유지하면 최초 관심사 저장, 인증 Session, 관심사 수정 동시성, 향후 관심사 기반 Trend 추천 사이의 책임을 분리한 채 기능을 확장할 수 있다.

---

# 47. 구현 시작 시 재검증 규칙

이 문서의 기준 커밋은:

```text
1ba1216b56a14cc7fd6e702d4d5671eb2c492841
```

이다.

구현 시작 시 이 SHA를 현재 상태라고 가정하지 않는다.

반드시 `dev` 최신 HEAD를 다시 확인하고, 이후 관심사 / Category / AuthProvider / Navigation / Query 관련 변경사항이 있는지 재검증한다.

설계와 현재 코드가 충돌하면 바로 구현하지 않고:

```text
변경 코드 확인
→ 설계 충돌 지점 확인
→ 기존 설계 유지 가능성 검토
→ 필요 시 대안 비교
→ 설계 변경
→ 구현
```

순서를 따른다.
