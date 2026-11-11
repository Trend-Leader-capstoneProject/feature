"""Graph rules over previously validated manifests; no trust/ACL claims."""

import unittest

from fr_b02b_inventory import registration_history_tip
from fr_b02b_registration import KEYS
from fr_b02b_protected_store import StagingError

EVENT = "LOCAL-OBS-1234567812344234a234123456789abc"
IDS = ["REG-OBS-" + prefix * 12 + "4" + prefix * 3 + "a" + prefix * 15 for prefix in "1234"]


def row(index, result="HOLD", parent=None):
    value = dict.fromkeys(KEYS, "already validated source")
    value.update(registration_id=IDS[index], local_evidence_id=EVENT,
                 review_result=result, supersedes_registration_id=parent,
                 reviewed_at_utc="2026-11-11T00:00:02Z",
                 registration_recorded_at_utc="2026-11-11T00:00:02Z")
    return value


class HistoryGraphTests(unittest.TestCase):
    def assert_conflict(self, rows):
        with self.assertRaises(StagingError):
            registration_history_tip(rows, EVENT)

    def test_empty_and_single_and_out_of_order_linear_history(self):
        self.assertIsNone(registration_history_tip([], EVENT))
        self.assertEqual(registration_history_tip([row(0)], EVENT), IDS[0])
        rows = [row(0), row(1, "REJECTED", IDS[0]), row(2, "HOLD", IDS[1]), row(3, "ACCEPTED", IDS[2])]
        self.assertEqual(registration_history_tip(list(reversed(rows)), EVENT), IDS[3])

    def test_duplicate_roots_branch_missing_parent_and_duplicate_ids_block(self):
        cases = [[row(0), row(1)], [row(0), row(1, parent=IDS[0]), row(2, parent=IDS[0])],
                 [row(1, parent=IDS[0])], [row(0), row(0)],
                 [row(0), row(1, parent=IDS[2]), row(2, parent=IDS[1])]]
        for rows in cases:
            with self.subTest(rows=rows):
                self.assert_conflict(rows)

    def test_self_link_cycle_and_accepted_parent_block(self):
        self.assert_conflict([row(0, parent=IDS[0])])
        self.assert_conflict([row(0, parent=IDS[1]), row(1, parent=IDS[0])])
        self.assert_conflict([row(0, "ACCEPTED"), row(1, parent=IDS[0])])

    def test_source_hash_binding_and_observation_identity_conflicts_block(self):
        for key in ("a1_archive_sha256", "observation_sha256", "index_sha256",
                    "content_ref", "source_url", "local_evidence_id"):
            child = row(1, parent=IDS[0])
            child[key] = "different validated source"
            with self.subTest(key=key):
                self.assert_conflict([row(0), child])

    def test_backward_review_clock_blocks_even_for_linear_links(self):
        child = row(1, parent=IDS[0])
        child["reviewed_at_utc"] = "2026-11-11T00:00:01Z"
        self.assert_conflict([row(0), child])


if __name__ == "__main__":
    unittest.main()
