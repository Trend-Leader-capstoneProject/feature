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


## 7. 사용자 승인 DEC-11~16 — 실제 공급 수직 통합 (Stage 1, 2026-11-19)

> 승인: 제한된 Godot 사실·메타데이터 이용을 첫 공급 범위로 채택, 최초 독립 운영 승인, 비게시/실제 경로 분리, 기존 Writer 재사용, OS Scheduler 단회 실행 및 로컬→Lightsail 실증. Stage 4의 다분야 공급 확장을 염두에 둔다. **설계 및 코드 구현 승인에 한정; G6 실제 운영 승인·DB 변경·배포는 별도이며 현재 HOLD.**

- DEC-11: Godot 공식 Release ID·버전·유형·공개일·원문 URL과 자체 사실 기반 제목/설명만. GitHub 공식 REST 공개 접근과 약관 D.8/H, 사실과 창작 표현의 구분(인수인계 문서 공식 근거 참조)을 바탕으로 이 범위를 채택하되 포괄 허가로 확대하지 않는다. 원문/이미지/로고/첨부/개인정보/AI 전달 제외. 별도 문의를 무조건 선행하지 않고 실제 범위에 중대한 제한이 있는 경우 해당 소스/행위만 제외한다. NCP·Google RSS 기존 제한 유지. 운영 프로필의 독립 권리 근거 등록은 남아 있다.
- DEC-12~13: 보호된 운영 프로필 AUTO-TREND-MVP / AUTO_V1, 승인 소스 목록 및 개별 이용 범위·근거, 승인자·유효기간·실제 대상·G5/G6 참조를 확인한다. AP-3C-1 검토용 DEFERRED 및 합성 경로는 유지. 실제 경로는 보호 프로필과 독립 상세 검증으로 Snapshot을 대상에 결합하며, 검토용 Boolean/해시만으로 권한을 부여하지 않는다.
- DEC-14: 공급원별 Adapter의 수집·검증만 특화한다. 고정 registry와 승인 목록으로 소스 확장, 공통 Snapshot/Category/영속 중복/SQL/Journal 재사용. Writer는 독립 공식 상세 조회 1회를 추가한다(DEC-10 정상 수집 2회는 유지, 신규 후보 전체 최대 3회/Cycle, 6시간 기준 첫 소스 최대 12회/일 예상). 동일 ID와 일치하는 Source Key면 무변경 SKIP(HIDDEN 포함), 충돌/비활성/불명확한 Commit 차단. MariaDB 활성 부모/Child는 명시적 REPEATABLE READ Transaction 안에서 공유 잠금 조회, 단건 3개 INSERT 원자성. 실제 잠금/권한 및 다른 쓰기 경로 배제는 운영 전 실측한다.
- DEC-15~16: OS Scheduler 단회 실행, 6시간, 기존 로컬 3309와 기존 Lightsail만 활용. 실제 APK 조회 및 원문 이동까지 수직 통합 후 여러 분야 공급으로 확대. OS 스케줄러 등록/배포/실데이터 적재는 이번 Stage 1에서 하지 않는다.

### 7.1 Stage 1 구현 세부 계약 및 제한

- `app/trend_collection/supply_adapter.py`: SourceAdapter(collect_preview/verify/scope)와 고정 registry. 현재 실제 Godot만 등록. ID로 공식 상세 endpoint 고정, 정확한 Rule-first Preview 재구성, 관측 10분 이내 및 공개 7일 이내 검증. 입력에서 받은 URL로 직접 요청하지 않는다. 복수 승인 소스 목록 지원은 Stage 4를 위한 최소 확장 지점이며 다분야 실수집 구현 완료는 아니다.
- `scripts/run_auto_supply.py`: collect/write 단회 CLI와 제한된 JSON handoff. Linux의 독립 비root UID 및 root 소유 비쓰기 가능 디렉터리/파일, 승인/철회를 조정하는 안정된 control.lock(배타 flock), 승인 근거/대상/만료 검증을 사용한다. 실제 파일은 /etc/trend-leader/auto-supply/approval.json, control.lock 및 writer-password; 권리 레코드에는 각 source_id, scope, rights, rights_ref, 프로필에는 environment, collector_uid, writer_uid, port, database, current_user, journal_id/device/inode, approved_at/valid_until/approved_by, g5_ref/g6_ref를 요구한다. enabled=true 및 PROFILE/VERSION 검사는 독립 관리자 발행 기록에 한한다. 실행자는 자동 발행·초기화할 수 없다. 증거 참조의 실질적 심사는 독립 승인 책임이며 문자열 존재 자체가 증거가 아님.
- 독립 Writer 전용 DB 계정 trend_auto_writer의 정확한 CURRENT_USER 및 승인된 loopback 대상(3306/3309, 테스트 DB 제외), SHOW GRANTS, PUBLIC grants 없음, InnoDB 및 FK/unique 검사. 자격증명은 root 소유, Writer 그룹 읽기, Collector 그룹 접근 금지. 실제 환경의 코드/실행 경로 보호, 다른 계정의 쓰기 배제, 계정/그룹/DB 대상은 Stage 2/3 검증.
- SQLite Journal 기존 schema/검증/claim/finish 재사용, 운영 모드/대상 분리. 신규 운영 journal은 /var/lib/trend-leader/auto-supply/journal.sqlite3, 사전 독립 등록된 identity 및 device/inode 대조, 보호된 부모/Writer 전용 디렉터리, 미해결 기록 시 연결 전 차단. 기존 3307 합성 Journal은 절대 변경하지 않는다. Stage 1은 운영 Journal을 생성하지 않는다. inode 검사만으로 악의적 동일 UID/관리자 조작까지 방어한다고 보지 않는다.
- Collector/Writer/승인 변경은 동일 안정된 control.lock과 권한 분리 아래 단일 호스트에서 동작한다. Writer는 잠금 구간에서 최신 승인 재대조 및 Commit 직전 만료 확인. 독립 관리자가 동일 잠금 아래 승인 철회를 발효하고 사후 공개중단은 별도 승인 권한으로 HIDDEN 및 조회/캐시 확인. 관리자 철회/공개중단 실행, Journal 안전한 사전 등록, 실제 OS 권한·잠금 경쟁 및 DB 동시성 검증은 아직 미실행. 활성 승인 파일 예시/자동 생성 경로를 배포하지 않는다.
- 운영 진입점은 Linux만 지원하는 구현 선택(기존 Windows 순수 테스트는 유지). 기존 로컬 WSL/Linux 환경과 3309 연결 가능성을 먼저 확인해야 하며, 불가하면 로컬→Lightsail 실증 순서 변경은 별도 결정한다. 6시간 스케줄 등록, Retry-After/요청 제한의 장기 재시도 제어, 실제 G5/G6·공개중단·APK 검증은 운영 활성화 전에 완료. 별도의 외부 서비스/DB/컨테이너/의존성은 도입하지 않았다.
- Stage 1 검사: 격리 사본에서 기존 112 + 신규 31 = 143 PASS, compileall, CLI help 및 미승인 root 실행 HOLD. Mock/SQLite 시험으로 실제 MariaDB/OS 권한·철회 경합을 검증했다고 주장하지 않는다. Ruff/전체 프로젝트 conftest 및 실데이터 저장 미실행. 실제 운영 HOLD 유지.
