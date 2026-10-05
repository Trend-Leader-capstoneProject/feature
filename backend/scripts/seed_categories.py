"""Category Master Seed를 명시적으로 실행하는 진입점."""

from app.db.seeds.category_master import seed_category_master
from app.db.session import SessionLocal


def main() -> None:
    """Session을 열고 Category Master Seed를 실행한다."""
    with SessionLocal() as db_session:
        seed_category_master(db_session)

    print("Category Master Seed 생성 및 검증이 완료되었습니다.")


if __name__ == "__main__":
    main()
