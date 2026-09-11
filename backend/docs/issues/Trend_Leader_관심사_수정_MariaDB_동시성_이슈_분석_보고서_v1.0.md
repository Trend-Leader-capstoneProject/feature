# Trend Leader 관심사 수정 MariaDB 동시성 이슈 분석 보고서 v1.0

- **프로젝트:** Trend Leader
- **기능:** 기존 관심사 조회 및 수정
- **대상 API:** `PUT /api/users/me/interests`
- **작업 브랜치:** `feat-interest`
- **보고서 작성 시점:** 2026-08-30
- **관련 설계 문서:** `Trend_Leader_관심사_조회_및_수정_설계_확정안_v1.0.md`
- **상태:** 원인 재현 및 대응 방향 검증 완료 / 실제 제품 코드 구현 전
- **목적:** Phase 2 Repository 구현 전에 발견된 MariaDB 동시성 이슈와 검증 과정을 기록하고, 이후 설계·구현·테스트의 기준으로 사용한다.

---

# 1. 핵심 요약

관심사 수정 API는 사용자의 기존 관심사 집합을 새로운 **전체 집합으로 원자적으로 교체**한다.

예:

```text
현재
{1, 2}

Request A
{1, 3}

Request B
{2, 4}
```

두 요청이 동시에 같은 과거 상태 `{1, 2}`를 기준으로 `keep / add / remove`를 계산하면, 잘못 구현된 경우 최종 상태가 어느 요청의 의도와도 다른 혼합 결과가 될 수 있다.

기존 설계에서는 이를 방지하기 위해 사용자의 현재 `user_interest_categories` Row를:

```sql
SELECT ...
FROM user_interest_categories
WHERE user_id = :user_id
FOR UPDATE
```

형태로 잠그고, 동일 사용자의 PUT Transaction을 직렬화하기로 했다.

그러나 실제 프로젝트 환경인:

```text
SQLAlchemy             2.0.51
MariaDB                12.3.2
Storage Engine         InnoDB
Transaction Isolation  REPEATABLE-READ
innodb_snapshot_isolation = ON
```

에서 두 개의 독립 Transaction을 사용한 Probe를 실행한 결과 다음 현상이 재현되었다.

```text
B가 먼저 일반 SELECT 수행
→ B의 Snapshot 형성

A가 Interest Row FOR UPDATE
→ 수정 후 commit

B가 동일 Row FOR UPDATE
→ A commit까지 정상 대기
→ 이후 최신 Row를 그대로 읽는 대신
→ MariaDB Error 1020 ER_CHECKREAD 발생
```

실제 오류:

```text
(1020,
 "Record has changed since last read in table
 'user_interest_categories'; try restarting transaction")
```

따라서 기존 설계의 다음 가정은 현재 환경에서 그대로 성립하지 않는다.

```text
A가 Lock
→ A 수정 + commit
→ B가 대기 종료
→ B가 자동으로 최신 상태를 읽고 계속 처리
```

하지만 B가 `ER_CHECKREAD(1020)`을 받은 뒤:

```text
Session.rollback()
→ 새 Transaction 시작
→ PUT 작업을 다시 수행
```

하도록 Probe를 확장했을 때, B는 A가 Commit한 최신 상태를 정상적으로 읽었다.

최종 Probe에서는:

```text
초기       {10, 11}
A 목표     {10, 12}
B 목표     {11, 12}

A commit
→ B 1020
→ B rollback
→ B 새 Transaction
→ B가 최신 {10,12} 재조회
→ B 목표 {11,12} 기준 diff 적용
→ B commit

최종 DB
{11, 12}
```

가 확인되었다.

## 결론

기존 `FOR UPDATE` 전략을 폐기하지 않는다.

대신 동시성 설계를 다음처럼 **보강**하는 방향이 현재 Trend Leader에서 가장 작은 변경으로 검증되었다.

```text
Interest Row FOR UPDATE
+
MariaDB ER_CHECKREAD(1020) 발생 시 rollback
+
새 Transaction에서 PUT 작업 전체를 bounded retry
```

단, **최대 Retry 횟수는 아직 확정하지 않는다.**

---

# 2. 발견 배경

관심사 조회·수정 설계 확정안 v1.0에서는 다음 정책이 이미 확정되어 있었다.

```text
PUT 의미
→ 최종 관심사 전체 집합 교체

DB 변경
→ keep / add / remove diff

Transaction
→ InterestService 책임

Repository
→ 조회 / add / delete / flush
→ commit / rollback 하지 않음

동일 사용자 동시 PUT
→ 사용자 Interest Row FOR UPDATE 계열 Lock
```

설계의 목표는 다음과 같았다.

```text
A가 현재 상태 Lock
→ A 수정 + commit
→ B가 새 상태 조회
→ B가 그 상태 기준으로 수정
```

