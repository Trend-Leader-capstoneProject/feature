# Trend Leader MVP-A — G5 A1 승인 증거 ↔ Batch 후보 대조 검증안 v0.1

> 작성·실행 검증일: 2026-11-04 (KST)  
> 상태: **독립 오프라인 검증 스크립트 자가 테스트 PASS / 실 G4 콘텐츠 승인 및 G5·G6 운영 Gate HOLD**  
> 근거: `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`와 기존 `Trend_Leader_MVP_A_G4_개별_Trend_검토카드_템플릿_v0.1.md`, `Trend_Leader_MVP_A_G5_G6_Batch_승인_게시_기록표_템플릿_v0.1.md`.  
> 범위: MVP-A/A1(승인 전 DB 밖에서 검토). 기존 G4·G5·G6의 정책 및 FROZEN 계약 변경 없음. 실제 게시/DB/외부 요청/GitHub/Notion 쓰기 없음.

## 1. 작업 이유 및 불변조건

기존 통합 시나리오에서는 **조건을 미리 넣은 합성 후보 중 적격 2건만 API에 노출**됨을 증명했다. 이번 단계에서는 서로 독립된 **승인 기록**과 **Batch 후보 파일**을 대조한다.

불변조건: `G4 PASS ∧ GENERAL_ELIGIBLE ∧ 개별 APPROVED ∧ 권리/링크/무복제 검토 기록 ∧ 승인된 content_ref와 현재 게시 필드 일치 ∧ 미철회`인 항목만 **잠재 적격 후보**로 분류한다. G6는 운영 프로필 별도 승인이고 **현재 HOLD**이므로 실제 게시 허가 항목은 항상 **0건**이다. 적격 후보라 해도 G6 HOLD 또는 등록 전 마지막 실검토가 남아 있으면 실제 INSERT/공개하지 않는다.

**중요**: 본 스크립트가 확인하는 것은 기록의 **구조와 값의 일치 여부**다. 파일의 `approved_by`, `approved_at`, `rights_evidence_id`, `rights_checked` 등의 **진위와 실제 원문 열람·권리 허가를 증명하지 않는다.** SHA-256은 변경 감지용이지 승인 서명이나 법적 권리 증거가 아니다. 실제 승인이나 운영 Gate를 자동 PASS 처리하지 않는다.

## 2. 설계 선택과 책임 분리

| 방식 | 구성 | 장점 | 제약 및 권고 |
|---|---|---|---|
| **A1(선택)** | G4 카드(사람) → 별도 승인 참조/스냅샷 → Batch 후보 파일 → 오프라인 대조 → 실제 운영 조건 확인 후 수동 등록 | 새 DB 테이블·관리자 API 없이 수동 단계에서 차단 가능 | 승인 기록 위조/누락, 실수로 검사 우회, 등록 후 변경은 자동 강제하지 못함 |
| B안(후순위) | 서버 쪽 승인 레코드·상태 및 인증된 등록 API | 승인·변경 감지 강제·감사 추적 유리 | 기존 스키마/API/권한/테스트 영향. 11월 MVP의 확정 범위를 별도 재검토해야 함 |

스크립트는 **B안 코드를 대신 구현하지 않는다**. A1의 오프라인 입력 도구이며, 서버가 모든 직접 SQL/다른 쓰기 경로를 차단한다는 증거가 아니다.

## 3. 내용 식별값 `content_ref`의 시범 규칙

- JSON 객체의 `trend_ref`, 정책 버전, `title`, `summary`, `category_refs`, `source_platform`, `source_url`, `source_title`, `thumbnail_url`을 정확히 직렬화한 후 SHA-256으로 변경 감지.
- **자체 작성 제목·설명만** 포함하고, 원 기사 본문/기사 제목/이미지는 승인 기록으로 복제하지 않는다.
- MVP-A 테스트 기본 제외: `source_title` 및 `thumbnail_url`은 `null`. Google RSS 파생 표시가 있으면 제외.
- 허용 필드 추가·삭제 시 **안전 중단 또는 해당 후보 제외**: 서비스의 공개 필드가 변경되면 이 도구의 스키마를 재검토해야 한다.
- 카테고리 참조 순서 변경도 해시가 달라지는 보수적 규칙. URL의 동일 페이지 리다이렉트·접속 가능성·이용 조건은 해시가 확인해 주지 않는다.
- `content_ref` 형식은 이번 **독립 도구의 시범 계약**이며 현행 DB `source_key`와 동일하거나 기존 확정안에 추가된 계약이라고 간주하지 않는다.
- 실제 G4 카드 작성 완료 시에만 승인 시점의 내용으로 이 참조값을 계산·고정해야 한다. **내용 변경 후 최신값으로 승인 기록을 자동 재계산하면 안 된다.**

## 4. 테스트 실행 — Windows PowerShell

다운로드 ZIP을 `Downloads` 폴더에 저장했다고 가정한다.

```powershell
$dir = Join-Path $env:USERPROFILE 'Downloads\trend_leader_g5_a1_reconcile_v01'
Expand-Archive -Path (Join-Path $env:USERPROFILE 'Downloads\trend_leader_g5_a1_reconcile_v01.zip') -DestinationPath $dir -Force

# 표준 라이브러리만 사용 (프로젝트 .venv 없이도 가능)
python (Join-Path $dir 'trend_leader_g5_a1_approval_reconcile_v01.py') --self-test
python (Join-Path $dir 'trend_leader_g5_a1_approval_reconcile_v01.py') --demo

# 승인 기록 파일과 Batch 후보 파일을 별개 입력으로 대조
python (Join-Path $dir 'trend_leader_g5_a1_approval_reconcile_v01.py') --check `
  --approvals (Join-Path $dir 'trend_leader_g5_a1_sample_approvals_SIM.json') `
  --batch (Join-Path $dir 'trend_leader_g5_a1_sample_batch_SIM.json')
```

