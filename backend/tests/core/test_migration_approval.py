"""B-3 offline contracts: comparison never issues or consumes an approval."""

import json
import socket
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy

from alembic import command
from scripts import migration_approval as approval
from scripts.migration_guard import main

NOW = datetime(2026, 11, 17, 3, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64


def encode(value):
    return json.dumps(value).encode()


@pytest.fixture
def inputs():
    manifest = {
        "schema_version": 1,
        "approval_id": "approval-001",
        "environment": "production",
        "deployment_project": "trend-leader",
        "db_host": "db",
        "db_port": 3306,
        "db_name": "trend",
        "expected_db_account": "migrator@%",
        "expected_from_revision": "a4d7c9e21f3b",
        "target_revision": "b7f2c81d9e04",
        "backend_image_digest": DIGEST,
        "preflight_evidence_id": "c66363da-35db-41ac-9748-20c0a2e76bca",
        "backup_or_empty_db_evidence_id": "recovery-001",
        "approved_by": "operator-001",
        "approved_at": "2026-11-17T02:00:00Z",
        "expires_at": "2026-11-17T04:00:00Z",
    }
    evidence = {
        "schema_version": 1,
        "evidence_id": manifest["preflight_evidence_id"],
        "observed_at_utc": "2026-11-17T01:00:00Z",
        "inspection_status": "OBSERVED",
        "schema_state": "VERSIONED_OBSERVED",
        "configured_target": {
            "host": "db", "port": 3306, "database": "trend", "user": "migrator"
        },
        "observed_target": {
            "database": "trend", "current_user": "migrator@%",
            "server_version": "12.3.2-MariaDB", "database_charset": "utf8mb4",
            "database_collation": "utf8mb4_unicode_ci",
        },
        "current_revisions": ["a4d7c9e21f3b"],
        "reason_codes": [],
        "checks": {"version_table_visible": True, "business_objects_visible": True},
        "image_identity_verification_status": "NOT_VERIFIED",
    }
    return manifest, evidence


def context_for(manifest, evidence, *, recovery_kind="BACKUP_RESTORE"):
    # Synthetic, independent trusted review facts. Never derive these from an
    # untrusted production Manifest/Evidence in an operational adapter.
    manifest_hash = sha256(encode(manifest)).hexdigest()
    return approval.ComparisonContext(
        environment="production",
        deployment_project="trend-leader",
        manifest_sha256=manifest_hash,
        evidence_sha256=sha256(encode(evidence)).hexdigest(),
        verified_image_digest=DIGEST,
        used_approval_ids=frozenset(),
        recovery=approval.RecoveryConfirmation(
            evidence_id="recovery-001", kind=recovery_kind,
            manifest_sha256=manifest_hash,
        ),
    )


def compare(manifest, evidence, context=None):
    return approval.compare_approval(
        encode(manifest), encode(evidence),
        context=context or context_for(manifest, evidence), now=NOW,
    )


def test_valid_manifest_and_matching_evidence_are_not_apply_authorization(inputs):
    manifest, evidence = inputs
    assert approval.validate_manifest(encode(manifest), now=NOW).matches
    result = compare(manifest, evidence)
    assert result.matches
    assert result.reason_codes == ()
    assert result.apply_enabled is False
    assert evidence["inspection_status"] == "OBSERVED"
    assert evidence["image_identity_verification_status"] == "NOT_VERIFIED"


@pytest.mark.parametrize("field", sorted(approval.MANIFEST_FIELDS))
def test_every_semantic_field_is_required(inputs, field):
    manifest, evidence = inputs
    del manifest[field]
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", True), ("schema_version", 2),
    ("db_port", True), ("db_port", "3306"), ("db_port", 0), ("db_port", 65536),
    ("approval_id", ""), ("approved_by", " operator "),
    ("expected_db_account", "migrator"), ("expected_db_account", "@%"),
    ("target_revision", "head"), ("target_revision", "heads"),
    ("target_revision", "+1"), ("target_revision", "a4d7c9e21f3b:head"),
    ("target_revision", "unknown"), ("expected_from_revision", "base"),
    ("expected_from_revision", "unknown"), ("backend_image_digest", "latest"),
    ("backend_image_digest", "sha256:abc"), ("expires_at", "2026-11-17T03:00:00Z"),
    ("expires_at", "2026-11-17T01:00:00Z"),
    ("approved_at", "2026-11-17T03:01:00Z"),
    ("approved_at", "2026-11-17T02:00:00"), ("expires_at", None),
    ("approved_at", "not-a-date"),
])
def test_invalid_manifest_values_fail_closed(inputs, field, value):
    manifest, evidence = inputs
    manifest[field] = value
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize("field", [
    "environment", "deployment_project", "db_host", "db_name", "db_port",
    "expected_db_account", "preflight_evidence_id", "backup_or_empty_db_evidence_id",
    "backend_image_digest",
])
def test_semantically_valid_but_mismatched_manifest(inputs, field):
    manifest, evidence = inputs
    manifest[field] = {
        "db_port": 3307, "expected_db_account": "migrator@localhost",
        "backend_image_digest": "sha256:" + "b" * 64,
    }.get(field, "other")
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize(("group", "field", "value"), [
    ("configured_target", "host", "other"),
    ("configured_target", "port", 3307),
    ("configured_target", "database", "other"),
    ("configured_target", "user", "root"),
    ("observed_target", "database", "other"),
    ("observed_target", "current_user", "migrator@localhost"),
    ("observed_target", "server_version", None),
    ("observed_target", "database_charset", None),
    ("checks", "version_table_visible", False),
])
def test_evidence_target_and_observation_contradictions(inputs, group, field, value):
    manifest, evidence = inputs
    evidence[group][field] = value
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize("revisions", [[], ["7e9d740c5df1"], ["unknown"],
                                       ["a4d7c9e21f3b", "b7f2c81d9e04"]])
