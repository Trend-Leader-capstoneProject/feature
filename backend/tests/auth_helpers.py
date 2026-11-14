"""새 인증 계약을 위한 API 단위 테스트의 격리된 세션 기록."""

from datetime import timedelta
from unittest.mock import Mock

from app.core.auth_time import utc_now
from app.models.auth_session import AuthSession
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

SESSION_ID = "11111111-1111-4111-8111-111111111111"


def session_service_for_user(find_user, user_id=100):
    db = Mock()
    db.scalar.side_effect = lambda statement: find_user(user_id)
    service = SessionService(db)
    records = Mock(spec=SessionRepository)
    records.find.return_value = AuthSession(
        session_id=SESSION_ID,
        user_id=user_id,
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(days=30),
        current_generation=1,
        revoked_at=None,
    )
    service.repository = records
    return service
