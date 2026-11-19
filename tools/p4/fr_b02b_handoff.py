"""Internal observation of protected history; never a reusable authorization token.

Synthetic stores exercise composition only. Every result retains operational and
time HOLD, including Native results. No registration, repair or resolver writes.
"""

from dataclasses import dataclass, field

import fr_b02b_registration as registration
from fr_b02b_binding import ExpectedBinding, verify_binding
from fr_b02b_protected_store import MirroredEvidenceStore, ProtectedEvidenceStore
from fr_b02b_review_service import require_process_sid
from fr_b02b_reviewer_allowlist import require_authorized_sid


@dataclass(frozen=True)
class HandoffAssessment:
    binding_status: str = "UNVERIFIED"
    latest_registration: bool | None = None
    current_review_state: str | None = None
    reason: str = "PROTECTED_HISTORY_UNVERIFIED"
    protected_inventory: str = "UNVERIFIED"
    operational_handoff: str = field(default="HOLD", init=False)
    publish_authorization: str = field(default="NONE", init=False)
    observation_time: str = field(default="HOLD", init=False)


def inspect_handoff(mirror, expected: ExpectedBinding, *, allowlist_source):
    """Revalidate identity, protection and the same history inside the existing Gate.

    The caller supplies the existing configured mirror, not a verdict/provider
    claiming ACCEPTED. Return only after successful Gate release. This receipt
    describes an observation and cannot authorize a later publication.
    """
    try:
        if not isinstance(expected, ExpectedBinding):
            raise TypeError("comparison required")
        if not isinstance(mirror, MirroredEvidenceStore):
            raise TypeError("configured mirror required")
        registration._id(expected.registration_id)
        stores = (mirror.primary, mirror.backup)
        if any(not isinstance(s, ProtectedEvidenceStore) for s in stores):
            raise TypeError("stores unavailable")
        roots = tuple(s.root for s in stores)
        layout, gate = mirror.verify_layout, mirror.exclusive_section
        if not callable(layout) or not callable(gate):
            raise TypeError("Gate/protection unavailable")
        provider = registration._native_provider(stores)
        final = registration._final_inventory(provider)
        if provider is not None and (final is None or layout != provider.verify_layout
                                     or gate != provider.exclusive_section):
            raise ValueError("Native Gate/inventory mismatch")
        sid = None

        def environment():
            nonlocal sid
            if (stores != (mirror.primary, mirror.backup)
                    or tuple(s.root for s in stores) != roots
                    or mirror.verify_layout != layout or mirror.exclusive_section != gate
                    or registration._native_provider(stores) is not provider
                    or registration._final_inventory(provider) is not final
                    or layout(*roots) is not True):
                raise ValueError("protection changed")
            current = require_authorized_sid(require_process_sid(), allowlist_source)
            if sid is not None and sid != current:
                raise ValueError("identity changed")
            sid = current

        with gate():
            environment()
            history = registration.RegistrationHistory(stores, revalidate_input=environment)
            rid = expected.registration_id
            if rid not in history.manifests:
                result = HandoffAssessment(reason="REGISTRATION_MISSING")
            else:
                row = history.manifests[rid]
                # Use the bytes pinned and rechecked by this history, never reopen.
                folder = roots[0] / "registrations" / rid
                files = {name: history.saved[folder / name][1]
                         for name in registration.BASE_FILES}
                binding = verify_binding(
                    a1_archive_bytes=files["a1_archive.zip"],
                    observation_bytes=files["observation.json"],
                    index_bytes=files["index.json"],
                    registration_bytes=files["registration.json"], expected=expected)
                latest = history.tips[row["local_evidence_id"]] == rid
                state = "REVOKED" if history.revocations[rid] else row["review_result"]
                reason = ("BINDING_FAILED" if binding.binding_status != "MATCH" else
                          "REGISTRATION_NOT_LATEST" if not latest else
                          "REVIEW_" + state if state != "ACCEPTED" else
                          "OBSERVATION_ONLY_OPERATIONS_HOLD")
                result = HandoffAssessment(binding.binding_status, latest, state, reason,
                                           "VERIFIED" if final is not None else "UNVERIFIED")
            history.check()
            environment()
        return result
    except (ValueError, OSError, TypeError, KeyError, OverflowError):
        return HandoffAssessment()
