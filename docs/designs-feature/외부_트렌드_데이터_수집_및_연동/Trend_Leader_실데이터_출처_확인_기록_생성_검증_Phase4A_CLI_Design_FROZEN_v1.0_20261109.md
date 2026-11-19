# Trend Leader — 실데이터 출처 확인 기록 생성·검증 Phase 4A CLI 설계 확정안 v1.0
> 요구사항 추적 ID: `FR-B02b` (파일명은 기능명으로 표기)

> **상태: FROZEN — Phase 4A 로컬 CLI 기능 범위에 한정 / 구현 전 / 운영 증거 아님 / G5·G6 HOLD**  
> **확정 기준일:** 2026-11-09 (KST)  
> **기준 저장소:** `Trend-Leader-capstoneProject/feature`, `dev` HEAD `c1f1dc874b54e59f7a7c86d5886324de3a2e9cb6` (작성 시 확인; 구현 시 최신 HEAD 재조회)  
> **구현 출발점:** 별도 로컬 산출물 `trend_leader_fr_b02b_cli_poc_v03`, Windows 사용자 제공 테스트 51/51 PASS 및 실제 A1 ZIP에 대한 `ELIGIBLE_FOR_REVIEW_ONLY` / 게시 허가 0 확인. 이 CLI는 아직 `dev` 코드가 아니다.  
> **상위 기준:** 운영 Gate `v0.3_POLICY_CONFIRMED`, G4 Python 3.15 v0.7 N절, A1 `A1_RECONCILE_V02`, RSS P0~P3 v1.1 FROZEN, P4 Final Review Addendum v0.2 (전체 **NOT FROZEN**), FR-B02b v0.1 REVIEW DRAFT·v0.2 경량화 DESIGN REVIEW, Phase 4 v0.3 REVIEW.  
> **승인 범위:** 사용자와 합의한 **신규 독립 CLI 명령 → 기존 ZIP 읽기 → 브라우저 수동 확인 1회 → 로컬 초안 기록·검증** 흐름의 구현 계약만 동결. **P4 Envelope·Writer, G4/G5/G6 운영 증거·권한, Google RSS 운영, 보호 저장소의 실제 배포 정책은 동결하거나 승인하지 않는다.**

---

## 0. 마지막 리뷰 결론과 충돌 처리

**결론:** 기존 v0.3 검토안의 **대안 B(신규 `observe-a1-zip` 경로)**를 Phase 4A로 채택한다. 독립 기록의 **생성과 로컬 무결성 검증**까지만 구현하고 운영 Evidence의 **검토 수락/게시 인계는 별도 Phase 4B**로 둔다. 기능 동결을 위해 아래의 입력·출력·상태·실패 동작을 구체화한다.

| 리뷰 관점 | 확인한 사실 / 설계 결정 | 결과 |
|---|---|---|
| 원본 데이터 구조 | 실제 A1 v0.2 ZIP의 `batch.items[]`는 `trend_ref`, `content`, `source_title_origin`; `content_ref`, `review_evidence_id`는 별도 `approvals.records[]`에 존재 | **기존 v0.3 검사 방식 유지**. Batch에 새 키를 끼워 넣지 않음 |
| 원본 호환 | 사용자 Windows에서 CLI v0.3 51/51 PASS, Python 3.15 지문 `sha256:458422...`, `ELIGIBLE_FOR_REVIEW_ONLY` 확인 | Phase 4A **입력 기반 검증 완료**, 새 관측 기능은 미구현 |
| 관측 의미 | 브라우저 열기 성공·HTTP 성공은 원문 내용 확인을 증명하지 못함 | 사용자가 실제 원문 확인 후 **정확히 `YES`** 입력. 단, 이는 **사용자의 자기 진술** |
| 시각 | 기존 G4 `approved_at`, 원문 발표일은 수집 시각이 아님 | **확인 입력 직후** 로컬 UTC 시각만 `confirmed_at_utc`로 신규 기록. 과거 소급 금지 |
| v0.1 관측 Evidence vs 이번 초안 | v0.1의 운영 Evidence는 `reviewer_ref`, `reviewed_at`, `review_result` 검증을 요구하지만 이 CLI에는 인증된 검토 사건이 없음 | **계약 충돌이 아니라 신뢰 수준 분리:** 로컬 초안 전용 schema 사용, `review_result=HOLD`. 운영 Evidence로 자동 변환 금지 |
| 무결성 | ZIP SHA-256, 생성된 JSON SHA-256은 서로 다른 대상 | 원본 ZIP 해시와 증거 파일 해시를 각각 고정·검증. 해시가 승인·서명·권리를 입증하지는 않음 |
| 인프라/협업 | 팀원 담당은 앱 **설정 화면 UI·기능**, 인프라 설정이 아님. 현재 `dev`에는 별도 증거 볼륨/Writer 없음 | 해당 프론트 기능과 독립 개발. Docker·DB·Compose·기존 설정 화면 변경 없음 |
| 게시 차단 | 운영 G5/G6 HOLD, Python 3.15 A1 `authorized_to_publish=0` | 반환/파일에서도 게시 권한은 `NONE`, 승인 상태 승격 불가 |

