# Trend Leader MVP-A — G4~G6 운영 절차 실행 검증 보고서 v0.1

> 작성 및 점검 기준: 2026-11-03 (KST)
>
> 문서 상태: **오프라인 정책 리허설 12/12 PASS / 실제 콘텐츠 승인·앱 운영 Gate HOLD**
>
> 근거: `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`, `Trend_Leader_MVP_A_G4_개별_Trend_검토카드_템플릿_v0.1.md`, `Trend_Leader_MVP_A_G5_G6_Batch_승인_게시_기록표_템플릿_v0.1.md`.
>
> 변경 금지 준수: GitHub/Notion/프로젝트 소스/DB 미수정. Google Trends RSS 실데이터 요청 및 실제 게시 없음. 이 작업에서 생성한 파일은 로컬 `/mnt/data` 보고서·합성 검사기·JSON 결과·테스트 출력에 한정.

## 0. 검증의 층위

| 층위 | 이번에 수행한 일 | 결과 | PASS 대상인가? |
|---|---|---|---|
| 정책 도상 리허설 | 합성 입력 7건으로 G4 판정·Batch 선별·G6 HOLD 차단 규칙을 별도 검사기로 실행 | 12개 단위 검증 통과 | **로컬 모의 정책 규칙만 PASS** |
| 실제 코드 읽기 전용 점검 | GitHub `feature`, `dev` 브랜치에서 관련 Router/Repository/ORM/Response/Frontend/Seed 읽기 | 공개 경계와 필드 노출 경로 확인 | **코드의 실제 통제 여부 PASS 아님** |
| 실출처 예비 점검 | Python·Node.js 공식 릴리스 페이지 검색, 원문 접근 재시도 | 공식 자료 검색 결과로 사실관계 일부 확인. 직접 페이지 열람 재시도는 실패 | **개별 G4 HOLD** |
| 팀원 공동 검토 | 참여 없이 역할만 계획 | 미실행 | HOLD |
| 실 DB/API/앱 검증 | 실행하지 않음 | 미실행 | HOLD |
| Google RSS 외부 자동 수집 | 수행하지 않음 | 신규 요청 0건(이번 리허설은 전부 합성 입력) | **G1~G3 N/A 검증 완료 아님** |

## 1. 실제로 실행한 정책 리허설 — `SIM` 네임스페이스

독립 검사기: `mvp_a_offline_gate_rehearsal_v01.py` (Trend Leader 소스 코드가 아님). 실행: `python /mnt/data/mvp_a_offline_gate_rehearsal_v01.py`.

실행 로그: `Trend_Leader_MVP_A_운영절차_오프라인_리허설_테스트출력_v0.1.txt`. 구조화된 결과: `Trend_Leader_MVP_A_운영절차_오프라인_리허설_결과_v0.1.json`.

- **실제 실행한 검사: 12개, 오류·실패: 0개.** 이 개수는 모의 정책 판단 로직의 검사 수이며 `pytest`, 운영 서버, GitHub CI, 실 DB 및 모바일 E2E 테스트 결과가 아니다.
- 모든 사례는 임의로 정한 `facts_verified`, `source_rights_verified`, `g4_approval` 등의 **테스트 전제값**을 사용한다. 실제 사실확인·권리허가·검토자 서명·승인 행위가 아니다.
- 합성 출처에는 실제 URL 대신 `fixture://SIM-...`를 사용한다. 네트워크 I/O나 외부 콘텐츠 복제 없음.
- `approved_digest`는 제목·자체 설명·링크·표시 필드·정책 버전의 SHA-256이며, **운영 시스템에 이미 이런 기능이 있다는 의미가 아님**.

| ID | 합성 상황 | 실행된 모의 G4 판단 | 모의 Batch 판정 | 실제 G4/게시 |
|---|---|---|---|---|
| SIM-001 | 일반 콘텐츠, 가정상 모든 검증·승인 완료 | SIM_ELIGIBLE | 후보 | HOLD / 미게시 |
| SIM-002 | 사실관계 증거 누락 | HOLD (INSUFFICIENT_EVIDENCE) | 제외 | HOLD / 미게시 |
| SIM-003 | 공동 검토해도 고위험 유지 | EXCLUDED (HIGH_RISK_MVP_EXCLUSION) | 제외 | HOLD / 미게시 |
| SIM-004 | 미승인 Google RSS 파생이라고 가정 | EXCLUDED (NO_PERMISSION) | 제외 | HOLD / 미게시 |
| SIM-005 | 승인 뒤 설명 수정 | HOLD (APPROVED_CONTENT_CHANGED) | 제외 | HOLD / 미게시 |
| SIM-006 | 일반 콘텐츠, 가정상 모든 검증·승인 완료 | SIM_ELIGIBLE | 후보 | HOLD / 미게시 |
| SIM-007 | 원문 제목·이미지 그대로 표시 | HOLD (UNREVIEWED_REPRODUCTION) | 제외 | HOLD / 미게시 |

