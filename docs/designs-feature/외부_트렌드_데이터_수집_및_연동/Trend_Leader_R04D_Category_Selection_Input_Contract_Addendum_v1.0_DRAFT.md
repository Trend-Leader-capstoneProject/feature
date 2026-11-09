# Trend Leader RSS P0–P3 PoC — R-04D Category 선택 입력 타입 안전성 계약 보완안

- 문서 ID: `RSS-P3-R04D-ADDENDUM`
- 버전: `v1.0-DRAFT`
- 작성일: 2026-11-02
- 상태: **R-04D 코드·보완안 문서 작업 브랜치 원격 반영 확인(DRAFT) / 기존 FROZEN 미변경**
- 기준 작업 브랜치: `feat-rss-p1-parser`
- 기준 계약: `docs/designs-feature/외부_트렌드_데이터_수집_및_연동/Trend_Leader_RSS_P0-P3_PoC_Implementation_Contract_v1.0_FROZEN.md` (`dev`)
- 관련 보완안: `Trend_Leader_R03_Title_Validation_Contract_Addendum_v1.0_DRAFT.md`, `Trend_Leader_R04_Review_Contract_Addendum_v1.0_DRAFT.md` (R-04A~C)
- 적용 범위: **합성 Fixture 기반 P3 Category Child 선택 및 최종 검증의 입력 계약만**. RSS 네트워크 수집, DB Writer, 저장·게시, 실데이터 활용 권한은 제외한다.

> **효력과 상태**: 이 문서는 R-04D의 관찰된 결함·설계 선택·사용자 로컬 검증 보고를 기록한 초안이다. 기존 FROZEN v1.0을 변경하지 않으며, 문서 생성 자체가 신규 설계를 동결하거나 `dev` 병합을 승인하지 않는다. 코드의 GitHub 원격 반영은 아래 커밋으로 확인했다. CI 통과 여부는 별도 확인해야 한다.

## 1. 문제 정의

`CategoryCatalog.__post_init__()`의 R-04A 검사는 Catalog에 저장된 Root/Child 정책 데이터의 타입을 검증한다. 그러나 Catalog를 **조회하는 입력**인 `evidence_child_ids`와 P3의 `proposed_child_ids`는 별도 런타임 검증이 없었다.

- Python에서 `101 == 101.0`과 `True == 1`이 성립하므로 부적절한 `float`·`bool` ID가 `dict.get()`을 통과할 수 있다. 최종 `WOULD_ACCEPT.category_ids`에 `tuple[int, ...]` 계약을 위반하는 값이 포함될 수 있다.
- `"101"`과 같은 문자열 ID는 정수와 일치하지 않지만, 단순 미등록 ID와 구분되지 않아 정상 정책 보류(`CATEGORY_UNCLEAR`)로 잘못 처리된다.
- `[101]`처럼 해시할 수 없는 리스트가 Child ID로 주입되면 비정형 `TypeError`가 발생할 수 있다.
- 호출부의 `proposed_child_ids or ()`는 정상적인 `None` 외에 잘못된 `[]`·`""`·`0` 등도 빈 튜플로 바꾸어 입력 오류를 은폐한다.

**핵심 구분:** Catalog **데이터 자체**의 무결성 검증(R-04A)과 Catalog에 **전달하는 선택값**의 입력 검증(R-04D)은 서로 다른 책임이다.

## 2. 결정 계약 — R-04D

### 2.1 `CategoryCatalog.select_active_child_ids()`

- `evidence_child_ids`는 **정확히 `tuple`** 이어야 한다. `list`, `str` 등은 허용하지 않는다.
- 각 요소는 **정확히 `int`** 이어야 한다. `isinstance(x, int)`로는 `bool`을 구분하지 못하므로 `type(x) is int`를 기준으로 검사한다. `float`, `str`, `bool`, `list` 등의 값은 `ValidationExecutionError("invalid category selection")`로 처리한다.
- 컨테이너와 ID 타입 검증은 `dict` 조회·중복 제거 이전에 수행한다.
- 정상적인 빈 튜플 `()`는 **선택 근거가 없음**을 뜻하며 기존처럼 `None`을 반환한다.
- 정수 ID가 존재하지 않거나 Child 또는 Parent가 비활성 상태면 기존처럼 `None`을 반환한다. 이 경우 최종 P3에서는 `DEFERRED(CATEGORY_UNCLEAR)`가 가능하다.
- 정상 정수 ID는 기존대로 중복 제거 후 **오름차순 `tuple[int, ...]`** 로 반환한다. ID 양수·범위·새 명명 규칙을 도입하지 않는다.

