"""Contract checks against synthetic A1 V02 examples, never operational approvals."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from fr_b02b_cli import run_cli

from fr_b02b_a1_adapter import (
    A1InspectionError,
    calculate_content_ref,
    inspect_a1_json,
    inspect_a1_paths,
    inspect_a1_zip,
    A1_ZIP_APPROVALS,
    A1_ZIP_BATCH,
)

SCHEMA = 'A1_RECONCILE_V02'
POLICY = 'v0.3_POLICY_CONFIRMED'


def example():
    """Synthetic fixture with the exact original A1 v0.2 file shape."""
    content = {
        'title': '가상 릴리스 안내',
        'summary': '가상 테스트 자료입니다.',
        'category_refs': ['IT_DIGITAL/소프트웨어·앱'],
        'source_platform': 'ETC',
        'source_url': 'https://example.test/release',
        'source_title': '가상 프로젝트 공식 안내',
        'thumbnail_url': None,
    }
    digest = calculate_content_ref('SIM-TREND-001', content, 'EDITORIAL_LABEL', 'SIM-E-G4-LABEL-001')
    approvals = {
        'schema': SCHEMA, 'policy_version': POLICY,
        'records': [{
            'trend_ref': 'SIM-TREND-001',
            'review_evidence_id': 'SIM-G4-001',
            'rights_evidence_id': 'SIM-RIGHTS-001',
            'approved_by': 'SIM-FEATURE-OWNER',
            'approved_at': '2026-11-09T15:00:00+09:00',
            'g4_result': 'PASS', 'approval_status': 'APPROVED',
            'risk_class': 'GENERAL_ELIGIBLE',
            'rights_checked': True, 'link_checked': True, 'no_reproduction_checked': True,
            'google_rss_derived': False, 'revoked': False,
            'policy_version': POLICY,
            'source_title_origin': 'EDITORIAL_LABEL',
            'source_label_evidence_id': 'SIM-E-G4-LABEL-001',
            'content_ref': digest,
        }],
    }
    batch = {
        'schema': SCHEMA, 'policy_version': POLICY,
        'batch_id': 'SIM-REVIEW-ONLY', 'profile': 'MVP-A',
        'g6_status': 'HOLD', 'items': [{
            'trend_ref': 'SIM-TREND-001',
            'source_title_origin': 'EDITORIAL_LABEL',
            'content': content,
        }],
    }
    return approvals, batch


class A1ReadOnlyInspectionTests(unittest.TestCase):
    def setUp(self):
        self.approvals, self.batch = example()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self):
        a, b = self.root / 'approvals.json', self.root / 'batch.json'
        a.write_text(json.dumps(self.approvals, ensure_ascii=False), encoding='utf-8')
        b.write_text(json.dumps(self.batch, ensure_ascii=False), encoding='utf-8')
        return a, b


    def write_zip(self, *, with_approvals=True, with_batch=True):
        archive_path = self.root / 'synthetic_g5_a1.zip'
        with ZipFile(archive_path, 'w', compression=ZIP_DEFLATED) as archive:
            if with_approvals:
                archive.writestr(A1_ZIP_APPROVALS, json.dumps(self.approvals, ensure_ascii=False))
            if with_batch:
                archive.writestr(A1_ZIP_BATCH, json.dumps(self.batch, ensure_ascii=False))
        return archive_path

    def test_known_zip_inspection_is_readonly(self):
        archive_path = self.write_zip()
        before = archive_path.read_bytes()
        result = inspect_a1_zip(archive_path)
        self.assertEqual(result['status'], 'A1_STRUCTURE_MATCH_REVIEW_ONLY')
        self.assertEqual(result['a1_authorized_to_publish'], 0)
        self.assertEqual(before, archive_path.read_bytes())
        self.assertEqual(sorted(x.name for x in self.root.iterdir()), ['synthetic_g5_a1.zip'])

    def test_zip_missing_batch_rejected(self):
        archive_path = self.write_zip(with_batch=False)
        with self.assertRaisesRegex(A1InspectionError, 'not found'):
            inspect_a1_zip(archive_path)

    def test_zip_unknown_member_shape_rejected(self):
        self.batch['items'][0]['content_ref'] = 'sha256:' + '0'*64
        archive_path = self.write_zip()
        with self.assertRaisesRegex(A1InspectionError, 'batch.items'):
            inspect_a1_zip(archive_path)

    def test_cli_inspect_zip_does_not_modify_input(self):
        archive_path = self.write_zip()
        before = archive_path.read_bytes()
        with patch('builtins.print') as output:
            exit_status = run_cli(['inspect-a1-zip', '--zip', str(archive_path)])
        self.assertEqual(exit_status, 0)
        self.assertEqual(before, archive_path.read_bytes())
        self.assertEqual(json.loads(output.call_args[0][0])['publish_authorization'], 'NONE')

    def test_zip_invalid_file_rejected(self):
        archive_path = self.root / 'not_zip.zip'
        archive_path.write_bytes(b'not a zip')
        with self.assertRaisesRegex(A1InspectionError, 'invalid'):
            inspect_a1_zip(archive_path)

    def test_exact_original_a1_batch_item_three_keys(self):
        self.assertEqual(set(self.batch['items'][0]), {'trend_ref', 'content', 'source_title_origin'})
        self.assertIn('review_evidence_id', self.approvals['records'][0])
        self.assertIn('content_ref', self.approvals['records'][0])
        self.assertEqual(inspect_a1_json(self.approvals, self.batch)['a1_reconcile_reason'],
                         'ELIGIBLE_FOR_REVIEW_ONLY')

    def test_rejects_legacy_v02_poc_extra_batch_item_keys(self):
        self.batch['items'][0]['content_ref'] = self.approvals['records'][0]['content_ref']
        with self.assertRaisesRegex(A1InspectionError, 'batch.items'):
            inspect_a1_json(self.approvals, self.batch)

    def test_ineligible_when_rights_check_false(self):
        self.approvals['records'][0]['rights_checked'] = False
        with self.assertRaisesRegex(A1InspectionError, 'G4_CHECK_INCOMPLETE'):
            inspect_a1_json(self.approvals, self.batch)

    def test_ineligible_when_time_missing(self):
        self.approvals['records'][0]['approved_at'] = None
        with self.assertRaisesRegex(A1InspectionError, 'APPROVAL_EVIDENCE_INCOMPLETE'):
            inspect_a1_json(self.approvals, self.batch)

    def test_ineligible_when_time_naive(self):
        self.approvals['records'][0]['approved_at'] = '2026-11-09T15:00:00'
        with self.assertRaisesRegex(A1InspectionError, 'APPROVAL_EVIDENCE_INCOMPLETE'):
            inspect_a1_json(self.approvals, self.batch)

    def test_missing_approval_fields_rejected(self):
        del self.approvals['records'][0]['rights_evidence_id']
        with self.assertRaisesRegex(A1InspectionError, 'approvals.records'):
            inspect_a1_json(self.approvals, self.batch)

    def test_missing_profile_rejected(self):
        del self.batch['profile']
        with self.assertRaisesRegex(A1InspectionError, 'batch'):
            inspect_a1_json(self.approvals, self.batch)

    def test_wrong_batch_profile_rejected(self):
        self.batch['profile'] = 'RSS-OPS'
        with self.assertRaisesRegex(A1InspectionError, 'profile'):
            inspect_a1_json(self.approvals, self.batch)

    def test_duplicate_approval_records_rejected(self):
        self.approvals['records'].append(deepcopy(self.approvals['records'][0]))
        with self.assertRaisesRegex(A1InspectionError, 'duplicate'):
            inspect_a1_json(self.approvals, self.batch)

    def test_eligible_snapshot_does_not_authenticate_observation(self):
        out = inspect_a1_json(self.approvals, self.batch)
        self.assertEqual(out['a1_authorized_to_publish'], 0)
        self.assertFalse(out['g4_authenticity_verified'])
        self.assertFalse(out['observation_evidence_verified'])
        self.assertEqual(out['publish_authorization'], 'NONE')

    def test_utf8_bom_supported_like_original(self):
        a, b = self.write()
        a.write_bytes(b'\xef\xbb\xbf' + a.read_bytes())
        self.assertEqual(inspect_a1_paths(a, b)['a1_reconcile_reason'],
                         'ELIGIBLE_FOR_REVIEW_ONLY')

    def test_source_title_none_offline_a1_not_p4_supported(self):
        approval = self.approvals['records'][0]
        item = self.batch['items'][0]
        item['content']['source_title'] = None
        item['source_title_origin'] = approval['source_title_origin'] = 'NONE'
        approval['source_label_evidence_id'] = None
        approval['content_ref'] = calculate_content_ref(
            item['trend_ref'], item['content'], 'NONE', None)
        result = inspect_a1_json(self.approvals, self.batch)
        self.assertEqual(result['a1_reconcile_reason'], 'ELIGIBLE_FOR_REVIEW_ONLY')
        self.assertFalse(result['p4_initial_adapter_source_title_supported'])

    def test_canonical_ref_matches_documented_python315_g4_snapshot(self):
        content = {
            'title': 'Python 3.15 정식 출시, 지연 가져오기와 frozendict 도입',
            'summary': 'Python 3.15가 2026년 10월 9일 출시됐다. 지연 가져오기와 변경할 수 없는 매핑 자료형 frozendict가 추가됐다.',
            'category_refs': ['IT_DIGITAL/소프트웨어·앱'],
            'source_platform': 'ETC',
            'source_url': 'https://www.python.org/downloads/release/python-3150/',
            'source_title': 'Python.org 공식 출시 안내',
            'thumbnail_url': None,
        }
        self.assertEqual(calculate_content_ref('PYTHON-315-MVP-A-001', content, 'EDITORIAL_LABEL', 'E-G4-05-PY315'), 'sha256:4584222134c7a420dcfd929c1e03f0b715ba332a2ebc78d266e1843a2d34c28f')

    def test_valid_synthetic_record_readonly(self):
        a, b = self.write()
        before = a.read_bytes(), b.read_bytes()
        result = inspect_a1_paths(a, b)
        self.assertEqual((a.read_bytes(), b.read_bytes()), before)
        self.assertEqual(result['status'], 'A1_STRUCTURE_MATCH_REVIEW_ONLY')
        self.assertEqual(result['publish_authorization'], 'NONE')
        self.assertEqual(result['source_url'], 'https://example.test/release')

    def test_modified_content_cannot_be_auto_rehashed(self):
        self.batch['items'][0]['content']['summary'] = '변경됨'
        with self.assertRaisesRegex(A1InspectionError, 'content_ref'):
            inspect_a1_json(self.approvals, self.batch)

    def test_changed_source_evidence_id_is_rejected(self):
        self.approvals['records'][0]['source_label_evidence_id'] = 'SIM-ANOTHER'
        with self.assertRaisesRegex(A1InspectionError, 'content_ref'):
            inspect_a1_json(self.approvals, self.batch)

    def test_changed_source_origin_is_rejected(self):
        self.batch['items'][0]['source_title_origin'] = 'NONE'
        with self.assertRaises(A1InspectionError):
            inspect_a1_json(self.approvals, self.batch)

    def test_wrong_review_evidence_is_rejected(self):
        self.approvals['records'][0]['review_evidence_id'] = ''
        with self.assertRaisesRegex(A1InspectionError, 'review_evidence_id'):
            inspect_a1_json(self.approvals, self.batch)

    def test_google_rss_record_is_rejected(self):
        self.approvals['records'][0]['google_rss_derived'] = True
        with self.assertRaises(A1InspectionError):
            inspect_a1_json(self.approvals, self.batch)

    def test_g6_pass_is_rejected(self):
        self.batch['g6_status'] = 'PASS'
        with self.assertRaisesRegex(A1InspectionError, 'G6'):
            inspect_a1_json(self.approvals, self.batch)

    def test_revoked_is_rejected(self):
        self.approvals['records'][0]['revoked'] = True
        with self.assertRaises(A1InspectionError):
            inspect_a1_json(self.approvals, self.batch)

    def test_missing_source_is_rejected(self):
        self.batch['items'][0]['content']['source_url'] = ''
        with self.assertRaises(A1InspectionError):
            inspect_a1_json(self.approvals, self.batch)

    def test_article_original_title_cannot_be_inferred(self):
        self.assertNotIn('source_label_evidence_id', self.batch['items'][0])
        # A1 only proves field consistency; does not independently establish authorship.
        self.assertEqual(inspect_a1_json(self.approvals, self.batch)['rights_verified'], False)

    def test_duplicate_json_keys_rejected(self):
        a, b = self.write()
        a.write_text('{"schema":"A1_RECONCILE_V02","schema":"A1_RECONCILE_V02"}', encoding='utf-8')
        with self.assertRaisesRegex(A1InspectionError, 'duplicate'):
            inspect_a1_paths(a, b)

    def test_same_file_for_both_inputs_rejected(self):
        a, _ = self.write()
        with self.assertRaises(A1InspectionError):
            inspect_a1_paths(a, a)

    def test_extra_content_field_rejected(self):
        self.batch['items'][0]['content']['observed_at'] = '2026-11-09T16:00+09:00'
        with self.assertRaisesRegex(A1InspectionError, 'content'):
            inspect_a1_json(self.approvals, self.batch)

    def test_multiple_batch_items_not_supported_in_this_phase(self):
        self.batch['items'].append(deepcopy(self.batch['items'][0]))
        with self.assertRaisesRegex(A1InspectionError, 'one'): inspect_a1_json(self.approvals, self.batch)

    def test_malformed_ipv6_url_fail_closed(self):
        self.batch['items'][0]['content']['source_url'] = 'https://[bad-host/release'
        with self.assertRaises(A1InspectionError):
            inspect_a1_json(self.approvals, self.batch)

    def test_cli_returns_review_only_without_modifying_manifest(self):
        a, b = self.write()
        before = a.read_bytes(), b.read_bytes()
        with patch('builtins.print') as output:
            status = run_cli(['inspect-a1', '--approvals', str(a), '--batch', str(b)])
        self.assertEqual(status, 0)
        self.assertEqual((a.read_bytes(), b.read_bytes()), before)
        result = json.loads(output.call_args[0][0])
        self.assertEqual(result['status'], 'A1_STRUCTURE_MATCH_REVIEW_ONLY')
        self.assertEqual(result['publish_authorization'], 'NONE')

    def test_cli_rejects_changed_manifest_without_output(self):
        a, b = self.write()
        self.batch['g6_status'] = 'PASS'
        b.write_text(json.dumps(self.batch, ensure_ascii=False), encoding='utf-8')
        with patch('builtins.print'):
            status = run_cli(['inspect-a1', '--approvals', str(a), '--batch', str(b)])
        self.assertEqual(status, 1)

    def test_no_network_or_file_writes_in_inspection(self):
        a, b = self.write()
        with patch('socket.create_connection', side_effect=AssertionError('network!')), patch('pathlib.Path.write_bytes', side_effect=AssertionError('file write!')):
            self.assertEqual(inspect_a1_paths(a, b)['status'], 'A1_STRUCTURE_MATCH_REVIEW_ONLY')


if __name__ == '__main__':
    unittest.main()
