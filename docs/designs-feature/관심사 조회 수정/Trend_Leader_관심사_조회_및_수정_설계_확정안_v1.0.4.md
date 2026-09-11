# Trend Leader 관심사 조회 및 수정 설계 확정안 v1.0.4

- 문서명: 관심사 조회 및 수정 설계 확정안
- 프로젝트: Trend Leader
- 기준 Repository: `Trend-Leader-capstoneProject/feature`
- 기준 브랜치: `dev`
- 기준일: 2026-09-09
- 상태: 설계 확정 / 문서 정합성 보강
- 기반 문서: `Trend_Leader_관심사_조회_및_수정_설계_확정안_v1.0.3.md`
- 연계 문서: `../관심사 분류/Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.md`

---

## 1. 문서 목적

본 문서는 `v1.0.3`의 관심사 조회 및 수정 설계를 새로 재설계하지 않는다.

`v1.0.3` 이후 실제 `dev` 구현과 Category Taxonomy 설계가 진행되면서 발생한 문서 시간성 및 참조 기준의 혼동을 제거하기 위한 **정합성 보강 문서**다.

본 문서에서 명시적으로 수정하는 항목을 제외한 관심사 GET / PUT의 API 계약, Transaction 책임, 오류 정책, Frontend 상태 분리 원칙은 `v1.0.3`을 그대로 유지한다.

충돌 시 다음 순서를 적용한다.

```text
현재 채팅의 명시적 확정 사항
→ 본 v1.0.4 보강 사항
→ v1.0.3 기존 확정안
→ Category 관련 세부 사항은 최신 Category Taxonomy 확정안
→ 현재 dev 코드와 테스트는 실제 구현 상태 확인 자료
```

---

## 2. 설계 당시 상태와 현재 구현 상태 구분

`v1.0.3` Section 2의 `현재 dev 상태` 표현은 **2026-08-30 설계 기준 시점의 구현 스냅샷**으로 해석한다.

따라서 다음 문구는 현재 `dev`의 최신 구현 상태를 의미하지 않는다.

```text
현재 구현된 관심사 Endpoint는 POST 하나
GET /api/users/me/interests 미구현
PUT /api/users/me/interests 미구현
```

2026-09-09 `dev` 기준 Backend에는 다음 Endpoint와 연결 흐름이 존재한다.

```text
POST /api/users/me/interests
GET  /api/users/me/interests
PUT  /api/users/me/interests
```

Backend의 GET / PUT은 Router → Service → Repository 구조로 구현되어 있다.

반면 현재 Frontend 관심사 Feature에는 최초 선택 흐름인 다음 구조가 존재한다.

```text
getCategories.ts
saveUserInterests.ts
useCategories.ts
useSaveInterests.ts
InterestSelectScreen.tsx
```

아직 다음 조회/수정 전용 Frontend 흐름은 구현되지 않은 상태다.

```text
getUserInterests
updateUserInterests
useUserInterests
useUpdateInterests
InterestEditScreen
```

따라서 `v1.0.3`의 Phase 계획은 삭제하지 않고 **설계 당시 구현 계획 기록**으로 유지한다.

---

## 3. Transaction Retry 횟수 최종 확정

동일 사용자의 관심사 PUT 동시성에서 검증된 MariaDB `ER_CHECKREAD(1020)`에 대한 Retry는 bounded whole-transaction retry를 유지한다.

최대 Transaction Attempt는 다음과 같이 확정한다.

```text
최초 시도 1회
+ ER_CHECKREAD(1020) 최대 Retry 2회
= 최대 Transaction Attempt 3회
```

정책은 다음과 같다.

```text
1번째 또는 2번째 Attempt에서 ER_CHECKREAD(1020)
→ rollback
→ Retry 가능 횟수가 남아 있으면
→ 새 Transaction에서 PUT Use Case 전체 재실행

3번째 Attempt에서도 ER_CHECKREAD(1020)
→ rollback
→ 원래 DB 예외 상위 전달
→ 공통 서버 오류 처리
```

`FOR UPDATE` Query 한 문장만 다시 실행하지 않는다.

Retry 시 다음 전체 흐름을 새 Transaction 기준으로 다시 수행한다.

```text
Category 조회/검증
→ 현재 Interest FOR UPDATE 조회
→ 기존 상태 검증
→ current / requested diff 계산
→ delete / add / flush
→ commit
```

`ER_CHECKREAD(1020)` 이외의 알 수 없는 DB 오류를 Retry 대상으로 일반화하지 않는다.

Retry exhaustion을 임의의 Domain `409 Conflict`로 변환하지 않는다.

### v1.0.3 내 문구 해석 정정

`v1.0.3`에 남아 있는 다음 취지의 문구는 본 문서로 대체한다.

```text
정확한 최대 Retry 횟수는 Phase 3 구현 전에 별도 확정한다.
```

