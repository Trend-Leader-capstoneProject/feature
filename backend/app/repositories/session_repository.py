from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.auth_refresh_token import AuthRefreshToken
from app.models.auth_session import AuthSession
from app.models.user import User


class SessionRepository:
    """잠금은 User → Session → Refresh 순서. commit은 Service가 소유한다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find(self, session_id: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession)
            .where(AuthSession.session_id == session_id)
            .execution_options(populate_existing=True)
        )

    def find_refresh(self, token_hash: str) -> AuthRefreshToken | None:
        return self.db.scalar(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
        )

    def lock_user(self, user_id: int) -> User | None:
        return self.db.scalar(
            select(User)
            .where(User.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_session(self, session_id: str) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession)
            .where(AuthSession.session_id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_refresh(self, token_hash: str) -> AuthRefreshToken | None:
        return self.db.scalar(
            select(AuthRefreshToken)
            .where(AuthRefreshToken.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add(self, value: AuthSession | AuthRefreshToken) -> None:
        self.db.add(value)
        self.db.flush()

    def revoke_others(self, user_id: int, current_sid: str, now) -> None:
        self.db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.session_id != current_sid,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    def delete_expired(self, now, limit: int = 100) -> int:
        ids = list(
            self.db.scalars(
                select(AuthSession.session_id)
                .where(AuthSession.expires_at <= now)
                .order_by(AuthSession.expires_at)
                .limit(limit)
                .with_for_update()
            )
        )
        if ids:
            self.db.execute(delete(AuthSession).where(AuthSession.session_id.in_(ids)))
        return len(ids)