구현 시작 프롬프트에서도 MariaDB / InnoDB의 실제 Row Lock 의미를 Mock이나 SQLite만으로 완료 판정하지 않고, 현재 SQLAlchemy와 실제 MariaDB 환경에서 검증하도록 요구하고 있었다.

이 검증을 Phase 2 전에 수행하면서 이번 이슈가 발견되었다.

---

# 3. 왜 동시 PUT이 위험한가

관심사 PUT은 증분 명령이 아니라 최종 전체 상태를 전달한다.

예:

```text
현재
{1, 2}

A 요청
{1, 3}

B 요청
{2, 4}
```

각 요청의 의도는 명확하다.

```text
A 성공 후 상태
{1, 3}

B 성공 후 상태
{2, 4}
```

그런데 두 요청이 동시에 `{1, 2}`를 읽으면:

```text
A
keep   = {1}
remove = {2}
add    = {3}

B
keep   = {2}
remove = {1}
add    = {4}
```

를 각각 계산할 수 있다.

Lock이나 동시성 제어 없이 두 변경이 교차 실행되면 예를 들어:

```text
{3, 4}
```

같이 어느 PUT의 최종 요청과도 일치하지 않는 상태가 생길 수 있다.

이 문제는 흔히 다음 범주와 관련된다.

- Lost Update
- Write Race
- Stale Read 기반 Diff
- 혼합 최종 상태
- Check-then-act Race

Trend Leader에서는 PUT의 의미가 **전체 집합 교체**이므로, 성공한 요청 하나의 최종 집합이 DB 상태로 정확히 남는 것이 중요하다.

---

# 4. 검증한 실제 환경

## 4.1 SQLAlchemy

실행:

```powershell
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

결과:

```text
2.0.51
```

프로젝트 `requirements.txt`의 범위:

```text
sqlalchemy>=2.0,<2.1
```

와 일치한다.

SQLAlchemy 2.0의 `Select.with_for_update()`는 공식 지원 API이며, 인자 없이 호출하면 `FOR UPDATE`를 생성한다.

개념적 Repository 구현은 다음 형태가 가능하다.

```python
statement = (
    select(UserInterestCategory)
    .where(
        UserInterestCategory.user_id == user_id,
    )
    .with_for_update()
)
```

---

## 4.2 MariaDB

실제 테스트 DB 결과:

```text
VERSION
12.3.2-MariaDB-ubu2404

transaction_isolation
REPEATABLE-READ

innodb_snapshot_isolation
ON

user_interest_categories ENGINE
InnoDB
```

즉 이번 Probe는 실제 Trend Leader 테스트 환경의 MariaDB 12.3.2 + InnoDB + REPEATABLE READ 조건에서 수행했다.

---

# 5. MariaDB `innodb_snapshot_isolation`이 중요한 이유

MariaDB 문서에 따르면 `innodb_snapshot_isolation`은 MariaDB 10.6.18에 도입되었고, 11.6.2부터 기본 활성화되었다.

이 옵션이 켜진 REPEATABLE READ 환경에서는 Transaction이 가진 현재 read view에 존재하지 않는 버전의 Record에 Lock을 획득하려 할 때:

```text
ER_CHECKREAD
```

가 발생할 수 있다.

MariaDB Error Code Reference에서:

```text
1020
HY000
ER_CHECKREAD
Record has changed since last read in table '%s'
```

로 정의된다.

이번 Probe에서 발생한 오류와 정확히 일치한다.

중요한 점은:

```text
FOR UPDATE가 Lock을 못 거는 것
```

과:

```text
Lock 대기 후 Snapshot 일관성 충돌로
ER_CHECKREAD이 발생하는 것
```

은 서로 다른 현상이라는 것이다.

이번 실험에서는 실제로 B가 A의 Lock 때문에 정상 대기했다.

즉:

```text
FOR UPDATE Lock 동작
✅

A commit 후 B가 자동으로 최신 Row를 이어서 처리
❌
```

였다.

---

# 6. 왜 B의 Snapshot이 먼저 형성될 수 있는가

Trend Leader의 실제 인증 흐름에서는 보호 API가 Service에 도달하기 전에 `CurrentUser` Dependency가 DB에서 User를 조회한다.

개념:

```text
Authorization Bearer Token
→ JWT 검증
→ user_id 추출
→ UserRepository.find_by_id()
→ CurrentUser
→ Router
→ InterestService
```

SQLAlchemy `Session`은 기본적으로 DB 작업이 시작되면 autobegin으로 Transaction을 시작한다.

따라서 PUT Service가 `FOR UPDATE`를 실행하기 전에 이미 동일 요청의 Session에서 일반 SELECT가 수행될 수 있다.

Probe에서는 이를 다음처럼 재현했다.

```text
Transaction B

User 일반 SELECT
→ B의 Transaction / Snapshot이 이미 시작된 상태

그 뒤 A가 Interest를 변경하고 commit

