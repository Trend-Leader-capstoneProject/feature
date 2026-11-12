"""출처 연결·URL 문자열·중복만 검증한다. 원문 확인이나 승인이 아니다."""

import re
from ipaddress import ip_address
from typing import cast
from unicodedata import category, normalize
from urllib.parse import urlsplit, urlunsplit

from .types import CandidateIssue, DiscoveryCandidate, ParsedResponse

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_NUMERIC_LABEL = re.compile(r"(?:0x[0-9a-f]+|[0-9]+)\Z", re.IGNORECASE)


def canonical_url(raw: str) -> str | None:
    if any(char.isspace() or category(char) == "Cc" or char == "\\" for char in raw):
        return None
    try:
        parts = urlsplit(raw)
        host, port = parts.hostname, parts.port
    except ValueError:
        return None
    if (
        parts.scheme not in {"http", "https"}
        or not host
        or not parts.netloc
        or any(char in parts.netloc for char in "@%[]")
        or parts.netloc.endswith(":")
        or host.endswith(".")
        or host == "localhost"
        or host.endswith(".localhost")
    ):
        return None
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        return None
    labels = host.split(".")
    if (
        len(labels) < 2
        or len(host) > 253
        or not all(_HOST_LABEL.fullmatch(label) for label in labels)
        or labels[-1].isdigit()
        or all(_NUMERIC_LABEL.fullmatch(label) for label in labels)
        or port not in (None, 80 if parts.scheme == "http" else 443)
    ):
        return None
    return urlunsplit((parts.scheme, host, parts.path, parts.query, ""))


def validate_candidates(
    parsed: ParsedResponse,
) -> tuple[tuple[DiscoveryCandidate, ...], tuple[CandidateIssue, ...]]:
    accepted = []
    issues = []
    urls: set[str] = set()
    topics: set[str] = set()
    fields = ("topic_draft", "source_url", "source_title_reference")
    for index, raw in enumerate(parsed.candidates):
        if not all(
            isinstance(raw.get(key), str) and cast(str, raw[key]).strip()
            for key in fields
        ):
            issues.append(CandidateIssue(index, "CANDIDATE_FIELDS_INVALID"))
            continue
        topic, url, title = (cast(str, raw[key]) for key in fields)
        canonical = canonical_url(url)
        if canonical is None:
            issues.append(CandidateIssue(index, "SOURCE_URL_INVALID"))
            continue
        if url not in parsed.citation_urls:
            issues.append(CandidateIssue(index, "CITATION_URL_MISMATCH"))
            continue
        normalized_topic = " ".join(normalize("NFC", topic).split()).translate(
            _ASCII_LOWER
        )
        if canonical in urls or normalized_topic in topics:
            issues.append(CandidateIssue(index, "DUPLICATE_CANDIDATE"))
            continue
        urls.add(canonical)
        topics.add(normalized_topic)
        accepted.append(DiscoveryCandidate(topic, url, title))
    return tuple(accepted), tuple(issues)
