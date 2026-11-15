# Trend Leader — Backend Image Registry Handoff Gate v0.1

- 작성 기준: 2026-11-15 KST
- 상태: **DESIGN / EVIDENCE CHECK ONLY. NO BACKEND CODE WRITE, NO REGISTRY PUSH, NO LIGHTSAIL OPERATION.**
- Source: `Trend-Leader-capstoneProject/feature` `dev` HEAD `c83e86d2615e1f54d48ce8de52f0adc036594434`, 2026-11-15 재확인.
- 운영 Compose v0.3: Windows 정적 검사 **33/33 PASS** (사용자 제공 결과). `compose.prod.v0.3.yaml.DRAFT`, 배포 승인 아님.
- 보호: AWS Caddy HTTPS probe/3308 Demo DB/백업 유지, Runtime Secret A안, Migration M-A1/S-A/G-B/A-2/L-2, G5/G6 및 P4 Writer APPLY HOLD.

## 1. 현재 확보된 로컬 이미지 증거

| 항목 | 결과/출처 | 판정 |
|---|---|---|
| 검증 태그 | `trendleader-backend:local-preflight-c83e86d261` (Windows 사용자 실행) | Local only |
| Image ID | `sha256:54637821b93a527212949b35da4f47502a9f8851b4950a23a2287d85bb99a3ce` | 확인: 사용자 출력 |
| OS/arch | `linux/amd64` | PASS |
| Buildx | 성공 | PASS |
| pip check | No broken requirements found | PASS |
| FastAPI Import/OpenAPI | FastAPI 0.163.1, 핵심 4 operation | PASS |
| `pip freeze` | 77 packages, 직접 의존성 13개 모두 충족 | PASS (정적 버전 정합성) |
| Snapshot 파일 SHA256 | `06976087612630fe5a2397e0c0a518b990a112f87a3e86cade5a4ff1ba0eaecf` | 업로드된 `trendleader-backend-packages.txt` 기준 |
| Registry manifest Digest | 발급되지 않음 | HOLD |
| Runtime HTTP / MariaDB / 신규 Revision / 실기기 / 부하 | 미검증 | HOLD |
| 전체 Backend 1,222 테스트를 이 이미지로 재실행 | 미검증 | 별도 Gate |

### 패키지 일부

FastAPI `0.163.1`, Starlette `1.10.0`, Uvicorn `0.54.0`, Pydantic `2.14.3`, pydantic-settings `2.16.3`, SQLAlchemy `2.0.57`, PyMySQL `1.2.4`, Alembic `1.18.5`, Pillow `13.0.0`.

**중요:** `pip freeze`는 설치 결과 스냅샷이며 lockfile이 아니다. 프로젝트의 `requirements.txt`에 열린 버전 범위가 있으므로 새 빌드에서 버전이 변할 수 있다. 이 결과를 `requirements.txt`로 자동 치환하지 않는다.

## 2. 현재 Git provenance의 공백

- GitHub의 `dev` Dockerfile은 아직 `FROM python:3.12-slim`이다.
- 검증된 로컬 이미지는 사용자 작업 트리에서 `FROM python:3.12.16-slim-trixie@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177`로 바꾸고 `.dockerignore`에 `var/`를 추가하여 빌드한 후보이다.
- 따라서 `c83e86d261`는 **기반 SHA**일 뿐, 이 검증 이미지 전체를 대표하는 확정 릴리스 소스 SHA가 아니다.
- 빌드 당시 작업 디렉터리/worktree/수정 파일이 정확히 일치했는지, 이미지에 OCI revision label이 있는지는 아직 확정 근거가 없다. Docker Image ID와 Registry manifest Digest를 혼동하면 안 된다.
- **Registry push 전 Gate:** 국소 변경을 검토용 PR에 확정해 Git 커밋으로 연결한 뒤, 깨끗한 소스 트리에서 새로 빌드하고 같은 검증을 다시 수행한다. 이는 설계 권고이며 Git write 권한을 뜻하지 않는다.

