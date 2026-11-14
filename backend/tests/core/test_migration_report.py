"""Pure assembly contract; no database fixtures."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from scripts import migration_report as report
from scripts.migration_observation import DatabaseObservation, ObservedTarget

SETTINGS = SimpleNamespace(host="db", port=3306, name="trend", user="migrator")
KNOWN = frozenset({"a4d7c9e21f3b"})
TARGET = ObservedTarget(
    "trend", "migrator@%", "12.3.2-MariaDB", "utf8mb4", "utf8mb4_unicode_ci"
)
STARTED_AT = datetime(2026, 11, 14, 1, 2, 3, 456789, tzinfo=UTC)


def normal():
    return DatabaseObservation(
        TARGET, ("a4d7c9e21f3b",), True, True, "VERSIONED_OBSERVED"
    )


def test_observed_json_v1():
    data = report.assemble_report(
        SETTINGS, normal(), known_revisions=KNOWN, observed_at_utc=STARTED_AT
    )
    assert data["inspection_status"] == "OBSERVED"
    assert data["reason_codes"] == []
    assert data["image_identity_verification_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize(
    ("observation", "status"),
    [
        (
            DatabaseObservation(
                TARGET, (), False, False, "UNVERSIONED_EMPTY_CANDIDATE"
            ),
            "OBSERVED",
        ),
        (
            DatabaseObservation(
                TARGET,
                ("unknown",),
                True,
                True,
                "INDETERMINATE",
                ("SCHEMA_INDETERMINATE",),
            ),
            "INDETERMINATE",
        ),
        (
            DatabaseObservation(
                TARGET, (None,), True, True, "INDETERMINATE", ("SCHEMA_INDETERMINATE",)
            ),
            "INDETERMINATE",
        ),
        (
            DatabaseObservation(
                TARGET, (), False, True, "INDETERMINATE", ("SCHEMA_INDETERMINATE",)
            ),
            "INDETERMINATE",
        ),
        (
            DatabaseObservation(
                observed_target=ObservedTarget("other", "migrator@%", "12.3-MariaDB"),
                reason_codes=("TARGET_MISMATCH",),
            ),
            "INDETERMINATE",
        ),
        *[
            (DatabaseObservation(reason_codes=(reason,)), "ERROR")
            for reason in [
                "SETTINGS_INVALID",
                "DB_CONNECTION_FAILED",
                "READ_ONLY_NOT_ESTABLISHED",
                "OBSERVATION_FAILED",
            ]
        ],
        (
            DatabaseObservation(reason_codes=("TARGET_MISMATCH", "OBSERVATION_FAILED")),
            "ERROR",
        ),
    ],
)
def test_status_reason_and_null_mapping(observation, status):
    from scripts.migration_evidence import _validate_report

    data = report.assemble_report(
        SETTINGS, observation, known_revisions=KNOWN, observed_at_utc=STARTED_AT
    )
    assert data["inspection_status"] == status
    assert data["schema_state"] == observation.schema_state
    assert (
        data["observed_target"]["database_charset"]
        == observation.observed_target.database_charset
    )
    assert data["checks"]["version_table_visible"] is observation.version_table_visible
    _validate_report(data)


@pytest.mark.parametrize(
    "observation",
    [
        DatabaseObservation(),
        replace(normal(), reason_codes=("OBSERVATION_FAILED",)),
        replace(normal(), reason_codes=("SCHEMA_INDETERMINATE",)),
        replace(normal(), reason_codes=("TARGET_MISMATCH",)),
        replace(normal(), reason_codes=("unsafe-raw-message",)),
        replace(normal(), schema_state="INDETERMINATE"),
        replace(normal(), current_revisions=("unknown",)),
        replace(normal(), observed_target=replace(TARGET, database="other")),
        replace(normal(), observed_target=replace(TARGET, database_charset=None)),
        replace(normal(), version_table_visible=None),
        DatabaseObservation(reason_codes=("TARGET_MISMATCH",)),
        DatabaseObservation(reason_codes=("SCHEMA_INDETERMINATE",)),
    ],
)
def test_contradictions_rejected(observation):
    with pytest.raises(ValueError, match="^OBSERVATION_FAILED$"):
        report.assemble_report(
            SETTINGS, observation, known_revisions=KNOWN, observed_at_utc=STARTED_AT
        )


@pytest.mark.parametrize(
    "reasons",
    [
        ("DB_CONNECTION_FAILED", "SCHEMA_INDETERMINATE"),
        ("READ_ONLY_NOT_ESTABLISHED", "TARGET_MISMATCH"),
        ("DB_CONNECTION_FAILED", "READ_ONLY_NOT_ESTABLISHED"),
    ],
)
def test_impossible_stage_reasons_rejected(reasons):
    with pytest.raises(ValueError, match="^OBSERVATION_FAILED$"):
        report.assemble_report(
            SETTINGS,
            DatabaseObservation(reason_codes=reasons),
            known_revisions=KNOWN,
            observed_at_utc=STARTED_AT,
        )


def test_explicit_start_time_survives_later_assembly_and_writer_validation():
    from scripts.migration_evidence import _validate_report

    # A fixed past instant makes this independent of execution speed/sleep.
    data = report.assemble_report(
        SETTINGS, normal(), known_revisions=KNOWN, observed_at_utc=STARTED_AT
    )
    assert data["observed_at_utc"] == STARTED_AT.isoformat()
    _validate_report(data)


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 11, 14),
        datetime(2026, 11, 14, tzinfo=timezone(timedelta(hours=9))),
        None,
        "2026-11-14T01:02:03Z",
    ],
)
def test_start_time_must_be_utc_aware_datetime(instant):
    with pytest.raises(ValueError, match="^OBSERVATION_FAILED$"):
        report.assemble_report(
            SETTINGS, normal(), known_revisions=KNOWN, observed_at_utc=instant
        )
