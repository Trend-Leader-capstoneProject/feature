# Trend Leader MVP-A — G5 P1 최소 실행 계약 및 G6 HOLD 차단 시험 v0.1

> **결정일:** 2026-11-04 KST · **판정:** 대안 ② 채택 / P1 **HOLD 구간 최소 계약 확정** / 격리 SQLite 시험 PASS / 실제 MariaDB 테스트 DB 시험 **미실행** / 운영 G5 및 G6 **HOLD**
>
> **기준:** `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md` §G5·G6; `Trend_Leader_MVP_A_G5_P1_게시차단경계_설계검토_v0.1_REVIEW.md`; `Trend_Leader_AI_Development_Guidelines.md` §1. 실제 코드 검토 기준 GitHub `Trend-Leader-capstoneProject/feature`, `dev` SHA `17bb3446128350011a54df882c5427aea69ec12a` (2026-11-04 조회). 실제 로컬 working tree와 같은지는 미확인.
>
> **금지 범위:** 이 산출물은 **운영 게시 코드가 아님**. 서비스 DB/HTTP 쓰기·새 게시 API·DB 승인 테이블·Google RSS 사용·G6 PASS 선언·GitHub 원격 변경 없음.

## 1. 사용자 결정과 이전 설계 관계

2026-11-04 사용자 명시 결정: “설계 대안 2로 결정하겠습니다. P1 최소 실행 계약 확정 → 격리 테스트 DB에서 G6 HOLD 쓰기 차단 검증 진행”. 따라서 **제한된 오프라인 Batch 실행 도구 + DB 테이블별 쓰기 권한 분리**를 후속 구현 목표로 채택했다. 이전 A1(오프라인 개별 승인·증거 대조, 이후 Batch)과 G4 승인 및 Gate v0.3을 유지한다.

- 실제 API의 `Trend.status` 기본값은 `ACTIVE`; 목록·맞춤 목록 모두 `ACTIVE` 조회. 개별 승인 자체는 API 필터가 아님.
- Demo Seed는 명시 실행 시 `local` 설정만 확인하고 DB에 `commit()` 가능. 환경 문자열만으로 DB 격리가 증명되지 않음.
- Python 3.15는 G4 승인·재확인 완료, A1 v0.2 `ELIGIBLE_FOR_REVIEW_ONLY`, `content_ref=sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f`.
- 사용자 로컬 API P0 증거: ACTIVE 25건 모두 Demo, Python 3.15 0건. 이 값은 로컬 API에서 관찰한 한 시점의 증거이며 격리 테스트 DB/운영 DB 재고는 아님.

## 2. **확정**: 최소 실행 경계 계약 (P1-HOLD-V01)

| 단계 | 입력·신뢰 경계 | 필수 판정과 실패 동작 | 이번 구현 범위 |
|---|---|---|---|
| `PREFLIGHT` | G4 승인 원장, A1 v0.2 승인·Batch, 증거와 정책 버전, 운영 프로필, 대상 DB와 권한 | **읽기만 허용**. A1 통과가 게시 허가가 아님. 원본 증거·DB 식별·권한이 검증되지 않으면 APPLY 후보 인계 금지 | A1 v0.2 읽기 대조 재실행, 추후 MariaDB 인벤토리용 조회 도구 |
| `APPLY_REQUEST` | **독립적으로 인증된 G6 프로필 승인 증거** (Batch 내 `g6_status`와 분리), 콘텐츠 재대조, 대상 DB 바인딩 | `G6=HOLD` 또는 G6 승인 증거 없음/검증기 미구현/문구만 PASS → **즉시 BLOCK**. 이 시점에 게시 DB 연결 함수 호출 **0회**, DB DML **0건** | **HOLD 전용 차단 경계만 구현**. PASS 게시 실행 경로는 의도적으로 없음 |
| `APPLY` | 별도 최소권한 게시 계정, 중복·취소·상태·DB 인벤토리·G6 재확인, Batch 감사 기록 | 필요한 조건 모두 충족하기 전에는 게시용 DB 세션/트랜잭션 생성 불가. `status` 명시, 미완성 COMMIT 금지 | **미구현** — G5 P2와 운영 권한 검증 이후 별도 설계/구현 |
| `VERIFY/REVOKE` | 커밋 증거 및 전체/맞춤 API, Source, 캐시, 정정/철회 이력 | 공개 불일치 시 중단·철회 절차 실행. 커밋 후 오류와 캐시는 별도 시험 | **미구현** — P2/P3에서 시험 |

