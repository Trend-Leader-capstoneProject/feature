# Trend Leader 관심사 기반 맞춤 트렌드 목록 조회 설계 확정안 v1.1

> 문서 상태: **FROZEN — B안 개인화 홈 역할·기능 정책 확정** (화면의 구체적인 시각 배치는 별도 Candidate)  
> 작성 기준일: 2026-10-13 (Asia/Seoul)  
> 기준 Repository: `Trend-Leader-capstoneProject/feature`  
> 기준 브랜치: `feat-personalized-trend-list`  
> 원격 기준 HEAD: `ff35b89160fd18a683adf14022725088bbef99a4` (Phase 5-5 체크포인트)  
> 선행 문서: 같은 폴더의 `Trend_Leader_관심사_기반_맞춤_트렌드_목록_조회_설계_확정안_v1.0.md` (FROZEN)  
> 관련 문서: `docs/frontend-design/screens/personalized-main-screen-spec.md` (화면 동작 요구 승인, 구체 시각 디자인 Candidate)  
> 구현 상태: Phase 5-5 자동 테스트 142개 PASS 및 TypeScript PASS는 사용자 실행 결과. **B안 홈 리팩터링 자체는 미구현·미검증.** 실기기 Acceptance는 별도.

## 0. 본 문서의 효력과 승계 방식

- 본 v1.1은 **v1.0의 개인화 조회 API·비즈니스 규칙·Cursor·Query·인증 계약을 전부 승계하는 화면 역할 변경안**이다.
- 다음 절에서 명시적으로 바꾸는 내용(메인 화면의 역할·명칭·진입점·홈 화면 정보 계층)만 v1.0을 구체화 또는 대체한다. **v1.0의 나머지 조항과 주의사항/OBS는 그대로 유효**하다.
- 확정안 충돌 시 해당 충돌을 보고한다. 기능별 구체 확정안, 현 채팅 사용자 명시 결정 및 `docs/prompt/Trend_Leader_AI_Development_Guidelines.md` v1.2의 우선순위를 따른다.
- **본 문서의 설계 확정은 기능 구현·실기기 Acceptance 완료를 뜻하지 않는다.** Home-H1~H4는 이 문서 확정 이후의 작업이며, 구체적인 레이아웃 픽셀 값은 화면 명세의 Candidate로 관리한다.

## 1. 변경 사유와 이전·새 결정

### 1.1 제품 의미

| 항목 | v1.0 및 기존 구현 | v1.1 결정 |
| --- | --- | --- |
| Main 역할 | 맞춤 트렌드 목록이 기본 콘텐츠인 Main | **B안: 개인화 추천을 중심으로 주요 기능을 탐색하는 홈 대시보드** |
| 사용자 1순위 경험 | 로그인 후 별도 이동 없이 맞춤 목록 바로 표시 | **그대로 유지**. 맞춤 목록은 홈의 핵심·최상위 콘텐츠 책임 |
| 컴포넌트 이름 | `MainPlaceholderScreen` | `PersonalizedMainScreen`으로 변경 |
| Route 키 | `Main` | 변경 없음 |
| 관심사 수정 | v1.0에서 Main 진입점 요구, 실제 코드는 409 복구 상태에서만 제공 | **정상 상태에도 `InterestEdit` 진입점 제공** |
| 전체 최신 | 기존 `LatestTrend` 진입점 | 유지 |
| 로그아웃 | 홈 상단 주요 버튼과 함께 노출 | **기능 유지, 시각적 우선순위 하향** |
| 북마크 | 별도 기능/화면 구현 범위 밖 | **향후 구현 시 홈에 연결**. 미구현 Route·API·눌러도 동작하지 않는 버튼은 만들지 않음 |
| Navigator | `AppNavigator`의 Native Stack | 유지. Bottom Tab은 별도 확정 전까지 추가하지 않음 |

### 1.2 기존 문서와의 충돌 처리

- v1.0 §2.3의 ‘맞춤 트렌드를 Main에 바로 제공’ 결정은 **변경하지 않는다.** Main의 책임을 ‘목록 전용’으로 해석하는 부분만 홈 대시보드 책임으로 확장한다.
- v1.0 §2.1의 관심사 수정 진입점은 현재 구현에서 정상 상태에 누락되어 있으므로, B안 작업 중 **기존 요구 누락분을 구현**한다.
- v1.0 §2.2의 ‘북마크 신규 구현 제외’는 이번에도 유지하며, **북마크 홈 연결은 이후 북마크 기능이 구현·검증되면 별도 작업으로 수행**한다. 이 문서가 북마크 API·Route 이름을 새로 정하지 않는다.
- 인증/관심사 기존 기능 설계의 임시 Main 범위 제한은 해당 기능 개발 당시의 제한이며, 이번 명시적인 Main 역할 승인에 따라 홈 역할을 정의한다. 다른 기능의 API 계약은 변경하지 않는다.

