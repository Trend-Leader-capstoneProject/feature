"""Source-bound freshness rules. Never take a time window from collector input."""

import re
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from app.trend_collection.godot_release_collector import REPO
from app.trend_collection.igdb_adapter import (
    SCOPE as IGDB_SCOPE,
    SOURCE_ID as IGDB_SOURCE_ID,
    SOURCE_URL,
    VISITS_ID,
)
from app.trend_collection.publication_policy import (
    ContentSnapshot,
    PopularitySnapshot,
)
from app.trend_collection.searchapi_article_reader import (
    ArticleReadBlocked,
    _allow_url,
)
from app.trend_collection.searchapi_interest import (
    ROOTS as INTEREST_ROOTS,
    SOURCE_URL as INTEREST_URL,
    WINDOW as INTEREST_WINDOW,
    InterestSnapshot,
    _case_key,
)
from app.trend_collection.searchapi_related_articles import validate_selected_articles
from app.trend_collection.searchapi_supply_snapshot import (
    NEWS_WINDOW,
    SCOPE as NEWS_SCOPE,
    SOURCE_ID as NEWS_SOURCE_ID,
    NewsSnapshot,
)
from app.trend_collection.supply_adapter import (
    INTEREST_HYBRID_SCOPE,
    INTEREST_RELATED_SCOPE,
    INTEREST_SCOPE,
    INTEREST_SOURCE_ID,
    SupplyBlocked,
    utc,
)

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
    elif type(snapshot) is InterestSnapshot:
        source_id, scope = INTEREST_SOURCE_ID, INTEREST_SCOPE
        if (
            not isinstance(snapshot.candidate_identity, str)
            or re.fullmatch(
                r"searchapi-interest:[a-f0-9]{64}", snapshot.candidate_identity,
            ) is None
            or not isinstance(snapshot.title, str)
            or snapshot.candidate_identity != "searchapi-interest:" + _case_key(
                snapshot.title,
            )
            or snapshot.source_url != INTEREST_URL
            or snapshot.parent_code not in INTEREST_ROOTS
            or not isinstance(snapshot.child_name, str)
            or not 1 <= len(snapshot.child_name.strip()) <= 255
        ):
            raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH")
        approved = profile.source(source_id)
        if approved.scope == INTEREST_RELATED_SCOPE:
            scope = INTEREST_RELATED_SCOPE
            try:
                validate_selected_articles(
                    snapshot.related_articles, topic=snapshot.title,
                    observed=utc(snapshot.observed_at_utc),
                    rules=approved.article_rules,
                )
            except (TypeError, ValueError, OverflowError, AttributeError):
                raise SupplyBlocked("ARTICLE_SNAPSHOT_INVALID") from None
        elif snapshot.related_articles:
            raise SupplyBlocked("ARTICLE_SCOPE_NOT_APPROVED")
        elif approved.scope == INTEREST_HYBRID_SCOPE:
            scope = INTEREST_HYBRID_SCOPE
        reference_time = snapshot.started_at_utc
        window = INTEREST_WINDOW
    elif type(snapshot) is NewsSnapshot:
        source_id, scope = NEWS_SOURCE_ID, NEWS_SCOPE
        if (
            not isinstance(snapshot.candidate_identity, str)
            or re.fullmatch(
                r"searchapi-event:[a-z0-9_:-]{1,120}",
                snapshot.candidate_identity,
            ) is None
            or snapshot.parent_code not in {
                "ENTERTAINMENT", "GAME", "IT_DIGITAL", "FOOD", "BEAUTY", "FASHION",
            }
            or not isinstance(snapshot.child_name, str)
            or not 1 <= len(snapshot.child_name.strip()) <= 255
        ):
            raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH")
        try:
            _allow_url(snapshot.source_url)
        except ArticleReadBlocked:
            raise SupplyBlocked("SOURCE_SNAPSHOT_MISMATCH") from None
        reference_time = snapshot.source_published_at
        window = NEWS_WINDOW
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
