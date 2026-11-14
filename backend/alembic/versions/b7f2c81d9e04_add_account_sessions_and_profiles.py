"""Add account profiles, login sessions and durable image cleanup.

Revision ID: b7f2c81d9e04
Revises: a4d7c9e21f3b
MariaDB DDL is not globally transactional. Run during the approved write pause.
"""

import re
import secrets
import string
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "b7f2c81d9e04"
down_revision = "a4d7c9e21f3b"
branch_labels = None
depends_on = None

KEY_TYPE = sa.String(10, collation="utf8mb4_bin")


def _nickname(value):
    if not isinstance(value, str):
        raise RuntimeError("Nickname preflight failed")
    display = unicodedata.normalize("NFC", value.strip())
    if not re.fullmatch(r"[가-힣A-Za-z0-9_]{2,10}", display):
        raise RuntimeError("Nickname preflight failed")
    return display, display.lower()


def _inspect():
    return sa.inspect(op.get_bind())


def upgrade():
    if op.get_context().as_sql:
        raise RuntimeError("Data preflight requires an online, explicitly selected DB")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT COUNT(*) FROM users WHERE status <> 'ACTIVE'")):
        raise RuntimeError("Unexpected account status; review before migration")
    existing = list(
        bind.execute(
            sa.text("SELECT profile_id, user_id, nickname FROM user_profiles")
        ).mappings()
    )
    keys = set()
    normalized = []
    for row in existing:
        display, key = _nickname(row["nickname"])
        if key in keys:
            raise RuntimeError("Nickname collision; review before migration")
        keys.add(key)
        normalized.append((row["profile_id"], display, key))

    # MariaDB DDL commits implicitly. Each step is repeatable after partial failure.
    with op.get_context().autocommit_block():
        columns = {col["name"]: col for col in _inspect().get_columns("user_profiles")}
        if "nickname_key" not in columns:
            op.add_column(
                "user_profiles", sa.Column("nickname_key", KEY_TYPE, nullable=True)
            )
        if "auth_sessions" not in _inspect().get_table_names():
            op.create_table(
                "auth_sessions",
                sa.Column(
                    "session_id", sa.CHAR(36, collation="utf8mb4_bin"), primary_key=True
                ),
                sa.Column(
                    "user_id",
                    sa.BigInteger(),
                    sa.ForeignKey("users.user_id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("created_at", sa.DateTime(), nullable=False),
                sa.Column("expires_at", sa.DateTime(), nullable=False),
                sa.Column("revoked_at", sa.DateTime(), nullable=True),
                sa.Column("current_generation", sa.BigInteger(), nullable=False),
                mysql_engine="InnoDB",
            )
        for name, column in (
            ("ix_auth_sessions_user_id", "user_id"),
            ("ix_auth_sessions_expires_at", "expires_at"),
        ):
            if name not in {i["name"] for i in _inspect().get_indexes("auth_sessions")}:
                op.create_index(name, "auth_sessions", [column])
        if "auth_refresh_tokens" not in _inspect().get_table_names():
            op.create_table(
                "auth_refresh_tokens",
                sa.Column(
                    "token_id", sa.BigInteger(), primary_key=True, autoincrement=True
                ),
                sa.Column(
                    "session_id",
                    sa.CHAR(36, collation="utf8mb4_bin"),
                    sa.ForeignKey("auth_sessions.session_id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column(
                    "token_hash", sa.CHAR(64, collation="utf8mb4_bin"), nullable=False
                ),
                sa.Column("generation", sa.BigInteger(), nullable=False),
                sa.Column("issued_at", sa.DateTime(), nullable=False),
                sa.Column("used_at", sa.DateTime(), nullable=True),
                sa.UniqueConstraint(
                    "token_hash", name="uq_auth_refresh_tokens_token_hash"
                ),
                sa.UniqueConstraint(
                    "session_id", "generation", name="uq_auth_refresh_tokens_generation"
                ),
                mysql_engine="InnoDB",
            )
        if "profile_image_cleanup_jobs" not in _inspect().get_table_names():
            op.create_table(
                "profile_image_cleanup_jobs",
                sa.Column(
                    "job_id", sa.BigInteger(), primary_key=True, autoincrement=True
                ),
                sa.Column(
                    "file_key", sa.String(100, collation="utf8mb4_bin"), nullable=False
                ),
                sa.Column("created_at", sa.DateTime(), nullable=False),
                sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
                sa.Column("attempt_count", sa.BigInteger(), nullable=False),
                sa.Column("last_error_code", sa.String(64), nullable=True),
                sa.UniqueConstraint(
                    "file_key", name="uq_profile_image_cleanup_jobs_file_key"
                ),
                mysql_engine="InnoDB",
            )
        for profile_id, display, key in normalized:
            bind.execute(
                sa.text(
                    "UPDATE user_profiles SET nickname=:nickname, nickname_key=:key WHERE profile_id=:id"
                ),
                {"nickname": display, "key": key, "id": profile_id},
            )

        cursor = 0
        while True:
            missing = list(
                bind.execute(
                    sa.text(
                        "SELECT u.user_id FROM users u LEFT JOIN user_profiles p ON p.user_id=u.user_id "
                        "WHERE p.user_id IS NULL AND u.user_id>:cursor ORDER BY u.user_id LIMIT 100"
                    ),
                    {"cursor": cursor},
                ).scalars()
            )
            if not missing:
                break
            for user_id in missing:
                for _ in range(100):
                    display = "임시닉네임" + "".join(
                        secrets.choice(string.ascii_uppercase + string.digits)
                        for _ in range(5)
                    )
                    key = display.lower()
                    if key not in keys:
                        break
                else:
                    raise RuntimeError("Temporary nickname retry limit reached")
                bind.execute(
                    sa.text(
                        "INSERT INTO user_profiles (user_id,nickname,nickname_key) VALUES (:id,:nickname,:key)"
                    ),
                    {"id": user_id, "nickname": display, "key": key},
                )
                keys.add(key)
                cursor = user_id

        invalid = bind.scalar(
            sa.text("SELECT COUNT(*) FROM user_profiles WHERE nickname_key IS NULL")
        )
        if invalid:
            raise RuntimeError("Profile backfill incomplete")
        columns = {col["name"]: col for col in _inspect().get_columns("user_profiles")}
        if getattr(columns["nickname"]["type"], "length", None) != 10:
            op.alter_column(
                "user_profiles",
                "nickname",
                existing_type=sa.String(50),
                type_=sa.String(10),
                existing_nullable=False,
            )
        if columns["nickname_key"]["nullable"]:
            op.alter_column(
                "user_profiles", "nickname_key", existing_type=KEY_TYPE, nullable=False
            )
        constraints = {
            i["name"] for i in _inspect().get_unique_constraints("user_profiles")
        }
        if "uq_user_profiles_nickname_key" not in constraints:
            op.create_unique_constraint(
                "uq_user_profiles_nickname_key", "user_profiles", ["nickname_key"]
            )


def downgrade():
    # Schema-only reversal. It does not recreate discarded sessions or old display values.
    op.drop_table("profile_image_cleanup_jobs")
    op.drop_table("auth_refresh_tokens")
    op.drop_table("auth_sessions")
    op.drop_constraint("uq_user_profiles_nickname_key", "user_profiles", type_="unique")
    op.drop_column("user_profiles", "nickname_key")
    op.alter_column(
        "user_profiles",
        "nickname",
        existing_type=sa.String(10),
        type_=sa.String(50),
        existing_nullable=False,
    )
