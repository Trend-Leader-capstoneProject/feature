# Reviewed Demo Daily Manual Registration — 최소 설계 v0.1

> 작성일: 2026-11-16 KST
> 대상 브랜치 기준: `feat/responses-live-mvp-20261116`, `d13076fd135be83e7409ba9445d36a763cd06943`
> 상태: **전시 전용 설계·구현 인계 기준**, 신규 구현 및 실제 DB 테스트 전에는 완료 아님
> 적용 기간: 2026-11-17 검증, 11-18~19 전시

## 1. 문제·목표·범위

- 이미 검증한 ICT 단일 후보: 실제 Responses 검색 → 수동 출처 확인 → 격리 DB(3310) 1건 등록 → 기존 API(8001) → Android TrendCard까지 성공했다.
- 6개 대분류 `FASHION`, `BEAUTY`, `GAME`, `FOOD`, `ENTERTAINMENT`, `IT_DIGITAL`에서 각 4건, 총 24건을 우선 목표로 한다. 확대 목표는 각 6건, 총 36건이다. ICT 기존 1건을 포함하면 목표 신규 수는 23/35건이다.
- **완성 범위:** 로컬 승인 격리 DB에 대해서만, 사람이 원출처를 검토한 Reviewed JSON을 CLI로 등록. 검색 자동화·스케줄러·운영 Writer·원격 DB DML·게시 승인·새 Schema·공개 API·UI 변경은 제외.
- 입력 형식은 **하루당 JSON 한 파일, 그 안에 `records` 배열**이다. 파일 1개/Trend 1건 규칙을 채택하지 않는다. 실제 DB 쓰기는 **1 Trend당 독립 Session/transaction/commit**이다.

## 2. 상위 확정안 및 충돌 기록

- `Trend_Leader_카테고리_Taxonomy_및_트렌드_매핑_설계_확정안_v1.0.1.md`: Category 6대분류/38세부분류; ID는 DB에서 조회. 일반 매핑 `is_primary=false`, 부모 대분류 매핑 금지. 기존 ICT 시연은 `is_primary=true`로 등록됨. **이 기존 행을 수정하지 않고 신규 등록은 false 사용**.
- `Trend_Leader_전체_트렌드_목록_조회_설계_확정안_v1.0.14.md`: 기존 `GET /api/trends` ACTIVE/Category/최신 Source, UTC-naive DB 저장 및 UTC-aware API 반환 유지.
- Phase 4B-2 검토·보호 등록 **FROZEN**은 운영 Evidence/ACL/철회용이며 이번 시연 DB INSERT 경로와 별개의 계약이다. 해당 FROZEN 구현/권한/게시 완료라고 주장하지 않는다. S0/S1 및 G5/G6 HOLD 유지.
- 기존 `app/services/reviewed_demo_registration.py`은 특정 ICT 제목, 정부 출처, 격리 포트/ID를 고정한 안전한 단일 후보 기록이다. **기존 함수·CLI·JSON·테스트를 그대로 보존**, 새로운 다분야 구현이 이를 덮어쓰거나 고정값을 완화하지 않는다.
- 현재 Responses 검색 D0 설정은 IT_DIGITAL 전용이다. 타 대분류에서 수동으로 발견한 자료를 Responses 발견으로 허위 표기하지 않는다.

## 3. 입력 UX: 1일 1 JSON · 복수 후보

제안 입력 예시(실제 URL, 사람 검토·승인은 예시 값을 복사하지 말고 사실대로 기입):

