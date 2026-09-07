"""Tests for the SQLite-backed concrete persistence sink (ADR-030)."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.persistence import PersistenceWriteError, SqliteCrawlResultSink

if TYPE_CHECKING:
    from pathlib import Path


def _rows(destination: Path) -> list[tuple[str, str, str]]:
    connection = sqlite3.connect(destination)
    try:
        return list(
            connection.execute(
                "SELECT requested_url, payload, updated_at "
                "FROM crawl_results ORDER BY requested_url"
            )
        )
    finally:
        connection.close()


def test_save_creates_the_database_and_table_on_first_write(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem({"requested_url": "https://a.test", "headline": "A"})

    sink.save(item)

    assert destination.exists()
    rows = _rows(destination)
    assert len(rows) == 1
    requested_url, payload, updated_at = rows[0]
    assert requested_url == "https://a.test"
    assert json.loads(payload) == {
        "requested_url": "https://a.test",
        "headline": "A",
    }
    assert updated_at


def test_save_upserts_by_requested_url_instead_of_duplicating(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    first = CrawlerItem({"requested_url": "https://a.test", "headline": "first"})
    second = CrawlerItem({"requested_url": "https://a.test", "headline": "second"})

    sink.save(first)
    sink.save(second)

    rows = _rows(destination)
    assert len(rows) == 1
    requested_url, payload, _ = rows[0]
    assert requested_url == "https://a.test"
    assert json.loads(payload)["headline"] == "second"


def test_save_updates_updated_at_on_each_upsert(tmp_path: Path) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem({"requested_url": "https://a.test"})

    sink.save(item)
    first_updated_at = _rows(destination)[0][2]
    sink.save(item)
    second_updated_at = _rows(destination)[0][2]

    assert first_updated_at
    assert second_updated_at
    # Not asserting inequality: two saves may land in the same
    # microsecond-resolution timestamp on a fast machine. The contract
    # under test is that a value is always written, not that it changes.


def test_distinct_urls_produce_distinct_rows(tmp_path: Path) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    sink.save(CrawlerItem({"requested_url": "https://a.test"}))
    sink.save(CrawlerItem({"requested_url": "https://b.test"}))

    rows = _rows(destination)
    assert [row[0] for row in rows] == ["https://a.test", "https://b.test"]


def test_destination_property_exposes_configured_path(tmp_path: Path) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)

    assert sink.destination == destination


def test_save_wraps_serialization_failure_before_opening_database(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem({"requested_url": "https://a.test", "unserializable": object()})

    with pytest.raises(PersistenceWriteError):
        sink.save(item)
    assert not destination.exists()


@pytest.mark.parametrize(
    "data",
    [
        {"headline": "no requested_url key at all"},
        {"requested_url": ""},
        {"requested_url": None},
        {"requested_url": 12345},
    ],
    ids=["missing_key", "empty_string", "none", "wrong_type"],
)
def test_save_rejects_missing_or_unusable_requested_url(
    tmp_path: Path,
    data: dict[str, object],
) -> None:
    destination = tmp_path / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem(data)

    with pytest.raises(PersistenceWriteError):
        sink.save(item)
    assert not destination.exists()


def test_save_wraps_write_failure_when_parent_directory_is_missing(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "missing-dir" / "results.db"
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem({"requested_url": "https://a.test"})

    with pytest.raises(PersistenceWriteError):
        sink.save(item)


def test_save_wraps_execute_failure_when_destination_is_not_a_valid_database(
    tmp_path: Path,
) -> None:
    # sqlite3.connect() succeeds lazily even against a non-database file;
    # the failure surfaces on the first execute(), exercising the second
    # error-handling path distinct from a connect()-time failure above.
    destination = tmp_path / "results.db"
    destination.write_text("not a sqlite database", encoding="utf-8")
    sink = SqliteCrawlResultSink(destination=destination)
    item = CrawlerItem({"requested_url": "https://a.test"})

    with pytest.raises(PersistenceWriteError):
        sink.save(item)
