# Trend Leader PersonalizedMainScreen — Screen Specification v0.2

> 문서 유형: Frontend Screen Specification
> 상태: **Candidate** — 개선형 B안 정보 구조·진입점 배치는 팀 승인 및 구현 완료, 시각 세부사항·전체 Home-H4 Acceptance는 계속 검증 대상
> 작성 기준일: 2026-10-13 (Asia/Seoul)
> 최종 정합성 점검일: 2026-10-23 (Asia/Seoul)
> 대상 플랫폼: Expo / React Native, Android 우선
> 대상 브랜치: `feat-personalized-trend-list`
> H4C-2 구현 확인 커밋: `0098ab331d8227bf363ed891245d3d8eb5266445` (이후 HEAD의 불변 선언이 아닌 검토 기준점)
> 현재 구현: `frontend/src/app/screens/PersonalizedMainScreen.tsx` (`Main` Route 유지)
> 상위 계약: `Trend_Leader_관심사_기반_맞춤_트렌드_목록_조회_설계_확정안_v1.0.md` 및 v1.1 FROZEN (화면 역할 변경만 v1.1 우선)
> 관련 UI 기준: `docs/frontend-design/design-system/design-system-snapshot.md` v0.1 **Candidate**
> H4C-2 승인 설계: `docs/frontend-design/screens/Trend_Leader_H4C-2_개선형_B안_화면_설계_승인안.md`
> 구현 상태: Home-H1~H3, H4B, H4C-1, H4C-2 레이아웃 코드 반영; 자동 검사는 사용자 실행 보고, Android 시각 검토 및 개인화 GET 200 로그 확인. 전체 H4 Acceptance와 최종 시각 동결은 미완료

## 1. 화면 목적

`PersonalizedMainScreen`은 인증된 사용자가 로그인 후 도착하는 **개인화 홈 대시보드**다. 관심사 맞춤 트렌드 목록이 핵심 콘텐츠이며, 현재 구현된 주요 기능인 관심사 수정 및 전체 최신 트렌드로 자연스럽게 이동할 수 있다.

- **Must:** 맞춤 목록을 기본 표시한다. 별도의 추천 목록 전용 Route를 거치지 않는다.
- **Must:** `Main` Route 이름과 인증 흐름을 유지한다.
- **Must not:** 북마크·검색·탭·트렌드 상세 등 아직 구현·확정되지 않은 동작을 만들어내지 않는다.
- **Future:** 북마크 기능이 구현·검증되면 실제 화면 및 Route에 홈 진입점을 연결한다.

## 2. 진입 조건과 외부 의존

| 항목 | 계약 |
| --- | --- |
| 인증 | `AuthProvider`의 AUTHENTICATED 세션 |
| 분기 | `next_step=MAIN`이면 `RootNavigator` → `AppNavigator` |
| Stack Route | **`Main`** (변경 금지) |
| 화면 컴포넌트 | `PersonalizedMainScreen` (H1 변경) |
| 맞춤 API | 인증 Client의 `GET /api/trends/personalized` |
| 데이터/캐시 | `getPersonalizedTrends` + `usePersonalizedTrends` + 전용 Query Key |
| 실제 이동 가능 Route | `InterestEdit`, `LatestTrend` |
| 로그아웃 | 기존 `useAuth().logout()` |

세션/온보딩 조건 판단은 `RootNavigator`가 책임진다. Main에서 신규 인증 규칙을 만들지 않는다.

## 3. 정보 계층과 화면 요소

### 3.1 콘텐츠 우선순위

1. **홈 식별:** `Trend Leader` 및 간결한 안내문. 로그인 확인용 임시 문장은 H3에서 홈 문구로 변경한다.
2. **핵심:** `관심사 맞춤 트렌드` 섹션. 개인화 목록이 가장 넓은 콘텐츠 영역을 차지하며 순번이 없다.
3. **보조 진입:** 정상 상태의 `관심사 수정`은 개인화 섹션 제목 옆, `전체 최신 보기`는 첫 카드 위에 배치한다. 시각 레이블과 접근성 이름의 구분은 H4C-2 설계안을 따른다.
4. **계정/보조:** 로그아웃은 항상 동작하지만 시각적 우선순위를 낮추고 주요 탐색 액션과 분리한다.
5. **북마크:** 미구현 단계에는 눌러도 동작하지 않는 버튼, 숫자/데이터/가짜 메뉴를 표시하지 않는다.

