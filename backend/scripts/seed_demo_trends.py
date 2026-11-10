"""전체 트렌드 목록 검증용 Demo Seed 명시 실행 진입점."""

import logging
import sys
from contextlib import contextmanager


class _SafeDatabaseLog(logging.LoggerAdapter):
    """CLI 전용 Engine/Pool의 로그 수준을 보존하고 원시 내용을 제거한다."""

    def __init__(self, logger):
        super().__init__(logger, {})
        self.failed = False

    def log(self, level, msg, *args, **kwargs):
        if level >= logging.ERROR:
            self.failed = True
        # 원시 msg/args 및 exc_info/stack_info를 로깅 시스템에 넘기지 않는다.
        self.logger.log(level, "Demo Seed DB event (details withheld).")


@contextmanager
def _safe_database_logs(engine):
    """공유 Logger 설정 대신 해당 객체의 로거만 Session 정리까지 감싼다."""
    targets = (engine, engine.pool)
    originals = tuple(target.logger for target in targets)
    adapters = tuple(_SafeDatabaseLog(logger) for logger in originals)
    try:
        for target, adapter in zip(targets, adapters, strict=True):
            target.logger = adapter
        yield adapters
    finally:
        for target, logger in zip(targets, originals, strict=True):
            target.logger = logger


def main() -> int:
    """설정/import/Engine 초기화부터 비밀정보 없는 CLI 오류 경계를 적용한다."""
    try:
        from app.core.config import get_settings
        from app.db.seeds.demo_trends import seed_demo_trends

        settings = get_settings()

        from app.db.session import SessionLocal, engine

        with _safe_database_logs(engine) as database_logs:
            with SessionLocal() as db_session:
                seed_demo_trends(
                    db_session,
                    app_env=settings.app_env,
                    allowed_host=settings.demo_seed_allowed_host,
                    allowed_port=settings.demo_seed_allowed_port,
                    allowed_database=settings.demo_seed_allowed_database,
                    allowed_current_user=settings.demo_seed_allowed_current_user,
                )
            # Pool이 정리 오류를 기록한 뒤 내부 처리해도 성공으로 보고하지 않는다.
            if any(logger.failed for logger in database_logs):
                raise RuntimeError("Demo Seed DB cleanup failed")
    except Exception:
        print(
            "Demo Trend Seed 실패: 설정 또는 승인된 DB 대상을 확인하세요.",
            file=sys.stderr,
        )
        return 1

    print("Demo Trend Seed 생성 및 검증이 완료되었습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
