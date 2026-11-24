"""Stage 1: once-only collector / independent Writer. Never self-activate.

Linux execution principals and a separately provisioned root-owned approval
are required. No config, DB credentials or journal are created by this CLI.
"""

import argparse
import json
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection
from sqlalchemy.pool import NullPool

from app.trend_collection.freshness_policy import validate_snapshot_freshness
from app.trend_collection.godot_release_collector import CollectionError, RateLimited
from app.trend_collection.igdb_adapter import (
    SOURCE_ID as IGDB_SOURCE_ID,
    IgdbBlocked,
)
from app.trend_collection.igdb_client import IgdbClient, IgdbClientError
from app.trend_collection.publication_policy import (
    PersistableSnapshot,
    PopularitySnapshot,
)
from app.trend_collection.supply_adapter import (
    ADAPTERS,
    IgdbOperationalAdapter,
    SupplyBlocked,
    bind_snapshot,
    utc,
)
from scripts.ap3_writer_journal import JournalBlocked, SyntheticJournal
from scripts.ap3_writer_observation import check_table_grants
from scripts.ap3_writer_transaction import _category_id, insert_trend_item

PROFILE = "AUTO-TREND-MVP"
VERSION = "AUTO_V1"
CONTROL = Path("/etc/trend-leader/auto-supply")
JOURNAL_PATH = Path("/var/lib/trend-leader/auto-supply/journal.sqlite3")
MAX_INPUT = 65536
RIGHTS = {"access": "ALLOWED", "storage": "ALLOWED", "display": "ALLOWED",
          "ai_transfer": "DENIED"}


def now_utc():
    return datetime.now(timezone.utc)


