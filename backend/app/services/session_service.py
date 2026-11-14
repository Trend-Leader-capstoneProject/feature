"""로그인별 세션·토큰 발급·교체·폐기의 Transaction 경계."""

import hashlib
import math
import re
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID, uuid4

from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth_time import as_utc, utc_now
from app.core.exceptions import ApplicationException, BadRequestException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.auth_refresh_token import AuthRefreshToken
from app.models.auth_session import AuthSession
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.schemas.account_schema import PasswordChangeRequest
from app.schemas.auth_schema import TokenPair


def reject(reason: str):
    from app.core.exceptions import UnauthorizedException

    return UnauthorizedException(data={"reason": reason})


@dataclass(frozen=True)
class AuthContext:
    user: User
    session_id: str
    user_id: int = field(init=False)

    def __post_init__(self) -> None:
        # 읽기 Transaction 종료 후 ORM 객체가 expire돼도 인증된 식별자는 유지한다.
        object.__setattr__(self, "user_id", self.user.user_id)


class SessionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SessionRepository(db)

    def issue(self, user: User) -> TokenPair:
        now = utc_now()
        session = AuthSession(
            session_id=str(uuid4()),
            user_id=user.user_id,
            created_at=now,
            expires_at=now + timedelta(days=30),
            current_generation=1,
        )
        self.repository.add(session)
        return self._issue_pair(session, now)

    def _issue_pair(self, session: AuthSession, now) -> TokenPair:
        refresh = secrets.token_urlsafe(32)
        self.repository.add(
            AuthRefreshToken(
                session_id=session.session_id,
                token_hash=hashlib.sha256(refresh.encode("ascii")).hexdigest(),
                generation=session.current_generation,
                issued_at=now,
            )
        )
        access_expiry = min(now + timedelta(minutes=15), session.expires_at)
        return TokenPair(
            access_token=create_access_token(
                session.user_id, session.session_id, as_utc(access_expiry)
            ),
            refresh_token=refresh,
            access_expires_at=as_utc(access_expiry),
            refresh_expires_at=as_utc(session.expires_at),
        )

    def authenticate(self, token: str) -> AuthContext:
        try:
            payload = decode_access_token(token, verify_exp=False)
            subject, sid, expiry = (
                payload.get("sub"),
                payload.get("sid"),
                payload["exp"],
            )
            if (
                not isinstance(subject, str)
                or not re.fullmatch(r"[0-9]+", subject)
                or not 0 < int(subject) <= 2**63 - 1
                or not isinstance(sid, str)
                or str(UUID(sid)) != sid
                or isinstance(expiry, bool)
                or not isinstance(expiry, (int, float))
                or not math.isfinite(expiry)
            ):
                raise ValueError("Invalid claims")
        except (JWTError, ValueError, TypeError, KeyError) as exc:
            raise reject("ACCESS_TOKEN_INVALID") from exc

        # 잠금 없는 조회도 ORM identity map의 이전 객체를 신뢰하지 않는다.
        from sqlalchemy import select

        user = self.db.scalar(
            select(User)
            .where(User.user_id == int(subject))
            .execution_options(populate_existing=True)
        )
        if user is None or user.status != UserStatus.ACTIVE:
            raise reject("ACCOUNT_UNAVAILABLE")
        session = self.repository.find(sid)
        self._check_session(session, user.user_id)
        if expiry <= as_utc(utc_now()).timestamp():
            raise reject("ACCESS_TOKEN_EXPIRED")
        return AuthContext(user=user, session_id=sid)

    def finish_read_phase(self) -> None:
        """쓰기 전 읽기 snapshot을 닫고 이후 잠금에서 최신 상태를 다시 검증한다."""
        if self.db.new or self.db.dirty or self.db.deleted:
            raise RuntimeError("Write verification requires a clean read transaction")
        self.db.rollback()

    def lock_context(self, context: AuthContext) -> tuple[User, AuthSession]:
        self.finish_read_phase()
        user = self.repository.lock_user(context.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise reject("ACCOUNT_UNAVAILABLE")
        session = self.repository.lock_session(context.session_id)
        self._check_session(session, user.user_id)
        return user, session

    @staticmethod
    def _check_session(session: AuthSession | None, user_id: int) -> None:
        if session is None or session.user_id != user_id or session.revoked_at:
            raise reject("SESSION_REVOKED")
        if session.expires_at <= utc_now():
            raise reject("SESSION_EXPIRED")

    def refresh(self, raw: str) -> TokenPair:
        commit_started = False
        try:
            if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
                raise reject("REFRESH_TOKEN_INVALID")
            token_hash = hashlib.sha256(raw.encode("ascii")).hexdigest()
            record = self.repository.find_refresh(token_hash)
            if record is None:
                raise reject("REFRESH_TOKEN_INVALID")
            initial_session = self.repository.find(record.session_id)
            if initial_session is None:
                raise reject("SESSION_REVOKED")
            user_id, session_id = initial_session.user_id, initial_session.session_id
            self.finish_read_phase()
            user = self.repository.lock_user(user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise reject("ACCOUNT_UNAVAILABLE")
            session = self.repository.lock_session(session_id)
            self._check_session(session, user.user_id)
            record = self.repository.lock_refresh(token_hash)
            if record is None:
                raise reject("REFRESH_TOKEN_INVALID")
            now = utc_now()
            if (
                record.used_at is not None
                or record.generation != session.current_generation
            ):
                session.revoked_at = now
                commit_started = True
                self.db.commit()  # 의존성의 예외 rollback 전에 종료를 확정한다.
                raise reject("REFRESH_TOKEN_REUSED")
            record.used_at = now
            session.current_generation += 1
            pair = self._issue_pair(session, now)
            commit_started = True
            self.db.commit()
            return pair
        except SQLAlchemyError as exc:
            if not commit_started:
                # commit을 시도하지 않았고 rollback이 확인된 경우에만 재사용 가능.
                self.db.rollback()
                error = ApplicationException(data={"reason": "REFRESH_NOT_APPLIED"})
                error.status_code = 503
                raise error from exc
            raise

    def logout(self, raw: str) -> None:
        token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        record = self.repository.find_refresh(token_hash)
        if record is None:
            return
        initial = self.repository.find(record.session_id)
        if initial is None:
            return
        user_id, session_id = initial.user_id, initial.session_id
        self.finish_read_phase()
        user = self.repository.lock_user(user_id)
        if user is None:
            return
        session = self.repository.lock_session(session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = utc_now()
        self.db.commit()

    def change_password(
        self, context: AuthContext, request: PasswordChangeRequest
    ) -> None:
        user, _ = self.lock_context(context)
        self.verify_current_password(user, request.current_password.get_secret_value())
        new_password = request.new_password.get_secret_value()
        if verify_password(new_password, user.password_hash):
            raise BadRequestException(data={"reason": "PASSWORD_UNCHANGED"})
        user.password_hash = hash_password(new_password)
        self.repository.revoke_others(user.user_id, context.session_id, utc_now())
        self.db.commit()

    @staticmethod
    def verify_current_password(user: User, password: str) -> None:
        if user.password_hash is None or not verify_password(
            password, user.password_hash
        ):
            raise BadRequestException(data={"reason": "CURRENT_PASSWORD_MISMATCH"})
