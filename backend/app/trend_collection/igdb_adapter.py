"""IGDB Visits review adapter. No credentials, DB, or publication authority."""

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Callable
from unicodedata import category

from app.external_trends.normalizer import normalize_title

SOURCE_ID = "igdb:visits"
SCOPE = "IGDB_VISITS_FACTS_LINK_V1"
DIVERSITY_SCOPE = "IGDB_VISITS_FACTS_LINK_DIVERSITY_V1"
VISITS_ID = 1
IGDB_ID = 121
LIMIT = 20
TYPE_QUERY = (
    "fields name,external_popularity_source.name; where id = 1; limit 1;"
)
POPULARITY_QUERY = (
    "fields game_id,value,popularity_type,external_popularity_source,calculated_at; "
    "where popularity_type = 1; sort value desc; limit 20;"
)
GAME_FIELDS = (
    "id,name,url,game_type.type,platforms.name,"
    "age_ratings.organization.name,age_ratings.rating_category.rating,"
    "themes.name"
)
Query = Callable[[str, str], object]

# Explicit observed ID/name pairs. No classification from display names alone.
PLATFORMS = {
    3: ("Linux", "PC 게임"),
    6: ("PC (Microsoft Windows)", "PC 게임"),
    14: ("Mac", "PC 게임"),
    34: ("Android", "모바일 게임"),
    39: ("iOS", "모바일 게임"),
    9: ("PlayStation 3", "콘솔 게임"),
    12: ("Xbox 360", "콘솔 게임"),
    48: ("PlayStation 4", "콘솔 게임"),
    49: ("Xbox One", "콘솔 게임"),
    130: ("Nintendo Switch", "콘솔 게임"),
    167: ("PlayStation 5", "콘솔 게임"),
    169: ("Xbox Series X|S", "콘솔 게임"),
    508: ("Nintendo Switch 2", "콘솔 게임"),
}
THEMES = {
    1: "Action", 17: "Fantasy", 18: "Science fiction", 19: "Horror",
    21: "Survival", 27: "Comedy", 33: "Sandbox", 34: "Educational",
    35: "Kids", 38: "Open world", 39: "Warfare", 42: "Erotic", 44: "Romance",
}
# Only exact pairs confirmed in the supplied response. Unknown pairs HOLD.
# GRAC ALL is policy-eligible but its current category label is unverified.
RATINGS = {
    1: ("ESRB", {4: "E10+", 5: "T", 6: "M"}),
    2: ("PEGI", {9: "7", 10: "12", 11: "16", 12: "18"}),
    3: ("CERO", {13: "A", 14: "B", 17: "Z"}),
    4: ("USK", {19: "6", 20: "12", 21: "16", 22: "18"}),
    5: ("GRAC", {24: "12+", 25: "15+", 26: "19+"}),
    6: ("CLASS_IND", {28: "L", 29: "10", 30: "12", 32: "16", 33: "18"}),
    7: ("ACB", {35: "PG", 36: "M", 37: "MA 15+", 38: "R 18+"}),
}
ADULT = {(1, 6), (2, 12), (3, 17), (4, 22), (5, 26), (6, 33), (7, 38)}
SOURCE_URL = re.compile(r"https://www\.igdb\.com/games/[a-z0-9][a-z0-9-]{0,254}")


class IgdbBlocked(ValueError):
    """Bounded diagnostic; never includes upstream text."""


def _id(value):
    if type(value) is not int or not 1 <= value < 10**20:
        raise IgdbBlocked("INVALID_ID")
    return value


def _utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise IgdbBlocked("INVALID_TIME")
    return value.astimezone(timezone.utc)


def _objects(value, maximum):
    if type(value) is not list or len(value) > maximum:
        raise IgdbBlocked("INVALID_LIST")
    if any(type(row) is not dict for row in value):
        raise IgdbBlocked("INVALID_OBJECT")
    return value


def _digest(value):
    return sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def validate_metric(raw):
    rows = _objects(raw, 1)
    if len(rows) != 1:
        raise IgdbBlocked("METRIC_MISMATCH")
    row = rows[0]
    source = row.get("external_popularity_source")
    if (
        _id(row.get("id")) != VISITS_ID or row.get("name") != "Visits"
        or type(source) is not dict or _id(source.get("id")) != IGDB_ID
        or source.get("name") != "IGDB"
    ):
        raise IgdbBlocked("METRIC_MISMATCH")


@dataclass(frozen=True, slots=True)
class Popularity:
    game_id: int
    rank: int
    value: float
    calculated_at: int
    tied: bool


