# Trend Leader [기능명] 기능 통합 설계

## 1. 채팅 목적

이 채팅은 Trend Leader의 `[기능명]`에 대한 백엔드·프론트엔드 통합 설계 채팅입니다.

이번 채팅에서는 실제 전체 구현 코드를 작성하기보다 다음 사항을 확정하는 것을 목표로 합니다.

* 사용자 시나리오
* 기능 범위와 제외 범위
* 화면 흐름
* API 계약
* 백엔드 책임 분리
* DB 처리 방식
* 프론트엔드 상태 및 컴포넌트 구조
* 예외 처리
* 테스트 시나리오
* 구현 단위와 순서

붙여넣기 가능한 전체 구현 코드는 별도의 구현 채팅에서 작성합니다.

## 2. 기능 목표

`[사용자가 이 기능을 통해 수행할 행동과 얻는 결과]`

예시:

```text
사용자가 활성 대분류 카테고리를 조회하고 관심사를 선택한 뒤,
선택한 카테고리를 자신의 관심사로 저장할 수 있어야 합니다.
```

## 3. 현재 진행 상태

### 완료된 부분

* `[완료된 백엔드 기반 코드]`
* `[완료된 프론트엔드 기반 코드]`
* `[완료된 DB 또는 Migration]`

### 아직 결정되지 않은 부분

* `[결정이 필요한 API 항목]`
* `[결정이 필요한 화면 항목]`
* `[결정이 필요한 비즈니스 규칙]`

## 4. 이번 설계 범위

### 포함

* `[기능 1]`
* `[기능 2]`
* `[기능 3]`

### 제외

* `[후속 기능 1]`
* `[후속 기능 2]`

제외 범위는 이번 설계에 임의로 포함하지 말아주세요.

## 5. 자료 우선순위

첨부 자료가 충돌하는 경우 다음 우선순위로 판단해주세요.

1. 현재 브랜치의 실제 소스코드
2. 적용된 Alembic Migration과 SQLAlchemy ORM
3. 확정된 API 계약 또는 실제 Swagger 응답
4. `schema_decisions.md`
5. 최신 ERD v2
6. Backend / Frontend 코딩 컨벤션
7. 최신 README
8. API 구성표
9. UI 디자인 문서와 기획서
10. 기존 SQL 및 과거 문서

자료 간 충돌이 발견되면 임의로 혼합하지 말고 다음 형식으로 구분해주세요.

```text
충돌 항목:
현재 구현:
과거 문서:
이번 설계 기준:
수정이 필요한 문서:
```

## 6. 전체 처리 흐름

다음 세로 흐름을 기준으로 설계해주세요.

```text
사용자 행동
→ Screen
→ Hook
→ API Function
→ FastAPI Router
→ Service
→ Repository
→ Database
→ Response
→ Hook 상태 갱신
→ Screen 반영
```

## 7. Backend 설계 기준

백엔드는 다음 책임을 유지합니다.

```text
Router
→ HTTP 요청·응답, Dependency 주입

Service
→ 비즈니스 검증, 여러 Repository 조합, 응답 데이터 구성

Repository
→ SQLAlchemy 기반 DB 조회·저장·수정·삭제

Schema
→ 요청·응답 데이터 검증

Model
→ DB 테이블 매핑

Dependency Provider
→ Repository와 Service 객체 조립
```

Router에서 Session, Repository, Service를 직접 생성하지 않습니다.

Service에서 SQLAlchemy Query를 직접 작성하지 않습니다.

Repository에 화면 흐름이나 비즈니스 판단을 넣지 않습니다.

## 8. Frontend 설계 기준

프론트엔드는 다음 책임을 유지합니다.

```text
Screen
→ 화면 구성, 사용자 이벤트, Navigation

Hook
→ React Query 상태와 API 호출 흐름

API Function
→ 서버 통신

Component
→ 재사용 UI

Type
→ API 요청·응답과 화면 데이터 타입
```

Screen에서 API Function을 직접 호출하지 않습니다.

조회는 `useQuery`, 생성·수정·삭제는 `useMutation`을 기준으로 합니다.

서버 응답 필드는 `snake_case`를 유지합니다.

공통 응답은 `CommonResponse<T>`를 사용합니다.

로딩, 오류, 빈 데이터, 성공 상태를 모두 설계합니다.

## 9. 반드시 결정할 항목

다음 순서로 설계해주세요.

### 9.1 사용자 흐름

* 화면 진입 조건
* 최초 상태
* 사용자 입력
* 버튼 활성화 조건
* 성공 후 이동
* 실패 후 처리

### 9.2 API 계약

* 기능명
* Method
* Endpoint
* 인증 필요 여부
* Path Parameter
* Query Parameter
* Request Body
* Response Body
* 상태 코드
* 예외 응답

### 9.3 Backend

* 필요한 Schema
* 필요한 Repository 메서드
* Service 검증 규칙
* 트랜잭션 범위
* Dependency Provider
* Router 반환 방식

### 9.4 Database

* 사용 테이블
* 조회 조건
* 저장 또는 수정 정책
* 중복 정책
* 외래 키 관련 정책
* Migration 필요 여부

### 9.5 Frontend

* 필요한 Type
* API Function
* Query Key
* Hook
* Screen
* Feature Component
* Shared Component
* Navigation
* 로딩·오류·빈 상태
* 캐시 갱신 방식

### 9.6 테스트

* 정상 시나리오
* 입력값 오류
* 인증 오류
* 데이터 없음
* 중복 요청
* 서버 오류
* 프론트 화면 상태

## 10. 설계 결과 형식

최종 결과를 다음 형식으로 정리해주세요.

1. 기능 정의
2. 포함·제외 범위
3. 사용자 흐름
4. 확정 API 계약
5. Backend 책임표
6. Database 처리표
7. Frontend 책임표
8. 예외 처리표
9. 생성·수정 예정 파일
10. 구현 순서
11. 테스트 시나리오
12. 미결정 사항
13. 구현 채팅에 전달할 인수인계 요약

설계 과정에서는 대안이 있다면 최소 두 가지를 비교하고, 최종 권장안을 명시해주세요.

설계가 완료되면 마지막에 다음 체크리스트를 제공해주세요.

```text
[ ] 기능 범위 확정
[ ] API 계약 확정
[ ] DB 처리 확정
[ ] Backend 책임 확정
[ ] Frontend 책임 확정
[ ] 예외 처리 확정
[ ] 테스트 기준 확정
[ ] 미결정 사항 없음
[ ] 구현 채팅 전환 가능
```
