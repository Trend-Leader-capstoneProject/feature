"""Explicit, non-publishing SearchApi KR live probe (1 Trending + up to 2 News).

No operational profiles, DB, Journal, API credentials persistence, or file writes.
Run from backend/: PYTHONDONTWRITEBYTECODE=1 python -m scripts.probe_searchapi_kr --live
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from getpass import getpass

from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.searchapi_client import SearchApiClient, SearchApiClientError
from app.trend_collection.searchapi_discovery import (
    SearchApiDiscoveryError,
    TrendingLead,
    parse_related_news,
    parse_trending_now,
)

_ROOT_PRIORITY = ("FOOD", "ENTERTAINMENT", "FASHION", "BEAUTY")
MAX_NEWS_QUERIES = 2


def choose_news_leads(leads: tuple[TrendingLead, ...]) -> tuple[TrendingLead, ...]:
    """At most 2 distinct-root leads, preferring unambiguous category hints."""
    selected: list[TrendingLead] = []
    used_roots: set[str] = set()
    for root in _ROOT_PRIORITY:
        for lead in leads:
            if (lead in selected or lead.possible_root_codes != frozenset({root})
                    or root in used_roots):
                continue
            selected.append(lead)
            used_roots.add(root)
            break
        if len(selected) == MAX_NEWS_QUERIES:
            return tuple(selected)
    for lead in leads:
        if lead not in selected:
            selected.append(lead)
            if len(selected) == MAX_NEWS_QUERIES:
                break
    return tuple(selected)


def collect_report(client: SearchApiClient, *, now: datetime) -> dict:
    """Read-only evidence discovery. Never treats metadata as verified facts."""
    raw = client.trending_now()
    leads = parse_trending_now(raw, now=now)
    selected = choose_news_leads(leads)
    items: list[dict] = []
    for lead in selected:
        raw_news = client.related_news(lead.news_token)
        parameters = raw_news.get("search_parameters")
        if (not isinstance(parameters, dict)
                or parameters.get("news_token") != lead.news_token):
            raise SearchApiDiscoveryError("NEWS_TOKEN_MISMATCH")
        news = parse_related_news(raw_news, now=now)
        items.append({
            "query": lead.query,
            "started_at_utc": lead.started_at_utc.isoformat(),
            "possible_root_codes": sorted(lead.possible_root_codes),
            "news_metadata_unverified": [
                {"title": item.title, "publisher": item.publisher,
                 "url": item.url, "published_at_utc": item.published_at_utc.isoformat()}
                for item in news
            ],
        })
    return {
        "status": "READ_ONLY_DISCOVERY",
        "publication_authorization": "NONE",
        "region": "KR", "time": "past_24_hours",
        "total_eligible_leads": len(leads),
        "news_queries": len(selected),
        "requests_executed": 1 + len(selected),
        "candidates": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Explicitly allow up to 3 SearchApi HTTP GET requests",
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("live requests are opt-in: pass --live")
    if not sys.stdin.isatty():
        print("SEARCHAPI_INTERACTIVE_TERMINAL_REQUIRED", file=sys.stderr)
        return 2
    try:
        key = getpass("SearchApi API key (hidden, not saved): ")
        client = SearchApiClient(key)
        del key
        report = collect_report(client, now=datetime.now(timezone.utc))
    except RateLimited:
        print("SEARCHAPI_RATE_LIMITED; stop and respect Retry-After", file=sys.stderr)
        return 1
    except (SearchApiClientError, SearchApiDiscoveryError) as exc:
        print(f"SEARCHAPI_PROBE_BLOCKED:{exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("SEARCHAPI_PROBE_CANCELLED", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
