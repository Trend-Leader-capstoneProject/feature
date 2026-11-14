import hashlib
import io
from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from jose import jwt
from PIL import Image

from app.core.auth_time import as_utc, utc_now
from app.core.config import get_settings
from app.core.exceptions import ApplicationException, UnauthorizedException
from app.core.nickname import nickname_key, normalize_nickname
from app.core.security import create_access_token
from app.models.auth_refresh_token import AuthRefreshToken
from app.models.auth_session import AuthSession
from app.models.db_enums import UserStatus
from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.schemas.account_schema import NicknameRequest
from app.services.image_service import ImageStore, process_image
from app.services.session_service import SessionService


@pytest.mark.parametrize(
    "value,expected",
    [
        (" 가나다 ", "가나다"),
        ("Trend_01", "Trend_01"),
        ("가나", "가나"),
        ("가" * 10, "가" * 10),
    ],
)
def test_nickname_normalizes_only_approved_characters(value, expected):
    assert normalize_nickname(value) == expected


@pytest.mark.parametrize("value", ["a", "a" * 11, "ㄱㄴ", "가 나", "ＡＢ", "éé", "", 3])
def test_nickname_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_nickname(value)


def test_nickname_preserves_display_case_and_compares_lowercase():
    assert nickname_key(" Trend ") == nickname_key("trend")
    assert NicknameRequest(nickname=" Trend ").nickname == "Trend"


def image_bytes(mode="RGB", size=(1200, 600), format="PNG"):
    image = Image.new(
        mode, size, color=(10, 20, 30, 40) if mode == "RGBA" else (10, 20, 30)
    )
    output = io.BytesIO()
    image.save(output, format=format)
    return output.getvalue()


def test_png_is_resized_without_metadata_or_losing_alpha():
    raw = image_bytes("RGBA")
    data, extension = process_image(raw)
    with Image.open(io.BytesIO(data)) as output:
        assert output.size == (1024, 512)
        assert output.mode == "RGBA"
        assert output.getpixel((0, 0))[3] == 40
        assert not output.getexif()
    assert extension == "png"


def test_small_jpeg_is_not_upscaled():
    data, extension = process_image(image_bytes(size=(80, 40), format="JPEG"))
    with Image.open(io.BytesIO(data)) as output:
        assert output.size == (80, 40)
    assert extension == "jpg"


@pytest.mark.parametrize(
    "raw,status,reason",
    [
        (b"x" * 5_000_001, 413, "PROFILE_IMAGE_TOO_LARGE"),
        (b"not an image", 400, "PROFILE_IMAGE_INVALID"),
        (image_bytes(size=(2, 2), format="GIF"), 415, "PROFILE_IMAGE_UNSUPPORTED"),
    ],
)
def test_image_rejects_bad_input(raw, status, reason):
    with pytest.raises(ApplicationException) as error:
        process_image(raw)
    assert error.value.status_code == status
    assert error.value.data["reason"] == reason


def test_jpeg_orientation_is_applied_and_private_metadata_removed():
    source = Image.new("RGB", (80, 40), "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private creator"
    raw = io.BytesIO()
    source.save(raw, format="JPEG", exif=exif, icc_profile=b"private profile")
    with Image.open(io.BytesIO(raw.getvalue())) as original:
        assert original.getexif()[274] == 6
        assert original.info["icc_profile"]
    data, extension = process_image(raw.getvalue())
    with Image.open(io.BytesIO(data)) as output:
        assert output.size == (40, 80)
        assert not output.getexif()
        assert "icc_profile" not in output.info
    assert extension == "jpg"


def test_animated_png_is_rejected():
    raw = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        raw,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")],
        duration=100,
        loop=0,
    )
    with pytest.raises(ApplicationException) as error:
        process_image(raw.getvalue())
    assert error.value.status_code == 415
    assert error.value.data["reason"] == "PROFILE_IMAGE_UNSUPPORTED"


def test_exactly_five_million_bytes_is_accepted():
    raw = image_bytes(size=(8, 8))
    padded = raw + b"\0" * (5_000_000 - len(raw))
    data, _ = process_image(padded)
    with Image.open(io.BytesIO(data)) as output:
        assert output.size == (8, 8)


def test_small_compressed_file_with_excess_pixels_is_rejected():
    raw = image_bytes(size=(5000, 4001))
    assert len(raw) < 5_000_000
    with pytest.raises(ApplicationException) as error:
        process_image(raw)
    assert error.value.status_code == 413
    assert error.value.data["reason"] == "PROFILE_IMAGE_PIXEL_LIMIT_EXCEEDED"