### 2.2 `None`의 처리 책임

- `None`은 `select_active_child_ids()`의 입력 타입이 아니다. P3 호출부에서만 **제안 근거 미제공**으로 허용한다.
- `evaluate_category_unclear_gate()` 및 최종 `validate_p3_candidate()`는 `proposed_child_ids is None`일 때에만 `()`로 변환한다.
- `[]`, `""`, `0` 등의 잘못된 입력을 truthiness 기반 `or ()`로 삼키지 않는다. Category 선택 단계에 도달하면 Catalog에서 실행 오류로 처리한다.
- 기존 Gate 우선순위는 유지한다. 1차 Topic에서 `SKIPPED`되거나 Event Gate에서 `DEFERRED`된 후보는 뒤의 Category Gate를 실행할 필요가 없다. 따라서 R-04D는 **Category 선택 단계에 실제로 도달한 입력**에 관한 계약이다.

### 2.3 정상 판정과 실행 오류의 구분

| 입력 또는 상황 | 기대 동작 |
|---|---|
| `(101,)` 등 유효한 활성 Child ID | 정상 선택; 근거가 모두 충족되면 `WOULD_ACCEPT` 가능 |
| `(101, 101)` | `(101,)`로 안정적인 중복 제거 |
| `()` / 최종 Validator의 `None` | 선택 근거 부족; 기존 `DEFERRED(CATEGORY_UNCLEAR)` |
| `(999,)` 등 정상 정수이지만 미등록 ID | 기존 `DEFERRED(CATEGORY_UNCLEAR)` |
| 비활성 Child/Parent | 기존 선택 실패, `CATEGORY_UNCLEAR` 가능 |
| `(101.0,)`, `("101",)`, `(True,)`, `(101, True)` | `ValidationExecutionError` |
| `([101],)` 등 해시 불가 요소 | 원시 `TypeError`가 아닌 `ValidationExecutionError` |
| `[101]`, `[]`, `"101"` 등 컨테이너 위반 | `ValidationExecutionError` |

## 3. 책임 분리와 트레이드오프

**채택: Catalog 메서드에서 입력 타입을 검사하고, 두 호출부에서는 `None`만 명시적으로 변환한다.**

- 대안 A: `validate_p3_candidate()` 진입부에서 모든 타입 오류를 확인. 장점은 입력 경계가 단일하지만, 직접 `CategoryCatalog`를 호출하는 테스트·다른 재사용 경로를 보호하지 못한다. 또한 기존 Gate 우선순위를 바꿀 가능성이 있다.
- **대안 B(채택):** `CategoryCatalog.select_active_child_ids()`에서 검증. 직접 호출과 최종 검증을 동일 규칙으로 보호한다. 호출부의 `or ()` 제거가 함께 필요하다.
- 선택 근거가 아예 없거나 정상 정수로 확인된 뒤 유효한 Category를 찾지 못한 상황은 **입력 타입 오류가 아니므로** 무조건 실행 실패시키지 않는다.

## 4. 수정 책임 범위

| 파일 | 변경 내용 |
|---|---|
| `backend/app/external_trends/candidate_validator.py` | `CategoryCatalog.select_active_child_ids()`, `evaluate_category_unclear_gate()`, `validate_p3_candidate()`의 타입 경계 보완 |
| `backend/tests/external_trends/test_candidate_validator.py` | R-04D 테스트 19개 추가 |
| `backend/app/external_trends/types.py` | 변경 없음; 새 ReasonCode 불필요 |
| `backend/app/external_trends/rss_parser.py` / `normalizer.py` | 변경 없음 |

## 5. 테스트 증거 — 사용자가 로컬에서 보고한 결과

- **Red:** R-04D 19개 중 `11 failed, 8 passed` (잘못된 ID, 컨테이너, bool/float 혼동, 최종 Validator 입력 경계에서 실패 재현).
- **Green:** `19 passed`, R-04A~D 관련 `36 passed`, 기존 V-06/V-11/V-13 관련 `39 passed`.
- **P3 전체:** `253 passed`.
- **P1~P3 전체:** **`406 passed`**.
- **정적 검사:** `All checks passed!` (Ruff).
- 사용자가 보고한 로컬 작업 트리는 `candidate_validator.py`, `test_candidate_validator.py` 두 파일 수정(` M`)이었다. 이후 원격 코드 커밋이 확인됐다.

위 숫자는 **사용자가 제공한 로컬 테스트 출력**이며 별도 원격 CI 실행이나 외부 환경 검증의 증거가 아니다.

### 5.1 원격 코드 체크포인트 확인(2026-11-02)