*위 번호는 콘텐츠 중요도/화면 책임의 순서다. H4C-2에서 개선형 B안의 상대 배치(상단 제목·로그아웃 → 안내 문구 → 개인화 섹션·관심사 수정 → 전체 최신 보기 → 첫 TrendCard)를 팀 승인하고 구현했다. 정확한 dp 값·줄바꿈·시각적 최종 동결은 실기기 추가 검증 대상이다.*

### 3.2 기본 화면 요소

| 요소 | 기존 코드와 연결 | 정책 |
| --- | --- | --- |
| App 헤더 | 기존 `Text`/`styles.header` | 홈 안내 문구로 정돈하되 과장된 AI·랭킹 표현 금지 |
| 보조 진입 | 홈 전용 `Pressable` + 기존 `AppNavigator` | 섹션 제목 옆 `관심사 수정`, 첫 카드 위 `전체 최신 보기`; 기존 Route 유지. 409 복구 CTA의 `PrimaryButton`은 보존 |
| 맞춤 목록 | 기존 `FlatList` + `TrendCard` | `data = pages.flatMap(items)`, id Key, 번호 없음 |
| Pagination | `onEndReached`, `ListFooterComponent` | 중복 Cursor 호출 방어, Footer Loading/Retry |
| Pull-to-refresh | `onRefresh`, `refreshing` | 화면 잠금과 Hook `restart()` 재사용 |
| 계정 | 기존 `handleLogout` + 헤더 텍스트형 `Pressable` | 우측 보조 액션으로 배치; 44dp 이상 터치 영역·진행 중 비활성화·실패 Alert 유지 |

### 3.3 스크롤 정책

- 구현된 홈 구조는 **`ScreenContainer` + 단일 `FlatList`**를 유지한다.
- 새 세로 `ScrollView` 안에 같은 방향의 `FlatList`를 중첩하지 않는다.
- 정상 항목 목록에서는 홈 헤더·보조 탐색 액션을 `ListHeaderComponent={renderHomeHeader()}`로 표시한다. Empty/Loading/Error 등에서는 목록 외부에 헤더를 한 번 표시한다.
- `onEndReached`, `refreshing`, Footer 위치 및 터치 영역의 기존 계약은 그대로 유지되어야 한다.
- 정상 Empty는 현재 별도 `EmptyView`로 표현된다. Empty에서의 Pull-to-refresh는 이번 B안의 필수 범위로 가정하지 않는다.

## 4. 사용자 상호작용과 Navigation

| 동작 | 이벤트 | 결과 |
| --- | --- | --- |
| 최초 Main 진입 | `Main` Route 렌더링 | 맞춤 첫 페이지 자동 조회 |
| 관심사 수정 | 정상 상태 CTA | `navigation.navigate('InterestEdit')` |
| 관심사 수정 완료 | 기존 InterestEdit PUT 성공 | `goBack()` → Personalized Query Reset 후 현 관심사 첫 페이지 |
| 전체 최신 | `최신 트렌드 보기` | `navigation.navigate('LatestTrend')` |
| 출처 열기 | 기존 TrendCard 원문 액션 | `openTrendSourceUrl` 기존 정책 |
| 목록 끝 도달 | `onEndReached` | 다음 Cursor로 추가 조회 (조건 충족 시) |
| 추가 페이지 오류 | Footer `다시 시도` | 수동 추가 페이지 재요청 |
| 아래로 당겨 새로고침 | `onRefresh` | `usePersonalizedTrends.restart()` 호출, 기존 Cursor 폐기 |
| 로그아웃 | 기존 버튼 | `logout()` 및 Root 인증 흐름 |
| 북마크 | **현재 없음** | Bookmark 화면/Route 구현·검증 후 별도 연동 |

정상 상태의 CTA와 `INTERESTS_NOT_AVAILABLE` 복구 CTA는 **중복해서 보이지 않아야 한다.** 화면 상태에 따른 하나의 적절한 진입점만 제공한다.

## 5. 상태별 UI와 우선순위

