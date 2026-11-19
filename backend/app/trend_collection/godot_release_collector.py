"""Read-only Source-first collector. Never authorizes publication or writes DB."""

import json
import re
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.external_trends.normalizer import normalize_source_url, normalize_title
from app.trend_collection.rate_limit import retry_deadline

REPO = "godotengine/godot-builds"
RELEASES = f"https://api.github.com/repos/{REPO}/releases"
TAG = re.compile(
    r"[0-9]+\.[0-9]+(?:\.[0-9]+)?-(stable|beta[0-9]+|rc[0-9]+|dev[0-9]+)\Z"
)
MAX_BYTES = 8_000_000


class CollectionError(Exception):
    """Safe diagnostic code, without raw upstream content or credentials."""


class RateLimited(CollectionError):
    """Operational rate-limit signal; None needs independent review."""

    def __init__(self, retry_not_before):
        super().__init__("RATE_LIMITED")
        self.retry_not_before = retry_not_before


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("REDIRECT_BLOCKED")


def _network_code(reason):
    if isinstance(reason, socket.gaierror):
        return "DNS_RESOLUTION_ERROR"
    if isinstance(reason, TimeoutError):
        return "TIMEOUT"
    if isinstance(reason, ssl.SSLError):
        return "TLS_ERROR"
    if isinstance(reason, OSError):
        return "CONNECTION_ERROR"
    return "NETWORK_ERROR"


def _request_json(url, *, enforce_rate_limit=False):
    if url != RELEASES + "?per_page=3" and not re.fullmatch(
        re.escape(RELEASES) + r"/[1-9][0-9]*", url
    ):
        raise CollectionError("ENDPOINT_NOT_ALLOWED")
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "TrendLeader-AP1-ReadOnly/0.2",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise CollectionError(f"HTTP_{response.status}")
            if (
                enforce_rate_limit
                and response.headers.get("X-RateLimit-Remaining") == "0"
            ):
                raise RateLimited(retry_deadline(response.headers, time.time()))
            data = response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        headers = exc.headers or {}
        if enforce_rate_limit and (
            exc.code in {403, 429}
            or headers.get("Retry-After") is not None
            or headers.get("X-RateLimit-Remaining") == "0"
        ):
            raise RateLimited(retry_deadline(headers, time.time())) from None
        raise CollectionError(f"HTTP_{exc.code}") from None
    except URLError as exc:
        raise CollectionError(_network_code(exc.reason)) from None
    except OSError as exc:
        raise CollectionError(_network_code(exc)) from None
    except HTTPException:
        raise CollectionError("INVALID_HTTP_RESPONSE") from None
    if len(data) > MAX_BYTES:
        raise CollectionError("RESPONSE_SIZE_LIMIT")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise CollectionError("INVALID_JSON") from None


@dataclass(frozen=True)
class ReleaseEvidence:
    release_id: int
    tag: str
    published_at: datetime
    url: str
    prerelease: bool


def _parse(raw):
    if not isinstance(raw, dict):
        raise CollectionError("INVALID_RELEASE")
    rid, tag = raw.get("id"), raw.get("tag_name")
    published, prerelease = raw.get("published_at"), raw.get("prerelease")
    if type(rid) is not int or rid <= 0 or not isinstance(tag, str):
        raise CollectionError("INVALID_RELEASE_ID_OR_TAG")
    if not TAG.fullmatch(tag) or type(prerelease) is not bool:
        raise CollectionError("INVALID_RELEASE_ID_OR_TAG")
    if raw.get("draft") is not False or prerelease == tag.endswith("-stable"):
        raise CollectionError("RELEASE_TYPE_MISMATCH")
    if raw.get("html_url") != f"https://github.com/{REPO}/releases/tag/{tag}":
        raise CollectionError("URL_MISMATCH")
    if not isinstance(published, str):
        raise CollectionError("INVALID_DATE")
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt.utcoffset() is None:
            raise ValueError
    except ValueError:
        raise CollectionError("INVALID_DATE") from None
    return ReleaseEvidence(
        rid, tag, dt.astimezone(timezone.utc), raw["html_url"], prerelease
    )


def collect(*, request_json=_request_json):
    """Select latest among the three returned releases; verify detail identity."""
    rows = request_json(RELEASES + "?per_page=3")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        raise CollectionError("EMPTY_OR_INVALID_LIST")
    releases = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("draft")) is not bool:
            raise CollectionError("INVALID_RELEASE")
        if row["draft"]:
            continue
        releases.append(_parse(row))
    if not releases:
        raise CollectionError("NO_PUBLISHED_RELEASES")
    chosen = max(releases, key=lambda row: row.published_at)
    detail = _parse(request_json(f"{RELEASES}/{chosen.release_id}"))
    if chosen != detail:
        raise CollectionError("LIST_DETAIL_MISMATCH")
    return detail


def build_candidate(evidence: ReleaseEvidence, observed_at: datetime):
    """Project only verified release facts; DB IDs and permissions are absent."""
    age = observed_at - evidence.published_at
    if not timedelta(0) <= age <= timedelta(days=7):
        raise CollectionError("OUTSIDE_PROPOSED_7_DAY_WINDOW")
    version, kind = evidence.tag.split("-", 1)
    label = "정식 버전" if kind == "stable" else kind
    title = normalize_title(f"Godot {version} {label} 공개")
    source = normalize_source_url(evidence.url)
    if title is None or source is None or source.canonical_url != evidence.url:
        raise CollectionError("NORMALIZATION_FAILED")
    return {
        "candidate_identity": f"github-release:{REPO}:{evidence.release_id}",
        "title": title.display_title,
        "normalized_title": title.normalized_title,
        "summary": None,
        "thumbnail_url": None,
        "proposed_category_ref": {
            "parent_code": "IT_DIGITAL", "child_name": "소프트웨어·앱",
        },
        "proposed_source": {
            "platform": "ETC",
            "external_id": f"github-release:{REPO}:{evidence.release_id}",
            "source_title": None, "source_url": source.canonical_url,
        },
        "source_published_at": evidence.published_at.isoformat(),
        "observed_at_utc": observed_at.isoformat(),
        "signal_type": "OFFICIAL_RELEASE_EVENT",
        "popularity_verified": False,
        "analysis_status": "NOT_RUN_FIXED_SOURCE_PREVIEW",
        "publication_status": "NOT_FOR_PUBLICATION",
        "publish_authorization": "NONE",
    }