**모의 이론상 적격 후보 2건**: SIM-001, SIM-006. **실제 승인된 콘텐츠 0건, 이번 작업의 실제 게시 0건**.

### 주요 시나리오 매핑

| 항목 | 이번 실행 내용 | 검증 범위 |
|---|---|---|
| AT-05 | 모의 원제목·이미지 노출 차단 분기 | 독립 검사기만 |
| AT-08 | 정책 버전 변경 시 기존 승인 무효화 | 독립 검사기만 |
| AT-10 | 일반 콘텐츠가 승인 증거 없으면 후보 제외 | 독립 검사기만 |
| AT-11 | 공동 검토에도 고위험 유지 시 MVP 제외 | 독립 검사기만 |
| AT-12 | 일반 주제라도 Google 권한 없음이면 제외 | 독립 검사기만 |
| AT-13 | G4 HOLD 항목은 Batch에서 제외 | 독립 검사기만 |
| AT-14 | 승인 후 내용 변경 시 재검증 HOLD | 독립 검사기만 |
| AT-15 | G6 HOLD면 실제 게시 호출 0으로 보고 | 독립 검사기만; 부분 DB 실패 처리 미검증 |
| AT-16 | 철회 플래그 이후 재편입 차단 | 독립 검사기만; 실제 공개중단 미검증 |

> 주의: 위 항목들의 **운영 환경에서의 Acceptance Test 상태는 여전히 미실행**이다. 같은 식별자를 사용한 `모의 분기`를 실제 앱 통합 AT 통과로 기록하지 않는다.

## 2. 현재 프로젝트 코드 정적 점검 (읽기 전용)

검토 기준: `Trend-Leader-capstoneProject/feature`, 브랜치 `dev`, GitHub Connector로 각 파일을 직접 읽음. 로컬 checkout, 실행, DB 접근 없음. 아래 SHA는 **개별 파일 blob SHA**이며 브랜치 HEAD 커밋 SHA로 해석하지 않는다.

| 확인 파일 | 검증한 동작 | G5 관점 영향 |
|---|---|---|
| `backend/app/models/db_enums.py` (`af90dff65c80…`) | `TrendStatus`는 `ACTIVE`, `HIDDEN` | 검증·승인 상태와는 다른 개념 |
| `backend/app/models/trend.py` (`8ea770c91997…`) | `status` 기본값이 `ACTIVE` | 신규 등록 데이터가 통제 없이 ACTIVE가 되는 위험을 검토해야 함 |
| `backend/app/repositories/trend_repository.py` (`3a45353682cb…`) | `find_page()`는 `Trend.status == ACTIVE`만 필터 | 개별 G4 승인·출처 권리 상태를 조회 단계에서 확인하지 않음 |
| `backend/app/api/routes/trend_router.py` (`3a69243642ba…`) | `GET /api/trends`, `GET /api/trends/personalized` 연결 | 두 경로 모두 같은 Repository `find_page()`에 의존 |
| `backend/app/services/trend_list_item_builder.py` | 최신 Source의 `source_title`, `source_url` 포함 | 원제목이 실데이터에서 입력되면 응답 필드로 전달될 수 있음 |
| `backend/app/schemas/trend_schema.py` (`1bfea63c9536…`) | `thumbnail_url`, `latest_source.source_title` 응답 정의 | 제외 정책과 표시 필드 대조가 필요 |
| `frontend/src/features/trend/components/TrendSourceSection.tsx` | `source_title != null`이면 텍스트로 표시 | 원기사 제목을 저장한 경우 그대로 노출 가능 |
| `frontend/src/features/trend/components/TrendCard.tsx` | `thumbnail_url != null`이면 이미지 렌더링 | 검토하지 않은 외부 이미지가 렌더링될 수 있음 |
| `backend/app/db/seeds/demo_trends.py` | `[DEMO]` 데이터, `platform=GOOGLE` 예시, `picsum.photos` 썸네일 예시 존재 | 합성 Google 라벨은 실 Google 제공·허가 콘텐츠로 오인되지 않도록 구분 필요; 샘플 이미지의 실제 이용조건은 별개 |

### 정적 점검 결론

