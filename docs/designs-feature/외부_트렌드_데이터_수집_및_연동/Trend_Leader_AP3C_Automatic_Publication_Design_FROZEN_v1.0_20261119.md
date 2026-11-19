# Trend Leader — AP-3C 자동 게시 정책 및 독립 Writer 연결 설계 확정안 v1.0

> 2026-11-19 KST | 사용자 승인: AP-3C 검토안 v0.1의 권장 설계, Batch 1건, is_primary=true, 수집 주기 6시간.
> 기준 dev: 7eacb8682b8017f17452af5a941f0613d5904835 (PR #132 병합).
> 상태: **FROZEN — AP-3C 기능 설계의 범위 및 불변조건 / 실제 운영 게시 HOLD**.
> 본 동결은 구현 및 합성 검증 위임이다. 소스 권리·G6·실제 운영 DB 변경·배포 승인과 다르다.

## 1. 목적과 기존 계약

Collector → Rule-first Preview → Publication Policy → Independent Writer + Journal → MariaDB → 기존 FastAPI 조회 → React Native.
AP-1/2 실수집 및 AP-3 격리 합성 저장 실증은 재사용한다. AI API 기본 0회, 판단 불가 HOLD, 기존 AI 기능은 보존한다.
새 Schema/Migration, API, 관리자 UI, Redis/Celery, 다중 호스트는 제외. 별도 Python 실행 프로세스 및 단일 호스트로 시작한다.

기존 Gate v0.3의 G4 개별 담당 승인 및 P4 운영자 실행 지시는 신규 AUTO-TREND-MVP에 한해 승인된 규칙/정책에 따른 자동 개별 판정과 승인된 Scheduler 실행으로 대체한다. 기존 MVP-A/RSS-OPS/P4/E1-W0/W1 합성 계약은 직접 변경하지 않는다. G0~G3 해당 소스 권리 및 G5 기술 통제, G6 최초 운영 프로필의 독립 승인과 변경 시 재검토는 유지한다.
첨부 schema_decisions.md SD-009/010의 동일 제목 last_collected_at 갱신과 달리 신규 프로필에서는 동일 Release ID를 무변경 건너뛰기로 처리한다. SD-011/012는 유지하며 기존 RSS/Demo Source Key를 변경하지 않는다.

## 2. 확정 결정

| ID | 결정 |
|---|---|
| DEC-01 | Policy와 Writer 분리, Collector에는 DB 쓰기 권한 없음. 별도 실행 프로세스, 별도 Writer 계정. |
| DEC-02 | AUTO_ELIGIBLE / DEFERRED / SKIPPED / BLOCKED. 콘텐츠 적격성과 운영 승인 및 실행 실패를 구분. |
| DEC-03 | Godot 공식 Release ID, 태그, 유형, 공개 일시, 공식 URL과 자체 제목/설명, Category 후보만. 원문/이미지/로고/첨부/개인정보/AI 전달 제외. 운영 접근·저장·표시 권리 미확인, 운영 HOLD. |
| DEC-04 | 정확한 공식 메타데이터, 7일 창, 저위험 범위, 허용 필드, 실제 활성 Child, 권리 검증, 중복 확인 및 독립 운영 승인·철회·Journal 경계. |
| DEC-05 | 불변 후보 Snapshot과 정책/근거 참조. Writer가 신뢰된 근거와 정책을 독립 재검증하며 해시 일치나 입력된 Boolean만으로 승인 금지. |
| DEC-06 | 기존 테이블과 필드 매핑; 단일 Child is_primary=true. Source Key SHA-256 UTF-8(platform + ':' + external_id). |
| DEC-07 | 동일 외부 ID (HIDDEN 포함) SKIP·수정 0, 다른 ID 동일 제목 HOLD, 다중/불일치 식별 HOLD. |
| DEC-08 | 초기 운영 Batch 크기 1; 확정 Batch 전체 단일 Transaction. 기존 W1 합성 2건은 유지. |
| DEC-09 | 미해결 Journal/Commit Unknown 전역 HOLD, 자동 재시도 없음. Commit 전 발효 철회 Rollback, 후 별도 권한 HIDDEN 및 조회/캐시 검증. |
| DEC-10 | 기본 6시간(21600초), 정상 Cycle 최대 후보 1건, 정상 GitHub 요청 2회/Cycle, 8회/일 예상. 실제 제한·Retry-After 및 오류 처리 AP-4 검증. |

## 3. AP-3C-1 확정 범위 및 구체 계약

실제 ReleaseEvidence와 Rule-first Preview를 일치하는 경우에만 검토용 Snapshot 구성. 미확인 권리는 DEFERRED, 만료(7일 초과)는 SKIPPED, 불일치 및 잘못된 입력은 BLOCKED. 기존 CLI 수집/투영 오류는 기존 HOLD 유지.
독립적으로 검증된 권리·활성 Category·운영 프로필은 아직 없으므로 실제 후보 AUTO_ELIGIBLE을 발행하지 않는다. 고정 합성 fixture만 분리 프로필의 AUTO_ELIGIBLE 예시를 구성할 수 있다. 이 예시는 권리/DB 검증의 대체가 아니며 임의 외부 후보를 입력받지 않는다.
SourcePolicy는 현재 Godot 운영 접근/저장/공개 권리 UNVERIFIED, AI 전달 DENIED로 고정. 신뢰된 권리 저장소/변경 권한/발행 주체를 AP-3C-2 및 운영 승인 전 별도 검증한다.

Snapshot: profile_id, policy_version, target, candidate_identity, evidence_ref, title, normalized_title, summary, source_url, external_id, source_key, platform, parent_code, child_name, observed_at_utc, source_published_at, proposed_status, is_primary, thumbnail_url=null, source_title=null.
Python frozen/slots dataclass, 정렬된 JSON key, compact separators, ensure_ascii=false, UTF-8, NaN 금지. SHA-256 content_digest는 Snapshot 전체에 대한 내용 동일성 확인 지표. evidence_ref는 수집 메타데이터의 canonical digest이지 독립 출처 검증이나 승인 증명이 아니다. evaluated_at은 주입된 현재 관측 UTC. 실제 Writer는 같은 값의 무결성뿐 아니라 최신 시각/권리/정책/대상 재검증 필요.
실제 Snapshot의 target=UNBOUND_OPERATIONAL, proposed_status=ACTIVE는 **향후 승인 시 제안값**이다. 저장 가능한 대상/권한을 의미하지 않는다. 합성 예시는 별도 프로필과 synthetic-ap3 namespace, example.invalid URL, HIDDEN, ISOLATED_SYNTHETIC_ONLY를 사용한다.

AP-3C-1에는 Writer 호출, Engine, DB 설정, CLI APPLY, 운영 승인 발급 기능이 없다. writer_boundary는 모든 입력을 BLOCKED_AP3C1_NO_WRITER_AUTHORITY로 처리하는 계약 표시이며 실제 connector 연동 테스트는 AP-3C-2에서 수행한다. 기존 AP-3 합성 Writer에는 변경 없음.
기존 read-only CLI에 --policy-preview를 추가한다. 기존 기본 및 --rule-first 동작을 유지하며 해당 두 옵션은 상호 배타적이다. 출력에는 판정/이유/Writer 차단 표시만 추가하고 Snapshot 전체나 실행 허가는 내보내지 않는다. 기존 in-process 중복을 영속 DB 중복으로 주장하지 않는다.

## 4. AP-3C-2 / AP-4 연결 불변조건

실제 적격 판단의 권한은 보호된 정책 근거 및 검증 주체에 귀속된다. Scheduler나 외부 입력이 운영 프로필을 자체 승인하지 않는다. G6 미확인/철회/권리 불명/기록 불일치 시 서비스 DB 연결 0. Writer는 정책/후보/근거의 독립 대조와 배타적 철회 조정, 보호 Journal STARTED 확인 이후 동일 세션 대상·권한 및 활성 부모/Child·중복 재검증.
DB: 승인된 실제 신규 건은 명시적 ACTIVE, 허용된 제목/설명, 최초/마지막 수집 시각 최초 관측 UTC(현재 DATETIME 계약에 맞춰 저장), thumbnail/source_title NULL, ETC, external_id, source_key, Child category_id, is_primary=true. 동일 외부 ID에는 INSERT/UPDATE하지 않는다. 전체 source identity UNIQUE는 현재 없으므로 단일 Writer 직렬화 필요. 다른 쓰기 경로와의 조정/DB 제약 및 Category 활성 변경 경쟁 검증 없이 동시성 안전을 주장하지 않는다.
Journal 보호·미해결·교체·장애·프로세스 경합 및 정책 철회 공유 조정 실증은 남음. Writer INSERT 최소권한 유지, 공개중단은 별도 권한 책임. 승인되지 않은 실데이터는 서비스 DB에 HIDDEN으로도 적재 금지. 실제 운영 대상/권한/Source rights 승인·G6·공개중단 및 API/캐시 확인 전 운영 활성화 금지.

## 5. 수용 기준 / 현재 상태

| AC | 기준 | 단계 |
|---|---|---|
| 01 | AI 0회, 허용 필드 기반 Preview | AP-2 실수집, AP-3C-1 회귀 |
| 02 | 권리 미확인 DEFERRED, 변조 BLOCKED | AP-3C-1 |
| 03 | 운영 미승인 실제 connector 0회 | AP-3C-1 경로 없음, AP-3C-2 실제 연결 검증 |
| 04 | Snapshot / 정책 불일치 거부 | AP-3C-1 순수 대조, AP-3C-2 독립 권한 검증 |
| 05 | 신규 합성 단건 원자적 등록 | AP-3C-2 (기존 W1 2건 실증 재사용) |
| 06 | 영속 중복 무변경 | AP-3C-2 |
| 07 | Journal 장애 및 철회 경쟁 차단 | AP-3C-2 |
| 08 | 권리·G6 승인 후 실제 데이터 기존 API 조회 | AP-4 |
| 09 | 모바일 카드 및 원출처 정상 | AP-4 |
| 10 | 6시간 주기의 건별 무인 공급 및 중복·오류 방어 | AP-4 |

## 6. 기준 자료 및 검증의 한계

dev 기준 Godot Collector 37b139f, Rule-first Preview d6528c5, 기존 CLI 8ccb937, AP3 Writer Transaction d41995d, Journal 167a311, MariaDB fixture f6ba1b1. 자동 게시 정책 개정안 v0.1 + §0 Rule-first 8022822, Gate v0.3 4140b11, P4 Addendum v0.2 ac974e5, 별도 B-Lite E1-W1 동결 계약(847970d), 첨부 schema_decisions.md SD-009~012 및 개발 가이드 v1.3·GitHub Write Safety Policy.
기존 실제 테스트 결과는 사용자가 전달한 기록이며 이번에 DB/운영 권리/배포를 재실행하거나 승인하지 않았다. 실제 운영 HOLD 유지.
