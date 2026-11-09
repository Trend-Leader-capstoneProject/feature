# Trend Leader RSS P0–P3 PoC — R-03 후보 제목 오류 판정 계약 보완안

- 문서 ID: `RSS-P3-R03-ADDENDUM`
- 버전: `v1.0-DRAFT`
- 작성일: 2026-11-02
- 상태: **설계 보완안 — 작업 브랜치 등록·원본 FROZEN 미변경**
- 대상 작업: Final Review `R-03` — 후보 제목 정규화 실패와 정책 실행 실패 구분
- 기준 문서: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_RSS_P0-P3_PoC_Implementation_Contract_v1.0_FROZEN.md` (`dev`)
- 구현 기준: `feat-rss-p1-parser`의 P1/P2/P3 구조 및 R-03 로컬 수정·테스트 보고
- 적용 범위: **합성 Fixture 기반 P0–P3 기술 PoC**. 실제 RSS 자동 호출, DB Writer, 게시·권한 처리는 제외.

> **문서 효력**: 이 파일은 사용자와 협의한 R-03 설계 결정을 근거 및 판정 우선순위 관점에서 정리한 **별도 보완안**이다. 기준 FROZEN v1.0의 내용을 임의로 덮어쓰지 않는다. 문서 반영 승인 및 버전 이력 기록 이후에만 상위 계약 개정으로 취급한다.

## 1. 문제 정의와 변경 근거

### 1.1 기존 FROZEN에서 이미 확정된 사실

- **§3.2, §4.1**: P1 Parser는 RSS Item 제목이 없거나 공백뿐이면 해당 Item을 제외하고 `ItemIssue(MISSING_ITEM_TITLE)`를 남긴다. 기사 제목·URL 오류는 P3에서 판단한다.
- **§5.1**: 후보 제목은 Unicode NFC, 공백 정리, ASCII 영문 소문자화 등의 정규화 후 표시 제목/정규화 제목이 비거나 **255 Unicode 코드포인트를 초과하면 저장 불가**이다. 255자 자체는 허용한다.
- **§6.3**: 후보 결정은 주제, Source, 사건, Category의 단계적 검증에 따른다. `FAILED`는 `CandidateEvaluation.decision`에 넣지 않으며 기술적 예외는 별도로 취급한다.
- **§6.4**: `WOULD_ACCEPT`는 정규화된 유효 제목, 적합 Source 최소 1건, 근거 있는 활성 Child 최소 1개를 필요로 한다. `DEFERRED`와 `SKIPPED`의 `valid_sources`와 `category_ids`는 비어 있어야 한다.

### 1.2 확인한 구현 문제

- P2 `normalize_title(raw_title)`은 **정규화 후 빈 문자열 또는 길이 256자 이상**에 대해 정상적으로 `None`을 반환한다.
- R-03 이전 P3 `validate_p3_candidate()`는 이 `None`을 `ValidationExecutionError("candidate title cannot be normalized")`로 전환했다.
- 제목 자체의 품질 문제와 코딩 버그/정책 설정 오류가 동일한 실행 실패로 기록되어, FROZEN §6.4의 **정상 후보 판정과 기술 실패의 구분** 목적에 맞지 않았다.
- 기존 계약은 저장 불가를 확정했지만 **해당 경우의 구체적인 `decision`/`ReasonCode`는 명시하지 않았다.** 이 문서는 그 공백을 보완한다.

### 1.3 선택 대안과 이유

| 대안 | 동작 | 판단 |
|---|---|---|
| A. 기술 실패 유지 | `ValidationExecutionError` | 정규화 가능한 데이터 문제를 정책 실행 실패로 혼동하므로 비권장 |
| B. 제외 | `SKIPPED` + 신규 코드 | 현재 `SKIPPED`의 명백한 제외 근거와 개념상 구별이 어려워 비권장 |
| **C. 보류** | **`DEFERRED(CANDIDATE_TITLE_INVALID)`** | **채택 불가를 명확히 표현하고 기술 실패와 구분**하므로 채택 |

**결정**: 정규화된 제목을 구성할 수 없는 *문자열 입력 후보*는 `DEFERRED`한다. 다만 타입 계약 위반, 프로그래밍 오류, 주입 정책 오류를 정상 보류로 숨기지 않는다.

## 2. 변경 계약 — R-03

### 2.1 신규 ReasonCode

`ReasonCode.CANDIDATE_TITLE_INVALID = "CANDIDATE_TITLE_INVALID"`

- **후보 전체의 제목** 정규화 실패를 나타낸다.
- 기존 `SourceIssueCode.SOURCE_TITLE_INVALID`는 **개별 기사의 제목** 오류이므로 재사용하지 않는다.
- 신규 `CandidateDecision` 값이나 `FAILED` 값을 추가하지 않는다.

### 2.2 적용 조건

`ParsedCandidate.raw_title`이 **문자열**이고, P2의 확정된 `normalize_title()` 결과가 `None`일 때 적용한다. 예시는 다음과 같다.

- 공백 정리 후 빈 문자열
- 공백 정리 및 NFC 변환 후 표시용 제목이나 정규화 제목이 255 Unicode 코드포인트 초과

다음 상황에는 적용하지 않는다.

- **비문자열** `raw_title`: `ParsedCandidate` 타입 계약 위반이므로 기존 예외(`TypeError`)를 유지한다.
- 유효한 후보 제목에 대해 **개별 기사 제목만** 잘못된 경우: 기존 Source 선별 및 `SourceIssueCode` 사용.
- 유효한 후보 제목이 **명백히 관심 범위 밖**인 경우: `SKIPPED(OUT_OF_SCOPE)` 유지.
- P1이 제목 없음/공백 Item을 이미 제외한 경우: P1 `ItemIssue`를 유지. P3의 공백 제목 테스트는 **직접 생성된 ParsedCandidate에 대한 방어적 계약 테스트**다.

### 2.3 출력 불변조건

```python
CandidateEvaluation(
    decision=CandidateDecision.DEFERRED,
    reason_codes=(ReasonCode.CANDIDATE_TITLE_INVALID,),
    normalized_title=None,
    valid_sources=(),
    category_ids=(),
    warnings=candidate.warnings,
    source_issues=(),
)
```

- 제목이 유효하지 않으면 Source Screening·Topic 분류·Event·Category 정책을 호출하지 않는다. 현 구현의 `evaluate_topic_gate()`는 정규화 실패 시 `None`을 반환하여 후속 P3 제목 검증으로 넘긴다.
- `source_issues=()`는 **기사 검증을 수행하지 않았음**을 뜻한다. 기사가 모두 적합하다는 뜻이 아니다.
- `warnings`는 기존 입력 순서를 유지한다.
- `DEFERRED` 결과는 저장·게시 가능한 후보가 아니다. P4 Writer가 해당 결과로 쓰기를 진행해서는 안 된다.

## 3. 최종 후보 판정 우선순위

이 순서는 **실제 함수 흐름에 따른 Gate 순서**이며, 모든 오류 사유를 단순 정렬하여 반환한다는 의미가 아니다. 기술적 오류는 발생 위치에서 일반 후보 판정과 별도로 전파한다.

| 순서 | Gate | 판정 및 사유 | 후속 실행 |
|---:|---|---|---|
| **0** | 후보 제목 타입·정규화 | 비문자열 → 실행 실패; 문자열이지만 정규화 실패 → `DEFERRED(CANDIDATE_TITLE_INVALID)` | **중단** |
| **1** | 1차 Topic | 명시적 `CLEAR_OUT_OF_SCOPE` → `SKIPPED(OUT_OF_SCOPE)` | 중단 |
| **2** | Source Screening | 적합 Source 0건 → 기존 차단 출처/출처 미확인/자료 누락/관련성 불명확 사유에 따른 `SKIPPED` 또는 `DEFERRED` | 중단 |
| **3** | 2차 기사 Topic | 적합 Source의 근거가 모두 명백히 범위 밖 → `SKIPPED(OUT_OF_SCOPE)`; 범위 밖 근거와 다른 범위 근거가 섞이면 기존 R-02B 정책에 따라 `DEFERRED(EVENT_AMBIGUOUS)` | 해당 판정 시 중단 |
| **4** | Event Consistency | 사건 불확정·충돌 → `DEFERRED(EVENT_AMBIGUOUS)` | 중단 |
| **5** | Category 구조·근거 | 활성 Child/제안 근거 불충분, `기타` 배제 근거 부족 → `DEFERRED(CATEGORY_UNCLEAR)` | 중단 |
| **6** | 최종 채택 가능 판정 | 앞선 조건 충족 → `WOULD_ACCEPT(VALIDATED_BY_FIXTURE_RULES)` | 반환 |

**R-03의 핵심 우선순위**: 제목 정규화 실패는 1차 `OUT_OF_SCOPE` 여부를 판별할 입력 자체가 없는 상태이므로 **범위 판정 및 Source 부족 판정보다 우선한다.** 기존 FROZEN의 1차 Topic 우선순위를 뒤집는 것이 아니라 **Topic 판정의 전제인 제목 유효성 Gate를 명시**하는 것이다.

### 3.1 우선순위 충돌 예시

| 입력 상태 | 우선하는 결과 | 이유 |
|---|---|---|
| 후보 제목 정규화 실패 + Source 0건 | `DEFERRED(CANDIDATE_TITLE_INVALID)` | 검증 가능한 제목 자체 없음 |
| 후보 제목 정규화 실패 + 모든 Source 차단 | `DEFERRED(CANDIDATE_TITLE_INVALID)` | Source Screening 실행 전 중단 |
| 유효 제목 + 1차 명백한 관심 범위 밖 + Source 0건 | `SKIPPED(OUT_OF_SCOPE)` | 1차 범위 밖이 Source 부족보다 우선 |
| 유효 제목 + 1차 모호함 + 적합 Source 0건 + Child 없음 | 기존 `NO_ELIGIBLE_SOURCE` 관련 판정 | Source 부족이 Category 부재보다 우선 |
| 유효 제목 + 적합 기사 전부 2차 범위 밖 + 사건 불명확 | `SKIPPED(OUT_OF_SCOPE)` | R-02B Gate가 Event Gate보다 먼저 적용 |
| 유효 제목 + 적합 Source 있음 + 사건 충돌 + Category 근거 없음 | `DEFERRED(EVENT_AMBIGUOUS)` | 사건 일관성 Gate가 Category보다 우선 |
| 유효 제목 + 적합 Source·사건 확인 + Child 근거 없음 | `DEFERRED(CATEGORY_UNCLEAR)` | Category 확정 불가 |
| 후보 제목 비문자열, 또는 주입 정책 자체가 잘못됨 | 실행 실패 | 정상 `DEFERRED`와 구분 |

> **별도 미해결 검토 사항**: R-02B가 *기사별 관심 범위 근거 충돌*에 `EVENT_AMBIGUOUS`를 사용하는 것은 현재 코드의 관찰된 동작이다. 이 사유가 사건 충돌과 개념적으로 정확히 일치하는지는 R-04 또는 최종 계약 검토에서 별도로 확인한다. **R-03에서는 변경하지 않는다.**

## 4. FROZEN v1.0 반영 제안 — 최소 문구

원본을 바로 편집하는 대신 다음 문구를 개정 시점에 해당 조항에 추가한다.

### 4.1 §3.2 출력 타입 의미

> `CandidateEvaluation.normalized_title=None`은 후보 제목을 유효하게 정규화하지 못한 `DEFERRED(CANDIDATE_TITLE_INVALID)` 결과에서 사용한다. P1 Parser는 제목 없음/공백 Item을 앞 단계에서 `ItemIssue(MISSING_ITEM_TITLE)`로 제외하나, P3는 직접 구성되거나 기타 상위 경로에서 전달된 유효하지 않은 문자열 후보에 대해 방어적으로 동일 계약을 적용한다.

### 4.2 §5.1 제목

> 제목 정규화 함수가 `None`을 반환하는 문자열 후보는 P3에서 `DEFERRED(CANDIDATE_TITLE_INVALID)`로 처리하고 저장하지 않는다. 비문자열 입력은 타입 계약 위반으로 정상 보류에 포함하지 않는다. 기존 NFC·공백·ASCII 대소문자·255 코드포인트 규칙은 변경하지 않는다.

### 4.3 §6.3 최종 상태 우선순위

> 각 판정의 전제인 후보 제목 타입 및 정규화 유효성 확인을 먼저 수행한다. 제목 정규화에 실패한 문자열 후보는 `DEFERRED(CANDIDATE_TITLE_INVALID)`로 확정하고 후속 Topic·Source·Event·Category 정책을 실행하지 않는다. 제목이 유효한 경우 기존 1차 Topic → Source별 검증 → 2차 기사 범위 근거 → Event → Category → 기술 판정 순서를 따른다. 제목 오류 보류는 관심 범위 밖(`OUT_OF_SCOPE`)이나 Source 부족(`NO_ELIGIBLE_SOURCE`)으로 바꾸지 않는다.

대표 판정표에 `후보 제목 정규화 불가 | DEFERRED | CANDIDATE_TITLE_INVALID` 행을 추가한다.

### 4.4 §6.4 판정 결과 불변조건

> `DEFERRED(CANDIDATE_TITLE_INVALID)`는 `normalized_title=None`, `valid_sources=()`, `category_ids=()`, `source_issues=()`를 반환하고 원본 `warnings`를 보존한다. `source_issues=()`는 Source 검사 미수행을 의미하며 Source 무결성 보증이 아니다. 정상 보류와 기술 실패를 구분하는 기존 규칙은 유지한다.

### 4.5 §7.2 인수 테스트

다음 계약 사례를 추가한다.

| ID | 핵심 검증 |
|---|---|
| R03-01 | 공백 제목 → `DEFERRED(CANDIDATE_TITLE_INVALID)` |
| R03-02 | 정규화 후 256자 제목 → 동일 판정 |
| R03-03 | 정확히 255자 → 후속 검증 계속 |
| R03-04 | 유효 제목 + Source 없음 → 기존 `NO_ELIGIBLE_SOURCE` |
| R03-05 | 유효 제목 + 명백한 범위 밖 → 기존 `OUT_OF_SCOPE` |
| R03-06 | 잘못된 제목 + 다른 메타데이터 존재 → `WOULD_ACCEPT` 금지 |
| R03-07 | 잘못된 제목 + Warning → Warning 보존·후속 정책 미호출 |
| R03-08 | 후보 제목 비문자열 → 정상 보류가 아닌 실행 실패 |

## 5. 구현·검증과 문서 상태

### 5.1 변경 책임

- `backend/app/external_trends/types.py`: `ReasonCode.CANDIDATE_TITLE_INVALID` 추가.
- `backend/app/external_trends/candidate_validator.py`: 최종 `validate_p3_candidate()`에서 제목 정규화 `None` 반환을 `DEFERRED`로 전환.
- `backend/tests/external_trends/test_candidate_validator.py`: R-03의 독립 회귀 테스트 8개 추가.
- `normalizer.py`, `rss_parser.py`: R-03으로 인한 변경 불필요.

### 5.2 검증 기록 (사용자 로컬 실행 보고)

- R-03: **8 passed**
- V-19: **30 passed**
- R-01: **9 passed**
- R-02A + R-02B: **13 passed**
- P3 전체: **217 passed**
- P1~P3 전체: **370 passed**
- Ruff: **All checks passed!**

위 수치는 **사용자가 로컬에서 실행하여 제공한 로그**다. 확인한 원격 `feat-rss-p1-parser`의 `candidate_validator.py`는 여전히 R-03 이전의 `ValidationExecutionError` 분기를 가지고 있었다. 따라서 **R-03 로컬 통과와 소스 코드 원격 반영은 구분**해야 한다. 이 보완안의 작업 브랜치 등록은 소스 코드의 원격 반영을 의미하지 않는다.

### 5.3 현재 범위에서 변경하지 않는 것

- 기존 FROZEN 파일의 무승인 수정 및 이 보완안 문서 외 원격 GitHub 쓰기.
- 실제 RSS 수집/네트워크 접속, DB 저장/트랜잭션, 외부 데이터 이용·게시 권한.
- P2 정규화 기준(255 코드포인트/NFC/ASCII만 소문자화)과 P1 Parser의 누락 Item 처리.
- R-01 `기타` 근거, R-02A 일반 Child 근거, R-02B 기사 기반 범위 판정의 기존 동작.

## 6. 승인·통합 체크리스트

- [x] 기존 FROZEN과 새 ReasonCode 간 계약 공백 식별
- [x] R-03 행동 규칙 및 우선순위 정리
- [x] R-03 Red → Green 및 로컬 관련·전체 회귀 PASS 보고
- [x] 사용자가 별도 보완안 문서의 작업 브랜치 원격 반영 승인(2026-11-02)
- [ ] 기존 FROZEN 대비 문구의 최종 개정·병합 승인
- [ ] 승인 후 기존 FROZEN의 버전/변경 이력 및 §3.2·§5.1·§6.3·§6.4·§7.2 반영 방식 결정
- [ ] R-04 및 최종 Final Review에서 전체 문서·코드 정합성 재점검
- [ ] 원격 체크포인트/PR 진행 시 해당 버전과 SHA를 최종 재확인

**결론**: R-03은 **입력 제목의 검증 불가능성 → 정상 보류**, **타입·정책·구현 문제 → 실행 실패**라는 책임 경계를 명확히 한다. 판정 우선순위 변경은 제목이 유효해야만 1차 주제 판정이 가능하다는 전제를 명시적으로 추가하는 것이며, 유효한 제목에 대한 나머지 우선순위는 유지한다.