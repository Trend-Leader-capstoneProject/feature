from queue import Queue
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.db_enums import UserStatus
from app.models.user import User
from app.models.user_interest_category import UserInterestCategory
from app.repositories.category_repository import CategoryRepository
from app.repositories.interest_repository import InterestRepository
from app.services.interest_service import InterestService

pytestmark = pytest.mark.integration


class FailingSaveInterestRepository(
    InterestRepository,
):
    """
    관심사 추가 단계에서 강제로 DB 오류를 발생시키는 테스트 Repository.
    실제 DB 처리
    """

    def save(
        self,
        user_interests: list[UserInterestCategory],
    ) -> list[UserInterestCategory]:
        raise SQLAlchemyError(
            "관심사 저장 강제 실패",
        )

class BlockingInterestRepository(
    InterestRepository,
):
    """첫 Lock 획득 후 테스트가 허용할 때까지 A Transaction을 대기시킨다."""

    def __init__(
        self,
        db: Session,
        *,
        lock_acquired: Event,
        allow_continue: Event,
    ) -> None:
        super().__init__(
            db=db,
        )
        self.lock_acquired = lock_acquired
        self.allow_continue = allow_continue
        self.has_blocked = False

    def find_by_user_id_for_update(
        self,
        user_id: int,
    ) -> list[UserInterestCategory]:
        user_interests = super().find_by_user_id_for_update(
            user_id,
        )

        if not self.has_blocked:
            self.has_blocked = True
            self.lock_acquired.set()

            if not self.allow_continue.wait(
                timeout=5,
            ):
                raise RuntimeError(
                    "A Transaction 계속 실행 신호를 받지 못했습니다.",
                )

        return user_interests

class ObservingInterestRepository(
    InterestRepository,
):
    """B의 FOR UPDATE 시도와 실제 DB 오류 코드를 기록한다."""

    def __init__(
        self,
        db: Session,
        *,
        lock_attempted: Event,
    ) -> None:
        super().__init__(
            db=db,
        )
        self.lock_attempted = lock_attempted
        self.observed_error_codes: list[int] = []

    def find_by_user_id_for_update(
        self,
        user_id: int,
    ) -> list[UserInterestCategory]:
        self.lock_attempted.set()

        try:
            return super().find_by_user_id_for_update(
                user_id,
            )

        except DBAPIError as exc:
            original_args = getattr(
                exc.orig,
                "args",
                (),
            )

            if original_args:
                self.observed_error_codes.append(
                    original_args[0],
                )

            raise


class CountingCategoryRepository(
    CategoryRepository,
):
    """PUT Retry 시 Category 조회 전체가 다시 수행되는지 기록한다."""

    def __init__(
        self,
        db: Session,
    ) -> None:
        super().__init__(
            db=db,
        )
        self.find_list_calls = 0

    def find_list_by_ids(
        self,
        category_ids: list[int],
    ) -> list[Category]:
        self.find_list_calls += 1

        return super().find_list_by_ids(
            category_ids,
        )

def create_test_user(
    db_session: Session,
    *,
    name: str,
) -> User:
    """InterestService 통합 테스트용 사용자를 생성한다."""

    user = User(
        name=name,
        status=UserStatus.ACTIVE,
    )

    db_session.add(
        user,
    )
    db_session.flush()

    return user


def create_test_category(
    db_session: Session,
    *,
    category_name: str,
) -> Category:
    """InterestService 통합 테스트용 활성 대분류를 생성한다."""

    category = Category(
        category_code=None,
        category_name=category_name,
        sort_order=1,
        is_active=True,
        parent_id=None,
    )

    db_session.add(
        category,
    )
    db_session.flush()

    return category


def create_user_interests(
    db_session: Session,
    *,
    user_id: int,
    category_ids: list[int],
) -> list[UserInterestCategory]:
    """테스트용 사용자 관심사 Row를 생성한다."""

    user_interests = [
        UserInterestCategory(
            user_id=user_id,
            category_id=category_id,
        )
        for category_id in category_ids
    ]

    db_session.add_all(
        user_interests,
    )
    db_session.flush()

    return user_interests


def build_service(
    db_session: Session,
    *,
    interest_repository: InterestRepository | None = None,
) -> InterestService:
    """실제 MariaDB Repository를 사용하는 InterestService를 생성한다."""

    return InterestService(
        db=db_session,
        category_repository=CategoryRepository(
            db=db_session,
        ),
        interest_repository=(
            interest_repository
            or InterestRepository(
                db=db_session,
            )
        ),
    )