이후 B가 Interest FOR UPDATE
```

이 순서가 실제 애플리케이션 흐름에서 충분히 가능하기 때문에 단순 이론적 케이스로 볼 수 없다.

---

# 7. Probe 1 — 기존 `FOR UPDATE` 가정 검증

## 7.1 시나리오

초기 관심사:

```text
{1, 2}
```

A:

```text
{1, 3}
```

B는 먼저 User 일반 SELECT로 Snapshot을 형성한 뒤 Interest Row `FOR UPDATE`를 수행한다.

실제 흐름:

```text
[B] User 일반 SELECT 완료
[A] Interest FOR UPDATE Lock 획득
[A] 변경 flush
[B] Interest SELECT ... FOR UPDATE 시작
[CHECK] B는 A Lock 때문에 대기
[A] commit
```

여기까지는 기존 설계 의도대로였다.

---

## 7.2 결과

B:

```text
status = DB_ERROR
error_type = OperationalError
error_args =
(
  1020,
  "Record has changed since last read in table
   'user_interest_categories'; try restarting transaction"
)
```

최종 DB:

```text
A의 변경 결과
{1, 3}
```

### 판정

A의 원자성은 유지되었다.

하지만 기존 설계에서 기대한:

```text
A commit
→ B가 최신 상태를 읽고 계속 실행
```

은 실패했다.

---

# 8. Probe 2 — Transaction Restart 가능성 검증

Probe 1의 MariaDB 오류 메시지에는:

```text
try restarting transaction
```

이라는 의미가 포함되어 있다.

따라서 다음을 검증했다.

```text
B 첫 번째 FOR UPDATE
→ 1020

B Session.rollback()
→ 기존 Transaction 종료

동일 Session에서 다시 DB 작업
→ SQLAlchemy autobegin
→ 새 Transaction

B Interest FOR UPDATE 재실행
```

## 결과

```text
[B] 첫 번째 FOR UPDATE 실패
1020 ER_CHECKREAD

[B] 새 Transaction에서 재시도

status = RETRY_SUCCESS
interest_ids = [4, 6]

A가 commit한 최신 상태
[4, 6]
```

Retry 수행 시간 예:

```text
first_elapsed = 0.503s
retry_elapsed = 0.009s
```

### 판정

`rollback()` 후 새로운 Transaction에서 Retry하면 기존 stale Snapshot이 사라지고, 최신 Commit 상태를 정상 조회할 수 있음이 현재 환경에서 확인되었다.

---

# 9. Probe 3 — Retry 후 실제 전체 PUT까지 검증

최신 상태를 읽는 것만으로는 충분하지 않다.

실제 PUT은 최신 상태를 기준으로:

```text
keep
add
remove
```

를 다시 계산하고 수정까지 완료해야 한다.

따라서 마지막 Probe에서는 B도 전체 수정 Transaction을 완료하도록 했다.

---

## 9.1 시나리오

```text
초기
{10, 11}

Request A
{10, 12}

Request B
{11, 12}
```

---

## 9.2 실행 흐름

```text
B User 일반 SELECT
→ B Snapshot 형성

A FOR UPDATE
→ {10,11} Lock

A
→ {10,12}로 변경
→ flush

B FOR UPDATE
→ A 때문에 대기

A commit

B
→ 1020 ER_CHECKREAD

B rollback

B 새 Transaction

B 최신 상태 재조회
→ {10,12}

B 요청 목표
→ {11,12}
```

따라서 Retry Transaction의 diff는:

```text
current   = {10, 12}
requested = {11, 12}

keep   = {12}
remove = {10}
add    = {11}
```

이다.

---

## 9.3 최종 결과

```text
status = RETRY_UPDATE_SUCCESS

read_after_retry
[10, 12]

target_ids
[11, 12]

Final DB State
[11, 12]
```

### 판정

최종 DB 상태가 B의 전체 PUT 요청과 정확히 일치했다.

즉 다음이 확인되었다.

```text
Lock 대기                         PASS
ER_CHECKREAD 재현                 PASS
rollback                         PASS
새 Transaction 시작              PASS
최신 상태 재조회                  PASS
최신 상태 기준 diff               PASS
두 번째 전체 PUT 적용             PASS
commit                           PASS
혼합 결과 없음                    PASS
최종 상태 = 마지막 성공 요청 집합   PASS
```

---

# 10. 기존 설계에서 수정해야 하는 정확한 부분

기존 설계의 `FOR UPDATE` 채택 자체가 잘못된 것은 아니다.

문제가 된 것은 다음 설명이었다.

```text
A가 현재 상태 Lock
→ A 수정 + commit
→ B가 새 상태 조회
→ B가 그 상태 기준으로 수정
```

현재 MariaDB 12.3.2 환경에서는 B가 이미 오래된 Snapshot을 가진 경우:

```text
A commit
→ B가 바로 최신 상태 조회
```

가 아니라:

```text
A commit
→ B ER_CHECKREAD(1020)
→ Transaction restart 필요
```

가 될 수 있다.

따라서 기존 동시성 설계는 폐기보다 **보강**이 적절하다.

---

# 11. 권고 설계 — `FOR UPDATE + bounded whole-transaction retry`

## 11.1 기본 성공 경로

```text
PUT Attempt

