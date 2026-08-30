"""Tests for the persistence error hierarchy."""

from __future__ import annotations

from aa_crawler.crawler import CrawlerError
from aa_crawler.persistence import PersistenceError, PersistenceWriteError


def test_persistence_error_derives_from_crawler_error() -> None:
    assert issubclass(PersistenceError, CrawlerError)


def test_persistence_write_error_derives_from_persistence_error() -> None:
    assert issubclass(PersistenceWriteError, PersistenceError)