| 상태 | 화면 정책 | 확인할 회귀 |
| --- | --- | --- |
| 최초 요청 Pending | 목록 영역 Loading | 홈/인증 상태를 잘못 표시하지 않음 |
| 성공, 항목 존재 | 번호 없는 TrendCard 목록 | 최신순·카드 원문 링크·카테고리·Source 계약 |
| 성공, 항목 0 | Empty 안내 | 정상 데이터 없음과 관심사 오류 구별, 관심사 수정 가능 |
| 일반 조회 실패 | 사용 가능한 Query Data가 없거나 Cursor 복구 실패 시 Error + Retry. 그 외 일반 재조회 실패에서 캐시가 남으면 기존 캐시 표시 정책 유지 | 정상 CTA로 최신 트렌드/관심사 수정 접근 보존, `409` 도메인 오류는 캐시보다 우선 |
| 추가 페이지 Fetching | 기존 카드 + Footer Loading | 최초 Loading으로 되돌아가지 않음 |
| 추가 페이지 일반 실패 | 기존 카드 + Footer Retry | 자동 반복 재시도 없음 |
| Pull-to-refresh 진행 | 기존 카드 유지 + Refresh Indicator | 연속 이벤트 1회, 완료/실패 시 Indicator 해제 |
| `INVALID_CURSOR` | 1회 첫 페이지 자동 Restart | 옛 Cursor/카드 미노출, 실패 시 오류 복구 |
| `INTERESTS_NOT_INITIALIZED` | Session 재검증/Onboarding 선언적 복구 | 임의 `navigate` 금지, 무한 반복 금지 |
| `INTERESTS_NOT_AVAILABLE` | 이전 카드 차단 + InterestEdit 복구 CTA | 정상 CTA와 중복 표시 금지 |
| 401 / 세션 만료 | 공통 인증 및 캐시 정리 | 이전 사용자 목록 미노출 |
| 로그아웃 실패 | 기존 Alert·상태 복구 | 인증 오류 처리 회귀 금지 |

## 6. 비동기·Cache 안전성

- `restart()`는 진행 중 Query 취소 → 이전 `pages`·`pageParams`/Cursor Chain 초기화 → Cursor 없는 첫 페이지 재조회이다.
- Screen의 `refreshInFlightRef`는 연속 사용자 이벤트를 방어하며, Hook의 `restartPromiseRef`는 실제 재시작 요청 중복을 방어한다.
- 이전 load-more 응답이 취소 신호를 무시하고 늦게 도착하더라도 새 첫 페이지와 Cache를 오염시키지 않아야 한다.
- 관심사 PUT 성공은 Personalized Query 전체 Reset이며 Public 최신 Cache는 영향받지 않는다.
- `INTERESTS_NOT_AVAILABLE` 오류가 있으면 과거 성공 데이터가 남아 있더라도 목록보다 도메인 오류 UI가 우선한다.

## 7. 디자인·접근성

- 공통 `colors`, `spacing`, `typography`와 기존 `LoadingView`, `ErrorView`, `EmptyView`, `TrendCard` 재사용. 홈 보조 탐색은 `Pressable`, 409 복구 CTA는 기존 `PrimaryButton`을 유지한다.
- Design System Snapshot v0.1은 Candidate이므로 **새 시각 토큰이나 Home 배치를 확정값으로 주장하지 않는다**.
- 스크린리더가 섹션 제목·액션·오류 내용을 구분할 수 있도록 `accessibilityRole`, 명확한 버튼 Label을 사용한다.
- Android의 작은 화면·세로 모드에서 주요 진입점이 너무 큰 영역을 차지하지 않도록 검증한다.
- Refresh Indicator·Loading·오류 상태를 색상만으로 표시하지 않는다.

## 8. 변경 단계 (Feature 작업과 이름 변경 분리)

| Phase | 작업 | 범위 제외 |
| --- | --- | --- |
| Home-H0 | 화면 명세와 v1.1 변경 정책 문서 검토·확정 | 코드 변경 |
| Home-H1 | `MainPlaceholderScreen` → `PersonalizedMainScreen`; Props/Import/테스트 참조 변경 | 새 기능·UI 배치 변경 |
| Home-H2 | 정상 상태 `InterestEdit` CTA 및 409 복구 중복 방지 | Bookmark, Bottom Tab |
| Home-H3 | 로그인 완료 화면 느낌 제거, 정보 계층·CTA/로그아웃 강조 정돈 | Backend/API/Query 변경 |
| Home-H4 | 전체 테스트·TS·실기기 및 문서 정합성 | 범위 밖의 추천 엔진 확장 |
| Follow-up | 실제 Bookmark Feature가 구현되면 Home 진입점 연결 | 구현 전 가짜 동작 |

## 9. Acceptance Criteria

