# Trend Leader — IGDB 자동 공급 설계 확정안 v1.0

> 2026-11-20 KST | Phase 4-C | 기준 dev: 52fe4a851a53c3d91654f859a6934df2c315c6a6
> 사용자 결정: IGDB-01~12 설계 승인. 2026-11-21 추가 결정으로 데이터 1건당 최대 30일 보존 상한과 1개월 이내 시연 서버 운영 계획을 채택한다. 보존 상한은 이용 허가가 아니며, 실제 운영 승인(G6), 갱신·만료·삭제 실행 경로, 배포와 DB 쓰기는 아직 미승인/HOLD.
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
- SNAP-10 (Phase 4-F 보완): IGDB Bridge의 **실행 불가능한 기본 Registry Descriptor**만 코드로 등록해 기존 운영 진입점의 통합 회귀를 허용한다. 이 Descriptor는 Query/자격증명이 없어 자체 수집·검증을 거부한다. 실제 Collector/Writer 연결은 보호 프로필에서 승인된 정확한 source_id/scope와 각 역할 전용 보호 자격증명이 있을 때만 생성된다. 이는 권리 판단·G6 발행이나 실제 DB DML의 허가가 아니다.
- 과도한 제약은 목적·근거·부작용을 개별 검증한 뒤 완화할 수 있으나, 기존 운영 Journal 무결성 및 실제 운영 승인 경계를 구현 편의만으로 축소하지 않는다.
- 이번 범위는 Snapshot/Source/Freshness/Writer 계약 및 테스트다. Scheduler 복수 소스 실행, OAuth 영속 Cache, 운영 배포는 포함하지 않는다.

## 5. 인증·복수 공급 실행 세부 권장안(추가 구현 결정)

- 기존 분리 UID를 유지. OAuth Client Credential을 보호된 관리자 발행 파일로 관리, Collector가 Writer DB secret을 절대 읽지 못하도록 한다. 역할별 root 소유 읽기 전용 자격증명과 각 역할의 0700 보호된 token-cache를 고려한다(별도 계정/DB/컨테이너 없음). 토큰은 expires_in과 안전 여유로 재사용, 운영 세션 유효성은 공식 validate 가이드 준수, 401 bounded refresh, token/secret을 envelope/Journal/DB/GitHub/로그에 포함 금지. 캐시 공유/권한/재발행 방식의 실제 운영 설계는 구현 시 검증하고, 사용자 Client Secret은 로컬 관리자만 입력. 활성 프로필 자동 발행 금지.
- 공통 Scheduler에서 승인 source 순환 선택을 권장. 6시간 GLOBAL 최소 간격, Batch 1 유지: 두 source이면 각 정상 약 12시간. 현재 auto_supply_control.py profile.source(None)는 단일 source 전용이며 run_child가 collect --source-id를 전달하지 않는다. 보호된 상태에 순환 위치를 저장하고 실제 실행할 source만 고정 ID로 전달. writer는 profile과 envelope의 source 일치를 독립 확인. 기존 scheduler-state.json pending/not_before/rate_failures 보존, 신규 필드 도입 시 strict 구버전 판독 및 잠금 아래 보존 전환. 이미 등록된 systemd ExecCondition은 load_state를 호출하므로 호환 시험 필요. lock/Journal inode 유지, cooldown 리셋 금지. 기존 pending 또는 불명확 writer 결과는 전체 HOLD.
- 동일 상위 후보 반복은 IGDB 공급 기아를 만들 수 있다. 후보 1건 계약을 바꾸지 않고 마지막 성공/SKIP 후보 ID 이후 적격 후보를 순환 선택하는 보호 cursor를 권장; 순위는 원본 유지. 없어진 ID는 첫 적격부터 시작. cursor는 승인/적격 판단이 아닌 선택 힌트에 한정, writer는 선택 후보의 공식 순위 및 적격 재검증. 에러/불명확 결과에서 임의 진전 금지. 구체적 순환 상태와 no-eligible 정상 SKIP 계약은 구현 전 확인할 세부 설계 항목이며 기존 상태 의미를 완화하지 않는다.
- 운영 중 프로필 변경은 관리자만 기존 control.lock 아래 발행/철회. Godot 활성 승인(2026-11-20 13:50 KST ~ 11-27 13:50 KST)은 이번 설계 범위 변경 없음. IGDB G6 신규 승인 및 권리 심사 전 registry를 통한 실제 실행 차단. 변경 배포 시 Timer 중지/Service 완료 확인 후 기존 권한/Journal/state 보존, 교체 및 재개는 별도 승인. 새로운 unit/계정 불필요.

