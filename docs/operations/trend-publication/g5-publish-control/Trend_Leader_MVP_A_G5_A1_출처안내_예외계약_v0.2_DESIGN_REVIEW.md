# Trend Leader MVP-A — A1 `source_title` 자체 작성 출처 안내 조건부 허용 계약 v0.2 (설계·검증 기록)

> 기준일: **2026-11-04 (KST)**  
> 상태: **사용자 B안 선택 확정 / 독립 오프라인 검사 v0.2 프로토타입 검증 PASS / 운영 G5·G6 HOLD**  
> 상위 기준: `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`  
> 관련 승인 기록: `Trend_Leader_MVP_A_G4_실전검토카드_Python_3_15_20261104_v0.6_APPROVAL_RECORDED_A1_HOLD.md`  
> 변경 범위: **A1 오프라인 승인 증거 ↔ Batch 후보 JSON 대조 규칙만 확장**. FastAPI/React Native/DB 스키마/Google RSS 권한 정책/FROZEN 기술 계약은 변경하지 않음. 실데이터·실서비스 등록 없음.

## 1. 해결하려는 충돌과 결정

- **현행 G4 승인 표시:** Python 3.15 실기기에서 `source_title="Python.org 공식 출시 안내"`, `source_platform=ETC`(화면 표기 `기타`), `thumbnail_url=null`을 표시했고 담당자가 그 범위를 승인했다.
- **기존 A1 v0.1:** `canonical_ref()`가 `source_title is None and thumbnail_url is None`만 통과시킨다. 따라서 승인된 UI 내용 그대로는 `INVALID_PUBLISH_PAYLOAD`이다.
- **사용자 선택 B안:** 자체 작성 출처 안내 문자열을 조건부로 허용하는 검사 계약으로 확장한다. 외부 원제목·원문·이미지를 자동으로 허용하지 않는다.
- **설계 적용:** 승인된 Python 3.15 제목·요약·출처 링크·화면 문구는 변경하지 않는다. 승인 결정(G4) 자체를 취소하지 않는다. A1 기술 대조 적격성은 **기존 v0.1 기준으로는 HOLD**, **v0.2 도구로 실제 G4 승인 증거를 대조하기 전에도 HOLD**다.

### 대안 비교

| 접근 | 이점 | 비용/위험 | 결론 |
|---|---|---|---|
| A. `source_title=null` | 기존 대조기 그대로 사용 | 승인한 화면과 달라짐, 콘텐츠 재검토 필요 | 선택하지 않음 |
| **B. 출처 안내의 사람 검토 근거를 명시하여 조건부 허용** | 승인한 UI를 유지, DB/API 변경 없음 | `source_title`의 현재 DB 의미(`수집 자료 제목`)와 임시 용도 간 불일치; 검토 증거 진위는 시스템이 보장 못 함 | **MVP-A 한정 선택** |
| C. 별도 `source_display_label` 필드·DB/API/UI 분리 | 의미와 책임이 명확 | Schema/API/FROZEN 영향·회귀 범위 확대 | Post-MVP 설계 검토 후보 |

## 2. v0.2 자료 계약 (v0.1을 덮어쓰지 않음)

- 파일/문서 `schema`: `A1_RECONCILE_V02` 필수. 이전 v0.1 JSON을 v0.2로 묵시 변환하지 않고 중단한다.
- G4 승인 기록(`approvals.records[]`)에 필수 **메타데이터 필드** 두 개 추가:
  - `source_title_origin`: `NONE` 또는 `EDITORIAL_LABEL`
  - `source_label_evidence_id`: `null` 또는 출처 안내 문구가 자체 작성·검토됐음을 연결하는 **실제 증거 참조 ID**
- Batch 후보(`batch.items[]`)에 `source_title_origin` 필수 추가. 두 파일의 값이 다르면 `SOURCE_TITLE_ORIGIN_MISMATCH`로 제외.
- `content`의 **표시 필드 7개**(`title`, `summary`, `category_refs`, `source_platform`, `source_url`, `source_title`, `thumbnail_url`)는 기존과 동일. 새 메타데이터는 DB/API에 신규 필드가 생겼다는 뜻이 아니다.
- `NONE`: `source_title=null` 및 `source_label_evidence_id=null`만 허용.
- `EDITORIAL_LABEL`: `source_title`이 공백 경계 없는 **1~80자**의 개행·`<`·`>` 없는 일반 텍스트이고, `source_label_evidence_id`는 비어 있지 않아야 함. 별도 인간 검토에서 공식 원제목·제공 요약·브랜드 제휴 암시가 아님을 확인해야 한다.
- **변경하지 않는 차단:** `thumbnail_url=null` 필수; HTTPS 원문 링크 필수; Google RSS 파생/고위험/철회/미승인/권리·링크 검토 미완료 제외; `g6_status=HOLD`만 허용, 실제 게시 허가 0건.
- v0.2 `content_ref`는 기존 JSON 내용에 **`source_title_origin`과 `source_label_evidence_id`까지 포함하여** 정규 JSON+SHA-256으로 산출한다. 승인 후 문구·표시 내용·출처 선언·근거 ID가 바뀌면 이전 해시와 불일치하여 해당 후보를 보류한다.

**정규화 규칙:** `json.dumps({schema, policy_version, trend_ref, content, source_title_origin, source_label_evidence_id}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`을 UTF-8로 인코딩하여 SHA-256. 스냅샷·근거 진위에 대한 전자서명은 아니다.

