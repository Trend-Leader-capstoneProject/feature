"""SearchApi Trending Now discovery values; never grants publication authority."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from unicodedata import category as unicode_category
from urllib.parse import urlsplit

MAX_CANDIDATES = 20
MAX_NEWS = 5
_ALLOWED_TOPICS = {
    "beauty_and_fashion": frozenset({"FASHION", "BEAUTY"}),
    "food_and_drink": frozenset({"FOOD"}),
    "entertainment": frozenset({"ENTERTAINMENT"}),
    "games": frozenset({"GAME"}),
    "technology": frozenset({"IT_DIGITAL"}),
}


class SearchApiDiscoveryError(ValueError):
    """Bounded diagnostic without external content or credentials."""


@dataclass(frozen=True, slots=True)
class TrendingLead:
    query: str
    started_at_utc: datetime
    news_token: str
    possible_root_codes: frozenset[str]
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class NewsLead:
    title: str
    url: str
    publisher: str
    published_at_utc: datetime


def _clean_text(value: object, *, limit: int) -> str | None:
    if not isinstance(value, str) or value != value.strip():
        return None
    if not 1 <= len(value) <= limit:
        return None
    if any(unicode_category(char).startswith("C") for char in value):
        return None
    return value


def _timestamp(value: object, now: datetime) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        stamp = parsed.astimezone(timezone.utc)
        return stamp if stamp <= now + timedelta(minutes=5) else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_trending_now(
    payload: object, *, now: datetime, allow_missing_news_token: bool = False,
    interest_only: bool = False,
) -> tuple[TrendingLead, ...]:
    """Use category labels only as hints, never as a concrete child category."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise SearchApiDiscoveryError("INVALID_CLOCK")
    if not isinstance(payload, dict) or not isinstance(payload.get("trends"), list):
        raise SearchApiDiscoveryError("INVALID_TREND_RESPONSE")
    params = payload.get("search_parameters")
    if (not isinstance(params, dict)
            or params.get("engine") != "google_trends_trending_now"
            or params.get("geo") != "KR"
            or params.get("time") != "past_24_hours"):
        raise SearchApiDiscoveryError("WRONG_TREND_SCOPE")
    seen: set[str] = set()
    candidates: list[TrendingLead] = []
    for item in payload["trends"]:
        if not isinstance(item, dict) or type(item.get("is_active")) is not bool:
            continue
        query = _clean_text(item.get("query"), limit=255)
        token = _clean_text(item.get("news_token"), limit=2048)
        if token is None and allow_missing_news_token:
            token = ""
        started = _timestamp(item.get("start_date"), now)
        categories = item.get("categories")
        if (query is None or token is None or started is None
                or not isinstance(categories, list) or not categories
                or any(not isinstance(value, str) for value in categories)):
            continue
        # An unknown / out-of-scope category cannot silently become a safe one.
        if any(value not in _ALLOWED_TOPICS for value in categories):
            continue
        possible = frozenset().union(*(_ALLOWED_TOPICS[value] for value in categories))
        if interest_only and (
            not item["is_active"]
            or not timedelta(0) <= now - started <= timedelta(hours=24)
            or not possible <= {"FOOD", "FASHION", "BEAUTY", "ENTERTAINMENT"}
        ):
            continue
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            TrendingLead(query, started, token, possible, item["is_active"])
        )
        if len(candidates) == MAX_CANDIDATES:
            break
    return tuple(candidates)


def summarize_trend_response(payload: object, *, now: datetime) -> dict:
    """Read-only raw distribution, even for excluded topics; never return tokens."""
    # Validate the KR response envelope before counting untrusted records.
    parse_trending_now(payload, now=now)
    counts: Counter[str] = Counter()
    states: Counter[str] = Counter()
    for item in payload["trends"]:
        if not isinstance(item, dict):
            states["invalid_record"] += 1
            continue
        state = item.get("is_active")
        states["active" if state is True else
               "inactive" if state is False else "unknown_state"] += 1
        categories = item.get("categories")
        if isinstance(categories, list):
            # Count actual upstream category tags independently of our filter.
            for tag in set(tag for tag in categories if isinstance(tag, str)):
                if 0 < len(tag) <= 100 and tag.isascii():
                    counts[tag] += 1
        else:
            counts["<missing/invalid>"] += 1
    return {
        "raw_total": len(payload["trends"]),
        "state_counts": dict(sorted(states.items())),
        "upstream_category_counts": dict(sorted(counts.items())),
        "mapped_eligible_count": len(parse_trending_now(payload, now=now)),
        "mapping_is_a_hint_only": True,
    }


def _safe_public_url(value: object) -> str | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return None
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or parts.port not in (None, 443)
                or parts.fragment or host == "localhost"
                or host.endswith((".localhost", ".local", ".internal"))
                or any(unicode_category(ch).startswith("C") for ch in value)):
            return None
        try:
            ip_address(host)
        except ValueError:
            pass
        else:
            return None
    except ValueError:
        return None
    return value


def parse_related_news(payload: object, *, now: datetime) -> tuple[NewsLead, ...]:
    """Parse news metadata, not the article body or verified publication facts."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise SearchApiDiscoveryError("INVALID_CLOCK")
    if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
        raise SearchApiDiscoveryError("INVALID_NEWS_RESPONSE")
    params = payload.get("search_parameters")
    if (not isinstance(params, dict)
            or params.get("engine") != "google_trends_trending_now_news"):
        raise SearchApiDiscoveryError("WRONG_NEWS_SCOPE")
    results: list[NewsLead] = []
    seen: set[str] = set()
    for item in payload["news"]:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), limit=255)
        publisher = _clean_text(item.get("source"), limit=255)
        url = _safe_public_url(item.get("link"))
        published = _timestamp(item.get("iso_date"), now)
        if None in (title, publisher, url, published) or url in seen:
            continue
        seen.add(url)
        results.append(NewsLead(title, url, publisher, published))
        if len(results) == MAX_NEWS:
            break
    return tuple(results)


def official_search_query(topic: str) -> str:
    """Keep an upstream topic a bounded literal, not a search operator."""
    if _clean_text(topic, limit=255) is None or '"' in topic or "\\" in topic:
        raise SearchApiDiscoveryError("INVALID_OFFICIAL_TOPIC")
    return f'"{topic}" 공식 발표'


def parse_official_search_links(
    payload: object, *, topic: str,
) -> tuple[str, ...]:
    """Only first three direct organic links; no redirects or source claims."""
    if not isinstance(payload, dict):
        raise SearchApiDiscoveryError("INVALID_OFFICIAL_RESPONSE")
    params = payload.get("search_parameters")
    if (
        not isinstance(params, dict)
        or params.get("engine") != "google"
        or params.get("q") != official_search_query(topic)
        or params.get("gl") != "kr" or params.get("hl") != "ko"
    ):
        raise SearchApiDiscoveryError("WRONG_OFFICIAL_SCOPE")
    organic = payload.get("organic_results", [])
    if not isinstance(organic, list):
        raise SearchApiDiscoveryError("INVALID_OFFICIAL_RESPONSE")
    links: list[str] = []
    for item in organic[:3]:
        if not isinstance(item, dict) or item.get("link_token"):
            continue
        url = _safe_public_url(item.get("link"))
        if url is None or url in links:
            continue
        if urlsplit(url).path == "/goto":
            continue
        links.append(url)
    return tuple(links)
