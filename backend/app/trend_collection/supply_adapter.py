"""Source-specific independent verification; no DB or operational approval."""

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.trend_collection.godot_release_collector import (
    RELEASES,
    REPO,
    CollectionError,
    RateLimited,
    _parse,
    _request_json,
    collect,
)
from app.trend_collection.igdb_adapter import (
    SCOPE as IGDB_SCOPE,
    SOURCE_ID as IGDB_SOURCE_ID,
)
from app.trend_collection.igdb_supply_snapshot import IgdbSnapshotBridge
from app.trend_collection.publication_policy import (
    ContentSnapshot,
    PersistableSnapshot,
    evaluate_release,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview

SEARCHAPI_SOURCE_ID = "searchapi-kr-reviewed-news"
SEARCHAPI_SCOPE = "SEARCHAPI_REVIEWED_NEWS_V1"
INTEREST_SOURCE_ID = "searchapi-kr-interest"
INTEREST_SCOPE = "SEARCHAPI_KR_INTEREST_V1"
INTEREST_HYBRID_SCOPE = "SEARCHAPI_KR_INTEREST_HYBRID_V1"
INTEREST_RELATED_SCOPE = "SEARCHAPI_KR_INTEREST_RELATED_V1"


class SupplyBlocked(RuntimeError):
    """Bounded diagnostic only."""


class SourceAdapter(Protocol):
    scope: str

    def collect_preview(self) -> dict | None: ...

    def verify(self, preview: dict, now: datetime) -> PersistableSnapshot: ...


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise SupplyBlocked("INVALID_TIME")
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise SupplyBlocked("INVALID_TIME") from None


class GodotAdapter:
    scope = "GODOT_FACTS_LINK_V1"

    def __init__(self, request_json=None):
        self._request_json = (
            request_json if request_json is not None
            else lambda url: _request_json(url, enforce_rate_limit=True)
        )

    def collect_preview(self) -> dict:
        evidence = collect(request_json=self._request_json)
        return build_rule_first_preview(evidence, datetime.now(timezone.utc))

    def verify(self, preview: dict, now: datetime) -> ContentSnapshot:
        if type(preview) is not dict:
            raise SupplyBlocked("INVALID_PREVIEW")
        identity = preview.get("candidate_identity")
        if not isinstance(identity, str) or not re.fullmatch(
            rf"github-release:{re.escape(REPO)}:[1-9][0-9]{{0,19}}", identity,
        ):
            raise SupplyBlocked("INVALID_SOURCE_IDENTITY")
        observed = utc(preview.get("observed_at_utc"))
        if not timedelta(0) <= now - observed <= timedelta(minutes=10):
            raise SupplyBlocked("STALE_PREVIEW")
        rid = int(identity.rsplit(":", 1)[1])
        try:
            evidence = _parse(self._request_json(f"{RELEASES}/{rid}"))
        except RateLimited:
            raise
        except CollectionError:
            raise SupplyBlocked("SOURCE_DETAIL_UNAVAILABLE") from None
        if evidence.release_id != rid or not (
            timedelta(0) <= now - evidence.published_at <= timedelta(days=7)
        ):
            raise SupplyBlocked("SOURCE_DETAIL_MISMATCH")
        decision = evaluate_release(evidence, observed, preview)
        if decision.decision != "DEFERRED" or decision.snapshot is None:
            raise SupplyBlocked("PREVIEW_MISMATCH")
        # The AP-3C-1 decision remains review-only; no authority is inherited.
        return decision.snapshot


class IgdbOperationalAdapter:
    """IGDB bridge; unbound registry entries cannot perform I/O or verify."""

    scope = IGDB_SCOPE

    def __init__(self, query=None):
        self._bridge = IgdbSnapshotBridge(query) if query is not None else None

    def _ready(self) -> IgdbSnapshotBridge:
        if self._bridge is None:
            raise SupplyBlocked("IGDB_CREDENTIALS_UNAVAILABLE")
        return self._bridge

    def collect_preview(self, *, after_game_id=None) -> dict | None:
        return self._ready().collect_preview(after_game_id=after_game_id)

    def verify(self, preview: dict, now: datetime) -> PersistableSnapshot:
        return self._ready().verify(preview, now)


class SearchApiOperationalDescriptor:
    """Inert registry entry; only the approved role binder can enable I/O."""

    scope = SEARCHAPI_SCOPE

    def collect_preview(self) -> dict | None:
        raise SupplyBlocked("SEARCHAPI_ROLE_NOT_BOUND")

    def verify(self, preview: dict, now: datetime) -> PersistableSnapshot:
        raise SupplyBlocked("SEARCHAPI_ROLE_NOT_BOUND")


class SearchInterestOperationalDescriptor(SearchApiOperationalDescriptor):
    """Interest rights and credentials must be bound separately from news."""

    scope = INTEREST_SCOPE


# Static code registry, not an approval list. External adapters stay inert
# until the protected profile selects them and the executing role is bound.
ADAPTERS: dict[str, SourceAdapter] = {
    REPO: GodotAdapter(),
    IGDB_SOURCE_ID: IgdbOperationalAdapter(),
    SEARCHAPI_SOURCE_ID: SearchApiOperationalDescriptor(),
    INTEREST_SOURCE_ID: SearchInterestOperationalDescriptor(),
}


def bind_snapshot(snapshot: PersistableSnapshot, *, policy: str, target: str):
    """Bind a verified snapshot to a target, not an authorization token."""
    return replace(snapshot, policy_version=policy, target=target)
