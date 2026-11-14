from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.profile_image_cleanup_job import ProfileImageCleanupJob
from app.models.user_profile import UserProfile


class ImageCleanupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, key, now, due) -> None:
        self.db.add(
            ProfileImageCleanupJob(
                file_key=key, created_at=now, next_attempt_at=due, attempt_count=0
            )
        )
        self.db.flush()

    def lock_key(self, key) -> ProfileImageCleanupJob | None:
        return self.db.scalar(
            select(ProfileImageCleanupJob)
            .where(ProfileImageCleanupJob.file_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def next_job(self, now) -> ProfileImageCleanupJob | None:
        return self.db.scalar(
            select(ProfileImageCleanupJob)
            .where(ProfileImageCleanupJob.next_attempt_at <= now)
            .order_by(
                ProfileImageCleanupJob.next_attempt_at, ProfileImageCleanupJob.job_id
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def metrics(self, now) -> dict[str, int]:
        count, oldest = self.db.execute(
            select(
                func.count(ProfileImageCleanupJob.job_id),
                func.min(ProfileImageCleanupJob.created_at),
            )
        ).one()
        return {
            "pending_count": int(count),
            "oldest_pending_seconds": max(0, int((now - oldest).total_seconds()))
            if oldest
            else 0,
        }

    def referenced(self, key) -> bool:
        return (
            self.db.scalar(
                select(UserProfile.profile_id)
                .where(UserProfile.profile_image_url == key)
                .limit(1)
            )
            is not None
        )
