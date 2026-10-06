# Trend Leader 관심사 기반 맞춤 트렌드 목록 조회 — 구현 채팅 시작 프롬프트

## 1. 사용 방법

새 구현 채팅에 아래 프롬프트를 붙여 넣고 설계 확정안 v1.0과 현재 기준 소스/저장소를 함께 제공한다. 이전 Review의 PASS는 설계 판정이며 현재 코드 검증 결과가 아니다.

## 2. 복사용 프롬프트

```text
같은 Trend Leader 프로젝트의 기능별 채팅 분리 기준을 적용해주세요.

이번 채팅은 `관심사 기반 맞춤 트렌드 목록 조회 구현` 채팅입니다.

프로젝트의 `Trend_Leader_AI_Development_Guidelines.md`와 첨부한
`Trend_Leader_관심사_기반_맞춤_트렌드_목록_조회_설계_확정안_v1.0.md`를
기준으로 진행해주세요. 이미 사용자 Design First Pass, Refinement,
11개 관점 Final Review와 Main 전환 결정까지 완료했습니다.
현재 계약을 처음부터 재설계하거나 이미 확정한 결정을 반복 질문하지 마세요.

우선 실제 저장소의 dev 최신 HEAD, 현재 작업 브랜치, working tree,
설치된 의존성 버전과 관련 코드·테스트를 확인하고 기준 SHA를 기록해주세요.
문서 작성 당시 HEAD는 이번 문서화 환경에서 확인하지 못했으므로
과거 SHA나 기억을 현재 HEAD로 간주하지 마세요.
소스가 없거나 접근할 수 없다면 필요한 파일을 구체적으로 알려주시고,
보이지 않는 함수·타입·API·설정을 추측해 구현하지 마세요.

먼저 확인할 자료와 연결은 다음과 같습니다.
- 전체 최신 트렌드 목록의 최신 확정안 및 GET /api/trends 실제 구현
- Router, CurrentUserDep, 공통 Exception Handler, Schema, Cursor Codec
- TrendService/TrendRepository 및 Source/Category batch 조회
- InterestRepository/Category 조회와 Root → Child 정책
- AuthProvider, Session 재검증, 공통 401 및 stale 401 방어, Cleanup
- Frontend 목록 API/Hook/Query Key, useUpdateInterests, InterestEditScreen
- MainPlaceholderScreen, TrendCard, Navigation 정의와 관련 테스트
- 실제 ORM Model, Migration, DB 설정 및 인덱스

첨부된 관심사 설계 v1.0.2의 향후 Trend invalidate 확장 지점은
이번 기능의 `취소 후 Personalized Pagination 전체 Reset` 계약으로 구체화합니다.
정상 관심사 수정의 응답 캐시 반영과 Session 재검증 생략은 유지해주세요.
과거 관심사/인증 채팅의 Main 기능 제외는 그 기능의 범위 제한이며,
이번에는 사용자가 승인한 실제 Personalized Main 전환을 구현합니다.
다른 충돌이 발견되면 근거와 영향 범위를 먼저 알려주세요.

이번 포함 범위:
1. GET /api/trends/personalized: 인증 필수, cursor 선택,
   limit 기본 20 / 1~50, category_id 필터 미지원.
2. 서버의 현재 사용자 관심 Root 중 유효 활성 Root를 선택하고
   활성 직속 Child 집합으로 확장하여 ACTIVE Trend를 조회.
3. 다중 Category Match에도 Trend 1회 반환.
   중복 row를 limit한 뒤 응답에서만 제거하는 방식은 피하고
   page 크기, has_next, Cursor 경계를 함께 검증.
4. last_collected_at DESC, trend_id DESC 및 기존 TrendListData 재사용.
   Source/Category 응답 정책과 batch 조회도 기존 계약을 재사용.
5. Personalized Cursor 논리 필드:
   version, last_collected_at, trend_id, context_fingerprint.
   현재 user_id + 정렬·중복 제거한 effective Child IDs로 SHA-256 계산.
   한 요청에서 같은 Child 집합을 Fingerprint와 실제 Query에 사용.
   Context 불일치는 400 INVALID_CURSOR.
   limit은 Fingerprint에서 제외.
6. Interest row 없음: 409 INTERESTS_NOT_INITIALIZED.
   row는 있으나 유효 Child Scope 없음: 409 INTERESTS_NOT_AVAILABLE.
   일부만 유효: 가능한 Scope로 200.
   유효 Scope는 있으나 Trend 없음: 200 정상 Empty.
7. Personalized API/Hook/Query Key는 Public과 분리하고
   authenticatedApiClient 사용. 응답 타입과 카드 UI는 재사용.
8. PUT 성공: 관심사 응답 Cache 반영, 진행 중 Personalized Query 취소,
   이전 pages/pageParams/Cursor 폐기, 다음 조회는 첫 페이지부터.
   Public 최신 목록 및 Category Cache는 이 Reset으로 변경하지 않음.
   PUT 실패는 성공한 것처럼 Reset하지 않음.
9. 추가 페이지 INVALID_CURSOR는 이전 Pagination 폐기 후
   Cursor 없는 첫 페이지를 1회 자동 요청.
   복구 실패는 해당 오류 UI로 전환하며 무한 Restart 금지.
10. Pull-to-refresh는 현재 관심사 기준 첫 페이지부터 재구성.
11. MainPlaceholderScreen을 맞춤 목록이 바로 보이는 Main으로 전환.
    Personalized 카드 번호 생략, 기존 Public 카드 동작 보존.
    관심사 수정·전체 최신 목록 진입점 및 기존 로그아웃 흐름 유지.
12. 설계 확정안의 Main 상태표, 테스트, 실제 기기 Acceptance,
    MariaDB EXPLAIN, 문서 정합성 검증.

보존할 핵심 한계와 안전조건:
- Fingerprint는 인증/서명이나 전체 Dataset Snapshot이 아님.
  인증 사용자 Scope는 매 요청 서버가 결정.
- 관심사 수정 후에도 유효 Child 집합이 같으면 Fingerprint가 같을 수 있음.
  그래도 클라이언트 PUT 성공 Reset은 항상 수행.
- live-feed에서 수집 시각/상태/매핑 변경에 따른 페이지 이동 한계는
  기존 Public 목록과 동일하며 Fingerprint가 해결한다고 표현하지 않음.
- Cursor 파싱, Public Cursor 오용, 미지원 버전 실패 경로 검증.
- 사용자 ID 없는 Key는 기존 계정 전환/로그아웃/401 Cleanup이 실제로
  사용자 Query 취소·Cache 제거를 보장하는지 확인하고 사용.
- cancel 호출만으로 Race 방어를 완료 처리하지 말고 AbortSignal,
  늦은 응답/Callback, 활성 Observer와 새 조회 타이밍을 확인.
- INITIALIZED는 기존 Session 재확인 및 선언적 Onboarding 복구,
  AVAILABLE은 Interest Edit 유도. 401은 기존 공통 처리.
- Domain 400/409를 일반 네트워크 Retry로 반복하지 않음.
- 동적 Trend Route가 있으면 정적 personalized Route와 충돌 확인.

제외 범위:
AI/ML·행동 기반 추천, 추천 점수/가중치/인기순,
검색·북마크·상세 기능 신규 구현, 외부 수집·AI Provider,
Refresh Token·OAuth, 카테고리 운영 정책 고도화,
새 Recommendation Engine/Personalized Repository,
실측 근거 없는 인덱스·Schema 변경과 대규모 리팩터링.

진행 방식:
문제 → 현재 코드와 설계 대조 → 변경 책임과 검증 계획 → 구현 → 검증.
신규 Service 분기와 Fingerprint/Codec은 TDD 적합성을 먼저 판단해주세요.
작은 검증 가능한 단위로 진행하고 실제 코드의 import/타입/시그니처를 사용해주세요.
버전 의존 TanStack Query/Axios/ORM 동작은 설치 버전과 공식 자료로 확인해주세요.
실제 코드 확인 후 removeQueries/resetQueries 등의 구체 구현을 선택하세요.
Windows PowerShell에 맞는 명령을 제공하고 Bash 줄 연속 문자를 섞지 마세요.

관련 자동 테스트, 정적 검사, 회귀 검증, MariaDB와 실기기 확인을 구분해서
실행 결과를 보고해주세요. 실행하지 못한 항목은 이유와 남은 위험을 명시하세요.
설계 확정안 OBS-01~13은 해결 시 상태·기준 SHA·검증 근거를 갱신해주세요.
구현 완료·자동 검증 완료·실제 동작 검증 완료·기능 완료를 구분해주세요.

기본 협업 방식은 제가 코드를 반영하고 Commit/Push하는 방식입니다.
현재 지침의 `[type/domain] 작업 내용` 형식으로 검증된 작업 단위의
Commit Message를 제안하되, 별도 요청 없이 직접 Commit/Push하지 마세요.

첫 응답은 Phase 0의 실제 확인 결과, 설계와의 차이,
첫 구현 단위의 변경 파일·책임·실패 시나리오부터 시작해주세요.
```

## 3. 구현 시작 전 문서 반영

저장소에 사용하는 기존 문서 위치를 확인한 뒤 두 파일을 같은 설계 문서 디렉터리에 반영한다. 후보는 기존 프로젝트 관례의 `docs/designs-feature/`이며, 실제 경로를 확인하지 않고 새 구조를 강제하지 않는다.

이번 문서화 환경에는 Git 저장소가 제공되지 않았다. 아래는 실제 소스에 두 문서만 반영하고 diff를 확인한 뒤 사용할 Commit Message 제안이다.

```text
[docs/trend] 관심사 기반 맞춤 트렌드 목록 설계 확정안과 구현 프롬프트 추가
```

두 파일만 명시적으로 Stage하여 기존 사용자 변경을 섞지 않는다. 문서 Commit과 실제 기능 구현 Commit을 구분한다. Push는 기존 팀 Workflow와 사용자의 실행 결정을 따른다.