## 2. 반드시 보존할 불변조건

1. `GET /api/trends/personalized`는 인증 필수이며 요청·응답·오류 계약은 v1.0을 유지한다.
2. 추천 범위는 서버가 현재 사용자 관심 대분류에서 계산한 활성 세부분류 집합이다. `ACTIVE` Trend만, 중복 없이 반환한다.
3. 최신순 정렬 `last_collected_at DESC, trend_id DESC`, Cursor 기본 limit 20/허용 범위 1~50, Context Fingerprint 정책을 그대로 유지한다. 인기순·점수순·AI 추천 등 별도 의미를 표현하지 않는다.
4. `getPersonalizedTrends`, `usePersonalizedTrends`, `TrendCard`, Personalized Query Namespace 및 Public 목록과의 캐시 분리를 유지한다.
5. 관심사 PUT 성공 시 진행 중 Personalized 요청 취소, 이전 pages/pageParams/Cursor 제거 및 최신 관심사로 첫 페이지 재조회 정책을 유지한다. Public 최신 목록 Cache는 변경하지 않는다.
6. `INTERESTS_NOT_INITIALIZED` → Session 재검증 후 `RootNavigator` 선언적 Onboarding 복구; `INTERESTS_NOT_AVAILABLE` → 관심사 수정 안내·CTA; `INVALID_CURSOR` → 1회 첫 페이지 재시작을 유지한다.
7. 로그아웃, 공통 401 및 계정 전환 시 사용자 캐시 격리 정책을 유지한다.
8. `AppStackParamList`의 `Main`, `InterestEdit`, `LatestTrend`; `next_step=MAIN`; `AuthProvider`/`RootNavigator` 계약을 유지한다.
9. Backend/DB의 비즈니스 로직·Schema·Migration 변경은 **이번 UI 역할 변경의 범위 밖**이다.

## 3. PersonalizedMainScreen 책임과 비책임

### 3.1 화면 책임

- 로그인한 사용자에게 홈을 표시하고, **개인화 TrendCard 목록을 핵심 콘텐츠**로 제공한다.
- 현재 구현된 `InterestEdit` 및 `LatestTrend`로의 실제 동작하는 진입점을 제공한다.
- 로그아웃은 유지하되 주요 콘텐츠/탐색 버튼과 시각적으로 구분한다.
- 개인화 목록의 초기/추가 페이지 Loading·정상 Empty·일반 Error·도메인 409·Cursor 복구·Pull-to-refresh와 Retry UX를 유지한다.
- 기존 UI 데이터 흐름을 재사용하며 임의의 북마크 건수/최근 저장 목록을 만들지 않는다.

### 3.2 비책임

- 신규 북마크 목록 API·상세 화면·탭 탐색·추천 알고리즘·검색·추천 점수·새로운 전역 디자인 토큰 구현.
- 화면에서 직접 Session의 `next_step`을 변경하거나 `INTERESTS_NOT_INITIALIZED`에 대해 Onboarding으로 강제 `navigate()`하는 일.
- 개인화 Query를 화면 내부의 별도 데이터 캐시로 복제하거나 Cursor를 화면에서 직접 재계산하는 일.

## 4. 정보 계층·화면 구성 정책

**콘텐츠/의미상 우선순위:** (1) 화면 식별 및 간결한 사용자 안내 → (2) 개인화 트렌드가 홈의 핵심 콘텐츠임을 명확히 표시 → (3) 관심사 수정·최신 트렌드 등의 빠른 이동 → (4) 낮은 우선순위의 계정/로그아웃. 이 순서는 픽셀 단위 배치 순서가 아니다. 빠른 이동 버튼과 개인화 섹션의 상하 위치는 H3의 화면 검증에서 결정하되, 맞춤 목록이 핵심 콘텐츠라는 우선순위를 유지한다.