```json
{
  "input_kind": "REVIEWED_DEMO_DAILY_BATCH",
  "approval_scope": "ISOLATED_DEMO_ONLY",
  "reviewer_alias": "demo-operator",
  "approved_record_count": 2,
  "records": [
    {
      "title": "원출처에 근거한 주제 제목",
      "source_title": "원출처 페이지의 실제 제목",
      "source_url": "https://example.org/news/1",
      "parent_code": "FASHION",
      "child_name": "신발",
      "discovery_method": "MANUAL_WEB_REVIEW",
      "original_ai_source_url": null,
      "original_failure": null,
      "source_checks": {
        "page_opened": true,
        "title_matched": true,
        "key_claim_matched": true
      },
      "review_note": "공식 원출처와 출시 사실 확인",
      "operator_approved": true
    }
  ]
}
```

`approved_record_count`는 이번 실행 대상 `records.length`와 **정확히 일치**해야 한다. 예시 `2`와 배열 1건은 **일부러 불일치한 미완성 예시**가 되므로 실제 사용 시 둘을 반드시 일치시킨다. 

입력 정책:
1. `records`는 비어 있지 않고, 1회 실행 입력 상한은 36건. 과도한 범용 배치 처리는 제외.
2. `parent_code`는 확정된 6개 값만 허용, `child_name`은 해당 부모에 속한 **유일한 활성 직계 세부분류**로 DB 재조회. ID 하드코딩 금지. 분류가 모호하거나 미존재·비활성 시 거절. `기타`는 확정된 fallback 조건에만 사용.
3. 신규 간소화 입력은 Trend마다 세부분류 1개·Source 1개. 기존 DB/조회 API의 다중분류 지원을 변경하지 않는다.
4. 사람이 직접 발견했다면 `MANUAL_WEB_REVIEW`, Responses 검색에서 발견했다면 `OPENAI_RESPONSES_WEB_SEARCH_LIVE`. Responses 기록에는 원래 AI 출처 URL 및 실제 citation 상태/실패 사유를 명시적으로 보존한다. 원본 `CITATION_URL_MISMATCH`를 누락·PASS 변환하지 않는다.
5. `source_checks`는 `page_opened`, `title_matched`, `key_claim_matched`의 3가지 실제 사람 확인 진술이다. 숫자·출시·일자 등 제목의 핵심 주장에 증거가 없으면 확인 완료 처리 금지. 출처 전체 정독, 별도 장문의 보고서, AI 요약·이미지 생성은 필수 아님. `review_note`는 한 문장으로 충분.
6. `reviewer_alias`, 개별 `operator_approved=true`, `review_note`, `approved_record_count`는 필수. JSON의 자기 진술만으로 신원 인증을 증명했다고 주장하지 않는다. `--execute`에서 TTY로 **일괄 등록 건수에 대한 명시적 확인**을 받아 무인 실행 금지.
7. 검색·출처 공개·사람 검토 완료 시각은 **확인되지 않았으면 만들지 않음**. CLI 승인·DB 등록 시각은 실제 실행 시에 별도 기록하고 다른 시각으로 전용하지 않는다. Provenance/승인 영수증은 DB Schema를 변경하지 않고 로컬 별도 JSON 파일 또는 표준 출력에 보존한다. 영수증에는 비밀값 금지.
8. 모든 입력은 먼저 검증하며, **같은 배치 안 중복 정규화 제목·Source URL**은 사전 거절. 기존 DB에서도 동일 검사를 실제 등록 직전 반복한다.

## 4. 실행 경계 및 Transaction

- CLI 예시 (명령 및 파일명은 구현 시 확인):
  - `python -m scripts.register_reviewed_demo_daily --input <daily.json> --password-file <external-password-file>`: 기본은 **read-only preflight**, DML 없음.
  - 동일 명령에 `--execute`를 추가하는 경우에만 TTY에서 `REGISTER <N>` 확인 후 실행. 동일 DB 1회 실행·자동 재시도 없음.
