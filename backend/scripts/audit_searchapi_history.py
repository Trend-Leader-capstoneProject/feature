"""Audit a saved SearchApi KR result; no new Trending Now/News requests.

Run from backend/: python -m scripts.audit_searchapi_history --day 2026-11-23
One free Search History GET and one cached JSON GET; never writes to disk/DB.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.trend_collection.searchapi_discovery import (
    SearchApiDiscoveryError,
    parse_trending_now,
    summarize_trend_response,
)

HISTORY_ENDPOINT = "https://www.searchapi.io/api/v1/search_history"
MAX_BYTES = 2_000_000
TIMEOUT = 10
_RESULT_PATH = re.compile(r"/api/v1/(?:public_search|searches)/search_[A-Za-z0-9]+(?:\.json)?")


class HistoryReadBlocked(RuntimeError):
    """Bounded, credential-free failure codes."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HistoryReadBlocked("HISTORY_REDIRECT_BLOCKED")


def _safe_result_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise HistoryReadBlocked("UNSAFE_HISTORY_RESULT_URL")
    try:
        part = urlsplit(value)
        if (part.scheme != "https" or part.hostname != "www.searchapi.io"
                or part.username is not None or part.password is not None
                or part.port not in (None, 443) or part.query or part.fragment
                or not _RESULT_PATH.fullmatch(part.path)):
            raise HistoryReadBlocked("UNSAFE_HISTORY_RESULT_URL")
    except ValueError:
        raise HistoryReadBlocked("UNSAFE_HISTORY_RESULT_URL") from None
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read_json(opener, url: str, *, key: str | None = None) -> dict:
    headers = {"Accept": "application/json"}
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    request = Request(url, headers=headers, method="GET")
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise HistoryReadBlocked("HISTORY_UNEXPECTED_STATUS")
            payload = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        try:
            raise HistoryReadBlocked(f"HISTORY_HTTP_{exc.code}") from None
        finally:
            exc.close()
    except (URLError, OSError, HTTPException):
        raise HistoryReadBlocked("HISTORY_NETWORK_ERROR") from None
    if len(payload) > MAX_BYTES:
        raise HistoryReadBlocked("HISTORY_RESPONSE_TOO_LARGE")
    def reject_constant(_):
        raise ValueError("non-finite value")
    try:
        parsed = json.loads(payload, object_pairs_hook=_unique_object,
                            parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise HistoryReadBlocked("HISTORY_INVALID_JSON") from None
    if not isinstance(parsed, dict):
        raise HistoryReadBlocked("HISTORY_INVALID_JSON")
    return parsed


def _select_history_entry(history: dict, day: date) -> dict:
    searches = history.get("searches")
    if not isinstance(searches, list):
        raise HistoryReadBlocked("HISTORY_RESPONSE_INVALID")
    selected = []
    for item in searches:
        if not isinstance(item, dict) or item.get("status") != "Success":
            continue
        params = item.get("params")
        if (item.get("engine") != "google_trends_trending_now"
                or not isinstance(params, dict) or params.get("geo") != "KR"
                or params.get("time", "past_24_hours") != "past_24_hours"):
            continue
        created_at = item.get("created_at")
        if not isinstance(created_at, str):
            continue
        try:
            when = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None or when.astimezone(timezone.utc).date() != day:
            continue
        if not isinstance(item.get("id"), str):
            continue
        selected.append(item)
    if len(selected) != 1:
        raise HistoryReadBlocked("HISTORY_NO_UNIQUE_KR_TREND_RESULT")
    return selected[0]


def recover_history(key: str, *, day: date, opener=None) -> dict:
    """Read existing history and its saved JSON only; never runs a search."""
    if (not isinstance(key, str) or not 1 <= len(key) <= 512
            or any(not 33 <= ord(c) <= 126 for c in key)):
        raise HistoryReadBlocked("HISTORY_KEY_INVALID")
    if opener is None:
        opener = build_opener(ProxyHandler({}), _NoRedirect())
    url = HISTORY_ENDPOINT + "?" + urlencode({
        "engine": "google_trends_trending_now", "limit": 100,
        "time_period_min": (day - timedelta(days=1)).isoformat(),
        "time_period_max": (day + timedelta(days=1)).isoformat(),
    })
    history = _read_json(opener, url, key=key)
    entry = _select_history_entry(history, day)
    result = _read_json(opener, _safe_result_url(entry.get("json_url")))
    metadata = result.get("search_metadata")
    if (not isinstance(metadata, dict)
            or metadata.get("id") != entry["id"]
            or metadata.get("status") != "Success"):
        raise HistoryReadBlocked("HISTORY_RESULT_ID_MISMATCH")
    now = datetime.now(timezone.utc)
    leads = parse_trending_now(result, now=now)
    overview = summarize_trend_response(result, now=now)
    return {
        "status": "HISTORY_AUDIT_ONLY",
        "new_trending_searches": 0,
        "history_reads": 2,
        "region": "KR",
        "date_utc": day.isoformat(),
        **overview,
        "eligible_leads": [
            {"query": lead.query,
             "possible_root_codes": sorted(lead.possible_root_codes),
             "is_active": lead.is_active}
            for lead in leads
        ],
        "publication_authorization": "NONE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", required=True, type=date.fromisoformat)
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("HISTORY_INTERACTIVE_TERMINAL_REQUIRED", file=sys.stderr)
        return 2
    try:
        key = getpass("SearchApi API key (hidden, not saved): ")
        report = recover_history(key, day=args.day)
        del key
    except (HistoryReadBlocked, SearchApiDiscoveryError) as exc:
        print(f"SEARCHAPI_HISTORY_BLOCKED:{exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("SEARCHAPI_HISTORY_CANCELLED", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