### 마지막 설계 선택 비교

| 대안 | 장점 | 비용·위험 | 최종 판단 |
|---|---|---|---|
| A. 기존 `simulate`에 실관측 분기 추가 | 초기 변경량 작음 | 가상 기록(`SIMULATION_ONLY`)과 실제 확인 진술의 신뢰 경계가 섞임 | 미채택 |
| **B. 신규 `observe-a1-zip` + 독립 로컬 Draft 스키마** | 기존 51개 테스트와 합성 기록 보호, 실제 진술과 운영 Evidence를 분리 | 신규 모듈·검증 명령과 테스트 필요 | **Phase 4A 채택** |
| C. 서버/DB 중심 기록 | 중앙 권한·감사 체계에 확장 용이 | 인프라/배포/운영 승인·추가 API에 의존, 11월 MVP 범위 확대 | Phase 4B 이후 재검토 |

**우선순위 해석:** 본 문서는 *Phase 4A 로컬 기록 생성 계약*에서 v0.3 리뷰의 미정 세부를 확정한다. 기존 상위 정책·P0~P3 FROZEN·A1 v0.2를 수정하지 않는다. **P4 v0.2의 `observation_evidence_ref`는 아직 구현/동결되지 않았으며, 본 문서의 `evidence_id`를 그 필드에 바로 넣을 수 없다.**

## 1. 문제 정의 / Goal / Non-goal

### 문제

현재 `inspect-a1-zip`은 승인 스냅샷의 **형식·내용 지문 일치**만 확인한다. 이때 A1의 승인은 수동 관측이 있었던 정확한 시각을 보증하지 않는다. 별도 기록이 없으면 P4에 관측 시간을 만들어 넣거나 승인 시간을 잘못 재사용할 위험이 있다.

### Phase 4A Goal

- `A1_RECONCILE_V02`의 **실제 단일 후보 ZIP을 수정 없이 읽고**, 사람이 직접 확인할 공식 원문 링크와 승인된 핵심 표현을 보여준다.
- 사람의 **현재 시점 원문 직접 확인 및 새로운 출처 근거 채택** 의사를 `YES` 한 번으로 받아, 그 확인 사건의 **로컬 시계 시각**과 승인 스냅샷 참조를 함께 기록한다.
- 신규 **로컬 전용 JSON 원본 + SHA-256 인덱스**를 기록하고 생성 직후·나중에 읽기 전용으로 재검증한다.
- 입력·기록 오류는 **Fail Closed** 처리하고, 기존 A1 ZIP·다른 기록을 덮어쓰지 않는다.
- Docker·MariaDB·웹 서버·외부 API 의존성 없이 실행한다.

### 명시적 Non-goal

원문 HTML/기사 본문/이미지/OG 메타데이터 자동 수집, Google RSS 접속, 권리 자동 판정, 승인자 신원 인증, 독립 타임스탬프, 브라우저의 실제 페이지 렌더링 감시, 로컬 파일의 변조 불가능성 보증, 서비스 DB INSERT/UPDATE, 운영용 P4 Evidence 발행, 승인 UI, G5/G6 전환, Writer/영속 Journal 구현.