### 5.1 Phase 4-D 공통 Scheduler 복수 공급원 연결 계약 (2026-11-21)

- 사용자 확정 IGDB-12 및 §5 순환 선택 설계를 최소 변경으로 구현한다. 하나의 systemd Timer, 기존 6시간 **전역** Cooldown, 전체 Batch 1, root control/scheduler locks, 기존 Journal inode 및 `AUTO_V1` 그대로 유지한다.
- 승인된 `ApprovedProfile.sources` 목록 순서로 순환한다. 선택은 오직 보호 프로필의 고정 source_id로 수행한다. 재조회 결과 또는 Preview가 임의 공급원을 지정할 수 없고 Collector envelope의 source_id가 선택값과 다르면 실행 결과를 불명확 상태로 유지한다.
- scheduler-state.json의 기존 세 필드 `pending/not_before/rate_failures`는 유지. 복수 공급원 성공 이후에만 `last_completed_source_id`가 선택적으로 기록된다. 이전 세 필드 상태를 읽을 수 있어야 하며, 단일 소스 기존 상태는 세 필드를 그대로 기록한다. 보호된 경로의 기존 파일을 초기화·삭제하지 않는다.
- `COMMITTED`·`SKIP_EXISTING_RELEASE`처럼 Writer의 종료가 확정되거나, IGDB Collector가 정규 `NO_ELIGIBLE_CANDIDATE`를 반환한 경우에만 마지막 완료 소스를 갱신한다. 후자의 경우 Writer는 실행하지 않는다. RATE_LIMITED 및 HOLD는 이전 순환 위치를 유지한다. 결과 불일치·프로세스 예외·미확정 Writer 결과는 `pending=true`를 남겨 무단 재시도를 차단한다.
- 승인 목록이 변경되어 이전 source_id가 사라진 경우 새 목록의 첫 번째 소스로 시작한다. 빈 목록 또는 중복 source_id는 오류 처리한다. 요청 건수는 그대로 단회/Cycle이다. 2개 소스일 때 각각의 실제 재선택 간격은 정상적으로 약 12시간이나, 이는 제공량에 따른 추정이며 가용 시간을 보장하지 않는다.
- IGDB는 Phase 4-F에서 **비실행 기본 Descriptor**로 코드 Registry에 등록된다. 미승인 프로필 및 미설치 역할별 자격증명에서는 실제 호출이 차단된다. 권리 및 G6 승인과 실제 보호 프로필 갱신, 운영 배포·데이터 쓰기는 별도 승인 범위이다. IGDB 후보 없음은 별도 정상 SKIP 결과로 구분하며 가짜 COMMITTED로 처리하지 않는다. 게임별 Cursor는 검증된 Writer 완료 이후에만 전진한다.
- 회귀 게이트: 단일 Godot 자식 프로세스, 성공·중복·RATE_LIMITED·HOLD, legacy/extended 상태 엄격 검증, source mismatch의 pending 보존, Writer exit code 상충 검증, 기존 systemd ExecCondition 호환 확인. Linux 특화 원자적 파일 작업은 Windows skipped와 구분하여 Linux에서 재검증한다.

### 5.2 Phase 4-D 후보 없음 및 IGDB 게임 Cursor 계약 (2026-11-21)