- **확인된 사실**: 두 Trend 목록 조회 경로에서 확인된 공개 필터는 `ACTIVE`다. `source_title`, `thumbnail_url`이 API와 화면으로 전달되는 경로도 확인된다.
- **추론되는 위험**: 적법성 미검증 콘텐츠를 `ACTIVE`로 등록하면 일반 사용자에게 노출될 수 있다. 이는 등록 경로와 DB 실제 값을 검증하지 않았기 때문에 *발생했다고 단정할 수 없는 위험*이다.
- **현재까지 확인되지 않은 것**: 운영자가 의도적으로 수동으로 HIDDEN→ACTIVE를 제어하는 관리 절차, 승인 버전 대조, 게시 롤백·차단, Google 비이용 배포 설정, 실제 DB 데이터 품질, 실기기 렌더링 결과.
- **설계 영향**: v0.3 정책을 바꿀 필요는 없으나 **G5 구현/운영 절차 검증 없이 G6 승인 불가**. 실제 코드 변경이 필요할지는 별도 설계·구현 채팅에서 기존 조회 계약 및 스키마 영향 분석 후 결정.

## 3. 실출처 예비 카드 — 승인되지 않은 G4 후보

> 아래 자료는 Google Trends RSS에서 가져오지 않았다. 공식 프로젝트의 공개 페이지를 웹 검색하여 제목·날짜 등의 사실을 우선 대조했다. 직접 페이지 열람 도구 재시도가 캐시 오류로 실패해, **운영 양식에서 요구하는 실제 원문 열람/링크 QA 완료라고 기록할 수 없다**. 또한 출처 자체의 데이터 재사용·게시 조건, 사용자 작성 설명의 최종 확정, 팀원과의 검토를 수행하지 않았다. **실제 G4 PASS 아님.**

### CAND-001 — Python 3.15.2 릴리스

| 필드 | 증거 및 현재 상태 |
|---|---|
| 검토 카드 | `G4-20261103-CAND-001` (임시 후보, 미승인) |
| 자체 작성 제목 후보 | `Python 3.15.2 유지보수 버전 공개` |
| 자체 설명 초안 | `Python 공식 릴리스 페이지에 따르면 2026년 10월 25일 Python 3.15.2가 출시되었습니다.` |
| 카테고리 제안 | `IT/디지털` (실제 DB 매핑 값과 별도 검증) |
| 원 출처 | https://www.python.org/downloads/release/python-3152/ |
| 근거 | Python.org 공식 릴리스 검색 결과: 2026-10-25, 3.15.2 유지보수 릴리스 |
| 웹 점검 | 원문 검색 결과 확인; 도구를 통한 직접 열람 시도 실패, 모바일 링크 QA 미실행 |
| 권리 검토 | 아직 미완료. 원문 기사 제목·본문·이미지 미사용 제안 |
| Google RSS 파생 | 이번 카드 작성 경로에서 사용하지 않음 |
| 분류 / 승인 | `INSUFFICIENT_EVIDENCE` / G4 HOLD / G4 담당자 승인 PENDING |
| Batch | 편입 NO, 게시 NOT_ATTEMPTED |

### CAND-002 — Node.js 26.x LTS 전환

| 필드 | 증거 및 현재 상태 |
|---|---|
| 검토 카드 | `G4-20261103-CAND-002` (임시 후보, 미승인) |
| 자체 작성 제목 후보 | `Node.js 26 버전 LTS 전환` |
| 자체 설명 초안 | `Node.js 공식 릴리스 목록은 2026년 10월 28일 26.13.0을 LTS로 표시하며, 릴리스 게시물은 26.x의 장기 지원 단계 진입을 설명합니다.` |
| 카테고리 제안 | `IT/디지털` (실제 DB 매핑 값과 별도 검증) |
| 원 출처 | https://nodejs.org/en/blog/release/v26.13.0 |
| 근거 | Node.js 공식 릴리스/블로그 검색 결과: 2026-10-28, 26.13.0 LTS |
| 웹 점검 | 공식 검색 결과 확인; 개별 릴리스 원문 직접 열람 재시도 실패, 모바일 링크 QA 미실행 |
| 권리 검토 | 미완료. 기사 원제목·본문·이미지 미사용 제안 |
| Google RSS 파생 | 이번 카드 작성 경로에서 사용하지 않음 |
| 분류 / 승인 | `INSUFFICIENT_EVIDENCE` / G4 HOLD / G4 담당자 승인 PENDING |
| Batch | 편입 NO, 게시 NOT_ATTEMPTED |

## 4. G0~G6 작업 후 현재 상태