def find_interest_rows(
    db_session: Session,
    *,
    user_id: int,
) -> list[UserInterestCategory]:
    """사용자의 관심사 Row를 결정적인 순서로 조회한다."""

    statement = (
        select(
            UserInterestCategory,
        )
        .where(
            UserInterestCategory.user_id == user_id,
        )
        .order_by(
            UserInterestCategory.category_id,
        )
    )

    return list(
        db_session.scalars(
            statement,
        ).all()
    )


def test_update_interests_applies_diff_and_preserves_kept_row(
    db_session: Session,
) -> None:
    """실제 DB에서 diff 수정하며 유지 Row를 재생성하지 않는다."""

    user = create_test_user(
        db_session,
        name="Service 통합 수정 사용자",
    )

    category_one = create_test_category(
        db_session,
        category_name="Service 통합 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        category_name="Service 통합 관심사 B",
    )
    category_three = create_test_category(
        db_session,
        category_name="Service 통합 관심사 C",
    )

    initial_interests = create_user_interests(
        db_session,
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_two.category_id,
        ],
    )

    db_session.commit()

    kept_interest_before = next(
        interest
        for interest in initial_interests
        if interest.category_id
        == category_one.category_id
    )

    kept_interest_id_before = (
        kept_interest_before.user_interest_id
    )
    kept_created_at_before = (
        kept_interest_before.created_at
    )

    service = build_service(
        db_session,
    )

    result = service.update_interests(
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_three.category_id,
        ],
    )

    assert result.selected_category_ids == [
        category_one.category_id,
        category_three.category_id,
    ]
    assert result.selected_count == 2

    final_interests = find_interest_rows(
        db_session,
        user_id=user.user_id,
    )

    assert [
        interest.category_id
        for interest in final_interests
    ] == [
        category_one.category_id,
        category_three.category_id,
    ]

    kept_interest_after = next(
        interest
        for interest in final_interests
        if interest.category_id
        == category_one.category_id
    )

    assert (
        kept_interest_after.user_interest_id
        == kept_interest_id_before
    )
    assert (
        kept_interest_after.created_at
        == kept_created_at_before
    )


def test_update_interests_restores_original_state_after_save_failure(
    db_session: Session,
) -> None:
    """delete 이후 save 실패 시 rollback으로 실제 DB 상태를 복원한다."""

    user = create_test_user(
        db_session,
        name="Service 통합 Rollback 사용자",
    )

    category_one = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 A",
    )
    category_two = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 B",
    )
    category_three = create_test_category(
        db_session,
        category_name="Service Rollback 관심사 C",
    )

    initial_interests = create_user_interests(
        db_session,
        user_id=user.user_id,
        category_ids=[
            category_one.category_id,
            category_two.category_id,
        ],
    )

    db_session.commit()

    initial_interest_ids = {
        interest.category_id: interest.user_interest_id
        for interest in initial_interests
    }

    failing_repository = FailingSaveInterestRepository(
        db=db_session,
    )

    service = build_service(
        db_session,
        interest_repository=failing_repository,
    )

    with pytest.raises(
        SQLAlchemyError,
        match="관심사 저장 강제 실패",
    ):
        service.update_interests(
            user_id=user.user_id,
            category_ids=[
                category_one.category_id,
                category_three.category_id,
            ],
        )

    final_interests = find_interest_rows(
        db_session,
        user_id=user.user_id,
    )

    assert [
        interest.category_id
        for interest in final_interests
    ] == [
        category_one.category_id,
        category_two.category_id,
    ]

    assert {
        interest.category_id: interest.user_interest_id
        for interest in final_interests
    } == initial_interest_ids


