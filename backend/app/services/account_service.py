import logging
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.auth_time import utc_now
from app.core.config import get_settings
from app.core.exceptions import ConflictException, NotFoundException
from app.core.nickname import nickname_key
from app.models.user import User
from app.repositories.image_cleanup_repository import ImageCleanupRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.account_schema import NicknameAvailability, ProfileData
from app.services.image_cleanup_service import ImageCleanupService
from app.services.image_service import ImageStore, image_error
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, db, *, store=None, session_factory=None) -> None:
        self.db = db
        self.profiles = ProfileRepository(db)
        self.sessions = SessionService(db)
        self.store = store or ImageStore(get_settings().profile_image_root)
        # 별도 commit용 Session은 요청의 외부 rollback Transaction을 공유하지 않는다.
        self.session_factory = session_factory or sessionmaker(
            bind=db.get_bind().engine, expire_on_commit=False
        )
        self.cleanup = ImageCleanupService(self.session_factory, self.store)

    def availability(self, nickname: str, user_id: int | None = None):
        profile = self.profiles.find_key(nickname_key(nickname))
        available = profile is None or profile.user_id == user_id
        return NicknameAvailability(
            nickname=nickname,
            is_available=available,
            reason=None if available else "DUPLICATED_NICKNAME",
        )

    def profile(self, user_id: int) -> ProfileData:
        return self._data(self._profile(user_id))

    def _profile(self, user_id: int, *, lock=False):
        profile = self.profiles.find(user_id, lock=lock)
        if profile is None:
            raise NotFoundException()
        return profile

    @staticmethod
    def _data(profile) -> ProfileData:
        key = profile.profile_image_url
        prefix = get_settings().api_prefix
        return ProfileData(
            user_id=profile.user_id,
            nickname=profile.nickname,
            profile_image_url=(
                f"{prefix}/users/{profile.user_id}/profile-image/{key}" if key else None
            ),
        )

    def save_nickname(self, context, nickname: str) -> ProfileData:
        user, _ = self.sessions.lock_context(context)
        profile = self._profile(user.user_id, lock=True)
        profile.nickname = nickname
        profile.nickname_key = nickname_key(nickname)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            args = getattr(exc.orig, "args", ())
            if (
                args
                and args[0] == 1062
                and "uq_user_profiles_nickname_key" in str(exc.orig)
            ):
                raise ConflictException(data={"reason": "DUPLICATED_NICKNAME"}) from exc
            raise
        return self._data(profile)

    def save_image(self, context, data: bytes, extension: str) -> ProfileData:
        # 인증 조회의 RR snapshot은 독립 prepare commit보다 먼저 시작됐다.
        # 쓰기 전 읽기 Transaction을 닫고, 아래에서 사용자·세션을 다시 잠금 검증한다.
        self.sessions.finish_read_phase()
        key = self.store.new_key(extension)
        now = utc_now()
        # 영구 파일을 쓰기 전에 별도 commit한 intent를 남긴다.
        with self.session_factory() as prepare_db:
            ImageCleanupRepository(prepare_db).add(key, now, now + timedelta(hours=1))
            prepare_db.commit()
        try:
            user, _ = self.sessions.lock_context(context)
            profile = self._profile(user.user_id, lock=True)
            intent = ImageCleanupRepository(self.db).lock_key(key)
            if intent is None:
                raise image_error(503, "PROFILE_IMAGE_PROCESSING_BUSY")
            old_key = profile.profile_image_url
            self.store.write(key, data)
            profile.profile_image_url = key
            self.db.delete(intent)
            if old_key:
                ImageCleanupRepository(self.db).add(old_key, now, now)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        result = self._data(profile)
        self._cleanup_after_commit(old_key)
        return result

    def reset_image(self, context) -> ProfileData:
        user, _ = self.sessions.lock_context(context)
        profile = self._profile(user.user_id, lock=True)
        old_key = profile.profile_image_url
        if old_key:
            now = utc_now()
            ImageCleanupRepository(self.db).add(old_key, now, now)
            profile.profile_image_url = None
        self.db.commit()
        result = self._data(profile)
        self._cleanup_after_commit(old_key)
        return result

    def image(self, user_id: int, key: str) -> tuple[bytes, str]:
        profile = self.profiles.find(user_id)
        if profile is None or profile.profile_image_url != key:
            raise image_error(404, "PROFILE_IMAGE_NOT_FOUND")
        try:
            data = self.store.read(key)
        except (OSError, ValueError) as exc:
            raise image_error(404, "PROFILE_IMAGE_NOT_FOUND") from exc
        return data, "image/png" if key.endswith(".png") else "image/jpeg"

    def verify_withdrawal(self, context, password: str) -> None:
        user, _ = self.sessions.lock_context(context)
        self.sessions.verify_current_password(user, password)
        # 검증 잠금을 후속 최종 확인 화면까지 보유하지 않는다.
        self.db.rollback()

    def withdraw(self, context, password: str) -> None:
        user, _ = self.sessions.lock_context(context)
        self.sessions.verify_current_password(user, password)
        profile = self._profile(user.user_id, lock=True)
        old_key = profile.profile_image_url
        if old_key:
            now = utc_now()
            ImageCleanupRepository(self.db).add(old_key, now, now)
        # DB CASCADE로 인증·프로필·관심사·북마크·검색 등 연결 기록을 삭제한다.
        self.db.execute(delete(User).where(User.user_id == user.user_id))
        self.db.commit()
        self._cleanup_after_commit(old_key)

    def _cleanup_after_commit(self, key) -> None:
        if not key:
            return
        try:
            self.cleanup.run(key=key)
        except Exception:
            # DB 변경 성공은 유지하고 durable job을 다음 실행에서 재처리한다.
            logger.warning("profile_image_cleanup_deferred")
