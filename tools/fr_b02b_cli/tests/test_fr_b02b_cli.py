"""PoC-only contract regression tests; no production integrations."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fr_b02b_cli import (
    SimulationError,
    build_simulation_record,
    canonical_bytes,
    load_fixture_bytes,
    run_cli,
    store_simulation,
    verify_simulation,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "fixtures" / "synthetic_approval.json"


class SimulatedObservationTests(unittest.TestCase):
    def setUp(self):
        self.raw = SAMPLE.read_bytes()
        self.fixture = load_fixture_bytes(self.raw)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def saved(self):
        record = build_simulation_record(
            self.fixture,
            now=lambda: datetime(2026, 11, 9, 6, 0, tzinfo=timezone.utc),
        )
        return store_simulation(record, self.root)

    def test_fixture_requires_synthetic_https_hostname(self):
        fixture = dict(self.fixture)
        fixture["source_url"] = "https://www.python.org/downloads/release/python-3150/"
        with self.assertRaisesRegex(SimulationError, "synthetic"):
            load_fixture_bytes(canonical_bytes(fixture))

    def test_fixture_rejects_real_trend_ref(self):
        fixture = dict(self.fixture)
        fixture["trend_ref"] = "PYTHON-315-MVP-A-001"
        with self.assertRaisesRegex(SimulationError, "real identifier"):
            load_fixture_bytes(canonical_bytes(fixture))

    def test_fixture_rejects_duplicate_keys(self):
        with self.assertRaisesRegex(SimulationError, "duplicate"):
            load_fixture_bytes(b'{"schema":"x","schema":"x"}')

    def test_fixture_rejects_unexpected_fields(self):
        fixture = dict(self.fixture)
        fixture["g6_status"] = "PASS"
        with self.assertRaisesRegex(SimulationError, "unsupported"):
            load_fixture_bytes(canonical_bytes(fixture))

    def test_fixture_rejects_missing_digest(self):
        fixture = dict(self.fixture)
        fixture["content_ref"] = "sha256:fake"
        with self.assertRaisesRegex(SimulationError, "content_ref"):
            load_fixture_bytes(canonical_bytes(fixture))

    def test_negative_confirmation_does_not_write(self):
        with patch("builtins.print"):
            status = run_cli(
                ["simulate", "--fixture", str(SAMPLE), "--output-dir", str(self.root / "out")],
                input_func=lambda _: "NO",
            )
        self.assertEqual(status, 2)
        self.assertFalse((self.root / "out").exists())

    def test_explicit_confirmation_creates_hold_only(self):
        with patch("builtins.print"):
            status = run_cli(
                ["simulate", "--fixture", str(SAMPLE), "--output-dir", str(self.root)],
                input_func=lambda _: "YES",
            )
        self.assertEqual(status, 0)
        records = list(self.root.glob("SIM-OBS-*"))
        self.assertEqual(len(records), 1)
        item = json.loads((records[0] / "observation.json").read_text(encoding="utf-8"))
        self.assertEqual(item["review_result"], "HOLD")
        self.assertEqual(item["observation_result"], "SIMULATED_ONLY")
        self.assertFalse(item["authorized_to_publish"])
        self.assertTrue(item["confirmation_clicked_at"].endswith("Z"))

    def test_verifier_accepts_only_intact_simulation(self):
        result = verify_simulation(self.saved(), self.fixture)
        self.assertEqual(result["status"], "PASS_SIMULATION_ONLY")
        self.assertEqual(result["publish_authorization"], "NONE")

    def test_record_tamper_blocks(self):
        folder = self.saved()
        record_file = folder / "observation.json"
        record_file.write_text(record_file.read_text(encoding="utf-8").replace(
            "SIMULATED_ONLY", "CONFIRMED"
        ), encoding="utf-8")
        with self.assertRaises(SimulationError):
            verify_simulation(folder, self.fixture)

    def test_missing_index_blocks(self):
        folder = self.saved()
        (folder / "index.json").unlink()
        with self.assertRaises(SimulationError):
            verify_simulation(folder, self.fixture)

    def test_index_tamper_blocks(self):
        folder = self.saved()
        index_path = folder / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["content_ref"] = "sha256:" + "0" * 64
        index_path.write_bytes(canonical_bytes(index))
        with self.assertRaisesRegex(SimulationError, "index binding"):
            verify_simulation(folder, self.fixture)

    def test_other_fixture_binding_blocks(self):
        folder = self.saved()
        fixture = dict(self.fixture)
        fixture["source_url"] = "https://example.test/another"
        with self.assertRaisesRegex(SimulationError, "fixture binding"):
            verify_simulation(folder, fixture)

    def test_verifier_rejects_promoted_status_even_if_digest_recomputed(self):
        folder = self.saved()
        record_path, index_path = folder / "observation.json", folder / "index.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["review_result"] = "ACCEPTED"
        bytes_ = canonical_bytes(record)
        record_path.write_bytes(bytes_)
        index = json.loads(index_path.read_text(encoding="utf-8"))
        import hashlib
        index["artifact_sha256"] = hashlib.sha256(bytes_).hexdigest()
        index_path.write_bytes(canonical_bytes(index))
        with self.assertRaisesRegex(SimulationError, "unsafe simulation status"):
            verify_simulation(folder, self.fixture)

    def test_naive_clock_blocks(self):
        with self.assertRaisesRegex(SimulationError, "timezone-aware"):
            build_simulation_record(self.fixture, now=lambda: datetime(2026, 11, 9))

    def test_fixture_change_during_confirmation_blocks_without_output(self):
        mutable = self.root / "mutable.json"
        mutable.write_bytes(self.raw)
        def modify_then_confirm(_):
            mutable.write_bytes(self.raw + b" ")
            return "YES"
        with patch("builtins.print"):
            result = run_cli(
                ["simulate", "--fixture", str(mutable), "--output-dir", str(self.root / "out")],
                input_func=modify_then_confirm,
            )
        self.assertEqual(result, 1)
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
