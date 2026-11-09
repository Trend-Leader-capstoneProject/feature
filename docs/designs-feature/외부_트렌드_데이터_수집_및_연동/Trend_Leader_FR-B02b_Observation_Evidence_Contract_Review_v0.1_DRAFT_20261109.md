# Trend Leader — FR-B02b 독립 관측 증거 연결 계약 검토안 v0.1

> **상태: REVIEW DRAFT / 미동결 / 미구현 / 실제 증거 미확보 / 게시 HOLD**  
> 작성 기준: 2026-11-09 (KST)  
> 기준 저장소: `Trend-Leader-capstoneProject/feature`, `dev` HEAD `c1f1dc874b54e59f7a7c86d5886324de3a2e9cb6`  
> 기능 범위: **MVP-A의 자체 작성·수동 확보 콘텐츠 1건(Python 3.15), A1 v0.2 승인 스냅샷 보존형 P4 v1 연결**  
> 금지: P0~P3 FROZEN 개정, Google RSS 실호출·저장·게시, 외부 AI 호출, 운영 DB 쓰기, G4/G6 승인 상태 임의 변경, 실제 시간·승인 증거 생성  
> 관련 문서: P4 Final Review Addendum v0.2 §5.3~5.6 및 §7 FR-B02b; G4 Python 3.15 v0.7 N절; Python 3.15 G4↔A1 체크포인트 v0.2 §8; 운영 Gate v0.3; `docs/operations/trend-publication/evidence/README.md`.

## 0. 결정 요약

- **이 문서가 제안하는 계약의 대상**은 콘텐츠가 승인되었다는 사실이 아니라, **실제 외부 출처를 언제·어떤 방식으로 관측하고 그 기록을 어떤 승인 스냅샷에 연결했는지**에 관한 독립적인 *관측 증거*다.
- 현재 G4 개별 콘텐츠 승인은 **PASS/APPROVED**로 기록돼 있고 A1 v0.2 대조는 **ELIGIBLE_FOR_REVIEW_ONLY**다. 이는 실제 관측 증거·P4 구현·G5/G6 게시 허가를 의미하지 않는다.
- `approved_at`, `recorded_at`, 외부 원문 `pubDate`, P4의 DB `collected_at`은 **의미가 다른 시간**이다. 상호 대체·소급 변환하지 않는다.
- 최소 설계 제안: **기존 A1 콘텐츠·`content_ref`는 불변**으로 두고, P4 Envelope의 기존 후보 필드 `observation_evidence_ref`에서 **별도 보호된 관측 기록**을 참조한다.
- 실제 증거의 보호 저장소·기록 책임자·검토 권한 및 최초 관측 이벤트 실물이 확인되지 않았으므로 **FR-B02b는 완료가 아니라 계약 초안 작성 단계**다. 최종 동결 및 실제 게시 판단을 하지 않는다.

## 1. 먼저 분리할 세 가지 질문

| 질문 | 증거의 종류 | 현재 확보 정도 |
|---|---|---|
| 어떤 콘텐츠를 승인했는가? | G4 승인 카드, A1 v0.2 불변 콘텐츠 스냅샷 및 해시 | 기존 문서에 승인·대조 기록 존재 |
| 해당 출처를 실제로 언제 확인·수집했는가? | 독립 관측 이벤트 및 시각·방법·원문 URL·원본 기록 | 2026-11-04 방문 **날짜 수준 보고**는 있으나 P4용 실제 시각·증거 연결은 미충족 |
| 실제 서비스를 통해 게시해도 되는가? | G4 유효성, 관측 증거, G5 실행 안전성, 독립 G6 승인, Batch 실행 허가 | G5/G6 HOLD, 미게시 |

**중요:** Python 3.15은 뉴스 인기도·Google Trends 검색량을 증명하는 사례가 아니라, **공식 발표 자료를 수동 확인한 편집형 MVP-A 콘텐츠**다. 원문 링크를 관측했다는 증거는 트렌드의 검색량이나 유행 원인을 입증하지 않는다.

## 2. 기존 확정안과의 접점 및 충돌 방지

