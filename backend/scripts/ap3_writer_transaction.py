"""Synthetic SQLite-only AP-3 transaction harness.

No CLI, external candidate input, MariaDB connection or operational APPLY.
SQL uses the current trend table columns. A future isolated MariaDB wrapper
must independently verify target, privileges, journal protection and authority.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal

BATCH_ID = "ap3-synthetic-batch-v1"
FIXTURE_TIME = datetime(2000, 1, 1)
PARENT = "IT_DIGITAL"
CHILD = "소프트웨어·앱"


class FixtureBlocked(RuntimeError):
    """Safe synthetic fixture rejection."""


@dataclass(frozen=True, slots=True)
class SyntheticItem:
    external_id: str
    title: str
    normalized_title: str
    source_url: str
    source_key: str


def _fixture(index: int) -> SyntheticItem:
    external_id = f"synthetic-ap3:release:{index}"
    # Fixture-only SD-011-shaped key. Not a production source-key decision.
    return SyntheticItem(
        external_id, f"Synthetic AP3 release {index}",
        f"synthetic ap3 release {index}", f"https://example.invalid/ap3/{index}",
        sha256(f"ETC:{external_id}".encode()).hexdigest(),
    )


BATCH = (_fixture(1), _fixture(2))
DIGEST = sha256(json.dumps({
    "items": [asdict(item) for item in BATCH], "parent": PARENT, "child": CHILD,
    "status": "HIDDEN", "platform": "ETC", "is_primary": False,
    "fixture_time": FIXTURE_TIME.isoformat(),
}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _verify_memory_database(conn: Connection) -> None:
    # Defend against a file-based/attached database even if a custom creator
    # returned a different connection from the engine URL's stated target.
    databases = conn.exec_driver_sql("PRAGMA database_list").all()
    if [tuple(row) for row in databases] != [(0, "main", "")]:
        raise FixtureBlocked("FIXTURE_DATABASE_NOT_ISOLATED")
    if conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
        raise FixtureBlocked("FIXTURE_FOREIGN_KEYS_DISABLED")


def _category_id(conn: Connection) -> int:
    rows = conn.execute(text(
        "SELECT c.category_id, c.category_name, c.category_code, c.is_active, "
        "p.category_code, p.parent_id, p.is_active FROM categories c "
        "JOIN categories p ON c.parent_id = p.category_id "
        "WHERE p.category_code = :parent AND c.category_name = :child LIMIT 2"
    ), {"parent": PARENT, "child": CHILD}).all()
    if len(rows) != 1 or tuple(rows[0][1:]) != (CHILD, None, 1, PARENT, None, 1):
        raise FixtureBlocked("FIXTURE_CATEGORY_MISSING_OR_AMBIGUOUS")
    return rows[0][0]


def _stage_batch(conn: Connection) -> None:
    """Stage both fixture items, never commit or open another connection."""
    _verify_memory_database(conn)
    _stage_items(conn, BATCH)


def _stage_items(
    conn: Connection, items: tuple[SyntheticItem, ...], *,
    after_item: Callable[[Connection, int, int, int], None] | None = None,
    summary: str | None = None, is_primary: bool = False,
) -> None:
    """Fixture SQL only; caller owns isolation guard and transaction."""
    category_id = _category_id(conn)
    fixture_at = FIXTURE_TIME.isoformat(sep=" ")
    for item in items:
        if conn.execute(text(
            "SELECT 1 FROM trend_sources WHERE platform = :platform "
            "AND (external_id = :external_id OR source_key = :source_key) LIMIT 1"
        ), {"platform": "ETC", "external_id": item.external_id,
            "source_key": item.source_key}).first():
            raise FixtureBlocked("FIXTURE_SOURCE_COLLISION")
        if conn.execute(text(
            "SELECT 1 FROM trends WHERE normalized_title = :title LIMIT 1"
        ), {"title": item.normalized_title}).first():
            raise FixtureBlocked("FIXTURE_TITLE_COLLISION")
    for index, item in enumerate(items):
        trend_id = conn.execute(text(
            "INSERT INTO trends (title, normalized_title, summary, thumbnail_url, "
            "status, first_collected_at, last_collected_at) "
            "VALUES (:title, :normalized, :summary, NULL, 'HIDDEN', :at, :at)"
        ), {"title": item.title, "normalized": item.normalized_title,
            "at": fixture_at, "summary": summary}).lastrowid
        if type(trend_id) is not int or trend_id <= 0:
            raise FixtureBlocked("FIXTURE_INSERT_ID_INVALID")
        conn.execute(text(
            "INSERT INTO trend_sources (trend_id, source_key, source_url, "
            "source_title, platform, collected_at, external_id) VALUES "
            "(:id, :key, :url, NULL, 'ETC', :at, :external_id)"
        ), {"id": trend_id, "key": item.source_key, "url": item.source_url,
            "at": fixture_at, "external_id": item.external_id})
        conn.execute(text(
            "INSERT INTO trend_category_map (trend_id, category_id, is_primary, "
            "created_at) VALUES (:id, :category, :primary, :at)"
        ), {"id": trend_id, "category": category_id, "at": fixture_at,
            "primary": is_primary})
        if after_item is not None:
            after_item(conn, index, trend_id, category_id)


def run_synthetic_batch(engine: Engine, journal: SyntheticJournal) -> str:
    """Journal-first fixture orchestration; never operates on MariaDB.

    A lost commit response is always UNKNOWN. No retry or auto-recovery.
    Finalization failure must propagate instead of reporting success.
    """
    url = engine.url
    if url.drivername not in {"sqlite", "sqlite+pysqlite"} or (
        url.database not in {None, "", ":memory:"} or url.query
    ):
        return "BLOCKED_NON_SYNTHETIC_TARGET"
    attempt = uuid4().hex
    journal.claim(BATCH_ID, DIGEST, attempt)
    state = "COMMIT_UNKNOWN"
    try:
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                _stage_batch(conn)
            except Exception:
                tx.rollback()
                state = "ROLLED_BACK"
            else:
                tx.commit()
                state = "COMMITTED"
    except Exception:
        # Connection/rollback/commit/close error: do not infer no DB changes.
        state = "COMMIT_UNKNOWN"
    except BaseException:
        # A process-level interruption can leave a durable STARTED instead.
        raise
    try:
        journal.finish(BATCH_ID, DIGEST, attempt, state)
    except JournalBlocked:
        return "HOLD_JOURNAL_FINALIZATION"
    return state