def parse_popularity(raw, now):
    now = _utc(now)
    rows = _objects(raw, LIMIT)
    items = []
    seen = set()
    previous = math.inf
    stamp = None
    for rank, row in enumerate(rows, 1):
        game_id = _id(row.get("game_id"))
        value, calculated = row.get("value"), row.get("calculated_at")
        if (
            game_id in seen or _id(row.get("popularity_type")) != VISITS_ID
            or _id(row.get("external_popularity_source")) != IGDB_ID
            or type(value) not in (int, float) or not 0 < value <= previous
            or value > 1e308 or not math.isfinite(value)
            or type(calculated) is not int
        ):
            raise IgdbBlocked("INVALID_POPULARITY")
        try:
            collected = datetime.fromtimestamp(calculated, timezone.utc)
        except (ValueError, OverflowError, OSError):
            raise IgdbBlocked("INVALID_TIME") from None
        if not timedelta(0) <= now - collected <= timedelta(hours=48):
            raise IgdbBlocked("STALE_POPULARITY")
        if stamp is not None and stamp != calculated:
            raise IgdbBlocked("MIXED_OBSERVATION")
        stamp = calculated
        seen.add(game_id)
        previous = value
        items.append((game_id, rank, float(value), calculated))
    counts = {}
    for _, _, value, _ in items:
        counts[value] = counts.get(value, 0) + 1
    return [
        Popularity(*item, tied=counts[item[2]] > 1) for item in items
    ]


@dataclass(frozen=True, slots=True)
class Candidate:
    game_id: int
    rank: int
    calculated_at: int
    title: str
    normalized_title: str
    child_name: str
    source_url: str
    evidence_digest: str

    @property
    def identity(self):
        return f"igdb-game:{self.game_id}"


def _rating_evidence(game):
    rows = _objects(game.get("age_ratings"), 40)
    found = {}
    for row in rows:
        org, rating = row.get("organization"), row.get("rating_category")
        if type(org) is not dict or type(rating) is not dict:
            raise IgdbBlocked("UNKNOWN_RATING")
        oid, rid = _id(org.get("id")), _id(rating.get("id"))
        known = RATINGS.get(oid)
        if (
            known is None or org.get("name") != known[0]
            or rid not in known[1] or rating.get("rating") != known[1][rid]
            or oid in found
        ):
            raise IgdbBlocked("UNKNOWN_OR_CONFLICTING_RATING")
        if (oid, rid) in ADULT:
            raise IgdbBlocked("ADULT_RATING")
        found[oid] = rid
    if found.get(5) not in {24, 25}:
        raise IgdbBlocked("GRAC_UNVERIFIED")
    return sorted(found.items())


def _named_ids(rows, known, reason):
    result = set()
    for row in _objects(rows, 80):
        ident = _id(row.get("id"))
        if ident in result or ident not in known or row.get("name") != known[ident]:
            raise IgdbBlocked(reason)
        result.add(ident)
    if not result:
        raise IgdbBlocked(reason)
    return sorted(result)


def evaluate_game(popularity, game, *, diversity=False):
    """Eligibility on already validated popularity evidence; no permission grant."""
    if popularity.tied:
        raise IgdbBlocked("UNCERTAIN_RANK")
    if type(game) is not dict or _id(game.get("id")) != popularity.game_id:
        raise IgdbBlocked("GAME_ID_MISMATCH")
    kind = game.get("game_type")
    if type(kind) is not dict or kind.get("type") != "Main Game":
        raise IgdbBlocked("GAME_TYPE_EXCLUDED")
    ratings = _rating_evidence(game)
    themes = _named_ids(game.get("themes"), THEMES, "UNKNOWN_THEME")
    if 42 in themes:
        raise IgdbBlocked("EROTIC_THEME")
    platform_names = {key: item[0] for key, item in PLATFORMS.items()}
    platforms = _named_ids(game.get("platforms"), platform_names, "UNKNOWN_PLATFORM")
    children = {PLATFORMS[key][1] for key in platforms}
    if len(children) != 1 and not diversity:
        raise IgdbBlocked("MULTIPLE_CATEGORIES")
    child = next(iter(children)) if len(children) == 1 else "기타"
    title, url = game.get("name"), game.get("url")
    if (
        not isinstance(title, str) or not 1 <= len(title) <= 255
        or any(category(char).startswith("C") for char in title)
        or not isinstance(url, str) or not SOURCE_URL.fullmatch(url)
    ):
        raise IgdbBlocked("INVALID_TITLE_OR_URL")
    normalized = normalize_title(title)
    if normalized is None:
        raise IgdbBlocked("INVALID_TITLE_OR_URL")
    evidence = {
        "popularity": asdict(popularity), "title": title, "url": url,
        "game_type": "Main Game", "ratings": ratings,
        "themes": themes, "platforms": platforms,
    }
    return Candidate(
        popularity.game_id, popularity.rank, popularity.calculated_at,
        title, normalized.normalized_title, child, url, _digest(evidence),
    )


