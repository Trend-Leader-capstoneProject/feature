"""B-2 orchestration: audit -> root -> observation -> assembly -> persistence.

Only a completed Writer result permits exit 0/3. No output, apply, or approval.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from app.core.migration_db_config import MigrationDbSettings
from scripts.migration_environment import EVIDENCE_INPUT, audit_environment
from scripts.migration_evidence import evidence_root_available, write_evidence
from scripts.migration_observation import (
    DatabaseObservation,
    observe_database,
    repository_revisions,
)
from scripts.migration_report import assemble_report


def run_preflight() -> tuple[int, tuple[str, ...]]:
    """Return only fixed codes; never expose input or exceptions to the CLI."""
    try:
        environ = dict(os.environ)
        reason = audit_environment(environ)
        if reason:
            return 4, (reason,)
        inputs = {key.upper(): value for key, value in environ.items()}
        settings = MigrationDbSettings(
            host=inputs["MIGRATION_DB_HOST"],
            port=inputs["MIGRATION_DB_PORT"],
            name=inputs["MIGRATION_DB_NAME"],
            user=inputs["MIGRATION_DB_USER"],
            password_file=inputs["MIGRATION_DB_PASSWORD_FILE"],
            connection_timeout=inputs.get("MIGRATION_DB_CONNECTION_TIMEOUT", "5"),
        )
        # Secret validation precedes any DB access; never retain/serialize URL.
        settings.connection_url
        root = Path(inputs[EVIDENCE_INPUT])
    except Exception:
        return 4, ("SETTINGS_INVALID",)

    if not evidence_root_available(root):
        return 4, ("EVIDENCE_WRITE_FAILED",)

    # Entry into the observation attempt, not the time of any SQL or success.
    observed_at_utc = datetime.now(UTC)
    try:
        known = repository_revisions()
        observation = observe_database(settings)
        data = assemble_report(
            settings,
            observation,
            known_revisions=known,
            observed_at_utc=observed_at_utc,
        )
    except Exception:
        # Invalid/contradictory internal result is never persisted as success.
        data = assemble_report(
            settings,
            DatabaseObservation(reason_codes=("OBSERVATION_FAILED",)),
            known_revisions=(),
            observed_at_utc=observed_at_utc,
        )
    try:
        result = write_evidence(root, data)
        if not result.success:
            return 4, ("EVIDENCE_WRITE_FAILED",)
    except Exception:
        return 4, ("EVIDENCE_WRITE_FAILED",)
    return (
        {"OBSERVED": 0, "INDETERMINATE": 3, "ERROR": 4}[data["inspection_status"]],
        tuple(data["reason_codes"]),
    )