선택: 결과 JSON을 **사용자가 지정한 위치에만** 저장하려면 명령 끝에 `--report (Join-Path $dir 'review_result.json')`을 붙인다. 결과 파일은 **모의 검증 산출물**이지 실제 심사·서명 기록이 아니다.

- **DB URL/비밀번호 불필요.** 스크립트에 SQLAlchemy, FastAPI, 네트워크 통신이 없다.
- 예제 파일은 `SIM-...`, `[SYNTHETIC]`, `example.com`만 사용한다. 실제 G4 승인자의 서명으로 사용 금지.
- 파일 오류가 발생하면 `[STOP]` 메시지와 종료 코드 2. 미승인 항목은 항목별 `EXCLUDE`이고, 구조 자체의 중복·버전 충돌은 전체 중단.
- 현재 G6 상태는 `HOLD`만 수락한다. 누군가 JSON을 `PASS`로 고치더라도 실제 게시 허가가 나오지 않도록 의도적으로 차단한다.

## 5. 이번에 실행한 합성 시나리오

| 후보 | 조건 | 오프라인 검사 예상/실제 |
|---|---|---|
| T-001, T-002 | 명목상 승인된 자체 콘텐츠, 승인 참조 일치 | `ELIGIBLE` 2건 (게시 허가 아님) |
| T-003 | 개별 G4 승인 기록 없음 | `G4_RECORD_MISSING` |
| T-004 | 승인 후 자체 설명 변경 | `CONTENT_CHANGED_REVIEW_REQUIRED` |
| T-005 | 고위험 판정 유지 | `HIGH_RISK_EXCLUDED` |
| T-006 | 권리 확인 체크 불완전 | `G4_CHECK_INCOMPLETE` |
| T-007 | Source 원제목 비-null | `INVALID_PUBLISH_PAYLOAD` |
| T-008 | Google RSS 파생임을 표시 | `UNAPPROVED_GOOGLE_RSS` |
| T-009 | G4 HOLD, 승인 PENDING | `G4_NOT_APPROVED` |
| T-010 | 승인 철회 | `APPROVAL_REVOKED` |

**실행 증거**: `python ... --self-test` → PASS. 또한 `--check`에 독립 JSON 입력을 연결하여 `ELIGIBLE 2 / EXCLUDE 8 / authorized_to_publish 0` 확인. 중복 승인, Batch 중복, 버전 불일치, 가짜 G6 PASS, 승인 기록의 미정의 필드 등의 구조 오류를 안전 중단하는 검증 포함.

## 6. 실제 G4 카드·G5 기록표에 연결하는 방법 (현재 미실행)

1. G4 카드에서 *실제* 자체 작성 제목·설명·카테고리·외부 링크 및 표시 계획을 검토한다. 권리·출처·위험 분류·검토자·승인 시각은 **실제 행위에 근거해** 기재한다.
2. 실제 카드별 승인 시점에 내용 스냅샷으로 `content_ref`를 발급하고, 승인 장부에는 참조값·증거 ID·담당 승인자를 남긴다. **G4 미승인 카드는 APPROVED로 만들지 않는다.**
3. A1 등록 후보를 별도 Batch 파일로 준비하고, 승인 파일을 수정하지 않은 상태에서 두 파일을 대조한다. `ELIGIBLE`이어도 **G6 HOLD면 게시하지 않는다.**
4. `E-G5-05`에는 Batch ID, 후보별 포함/제외 사유, 승인 증거 참조, 대조 일시, 실행자, 원본 파일 버전/식별값을 기록한다. `E-G5-06`에는 변경 감지와 예외 결과를 기록한다.
5. 실제 운영 전에는 G6 승인 증거/운영 범위, DB 접근 통제, 등록 경로, 부적격 기존 ACTIVE 데이터 점검 및 미승인 재등록 방지, 부분 실패 복구를 별도 확인한다. **시험 스크립트만으로는 운영 Gate PASS가 아니다.**

## 7. 완료 기준과 남은 위험

- [x] 승인 기록과 등록 후보를 별도 입력으로 읽는 오프라인 도구 작성
- [x] 해시 기반 승인 당시 필드 일치 검증(합성 데이터)
- [x] 누락·변경·고위험·권리/체크/원제목·RSS 파생·철회 배제 사례 검증
- [x] G6 HOLD의 실제 게시 허가 0건 고정(오프라인 도구 범위)
- [x] 중복/버전/위장 G6 PASS 안전 중단 반례 검증
- [ ] **실제** G4 카드 서명·사실/권리 검증 및 실데이터 승인
- [ ] 실제 Batch 자료 연결(실제 승인 기록을 만든 다음에만)
- [ ] 운영 등록 경로의 강제 차단(서비스/DB 쓰기 전체) 검증
- [ ] Google RSS 미사용 G1~G3 N/A 근거 및 최종 G6 운영 승인
- [ ] 앱 캐시/실기기 비노출, 부분 실패·정정 대응

**최종 판정:** 오프라인 승인증거↔Batch **구조·변경감지 리허설 PASS**. 실제 승인 진위 검증·운영 G5/G6 **HOLD 유지**.