## 3. 최소 읽기 전용 Windows PowerShell 현장 점검

**실행 위치:** `backend/Dockerfile`/`.dockerignore` 수정이 실제 존재하는 worktree. 서버가 아닌 Windows Docker Desktop. `Get-Location`와 branch 상태로 확인할 것.

```powershell
$tag = "trendleader-backend:local-preflight-c83e86d261"
$expectedId = "sha256:54637821b93a527212949b35da4f47502a9f8851b4950a23a2287d85bb99a3ce"

Get-Location
git status -sb
git rev-parse HEAD
git diff --check
git diff --name-only

$actualId = (docker image inspect --format '{{.Id}}' $tag).Trim()
if ($LASTEXITCODE -ne 0 -or $actualId -ne $expectedId) {
    throw "Local image ID differs from the reviewed candidate; STOP"
}
docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Id}}' $tag

Get-FileHash "$HOME\Downloads\trendleader-backend-packages.txt" -Algorithm SHA256
```

**보안:** 토큰, DB Secret, JWT Secret, `docker compose config` 해석값은 출력하거나 채팅에 붙여넣지 않는다. 이 점검은 `docker login/push/pull`, Compose up, AWS 접근, Migration을 수행하지 않는다.

## 4. 이미지 전달 선택지

| 선택지 | 이점 | 제약/리스크 |
|---|---|---|
| R: private GitHub Container Registry (GHCR), **우선 권고** | 소스 Repo와 패키지 연계, 버전/배포 Digest 기록, 기존 `${BACKEND_IMAGE_REF}` 계약 유지, 나중에 CI/CD 연동 용이 | 조직 패키지 생성/업로드 권한 및 private GHCR의 서버 읽기 권한 사전 검증 필요. 첫 이미지 게시 기본 private. |
| T: docker save + SSH/SCP + docker load | Registry 권한 불필요 | `.tar` SHA와 Docker Image ID는 Registry Digest가 아니다. 현재 Compose의 digest pin 계약을 변경하거나 예외 승인 필요. |

**GHCR 후보 식별자(확정되지 않은 이름)**: `ghcr.io/trend-leader-capstoneproject/trend-leader-backend`.
기본적으로 private 패키지인 상태에서 공개 여부를 별도로 결정. 원격 Lightsail에 저장될 read-only pull credential의 보관/회수 정책 선행. 사용자 승인 없이 PAT 생성·login·push·pull·package 생성 금지.

### Registry 게시 Gate (설계만)

1. 로컬 패치의 출처/Git PR 승인, 정확한 Git release SHA 확보.
2. 깨끗한 HEAD에서 linux/amd64 이미지 빌드, 소스 revision label 및 테스트 증거 기록.
3. 레지스트리 namespace/패키지 권한/비공개 유지 정책 합의.
4. 승인된 자격증명으로 **별도 실행 단계**에서 push 후 `docker buildx imagetools inspect`로 실제 registry manifest Digest 취득; Image ID와 혼동 금지.
5. 운영 Compose `BACKEND_IMAGE_REF`는 게시한 `repo@sha256:<manifest>`로 지정하는 후보지만, 운영 반입·실행은 DB/Secret/Volume/Migration/Caddy 전환 Gate가 모두 완료될 때까지 HOLD.

## 5. 참고(공식 문서)

- GHCR authentication/permissions/push: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- Docker digests and manifest references: https://docs.docker.com/dhi/explore/security-concepts/digests/
- Docker `imagetools inspect`: https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/
- pip freeze is not a lockfile: https://pip.pypa.io/en/stable/cli/pip_freeze/

**Gate 결과:** 로컬 패키지·Import **PASS**, 소스 provenance 및 GHCR 권한/게시 **HOLD**, 실제 운영 배포 **금지**.
