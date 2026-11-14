"""실제 commit·별도 연결을 사용하는 계정/인증/파일 통합 검증."""

import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.core.auth_time import utc_now
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.auth_refresh_token import AuthRefreshToken
from app.models.auth_session import AuthSession
from app.models.profile_image_cleanup_job import ProfileImageCleanupJob
from app.models.search_log import SearchLog
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.image_cleanup_service import ImageCleanupService
from app.services.image_service import ImageStore
from app.services.session_service import SessionService

pytestmark = pytest.mark.integration
PASSWORD = "correct-password-123"
NEW_PASSWORD = "changed-password-456"


@dataclass
class Runtime:
    client: TestClient
    factory: object
    root: Path
    owned_login_ids: set[str] = field(default_factory=set)

    def signup(self, *, login_id=None, nickname=None, email=None):
        login_id = login_id or "acct_" + uuid4().hex[:20]
        nickname = nickname or "닉_" + uuid4().hex[:8]
        self.owned_login_ids.add(login_id)
        response = self.client.post(
            "/api/auth/signup",
            json={
                "login_id": login_id,
                "nickname": nickname,
                "name": "계정 비공개 이름",
                "email": email,
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
        )
        assert response.status_code == 201
        return response.json()["data"], login_id

    @staticmethod
    def header(data):
        return {"Authorization": "Bearer " + data["access_token"]}

    def login(self, login_id, password=PASSWORD):
        response = self.client.post(
            "/api/auth/login",
            json={
                "login_id": login_id,
                "password": password,
            },
        )
        assert response.status_code == 200
        return response.json()["data"]


@pytest.fixture
def account_runtime(test_engine, tmp_path, monkeypatch):
    url = test_engine.url
    assert url.database == "trend_leader_test"
    assert url.host in {"127.0.0.1", "localhost"} and url.port in {3307, 3308}
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    settings = get_settings()
    monkeypatch.setattr(settings, "profile_image_root", tmp_path.resolve())
    monkeypatch.setattr(settings, "maintenance_enabled", False)
    monkeypatch.setattr(settings, "debug", False)
    owned_files = set()
    original_new_key = ImageStore.new_key

    def new_key(extension):
        key = original_new_key(extension)
        owned_files.add(key)
        return key

    monkeypatch.setattr(ImageStore, "new_key", staticmethod(new_key))
    app = create_app()

    def isolated_db():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = isolated_db
    with TestClient(app, raise_server_exceptions=False) as client:
        runtime = Runtime(client, factory, tmp_path.resolve())
        try:
            yield runtime
        finally:
            app.dependency_overrides.clear()
            with factory() as db:
                if runtime.owned_login_ids:
                    db.execute(
                        delete(User).where(User.login_id.in_(runtime.owned_login_ids))
                    )
                if owned_files:
                    db.execute(
                        delete(ProfileImageCleanupJob).where(
                            ProfileImageCleanupJob.file_key.in_(owned_files)
                        )
                    )
                db.commit()


def png(size=(40, 20), mode="RGBA"):
    output = io.BytesIO()
    Image.new(mode, size, (10, 20, 30, 40) if mode == "RGBA" else (10, 20, 30)).save(
        output, format="PNG"
    )
    return output.getvalue()


def upload(runtime, data, raw=None):
    return runtime.client.put(
        "/api/users/me/profile-image",
        headers=runtime.header(data),
        files={"image": ("input.png", png() if raw is None else raw, "image/png")},
    )


def test_signup_profile_nickname_and_name_are_independent(account_runtime):
    rt = account_runtime
    nickname = "Trend" + uuid4().hex[:5]
    account, _ = rt.signup(nickname=nickname)
    header = rt.header(account)
    profile = rt.client.get("/api/users/me", headers=header)
    assert profile.status_code == 200
    assert profile.json()["data"]["nickname"] == nickname
    assert account["user"]["name"] == "계정 비공개 이름"
    duplicate = rt.client.get(
        "/api/auth/check-nickname", params={"nickname": nickname.lower()}
    )
    assert duplicate.json()["data"]["is_available"] is False
    own = rt.client.get(
        "/api/users/me/check-nickname",
        headers=header,
        params={"nickname": nickname.upper()},
    )
    assert own.json()["data"]["is_available"] is True
    result = rt.client.patch(
        "/api/users/me/nickname", headers=header, json={"nickname": nickname.upper()}
    )
    assert result.status_code == 200
    assert result.json()["data"]["nickname"] == nickname.upper()
    assert (
        rt.client.patch(
            "/api/users/me/nickname", headers=header, json={"nickname": "ㄱㄴ"}
        ).status_code
        == 422
    )
    with rt.factory() as db:
        profile = db.scalar(
            select(UserProfile).where(UserProfile.user_id == account["user"]["user_id"])
        )
        assert profile.nickname_key == nickname.lower()


def test_password_change_retains_current_pair_and_revokes_other_login(account_runtime):
    rt = account_runtime
    current, login_id = rt.signup()
    other = rt.login(login_id)
    sid = decode_access_token(current["access_token"])["sid"]
    with rt.factory() as db:
        before = db.get(AuthSession, sid).expires_at
    changed = rt.client.put(
        "/api/users/me/password",
        headers=rt.header(current),
        json={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password_confirm": NEW_PASSWORD,
        },
    )
    assert changed.status_code == 200 and changed.json()["data"] is None
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(current)).status_code
        == 200
    )
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(other)).status_code == 401
    )
    assert (
        rt.client.post(
            "/api/auth/refresh", json={"refresh_token": other["refresh_token"]}
        ).status_code
        == 401
    )
    with rt.factory() as db:
        session = db.get(AuthSession, sid)
        assert session.revoked_at is None and session.current_generation == 1
        assert session.expires_at == before
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthRefreshToken)
                .where(AuthRefreshToken.session_id == sid)
            )
            == 1
        )
    assert (
        rt.client.post(
            "/api/auth/login", json={"login_id": login_id, "password": PASSWORD}
        ).status_code
        == 401
    )
    rt.login(login_id, NEW_PASSWORD)
    assert (
        rt.client.post(
            "/api/auth/refresh", json={"refresh_token": current["refresh_token"]}
        ).status_code
        == 200
    )