- **후보 없음**: IGDB ReviewAdapter가 Top20 실측·정책 검증 후 반환한 `None`만 Collector의 `{source_id: "igdb:visits", status: "NO_ELIGIBLE_CANDIDATE"}`로 투영한다. 실행 컨트롤러는 정확히 일치한 수집 결과를 `SKIP_NO_CANDIDATE`로 기록하고 Writer/DB/Journal 접근 없이 정상 종료한다. 원천 API 오류·인증 실패·응답 변조·비인가 공급원 또는 Godot의 `None`은 이 경로로 승격하지 않는다.
- **전역 회전**: 후보 없음은 해당 공급원에 처리할 새 후보가 없다는 정상적인 관측 결과이므로, 전역 6시간 Cooldown을 적용하고 `last_completed_source_id`를 갱신해 다음 승인 공급원으로 넘어간다. 단일 Godot의 기존 상태 세 필드는 그대로 유지한다. 후보 없음일 때 IGDB Game Cursor는 변하지 않는다.
- **게임별 Cursor**: `scheduler-state.json`에 선택적 양의 정수 `igdb_last_game_id`를 추가한다. 기존 상태는 그대로 파싱하며 알 수 없는 필드, bool/0/음수/상한 초과 Game ID는 거부한다. IGDB Collector 요청에 한하여 `--after-game-id <integer>`를 전달하며, `IgdbSnapshotBridge.collect_preview(after_game_id=...)`가 해당 값을 ReviewAdapter에 넘긴다. 순위는 IGDB 실측 원래 순위를 유지한다.
- **Cursor 변경의 증거**: Writer가 `COMMITTED` 또는 `SKIP_EXISTING_RELEASE`로 정상 종료했을 때, Controller가 Collector Preview의 `candidate_identity`와 Writer 독립 검증의 `candidate_identity`가 정확히 일치하는지 검사한다. `igdb-game:<positive integer>`만 상태에 반영한다. 응답 불일치·Writer 불명확 종료에서는 `pending=true`가 남고 Cursor는 전진하지 않는다.
- **원자성 및 보존**: Source Cursor 및 Game Cursor는 기존 `pending/not_before/rate_failures`와 동일 원자적 상태 파일 갱신으로 기록한다. Writer가 DB에 반영됐으나 상태 기록 전 장애가 나면 기존 pending 조사 HOLD를 유지한다. 기존 Journal·DB·systemd Timer·보호된 승인 프로필은 이 작업에서 변경하지 않는다.
- **운영 범위**: 새로운 프로세스 간 Cache, 별도 DB 테이블, 새로운 API, 디스크 초기화는 도입하지 않는다. Phase 4-F의 비실행 Registry Descriptor는 **실제 운영 프로필 승인·배포와 구별**한다. 권리·G6 운영 승인 HOLD는 유지하며, 실제 활성화 전 권리/보존 요건과 운영 Linux 회귀 및 역할별 자격증명 배포 경계를 별도로 검증한다.

### 5.3 Phase 4-F 비실행 운영 Adapter 연결 (2026-11-21)

- **코드와 승인 분리**: `supply_adapter.ADAPTERS["igdb:visits"]`는 Query가 없는 `IgdbOperationalAdapter` Descriptor이며 직접 호출은 `IGDB_CREDENTIALS_UNAVAILABLE`로 차단된다. 운영 `parse_profile`은 여전히 enabled, 승인 source/scope/rights, 실제 대상, G5/G6 근거와 시간 경계를 검증한다. **운영 approval.json에 IGDB 추가 또는 자동 활성화는 이번 코드 작업에 포함하지 않는다.**
- **Collector / Writer 보안**: 기존 Linux `CONTROL` 경로에 관리자가 별도 발행할 `igdb-collect-credentials.json`, `igdb-write-credentials.json`을 각각 root 소유, 해당 역할 전용 그룹, `0640`으로 제한한다. JSON은 정확히 `client_id`와 `client_secret`만 포함한다. 운영 코드는 파일을 생성/수정하거나 내용·토큰을 출력/Journal/DB/환경변수로 전달하지 않는다. 그룹·모드·스키마 검증 실패 시 HOLD. 기존 Writer DB Secret은 Collector 접근 불가를 유지한다.
- **독립 검증**: Collector는 한 Cycle의 독립 `IgdbClient`로 후보 Preview를 생성하고, Writer는 자기 역할의 별도 Client로 IGDB 원천을 다시 조회·검증한 `PopularitySnapshot`만 공통 Writer에 전달한다. 후보 없음은 기존 `SKIP_NO_CANDIDATE` 경로, 변조·상태 불일치·오류는 HOLD. 기존 단일 Godot Adapter의 호출·공통 6시간 주기·Journal·DB/API 계약은 그대로 유지한다.
- **남은 운영 Gate**: 이번 통합 코드와 모의 검증은 실데이터 저장 권한을 부여하지 않는다. IGDB 최소 필드 권리·30일 만료 집행·Linux 역할별 파일 접근 및 systemd 회귀·G6 기간 한정 최초 승인이 확보되기 전에는 실제 DB 쓰기/스케줄러 활성화 금지. 승인 유효기간 중 개별 6시간 Cycle마다 사용자 재승인은 요구하지 않는다.

## 6. 권리 및 운영 Gate