- 연결 설정은 로컬 격리 대상 `127.0.0.1:3310 / trend_leader_demo_review_20261117 / trend_demo_review@%`와 고정 Alembic `b7f2c81d9e04`만 수용. 비밀정보는 저장소 외부의 credential 파일, 로그에 출력하지 않음.
- 기존 `_verified_seed_connection`의 단일 물리 연결/Session/트랜잭션 가드를 재사용하되, Demo Seed 데이터 생성 함수를 호출하지 않는다. `app_env=local`에서만 허용. Category 조회 시 활성 Parent·Child 및 관계를 같은 트랜잭션에서 검증하고 잠근다.
- 1건당 Trend 1, TrendSource 1, TrendCategoryMap 1 INSERT; `status=ACTIVE`, `platform=ETC`, `summary/thumbnail=null`, `is_primary=false`. UTC 시각을 MariaDB DATETIME에 UTC-naive로 기록. 성공 시 ID 3개, 입력 해시·시각·출처 유형을 기록한다.
- 성공한 건을 다음 건의 실패 때문에 Rollback하지 않음; **해당 1건의 세 INSERT는 원자적 Rollback**. 등록 실패·중복·DB 대상 오류가 발생하면 거절·종료하고 무인 재시도하지 않음. Commit 결과 불명확 시 무조건 정지, 수동 조회 후 판단. 스크립트 재실행도 중복 차단.
- 부하/경합 범위: 한 사람, 하나의 CLI, 순차 실행. Source URL에 전역 UNIQUE가 없으므로 사전 중복 조회만으로 **동시 Writer 경쟁까지 방어했다고 주장하지 않음**.
- 실제 출처 확인은 사람에게 위임하며, 코드가 원문 진실성·권리·게시 적격성을 자동 보증하지 않는다.

## 5. 최소 구현 / 테스트 / Acceptance

**권장 파일:** 신규 Daily Service, 신규 CLI, 신규 Daily 테스트 및 위 문서. 기존 조회 API/TrendCard/DB Schema·Migration 수정 없음. 기존 Repo 조회·정규화·세 INSERT 중 가능한 부분만 재사용하고, Category 조회와 동적 매핑값에 한정해 최소 조정한다. 기존 ICT 경로를 변경한다면 기존 회귀 통과가 필수다.

필수 검증:
1. batch 건수·레코드 구조·6개 parent_code·source_checks·수동/Responses provenance, 필수 검토 기록 거부 반례
2. 실제 DB 활성 Parent/Child 유일성, 비활성·모호·타부모 Category 거절; 상수 Category ID 사용 금지
3. 다른 DB(3307/3308/3309/운영) 연결 이전 차단; 기존 보안 가드·비밀값 비노출
4. 조회 전용 기본 모드에서 DML 0; 승인 없는 `--execute`에서 DML 0
5. 단건 INSERT 원자성, 중복/동일 배치 재실행 거부, Source INSERT 실패 Rollback, 불명확 Commit에서 자동 재시도 0
6. 기존 ICT 단일 경로 회귀와 신규 관련 테스트, Ruff
7. **승인된 신규 실자료 1건에 한해** 로컬 격리 MariaDB 실제 COMMIT·조회 확인. 별도 사용자 승인 없이 임의 자료를 INSERT하지 않는다.
8. 기존 `GET /api/trends` 200 및 신규 Trend 노출, Parent filter, TrendCard 실기기 확인. 사용자 실기기 수동 검증은 도구 자동 검증과 구분.

**완료 표현:** `DIFF/STATIC`, `TESTED`, `LOCAL_DB_VERIFIED`, `DEVICE_VERIFIED`를 각각 별도로 보고하며, 테스트 전 코드를 완료라고 주장하지 않는다.

## 6. 확정하지 않은 운영 사항

- 24/36건의 실제 출처와 독립적인 팩트체크는 아직 수행되지 않았다.
- 원격 Lightsail DB 반영은 이번 CLI의 대상이 아니다. 별도 운영 승인 없이 격리 로컬 데이터를 클라우드에 업로드하지 않는다.
- 부재 시 운영자가 직접 실행할 수 없는 무인 스케줄러·재시도·일괄 게시 기능은 만들지 않는다.