def build_preview(candidate, observed_at, *, diversity=False):
    """Review-only projection; no executable ContentSnapshot or ACTIVE flag."""
    observed_at = _utc(observed_at)
    calculated = datetime.fromtimestamp(candidate.calculated_at, timezone.utc)
    if not timedelta(0) <= observed_at - calculated <= timedelta(hours=48):
        raise IgdbBlocked("STALE_POPULARITY")
    date = calculated.astimezone(timezone(timedelta(hours=9))).date().isoformat()
    return {
        "source_id": SOURCE_ID, "scope": DIVERSITY_SCOPE if diversity else SCOPE,
        "candidate_identity": candidate.identity,
        "game_id": candidate.game_id, "rank": candidate.rank,
        "calculated_at": calculated.isoformat(),
        "observed_at_utc": observed_at.isoformat(),
        "title": candidate.title, "normalized_title": candidate.normalized_title,
        "summary": (
            f"IGDB Visits {date} KST 관측 {candidate.rank}위 "
            "(IGDB 게임 페이지 방문 기반 지표)."
        ),
        "proposed_category_ref": {
            "parent_code": "GAME", "child_name": candidate.child_name,
        },
        "proposed_source": {
            "platform": "ETC", "external_id": candidate.identity,
            "source_url": candidate.source_url, "source_title": None,
        },
        "thumbnail_url": None, "evidence_digest": candidate.evidence_digest,
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE", "ai_api_calls": 0,
    }


class IgdbReviewAdapter:
    """Injected transport only. Intentionally absent from operational registry."""

    scope = SCOPE

    def __init__(self, query: Query, *, diversity=False):
        self._query = query
        self._diversity = diversity
        self.scope = DIVERSITY_SCOPE if diversity else SCOPE
        self.diagnostics: dict[str, int] = {}

    def _popularity(self, now):
        validate_metric(self._query("popularity_types", TYPE_QUERY))
        return parse_popularity(self._query(
            "popularity_primitives", POPULARITY_QUERY,
        ), now)

    def _games(self, ids):
        ids = tuple(_id(value) for value in ids)
        if not 1 <= len(ids) <= LIMIT or len(set(ids)) != len(ids):
            raise IgdbBlocked("INVALID_GAME_REQUEST")
        joined = ",".join(map(str, ids))
        rows = _objects(self._query(
            "games", f"fields {GAME_FIELDS}; where id = ({joined}); limit {len(ids)};",
        ), len(ids))
        result = {}
        for row in rows:
            ident = _id(row.get("id"))
            if ident not in ids or ident in result:
                raise IgdbBlocked("GAME_RESPONSE_MISMATCH")
            result[ident] = row
        return result

    def collect_review(self, now, *, after_game_id=None):
        now = _utc(now)
        if after_game_id is not None:
            _id(after_game_id)
        items = self._popularity(now)
        self.diagnostics = {"examined": len(items), "eligible": 0}
        if not items:
            return None
        games = self._games(item.game_id for item in items)
        eligible = []
        counts = Counter()
        for item in items:
            if item.game_id not in games:
                counts["GAME_METADATA_MISSING"] += 1
                continue
            try:
                candidate = evaluate_game(
                    item, games[item.game_id], diversity=self._diversity,
                )
            except IgdbBlocked as exc:
                counts[str(exc)] += 1
                continue
            eligible.append(candidate)
            if candidate.child_name == "기타":
                counts["ROOT_OTHER"] += 1
        self.diagnostics = {"examined": len(items), "eligible": len(eligible), **counts}
        if not eligible:
            return None
        index = next((
            i + 1 for i, item in enumerate(eligible)
            if item.game_id == after_game_id
        ), 0)
        return build_preview(
            eligible[index % len(eligible)], now, diversity=self._diversity,
        )

    def verify_review(self, preview, now):
        now = _utc(now)
        if type(preview) is not dict:
            raise IgdbBlocked("INVALID_PREVIEW")
        game_id = _id(preview.get("game_id"))
        try:
            observed = _utc(datetime.fromisoformat(preview["observed_at_utc"]))
        except (KeyError, TypeError, ValueError, OverflowError):
            raise IgdbBlocked("INVALID_PREVIEW_TIME") from None
        if not timedelta(0) <= now - observed <= timedelta(minutes=10):
            raise IgdbBlocked("STALE_PREVIEW")
        items = self._popularity(now)
        chosen = next((item for item in items if item.game_id == game_id), None)
        if chosen is None:
            raise IgdbBlocked("CANDIDATE_NOT_IN_TOP_LIST")
        games = self._games((game_id,))
        if game_id not in games:
            raise IgdbBlocked("GAME_RESPONSE_MISMATCH")
        expected = build_preview(
            evaluate_game(chosen, games[game_id], diversity=self._diversity),
            observed, diversity=self._diversity,
        )
        try:
            matches = _digest(preview) == _digest(expected)
        except (TypeError, ValueError, RecursionError, UnicodeError):
            raise IgdbBlocked("PREVIEW_MISMATCH") from None
        if not matches:
            raise IgdbBlocked("PREVIEW_MISMATCH")
        return expected