## 2. 도메인 책임 및 시간 의미

| 개념 | 소유 책임 | Phase 4A 처리 |
|---|---|---|
| **A1 Approved Snapshot** | 기존 독립 승인 파일·A1 v0.2 검사기 | 콘텐츠 7개 필드·origin·evidence ID·`content_ref` **불변**, 읽기 및 재계산 대조만 수행 |
| **Local Observation Attestation** | 이번 CLI | 사용자가 지금 확인했다고 **진술한 사건** 기록. 원문 사실 검증의 독립 인증 아님 |
| **Operational Observation Evidence** | 후속 FR-B02b Phase 4B / 보호 저장소·검토 책임자 | 이번 범위 **제외**, 별도 실제 검토와 신뢰 경계 필요 |
| **Publish Authorization** | 독립 G4/G5/G6 및 P4 Writer | 이번 CLI에 권한 없음; 항상 `NONE` |

- `confirmed_at_utc`: 사용자의 **대문자 `YES` 입력 반환 직후** 측정한 timezone-aware UTC 시각. 페이지를 연 순간, 외부 원문 게시일, 11월 4일 승인 시각이 아니다.
- `record_created_at_utc`: 로컬 증거 JSON을 조립하기 **직전** 측정한 UTC 시각. 파일의 영속 저장 완료 시각 또는 제3자 인증 시각이 아니다. `record_created_at_utc`가 `confirmed_at_utc`보다 빠르면 차단한다.
- `observation_method`: `HUMAN_BROWSER_ATTESTATION` — 자동 원문 내용 검증이 아닌 **확인자의 진술**을 정확히 표시한다.
- `event_kind`: `MANUAL_SOURCE_COLLECTION` — 사용자가 이 시점에 해당 원문을 MVP-A 콘텐츠의 **새로운 출처 근거로 확보한다**고 확인한 사건. 기존 2026-11-04 최초 확인 시각을 복원한 것이 아니며, 후속 P4가 이 사건을 DB의 `first_collected_at`으로 채택할지는 별도 판단한다.
- `SOURCE_LINK_RECHECK` 전용 동작·과거 시점 입력·자동 `collected_at` 변환은 본 버전에서 **지원하지 않는다**. 이미 읽었던 링크가 열리는지만 재확인하는 경우에는 `YES`를 사용하지 않고 취소해야 한다.

## 3. CLI 계약 (구현 후 제공할 새 명령)

```powershell
# 현재 존재하는 명령이 아니라 Phase 4A 구현 목표입니다.
python .\fr_b02b_cli.py observe-a1-zip `
  --zip '<G5 A1 v0.2 원본 ZIP의 절대 경로>' `
  --output-dir '<Git 작업 트리 밖의 로컬 개인 기록 폴더>'

# 생성 직후 자동 검증 외에 별도의 읽기 전용 재검증도 제공
python .\fr_b02b_cli.py verify-observation `
  --zip '<동일한 원본 ZIP의 절대 경로>' `
  --record-dir '<생성된 LOCAL-OBS-... 디렉터리>'
```

### 3.1 `observe-a1-zip` 단계

