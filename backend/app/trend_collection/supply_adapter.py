"""Source-specific independent verification; no DB or operational approval."""

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.trend_collection.godot_release_collector import (
    RELEASES,
    REPO,
    CollectionError,
    _parse,
    _request_json,
    collect,
)
from app.trend_collection.publication_policy import (
    ContentSnapshot,
    evaluate_release,
)
from app.trend_collection.rule_first_preview import build_rule_first_preview


class SupplyBlocked(RuntimeError):
    """Bounded diagnostic only."""


class SourceAdapter(Protocol):
    scope: str

    def collect_preview(self) -> dict: ...

    def verify(self, preview: dict, now: datetime) -> ContentSnapshot: ...


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

    def __init__(self, request_json=_request_json):
        self._request_json = request_json

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


# Fixed code registry, no dynamic imports or arbitrary caller-provided URLs.
ADAPTERS: dict[str, SourceAdapter] = {REPO: GodotAdapter()}


def bind_snapshot(snapshot: ContentSnapshot, *, policy: str, target: str):
    """Bind a verified snapshot to a target, not an authorization token."""
    return replace(snapshot, policy_version=policy, target=target)
