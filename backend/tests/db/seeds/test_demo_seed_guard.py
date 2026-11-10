"""DB checkout 없이 실제 SQLAlchemy Session과 모의 DBAPI로 가드를 검증한다."""

from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, make_transient_to_detached, sessionmaker

from app.db.seeds import demo_trends as seed_module
from app.db.seeds.demo_trends import DemoTrendSeedError, seed_demo_trends
from app.models.trend import Trend


def approval(**changes):
    return {
        "allowed_host": "127.0.0.1",
        "allowed_port": 3307,
        "allowed_database": "trend_leader_test",
        "allowed_current_user": "seed_manager@%",
        **changes,
    }


@pytest.fixture
def session():
    engine = create_engine(
        "mysql+pymysql://test:fake-secret@127.0.0.1:3307/trend_leader_test"
    )
    # 이 단위 테스트에서 네트워크 연결 시도는 테스트 실패다.
    checkout = Mock(side_effect=AssertionError("checkout"))
    event.listen(engine, "do_connect", checkout)
    with Session(engine) as db:
        yield db
    engine.dispose()
    checkout.assert_not_called()


def rejected(db, **kwargs):
    db.add = Mock(wraps=db.add)
    db.flush = Mock(wraps=db.flush)
    db.commit = Mock(wraps=db.commit)
    db.rollback = Mock(wraps=db.rollback)
    with pytest.raises(DemoTrendSeedError) as error:
        seed_demo_trends(db, **{"app_env": "local", **approval(), **kwargs})
    assert "fake-secret" not in str(error.value)
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize("app_env", ["production", "test", "", None])
def test_non_local_has_no_checkout_or_dml(session, app_env):
    rejected(session, app_env=app_env)


@pytest.mark.parametrize(
    "key,value",
    [
        ("allowed_host", None),
        ("allowed_host", ""),
        ("allowed_database", " "),
        ("allowed_current_user", None),
        ("allowed_current_user", "user"),
        ("allowed_port", None),
        ("allowed_port", 0),
        ("allowed_port", 65536),
        ("allowed_port", "3307"),
        ("allowed_port", True),
        ("allowed_host", 127),
        ("allowed_database", 123),
        ("allowed_current_user", "user@"),
        ("allowed_current_user", "@host"),
    ],
)
def test_incomplete_approval_has_no_checkout_or_dml(session, key, value):
    rejected(session, **{key: value})


def test_omitted_approval_fails_closed(session):
    session.flush = Mock(wraps=session.flush)
    session.commit = Mock(wraps=session.commit)
    session.rollback = Mock(wraps=session.rollback)
    with pytest.raises(DemoTrendSeedError, match="approval_settings"):
        seed_demo_trends(session, app_env="local")
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


@pytest.mark.parametrize("key", list(approval()))
def test_each_missing_approval_is_rejected(session, key):
    rejected(session, **{key: None})


@pytest.mark.parametrize(
    "changes",
    [
        {"allowed_host": "localhost"},
        {"allowed_port": 3306},
        {"allowed_database": "other"},
    ],
)
def test_url_target_mismatch_has_no_checkout_or_dml(session, changes):
    rejected(session, **changes)


def test_pending_new_is_rejected_before_autoflush(session):
    session.add(Trend(title="pending", normalized_title="pending"))
    rejected(session)


def test_unbound_has_no_dml():
    with Session() as db:
        rejected(db)


def test_multibind_has_no_checkout_or_dml(session):
    other = create_engine("mysql+pymysql://test@127.0.0.1:3307/trend_leader_test")
    session.bind_mapper(Trend, other)
    try:
        rejected(session)
    finally:
        other.dispose()


def test_routing_session_is_rejected(session):
    class RoutingSession(Session):
        def get_bind(self, *args, **kwargs):
            return super().get_bind(*args, **kwargs)

    with RoutingSession(session.bind) as db:
        rejected(db)


