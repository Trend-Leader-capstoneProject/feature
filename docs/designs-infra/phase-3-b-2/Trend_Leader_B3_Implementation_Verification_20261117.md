# Phase 3-B-2 B-3 구현 및 검증 기록

기준: `origin/dev` `30ddab265f2dfdc47aec8e3d6cfb0220d5ba8df3` (시작 시 fetch 확인).
범위: **오프라인 승인 Manifest 의미 검증 및 B-2 Evidence 대조 최소 구현**.
운영 APPLY, 승인 발급, 계정 Provisioning, 배포 및 운영 정책 동결은 포함하지 않는다.

## 구현 경계

- `backend/scripts/migration_approval.py`: `validate_manifest(bytes, now=...)`,
  `compare_approval(manifest_bytes, evidence_bytes, context=..., now=...)` 제공.
- 입력은 분리된 JSON 바이트이며 환경변수·Secret·DB를 읽지 않는다. 실제 체크아웃의
  Alembic Revision 메타데이터만 읽고 `env.py`나 Migration 함수를 실행하지 않는다.
- `ValidationResult.matches`는 해당 함수의 검증/대조 일치만 의미한다.
  `apply_enabled`는 항상 `False`. 운영자 인증·승인 발급·승인 사용 처리가 아니다.
- 기존 Guard 및 B-2 코드는 변경하지 않았다. 기본 `deny`, 정확한 `preflight`,
  `apply`의 `MODE_NOT_ENABLED`와 기존 종료 코드가 유지된다. B-3 CLI를 추가하지 않았다.
- Revision 원본, API, 개발/테스트 Compose, AWS, G5/G6 Writer 변경 없음.

## 구현용 형식과 대조 규칙

M-A1 §5의 15개 필수 의미 필드와 정수 `schema_version: 1`을 사용한다.
정확한 키 집합, 중복 키(중첩 포함), 비표준 JSON 상수, UTF-8, 자료형, 빈 값,
UTC ISO 시각을 검사한다. 정수 Port와 `sha256:` + 소문자 64자리 이미지 Digest를 사용한다.
이 표현 방식은 **구현·테스트용이며 운영 파일 형식 최종 동결을 선언하지 않는다**.
추가 필드는 조용히 무시하지 않고 거부한다.

- `approved_at <= now < expires_at`, `observed_at_utc <= approved_at`를 요구한다.
  Evidence 최대 수명이나 승인 최대 유효기간은 임의로 정하지 않았다.
- `target_revision`과 비어 있지 않은 `expected_from_revision`은 실제 계보의 ID만 허용한다.
  가변 별칭·범위·상대 Revision·미식별 ID·역방향 변경은 거부한다. 현재 실제 계보는
  `2f29fa23597c → 7e9d740c5df1 → a4d7c9e21f3b → b7f2c81d9e04`이다.
- 환경/프로젝트와 설정 Host/Port/DB명, 관찰 DB명, 정확한 `CURRENT_USER()`의 `user@host`,
  설정 사용자명, 이전 Revision, Evidence ID, 복구 증거 ID를 대조한다.
- B-2 JSON v1 검증을 재사용하고 관찰 상태·Reason·Revision·가시성 검사 간 모순을 거부한다.
  `OBSERVED`는 승인으로 바꾸지 않으며 `NOT_VERIFIED`를 `VERIFIED`로 수정하지 않는다.
- 이전 Revision이 없는 경우 구현용 표현은 **키가 존재하는 명시적 `null`**이다.
  `UNVERSIONED_EMPTY_CANDIDATE`만으로 통과하지 않는다. 독립적인 검증된 빈 DB/Bootstrap
  확인이 필요하다. 버전이 있는 DB는 독립적인 백업·복원 확인이 필요하다.

## 신뢰 경계와 Fail Closed

`ComparisonContext`는 외부에서 독립적으로 확인한 검토 사실을 전달하는 내부 인터페이스다.
입력 JSON에서 복사하거나, 방금 제출한 파일을 해시한 값만으로 신뢰를 만들면 안 된다.
테스트의 `context_for`는 합성 Fixture일 뿐 운영 승인·검증 어댑터가 아니다.

- 독립 검토 당시 Manifest와 Evidence의 정확한 바이트 SHA-256 pin이 없거나 다르면 거부한다.
  동일 ID의 내용 변경도 거부한다. 해시는 전자서명이나 위변조 방지 저장소가 아니다.
- 독립적으로 검증한 실행 이미지 Digest가 없거나 다르면 `IMAGE_NOT_VERIFIED`이다.
  Manifest의 Digest 주장이나 B-2의 `OBSERVED`/`NOT_VERIFIED`로 검증 사실을 추론하지 않는다.
- `RecoveryConfirmation`은 별도 검토한 증거 ID/종류와 Manifest 바이트 해시를 연결한다.
  다른 대상/Revision/승인에 대한 확인을 재사용할 수 없다. 증거 실체 검증·발급은 하지 않는다.
  B-2 Evidence 자신을 복구 증거로 참조할 수 없다.