1. **A1 v0.2 불변:** 승인한 7개 콘텐츠 필드(`title`, `summary`, `category_refs`, `source_platform`, `source_url`, `source_title`, `thumbnail_url`), `source_title_origin`, `source_label_evidence_id`, `canonical_ref()` 직렬화 규칙을 변경하지 않는다.
2. **P4 v1 Envelope:** 상위 `schema_version`, `batch_id`, `a1_batch_ref`, `items[]` 및 item의 `trend_ref`, `review_evidence_id`, `content_ref`, `observation_evidence_ref` 구조는 **기존 P4 DRAFT의 제안**으로 유지한다. 이미 운영 구현되었다고 가정하지 않는다.
3. **출처 1건:** 현재 P4 A1 어댑터 범위는 Source **정확히 1건**, 검토된 HTTPS 원문 URL·비공백 자체 작성 출처 안내·`thumbnail_url=null`이다. 소스 없는 트렌드를 게시 가능하게 만드는 별도 요구를 FR-B02b로 우회하지 않는다.
4. **RSS 경계:** P0~P3 v1.1 FROZEN의 `DEFERRED(NO_ELIGIBLE_SOURCE)`와 RSS-OPS HOLD 유지. RSS 검색량·`pubDate`를 P4 수동 관측 증거로 대체하지 않는다.
5. **승인 구분:** G4의 `E-G4-01-PY315` 및 A1 적격 판정은 별도 근거다. `observation_evidence_ref`만 있다고 G4 승인·철회 상태·G6 유효성을 생략하지 않는다.
6. **기존 DB/API 변경 없음:** `Trend.first_collected_at`, `last_collected_at`, `TrendSource.collected_at`은 기존 UTC-naive 계약 유지. 이 초안은 신규 DB 컬럼/테이블/공개 API/Frontend 필드를 만들지 않는다.

## 3. 관측 이벤트 의미 (제안)

MVP-A에서 최초 검토 대상은 사용자가 승인한 **원문 페이지 자체**다. 단, 단순히 오늘 링크가 열렸다는 재확인과 서비스 데이터 취득 사건은 구분한다.

| 논리 이벤트 종류 (제안 명칭) | 뜻 | P4 수집 시각으로 사용 가능성 |
|---|---|---|
| `MANUAL_SOURCE_COLLECTION` | 담당자가 특정 출처와 승인 대상의 관련 사실을 직접 열람·확인하고 **서비스 콘텐츠의 근거로 수동 취득/등록한 사건** | 검증된 *같은 사건*일 때에만 후보. 정확한 관측 시각·자료·대상·검토가 필요 |
| `SOURCE_LINK_RECHECK` | 이미 수집한 출처의 링크/사실/이용 범위를 나중에 재확인한 사건 | 링크 유효성 보완 증거. **최초 수집 시각을 소급 생성하는 용도로 사용 불가** |

- `observed_at`: 사건이 **실제로 발생한 시각**, 타임존을 포함하는 offset-aware ISO 8601. 기록자 추측값·문서 생성일·날짜만의 `YYYY-MM-DD`는 불가.
- `recorded_at`: 증거를 보호 저장소에 **기록한 시각**. `observed_at`과 다를 수 있으며 같다고 가정하지 않음.
- `reviewed_at`: 검토 담당자가 관측 기록·A1 연결·증거의 신뢰성을 **확인한 시각**. G4 승인 시각과 다름.
- `approved_at`: **기존 G4 승인 또는 재확인 기록**의 시각. 관측 사건이 아님.
- `published_at`: **나중에 실제 게시가 허용되어 실행됐을 때**의 시각. 현재 존재한다고 가정하지 않음.
- `pubDate` 또는 공식 문서 게시일: 외부 콘텐츠 작성 시각. 위 관측·수집 사건을 자동으로 입증하지 않음.

**2026-11-04 자료의 처리:** 정확한 관측 시각을 가진 원본 증거가 없으면 과거 `MANUAL_SOURCE_COLLECTION`으로 소급 등록하지 않는다. 현재 새 관측을 수행한다면 *새로운 실제 시각*으로 `MANUAL_SOURCE_COLLECTION`을 기록하거나 재확인 목적이라면 `SOURCE_LINK_RECHECK`로 기록한다. 새 관측 사실이 기존 승인 스냅샷의 사실·링크·권리 상태와 다르면 **G4 재검토 전까지 HOLD**한다.

## 4. 관측 증거 최소 필드 계약 v1 후보 (미동결)

**원칙:** P4 Envelope에는 참조만, 불변 관측 원본은 별도 접근통제 영역에 보관한다. 아래 이름은 P4 v0.2의 논리 필드 후보를 구체화한 **제안**이지 현행 구현 스키마가 아니다.

