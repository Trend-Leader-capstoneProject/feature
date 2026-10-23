# Trend Leader 전체 트렌드 목록 조회 구현 채팅 시작 프롬프트

아래 `복사할 프롬프트`부터 문서 끝까지 새 구현 채팅에 붙여 넣는다.

- 설계 문서 커밋: `710493187436ae409736f5813cf0ce4aab6d3494`
- 문서 브랜치: `docs/trend-list-design-v1`
- 설계 기준 dev HEAD: `8c934018b644934aa188501140fecb16d0213051`
- 위 SHA는 고정 기준점이며 현재 최신 HEAD라는 뜻이 아니다.

## 복사할 프롬프트

같은 Trend Leader 프로젝트의 기능별 채팅 분리 기준을 적용해주세요.
이번 채팅은 `전체 트렌드 목록 조회 구현` 채팅입니다.
승인된 설계를 다시 처음부터 질문하기보다 현재 코드 확인 → 구현 → 검증 순서로 진행해주세요.

### 1. 기준 저장소와 문서

Repository는 `Trend-Leader-capstoneProject/feature`입니다.

다음 문서를 먼저 읽고 기준으로 삼아주세요.

1. `docs/designs-feature/전체_트렌드_목록_조회/Trend_Leader_전체_트렌드_목록_조회_설계_확정안_v1.0.md`
2. `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`
3. `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`
4. `docs/designs-feature/관심사 분류/Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.1.md`
5. 현재 인증 세션 관리·로그아웃 및 관심사 조회·수정의 최신 확정안과 실제 코드

설계 v1.0은 문서 브랜치 `docs/trend-list-design-v1`의 커밋 `710493187436ae409736f5813cf0ce4aab6d3494`에 생성되었습니다. dev에 문서가 없다면 미병합 여부와 이 브랜치를 확인하세요. 파일을 못 찾았다는 이유로 설계를 추측해서 재작성하지 마세요.

실제 구현은 최신 dev와 작업 트리를 확인하고, 문서 변경이 포함된 기능 브랜치를 준비해서 진행하세요. 문서 브랜치가 dev에 미병합이면 분기 관계와 변경 파일을 먼저 확인하고, 문서 커밋을 안전하게 포함하는 방식을 선택하세요. 사용자 변경을 덮어쓰거나 dev를 자동 병합하지 마세요.

이번 구현 채팅의 지시는 구현·테스트를 위한 것이며, 이후 commit/push/PR merge는 해당 시점에 합의된 범위만 수행하세요.

### 2. 확정된 범위

`GET /api/trends`와 최신 트렌드 목록 화면을 구현합니다.

- 인증 불필요. 로그인 여부와 무관하게 publicApiClient 사용.
- ACTIVE만 조회. last_collected_at DESC, trend_id DESC.
- Cursor 기반 무한 스크롤. limit 기본 20, 허용 1~50.
- category_id는 활성 대분류·활성 세부분류 허용.
- 대분류는 활성 직계 세부분류로 확장하고 Trend 중복 제거.
- 기본 summary/thumbnail과 전체 Category/Parent 반환.
- 최신 Source는 collected_at DESC, source_id DESC로 1개 선정.
- 응답 필드명은 latest_source이며 object 또는 null.
- summary, thumbnail_url, source_title은 nullable.
- 표시 순번은 최종 표시 배열의 index+1. 실제 Rank가 아님.
- Category는 한 번에 약 2~3개를 표시하고 가로 스와이프.
- Source 원문 보기는 이번 구현 범위.
- 관련 요약·상세의 실제 데이터 연결은 후속 기능. 동작하지 않는 활성 버튼을 만들지 않음.
- 기존 AuthNavigator/AppNavigator에 LatestTrend 진입 추가. 새 GUEST 인증 상태는 만들지 않음.
- Category Master Seed와 별도 Demo Trend Seed 및 독립 테스트 Fixture.
- Demo는 Source가 있는 ACTIVE 25개와 별도 HIDDEN 데이터를 구성해 20+5 검증.

추천, 검색, 상세 API, 북마크, 실제 Rank, 외부 수집, AI Provider, Snapshot Feed, 인증 전면 개편은 제외합니다.

### 3. 두 주의사항을 구현·문서에 보존

`TL-LIST-001` — Source 최소 1개는 아직 모든 데이터에 보장되지 않습니다.

- latest_source=null을 정상 방어하고 전체 목록 500을 만들지 마세요.
- 정상 Demo·향후 수집 데이터에 Source가 있어야 한다는 규칙과 API nullable을 구분하세요.
- 후속 수집·관리 경로에서 불변조건을 보장하더라도 API non-null 변경은 별도 계약 검토 대상입니다.

`TL-LIST-002` — last_collected_at은 변경 가능한 정렬 키입니다.

- 페이지 사이 재관측으로 항목이 Cursor 앞에 이동하면 현재 스크롤에서 빠질 수 있습니다.
- 새로고침·재진입으로 최신 목록을 다시 확인하는 live-feed 의미를 보존하세요.
- 중복 제거 또는 timestamp 상한만으로 Snapshot이 보장된다고 설명하지 마세요.