1. **사전 검증:** 기존 CLI v0.3의 A1 구조·정규 해시 검사에 의거해 `MVP-A`, `A1_RECONCILE_V02`, G6 입력 `HOLD`, 개별 G4 명목상 `PASS/APPROVED`, 미철회, 필수 권리/링크 체크, Google RSS 비파생, `EDITORIAL_LABEL`, Source **정확히 1건**, `thumbnail_url=null`인 단일 적격 후보를 요구한다. 이 결과는 실제 G4 진위·권리를 인증하지 않음.
2. **읽기 스냅샷:** 동일한 ZIP 바이트에서 승인 JSON·Batch JSON을 검증하고, 승인된 `title`, `summary`, `source_title`, `source_url`, `content_ref`, `review_evidence_id`를 **읽기 전용** 추출한다. ZIP 바이트의 SHA-256을 별도로 계산한다. `inspect-a1-zip`의 기존 출력/판정 계약을 변경하지 않는다.
3. **출력 경로 검사:** `--output-dir` 필수. Git 작업 트리 내부·입력 ZIP 자체 경로·symlink 우회·불확실한 재분석 대상 경로·기존 동일 ID 디렉터리 덮어쓰기를 차단한다. 안전 여부를 확인할 수 없는 경로는 Fail Closed한다. 실제 접근 권한이나 백업을 입증하지는 않음.
4. **미리보기/브라우저:** 터미널에서 제목·짧은 설명·자체 작성 출처 안내·승인된 HTTPS URL을 보여준 뒤, 로컬 기본 브라우저 열기를 시도한다. **CLI 자체는 HTTP 요청·리디렉션 추적·페이지 파싱을 수행하지 않는다.** `webbrowser.open`이 실패를 보고하면 증거를 생성하지 않는다. 성공 반환도 실제 페이지 열람 성공을 증명하지 않는다.
5. **확인 입력:** 원문 사실·페이지 대상·출처 URL이 승인 스냅샷과 일치하고, **지금 새 근거로 직접 확인·채택**한다는 내용을 읽은 뒤 **정확히 `YES`** 입력 시에만 진행한다. `NO`, `yes`, 빈 입력, EOF, Ctrl+C, URL 불일치·의심스러운 리디렉션·내용 변경 시 **취소/차단하며 기록 생성 0건**. 이때 재승인/URL 자동 수정 금지.
6. **사건·시간:** 확인 입력 반환 직후 `confirmed_at_utc`, 기록 객체 생성 직전 `record_created_at_utc`를 **서로 구분**해 측정한다. timezone-aware UTC 변환이 불가능하거나 시각 역행이 확인되면 차단한다. `observer_ref=UNVERIFIED_LOCAL_OPERATOR`, `actor_assurance=UNVERIFIED`로 신원 미인증 명시.
7. **변경 방어:** 확인 후 **기록 확정 전에** 입력 ZIP 원본 바이트가 초기 읽기와 동일한지 재확인한다. 그 사이 내용이 바뀌면 차단하고 기존 승인 기록은 수정하지 않는다. 이 검사는 로컬 동시 파일 변경 위험을 줄이는 것이며, 적대적 파일시스템에서 모든 TOCTOU를 해결했다는 주장이 아니다.
8. **저장·재검증:** 생성한 ID 전용 신규 디렉터리에 `observation.json`과 `index.json`을 안전한 임시 스테이징 후 기록한다. JSON의 SHA-256·참조 및 A1 ZIP 해시를 읽기 전용 검증하는 로직을 **동일 모듈에서 재사용**한다. 최종 확인 실패/부분 저장/중복 시 성공을 출력하지 않는다. 불명확한 잔여 파일은 HOLD로 남기며 자동으로 사용하지 않는다.
9. **성공 출력:** 상태 `LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD`, 증거 ID, 로컬 폴더, `publish_authorization=NONE`. 이 결과는 **운영 P4 Evidence 발행이나 게시 승인 아님**을 사용자에게 표시한다.

### 3.2 `verify-observation`

- 입력 ZIP과 로컬 기록 경로를 **읽기만** 한다. 단일 A1 후보를 다시 대조하고 원본 ZIP SHA-256, JSON 스키마·필드·사건 종류·시간 형식·기록 파일 SHA-256·index 참조·ID·경로·HOLD/NONE 상태가 일치하는지 검증한다.
- 신원·권리·진짜 브라우저 열람·독립 시계 신뢰성을 검증했다고 반환하지 않는다. 성공 상태는 **`PASS_LOCAL_INTEGRITY_ONLY`**이며 `publish_authorization=NONE`을 유지한다.
- 증거가 누락되거나 변조·교체된 경우 BLOCK; 자동 수정/재해시/자동 승격 금지.

### 3.3 기존 CLI 하위 호환