def test_store_never_interprets_client_path(tmp_path):
    store = ImageStore(tmp_path.resolve())
    for key in ["../secret.jpg", "/secret.jpg", "hello.jpg"]:
        with pytest.raises(ValueError):
            store.path(key)
    key = store.new_key("jpg")
    store.write(key, b"test")
    assert store.read(key) == b"test"
    with pytest.raises(FileExistsError):
        store.write(key, b"overwrite")
    store.delete(key)
    store.delete(key)


def session_service():
    db = Mock()
    db.new, db.dirty, db.deleted = set(), set(), set()
    service = SessionService(db)
    repository = Mock(spec=SessionRepository)
    service.repository = repository
    user = User(
        user_id=42, name="private name", login_id="user42", status=UserStatus.ACTIVE
    )
    now = utc_now()
    session = AuthSession(
        session_id=str(uuid4()),
        user_id=42,
        created_at=now,
        expires_at=now + timedelta(days=30),
        current_generation=1,
    )
    session.revoked_at = None
    repository.find.return_value = session
    repository.lock_session.return_value = session
    repository.lock_user.return_value = user
    db.scalar.return_value = user
    return service, db, repository, user, session


def test_rotation_keeps_absolute_expiry_and_only_hashes_refresh():
    service, db, repo, _, session = session_service()
    raw = "A" * 43
    record = AuthRefreshToken(session_id=session.session_id, generation=1, used_at=None)
    repo.find_refresh.return_value = record
    repo.lock_refresh.return_value = record
    result = service.refresh(raw)
    assert record.used_at is not None
    assert session.current_generation == 2
    assert result.refresh_expires_at == as_utc(session.expires_at)
    saved = repo.add.call_args.args[0]
    assert (
        saved.token_hash
        == hashlib.sha256(result.refresh_token.encode("ascii")).hexdigest()
    )
    assert not hasattr(saved, "refresh_token")
    assert len(result.refresh_token) == 43
    db.commit.assert_called_once()


def test_replay_commits_revocation_before_401():
    service, db, repo, _, session = session_service()
    record = AuthRefreshToken(
        session_id=session.session_id, generation=1, used_at=utc_now()
    )
    repo.find_refresh.return_value = record
    repo.lock_refresh.return_value = record
    with pytest.raises(UnauthorizedException) as error:
        service.refresh("A" * 43)
    assert error.value.data["reason"] == "REFRESH_TOKEN_REUSED"
    assert session.revoked_at is not None
    db.commit.assert_called_once()
    calls = [call[0] for call in db.method_calls]
    assert calls.index("rollback") < calls.index("commit")
    assert calls[-1] == "commit"
    repo.add.assert_not_called()


def test_unknown_refresh_cannot_revoke_any_session():
    service, db, repo, _, session = session_service()
    repo.find_refresh.return_value = None
    with pytest.raises(UnauthorizedException):
        service.refresh("A" * 43)
    repo.lock_user.assert_not_called()
    assert session.revoked_at is None
    db.commit.assert_not_called()


def test_expired_access_can_only_refresh_if_session_is_live():
    service, _, repo, _, session = session_service()
    token = create_access_token(
        42, session.session_id, as_utc(utc_now() - timedelta(seconds=1))
    )
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token)
    assert error.value.data["reason"] == "ACCESS_TOKEN_EXPIRED"
    session.revoked_at = utc_now()
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token)
    assert error.value.data["reason"] == "SESSION_REVOKED"


def test_legacy_token_without_session_requires_relogin():
    service, db, _, _, _ = session_service()
    token = create_access_token(42)
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token)
    assert error.value.data["reason"] == "ACCESS_TOKEN_INVALID"
    db.scalar.assert_not_called()


def test_access_cannot_outlive_session_boundary():
    service, _, _, _, session = session_service()
    token = create_access_token(
        42, session.session_id, as_utc(utc_now() + timedelta(minutes=15))
    )
    session.expires_at = utc_now()
    with pytest.raises(UnauthorizedException) as error:
        service.authenticate(token)
    assert error.value.data["reason"] == "SESSION_EXPIRED"


def test_invalid_signature_does_not_query_database():
    service, db, _, _, session = session_service()
    token = jwt.encode(
        {"sub": "42", "sid": session.session_id, "exp": as_utc(session.expires_at)},
        "different-test-key-that-is-long-enough",
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(UnauthorizedException):
        service.authenticate(token)
    db.scalar.assert_not_called()
