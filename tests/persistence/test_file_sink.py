"""Tests for the file-based concrete persistence sink."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.persistence import FileCrawlResultSink, PersistenceWriteError

if TYPE_CHECKING:
    from pathlib import Path


def test_save_appends_one_json_line(tmp_path: Path) -> None:
    destination = tmp_path / "results.jsonl"
    sink = FileCrawlResultSink(destination=destination)
    item = CrawlerItem({"source": "cnn_indonesia", "headline": "A"})

    sink.save(item)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"source": "cnn_indonesia", "headline": "A"}


def test_save_appends_without_overwriting_or_deduplicating(tmp_path: Path) -> None:
    destination = tmp_path / "results.jsonl"
    sink = FileCrawlResultSink(destination=destination)
    item = CrawlerItem({"source": "cnn_indonesia"})

    sink.save(item)
    sink.save(item)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == lines[1]


def test_destination_property_exposes_configured_path(tmp_path: Path) -> None:
    destination = tmp_path / "results.jsonl"
    sink = FileCrawlResultSink(destination=destination)

    assert sink.destination == destination


def test_save_wraps_serialization_failure_before_opening_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "results.jsonl"
    sink = FileCrawlResultSink(destination=destination)
    item = CrawlerItem({"unserializable": object()})

    with pytest.raises(PersistenceWriteError):
        sink.save(item)
    assert not destination.exists()


def test_save_wraps_write_failure_when_parent_directory_is_missing(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "missing-dir" / "results.jsonl"
    sink = FileCrawlResultSink(destination=destination)
    item = CrawlerItem({"source": "cnn_indonesia"})

    with pytest.raises(PersistenceWriteError):
        sink.save(item)
