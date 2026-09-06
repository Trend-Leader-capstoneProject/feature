import pytest
from pydantic import ValidationError

from app.schemas.interest_schema import (
    InterestCreateRequest,
    InterestSelectionRequest,
    InterestUpdateRequest,
)


@pytest.mark.parametrize(
    "request_schema",
    [
        InterestCreateRequest,
        InterestUpdateRequest,
    ],
)
def test_interest_request_accepts_valid_category_ids(
    request_schema: type[InterestSelectionRequest],
) -> None:
    """POST와 PUT 요청은 정상 관심사 ID 목록을 동일하게 허용한다."""

    request = request_schema.model_validate(
        {
            "category_ids": [
                1,
                4,
                6,
            ],
        }
    )

    assert request.category_ids == [
        1,
        4,
        6,
    ]


@pytest.mark.parametrize(
    "request_schema",
    [
        InterestCreateRequest,
        InterestUpdateRequest,
    ],
)
def test_interest_request_rejects_empty_category_ids(
    request_schema: type[InterestSelectionRequest],
) -> None:
    """POST와 PUT 요청은 빈 관심사 목록을 동일하게 거부한다."""

    with pytest.raises(ValidationError):
        request_schema.model_validate(
            {
                "category_ids": [],
            }
        )


@pytest.mark.parametrize(
    "request_schema",
    [
        InterestCreateRequest,
        InterestUpdateRequest,
    ],
)
def test_interest_request_rejects_duplicate_category_ids(
    request_schema: type[InterestSelectionRequest],
) -> None:
    """POST와 PUT 요청은 중복 관심사 ID를 동일하게 거부한다."""

    with pytest.raises(ValidationError):
        request_schema.model_validate(
            {
                "category_ids": [
                    1,
                    1,
                ],
            }
        )


@pytest.mark.parametrize(
    "request_schema",
    [
        InterestCreateRequest,
        InterestUpdateRequest,
    ],
)
def test_interest_request_rejects_non_integer_category_ids(
    request_schema: type[InterestSelectionRequest],
) -> None:
    """POST와 PUT 요청은 정수가 아닌 관심사 ID를 동일하게 거부한다."""

    with pytest.raises(ValidationError):
        request_schema.model_validate(
            {
                "category_ids": [
                    "1",
                ],
            }
        )


@pytest.mark.parametrize(
    "request_schema",
    [
        InterestCreateRequest,
        InterestUpdateRequest,
    ],
)
def test_interest_request_rejects_missing_category_ids(
    request_schema: type[InterestSelectionRequest],
) -> None:
    """POST와 PUT 요청은 category_ids 누락을 동일하게 거부한다."""

    with pytest.raises(ValidationError):
        request_schema.model_validate({})