| 필드 | 필수 제안 | 검증 목적 / 금지 조건 |
|---|---|---|
| `schema_version` | 필수 | `1` 제안. 미지원 버전은 거부; 자동 마이그레이션 금지 |
| `evidence_id` | 필수 | 보호 장부 내 유일한 불변 ID. 임의 사용자 URL·경로를 식별자로 취급하지 않음 |
| `profile` | 필수 | `MVP-A`로 고정. `RSS-OPS` 관측 증거와 혼합 금지 |
| `trend_ref` | 필수 | 정확히 A1 `trend_ref`와 일치. 다른 Trend 참조 재사용 금지 |
| `content_ref` | 필수 | 독립 A1 v0.2 승인 Record의 해시와 정확히 일치, Writer에서 원본으로 재계산 |
| `review_evidence_id` | 필수 | 기존 G4 개별 검토 기록 ID와 연결. ID 존재만으로 승인·권한 진위는 입증 안 됨 |
| `source_url` | 필수 | A1 승인된 `content.source_url` 원문 문자열과 **정확히 일치**. 무단 canonical 치환 금지 |
| `resolved_url` | 조건부 | 실열람 후 도달 URL을 확인했을 때 기록; 변경·리디렉션은 별도 정합성 검토. 단순 호스트 일치로 허용 금지 |
| `event_kind` | 필수 | `MANUAL_SOURCE_COLLECTION` 또는 `SOURCE_LINK_RECHECK`; 이벤트 종류를 기재하지 않은 시각은 매핑 금지 |
| `observation_method` | 필수 | 현재 MVP-A는 수동 브라우저 열람 등 **실제 수행한 방법** 기재. 실행하지 않은 자동 검증 주장 금지 |
| `observed_at` | 필수 | 이벤트 실제 시각 및 타임존. 과거 날짜/승인 시간 임의 합성 불가 |
| `recorded_at` | 필수 | 보호 장부 기록 시각 및 타임존. 원본 등록 시각 검증 필요 |
| `observer_ref` | 필수 | 수행자의 내부 역할/담당자 식별 참조. 공개 문서에 개인 식별 정보를 쓸 필요 없음 |
| `observation_result` | 필수 | `CONFIRMED` / `FAILED` / `UNDETERMINED` 제안. `CONFIRMED` 외 게시 입력 불가 |
| `artifact_reference` | 필수 | **실제 존재하는 보호된 원본 증거 자료**의 내부 참조. Google URL 자체만 적는 것은 관측 행위의 증거가 아님 |
| `artifact_sha256` | 필수 | 실제 원본 바이트의 SHA-256 변경 감지값. 진위/시각/권리 증명과 구분 |
| `reviewer_ref` | 필수 | 관측 증거의 유효성·콘텐츠/원문 링크 일치성을 확인한 담당자 참조. 역할·권한 검증 전 HOLD |
| `reviewed_at` | 필수 | 검토 사건의 실제 시각(타임존 포함) |
| `review_result` | 필수 | `ACCEPTED` / `HOLD` / `REJECTED` 제안. `ACCEPTED`도 실제 G6 승인이 아님 |

**검토용 기록 예시:** 아래는 필드 형식을 설명하는 **합성 입력 예시**이며 실제 관측·허가 증거가 **아니다**. 임의 시각·해시를 유효한 운영값으로 간주할 수 없다.

```json
{
  "schema_version": 1,
  "evidence_id": "SIM-OBS-001",
  "profile": "MVP-A",
  "trend_ref": "SIM-TREND-001",
  "content_ref": "sha256:<합성_승인_스냅샷_해시>",
  "review_evidence_id": "SIM-G4-001",
  "source_url": "https://example.test/source/1",
  "resolved_url": null,
  "event_kind": "MANUAL_SOURCE_COLLECTION",
  "observation_method": "MANUAL_BROWSER_CHECK",
  "observed_at": "<실제_관측_시각_및_타임존>",
  "recorded_at": "<보호_장부_기록_시각_및_타임존>",
  "observer_ref": "SIM-OBSERVER-ROLE",
  "observation_result": "CONFIRMED",
  "artifact_reference": "SIM-PROTECTED-ARTIFACT-ID",
  "artifact_sha256": "<실제_증거_원본_SHA256>",
  "reviewer_ref": "SIM-REVIEWER-ROLE",
  "reviewed_at": "<실제_검토_시각_및_타임존>",
  "review_result": "HOLD"
}
```

예시의 `SIM-` 값, `<...>` 플레이스홀더, 검증 전 `CONFIRMED`는 실제 Writer 입력으로 사용할 수 없다. **실제 관측 증거를 이미 확보했다는 주장이 아님**을 보존한다.