요청 Category 조회
→ Category 규칙 검증
→ 현재 Interest Row SELECT ... FOR UPDATE
→ 기존 관심사 존재 여부 확인
→ current / requested diff
→ No-op 여부 판단
→ remove
→ add / flush
→ commit
→ Response
```

---

## 11.2 ER_CHECKREAD 경로

```text
PUT Attempt

...
→ SELECT ... FOR UPDATE
→ MariaDB ER_CHECKREAD(1020)

InterestService
→ rollback

Retry 가능 횟수가 남아 있다면
→ PUT Attempt 전체를 새 Transaction에서 다시 실행
```

### 핵심

다음처럼 `FOR UPDATE` 한 문장만 다시 실행하면 안 된다.

```text
Category 조회
→ Validation
→ FOR UPDATE
→ 1020
→ rollback
→ FOR UPDATE만 Retry
```

권고는:

```text
Attempt 1
├─ Category 조회
├─ Validation
├─ Interest Lock
├─ diff
└─ 1020

rollback

Attempt 2
├─ Category 다시 조회
├─ Validation 다시 수행
├─ Interest Lock
├─ diff 재계산
├─ remove / add
└─ commit
```

이다.

이유는 Retry가 **새 Transaction / 새 Snapshot**에서 하나의 Use Case 전체를 다시 평가해야 하기 때문이다.

---

# 12. Retry 책임 위치

## Repository가 담당하지 않는 것

```text
commit
rollback
transaction retry
ER_CHECKREAD에 대한 Use Case 판단
```

Repository의 책임은 기존 원칙대로 유지한다.

```text
SELECT
SELECT ... FOR UPDATE
add
delete
flush
```

---

## InterestService가 담당할 것

```text
Transaction Attempt 실행
commit
rollback
ER_CHECKREAD(1020) 판별
bounded retry orchestration
retry exhaustion 처리
```

이 구조가 기존 Trend Leader의 책임 분리와 가장 일관된다.

---

# 13. 어떤 오류를 Retry할 것인가

모든 `OperationalError` 또는 `SQLAlchemyError`를 Retry하면 안 된다.

예:

```text
DB 서버 다운
Connection refused
잘못된 SQL
Lock wait timeout
권한 문제
기타 예상하지 못한 DB 오류
```

까지 모두 Retry하면 실제 장애를 늦게 드러내거나 숨길 수 있다.

현재 실제로 검증된 특별 케이스는:

```text
MariaDB Error Code 1020
ER_CHECKREAD
```

이다.

따라서 제품 구현에서는 오류 객체의 DBAPI 원본 오류 코드를 확인하여:

```text
1020인 경우에만
→ 동시성 Snapshot Conflict Retry 후보

그 외
→ 기존 rollback 후 상위 전달
```

정책을 유지하는 것이 적절하다.

기존 설계의:

```text
알 수 없는 DB 오류를 임의로 Domain 409로 변환하지 않는다.
```

정책도 그대로 유지한다.

`ER_CHECKREAD` 역시 사용자 Domain Conflict를 의미하는 `409`로 변환하는 것보다 내부 Transaction Retry 대상으로 보는 것이 현재 검증 결과와 더 잘 맞는다.

---

# 14. Retry 횟수는 왜 아직 확정하지 않는가

두 요청 Probe에서는 한 번의 Retry로 충분했다.

그러나 이것만으로:

```text
항상 Retry 1회면 충분하다
```

고 증명할 수는 없다.

예:

```text
A / B / C가 거의 동시에 PUT

B가 A 때문에 1020
→ B retry