def test_refresh_replay_revocation_is_committed_and_other_login_survives(
    account_runtime,
):
    rt = account_runtime
    first, login_id = rt.signup()
    other = rt.login(login_id)
    rotated = rt.client.post(
        "/api/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert rotated.status_code == 200
    pair = rotated.json()["data"]
    assert pair["refresh_expires_at"] == first["refresh_expires_at"]
    replay = rt.client.post(
        "/api/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401
    assert replay.json()["data"]["reason"] == "REFRESH_TOKEN_REUSED"
    sid = decode_access_token(first["access_token"])["sid"]
    with rt.factory() as db:
        assert db.get(AuthSession, sid).revoked_at is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthRefreshToken)
                .where(AuthRefreshToken.session_id == sid)
            )
            == 2
        )
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(pair)).status_code == 401
    )
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(other)).status_code == 200
    )


def test_concurrent_refresh_uses_distinct_connections_and_replay_ends_session(
    account_runtime,
):
    rt = account_runtime
    account, _ = rt.signup()
    barrier = Barrier(2)

    def rotate():
        with rt.factory() as db:
            barrier.wait(timeout=5)
            try:
                return ("ok", SessionService(db).refresh(account["refresh_token"]))
            except UnauthorizedException as exc:
                return ("error", exc.data["reason"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(rotate) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sum(kind == "ok" for kind, _ in results) == 1
    assert ("error", "REFRESH_TOKEN_REUSED") in results
    with rt.factory() as db:
        sid = decode_access_token(account["access_token"])["sid"]
        assert db.get(AuthSession, sid).revoked_at is not None


def test_server_logout_is_idempotent_and_only_ends_target_session(account_runtime):
    rt = account_runtime
    account, login_id = rt.signup()
    other = rt.login(login_id)
    for _ in range(2):
        result = rt.client.post(
            "/api/auth/logout", json={"refresh_token": account["refresh_token"]}
        )
        assert result.status_code == 200
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(account)).status_code
        == 401
    )
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(other)).status_code == 200
    )


