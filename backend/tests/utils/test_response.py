import pytest
from pydantic import ValidationError

from app.schemas.common_schema import CommonResponse
from app.utils.response import success_response


def test_success_response_creates_common_response() -> None:
    """성공 응답 Factory가 CommonResponse를 생성하는지 확인한다."""

    response = success_response(
        message="테스트 성공",
        data={
            "value": 1,
        },
        status_code=200,
    )

    assert isinstance(response, CommonResponse)
    assert response.success is True
    assert response.status_code == 200
    assert response.message == "테스트 성공"
    assert response.data == {
        "value": 1,
    }


def test_success_response_serializes_status_code_with_alias() -> None:
    """직렬화 결과가 statusCode를 사용하는지 확인한다."""

    response = success_response(
        message="테스트 성공",
        data={
            "value": 1,
        },
        status_code=200,
    )

    assert response.model_dump(by_alias=True) == {
        "success": True,
        "statusCode": 200,
        "message": "테스트 성공",
        "data": {
            "value": 1,
        },
    }


def test_common_response_rejects_false_success() -> None:
    """성공 응답에 success=False를 입력할 수 없는지 확인한다."""

    with pytest.raises(ValidationError):
        CommonResponse[None].model_validate(
            {
                "success": False,
                "status_code": 500,
                "message": "잘못된 성공 응답",
                "data": None,
            }
        )