- 화면 상단에는 `Trend Leader` 및 과장하지 않은 안내문을 표시한다. 현재의 ‘로그인되어 있습니다/세션 복원’ 중심 문구는 홈 안내 중심으로 정돈하는 것이 H3 작업이다.
- **관심사 맞춤 트렌드**가 가장 큰 콘텐츠 영역을 차지한다. 기존 `TrendCard`의 번호 없는 표시 정책을 유지한다.
- `InterestEdit`·`LatestTrend`는 실제 등록된 Route에만 연결한다. 빠른 이동 버튼은 카드 목록의 가독성/스크롤을 해치지 않도록 간결하게 배치한다. 정확한 상·하단 배치는 화면 명세/실기기에서 조정한다.
- 로그아웃 버튼은 기능을 제거하지 않고 상대적으로 덜 강조한다. 새 ‘설정’ Route는 만들지 않는다.
- **현재 `ScreenContainer` + 단일 `FlatList` 구조를 우선 보존**한다. 홈 섹션 재배치 때문에 별도 수직 `ScrollView`로 `FlatList`를 감싸지 않는다. 필요한 경우 후속 H3에서 `FlatList.ListHeaderComponent` 채택 여부를 검토하며, 기존 Pagination/Refresh 행동 보존을 통과 기준으로 둔다.
- 북마크는 별도 기능이 구현되고 실제 화면·Route·필요한 데이터 흐름이 연결·검증된 이후 홈 진입점을 추가한다. **미구현 진입점의 빈 버튼·가짜 링크·추측 Route는 금지**한다.

## 5. UI 상태 정책과 우선순위

| 상태 | 홈 동작 / 불변조건 |
| --- | --- |
| 최초 Loading | 개인화 목록 영역의 기존 Loading, 홈 진입/인증 책임 보존 |
| 정상 목록 | 기존 TrendCard, 번호 없음, 최신순·추가 페이지·Refresh 유지 |
| 정상 Empty | 목록 없음 안내. 기본 관심사 수정 진입점은 접근 가능 |
| 일반 조회 오류 | **사용 가능한 Query Data가 없거나 Cursor 복구가 실패한 경우** 기존 Error + Retry. 그 밖의 일반 재조회 오류에서 캐시가 남아 있으면 현재 화면의 캐시 표시 정책을 보존한다. `409` 도메인 오류는 캐시보다 우선한다. 실제 접근 가능한 최신 트렌드·관심사 수정 진입점 보존 |
| 추가 페이지 Loading | 기존 목록 유지, Footer Loading |
| 추가 페이지 일반 오류 | 기존 목록 유지, Footer 수동 Retry; 자동 반복 재시도 없음 |
| Pull-to-refresh | 기존 카드 유지·Refresh Indicator 표시; `restart()`로 Cursor Chain 폐기 후 첫 페이지 재조회 |
| Refresh와 load-more 경합 | 이전 요청 취소·늦은 응답 무시, 새 첫 페이지 Cache·UI 오염 방지 |
| `INVALID_CURSOR` | 첫 페이지 1회 복구; 복구 실패 시 기존 정책의 Error/Domain UI |
| `INTERESTS_NOT_AVAILABLE` | 오래된 Cache 노출 금지; 복구용 관심사 수정 CTA 우선, 동일 CTA 중복 표시하지 않음 |
| `INTERESTS_NOT_INITIALIZED` | Session 재검증·RootNavigator 복구가 우선; 정상 관심사 수정 CTA로 오인 유도하지 않음 |
| 401/로그아웃 | 공통 인증 실패/Session Cleanup; 홈에서 임의 복구 시도하지 않음 |

**기존 상태와 차이:** 현재 `FlatList`는 목록에 항목이 있을 때에만 렌더링된다. 정상 Empty 화면에서는 기존 `EmptyView`를 유지한다. Empty에서 Pull-to-refresh까지 지원할지는 **별도 UX 개선 후보**이며 이번 B안의 필수 신규 기능이라고 간주하지 않는다.

## 6. 명칭·Navigation·코드 변경 범위

| 구분 | 예상 경로/명칭 | 변경 원칙 |
| --- | --- | --- |
| 이름 변경 | `frontend/src/app/screens/MainPlaceholderScreen.tsx` → `PersonalizedMainScreen.tsx` | 파일·함수·Props 타입 및 참조만 변경하는 **독립 커밋** |
| Navigator | `frontend/src/app/navigation/AppNavigator.tsx` | `component={PersonalizedMainScreen}`, Route는 `Main` 유지 |
| 기존 테스트 | `frontend/__test__/trend/PersonalizedMainScreen.test.tsx` 및 연계 통합/Navigation 테스트 | Mock·Import·컴포넌트 참조만 갱신, 기대 동작 변경 금지 |
| 관심사 수정 CTA | `PersonalizedMainScreen` | 정상 상태 진입점 추가, 409 복구 CTA 중복 방지, 동작 테스트 선행 |
| 홈 문구 및 배치 | `PersonalizedMainScreen` 및 필요 최소한의 기존 UI 구성 | API/Hook/TrendCard 구조 유지, 별도 변경 단계 |
| 북마크 | 미정 | 별도 기능 완성 뒤 Home 연결 작업으로 추진; 임의 파일·Route/API 생성 금지 |

## 7. 구현 순서와 체크포인트