## 5. 실제 관측 증거물: 무엇을 보관할 것인가?

### 대안 A — 수동 확인 + 보호된 최소 관측 기록 (**MVP-A 우선 권고**) 

- 담당자가 브라우저에서 승인된 Source URL을 직접 열고, 어떤 원문 사실을 확인했는지 **자체 작성한 짧은 체크 기록**과 시간 근거를 남긴다.
- 관측·기록 시각을 구분하며, 기록 시각은 통제된 기록 절차에서 실제로 생성·보존한다. 나중에 편집한 문서의 파일 수정 시각만으로 당시 열람 시각을 입증하지 않는다.
- 보호 저장소에 원본 최소 증거를 보관하고, 별도 인덱스에 ID·SHA-256·검토 결과를 고정한다. 공개 GitHub에는 비밀/개인정보/비공개 증거 원본을 올리지 않는다.
- G4 담당자가 해당 증거의 출처·A1 원문 URL·승인 내용 동일성을 검토하고 확인한다. **독립 파일이라는 뜻이지, 사람이 실시간 현장을 제3자로 검증했다는 뜻은 아니다.**
- 장점: 새 외부 API나 관리자 UI가 필요 없다. 단점: 수동 입력의 신뢰성·실수 및 기록 경합 통제는 별도 검증 필요.

### 대안 B — 별도 관측 기록 도구와 자동 타임스탬프

- 수동 브라우저 확인 직후 도구가 시각·관측 URL·검토 이벤트를 기록하고 원본을 보호 저장소에 저장한다. 원문을 자동 크롤링하지 않는다.
- 장점: 시각 입력 오류 감소·재현성 향상. 단점: 기록 도구·파일 무결성·권한·시계 동기화·실패 안전성을 추가로 검증해야 한다.

**권고:** 11월 MVP-A에서는 **대안 A**를 계약 초안으로 선택하되, 실제 시각을 뒷받침할 수 있는 관측 도구나 보호된 시점 기록이 없으면 `observed_at`을 창작하지 않고 HOLD한다. 수동 서명이 독립적인 타임스탬프 인증을 제공한다고 주장하지 않는다. 보호 장부/검토 책임자의 실물 확인 전 A안을 운영 승인하지 않는다.

**증거물 최소화:** 원문 기사 본문·이미지·전체 페이지 스크린샷·로그인 쿠키·개인정보를 불필요하게 복제하지 않는다. 안전한 최소 관측 메모(정확한 URL, 확인한 자체 작성 사실 요약, 확인 결과, 시각 및 작성자 참조)와 생성 당시의 기록 근거만 보존하는 방향이다. 사용 권리 확인과 증거 신뢰성은 별도 검토한다.

## 6. 보호 저장소·참조 불변성·검토 책임 경계

1. `observation_evidence_ref`는 **서버가 보호 장부에서 해석하는 논리 참조**다. 외부 호출자가 임의 파일 경로·원문 URL·네트워크 위치를 지정해 Writer가 읽도록 하지 않는다.
2. 관측 원본은 불변으로 보존하고, 정정이 필요하면 **새 evidence ID와 명시적 대체/철회 관계**를 남긴다. 예전 원본·기존 A1 `content_ref`는 덮어쓰지 않는다.
3. 보호된 별도 인덱스는 `evidence_id → artifact_reference + digest + 연결된 trend_ref/content_ref + 검토 상태`를 기록한다. **해시만으로 원본의 진위나 참조 교체 차단을 주장하지 않는다.**
4. Writer에게는 관련 원본·인덱스 **읽기 전용** 권한만 부여하는 방향. 생성·수정·철회 권한은 담당자 승인 절차에 분리하며, FR-B04의 승인 변경 조정 보호 구간과 충돌 없는지 검증한다.
5. 서로 다른 권한 주체가 보호 장부와 인덱스를 동시에 임의로 교체할 수 있으면 참조 불변성이 입증되지 않는다. 파일 접근 통제·별도 검토 기록·교체 탐지 방식을 실증하기 전 **G5/G6 HOLD**다.
6. **실제 증거 저장 위치(기존 디렉터리/보호 볼륨), 보관 기간, 책임자/검토자 지정은 현재 GitHub 문서로 확정되지 않았다.** 임의 경로를 실재한다고 만들지 않는다. 실제 인프라 보호 경계는 FR-B03/04/05와 함께 재검증해야 한다.

## 7. P4 연결·시각 매핑 제안

### 7.1 P4 Envelope 관계