기존 `inspect`, `simulate`, `verify`, `inspect-a1`, `inspect-a1-zip` 명령과 합성 전용 `SIMULATION_ONLY` 레코드/테스트를 유지한다. 기존 합성 기록을 실관측 기록으로 승격·변환하지 않는다. 원본 ZIP **내부 Python 코드는 실행하지 않으며**, JSON만 제한 크기로 읽는다.

## 4. 로컬 초안 JSON v1.0 — 정확한 최소 필드

**주의:** 다음 두 JSON은 **이번 Phase 4A의 신규 로컬 출력 계약**이며, 운영용 FR-B02b v0.1/P4 Envelope의 JSON schema가 아니다. 아래 값은 형식 설명용이며 실제 관측 사건·시각이 아니다.

### 4.1 `observation.json`

`schema = "FR_B02B_LOCAL_OBSERVATION_V1"`로 고정하고 **정확히** 아래 키를 허용한다. 누락/미정의 키는 거부한다.

```json
{
  "schema": "FR_B02B_LOCAL_OBSERVATION_V1",
  "evidence_id": "LOCAL-OBS-<uuid4-hex>",
  "profile": "MVP-A",
  "trend_ref": "<원본 A1 trend_ref>",
  "content_ref": "sha256:<A1 승인 콘텐츠 해시>",
  "review_evidence_id": "<원본 승인 기록의 G4 증거 참조>",
  "source_url": "<A1의 승인된 원문 URL>",
  "source_title_origin": "EDITORIAL_LABEL",
  "a1_archive_sha256": "sha256:<원본 ZIP 바이트 해시>",
  "event_kind": "MANUAL_SOURCE_COLLECTION",
  "observation_method": "HUMAN_BROWSER_ATTESTATION",
  "attestation": "USER_CONFIRMED",
  "confirmed_at_utc": "<실제 YES 직후의 UTC ISO8601 시각>",
  "record_created_at_utc": "<실제 기록 생성 직전의 UTC ISO8601 시각>",
  "clock_source": "LOCAL_SYSTEM_CLOCK",
  "observer_ref": "UNVERIFIED_LOCAL_OPERATOR",
  "actor_assurance": "UNVERIFIED",
  "review_result": "HOLD",
  "publish_authorization": "NONE"
}
```

- `LOCAL-OBS-`는 UUID4 기반으로 새 사건마다 달라야 하며 기존 `E-G4-*`, `SIM-OBS-*`, 운영 `observation_evidence_ref`와 동일시하지 않는다.
- `source_url`은 A1의 **원 문자열과 byte-equivalent 의미의 정확한 문자열 일치**를 요구한다. 원격 리디렉션 결과로 조용히 치환하지 않는다.
- 승인 콘텐츠 7개 필드 전체를 중복 저장하지 않는다. 실제 확인 대상 제목/설명의 확인에는 원본 ZIP의 A1 승인 스냅샷을 참조한다.
- 기록은 확인자가 해당 내용을 승인했다는 **주장(assertion)**이지, CLI가 원문 내용이나 이용 허가를 인증한 증거가 아니다.
- 키/문자열/상태/시간은 엄격 검증한다. **`reviewed_at` / `reviewer_ref` / `review_result=ACCEPTED`는 생성하지 않는다**. `review_result=HOLD`가 필수다.

### 4.2 `index.json`

`schema = "FR_B02B_LOCAL_INDEX_V1"`로 고정하고 정확히 아래 키를 허용한다.

```json
{
  "schema": "FR_B02B_LOCAL_INDEX_V1",
  "evidence_id": "LOCAL-OBS-<동일 uuid4-hex>",
  "artifact_file": "observation.json",
  "artifact_sha256": "sha256:<observation.json 실제 UTF-8 바이트 SHA-256>",
  "trend_ref": "<observation.json과 동일>",
  "content_ref": "<observation.json과 동일>",
  "a1_archive_sha256": "<observation.json과 동일>",
  "status": "LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD"
}
```

