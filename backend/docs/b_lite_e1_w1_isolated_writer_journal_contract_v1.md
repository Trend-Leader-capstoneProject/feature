# Trend Leader — B-Lite E1-W1 격리 Writer·Journal 최소 실행 계약 v1.0

> **상태: E1-W1 격리 구현 계약 한정 확정(FROZEN) / NOT IMPLEMENTED / NOT TESTED / NOT FOR OPERATIONAL APPLY**
>
> 기준일: 2026-11-17 KST · 기준 브랜치: `feat/b-lite-exhibition-manual-20261117` · 기준 HEAD: `682d44316e3e306eefaa05e02376596b96bf60cc`
>
> **운영 상태:** 실제 G5/G6 **HOLD**. 이 문서의 동결은 격리 시험 범위의 책임·안전 불변조건만 고정하며, 실데이터 등록·서비스 DB 연결·게시 권한·G6 최종 승인을 뜻하지 않는다.

## 1. 검증된 현 상태 및 이번 결정

- Windows 사용자 보고 증거: E0 19개 + AL-02 12개 + E1-W0 11개 = **42 passed, 1 warning**. `python -m scripts.b_lite_e1_preconnect_entry --input ...` → `BLOCKED / APPROVAL_DOCUMENT_MISSING`, exit `1`, 반환상 DB 연결/쓰기 `0`. **실제 Writer DB 연결 경로 테스트는 아니다**.
- AL-01: 승인 문서의 파일 ACL과 SHA-256 산출 확인. 독립 기준 해시·승인권자 인증·Writer 수정 불가 검증은 미완료다. ACL 추가 자동화·전자서명은 이번 구현에 포함하지 않는다.
- **이번 확정:** 기존 E0/AL-02/W0의 차단 동작은 불변. 새 **격리 시험 전용** 별도 CLI Writer와 보호된 실행 Journal의 *최소 책임과 거부·장애 규칙*만 동결한다. 상세 저장 형식·실제 DB 연결 설정은 격리 환경을 실측한 뒤 해당 구현 단계에서 결정한다.
- **불변:** G4 개별 실데이터 검토, G5 Batch 통제, 독립 G6 운영 프로필 승인, 철회 유효성, Writer 최소권한·실행 격리, 단일 Batch 트랜잭션, 보호 Journal, 중복 및 실패 시 중단. 별도 실제 승인 원본의 신뢰 입증은 생략할 수 없다.

## 2. 문서 간 적용 경계와 충돌

1. **P4 Addendum v0.2 DRAFT:** 게시 지시 API + 별도 Writer(A1), 보호 영속 Journal(B2), G4/G6 독립 대조, 전체 확정 Batch 원자성 및 재실행 HOLD를 제안한다. **전시용 B-Lite에서 사용자가 선택한 수동 CLI는 해당 P4 API 방향의 좁은 전시 한정 예외**다. 원래 P4 DRAFT·P4-DEC·FROZEN 문서를 직접 변경하지 않는다.
2. **건수 차이:** E0 `B_LITE_EXHIBITION_REVIEW_V1`은 검토 최대 **36개**. P4 참조 Envelope v1의 **1~10개**는 해당 P4 어댑터에 대한 DRAFT 상한이다. E1-W1은 그 Envelope를 도입하지 않으므로 이 상한을 무조건 복제하지 않는다. **격리 시험은 검증된 작은 합성 Batch(우선 2개)**로 시작하며 실제 21~25개 APPLY 가능 여부는 이번 동결 대상이 아니다. 실제 게시 건수·분할 Batch 결정은 별도 검증 대상이다.
3. **Gate v0.3과 P4-DEC-04:** 후보 선별에서 부적격 항목을 제외할 수 있지만, *확정된 한 Batch* 실행 중 하나라도 검증 실패·중복·철회되면 전체 HOLD/ROLLBACK. 일부 성공을 자동 Commit하지 않는다.
4. **G5 P1 FROZEN(HOLD 경계):** G6 누락·HOLD·문구형 PASS·검증기 없음은 게시 DB 연결 **0회**, DML **0건**으로 차단한다. E1-W0가 BLOCKED만 반환한다는 사실을 운영 G6 신뢰 검증 완료로 해석하지 않는다.
5. **Phase 4B-2 FROZEN:** 로컬 관측 검토 등록과 승인 사건은 `publish_authorization=NONE`이며 E1의 G6 최종 승인 증거를 대체하지 않는다. 해당 기능의 기존 CLI·ACL·백업·철회 계약은 변경하지 않는다.