그 사이 C가 다른 변경 commit
→ B가 다시 충돌할 가능성
```

이 존재할 수 있다.

반대로 무한 Retry는:

```text
응답 지연
DB 부하
장애 은폐
무한 루프 위험
```

이 있으므로 사용하면 안 된다.

따라서 현재 확정 가능한 것은:

```text
Retry는 bounded 해야 한다.
```

까지이다.

정확한 최대 Retry 횟수는 Phase 3 InterestService 구현 전에 별도 결정한다.

현재 후보 예시는:

```text
최초 1회 + Retry 최대 2회
= 총 3 attempts
```

정도이나, 이 숫자는 **검증 완료 사실이 아니라 설계 후보**이다.

---

# 15. 검토한 대안과 트레이드오프

## 15.1 대안 A — `FOR UPDATE + ER_CHECKREAD Retry`

### 장점

- 기존 확정 설계의 대부분 유지
- DB Isolation Level 변경 없음
- MariaDB 전역 설정 변경 없음
- 실제 Probe에서 최신 상태 재조회와 최종 PUT 성공 확인
- Transaction 책임을 기존 InterestService에 유지 가능

### 단점

- MariaDB Error Code에 대한 DB별 처리 필요
- Retry 횟수 정책 필요
- 동시 요청이 많으면 Retry가 반복될 수 있음
- 반드시 실제 MariaDB Integration Test가 필요

### 현재 판단

**우선 채택 후보.**

---

## 15.2 대안 B — 프로젝트 전체 `READ COMMITTED`

### 장점

- 문장 단위로 더 최신 Commit 상태를 볼 가능성이 높음
- Snapshot 충돌 문제를 줄일 수 있음

### 단점

- 관심사 기능 하나 때문에 전체 DB Transaction 의미 변경
- 다른 Service / Transaction에 대한 영향 검토 필요
- 현재 프로젝트가 기대하던 REPEATABLE READ 의미 변화

### 현재 판단

현재 범위에서 변경 폭이 너무 큼.

---

## 15.3 대안 C — `innodb_snapshot_isolation=OFF`

### 장점

- 기존 InnoDB locking read에 가까운 동작으로 돌아갈 수 있음

### 단점

- DB 설정에 의존
- 다른 Transaction의 격리 의미에도 영향
- 개발/테스트/운영 환경 설정 일치 요구
- 기능 하나를 위해 DB 전역 정책을 낮추는 선택이 될 수 있음

### 현재 판단

우선순위 낮음.

---

## 15.4 대안 D — User Row를 별도 직렬화 Lock으로 사용

개념:

```sql
SELECT ...
FROM users
WHERE user_id = :user_id
FOR UPDATE
```

### 장점

- 사용자마다 항상 존재하는 고정 Row를 직렬화 기준으로 사용 가능
- 관심사 Row의 add/remove에 의해 Lock 대상 집합이 바뀌는 문제 감소

### 단점

- 관심사 기능이 `users` Row Lock에 결합
- 같은 User Row를 수정하는 다른 기능과 불필요한 경합 가능
- 이미 형성된 Snapshot과 MariaDB `innodb_snapshot_isolation` 문제를 이것만으로 해결한다고 단정할 수 없음
- 기존 설계 변경 폭 증가

### 현재 판단

현재 Probe 결과상 먼저 도입할 필요 없음.

---

# 16. Phase 2 Repository에 미치는 영향

이번 이슈 때문에 Phase 2 Repository의 기본 책임을 바꿀 필요는 없다.

필요한 기능은 그대로다.

```text
find current interests
find current interests FOR UPDATE
delete removed interests
save added interests
flush
```

Repository는 여전히:

```text
commit X
rollback X
retry X
```

이다.

즉 이번 이슈의 핵심 대응은 Phase 2보다 **Phase 3 InterestService Transaction orchestration**에 위치한다.

Phase 2에서는 `FOR UPDATE` 조회가 실제 SQLAlchemy 2.0.51 API로 올바르게 생성되고, 실제 MariaDB Integration Test에서 해당 사용자의 Row를 잠그는지만 검증한다.

---

# 17. Phase 3 InterestService에 추가해야 할 설계 포인트

기존 Phase 3 범위에 다음을 추가해야 한다.

```text
1. PUT Transaction Attempt 단위 정의
2. MariaDB ER_CHECKREAD(1020) 감지
3. 해당 오류 시 rollback
4. bounded retry
5. Retry 시 Category 조회부터 전체 Use Case 재실행
6. 각 Retry에서 current 상태 새로 조회
7. diff 새로 계산
8. Retry exhaustion 처리
9. 그 외 DB 오류는 기존처럼 rollback 후 상위 전달
```

---

# 18. 정식 테스트로 승격해야 할 항목

현재 Probe는 탐색용 임시 코드다.

제품 구현 후에는 같은 핵심을 정식 Backend Integration Test로 옮긴다.

## 필수 조건

```text
SQLite X
Mock-only X
한 Connection 공유 X
```

반드시:

```text
실제 MariaDB
독립 Connection A
독립 Connection B
독립 Transaction A
독립 Transaction B
```

를 사용한다.

현재 일반 `db_session` fixture는 테스트 격리를 위해 한 Connection과 외부 Transaction / Savepoint 구조를 사용하므로, 실제 Lock 경쟁 테스트에서는 `test_engine`으로 별도 Session 두 개를 만드는 편이 적합하다.

---

## 정식 Race Test 권장 시나리오

```text
초기
{1, 2}

A 목표
{1, 3}

B 목표
{2, 3}
```

검증:

```text
A Lock 획득
B 대기
A commit
B 1020 가능
B rollback + Retry
B 최신 A 상태 재조회
B diff 재계산
B commit

