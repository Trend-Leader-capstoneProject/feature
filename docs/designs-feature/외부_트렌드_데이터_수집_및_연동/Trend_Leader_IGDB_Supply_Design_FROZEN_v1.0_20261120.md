# Trend Leader — IGDB 자동 공급 설계 확정안 v1.0

> 2026-11-20 KST | Phase 4-C | 기준 dev: 52fe4a851a53c3d91654f859a6934df2c315c6a6
> 사용자 결정: IGDB-01~12 설계 제안 승인(현재 채팅). 기술 설계의 승인 범위만 확정한다. IGDB 실제 운영 승인(G6), 보존/갱신 정책, 배포와 DB 쓰기는 미승인/HOLD.
> 상위 계약: Trend_Leader_AP3C_Automatic_Publication_Design_FROZEN_v1.0_20261119.md §7. 기존 Godot 운영·Journal·DB/API 계약을 보존한다. 새로운 인증 및 복수 공급원 상태 세부안은 아래 제안과 검증 조건에 따라 구현 전 위험을 해소한다.

## 1. 문제 및 실측

출시 사실 이벤트 공급(Godot)에 게임 관심도 신호를 추가한다. 서비스는 순위 서비스나 게임 이용/판매 플랫폼이 아니라 원출처 연결형 큐레이션이다. IGDB Visits는 IGDB 페이지 방문 기반 인기 지표이며 24시간 갱신, 한국 전체 검색량/실제 방문자 수/동시 접속자 수가 아니다. Wikimedia는 기존 실측에서 주력 부적합, 보조 후보로 유지. SearchApi는 공급 인프라 이용 검토와 Google 원천 데이터 권리를 구분하며 별도 HOLD.

사용자 PowerShell 라이브 조회(2026-11-20): 인증 및 popularity_types, popularity_primitives, games 성공. Visits type 1, external source 121/IGDB. 상위 20 distinct Game ID, 동일 calculated_at=1795134640(2026-11-20 09:30:40 KST). Main Game 17, Remake/Port/Expansion 각 1. 추가 등급 응답은 첨부 끝이 잘려 18개 완전한 객체만 확인: 등급 12, 미제공 6, 미확인 2. 제안 필터로 Free Fire(5위, 87622, GRAC 15+, 모바일), League of Legends(17위, 115, GRAC 12+, PC), Minecraft: Java Edition(20위, 121, GRAC 12+, PC) 후보. 실제 운영 승인/등록 아님. 사용자 인증 로그 및 Client ID/Secret/Token 원문을 저장소에 넣지 않는다.

## 2. 승인된 정책

| ID | 계약 |
|---|---|
| IGDB-01 | IGDB Visits만. Steam/Twitch 외부 지표 제외. |
| IGDB-02 | popularity_primitives 상위 최대 20건; 원래 관측 순위 보존, 필터 후 재순위 금지. |
| IGDB-03 | 전체 글로벌 Cycle 최대 후보/등록 1건. |
| IGDB-04 | calculated_at 48시간 이내, 미래 시각 금지. Preview 관측 10분 이내 유지. |
| IGDB-05 | GRAC 전체/12+/15+ 명시 확인, GRAC 19+ 또는 다른 기관 성인 등급, Erotic 테마 제외. 미확인/충돌 보류. |
| IGDB-06 | Main Game만 초기 적격, Remake/Port/Expansion/불명 유형 제외. |
| IGDB-07 | 플랫폼 ID 명시 매핑, 단일 세부분류만 is_primary=true. 복수/미등록 플랫폼 보류. |
| IGDB-08 | IGDB Game ID 기준 중복 방지, 날짜별 카드 중복 금지. |
| IGDB-09 | 게임명, 출처 명시, 관측 순위, 지표 기준일, IGDB 상세 링크. |
| IGDB-10 | 이미지/원문 소개/AI 전달 제외, AI API 0. |
| IGDB-11 | 실제 저장·공개·보존·갱신·삭제 조건 확인 전 운영 HOLD. 최초 INSERT/SKIP 모델은 권리 양립 시에만 채택. |
| IGDB-12 | 공통 Writer/Journal/운영 프로필/OS Scheduler 및 기존 API/DB 재사용. |