def test_session_deadline_rejects_signed_access_and_refresh(account_runtime):
    rt = account_runtime
    account, _ = rt.signup()
    sid = decode_access_token(account["access_token"])["sid"]
    with rt.factory() as db:
        db.get(AuthSession, sid).expires_at = utc_now()
        db.commit()
    response = rt.client.get("/api/auth/session", headers=rt.header(account))
    assert (
        response.status_code == 401
        and response.json()["data"]["reason"] == "SESSION_EXPIRED"
    )
    response = rt.client.post(
        "/api/auth/refresh", json={"refresh_token": account["refresh_token"]}
    )
    assert (
        response.status_code == 401
        and response.json()["data"]["reason"] == "SESSION_EXPIRED"
    )


def test_photo_protection_replacement_reset_and_old_url_rejection(account_runtime):
    rt = account_runtime
    account, _ = rt.signup()
    other, _ = rt.signup()
    first = upload(rt, account)
    assert first.status_code == 200
    url = first.json()["data"]["profile_image_url"]
    assert rt.client.get(url).status_code == 401
    image = rt.client.get(url, headers=rt.header(other))
    assert image.status_code == 200
    assert image.headers["cache-control"] == "private, no-store"
    with Image.open(io.BytesIO(image.content)) as decoded:
        assert decoded.mode == "RGBA" and decoded.getpixel((0, 0))[3] == 40
    second = upload(rt, account)
    assert second.status_code == 200
    assert rt.client.get(url, headers=rt.header(account)).status_code == 404
    assert not (rt.root / url.rsplit("/", 1)[1]).exists()
    current_url = second.json()["data"]["profile_image_url"]
    reset = rt.client.delete("/api/users/me/profile-image", headers=rt.header(account))
    assert (
        reset.status_code == 200 and reset.json()["data"]["profile_image_url"] is None
    )
    assert rt.client.get(current_url, headers=rt.header(account)).status_code == 404


def test_upload_validates_actual_body_and_documented_field(account_runtime):
    rt = account_runtime
    account, _ = rt.signup()
    header = rt.header(account)
    assert upload(rt, account, b"broken image").status_code == 400
    assert upload(rt, account, b"x" * 5_000_001).status_code == 413
    assert (
        rt.client.put("/api/users/me/profile-image", headers=header).status_code == 422
    )
    assert (
        rt.client.put(
            "/api/users/me/profile-image",
            headers=header,
            files={"wrong-field": ("input.png", png(), "image/png")},
        ).status_code
        == 422
    )
    assert (
        rt.client.put(
            "/api/users/me/profile-image",
            headers=header,
            files=[
                ("image", ("a.png", png(), "image/png")),
                ("image", ("b.png", png(), "image/png")),
            ],
        ).status_code
        == 422
    )
    assert (
        rt.client.get("/api/users/me", headers=header).json()["data"][
            "profile_image_url"
        ]
        is None
    )


def test_file_delete_failure_keeps_db_result_and_durable_retry(
    account_runtime, monkeypatch
):
    rt = account_runtime
    account, _ = rt.signup()
    first = upload(rt, account)
    assert first.status_code == 200
    old_url = first.json()["data"]["profile_image_url"]
    old_key = old_url.rsplit("/", 1)[1]
    original = ImageStore.delete

    def fail_delete(self, key):
        raise OSError("injected delete failure")

    monkeypatch.setattr(ImageStore, "delete", fail_delete)
    second = upload(rt, account)
    assert second.status_code == 200
    assert (rt.root / old_key).exists()
    assert rt.client.get(old_url, headers=rt.header(account)).status_code == 404
    with rt.factory() as db:
        job = db.scalar(
            select(ProfileImageCleanupJob).where(
                ProfileImageCleanupJob.file_key == old_key
            )
        )
        assert job is not None and job.attempt_count == 1
        assert job.next_attempt_at >= utc_now() + timedelta(seconds=50)
    monkeypatch.setattr(ImageStore, "delete", original)
    assert ImageCleanupService(rt.factory, ImageStore(rt.root)).run(key=old_key) == 1
    assert not (rt.root / old_key).exists()


