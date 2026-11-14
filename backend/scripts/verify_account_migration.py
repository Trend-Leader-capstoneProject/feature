"""Explicit, guarded migration recovery verification on an empty local test DB."""

import argparse
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.operations import Operations
from dotenv import dotenv_values
from sqlalchemy import bindparam, create_engine, inspect, text
from sqlalchemy.engine import make_url

from alembic import command

BACKEND = Path(__file__).resolve().parents[1]
HEAD = "b7f2c81d9e04"
PREVIOUS = "a4d7c9e21f3b"


def test_url():
    url = dotenv_values(BACKEND / ".env.test").get("TEST_DATABASE_URL") or ""
    target = make_url(url)
    if (
        target.host not in {"127.0.0.1", "localhost"}
        or target.port != 3307
        or target.database != "trend_leader_test"
    ):
        raise RuntimeError(
            "Migration verification requires local trend_leader_test:3307"
        )
    return url


def verify(apply=False):
    url = test_url()
    os.environ.update(
        DATABASE_URL=url, TEST_DATABASE_URL=url, MAINTENANCE_ENABLED="false"
    )
    os.environ.setdefault(
        "JWT_SECRET_KEY", "migration-verification-only-key-at-least-32-characters"
    )
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    ids = []
    result = {"database": "trend_leader_test", "port": 3307}
    with engine.connect() as db:
        assert db.scalar(text("SELECT DATABASE()")) == "trend_leader_test"
        if db.scalar(text("SELECT COUNT(*) FROM users")):
            raise RuntimeError(
                "Refusing migration simulation: test accounts already exist"
            )
        for table in [
            "auth_sessions",
            "auth_refresh_tokens",
            "profile_image_cleanup_jobs",
        ]:
            if table in inspect(db).get_table_names() and db.scalar(
                text(f"SELECT COUNT(*) FROM {table}")
            ):
                raise RuntimeError(
                    "Refusing migration simulation: auth/file records exist"
                )
    if not apply:
        engine.dispose()
        return {**result, "eligible_empty_test_database": True, "applied": False}
    try:
        command.downgrade(cfg, PREVIOUS)
        with engine.begin() as db:
            for _ in range(4):
                inserted = db.execute(
                    text(
                        "INSERT INTO users (login_id,name,status) "
                        "VALUES (:login,'migration fixture','ACTIVE')"
                    ),
                    {"login": "migrate_" + uuid4().hex[:20]},
                )
                ids.append(inserted.lastrowid)
            for user_id, nickname in zip(
                ids[:3], ["Trend123", "trend123", "가나"], strict=True
            ):
                db.execute(
                    text(
                        "INSERT INTO user_profiles(user_id,nickname) "
                        "VALUES(:id,:nickname)"
                    ),
                    {"id": user_id, "nickname": nickname},
                )

        def rejected(message):
            try:
                command.upgrade(cfg, HEAD)
            except RuntimeError as exc:
                assert message in str(exc)
            else:
                raise AssertionError("Expected preflight rejection")
            with engine.connect() as db:
                assert (
                    db.scalar(text("SELECT version_num FROM alembic_version"))
                    == PREVIOUS
                )
                assert "auth_sessions" not in inspect(db).get_table_names()
                assert "nickname_key" not in {
                    c["name"] for c in inspect(db).get_columns("user_profiles")
                }

        rejected("Nickname collision")
        result["case_insensitive_collision_stops_before_ddl"] = True
        with engine.begin() as db:
            db.execute(
                text("DELETE FROM user_profiles WHERE user_id=:id"), {"id": ids[1]}
            )
            db.execute(
                text(
                    "UPDATE user_profiles SET nickname='invalid nickname' "
                    "WHERE user_id=:id"
                ),
                {"id": ids[2]},
            )
        rejected("Nickname preflight failed")
        result["invalid_nickname_stops_before_ddl"] = True
        with engine.begin() as db:
            db.execute(
                text("UPDATE user_profiles SET nickname=:name WHERE user_id=:id"),
                {"name": "가나", "id": ids[2]},
            )
            db.execute(
                text("UPDATE users SET status='SUSPENDED' WHERE user_id=:id"),
                {"id": ids[3]},
            )
        rejected("Unexpected account status")
        with engine.begin() as db:
            db.execute(
                text("UPDATE users SET status='ACTIVE' WHERE user_id=:id"),
                {"id": ids[3]},
            )
        result["unexpected_status_stops_before_ddl"] = True

        original_create = Operations.create_table

        class SimulatedInterruption(RuntimeError):
            pass

        def stop_after_sessions(self, name, *columns, **kwargs):
            table = original_create(self, name, *columns, **kwargs)
            if name == "auth_sessions":
                raise SimulatedInterruption("After durable DDL, before backfill")
            return table

        Operations.create_table = stop_after_sessions
        try:
            try:
                command.upgrade(cfg, HEAD)
            except SimulatedInterruption:
                pass
            else:
                raise AssertionError("DDL interruption was not injected")
        finally:
            Operations.create_table = original_create
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT version_num FROM alembic_version")) == PREVIOUS
            )
            assert "auth_sessions" in inspect(db).get_table_names()
            key = next(
                c
                for c in inspect(db).get_columns("user_profiles")
                if c["name"] == "nickname_key"
            )
            assert key["nullable"]
        command.upgrade(cfg, HEAD)
        result["partial_ddl_resume"] = True

        def profiles():
            with engine.connect() as db:
                return {
                    row.user_id: (row.nickname, row.nickname_key)
                    for row in db.execute(
                        text("SELECT user_id,nickname,nickname_key FROM user_profiles")
                    )
                }

        before = profiles()
        assert len(before) == 4 and before[ids[0]] == ("Trend123", "trend123")
        assert before[ids[2]] == ("가나", "가나")
        for user_id in [ids[1], ids[3]]:
            assert re.fullmatch(r"임시닉네임[A-Z0-9]{5}", before[user_id][0])
            assert len(before[user_id][0]) == 10
        assert len({key for _, key in before.values()}) == 4
        result["backfill_and_nfc"] = True
        command.stamp(cfg, PREVIOUS)
        command.upgrade(cfg, HEAD)
        assert profiles() == before
        result["repeat_does_not_reissue_nickname"] = True
        with engine.connect() as db:
            columns = {c["name"]: c for c in inspect(db).get_columns("user_profiles")}
            assert columns["nickname"]["type"].length == 10
            assert columns["nickname_key"]["nullable"] is False
            assert any(
                c["name"] == "uq_user_profiles_nickname_key"
                for c in inspect(db).get_unique_constraints("user_profiles")
            )
        result["final_constraints"] = True
    finally:
        try:
            if ids:
                with engine.begin() as db:
                    db.execute(
                        text("DELETE FROM users WHERE user_id IN :ids").bindparams(
                            bindparam("ids", expanding=True)
                        ),
                        {"ids": ids},
                    )
            command.upgrade(cfg, HEAD)
        finally:
            engine.dispose()
    return {**result, "restored_revision": HEAD, "applied": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Only on the approved empty 3307 test DB"
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.apply)))