### 게시 전 강제 불변조건 (미래 APPLY 포함)

1. 배치 문서의 `g6_status="PASS"`, 환경변수, UI 버튼, 사람의 채팅 메시지 문자열은 **독립 G6 운영 승인 증거가 아니다**. 운영 승인 원본의 **승인자 권한·프로필·대상 환경·정책 버전·범위·유효성·시각**을 확인해야 한다. 신뢰 검증 방식은 별도 확정한다.
2. `G6 HOLD → 전체 Batch BLOCK → DB 쓰기 0`. `PASS`를 가장한 Batch 값도 **BLOCK**. 기본값은 거절.
3. G4 승인 상태, 철회, 권리·링크 검토, Google RSS 미파생, 정확한 7개 표시 필드와 `source_title_origin`·`source_label_evidence_id`, A1 v0.2 `content_ref`를 게시 직전 최신본과 재대조한다. 바뀐 항목만 제외하고 전체 위험이면 전역 중단.
4. DB 대상은 프로필·호스트·포트·DB명·접속 사용자, 기존 ACTIVE 전체와 Demo 포함 여부를 점검한다. 로컬 Demo ACTIVE 25건인 환경을 서비스 DB로 전제하지 않는다.
5. 앱 API 계정의 `trends`, `trend_sources`, `trend_category_map` DML을 분리·제한하고, 전용 게시 계정의 수명/권한/배포 범위를 통제한다. 단 **현 계정 GRANT는 미검증**이며 직접 관리자 SQL 우회가 가능하면 강제 차단 PASS 불가.
6. 상태는 DB 기본 `ACTIVE`에 의존하지 않고 명시한다. 실행·감사·부분 실패·철회 후 재게시 방지는 P2/P3에서 확정한다. G6 승인 전 서비스 DB에 `HIDDEN`으로라도 사전 INSERT하지 않는다.

**설계의 미확정 부분:** 독립 G6 증거의 인증 방식, 게시 계정 GRANT/배포 방식, 실제 APPLY 구현, 다건 트랜잭션/부분 성공, 캐시 회수, 감사 영속 저장소. **이 항목들을 현재 코드가 지원한다고 간주하지 않는다.**

## 3. 실제 실행한 격리 SQLite HOLD 테스트

- 파일: `g5_p1_hold_boundary_v01.py`, `g5_p1_hold_sqlite_test_v01.py`.
- 시험 DB: Python `tempfile.TemporaryDirectory` 내 **독립 SQLite 파일** `isolated_probe.sqlite3`; 합성 테이블 1개, 합성 ACTIVE 행 1개를 넣어 시험 전후 스냅샷 비교. **MariaDB 운영/테스트 DB와 무관**.
- 시험: `HOLD`, 위조 `PASS`, 누락 `None`, 부울 `True`, 임의 `APPROVED`, 기존 ACTIVE 행 보존의 6건.
- **실제 실행 결과: 6 / 6 PASS**, 게시 DB connector spy 호출 **0**, 경계의 쓰기 요청 **0**, 시험 DB 데이터 **전후 동일**. 단, 시험 DB를 준비하기 위해 실행한 테스트 전용 초기 INSERT는 `G6 HOLD 게시 시도`가 아니며 격리 테스트 준비 작업이다.
- 코드의 `deny_apply_before_connection()`은 의도적으로 **항상 차단**한다. 운영 `PASS` 경로를 구현하지 않았으므로 이것만으로 실서비스 쓰기 방어·DB GRANT 통제·실제 게시 성공을 증명하지 못한다.
- 실행 증거: `g5_p1_sqlite_test_result_v01.txt`.

## 4. 실제 Python 3.15 A1 v0.2 후보 연결 재시험

- A1 승인 장부·Batch JSON을 **기존 v0.2 검사기로 다시 대조**.
- `ELIGIBLE_FOR_REVIEW_ONLY` 1건 / `authorized_to_publish=0` 유지.
- HOLD 전용 P1 `APPLY_REQUEST`: `BLOCK / G6_HOLD`, DB connector **0회**, writes **0건**.
- 합성 16건 A1 v0.2 자가 테스트도 PASS; 가짜 G6 PASS/누락·변경·문구 계약 오류는 차단.
- 실행 증거: `g5_p1_a1_hold_check_result_v01.json`; G4 개별 승인 결정을 변경하거나 콘텐츠를 재승인한 것은 아님.