- 브랜치: `feat-rss-p1-parser`
- 원격 커밋: [`4578aa3b5f3cbff3ed42041033a2413f4dcf18ea`](https://github.com/Trend-Leader-capstoneProject/feature/commit/4578aa3b5f3cbff3ed42041033a2413f4dcf18ea)
- 커밋 메시지: `[fix/external-trends] Category Child ID 입력 타입 검증 보완`
- 변경 파일: `backend/app/external_trends/candidate_validator.py`, `backend/tests/external_trends/test_candidate_validator.py` (2개)
- 원격 확인: Category 선택 시 정확한 튜플·정수 타입 검사, `None`의 명시적 분리, R-04D 테스트 6개 함수 확인
- `dev` 대비 브랜치: 12 commits ahead / 0 behind (확인 당시)
- 미확인: 원격 CI 실행·전체 406개 테스트의 서버 측 재검증
- 문서 상태: 사용자 승인에 따라 R-04D 보완안을 `feat-rss-p1-parser` 브랜치에 신규 문서로 등록했다. 문서의 DRAFT 상태와 기존 FROZEN의 효력은 유지한다.

## 6. FROZEN v1.0 통합 제안 (원본은 유지)

### 6.1 §3.2 출력 타입·§6.4 결과 불변조건

> Category에 대한 제안·근거 ID는 런타임에 `tuple[int, ...]` 계약을 검증한다. `bool`, `float`, 문자열, 리스트 등 잘못된 입력을 `CATEGORY_UNCLEAR`와 같은 정상 후보 보류로 대체하지 않으며 `ValidationExecutionError`로 분리한다. Catalog에 저장된 정책 데이터의 검증과 Catalog에 전달하는 선택 입력의 검증은 모두 필요하다. 정상 판정에서 선택된 `category_ids`는 실제 정수 ID의 오름차순 튜플이다.

### 6.2 §6.3 최종 판정 우선순위

> 1차 Topic·Source·2차 Topic·Event Gate를 지난 경우에 Category 선택 입력을 검증한다. `proposed_child_ids=None`은 근거 미제공으로 보고 빈 튜플과 동일하게 취급한다. 빈 리스트 등 잘못된 컨테이너는 빈 튜플로 강제 변환하지 않는다. 잘못된 타입은 실행 실패, 정상 정수 ID의 미등록·비활성·근거 부족은 기존 `CATEGORY_UNCLEAR`로 처리한다.

### 6.3 §7.2 인수 테스트 확장

| ID | 검증 | 기대 결과 |
|---|---|---|
| R04D-01 | `float`·`str`·`bool`·혼합·해시 불가 Child ID | `ValidationExecutionError` |
| R04D-02 | `list`, 빈 `list`, `str` 컨테이너 | `ValidationExecutionError` |
| R04D-03 | `True` vs 정수 Child ID `1` | `ValidationExecutionError` |
| R04D-04 | 최종 Validator에서 `(101.0,)`, `[]` | `ValidationExecutionError` |
| R04D-05 | 정상 활성 ID·중복 ID·빈 튜플·미등록 정수 ID | 기존 선택 결과 보존 |
| R04D-06 | 최종 Validator의 정상 ID·미등록 ID·`None`·빈 튜플 | 기존 `WOULD_ACCEPT`/`CATEGORY_UNCLEAR` 보존 |

## 7. 남은 작업과 승인 경계

- [x] R-04D Red 재현: `11 failed, 8 passed` 사용자 보고
- [x] R-04D Green 및 P1~P3 전체: `406 passed`, Ruff PASS 사용자 보고
- [ ] 로컬 변경 두 Python 파일의 `git diff --check`, 변경 범위, Secret 포함 여부 점검
- [x] 해당 두 Python 파일만 코드 체크포인트 커밋하고 원격 푸시
- [x] 원격 `feat-rss-p1-parser`에서 반영된 파일과 커밋 SHA 재검증 (`4578aa3`)
- [x] 사용자 승인에 따라 R-04D 보완안을 GitHub 신규 파일로 등록(2026-11-02)
- [ ] R-03·R-04A~D 통합 FROZEN 개정안의 사용자 검토·승인
- [ ] 최종 CI 및 `dev` 병합 판단

**결론:** R-04D는 Category의 정책값 검증과 선택 입력 검증을 모두 갖춤으로써, 잘못된 타입을 정상 Category 보류로 오인하거나 `WOULD_ACCEPT`에 비정수 식별자를 포함하는 경로를 차단한다. 자동 테스트 통과의 실행 증거는 사용자 로컬 보고에 한정하고, 코드 원격 반영 자체는 GitHub에서 직접 확인했다.