@pytest.mark.parametrize("failure", ["write", "before_commit", "commit_ack"])
def test_photo_failure_preserves_reference_and_cleanup_intent(
    account_runtime, monkeypatch, failure
):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    rt = account_runtime
    account, _ = rt.signup()
    first = upload(rt, account)
    assert first.status_code == 200
    old_url = first.json()["data"]["profile_image_url"]
    old_key = old_url.rsplit("/", 1)[1]
    original_write, original_commit = ImageStore.write, Session.commit
    if failure == "write":

        def broken_write(self, key, data):
            original_write(self, key, data[:8])
            raise OSError("injected partial write")

        monkeypatch.setattr(ImageStore, "write", broken_write)
    else:
        original_flush = Session.flush

        def observe_flush(self, *args, **kwargs):
            if any(isinstance(item, UserProfile) for item in self.dirty):
                self.info["test_photo_changed"] = True
            return original_flush(self, *args, **kwargs)

        monkeypatch.setattr(Session, "flush", observe_flush)

        def uncertain_commit(self):
            photo_change = self.info.pop("test_photo_changed", False)
            if photo_change and failure == "before_commit":
                raise SQLAlchemyError("injected before commit")
            original_commit(self)
            if photo_change and failure == "commit_ack":
                raise SQLAlchemyError("injected lost commit acknowledgement")

        monkeypatch.setattr(Session, "commit", uncertain_commit)
    changed = upload(rt, account)
    assert changed.status_code == 500
    current_url = rt.client.get("/api/users/me", headers=rt.header(account)).json()[
        "data"
    ]["profile_image_url"]
    monkeypatch.setattr(ImageStore, "write", original_write)
    monkeypatch.setattr(Session, "commit", original_commit)
    with rt.factory() as db:
        jobs = list(db.scalars(select(ProfileImageCleanupJob)))
        assert len(jobs) == 1
        if failure == "commit_ack":
            assert current_url != old_url
            assert jobs[0].file_key == old_key
        else:
            assert current_url == old_url
            assert jobs[0].file_key != old_key
            assert jobs[0].next_attempt_at >= utc_now() + timedelta(minutes=59)
        jobs[0].next_attempt_at = utc_now()
        db.commit()
    cleanup = ImageCleanupService(rt.factory, ImageStore(rt.root))
    assert cleanup.run() == 1
    assert (rt.root / current_url.rsplit("/", 1)[1]).exists()
    assert rt.client.get(current_url, headers=rt.header(account)).status_code == 200
    assert cleanup.metrics()["pending_count"] == 0


def test_cleanup_never_deletes_current_referenced_photo(account_runtime):
    from app.repositories.image_cleanup_repository import ImageCleanupRepository

    rt = account_runtime
    account, _ = rt.signup()
    photo = upload(rt, account)
    assert photo.status_code == 200
    key = photo.json()["data"]["profile_image_url"].rsplit("/", 1)[1]
    with rt.factory() as db:
        ImageCleanupRepository(db).add(key, utc_now() - timedelta(minutes=2), utc_now())
        db.commit()
    cleanup = ImageCleanupService(rt.factory, ImageStore(rt.root))
    assert cleanup.run() == 0
    assert (rt.root / key).exists()
    metrics = cleanup.metrics()
    assert metrics["pending_count"] == 1 and metrics["oldest_pending_seconds"] >= 120


def test_concurrent_nickname_unique_constraint_has_one_winner(account_runtime):
    from app.core.exceptions import ConflictException
    from app.services.account_service import AccountService

    rt = account_runtime
    accounts = [rt.signup()[0], rt.signup()[0]]
    barrier = Barrier(2)
    nickname = "동_" + uuid4().hex[:8]

    def save(account):
        with rt.factory() as db:
            context = SessionService(db).authenticate(account["access_token"])
            barrier.wait(timeout=5)
            try:
                AccountService(db, store=ImageStore(rt.root)).save_nickname(
                    context, nickname
                )
                return 200
            except ConflictException:
                return 409

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(save, account) for account in accounts]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]