### 9.1 자동 테스트

- AC-01: `AppNavigator`의 `Main`은 새 `PersonalizedMainScreen`을 렌더링하며 `RootNavigator` 조건은 그대로다.
- AC-02: Main의 정상 목록·Empty·일반 오류에서 `InterestEdit` 진입이 가능하고, 기존 `LatestTrend` 이동이 유지된다. 일반 재조회 실패 시 사용 가능한 캐시가 있는 경우와 없는 경우를 구분한다.
- AC-03: `INTERESTS_NOT_AVAILABLE` 복구 CTA가 보이며, 동일 액션이 중복 표시되지 않고 오래된 데이터가 가려진다.
- AC-04: `INTERESTS_NOT_INITIALIZED`는 기존 Session 재검증 및 선언적 Onboarding 복구를 따른다.
- AC-05: Pagination의 Cursor, Footer Loading/Retry 및 `INVALID_CURSOR` 1회 복구가 유지된다.
- AC-06: Pull-to-refresh는 기존 페이지를 잠시 표시하면서 첫 페이지부터 재조회한다. 늦은 과거 응답이 화면/Cache를 덮어쓰지 않는다.
- AC-07: 관심사 PUT 성공 뒤 이전 Personalized Cursor가 제거되고, Public 최신 Query가 보존된다.
- AC-08: 로그아웃·401·계정 전환 시 이전 사용자 카드가 노출되지 않는다.
- AC-09: 북마크 미구현 단계에는 동작하지 않는 CTA/추측 Route가 없다.
- AC-10: 전체 Frontend 회귀·TypeScript·변경 Diff를 검증한다.

### 9.2 실기기/Backend 연계 (부분 확인 / 미완료)

- Android에서 개선형 B안의 헤더·섹션·보조 버튼 및 TrendCard 노출을 사용자 스크린샷으로 확인했다.
- 관심사 PUT 성공 후 홈 복귀·개인화 첫 페이지 자동 GET은 이전 H4B 검증에서 확인했다.
- 사용자 제공 Backend 로그에 `GET /api/trends/personalized?limit=20` 200이 여러 차례 기록됐고 `cursor` 파라미터는 보이지 않았다. 다만 각 GET이 어떤 UI 이벤트에 대응하는지 모두 추적한 것은 아니므로 Pull-to-refresh 단독 요청 횟수·중복 방지는 화면 테스트 및 별도 검증 범위를 구분한다.
- 사용자는 Android에서 주요 버튼·화면 동작에 이상이 없다고 보고했다. 360~412dp 여러 크기, 긴 사용자명/글자 확대, 전체 409·401/재로그인·Pagination 오류 복구, MariaDB EXPLAIN 등의 모든 Acceptance를 수행했다는 의미는 아니다.
- 기존 v1.0/v1.1에 남은 Backend·DB·실기기 검증 항목은 별도 추적한다.

## 10. 후속 UI 검토 및 확정되지 않은 디자인 세부사항

- H4C-2에서 개인화 섹션 우선, 헤더 우측 로그아웃, 제목 옆 관심사 수정, 첫 카드 위 전체 최신 보기의 상대 배치를 승인·구현했다. 정확한 dp 값·줄바꿈·글자 확대 대응은 후속 시각 검증 대상으로 남긴다.
- Empty 상태에서 수동 새로고침 액션을 추가할지 여부는 추후 UX 개선 항목으로 별도 검토한다.
- 북마크 기능이 실제로 구현되면 홈 진입점 위치와 표시 정책을 별도 작업으로 확정한다.

**현재 확정된 것:** B안 제품 역할, 개인화 목록 우선, 개선형 B안의 상대 배치, 실제 InterestEdit/LatestTrend 연결, 로그아웃 강조 하향, 단일 FlatList 스크롤 구조, 북마크 구현 뒤 연결, Bottom Tab 보류.

**문서 상태 주의:** 기능별 설계 확정안 v1.1은 FROZEN이며 화면 명세는 `docs/frontend-design/README.md`에 따라 Candidate로 유지한다. H1~H3와 H4C-2의 해당 화면 구현은 진행됐으나, 전체 Home-H4 Acceptance 및 대표 화면의 시각적 동결까지 완료된 것으로 간주하지 않는다.

## 11. Home-H4B 구현 및 Acceptance 추적 (2026-10-15)

### 확인된 사항

