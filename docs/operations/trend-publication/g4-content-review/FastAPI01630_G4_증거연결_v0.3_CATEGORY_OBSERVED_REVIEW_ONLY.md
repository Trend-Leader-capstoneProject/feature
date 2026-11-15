# Trend Leader MVP-A — FastAPI 0.163.0 G4 증거 연결 v0.3

> **상태:** REVIEW-ONLY / G4 담당자 승인 의사 확인 / A1 적격성 미검증 / G5·G6 HOLD / 카테고리 API 증거 추가  
> **기준일:** 2026-11-15 KST (승인 메시지의 정확한 시각 미확인)  
> **기준:** `Trend_Leader_MVP_A_G4_개별_Trend_검토카드_템플릿_v0.1.md`, `Trend_Leader_MVP_A_G5_A1_출처안내_예외계약_v0.2_DESIGN_REVIEW.md`, 운영 Gate v0.3  
> **이전 G4 검토 카드:** `G4-20261115-001` (임시 참조 ID; 실제 등록 번호 아님)  
> **범위:** 증거 간 논리 연결만 수행. 승인 원장 보호 등록, DB 저장, Batch 편입, 앱 게시, GitHub 원격 수정은 수행하지 않음.

## 1. 승인 대상으로 검토한 콘텐츠 스냅샷 (표시값 7개)

아래 표시값을 **변경 감지 대상 초안**으로 고정해 검토한다. 실제 A1 승인 스냅샷과 `content_ref`로 확정된 상태는 아니다.

```json
{
  "title": "FastAPI 0.163.0 공개, 의존성 동시성 제한 기능 추가",
  "summary": "FastAPI 0.163.0이 공개됐다. 이번 버전에서는 `Depends(max_concurrency=...)`를 사용해 의존성 실행의 동시성 상한을 지정하는 기능이 추가됐다.",
  "category_refs": ["IT_DIGITAL/소프트웨어·앱"],
  "source_platform": "ETC",
  "source_url": "https://github.com/fastapi/fastapi/releases/tag/0.163.0",
  "source_title": "FastAPI 공식 GitHub 릴리스",
  "thumbnail_url": null
}
```

- 초안 버전: `DRAFT-FASTAPI01630-v0.1`
- `source_title_origin`: `EDITORIAL_LABEL` (자체 작성 출처 안내 문자열; 공식 릴리스 원제목 자동 복제 아님)
- `source_label_evidence_id` 후보: `E-G4-04-FAPI01630` (이 문서 §2의 **내부 연결 참조**; 보호 등록된 독립 증거 ID가 아님)
- 이번 로컬 API(8001) 관찰: `IT_DIGITAL` 대분류 `category_id=1258`; `sort_order=4` 세부분류 `category_id=1262`, `parent_id=1258`. Seed 정의상 이 위치가 `소프트웨어·앱`에 대응하나 **API 응답의 한국어 문자열이 깨져 직접 이름 일치를 검증하지 못함**. 다른 DB 환경에는 ID를 재사용하지 않는다.
- `published_at=2026-11-14T16:53:02+00:00`은 **원출처 공개 시각**이며, Trend DB의 `collected_at` 또는 G4 승인 시각이 아니다.
- `source_platform=ETC`는 현재 앱에서 `기타`로 표시된다. 신규 GitHub 플랫폼 Enum을 만들지 않는다.
- 인기도 및 랭킹: `NOT_VERIFIED`. 사실로 주장하지 않는다.

## 2. 증거 연결 인덱스

| 내부 증거 ID | 확인 내용 | 증거 수준·한계 |
|---|---|---|
| `E-G4-01-FAPI01630` | GitHub 공식 Releases API의 `fastapi/fastapi` Release `445441864`, 태그 `0.163.0`, URL, 공개 시각, 릴리스 기능 설명 | 공식 API·원출처 조회 관찰. 별도 원본 응답 파일 보관 여부 미확인 |
| `E-G4-02-FAPI01630` | 로컬 `collect_github_releases()` 실행에서 `error_code=None`, 3건 반환, 0.163.0 `REVIEW_REQUIRED/NOT_FOR_PUBLICATION` | 사용자 제출 터미널 출력. 원본 실행 로그 파일·정확한 시각 미확인 |
| `E-G4-03-FAPI01630` | 담당자 `confirmed` / `adopt` / `checked` 및 이후 G4 최종 승인 의사 | 대화상의 **실제 사용자 의사 확인**. 최종 승인 이벤트의 정확한 오프셋 시각·권한 위임 증빙 미확보. G5/G6 승인 아님 |
| `E-G4-04-FAPI01630` | FastAPI 전용 `FastAPI01630SourceCard.g4.test.tsx`: 1 suite / 1 test PASS. 자체 표시값, 출처 링크 전달, `thumbnail_url=null` 이미지 미표시 | 사용자 제출 Jest 결과·검토한 프론트 코드 기준. 실제 모바일 기기에서의 링크 열람/OG 노출 전체 경로는 미확인. 출처 안내 문자열은 담당자 `checked` 기록과 함께 검토 |
| `E-G4-05-FAPI01630` | 본 문서 §1의 7개 표시 필드 및 `EDITORIAL_LABEL` 출처 선언 | **변경 감지 대상 초안**. 승인된 A1 `content_ref` 또는 보관된 보호 승인 원장이 아님 |

`E-G4-*`는 **이 문서에서 사용하는 내부 근거 참조**다. 별도 파일·서명·보호 저장소가 이미 존재한다고 주장하지 않는다.