GRAC 정책은 현재 연령별 노출 제어 없는 서비스의 내부 기준으로, 게임 제목/링크 제공에 관한 법률 금지 또는 공식 심의 확인의 대체가 아니다. 일반 Violence/PEGI Sex descriptor만으로 성인 등급을 추론하지 않는다. 명시적 Erotic 및 성인 등급은 우선 제외, 알려지지 않은 등급/기관 매핑은 fail closed. 등급 정보가 있어도 테마 등 필수 정책 근거가 누락되면 HOLD. 국내 등급 ID·표기는 실제 응답과 공식 메타데이터로 고정하고 추측하지 않는다.

## 3. 수집 및 검증 책임

- 신규 모듈 후보 igdb_client.py (OAuth/HTTP), igdb_adapter.py (파싱/순수 적격 정책/표시 투영), 기존 supply_adapter.py (고정 registry, 순환 import 방지). 새 라이브러리 없이 기존 표준 HTTP 경로 우선.
- 고정 POST endpoints: id.twitch.tv/oauth2/token, api.igdb.com/v4/popularity_types, popularity_primitives, games; token 검증은 id.twitch.tv/oauth2/validate. 인증 및 고정 호스트 TLS, redirect 금지, timeout/응답 크기 제한, 민감값/전체 원문 stdout 금지. Token은 요청 본문/Authorization 헤더에서만 취급. IGDB 공식 4 req/s, 8 동시 제한보다 보수적으로 순차 최소 500ms. 429 Retry-After 및 기존 global cooldown/backoff, 무한 재시도 금지. 실제 요청 수는 Godot의 3회 계약과 구분; IGDB 각 주체 최대 정상 메타 요청 3회 + OAuth 1회/검증 1회, 401 재발급 최대 1회는 별도 제한, 장애 시 조기 HOLD.
- 각 독립 주체가 Visits type ID 1/name Visits/source 121/name IGDB 일치를 확인. 상위 20 popularity rows의 game_id, value, popularity_type, external_popularity_source, calculated_at를 확인. 고유 ID, 유한 양수, UTC 시각, 내림차순, 동일 산출 시점 검증. 값 동률은 초기 보수적으로 순위 불확실 후보 보류(임의 순위 주장 금지). games는 숫자 ID 목록만 요청; writer는 top20을 독립 재조회하고 선택 Game ID의 메타데이터 재조회. Collector의 순위/등급/URL/문구를 신뢰하지 않고 재구성, 산출 시점 또는 필수 증거가 바뀌면 HOLD, 재시도 반복 금지.
- 게임 필드: id,name,url,game_type.type,platforms.id/name,age_ratings.organization/rating_category, themes.id/name; age_ratings.rating_content_descriptions 및 genres는 위험 검토용, DB 저장하지 않음. URLs는 응답에서 확인한 https://www.igdb.com/games/ 경로만(매개변수, 사용자정보, 임의 redirect 금지), 요청 URL로 재사용하지 않는다. 제목 길이 및 정규화 검증(255), 제어문자/이상한 스킴 차단.
- 초기 플랫폼 ID 예시: 6 Windows,3 Linux,14 Mac → PC 게임; 34 Android,39 iOS → 모바일 게임; 169 Xbox Series X|S,167 PS5,48 PS4 등 실측 콘솔 → 콘솔 게임. 전체 매핑은 실제 확인된 명시 allowlist만. platform_type=Operating_system만으로 분류 금지. VR/브라우저/visionOS 등 미정 플랫폼 포함 시 HOLD. 다중 카테고리를 임의로 하나 선택하지 않는다.

## 4. 공통 저장 계약 확장(설계)

