# Trend Leader — L-2 최종 기술 검증 보고서

> 검증일: 2026-11-17 (KST)  
> 환경: AWS Lightsail Ubuntu / 격리된 D-2 MariaDB 테스트 환경  
> **최종 판정: L-2 기술 검증 PASS**  
> 범위: 기술 검증 결과 및 감사 기록 보존. **운영 DB Alembic APPLY 완료 판정이 아님.**

## 1. 검증 목적

SQLAlchemy와 MariaDB의 `GET_LOCK()` 동작, 테스트 실행 전 격리·안전 조건, 실행 후 DB 및 테스트 컨테이너 상태, 감사 기록의 보존과 독립 백업을 확인한다.

## 2. 검증 결과

| 검증 항목 | 결과 |
|---|---|
| 시험 소스·컨테이너 이미지 무결성 | PASS |
| D-2 DB·네트워크 격리 | PASS |
| Launcher Precheck (실제 테스트 실행 전) | PASS |
| `GET_LOCK()` 통합 테스트 | **1/1 PASS** |
| 실패 / 오류 / Skip | **0 / 0 / 0** |
| 테스트 후 DB 컨테이너 | `running=true` |
| DB 호스트 포트 바인딩 | `{}` (미게시 확인) |
| Internal 네트워크 | `internal=true`, 연결 컨테이너 1개 |
| L-2 테스트 컨테이너 | 부재 확인 (정리 완료) |
| 감사 기록 내용 검증 | `L2_AUDIT_RECORD_VALID` |
| Windows 로컬 백업 및 해시 대조 | **2/2 SHA-256 일치** |

테스트는 같은 DB Connection에서 `GET_LOCK()` 획득 후 `COMMIT`을 실행해 잠금과 연결이 유지되는지 확인하고, 다른 연결의 경합(즉시 획득 실패), 명시적 해제, 다른 연결의 재획득·해제를 검증했다.

## 3. 실행 및 감사 증거

- **실행 ID:** `d2-l2-lock-f60c3f46421e462ab60a0ce43b1c24a2`
- **최종 실행 상태:** `D2_L2_FINAL_STATUS=PASS`
- **관찰 테스트 수:** 1 / failures 0 / errors 0 / skipped 0
- **감사 기록 원본:** `/home/ubuntu/trend-leader-d2-isolated-test/l2-lock-runs/d2-l2-lock-f60c3f46421e462ab60a0ce43b1c24a2/`
- **Windows 로컬 백업:** `$HOME/Documents/TrendLeader-L2-Backup/d2-l2-lock-f60c3f46421e462ab60a0ce43b1c24a2/`

| 감사 파일 | 크기 | 원본 SHA-256 (= Windows 백업본) |
|---|---:|---|
| `started.json` | 225 bytes | `1c2bf9434195ad0bb75a53e5c1d57ba853eb66cde29cea9536a336339e4d1733` |
| `result.json` | 302 bytes | `02bb29e68ddc433b8e071b57042236521afbd6bdbb03ad2ba0f379921df752ed` |

두 파일 모두 Lightsail 원본의 소유자 UID 1000, 파일 권한 `0600`으로 확인했다. 백업 후 Windows에서 `BACKUP_HASH_OK`를 각 파일에 대해 확인했다. 서버 원본 및 Windows 백업본은 삭제하지 않고 보존한다. Windows 백업은 원본과 다른 장치에 복사한 증적이며, 추가적인 장기 보관·오프사이트 보존까지 검증한 것은 아니다.

## 4. 소스 기준과 범위 제한

- **테스트 실행 소스 커밋:** `1aa516a09a9e1810d19066047cc159f0022fa7fc`
- **L-2 설계 기준 커밋:** `b6831cf5d855fa5b3b02adaf8a350f83ded86487`
- 참고: [L-2 실행 준비 기록](L2_SQLAlchemy_Lock_Test_Readiness.md) — **실행 전 시점 문서**이며, 해당 문서의 '미실행' 표기는 본 보고서의 사후 검증 결과를 대체하지 않는다.

본 결과는 격리된 D-2 환경의 **L-2 단일 통합 테스트**에 한정된다. 전체 Phase 3-B-2 완료, 운영 환경의 모든 동시성 조건 검증, 실제 운영 DB Alembic Migration APPLY, 배포 공개 Gate 승인을 의미하지 않는다. 이 항목들은 각각 별도 승인 및 실행 증거로 판단한다.

## 5. 최종 결론

L-2 `GET_LOCK()` 통합 테스트 **1/1 PASS**, 실행 후 DB·네트워크 격리 유지 및 테스트 컨테이너 정리 확인, 감사 기록 2개 파일의 Windows 독립 백업과 SHA-256 대조 **2/2 PASS**.

**L-2 기술 검증 완료(PASS). 동일 기술 검증의 반복 실행 없이 종료하고, 잔여 운영 조건은 별도 Gate에서 관리한다.**