## 3. A1 v0.2 승인 증거 연결 준비

| A1 항목 | 현재 연결 대상 / 상태 |
|---|---|
| `trend_ref` | `FASTAPI-01630-MVP-A-001` (임시 논리 참조) |
| `review_evidence_id` | `E-G4-03-FAPI01630` (담당자 승인 의사 기록) |
| `rights_evidence_id` | 담당자 사용 범위 검토는 `E-G4-03-FAPI01630`에 기록. **권리 적용 근거 및 실제 UI 노출 검토의 충분성은 미확정** |
| `source_title_origin` | `EDITORIAL_LABEL` (v0.2 조건부 규칙) |
| `source_label_evidence_id` | `E-G4-04-FAPI01630` (초안 연결; 원본 증거 보존 확인 필요) |
| `approved_by` | 기능·콘텐츠 담당자 (사용자 직접 승인 의사; 권한 근거 문서 미연결) |
| `approved_at` | **미확인** — 정확한 offset-aware 시각을 생성하지 않음 |
| `g4_result` / `approval_status` | **검증 완료 선언 보류**. 담당자 승인 의사 확인 사실과 A1 구조 적격 판정은 별도로 기록 |
| `content_ref` | **미산출 / 미고정** — A1 v0.2 실제 대조기 및 승인 대상 값 최종 확인 후 산출 |
| `g6_status` | `HOLD` (실제 게시 허가 없음) |

A1 v0.2 `content_ref`는 7개 표시 필드뿐 아니라 `source_title_origin`과 `source_label_evidence_id`까지 포함한 **계약상 정규 JSON + SHA-256** 지문이다. 임의 해시나 과거 Python 3.15 지문을 재사용하지 않는다. 자동 검사 PASS 또한 사용자 승인·실운영 권리를 독립 인증하지 않는다.

## 4. 정확한 최종 연결을 위해 남은 최소 증거

1. **활성 카테고리 ID:** 8001 로컬 `GET /api/categories`에서 부모 1258, 정렬순서 4의 자식 1262를 관찰했다. Seed와 구조는 일치하지만 한국어 라벨의 직접 일치는 깨진 문자열 때문에 미확인이다. 문자 인코딩 또는 API/DB 데이터를 확인하고 근거를 보강한다. `category_refs`는 논리 참조를 유지한다.
2. **표시/권리 범위:** 실제 앱에서 외부 OG 이미지·원문 자동 노출이 없고, 자체 설명·공식 URL·출처 안내만 사용한다는 범위를 확인한다. Jest 결과는 부분 증거로 보존한다.
3. **승인 시각과 내용 동일성:** 담당자의 정확한 승인 사건 시각이 없으면 임의로 만들지 않는다. 필요할 경우 **변경 없는 콘텐츠 재확인**을 별도 기록하고, 그 시점의 정확한 시각을 구분한다. 위 7개 필드와 출처 메타데이터 일치가 확인된 후 기존 A1 v0.2 도구로 `content_ref`를 산출·대조한다.

## 5. 현재 판정 및 금지 범위

- **완료:** 공식 소스 확보, 로컬 실수집, 담당자 콘텐츠 채택·승인 의사, Source Card 전용 Jest 1/1 PASS, 검토용 콘텐츠와 증거의 **논리 연결 초안 작성**.
- **미완료:** 승인 시각 근거, 카테고리 한국어 라벨 일치 증거, UI 전 경로·권리 근거, A1 v0.2 `content_ref` 계산 및 검사기 결과.
- **현재 상태:** G4 절차상 `HOLD`, A1 자격 **미판정**, Batch `NO`, G5·G6 `HOLD`, 실제 등록·게시 `NOT_ATTEMPTED`.
- **금지:** 승인 상태 임의 PASS 전환, 서비스/테스트 DB에 실데이터 삽입, 앱에 공개, P4/G5/G6 실행, 프로젝트 원격 파일 수정.


## 6. 카테고리 실조회 추가 증거 — `E-G4-06-FAPI01630` (2026-11-15 KST)

**관찰 주체/범위:** 사용자가 로컬 FastAPI `http://localhost:8001/api/categories`에 대해 PowerShell `Invoke-RestMethod`로 GET 수행; Uvicorn 접근 로그 `200 OK` 2건 제시. 이번 기록은 **실행 출력으로 전달받은 사실**이며, 서버 DB에 대한 별도 읽기 검증이나 저장된 원본 응답 증거는 아님.

| 항목 | 관찰 결과 |
|---|---|
| 최상위 카테고리 수 | 6 |
| 부모 | `category_id=1258`, `category_code=IT_DIGITAL`, `parent_id=null` |
| 대상 자식 행 | `category_id=1262`, `parent_id=1258`, `sort_order=4` |
| Seed 정의 비교 | IT_DIGITAL의 4번째 항목 = `소프트웨어·앱` (기존 `category_master.py`) |
| 한국어 원문 이름 직접 비교 | **미확인** — PowerShell JSON 출력의 `category_name`이 mojibake로 깨짐 |
| 결과 | **구조상 대응 후보 확인. 실제 표시 문자열/DB 활성 상태의 직접 증거는 보강 필요** |

**범위 구분:** `category_id=1262`는 이번 로컬 서버/DB의 수치 PK 관찰값이다. 다른 DB에서 사용할 정식 계약값은 `category_refs=["IT_DIGITAL/소프트웨어·앱"]` 같은 논리 참조를 유지한다. 해당 확인은 `content_ref`의 생성·G4 최종 승인 효력·G5/G6 게시 권한을 발생시키지 않는다.