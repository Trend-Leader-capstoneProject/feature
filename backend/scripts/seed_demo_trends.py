"""전체 트렌드 목록 검증용 Demo Seed 명시 실행 진입점."""

from app.core.config import get_settings
from app.db.seeds.demo_trends import seed_demo_trends
from app.db.session import SessionLocal


def main() -> None:
    """현재 환경을 확인하고 Demo Trend Seed를 실행한다."""

    settings = get_settings()

    with SessionLocal() as db_session:
        seed_demo_trends(
            db_session,
            app_env=settings.app_env,
        )

    print(
        "Demo Trend Seed 생성 및 검증이 완료되었습니다."
    )


if __name__ == "__main__":
    main()