def test_dataset_contract_without_db():
    seeds = seed_module.DEMO_TRENDS
    assert len(seeds) == 26
    assert sum(len(seed.sources) for seed in seeds) == 29
    assert [seed.normalized_title for seed in seeds] == [
        *(f"demo-trend-list-{i:03}" for i in range(1, 26)),
        "demo-trend-list-hidden-001",
    ]
    assert all(seed.last_collected_at.tzinfo is None for seed in seeds)


class FakeCursor:
    def __init__(self, dbapi):
        self.dbapi = dbapi
        self.description = None
        self.lastrowid = 101
        self.rowcount = 1
        self.rows = []

    def execute(self, statement, parameters=None):
        self.dbapi.statements.append(statement)
        if "DATABASE()" in statement:
            if self.dbapi.error:
                raise RuntimeError("fake-secret raw DBAPI error")
            self.description = [
                (name, None, None, None, None, None, None)
                for name in ("db_name", "authenticated_user")
            ]
            self.rows = [self.dbapi.identity]

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def close(self):
        pass


class FakeDBAPI:
    def __init__(self):
        self.identity = ("trend_leader_test", "seed_manager@%")
        self.error = False
        self.statements = []

    def cursor(self):
        return FakeCursor(self)

    def character_set_name(self):
        return "utf8mb4"

    def rollback(self):
        pass

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fake_engine():
    dbapi = FakeDBAPI()
    engine = create_engine(
        "mysql+pymysql://test:fake-secret@127.0.0.1:3307/trend_leader_test",
        creator=lambda: dbapi,
    )
    # 실제 서버 handshake 대신 모의 DBAPI만 사용한다.
    engine.dialect.initialize = Mock()
    engine.dialect.server_version_info = (10, 11, 0)
    statements = []
    event.listen(
        engine,
        "before_cursor_execute",
        lambda c, u, s, p, x, m: statements.append((c, s)),
    )
    yield engine, dbapi, statements
    engine.dispose()


@pytest.mark.parametrize(
    "identity",
    [
        (None, "seed_manager@%"),
        ("other", "seed_manager@%"),
        ("trend_leader_test", None),
        ("trend_leader_test", "seed_manager@localhost"),
        ("", ""),
    ],
)
def test_identity_mismatch_has_only_read_sql(fake_engine, identity):
    engine, dbapi, statements = fake_engine
    dbapi.identity = identity
    with Session(engine) as db:
        rejected(db)
    assert len(statements) == 1
    assert statements[0][1].startswith("SELECT DATABASE()")


def test_identity_error_is_safe_and_has_no_dml(fake_engine, caplog, capsys):
    engine, dbapi, statements = fake_engine
    dbapi.error = True
    with Session(engine) as db:
        rejected(db)
    assert len(statements) == 1
    assert statements[0][1].startswith("SELECT DATABASE()")
    captured = capsys.readouterr()
    assert "fake-secret" not in caplog.text + captured.out + captured.err