- source_id 제안 igdb:visits, scope IGDB_VISITS_FACTS_LINK_V1. candidate_identity/external_id 제안 igdb-game:<positive integer>, ETC, SHA-256("ETC:"+external_id). 기존 ID 충돌/normalized_title 충돌/URL 불일치/HIDDEN은 기존 정책대로 SKIP 또는 HOLD. 전체 unique와 source 검사, category parent/child lock, Journal claim/commit/finish 재사용. 권리 승인 전 실제 DB 연결/쓰기 경로를 활성화하지 않는다.
- 제목은 IGDB game name 그대로, summary 예: "IGDB Visits 2026-11-20 관측 상위 5위 (IGDB 게임 페이지 방문 기반 지표)." 기준 날짜/시각은 UTC 기준 또는 명시된 KST로 일관 표시. 현재 순위/국내 순위/실제 방문자 수로 과장 금지. source_title/thumbnail_url NULL. 값/등급/전체 목록 비저장. 운영 권리 확정 전 이 형태는 표시 예시일 뿐.
- ContentSnapshot은 공개 이벤트와 관심도 관측을 구분해야 한다. Godot source_published_at을 인위적으로 calculated_at으로 대체하지 않는다. 신규 관측 필드/타입 또는 별도 source-specific freshness contract 도입 후보; 기존 Godot 7일/Preview 10분 및 기존 digest/Journal 식별자를 그대로 유지하는 하위호환 테스트 필수. IGDB 48시간은 독립 verify 및 commit 직전 적용; 항상 승인된 adapter/source에 바인딩하고 caller 임의 freshness 지정 금지.
- 현재 Writer의 SKIP_EXISTING_RELEASE 결과는 기존 계약/상태 전이를 위해 보존하고 IGDB에서도 동일 ID 무변경으로 해석 가능. 새 명칭 확대는 후순위. 현재 순위 갱신/재노출은 승인하지 않음.

### 4.1 SNAP-01~10 공통 저장 계약 확정 (2026-11-21 승인)

- SNAP-01~03: 기존 `ContentSnapshot`의 필드 순서·직렬화·해시는 변경하지 않는다. 새로운 `PopularitySnapshot`은 `calculated_at_utc`, 관측 순위와 Visits 지표 ID를 별도로 가진다. `PersistableSnapshot`은 타입 계약이지 새로운 DB 테이블이 아니다.
- SNAP-04~05: 고정된 소스 ID와 Concrete Snapshot Type 및 보호된 운영 프로필 Scope가 정확히 일치해야 한다. Godot은 7일, IGDB는 48시간; 공통 Preview 10분. 후보의 임의 파라미터나 Snapshot이 자체 권한을 지정하지 않는다. Commit 직전에도 같은 검사 적용.
- SNAP-06~09: 공통 Writer/Journal 및 `AUTO_V1` 유지. IGDB의 동일 Game ID는 SKIP하며 저장 URL이 달라지면 UPDATE 대신 HOLD. 기존 DB/API/Schema/권한 변경 없음. 이벤트 타임스탬프와 관측 타임스탬프의 의미 혼동 금지.
- SNAP-10: 독립 검증 후 Snapshot으로 투영하는 Bridge는 기술 구현 가능하나 IGDB가 허용된 운영 Registry에 들어가거나 실제 DB DML을 수행하는 것은 별도 권리 검토 및 G6 승인 이후에만 가능.
- 과도한 제약은 목적·근거·부작용을 개별 검증한 뒤 완화할 수 있으나, 기존 운영 Journal 무결성 및 실제 운영 승인 경계를 구현 편의만으로 축소하지 않는다.
- 이번 범위는 Snapshot/Source/Freshness/Writer 계약 및 테스트다. Scheduler 복수 소스 실행, OAuth 영속 Cache, 운영 배포는 포함하지 않는다.

## 5. 인증·복수 공급 실행 세부 권장안(추가 구현 결정)