최종 값은 이미 다음과 같이 확정 및 구현되어 있다.

```text
MAX_UPDATE_ATTEMPTS = 3
```

---

## 4. Category Taxonomy 후속 확정 사항 연결

관심사 조회/수정 기능의 Category 관련 세부 정책은 다음 최신 문서를 함께 기준으로 사용한다.

```text
docs/designs-feature/관심사 분류/
Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.md
```

현재 후속 확정 사항은 다음과 같다.

```text
사용자 관심사 저장/수정 단위
→ 활성 대분류만 허용

대분류
→ category_code 사용
→ parent_id = NULL

세부분류
→ category_code = NULL
→ parent_id = 대분류 category_id

category_name
→ 사용자 표시명
→ 전역 UNIQUE 식별자로 사용하지 않음
→ 서로 다른 부모 아래 동일 표시명 허용

Category Master Seed v1.0
→ 대분류 6개
→ 세부분류 38개
→ 총 44 Row
```

이번 Taxonomy 확정으로 **관심사 API 계약 자체는 변경되지 않는다.**

관심사는 기존과 동일하게 다음 조건을 만족하는 Category만 저장/수정할 수 있다.

```text
존재함
AND is_active = true
AND parent_id IS NULL
```

세부분류는 Trend 분류를 위한 단위이며 사용자 관심사 Row에 직접 저장하지 않는다.

---

## 5. Category Seed와 관심사 기능의 관계

Category Master Seed v1.0은 관심사 기능이 참조하는 기준 데이터를 제공하지만, 관심사 Service가 Seed 생성 책임을 가지지는 않는다.

책임은 다음과 같이 분리한다.

```text
Category Seed
→ 서비스 구동에 필요한 Category Master Data 생성/동기화

InterestService
→ 요청된 category_id가 존재하는 활성 대분류인지 검증
→ 사용자 관심사 저장/조회/수정
```

Category Seed 구현은 Alembic Schema Migration과 분리된 별도 idempotent Seed 방식으로 진행한다.

Seed가 아직 구현되지 않았다는 이유로 현재 관심사 GET / PUT 설계를 변경하지 않는다.

---

## 6. 현재 완료/미완료 상태 해석

2026-09-09 기준 문서와 구현 상태는 다음과 같이 구분한다.

| 항목 | 상태 |
| --- | --- |
| 관심사 GET Backend | 구현됨 |
| 관심사 PUT Backend | 구현됨 |
| `InterestService` 최대 Attempt 3회 | 구현됨 |
| 활성 대분류만 관심사 허용 | 구현/설계 유지 |
| Category `category_name` 전역 UNIQUE 제거 | 구현됨 |
| Category Taxonomy / Seed v1.0 목록 | 설계 확정 |
| Category Master Seeder | 구현 전 |
| 관심사 GET Frontend API / Query | 구현 전 |
| 관심사 PUT Frontend Mutation | 구현 전 |
| `InterestEditScreen` | 구현 전 |

이 표는 설계의 완료 여부와 실제 코드의 구현 여부를 혼동하지 않기 위한 상태 메모다.

---

## 7. 최종 유지 정책

본 v1.0.4 보강 후 관심사 조회/수정의 핵심 정책은 다음과 같다.

```text
POST
→ 최초 관심사 저장 전용

GET
→ 현재 사용자 관심사 Collection 조회
→ 관심사 없음은 200 + []

PUT
→ 비어 있지 않은 최종 관심사 집합 전체 교체
→ Backend 내부에서는 keep / add / remove diff

저장 가능한 Category
→ 존재하는 활성 대분류만

Transaction
→ InterestService 소유

Repository
→ 조회 / add / delete / flush
→ commit / rollback 하지 않음

동일 사용자 동시 PUT
→ FOR UPDATE 계열 Lock
→ ER_CHECKREAD(1020) 시 whole-transaction retry
→ 최대 Transaction Attempt 3회

정상 PUT 성공
→ AuthProvider 인증 Session 상태 변경 없음

상태 불일치 409
→ Frontend에서 revalidateSession() 정책 유지
```

---

## 8. 구현 시작 시 재검증 규칙

향후 관심사 Frontend 조회/수정 또는 Category Seed 구현을 시작할 때는 본 문서의 날짜를 현재 상태라고 가정하지 않는다.

반드시 작업 대상 브랜치의 최신 HEAD에서 다음을 다시 확인한다.

```text
Router
→ Schema
→ Service
→ Repository
→ ORM / Migration
→ 관련 Test
→ Frontend API / Hook / Screen
→ Navigation
→ 최신 Category Taxonomy 확정안
```

Category 관련 판단이 본 문서와 최신 Category Taxonomy 문서에서 겹치는 경우 더 구체적인 최신 Category Taxonomy 확정안을 우선한다.
