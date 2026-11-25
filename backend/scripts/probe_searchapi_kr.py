"""Non-publishing SearchApi KR probe: 1 Trending + up to 2 other calls.

No operational profiles, DB, Journal, API credentials persistence, or file writes.
Run from backend/: PYTHONDONTWRITEBYTECODE=1 python -m scripts.probe_searchapi_kr --live
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from getpass import getpass

from app.trend_collection.godot_release_collector import RateLimited
from app.trend_collection.searchapi_client import SearchApiClient, SearchApiClientError
from app.trend_collection.searchapi_discovery import (
    SearchApiDiscoveryError,
    TrendingLead,
    parse_official_search_links,
    parse_related_news,
    parse_trending_now,
    summarize_trend_response,
)

_ROOT_PRIORITY = ("FOOD", "ENTERTAINMENT", "FASHION", "BEAUTY", "GAME", "IT_DIGITAL")
MAX_NEWS_QUERIES = 2


def choose_news_leads(leads: tuple[TrendingLead, ...]) -> tuple[TrendingLead, ...]:
    """At most 2 distinct-root leads, preferring unambiguous category hints."""
    selected: list[TrendingLead] = []
    used_roots: set[str] = set()
    # Recently active topics take priority over ended 24-hour observations.
    ordered = sorted(leads, key=lambda lead: not lead.is_active)
    for root in _ROOT_PRIORITY:
        for lead in ordered:
            if (lead in selected or lead.possible_root_codes != frozenset({root})
                    or root in used_roots):
                continue
            selected.append(lead)
            used_roots.add(root)
            break
        if len(selected) == MAX_NEWS_QUERIES:
            return tuple(selected)
    for lead in ordered:
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
    # Include every eligible lead, even those skipped by the 2-news-call
    # probe budget. No news tokens, credentials or raw response are emitted.
    audit = summarize_trend_response(raw, now=now)
    return {
        "status": "READ_ONLY_DISCOVERY",
        "publication_authorization": "NONE",
        "region": "KR", "time": "past_24_hours",
        "total_trends_returned": len(raw["trends"]),
        "active_trends_returned": sum(
            isinstance(item, dict) and item.get("is_active") is True
            for item in raw["trends"]
        ),
        "raw_category_counts": audit["upstream_category_counts"],
        "total_eligible_leads": len(leads),
        "eligible_leads": [
            {
                "query": lead.query,
                "started_at_utc": lead.started_at_utc.isoformat(),
                "is_active": lead.is_active,
                "possible_root_codes": sorted(lead.possible_root_codes),
            }
            for lead in leads
        ],
        "news_queries": len(selected),
        "requests_executed": 1 + len(selected),
        "candidates": items,
    }



def collect_official_report(
    client: SearchApiClient, *, now: datetime,
    choose: Callable[[tuple[TrendingLead, ...]], int | None],
) -> dict:
    """Select one fresh lead, then spend one News and one Google request."""
    leads = parse_trending_now(client.trending_now(), now=now)
    eligible = tuple(
        lead for lead in leads
        if lead.is_active
        and timedelta(0) <= now - lead.started_at_utc <= timedelta(hours=24)
        and lead.possible_root_codes.intersection(
            {"FOOD", "FASHION", "BEAUTY", "ENTERTAINMENT"},
        )
    )
    report = {
        "status": "READ_ONLY_DISCOVERY",
        "publication_authorization": "NONE",
        "mode": "OFFICIAL_SOURCE_DISCOVERY",
        "requests_executed": 1,
        "candidate": None,
    }
    index = choose(eligible) if eligible else None
    if index is None:
        return report
    if type(index) is not int or not 0 <= index < len(eligible):
        raise SearchApiDiscoveryError("INVALID_OFFICIAL_SELECTION")
    lead = eligible[index]
    raw_news = client.related_news(lead.news_token)
    parameters = raw_news.get("search_parameters")
    if (
        not isinstance(parameters, dict)
        or parameters.get("news_token") != lead.news_token
    ):
        raise SearchApiDiscoveryError("NEWS_TOKEN_MISMATCH")
    news = parse_related_news(raw_news, now=now)
    links = parse_official_search_links(
        client.official_search(lead.query), topic=lead.query,
    )
    report["requests_executed"] = 3
    report["candidate"] = {
        "query": lead.query,
        "started_at_utc": lead.started_at_utc.isoformat(),
        "possible_root_codes": sorted(lead.possible_root_codes),
        "related_news_links_unverified": [item.url for item in news],
        "official_search_links_unverified": list(links),
    }
    return report


def _choose_official_lead(leads: tuple[TrendingLead, ...]) -> int | None:
    print("Choose one product/work/service topic (blank to cancel):",
          file=sys.stderr)
    for index, lead in enumerate(leads, start=1):
        print(f"{index}. {lead.query} ({', '.join(sorted(lead.possible_root_codes))})",
              file=sys.stderr)
    selected = input("Topic number: ").strip()
    if not selected:
        return None
    if not selected.isascii() or not selected.isdecimal() or len(selected) > 2:
        raise SearchApiDiscoveryError("INVALID_OFFICIAL_SELECTION")
    return int(selected) - 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Explicitly allow up to 3 SearchApi HTTP GET requests",
    )
    parser.add_argument(
        "--official-source", action="store_true",
        help="Choose one current topic; spend the third call on official links",
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
        now = datetime.now(timezone.utc)
        if args.official_source:
            report = collect_official_report(
                client, now=now, choose=_choose_official_lead,
            )
        else:
            report = collect_report(client, now=now)
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
