# B-Lite 전시 — E1 AL-02 HOLD 전용 차단 계약 검토 v0.1

> **상태: 격리 부정 경로 프로토타입 검증 / NOT AN APPROVAL / NOT FOR APPLY / G5·G6 HOLD**
>
> 검토일: 2026-11-17 (KST) · 전시 A-Lite 승인 증거의 **연결 전 거부 경계**에 한정. E1 전체 동결·운영 게시 완료 판정이 아니다.

## 1. 승인 신뢰 방식과 변경 경계

- **A안**: Git 작업 트리 외부에 접근 통제된 승인 원본을 보관하고 실행 전 사람이 대조한다. 전자서명·공개키·키 관리 시스템은 Post-MVP 검토 대상으로 이관하되 **독립 G6 승인 증거 검증 의무는 유지**한다.
- 운영 책임자·G6 최종 승인권자는 본인. 팀원 1명의 G4/Batch 승인 권한은 명시적인 위임 범위·기간·권한 근거를 별도로 확보해야 효력이 있으며, **G6 최종 승인은 별도 위임 전까지 미위임**이다.
- G6 운영 프로필 승인, G4 개별 콘텐츠 승인, Batch 실행 승인은 다른 사건이다. E0의 `REVIEW_ONLY`나 문서 `PASS` 문자열을 운영 게시 허가로 승격하지 않는다.
- 전시 한정 **수동 CLI-only 인터페이스 예외**를 적용하되, P4 Addendum v0.2는 여전히 DRAFT다. 독립 Writer, 보호된 영속 Journal, DB 최소 GRANT, 단일 Batch Transaction, 중복·동시 실행·Commit 불명확·철회 경쟁 차단은 그대로 필요하다.
- Phase 4A/4B-1/4B-2 FROZEN은 변경하지 않는다. 4B-2 등록 결과의 `publish_authorization=NONE`과 E1의 운영 승인 증거는 별개다.

## 2. AL-01 관찰 결과와 한계

- 사용자 Windows 실측: 승인 문서 파일 SHA-256 계산 성공, 파일 ACE는 `IsInherited=True`. 앞서 보호 부모 폴더의 ACE가 `IsInherited=False`였다는 사실과 양립한다.
- 본인 계정, 관리자 그룹, SYSTEM은 `FullControl`, CodexSandboxUsers는 `ReadAndExecute` 권한으로 관찰됨. 이것은 ACL 표시에 관한 사실이며 승인자의 독립 인증·Writer 권한 분리·악의적 변조 불가의 증명이 아니다.
- **`AL-01 = OBSERVED_PARTIAL`**: 파일 ACL·지문 산출 확인. 독립된 기준 지문 보관과 확인, 실제 위임·철회, Writer의 수정 불가·권한 실증은 미완료다.
- 실제 승인 원문, 비공개 경로, SID, 파일 지문은 GitHub에 넣지 않는다. SHA-256 일치는 파일 바이트 대조이지 승인자 인증이 아니다.

## 3. AL-02 HOLD 전용 실행 계약

- 구현: `backend/scripts/b_lite_e1_hold_boundary.py` · 테스트: `backend/tests/core/test_b_lite_e1_hold_boundary.py`.
- CLI: `python -m scripts.b_lite_e1_hold_boundary --approval-file <경로> --comparison-sha256 <64자리 SHA-256>`.
- 승인 파일·비교 해시 누락, 해시 형식 오류·불일치, 문서 내 `HOLD`, 위조 `PASS` 등 **모든 정상 CLI 실행 결과는 `BLOCKED`, 종료 코드 1**이다. 미지원 인수는 종료 코드 2.
- 문서 바이트와 비교 해시가 일치하더라도 **`G6_INDEPENDENT_AUTH_NOT_VERIFIED`**를 반환한다. 전달된 경로와 해시는 **신뢰된 승인 근거가 아니라 호출자 제공 입력**이다.
- 결과 `authorized_to_publish=false`, `g6_approval=HOLD`, `database_connections=0`, `database_writes=0`. **출력된 0은 E1 프로토타입의 비연결 동작 설명이지 실제 Writer 접속/DB 감사 증거가 아니다.**
- DB·SQLAlchemy·네트워크·게시 SQL·`--apply` 옵션이 없다. `test_only_writer_entry_probe()`는 connector 함수를 **의도적으로 무시하는 테스트용 주입 지점**으로, 실제 Writer가 아니다.
- 문서의 승인자 신원·권한·유효기간·독립 승인 인덱스·철회·대상 DB는 검증하지 않는다. 운영 승인을 이 모듈의 출력으로 주장하지 않는다.