주의사항을 해결하거나 정책이 변경되면 해당 코드 변경과 같은 PR/변경 묶음에서 확정안 §14의 상태·근거·이력과 본문/API/타입/테스트를 함께 갱신하세요. 해결 증거 없이 RESOLVED로 바꾸지 마세요.

### 4. 먼저 확인할 사항

다음 항목을 실제 최신 코드로 확인하고 `확인 완료 / 설계 목표 / 추가 확인 필요`를 구분해주세요.

- branch/HEAD/working tree와 문서 브랜치 병합 여부.
- 관련 AGENTS.md, 최신 설계 문서, 의존성·lock·실행 설정.
- Trend/Source/Category/Mapping ORM, Migration, Category Seed.
- Router 등록, Dependency, Schema, 공통 응답·예외 Handler, Session 수명 주기.
- publicApiClient, QueryClient/Provider, AuthProvider, Root/Auth/App/Onboarding Navigation.
- 기존 테스트 구조와 실제 실행 가능한 명령.

확정안 §13의 경계도 확인해주세요.

1. DB 저장 시간대·응답 직렬화·Cursor 시각 정밀도. 근거 없이 UTC 또는 KST로 단정하지 않기.
2. 비활성 부모 아래 활성 세부분류 필터 정책과 Category API 정합성.
3. 과거 비정상 Category 매핑 존재와 처리 정책.
4. Category 정렬, Cursor codec·입력 제한, 설치 버전 기준 Query 재시작 방식.
5. Demo의 개발 환경 경계와 재실행 식별 방법.

코드로 확정 가능한 것은 직접 해소하세요. 새로운 API 의미가 필요한 항목만 최소 선택지·영향과 함께 결정하고 문서에 반영하세요. 확인되지 않은 의존 코드·타입·환경변수·API를 임의로 만들지 마세요.

### 5. 책임과 구현 순서

Backend는 Router → Service → Repository 구조를 지켜주세요.

- Router/Schema: HTTP 입력과 envelope.
- Service: Category 의미, Cursor 검증, 응답 조립과 페이지 판단.
- Repository: Trend Page와 Source/Category Batch Query.
- Cursor helper: 테스트 가능한 순수 변환.

Trend 목록을 먼저 limit+1개 조회한 후 응답할 ID에 대해 Source와 Category를 일괄 조회하세요. Source×Category JOIN 결과에 직접 LIMIT을 적용하지 마세요. 다음 Cursor는 응답한 마지막 Trend로 만들고 초과 조회 행으로 만들지 마세요.

읽기 전용이므로 업무용 commit/잠금/관심사 쓰기 재시도를 추가하지 않되, 기존 Session 예외 rollback·close는 유지하세요.

Frontend는 API/Type/Query Key/Hook → Screen/Card → Navigation 순서로 진행하세요. Cursor는 pageParam으로 다루고, 필터 Key 변경만으로 기존 Cache가 항상 초기화된다고 가정하지 마세요. refresh/reentry/필터 재방문의 첫 페이지 재시작과 느린 응답을 검증하세요.

단계:

1. 현재 상태·충돌·미확정 경계 점검.
2. Backend Schema/Cursor/Service 행동 테스트와 구현.
3. Repository MariaDB 통합 및 Dependency/Router/OpenAPI 연결.
4. Demo Seed와 실제 API 검증.
5. Frontend 데이터 계층 및 Hook 검증.
6. 화면·원문·Navigation과 인증 회귀.
7. 실기기 Acceptance, 관련 회귀, 문서·diff 최종 점검.

각 단계에서는 변경 이유·파일·검증 결과를 짧게 설명하고 범위 안에서 이어서 진행해주세요. 중요한 계약 충돌이 발견된 경우에만 해당 결정부터 해결해주세요.

### 6. 검증과 보고

신규 Service 분기와 Cursor 순수 규칙에는 Red → Green → Refactor를 우선 적용하세요. 문서나 얇은 연결 코드까지 형식적으로 TDD를 강제하지 마세요.

최소한 다음을 검증해주세요.

- 정렬 동률, 경계 페이지, Category 중복 제거, 최신 Source 동률.
- 400/404/422 및 data.reason, nullable, 빈 목록, 마지막 Cursor.
- N+1 방지와 실제 MariaDB 쿼리 결과.
- Public 호출, pagination/refresh/filter race, 첫 오류·추가 오류 구분.
- Guest/로그인 진입, Android Back, 가로/세로 제스처, 외부 URL, 네트워크 복구.
- Session Restore/공통 401/로그아웃/관심사 흐름 회귀.

실행한 테스트와 미실행 검증을 구분하고 실기기 확인을 자동 테스트 통과로 대체하지 마세요. 사용자 환경은 Windows PowerShell이므로 명령을 한 줄 또는 PowerShell 문법으로 제공하세요.

최초 응답은 현재 코드 점검 결과, 설계와의 차이, 변경 예상 파일, 첫 구현 단계와 검증 계획부터 시작해주세요. 최종 보고에서는 구현 완료·자동 검증 완료·실기기 검증 완료·기능 완료를 구분해주세요.