def test_login_reloads_password_after_user_lock(account_runtime, monkeypatch):
    from threading import Event

    from app.core.security import hash_password
    from app.repositories.interest_repository import InterestRepository
    from app.repositories.session_repository import SessionRepository
    from app.repositories.user_repository import UserRepository
    from app.schemas.auth_schema import LoginRequest
    from app.services.auth_service import AuthService

    rt = account_runtime
    account, login_id = rt.signup()
    read_old_user = Event()
    original = UserRepository.find_by_login_id

    def observed_read(self, value):
        user = original(self, value)
        read_old_user.set()
        return user

    monkeypatch.setattr(UserRepository, "find_by_login_id", observed_read)
    with rt.factory() as blocker:
        user = SessionRepository(blocker).lock_user(account["user"]["user_id"])
        user.password_hash = hash_password(NEW_PASSWORD)
        blocker.flush()

        def login():
            with rt.factory() as db:
                try:
                    AuthService(db, UserRepository(db), InterestRepository(db)).login(
                        LoginRequest(login_id=login_id, password=PASSWORD)
                    )
                    return 200
                except UnauthorizedException:
                    return 401

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(login)
            assert read_old_user.wait(timeout=5)
            blocker.commit()
            assert future.result(timeout=15) == 401
    with rt.factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuthSession)
                .where(AuthSession.user_id == account["user"]["user_id"])
            )
            == 1
        )


def test_stale_profile_object_does_not_overwrite_other_field(account_runtime):
    from app.services.account_service import AccountService

    rt = account_runtime
    account, _ = rt.signup()
    with rt.factory() as stale:
        context = SessionService(stale).authenticate(account["access_token"])
        previous = stale.scalar(
            select(UserProfile).where(UserProfile.user_id == context.user_id)
        )
        assert previous.profile_image_url is None
        photo = upload(rt, account)
        assert photo.status_code == 200
        url = photo.json()["data"]["profile_image_url"]
        nickname = "변_" + uuid4().hex[:8]
        result = AccountService(stale, store=ImageStore(rt.root)).save_nickname(
            context, nickname
        )
        assert result.profile_image_url == url
    current = rt.client.get("/api/users/me", headers=rt.header(account)).json()["data"]
    assert current["profile_image_url"] == url and current["nickname"] == nickname


def test_missing_member_photo_has_documented_error_reason(account_runtime):
    rt = account_runtime
    account, _ = rt.signup()
    response = rt.client.get(
        "/api/users/9223372036854775800/profile-image/" + "a" * 32 + ".png",
        headers=rt.header(account),
    )
    assert response.status_code == 404
    assert response.json()["data"]["reason"] == "PROFILE_IMAGE_NOT_FOUND"


def test_withdrawal_rechecks_password_deletes_rows_and_allows_new_account(
    account_runtime,
):
    rt = account_runtime
    nickname = "닉_" + uuid4().hex[:8]
    email = uuid4().hex + "@example.com"
    account, login_id = rt.signup(nickname=nickname, email=email)
    user_id = account["user"]["user_id"]
    first = upload(rt, account)
    assert first.status_code == 200
    photo_key = first.json()["data"]["profile_image_url"].rsplit("/", 1)[1]
    with rt.factory() as db:
        db.add(
            SearchLog(
                user_id=user_id, keyword="test search", normalized_keyword="test search"
            )
        )
        db.commit()
    assert (
        rt.client.post(
            "/api/users/me/withdrawal/verify-password",
            headers=rt.header(account),
            json={"current_password": PASSWORD},
        ).status_code
        == 200
    )
    assert (
        rt.client.put(
            "/api/users/me/password",
            headers=rt.header(account),
            json={
                "current_password": PASSWORD,
                "new_password": NEW_PASSWORD,
                "new_password_confirm": NEW_PASSWORD,
            },
        ).status_code
        == 200
    )
    assert (
        rt.client.post(
            "/api/users/me/withdrawal",
            headers=rt.header(account),
            json={"current_password": PASSWORD},
        ).status_code
        == 400
    )
    final = rt.client.post(
        "/api/users/me/withdrawal",
        headers=rt.header(account),
        json={"current_password": NEW_PASSWORD},
    )
    assert final.status_code == 200
    with rt.factory() as db:
        assert db.get(User, user_id) is None
        for model in [UserProfile, AuthSession, SearchLog]:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.user_id == user_id)
                )
                == 0
            )
    assert not (rt.root / photo_key).exists()
    assert (
        rt.client.get("/api/auth/session", headers=rt.header(account)).status_code
        == 401
    )
    new_account, _ = rt.signup(login_id=login_id, nickname=nickname, email=email)
    assert new_account["user"]["user_id"] != user_id
    assert new_account["has_selected_interests"] is False
    assert (
        rt.client.post(
            "/api/auth/refresh", json={"refresh_token": account["refresh_token"]}
        ).status_code
        == 401
    )
