"""Internal B-option request boundary; no IPC, elevation or Native adapter.

Only trusted bootstrap code may supply these dependencies. Python objects are
not an OS authentication mechanism. No concrete authentication/creation provider
is shipped, and nothing here is connected to the public CLI.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
import re
from threading import Lock
from types import MappingProxyType

import fr_b02b_observation as observation
from fr_b02b_a1_adapter import MAX_ARCHIVE_BYTES, _load_a1_snapshot_bytes
from fr_b02b_protected_store import PENDING_KEYS, _validated_files
from fr_b02b_registration import _id, _now, _parse
from fr_b02b_review_service import ReviewBlocked, ReviewCancelled
from fr_b02b_reviewer_allowlist import AllowlistSource, _valid_sid, require_authorized_sid


@dataclass(frozen=True, repr=False)
class RegisterRequest:
    """Exact reviewed bytes only: no paths, ACLs, roots, commands or final IDs."""

    pending_bytes: bytes
    archive_bytes: bytes
    observation_bytes: bytes
    index_bytes: bytes


@dataclass(frozen=True, repr=False)
class RevokeRequest:
    registration_id: str
    registration_sha256: str
    revoker_sid: str  # Untrusted claim, never authentication evidence.
    reason: str


class AuthenticatedPeer(ABC):
    """Live transport-authenticated caller, distinct from helper process token.

    Future OS adapter must retain/bind the authenticated connection/token for
    this scope. revalidate must fail on disconnect, cancellation or token change.
    No constructor accepting an SID string is provided.
    """

    @abstractmethod
    def requester_sid(self) -> str: ...

    @abstractmethod
    def revalidate(self) -> None: ...


class RequestAuthenticator(ABC):
    @abstractmethod
    def authenticate(self) -> AbstractContextManager[AuthenticatedPeer]:
        """Context manager yielding AuthenticatedPeer; never consult body SID."""
        ...


class CreationSession(ABC):
    """Helper-only scope, already holding its sole global Gate.

    apply must resolve duplicates/history under that Gate, bind revoke to the
    verified ACCEPTED manifest hash, and use checkpoint before/after each
    mutation. Partial failures leave HOLD residue, never repair/delete/retry.
    verify must independently validate both copies, restore evidence, final
    inventory and result binding, including the existing-result duplicate path.
    Neither method may acquire another Gate or collect human judgments.
    """

    @abstractmethod
    def apply(self, request: RegisterRequest | RevokeRequest,
              evidence: observation.VerifiedObservation | None,
              checkpoint: Callable[[], None]) -> object: ...

    @abstractmethod
    def verify(self, request: RegisterRequest | RevokeRequest, result: object,
               checkpoint: Callable[[], None]) -> bool: ...


class ProtectedCreationBoundary(ABC):
    @abstractmethod
    def exclusive_section(self) -> AbstractContextManager[CreationSession]:
        """Own the sole Gate; yield CreationSession; release failure must raise."""
        ...


@dataclass(frozen=True)
class BoundaryReceipt:
    """Internal boundary completion only; not an operational registration ID."""

    publish_authorization: str = field(default="NONE", init=False)
    external_eligible: bool = field(default=False, init=False)


def _validate(request):
    if type(request) is RegisterRequest:
        for raw, limit in ((request.archive_bytes, MAX_ARCHIVE_BYTES),
                           (request.pending_bytes, observation.MAX_RECORD_BYTES),
                           (request.observation_bytes, observation.MAX_RECORD_BYTES),
                           (request.index_bytes, observation.MAX_RECORD_BYTES)):
            if type(raw) is not bytes or not 0 < len(raw) <= limit:
                raise ValueError("invalid request bytes")
        pending = _parse(request.pending_bytes, PENDING_KEYS)
        snapshot = _load_a1_snapshot_bytes(request.archive_bytes)
        record = observation._validate_records(snapshot, request.observation_bytes,
            request.index_bytes, pending["local_evidence_id"])
        evidence = observation.VerifiedObservation(snapshot, MappingProxyType(record),
            request.observation_bytes, request.index_bytes)
        _validated_files(evidence, request.pending_bytes)
        if observation._timestamp(pending["reviewed_at_utc"]) > _now():
            raise ValueError("future review")
        sid = pending["reviewer_sid"]
    elif type(request) is RevokeRequest:
        _id(request.registration_id)
        if (type(request.registration_sha256) is not str
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", request.registration_sha256)
                or type(request.reason) is not str or not request.reason.strip()
                or len(request.reason) > 500):
            raise ValueError("invalid revocation request")
        sid, evidence = request.revoker_sid, None
    else:
        raise ValueError("unsupported request")
    if not _valid_sid(sid):
        raise ValueError("invalid claimed identity")
    return sid, evidence


class HelperRequestCore:
    """One attempt per instance, including failed/cancelled attempts.

    Cross-process replay/semantic duplicates require protected history under the
    Gate, NOT an in-memory request-ID cache. All providers are trusted internal
    dependencies, never deserialized from a request or selected by the caller.
    """

    def __init__(self, *, authenticator: RequestAuthenticator | None = None,
                 creation: ProtectedCreationBoundary | None = None,
                 allowlist_source: AllowlistSource | None = None):
        self._authenticator = authenticator
        self._creation = creation
        self._allowlist_source = allowlist_source
        self._attempt = Lock()

    def execute(self, request: RegisterRequest | RevokeRequest) -> BoundaryReceipt:
        if not self._attempt.acquire(blocking=False):
            raise ReviewBlocked("helper attempt already consumed; HOLD")
        try:
            if (not isinstance(self._authenticator, RequestAuthenticator)
                    or not isinstance(self._creation, ProtectedCreationBoundary)):
                raise ReviewBlocked("helper boundary is not configured; HOLD")
            claimed_sid, evidence = _validate(request)
            authenticated_completion = False
            # Authenticate before entering the protected creation scope. This
            # must never resolve the elevated helper's own SID as the caller.
            with self._authenticator.authenticate() as peer:
                if not isinstance(peer, AuthenticatedPeer):
                    raise ValueError("authenticated peer unavailable")
                sid = peer.requester_sid()
                last_clock = None

                def checkpoint():
                    nonlocal last_clock
                    peer.revalidate()
                    if (not _valid_sid(sid) or sid != claimed_sid
                            or peer.requester_sid() != sid):
                        raise ValueError("authenticated identity changed")
                    require_authorized_sid(sid, self._allowlist_source)
                    _validate(request)
                    clock = _now()
                    if last_clock is not None and clock < last_clock:
                        raise ValueError("helper clock regressed")
                    last_clock = clock

                checkpoint()
                creation_completion = False
                with self._creation.exclusive_section() as session:
                    if not isinstance(session, CreationSession):
                        raise ValueError("creation session unavailable")
                    checkpoint()
                    result = session.apply(request, evidence, checkpoint)
                    checkpoint()
                    if session.verify(request, result, checkpoint) is not True:
                        raise ValueError("protected result verification failed")
                    checkpoint()
                    creation_completion = True
                if not creation_completion:
                    raise ValueError("creation scope suppressed a failure")
                checkpoint()
                authenticated_completion = True
            if not authenticated_completion:
                raise ValueError("authentication scope suppressed a failure")
            return BoundaryReceipt()  # Both context exits must succeed first.
        except (ReviewCancelled, KeyboardInterrupt, EOFError):
            raise ReviewCancelled() from None
        except (OSError, ValueError, TypeError, RuntimeError, OverflowError):
            raise ReviewBlocked("helper authentication/request/creation failed; HOLD") from None