| Phase | 작업 | 완료 기준 |
| --- | --- | --- |
| 5-5 (기존) | Pull-to-refresh·중복 요청·경합 방어 | `ff35b891` 체크포인트, 사용자 실행 기준 전체 142 tests 및 TS PASS |
| Home-H0 | v1.1 변경 계약/화면 명세 확정 | 사용자 검토, 상태·비범위 기록, 문서만 별도 저장 |
| Home-H1 | 파일·컴포넌트·Props·Import 이름 변경 | 기존 동작 보존, 관련/전체 테스트·TypeScript PASS, 독립 커밋 |
| Home-H2 | 정상 상태 InterestEdit CTA 연결 및 중복 상태 분기 | RED → GREEN, 409/Navigation 회귀 PASS, 별도 커밋 |
| Home-H3 | 개인화 중심 홈 문구·정보 계층 정돈 | 기존 스크롤/목록·Refresh/CTA/Logout 동작 유지, Android 레이아웃 확인 |
| Home-H4 | 전체 회귀·실기기 Acceptance·문서 정합성 | 테스트/실기기 실행 증거, 미검증 명시, diff 확인 및 체크포인트 |
| 향후 Bookmark 연계 | 북마크 기능 구현 뒤 홈 진입점 연결 | 실제 Bookmark 화면/Route·데이터 흐름 확인 및 Navigation/기기 테스트 |

커밋 직전 최신 `HEAD`·Working Tree·diff를 재확인한다. 미커밋 로컬 작업을 원격 과거 코드로 덮어쓰지 않는다. 화면 구조·기능 변경을 기계적 이름 변경과 같은 커밋에 섞지 않는다.

## 8. 테스트·Acceptance Criteria

### 8.1 Frontend 자동 검증

- `Main` Route를 유지하면서 새 컴포넌트로 실제 연결된다.
- 최초 조회, 정상 목록·Empty·일반 Error·Footer Loading/Retry가 기존과 같다. 사용 가능한 캐시가 있는 일반 재조회 오류와 캐시보다 우선하는 409 도메인 오류를 구분한다.
- 정상 화면에서 `InterestEdit`, `LatestTrend` 버튼이 각각 올바른 Route로 이동한다.
- `INTERESTS_NOT_AVAILABLE`에서 정상 CTA와 복구 CTA가 중복되지 않고 오래된 Cache가 표시되지 않는다.
- `INTERESTS_NOT_INITIALIZED`의 재검증 → 선언적 Onboarding 전환 및 401 처리에 변화가 없다.
- PUT 성공 후 Personalized Cache/Cursor가 초기화되고 Public 목록은 유지된다.
- `INVALID_CURSOR`, Pull-to-refresh, load-more와 Refresh 경합·늦은 응답의 차단을 보존한다.
- 로그아웃 및 계정 전환에서 이전 사용자 데이터가 나타나지 않는다.
- 북마크 미구현 상태에서 가짜 액션이나 추측 Route가 없다.
- 전체 Frontend 테스트·TypeScript 검사를 통과하고 변경 파일 및 Diff가 설명 가능하다.

### 8.2 실기기·Backend 연계 검증 (미실시)

1. Android 실기기에서 로그인/세션 복원 → Main 첫 화면의 개인화 트렌드 표시.
2. 정상 상태에서 관심사 수정 → PUT 저장 → Main 복귀 후 현재 관심사 기준 첫 페이지 확인.
3. 최신 트렌드 이동 및 뒤로가기; 기존 개인화 화면 복귀.
4. 여러 페이지 추가 조회, Refresh, Footer Retry, 작은 화면에서 CTA·목록 스크롤/터치 영역 확인.
5. 정상 Empty와 두 409 원인의 회복 경로 확인.
6. 로그아웃·401·계정 전환 후 이전 Cache 노출 방지.
7. 기존 v1.0이 요구하는 MariaDB EXPLAIN 및 서버 연계 검증 항목은 이 UI 변경으로 완료됐다고 판단하지 않는다.

## 9. 변경 이력

| 문서 버전 | 날짜 | 내역 |
| --- | --- | --- |
| v1.0 | 2026-10-06 | 맞춤 목록 조회 및 Main 기본 콘텐츠 설계 FROZEN |
| v1.1 (FROZEN) | 2026-10-13 | B안 개인화 홈 역할·명칭·진입점·로그아웃/스크롤/북마크 연결 정책 확정, 오류-캐시 상태 구분 보완. 기존 API·도메인·Cursor 계약 승계 |

**다음 작업:** 본 확정안과 Screen Specification을 기존 기능 코드와 분리해 문서만 커밋한다. 이후 Home-H1 순수 이름 변경으로 착수한다. 실제 Home 구현·Backend/실기기 검증 상태는 별도로 추적한다.