def test_revision_mismatch(inputs, revisions):
    manifest, evidence = inputs
    evidence["current_revisions"] = revisions
    assert not compare(manifest, evidence).matches


def test_downgrade_is_not_an_upgrade_approval(inputs):
    manifest, evidence = inputs
    manifest["target_revision"] = "7e9d740c5df1"
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize("field", ["manifest_sha256", "evidence_sha256"])
@pytest.mark.parametrize("pin", [None, "b" * 64])
def test_missing_or_tampered_content_pin(inputs, field, pin):
    manifest, evidence = inputs
    context = replace(context_for(manifest, evidence), **{field: pin})
    assert not compare(manifest, evidence, context).matches


def test_same_id_changed_evidence_is_not_trusted(inputs):
    manifest, evidence = inputs
    context = context_for(manifest, evidence)
    evidence["observed_target"]["server_version"] = "12.3.99-MariaDB"
    assert "CONTENT_PIN_MISMATCH" in compare(manifest, evidence, context).reason_codes


@pytest.mark.parametrize("digest", [None, "", "sha256:" + "b" * 64])
def test_unverified_image_never_inferred_from_manifest_or_observed(inputs, digest):
    manifest, evidence = inputs
    context = replace(context_for(manifest, evidence), verified_image_digest=digest)
    assert "IMAGE_NOT_VERIFIED" in compare(manifest, evidence, context).reason_codes


@pytest.mark.parametrize("used", [None, frozenset({"approval-001"})])
def test_unavailable_audit_or_duplicate_id_fails_closed(inputs, used):
    manifest, evidence = inputs
    context = replace(context_for(manifest, evidence), used_approval_ids=used)
    assert not compare(manifest, evidence, context).matches


