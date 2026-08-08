from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import (
    ConflictException,
    UnauthorizedException,
)
from app.main import create_app


class ValidationRequest(BaseModel):
    """422 예외 처리를 검증하기 위한 테스트 요청 Schema."""

    category_ids: list[int]


@pytest.fixture
def application() -> FastAPI:
    """공통 예외 처리 테스트용 애플리케이션을 생성한다."""

    app = create_app()

    # DEBUG 모드에서는 FastAPI가 디버그 응답을 우선할 수 있으므로
    # 공통 500 응답 검증 시에는 비활성화한다.
    app.debug = False

    @app.post("/_test/validation")
    def validation_route(
        _request: ValidationRequest,
    ) -> None:
        return None

    @app.get("/_test/conflict")
    def conflict_route() -> None:
        raise ConflictException(
            message="이미 관심사가 등록되어 있습니다.",
        )

    @app.get("/_test/unauthorized")
    def unauthorized_route() -> None:
        raise UnauthorizedException()

    @app.get("/_test/server-error")
    def server_error_route() -> None:
        raise RuntimeError(
            "내부 데이터베이스 정보",
        )

    return app


@pytest.fixture
def client(
    application: FastAPI,
) -> Iterator[TestClient]:
    """서버 예외를 HTTP 응답으로 확인하는 TestClient를 생성한다."""

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


def test_validation_error_returns_common_422_response(
    client: TestClient,
) -> None:
    """Request Body 검증 실패가 공통 422 응답으로 변환된다."""

    response = client.post(
        "/_test/validation",
        json={},
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["statusCode"] == 422
    assert body["message"] == (
        "요청 데이터가 올바르지 않습니다."
    )

    validation_error = body["data"]["errors"][0]

    assert validation_error["field"] == "body.category_ids"
    assert validation_error["type"] == "missing"


def test_application_exception_returns_common_response(
    client: TestClient,
) -> None:
    """사용자 정의 예외가 지정된 상태 코드와 메시지를 반환한다."""

    response = client.get(
        "/_test/conflict",
    )

    assert response.status_code == 409
    assert response.json() == {
        "success": False,
        "statusCode": 409,
        "message": "이미 관심사가 등록되어 있습니다.",
        "data": None,
    }


def test_unauthorized_exception_returns_bearer_header(
    client: TestClient,
) -> None:
    """인증 예외가 401 응답과 Bearer 인증 헤더를 반환한다."""

    response = client.get(
        "/_test/unauthorized",
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["message"] == "로그인이 필요합니다."


def test_unknown_endpoint_returns_common_404_response(
    client: TestClient,
) -> None:
    """존재하지 않는 Endpoint가 공통 404 응답을 반환한다."""

    response = client.get(
        "/api/not-existing-endpoint",
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "statusCode": 404,
        "message": "요청한 데이터를 찾을 수 없습니다.",
        "data": None,
    }


def test_unhandled_exception_does_not_expose_internal_message(
    client: TestClient,
) -> None:
    """예상하지 못한 오류가 내부 내용을 노출하지 않는다."""

    response = client.get(
        "/_test/server-error",
    )

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "statusCode": 500,
        "message": "서버 오류가 발생했습니다.",
        "data": None,
    }
    assert "내부 데이터베이스 정보" not in response.text