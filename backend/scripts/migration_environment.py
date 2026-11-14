"""Pure P0-B key audit. Never read files, connect, or return input values."""

from collections.abc import Mapping

DB_INPUTS = frozenset(
    {
        "MIGRATION_DB_HOST",
        "MIGRATION_DB_PORT",
        "MIGRATION_DB_NAME",
        "MIGRATION_DB_USER",
        "MIGRATION_DB_PASSWORD_FILE",
        "MIGRATION_DB_CONNECTION_TIMEOUT",
    }
)
EVIDENCE_INPUT = "MIGRATION_PREFLIGHT_EVIDENCE_DIR"
REQUIRED_INPUTS = (DB_INPUTS - {"MIGRATION_DB_CONNECTION_TIMEOUT"}) | {EVIDENCE_INPUT}


def audit_environment(environ: Mapping[str, str]) -> str | None:
    keys = [key.upper() for key in environ]
    for key in keys:
        if (
            key in {"DATABASE_URL", "JWT_SECRET_KEY", "MARIADB_ROOT_PASSWORD"}
            or key.startswith(("DB_", "API_DB_"))
            or (key.startswith("MIGRATION_DB_") and key not in DB_INPUTS)
        ):
            return "ENV_CONFLICT"
    # Case aliases can coexist on POSIX. Do not let their iteration order pick
    # a different target from Pydantic's case-insensitive environment source.
    inputs = DB_INPUTS | {EVIDENCE_INPUT}
    if any(keys.count(key) > 1 for key in inputs):
        return "ENV_CONFLICT"
    normalized = {key.upper(): value for key, value in environ.items()}
    if any(not normalized.get(key, "").strip() for key in REQUIRED_INPUTS):
        return "SETTINGS_INVALID"
    return None
