# Trend Leader — P4 Final Review 보완안 v0.2 — A1 연계 최소 계약 (DRAFT)

> 작성 기준: 2026-11-08 (KST)  
> 기준 코드: `Trend-Leader-capstoneProject/feature` `dev` HEAD `42f307bde8649a67ab5788422e64a0eb4f22854d` (2026-11-08 PR #81 병합 후 재확인; 원초안 기준 `17bb3446128350011a54df882c5427aea69ec12a`)  
> 상태: **기존 P4-DEC-01~20 유지 / A1(B-Lite 실행 지시 + 별도 실행 환경 독립 Writer)·B2(보호된 영속 Journal + 로그) 방향 결정 / 세부 계약 DRAFT / P4 NOT FROZEN / G5 P1 전체 및 실제 G4·G5·G6 HOLD**  
> 대상: P4-DEC-01~20 누적 확정안을 **변경하지 않고** 구현 가능성과 신뢰 경계를 보완  
> 비범위: P0~P3 FROZEN 변경, Google RSS 실운영, 관리자 UI/온라인 승인 시스템, 신규 게시 이력 DB 테이블, 자동 재시도·자동 복구  
> 변경 범위: **본 P4 DRAFT 문서 1개만 신규 추가**. 기존 v0.1 원본·다른 GitHub 문서·Notion·Backend 코드·DB·Compose·FROZEN 정책은 수정하지 않음. §5의 A1 v0.2 참조 계약과 이번 A1/B2·격리 검증 결정을 같은 DRAFT에 보완함.

## 0. 근거 수준과 선행 주의사항

1. 기존 `dev`의 ORM, FastAPI 인증/공통 응답, `docker-compose.yml`, Demo Seed, Category Taxonomy v1.0.1, 전체 목록 v1.0.14, P0~P3 v1.1 FROZEN, G5 A1 2026-11-04 체크포인트를 확인하였다.
2. G5 A1 체크포인트는 기술·합성 리허설 일부 PASS이지만 **실제 G4/G5/G6는 HOLD**라고 기록한다. 독립 JSON 대조 도구도 당시 실제 G6 PASS를 발행하지 않았다.
3. 최상위 정책 원본 `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md` **전체 원문은 아직 미대조**다. 이전 검토 기록에서는 `trend_leader_g5_p1_hold_gate_v01(1).zip`의 `trend_leader_g5_a1_approval_reconcile_v02.py`와 Python 3.15 합성 JSON을 읽고 `content_ref`를 독립 재계산하여 일치했다고 보고했다. **이번 문서 반영 작업에서는 해당 ZIP 원본을 다시 확보·재실행·독립 재계산하지 않았다.** 해시 일치는 이전 기록에 한정되며 운영 승인 증거가 아니다.
4. 이전 검토에서 언급된 `Trend_Leader_P4_Writer_G0-G6_Final_Review_DRAFT_20261108.md`는 **현재 `dev` 파일 트리에서 발견되지 않았다**. 이전 검토 기록이 지적한 ‘같은 Batch 재실행 멱등 처리’·‘CLI 우선’·‘P3 후보→Writer 직접 흐름’과 DEC-05·12·16의 차이는 문서 이력에 관한 **재검증 필요 사항**으로 남긴다. 이 초안이 `dev`에 있다고 가정하거나 기존 문서를 임의 수정하지 않는다.

## 1. 결론 및 공통 불변조건

**결론: 4개 영역 모두 최소 구현 전략을 제시할 수 있으나, 안전성의 실증 전에는 P4 전체 동결·실제 게시를 선언하지 않는다.**

- P4-B-Lite는 **게시 실행 지시 API만** 제공하고, 실제 DB 게시 책임은 **별도 실행 환경에서 동작하는 독립 Writer**가 갖는다(A1 사용자 선택). G4 승인·철회 담당자와 게시 실행 운영자의 권한을 혼동하지 않는다.
- 진입: 운영자별 전용 인증키 + 실제 내부 접근 제한 + API는 `batch_id`만 수신. 서버의 보호된 승인 Batch v1만 로드한다.
- 승인: 보호된 G4 개별 기록, `content_ref` 일치, 철회 상태, 신뢰 가능한 G6 운영 프로필을 **서로 독립적으로** 검사한다. 클라이언트 `approved=true`는 증거가 아니다.
- DB: 명시적 관측 UTC, 활성 Child Category, 원문 Source, 기존 HIDDEN 포함 중복을 재검증하고 Batch **전체 하나의 Transaction**만 Commit/Rollback한다. 실패·중복 시 자동 재시도하지 않는다.
- `WOULD_ACCEPT`는 P0~P3 합성 Fixture 기술 결과이며 게시 허가가 아니다. Google RSS 실수집·재공개는 별도 승인 전 비활성이다.
- 게시 시도와 DB 확정은 다른 사건이다. 응답 소실·Commit 결과 불명확은 **실패가 아니라 조사 필요**로 기록한다.
- B2 사용자 선택: **보호된 영속 Journal + 구조화 로그**를 분리한다. Journal 무결성이나 복구를 검증하지 못하면 실행을 차단한다.
- **이번 단계에서는 합성 데이터·격리 테스트 DB로 승인 철회/HOLD/복구 흐름만 검증**하고, 실제 G4/G5/G6 게시 Gate는 HOLD로 유지한다. 운영 게시의 철회·게시 경쟁 제어를 구현·실증하기 전 실제 게시를 허가하지 않는다.

## 2. 보완 ① DEC-13·19 — 영속 실행 기록·재실행 방지

### 2.1 역할 분리 (단일 파일 물리 구성은 가능하나 책임은 구분)

| 역할 | 의미 | 책임 |
|---|---|---|
| 구조화 감사 로그 | 누가 무엇을 시도했고 어떤 결과를 관측했는가 | 관측·진단. 비밀키/원문 본문/전체 원문 URL 기록 금지 |
| 영속 실행 Journal | 이 Batch가 실행된 적 있는지·미해결 실행이 남았는지 | **안전 차단의 의사결정 근거**. 손실·손상·불명확이면 전체 게시 HOLD |
| A1 오프라인 게시 기록 | 사람의 승인·운영 결과 대조 | G4/G6와 별개의 실행 승인, 조사·조정·사후 책임 기록 |

**주장 금지:** Python 일반 `logging`, 컨테이너 `stdout`, DB Named Lock만으로 Journal의 영속성과 재시작 후 재실행 금지가 자동 보장된다는 주장.

### 2.2 전시 MVP용 최소 배포 프로필 (제안)

- P4 Writer는 일반 FastAPI와 **별도 실행 환경**(단일 호스트 내 독립 서비스/프로세스 후보)으로 격리한다. 최소 MVP는 **단일 배포 호스트 / 단일 보호된 영속 볼륨 / 동일 MariaDB**로 제한한다. 복수 실행 시도는 Named Lock과 같은 Journal 저장소에서 직렬화한다. 다중 서버·네트워크 파일시스템 환경은 범위 밖이며, 정확한 실행 프로세스/통신 방식은 별도 검증 후 정한다.
- 운영 시작 전에 Journal 저장소의 기존 등록·무결성·쓰기/읽기 가능 여부를 확인한다. **빈 디렉터리가 생겼다는 사실만으로 자동 신규 초기화하지 않는다.** 기초 등록 기록 또는 독립된 A1 인덱스와의 대조 없이는 FAIL CLOSED한다.
- 파일 기반 구현을 택한다면 원자적 레코드 생성, 파일/디렉터리 `fsync` 등 실제 영속화, 중복 ID 차단, 손상 검사, 접근 권한, 볼륨 재마운트 후 복구를 격리 환경에서 테스트한다. 이 조건을 충족하지 못하면 실제 게시 HOLD; 새 DB 테이블을 몰래 추가하지 않는다.
- 이 저장소의 영속성을 확보하기 어렵다면 DEC-13 유지가 실현 가능한지 별도 **설계 변경 요청**을 해야 한다. 복잡한 커스텀 파일 DB를 무조건 만들어야 한다는 결론은 아니다.

### 2.3 최소 실행 상태 전이

```text
실행 요청
  └─ 전역 Named Lock 획득
      └─ 미해결 Journal 및 같은 Batch 기록 확인
          └─ G4/G6/Batch 사전검증 및 승인 변경 차단 구간 진입
              └─ COMMIT 시도 전에 STARTED 기록 영속 확인
                  └─ DB 최종 재검증 + 트랜잭션 쓰기
                      ├─ COMMITTED (Commit 성공 확인)
                      ├─ ROLLED_BACK (Rollback 완료 확인)
                      └─ COMMIT_UNKNOWN (확정 불가)
```

- `STARTED`만 남거나 결과 레코드가 누락된 경우 **미해결 실행**으로 판정한다. `COMMIT_UNKNOWN`을 기록할 기회조차 없었던 장애도 HOLD다.
- `COMMITTED`로 응답하기 전 DB Commit 성공과 필수 사후 기록의 영속화를 각각 확인한다. Commit은 됐지만 결과 기록 실패 시 성공을 추정하여 재실행하지 않고 운영 HOLD 및 수동 DB 대조로 처리한다.
- `ROLLED_BACK`도 **자동 재시도 허가가 아니다.** 수동 대조·재승인·별도 실행 결정을 거친다.
- 별도 오류나 HOLD가 남아 있으면 다른 Batch도 새로 게시하지 않는다(DEC-19).
- 전역 Named Lock은 연결 소유이며 DB 트랜잭션 `COMMIT`/`ROLLBACK`으로 해제되지 않는다. 전용 연결 수명, 정상 `RELEASE_LOCK`, 연결 풀 반환 전 해제 및 강제 장애 테스트가 필요하다.

### 2.4 필수 검증

`FJ-01` 동일 Batch 2 Worker 동시 실행 → 최대 1회 쓰기 시도. `FJ-02` Commit 직후 프로세스 종료 → Journal 미완료 및 전체 HOLD. `FJ-03` Journal 디렉터리 삭제·손상·읽기 불가 → 실행 금지. `FJ-04` Commit은 성공, 사후 기록 실패 → 자동 재실행 금지·수동 조사. `FJ-05` Rollback 확인 → 전체 데이터 0건·수동 재실행 정책 유지. `FJ-06` DB Named Lock 연결 반환 후 잠금 누수 없음.

## 3. 보완 ② DEC-08·15·20 — G4/G6 승인 변경·철회 통제

### 3.1 불변 스냅샷 ≠ 승인 효력

- 검증된 Batch JSON 바이트와 G4가 승인한 게시 필드의 `content_ref` 일치는 **내용 동일성 확인**이다.
- G4 승인 권한·철회·콘텐츠 이용 권리와 G6 운영 프로필의 유효성은 **독립 승인 기록에서 확인**한다.
- G4 승인, G6 운영 프로필 승인, 각 Batch의 실행 허가는 서로 다른 의사결정이다. 같은 상태값으로 합치지 않는다.

### 3.2 최소 운영 프로토콜 (제안)

1. **승인 기록 관리 책임자(G4)**와 **게시 실행자(P4)**를 구분한다. P4 API 인증키에는 승인·철회 기록 수정 권한을 부여하지 않는다.
2. 승인 파일은 게시자에게 읽기 전용으로 제공한다. 게시 실행 전 최신 승인/철회 상태, Batch 스냅샷 해시, G6 적용 환경·소스·기한·승인 권한을 다시 확인한다.
3. 게시 실행 중 승인 변경은 임의 파일 편집이 아니라 **하나의 조정된 승인 변경 절차**만 사용한다. 두 절차(승인 변경·Writer)가 동일한 보호 구간을 배타적으로 사용해야 한다. 별도 제어가 없다면 ‘모든 변경 감지 보장’이라고 주장할 수 없다.
4. 운영상 긴급 철회가 접수되면 신규 게시를 차단한다. **COMMIT 요청 전** 유효하게 철회가 확인되면 전체 Rollback, **COMMIT 요청 후 응답·확정이 불명확하면** 성공/취소를 추정하지 않고 Journal HOLD 및 운영자 대조, **COMMIT 완료 후** 철회가 발효되면 기존 트랜잭션을 Rollback할 수 없으므로 별도 승인된 공개중단(`HIDDEN` 전환·캐시 확인) 절차로 처리한다. 승인 철회의 발효 시점과 게시 Commit의 선후는 공유 통제 경계에서 별도 정의한다. 기존 HIDDEN 자동 복구 금지는 유지한다.
5. 승인 변경 경로의 단일성·공유 보호 구간·기록 신뢰성을 입증하지 못하면 실제 P4 게시 HOLD. 초기 MVP는 **격리 DB의 합성 철회·HOLD·사후 대조 시험만 수행**하며, 이 시험 성공을 운영상 철회 경쟁 제어의 PASS로 승격하지 않는다. ‘게시 전 한 번 더 읽기’만으로 실시간 철회 레이스가 해결됐다고 보고하지 않는다.

### 3.3 책임 명확화

| 검증 | 결정 시점 / 실패 동작 |
|---|---|
| 승인 스냅샷 | 게시 진입 직전 불변 데이터로 고정, 내용 불일치 시 전체 차단 |
| 승인 유효성 | 승인 변경 조정 보호 구간에서 마지막 확인, 미검증·철회 시 전체 차단 |
| Category | DB 트랜잭션 내 실제 Parent/Child 활성과 계층을 확인하고 필요한 행 잠금 |
| Trend 중복 | DB 최종 조회+UNIQUE, `HIDDEN` 포함 충돌 시 전체 Rollback |
| Source 중복 | 정규 URL SHA-256, DB UNIQUE, 충돌 시 전체 Rollback |

**검증:** `FA-01` 승인 후 내용 변조 거부, `FA-02` Commit 전 철회 차단, `FA-03` 게시 중 철회 경합이 정의된 순서대로 처리, `FA-04` 승인 변경 통제 우회 시 FAIL CLOSED, `FA-05` Category 부모/Child 활성 변경 레이스 안전, `FA-06` Commit 후 철회 및 사용자 공개 중단 절차의 책임 경계 확인.

## 4. 보완 ③ DEC-09·12·14 — DB 우회 쓰기와 B-Lite 배포 보안

### 4.1 실제 코드상 위험

- `Trend.status`의 ORM·서버 기본값이 `ACTIVE`이므로, 승인 경로를 우회한 INSERT는 자동 공개 위험이 있다.
- `backend/app/db/seeds/demo_trends.py`는 `app_env == 'local'`인지 검사한다. 현재 `backend/app/core/config.py`의 `database_url` override가 `db_host/name`보다 우선하므로 **환경 문자열만으로 DB 연결 대상이 안전하다고 보장하지 못한다**.
- `docker-compose.yml`의 `${BACKEND_EXTERNAL_PORT}:8000`는 별도 바인딩 주소 제한이 없는 포트 매핑이다. **같은 공개 서버에 `/internal` 경로를 추가하는 것만으로 내부 API가 되지 않는다**.
- 기존 일반 `CurrentUserDep`는 사용자 신원과 활성 상태를 확인하지만 관리자 게시 권한은 제공하지 않는다.

### 4.2 MVP 배포 구조의 최소 수용 조건

- **공개 앱 API와 게시 실행 진입점의 네트워크 경계가 실제로 분리되어야 한다.** 최소 선택지는 동일 코드베이스의 별도 관리용 프로세스/포트(호스트 loopback 또는 관리 VPN에서만 접근)이다. 또는 공개 앱 API 앞에 게이트웨이를 두고 게시 경로를 강제 차단할 수 있으나, 백엔드 직접 접근 우회를 봉쇄해야 한다. 어느 것도 구성되지 않으면 B-Lite 게시 경로를 활성화하지 않는다.
- 별도의 운영자별 인증키를 서버 보안 설정에 주입한다. 인증키 존재·유효성·게시 권한과 출처 네트워크를 모두 검사한다. 키 원문·인증 헤더는 감사 로그에 기록하지 않는다.
- 실제 접속 DB에서 DB 이름·DB 사용자 및 운영 프로필을 **세션에서 직접** 확인하고, 승인된 대상과 일치하지 않으면 쓰기를 차단한다. `APP_ENV` 문자열만 신뢰하지 않는다.
- DB 계정의 권한은 **서비스 목적별 최소 권한**으로 통제한다. 공개 앱 계정은 Trend/Source/Category Map 쓰기가 필요하지 않다면 해당 테이블 INSERT·UPDATE 권한을 제거하고, 승인 Writer 계정에만 필요한 권한을 준다. 일반 로그인·관심사 등의 필수 쓰기는 보존한다.
- Demo Seed는 실제 게시 DB에서 실행 불가능해야 한다. 로컬 시연 Seed와 승인된 P4 등록 데이터를 같은 근거로 취급하지 않는다. 직접 SQL·DB 관리자 권한은 별도 관리 책임과 접근 통제를 둔다.
- C4(2026-11-08, PR #81) `dev`에서는 MariaDB 관리용 `trend_user`와 FastAPI 실행용 `trend_api_runtime`을 구분하며, Compose의 Backend `DB_USER`/`DB_PASSWORD`는 `${API_DB_USER}`/`${API_DB_PASSWORD}`로 주입된다. `backend/.env`/Windows 온보딩은 Migration·Seed의 관리 계정 사용을 구분한다. **이 설정은 Writer 전용 계정/격리 실행을 생성하지 않는다.** 현재 문서 검토에서는 DB의 실제 GRANT를 재실행 검증하지 않았다.
- 일반 API에 Writer 전용 DB 인증정보·영속 Journal 수정 권한·Docker daemon/socket 제어 권한을 주지 않는 방향을 우선한다. 별도 실행 환경의 보호된 내부 호출 인증·운영자별 키·Writer 전용 계정 최소 GRANT는 추가 설계·격리 시험 대상이다.
- 현재 Compose·권한 설정만으로 위 격리가 실현됐다고 주장하지 않는다. DB 권한·포트 바인딩·키 설정은 실제 배포 환경에서 확인한다.

### 4.3 필수 검증

`FS-01` 일반 JWT로 관리 API 게시 거부. `FS-02` 운영자 키 미설정·회수·오류 시 거부. `FS-03` 허용되지 않은 네트워크에서 접근 불가. `FS-04` 관리 API 네트워크 경계의 직접 백엔드 우회 차단. `FS-05` DB 접속 대상 override를 바꿔도 잘못된 환경에서 INSERT 거부. `FS-06` 공개 API DB 계정의 Trend INSERT 권한 거부, 일반 사용자 도메인 쓰기는 정상. `FS-07` Demo Seed가 실제 운영 연결로 실행 불가. `FS-08` 관리자/수동 SQL 우회는 서비스 외부 책임 경계·조사 절차 기록.

## 5. 보완 ④ DEC-02·07·08·10·15·16·17 — A1 v0.2 보존형 P4 Batch v1 최소 연결 계약

> **방향 승인:** 2026-11-08 사용자 선택은 **A안(기존 A1 v0.2 승인 스냅샷 보존 + P4 최소 연결 정보)**이다. 아래 구체 필드·관측 증거 구현은 P4 최종 FROZEN 전 확인할 **계약 초안**이며 운영 게시 승인이 아니다. P4-DEC-01~20은 변경하지 않는다.

### 5.1 사실 확인: A1 v0.2와 P4는 서로 다른 계약

**확인한 원본**

- 업로드 `trend_leader_g5_p1_hold_gate_v01(1).zip`의 `g5_p1_hold_v01/trend_leader_g5_a1_approval_reconcile_v02.py` (`SCHEMA_VERSION = "A1_RECONCILE_V02"`, `POLICY_VERSION = "v0.3_POLICY_CONFIRMED"`).
- 같은 ZIP의 `python315_approval_manifest_RECONFIRMED_v02.json`, `python315_batch_candidate_REVIEW_ONLY_v02.json`, `g5_p1_a1_hold_check_result_v01.json`.
- 독립 SHA-256 재계산: 예시의 `content_ref = sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f`와 일치. 이 값은 **해당 예시 콘텐츠에만 해당**하며 공식 승인 서명·이용 권한 입증이 아니다.

**A1 v0.2에서 해시에 포함되는 정확한 필드**

```python
# A1 v0.2 canonical_ref()에서 직렬화하는 payload의 필드 구조
{
    "schema": "A1_RECONCILE_V02",
    "policy_version": "v0.3_POLICY_CONFIRMED",
    "trend_ref": trend_ref,
    "content": {
        "title": ..., "summary": ..., "category_refs": ...,
        "source_platform": ..., "source_url": ...,
        "source_title": ..., "thumbnail_url": ...,
    },
    "source_title_origin": source_title_origin,
    "source_label_evidence_id": source_label_evidence_id,
}
```

`json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`의 UTF-8 바이트를 SHA-256 해시하고, 결과에 `sha256:` 접두사를 붙인다. `content` 키는 정확히 위 7개이며 미정의/누락 필드는 A1 검사기에서 거부한다. `category_refs`는 중복 없는 비어 있지 않은 문자열 배열이고 **배열 순서 또한 해시의 일부**이므로 임의 정렬하지 않는다.

`source_label_evidence_id`는 **Batch item이 아닌 독립 승인 record에 존재**한다. A1 검사는 승인 record의 이 값을 사용해 해시를 재계산한다. `content_ref`는 출처 권리·승인 진위·G6 PASS를 증명하지 않는다.

A1 v0.2의 `reconcile()` 결과 `ELIGIBLE_FOR_REVIEW_ONLY`는 **검토용 적격성**만 나타낸다. 검사기는 `batch.g6_status == "HOLD"`만 허용하며 `authorized_to_publish = 0`을 반환한다. 따라서 `g6_status` 값을 `PASS`로 바꿔 직접 게시하려는 방식은 금지한다.

### 5.2 최소 어댑터 범위: 당장 지원할 수 있는 A1 v0.2 부분집합

| 필드·기능 | A1 v0.2 실제 검증 | P4 연결 v1의 초기 수용 조건 | DEC 정합성 |
|---|---|---|---|
| `title` | 비공백 필수 | 기존 스냅샷 그대로 사용, P2 및 DB 255자 검증 추가 | DEC-01·17 |
| `summary` | 비공백 필수 | **필수로 유지**. P4의 일반 nullable 허용 범위보다 좁게 구현 | DEC-10 유지 |
| `category_refs` | 중복 없는 비공백 문자열 배열 | 정확한 부모 코드/Child 이름 매핑, 활성·계층 검증 후 DB ID 파생 | Taxonomy·DEC-09 |
| `source_platform` | `GOOGLE/YOUTUBE/SNS/ETC` | 원문 실제 목적지 플랫폼으로 확인, 무조건 Google Trends로 기재 금지 | DEC-03 |
| `source_url` | HTTPS·호스트 존재·사용자정보 없음 | 원본 보존, 별도 P2 URL 안전성·Canonical URL·4,096자 검증 추가 | DEC-02·17 |
| `source_title` | `NONE→null`, `EDITORIAL_LABEL→1~80자` | **`EDITORIAL_LABEL`이면서 증거 존재하는 항목만** P4 게시 후보. `NONE`은 전체 차단 | DEC-10 |
| `thumbnail_url` | 반드시 `null` | 현 A1 경로에서는 `null` 고정. 임의 이미지 추가 불가 | DEC-10 |
| Source 수 | A1 item에 하나의 `source_url` | 초기 연결은 **Source 정확히 1건**. DEC-17 최대 5건은 상한 유지 | DEC-17 |
| 관측 시각 | A1 `content_ref`에 **없음** | 독립된 실제 Collection/관측 증거와 연결 후에만 저장 | DEC-07·08 |

A1 v0.2의 출처 문구 규칙 중 `EDITORIAL_LABEL`은 앞뒤 공백 없음·길이 1~80자·개행/`<`/`>` 없음이며, `source_label_evidence_id`가 비어 있으면 거부한다. A1의 `NONE` 사례는 합성 오프라인 검토용으로 유효할 수 있지만 DEC-10에서 요구한 **P4 비공백 Source 제목**을 충족하지 못한다. Writer가 새 제목을 생성하거나 승인 스냅샷을 변경해서 보완해서는 안 된다.

### 5.3 새 게시 콘텐츠 복제를 피하는 P4 v1 Envelope (제안)

공식 API 요청은 이전 DEC-15대로 **`batch_id` 하나만** 받는다. 서버가 그 ID로 **사전 등록된 보호된 P4 Batch v1**을 로드하며, 실제 콘텐츠는 **별도로 보호된 불변 A1 v0.2 Batch 스냅샷**에서 `trend_ref`로 읽는다. P4 Envelope는 제목·Source URL 등 A1 해시 대상 필드를 중복 저장하지 않는다.

```json
{
  "schema_version": 1,
  "batch_id": "P4-EXAMPLE-001",
  "a1_batch_ref": "PROTECTED-A1-SNAPSHOT-001",
  "items": [
    {
      "trend_ref": "SIM-ITEM-001",
      "review_evidence_id": "SIM-G4-001",
      "content_ref": "sha256:<실제 보호된 승인 기록과 대조할 해시>",
      "observation_evidence_ref": "SIM-OBS-001"
    }
  ]
}
```

> **구조 예시일 뿐 승인된 실제 데이터가 아니다.** `a1_batch_ref`와 `observation_evidence_ref`는 **서버 관리 보호 저장소 내 논리 식별자**이며 파일 경로나 사용자가 임의 지정할 외부 URL을 뜻하지 않는다. 예시 플레이스홀더는 유효한 해시값으로 취급하지 않는다. 필드명은 구현 전 문서 계약으로 고정해야 하며 현재 구현된 API/스키마는 아니다.

**Envelope의 v1 엄격 검증 후보**

- 상위 키는 `schema_version`, `batch_id`, `a1_batch_ref`, `items` 네 개로 한정한다.
- item 키는 `trend_ref`, `review_evidence_id`, `content_ref`, `observation_evidence_ref` 네 개로 한정한다. 공백값·중복 `trend_ref`·미정의 키·문서 버전 오류는 **Batch 전체 차단**한다.
- P4 JSON 실제 바이트 크기는 **1 MiB 이하**, Trend 항목은 **1~10건**, 현재 A1 연결 Source는 **각 Trend 정확히 1건**으로 제한한다. Source 최대 5건이라는 이전 상한을 변경하지 않으며, 현재 A1 어댑터의 **지원 범위만 제한**한다.
- `batch_id`는 서버 등록된 식별자·보호 스냅샷과 일치해야 한다. 클라이언트가 보내는 `batch_id`·Envelope의 참조·해시가 **승인 권한의 근거는 아니므로**, 독립 G4 승인 기록·A1 개별 게시 실행 승인 기록·G6 운영 승인 기록과 각각 재대조한다.
- A1 검토용 Batch JSON의 `g6_status = HOLD`를 수정하지 않는다. **P4의 실제 G6 허용 여부는 별도의 진짜 운영 승인 기록에서 검증**한다. A1 v0.2 `ELIGIBLE_FOR_REVIEW_ONLY`를 `PASS`로 승격하지 않는다.
- 독립 승인 기록의 `trend_ref`, `review_evidence_id`, `content_ref`, `source_title_origin`, `source_label_evidence_id`를 실제 A1 스냅샷에 대조한다. `content_ref`는 A1 `canonical_ref()`를 변경 없이 재계산한다.
- A1 `source_url`은 승인된 표시 콘텐츠이므로 **원본을 임의 변경하거나 해시를 갱신하지 않는다.** P4는 같은 문자열을 검증하고 별도로 `canonical_url`을 구해 `source_key = SHA256(canonical_url UTF-8)`을 만든다. DB `source_url`을 승인 원문 그대로 보존하는 방식을 초기 제안하며, Canonical URL과의 정책 관계는 DB 통합 테스트로 검증한다.

### 5.4 실제 관측 증거: 없는 시간을 만들어내지 않기

**현재 입증 수준:** A1 v0.2의 `content_ref` 계산 대상 및 예시 JSON에는 `observed_at`·`collected_at`이 없다. G4 `approved_at`은 **승인 시각이지 수집 시각이 아니다**. 원문 기사 게시일(`pubDate`)도 자동으로 실제 수집 시각이 되는 것은 아니다.

**P4에서 별도 보호 기록으로 확인할 최소 사실(제안)**

| 사실 | 확인 규칙 |
|---|---|
| 관측 증거 식별 | `observation_evidence_ref`는 서버 측 독립 보호 자료에서 해석 |
| 대상 연결 | `trend_ref`와 A1 `content_ref`에 연결되며 다른 항목으로 교체 불가 |
| URL 연결 | 관측한 URL이 A1의 `source_url`과 정확히 일치하거나 사전에 승인된 정규화 관계임을 증명. 단순 호스트 일치 금지 |
| 실제 시각 | 출처를 실제 관측/수집한 시각과 그 증거가 있어야 함. 타임존 명시 및 UTC 변환 검증 |
| 검토 범위 | 원본 링크·관측 증거가 G4의 확인 대상과 정합하며 별도 승인·변조 방지가 확인됨 |

현재 **실제 관측 증거 서식·보관 경로·검토 권한이 확인되지 않았으므로**, 이를 존재한다고 가정해 `collected_at` 값을 생성하거나 G4 승인 완료라고 표시하지 않는다. 증거가 없거나 내용이 불일치하면 전체 Batch **HOLD**한다.

초기 단일 Source 연결에서는 검증된 동일 관측 이벤트의 UTC 시각을 `Trend.first_collected_at`, `Trend.last_collected_at`, `TrendSource.collected_at`에 명시적으로 적용하는 방식을 제안한다. 실제 관측 이벤트가 이 의미를 충족하는지는 예시 증거를 확인한 후 검증하며, 단순히 시간이 같아 편하다는 이유로 설정하지 않는다. DB에 저장할 때는 프로젝트 기존 계약대로 UTC-naive `DATETIME`으로 변환한다.

### 5.5 Writer의 검증·파생 책임 (A1 원본에 영향 없음)

| 순서 | Writer 책임 | 거부 조건 |
|---|---|---|
| 1 | 서버 등록 `batch_id` → 보호된 P4 v1 Envelope, A1 v0.2 스냅샷 및 독립 G4 기록 조회 | 미등록/변조/증거 불명확 |
| 2 | DEC-17 엄격 v1·크기·건수·중복·필드 검사 | 형식 불일치·일부만 적격 |
| 3 | A1 `canonical_ref()` 그대로 재계산 + 독립 승인 기록과 대조 | 해시 불일치·권리/승인 증거 누락·철회 |
| 4 | `EDITORIAL_LABEL` 검토된 Source 제목·`thumbnail_url=null`·원문 URL 검증 | `NONE` 또는 미승인 표시·URL |
| 5 | `category_refs` 정확한 **부모 코드/Child 표시명** → 현재 DB Category ID 매핑 | 미등록/모호·부모나 Child 비활성·계층 오류 |
| 6 | 독립 관측 증거 검증·UTC 적용, 정규 제목·Canonical URL·Source Key 결정적 계산 | 관측 시각 누락/위조·정규화·길이 오류 |
| 7 | 독립 G6 운영 범위 + 해당 Batch의 A1 게시 실행 허가 + 영속 Journal·잠금 정책 | 실제 G6 HOLD·Batch 실행 승인 없음·미해결 실행 |
| 8 | 트랜잭션 내부 DB Category·중복 최종 재검증 후 Batch 전체 Commit | UNIQUE/잠금/검증 실패 → 전체 Rollback; Commit 불명확 → 조사 HOLD |

P4가 `category_ids`·`source_key`·`normalized_title` 등을 **추가 계산한다고 A1의 승인된 `content` 필드를 고치지 않는다.** Category 문자열 매핑은 대분류의 안정적인 `category_code`와 부모 아래 세부분류 표시명을 정확히 조회하되, 실제 매핑이 유일하지 않거나 명칭이 바뀌면 수동 검토한다. 비슷한 이름이나 최신 ID로 자동 대체하지 않는다.

### 5.6 경계 테스트: 이 단계에서 필요한 최소 집합

| ID | 시험 | 예상 결과 |
|---|---|---|
| `FB-01` | A1 v0.2 Python 3.15 합성 예시를 같은 직렬화로 해시 재계산 | 해시 일치 **[정적 재계산 확인]** |
| `FB-02` | A1 `title`/`source_title`/`source_label_evidence_id` 하나 변경 | 예전 해시 불일치 **[검사기 self-test 코드에 시나리오 있음; P4 구현 검증은 미실행]** |
| `FB-03` | P4 Envelope v1: 미지원 버전·초과 크기·중복 키·미정의 키 | 전체 차단 **[미구현]** |
| `FB-04` | `NONE` Source 제목·썸네일 추가·미승인 다중 Source | 전체 차단 **[미구현]** |
| `FB-05` | 잘못된 Category 문자열·활성 Parent/Child·DB Collation 충돌 | 전체 차단 **[미구현]** |
| `FB-06` | 관측 증거 없음·다른 Source의 증거·승인 시간만 존재 | 전체 차단 **[계약 제안·증거 미확보]** |
| `FB-07` | `ELIGIBLE_FOR_REVIEW_ONLY`와 A1 `g6_status=HOLD`만 제출 | 실제 게시 0건 **[A1 합성 도구 증거; P4 미구현]** |
| `FB-08` | Batch 내부 1개 항목만 실패·DB UNIQUE 충돌·Rollback | 전체 Batch 0건 **[P4 미구현]** |

### 5.7 이 단계의 절차 종료 기준

- **기존 검토 기록상 확인:** A1 v0.2 원본, 7개 표시 필드, provenance 포함 해시 직렬화, 예시 해시 일치, `ELIGIBLE_FOR_REVIEW_ONLY`/G6 HOLD 분리, P4 연결에 필요한 필드 차이. 이번 문서 반영 시 원본 ZIP은 재열람하지 않았으며 **실제 승인 진위·운영 G6 PASS로 승격하지 않는다**.
- **최소 변경 방향 사용자 승인:** 기존 A1 원본 보존 + P4 v1 Envelope에 참조만 보유. 추가 승인 UI·새 해시·다중 Source 어댑터 설계는 제외.
- **동결 전 남은 단일 도메인 의존성:** 실제 관측 증거가 무엇이고 누가 검증하는지. 증거를 찾기 전 임의로 생성하거나 가짜 승인·시각으로 보충하지 않는다.
- **이번 단계 종료:** 해시·스키마 차이 검토를 반복하지 않고, 다른 차단 영역(Journal·승인 변경 보호·관리 네트워크/DB 권한)의 **필요 최소 검증**으로 이동. 임의의 코드/DB/외부 데이터 게시로 진행하지 않는다.

## 6. 중점 설계 선택의 비교와 제안

| 영역 | 최소 구현안(현재 권고) | 장기 확장안 | 선택 근거 |
|---|---|---|---|
| 영속 Journal | 단일 호스트 보호 볼륨 + 원자적 레코드 + 수동 대조 | DB 이력 테이블/공유 트랜잭션 저장소 | DEC-13의 ‘신규 감사 DB 테이블 없음’을 보존, 실제 fsync·복구 검증 실패 시 재논의 |
| 승인 변경 | G4 책임자 전용 변경 절차 + Writer와 동일 변경 보호 구간 | DB 승인 레지스트리 | DEC-15·20 A1 오프라인 정책 보존, 외부 임의 변경은 지원 불가 |
| 내부 API | 별도 관리 프로세스/사설 진입점, 키별 인증, DB 최소 권한 | 정식 관리 서버/대시보드 | DEC-12 B-Lite 범위 유지 및 외부 공개 포트 우회 차단 |
| Batch | A1 v0.2 원본 보존 + P4 v1 참조 Envelope·관측 증거 연결 | 신규 전체 콘텐츠 재승인·다중 Source 어댑터 | DEC-15~17 보존, 출처/해시 계약 재작성 방지 |

## 7. 구현 전 차단 조건 (설계와 운영 승인 구분)

### 설계 FROZEN 전에 해결해야 하는 사실 확인

- [ ] **FR-B01** 운영 Gate v0.3 원문과 이번 보완안의 G4/G5/G6 정의/예외 및 서식 일치 확인.
- [x] **FR-B02a (기존 검토 기록 기준)** A1 v0.2 검사기·승인/Batch 예시 원문 확인 및 `content_ref` SHA-256 독립 재계산 일치가 이전에 보고됨. **이번 작업에서는 원본 재검증 미실행; 실제 승인 진위·G6 운영 허가 미입증**.
- [ ] **FR-B02b** 독립 실제 관측 증거의 형식·책임자·`trend_ref`/`content_ref`/Source 연결 방식을 확인하고 P4 v1 Envelope 필드 최종 동결.
- [ ] **FR-B03** 영속 Journal 저장·원자화·복구 설계를 격리 환경에서 실증하거나 불가능하면 대체 설계 재승인.
- [ ] **FR-B04** 승인 기록 변경/철회가 게시 중 Writer와 조정되는 운영 절차의 유일한 경로·책임자를 확인.
- [ ] **FR-B05** B-Lite 관리 API의 배포 경계(외부 직접 접속 금지)와 운영 계정·DB 별도 권한 실현 가능성 확인.

### 구현·G5 검증 전/중에 확인할 사항

- [ ] **G5-T01** 시험 DB에서 G6 HOLD일 때 게시 테이블 0건.
- [ ] **G5-T02** 트렌드 중복(HIDDEN 포함), Source 중복, Category 비활성 시 Batch 전체 Rollback.
- [ ] **G5-T03** 2개 이상 DB 연결/Worker 동시 요청, Named Lock·Journal 상호작용.
- [ ] **G5-T04** Commit·Rollback·연결 유실·Journal 기록 오류 강제주입, 결과 불명확 시 영속 HOLD.
- [ ] **G5-T05** B-Lite 인증키/네트워크·DB 접속 대상/계정 실제 권한 및 Demo Seed 우회 거부.
- [ ] **G5-T06** 승인·철회 경합/스냅샷 내용 변경/관측 시각 정확성.
- [ ] **G5-T07** 기존 GET API·Frontend Source Card 및 모바일 캐시 회귀 확인.

## 8. 권고 구현 순서

1. **보완안 검토·조건부 승인:** 위 4개 영역의 책임·최소 배포 프로필 승인. `FR-B01~05`는 근거 확보 전 미완료로 둔다.
2. **Phase 0 (차단 사실 확인):** v0.3 원문과 독립 관측 증거 형식, Journal·승인 변경 보호·DB 권한과 관리자 네트워크 배포 환경 확인. A1 v0.2의 해시 계산은 기존 검토 기록을 활용하되 **원본이 필요한 변경이나 검증에는 다시 확인**하고, 원본 부재를 PASS로 처리하지 않음.
3. **Phase 1 (격리 기술 구현):** A1 v0.2 승인 원본을 변경하지 않는 P4 참조 Envelope v1 → P4 Core Writer + Transaction + 테스트 DB. 합성 데이터만 사용.
4. **Phase 2 (실행 통제):** 오프라인 승인 변경 절차 + Journal + Named Lock + 운영자 키/DB 대상 검증.
5. **Phase 3 (B-Lite API):** 동기 실행, 응답·오류 계약, 이중 Worker 재요청 차단.
6. **Phase 4 (G5 종합 검증):** 장애 주입, 우회 경로, 모바일 API 캐시, 실제 Gate와 격리 테스트의 구분.

## 9. 이번 DRAFT에서 변경하지 않는 결정과 후속 범위

- **P4-DEC-01~20 전부 확정 유지.** 핵심 도메인 정책 또는 DEC-13(신규 DB 감사 테이블 미도입), DEC-19(영속 HOLD)를 임의로 수정하지 않는다.
- 기존 `GET /api/trends*`, Taxonomy v1.0.1, P0~P3 v1.1 FROZEN은 유지한다.
- 실제 G0/G4/G5/G6 승인·승인자 증거 확보, Google RSS 접근 권한, 실 운영 DB 초기 콘텐츠 정합성은 **별도 완료 조건**이다. 미확인 내용을 PASS로 기재하지 않는다.
- **제외:** 관리자 승인 UI, 자동 수집/스케줄러, 비동기 게시 큐, 고급 감사 조회, 다중 서버/파일시스템, 자동 재시도, P3→Writer 자동 연결, 데이터 마이그레이션(필수 안전성 근거 없이), 자료 원문 저장.

## 10. 보완안 검토 결론

**권고:** ‘B-Lite 실행 지시 + 별도 실행 환경의 독립 Writer(A1) + 단일 호스트 보호 Journal·구조화 로그(B2) + 공통 승인 변경 보호 구간 + 별도 관리 진입점 + **A1 v0.2 원본 보존형 P4 Batch v1 참조 계약**’을 **조건부 DRAFT**로 유지한다. 우선 격리 테스트 DB에서 합성 승인 철회·HOLD·복구를 검증하며, 실제 게시 Gate를 HOLD로 남긴다. 차단 근거를 확보하기 전 전체 FROZEN·실제 G4/G5/G6 PASS를 선언하지 않는다.

**중요:** 별도 DB 감사 테이블을 만들지 않겠다는 정책이 커스텀 파일형 실행 DB를 과도하게 복잡하게 만든다면, DEC-13만 최소 변경 안건으로 다시 제시하는 편이 설계 품질에 유리하다. 복잡도를 숨기기 위해 안전성을 포기하거나 감사 로그를 영속 Journal인 것처럼 주장하지 않는다.

**최종 상태:** DEC-01~20 유지 / A1+B2 및 격리 DB 선검증·실운영 HOLD 사용자 방향 결정 / P4 v1 참조 계약 세부 DRAFT / P4 전체 NOT FROZEN / G5 P1 전체 및 실제 G4·G5·G6 HOLD / **이번 GitHub 변경은 신규 DRAFT 문서 1개에 한정**, 기존 v0.1·코드·DB·Compose·FROZEN 정책·Notion 불변.