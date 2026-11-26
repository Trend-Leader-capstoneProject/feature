"""Single-run, read-only HTML compatibility probe for two known news URLs.

Run from backend: python -m scripts.probe_searchapi_articles --live
No SearchApi requests, database access, file writes, or publication.
Outputs only parser status, body length and publication timestamp.
"""

import argparse
import json
from datetime import datetime, timezone

from app.trend_collection.searchapi_article_reader import (
    ArticleReadBlocked,
    ArticleReader,
)

_ARTICLES = (
    ("YNA", "https://www.yna.co.kr/view/AKR20261123042700005"),
    ("NEWSIS", "https://mobile.newsis.com/view/NISX20261123_0003878761"),
)


def collect_report(reader: ArticleReader, *, now: datetime) -> dict:
    """Two bounded source reads; article text is never returned or logged."""
    results = []
    for publisher, url in _ARTICLES:
        try:
            observation = reader.read_url(url, now=now)
        except ArticleReadBlocked as exc:
            results.append({
                "publisher": publisher,
                "status": "HOLD",
                "reason": str(exc),
            })
            continue
        results.append({
            "publisher": publisher,
            "status": "PARSE_OK_NOT_FACT_VERIFIED",
            "published_at_utc": observation.published_at_utc.isoformat(),
            "body_character_count": len(observation.body_text),
        })
    return {
        "status": "READ_ONLY_ARTICLE_DIAGNOSTIC",
        "publication_authorization": "NONE",
        "new_searchapi_requests": 0,
        "max_publisher_requests": 2,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true",
        help="Explicitly allow one read for each of the two fixed article URLs",
    )
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("HOLD: --live required; no article requests made")
    reader = ArticleReader()
    result = collect_report(reader, now=datetime.now(timezone.utc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(
        item["status"] == "PARSE_OK_NOT_FACT_VERIFIED"
        for item in result["results"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