@pytest.mark.parametrize("connection_bound", [False, True])
def test_identity_and_orm_dml_share_connection(
    fake_engine,
    monkeypatch,
    connection_bound,
):
    engine, _, statements = fake_engine
    with engine.connect() as connection:
        outer = connection.begin()
        factory = sessionmaker(
            bind=connection if connection_bound else engine,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        with factory() as db:

            def rows(session):
                session.add(Trend(title="test", normalized_title="guard-test"))
                session.flush()

            monkeypatch.setattr(seed_module, "_seed_demo_rows", rows)
            seed_demo_trends(db, app_env=" LOCAL ", **approval())
        sql_connections = {c for c, s in statements if not s.startswith("SAVEPOINT")}
        assert len(sql_connections) == 1
        assert any("INSERT INTO trends" in s for c, s in statements)
        if connection_bound:
            assert sql_connections == {connection}
            assert outer.is_active
        outer.rollback()


@pytest.mark.parametrize("change", ["invalidate", "close", "binding", "transaction"])
def test_connection_change_blocks_first_orm_dml(fake_engine, monkeypatch, change):
    engine, _, statements = fake_engine
    with Session(engine) as db:

        def rows(session):
            connection = session.connection()
            if change == "invalidate":
                connection.invalidate()
            elif change == "close":
                connection.close()
            elif change == "binding":
                session.bind_mapper(Trend, create_engine("sqlite://"))
            else:
                connection.rollback()
            session.add(Trend(title="test", normalized_title="guard-test"))
            session.flush()

        monkeypatch.setattr(seed_module, "_seed_demo_rows", rows)
        with pytest.raises(
            DemoTrendSeedError,
            match="connection_changed|session_binding",
        ):
            seed_demo_trends(db, app_env="local", **approval())
    assert [s for c, s in statements] == [
        "SELECT DATABASE() AS db_name, CURRENT_USER() AS authenticated_user"
    ]


@pytest.mark.parametrize("change", ["dirty", "deleted"])
def test_pending_existing_objects_do_not_flush(session, change):
    trend = Trend(trend_id=1, title="existing", normalized_title="existing")
    make_transient_to_detached(trend)
    session.add(trend)
    if change == "dirty":
        trend.title = "pending"
    else:
        session.delete(trend)
    rejected(session)


@pytest.mark.parametrize(
    "url",
    [
        "mysql+pymysql://test@127.0.0.1/trend_leader_test",
        "mysql+pymysql://test@127.0.0.1:3307/trend_leader_test?unix_socket=/tmp/fake",
        "mysql+pymysql://test@127.0.0.1:3307/trend_leader_test?host=other",
        "mysql+pymysql://test@[::1]:3307/trend_leader_test",
        "sqlite://",
    ],
)
def test_ambiguous_transport_does_not_checkout(url):
    engine = create_engine(url)
    checkout = Mock(side_effect=AssertionError("checkout"))
    event.listen(engine, "do_connect", checkout)
    with Session(engine) as db:
        rejected(db)
    checkout.assert_not_called()
    engine.dispose()


def test_validation_connection_mismatch_has_no_sql(fake_engine, monkeypatch):
    engine, dbapi, statements = fake_engine
    with engine.connect() as first, engine.connect() as second:
        with Session(first) as db:
            original = db.connection

            def connection(bind_arguments=None, **kwargs):
                if bind_arguments:
                    return second
                return original(**kwargs)

            monkeypatch.setattr(db, "connection", connection)
            rejected(db)
    assert not statements
    assert not any(s.startswith("INSERT") for s in dbapi.statements)


def test_connection_lost_during_identity_is_not_reused(fake_engine, monkeypatch):
    engine, _, statements = fake_engine

    def disconnect(connection, cursor, statement, *args):
        if "DATABASE()" in statement:
            connection.invalidate()

    event.listen(engine, "after_cursor_execute", disconnect)
    rows = Mock()
    monkeypatch.setattr(seed_module, "_seed_demo_rows", rows)
    with Session(engine) as db:
        rejected(db)
    rows.assert_not_called()
    assert len(statements) == 1


def test_guard_is_revalidated_after_rollback_and_listeners_are_removed(
    fake_engine,
    monkeypatch,
):
    engine, dbapi, statements = fake_engine
    monkeypatch.setattr(seed_module, "_seed_demo_rows", lambda db: None)
    with Session(engine) as db:
        dbapi.identity = ("other", "seed_manager@%")
        with pytest.raises(DemoTrendSeedError):
            seed_demo_trends(db, app_env="local", **approval())
        dbapi.identity = ("trend_leader_test", "seed_manager@%")
        seed_demo_trends(db, app_env="local", **approval())
        # 반환 후의 새 Transaction에 이전 판정이나 listener가 남지 않아야 한다.
        db.add(Trend(title="post-seed", normalized_title="post-seed"))
        db.commit()
    assert sum("DATABASE()" in s for c, s in statements) == 2