@pytest.mark.parametrize("used", [frozenset({" approval-001 "}), frozenset({""})])
def test_malformed_audit_ids_are_not_treated_as_an_unused_approval(inputs, used):
    manifest, evidence = inputs
    context = replace(context_for(manifest, evidence), used_approval_ids=used)
    assert compare(manifest, evidence, context).reason_codes == ("AUDIT_UNAVAILABLE",)


def test_comparison_never_consumes_id_and_repeat_is_not_permission(inputs):
    manifest, evidence = inputs
    context = context_for(manifest, evidence)
    assert compare(manifest, evidence, context).matches
    assert compare(manifest, evidence, context).matches
    assert context.used_approval_ids == frozenset()
    assert compare(manifest, evidence, context).apply_enabled is False


@pytest.mark.parametrize("kind", [None, "EMPTY_BOOTSTRAP", "OTHER"])
def test_versioned_db_requires_independent_backup_restore_confirmation(inputs, kind):
    manifest, evidence = inputs
    context = context_for(manifest, evidence, recovery_kind=kind)
    if kind is None:
        context = replace(context, recovery=None)
    assert not compare(manifest, evidence, context).matches


def test_empty_candidate_requires_independent_scoped_bootstrap_confirmation(inputs):
    manifest, evidence = inputs
    manifest["expected_from_revision"] = None
    evidence.update(schema_state="UNVERSIONED_EMPTY_CANDIDATE", current_revisions=[])
    evidence["checks"] = {
        "version_table_visible": False, "business_objects_visible": False
    }
    assert not compare(manifest, evidence).matches  # backup is not bootstrap
    context = context_for(manifest, evidence, recovery_kind="EMPTY_BOOTSTRAP")
    assert not compare(manifest, evidence, replace(context, recovery=None)).matches
    recovery = replace(context.recovery, manifest_sha256="b" * 64)
    assert not compare(manifest, evidence, replace(context, recovery=recovery)).matches
    result = compare(manifest, evidence, context)
    assert result.matches
    assert result.apply_enabled is False


@pytest.mark.parametrize("change", [
    {"inspection_status": "ERROR"}, {"inspection_status": "INDETERMINATE"},
    {"schema_state": "INDETERMINATE"}, {"reason_codes": ["OBSERVATION_FAILED"]},
    {"image_identity_verification_status": "VERIFIED"},
    {"observed_at_utc": "2026-11-17T02:01:00Z"},
    {"checks": {}}, {"schema_version": 2}, {"evidence_id": "other"},
])
def test_non_b2_or_incomplete_or_post_approval_observation(inputs, change):
    manifest, evidence = inputs
    evidence.update(change)
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize("raw", [b"", b"[]", b"null", b"{", b"\xff",
                                  b'{"approval_id":"a","approval_id":"b"}',
                                  b'{"db_port":NaN}'])
def test_malformed_json_is_safe(inputs, raw):
    manifest, evidence = inputs
    context = context_for(manifest, evidence)
    assert not approval.validate_manifest(raw, now=NOW).matches
    assert not approval.compare_approval(
        encode(manifest), raw, context=context, now=NOW
    ).matches


def test_secret_values_and_exceptions_are_not_returned_or_logged(
    inputs, monkeypatch, capsys, caplog
):
    manifest, evidence = inputs
    marker = "sensitive-marker-mysql://user:password@host-eyJ.fake.jwt"
    for field in manifest:
        if field != "schema_version":
            changed = {**manifest, field: marker}
            result = compare(changed, evidence)
            assert not result.matches
            assert marker not in repr(result)
    monkeypatch.setenv("JWT_SECRET_KEY", marker)
    monkeypatch.setattr(
        approval, "_repository_lineage", Mock(side_effect=ValueError(marker))
    )
    assert not compare(manifest, evidence).matches
    captured = capsys.readouterr()
    assert captured.out == captured.err == caplog.text == ""


