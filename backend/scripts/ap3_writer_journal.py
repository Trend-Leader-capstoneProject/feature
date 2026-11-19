"""AP-3 synthetic harness journal prototype (no operational approval).

SQLite provides durable claims and atomic state transitions in the test harness.
A real protected directory, independent authority and revocation coordination
must be verified before this journal can be used with a MariaDB writer.
"""

import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PROFILE = "AP3_SYNTHETIC_SQLITE"
POLICY = "SYNTHETIC_V1"
TARGET = "SQLITE_MEMORY_TEST"
MODE = "SYNTHETIC_TEST_ONLY"
TERMINAL = frozenset({"COMMITTED", "ROLLED_BACK", "COMMIT_UNKNOWN"})


class JournalBlocked(RuntimeError):
    """Safe fail-closed diagnostic; never include paths or raw data."""


class SyntheticJournal:
    """Explicitly provisioned test journal; never auto-create on open."""

    profile_id = PROFILE
    target = TARGET
    policy_version = POLICY
    mode = MODE

    def __init__(self, path: Path, journal_id: str) -> None:
        if not path.is_absolute() or not re.fullmatch(r"[a-f0-9]{32}", journal_id):
            raise JournalBlocked("JOURNAL_CONFIG_INVALID")
        self._path = path
        self._journal_id = journal_id

    def _connect(self) -> sqlite3.Connection:
        if self._path.is_symlink() or not self._path.is_file():
            raise JournalBlocked("JOURNAL_UNAVAILABLE")
        conn = sqlite3.connect(
            self._path.as_uri() + "?mode=rw", uri=True, timeout=0,
        )
        try:
            conn.execute("PRAGMA synchronous=FULL")
            if conn.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                raise JournalBlocked("JOURNAL_MODE_UNEXPECTED")
        except BaseException:
            conn.close()
            raise
        return conn

    def initialize_for_synthetic_test(self) -> None:
        """Explicit one-time provisioning in an independently prepared path.

        Never called by a writer. If provisioning fails, leave the file for
        investigation; never replace, repair or initialize it automatically.
        """
        try:
            fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("CREATE TABLE identity (journal_id TEXT PRIMARY KEY)")
                conn.execute("INSERT INTO identity VALUES (?)", (self._journal_id,))
                conn.execute(
                    "CREATE TABLE attempts (batch_id TEXT PRIMARY KEY, "
                    "digest TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE, "
                    "profile_id TEXT NOT NULL, policy_version TEXT NOT NULL, "
                    "target TEXT NOT NULL, mode TEXT NOT NULL, "
                    "investigation_ref TEXT NOT NULL, "
                    "state TEXT NOT NULL CHECK (state IN "
                    "('STARTED','COMMITTED','ROLLED_BACK','COMMIT_UNKNOWN')))"
                )
                conn.commit()
            finally:
                conn.close()
        except (OSError, sqlite3.Error):
            raise JournalBlocked("JOURNAL_INITIALIZATION_FAILED") from None

    @contextmanager
    def _locked(self) -> Iterator[sqlite3.Connection]:
        try:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                if (
                    conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                    or conn.execute("SELECT journal_id FROM identity").fetchall()
                    != [(self._journal_id,)]
                ):
                    raise JournalBlocked("JOURNAL_INTEGRITY_OR_IDENTITY_MISMATCH")
                if conn.execute(
                    "SELECT 1 FROM attempts WHERE profile_id <> ? "
                    "OR policy_version <> ? OR target <> ? OR mode <> ? "
                    "OR investigation_ref <> attempt_id "
                    "OR state NOT IN ('STARTED','COMMITTED','ROLLED_BACK',"
                    "'COMMIT_UNKNOWN') LIMIT 1",
                    (self.profile_id, self.policy_version, self.target, self.mode),
                ).fetchone():
                    raise JournalBlocked("JOURNAL_RECORD_MISMATCH")
                yield conn
                conn.commit()
            finally:
                conn.close()
        except (OSError, sqlite3.Error):
            raise JournalBlocked("JOURNAL_UNAVAILABLE_OR_LOCKED") from None

    def check_ready(self) -> None:
        """Read the protected journal before opening an operational connector."""
        with self._locked() as conn:
            if conn.execute(
                "SELECT 1 FROM attempts WHERE state IN "
                "('STARTED','COMMIT_UNKNOWN') LIMIT 1"
            ).fetchone():
                raise JournalBlocked("JOURNAL_UNRESOLVED_ATTEMPT")

    def claim(self, batch_id: str, digest: str, attempt_id: str) -> None:
        """Commit STARTED before any trend DML. Claims serialize all attempts.

        BEGIN IMMEDIATE serializes the claim; the durable STARTED record then
        blocks all other claims until finalization. No revocation integration.
        """
        if (
            not re.fullmatch(r"[a-z0-9_-]{1,80}", batch_id)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or not re.fullmatch(r"[a-f0-9]{32}", attempt_id)
        ):
            raise JournalBlocked("JOURNAL_CLAIM_INVALID")
        with self._locked() as conn:
            if conn.execute(
                "SELECT 1 FROM attempts WHERE state IN "
                "('STARTED','COMMIT_UNKNOWN') LIMIT 1"
            ).fetchone():
                raise JournalBlocked("JOURNAL_UNRESOLVED_ATTEMPT")
            if conn.execute(
                "SELECT 1 FROM attempts WHERE batch_id = ?", (batch_id,),
            ).fetchone():
                raise JournalBlocked("JOURNAL_BATCH_ALREADY_ATTEMPTED")
            conn.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'STARTED')",
                (batch_id, digest, attempt_id, self.profile_id, self.policy_version,
                 self.target, self.mode, attempt_id),
            )

    def finish(
        self, batch_id: str, digest: str, attempt_id: str, state: str,
    ) -> None:
        if state not in TERMINAL:
            raise JournalBlocked("JOURNAL_TERMINAL_STATE_INVALID")
        with self._locked() as conn:
            changed = conn.execute(
                "UPDATE attempts SET state = ? WHERE batch_id = ? AND digest = ? "
                "AND attempt_id = ? AND state = 'STARTED'",
                (state, batch_id, digest, attempt_id),
            ).rowcount
            if changed != 1:
                raise JournalBlocked("JOURNAL_FINALIZATION_MISMATCH")
