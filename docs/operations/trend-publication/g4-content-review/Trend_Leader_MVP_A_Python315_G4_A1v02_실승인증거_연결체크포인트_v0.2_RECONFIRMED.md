# Trend Leader MVP-A — Python 3.15 G4 실승인 증거 ↔ A1 v0.2 장부 연결 v0.2 재확인 추가

> **기록 기준:** 2026-11-04 (KST), 원격 게시 없이 로컬 기록만 작성  
> **기준 정책:** `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`  
> **입력 G4 카드:** `Trend_Leader_MVP_A_G4_실전검토카드_Python_3_15_20261104_v0.6_APPROVAL_RECORDED_A1_HOLD.md` (M절 최신 승인 기록)  
> **대조 계약:** `Trend_Leader_MVP_A_G5_A1_출처안내_예외계약_v0.2_DESIGN_REVIEW.md`, `A1_RECONCILE_V02`  
> **주의: 이 문서의 §1~§7은 재확인 전 시점의 이력이다. 최신 판정은 아래 §8을 기준으로 한다.**
> **과거 상태:** 사람의 **G4 승인 결정 확인** / A1 자료 연결 **부분 완료** / `approved_at` 확인 전이므로 **A1 검사 결과 EXCLUDE** / **G5·G6 HOLD, 게시 NOT_ATTEMPTED**

## 1. 확인된 승인 사실과 증거 등급

- 2026-11-04 대화에서 담당자가 네 조건(콘텐츠 확정, 자체 설명+공식 링크만 사용, `기타 / Python.org 공식 출시 안내` 수용, `GENERAL_ELIGIBLE` 위험 분류)을 제시받고 **“승인합니다!!”**라고 명시적으로 승인했다. 이 결정은 **개별 G4**에 한하며 G6/Batch 실행을 허가하지 않는다.
- 이 대화의 승인 메시지 **정확한 발생 시각을 확보하지 못했다.** 카드 v0.6의 `2026-11-04T20:02:56+09:00`은 **승인 문서 작성 시 조회한 시각**일 뿐 `approved_at`로 사용할 수 없다.
- `approved_by`는 현재 확보 가능한 수준에서 **역할 기반**으로 기록했다. 실명 서명·책임자 권한 위임 원본의 별도 확인은 이루어지지 않았다.
- 이용 조건·권리 평가는 담당자가 **별도 작성 제목·설명과 공식 링크만 사용**하는 제한된 범위를 검토·수용한 기록이다. Python Software Foundation의 개별 허가서나 법적 면책 보증은 아니다.
- 실제 등록한 DB/운영 브랜치/배포 설정은 변경되지 않았다. 앱 화면은 개발용 MOCK 미리보기로 확인했으며 실제 데이터 게시 증거는 아니다.

## 2. A1 장부 필드별 근거 대조

| A1 필드 | 이번 기록 | 근거 및 남은 한계 |
|---|---|---|
| `trend_ref` | `PYTHON-315-MVP-A-001` | G4 카드 M-1·M-2 |
| `review_evidence_id` | `E-G4-01-PY315` | G4 카드 M-1의 개별 승인 의사 기록 |
| `rights_evidence_id` | `E-G4-04-PY315` | G4 카드 C·I·M절, 제한된 링크·자체 설명의 권리 검토 |
| `source_title_origin` | `EDITORIAL_LABEL` | 팀이 채택·검수한 **AI 제안** 출처 안내 문자열. 공식 원문 페이지 제목의 자동 복제가 아님 |
| `source_label_evidence_id` | `E-G4-05-PY315` | 아래 §3에서 이번에 별도 기록한 출처 표시 검토 사실의 **내부 증거 ID** |
| `approved_by` | 기능·콘텐츠 담당자(채팅 승인자) | 담당자의 대화상 승인 확인; 실명·권한 위임 별도 미확인 |
| `approved_at` | **`null` (미확인)** | 승인 메시지의 정확한 offset-aware 시각을 창작하지 않음 |
| `g4_result` / `approval_status` | `PASS` / `APPROVED` | 사람의 실제 의사결정. A1 기계 검증 적격성은 별도 |
| `risk_class` | `GENERAL_ELIGIBLE` | 위험 분류 승인, 고위험 정황 미발견 |
| `rights_checked` / `link_checked` / `no_reproduction_checked` | `true` | 각각 담당자 검토·링크 접속 보고·무복제 범위 승인이라는 **자기 검토 기록**, 외부 기관 인증이 아님 |
| `google_rss_derived` / `revoked` | `false` / `false` | 이번 후보 자료 경로에 Google RSS 유입 없음; 철회 보고 없음. MVP 전체 G1~G3 N/A 증거는 별도 필요 |
| `content_ref` | **`null` (A1 최종 고정 보류)** | 승인 당시 스냅샷을 v0.2 규칙으로 해싱할 수 있으나 승인 시간 누락 시 이 값을 적격 승인 지문으로 고정하지 않음 |

