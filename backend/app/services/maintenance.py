"""API 생명주기에 귀속된 정리 루프. 테스트는 기본 비활성/격리 의존성 주입."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

from starlette.concurrency import run_in_threadpool

from app.core.auth_time import utc_now
from app.repositories.session_repository import SessionRepository
from app.services.image_cleanup_service import ImageCleanupService
from app.services.image_service import ImageStore

logger = logging.getLogger(__name__)


def cleanup_auth(session_factory) -> None:
    while True:
        with session_factory() as db:
            count = SessionRepository(db).delete_expired(utc_now())
            db.commit()
        if count < 100:
            break


async def _loop(session_factory, root, stop):
    images = ImageCleanupService(session_factory, ImageStore(root))
    next_auth = utc_now()  # 시작 시 만료 기록 catch-up.
    while not stop.is_set():
        try:
            deleted = await run_in_threadpool(images.run)
            metrics = await run_in_threadpool(images.metrics)
            logger.info(
                "profile_image_cleanup_cycle",
                extra={"deleted_count": deleted, **metrics},
            )
            now = utc_now()
            if now >= next_auth:
                await run_in_threadpool(cleanup_auth, session_factory)
                # 다음 한국시간 03:00 = UTC 18:00.
                next_auth = now.replace(hour=18, minute=0, second=0)
                if next_auth <= now:
                    next_auth += timedelta(days=1)
                logger.info("auth_cleanup_cycle_completed")
        except Exception:
            logger.warning(
                "account_maintenance_retry", extra={"reason": "MAINTENANCE_FAILED"}
            )
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except TimeoutError:
            pass


def maintenance_lifespan(settings, session_factory=None):
    @asynccontextmanager
    async def lifespan(app):
        if not settings.maintenance_enabled:
            yield
            return
        if session_factory is None:
            from app.db.session import SessionLocal

            factory = SessionLocal
        else:
            factory = session_factory
        stop = asyncio.Event()
        task = asyncio.create_task(_loop(factory, settings.profile_image_root, stop))
        try:
            yield
        finally:
            stop.set()
            await task

    return lifespan
