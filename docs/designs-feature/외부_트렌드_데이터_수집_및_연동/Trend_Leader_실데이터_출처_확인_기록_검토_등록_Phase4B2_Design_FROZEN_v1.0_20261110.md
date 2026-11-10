# Trend Leader — 실데이터 출처 확인 기록 검토·등록 Phase 4B-2 최소 계약 FROZEN v1.0

> 요구사항 추적 ID: `FR-B02b`
>
> **상태: FROZEN — Phase 4B-2 로컬 검토·보호 등록·철회 계약에 한정 / 미구현 / 운영 Evidence 미승인 / G5·G6 HOLD**  
> 작성 기준: 2026-11-10 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`, 원격 `dev` HEAD `8b427dc7af92c4ff15e1a967ea01cc79bfde4edd` (작성 시 읽기 전용 확인)  
> 범위: 기존 Phase 4A 수동 관측 기록과 Phase 4B-1 검토 후보에 대한 **Windows 로컬 수동 검토·권한 확인·보호 등록·철회**만 다룬다.  
> **승인 범위:** 2026-11-10 최종 검토 후 동결·별도 개발 브랜치 반영 지시에 따른 Phase 4B-2의 최소 계약만 동결. 기존 4A·4B-1 FROZEN 파일과 P4/Gate 정책은 수정하지 않는다. 구현 완료 및 운영 등록·게시 승인이 아니다.

## 0. Final Review 판정 및 확인 근거

**판정: Phase 4B-2 최소 계약 동결.** Windows 기초 실측으로 로컬 CLI 방식을 선택할 근거를 확보했다. 보호 등록 코드, SID 허용 목록, 운영 ACL 및 보호 백업은 아직 구현·검증하지 않았다. 본 동결은 입력·출력·상태·저장·철회 및 Fail-Closed 규칙을 고정하며, 구현 완료나 운영 Gate 승인이 아니다.

### 0.1 확인된 사실

- 원격 `dev` HEAD는 위 SHA이고, Phase 4A·4B-1 v1.0 FROZEN 문서와 현재 읽기 전용 `review-candidate` 구현이 존재한다.
- 현재 4B-1의 `review_candidate()`는 기존 `_load_verified_observation()`에서 검증된 기록을 투영해 `REVIEW_CANDIDATE_HOLD`, `review_result=HOLD`, `publish_authorization=NONE`을 반환한다. 파일/DB/네트워크 쓰기는 하지 않는 계약이다.
- 사용자 Windows 환경: 개인 전용 계정, SID 조회 및 Windows 인증 확인, 일반 권한 실행 가능. C/D는 `Disk 0` NVMe, E는 `Disk 1` NVMe로 인식되고 C/D/E는 NTFS로 조회되었다.
- 합성 ACL 시험: 상속 해제, 지정한 현재 사용자/SYSTEM/Administrators SID 규칙 존재, 예상 밖 규칙 0, 일반 권한 파일 쓰기 성공, 시험 디렉터리 정리 성공.
- 합성 C: → E: 백업 및 E: → C: 복원: 두 SHA-256 대조 성공, 원본/백업/복원 파일 생성 성공, 시험 폴더 3개 정리 성공. E: 임시 백업 디렉터리의 상속 상태는 `True`, 규칙 수는 8개로 보고되었으므로 운영용 ACL은 **미입증**이다.
- 위 실측은 사용자 제공 실행 출력 근거이며 이 문서 작성 중 Windows 명령·자동 테스트를 다시 실행하지 않았다.

### 0.2 기존 문서의 시간성 및 충돌 정리

- FR-B02b v0.1/v0.2 DRAFT의 “실제 관측 미생성”은 **2026-11-09 당시 서술**이다. 이후 4A의 실제 로컬 관측 생성 보고와 4B-1 구현/동결이 이루어졌으므로 현재 상태로 사용하지 않는다.
- 4A `confirmed_at_utc`는 정확한 `YES` 입력 직후의 **로컬 시계 기반 사용자 진술 시각**이고, 4A `record_created_at_utc`는 로컬 JSON 구성 직전 시각이다. 4B-2가 이들의 이름·의미를 바꾸거나 `observed_at`/DB `collected_at`으로 자동 변환하지 않는다.
- 4A는 `observer_ref=UNVERIFIED_LOCAL_OPERATOR`, `actor_assurance=UNVERIFIED`를 고정한다. 사후 검토자 SID 인증은 4A 관측자 신원을 소급 인증하지 않는다.
- 4B-1은 읽기 전용 검토 후보까지만 소유한다. 4B-2의 검토 결과·보호 저장소·철회 기능을 4B-1에 혼입하지 않는다.
- P4 Addendum v0.2는 **전체 NOT FROZEN**이며 `observation_evidence_ref`/Writer 계약은 제안 상태다. 운영 Gate v0.3의 G5/G6는 HOLD이다. Phase 4B-2의 보호 등록 성공만으로 해당 상태를 바꿀 수 없다.

## 1. 문제 · Goal · Non-goal

**문제:** 검증된 4A 로컬 관측 기록과 4B-1 검토 후보는 아직 승인된 검토자, 보호 원본·백업, 수락·보류·거절 및 철회 사건과 묶여 있지 않다. 읽기 전용 기술 정합성을 실운영 Evidence 수락 또는 게시 허가와 혼동할 위험이 있다.

**Goal:**

1. 사용자 요청 시 기존 A1 ZIP + 4A 관측 기록을 **다시 검증**하고, 같은 바이트를 검토 및 보호 등록에 사용한다.
2. Windows 프로세스 보안 컨텍스트에서 현재 계정 SID를 읽고 **보호된 검토자 허용 목록**을 대조한다.
3. 검토자는 승인된 내용의 표시값을 확인한 다음 명시적으로 `ACCEPTED`/`HOLD`/`REJECTED`를 결정한다. 자동 수락 및 기존 입력값 재입력은 금지한다.
4. A1 ZIP, `observation.json`, `index.json`의 등록 시점 바이트 및 다이제스트, 결정 사건을 Git 작업 트리 외부 보호 저장소에 보관하고 별도 디스크 보호 백업에서 복원 가능한지 확인한다.
5. 철회는 별도 사건으로 기록하고 유효한 등록 참조를 차단한다. 원본·과거 판단은 수정하지 않는다.

**Non-goal:** 신규 DB/REST API/관리자 UI/클라우드/스케줄러, 다중 호스트 지원, 암호학적 서명·독립 공인 타임스탬프, 원문 HTTP/스크래핑, Google RSS 호출, 운영 P4 Writer/Journal/배포·DB DML, G4/G5/G6 실제 승인, 외부 사이트 권리 자동 판정, 완전한 악의적 관리자 방어.

## 2. 설계 선택과 신뢰 한계

| 대안 | 이점 | 한계 | 판단 |
|---|---|---|---|
| **A. 기존 Windows CLI + 로컬 보호 디렉터리 + E: 백업** | 이미 검증된 NTFS/ACL/파일 복사 환경 재사용, 인프라 추가 최소 | 같은 PC·관리자 계정 침해 시 동시 변조/손실 위험, P4가 자동으로 접근하지 못함 | **4B-2 최소 계약 후보로 채택** |
| B. 운영 서버/별도 관리자 서비스 | 중앙화·권한 분리·Writer 조회 확장에 유리 | 배포·네트워크·운영 권한·추가 테스트 필요 | 4B-2 범위 밖. P4 인계 시 재검토 |

**위협 모델:** 신뢰된 개인 Windows 운영자가 사용하되, 우발적 변경·다른 일반 사용자 접근·입력 교체·저장 실패·불일치·철회를 감지하고 차단한다. 동일 계정이 관리자로 승격될 수 있으므로 로컬 ACL·SHA-256만으로 검토자 본인의 악의적 변조 또는 관리자 침해에 대한 독립 증명을 주장하지 않는다. C/E 두 디스크가 같은 PC에 있는 백업은 별도 디스크 장애 대응 후보이지 오프사이트/오프라인 독립 백업이 아니다.

## 3. 책임 분리

| 책임 | 소유 | 금지 범위 |
|---|---|---|
| A1 ZIP·승인 스냅샷 검증 | 기존 `fr_b02b_a1_adapter.py` | A1 내용·`content_ref` 변경 금지 |
| 4A 관측 기록 바인딩·무결성 검증 | 기존 `fr_b02b_observation.py` | `HOLD/NONE`, 관측자 미인증 기록 변경 금지 |
| 4B-1 검토 후보 출력 | 기존 `fr_b02b_review_candidate.py` | 쓰기·검토 승인·권한 판단 금지 |
| **4B-2 검토 정책** | 신규 소규모 Review Service 함수/모듈 | 게시권한·G4 권리 판단 금지 |
| **Windows 실행 계정/허용 목록** | 신규 OS 인증·Authorization Adapter | 수동 입력한 `reviewer_ref`만 신뢰 금지 |
| **보호 저장·조회·철회** | 신규 Protected Evidence Store 모듈 | 원본 덮어쓰기·자동 복구를 통한 묵시적 승인 금지 |
| CLI 명령 및 사람 검토 입력 | 기존 `fr_b02b_cli.py`에 새 경로 최소 추가 | 로직 전체를 `run_cli`에 혼합 금지 |
| P4 참조 해석·시간 매핑·게시 결정 | **후속 P4** | 4B-2에서 대리 수행 금지 |

## 4. 입력 · 수동 검토 · 결과 계약

### 4.1 입력

- 명시적인 `--zip`, `--record-dir`만으로 기존 4B-1 대상 선택. 최신 파일 자동 탐색·와일드카드 대입 금지.
- 보호 저장소 루트·백업 루트·허용 목록은 **사전 관리되는 로컬 비공개 설정**에서 가져온다. CLI 사용자가 실행마다 임의 경로·허용 SID를 넣어 보안 경계를 우회하지 않는다. 실제 경로·설정 파일 형식은 구현 시 환경 확인 후 고정하되 검증되지 않은 경로를 기본값으로 암묵 사용하지 않는다.
- 입력 A1 ZIP·관측 기록은 읽기 전용. 4B-1의 기존 검증 결과 출력 JSON만 믿지 말고 등록 시 재검증한다.

### 4.2 검토자 인증·권한

- 실제 Windows 실행 프로세스의 보안 토큰에서 **현재 사용자 SID**를 획득한다. SID 없음/인증 실패·허용 목록 미등록/비활성·목록 손상/접근 경계 불명확 시 `BLOCKED`.
- 역할은 최소 `EVIDENCE_REVIEWER` 하나를 사용한다. 검토·수락·보류·거절 및 철회 권한을 이 역할에 귀속시키는 **MVP 단일 역할** 후보이다. 허용 목록을 수정·승인하는 운영 책임은 일반 검토 사건과 분리해 기록한다.
- 공유 Windows 계정과 환경변수 `USERNAME`, 임의 `--reviewer`, Git 사용자명은 개인 신원 증명의 근거가 아니다.
- 관측자·검토자가 같은 사람인 것은 허용한다. 동일인 진술은 추가 기록할 수 있지만, **4A `UNVERIFIED_LOCAL_OPERATOR`가 인증되었다고 소급 표기하지 않는다.**
- 일반 권한 CLI 사용을 기본으로 하며 관리자 상승은 ACL 초기 구성·관리 업무에 한정한다. 이는 실무 사고를 줄이는 운영 규칙일 뿐 동일 관리자 계정으로부터 독립적인 보안 경계를 보장하지 않는다.

### 4.3 사용자 흐름

1. 4B-2 명령이 기존 4A/4B-1 검증 로직으로 입력의 동일성·무결성·HOLD/NONE을 재검증한다.
2. 보호된 허용 목록과 Windows SID를 검증한다. 원본 승인 제목·요약·원문 URL·기존 확인 시각·관측자 미인증 수준을 읽기 전용으로 보여준다.
3. 검토자가 **`ACCEPTED`, `HOLD`, `REJECTED` 중 하나를 명시적으로 선택**한다. 기본값으로 `ACCEPTED`를 선택하지 않는다. 임의의 필드나 해시 재입력을 요구하지 않는다.
4. 결정 시각 `reviewed_at_utc`를 로컬 UTC 시계에서 신규 측정한다. 로컬 시계 이상·시간 역행 시 차단한다. 이는 독립 인증 시각이 아니다.
5. 검증된 **동일 바이트 집합**(A1 ZIP, 4A 기록/인덱스)을 보호 스테이징에 보존한다. 확정 전후 저장된 바이트, SID 권한 경계, 등록 연결 정보, C/E 백업 바이트를 확인한다.
6. 보호 등록 성공 후 **4B-2 전용 로컬 논리 ID**를 부여·반환한다. `ACCEPTED` 이외 결과는 운영 증거 후보로 사용 금지. 모든 결과의 `publish_authorization=NONE`은 유지한다.

### 4.4 등록·결정 상태

- `ACCEPTED`: 사람이 **관측 진술과 기존 승인 자료의 연결·검토 기록을 수락**했다는 의미만 갖는다. 원문에 대한 독립 사실 확인·이용 권리·G4/G5/G6 PASS가 아니다.
- `HOLD`: 사람의 검토 보류; 이후 명시적 재검토만 허용. 자동 승격 금지.
- `REJECTED`: 사람의 거절; 후속 재검토 시 별도 결정 사건 필요. 기록 덮어쓰기 금지.
- `BLOCKED`: 인증·무결성·권한·저장·복원 검증 오류. 사람의 `REJECTED`와 다르다. **성공/유효 등록 참조 없음**.
- `REVOKED`: 이전 수락을 무효화하는 신규 철회 사건. 이전 수락·증거는 보존한다. 기존 등록 자동 복원/재수락 금지.

**운영 논리 ID 및 JSON 계약은 §5, 공개 CLI 계약은 §8.1에 정의한다.** 이는 4A `LOCAL-OBS-...`, G4 `E-G4-*`, P4 제안 `observation_evidence_ref`와 서로 다른 식별 공간이다.

## 5. 보호 기록·참조 스키마 v1.0 (4B-2 전용, 아직 미구현)

**기본 단위:** 1개의 등록 ID에 1개 A1 ZIP + 1개 4A `observation.json` / `index.json` + 명시적인 검토 판단을 결속한다. `registration_id` 형식은 `REG-OBS-<uuid4-hex>`이다. 사용자가 파일 경로·URL을 논리 ID로 제공할 수 없다. 이 ID는 **P4 `observation_evidence_ref`로 자동 승인된 ID가 아니다.**

### 5.1 등록 매니페스트 고정 필드

보호 원본의 `registration.json`은 `schema=FR_B02B_PROTECTED_REVIEW_V1`이며 **정확히** 다음 필드를 포함한다. 모든 값은 비어 있지 않은 문자열을 원칙으로 하되 `decision_reason`은 `ACCEPTED`에서만 빈 문자열 허용, `supersedes_registration_id`는 이전 결정이 없으면 JSON `null`을 허용한다. 미정의 키·누락 키·잘못된 타입·중복 JSON 키를 차단한다.

| 필드 | 고정 의미 및 검증 조건 |
|---|---|
| `schema` | `FR_B02B_PROTECTED_REVIEW_V1` |
| `registration_id` | `REG-OBS-<uuid4-hex>` 신규 ID; 추측한 증거 ID 재사용 금지 |
| `local_evidence_id` | 검증된 기존 `LOCAL-OBS-...` 값 |
| `a1_archive_sha256`, `observation_sha256`, `index_sha256` | 보관된 **세 입력 파일 각각**의 실제 UTF-8/ZIP 바이트 SHA-256(`sha256:` + 소문자 64자리 hex) |
| `trend_ref`, `content_ref`, `review_evidence_id`, `source_url` | 검증된 4A/4B-1 연결 값과 엄격 일치; 사람의 재입력 금지 |
| `event_kind`, `observation_method` | 4A의 고정 `MANUAL_SOURCE_COLLECTION`, `HUMAN_BROWSER_ATTESTATION` |
| `confirmed_at_utc`, `record_created_at_utc` | 원본 4A 시각 **원문 그대로** 보존 |
| `observer_ref`, `actor_assurance` | `UNVERIFIED_LOCAL_OPERATOR`, `UNVERIFIED` 그대로 보존 |
| `reviewer_sid` | Windows 현재 프로세스 토큰에서 획득한 실제 SID. 비공개 자료 |
| `reviewed_at_utc` | 검토자 판단 직후의 로컬 UTC 시각. 독립 시간 인증 아님 |
| `review_result` | `ACCEPTED`, `HOLD`, `REJECTED` 중 명시적 선택값 |
| `decision_reason` | 자체 작성 근거. `HOLD`/`REJECTED`는 비공백 필수; `ACCEPTED`는 빈 문자열 허용. 최대 500자. 원문 복제·PII·비밀 배제 |
| `registration_recorded_at_utc` | 매니페스트 구성 시점 로컬 UTC. 두 디스크의 기록 완료 시각으로 오인 금지 |
| `supersedes_registration_id` | 이전 `HOLD`/`REJECTED` 판단을 **명시적으로 재검토**하는 경우 그 이전 `REG-OBS-...` ID, 아니면 `null`. 철회된 ID는 참조 불가 |
| `publish_authorization` | 항상 `NONE` |

- 매니페스트는 **UTF-8, `json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` + 단일 LF**를 사용한다. 등록·철회 파일은 실제 저장 바이트의 SHA-256으로 검증한다. 이 규칙은 **A1 `content_ref` 계산을 변경하지 않는다.**
- `reviewed_at_utc`, `registration_recorded_at_utc`는 offset-aware UTC ISO 8601이며 4A `record_created_at_utc`보다 빠르거나 `registration_recorded_at_utc`가 `reviewed_at_utc`보다 빠른 경우 차단한다. 로컬 시계 보증 범위를 넘는 사실·시간은 주장하지 않는다.
- 저장 위치·Windows 실제 SID와 같은 **환경별 값**만 사전 보호된 설정으로 주입한다. 위 필드명·판정 의미·CLI 공개 명령은 구현 중 임의 변경하지 않는다.

### 5.2 보호 저장소의 논리 레이아웃

등록 단위마다 `registrations/<registration_id>/` 아래에 `a1_archive.zip`, `observation.json`, `index.json`, `registration.json`, `registration_complete.json`을 둔다. 철회 시 같은 ID의 `revocations/<event_id>.json`을 별도로 추가한다. `registration_complete.json`에는 고정 `schema=FR_B02B_REGISTRATION_COMPLETE_V1`, `registration_id`, `registration_sha256`(매니페스트 실제 바이트 해시), `status=COMPLETE`를 기록한다. 파일명이 유일하고 허용되지 않은 추가 파일·다이제스트 차이는 차단한다(철회 사건 디렉터리 및 통제된 임시 스테이징 제외).

- `registration_complete.json`은 **두 보호 사본 C/E의 필수 원본·검토 매니페스트를 확인한 후** 각각 기록한다. 두 디스크를 하나의 원자적 트랜잭션으로 취급하지 않는다. C/E 양쪽 완료 표식과 원본 바이트·ACL·철회 이력을 재검증한 경우에만 `PROTECTED_REVIEW_RECORDED`가 유효하다.
- 읽기/재실행/등록 반환 전 한쪽이라도 없거나 불일치하면 `BLOCKED/HOLD`; 백업만을 사용한 자동 원본 교체·무조건 복구·자동 `ACCEPTED` 금지. 같은 머신 관리자에 의한 두 사본 동시 변조는 보호 범위 밖이다.
- 별도의 중앙 변경 가능 인덱스는 필수로 만들지 않는다. **소량 단일 호스트 MVP**에서는 보호된 등록 디렉터리와 안전하게 검증된 ID/연결 기록으로 조회하며, 같은 `local_evidence_id` 작업은 보호된 단일 호스트 배타 구간에서 처리한다. 잠금 잔여·중복 이력 충돌은 수동 조사 HOLD.

### 5.3 철회 사건 고정 필드

`revocations/<event_id>.json`은 `schema=FR_B02B_REVOKE_V1`, `event_id=REV-OBS-<uuid4-hex>`, `registration_id`, `registration_sha256`, `revoker_sid`, `revoked_at_utc`, `reason`, `publish_authorization=NONE`을 필수로 가진다. 지정된 유효 `ACCEPTED` 등록의 원본 지문에 결속한다. 사유는 비공백의 자체 작성 짧은 문장이고, 철회 이벤트는 원본을 수정하지 않는 **추가 전용** 기록이다.

- 두 보호 사본의 철회 이벤트 집합/바이트/등록 연결을 매번 대조한다. 한쪽의 철회 쓰기만 성공하거나 철회 기록을 읽을 수 없다면 **현재 수락 참조를 사용 불가(HOLD)**로 처리한다. 양쪽 철회 기록 검증 전에 철회 완료 성공을 출력하지 않는다.
- 이미 철회된 ID를 다시 `ACCEPTED`로 전환하는 명령은 제공하지 않는다. 원래 철회 사건은 오류·동시성·재실행 시에도 삭제하지 않는다.

## 6. 저장 · 백업 · 원자성 · 중복 정책

### 6.1 실측 기반 저장 후보

- 원본 저장소: Windows `LocalAppData`를 **상위 경로 후보**로 검증했으나 실제 보호 루트는 미생성·미확정. Git 작업 트리/입력 ZIP 경로 외부여야 한다.
- 백업: Windows E:가 C:와 다른 `DiskNumber`임을 확인했고 합성 백업/복원 해시가 일치했다. 그러나 E: **실운영 ACL은 미설정**이고, 동일 PC 관리자 계정/악성코드에 의한 동시 손상 가능성이 있다.
- 새 보호 루트와 E: 백업 루트는 접근을 명시적으로 제한한다. ACL 상속이 활성화되어 불필요한 `Users` 접근을 허용하거나, 허용 목록/저장소를 비인가자가 바꿀 수 있으면 **등록 중단**한다.
- 실제 루트의 재분석 지점·심볼릭 링크·부모 경로·Git 작업 트리 여부 및 실행 계정과 디스크 번호·쓰기 가능 여부를 등록 시 재확인한다. 경로가 불명확하면 Fail Closed한다.

### 6.2 저장 성공의 최소 불변조건

1. 현재 요청 대상의 4A ZIP/JSON/인덱스를 일관된 바이트 스냅샷으로 검증하고 등록에 사용한다. 4B-1 검증 후 원본 파일을 무검증으로 다시 읽지 않는다.
2. 등록 프로세스는 단일 호스트에 한정하고 **동일 `local_evidence_id` 등록을 직렬화**한다. 완료 여부 확인 없이 새 ID를 자동 발급하여 경쟁 결과를 숨기지 않는다.
3. 보호 루트 내 안전한 스테이징에서 파일을 생성하고, 원본·메타데이터·수락/보류/거절 사건을 지문으로 연결한다. 저장된 원본과 검증 바이트가 일치해야 한다.
4. C: 보호 등록본과 E: 보호 백업본의 필수 파일·해시를 검증하고 **백업의 복원 가능성 검증 기준**을 충족해야 유효 등록을 반환한다. 단일 로컬 파일 쓰기·개별 rename 성공만으로 양 디스크 원자성을 주장하지 않는다.
5. 중간 실패·충돌·권한 변경·시각 이상·해시 차이·부분 백업이면 성공 반환 금지. 확인되지 않은 잔여 디렉터리는 **수동 조사 대상 HOLD**이며 자동 인덱싱/승격 금지.
6. 등록 완료 후 원본 파일/검토 결정은 덮어쓰지 않는다. 변동 발생 시 탐지하고 사용을 차단한다. 한 저장소의 파일만 바꿔 전체 해시를 다시 생성하는 자동 복구 금지.
7. 허용 목록·검토 기록·등록 인덱스·철회 기록 모두 비공개로 보관하고 실제 SID, 개인 경로, 비밀을 공개 GitHub에 업로드하지 않는다.

**구현상 주의:** C:와 E: 간 복사 전체가 하나의 파일시스템 트랜잭션이 되는 것은 아니다. “등록 성공” 표식은 두 사본의 검증 이후에만 노출하며, 크래시·재시작·동시 요청에서 **부분 확정 상태를 성공으로 오인하지 않는 복구/재대조 절차**를 구현·시험해야 한다. fsync·rename만으로 전원 손실 상황의 완전한 내구성을 주장하지 않는다.

### 6.3 중복과 이력

- 동일 `local_evidence_id` + 동일 세 입력 파일 다이제스트로 이미 유효 `ACCEPTED` 등록이 있으면 새 ID를 만들지 않고 기존 등록 결과를 C/E 양측 재검증 후 반환한다.
- 동일 ID에 다른 증거/승인 내용/해시를 붙이면 `BLOCKED`. 원래 등록을 덮어쓰지 않는다.
- 기존 `HOLD`/`REJECTED`의 판단 변경은 다시 `review-register`에서 사람이 새 판단을 명시해 **새 등록 ID**를 발급하고 `supersedes_registration_id`로 이전 결정을 연결한다. 승인 자동 승격은 금지하고, 같은 관측 ID의 이력이 분기·모호하면 `BLOCKED`한다. 중복 해소와 이력 연결은 단일 등록 보호 구간에서 처리한다.
- 철회된 동일 등록은 자동 재활성화할 수 없다. 필요 시 새 4A 관측 사건·검토를 거쳐 별도의 등록 절차를 시작한다(새로운 실제 관측 및 확인에 따른 시간 사용).

## 7. 철회 · 재검증 · 시간 의미

1. 지정된 검토 권한을 가진 실행 계정만 철회를 요청한다. 다른 G4/G6 철회 절차와 혼동하지 않는다.
2. 철회는 `registration_id`, 대상 등록 지문, 철회자 SID, 철회 UTC 시각, 사유를 지닌 **별도 신규 사건**으로 기록한다. 원본 수락 문서·4A 관측 기록·A1 ZIP을 덮어쓰지 않는다.
3. 참조 조회는 등록 스냅샷의 `ACCEPTED` 여부뿐 아니라 **최신 유효 철회 사건**도 확인한다. 철회 기록 누락·손상·조회 실패·이력 경합 또는 상태 불명확 시 **사용 차단(HOLD)**한다.
4. 철회 이후 재등록/묵시적 재수락 금지. 더 최근 G4 승인 변경·원문/링크 사실 변화는 4B-2 `ACCEPTED`와 무관하게 P4에서 별도 검증하여 HOLD할 수 있다.
5. `confirmed_at_utc`는 4A의 `YES` 직후 로컬 시계 시각, `reviewed_at_utc`는 4B-2 판단 시각, `registration_recorded_at_utc`는 등록 매니페스트 작성 시각, `revoked_at_utc`는 철회 사건 기록 시각이다. 이 네 시각을 G4 `approved_at`, 외부 `pubDate`, P4 DB `collected_at`으로 자동 대체하지 않는다.

## 8. CLI·오류·테스트 계약

### 8.1 신규 CLI 공개 계약 (명칭·입력·출력 동결, 아직 미구현)

다음 명칭과 필수 옵션은 **4B-2에서 신설할 공개 CLI 계약**이다. 기존 명령을 개명하지 않는다. 실행 파일 내부 구조와 테스트 전용 주입 지점은 구현 단계에서 결정할 수 있지만 공개 명령 및 상태 문자열 변경은 별도 설계 변경으로 처리한다.

```powershell
# 기존 A1 ZIP + 기존 4A 관측 폴더를 명시해 사람의 검토 결정 및 보호 등록
python .\fr_b02b_cli.py review-register --zip '<A1 ZIP 경로>' --record-dir '<LOCAL-OBS 폴더>'

