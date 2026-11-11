"""Service identity policy independent of argparse, Windows and persistence."""

import unittest
from pathlib import Path
from unittest.mock import patch

import fr_b02b_review_service as service
import fr_b02b_windows_auth as windows_auth


class ReviewServiceTests(unittest.TestCase):
    def test_service_blocks_failed_or_missing_process_sid_without_raw_diagnostics(self):
        private_diagnostic = "synthetic-private-SID-provider-diagnostic"
        for outcome in (OSError(private_diagnostic), None, ""):
            with self.subTest(outcome=type(outcome).__name__), \
                    patch.object(windows_auth, "get_current_process_sid") as lookup:
                if isinstance(outcome, Exception):
                    lookup.side_effect = outcome
                else:
                    lookup.return_value = outcome
                with self.assertRaises(service.ReviewBlocked) as blocked:
                    service.require_process_sid()
                lookup.assert_called_once_with()
                self.assertEqual(str(blocked.exception), "reviewer identity unavailable")
                self.assertNotIn(private_diagnostic, str(blocked.exception))

    def test_sid_lookup_success_alone_cannot_complete_registration(self):
        # Isolate policy: input validation succeeds, but no protected role/store
        # has been configured. This must never become a registration success.
        with patch.object(service, "_load_verified_observation", return_value={}), \
                patch.object(windows_auth, "get_current_process_sid",
                             return_value="S-1-5-21-100-200-300-1001") as lookup:
            with self.assertRaisesRegex(
                service.ReviewBlocked, "^protected review registration is not configured$"
            ):
                service.review_register(Path("synthetic.zip"), Path("synthetic-record"))
            lookup.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
