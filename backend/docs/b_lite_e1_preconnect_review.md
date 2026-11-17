# B-Lite E1-W0 — E0·AL-02 진입 경계 최소 검토

> **2026-11-17 / 격리·HOLD 전용 / G5·G6 HOLD / 운영 Writer 미구현 / NOT FOR APPLY**

## 결정 및 범위

- 기존 A-Lite 최소 검증 v0.2에서 `AL-03`은 **E0 Windows 검증 증거 보존**이다. E0는 이미 Windows에서 19 PASS 및 CLI/`.bat` 확인 완료. 새 `AL-03` 개발 단위를 만들지 않는다.
- 다음 최소 작업을 `E1-W0`로 구분한다. `b_lite_e1_preconnect_entry.py`가 E0 매니페스트 검증을 먼저 호출하고 AL-02 승인 문서 검사를 연결한다. **두 결과 모두 게시 허가가 아니며 최종 결과는 항상 `BLOCKED`**이다.
- G6 미인증·HOLD의 사유를 유지하고, 미래에 하위 검사기의 결과가 예상치 못하게 승인으로 바뀌어도 차단한다.
- FastAPI, 운영 DB Session/Engine, Writer, Journal, G6 승인 원본, DB 권한, 실제 게시 API·스키마·Migration은 변경하지 않는다. 이 모듈은 **실제 Writer의 DB 연결 함수에 연결되어 있지 않다**.

## Windows 실행 (backend)

```powershell
python -m pytest tests/core/test_b_lite_e1_preconnect_entry.py -q
python -m pytest tests/core/test_b_lite_exhibition_once.py tests/core/test_b_lite_e1_hold_boundary.py tests/core/test_b_lite_e1_preconnect_entry.py -q

# 입력은 E0 형식의 JSON. 승인 문서·SHA-256은 미인증 선언이므로
# 일치하더라도 BLOCKED / 종료 코드 1이 정상이다.
python -m scripts.b_lite_e1_preconnect_entry --input "C:\path\to\review-manifest.json"
$LASTEXITCODE
```

## 최소 수용 기준

| 검사 | 합격 조건 |
|---|---|
| E0 위조 G6 PASS·잘못된 매니페스트 | `BLOCKED`, E1로 승격 없음 |
| 승인 파일 누락·HOLD·임의 PASS·해시 불일치 | `BLOCKED` |
| 하위 검사기의 예기치 않은 승인 결과 | `BLOCKED` |
| DB 관련 모듈 접근 및 게시 실행 옵션 | DB 모듈 임포트 없음, `--apply` 거부 |

테스트의 출력상 DB 연결·쓰기 `0`은 **이 비연결 코드 경계에 한정**된다. 실제 Writer의 `SessionLocal` 호출 0회, 운영 GRANT, Journal·중복·단일 Transaction 검증, 실제 G5/G6 운영 승인을 입증하지 않는다.

**GO:** E1-W0 격리 차단 연결 검증. **HOLD:** Writer APPLY / 운영 게시. 이후 별도 Writer 구현 시에는 G5 P1의 **실제 접속 함수 호출 전 차단 시험**이 필수이다. FROZEN 계약 변경 없음.
