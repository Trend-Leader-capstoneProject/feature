from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    StrictInt,
    field_validator,
)

InterestUpdateConflictReason = Literal[
    "INTERESTS_NOT_INITIALIZED",
]


class InterestSelectionRequest(BaseModel):
    """사용자 관심사 선택 집합의 공통 요청 Schema."""

    category_ids: list[StrictInt] = Field(
        min_length=1,
        description="사용자가 선택한 활성 대분류 카테고리 ID 목록",
    )

    @field_validator("category_ids")
    @classmethod
    def validate_unique_category_ids(
        cls,
        category_ids: list[int],
    ) -> list[int]:
        """배열 내부에 중복된 카테고리 ID가 있는지 검증한다."""

        if len(category_ids) != len(set(category_ids)):
            raise ValueError(
                "category_ids에 중복된 카테고리 ID를 포함할 수 없습니다.",
            )

        return category_ids


class InterestCreateRequest(
    InterestSelectionRequest,
):
    """사용자의 최초 관심사 저장 요청 Schema."""


class InterestUpdateRequest(
    InterestSelectionRequest,
):
    """사용자의 기존 관심사 전체 교체 요청 Schema."""


class InterestSelectionData(BaseModel):
    """사용자의 최종 관심사 선택 상태를 나타내는 공통 데이터."""

    selected_category_ids: list[int]
    selected_count: int


class InterestCreateData(
    InterestSelectionData,
):
    """관심사 최초 저장 성공 응답의 실제 데이터."""


class InterestReadData(
    InterestSelectionData,
):
    """현재 관심사 조회 성공 응답의 실제 데이터."""


class InterestUpdateData(
    InterestSelectionData,
):
    """관심사 수정 성공 응답의 실제 데이터."""


class InterestUpdateConflictData(BaseModel):
    """관심사 수정 상태 충돌의 machine-readable 오류 데이터."""

    reason: InterestUpdateConflictReason