- 파일은 UTF-8 + `json.dumps(ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)`와 LF 한 개를 쓰는 **단일 canonical 형식**으로 직렬화한다. SHA-256은 실제 저장된 `observation.json` 바이트에 계산한다. 이 JSON 직렬화는 A1 **`content_ref` 계산 규칙을 변경하지 않는다**.
- 해시 알고리즘·파일명·schema 버전·상태 고정. 인덱스를 함께 교체한 공격까지 SHA-256만으로 방어한다고 주장하지 않는다.
- 본 단계에서는 파일 기반 로컬 사본만 만들며 보안이 입증된 보호 저장소·영속 Journal·전자서명이라고 명명하지 않는다.

## 5. 저장 방식 및 실패·보안 정책

### 저장 불변조건

1. 입력 ZIP은 읽기 전용. ZIP 내부에서 알려진 두 JSON 멤버만 읽고 **파일 추출·ZIP 내부 코드 실행 금지**. 중복 멤버명·과도한 압축 해제 크기·잘못된 JSON/중복 키·누락/추가 필드는 차단. 기존 v0.3 파일별 1 MiB, ZIP 20 MiB 제한을 **최소 유지**한다.
2. 원본 ZIP 바이트 SHA-256을 사전 검증된 A1 후보와 결속한다. 기록 전 ZIP 재확인과 검증 도구의 사후 재대조를 제공한다.
3. 결과 경로는 Git 작업 트리 밖에 둔다. 존재 여부, 심볼릭 링크·접근 권한, 디렉터리 충돌을 사전 검사한다. **새 기록의 기존 파일 덮어쓰기 금지**. OS 보안 정책/ACL 강제 설정을 동작했다고 가정하지 않는다.
4. 저장은 동일 파일시스템의 임시 스테이징 디렉터리에서 파일 생성(`x`/exclusive)·flush/fsync 후 최종 단일 디렉터리 이름으로 이동한다. 기록 직후 독립 읽기 검증. **크래시 일관성·디렉터리 fsync·다중 프로세스 경쟁 완전 방어를 보증하지 않는다.** 불명확한 상태는 사용 불가 HOLD.
5. 오류/취소/철회/원본 변경/브라우저 실패/시간 오류/기록 검증 실패 때 **성공 코드 및 정상 증거 기록을 남기지 않는다**. 부분 파일이 남았다면 수동 조사 대상으로 표시하고 `PASS`로 처리하지 않는다.
6. 로컬 파일에는 최소 필요값만 보관한다. 원문 페이지 본문·스크린샷·이미지·쿠키·토큰·DB 접속정보·전체 승인 JSON을 복사하지 않는다. 공개 GitHub에 실제 확인 기록을 커밋하지 않는다.

### 응답 및 종료 계약

| 동작 | 종료 코드 | 사용자 출력 |
|---|---:|---|
| 새 로컬 기록과 재검증 성공 | `0` | `LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD` + ID + 디렉터리 + `publish_authorization=NONE` |
| 로컬 증거 무결성 재검증 성공 | `0` | `PASS_LOCAL_INTEGRITY_ONLY` + ID + `publish_authorization=NONE` |
| 입력·ZIP·브라우저·시각·저장·검증 실패 | `1` | `BLOCKED: <간단한 사유>` / 증거 수락 없음 |
| 사용자 `YES` 미입력·EOF·Ctrl+C 또는 인자 누락 | `2` | `CANCELLED`(사용자 취소) 또는 표준 인자 사용 오류 / 기록 없음 |

실제 CLI에서 비밀키·원문 전문·전체 사용자 경로를 불필요하게 오류 로그에 출력하지 않는다. 반대로 보안상 필요한 원인 코드까지 숨기지 않는다.

## 6. 구현 책임 분리·예상 변경

