"""Probe never issues SearchApi queries and never exposes article bodies."""

from datetime import datetime, timezone

import pytest

from app.trend_collection.searchapi_article_reader import ArticleReadBlocked
from app.trend_collection.searchapi_evidence import ArticleObservation
from scripts import probe_searchapi_articles as probe

NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


class FakeReader:
    def __init__(self, *, fail_first=False):
        self.calls = []
        self.fail_first = fail_first

    def read_url(self, url, *, now):
        self.calls.append(url)
        if self.fail_first and len(self.calls) == 1:
            raise ArticleReadBlocked("ARTICLE_BODY_MISSING_OR_INVALID")
        return ArticleObservation(
            source_url=url,
            body_text="SECRET ARTICLE BODY — NEVER PRINT THIS",
            published_at_utc=NOW,
            retrieved_at_utc=now,
        )


def test_success_report_is_bounded_and_omits_article_contents():
    reader = FakeReader()
    report = probe.collect_report(reader, now=NOW)
    assert len(reader.calls) == 2
    assert len(set(reader.calls)) == 2
    assert report["new_searchapi_requests"] == 0
    assert report["max_publisher_requests"] == 2
    assert report["publication_authorization"] == "NONE"
    assert [r["status"] for r in report["results"]] == [
        "PARSE_OK_NOT_FACT_VERIFIED",
        "PARSE_OK_NOT_FACT_VERIFIED",
    ]
    assert report["results"][0]["published_at_utc"] == NOW.isoformat()
    assert "SECRET ARTICLE BODY" not in str(report)
    assert "https://" not in str(report)


def test_first_error_is_safe_and_second_article_still_checked():
    reader = FakeReader(fail_first=True)
    report = probe.collect_report(reader, now=NOW)
    assert len(reader.calls) == 2
    assert report["results"][0] == {
        "publisher": "YNA",
        "status": "HOLD",
        "reason": "ARTICLE_BODY_MISSING_OR_INVALID",
    }
    assert report["results"][1]["status"] == "PARSE_OK_NOT_FACT_VERIFIED"
    assert report["publication_authorization"] == "NONE"


def test_no_live_flag_never_initializes_reader(monkeypatch, capsys):
    def not_allowed():
        raise AssertionError("Reader must not be created")
    monkeypatch.setattr(probe, "ArticleReader", not_allowed)
    with pytest.raises(SystemExit) as stopped:
        probe.main([])
    assert stopped.value.code == 2
    assert "--live required" in capsys.readouterr().err


def test_opt_in_calls_only_fake_reader_and_prints_safe_report(
    monkeypatch, capsys,
):
    reader = FakeReader()
    monkeypatch.setattr(probe, "ArticleReader", lambda: reader)
    status = probe.main(["--live"])
    output = capsys.readouterr().out
    assert status == 0
    assert len(reader.calls) == 2
    assert "READ_ONLY_ARTICLE_DIAGNOSTIC" in output
    assert "SECRET ARTICLE BODY" not in output
    assert "https://" not in output


def test_opt_in_reports_hold_as_failure_without_retry(monkeypatch, capsys):
    reader = FakeReader(fail_first=True)
    monkeypatch.setattr(probe, "ArticleReader", lambda: reader)
    assert probe.main(["--live"]) == 1
    assert len(reader.calls) == 2
    assert "ARTICLE_BODY_MISSING_OR_INVALID" in capsys.readouterr().out