Final DB
== B 요청 전체 집합
```

또한 다음을 확인한다.

```text
혼합 집합 없음
중복 Row 없음
유지 대상 Row의 created_at 보존
다른 사용자 Interest 영향 없음
Transaction 실패 시 이전 상태 복구
Retry 횟수 제한 동작
비-1020 DB 오류는 Retry하지 않음
```

---

# 19. Probe에서 발견한 부수 이슈

## 19.1 테스트 DB Schema가 비어 있던 문제

Probe 초기 실행에서:

```text
Table 'trend_leader_test.categories' doesn't exist
```

오류가 발생했다.

원인은 MariaDB 연결 실패가 아니라 테스트 DB Schema가 준비되지 않은 상태였다.

기존 pytest Integration fixture는 실행 전에:

```text
alembic upgrade head
```

를 자동 수행하지만, 임시 Probe는 직접 DB Engine을 만들기 때문에 해당 fixture를 사용하지 않았다.

따라서 Probe 전에 테스트 DB가 migration head 상태인지 확인할 필요가 있었다.

### 학습 포인트

```text
DB 연결 성공
!=
Schema 준비 완료
```

이다.

---

## 19.2 Probe 출력 상태 분기 버그

마지막 Probe 중:

```text
status = retry_update_success
```

결과가 Queue에 정상 저장되었지만, 출력 코드가 새로운 상태를 처리하지 않아:

```text
PROBE_ERROR
KeyError: 'error_type'
```

가 발생했다.

이는 DB/동시성 오류가 아니라 Probe 출력 로직 문제였다.

이 경험으로 결과 출력 코드에서는 예상하지 못한 상태를:

```text
UNKNOWN_RESULT
raw_result = ...
```

형태로 보여주는 것이 디버깅에 더 안전하다는 점도 확인했다.

---

# 20. 이번 이슈에서 배울 수 있는 핵심 개념

## 20.1 Transaction

Transaction은 여러 DB 작업을 하나의 논리적 작업 단위로 묶는다.

관심사 PUT에서는:

```text
현재 상태 읽기
→ diff 계산
→ delete
→ insert
→ commit
```

전체가 하나의 Transaction이어야 한다.

중간에 실패하면:

```text
rollback
```

되어 PUT 이전 상태로 돌아가야 한다.

---

## 20.2 Snapshot / Read View

REPEATABLE READ Transaction은 일정 시점의 DB 상태를 자신의 read view로 유지한다.

쉽게 말하면:

```text
Transaction B가 사진 한 장을 찍고
그 사진을 기준으로 계속 읽는 것
```

에 가깝다.

다른 Transaction A가 그 뒤 데이터를 바꾸어도 B의 기존 Snapshot과 최신 DB 상태가 다를 수 있다.

---

## 20.3 `SELECT ... FOR UPDATE`

일반 SELECT는 데이터를 조회하기 위한 읽기다.

`FOR UPDATE`는:

```text
이 Row를 지금 수정 Transaction에서 사용할 것이므로
다른 쓰기 Transaction과 충돌하지 않도록 잠근다.
```

는 의미의 locking read다.

하지만:

```text
FOR UPDATE 사용
==
모든 격리 수준 / DB 버전에서
자동으로 최신 상태를 읽고 계속 진행
```

은 아니다.

이번 MariaDB 12.3.2 사례가 이를 보여준다.

---

## 20.4 ER_CHECKREAD

현재 환경에서 B의 기존 Snapshot과 A의 새 Commit 상태가 충돌한 뒤, B가 변경된 Record에 Lock을 획득하려 하자:

```text
1020 ER_CHECKREAD
```

가 발생했다.

이 오류는 단순 SQL 문법 오류가 아니라 Transaction의 Snapshot 일관성 관련 충돌이다.

---

## 20.5 Rollback 후 Retry

SQLAlchemy `Session.rollback()` 후에는 기존 Transaction이 끝난다.

기본 `Session`은 다음 DB 작업이 필요할 때 autobegin으로 새 Transaction을 시작할 수 있다.

따라서:

```text
오래된 Snapshot Transaction
→ rollback
→ 새 Transaction
→ 최신 상태 기준으로 전체 Use Case 재평가
```

가 가능하다.

중요한 것은 단순 SQL 한 줄의 재실행이 아니라 **Transaction 단위 작업 전체를 다시 평가**하는 것이다.

---

# 21. 설계 확정안 수정 초안

기존 설계 문서의 `PUT 동시성 / Race Condition` 부분은 다음처럼 보강하는 것을 권장한다.

## 수정안

```text
같은 사용자의 관심사 수정 Transaction은
사용자의 현재 Interest Row에 SELECT ... FOR UPDATE 계열 Lock을 사용하여
동시에 같은 이전 상태를 기준으로 diff를 적용하지 않도록 한다.

현재 Trend Leader 테스트 환경은:

- SQLAlchemy 2.0.51
- MariaDB 12.3.2
- InnoDB
- REPEATABLE-READ
- innodb_snapshot_isolation=ON