| 모듈/파일 | 책임 | 필수 제약 |
|---|---|---|
| `fr_b02b_a1_adapter.py` | 기존 A1 ZIP·승인/Batch 일치 검사 및 **검증된 안전 표시값 추출을 위한 최소 읽기 API** | 원본 검사 범위 변경·공식 승인/권리 진위 주장 금지. `inspect-a1-zip` 응답 하위 호환 |
| `fr_b02b_observation.py` (신규) | 로컬 사건 JSON·시간·ID·인덱스 생성, 저장/읽기 검증 | A1 승인/철회·권리·G6 결정 소유 금지. 브라우저 호출/CLI 출력 로직에서 분리 |
| `fr_b02b_cli.py` | `observe-a1-zip`, `verify-observation`, browser-open, YES 프롬프트와 종료 코드 연결 | 기존 simulate/inspect 경로 변경 최소화 |
| `tests/test_fr_b02b_real_observation.py` (신규) | 합성 원본 ZIP Fixture 및 정합성·무결성·Fail-Closed·시간·브라우저 mock 검증 | 실 URL 네트워크 호출·실 운영 증거 생성 금지 |
| `README.md` | Windows PowerShell 명령, 상태·보관 주의사항, 실제 시연 결과 기록법 | 없는 CLI 옵션·서버 의존성 추가 금지 |

**분리 이유:** A1 어댑터는 *승인 스냅샷 구조*를, 관측 모듈은 *확인 기록의 불변 구조*를, CLI는 *사용자 상호작용*을 소유한다. 이 셋을 묶어 승인/게시 판단을 하게 만들면 Phase 4A가 G5/G6의 권한 경계를 침범한다.

## 7. 테스트 및 Acceptance Criteria (TDD)

| ID | Given / When | Then / 완료 판정 |
|---|---|---|
| `RO-01` | 실제 계약과 동일한 **합성 A1 v0.2** ZIP (단일 적격 후보) | 승인 제목·요약·`source_url`·`content_ref`·G4 증거 ID를 불변 로드하고 원본 바이트 변화 없음 |
| `RO-02` | 브라우저 열기를 시도했으나 `YES` 전 | 로컬 증거 기록 0. 브라우저 반환값만으로 `USER_CONFIRMED` 생성 금지 |
| `RO-03` | 대상 확인 후 정확히 `YES`, UTC 시계 정상 | 새 ID/두 JSON·지문 생성, status=`LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD`, `review_result=HOLD`, `publish_authorization=NONE` |
| `RO-04` | `NO`, `yes`, `Yes`, 입력 종료·Ctrl+C | **기록 0건**, 취소 종료. 소문자/공백 입력 암묵 승격 금지 |
| `RO-05` | 확인 중 원본 ZIP 바이트 변경·G4 후속 철회/부적격 후보 | 전체 BLOCK, ZIP·기존 기록 불변 |
| `RO-06` | Batch `g6_status=PASS` 위장·Google RSS 파생·`source_title_origin=NONE`·복수 Batch item | 전체 BLOCK, 승인 적격 자동 전환 금지 |
| `RO-07` | 로컬 시계 tz-naive·UTC 변환 실패·기록 생성 시각 역행 | 기록 0건 또는 안전 중단, 과거 시각 자동 보정 금지 |
| `RO-08` | 증거/인덱스 파일 삭제·내용 변경·ID/경로·ZIP 지문 불일치 | `verify-observation` BLOCK, 무결성 자동 재생성 금지 |
| `RO-09` | 동일 evidence ID 디렉터리 존재·파일 쓰기 실패·스테이징 잔재 | 성공 응답 금지, 기존 기록 무변경, 잔재 자동 승인 금지 |
| `RO-10` | 브라우저 시작 실패 또는 사용자가 리디렉션/출처 불일치 보고 | 기록 생성 금지, 승인 `source_url` 자동 변경 금지 |
| `RO-11` | 기존 v0.3 전체 51개 테스트와 5개 명령 | 전부 회귀 PASS; 기존 합성 레코드와 실제 초안 타입이 혼용되지 않음 |
| `RO-12` | 실제 사용자 Windows PowerShell에서 승인 원문을 열람·YES 1회 | 새 기록 생성·`verify-observation`에서 `PASS_LOCAL_INTEGRITY_ONLY`; **사용자의 확인 진술만 입증**, 운영 Gate PASS 아님 |
| `RO-13` | Git 작업 트리 내부·symlink 경유 출력 경로, 부적절한 ZIP | 증거 기록 0건, 안전성 판별 불가 시 차단 |
| `RO-14` | JSON 상태를 `ACCEPTED` 또는 게시 허가로 조작하거나 함께 해시를 바꿈 | 고정된 상태·스키마 검증으로 BLOCK. 단, 양쪽 파일 일치 재작성 공격의 암호학적 진위까지 방어 주장 금지 |

