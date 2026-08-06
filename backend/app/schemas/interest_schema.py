from pydantic import BaseModel, Field, StrictInt, field_validator


class InterestCreateRequest(BaseModel):
    """사용자의 최초 관심사 저장 요청 Schema."""

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


class InterestCreateData(BaseModel):
    """관심사 최초 저장 성공 응답의 실제 데이터."""

    selected_category_ids: list[int]
    selected_count: int