- 관심사 PUT 성공 후 Main의 활성 Personalized Query 자동 재조회
- 비활성 Personalized Query Cache 제거
- 기존 Cursor 및 Pagination 상태 폐기
- Public 최신 목록 Cache 보존
- 관련 Hook 테스트 7개 및 전체 Frontend 테스트 150개 PASS
- TypeScript PASS
- Android 실기기 PUT 이후 Personalized GET 자동 발생 확인
- 수동 Refresh 없이 변경된 개인화 목록 표시 확인

### 추가 관찰

전체 테스트 실행 중
`PersonalizedMainCursorRecovery.test.tsx`에서
Jest 5초 Timeout이 1회 발생하였다.

동일 테스트 단독 재실행 3회 PASS,
이후 전체 테스트 재실행 PASS를 확인하였다.

원인은 미확정이며, 재발 시 비동기 테스트 안정성을
별도 점검한다. 기능 결함으로 단정하지 않는다.

### H4B 당시 후속 계획

- 홈 상단 영역 및 빠른 탐색 CTA의 시각적 밀도 개선 → H4C-1/2에서 반영
- 중복 여백 및 버튼 배치 재검토 → H4C-1/2에서 반영
- 기타 Home-H4 Acceptance 미검증 항목 별도 추적 → 계속 유효

시각 배치는 계속 Candidate 상태로 유지한다.

## 12. Home-H4C-2 — 개선형 B안 화면 구현·검증 추적 (2026-10-22 정합성 점검)

### 12.1 승인 기준 및 참조

- 팀 승인 설계: `Trend_Leader_H4C-2_개선형_B안_화면_설계_승인안.md` (2026-10-16 승인 내용)
- 구현 커밋: `0098ab331d8227bf363ed891245d3d8eb5266445` (`[feat/home] 개인화 홈 콘텐츠 우선 레이아웃 정돈`)
- 변경 코드: `frontend/src/app/screens/PersonalizedMainScreen.tsx`, `frontend/__test__/trend/PersonalizedMainScreen.test.tsx` — 정확히 2개 파일

### 12.2 실제 코드에서 확인한 화면 정책

1. `home-top-bar`: 앱 제목과 텍스트형 로그아웃을 같은 영역에 배치하며 기존 로그아웃 로직·비활성화·Busy State를 유지한다.
2. `home-personalized-section`: 개인화 제목과 `관심사 수정` 보조 액션을 함께 표시하고 `전체 최신 보기 ↗`를 첫 카드 위에 제공한다.
3. 실제 시각 문구는 `관심사 수정` / `전체 최신 보기 ↗`이며 접근성 이름은 기존 테스트·기능 계약에 맞춰 `관심사 수정하기` / `최신 트렌드 보기`를 유지한다.
4. 정상 Empty에서도 개인화 섹션 제목 및 관심사 수정 진입점이 나타난다. 최초 Loading과 409 도메인 오류에서는 일반 관심사 수정 진입점을 숨겨 기존 상태·복구 동작과 충돌하지 않게 한다.
5. 정상 항목 목록은 기존 `FlatList`·`TrendCard`·Cursor·Refresh/Retry 구조를 유지한다. 신규 Bottom Tab, 설정 메뉴, 미구현 북마크/검색 기능을 추가하지 않는다.
6. 개인화 목록의 API/Query 및 인증·세션 계약은 이번 UI 커밋에서 수정하지 않았다.

### 12.3 Acceptance 증거와 제한

| 검증 | 결과 및 근거 | 상태 |
| --- | --- | --- |
| H4C-2A RED | 새 레이아웃 testID 미존재, Empty 제목 미표시로 2건 의도된 실패 | 사용자 Jest 로그 확인 |
| H4C-2B GREEN | 최초 24/25 PASS 후 로그아웃 배경색의 이전 기대값을 수정했고, 이후 사용자 전체 npm 검사 실행·정상 보고 | 사용자 결과 보고; CI 별도 확인하지 않음 |
| Diff 및 원격 반영 | 2개 파일 커밋 확인, 해당 파일에 한해 JSX·스타일·테스트 변경; 데이터/Query 코드 변경 없음 | GitHub Diff 확인 |
| Android 시각 | 개인화 섹션·보조 이동 링크·TrendCard 노출, 사용자 디자인 승인 | 스크린샷 및 사용자 확인 |
| 새로고침 연계 | 개인화 첫 페이지 형태의 GET 200 로그(`cursor` 없음) 여러 건 관찰 | 연계 정황 확인; 요청별 원인 전수 추적 아님 |
| 추가 실기기 경계 | 360~412dp 다양한 장치, 텍스트 배율 확대·긴 이름·모든 예외 상태·동시성·전체 서버/DB 검증 | 미완료·후속 |

