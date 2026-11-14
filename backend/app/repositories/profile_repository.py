from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_profile import UserProfile


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find(self, user_id: int, *, lock: bool = False) -> UserProfile | None:
        query = select(UserProfile).where(UserProfile.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query.execution_options(populate_existing=True))

    def find_key(self, key: str) -> UserProfile | None:
        return self.db.scalar(
            select(UserProfile).where(UserProfile.nickname_key == key)
        )

    def add(self, value: UserProfile) -> None:
        self.db.add(value)
        self.db.flush()