## 5. 격리 MariaDB 실제 시험 — **사용자 환경에서 실행 대기**

현재 작업 환경에서는 Docker·MariaDB 서버 및 DB 접속 드라이버가 없어 `127.0.0.1:3307/trend_leader_test`에 접근할 수 없었다. **따라서 MariaDB 테스트 DB를 실제로 검사했다고 적지 않는다.**

`g5_p1_mariadb_testdb_readonly_probe_v01.py`는 Trend Leader `backend/.env.test`의 `TEST_DATABASE_URL`만 읽고, 접속 문자열이 **localhost/127.0.0.1:3307/trend_leader_test**인 경우에만 실행된다. 실제 연결 시 `DATABASE()='trend_leader_test'`, 컨테이너 내부 `@@port=3306`을 재확인한다. `trends`, `trend_sources`, `trend_category_map`의 행 내용 스냅샷을 SELECT로 비교하며, HOLD와 가짜 PASS의 DB 연결을 허용하지 않는다. 결과에 비밀번호/접속 URL을 노출하지 않는다.

**허용 범위:** test DB SELECT 및 로컬 경계 함수 호출만. DB 마이그레이션, `CREATE/INSERT/UPDATE/DELETE`, GRANT 변경, 서비스 API 쓰기 없음. 테스트 DB가 아직 마이그레이션되지 않았다면 자동으로 마이그레이션하지 않고 오류로 중단한다.

```powershell
# [프로젝트 루트]/backend 에서 실행 — 기존 .venv 활성화 기준
cd backend
python "$env:USERPROFILE\Downloads\g5_p1_hold_v01\g5_p1_mariadb_testdb_readonly_probe_v01.py"
```

**시험 완료 판정:** 실제 콘솔 JSON의 `result=PASS`, `db_tables_unchanged=true`, `apply_db_connect_calls=0`, `db_writes_by_probe=0`가 확인될 때 **해당 격리 MariaDB에서만** `P1 HOLD 접속 전 차단 시나리오 PASS`를 추가 기록한다. 이것은 DB 계정 GRANT와 직접 SQL 우회 방어를 증명하지 않는다. 그 시험은 후속 P1 권한 분리 검증에서 필요하다.

## 6. 증거-판정 매핑

| 증거 ID / 단계 | 근거 | 판정 |
|---|---|---|
| `E-G5-01` 차단 시나리오 — 격리 SQLite | 6건 PASS / connector 0 / 데이터 전후 동일 | **PASS (격리 합성 환경 범위)** |
| `E-G5-05` A1 승인 대상 대조 | Python 3.15 1건 REVIEW_ONLY / 실제 허가 0 | **PASS (오프라인 범위)** |
| `E-G5-01` — 실제 MariaDB 3307 | 실행 준비 코드 작성, **사용자 실행 결과 없음** | **미실행** |
| `E-G5-01/02` — DB 계정 권한 | 실제 GRANT/직접 INSERT 차단 시험 미실시 | **미검증** |
| `E-G5-03/06` — 철회·실제 게시 부분 실패 | P2/P3로 분리 | **HOLD** |
| `E-G6-01~05` | 운영 프로필 최종 승인 미실시 | **HOLD** |

**종합:** **대안 ② 방향 및 P1 최소 실행 계약(HOLD 경계) 확정**, 격리 SQLite 테스트 PASS. **P1 전체 완료는 아님. G5 운영·G6 HOLD, 실제 게시 `NOT_ATTEMPTED`.**

## 7. 다음 작업

1. 사용자 격리 MariaDB `3307`에서 SELECT 전후 비교 실행 → 결과 연결. 비밀번호·실제 DB URL은 공유하지 않는다.
2. **DB 권한 분리 실제 가능성**을 `SHOW GRANTS` 등 읽기 전용 확인으로 검증하고, 테스트 전용 계정에 한해 별도 SQL 우회 차단 실험 계획 확정. 무단으로 계정/GRANT를 변경하지 않는다.
3. 독립 G6 프로필 승인 원본의 위변조 방지·검증 절차를 설계한 뒤, `APPLY` 코드 추가 여부를 결정한다. 실제 G6 승인은 G5 통제 검증과 별도다.

> 원격 GitHub/Notion, 서비스 DB, 승인 장부 원본과 게시 콘텐츠는 변경하지 않았다. 본 문서는 테스트·설계 증거이지 운영 승인서가 아니다.