### 서식 예시 (합성 예시, 실제 승인/게시 기록 아님)

승인 장부의 **추가 필드**:

```json
{
  "source_title_origin": "EDITORIAL_LABEL",
  "source_label_evidence_id": "SIM-E-G4-SOURCE-LABEL-001"
}
```

Batch item의 **추가 필드**:

```json
{
  "source_title_origin": "EDITORIAL_LABEL"
}
```

위 예시는 전체 JSON이 아니라 기존 필드에 **추가하는 조각**이다. 실제 구조는 동봉된 SIM JSON 두 파일 참고.

## 3. Python 3.15 승인 스냅샷과의 연결 규칙

- 기존 승인 카드 v0.6의 M-2 콘텐츠 자체는 그대로 보존한다. `source_title="Python.org 공식 출시 안내"`는 팀이 자체 작성한 출처 **안내 문자열**이라는 G4 기록의 설명을 근거로 `EDITORIAL_LABEL` 후보가 된다.
- **추천 증거 연결:** `E-G4-01-PY315`(개별 승인)와 `E-G4-03-PY315`(미리보기 화면·출처 표시)를 참고하여 담당자가 출처 안내 문구의 자체 작성·비복제 여부를 점검하고 **별도의 실제 증거 식별자**를 명시한다. 임의로 `SIM-...` 식별자를 실제 증거로 재사용하지 않는다.
- 현재 승인 카드의 `sha256:a5d83b3c1a6a38b1f56c19f87f4017fba41d4bb9f104eba9898b76ece1ca7688`은 **`G4_APPROVED_SNAPSHOT_V01` 지문**이다. v0.2의 `content_ref`와 **절대 동일시하지 않음**. v0.2 승인 장부에는 신규 계산값을 별도 기록한다.
- 사용자 승인 메시지는 2026-11-04에 존재하지만 **정확한 사건 발생 시각 및 실명 서명/권한 위임 원본은 확보되지 않았다**. 오프라인 스크립트의 `approved_at` 필드에 임의 시각을 채우지 않는다. 실제 증거 인수인계 시 정확한 기록 근거를 확인하거나 이후 담당자 서명/확인 시각을 구분하여 기입해야 한다.
- 이전 G4 결정이 있다는 사실과 **G5/A1 입력 매니페스트가 아직 갖춰지지 않았다**는 사실을 동시에 유지한다. 새 매니페스트에 **허위 승인자·시간**을 넣어 테스트를 통과시키지 않는다.

## 4. 유효성 및 안전 중단 검증 결과 (모두 합성/오프라인)

- v0.1 기존 자가 테스트: `10건 중 잠재 적격 2 / 제외 8`, PASS (기존 규칙 보존).
- v0.2 자가 테스트 및 독립 SIM JSON `--check`: **16건 중 잠재 적격 3 / 제외 13 / 게시 허가 0**, PASS.
- v0.2 추가 확인: 자체 출처 안내+증거가 있는 합성 후보 통과, 출처 안내 증거 누락 차단, 변경된 안내 문자열 해시 불일치, 출처 선언 불일치/미허용 값 차단, 81자 안내 차단, 근거 ID 변경 해시 불일치, 기존 v0.1 문서 버전 혼합 차단, 위장 G6 PASS 차단.
- **PASS의 의미:** 자료 구조와 변화 탐지만 검증한다. 문구의 진짜 작성자, 허가 범위, 원문 표현과의 실질적 유사성, 권리 보유자 승인은 검사할 수 없다.
- v0.2는 개발 PC에서 단독 실행하는 표준 Python 3 프로그램이며 FastAPI/SQLAlchemy/HTTP/DB를 사용하지 않는다. 서버의 미승인 INSERT/ACTIVE 기본값을 강제 차단하지 못한다.

## 5. 다음 Gate 인계 및 종료 조건

1. **실제 G4 증거 카드 기록 확인:** 승인자/승인 결정의 기준 시각 및 자체 출처 안내 검토 증거 식별자가 누락되지 않아야 한다.
2. **A1 매니페스트 2종 준비:** `approvals.records[]`의 v0.2 메타데이터 및 `batch.items[]`의 동일 origin 선언, 승인 대상과 동일한 `content`. 미확정 승인 정보는 채우지 않고 HOLD.
3. **v0.2 `content_ref` 생성:** 승인 대상 고정 내용과 검토 근거를 활용하여 계산. 서명 대신 쓰지 않으며 G4 문서 원래 스냅샷 지문은 보존.
4. **오프라인 대조 후 G5 인계:** `ELIGIBLE_FOR_REVIEW_ONLY`는 실제 게시 허가 아님. G6와 다른 G0/G5 증거는 여전히 별도.
5. **향후 개선 검토:** `source_title` DB 주석의 ‘수집 자료 제목’과 자체 안내 의미 충돌을 API/스키마의 명시적 출처표시 타입으로 분리할지 검토. 현재 MVP 계약·기능 동결 상태에서는 독립 사안.

**최종 판정:** **B안의 오프라인 설계·합성 검증 PASS.** 실제 Python 3.15 콘텐츠의 **G4 승인 결정은 유지**, A1 입력 실증·Batch 편입 **HOLD**, G5 운영 통제 **HOLD**, G6 운영 승인 **HOLD**, DB/앱 게시 **NOT_ATTEMPTED**.