```text
B-Lite API: batch_id 만 수신
     |
     v
보호된 P4 Envelope ──a1_batch_ref──> 불변 A1 v0.2 Batch/승인 스냅샷
     |
     └──items[i].observation_evidence_ref──> 보호된 관측 Evidence/원본
                                              |
                          evidence_id + trend_ref + content_ref + source_url 대조
                                              |
                                    관측/검토 신뢰성 확인
                                              |
                   독립 G4 유효성·철회 + G6 + Journal + DB 중복 최종 검사
                                              |
                                       조건 미충족 시 HOLD
```

- 참조 ID, 승인 내용 해시, 실제 증거 Digest, URL 일치, 검토자의 승인 권한은 **각각 별도로** 확인한다.
- URL 리디렉션 또는 정규화가 발견돼도 `source_url`을 몰래 변경하거나 원래 콘텐츠 해시를 새로 계산하지 않는다. URL 대상 동일성을 G4가 확인하지 못하면 HOLD한다.
- `SOURCE_LINK_RECHECK`만 있는 경우 수집 시각 증거로 승격하지 않는다.

### 7.2 SQLAlchemy 시간 필드

| 기존 DB 필드 | 제안 초기 매핑 (단일 Source 1건, 검증된 한 번의 수동 수집 사건만) |
|---|---|
| `Trend.first_collected_at` | 최초로 입증된 `MANUAL_SOURCE_COLLECTION.observed_at`을 UTC 변환해 naive `DATETIME`으로 저장하는 후보 |
| `Trend.last_collected_at` | 이번 최초 수집 사건과 동일한 경우에만 같은 UTC 시각 후보. 이후 재관측 시 정책 별도 확인 |
| `TrendSource.collected_at` | 실제 그 Source가 수동 확보된 동일 사건 시각 후보 |

**필수 전제:** 위 3개 값이 같은 관측 사건을 가리키는지 검증되어야 한다. 단순 출처 **접속 재확인**, G4 승인일, Batch 실행일, DB 서버 `CURRENT_TIMESTAMP` 또는 기사 원문 날짜를 수집 시각 대신 쓰지 않는다. 현재 ORM의 기본값이 있더라도 P4가 명시적으로 정확한 시각을 제공할 계약을 별도 검증한다.

## 8. Fail-Closed 테스트 초안 (아직 미실행)

| ID | 반례/경계 | 기대 결과 |
|---|---|---|
| `OB-01` | `observation_evidence_ref` 없음/미등록/다른 ID | Batch 전체 HOLD / DB 0건 |
| `OB-02` | 증거 `trend_ref` 또는 `content_ref`가 A1 승인 Record와 다름 | Batch 전체 HOLD |
| `OB-03` | `source_url` 불일치 또는 미승인 redirect·단순 호스트 일치 | Batch 전체 HOLD |
| `OB-04` | `observed_at` 없음·날짜만 있음·타임존 없음·승인 시각만 존재 | Batch 전체 HOLD, 임의 시간 생성 금지 |
| `OB-05` | `SOURCE_LINK_RECHECK`만으로 최초 수집 시각 생성 시도 | Batch 전체 HOLD |
| `OB-06` | 원본 증거 자료 없음·SHA-256 불일치·서버 인덱스 참조 변조 | Batch 전체 HOLD |
| `OB-07` | `observation_result != CONFIRMED`, `review_result != ACCEPTED` | Batch 전체 HOLD |
| `OB-08` | 확인 주체·검토 주체/권한 미확인, 증거 공개·접근 권한 부적합 | Batch 전체 HOLD |
| `OB-09` | 한 Batch 2개 항목 중 1개 관측 증거 부적격 | 확정 Batch 전체 HOLD 또는 Transaction 전체 Rollback (P4-DEC-04) |
| `OB-10` | 관측 시각이 승인/게시/외부 발표 날짜로 임의 대체됨 | Batch 전체 HOLD |
| `OB-11` | 관측 후 링크/사실 변경, G4 재검토 없음 | Batch 전체 HOLD |
| `OB-12` | 격리 Fixture로 승인 스냅샷·증거 정합/UTC 변환/단일 Source 검증 | 정합성 PASS는 **기술 시험 범위**에만 적용. G6/실게시 승인 아님 |

현재 테스트 결과를 `PASS`라고 적지 않는다. 실제 P4 Writer가 미구현이므로 위 기대 결과는 **수용 기준 후보**다.

## 9. Python 3.15 사례 인수인계 — 기존 사실 vs 남은 실물