이다.

실제 두 Transaction Probe에서,
두 번째 Transaction이 먼저 read view를 형성한 뒤
첫 번째 Transaction이 관심사 Row를 변경하고 commit하면
두 번째 Transaction의 FOR UPDATE가 MariaDB Error 1020
ER_CHECKREAD를 발생시킬 수 있음이 확인되었다.

따라서 FOR UPDATE만으로
'A commit 후 B가 자동으로 최신 상태를 읽는다'고 가정하지 않는다.

PUT 실행 중 ER_CHECKREAD(1020)이 발생하면:

1. InterestService가 현재 Transaction을 rollback한다.
2. 제한된 Retry 횟수가 남아 있으면 새 Transaction에서 PUT Use Case 전체를 다시 수행한다.
3. Retry에서는 요청 Category 조회/검증, 현재 Interest Lock 조회,
   existing-state 검증, current/requested diff 계산, delete/add/flush/commit을
   모두 새 Transaction 기준으로 다시 수행한다.
4. FOR UPDATE 문장만 단독 Retry하지 않는다.
5. 1020 이외의 알 수 없는 DB 오류는 Retry 대상으로 일반화하지 않고
   기존 정책대로 rollback 후 상위에 전달한다.
6. Retry 횟수는 무한으로 두지 않고 bounded 한다.
7. 최대 Retry 횟수의 정확한 값은 InterestService 구현 전에 별도로 확정한다.

정식 완료 판정은 실제 MariaDB의 서로 독립된 Connection/Transaction을 사용한
Concurrency Integration Test로 수행한다.
```

---

# 22. 구현 시작 프롬프트 수정 초안

기존 `[Backend 동시성 / Race Condition]` 부분에는 아래 항목을 추가하는 것을 권장한다.

```text
현재 MariaDB 12.3.2 / REPEATABLE-READ /
innodb_snapshot_isolation=ON 환경에서 수행한 Probe 결과,
동일 사용자 PUT의 두 번째 Transaction이 오래된 read view를 가진 상태로
FOR UPDATE를 시도하면 Error 1020 ER_CHECKREAD이 발생할 수 있음이 확인되었습니다.

따라서 InterestService 구현에서는:

- Interest Row FOR UPDATE 전략 유지
- ER_CHECKREAD(1020) 발생 시 rollback
- bounded whole-transaction retry
- Retry 시 Category 조회 및 Validation부터 전체 PUT Use Case 재실행
- 1020 이외의 DB 오류를 일반 Retry 대상으로 확대하지 않음
- Retry exhaustion 시 무한 반복하지 않음
- 실제 MariaDB 두 Session Race Test 필수

정책을 반영해주세요.