| Gate | MVP-A 실제 운영 판정 | 확인된 근거 / 남은 조건 |
|---|---|---|
| G0 | HOLD | 예비 출처와 필드 범위 작성. 실제 팀의 데이터 취득·보존 범위 최종 지정과 표본 검증 필요 |
| G1 | HOLD (N/A 증명 전) | 이번 독립 검사기는 Google RSS 호출하지 않음. **배포 앱/스케줄 설정 비이용 증명은 미실행** |
| G2 | HOLD (N/A 증명 전) | 실제 DB/로그/Seed에 Google RSS 파생 데이터 없는지 미검증 |
| G3 | HOLD (N/A 증명 전) | 현재 API/앱 데이터가 Google RSS 파생이 아닌지 실측 미검증 |
| G4 절차 | 양식·모의 분기 검토됨, 실제 PASS 전 | 실제 링크/권리/2인 공동 검토 기록 및 승인 필요 |
| G4 개별 콘텐츠 | HOLD | CAND-001, CAND-002 모두 미승인 |
| G5 | HOLD | 코드 정적 위험 분석. 실 DB/API 게시 차단·변경 방어·공개중단 미검증 |
| G6 | HOLD | 팀의 최종 승인자(사용자 예정)가 Gate 근거를 검증해 최종 서명해야 함 |

## 5. G5에서 확인해야 할 최소 개발/운영 선택지 (구현 변경 결정 아님)

| 대안 | 설명 | 장점 | 주의점 |
|---|---|---|---|
| **A. 엄격한 수동 Seed·상태 통제** | 검토된 콘텐츠만 비공개 준비 상태로 다루고, 승인된 Batch의 등록/노출을 담당자가 직접 제어 | MVP 일정에 상대적으로 유리; 별도 관리자 UI 불필요 | 현재 `ACTIVE` 기본값과 데모 Seed 동작을 통제해야 하며, 수동 절차 누락 시 위험. 현재 개발/데모 DB가 실제로 분리되어 있는지 확인 필요 |
| **B. 게시 승인 기능을 서비스에 구현** | 콘텐츠 검증 상태/승인 버전 등을 애플리케이션에서 강제하고 적격 데이터만 공개 | 향후 자동 수집·상업 운영 확장에 유리 | DB·API·테스트 영향. 새 구현은 기존 FROZEN 계약/조회 확정안과의 영향 검토가 선행되어야 함 |

> **현 단계 권고**: 11월 MVP는 A의 가능성을 먼저 읽기 전용으로 검증하고, 운영 실수 방지 능력이 부족하다면 G5 HOLD를 유지하며 B의 최소 변경 범위를 별도 설계. 운영 중 위험이 확인되면 기한을 이유로 근거 없는 PASS를 내리지 않는다.

## 6. 두 팀원이 실제로 실행해야 하는 검증 절차

1. CAND-001~002의 원문을 브라우저/실기기에서 직접 열고, 정확한 사실·링크·개별 이용 조건을 검증한다. 권리 근거/출처/확인 날짜를 G4 카드에 기록한다. 사실 오류나 권리 불명확이 있으면 HOLD.
2. 실사용 제목·설명·카테고리를 자체 작성하고, 원기사 제목·본문·이미지 자동 노출이 없는지 API/화면을 확인한다. `content_ref`를 기록한다.
3. 팀원 1명은 고위험 의심 항목과 근거 부족 항목을 논의하며, 기능 담당자는 검토 카드별로 승인 또는 보류를 기록한다.
4. G6 실제 운영 승인이 되기 전에는 Batch 기록표에 적격 후보를 표시할 수 있어도 **실제 게시 실행은 하지 않는다**.
5. G1~G3 N/A 정적/실행 점검 및 G5의 승인 후 변경·혼입·철회 방어를 테스트 환경에서 검증한 뒤, 운영 승인자가 Gate 증거를 확인한다.

## 7. 전체 결론 및 변경 제한

- **검증 완료:** 별도 합성 정책 검사기의 12가지 분기; 현재 Trend 조회 경로의 `ACTIVE` 필터 및 `source_title`·`thumbnail_url` 노출 코드 확인.
- **실제 미완료:** 실제 G4 PASS, 팀 합의·승인 서명, 배포 데이터·Google 비이용 증명, G5 통합 테스트, G6 운영 승인.
- **계약 영향:** 기존 P0~P3 FROZEN 계약 수정 제안 없음. 신규 게시 승인 상태를 DB/API에 넣어야 할지는 기존 Trend 조회 계약에 미칠 영향을 별도 설계에서 먼저 보고.
- **보존 사항:** v0.3 정책 자체 변경 없음. Google RSS 운영 HOLD. GitHub·Notion·DB·프로젝트 코드 변경 없음.