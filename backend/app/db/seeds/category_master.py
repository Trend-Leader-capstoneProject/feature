from sqlalchemy.orm import Session


class CategorySeedConflictError(RuntimeError):
    """기존 Category가 Seed 정의와 충돌하거나 식별이 모호할 때 발생한다."""


def seed_category_master(db_session: Session) -> None:
    """Category Master Seed를 생성하고 기존 데이터와의 일치를 검증한다."""

    raise NotImplementedError(
        "Category Master Seed 로직은 아직 구현되지 않았습니다."
    )
