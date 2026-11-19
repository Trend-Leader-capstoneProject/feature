"""Synthetic single-candidate binding only; no operational evidence or I/O."""

import importlib
import io
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch
from zipfile import ZipFile

import fr_b02b_a1_adapter as a1
import fr_b02b_observation as obs
import fr_b02b_registration as reg
from test_fr_b02b_a1_adapter import example

EID = "LOCAL-OBS-123456781234423492341234567890ab"
RID = "REG-OBS-1234567812344234a234123456789abc"
OTHER_RID = "REG-OBS-2234567812344234a234123456789abc"
TIME = "2026-11-09T08:00:00Z"


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("fr_b02b_binding"),
                             "P4 pure binding validator is not implemented")
        self.p4 = importlib.import_module("fr_b02b_binding")
        approvals, batch = example()
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr(a1.A1_ZIP_APPROVALS, obs.canonical_bytes(approvals))
            archive.writestr(a1.A1_ZIP_BATCH, obs.canonical_bytes(batch))
        self.archive = stream.getvalue()
        snapshot = a1._load_a1_snapshot_bytes(self.archive)
        self.record = dict(obs.RECORD_CONSTANTS,
                           **{key: getattr(snapshot, key) for key in obs.BINDING_KEYS},
                           evidence_id=EID, a1_archive_sha256=obs.digest(self.archive),
                           confirmed_at_utc=TIME, record_created_at_utc=TIME)
        self.record_raw = obs.canonical_bytes(self.record)
        self.index = {"schema": "FR_B02B_LOCAL_INDEX_V1", "evidence_id": EID,
                      "artifact_file": "observation.json",
                      "artifact_sha256": obs.digest(self.record_raw),
                      "trend_ref": snapshot.trend_ref, "content_ref": snapshot.content_ref,
                      "a1_archive_sha256": obs.digest(self.archive), "status": obs.RECORDED}
        self.index_raw = obs.canonical_bytes(self.index)
        self.manifest = dict(
            schema=reg.SCHEMA, registration_id=RID, local_evidence_id=EID,
            **{key: self.record[key] for key in (
                *obs.BINDING_KEYS, "event_kind", "observation_method", "confirmed_at_utc",
                "record_created_at_utc", "observer_ref", "actor_assurance")},
            a1_archive_sha256=obs.digest(self.archive),
            observation_sha256=obs.digest(self.record_raw), index_sha256=obs.digest(self.index_raw),
            reviewer_sid="S-1-5-21-111-222-333-1001", reviewed_at_utc=TIME,
            review_result="ACCEPTED", decision_reason="", registration_recorded_at_utc=TIME,
            supersedes_registration_id=None, publish_authorization="NONE")
        self.manifest_raw = obs.canonical_bytes(self.manifest)
        self.expected = self.p4.ExpectedBinding(
            **{key: getattr(snapshot, key) for key in obs.BINDING_KEYS},
            local_evidence_id=EID, a1_archive_sha256=obs.digest(self.archive),
            observation_sha256=obs.digest(self.record_raw), index_sha256=obs.digest(self.index_raw),
            registration_id=RID, registration_sha256=obs.digest(self.manifest_raw))

    def verify(self, **changes):
        inputs = {"a1_archive_bytes": self.archive, "observation_bytes": self.record_raw,
                  "index_bytes": self.index_raw, "expected": self.expected,
                  "registration_bytes": self.manifest_raw}
        inputs.update(changes)
        return self.p4.verify_binding(**inputs)

    def assert_blocked(self, result):
        self.assertEqual(result.binding_status, "BLOCKED")
        self.assertEqual(result.operational_handoff, "HOLD")
        self.assertEqual(result.publish_authorization, "NONE")

    def test_matching_binding_still_holds_operations_and_time(self):
        result = self.verify()
        self.assertEqual(result.binding_status, "MATCH")
        self.assertEqual(result.operational_handoff, "HOLD")
        self.assertEqual(result.observation_time, "HOLD")
        self.assertEqual(result.publish_authorization, "NONE")
        self.assertEqual(set(asdict(result)), {
            "binding_status", "reason", "operational_handoff", "observation_time",
            "publish_authorization"})

    def test_each_expected_binding_field_is_compared(self):
        for key, value in asdict(self.expected).items():
            with self.subTest(key=key):
                other = OTHER_RID if key == "registration_id" else value + "different"
                self.assert_blocked(self.verify(expected=replace(self.expected, **{key: other})))

    def test_source_url_comparison_preserves_original_string(self):
        self.assert_blocked(self.verify(expected=replace(
            self.expected, source_url=self.expected.source_url.replace("example.test", "EXAMPLE.TEST"))))

    def test_each_artifact_byte_change_is_blocked(self):
        for key, raw in (("a1_archive_bytes", self.archive),
                         ("observation_bytes", self.record_raw), ("index_bytes", self.index_raw)):
            with self.subTest(key=key):
                self.assert_blocked(self.verify(**{key: raw + b" "}))

    def test_same_registration_id_replaced_manifest_is_blocked(self):
        raw = obs.canonical_bytes(dict(self.manifest, decision_reason="replacement"))
        self.assert_blocked(self.verify(registration_bytes=raw))

    def test_manifest_links_remain_checked_when_fingerprint_is_updated(self):
        for key in (*obs.BINDING_KEYS, "local_evidence_id", "a1_archive_sha256",
                    "observation_sha256", "index_sha256", "schema", "publish_authorization",
                    "observer_ref", "actor_assurance", "review_result", "reviewer_sid",
                    "confirmed_at_utc", "record_created_at_utc", "event_kind", "observation_method"):
            with self.subTest(key=key):
                raw = obs.canonical_bytes(dict(self.manifest, **{key: "different"}))
                self.assert_blocked(self.verify(registration_bytes=raw, expected=replace(
                    self.expected, registration_sha256=obs.digest(raw))))

    def test_invalid_a1_and_observation_are_not_trusted_with_updated_hashes(self):
        self.assert_blocked(self.verify(a1_archive_bytes=b"invalid", expected=replace(
            self.expected, a1_archive_sha256=obs.digest(b"invalid"))))
        for key in (*obs.BINDING_KEYS, "evidence_id", "publish_authorization",
                    "confirmed_at_utc", "actor_assurance"):
            with self.subTest(key=key):
                raw = obs.canonical_bytes(dict(self.record, **{key: "different"}))
                index = obs.canonical_bytes(dict(self.index, artifact_sha256=obs.digest(raw)))
                self.assert_blocked(self.verify(observation_bytes=raw, index_bytes=index,
                    expected=replace(self.expected, observation_sha256=obs.digest(raw),
                                     index_sha256=obs.digest(index))))

    def test_missing_registration_is_explicitly_unverified_and_hold(self):
        result = self.verify(registration_bytes=None)
        self.assertEqual(result.binding_status, "UNVERIFIED")
        self.assertEqual(result.operational_handoff, "HOLD")
        self.assertEqual(result.publish_authorization, "NONE")
        # A missing registration cannot hide a known candidate mismatch.
        self.assert_blocked(self.verify(registration_bytes=None, expected=replace(
            self.expected, trend_ref="other")))

    def test_accepted_or_revoked_claim_cannot_promote_operational_use(self):
        for claim in ("ACCEPTED", "REVOKED", "AMBIGUOUS", True, False):
            # Operational claims are deliberately not part of this function's inputs.
            with self.subTest(claim=claim), self.assertRaises(TypeError):
                self.verify(operational_approval=claim)
        self.assertEqual(self.verify().operational_handoff, "HOLD")

    def test_hold_and_rejected_manifests_bind_without_becoming_operational(self):
        for decision in ("HOLD", "REJECTED"):
            raw = obs.canonical_bytes(dict(self.manifest, review_result=decision,
                                           decision_reason="synthetic review"))
            result = self.verify(registration_bytes=raw, expected=replace(
                self.expected, registration_sha256=obs.digest(raw)))
            self.assertEqual(result.binding_status, "MATCH")
            self.assertEqual(result.operational_handoff, "HOLD")

    def test_malformed_and_oversized_bytes_fail_closed(self):
        for key in ("observation_bytes", "index_bytes", "registration_bytes"):
            for raw in (b"{}", b"\xff", b"x" * (obs.MAX_RECORD_BYTES + 1), "not bytes"):
                with self.subTest(key=key, kind=type(raw).__name__):
                    self.assert_blocked(self.verify(**{key: raw}))

    def test_registration_parser_rejects_duplicate_noncanonical_and_extra_fields(self):
        for raw in (self.manifest_raw + b" ",
                    b'{"schema":"duplicate",' + self.manifest_raw[1:],
                    obs.canonical_bytes(dict(self.manifest, extra="field"))):
            self.assert_blocked(self.verify(registration_bytes=raw, expected=replace(
                self.expected, registration_sha256=obs.digest(raw))))

    def test_frozen_manifest_clock_order_parent_and_reason_rules_are_reused(self):
        for changes in ({"reviewed_at_utc": "2026-11-09T07:59:59Z"},
                        {"registration_recorded_at_utc": "2026-11-09T07:59:59Z"},
                        {"reviewed_at_utc": "2026-11-09T08:00:00"},
                        {"supersedes_registration_id": RID},
                        {"supersedes_registration_id": "invalid"},
                        {"review_result": "HOLD", "decision_reason": ""},
                        {"decision_reason": "x" * 501}):
            with self.subTest(changes=changes):
                raw = obs.canonical_bytes(dict(self.manifest, **changes))
                self.assert_blocked(self.verify(registration_bytes=raw, expected=replace(
                    self.expected, registration_sha256=obs.digest(raw))))

    def test_invalid_index_binding_with_updated_digest_is_blocked(self):
        for key in self.index:
            with self.subTest(key=key):
                raw = obs.canonical_bytes(dict(self.index, **{key: "different"}))
                self.assert_blocked(self.verify(index_bytes=raw, expected=replace(
                    self.expected, index_sha256=obs.digest(raw))))

    def test_pure_path_does_not_read_clock_files_network_or_allocate_ids(self):
        with patch("builtins.open", side_effect=AssertionError("no file I/O")), \
                patch.object(obs, "utc_now", side_effect=AssertionError("no clock")), \
                patch.object(reg, "uuid4", side_effect=AssertionError("no ID allocation")), \
                patch("socket.create_connection", side_effect=AssertionError("no network")):
            self.assertEqual(self.verify().binding_status, "MATCH")


if __name__ == "__main__":
    unittest.main()
