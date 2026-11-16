"""Bounded untrusted display material. No persistence or registration entry point."""

import re
from unicodedata import category

from .types import CandidateIssue, ParsedResponse
from .validator import canonical_url

_PRIVATE_TEXT = re.compile(
    r"(?:\bbearer\s+|\b(?:authorization|api[_ -]?key|password|secret|token)\s*[:=]"
    r"|\bsk-[a-z0-9_-]{8,}|-----begin .*private key-----"
    r"|<\|(?:system|developer)|ignore (?:all |previous )?instructions"
    r"|시스템\s*프롬프트)",
    re.IGNORECASE,
)


def collect_review_material(
    parsed: ParsedResponse, issues: tuple[CandidateIssue, ...], *,
    private_texts: tuple[str, ...],
) -> list[dict[str, object]]:
    """Copy only safe, bounded fields from citation-mismatch issues as display data."""
    result = []
    seen_urls = set()
    fields = ("topic_draft", "source_url", "source_title_reference")
    limits = (255, 4096, 255)
    for issue in issues:
        if issue.code != "CITATION_URL_MISMATCH":
            continue
        raw = parsed.candidates[issue.candidate_index]
        values = [raw.get(field) for field in fields]
        if not all(
            isinstance(value, str) and value.strip() and len(value) <= limit
            and not any(category(char).startswith("C") for char in value)
            and not _PRIVATE_TEXT.search(value)
            and not any(secret and secret.casefold() in value.casefold()
                        for secret in private_texts)
            for value, limit in zip(values, limits, strict=True)
        ):
            continue
        url = canonical_url(values[1])
        if url is None or url in seen_urls:
            continue
        seen_urls.add(url)
        result.append({
            **dict(zip(fields, values, strict=True)),
            "candidate_index": issue.candidate_index,
            "rejection_reason": issue.code,
            "content_trust": "UNTRUSTED_MODEL_OUTPUT",
        })
        if len(result) == 3:
            break
    return result