def test_comparison_and_guard_do_not_connect_write_or_run_alembic(
    inputs, monkeypatch, capsys
):
    manifest, evidence = inputs
    context = context_for(manifest, evidence)
    # Load actual revision metadata before prohibiting all other I/O.
    lineage = approval._repository_lineage()
    monkeypatch.setattr(approval, "_repository_lineage", lambda: lineage)
    forbidden = Mock(side_effect=AssertionError("unauthorized side effect"))
    for module, name in [
        (socket, "create_connection"), (socket.socket, "connect"),
        (sqlalchemy, "create_engine"), (subprocess, "run"),
        (command, "upgrade"), (command, "downgrade"), (command, "stamp"),
        (command, "revision"), (Path, "write_text"), (Path, "write_bytes"),
        (Path, "mkdir"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    assert compare(manifest, evidence, context).matches
    assert not compare(manifest, evidence, replace(context, recovery=None)).matches
    for args in ([], ["deny"], ["apply"], ["apply", "--approval", "example.json"]):
        assert main(args) == 2
    forbidden.assert_not_called()
    capsys.readouterr()


@pytest.mark.parametrize("field", [
    "schema_version", "evidence_id", "observed_at_utc", "inspection_status",
    "schema_state", "configured_target", "observed_target", "current_revisions",
    "reason_codes", "checks", "image_identity_verification_status",
])
def test_missing_evidence_field(inputs, field):
    manifest, evidence = inputs
    del evidence[field]
    assert not compare(manifest, evidence).matches


def test_unknown_manifest_fields_not_silently_accepted(inputs):
    manifest, evidence = inputs
    manifest["password"] = "sensitive-marker"
    assert not compare(manifest, evidence).matches


@pytest.mark.parametrize("now", [None, datetime(2026, 11, 17), "2026-11-17"])
def test_missing_or_naive_validation_clock_is_not_guessed(inputs, now):
    manifest, evidence = inputs
    assert not approval.validate_manifest(encode(manifest), now=now).matches
    assert not approval.compare_approval(
        encode(manifest), encode(evidence),
        context=context_for(manifest, evidence), now=now,
    ).matches


def test_omitted_confirmation_inputs_fail_closed(inputs):
    manifest, evidence = inputs
    context = approval.ComparisonContext("production", "trend-leader")
    assert not compare(manifest, evidence, context).matches
    context = replace(
        context, manifest_sha256=sha256(encode(manifest)).hexdigest(),
        evidence_sha256=sha256(encode(evidence)).hexdigest(),
    )
    assert set(compare(manifest, evidence, context).reason_codes) == {
        "IMAGE_NOT_VERIFIED", "RECOVERY_NOT_VERIFIED", "AUDIT_UNAVAILABLE",
    }


def test_recovery_reference_cannot_be_the_preflight_itself(inputs):
    manifest, evidence = inputs
    manifest["backup_or_empty_db_evidence_id"] = evidence["evidence_id"]
    context = context_for(manifest, evidence)
    context = replace(
        context,
        recovery=replace(context.recovery, evidence_id=evidence["evidence_id"]),
    )
    assert "RECOVERY_NOT_VERIFIED" in compare(manifest, evidence, context).reason_codes


def test_actual_lineage_uses_revision_ids_in_current_checkout():
    assert approval._repository_lineage() == (
        "d3a9f27c6b41", "b7f2c81d9e04", "a4d7c9e21f3b",
        "7e9d740c5df1", "2f29fa23597c",
    )


@pytest.mark.parametrize("raw", [
    b'{"outer":{"x":1,"x":2}}', b'{"x":Infinity}',
    b'{"x":-Infinity}', "not bytes", None,
])
def test_duplicate_nested_keys_constants_and_non_bytes_fail_closed(inputs, raw):
    manifest, evidence = inputs
    assert not approval.validate_manifest(raw, now=NOW).matches
    assert not approval.compare_approval(
        encode(manifest), raw, context=context_for(manifest, evidence), now=NOW,
    ).matches
