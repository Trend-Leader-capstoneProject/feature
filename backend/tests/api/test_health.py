from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


class ScalarResult:
    """테스트용 SQL 실행 결과."""

    def __init__(
        self,
        value: int,
    ) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class ReadySession:
    """SELECT 1 결과를 반환하는 테스트용 Session."""

    def execute(
        self,
        _statement: object,
    ) -> ScalarResult:
        return ScalarResult(1)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Health API 테스트용 Client를 생성한다."""

    application = create_app()

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def test_root_returns_common_response(
    client: TestClient,
) -> None:
    """기본 진입점이 공통 성공 응답을 반환한다."""

    response = client.get("/")

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200
    assert "status_code" not in body
    assert body["data"]["status"] == "running"


def test_health_check_returns_common_response(
    client: TestClient,
) -> None:
    """Liveness API가 공통 성공 응답을 반환한다."""

    response = client.get(
        "/api/health",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["statusCode"] == 200
    assert body["data"]["status"] == "healthy"
    assert "checkedAt" in body["data"]


def test_readiness_check_returns_ready_response() -> None:
    """DB 확인 성공 시 Readiness API가 200을 반환한다."""

    application = create_app()

    def override_get_db() -> Iterator[ReadySession]:
        yield ReadySession()

    application.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(application) as client:
            response = client.get(
                "/api/health/ready",
            )
    finally:
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["statusCode"] == 200
    assert response.json()["data"]["status"] == "ready"
    assert response.json()["data"]["database"] == "available"