## 3. E1-W1 최소 구현 범위

| 구성 요소 | 해야 할 일 | 금지·제외 |
|---|---|---|
| 기존 E0 + AL-02 + W0 | Windows에서 확인한 HOLD 차단 그대로 유지 | `PASS` 해제, `--apply` 추가, E0 검토 상한을 게시 허가로 오용 |
| **별도 격리 Writer CLI** | 사용자 승인된 별도 격리 DB에서만 합성 Batch의 트랜잭션·오류 경로 시험. 단일 호스트·수동 실행 | 기존 일반 API/운영 DB, Daily CLI, 공개 게시 API 수정 및 운영 자격 증명 사용 |
| **시험 전용 Gate Fixture** | *합성 시험에서만* 유효한 내부 제어 신호로 정상 Commit/Rollback 시험. 실제 G6 승인과 완전 분리 | 승인 문서 문자열·CLI YES·파일 해시를 진짜 `G6=PASS`로 전환, 동일 경로에 운영 DB 선택 옵션 제공 |
| **보호 영속 Journal** | Batch의 시작·결과·미해결/중복 상태를 재시작 뒤에도 구별; 구조화 로그와 책임 분리 | stdout만 사용, 손상 시 자동 재생성, 오류 후 자동 재실행, 무승인 신규 DB 감사 테이블 추가 |
| **DB 권한·대상** | 운영 경로와 격리 계정 분리. 격리 DB 대상·사용자·계정 권한을 실측하고 비일치 시 DML 전 차단 | 환경 변수 `APP_ENV=local`만으로 격리 증명, 관리자/root 자격 증명 관행적 사용 |
| **회수 및 철회** | 격리 시험에서 Commit 전 철회 시 전체 차단; Commit 후 비노출은 별도 검증 | `HIDDEN` 자동 복원, 게시된 데이터를 파일 삭제만으로 철회했다고 주장 |

**중요:** `E1-W0`의 DB 미연결 반환값을 실제 DB 세션/Engine 차단 시험으로 대체하지 않는다. 격리 Writer 경로는 운영 자격 증명을 받아서는 안 되며, 진짜 운영 G6 PASS 검증기를 만드는 일은 **본 동결의 구현 범위 밖**이다.

## 4. 실행 순서의 불변조건

```text
[실행 전] 격리 대상 및 비운영 시험 프로필 확인
  ├─ 불명확/운영 대상 → BLOCK, DB 연결 0 (가능한 사전 검증 범위)
  └─ 격리 합성 시험 전용 Gate 확인
        ├─ 실제 G6 HOLD/미검증 사용자 입력 → BLOCK, DB 연결 0
        └─ 시험 하네스에서만 허용한 합성 시험 경로
              → 보호 Journal 읽기/무결성·중복·미해결 확인
              → 직렬화 잠금 및 승인 변경 보호 경계 확보
              → 잠금 안에서 Journal·승인 상태 최종 재확인
              → STARTED 영속 확인
              → 격리 DB 연결 및 실제 세션에서 DB identity/권한 재확인
              → DB 트랜잭션 한 개로 Batch 전량 검증/쓰기
                    ├─ COMMITTED + 기록 영속 확인
                    ├─ ROLLED_BACK + 기록 영속 확인
                    └─ COMMIT_UNKNOWN 또는 기록 실패 → 전역 HOLD/수동 대조
```