## 3. 추가 출처 안내 문구 증거 — `E-G4-05-PY315` (새 내부 기록)

- **대상 필드:** `source_title = "Python.org 공식 출시 안내"`.
- **작성·검토 과정:** AI가 사실 근거에 따라 한국어 출처 안내를 제안했고, 담당자가 실제 휴대폰 MOCK 화면에서 이 문구의 표시를 확인했으며 **해당 문구와 `ETC→기타` UX를 수용하는 네 가지 조건에 동의해 G4를 승인**했다.
- **유래 선언:** `EDITORIAL_LABEL` — 편집·승인된 설명용 레이블이며, 공식 릴리스 페이지의 원문 제목을 자동 수집·복제한 데이터가 아니다.
- **표시 내용 범위:** 이 문구와 `https://www.python.org/downloads/release/python-3150/`만 출처 구간에 사용. 외부 이미지/로고/OG 미리보기, 기사 본문 복제 없음.
- **연결 증거:** G4 카드 v0.6 M-1·M-2, 사용자가 공유한 2026-11-04 수정된 실제 기기 MOCK 스크린샷 및 원문 이동 성공 보고. **원본 이미지 파일·확인 로그의 저장소 경로 및 검토 당시 정확한 시각은 별도 인덱싱 전**이다.
- **증거 판정:** 승인 당시 레이블에 대한 **대화 및 검토 카드 기반 내부 증거 연결 완료**. 실제 언론사/PSF가 승인했다는 증거로 사용 불가. `E-G4-05-PY315`는 이번 문서에서 새로 부여한 ID이며 그 이전에 존재했던 독립 기관 증거가 아니다.

## 4. 내용 동일성 검증

G4 카드 v0.6 M-2의 승인 콘텐츠 7개 표시 필드와 `python315_batch_candidate_REVIEW_ONLY_v02.json`의 7개 필드가 **완전 일치**함을 JSON 객체 수준에서 검사했다.

- G4 승인 스냅샷 지문(기존 유지): `sha256:a5d83b3c1a6a38b1f56c19f87f4017fba41d4bb9f104eba9898b76ece1ca7688`.
- v0.2 A1 **예비 계산값** (검증용, 아직 장부 `content_ref`로 고정하지 않음): `sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f`.
- 두 지문은 계약 및 정규화 규칙이 다르므로 동일 값이어야 할 이유가 없다.
- `category_refs=["IT_DIGITAL/소프트웨어·앱"]`은 안정적 논리 참조이며, `category_id=42`는 사용자 환경의 활성 API 조회 당시 값이다. 다른 환경에 그대로 사용할 수 있는 DB PK라고 보장하지 않는다.

## 5. 오프라인 대조 실측 결과

```text
[BATCH] REVIEW-ONLY-PY315-NOT-FOR-PUBLISH / G6=HOLD
[ITEM] PYTHON-315-MVP-A-001: EXCLUDE / APPROVAL_EVIDENCE_INCOMPLETE
[RESULT] 잠재 적격 0건, 실제 게시 허가 0건
```

`APPROVAL_EVIDENCE_INCOMPLETE`는 **실제 승인 의사가 없다는 뜻이 아니다.** 대조 규칙상 offset-aware `approved_at`이 없음을 의미한다. 검사기는 승인 메시지의 존재나 시각을 스스로 인증하지 않는다.

**계약 반례 검증 (별도 임시 합성 객체만 이용):** 실제 장부를 변경하지 않고, 실재하지 않는 2030년 시각을 테스트 데이터에만 넣고 예비 해시를 일치시켰을 때 `ELIGIBLE_FOR_REVIEW_ONLY`가 나왔으며, 출처 문구 변경 시 `CONTENT_CHANGED_REVIEW_REQUIRED`가 확인됐다. 이 임시 시각을 **실제 승인 기록에 저장하지 않았다**. `ELIGIBLE_FOR_REVIEW_ONLY`조차 게시 허가는 아니다.

## 6. 보류 해소 및 다음 실행 조건

