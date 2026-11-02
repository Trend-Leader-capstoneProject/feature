# Trend Leader RSS P0–P3 PoC — R-04 최종 안전·판정 정합성 계약 보완안

- 문서 ID: `RSS-P3-R04-ADDENDUM`
- 버전: `v1.0-DRAFT`
- 작성일: 2026-11-02
- 상태: **별도 설계 보완안 초안 — 작업 브랜치 원격 등록 / 원본 FROZEN 미변경**
- 기준 브랜치: `feat-rss-p1-parser` (원격 코드 확인; 테스트 결과는 사용자 로컬 보고 기준)
- 기준 계약: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_RSS_P0-P3_PoC_Implementation_Contract_v1.0_FROZEN.md` (`dev`)
- 연결 보완안: `Trend_Leader_R03_Title_Validation_Contract_Addendum_v1.0_DRAFT.md` (작업 브랜치 원격 등록, 커밋 `c903b1c`)
- 범위: 합성 Fixture 기반 P3 검증. RSS 실수집, DB Writer, 저장·게시, 권리 검증은 **범위 밖**.

> **문서 효력**: R-04A~R-04C의 구현·테스트 관찰 결과 및 승인할 계약 변경을 분리해 기록한다. 이 초안의 작성은 FROZEN v1.0을 개정하거나 `dev` 병합을 승인한다는 뜻이 아니다. 사용자의 로컬 테스트 보고를 GitHub CI 결과로 오인하지 않는다.

## 1. 문제와 변경 근거

### 1.1 R-04A — CategoryCatalog 정책 데이터 오염

- `CategoryRoot.category_id`, `CategoryChild.category_id`/`parent_id`가 Python 타입 힌트상 `int`여도 런타임 객체 생성에서 `str`·`float`·`bool`이 자동 배제되지는 않는다.
- 특히 `is_active="False"`는 문자열로서 truthy이며, `True`는 `int`의 하위 타입이라는 Python 특성 때문에 일반적인 참/거짓 검사만으로 잘못된 설정을 통과시킬 위험이 있었다.
- **결정**: `CategoryCatalog.__post_init__()`에서 `roots`/`children`의 tuple 계약, 각각의 Root/Child 객체 타입, ID의 **정확한 `int`**, 활성 상태의 **정확한 `bool`**, 코드·이름의 문자열 타입을 검사한다. 잘못된 정책 데이터는 `ValidationExecutionError`로 실패시키며 정상 `CATEGORY_UNCLEAR`로 숨기지 않는다.
- **유지**: 중복 Root/Child ID, 중복 Root 코드, Root/Child ID 충돌, 존재하지 않는 부모 참조 검증. 유효한 정책에서 비활성 Child가 선택되지 않는 기존 `None → CATEGORY_UNCLEAR` 동작 유지.
- **미확정 정책을 임의로 도입하지 않음**: ID 양수 범위, 코드 정규식, 이름의 공백 금지 등은 별도 계약 없이는 추가하지 않는다.

### 1.2 R-04B — 중복 Source의 판단 근거 소실

- V-18의 `screen_candidate_sources()`는 제목·안전 URL·승인 도메인·명시적 관련성 검증 후 동일 `source_key`의 두 번째 이후 Source를 `DUPLICATE_SOURCE`로 기록하고 `valid_sources`에서 제외한다.
- 그러나 R-02B의 `evaluate_article_topic_scope_gate()`가 `valid_sources`만 평가하면, 중복으로 제외된 기사에 명시된 `CLEAR_OUT_OF_SCOPE`가 판단에서 사라질 수 있었다. 이때 첫 기사와 두 번째 기사의 근거 순서에 따라 `WOULD_ACCEPT` 또는 `SKIPPED`로 잘못 확정되는 경로가 테스트에서 재현되었다.
- **결정**: 저장 후보로 반환하는 `valid_sources`에는 최초 Source 1개만 남긴다. 단, `source_issues`가 `DUPLICATE_SOURCE`로 표시한 **검증 통과 중복 기사**의 원본 제목을 *범위 근거 판단에만* 추가한다. 다른 실패 사유(`BLOCKED_SOURCE_DOMAIN`, `UNKNOWN_SOURCE_DOMAIN`, `SOURCE_UNRELATED` 등)는 범위 근거로 확장하지 않는다.
- **유지**: 검증된 중복 Source의 저장 가능 목록 복원 금지; `source_issues`의 최초 등장 순서와 중복 사유 유지. 사건 ID 판정은 별도 Event Gate의 책임이다.
- **실행 안전**: 중복 issue 인덱스와 원본 Source 매칭이 불완전하거나 중복된 인덱스가 발견되면 정상 후보 판정으로 간주하지 않고 `ValidationExecutionError` 처리.

### 1.3 R-04C — 범위 모호성과 사건 모호성의 사유 코드 분리

- R-02B/R-04B에서 일부 기사만 `CLEAR_OUT_OF_SCOPE`일 때 `DEFERRED(EVENT_AMBIGUOUS)`를 사용했다. 이는 실제 사건 ID가 다르거나 사건 일관성을 판정할 수 없는 경우와 의미가 다르다.
- **결정**: 새로운 `ReasonCode.TOPIC_SCOPE_UNCLEAR = "TOPIC_SCOPE_UNCLEAR"`를 도입한다. 명백한 범위 밖 근거가 일부 존재하지만 다른 검증 대상 기사는 `POSSIBLE_IN_SCOPE` 또는 `AMBIGUOUS`인 경우 `DEFERRED(TOPIC_SCOPE_UNCLEAR)`.
- **유지**: 모든 범위 검증 대상이 `CLEAR_OUT_OF_SCOPE`면 `SKIPPED(OUT_OF_SCOPE)`. 명백한 범위 밖 근거가 전혀 없으면 기존 Event·Category 단계로 진행. Event Gate의 사건 충돌·불확정은 계속 `DEFERRED(EVENT_AMBIGUOUS)`.
- `TOPIC_SCOPE_UNCLEAR`는 **주제 범위를 확정하지 못했다**는 뜻이지, 기사 내용의 사실성이나 실제 관심 분야 적합성을 판정했다는 뜻이 아니다.

## 2. 최종 판정 우선순위 — R-03 포함

실제 P3의 정상 결과 판단은 다음 순서다. 각 Gate는 앞 단계가 종료 판정을 반환하면 실행하지 않는다. 타입 위반과 정책 설정·실행 오류는 해당 위치에서 예외로 전파하며 `CandidateDecision.FAILED`나 `DEFERRED`로 변환하지 않는다.

| 순서 | Gate | 종료 조건 및 반환 | 비고 |
|---:|---|---|---|
| 0 | 후보 제목 타입·정규화 | 비문자열 → 실행 실패; 문자열 제목이 비거나 정규화 후 255자 초과 → `DEFERRED(CANDIDATE_TITLE_INVALID)` | R-03, Source 검사 미실행 |
| 1 | 1차 Topic | 명시적 `CLEAR_OUT_OF_SCOPE` → `SKIPPED(OUT_OF_SCOPE)` | 명백한 근거만 조기 제외 |
| 2 | Source Screening | 검증된 Source 0건 → 차단만 있는 경우 기존 `SKIPPED(BLOCKED_SOURCES_ONLY)` 또는 기존 Source 관련 `DEFERRED` | Source 0건이면 이후 범위·사건·Category 게이트 미실행 |
| 3 | 2차 기사 Topic | 모든 평가 대상이 명백히 밖 → `SKIPPED(OUT_OF_SCOPE)`; 일부만 명백히 밖 → `DEFERRED(TOPIC_SCOPE_UNCLEAR)` | R-04B: `DUPLICATE_SOURCE`의 근거도 평가 (저장 후보에는 포함하지 않음) |
| 4 | Event Consistency | 사건 충돌·불확정 → `DEFERRED(EVENT_AMBIGUOUS)` | Topic 모호성 코드로 대체 금지 |
| 5 | Category 구조·근거 | 활성 Child 제안·근거·`기타` 조건 미충족 → `DEFERRED(CATEGORY_UNCLEAR)` | CategoryCatalog **오염 데이터는 별도 실행 실패** |
| 6 | 최종 판정 | 모든 제약 충족 → `WOULD_ACCEPT(VALIDATED_BY_FIXTURE_RULES)` | 실제 저장·게시와 무관 |

### 2.1 대표 충돌 사례

| 상황 | 최종 결과 | 근거 |
|---|---|---|
| 제목 무효 + 적합 Source 존재 | `DEFERRED(CANDIDATE_TITLE_INVALID)` | 제목 유효성 우선; Source·기사 판단 생략 |
| 유효 제목 + 적합 Source 없음 | 기존 Source 부족 판정 | Category 누락이나 2차 Scope 보다 우선 |
| 적합 기사 모두 명백히 범위 밖 | `SKIPPED(OUT_OF_SCOPE)` | 2차 명백한 제외 |
| 적합 기사 한 건 범위 밖, 다른 건 범위 밖으로 확정되지 않음 | `DEFERRED(TOPIC_SCOPE_UNCLEAR)` | 실제 사건 충돌을 가정하지 않음 |
| 승인·관련성 확인된 중복 URL 기사끼리 범위 근거가 달라짐 | `DEFERRED(TOPIC_SCOPE_UNCLEAR)` | R-04B 근거 유실 방지 |
| 범위 제외 근거 없음 + 서로 다른 사건 ID | `DEFERRED(EVENT_AMBIGUOUS)` | Event 책임 유지 |
| 범위·사건 확인 + 활성 Child 근거 부족 | `DEFERRED(CATEGORY_UNCLEAR)` | Category 책임 유지 |
| CategoryCatalog에 `is_active="False"` | `ValidationExecutionError` | 정상 비활성 Category와 다른 **설정 오류** |

## 3. 출력 불변조건

- `WOULD_ACCEPT`: 유효한 정규화 제목(1~255 코드포인트), 검증된 중복 없는 `valid_sources` 최소 1개, 근거 있는 활성 Child ID 최소 1개; 실제 RSS 콘텐츠 이용 권한·DB 저장·공개를 뜻하지 않는다.
- `SKIPPED`/`DEFERRED`: `valid_sources=()`, `category_ids=()`; `warnings` 보존, 평가된 Source의 `source_issues` 보존.
- `DEFERRED(CANDIDATE_TITLE_INVALID)`: `normalized_title=None`, `valid_sources=()`, `category_ids=()`, `source_issues=()`, 입력 `warnings` 유지. Source 검사 미수행을 의미한다.
- `DEFERRED(TOPIC_SCOPE_UNCLEAR)`: 정규화된 후보 제목은 존재하고 Source는 한 건 이상 적합했으나, Scope 근거가 혼재하여 저장·게시할 수 없는 결과. 중복 Source의 `DUPLICATE_SOURCE` 문제를 소실하지 않는다.
- `DEFERRED(EVENT_AMBIGUOUS)`: 실제 Event 규칙이 사건 불명확/충돌을 보고할 때 사용. Scope 혼재 여부를 대신 표현하지 않는다.
- `ValidationExecutionError` 및 타입 오류는 `CandidateEvaluation` 정상 결과에 포함하지 않는다.

## 4. FROZEN v1.0 반영 시 최소 수정안 (원본 보존)

### 4.1 §3.2 출력 타입 의미

> `ReasonCode.TOPIC_SCOPE_UNCLEAR`는 기사별 관심 범위의 명백한 범위 밖 근거와 범위 밖으로 확정되지 않은 근거가 함께 존재하여 판정을 보류하는 경우에 사용한다. `EVENT_AMBIGUOUS`는 사건 충돌·불확정에 한정한다. Source는 저장 후보 목록과 판정 근거 목록이 다를 수 있으며, 적합한 중복 Source의 제목은 범위 판정에만 참여하고 `valid_sources`에는 중복 저장하지 않는다.

### 4.2 §6.1 주입 정책 및 §6.4 결과 불변조건

> `CategoryCatalog`의 Root/Child 데이터는 활성 상태가 정확한 `bool`, 식별자/부모 ID가 정확한 `int`인지를 검사한다. 잘못된 타입, 중복 식별자·코드 또는 부모 참조 오류는 `ValidationExecutionError`로 구분한다. 정상적인 비활성 Root/Child는 실행 오류가 아니라 선택 불가능한 정책 상태다.

### 4.3 §6.2 2단계 선별

> 승인 도메인·제목·URL·관련성 검증에 성공했으나 동일 `source_key`로 제외된 `DUPLICATE_SOURCE` 기사는 저장 대상에서는 제외하되, 명시적 기사별 관심 범위 판정의 근거 유실을 막기 위해 Scope 검증 대상에 포함한다. 그 외의 검증 실패 기사는 범위 밖 판정을 좌우하지 않는다.

### 4.4 §6.3 최종 우선순위 및 ReasonCode

> 2차 기사 범위 판정에서 모든 검증 대상이 `CLEAR_OUT_OF_SCOPE`면 `SKIPPED(OUT_OF_SCOPE)`, 일부만 `CLEAR_OUT_OF_SCOPE`이면 `DEFERRED(TOPIC_SCOPE_UNCLEAR)`로 처리한다. 명백한 범위 밖 근거가 없다면 Event Gate로 진행한다. Event Gate의 사건 불명확·충돌은 `DEFERRED(EVENT_AMBIGUOUS)`를 유지한다. 이 Gate들의 순서는 R-03의 제목 유효성 Gate, 1차 Topic, Source Screening 이후에 적용한다.

### 4.5 §7.2 인수 테스트 확장

| ID | 핵심 검증 | 예상 결과 |
|---|---|---|
| R04A-01 | 활성 상태 타입 오염 4종 | `ValidationExecutionError` |
| R04A-02 | Root/Child/parent ID 타입 오염 4종 | `ValidationExecutionError` |
| R04A-03 | 정상 활성 Child | 선택 성공 |
| R04A-04 | 정상 비활성 Child | 선택 실패(`None`) |
| R04B-01 | 같은 URL, Scope 근거 혼합(순서 2종) | `DEFERRED` + `DUPLICATE_SOURCE` 보존 |
| R04B-02 | 같은 URL, Event ID 충돌 | `DEFERRED(EVENT_AMBIGUOUS)` |
| R04B-03 | 같은 URL, 같은 사건 | 최초 Source 유지, `WOULD_ACCEPT` 가능 |
| R04B-04 | 관련성 없는 기사 | Scope 판정 근거에서 제외 |
| R04C-01 | 기존 직접 Gate / 최종 경로의 Scope 혼합 | `TOPIC_SCOPE_UNCLEAR` |
| R04C-02 | 중복 URL Scope 혼합 | `TOPIC_SCOPE_UNCLEAR` |
| R04C-03 | `CLEAR_OUT_OF_SCOPE` + `AMBIGUOUS` | `TOPIC_SCOPE_UNCLEAR` |
| R04C-04 | 두 기사의 다른 Event ID | `EVENT_AMBIGUOUS` 유지 |

## 5. 검증 기록 및 현재 상태

### 5.1 사용자가 직접 실행해 보고한 테스트

| 단계 | 회귀 테스트 결과 | 정적 검사 |
|---|---|---|
| R-03 종료 | P1~P3 `370 passed` | Ruff PASS |
| R-04A 종료 | P1~P3 `380 passed` | Ruff PASS |
| R-04B 종료 | P1~P3 `385 passed` | Ruff PASS |
| **R-04C 종료** | **P1~P3 `387 passed`** | **Ruff PASS** |

해당 수치는 사용자가 직접 제공한 **로컬 실행 로그**다. 이 문서 생성 시점에 별도 GitHub CI 재실행 또는 사용자의 로컬 staged diff 전체 재검토를 수행한 것은 아니다.

### 5.2 파일별 작업 범위

- `backend/app/external_trends/candidate_validator.py`: R-04A `CategoryCatalog` 타입 검증, R-04B 중복 기사 범위 근거 반영, R-04C 반환 사유 분리.
- `backend/app/external_trends/types.py`: R-03 `CANDIDATE_TITLE_INVALID`, R-04C `TOPIC_SCOPE_UNCLEAR` 추가.
- `backend/tests/external_trends/test_candidate_validator.py`: R-03, R-04A~R-04C 테스트 및 기존 R-02B 기대 사유 변경.
- `normalizer.py`, `rss_parser.py`: 이 변경으로 인한 추가 수정 없음.

### 5.3 이전 R-03 보완안과의 정합성 유의사항

작업 브랜치에 등록된 **R-03 DRAFT**는 작성 시점의 동작을 기록하므로, R-03 §3의 범위 혼합 판정에 `DEFERRED(EVENT_AMBIGUOUS)`가 남아 있을 수 있다. **R-04C 이후 최종 계약에서는 이를 `DEFERRED(TOPIC_SCOPE_UNCLEAR)`로 대체**해야 한다. 기존 R-03 보완안을 삭제하거나 역사를 덮어쓰지 말고, 이 R-04 보완안과 연결하여 최신 판정 계약을 분명히 한다. 최종 FROZEN 개정은 별도 승인 후 수행한다.

### 5.4 아직 검증되지 않은 사항

- 로컬 staged diff의 범위와 외부 문서(`docs/infra/`)의 현재 Git 이력 상태.
- GitHub CI에서 R-03~R-04C 전체 테스트를 별도로 재실행했는지 여부는 **미확인**이다. 원격 코드 반영은 확인했으며 R-03 문서 커밋 `c903b1c` 이후 1개 커밋으로 위 Python 3개 파일만 변경됐다.
- CategoryCatalog의 명명 규칙·ID 양수 정책 등 추가 데이터 정책의 타당성. 본 보완에서는 합의되지 않은 규칙을 도입하지 않는다.
- `DUPLICATE_SOURCE`가 있는 비정상적 수동 주입 `SourceScreeningResult` 전체에 대한 완전한 무결성 보증. 현재 Scope Gate는 이슈 인덱스와 원본 기사 매칭에 대한 일부 방어만 수행한다.
- 실제 수집/저장/게시 권한, MariaDB 상태 및 P4 Writer의 검증 책임.

## 6. 최종 승인·체크포인트 전 확인

- [x] R-04A 오염 정책 데이터 Red→Green, 로컬 회귀 통과 보고
- [x] R-04B 중복 URL 판정 근거 소실 Red→Green, 로컬 회귀 통과 보고
- [x] R-04C 범위 vs 사건 ReasonCode Red→Green, 로컬 회귀 통과 보고
- [x] 로컬 P1~P3 전체 387 passed, Ruff PASS 보고
- [ ] Git staged diff가 지정된 Python 3개 파일만 포함하는지 확인
- [ ] `git diff --cached --check` 실행 결과 확인
- [ ] R-03 DRAFT와 R-04 DRAFT의 상호 관계를 최종 승인
- [x] 사용자 승인에 따라 R-04 DRAFT를 작업 브랜치에 별도 신규 문서로 등록(2026-11-02)
- [x] 코드 체크포인트 원격 반영 및 세 Python 파일 변경 확인
- [ ] 코드 체크포인트의 전체 커밋 SHA 문서 기록
- [ ] 원본 FROZEN v1.0 개정/병합 시점 별도 결정

**결론**: R-04는 정책 값 객체의 무결성, 중복 Source의 범위 근거 보존, ReasonCode 의미 분리를 통해 **안전한 보류·제외 판정**을 강화했다. 단, P3의 `WOULD_ACCEPT`는 합성 Fixture에 대한 기술적 채택 가능 판정이며 실제 DB 쓰기나 무인 게시는 허용하지 않는다.