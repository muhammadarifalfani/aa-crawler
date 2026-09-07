"""SQLite-backed concrete persistence sink with idempotent upserts (ADR-030)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from aa_crawler.persistence.base import BaseCrawlResultSink
from aa_crawler.persistence.errors import PersistenceWriteError

if TYPE_CHECKING:
    from pathlib import Path

    from aa_crawler.crawler import CrawlerItem

_CREATE_TABLE = (
    "CREATE TABLE IF NOT EXISTS crawl_results ("
    "requested_url TEXT PRIMARY KEY, "
    "payload TEXT NOT NULL, "
    "updated_at TEXT NOT NULL"
    ")"
)

_UPSERT = (
    "INSERT INTO crawl_results (requested_url, payload, updated_at) "
    "VALUES (?, ?, ?) "
    "ON CONFLICT(requested_url) DO UPDATE SET "
    "payload = excluded.payload, "
    "updated_at = excluded.updated_at"
)


class SqliteCrawlResultSink(BaseCrawlResultSink):
    """Upsert one row per ``requested_url`` into a local SQLite database.

    Unlike `FileCrawlResultSink`'s append-only, no-deduplication contract,
    each `save()` call upserts by `item.data["requested_url"]`: re-crawling
    the same URL replaces its existing row instead of duplicating it,
    giving real idempotency for the scheduled and batch re-crawls ADR-028
    and ADR-029 introduced. The `crawl_results` table is created
    automatically on first use if it does not already exist. The
    destination file's parent directory must already exist; this sink
    does not create directories, matching `FileCrawlResultSink`'s
    existing documented behavior.

    This sink is not wired into the CLI (ADR-030 explicitly defers that);
    a caller composes it directly, exactly as `FileCrawlResultSink` could
    be composed before ADR-027.
    """

    def __init__(self, *, destination: Path) -> None:
        """Configure the destination SQLite database file this sink upserts to.

        Args:
            destination: The local database file path. The file and its
                schema are created on first write if they do not already
                exist; the parent directory must already exist.
        """
        self._destination = destination

    @property
    def destination(self) -> Path:
        """Return the configured destination database file path."""
        return self._destination

    def save(self, item: CrawlerItem) -> None:
        """Upsert one crawl result, keyed by its ``requested_url``.

        Args:
            item: The produced crawler item to persist.

        Raises:
            PersistenceWriteError: If the item cannot be serialized, has
                no usable ``requested_url`` to upsert by, or the
                destination database cannot be durably written.
        """
        try:
            payload = json.dumps(dict(item.data), sort_keys=True)
        except (TypeError, ValueError) as error:
            raise PersistenceWriteError(
                "crawl result could not be serialized for persistence"
            ) from error

        requested_url = item.data.get("requested_url")
        if not isinstance(requested_url, str) or not requested_url:
            raise PersistenceWriteError(
                "crawl result has no usable requested_url to upsert by"
            )

        updated_at = datetime.now(UTC).isoformat()

        try:
            connection = sqlite3.connect(self._destination)
        except sqlite3.Error as error:
            raise PersistenceWriteError(
                "crawl result could not be durably written"
            ) from error

        try:
            with connection:
                connection.execute(_CREATE_TABLE)
                connection.execute(_UPSERT, (requested_url, payload, updated_at))
        except sqlite3.Error as error:
            raise PersistenceWriteError(
                "crawl result could not be durably written"
            ) from error
        finally:
            connection.close()