### 12.4 후속 정리

- `renderHomeHeader()` 들여쓰기, 중복 주석 같은 비기능적 코드 정돈은 필요하면 별도의 최소 변경으로 처리한다.
- 브랜치 최신 HEAD와 실제 로컬 테스트 로그의 개수/성공 내역은 후속 PR 전 다시 확인한다.
- Design System 및 화면 배치의 최종 Frozen은 모든 대표 화면·접근성 검증 및 팀 결정 후 별도로 수행한다.

## 13. Home-H4 — 최종 Acceptance 검증 체크포인트 (2026-10-23)

> 검토 브랜치: `feat-personalized-trend-list`
> 검증 결과 정리 기준 코드 HEAD: `eff3ced5a21ec583cca66f230f44d44a89b11b93` (본 문서 커밋 이전)
> 증거 구분: **GitHub에서 확인한 코드·Diff**, **사용자가 공유한 로컬 실행 로그**, **사용자 실기기 확인 보고**를 구분한다.
> 범위: 개인화 홈 H4 및 맞춤 트렌드 목록 조회의 PR 전 검증 기록. v1.0/v1.1의 FROZEN 기능 계약은 변경하지 않는다.

### 13.1 자동 검증 및 MariaDB 증거

| 검증 | 실제 근거 | 판정 |
| --- | --- | --- |
| Frontend 전체 Jest | `npm test -- --runInBand` 실행 및 정상 결과를 사용자가 보고함. H4C-2 화면 테스트는 신규 구조·정상 Empty 상태를 포함함 | 사용자 PASS 보고. 전체 개수·CI 결과는 별도 독립 확인하지 않음 |
| Frontend TypeScript | `npm run typecheck` 정상 실행을 사용자가 보고함 | 사용자 PASS 보고 |
| Frontend 변경 Diff | H4C-2 코드 커밋 `0098ab331d8227bf363ed891245d3d8eb5266445`의 변경 파일은 화면·화면 테스트 2개이며, API/Query/Auth 로직을 변경하지 않았음을 GitHub Diff에서 확인함 | 코드 범위 확인 |
| Backend 전체 회귀 | `python -m pytest -v -ra` — **347 passed**, 사용자 최종 실행 보고 | PASS. 스킵 유무·세부 로그를 독립적으로 재실행하지 않음 |
| Backend Ruff | `python -m ruff check .` — 사용자 정상 실행 보고 | PASS |
| MariaDB 통합 조회·Cursor·409 | `tests/api/test_personalized_trend_router_integration.py` — 사용자 제공 테스트 출력에서 **16개 PASSED** | PASS |
| MariaDB EXPLAIN/ANALYZE | `tests/repositories/test_personalized_trend_explain.py` — Small/Wide Scope **2개 PASSED** 및 실행 계획 출력 확인 | 테스트 환경에서 PASS |
| 최신 DB Migration | 통합 테스트 실행 시 Alembic `2f29fa23597c` → `7e9d740c5df1` → `a4d7c9e21f3b` 적용 로그 확인 | 해당 테스트 DB에서 Migration 실행 확인 |

MariaDB 실행 계획 관찰:

- Small Scope(1 Child): `ix_trend_category_map_category_id_trend_id` 인덱스 이용. `Using temporary; Using filesort` 발생. ANALYZE 총 쿼리 시간 관측치 약 **0.388ms**.
- Wide Scope(24 Children): `ix_trends_status_last_collected_at` 인덱스 이용 및 Trend–Category 매핑 Join. ANALYZE 총 쿼리 시간 관측치 약 **0.073ms**.
- 위 시간은 **테스트 데이터·실행 환경의 단일 관측치**이며, 실제 서비스 규모의 성능 보장이나 Filesort의 보편적인 무해성 판정을 의미하지 않는다.
- 범위별 실행 계획이 서로 다른 것은 확인됐으나, 대량 데이터·선택도 변화·운영 인덱스 효과는 별도 Performance Observation으로 유지한다.

통합 테스트 18개 결과와 전체 Backend 347개 결과는 **서로 다른 실행의 증거**다. 전체 개수 산정 시 임의로 더하지 않는다.