**수행 순서:** (a) 확정 계약 기반 실패 테스트 작성 → (b) `A1 → CLI → observation → verify` 최소 구현 → (c) 기존 51개 회귀 → (d) 생성·변조·취소·동시성/저장 실패 단위 검증 → (e) 로컬 실제 브라우저 확인 1회 → (f) 최종 diff 및 기능별 완료 점검. 테스트 건수 증가보다 `RO-01~14` 핵심 반례 충족이 중요하다.

## 8. 완료 판정과 Phase 4B 인계

### Phase 4A 완료의 필요조건

- 신규 두 명령이 확정 I/O 계약과 상태 필드를 준수하고, 기존 CLI 51개 테스트를 모두 유지한다.
- A1 원본 ZIP을 **읽기 전용**으로 검증하며 변경에 안전하게 중단한다. 실제 원본의 명목상 `ELIGIBLE_FOR_REVIEW_ONLY`를 관측/게시에 대한 승인으로 오인하지 않는다.
- 단일 `YES` 이벤트에 대해 **로컬 확인 기록 생성·즉시/사후 무결성 검증** 및 실패 차단을 입증한다.
- Windows 실사용 시험에서 링크 열람 + 확인 1회 + 검증까지 성공하고, 시각이 **당시 로컬 확인 시점**임을 명시한다.
- 테스트 로그·입력/출력 샘플에는 실제 개인정보/비밀이나 페이지 원문을 넣지 않는다.

### 후속 Phase 4B에서 별도로 결정할 사항 (이 문서가 확정하지 않음)

운영 보호 저장소 경로·백업·ACL/분리 권한, 서명/불변 장부, 실제 관측자/검토자 권한 및 동일인 검토 허용 기준, P4 `observation_evidence_ref`와 로컬 ID 매핑, 승인 철회 및 시간 신뢰성, P4 DB `collected_at` 선택, G5 Journal·DB 최소 GRANT·관리 네트워크와 G6 운영 승인. **이들이 충족되지 않으면 실제 Writer 게시 진입은 계속 HOLD**다.

### 운영 중단·변경 요청

기존 A1 v0.2의 형식이 달라졌거나 원본 ZIP/소스의 신뢰 경계가 다름을 발견하면, ZIP에 임의 필드를 추가해 통과시키지 않는다. `FROZEN v1.0`의 필요한 변경점·영향·반례를 제시하고 **설계 변경을 별도 합의**한다. 이 동결은 운영 `P4 FROZEN` 선언 또는 `FR-B02b 운영 Evidence 완료` 선언이 아니다.

## 9. GitHub 반영 및 구현 채팅 인수인계

- 문서만 반영한다. PoC 스크립트·실제 ZIP·실관측 결과·승인 원본·DB·Docker·Frontend 설정 화면 코드는 이번 **설계 PR**에 넣지 않는다.
- `dev` 기준 구현 전 최신 HEAD 및 **PoC v0.3 코드 해시/ZIP/로컬 working tree**를 다시 확인하고, 별도 **기능 PR**을 생성한다. 기존 팀원의 설정 화면 작업과 충돌하지 않는다.
- 구현 채팅 시작 시 이 **Phase 4A v1.0 FROZEN**을 최우선으로 하되, A1 v0.2·운영 Gate v0.3·RSS P0~P3 및 기존 FROZEN을 상위 권한 제약으로 유지한다. 기존 51개 테스트와 새 `RO-01~14`를 완료 기준으로 사용한다.

> **최종 판정:** **Phase 4A 로컬 실제 관측 *확인 기록* 기능 계약만 FROZEN**. 코드 미구현, 운영 관측 Evidence 미승인, 원본 G4/A1 불변, **G5/G6 HOLD**, 게시 `NOT_ATTEMPTED`.