## 4. 검증 기록

| 항목 | 증거 범위 | 판정 |
|---|---|---|
| E0 Windows 테스트 | 사용자 실행 로그 | **19 PASS** |
| AL-02 Windows 테스트 | 사용자 실행 로그 | **12 PASS**, pytest/anyio 경고 1건 |
| E0+AL-02 Windows 통합 | 사용자 실행 로그 | **31 PASS**, 동일 계열 경고 1건 |
| AL-02 원본 코드 별도 격리 검증 | 작성 환경 Python/pytest | **12 PASS** |
| 실제 Writer `connect()` 호출 검증 | Writer 미연결 | **NOT_TESTED** |
| 실제 DB DML, 최소 GRANT, 보호 Journal, 단일 Commit | 미구현·미실행 | **NOT_TESTED** |
| 실제 G4/G5/G6 운영 승인 | 독립 증거 미검증 | **HOLD** |

**AL-02 완료의 의미:** 격리된 거부 전용 로직과 부정 테스트 통과. Writer의 실제 연결 전 차단 완료나 게시 준비 완료를 의미하지 않는다.

## 5. 다음 통합 최소 조건

1. 실제 Writer를 별도 격리 구현할 때, G6 HOLD·승인 누락·임의 PASS·철회·해시 불일치에서 **실제 DB 연결 함수 호출 0회, 게시 DML 0건**을 별도로 시험해야 한다. 현재 테스트용 connector 감시를 근거로 대체하지 않는다.
2. 격리 DB에서 전용 계정 권한, Batch 단일 Commit/Rollback, 미해결·중복 Journal, Commit 불명확, 승인 철회 경쟁을 검증하기 전 APPLY를 활성화하지 않는다.
3. G5/G6 Gate, B-3/L-2 운영 배포 근거, 실제 승인자·권한 원본 확인 전 **운영 APPLY는 HOLD**한다.
4. 기존 E0·G5 P1·Phase 4 FROZEN·P4 DRAFT는 이 작업에서 수정하지 않는다.

### Windows PowerShell (backend 디렉터리)

```powershell
python -m pytest tests/core/test_b_lite_e1_hold_boundary.py -q
python -m pytest tests/core/test_b_lite_exhibition_once.py tests/core/test_b_lite_e1_hold_boundary.py -q
git status -sb
```

## 6. 근거

- `Trend_Leader_B_Lite_E1_A_Lite_Minimum_Check_v0.2_20261117.md` (사용자 제공 AL-01~03 검토안)
- `Google_Trends_RSS_운영_Gate_통과기준_검증증거_v0.3_POLICY_CONFIRMED.md`
- `Trend_Leader_MVP_A_G5_P1_최소실행계약_확정_HOLD_차단시험_v0.1.md`
- `Trend_Leader_P4_Final_Review_Addendum_v0.2_A1_Aligned_DRAFT_20261108.md`
- `Trend_Leader_실데이터_출처_확인_기록_검토_등록_Phase4B2_Design_FROZEN_v1.0_20261110.md`

**GO:** AL-02 시험 코드 및 계약 문서 반영. **HOLD:** 실제 Writer APPLY와 G5/G6 운영 게시.