- 기존 분리 UID를 유지. OAuth Client Credential을 보호된 관리자 발행 파일로 관리, Collector가 Writer DB secret을 절대 읽지 못하도록 한다. 역할별 root 소유 읽기 전용 자격증명과 각 역할의 0700 보호된 token-cache를 고려한다(별도 계정/DB/컨테이너 없음). 토큰은 expires_in과 안전 여유로 재사용, 운영 세션 유효성은 공식 validate 가이드 준수, 401 bounded refresh, token/secret을 envelope/Journal/DB/GitHub/로그에 포함 금지. 캐시 공유/권한/재발행 방식의 실제 운영 설계는 구현 시 검증하고, 사용자 Client Secret은 로컬 관리자만 입력. 활성 프로필 자동 발행 금지.
- 공통 Scheduler에서 승인 source 순환 선택을 권장. 6시간 GLOBAL 최소 간격, Batch 1 유지: 두 source이면 각 정상 약 12시간. 현재 auto_supply_control.py profile.source(None)는 단일 source 전용이며 run_child가 collect --source-id를 전달하지 않는다. 보호된 상태에 순환 위치를 저장하고 실제 실행할 source만 고정 ID로 전달. writer는 profile과 envelope의 source 일치를 독립 확인. 기존 scheduler-state.json pending/not_before/rate_failures 보존, 신규 필드 도입 시 strict 구버전 판독 및 잠금 아래 보존 전환. 이미 등록된 systemd ExecCondition은 load_state를 호출하므로 호환 시험 필요. lock/Journal inode 유지, cooldown 리셋 금지. 기존 pending 또는 불명확 writer 결과는 전체 HOLD.
- 동일 상위 후보 반복은 IGDB 공급 기아를 만들 수 있다. 후보 1건 계약을 바꾸지 않고 마지막 성공/SKIP 후보 ID 이후 적격 후보를 순환 선택하는 보호 cursor를 권장; 순위는 원본 유지. 없어진 ID는 첫 적격부터 시작. cursor는 승인/적격 판단이 아닌 선택 힌트에 한정, writer는 선택 후보의 공식 순위 및 적격 재검증. 에러/불명확 결과에서 임의 진전 금지. 구체적 순환 상태와 no-eligible 정상 SKIP 계약은 구현 전 확인할 세부 설계 항목이며 기존 상태 의미를 완화하지 않는다.
- 운영 중 프로필 변경은 관리자만 기존 control.lock 아래 발행/철회. Godot 활성 승인(2026-11-20 13:50 KST ~ 11-27 13:50 KST)은 이번 설계 범위 변경 없음. IGDB G6 신규 승인 및 권리 심사 전 registry를 통한 실제 실행 차단. 변경 배포 시 Timer 중지/Service 완료 확인 후 기존 권한/Journal/state 보존, 교체 및 재개는 별도 승인. 새로운 unit/계정 불필요.

## 6. 권리 및 운영 Gate

근거 확인 2026-11-20: https://api-docs.igdb.com/ (Getting Started, PopScore, FAQ) 비상업적 API 이용 지원 및 로컬 저장/최종 이용자 제공에 긍정적; FAQ의 보존/귀속 일부는 상업 파트너십 맥락. https://legal.twitch.com/en/legal/developer-agreement/ 원문 접근 시 본문 미확보. https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/ 및 https://dev.twitch.tv/docs/authentication/validate-tokens/ 인증 계약.
확정 필요: 비상업적 캡스톤의 IGDB 자체 Visits 순위/기준일·게임명·링크 장기 DB 저장/공개, refresh/delete/termination 요구, 표시 귀속. 공식 근거로 해소 가능하면 별도 문의 필수 아님; 불명확 시 IGDB에 이 제한 범위만 확인. 요구되는 갱신/삭제가 있다면 INSERT/SKIP 영구 보존은 채택 금지; 별도 보존 설계 결정 필요. 운영 G6 승인과 권리 판단은 독립. 이미지/제3자 지표/AI 전송 범위 확대 금지.

## 7. 테스트 및 종료 기준

1. 실측 입력의 최소 비밀 제거 fixture로 정상 선택/등급 미제공·성인·Erotic·복수 플랫폼·유형·48h 경계·순위 변조·date mismatch·URL 변조·동일 ID·unknown enum 거부. 전체 덤프 재게시 금지.
2. HTTP mocked 인증 만료/401/429/timeout/redirect/invalid payload, 독립 재조회, source binding, no eligible, bounded request budget 및 정보 노출 검사.
3. 공통 회귀: Godot 기존 7일/10분/identity/digest, 기존 운영 Profile V1 및 Journal, Transaction 중복/HIDDEN/lock/rollback, old state/cooldown/pending migration, Timer 조건 호환, 한 Cycle 최대 후보 1.
4. 로컬 기존 테스트 DB만 승인된 대상 사용. Ruff/영향 테스트, 필요 일반 회귀 및 실제 환경 smoke. Godot 운영 중 코드/프로필 변경 없이 실증 로그 수집. 운영 환경에 대한 합성 시험 반복 금지.
5. 실제 권리 확정 및 사용자 G6 별도 승인 이후만 로컬 최초 Game 카드, API/UTF-8/모바일 원문 링크, 반복 SKIP 및 순환 확인. Lightsail 및 다분야 추가는 별도 범위.

단계 종료: 확정된 필터/순수 정책부터 구현 가능, 권리/보존 및 인증·순환 상태의 미확정 메커니즘은 확정 전 실제 운영 경로 활성화 금지. 기존 Godot의 6시간 무인 실행은 아직 실제 로그 미확인. 문서화 병렬 작업의 Current Work 수정은 이번 설계 커밋에서 제외하고 통합 시 증거와 함께 최소 갱신.