# 보호된 등록 ID의 현재 유효성·철회 상태와 원본/백업 바이트를 읽기 전용 검증
python .\fr_b02b_cli.py review-verify --registration-id '<REG-OBS ID>'

# 권한 있는 계정의 별도 철회 사건 생성(사유 입력 필수)
python .\fr_b02b_cli.py review-revoke --registration-id '<REG-OBS ID>'
```

- `review-register`는 허용된 SID 검증 및 4B-1/4A 입력 재검증 후 사람에게 `ACCEPTED`, `HOLD`, `REJECTED`를 명시적으로 선택하게 한다. **수락 기본값/무인 자동 수락/추가 `YES` 입력은 없다.** 보류·거절 사유는 필수다.
- 검증된 정상 등록 응답의 최소 필드: `status=PROTECTED_REVIEW_RECORDED`, `registration_id`, `local_evidence_id`, `review_result`, `publish_authorization=NONE`. `ACCEPTED`는 검토 수락뿐이며 **P4 사용 허가가 아님**을 출력한다.
- `review-verify`는 `status=PASS_PROTECTED_LOCAL_INTEGRITY_ONLY`, `registration_id`, `effective_review_state=ACCEPTED|HOLD|REJECTED|REVOKED`, `publish_authorization=NONE`을 반환한다. **무결성 PASS와 현재 유효한 수락은 별개의 값**이다.
- `review-revoke`는 검증된 철회 사건 등록·백업 후 `status=REVOKED_LOCAL_REGISTRATION`, `registration_id`, `publish_authorization=NONE`을 반환한다. 이미 철회된 대상의 반복 요청은 안전한 기존 결과를 재검증하고 반환할 수 있으나 새로운 수락을 생성해서는 안 된다.
- 세 명령 모두 정상적인 등록/검토/철회 작업 성공 시 종료 코드 `0`, 입력·신원·무결성·ACL·저장/복원 검증 실패 시 `1` 및 `BLOCKED: <원인 범주>`를 사용한다. 명시적 사용자 취소·인자 사용 오류는 `2`로 구분한다. 기존 CLI의 사용자 개인 경로·SID·비밀이 오류 메시지에 유출되지 않도록 한다.
- 원본 A1 ZIP과 4A 기록 경로는 **명시적으로 선택**하되, 검증된 출처 URL·해시·시각·증거 ID·검토자 SID를 사용자에게 다시 입력시키지 않는다. 원본 승인 제목·요약 등은 기존 A1 검증 결과에서 보여준다.
- `review-verify`/`review-revoke`는 경로를 새로 입력받지 않고 보호 저장소 설정에서 ID를 내부 조회한다. 조회 전 인증·허용 목록·경로 보호 상태를 검사한다.
- 기존 4A의 정확한 대문자 `YES` 정책과 4B-1 `review-candidate` 출력·읽기 전용 정책은 변경하지 않는다.

### 8.2 우선 검증 시나리오 (기능 완료 전에 필수)

| ID | 반례 또는 정상 경로 | 수용 기준 |
|---|---|---|
| B42-01 | 합성 적격 A1·4A 기록과 승인 SID | 명시적 사람 수락 후 검증된 보호 등록 생성. 원본과 `HOLD/NONE` 불변 |
| B42-02 | SID 미확인·허용 목록 외 사용자·손상/비인가 수정된 허용 목록 | `BLOCKED`, 수락·유효 등록 0건 |
| B42-03 | 원본 ZIP/4A JSON/인덱스 교체·해시 변경·재확인 사이 변경 | `BLOCKED`, 원본 수정/다른 바이트 등록 0건 |
| B42-04 | 판단 없음·`HOLD`·`REJECTED` 선택 | 자동 `ACCEPTED` 금지; 판단 사건·실패 상태 구별 |
| B42-05 | C: 또는 E: 저장 실패·백업 누락·ACL 과다 허용·부분 쓰기 | 등록 성공 0건, 잔재 HOLD, 안전 재검증 |
| B42-06 | 동일 ID 동일 바이트 재등록 / 동일 ID 다른 바이트 / 두 프로세스 경쟁 | 정당한 기존 ID 재사용 또는 충돌 BLOCK; 중복 수락 0건 |
| B42-07 | 허용된 계정의 철회·손상된 철회 기록·철회 후 재사용 | 별도 철회 사건 보존, 참조 조회 차단, 자동 재활성화 금지 |
| B42-08 | C/E 백업 복원·해시/참조 연결·ACL 실환경 검증 | 합성 데이터의 독립 디스크 복원 성공, 오류 시 HOLD; 운영 경로는 별도 증명 |
| B42-09 | 기존 Phase 4A·4B-1 전체 회귀 | 공개 상태·출력·명령·원본 바이트 변경 없음, 새 테스트 포함 회귀 PASS |
| B42-10 | 4B-2 전체 경로 | 게시 권한 NONE·G5/G6 HOLD, P4 Writer/DB DML·HTTP 요청·RSS/외부 AI 호출 0건 |

### 8.3 구현 완료와 운영 인계 조건

- **설계 FROZEN:** 이 문서의 공개 CLI/스키마·상태·안전·검증 계약을 동결. 구현·실운영 PASS 아님.
- **기능 구현 완료:** 위 B42 핵심 반례, 기존 회귀, 실제 Windows 계정/SID 허용 목록·실제 운영 후보 경로의 접근통제와 백업/재시작 복구 시험을 통과하고, 4A·4B-1 계약이 유지됨을 확인. 자동 테스트 통과 보고와 사용자 수동 시험 결과를 구분한다.
- **운영 P4 인계:** 장래 Writer 환경이 보호된 등록 ID를 읽기 전용으로 해석하고 각 원본·인덱스·철회·G4/G6 상태를 독립 검증해야 한다. P4 `observation_evidence_ref` 형식, 수집 시각 매핑 및 Writer 배포 권한은 **별도 계약으로 결정**한다. 따라서 4B-2 완료만으로 G5/G6 PASS 또는 게시 1건을 주장하지 않는다.

## 9. 납기 대응 구현 순서

1. **AuthZ + 검토 결정:** 개인 Windows 계정의 실제 SID 획득과 비공개 허용 목록 검증. 합성 입력으로 정상/거절/보류/차단 구현.
2. **보호 원본 등록:** 4A/4B-1 검증 재사용, 원본 바이트 보호 스테이징, 제한 ACL 검사 및 복사본 검증.
3. **별도 E: 백업과 재검증:** 보호 백업·부분 실패·복구/재시작 조회 시험.
4. **철회와 조회 차단:** 원본 유지, 신규 철회 사건·유효성 판정, 중복·경합 최소 테스트.
5. **회귀 및 Windows 통합:** 4A/4B-1 테스트·Ruff·실제 PC의 합성 자료로 정상 및 실패 검증. 실제 승인 ZIP은 공개 테스트/커밋에 추가하지 않는다.

**Feature Freeze 이후 범위 확대 금지:** 관리자 UI/클라우드/서버 자동 동기화/DB 감사 테이블/다중 호스트/별도 관측 브라우저 플러그인/공인 타임스탬프/복잡한 권한 역할 계층은 Post-MVP로 분리한다. 실제 취약한 ACL·누락 백업과 같이 필수 안전성을 막는 결함은 후속으로 숨기지 않고 기능 완료를 보류한다.

## 10. 이번 Final Review에서 구현·운영 검증으로 남기는 것

- 실제 운영 루트 경로 및 백업 경로, 보호 허용 목록 파일의 물리 위치·관리자·ACL. 현재 LocalAppData와 E:는 **후보 환경 검증**만 완료했다.
- 허용 SID 목록의 승인·변경 절차 및 보안 사고 시 계정 비활성화 책임자. 단일 개인 관리자 계정의 독립 승인 보증은 하지 않는다.
- 보호 등록의 파일 단위 원자적 교체·Crash Recovery·동일 ID 배타 구간·실제 Windows 파일 처리 구현 가능성. 본 문서의 **고정 CLI/JSON/철회 계약**대로 합성 장애 테스트로 검증한다. 불가능하면 임의 축소하지 않고 변경 검토한다.
- E:가 다른 DiskNumber임은 확인했지만 물리 장치/스토리지 구성의 완전한 독립성과 오프사이트 보관은 미입증이다.
- P4 Writer가 로컬 레지스트리에 접근할 방법, P4 v1 Envelope·`observation_evidence_ref`의 최종 형식, DB `collected_at` 매핑, G4/G5/G6 실제 승인 상태.

**중요:** §4~§8의 핵심 보안·상태·공개 CLI·JSON 계약은 본 FROZEN의 준수 대상이다. 실제 운영 경로·인프라 실물·P4 인계 방식은 검증 전 사실처럼 채우지 않는다. 구현 시 필수 안전 조건을 충족하지 못하면 `BLOCKED/HOLD`를 유지한다.

## 11. 기준 자료 및 변경 통제

- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_생성_검증_Phase4A_CLI_Design_FROZEN_v1.0_20261109.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_자동_검증_연결_Phase4B1_Design_FROZEN_v1.0_20261110.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_검토_등록_관측_증거_연결_계약_검토안_v0.1_DRAFT_20261109.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_실데이터_출처_확인_기록_검토_등록_경량화_보완안_v0.2_DRAFT_20261109.md`
- `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_P4_Final_Review_Addendum_v0.2_A1_Aligned_DRAFT_20261108.md`
- `docs/operations/trend-publication/policy/Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`
- `docs/operations/trend-publication/evidence/README.md`
- `docs/prompt/Trend_Leader_AI_Development_Guidelines.md`, `docs/prompt/Trend_Leader_GitHub_Write_Safety_Policy.md`
- 확인 코드: `tools/fr_b02b_cli/fr_b02b_review_candidate.py`, `fr_b02b_observation.py`, `fr_b02b_cli.py`, 관련 테스트.

> **최종 판정: Phase 4B-2 최소 계약만 FROZEN v1.0.** 기존 4A·4B-1 FROZEN 불변, Phase 0 합성 시험 결과 보존, 신규 4B-2 구현·운영 등록 미완료, P4 전체 NOT FROZEN, G5/G6 HOLD, 게시 허가 NONE. 이 문서는 개발 브랜치에서의 문서 동결이며 `dev` 직접 수정·Merge 승인은 아니다.
