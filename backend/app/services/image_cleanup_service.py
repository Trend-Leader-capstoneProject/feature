import logging
from datetime import timedelta

from app.core.auth_time import utc_now
from app.repositories.image_cleanup_repository import ImageCleanupRepository

logger = logging.getLogger(__name__)


class ImageCleanupService:
    def __init__(self, session_factory, store) -> None:
        self.session_factory = session_factory
        self.store = store

    def metrics(self) -> dict[str, int]:
        with self.session_factory() as db:
            return ImageCleanupRepository(db).metrics(utc_now())

    def run(self, *, key: str | None = None, limit: int = 100) -> int:
        completed = 0
        for _ in range(1 if key else limit):
            with self.session_factory() as db:
                repo = ImageCleanupRepository(db)
                job = repo.lock_key(key) if key else repo.next_job(utc_now())
                if job is None:
                    break
                # 불변 키와 쓰기 전 intent 잠금이 새 참조와 삭제의 경합을 막는다.
                if repo.referenced(job.file_key):
                    job.next_attempt_at = utc_now() + timedelta(hours=1)
                    job.last_error_code = "STILL_REFERENCED"
                    db.commit()
                    continue
                try:
                    self.store.delete(job.file_key)
                except (OSError, ValueError):
                    job.attempt_count += 1
                    minutes = min(60, 2 ** min(job.attempt_count - 1, 6))
                    job.next_attempt_at = utc_now() + timedelta(minutes=minutes)
                    job.last_error_code = "FILE_DELETE_FAILED"
                    logger.warning(
                        "profile_image_cleanup_retry",
                        extra={
                            "attempt_count": job.attempt_count,
                            "reason": job.last_error_code,
                        },
                    )
                else:
                    db.delete(job)
                    completed += 1
                db.commit()
        return completed