def test_update_interests_retries_er_checkread_and_preserves_last_writer_set(
    test_engine: Engine,
) -> None:
    """동일 사용자 동시 PUT에서 1020 Retry 후 마지막 전체 집합을 보존한다."""

    suffix = uuid4().hex

    setup_session = Session(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    user_id: int | None = None
    category_ids: list[int] = []

    try:
        user = create_test_user(
            setup_session,
            name=f"Service 동시성 사용자 {suffix}",
        )

        category_one = create_test_category(
            setup_session,
            category_name=f"Service 동시성 관심사 A {suffix}",
        )
        category_two = create_test_category(
            setup_session,
            category_name=f"Service 동시성 관심사 B {suffix}",
        )
        category_three = create_test_category(
            setup_session,
            category_name=f"Service 동시성 관심사 C {suffix}",
        )

        user_id = user.user_id
        category_ids = [
            category_one.category_id,
            category_two.category_id,
            category_three.category_id,
        ]

        create_user_interests(
            setup_session,
            user_id=user_id,
            category_ids=[
                category_one.category_id,
                category_two.category_id,
            ],
        )

        setup_session.commit()

    finally:
        setup_session.close()

    category_a = category_ids[0]
    category_b = category_ids[1]
    category_c = category_ids[2]

    a_target = [
        category_a,
        category_c,
    ]
    b_target = [
        category_b,
        category_c,
    ]

    a_lock_acquired = Event()
    allow_a_continue = Event()
    b_lock_attempted = Event()

    a_result_queue: Queue[dict[str, object]] = Queue()
    b_result_queue: Queue[dict[str, object]] = Queue()

    def run_transaction_a() -> None:
        session = Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        try:
            repository = BlockingInterestRepository(
                db=session,
                lock_acquired=a_lock_acquired,
                allow_continue=allow_a_continue,
            )

            service = InterestService(
                db=session,
                category_repository=CategoryRepository(
                    db=session,
                ),
                interest_repository=repository,
            )

            result = service.update_interests(
                user_id=user_id,
                category_ids=a_target,
            )

            a_result_queue.put(
                {
                    "status": "success",
                    "selected_category_ids": (
                        result.selected_category_ids
                    ),
                }
            )

        except Exception as exc:
            session.rollback()

            a_result_queue.put(
                {
                    "status": "error",
                    "error": repr(
                        exc,
                    ),
                }
            )

        finally:
            session.close()

    def run_transaction_b() -> None:
        session = Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        try:
            # 실제 보호 API의 CurrentUser DB 조회처럼
            # InterestService 실행 전에 일반 SELECT를 수행하여
            # B의 기존 read view가 형성될 수 있는 조건을 만든다.
            current_user = session.get(
                User,
                user_id,
            )

            if current_user is None:
                raise RuntimeError(
                    "동시성 테스트 사용자를 조회하지 못했습니다.",
                )

            category_repository = CountingCategoryRepository(
                db=session,
            )
            interest_repository = ObservingInterestRepository(
                db=session,
                lock_attempted=b_lock_attempted,
            )

            service = InterestService(
                db=session,
                category_repository=category_repository,
                interest_repository=interest_repository,
            )

            result = service.update_interests(
                user_id=user_id,
                category_ids=b_target,
            )

            b_result_queue.put(
                {
                    "status": "success",
                    "selected_category_ids": (
                        result.selected_category_ids
                    ),
                    "error_codes": (
                        interest_repository.observed_error_codes
                    ),
                    "category_query_count": (
                        category_repository.find_list_calls
                    ),
                }
            )

        except Exception as exc:
            session.rollback()

            b_result_queue.put(
                {
                    "status": "error",
                    "error": repr(
                        exc,
                    ),
                }
            )

        finally:
            session.close()

    thread_a = Thread(
        target=run_transaction_a,
    )
    thread_b = Thread(
        target=run_transaction_b,
    )

    try:
        thread_a.start()

        assert a_lock_acquired.wait(
            timeout=5,
        )

        thread_b.start()

        assert b_lock_attempted.wait(
            timeout=5,
        )

        # A가 FOR UPDATE Lock을 가진 동안 B가 종료되면 안 된다.
        thread_b.join(
            timeout=0.2,
        )

        assert thread_b.is_alive()

        allow_a_continue.set()

        thread_a.join(
            timeout=5,
        )
        thread_b.join(
            timeout=5,
        )

        assert not thread_a.is_alive()
        assert not thread_b.is_alive()

        a_result = a_result_queue.get_nowait()
        b_result = b_result_queue.get_nowait()

        assert a_result["status"] == "success"
        assert a_result["selected_category_ids"] == sorted(
            a_target,
        )

        assert b_result["status"] == "success"
        assert b_result["selected_category_ids"] == sorted(
            b_target,
        )

        assert b_result["error_codes"] == [
            InterestService.ER_CHECKREAD_CODE,
        ]

        assert b_result["category_query_count"] == 2

        verification_session = Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        try:
            final_interests = find_interest_rows(
                verification_session,
                user_id=user_id,
            )

            assert [
                interest.category_id
                for interest in final_interests
            ] == sorted(
                b_target,
            )

        finally:
            verification_session.close()

    finally:
        allow_a_continue.set()

        if thread_a.is_alive():
            thread_a.join(
                timeout=5,
            )

        if thread_b.is_alive():
            thread_b.join(
                timeout=5,
            )

        cleanup_session = Session(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        try:
            cleanup_session.execute(
                delete(
                    UserInterestCategory,
                ).where(
                    UserInterestCategory.user_id == user_id,
                )
            )

            cleanup_session.execute(
                delete(
                    User,
                ).where(
                    User.user_id == user_id,
                )
            )

            cleanup_session.execute(
                delete(
                    Category,
                ).where(
                    Category.category_id.in_(
                        category_ids,
                    )
                )
            )

            cleanup_session.commit()

        finally:
            cleanup_session.close()