- G5 P1의 **운영 APPLY_REQUEST**에서는 **진짜 독립 G6 검증 통과 전** Writer DB 연결 함수 호출이 **0**이어야 한다. 격리 하네스의 합성 승인 신호는 이 규칙의 예외를 운영 경로로 열 수 없다.
- 확정 Batch 전체가 하나의 트랜잭션이다. DB `status` 기본값 `ACTIVE`에 묵시적으로 의존하지 않는다. 기존 `ACTIVE`뿐 아니라 `HIDDEN`도 중복 검사 대상이다.
- `STARTED`가 남거나 Commit 결과를 확인할 수 없으면 **동일 Batch뿐 아니라 신규 Batch APPLY도 HOLD**. `ROLLED_BACK`이라도 자동 재시도 허가가 아니다. 명시적 수동 조사·재승인 없이는 복구·재실행하지 않는다.
- 잠금은 단일 호스트에서 동일 Batch뿐 아니라 복수 시도 전반을 직렬화해야 한다. **잠금 취득 전에 읽은 Journal 결과만으로 실행을 결정하지 않고, 잠금 안에서 다시 검증한다.** DB Named Lock을 사용한다면 연결 수명·해제·풀 반환을 격리 시험한다. 파일 잠금/저널은 저장물 손상·교체·동시 시작에도 FAIL CLOSED여야 한다.
- 승인 변경/철회가 Writer 실행과 경쟁할 때의 **공유 조정 경계가 검증되지 않으면 운영 APPLY HOLD**. 단지 Commit 직전 파일을 한 번 더 읽는 방식만으로 경쟁 해결을 주장하지 않는다.

## 5. 최소 Journal 결정 (형식 미동결, 동작 동결)

- 보호된 영속 보관 위치: Git 작업 트리·임시 폴더·stdout 외부. 구체 OS/볼륨/권한은 격리 환경 확인 후 선택한다. 기존 승인 문서 폴더와 동일 저장소일 필요는 없지만 **쓰기 권한은 분리**한다.
- 필수 식별: `profile_id`, `batch_id`, 불변 Batch digest, 정책 버전, 승인/시험 구분, 대상 DB 식별, 실행 시도 식별자와 상태, 수동 조사 연결 정보. 실제 비밀번호·토큰·기사 원문·민감 경로 저장 금지.
- 필수 상태: `STARTED`, `COMMITTED`, `ROLLED_BACK`, `COMMIT_UNKNOWN`; `STARTED`는 DB 쓰기/Commit 전에 영속화해야 한다. 일부 기록 손실은 HOLD.
- Journal이 비어 보이거나 소실·손상·읽기 불가·이전 미해결 작업을 발견하면 **자동 초기화·자동 복구 금지**. 신뢰된 최초 구성과 재시작 복구 동작은 별도 시험으로 증명한다.
- 구체 파일 직렬화, 원자 생성·flush/fsync, 백업 방식, 경합 잠금 구현 등은 기술 선택을 비교한 뒤 **격리 통합 시험에 포함**한다. 입증되지 않은 구현을 영속 Journal PASS로 선언하지 않는다.

## 6. 최소 필수 검증 묶음 (6개, 중복 테스트 추가 금지)

| ID | 격리 시나리오 | 합격 조건 |
|---|---|---|
| W1-01 | 승인 누락/HOLD/문구형 PASS, 합성 Gate의 운영 경로 유입 | 실제 DB connector 호출 0, DML 0, `BLOCKED` |
| W1-02 | 대상 DB·실제 DB 사용자·계정 권한/환경 바인딩 오류 | 운영 DB 접속 불가, 격리 시험 대상만 인정, 불일치 시 쓰기 0 |
| W1-03 | 합성 적격 Batch 2건 정상 처리 / 둘째 항목 오류 주입 | 정상 전체 Commit; 오류 시 Batch 전체 Rollback, 부분 공개 0 |
| W1-04 | 같은 Batch 반복·두 프로세스 경합, Journal 미해결/손상 | 중복 쓰기 0, 자동 재시도 0, 전체 HOLD |
| W1-05 | Commit 직후 종료·응답 유실·사후 Journal 기록 실패 | `COMMIT_UNKNOWN`/미해결로 보수적 처리, 자동 재게시 0, 수동 DB 대조 필요 |
| W1-06 | Commit 전 승인 철회 / Commit 후 `HIDDEN` 및 GET·캐시 확인 | 선행 철회 시 Batch Rollback, 완료 후 별도 공개중단 동작 실증 전 운영 HOLD |