- 사용 승인 ID 조회 결과가 없거나 형식이 불명확하면 `AUDIT_UNAVAILABLE`, 이미 사용한
  ID이면 `APPROVAL_ALREADY_USED`이다. 읽기 스냅샷은 동시 실행의 원자적 ID 예약이 아니다.
  대조를 반복해도 승인 ID를 소비하지 않으며 APPLY 권한도 생기지 않는다.
- 결과에는 고정 Reason Code만 포함한다. 입력값·비밀번호·URL·JWT·환경변수·예외 원문을
  반환/출력/기록하지 않는다. Manifest나 승인 증거를 생성·기록하는 기능도 없다.

## 자동 검증 결과

2026-11-17 Windows, Python 3.14.0, pytest 9.1.1, SQLAlchemy 2.0.51,
Pydantic 2.13.4, Ruff 0.16.0. 기본 Python에는 pytest/Ruff가 없고 공유 `.venv` 실행기는
기존 Python 경로를 찾지 못했다. 현재 Python에서 공유 환경의 설치 패키지를
`PYTHONPATH`로 지정해 실행했다. 의존성 파일 변경이나 패키지 설치는 하지 않았다.

초기 B-3 수집은 미구현 모듈 ImportError였다(행동 Red 검증으로 집계하지 않음).
감사 ID 앞뒤 공백을 미사용 승인으로 오인하는 부정 시험은 **1 FAIL, 1 PASS**를 확인한 뒤
입력 불명확 시 차단하도록 수정했다. 최종 회귀 결과는 아래와 같다.

`backend/`에서 실행한 PowerShell 명령:

```powershell
$env:PYTHONPATH = (Resolve-Path ../../trend-leader/.venv/Lib/site-packages).Path
$b3TestTemp = Join-Path '.venv' ('b3-pytest-' + [guid]::NewGuid().ToString('N'))
# .venv 부모는 이 작업에서 생성한 테스트 임시 디렉터리이며 Git ignore 대상이다.
python -m pytest tests/core/test_migration_approval.py tests/core/test_migration_guard.py tests/core/test_migration_preflight.py tests/core/test_migration_environment.py tests/core/test_migration_evidence.py tests/core/test_migration_observation.py tests/core/test_migration_report.py tests/core/test_migration_integration.py tests/core/test_migration_db_config.py tests/core/test_migration_fixture_env.py -q -rs --tb=short --maxfail=3 --basetemp=$b3TestTemp
python -m ruff check .
```

- 최종 영향 범위: **426 PASS, 1 SKIP, 0 FAIL/ERROR** (B-3 123건 포함).
- 1 SKIP은 POSIX 소유자/권한 검사이며 Windows ACL 검증을 대신하지 않는다.
- Ruff Backend 전체: **PASS**.
- 앞선 회귀 실행 2회는 임시 경로 접근 거부/부모 디렉터리 누락 때문에 각각
  **2 FAIL, 251 PASS, 1 SKIP, 171 ERROR**였다. 해당 실행을 PASS로 집계하지 않았다.
  작업 전용 임시 경로의 부모를 만든 뒤 최종 실행이 통과했다.
- 정상/만료/필드 누락/대상·계정·Revision·증거 ID·내용 pin 불일치/이미지 미검증/
  중복·감사 불명/복구 증거 누락/빈 DB 후보 자동 승인 방지/Secret 비노출을 검사했다.
- 부수 효과 부정 시험에서 네트워크·Engine 생성·Alembic 변경 명령·서브프로세스·파일 쓰기
  호출이 없음을 검사했다. B-2 가짜 Connection 시험은 기존 읽기 SQL 허용 목록을 검증한다.
- L-2 기술 시험, 실DB 접속, 실제 Migration, 운영 계정/리소스 변경은 실행하지 않았다.
  Backend 전체 기능/DB 통합/프런트엔드 회귀 PASS를 주장하지 않는다.

## 완료 판정과 후속 차단 조건

**B-3 최소 오프라인 구현 및 자동 검증 완료. 운영 APPLY 미활성화.**
상위 M-A1/B-2 계약과 충돌하는 변경은 없다. 다음은 후속 승인/운영 통합 전까지 미확정이다.

1. Manifest 형식·키의 최종 동결, 보호 경로·읽기 전용 마운트·UID/GID/ACL·승인자 접근 통제.
2. 신뢰할 수 있는 내용 pin/이미지 실측/복구 증거 확인의 획득·보호·전달 방식과 운영자 발급 절차.
3. 독립 감사 저장 위치·내구성·APPLY 전 원자적 사용 기록·실패/결과 미상 처리 계약.
4. 운영 DB 서버/계정 신원·최소 권한·백업 및 복원 또는 검증된 빈 DB/Bootstrap 실증.
5. 기존 검증된 L-2와의 실제 Guard 통합, 동일 Connection 잠금 아래 적용 직전/직후 재검증,
   운영 Compose 및 공개 Gate. L-2 기술 검증 자체를 이번에 반복하거나 재판정하지 않았다.

위 조건 없이 `matches=True`를 운영 승인으로 사용하거나 Guard APPLY 차단을 해제하면 안 된다.