### 13.2 Android 실기기 확인 및 해석 경계

| 시나리오 | 관찰·보고 | 판정 |
| --- | --- | --- |
| 개인화 홈·개선형 B안 | Android 스크린샷에서 홈 헤더·관심사 수정·전체 최신 보기·개인화 TrendCard 확인. 사용자가 배치 승인 및 주요 기능 정상 보고 | 해당 실기기 조건에서 PASS |
| 관심사 수정 후 자동 갱신 | H4B에서 PUT 200 후 Cursor 없는 Personalized GET 200과 변경된 개인화 목록의 자동 표시를 확인 | 이전 실기기 Acceptance PASS |
| 사용자 A 로그아웃 → B 로그인 | 사용자가 계정 전환 정상, A의 이전 개인화 카드가 B 화면에 남지 않음 확인 | 해당 실기기 시나리오 PASS |
| 긴 사용자명 | 테스트 중 DB에서 사용자명을 변경해 화면 배치를 확인했고 문제가 없었다고 사용자가 보고 | 검증한 사용자명·기기 조건에서 PASS |
| Pull-to-refresh | 기존 Frontend 테스트가 `restart()` 호출·연속 이벤트 중복 차단·기존 카드 유지를 검증. 실제 Backend 로그에는 Cursor 없는 Personalized GET 200 여러 건 기록 | 자동 계약 PASS; 실기기 GET의 정확한 이벤트별 인과·요청 횟수는 미확인 |
| 목록 중간 스와이프 | 중간 위치에서 아래로 당겨도 Refresh가 실행되지 않는다는 관찰. 기존 `FlatList` 최상단 Pull-to-refresh UX의 기대 동작과 구분 | 단독 결함 증거 아님. 최상단 제스처 검증 기준 유지 |

실기기 접근성·예외 상태는 이번 사용자 보고만으로 전수 검증되었다고 단정하지 않는다.

### 13.3 미검증·후속 Acceptance

- 화면 너비 **360~412dp**의 여러 조건, 시스템 글자 확대·최대 규모 긴 사용자명에서 제목/버튼 겹침과 실제 44×44dp 터치 영역 추가 확인.
- 실제 서버 응답을 사용한 `INTERESTS_NOT_INITIALIZED`, `INTERESTS_NOT_AVAILABLE`, 401 세션 만료·온보딩 복구, Footer Retry 등 일부 예외 시나리오의 추가 실기기 확인. 해당 자동 테스트 통과와 실제 기기 검증은 구분한다.
- 운영 규모에 준하는 MariaDB 데이터·선택도 기반 성능 분석 및 인덱스 검증. 이번 EXPLAIN/ANALYZE는 통합 테스트 데이터에 한정한다.
- PR 단계에서 `dev` 대비 **Backend·Frontend·문서를 포함한 전체 변경 범위**, 의도하지 않은 파일·Secret 포함 여부, 실제 CI 및 코드리뷰 결과 확인.
- 기존 문서의 `renderHomeHeader()` 들여쓰기 및 중복 주석 같은 비기능적 정리는 선택적 후속 작업이며, 현재 확인된 기능 결함으로 분류하지 않는다.

### 13.4 H4 체크포인트 판정

- **구현:** 개선형 B안과 핵심 개인화 화면·Navigation·상태 처리가 현재 코드에 반영됨.
- **자동 검증:** 사용자가 보고한 Frontend 전체 Jest/TypeScript, Backend 347 passed/Ruff, 공유된 MariaDB 통합 16개 및 EXPLAIN 2개 PASS를 확인 기록함. GitHub CI의 독립 실행 증거는 없음.
- **실제 동작:** 개인화 홈, 관심사 변경 후 첫 페이지 갱신, 사용자 전환에 따른 화면 격리, 시험된 긴 사용자명과 기본 탐색을 해당 기기 조건에서 확인.
- **PR:** 검토·제출 준비 단계로 진행 가능. 단, 전체 기능의 모든 실기기 예외/접근성 Acceptance 완료, 운영 성능 검증 완료 또는 최종 Merge 승인을 의미하지 않는다.
- **문서 상태:** Screen Specification **v0.2 Candidate 유지**. 최신 기능별 v1.1 FROZEN 및 상위 계약 v1.0은 그대로 보존하며, 최종 시각 Frozen과 PR Merge 판정은 별도 결정한다.

