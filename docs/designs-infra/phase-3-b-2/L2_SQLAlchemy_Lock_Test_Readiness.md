# L-2 Connection Lock: D-2 내부 네트워크 실행 준비

기준 dev: `b6831cf5d855fa5b3b02adaf8a350f83ded86487` (PR #117 병합).
2026-11-17 KST. **정적 준비 / 이미지 빌드·실제 테스트 미실행**.
M-A1 / S-A / G-B / A-2 / L-2, B-2, Guard deny 정책을 변경하지 않는다.

## 실행 경로와 변경 이유

사용자가 제공한 실제 D-2 환경은 AWS Lightsail Ubuntu이며 Compose 경로는
`/home/ubuntu/trend-leader-d2-isolated-test/compose.d2-isolated-test.yaml.DRAFT`,
프로젝트는 `trendleader-d2-isolated-test`, DB 서비스는 `db`이다.
사용자가 이전 Lightsail 구축 과정에서 확인한 식별자는 아래와 같다.
현재 상태 재조회 결과가 아니며 launcher가 실행 직전 같은 값인지 재검증한다.

| 고정 식별자 | 값 |
|---|---|
| DB 컨테이너 | `trendleader-d2-isolated-test-db-1` |
| Docker 네트워크 | `trendleader-d2-isolated-test_d2_net` |
| Compose 네트워크 키 | `d2_net` |
| DB 볼륨 | `trendleader-d2-isolated-test_d2_db_data` |
| DB / 계정 / 접속점 | `trend_leader_d2_test` / `d2_migrator` / `db:3306` |

호스트에서 localhost로 접속하려면 DB 포트 게시가 필요하므로 그 방식을 사용하지 않는다.
**D-2 호스트에서 별도 테스트 이미지를 기존 internal 네트워크에 한 번 연결**하고
컨테이너 안에서 `db:3306`으로 접속한다. Compose/DB 컨테이너는 수정·재기동하지 않는다.
`docker run`은 전용 이미지의 자체 pytest EntryPoint를 사용하며 Guard 이미지를 사용하지 않는다.
MariaDB ports 게시, host network, Docker socket 마운트, root Secret 전달은 없다.

## 이미지 및 의존성 확인 범위

저장소 backend/Dockerfile은 requirements.txt만 설치한다. SQLAlchemy/PyMySQL은 선언되어 있으나
pytest는 requirements-dev.txt에만 있어 Runtime 이미지에 pytest가 있다고 가정할 수 없다.
로컬 B-2 Compose harness 소스는 pytest 및 SQLAlchemy/PyMySQL을 설치하도록 정의되어 있으며,
중지된 로컬 harness의 패키지 메타데이터에서 pytest 9.2.0, SQLAlchemy 2.0.57,
PyMySQL 1.2.4를 확인했다. **로컬 B-2는 Lightsail D-2와 별개이며 이 결과는 D-2 증거가 아니다.**
D-2의 기존 테스트 이미지명/설치 상태는 제공되지 않았으므로 확인되지 않았다.

이를 위해 `tools/l2_lock/Dockerfile`을 별도 제공한다. 위 3개 버전을 고정 설치하고 pip check를
수행하도록 정의했다. 실제 이미지 빌드 및 설치 성공은 아직 확인하지 않았다.
Dockerfile 전용 .dockerignore는 시험 소스/설정만 허용해 Secret/.env가 빌드 컨텍스트로 전송되지 않도록 한다.
테스트도 DB 접속 전에 설치 버전 일치를 검사한다. 이 버전 고정은 시험 harness에만 적용된다.
앱 requirements, Runtime 이미지 및 기존 harness는 변경하지 않는다.
베이스는 저장소에서 사용 중인 digest 고정 Python 3.12.16 linux/amd64이다.
실제 D-2 호스트가 amd64인지 먼저 확인한다. 다른 아키텍처는 그대로 실행하지 않는다.
빌드 시 네트워크가 필요하므로 DB internal 네트워크 안에서 런타임 pip install을 하지 않는다.

## 실행 전에 확정해야 할 독립 승인값

기존 D-2 운영 기록 및 선택 필드 inspect를 대조해 승인 JSON을 준비한다.
아래 값은 시험/접속 결과에서 자동 승인하거나 로컬 B-2 값으로 대체하지 않는다.
비밀번호/접속 URL을 JSON에 넣지 않는다. 모든 값은 문자열이다.

| JSON 키 | 값/확인 대상 |
|---|---|
| ALLOWED_HOST | `db` |
| ALLOWED_PORT | `3306` (컨테이너 내부 포트) |
| ALLOWED_DB_IP | 승인한 D-2 DB 컨테이너의 내부 IP |
| ALLOWED_CURRENT_USER | 실제 승인 기록의 정확한 `d2_migrator@…` |
| ALLOWED_SERVER_HOSTNAME | 승인 기록의 @@hostname |
| ALLOWED_SERVER_ID | 승인 기록의 @@server_id, 10진수 표기 |
| ALLOWED_VOLUME | `trendleader-d2-isolated-test_d2_db_data` |
| ALLOWED_NETWORK | `trendleader-d2-isolated-test_d2_net` |
| ALLOWED_NETWORK_KEY | `d2_net` |
| ALLOWED_DB_CONTAINER | `trendleader-d2-isolated-test-db-1` |
| ALLOWED_DB_IMAGE_DIGEST | 승인된 D-2 MariaDB 이미지의 `sha256:…` digest |

고정 식별자는 위 사용자 확인값을 사용한다. 내부 IP, CURRENT_USER의 host 부분, 서버 hostname/id,
DB 이미지 digest와 테스트 이미지 ID는 실제 실행 직전 독립 증거와 실측을 대조할 동적 값이다.
실제 Compose를 검토하고 위 값을 확정해야 실행할 수 있다. Compose config/env 전체 출력은 금지한다.
서버 hostname/id도 전역적으로 고유한 인증 증거는 아니므로 프로젝트/네트워크/volume 검증을 함께 한다.
D-2 DB는 `trend_leader_d2_test`, 계정은 `d2_migrator`로 코드에 고정되어 있다.
Secret은 정확히 `/home/ubuntu/trend-leader-d2-isolated-test/secrets/d2_migration_password`만 허용한다.
`--secret-file` 생략 시 이 경로가 기본이며 다른 파일/운영 Secret 경로를 지정하면 거부한다.
정규화 전·후 경로 일치, 모든 부모의 symlink 부재, 일반 파일·hardlink 수 1,
파일/부모의 owner(root 또는 uid 1000) 및 group/other 쓰기 금지를 확인한다.
파일 또는 부모의 바꿔치기가 없도록 시험 중 관리 작업을 중지한다. 파일 내용의 출처까지
판별할 수는 없으므로 운영 Secret을 이 경로로 복사해 대체하지 않았음을 운영자가 확인한다.
기존 보호된 이 파일 하나만 read-only 마운트한다. 파일/부모 ACL과 uid 1000의 읽기 권한을
확인하며 이 스크립트는 chmod, 계정 생성, GRANT를 수행하지 않는다.

## 소스 출처 및 Lightsail 배치 전제

기준 Git SHA는 **기존 dev의 설계/구현 비교 기준**이다. 이 패치의 신규 시험 파일이 그 커밋에
포함되어 있다는 뜻이 아니다. 현재 시험 코드는 별도 검토한 패치에서 공급된다.
Lightsail에 소스가 배치되었는지는 확인되지 않았다. AWS 접속/전송/빌드는 별도 승인 후 수행한다.
승인한 전체 패치 또는 소스 묶음과 독립 SHA256 manifest를 Secret 없이 전달하고, 별도 작업 경로에
기준 dev checkout과 패치를 적용한다. D-2 Compose 디렉터리/기존 볼륨에는 소스를 덮어쓰지 않는다.
수신본의 manifest를 먼저 대조한다. 특히 launcher/Dockerfile/dockerignore도 검토한 전달본과 같아야 한다.
소스 묶음 전체 checksum은 전송 무결성 증거이고, 아래 SOURCE_SHA256은 이미지에 들어가는
`test_connection_lock.py`와 `pytest.ini`의 이름+NUL+원문 바이트를 순서대로 해시한 값이다.
빌드는 두 소스의 해시 및 BASE_REVISION을 검사하고 이미지 label에 기록한다.
launcher도 배치된 소스로 해시를 다시 계산해 이미지와 대조한다. 이 label/checksum은 서명/인증이 아니다.
이미지는 전용 Dockerfile에서 빌드하며 테스트 소스를 수정하면 재검토·새 해시·재빌드해야 한다.

## 준비 및 실행 명령 (지금 실행하지 말 것)

다음은 **별도 AWS 작업 승인 이후** D-2 Ubuntu에서 적용할 Bash 명령이다.
Windows PowerShell 명령이 아니다. 패치를 반영한 저장소 루트에서 실행한다.
승인 JSON 경로만 실제 보호 경로로 교체한다. Secret 경로는 고정값을 사용한다.
Docker 그룹 추가, chmod/chown, sudoers 수정은 하지 않는다. 기존 `sudo docker` 방식을 유지한다.
launcher는 **실제 UID와 effective UID가 모두 1000인 일반 ubuntu 사용자로** 호출한다.
입력/Secret/Docker 접근 전에 이를 검사하며 root 또는 다른 UID는 권한 변경 없이 거부한다.
기존 Secret 검증은 그대로 유지한다. 내부 Docker 호출만 `sudo -n /usr/bin/docker`를 사용한다.
먼저 `sudo -v`로 기존 권한 인증을 갱신한다. non-interactive sudo 권한이 만료되거나
Docker 바이너리 경로가 다르면 FAIL/UNKNOWN이며 권한 완화나 일반 docker로 fallback하지 않는다.
`sudo python3`로 launcher 전체를 root 실행하지 않는다.
최신 dev와 기준 SHA가 달라졌다면 먼저 재검토하고 launcher와 Dockerfile의 BASE_REVISION 검사도 함께 재검토한다.

```bash
sudo -v
revision=b6831cf5d855fa5b3b02adaf8a350f83ded86487
test "$(git rev-parse HEAD)" = "$revision" || exit 1
test_hash=$(sha256sum backend/tests/l2_lock/test_connection_lock.py | cut -d ' ' -f 1)
source_hash=$(python3 -c "import hashlib,pathlib; d=hashlib.sha256(); [d.update(n.encode()+b'\0'+pathlib.Path('backend/tests/l2_lock',n).read_bytes()) for n in ('test_connection_lock.py','pytest.ini')]; print(d.hexdigest())")
sudo /usr/bin/docker build --platform linux/amd64 -f tools/l2_lock/Dockerfile --build-arg BASE_REVISION="$revision" --build-arg SOURCE_SHA256="$source_hash" --build-arg TEST_SHA256="$test_hash" -t trendleader-l2-lock:prepared .
image_id=$(sudo /usr/bin/docker image inspect trendleader-l2-lock:prepared --format '{{.Id}}')
python3 tools/l2_lock/run_d2_lock.py --image-id "$image_id" --approval /approved/l2-identifiers.json --secret-file /home/ubuntu/trend-leader-d2-isolated-test/secrets/d2_migration_password
```

마지막 명령의 기본 동작은 **Docker inspect만 수행하는 precheck**이다. DB/테스트 컨테이너를
실행하지 않는다. 로컬 이미지 ID, 기준 dev revision 및 시험 소스 묶음 SHA256/테스트 SHA256, EntryPoint, user를 대조한다.
DB project/service/Compose 경로/이미지 digest/volume/포트 비공개/단일 네트워크,
네트워크 internal 속성/label/ID/등록 컨테이너를 검증한다.
D-2 네트워크에 DB 이외 컨테이너가 연결되어 있으면 중단한다. 관리자가 검토 없이 연결을 끊지 않는다.
검증 후 실제 실행을 별도 승인받은 경우에만 아래 명령을 사용한다.

```bash
python3 tools/l2_lock/run_d2_lock.py --image-id "$image_id" --approval /approved/l2-identifiers.json --secret-file /home/ubuntu/trend-leader-d2-isolated-test/secrets/d2_migration_password --run
```

launcher가 동일 검증을 다시 수행한 뒤 `sudo -n /usr/bin/docker run --name <고유-run-id> --pull=never`로 한 번 실행한다.
read-only rootfs, uid 1000, 모든 capability 제거, no-new-privileges, /tmp tmpfs를 사용한다.
Secret 하나는 read-only, 시험 출력용 임시 디렉터리 하나는 read-write로 마운트한다.
Docker socket 및 DB volume은 마운트하지 않는다.
L2_LOCK_RUN 및 전용 L2_LOCK_* 입력만 전달하고 기존 Runtime/Migration 환경을 상속하지 않는다.
기본 이미지 CMD는 다음과 같다. 별도의 수동 명령으로 안전 검증을 생략하지 않는다.

```text
python -m pytest -c /l2/pytest.ini /l2/test_connection_lock.py --confcutdir=/l2 -m integration -q --tb=no --show-capture=no -p no:cacheprovider --junitxml=/results/l2-report.xml
```

이미지에는 이 테스트 파일과 독립 pytest.ini만 복사한다. 기존 conftest/자동 Alembic fixture,
.env.test, 앱 설정을 로딩하지 않는다. 환경 플래그 미지정 시 Secret 읽기 전에 SKIP한다.
launcher 실행은 플래그를 명시적으로 설정한다. 테스트 실패·대상 불일치·정리 실패는 FAIL이다.
각 실행은 `D2_L2_RUN_ID`를 먼저 출력한다. inspect/rm 등 Docker 제어 명령은 각 15초,
테스트 프로세스 전체는 90초로 제한한다. timeout/중단/관찰 실패 시 해당 run-id의
테스트 컨테이너만 stop(time=5초, 제어 제한 15초) 시도하고 결과는 UNKNOWN(exit 2)이다.
stop 확인 실패도 출력한다. DB 컨테이너/volume/network는 stop/remove하지 않는다.
CLI timeout은 서버 세션 종료 증거가 아니므로 관리자는 run-id와 기존 승인 절차로 조사한다.
자동 재시도는 없다. 실패/UNKNOWN 컨테이너는 조사용으로 남기며 확인 후 그 컨테이너만 정리한다.
pytest exit 0만으로 PASS 처리하지 않는다. 컨테이너 종료 코드/정상 종료와 JUnit XML의
정확한 테스트명 1개, failures=0/errors=0/skipped=0과 아래 영속 기록 성공까지 모두 확인해야 PASS(exit 0)이다.
JUnit은 launcher가 만든 uid 1000 소유의 임시 결과 디렉터리를 /results에 마운트해 기록한다.
이 시험 출력용 bind만 read-write이며 기존 DB volume과 별개다. 컨테이너 종료 후 판독하고
launcher 종료 시 임시 디렉터리를 정리한다. 내용/예외는 출력하지 않는다.
Lightsail ubuntu의 uid가 1000인지 먼저 확인한다. 결과 파일은 일반 파일·hardlink 수·크기를 검사한다. PASS 컨테이너는 제거한다.
pytest exit 1은 FAIL(exit 1); 보고서 누락/skip/수집 실패/종료 관찰 불능은 UNKNOWN(exit 2)이다.
precheck의 성공(exit 0)은 테스트 PASS가 아니다. 고정 상태 메시지로 구별한다.
컨테이너 stdout/stderr는 그대로 노출하지 않는다.
`--showlocals`, `-s`, SQL echo, 환경 덤프 및 Secret/URL 출력은 금지한다.

## 실행별 영속 기록

고정 경로 `/home/ubuntu/trend-leader-d2-isolated-test/l2-lock-runs`를 사용한다.
기존 B-2 Evidence/승인 파일 경로와 별개이며 기존 파일을 이동·수정하지 않는다.
실행 전 관리자가 이 디렉터리가 별도 영속 디스크 경로이고 uid 1000 소유·0700이며
남은 공간이 충분한지 확인해야 한다. launcher는 루트를 자동 생성하거나 chmod/chown하지 않는다.
루트/부모 symlink, root/uid 1000 외 소유자, group/other 쓰기 권한을 거부한다.
이 루트는 컨테이너에 마운트하지 않는다. 기본 precheck도 기록 루트와 UID 전제조건을 검사한다.

실제 실행마다 UUID 기반 D2_L2_RUN_ID로 새 디렉터리를 배타적으로 생성한다.
이름이 이미 있거나 생성/기록 실패 시 컨테이너 실행 전에 거부한다. ID/부분 파일은 재사용하지 않는다.
`started.json`을 fsync하고 디렉터리도 동기화한 후에만 테스트를 시작한다.
이 파일은 초기 status=UNKNOWN이며 완료 기록이 없으면 결과 불명으로 처리한다.
테스트 후 별도 `result.json`을 배타적으로 생성하고 파일/디렉터리를 fsync한다.
두 파일 모두 0600이며 기존 파일을 덮어쓰지 않는다. 실패 파일을 지우고 재시도하지 않는다.

기록 필드는 schema_version, run_id, status(PASS/FAIL/UNKNOWN), started_at_utc,
finished_at_utc, expected_tests=1, observed_counts이다.
UTC 시각은 timezone을 포함한다. observed_counts는 tests/failures/errors/skipped의 숫자만 기록한다.
보고서가 없거나 신뢰할 수 없으면 null이며 0개로 추정하지 않는다.
DB 계정/host/주소/Secret 경로/환경값/XML/원시 예외/테스트 출력은 기록하지 않는다.
실패 및 timeout/중단 경로도 결과와 관찰 가능한 건수를 기록한다.
강제 프로세스 종료·전원 장애로 최종 기록이 없으면 started.json을 UNKNOWN으로 조사한다.

최종 기록이 완료된 뒤에만 `D2_L2_FINAL_STATUS=PASS|FAIL|UNKNOWN`을 출력한다.
시작 기록 실패는 테스트 미시작·exit 2, 최종 기록 실패는 결과 불명·exit 2이며 PASS를 출력하지 않는다.
파일이 존재한다는 사실만으로 기록 완료를 판정하지 않는다. 중단/기록 오류로 남은 부분 파일은
정상 완료 증거가 아니다. 운영자는 종료 상태와 기록 완료 여부를 함께 확인한다.
디스크 손상/관리자 변경에 대한 위변조 방지나 독립 감사 저장소를 보장하지 않는다.
네트워크/기록 실패 이후 자동 테스트 재실행은 없다. 기존 run-id를 조사한 뒤 별도 판단한다.

## 보존한 시나리오 및 잔여 위험

두 Connection의 DB/계정/서버 식별 및 서로 다른 CONNECTION_ID를 검증한다.
컨테이너 DNS `db`가 승인 IP로만 해석되는지 먼저 검사한다.
GET_LOCK(name, 0)=1 → 소유 ID 확인 → owner COMMIT → 같은 세션과 잠금 유지 →
다른 세션 획득 결과=0 → 명시적 RELEASE_LOCK=1 → 다른 세션 인계/해제 → close를 확인한다.
NULL 및 예외는 성공으로 간주하지 않는다. timeout은 획득 0초, 접속/읽기/쓰기 5초이다.
실패 시 SQL 재시도/신규 연결/KILL 없이 invalidate/close/dispose하고 종료 실패도 기록한다.
SQLAlchemy Pool private close hook의 버전 의존성과 네트워크 단절 후 정리 지연은 남아 있다.
inspect 후 실행 사이 Docker 변경/DNS 교체 가능성이 있어 D-2 관리 작업을 중지한 상태에서 실행한다.
재생성으로 IP/서버 식별값이 달라지면 자동 갱신하지 말고 새 승인값을 확인한다.
DDL 암묵 COMMIT, 강제 단절 주입, Alembic 통합, A-2/Guard apply는 검증 범위 밖이다.

이번 수정에서는 Docker 이미지 빌드, AWS 접속, MariaDB 접속, pytest 수집/실행을 하지 않았다.
위 로컬 B-2 의존성 확인은 이전 준비 단계의 증거다. 이번 리뷰 반영에서는 Docker를 호출하지 않았다.
오프라인 launcher 회귀는 `python -m unittest discover -s tools/l2_lock -p test_launcher_offline.py -v`로
15개 통과했다(사용자 로컬 실행 확인). subprocess는 전부 차단 또는 Mock 처리하여 Docker/DB/실제 Secret을 사용하지 않는다.
Ruff 및 AST 구문 검사를 함께 수행했다. 이는 D-2 통합 PASS를 의미하지 않는다.

근거: [L-2 확정안](Trend_Leader_Phase_3-B-2_M-A1_Design_Decision_v1.0_20261113.md).
