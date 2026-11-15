from datetime import timedelta

import pytest
from jose import jwt

from app.api.dependencies.auth_dependency import get_current_user
from app.core.auth_time import as_utc, utc_now
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.models.db_enums import UserStatus
from app.models.user import User
from tests.auth_helpers import SESSION_ID, session_service_for_user


def token(**changes):
    claims = {
        "sub": "10",
        "sid": SESSION_ID,
        "exp": as_utc(utc_now() + timedelta(minutes=15)),
    }
    claims.update(changes)
    return jwt.encode(
        claims, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm
    )


def user(status=UserStatus.ACTIVE):
    return User(user_id=10, name="private account name", status=status)


def test_verified_context_supplies_current_user():
    account = user()
    service = session_service_for_user(lambda _: account, 10)
    assert get_current_user(service.authenticate(token())) is account


@pytest.mark.parametrize(
    "changes",
    [
        {"sub": "not-a-number"},
        {"sub": "0"},
        {"sub": "-1"},
        {"sub": None},
        {"sid": None},
        {"sid": "not-a-session"},
        {"exp": None},
        {"exp": True},
    ],
)
def test_malformed_claims_do_not_reach_database(changes):
    service = session_service_for_user(lambda _: user(), 10)
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token(**changes))
    assert error.value.data["reason"] == "ACCESS_TOKEN_INVALID"
    service.db.scalar.assert_not_called()


def test_missing_exp_is_rejected_without_query():
    service = session_service_for_user(lambda _: user(), 10)
    raw = jwt.encode(
        {"sub": "10", "sid": SESSION_ID},
        get_settings().jwt_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(UnauthorizedException):
        service.authenticate(raw)
    service.db.scalar.assert_not_called()


@pytest.mark.parametrize(
    "account", [None, user(UserStatus.WITHDRAWN), user(UserStatus.SUSPENDED)]
)
def test_missing_or_inactive_account_is_rejected(account):
    service = session_service_for_user(lambda _: account, 10)
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token())
    assert error.value.data["reason"] == "ACCOUNT_UNAVAILABLE"


@pytest.mark.parametrize(
    "reason,modify",
    [
        ("SESSION_REVOKED", lambda record: setattr(record, "revoked_at", utc_now())),
        ("SESSION_EXPIRED", lambda record: setattr(record, "expires_at", utc_now())),
    ],
)
def test_session_is_checked_before_access_expiry(reason, modify):
    service = session_service_for_user(lambda _: user(), 10)
    modify(service.repository.find.return_value)
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token(exp=as_utc(utc_now() - timedelta(minutes=1))))
    assert error.value.data["reason"] == reason
