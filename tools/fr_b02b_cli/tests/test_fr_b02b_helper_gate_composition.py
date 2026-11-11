"""H1-04 negative composition only; no operational adapter or OS security proof."""

from contextlib import contextmanager
import json
import unittest
from unittest.mock import Mock, patch

import fr_b02b_helper_core as helper
import fr_b02b_protected_store as storage
import fr_b02b_registration as registration
import fr_b02b_review_service as service
import test_fr_b02b_helper_core as peers
import test_fr_b02b_registration_core as fixtures


class SingleEntryGate:
    def __init__(self):
        self.owner = None
        self.events = []

    @contextmanager
    def enter(self, owner):
        self.events.append(("attempt", owner))
        if self.owner is not None:
            self.events.append(("denied", owner))
            raise OSError("synthetic nested Gate denial")
        self.owner = owner
        self.events.append(("acquire", owner))
        try:
            yield
        finally:
            self.events.append(("release", owner))
            self.owner = None


class DelegatingBoundary(helper.ProtectedCreationBoundary, helper.CreationSession):
    """Deliberately invalid test wiring: delegate to a Gate-owning Core entry."""

    def __init__(self, gate, delegate):
        self.gate, self.delegate = gate, delegate
        self.verify = Mock(side_effect=AssertionError("blocked apply cannot verify"))

    @contextmanager
    def exclusive_section(self):
        with self.gate.enter("helper"):
            yield self

    def apply(self, request, evidence, checkpoint):
        checkpoint()
        return self.delegate(request, evidence, checkpoint)

    def verify(self, request, result, checkpoint):
        raise AssertionError("blocked apply cannot verify")


class HelperGateCompositionTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.RegistrationCoreTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.base = self.case.base
        self.source = self.base.fixture.source
        self.mirror = self.case.mirror

    def snapshot(self):
        # Include directory names so even empty new staging/residue is detected.
        roots = (*[s.root for s in self.case.stores], self.case.fixture.target.root)
        return {p: p.read_bytes() if p.is_file() else None
                for root in roots for p in root.rglob("*")}

    def assert_nested_core_blocked(self, request, delegate):
        before, originals = self.snapshot(), self.base.originals()
        gate = SingleEntryGate()
        self.mirror.exclusive_section = lambda: gate.enter("core")
        boundary = DelegatingBoundary(gate, delegate)
        core = helper.HelperRequestCore(authenticator=peers.Authenticator(peers.Peer()),
            creation=boundary, allowlist_source=self.source)
        with patch.object(storage, "_write_exclusive") as writes, \
                patch.object(registration, "uuid4") as ids, \
                patch.object(service, "require_process_sid") as process_sid:
            with self.assertRaisesRegex(service.ReviewBlocked, "HOLD"):
                core.execute(request)
            writes.assert_not_called()
            ids.assert_not_called()
            process_sid.assert_not_called()  # Denial precedes legacy process auth.
        boundary.verify.assert_not_called()
        self.assertEqual(gate.events, [("attempt", "helper"), ("acquire", "helper"),
            ("attempt", "core"), ("denied", "core"), ("release", "helper")])
        self.assertIsNone(gate.owner)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.base.originals(), originals)

    def test_registration_stage_with_real_core_cannot_reacquire_helper_gate(self):
        evidence = self.base.pending.evidence
        request = helper.RegisterRequest(self.base.metadata(), evidence.a1_snapshot.archive_bytes,
            evidence.record_bytes, evidence.index_bytes)

        def delegate(request, evidence, checkpoint):
            plan = registration.RegistrationCore(None, evidence, request.pending_bytes)
            return self.mirror.stage(evidence, request.pending_bytes, revalidate_input=checkpoint,
                restore_store=self.case.fixture.target, registration_core=plan)

        self.assert_nested_core_blocked(request, delegate)

    def test_revocation_history_core_cannot_reacquire_helper_gate(self):
        completed = self.case.call().completion
        manifest = json.loads((self.case.folders[0] / "registration.json").read_bytes())
        self.assertEqual(manifest["reviewer_sid"], peers.SID)
        self.assertEqual(manifest["publish_authorization"], "NONE")
        self.assertEqual(completed.publish_authorization, "NONE")
        request = helper.RevokeRequest(completed.registration_id, completed.registration_sha256,
            peers.SID, "synthetic withdrawal")

        def delegate(request, evidence, checkpoint):
            return self.mirror.revoke(request.registration_id, reason=request.reason,
                allowlist_source=self.source)

        self.assert_nested_core_blocked(request, delegate)
