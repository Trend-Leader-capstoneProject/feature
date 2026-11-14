"""Pure Observation -> JSON v1 assembly; no persistence or approval."""

from collections.abc import Collection
from dataclasses import asdict
from datetime import datetime, timedelta

from app.core.migration_db_config import MigrationDbSettings
from scripts.migration_evidence import new_evidence_id
from scripts.migration_observation import DatabaseObservation
from scripts.migration_preflight import classify_schema_state

ERROR_REASONS = frozenset(
    {
        "SETTINGS_INVALID",
        "DB_CONNECTION_FAILED",
        "READ_ONLY_NOT_ESTABLISHED",
        "OBSERVATION_FAILED",
    }
)


def assemble_report(
    settings: MigrationDbSettings,
    observation: DatabaseObservation,
    *,
    known_revisions: Collection[str],
    observed_at_utc: datetime,
) -> dict:
    """Reject contradictory internal results with a fixed, secret-free error.

    The caller supplies the checkout lineage and UTC observation-attempt start.
    Assembly never queries the clock. Visibility is not proof of
    emptiness; no read-only/cleanup/image checks are inferred from missing data.
    """
    if not isinstance(
        observed_at_utc, datetime
    ) or observed_at_utc.utcoffset() != timedelta(0):
        raise ValueError("OBSERVATION_FAILED")
    reasons = set(observation.reason_codes)
    state = observation.schema_state
    target = asdict(observation.observed_target)
    visible = observation.version_table_visible
    business = observation.business_objects_visible
    revisions = observation.current_revisions
    mismatch = (
        target["database"] is not None and target["database"] != settings.name
    ) or (
        target["current_user"] is not None
        and target["current_user"].rpartition("@")[0] != settings.user
    )

    def invalid():
        raise ValueError("OBSERVATION_FAILED")

    if len(reasons) != len(observation.reason_codes):
        invalid()
    if reasons & ERROR_REASONS:
        if reasons - ERROR_REASONS - {"TARGET_MISMATCH", "SCHEMA_INDETERMINATE"}:
            invalid()
        # A second reason is possible only when cleanup failed after a prior
        # stage result. Connection failure cannot coexist with a schema read.
        if len(reasons) > 1 and (
            len(reasons) != 2
            or "OBSERVATION_FAILED" not in reasons
            or "SETTINGS_INVALID" in reasons
        ):
            invalid()
        # The observer discards successful reads on connection/read/cleanup
        # failure. Do not accept a fabricated success alongside an error.
        if (
            state is not None
            or revisions
            or visible is not None
            or business is not None
        ):
            invalid()
        if any(value is not None for value in target.values()):
            invalid()
        status = "ERROR"
    elif reasons == {"TARGET_MISMATCH"}:
        if not mismatch or state is not None or revisions:
            invalid()
        if visible is not None or business is not None:
            invalid()
        status = "INDETERMINATE"
    else:
        if type(visible) is not bool or type(business) is not bool:
            invalid()
        if mismatch or any(value is None for value in target.values()):
            invalid()
        if any(value is not None and not isinstance(value, str) for value in revisions):
            invalid()
        expected = classify_schema_state(
            version_table_visible=visible,
            business_objects_visible=business,
            current_revisions=revisions
            if all(isinstance(v, str) for v in revisions)
            else (),
            known_revisions=known_revisions,
        )
        if state != expected or (not visible and revisions):
            invalid()
        expected_reasons = (
            {"SCHEMA_INDETERMINATE"} if state == "INDETERMINATE" else set()
        )
        if reasons != expected_reasons:
            invalid()
        status = "INDETERMINATE" if reasons else "OBSERVED"

    return {
        "schema_version": 1,
        "evidence_id": new_evidence_id(),
        "observed_at_utc": observed_at_utc.isoformat(),
        "inspection_status": status,
        "schema_state": state,
        "configured_target": {
            "host": settings.host,
            "port": settings.port,
            "database": settings.name,
            "user": settings.user,
        },
        "observed_target": target,
        "current_revisions": list(revisions),
        "reason_codes": list(observation.reason_codes),
        "checks": {
            "version_table_visible": visible,
            "business_objects_visible": business,
        },
        "image_identity_verification_status": "NOT_VERIFIED",
    }