근거 확인 2026-11-20: https://api-docs.igdb.com/ (Getting Started, PopScore, FAQ) 비상업적 API 이용 지원 및 로컬 저장/최종 이용자 제공에 긍정적; FAQ의 보존/귀속 일부는 상업 파트너십 맥락. https://legal.twitch.com/en/legal/developer-agreement/ 원문 접근 시 본문 미확보. https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/ 및 https://dev.twitch.tv/docs/authentication/validate-tokens/ 인증 계약.
확정 필요: 비상업적 캡스톤의 IGDB 자체 Visits 순위/기준일·게임명·링크 장기 DB 저장/공개, refresh/delete/termination 요구, 표시 귀속. 공식 근거로 해소 가능하면 별도 문의 필수 아님; 불명확 시 IGDB에 이 제한 범위만 확인. 요구되는 갱신/삭제가 있다면 INSERT/SKIP 영구 보존은 채택 금지; 별도 보존 설계 결정 필요. 운영 G6 승인과 권리 판단은 독립. 이미지/제3자 지표/AI 전송 범위 확대 금지.

### 6.1 IGDB 데이터 이용 권리 및 최대 30일 보유 정책 사전검토 (2026-11-21)

**상태: 프로젝트 보존 상한은 최대 30일로 확정. 외부 이용 권리·만료 집행·G6 승인과 실제 운영 저장·노출·삭제는 별개로 미완료.**