| 항목 | 이미 문서에서 확인한 값 | 다음 조치 |
|---|---|---|
| `trend_ref` | `PYTHON-315-MVP-A-001` | 유지 |
| G4 `review_evidence_id` | `E-G4-01-PY315` | 독립 승인 장부 원본과 대조 |
| A1 `content_ref` | `sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f` | 변경하지 않음; 검사기 원본 필요 시 재검증 |
| `source_url` | `https://www.python.org/downloads/release/python-3150/` | 실제 담당자의 별도 URL 관측·재확인 절차로 확인 |
| `source_title_origin` | `EDITORIAL_LABEL` | 기존 `E-G4-05-PY315` 유지 |
| G4 재확인 기록 | `E-G4-06-PY315`, 기록 시각 `2026-11-04T22:07:37+09:00` | 관측 시각으로 복사 금지 |
| **실제 관측 증거** | 2026-11-04 수동 열람 **날짜 수준의 사용자 보고** | 정밀 시각/원본 확보 여부 확인; 없으면 새 사건을 실제로 기록 |
| 보호 증거 저장소/담당 | 미확인 | 실제 팀의 보호 보관 장소·생성·검토 책임을 정해 문서화 |
| P4 Envelope | `observation_evidence_ref` 등 v1 구조 **제안** | 실제 관측 실물 확인 뒤 최종 필드 확정 |
| 게시 Gate | G5/G6 HOLD | 아무것도 승격하지 않음 |

## 10. 설계 동결 전 사용자/팀에서 확정해야 할 최소 결정

1. **증거 생성/검토 책임:** 관측 수행자와 G4 검토/승인 책임자가 누구이며, 동일인 가능 여부 및 책임 기록 방식을 어떻게 정할 것인가? (기존 G4 일반 콘텐츠 담당자 승인 정책을 새로 강화하려면 명시적 결정 필요)
2. **증거 실물/보관 위치:** 2026-11-04 원본 시각이 포함된 관측 증거가 존재하는가? 없다면 새 수동 관측 사건을 **실제로** 기록할 수 있는가? 보호된 증거 보관소와 기록 방식은 무엇인가?
3. **증거 신뢰 수준:** 사람의 수동 기록과 보호 장부로 MVP-A에 필요한 최소 관측 사실을 인정할 것인가, 별도 기록 도구의 자동 생성 시각까지 요구할 것인가?
4. **DB 수집 시각 의미:** '수동으로 근거 자료를 서비스 콘텐츠로 확보한 시각'을 최초·최종 수집 시각으로 취급할 조건을 실제 사례로 입증할 수 있는가?

이 질문에 필요한 **실제 기록·책임·보관**이 확인되면 FR-B02b 최종 검토를 진행한다. 그전에는 구조적 계약 초안만 완성, FR-B02b 자체는 **OPEN / NOT FROZEN**으로 유지한다.

## 11. 이번 작업 검증 범위

- GitHub 최신 `dev` P4 보완안 v0.2, G4 v0.7 N절, A1 연결 체크포인트 v0.2 §8, 운영 Gate v0.3, 기존 ORM 및 evidence README **읽기 전용 확인**.
- 기존 A1 콘텐츠/해시/승인·재확인 기록은 수정하지 않았으며, 운영 네트워크 호출, RSS/AI API 호출, 운영 DB/게시, GitHub/Notion 쓰기를 수행하지 않는다.
- 이 초안은 사실확인 및 설계 Review를 위한 문서다. **JSON 필드·권한·시간·저장소 구현을 확정하는 문서가 아니다.**

### 기준 자료 (GitHub `dev`)

- [P4 Final Review Addendum v0.2](https://github.com/Trend-Leader-capstoneProject/feature/tree/dev/docs/designs-feature/%EC%99%B8%EB%B6%80_%ED%8A%B8%EB%A0%8C%EB%93%9C_%EB%8D%B0%EC%9D%B4%ED%84%B0_%EC%88%98%EC%A7%91_%EB%B0%8F_%EC%97%B0%EB%8F%99)
- [Python 3.15 G4 v0.7](https://github.com/Trend-Leader-capstoneProject/feature/tree/dev/docs/operations/trend-publication/g4-content-review)
- [운영 Gate v0.3](https://github.com/Trend-Leader-capstoneProject/feature/tree/dev/docs/operations/trend-publication/policy)
- [증거 보존 가이드](https://github.com/Trend-Leader-capstoneProject/feature/blob/dev/docs/operations/trend-publication/evidence/README.md)
