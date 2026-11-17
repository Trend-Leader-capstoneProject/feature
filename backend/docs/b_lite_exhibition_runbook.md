# B-Lite 전시 — E0 읽기 전용 사전 검증

**상태: E0 ONLY / REVIEW_ONLY / NOT PUBLISHED / G5-G6 HOLD**

이 명령은 DB에 연결하거나 콘텐츠를 게시하지 않으며, 검토자의 신원이나 실제 승인 근거의 유효성을 검증하지 않습니다. 기존 G5 P1 HOLD 차단 Gate, 격리 환경 전용 Daily CLI, Phase 4 FROZEN 작업 또는 B-3/L-2 절차를 대체하지 않습니다.

## Windows에서 실행하기

프로젝트를 체크아웃한 뒤 Backend Python 실행 환경을 활성화하고, UTF-8 인코딩의 JSON 매니페스트 경로를 지정합니다.

```powershell
cd backend
python -m scripts.b_lite_exhibition_once --input "C:\path\to\review-manifest.json"
```

또는 JSON 파일 경로를 `backend\scripts\run_b_lite_exhibition.bat`에 인수로 전달하거나, JSON 파일을 해당 `.bat` 파일에 끌어다 놓을 수 있습니다.

이 `.bat` 파일은 동일한 **읽기 전용** Python CLI만 호출합니다. **실제 등록·게시를 실행하는 옵션은 없습니다.**

- `REVIEW_ONLY`: 종료 코드 `0`
- `BLOCKED`: 종료 코드 `1`
- 잘못된 CLI 옵션: 종료 코드 `2`

매니페스트나 GitHub 저장소에는 비밀번호 등 인증정보를 넣지 마세요.

## 검토 후보 매니페스트 — 합성 데이터만 포함한 예시

```json
{
  "schema": "B_LITE_EXHIBITION_REVIEW_V1",
  "profile_id": "MVP_A_EXHIBITION_20261118_19",
  "approval_scope": "REVIEW_ONLY",
  "g6_status": "HOLD",
  "batch_id": "EXAMPLE-REVIEW-ONLY",
  "records": [
    {
      "kind": "SYNTHETIC_DEMO",
      "title": "【DEMO】 가상 시연 주제",
      "summary": "가상의 시연 데이터입니다. 실제 검색·수집 결과가 아닙니다.",
      "thumbnail_url": null,
      "google_rss_derived": false,
      "parent_code": "GAME",
      "child_name": "기타",
      "source_url": null,
      "source_title": null
    }
  ]
}
```

실데이터 후보인 `REVIEWED_REAL`에는 추가로 다음 정보가 필요합니다.

- `review_evidence_id`
- 형식이 올바른 `content_ref`: `sha256:` 접두사 뒤에 소문자 16진수 64자리
- `source_review=URL_TITLE_KEY_CLAIMS_VERIFIED`
- 외부 HTTPS 주소인 `source_url`
- 출처 안내 문구를 사용하지 않는 경우: `source_title_origin=NONE`, `source_title=null`, `source_label_evidence_id=null`
- 팀이 직접 작성한 출처 안내 문구를 사용하는 경우: `source_title_origin=EDITORIAL_LABEL`, 1~80자의 `source_title`, 비어 있지 않은 `source_label_evidence_id`

**이 필드들은 입력자가 작성한 선언일 뿐, 검증된 승인 증거가 아닙니다.** 현재 도구는 증거의 진위, 원출처 내용, 링크 접속 가능 여부, 콘텐츠 해시 일치, 실제 DB 카테고리 존재 여부, Google RSS 데이터 유래 여부, 실행 계정의 DB 권한(GRANT), G6 승인을 검증하지 않습니다. 이러한 검증은 별도로 승인받은 후속 단계에서 다룹니다.

입력 제한 및 동작은 다음과 같습니다.

- 레코드 `1~36건`, JSON 파일 크기 `1MB 이하`
- 프로젝트에서 정의한 6개 대분류 코드만 허용
- 중복 JSON 키, 중복 제목, 실데이터 후보 간 중복 Source URL은 차단
- 결과는 사유를 포함한 `BLOCKED` 또는 `REVIEW_ONLY`이며, **어느 경우에도 게시 허가를 의미하지 않음**
- 입력 JSON을 읽기만 하며 별도 결과 보고서 파일을 생성하지 않음

## 다음 단계 — 현재 E0 범위에 포함되지 않음

이 사전 검증 결과만으로 운영 DB에 `INSERT`를 실행하거나, `HIDDEN` 상태로 사전 등록하거나, 마이그레이션·DB 권한 변경·APK 배포를 진행해서는 안 됩니다.

별도로 승인받는 전시 한정 일회성 Writer에는 신뢰할 수 있는 G4/G6 승인 증거 확인, 실제 대상 DB 식별 및 유효 GRANT 확인, 영속적인 실행 Journal, Batch 전체의 원자적 트랜잭션, 승인 철회·공개중단 처리, 격리 환경 테스트, 독립적인 B-3/L-2 및 운영 배포 승인이 필요합니다. 관련 증거를 독립적으로 확보·검증하기 전까지 **G5/G6는 HOLD**입니다.

격리 테스트는 `backend` 디렉터리에서 `python -m pytest tests/core/test_b_lite_exhibition_once.py -q` 명령으로 실행합니다.

**검증 범위 주의:** 본 문서의 PowerShell 경로와 명령어는 사용자 Windows 실기기 환경에서 아직 검증하지 않았습니다.