**구현 단계 구분:** W1-01·02는 연결 차단·격리성 검증으로 먼저 진행 가능. W1-03~06을 실증하기 전 전체 Writer/Journal 완료라고 보고하지 않는다. 모든 테스트는 합성 데이터를 사용하고, 명시적으로 별도 승인한 격리 DB·Journal 위치에 한정한다.

## 7. 이번에 확정하지 않는 것

- 실제 G6 승인 수기 원본에 대한 독립 신원·권한 인증 완성, G4 실자료 8~12건 승인 여부, 실데이터 실제 게시.
- 운영 DB/AWS/배포·서비스 계정 GRANT·`dev` 병합·API/Expo UI 변경.
- 승인 UI, 전자서명·공개키, 다중 호스트, 자동 스케줄러·재시도·복구, 새로운 DB 감사 테이블, 범용 Publisher 제품화.
- **운영 PASS 전환**: G0/G4/G5/G6 증거, Writer GRANT/Transaction/Journal/철회 실증, 배포 B-3/L-2, 게시 후 비노출·캐시 검증, 실제 DB/범위 승인까지 모두 별도 필요.

## 8. 변경 범위 및 구현 인계

- **본 E1-W1 격리 계약 한정 동결.** E0·AL-02·E1-W0 기존 파일 및 테스트를 수정하지 않는다.
- 코드 구현은 다음 작업으로 분리하고, 처음에는 W1-01·02를 위한 격리 접속 차단/DB target guard를 우선 검토한다. **이번 문서 확정에서는 DB·Writer·Journal 실행이나 GitHub 이외 외부 시스템 변경을 하지 않는다.**
- 실제 테스트 DB URL/계정, 보관 디렉터리의 물리 경로 및 ACL, MariaDB 현재 상태, GRANT는 **미확인**이다. 임의 값이나 가짜 승인 증거를 실운영 설정으로 채우지 않는다.
- 유지보수 관점: `ApprovalEvidenceReader`(향후 운영 별도), `IsolationGuard`(시험 격리용), `BatchValidator`, `Journal`, `TransactionWriter`의 **책임은 분리**하되 구현 클래스명·모듈 경로는 고정하지 않는다. 테스트 후 자연스러운 모듈 경계를 선택한다.

## 9. 근거 및 판정

- 운영 Gate v0.3 `POLICY_CONFIRMED` 및 G5 P1 HOLD 최소 실행 계약 v0.1 — DB 연결 전 G6 불명확 차단.
- P4 Final Review Addendum v0.2 `DRAFT` — 독립 Writer, 보호 Journal, Batch 원자성, 철회 경합·Commit Unknown.
- Phase 4B-2 FROZEN v1.0 — 로컬 증거 등록의 권한 및 `publish_authorization=NONE`.
- B-Lite 전시 일회성 설계 REVIEW v0.1 및 Pre-Implementation Final Review v0.2 — CLI 전시 예외, 운영 Gate 미검증.
- `backend/docs/b_lite_e1_al02_hold_contract.md` 및 `backend/docs/b_lite_e1_preconnect_review.md` — Windows E0 + AL-02 + W0 검증과 비게시 경계.

**최종 판정:** **GO — 격리 Writer·Journal의 이 문서에 한정된 구현 계약 확정. HOLD — 실제 G5/G6 PASS, 서비스 DB 연결·운영 APPLY, 게시 및 전시 공개 허가.**