- 공식 IGDB API FAQ(https://api-docs.igdb.com/): 비상업적 이용은 Twitch Developer Services Agreement 적용 대상. FAQ Business 섹션은 로컬 저장 및 최종 사용자 제공을 긍정하고, 제휴 종료 후 보유도 언급한다. 이 안내가 비상업 캡스톤의 Visits 지표, 순위·기준일·게임명·URL의 장기 공개·보존까지 포괄하는지는 확인이 필요하다.
- Twitch Developer Services Agreement(https://legal.twitch.com/en/legal/developer-agreement/, 2024-12-04 게시판 기준): Program Materials/Twitch Content의 무허가 저장은 최대 24시간 캐싱 예외, 원천 자료 재배포 제한, 삭제·변경 반영 요구가 있다. IGDB FAQ의 구체적 저장 안내와 어떤 조항이 우선하거나 범위가 다른지 확정할 수 없다. **30일 자체 삭제 정책을 라이선스로 간주하지 않는다.**
- 사용자 결정(2026-11-21): 앱은 실제 출시 목적이 아니며 서버 운영은 1개월을 넘기지 않을 계획이다. IGDB 원천 데이터는 **개별 수집 시점부터 최대 30일**을 프로젝트 보존 상한으로 확정하고, 시연 종료·이용 종료·정정/삭제 요구 또는 공식 조건의 더 짧은 기간이 있으면 그 조건을 우선한다. 서버 중단만으로 DB·백업·캐시 데이터가 삭제되는 것은 아니다. 별도 24시간 규정이 실제 IGDB 자료에 적용되면 30일을 우선할 수 없다.
- 별도 메일 문의 전제는 최소화하지만, 위 상충을 해소하지 못하면 partner@igdb.com(공식 안내 주소)에 다음 사실을 좁혀 확인한다: 비상업적 한국 대학 캡스톤, 자체 작성 게임명/관측 순위·날짜·공식 링크만 표시, 이미지/원문 설명/외부 인기 소스 사용 안 함, 최대 30일 보유 후 비노출·삭제, 앱에서 IGDB 출처 고정 표시. *24시간 캐싱 제한 및 재배포 조항과의 관계*, 변경/삭제 통지 시 조치, 보존/종료 조건을 질의한다.
- **구현된 격리 사전검토**: `igdb_retention_policy.py`는 `platform=ETC`, `external_id=igdb-game:<ID>`, 출처 해시 및 공식 IGDB URL의 일치를 확인하고 UTC `collected_at` 기준 마감 시각만 계산한다. 프로젝트 상한은 30일이며 입력된 더 짧은 제한(예: 24시간), 위조 출처/시간 이상을 검증한다. **실제 만료 비노출·삭제 집행은 아직 없음**. 운영 Registry·DB 조회·DELETE·UPDATE·systemd 연결은 없다.
- **실제 삭제 설계 미확정**: `trend_sources`는 `trends` 자식, 다른 FK(북마크, 순위, AI 분석 등)가 `ON DELETE CASCADE`를 가질 수 있다. source 단위 제거와 Trend 부모 제거를 동일하게 취급하면 사용자 데이터가 의도치 않게 삭제된다. 전체 연관 출처·북마크·Journal/중복 기록, 백업, API 응답 캐시 및 시연 자료를 확인한 후 관리자 승인과 별도 권한으로 삭제·비노출 정책을 확정한다. 주기적 작업만으로 마감 이후 추가 보관이 생기지 않도록 공개 조회의 만료 가드 또는 선제적인 삭제 일정도 필요하다.
- **운영 전 Gate**: (1) 자료 저장·표시 권리 확인, (2) 권리 조건에 맞는 보존 상한·출처 표시·즉시 정정/삭제 절차, (3) 최소 권한/삭제 경계 및 의존 FK 검증, (4) 별도 사용자 G6 최초 활성화 승인. 확인 전 IGDB 운영 공급은 HOLD. 현재 파일·코드 변경만으로 승인이나 법적 보증을 주장하지 않는다.
- **G6 비병목 원칙(2026-11-21)**: 설계·구현·자동 테스트·기능 브랜치/PR 준비는 G6 승인과 독립적으로 진행한다. 기존 `ApprovedProfile`의 소스·대상·승인 참조 및 `approved_at <= now < valid_until`을 만족한 **기간 한정 최초 승인 1회**로 해당 기간의 6시간 Scheduler Cycle을 무인 실행한다. 매 Cycle의 시간/권한 재검증은 유지하지만 **매 Cycle 사용자 재승인은 요구하지 않는다**. 만료·철회·승인되지 않은 소스 추가·운영 대상 변경·원자성 미확정 등에서는 기존 HOLD 후 변경 승인한다. G6 승인 자동 발행/연장이나 미승인 DB 쓰기는 금지한다.

### 6.1.1 Phase 4-F IGDB 조회 단계 만료 방어 (2026-11-21)

- **기존 API만 사용**: `TrendRepository.find_page()` 공통 조회에서 `platform=ETC` 및 `external_id`의 `igdb-game:` 접두사로 식별된 IGDB 출처가 **UTC `collected_at <= now - 30일`**이면 연결된 Trend를 공개·맞춤 목록에서 제외한다. 제외 조건은 Cursor/limit보다 먼저 적용한다. `find_latest_sources_by_trend_ids()`도 만료된 IGDB Source를 반환하지 않는다. 조회 시각은 UTC로 평가하며 기존 DB의 UTC-naive DATETIME 계약을 사용한다.
- **Godot/Legacy 보존**: 일반 `ETC` 또는 `external_id=NULL` 출처, IGDB와 무관한 Trend, 출처가 없는 기존 Demo 데이터는 이 정책만으로 숨기지 않는다. **혼합 Source**(동일 Trend의 만료 IGDB + 다른 유효 Source)는 현재 부모 `trends.title/summary`의 원천을 식별할 수 없으므로 조회만 fail-closed 처리한다. 유효한 다른 Source 및 북마크를 **삭제하지 않는다**. 향후 출처별 제목 원천이 확정되면 혼합 데이터 노출 정책을 별도 검토한다.
- **실제 삭제와의 경계**: 조회 방어는 데이터 수명 종료 및 캐시 무효화를 뜻하지 않는다. 운영 DB·백업·모바일 캐시의 만료 데이터는 여전히 남을 수 있다. FK/중복·Journal/복수 Source/북마크를 검증하기 전 부모 Trend `DELETE` 또는 `HIDDEN` 자동 변경은 금지한다. 종료 시 삭제·캐시 정책과 별도 관리자 정리 권한을 후속 구현한다.
- **검증**: 승인된 격리 테스트 DB에서 정확한 30일 경계/직전 유효/비IGDB 구형 출처/혼합 Source fail-closed/부모·출처 보존/최신 Source 배제/limit 선적용을 테스트한다. 이 검증은 실제 운영 게시·G6 승인 및 30일 보유 데이터의 물리 삭제 완료를 의미하지 않는다.

### 6.2 IGDB 로컬 전용 TrendCard 검토 연결 (2026-11-21)

- **목적 및 범위**: 이미 승인된 개발·내부 검증 허용 범위에서만 IGDB Visits 수집 → 후보 적격성 → **독립 API 재조회** → 임시 카드 표시를 수직 연결한다. 실제 APK `TrendCard`는 DB 기반 식별자/카테고리 ID를 요구하므로, 가짜 DB ID를 만들거나 공개 FastAPI Router를 추가하지 않는다. 이는 Expo UI 또는 실제 APK E2E 증거가 아닌 별도 **로컬 브라우저 UI 검증**이다.
- **진입점**: Backend의 `python -m scripts.igdb_local_preview`를 수동 실행한다. Client ID는 입력, Client Secret은 `getpass` 비표시 입력으로 받고 두 개의 독립 `IgdbClient` 인스턴스를 검증 사이클마다 생성한다. 외부 요청은 Client의 고정 allowlist 및 rate limit에 한정한다. 환경변수/파일/DB/Journal/systemd에 자격증명이나 수집한 결과를 저장하지 않는다.
- **표시**: 표준 라이브러리 HTTPServer를 **127.0.0.1**에만 바인딩하고 임의 포트를 기본으로 쓴다. 루트 경로 `/`만 허용; 브라우저의 로컬 주소를 수동으로 연다. 검증된 `PopularitySnapshot`에서 게임명, 원래 IGDB Visits 관측 순위, 기준시각, 부문, 공식 IGDB 게임 링크 및 고정 출처만 표시한다. 이미지, 원문 소개문, 지표값, 인증정보는 표시하지 않는다. 다른 요청 경로는 404, Host 불일치는 400으로 차단하고 HTML 문자열은 escape한다.
- **보존/접근**: HTML 파일을 만들지 않고 페이지는 요청 시 메모리에서 생성한다. `no-store`, Referrer-Policy, Content Security Policy, robots noindex를 설정하며 접근 로그를 남기지 않는다. 원천 수집이 비정상적이면 상세 오류/비밀을 반환하지 않는 503 페이지다. IGDB 적격 후보 없음은 별도 빈 카드로 표시한다. 이 화면은 인증된 다중 사용자 서비스가 아니며 로컬 컴퓨터에서만 수동 실행·종료한다.
- **승인 경계(완료된 과거 검토 범위)**: 기존 `ADAPTERS` Registry·Approval/G6·MariaDB·Journal·Scheduler·FastAPI Router·React Native 화면은 **변경하지 않는다**. 비상업 API의 로컬 검토 근거와 실제 데이터 저장/제공 권리는 구분한다. 30일 보존 상한은 이번 서버의 저장 권한 또는 운영 승인을 부여하지 않는다. **별도 Expo Preview 개발 PR #138은 사용자 결정으로 미병합 종료되었으며 반복하지 않는다.** 다음 우선 작업은 기존 Writer → MariaDB → FastAPI → 실제 TrendCard 통합이다.
- **검증**: 두 독립 Query 사이의 원천 응답 변경 거부, HTML escape, 비정상 후보 없음, localhost/Host/path 차단, 브라우저 Cache-Control 및 503 민감값 비노출에 대한 mocked 회귀를 추가한다. 실제 IGDB 인증 및 브라우저 열람은 사용자의 개발 환경에서 별도 확인한다.

## 7. 테스트 및 종료 기준

1. 실측 입력의 최소 비밀 제거 fixture로 정상 선택/등급 미제공·성인·Erotic·복수 플랫폼·유형·48h 경계·순위 변조·date mismatch·URL 변조·동일 ID·unknown enum 거부. 전체 덤프 재게시 금지.
2. HTTP mocked 인증 만료/401/429/timeout/redirect/invalid payload, 독립 재조회, source binding, no eligible, bounded request budget 및 정보 노출 검사.
3. 공통 회귀: Godot 기존 7일/10분/identity/digest, 기존 운영 Profile V1 및 Journal, Transaction 중복/HIDDEN/lock/rollback, old state/cooldown/pending migration, Timer 조건 호환, 한 Cycle 최대 후보 1.
4. 로컬 기존 테스트 DB만 승인된 대상 사용. Ruff/영향 테스트, 필요 일반 회귀 및 실제 환경 smoke. Godot 운영 중 코드/프로필 변경 없이 실증 로그 수집. 운영 환경에 대한 합성 시험 반복 금지.
5. 실제 권리 확정 및 사용자 G6 별도 승인 이후만 로컬 최초 Game 카드, API/UTF-8/모바일 원문 링크, 반복 SKIP 및 순환 확인. Lightsail 및 다분야 추가는 별도 범위.

단계 종료: 확정된 필터/순수 정책부터 구현 가능, 권리/보존 및 인증·순환 상태의 미확정 메커니즘은 확정 전 실제 운영 경로 활성화 금지. 기존 Godot의 6시간 무인 실행은 아직 실제 로그 미확인. 문서화 병렬 작업의 Current Work 수정은 이번 설계 커밋에서 제외하고 통합 시 증거와 함께 최소 갱신.