정확한 최대 Retry 횟수는 Phase 3 구현 전에 대안을 비교한 뒤 확정해주세요.
```

---

# 23. 현재 상태 구분

## 확인 완료

- SQLAlchemy 실제 버전 `2.0.51`
- MariaDB 실제 버전 `12.3.2`
- `REPEATABLE-READ`
- `innodb_snapshot_isolation=ON`
- `user_interest_categories` 실제 Engine `InnoDB`
- `FOR UPDATE`에서 실제 Lock 대기 발생
- 오래된 Snapshot의 B에서 Error 1020 `ER_CHECKREAD` 재현
- `rollback()` 후 새 Transaction Retry 시 최신 상태 조회 성공
- 최신 상태 기준 diff 재계산 가능
- Retry 후 두 번째 전체 PUT Commit 성공
- 최종 DB 상태가 두 번째 요청의 최종 집합과 정확히 일치
- 혼합 최종 상태가 만들어지지 않음

---

## 설계 판단

현재는 기존 `FOR UPDATE` 구조를 버리기보다:

```text
FOR UPDATE
+
ER_CHECKREAD 전용 rollback
+
bounded whole-transaction retry
```

로 보강하는 것이 변경 범위와 실제 검증 결과를 고려할 때 가장 적합하다.

---

## 추가 검증 필요

- 정확한 최대 Retry 횟수
- Retry exhaustion 시 최종 오류 처리 방식
- 실제 InterestService 구현 후 정식 MariaDB Race Test
- 3개 이상의 동시 PUT이 있을 때 bounded retry 동작
- Retry 중 비-1020 DB 오류 발생 시 기존 실패 경로 유지 여부

---

# 24. Phase 2 진행 전 결론

이번 이슈는 Phase 2 Repository 구현을 막기 위해 발견한 것이 아니라, **Repository와 Service를 잘못된 Transaction 가정 위에 구현하지 않기 위해 먼저 검증한 이슈**다.

따라서 다음 단계는:

```text
동시성 이슈 문서화
→ 설계 확정안의 동시성 섹션 보강
→ Phase 2 InterestRepository 구현
→ Repository Integration Test
→ Phase 3 InterestService 구현 시 bounded retry 최종 정책 확정
→ 실제 MariaDB Race Condition 정식 테스트
```

순서로 진행한다.

Phase 2의 Repository 책임은 유지하고, Retry는 Phase 3 InterestService 책임으로 둔다.

---

# 25. 한 문장 정리

> Trend Leader의 관심사 PUT은 `FOR UPDATE`만으로 모든 동시 요청이 자동 직렬화된다고 가정하지 않고, MariaDB 12.3.2의 Snapshot Isolation에서 재현된 `ER_CHECKREAD(1020)`을 제한적으로 감지하여 Transaction 전체를 새 Snapshot에서 재시도함으로써, 최종 관심사 집합이 마지막으로 성공한 전체 PUT 요청과 정확히 일치하도록 보장하는 방향으로 동시성 설계를 보강한다.

---

# 26. 참고 자료

## 프로젝트 내부 문서

- `Trend_Leader_관심사_조회_및_수정_설계_확정안_v1.0.md`
  - Section 18 Repository 책임
  - Section 19 InterestService 책임
  - Section 20 Transaction / rollback 정책
  - Section 21 PUT 동시성 / Race Condition
  - Section 41 구현 순서
- `Trend_Leader_관심사_조회_및_수정_구현_채팅_시작_프롬프트.md`
  - Backend Repository
  - Backend Service
  - Backend 동시성 / Race Condition
  - Backend Test / Concurrency

## MariaDB 공식 자료

- Error 1020 / ER_CHECKREAD  
  https://mariadb.com/docs/server/reference/error-codes/mariadb-error-codes-1000-to-1099/e1020

- MariaDB Error Code Reference  
  https://mariadb.com/docs/server/reference/error-codes/mariadb-error-code-reference

- Isolation level violation testing and debugging in MariaDB  
  https://mariadb.com/resources/blog/isolation-level-violation-testing-and-debugging-in-mariadb/

## SQLAlchemy 2.0 공식 자료

- `Select.with_for_update()`  
  https://docs.sqlalchemy.org/en/20/core/selectable.html

- Session Basics — Autobegin / Rollback  
  https://docs.sqlalchemy.org/en/20/orm/session_basics.html

---

# Appendix A. 최종 Probe 결과 요약

```text
=== Probe Data ===
user_id = 4
initial interests = [10, 11]
A will change to = [10, 12]
B will change to = [11, 12]

[B] User 일반 SELECT 완료
[A] Interest FOR UPDATE Lock 획득: [10, 11]
[A] 변경 flush 완료
[B] Interest SELECT ... FOR UPDATE 시작
[CHECK] B는 A Lock 때문에 대기 중
[A] commit

[B] 첫 번째 FOR UPDATE 실패:
(1020,
 "Record has changed since last read in table
 'user_interest_categories'; try restarting transaction")

[B] ER_CHECKREAD 확인
→ 새 Transaction에서 재시도

[B] Retry 후 최신 관심사:
[10, 12]

status = RETRY_UPDATE_SUCCESS
read_after_retry = [10, 12]
target_ids = [11, 12]

=== Final DB State ===
interest_ids = [11, 12]
```

## 해석

```text
A 요청
{10,12}
→ 정상 commit

B 첫 시도
→ stale Snapshot 때문에 1020

B rollback 후 Retry
→ A의 최신 상태 {10,12} 확인
→ B의 목표 {11,12} 기준 diff 재계산
→ commit

최종
{11,12}
```

즉 최종 상태가 두 요청의 혼합이 아니라 **마지막으로 성공한 B의 전체 PUT 요청과 정확히 일치**했다.

---

# Appendix B. 용어 빠른 복습

| 용어 | 의미 |
|---|---|
| Transaction | 여러 DB 작업을 하나의 원자적 작업 단위로 묶는 범위 |
| Commit | Transaction의 변경을 최종 확정 |
| Rollback | Transaction의 변경을 취소 |
| Snapshot / Read View | Transaction이 읽는 일관된 DB 상태의 기준 시점 |
| REPEATABLE READ | 동일 Transaction에서 일관된 읽기 상태를 유지하는 격리 수준 |
| `SELECT ... FOR UPDATE` | 조회한 Row를 수정 목적의 Locking Read로 잠그는 방식 |
| Race Condition | 실행 순서에 따라 결과가 달라질 수 있는 동시성 문제 |
| Lost Update | 한 요청의 변경이 다른 요청에 의해 덮이거나 유실되는 문제 |
| ER_CHECKREAD | MariaDB Error 1020. Record가 이전 read 이후 변경되었음을 나타내는 오류 |
| Retry | 실패한 Transaction을 새 Transaction에서 다시 수행 |
| Bounded Retry | 무한 반복하지 않고 정해진 최대 횟수까지만 Retry |
| Diff Update | 전체 삭제/재삽입 대신 keep/add/remove 차이만 반영하는 수정 방식 |
