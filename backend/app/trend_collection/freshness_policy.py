"""Source-bound freshness rules. Never take a time window from collector input."""

import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.trend_collection.godot_release_collector import REPO
from app.trend_collection.igdb_adapter import (
    SCOPE as IGDB_SCOPE,
)
from app.trend_collection.igdb_adapter import (
    SOURCE_ID as IGDB_SOURCE_ID,
)
from app.trend_collection.igdb_adapter import SOURCE_URL, VISITS_ID
from app.trend_collection.publication_policy import (
    ContentSnapshot,
    PopularitySnapshot,
)
from app.trend_collection.supply_adapter import SupplyBlocked, utc

GODOT_SCOPE = "GODOT_FACTS_LINK_V1"
PREVIEW_WINDOW = timedelta(minutes=10)
RELEASE_WINDOW = timedelta(days=7)
POPULARITY_WINDOW = timedelta(hours=48)
GAME_ID = re.compile(r"igdb-game:([1-9][0-9]{0,19})\Z")


def validate_snapshot_freshness(profile, snapshot, now: datetime) -> None:
    """Check approved source, concrete snapshot type and bounded timestamps.

    Profile.source is the only source of approved scope; the snapshot cannot
    decide its own freshness policy or convey authority.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise SupplyBlocked("INVALID_CLOCK")
    now = now.astimezone(timezone.utc)
    if type(snapshot) is ContentSnapshot:
        source_id, scope = REPO, GODOT_SCOPE
        if (not isinstance(snapshot.candidate_identity, str)
                or not re.fullmatch(
                    rf"github-release:{re.escape(REPO)}:[1-9][0-9]{{0,19}}",
                    snapshot.candidate_identity,
                )):
            raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH")
        reference_time = snapshot.source_published_at
        window = RELEASE_WINDOW
    elif type(snapshot) is PopularitySnapshot:
        source_id, scope = IGDB_SOURCE_ID, IGDB_SCOPE
        identity = snapshot.candidate_identity
        if (
            not isinstance(identity, str)
            or GAME_ID.fullmatch(identity) is None
            or type(snapshot.metric_id) is not int
            or snapshot.metric_id != VISITS_ID
            or type(snapshot.rank) is not int or not 1 <= snapshot.rank <= 20
            or snapshot.parent_code != "GAME"
            or snapshot.child_name not in {"PC 게임", "모바일 게임", "콘솔 게임"}
            or not isinstance(snapshot.source_url, str)
            or SOURCE_URL.fullmatch(snapshot.source_url) is None
        ):
            raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH")
        reference_time = snapshot.calculated_at_utc
        window = POPULARITY_WINDOW
    else:
        raise SupplyBlocked("SNAPSHOT_TYPE_NOT_SUPPORTED")
    if (
        profile.source(source_id).scope != scope
        or snapshot.external_id != snapshot.candidate_identity
        or snapshot.platform != "ETC"
        or snapshot.source_key != sha256(
            f"ETC:{snapshot.external_id}".encode("utf-8"),
        ).hexdigest()
    ):
        raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH")
    try:
        preview_age = now - utc(snapshot.observed_at_utc)
        source_age = now - utc(reference_time)
    except (TypeError, ValueError, OverflowError):
        raise SupplyBlocked("SNAPSHOT_EXPIRED") from None
    if not (timedelta(0) <= preview_age <= PREVIEW_WINDOW
            and timedelta(0) <= source_age <= window):
        raise SupplyBlocked("SNAPSHOT_EXPIRED")
