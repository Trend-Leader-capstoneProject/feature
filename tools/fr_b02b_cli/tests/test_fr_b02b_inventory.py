"""Synthetic protected creation authority + temporary files; never operating I/O."""

from dataclasses import replace
import json
from unittest.mock import Mock, patch
import unittest

import fr_b02b_inventory as inventory
import fr_b02b_native_store as native
import fr_b02b_observation as observation
import fr_b02b_review_service as service
import test_fr_b02b_native_store as fixtures


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        api = self.fixture.api
        root = api.folder / "separate-inventory"
        root.mkdir()
        ro_acl = native.AclPolicy("S-1-5-32-544", (
            (0, 0, 0x1F01FF, "S-1-5-18"), (0, 0, 0x1F01FF, "S-1-5-32-544"),
            (0, 0, 0x1200A9, self.fixture.policy.reviewer_sid)), 0x1004)
        file_acl = replace(ro_acl, aces=ro_acl.aces[:2] + ((0, 0, 0x120089, self.fixture.policy.reviewer_sid),))
        info = native.ObjectInfo(root, (1, "e" * 32), ro_acl, True, False, 1)
        api.records[root] = info
        root_spec = native.ApprovedObject(root, info.identity, ro_acl, True)
        self.policy = replace(self.fixture.policy, anchors=(*self.fixture.policy.anchors, root_spec))
        self.protection = inventory.InventoryPolicy(root_spec, file_acl)
        self.boundary = native.NativeStoreBoundary(self.policy, api)
        self.store = self.boundary.mirrored_store()
        self.publisher = inventory.ProtectedInventory(self.protection, self.boundary)
        self.event = self.fixture.base.pending.local_evidence_id
        self.path = root / ("inventory-" + self.event + ".json")
        self.gate = self.policy.control / "global.gate"
        api.inventory_creation_available = Mock(return_value=True)
        api.children = lambda handle: tuple(p.name for p in handle.iterdir())
        self.created_inventory = []

        def create_inventory(path, acl, parent):
            self.assertTrue(self.boundary.active)
            for source in (self.policy.primary, self.policy.backup):
                self.assertTrue((source / (".review-staging-" + self.event) / "index.json").exists())
            self.assertTrue((self.policy.primary / (".review-restore-" + self.event) / "index.json").exists())
            self.created_inventory.append(path)
            return api.create(path, acl, parent=parent)
        api.create_inventory = create_inventory  # TEST authority; no production seal is claimed.

    def stage(self):
        original = self.store.stage

        def recording(*args, **kwargs):
            return original(*args, **kwargs, restore_store=self.store.primary, inventory_store=self.publisher)

        with patch.object(self.store, "stage", side_effect=recording):
            return self.fixture.base.stage(store=self.store)

    def reader(self):
        api = self.fixture.api
        # New read-only adapter, using the synthetic authority's persisted object facts.
        view = fixtures.FakeApi(api.folder)
        view.allow_changes = False
        view.records = dict(api.records)
        view.volumes = dict(api.volumes)
        view.exists = lambda path: path.exists()
        view.children = lambda handle: tuple(p.name for p in handle.iterdir())
        view.create = Mock(side_effect=AssertionError("read-only mutation"))
        view.write = Mock(side_effect=AssertionError("read-only mutation"))
        view.mark_delete = Mock(side_effect=AssertionError("read-only mutation"))
        return view

    def test_record_after_restore_before_gate_release_and_verified_restart_load(self):
        result = self.stage()
        self.assertEqual(result.state, "HOLD")
        self.assertEqual(self.created_inventory, [self.path])
        self.assertFalse(self.gate.exists())
        view = self.reader()
        loaded = inventory.load_inventory(self.policy, self.protection, self.event, api=view)
        self.assertEqual(len(loaded.expected_objects), 15)
        observed = inventory.inspect_restart_with_inventory(self.policy, self.protection, self.event, api=self.reader())
        self.assertEqual(observed.reason, "UNCOMPLETED_HOLD")
        self.assertFalse(observed.valid_registration)
        view.create.assert_not_called()
        view.write.assert_not_called()

    def test_unavailable_authority_blocks_before_ce_writes_without_fallback(self):
        self.fixture.api.inventory_creation_available.return_value = False
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertFalse((self.policy.primary / (".review-staging-" + self.event)).exists())
        self.assertFalse(self.path.exists())
        self.assertFalse(self.gate.exists())

    def test_authority_revoked_after_ce_restore_keeps_gate_without_inventory(self):
        self.fixture.api.inventory_creation_available.side_effect = (True, True, False)
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertFalse(self.path.exists())
        self.assertTrue((self.policy.primary / (".review-restore-" + self.event) / "index.json").exists())

    def test_authority_failure_is_private_and_blocks_before_any_gate(self):
        self.fixture.api.inventory_creation_available.side_effect = OSError("private SID SDDL path")
        with self.assertRaises(service.ReviewBlocked) as blocked:
            self.stage()
        self.assertNotIn("private SID", str(blocked.exception))
        self.assertFalse(self.gate.exists())
        self.assertFalse(self.path.exists())

    def test_missing_or_mutable_root_policy_is_rejected(self):
        for protection in (None, replace(self.protection, file_acl=self.fixture.acl),
                           replace(self.protection, root=replace(self.protection.root,
                                                               acl=self.fixture.acl))):
            with self.subTest(), self.assertRaises(native.StagingError):
                inventory.ProtectedInventory(protection, self.boundary)

    def test_partial_inventory_write_keeps_gate_sources_and_partial_record(self):
        write = self.fixture.api.write

        def partial(handle, raw):
            if handle == self.path:
                handle.write_bytes(raw[:9])
                raise native.NativeError(112)
            write(handle, raw)
        self.fixture.api.write = partial
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.gate.exists())
        self.assertEqual(len(self.path.read_bytes()), 9)
        self.assertTrue((self.policy.backup / (".review-staging-" + self.event) / "index.json").exists())
        self.assertEqual(inventory.inspect_restart_with_inventory(
            self.policy, self.protection, self.event, api=self.reader()).classification, "HOLD")

    def test_duplicate_inventory_never_overwrites_or_regenerates_from_ce(self):
        self.path.write_bytes(b"preserve existing")
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertFalse((self.policy.primary / (".review-staging-" + self.event)).exists())
        self.assertEqual(self.path.read_bytes(), b"preserve existing")

    def test_tampered_inventory_or_changed_descriptor_is_not_loadable(self):
        self.stage()
        original = self.path.read_bytes()
        self.path.write_bytes(original[:19])
        with self.assertRaises(native.StagingError):
            inventory.load_inventory(self.policy, self.protection, self.event, api=self.reader())
        self.path.write_bytes(original)
        view = self.reader()
        view.records[self.path] = replace(view.records[self.path], acl=self.fixture.acl)
        with self.assertRaises(native.StagingError):
            inventory.load_inventory(self.policy, self.protection, self.event, api=view)

    def test_gate_release_failure_never_returns_record_receipt(self):
        self.fixture.api.bad_release = True
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertTrue(self.path.exists())
        self.assertTrue(self.gate.exists())

    def test_strict_schema_rejects_partial_duplicate_extra_and_noncanonical_records(self):
        self.stage()
        raw = self.path.read_bytes()
        bad = [raw[:10], raw.replace(b'{"local_evidence_id":', b'{"state":"HOLD","local_evidence_id":', 1),
               json.dumps(json.loads(raw), indent=2).encode(), b'{}', raw + b" "]
        for change in ("unknown", "self_hash", "identity", "duplicate_object", "bool_ace"):
            document = json.loads(raw)
            if change in ("unknown", "self_hash"):
                document[change] = observation.digest(raw)
            elif change == "identity":
                document["objects"][0]["identity"][0] = True
            elif change == "duplicate_object":
                document["objects"][1] = document["objects"][0]
            else:
                document["objects"][0]["acl"]["aces"][0][0] = False
            bad.append(observation.canonical_bytes(document))
        for value in bad:
            with self.subTest(size=len(value)), self.assertRaises(native.StagingError):
                inventory.decode_inventory(value, self.policy, self.protection, self.event)

    def test_policy_and_observation_binding_cannot_be_replaced(self):
        self.stage()
        raw = self.path.read_bytes()
        changed = replace(self.policy, reviewer_sid="S-1-5-21-9-9-9-9")
        for policy, event in ((changed, self.event), (self.policy, "LOCAL-OBS-" + "f" * 32)):
            with self.subTest(), self.assertRaises(native.StagingError):
                inventory.decode_inventory(raw, policy, self.protection, event)

    def test_new_inventory_acl_is_verified_before_private_payload(self):
        create = self.fixture.api.create_inventory

        def unsafe(path, acl, parent):
            result = create(path, acl, parent)
            self.fixture.api.records[path] = replace(self.fixture.api.records[path], acl=self.fixture.acl)
            return result
        self.fixture.api.create_inventory = unsafe
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertEqual(self.path.read_bytes(), b"")
        self.assertTrue(self.gate.exists())

    def test_record_tampering_during_readback_keeps_gate_and_does_not_repair(self):
        flush = self.fixture.api.flush

        def tamper(handle):
            flush(handle)
            if handle == self.path:
                handle.write_bytes(b"tampered private record")
        self.fixture.api.flush = tamper
        with self.assertRaises(service.ReviewBlocked):
            self.stage()
        self.assertEqual(self.path.read_bytes(), b"tampered private record")
        self.assertTrue(self.gate.exists())

    def test_loader_root_identity_and_unknown_files_are_not_self_approved(self):
        self.stage()
        view = self.reader()
        root = self.protection.root.path
        view.records[root] = replace(view.records[root], identity=(1, "f" * 32))
        with self.assertRaises(native.StagingError):
            inventory.load_inventory(self.policy, self.protection, self.event, api=view)
        (root / "unexpected.partial").write_bytes(b"preserve")
        with self.assertRaises(native.StagingError):
            inventory.load_inventory(self.policy, self.protection, self.event, api=self.reader())
        self.assertEqual((root / "unexpected.partial").read_bytes(), b"preserve")

    def test_no_restore_or_wrong_gate_binding_blocks_before_changes(self):
        with self.assertRaises(native.StagingError):
            self.store.stage(self.fixture.base.pending.evidence, self.fixture.base.metadata(),
                             revalidate_input=Mock(), inventory_store=self.publisher)
        other = native.NativeStoreBoundary(self.policy, self.fixture.api)
        publisher = inventory.ProtectedInventory(self.protection, other)
        with self.assertRaises(native.StagingError):
            self.store.stage(self.fixture.base.pending.evidence, self.fixture.base.metadata(),
                             revalidate_input=Mock(), restore_store=self.store.primary, inventory_store=publisher)
        self.assertFalse(self.gate.exists())


if __name__ == "__main__":
    unittest.main()
