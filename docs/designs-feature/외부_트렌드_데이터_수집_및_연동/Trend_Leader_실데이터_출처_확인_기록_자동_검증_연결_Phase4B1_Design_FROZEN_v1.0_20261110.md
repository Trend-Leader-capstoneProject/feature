# Trend Leader — 실데이터 출처 확인 기록 자동 검증·연결 (Phase 4B-1) 설계 확정안 v1.0

> 상태: **FROZEN — Phase 4B-1 읽기 전용 검증·검토 후보 구성 범위에 한정 / 구현 전**  
> 결정일: 2026-11-10 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`, `dev` HEAD `e10d2579db12f0328535453aced2fdbf2752ddcd`  
> 요구사항 추적 ID: `FR-B02b` (팀원 대상 기능명은 제목과 같이 표기)  
> 상위 제약: Phase 4A FROZEN v1.0, A1 v0.2 불변 승인 자료, P4-DEC-01~20, G5/G6 HOLD  
> 결정: 4B-1/4B-2 책임 분리, 4B-1 소범위 동결, 동일 담당자의 관측·검토 허용 정책은 4B-2에서 구체화

## 1. 문제와 목표

Phase 4A에서 실제 사용자는 승인된 원문을 확인하고 `LOCAL_OBSERVATION_RECORDED_REVIEW_HOLD` 기록을 생성했으며, `verify-observation` 결과 `PASS_LOCAL_INTEGRITY_ONLY`를 확인했다. 자동 테스트 90개 PASS는 사용자 실행 보고이며 이 문서 작성 과정에서 재실행하지 않았다.

현재 `verify_observation()`은 `status`, `evidence_id`, `publish_authorization`만 반환한다. 4B의 다음 단계가 개별 JSON을 임의로 다시 해석하지 않도록 **이미 검증한 같은 입력 스냅샷으로부터 검토용 연결 정보를 안전하게 구성**한다.

**이번 단계의 Goal**
- 기존 A1 ZIP과 Phase 4A 로컬 관측 기록을 **읽기 전용으로 재검증**한다.
- 두 입력에서 검증된 `trend_ref`, `content_ref`, `review_evidence_id`, `source_url` 및 로컬 확인 시각을 하나의 검토 후보로 연결한다.
- 사람이 동일한 정보를 재입력하거나 추가로 `YES`를 입력하지 않고, 한 번의 명령 실행으로 검토 가능한 결과를 확인한다.
- 무결성·연결 불일치 시 명확하게 `BLOCKED` 처리하고, 미승인 상태는 그대로 유지한다.

## 2. 명시적 비범위

- **4B-2**: 실제 관측자/검토자 신원·권한 확인, 동일인 역할 기록, 검토의 `ACCEPTED/REJECTED` 판단, 보호 저장소/ACL·백업·서명/변조 방지 정책, 운영용 논리 참조 등록.
- **P4**: `observation_evidence_ref` 확정·등록, DB Writer, `collected_at` 확정, 게시 Transaction/Journal/GRANT, G5/G6 전환.
- 실제 웹사이트 재접속, 브라우저 열기, 크롤링·RSS·외부 AI 호출, 새로운 원문 사실·권리 판정.
- A1 ZIP/승인 기록/Phase 4A 로컬 파일 변경, 신규 DB·API·Frontend·관리자 UI·추가 인프라.
- 기존 Phase 4A의 정확한 `YES` 입력 정책 변경(사용성 개선 별도 범위).

## 3. 사용 흐름 및 사용자 경험

1. 사용자는 **기존 A1 ZIP 경로와 명시적인 로컬 관측 기록 디렉터리**만 지정한다. 성공했던 RO-12 자료를 그대로 사용하며 자동으로 최신 폴더를 선택하지 않는다.
2. 명령은 대화형 재확인 없이 기존 검증기 로직을 재사용하여 ZIP 및 기록·인덱스를 한 흐름에서 검사한다.
3. 정상이라면 결과를 간단히 출력하고 종료한다. 오류라면 원인을 범주 수준으로 안내하고 성공 결과를 내지 않는다. 파일을 고치거나 새로운 증거를 만들지 않는다.
4. 경로 입력이나 오류 메시지에 불필요한 대소문자·문구 규칙을 추가하지 않는다. 데이터 식별자의 정확한 일치 검사는 유지한다.

**제안 CLI 명령(구현 명칭 확정):** `review-candidate --zip <A1_ZIP_PATH> --record-dir <LOCAL_OBSERVATION_DIR>`.

## 4. 입력·검증 계약

| 입력 | 계약 |
|---|---|
| `--zip` | 기존 A1 v0.2 단일 후보 ZIP. `load_a1_snapshot()`의 확정 구조·해시·HOLD 검사 재사용. ZIP 바이트 변경 감지. |
| `--record-dir` | Phase 4A가 생성한 **명시적인** `LOCAL-OBS-...` 폴더. `observation.json`, `index.json`을 기존 검증 규칙으로 확인. |
| 바인딩 | `trend_ref`, `content_ref`, `review_evidence_id`, `source_url`의 승인 스냅샷/관측 기록 일치. `evidence_id`, 원본 ZIP SHA-256 및 인덱스 무결성 검증. |
| 상태 | 기존 `review_result=HOLD`, `actor_assurance=UNVERIFIED`, `publish_authorization=NONE` 유지. 다른 상태로 변경·승격하지 않음. |
| 시간 | 기존 `confirmed_at_utc`, `record_created_at_utc`를 원본 의미 그대로 전달. 독립적으로 검증된 `observed_at`이나 P4 `collected_at`으로 표시하지 않음. |

**검증 시점의 일관성:** 기존 `verify_observation()`과 공통 검증 함수를 재사용·필요 시 내부적으로 분리하여, 검증된 **동일한 ZIP/JSON 바이트**에서 후보 데이터를 구성한다. 검증 후 파일을 무검증으로 다시 읽어 새 값을 추출하지 않는다. 기존 4A 공개 CLI의 출력·검사 계약은 변경하지 않는다.

## 5. 출력·상태 계약

정상 실행은 다음 필드의 **단일 검토 후보 JSON**을 stdout에 반환한다. 아래는 필드 형식 예시이며, 실제 증거 ID·시간을 만들어 넣은 운영 기록이 아니다.

```json
{
  "status": "REVIEW_CANDIDATE_HOLD",
  "local_evidence_id": "LOCAL-OBS-<actual-id>",
  "trend_ref": "<validated-trend-ref>",
  "content_ref": "sha256:<validated-digest>",
  "review_evidence_id": "<validated-g4-reference>",
  "source_url": "<validated-approved-url>",
  "confirmed_at_utc": "<actual-recorded-confirmation-time>",
  "record_created_at_utc": "<actual-recorded-creation-time>",
  "review_result": "HOLD",
  "publish_authorization": "NONE"
}
```

- `REVIEW_CANDIDATE_HOLD`는 *기술적 정합성 검사 성공 및 다음 사람 검토 준비*만 의미한다. `ACCEPTED`, 실제 G4·권리 확인, 보호 저장소 등록, 운영 게시를 의미하지 않는다.
- 실패는 성공 JSON 없이 간단한 `BLOCKED: <category>`와 종료 코드 `1`. 정상 종료 코드는 `0`이다.
- 이 명령은 **파일·DB·네트워크에 쓰지 않는다**. 기록 원본을 보존하고, 별도 실행 기록 파일도 생성하지 않는다.
- 실제 출력값에는 임의의 새 시각·새 증거 ID·추측한 승인자를 생성하지 않는다.

## 6. 책임 분리·최소 변경

- **A1 adapter**: 기존 승인/ZIP 파싱 및 불변 스냅샷 검증만 소유.
- **Phase 4A observation validator**: 기존 기록·인덱스·바인딩 무결성 검증만 소유. 필요한 경우 검증된 값을 제공하는 내부 읽기 전용 함수를 추가하되 기존 CLI 결과를 유지.
- **Phase 4B-1 candidate adapter**: 앞선 두 검증 결과를 이용하여 검토 후보를 구성. 권리·담당자·게시 결정을 소유하지 않음.
- **CLI**: 입력 2개·결과 표시·오류 종료만 담당. 별도 DB/서비스/인프라 도입 없음.

기존 `tools/fr_b02b_cli/` 경로·모듈명은 구현 호환성 때문에 유지한다. 새 코드는 필요한 최소 파일만 추가한다.

## 7. 수용 기준 — 핵심 8개

| ID | 상황 | 기대 결과 |
|---|---|---|
| B41-01 | 정상 A1 ZIP + RO-12 형식의 정상 관측 기록 | 검증된 연결 필드 출력, `REVIEW_CANDIDATE_HOLD`, 종료 코드 0 |
| B41-02 | `trend_ref`·`content_ref`·`review_evidence_id`·`source_url` 중 하나 불일치 | `BLOCKED`, 성공 후보 없음 |
| B41-03 | 로컬 기록·인덱스 누락/손상/해시 불일치/잘못된 상태 | `BLOCKED`, 자동 수정 없음 |
| B41-04 | A1 ZIP이 잘못됐거나 검증 중 변경 | `BLOCKED`, 원본 변경 없음 |
| B41-05 | 동일 검증 입력에서 후보를 두 번 조회 | 새로운 증거 ID·시각 생성 없음, 동일 논리 결과 |
| B41-06 | 정상 출력이라도 관측자 미인증·로컬 시계 정보·HOLD 유지 | `ACCEPTED`, `observed_at`, DB `collected_at`, 게시 허가로 승격하지 않음 |
| B41-07 | 정상/실패 어느 쪽이든 실행 | DB DML, 외부 HTTP, 파일 생성·수정 없음 |
| B41-08 | 오류 메시지·경로 입력 | 재확인 프롬프트 없음, 간결한 오류; 원시 비밀·개인 경로 불필요 노출 금지 |

테스트는 합성 A1·4A Fixture를 기본으로 한다. 사용자의 실제 원본 관측 기록을 테스트 저장소나 공개 GitHub에 추가하지 않는다. 기존 Phase 4A 87건(구현 README 기준) 포함 회귀를 보존하고, 사용자 보고 90건과의 차이는 실제 최신 실행 환경에서 테스트 수를 재확인한다. 테스트 개수 증가 자체를 완료 조건으로 삼지 않는다.

## 8. 완료·인계 기준

- 위 AC와 기존 Phase 4A 관련 회귀가 통과하고 원본 입력이 변경되지 않음이 확인되어야 구현 완료다.
- 완료 산출물은 **검토 후보를 보여 주는 읽기 전용 CLI 결과**뿐이다. 보호 저장소·검토 승인은 생성하지 않는다.
- Phase 4B-2에서는 이번 결과를 바로 승인하는 대신, 실제 담당자 역할/권한, 독립 검토 행위, 보호 저장소 및 참조 등록을 별도로 설계한다. **동일 담당자 허용**이라는 사용자 정책 결정은 유지한다.
- Phase 4B-2가 완료되기 전에도 P4 Writer/G5/G6는 HOLD이며, 4B-1의 `REVIEW_CANDIDATE_HOLD`를 게시 허가로 해석하지 않는다.

## 9. 변경·운영 주의사항

- 이 문서는 **Phase 4B-1의 작은 기능 계약만 동결**한다. Phase 4B 전체, 운영 증거 수락, 실제 서비스 데이터 연동/게시 여부를 동결하거나 승인하지 않는다.
- 장래에 Phase 4A 입력의 `YES` 대소문자 강제 등 사용성 문제를 개선할 때는 Phase 4A FROZEN 변경으로 별도 다룬다. 4B-1 검증에는 그 확인 입력을 반복하지 않는다.
- 기존 DRAFT에 적힌 '관측 증거 미생성'은 문서 작성 당시 상태로 남아 있다. 2026-11-10 현재 RO-12 성공은 **사용자 실행 출력으로 확인**했고, 운영 권한·저장소·담당자 실증으로 확대 해석하지 않는다.
- GitHub 문서 반영은 **Phase 4B-1 기능 구현 브랜치에서 진행**하며, 구현·검증 이후 같은 브랜치로 단일 PR을 생성한다. 직접 `dev`를 수정하거나 Merge하지 않는다.