def _json(data: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SupplyBlocked("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    return json.loads(data, object_pairs_hook=unique)


@dataclass(frozen=True, slots=True)
class ApprovedSource:
    source_id: str
    scope: str
    rights_ref: str


@dataclass(frozen=True, slots=True)
class ApprovedProfile:
    sources: tuple[ApprovedSource, ...]
    environment: str
    collector_uid: int
    writer_uid: int
    port: int
    database: str
    current_user: str
    journal_id: str
    journal_device: int
    journal_inode: int
    approved_at: str
    valid_until: str
    approved_by: str
    g5_ref: str
    g6_ref: str

    @property
    def username(self):
        return self.current_user.partition("@")[0]

    @property
    def target(self):
        return (f"{self.environment}:127.0.0.1:{self.port}/"
                f"{self.database}/{self.current_user}")

    def source(self, source_id: str | None) -> ApprovedSource:
        if source_id is None and len(self.sources) == 1:
            return self.sources[0]
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise SupplyBlocked("SOURCE_NOT_APPROVED")

    def validate_time(self, now):
        if not utc(self.approved_at) <= now < utc(self.valid_until):
            raise SupplyBlocked("APPROVAL_OUTSIDE_VALIDITY")


def parse_profile(raw, now: datetime) -> ApprovedProfile:
    """Schema/meaning check only. Trust comes from protected file + principal."""
    if type(raw) is not dict or raw.get("enabled") is not True:
        raise SupplyBlocked("OPERATION_DISABLED")
    keys = set(ApprovedProfile.__dataclass_fields__)
    if set(raw) != keys | {"enabled", "profile_id", "policy_version"}:
        raise SupplyBlocked("APPROVAL_SCHEMA_MISMATCH")
    if raw["profile_id"] != PROFILE or raw["policy_version"] != VERSION:
        raise SupplyBlocked("APPROVAL_VERSION_MISMATCH")
    sources = raw["sources"]
    if type(sources) is not list or not 1 <= len(sources) <= len(ADAPTERS):
        raise SupplyBlocked("SOURCE_SCOPE_NOT_APPROVED")
    approved = []
    for entry in sources:
        if (type(entry) is not dict or set(entry) != {
            "source_id", "scope", "rights", "rights_ref",
        }):
            raise SupplyBlocked("SOURCE_SCOPE_NOT_APPROVED")
        source = entry["source_id"]
        if (not isinstance(source, str) or source not in ADAPTERS
                or entry["scope"] != ADAPTERS[source].scope
                or entry["rights"] != RIGHTS
                or any(item.source_id == source for item in approved)):
            raise SupplyBlocked("SOURCE_SCOPE_NOT_APPROVED")
        approved.append(ApprovedSource(source, entry["scope"], entry["rights_ref"]))
    values = {key: raw[key] for key in keys}
    values["sources"] = tuple(approved)
    profile = ApprovedProfile(**values)
    if (profile.environment not in {"local", "lightsail"}
            or type(profile.port) is not int or profile.port not in {3306, 3309}
            or not isinstance(profile.database, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", profile.database)
            or profile.database in {"mysql", "sys", "information_schema",
                                    "performance_schema"}
            or "test" in profile.database
            or not isinstance(profile.current_user, str)
            or not re.fullmatch(r"trend_auto_writer@[a-zA-Z0-9.:-]{1,255}",
                                profile.current_user)):
        raise SupplyBlocked("TARGET_NOT_APPROVED")
    for uid in (profile.collector_uid, profile.writer_uid):
        if type(uid) is not int or uid <= 0:
            raise SupplyBlocked("EXECUTION_PRINCIPAL_INVALID")
    if profile.collector_uid == profile.writer_uid:
        raise SupplyBlocked("EXECUTION_PRINCIPAL_INVALID")
    if (not isinstance(profile.journal_id, str)
            or not re.fullmatch(r"[a-f0-9]{32}", profile.journal_id)
            or type(profile.journal_device) is not int or profile.journal_device < 0
            or type(profile.journal_inode) is not int or profile.journal_inode <= 0):
        raise SupplyBlocked("JOURNAL_ANCHOR_INVALID")
    for value in (profile.approved_by, profile.g5_ref, profile.g6_ref,
                  *(source.rights_ref for source in profile.sources)):
        if (not isinstance(value, str) or not 1 <= len(value.strip()) <= 500
                or value.strip().upper() in {"PASS", "TRUE", "ALLOWED", "TODO"}):
            raise SupplyBlocked("APPROVAL_EVIDENCE_MISSING")
    profile.validate_time(now)
    return profile


def _root_directory(path: Path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise SupplyBlocked("UNPROTECTED_CONTROL_DIRECTORY")


def _root_file(path: Path, *, secret=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_nlink != 1
                or (secret and info.st_mode & 0o007)):
            raise SupplyBlocked("UNPROTECTED_CONTROL_FILE")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def _bounded(stream):
    data = stream.read(MAX_INPUT + 1)
    if not data or len(data) > MAX_INPUT:
        raise SupplyBlocked("INPUT_SIZE_INVALID")
    return data


def _igdb_query(role: str):
    """Bind a fresh IGDB client to only the currently executing Linux role."""
    if role not in {"collect", "write"}:
        raise SupplyBlocked("IGDB_EXECUTION_ROLE_INVALID")
    # Administrator-provisioned files only; no .env, token cache or stdout.
    # Each file must be root-owned, 0640, with the executing role's group.
    path = CONTROL / f"igdb-{role}-credentials.json"
    try:
        with _root_file(path, secret=True) as stream:
            info = os.fstat(stream.fileno())
            if (info.st_gid != os.getegid()
                    or info.st_mode & 0o077 != 0o040):
                raise SupplyBlocked("IGDB_CREDENTIAL_SCOPE_INVALID")
            credentials = _json(_bounded(stream))
    except (FileNotFoundError, PermissionError):
        raise SupplyBlocked("IGDB_CREDENTIALS_UNAVAILABLE") from None
    if type(credentials) is not dict or set(credentials) != {
        "client_id", "client_secret",
    }:
        raise SupplyBlocked("IGDB_CREDENTIALS_INVALID")
    try:
        return IgdbClient(
            credentials["client_id"], credentials["client_secret"],
        ).query
    except IgdbClientError:
        raise SupplyBlocked("IGDB_CREDENTIALS_INVALID") from None


def _operational_adapter(source: ApprovedSource, role: str):
    """Static registry scope plus separately supplied principal-scoped secrets."""
    if source.source_id == IGDB_SOURCE_ID:
        return IgdbOperationalAdapter(_igdb_query(role))
    return ADAPTERS[source.source_id]


@contextmanager
def approved_cycle(role: str) -> Iterator[ApprovedProfile]:
    """Single-host lock shared with the independent approval/revocation operator."""
    if sys.platform != "linux" or os.geteuid() == 0 or os.getuid() != os.geteuid():
        raise SupplyBlocked("PROTECTED_LINUX_PRINCIPAL_REQUIRED")
    import fcntl

    _root_directory(CONTROL)
    # Administrator must keep this inode stable and use the same lock for changes.
    with _root_file(CONTROL / "control.lock") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        profile = _read_profile()
        uid = profile.collector_uid if role == "collect" else profile.writer_uid
        if role not in {"collect", "write"} or os.geteuid() != uid:
            raise SupplyBlocked("EXECUTION_PRINCIPAL_MISMATCH")
        yield profile


def _read_profile():
    with _root_file(CONTROL / "approval.json") as stream:
        return parse_profile(_json(_bounded(stream)), now_utc())


def _assert_current(profile: ApprovedProfile, snapshot: PersistableSnapshot):
    # Defense in depth; the shared control lock, not this read, orders revocation.
    if _read_profile() != profile:
        raise SupplyBlocked("APPROVAL_CHANGED")
    now = now_utc()
    profile.validate_time(now)
    validate_snapshot_freshness(profile, snapshot, now)


class OperationalJournal(SyntheticJournal):
    profile_id = PROFILE
    policy_version = VERSION
    mode = "AUTHORIZED_OPERATIONAL"

    def __init__(self, profile: ApprovedProfile):
        self.target = profile.target
        self._profile = profile
        super().__init__(JOURNAL_PATH, profile.journal_id)

    def _connect(self):
        _root_directory(self._path.parent.parent)
        directory = self._path.parent.lstat()
        info = self._path.lstat()
        if (not stat.S_ISDIR(directory.st_mode)
                or directory.st_uid != self._profile.writer_uid
                or directory.st_mode & 0o077 or not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._profile.writer_uid or info.st_mode & 0o077
                or info.st_nlink != 1 or (info.st_dev, info.st_ino) != (
                    self._profile.journal_device, self._profile.journal_inode,
                )):
            raise JournalBlocked("OPERATIONAL_JOURNAL_ANCHOR_MISMATCH")
        return super()._connect()

    def initialize_for_synthetic_test(self):
        raise JournalBlocked("OPERATIONAL_JOURNAL_REQUIRES_ADMIN_PROVISIONING")


def _make_engine(profile: ApprovedProfile):
    import pwd

    with _root_file(CONTROL / "writer-password", secret=True) as stream:
        info = os.fstat(stream.fileno())
        collector = pwd.getpwuid(profile.collector_uid)
        collector_groups = os.getgrouplist(collector.pw_name, collector.pw_gid)
        if (info.st_gid in collector_groups or not info.st_mode & 0o040
                or info.st_gid not in {os.getegid(), *os.getgroups()}):
            raise SupplyBlocked("WRITER_SECRET_SCOPE_INVALID")
        password = _bounded(stream).decode("utf-8").rstrip("\r\n")
    if not password or "\n" in password or "\r" in password:
        raise SupplyBlocked("WRITER_SECRET_INVALID")
    url = URL.create("mysql+pymysql", username=profile.username, password=password,
                     host="127.0.0.1", port=profile.port, database=profile.database)
    return create_engine(url, poolclass=NullPool, hide_parameters=True,
                         connect_args={"connect_timeout": 5, "charset": "utf8mb4",
                                       "read_timeout": 30, "write_timeout": 30})


def _verify_session(conn: Connection, profile: ApprovedProfile):
    database, account, role, version = conn.exec_driver_sql(
        "SELECT DATABASE(), CURRENT_USER(), CURRENT_ROLE(), VERSION()"
    ).one()
    if ((database, account, role) != (profile.database, profile.current_user, None)
            or not isinstance(version, str) or "mariadb" not in version.lower()):
        raise SupplyBlocked("WRITER_SESSION_MISMATCH")
    check_table_grants(conn.exec_driver_sql("SHOW GRANTS").scalars().all(),
                       profile.database, profile.current_user)
    if conn.exec_driver_sql("SHOW GRANTS FOR PUBLIC").all():
        raise SupplyBlocked("PUBLIC_GRANTS_PRESENT")
    engines = conn.exec_driver_sql(
        "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN "
        "('categories','trends','trend_sources','trend_category_map')"
    ).all()
    if dict(engines) != {name: "InnoDB" for name in (
        "categories", "trends", "trend_sources", "trend_category_map",
    )} or tuple(conn.exec_driver_sql(
        "SELECT @@session.foreign_key_checks, @@session.unique_checks"
    ).one()) != (1, 1):
        raise SupplyBlocked("WRITER_STORAGE_MISMATCH")


def inspect_snapshot(conn: Connection, snapshot: PersistableSnapshot) -> str:
    """Source-independent identity and key collision handling, including HIDDEN."""
    rows = conn.execute(text(
        "SELECT external_id, source_key FROM trend_sources WHERE platform = :platform "
        "AND (external_id = :external_id OR source_key = :source_key) LIMIT 2"
    ), {"platform": snapshot.platform, "external_id": snapshot.external_id,
        "source_key": snapshot.source_key}).all()
    if rows:
        expected = [(snapshot.external_id, snapshot.source_key)]
        if [tuple(row) for row in rows] == expected:
            if type(snapshot) is PopularitySnapshot:
                urls = conn.execute(text(
                    "SELECT source_url FROM trend_sources WHERE platform = :platform "
                    "AND external_id = :external_id AND source_key = :source_key "
                    "LIMIT 2"
                ), {"platform": snapshot.platform,
                    "external_id": snapshot.external_id,
                    "source_key": snapshot.source_key}).all()
                if len(urls) != 1 or urls[0][0] != snapshot.source_url:
                    raise SupplyBlocked("SOURCE_URL_CHANGED")
            return "SKIP_EXISTING_RELEASE"
        raise SupplyBlocked("SOURCE_IDENTITY_COLLISION")
    if conn.execute(text(
        "SELECT trend_id FROM trends WHERE normalized_title = :title LIMIT 1"
    ), {"title": snapshot.normalized_title}).first() is not None:
        raise SupplyBlocked("TITLE_COLLISION")
    return "NEW"


def _write(profile: ApprovedProfile, snapshot: PersistableSnapshot, journal) -> str:
    """Caller holds control lock and has independently verified source scope."""
    if (snapshot.profile_id != PROFILE or snapshot.policy_version != VERSION
            or snapshot.target != profile.target or snapshot.proposed_status != "ACTIVE"
            or snapshot.is_primary is not True):
        raise SupplyBlocked("SNAPSHOT_TARGET_MISMATCH")
    _assert_current(profile, snapshot)
    journal.check_ready()
    engine = _make_engine(profile)
    batch_id = "auto-" + sha256(snapshot.candidate_identity.encode()).hexdigest()
    attempt, digest = uuid4().hex, snapshot.content_digest
    claimed = False
    state = "COMMIT_UNKNOWN"
    result = "HOLD"
    try:
        with engine.connect() as conn:
            _verify_session(conn, profile)
            conn.rollback()
            conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            conn.exec_driver_sql("START TRANSACTION")
            if conn.exec_driver_sql("SELECT @@in_transaction").scalar_one() != 1:
                raise SupplyBlocked("TRANSACTION_NOT_ACTIVE")
            # Parent and child locks stay in the same transaction until commit.
            category_id = _category_id(conn, snapshot.parent_code, snapshot.child_name,
                                       lock=True)
            if inspect_snapshot(conn, snapshot) == "SKIP_EXISTING_RELEASE":
                conn.rollback()
                return "SKIP_EXISTING_RELEASE"
            journal.claim(batch_id, digest, attempt)
            claimed = True
            try:
                _verify_session(conn, profile)
                if conn.exec_driver_sql("SELECT @@in_transaction").scalar_one() != 1:
                    raise SupplyBlocked("TRANSACTION_NOT_ACTIVE")
                _assert_current(profile, snapshot)
                insert_trend_item(
                    conn, snapshot, category_id=category_id,
                    collected_at=utc(snapshot.observed_at_utc).replace(tzinfo=None),
                    summary=snapshot.summary, is_primary=True,
                    status="ACTIVE", platform=snapshot.platform,
                )
                _assert_current(profile, snapshot)
            except Exception:
                conn.rollback()
                state = "ROLLED_BACK"
            else:
                conn.commit()
                state, result = "COMMITTED", "COMMITTED"
    except Exception:
        # Any error after claiming, including lost commit response, stops replay.
        state, result = "COMMIT_UNKNOWN", "HOLD"
    finally:
        engine.dispose()
    if claimed:
        journal.finish(batch_id, digest, attempt, state)
    return result


def run_writer(profile: ApprovedProfile, envelope: dict) -> dict:
    if (type(envelope) is not dict or set(envelope) != {"source_id", "preview"}
            or not isinstance(envelope["source_id"], str)):
        raise SupplyBlocked("SOURCE_ENVELOPE_MISMATCH")
    source = profile.source(envelope["source_id"])
    snapshot = _operational_adapter(source, "write").verify(
        envelope["preview"], now_utc(),
    )
    bound = bind_snapshot(snapshot, policy=VERSION, target=profile.target)
    result = _write(profile, bound, OperationalJournal(profile))
    return {"status": result, "candidate_identity": snapshot.candidate_identity}


def collect_envelope(source: ApprovedSource, *, after_game_id=None) -> dict:
    """Collector-only output; no candidate is not a publication authorization."""
    if after_game_id is not None and (
        source.source_id != IGDB_SOURCE_ID
        or type(after_game_id) is not int
        or not 1 <= after_game_id < 10**20
    ):
        raise SupplyBlocked("GAME_CURSOR_INVALID")
    adapter = _operational_adapter(source, "collect")
    if source.source_id == IGDB_SOURCE_ID:
        preview = adapter.collect_preview(after_game_id=after_game_id)
    else:
        preview = adapter.collect_preview()
    if preview is None:
        if source.source_id != IGDB_SOURCE_ID:
            raise SupplyBlocked("SOURCE_PREVIEW_MISSING")
        return {"source_id": source.source_id, "status": "NO_ELIGIBLE_CANDIDATE"}
    if type(preview) is not dict:
        raise SupplyBlocked("SOURCE_PREVIEW_INVALID")
    return {"source_id": source.source_id, "preview": preview}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("collect", "write"))
    parser.add_argument("--source-id")
    parser.add_argument("--after-game-id", type=int)
    args = parser.parse_args()
    if args.role == "write" and (
        args.source_id is not None or args.after_game_id is not None
    ):
        parser.error("--source-id and --after-game-id are for collect only")
    try:
        envelope = _json(_bounded(sys.stdin.buffer)) if args.role == "write" else None
        with approved_cycle(args.role) as profile:
            if args.role == "collect":
                source = profile.source(args.source_id)
                result = collect_envelope(
                    source, after_game_id=args.after_game_id,
                )
                profile.validate_time(now_utc())
                print(json.dumps(result, ensure_ascii=False))
                return 0
            result = run_writer(profile, envelope)
    except RateLimited as exc:
        result = {"status": "HOLD", "reason": "RATE_LIMITED",
                  "retry_not_before": exc.retry_not_before}
    except (CollectionError, SupplyBlocked, JournalBlocked, IgdbBlocked) as exc:
        result = {"status": "HOLD", "reason": str(exc)}
    except Exception:
        # Do not print raw config, SQL, credentials or upstream content.
        result = {"status": "HOLD", "reason": "OPERATION_FAILED"}
    print(json.dumps({**result, "profile": PROFILE}))
    return 0 if result["status"] in {"COMMITTED", "SKIP_EXISTING_RELEASE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
