# Trend Leader [기능명] 기능 통합 구현

## 1. 채팅 목적

이 채팅은 Trend Leader의 `[기능명]`을 백엔드부터 프론트엔드까지 구현하는 채팅입니다.

첨부한 `[기능명] 통합 설계 결과`를 구현 기준으로 사용해주세요.

설계 내용에 중대한 모순이 없는 한 기능 범위와 API 계약을 임의로 다시 설계하지 말고, 현재 실제 소스코드에 맞게 구현해주세요.

## 2. 구현 목표

이번 구현에서 다음 세로 흐름을 완성합니다.

```text
사용자 행동
→ Screen
→ Hook
→ API Function
→ FastAPI Router
→ Service
→ Repository
→ Database
→ API Response
→ Screen 반영
```

## 3. 이번 구현 범위

### 포함

* `[Backend 구현 범위]`
* `[Frontend 구현 범위]`
* `[테스트 범위]`
* `[문서 수정 범위]`

### 제외

* `[후속 기능]`
* `[이번 브랜치에서 다루지 않을 기능]`

제외 범위는 임의로 구현하지 말아주세요.

## 4. 기준 자료 우선순위

첨부 자료가 충돌하는 경우 다음 우선순위로 판단해주세요.

1. 현재 브랜치의 실제 소스코드
2. 적용된 Alembic Migration과 SQLAlchemy ORM
3. 확정된 기능 통합 설계 결과
4. 실제 Swagger API 응답
5. `schema_decisions.md`
6. 최신 ERD v2
7. Backend / Frontend 코딩 컨벤션
8. 최신 README
9. API 구성표와 기획 문서
10. 기존 SQL 및 과거 문서

충돌을 발견하면 코드를 작성하기 전에 다음 형식으로 알려주세요.

```text
충돌 위치:
현재 코드:
설계 문서:
권장 적용안:
영향받는 파일:
```

## 5. Backend 구현 기준

다음 구조를 유지해주세요.

```text
Router
→ Service
→ Repository
→ Database
```

Repository와 Service 생성은 `app/api/dependencies`에서 담당합니다.

Router에서 Session, Repository, Service를 직접 생성하지 않습니다.

Router는 HTTP 요청·응답만 담당합니다.

Service는 비즈니스 검증과 데이터 조합을 담당합니다.

Repository는 DB 접근만 담당합니다.

요청·응답은 Pydantic Schema로 정의합니다.

모든 성공 응답은 프로젝트의 공통 응답 구조를 사용합니다.

## 6. Frontend 구현 기준

다음 구조를 유지해주세요.

```text
Screen
→ Hook
→ API Function
→ FastAPI
```

Screen에서 API Function을 직접 호출하지 않습니다.

조회에는 `useQuery`, 생성·수정·삭제에는 `useMutation`을 사용합니다.

서버 응답 필드는 `snake_case`를 유지합니다.

공통 응답은 `CommonResponse<T>`를 사용합니다.

로딩, 오류, 빈 데이터, 성공 상태를 처리합니다.

Feature 전용 코드는 해당 `features/[기능명]`에 배치하고, 여러 기능에서 실제로 재사용되는 코드만 `shared`에 배치합니다.

## 7. 코드 작성 방식

설명용 예제가 아니라 현재 프로젝트에 바로 붙여넣을 수 있는 코드를 작성해주세요.

코드는 다음 순서로 제공해주세요.

```text
1. 파일 경로
2. 해당 파일의 책임
3. 수정 또는 생성 이유
4. 파일 전체 코드
```

기존 파일을 수정하는 경우 생략 부호 없이 수정된 전체 파일을 제공해주세요.

첨부되지 않은 의존 코드나 타입을 임의로 추정하지 말아주세요.

필수 의존 코드가 확인되지 않는 경우 구현을 가정으로 밀어붙이지 말고, 다음 형식으로 누락 사항을 분리해주세요.

```text
필요한 파일:
필요한 이유:
확인할 타입 또는 함수:
현재 구현 가능한 범위:
```

다만 확인 가능한 범위의 코드는 먼저 완성해주세요.

## 8. 구현 진행 순서

다음 순서로 진행해주세요.

1. 현재 소스 구조 분석
2. 설계 결과와 현재 코드의 차이 분석
3. 생성·수정 파일 목록 확정
4. Backend Repository 구현
5. Backend Service 구현
6. Dependency Provider 구현
7. Backend Router와 Schema 구현
8. Backend 테스트 구현
9. Frontend Type 구현
10. Frontend API Function 구현
11. Frontend Hook 구현
12. Frontend Component 구현
13. Frontend Screen 구현
14. Navigation 연결
15. Backend·Frontend API 계약 검증
16. 실행 및 테스트 방법 정리
17. README 또는 문서 반영 사항 정리

## 9. 검증 기준

### Backend

* Router가 DB에 직접 접근하지 않음
* Service가 ORM Query를 직접 작성하지 않음
* Repository에 비즈니스 판단이 없음
* Dependency Provider에서 객체를 조립함
* Pydantic 응답 타입과 실제 반환값이 일치함
* 예외 상태 코드가 설계와 일치함
* 테스트가 정상·예외 시나리오를 포함함

### Frontend

* TypeScript 타입 오류가 없음
* Screen에서 API Function을 직접 호출하지 않음
* React Query Query Key가 일관됨
* 로딩·오류·빈 상태가 구현됨
* API 응답 접근 방식이 실제 응답과 일치함
* Navigation 타입이 일치함
* 불필요한 전역 상태를 만들지 않음
* 사용하지 않는 import와 임시 코드가 없음

### Integration

* Method와 Endpoint가 양쪽에서 일치함
* Request 필드가 일치함
* Response 필드가 일치함
* 인증 Header가 필요한 요청에 적용됨
* 성공 후 화면 상태가 갱신됨
* Mutation 후 필요한 Query가 무효화됨
* 서버 오류 메시지를 프론트에서 처리함

## 10. 최종 결과 형식

마지막에는 다음 내용을 정리해주세요.

1. 구현된 기능
2. 생성한 파일
3. 수정한 파일
4. Backend 데이터 흐름
5. Frontend 데이터 흐름
6. API 계약 검증 결과
7. 실행 명령
8. 테스트 방법
9. 남은 작업
10. 권장 커밋 메시지
11. 팀원에게 전달할 변경 사항
