"""No real DB, DML or parent integration fixtures in this suite."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql

from app.repositories.reviewed_demo_repository import ReviewedDemoRepository
from app.services.reviewed_demo_preflight import dry_run, validate_reviewed_input


@pytest.fixture
def candidate():
    return json.loads((Path(__file__).parents[2] / "docs" /
                       "reviewed_demo_ict_20261116.json").read_text(encoding="utf-8"))


@pytest.fixture
def engine():
    engine = create_engine("mysql+pymysql://test:synthetic@127.0.0.1:3309/demo")
    connection = MagicMock()
    engine.connect = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    identity = {"database_name": "demo", "authenticated_user": "demo_user@%"}
    result = connection.execute.return_value
    result.mappings.return_value.one.return_value = identity
    result.mappings.return_value.__iter__.return_value = iter(())
    result.scalars.return_value.__iter__.return_value = iter(())
    yield engine, connection
    engine.dispose()


def test_missing_target_and_category_are_blocked_but_inspection_is_read_only(
    engine, candidate,
):
    db, connection = engine
    report = dry_run(db, data=candidate, app_env="local")
    assert report["status"] == "BLOCKED"
    assert report["dml_allowed"] is False
    assert report["automatic_validation"] == "CITATION_URL_MISMATCH"
    assert "ISOLATED_TARGET_UNCONFIRMED" in report["blockers"]
    assert "ACTIVE_IT_CHILD_SELECTION_REQUIRED" in report["blockers"]
    connection.exec_driver_sql.assert_called_once_with("START TRANSACTION READ ONLY")
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    for call in connection.execute.call_args_list:
        assert str(call.args[0]).lstrip().upper().startswith("SELECT")
    assert "synthetic" not in json.dumps(report)


def test_ready_is_still_read_only_and_uses_observed_child(
    engine, candidate, monkeypatch,
):
    db, connection = engine
    # Test-only ID, never used as a real category selection.
    candidate["category_id"] = 901
    monkeypatch.setattr(ReviewedDemoRepository, "categories", lambda self: [
        {"category_id": 901, "category_name": "fixture", "parent_id": 900},
    ])
    monkeypatch.setattr(ReviewedDemoRepository, "duplicates", lambda self, **kw: {
        "title_trend_ids": [], "source_trend_ids": [], "existing_category_maps": [],
    })
    monkeypatch.setattr(ReviewedDemoRepository, "schema_issues", lambda self: [])
    expected = {"host": "127.0.0.1", "port": 3309, "database": "demo",
                "current_user": "demo_user@%"}
    report = dry_run(db, data=candidate, app_env="local", expected_target=expected)
    assert report["status"] == "DRY_RUN_READY"
    assert report["dml_allowed"] is False
    assert report["plan"]["row_counts"] == {
        "Trend": 1, "TrendSource": 1, "TrendCategoryMap": 1,
    }
    connection.commit.assert_not_called()


@pytest.mark.parametrize("case", ["wrong-user", "wrong-db", "duplicate", "read-error"])
def test_identity_conflict_or_failure_blocks(engine, candidate, monkeypatch, case):
    db, connection = engine
    if case == "wrong-db":
        connection.execute.return_value.mappings.return_value.one.return_value = {
            "database_name": "other", "authenticated_user": "demo_user@%",
        }
    elif case == "duplicate":
        monkeypatch.setattr(ReviewedDemoRepository, "duplicates", lambda self, **kw: {
            "title_trend_ids": [501], "source_trend_ids": [],
            "existing_category_maps": [],
        })
    elif case == "read-error":
        connection.execute.side_effect = RuntimeError("private error never expose")
    report = dry_run(db, data=candidate, app_env="local", expected_target={
        "host": "127.0.0.1", "port": 3309, "database": "demo",
        "current_user": "different@%",
    })
    assert report["status"] == "BLOCKED"
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    assert "private error" not in json.dumps(report)


def test_production_target_has_no_connection(engine, candidate):
    db, _ = engine
    assert dry_run(db, data=candidate, app_env="production")["status"] == "BLOCKED"
    db.connect.assert_not_called()


@pytest.mark.parametrize("change", [
    {"input_kind": "LIVE"}, {"original_failure": "PASS"},
    {"source_url": "http://localhost/private"}, {"title": ""},
    {"category_id": True}, {"review_note": ""},
])
def test_invalid_review_record_rejected(candidate, change):
    candidate.update(change)
    with pytest.raises(ValueError):
        validate_reviewed_input(candidate)


def test_category_query_uses_actual_active_it_children(engine):
    _, connection = engine
    ReviewedDemoRepository(connection).categories()
    sql = str(connection.execute.call_args.args[0].compile(dialect=mysql.dialect()))
    assert "child.parent_id = parent.category_id" in sql
    assert "parent.is_active IS true" in sql
    assert "child.is_active IS true" in sql
    assert "parent.category_code" in sql


@pytest.mark.parametrize("use_url", [False, True])
def test_cli_uses_db_only_settings_and_hides_credentials(
    engine, candidate, tmp_path, monkeypatch, capsys, use_url,
):
    from scripts.reviewed_demo_dry_run import main

    db, connection = engine
    captured_urls = []

    def capture_engine(url, **kwargs):
        captured_urls.append(url)
        return db

    monkeypatch.setattr("sqlalchemy.create_engine", capture_engine)
    input_path = tmp_path / "reviewed.json"
    input_path.write_text(json.dumps(candidate), encoding="utf-8")
    env_path = tmp_path / "db.env"
    env_path.write_text(
        "APP_ENV=local\nDB_HOST=db\nDB_PORT=3306\nDB_NAME=demo\n"
        "DB_USER=demo_user\nDB_PASSWORD=synthetic-cli-secret\n"
        + ("DATABASE_URL=mysql+pymysql://demo_user:synthetic-cli-secret@db:3306/demo\n"
           if use_url else ""), encoding="utf-8",
    )
    assert main(["--input", str(input_path), "--env-file", str(env_path),
                 "--host", "127.0.0.1", "--port", "3309"]) == 1
    assert captured_urls[0].host == "127.0.0.1"
    assert captured_urls[0].port == 3309
    assert "DB_HOST=db\nDB_PORT=3306" in env_path.read_text(encoding="utf-8")
    output = capsys.readouterr()
    assert json.loads(output.out)["dml_allowed"] is False
    assert "synthetic-cli-secret" not in output.out + output.err
    connection.commit.assert_not_called()


def test_cli_invalid_json_never_connects(tmp_path, monkeypatch, capsys):
    from scripts.reviewed_demo_dry_run import main

    create = MagicMock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr("sqlalchemy.create_engine", create)
    path = tmp_path / "invalid.json"
    path.write_text("not-json-private", encoding="utf-8")
    assert main(["--input", str(path), "--env-file", str(path)]) == 1
    create.assert_not_called()
    output = capsys.readouterr()
    assert "not-json-private" not in output.out + output.err


def test_identity_query_avoids_mariadb_reserved_alias(engine):
    _, connection = engine
    identity = ReviewedDemoRepository(connection).identity()
    sql = str(connection.execute.call_args.args[0])
    assert "AS authenticated_user" in sql
    assert "AS current_user" not in sql
    assert identity == {"database_name": "demo", "current_user": "demo_user@%"}


@pytest.mark.parametrize("case", ["matching", "short-string", "missing-column"])
def test_model_schema_field_checks(engine, case):
    from app.models.trend import Trend
    from app.models.trend_category_map import TrendCategoryMap
    from app.models.trend_source import TrendSource

    _, connection = engine
    rows = [
        {"TABLE_NAME": model.__tablename__, "COLUMN_NAME": column.name,
         "IS_NULLABLE": "YES" if column.nullable else "NO",
         "CHARACTER_MAXIMUM_LENGTH": getattr(column.type, "length", None)}
        for model in (Trend, TrendSource, TrendCategoryMap)
        for column in model.__table__.columns
    ]
    if case == "missing-column":
        rows.pop()
    elif case == "short-string":
        next(row for row in rows if row["TABLE_NAME"] == "trends"
             and row["COLUMN_NAME"] == "title")["CHARACTER_MAXIMUM_LENGTH"] = 10
    result = connection.execute.return_value.mappings.return_value
    result.__iter__.return_value = iter(rows)
    issues = ReviewedDemoRepository(connection).schema_issues()
    assert bool(issues) is (case != "matching")