1. **승인 메시지 정확한 시각 확인 또는 담당자의 신규 확인 기록:** 원래 메시지의 신뢰 가능한 날짜·시간·시간대를 확보할 수 있으면 `approved_at`에 기록한다. 확보할 수 없다면 담당자가 **현재 시각을 확인하면서 콘텐츠·출처 안내를 재확인하는 명시적 재확인 기록**을 남겨 그 사건 시각을 사용한다. 원래 승인과 재확인 시각은 별도 표기한다.
2. 위 증거를 카드의 후속 승인 근거 절에 연결하고, `approved_at` 및 `content_ref`를 채운 뒤 **v0.2 재대조를 실행**한다. 예비 지문만 복사해서 `APPROVED` 적격을 주장하지 않는다. 값 변경 시 새 해시·재검토가 필요하다.
3. 이후에도 **G5 실제 게시 차단·부분 실패·철회 통제**, **G1~G3 Google RSS 비이용 증빙**, **G6 운영 프로필 승인**은 HOLD로 유지한다. 실제 DB INSERT / 공개는 별도 근거와 승인 전 수행하지 않는다.
4. 원격 GitHub·Notion·DB 쓰기는 이번 작업에 포함하지 않는다.

## 7. 실행 방법 (Windows PowerShell)

동봉된 검사기를 같은 폴더에서 실행한다. 별도 FastAPI·DB·네트워크가 필요하지 않다.

```powershell
python .	rend_leader_g5_a1_approval_reconcile_v02.py --check `
  --approvals .\python315_approval_manifest_REAL_EVIDENCE_TIME_PENDING_v02.json `
  --batch .\python315_batch_candidate_REVIEW_ONLY_v02.json `
  --report .\python315_reconcile_result_TIME_PENDING_v02.json
```

예상 `APPROVAL_EVIDENCE_INCOMPLETE / 게시 허가 0`. `--report` 옵션은 로컬 결과 파일만 쓰며 기존 manifest 또는 서비스 데이터는 수정하지 않는다.

> **최종 판정:** 실제 G4 승인 결정 `PASS/APPROVED` 문서 연결 + 출처 안내 증거 참조 확보. **A1 검사 결과 `EXCLUDE / APPROVAL_EVIDENCE_INCOMPLETE`**, Batch 편입 `NO`, G5·G6 `HOLD`, 실제 게시 `NOT_ATTEMPTED`.


---

## 8. 기존 승인 변경 없는 재확인 및 A1 v0.2 재대조 (최신: 2026-11-04)

- **새 내부 재확인 증거:** `E-G4-06-PY315` — 담당자의 “변경 없이 현재 시점에도 승인한다고 재확인합니다.”라는 이 대화의 명시적 의사.
- **기존 최초 승인 메시지 정확 시각:** 미확인; 그대로 미기재.
- **재확인 기록 `approved_at`:** `2026-11-04T22:07:37+09:00` (응답 후 시계 도구로 조회한 **기록 시각**, 송신의 정확한 원본 타임스탬프가 아님).
- **원본과 내용 비교:** G4 카드 v0.6 M-2의 7개 표시 필드와 Batch 후보 JSON이 변경 없이 일치.
- **A1 v0.2 `content_ref`:** `sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f`. G4 v0.6의 별도 스냅샷 지문과 혼동 금지.
- **검증 명령:** 동봉 `trend_leader_g5_a1_approval_reconcile_v02.py --check`를 사용해 새 장부와 Batch 후보를 대조.

```text
[BATCH] REVIEW-ONLY-PY315-NOT-FOR-PUBLISH / G6=HOLD
[ITEM] PYTHON-315-MVP-A-001: ELIGIBLE / ELIGIBLE_FOR_REVIEW_ONLY
[RESULT] 적격 후보 1건, 게시 허가 0건 (G6 HOLD)
[LIMIT] 증거 ID·승인자·체크값의 진위는 검증하지 않았습니다. DB/HTTP 연결 없음.
[INFO] 파일 저장: /mnt/data/python315_a1_v02_reconfirmation_complete/python315_reconcile_result_RECONFIRMED_v02.json
```

- **실제 검사기 판정:** `ELIGIBLE_FOR_REVIEW_ONLY` / 1개 잠재 적격 / 실제 게시 권한 0.
- **안전 반례:** 출처 레이블 변경 시 `CONTENT_CHANGED_REVIEW_REQUIRED`; `revoked=true` 시 `APPROVAL_REVOKED`; 가짜 G6 PASS 입력은 문서 단계 안전 중단.
- **기계 검사의 한계:** 데이터의 구조·값의 일치에만 근거. 승인자의 권한 및 실제 원문·법적 사용 허가, 독립 감사 가능한 채팅 이벤트 타임스탬프를 증명하지 않음.
- **남은 HOLD:** G5 실제 운영 통제, G0 / G1~G3 N/A 전체 확인, G6 프로필 별도 승인. DB/HTTP/게시/원격 커밋 `NOT_ATTEMPTED`.