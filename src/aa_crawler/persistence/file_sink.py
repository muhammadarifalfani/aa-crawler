"""Minimal concrete file-based persistence sink (ADR-024)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aa_crawler.persistence.base import BaseCrawlResultSink
from aa_crawler.persistence.errors import PersistenceWriteError

if TYPE_CHECKING:
    from pathlib import Path

    from aa_crawler.crawler import CrawlerItem


class FileCrawlResultSink(BaseCrawlResultSink):
    """Append one JSON Lines record per saved crawl result to a local file.

    Each ``save()`` call appends exactly one line and never deduplicates or
    overwrites a prior line for the same URL; ADR-024 leaves idempotency
    unresolved, and this sink makes no guarantee beyond append-only writes.
    The destination file's parent directory must already exist; this sink
    does not create directories.
    """

    def __init__(self, *, destination: Path) -> None:
        """Configure the destination file this sink appends to.

        Args:
            destination: The local file path to append JSON Lines records
                to. The file is created on first write if it does not
                already exist.
        """
        self._destination = destination

    @property
    def destination(self) -> Path:
        """Return the configured destination file path."""
        return self._destination

    def save(self, item: CrawlerItem) -> None:
        """Append one crawl result as a single JSON line.

        Reuses the same conversion `aa_crawler.cli.app.run_crawl` already
        performs: the immutable `CrawlerItem.data` mapping is converted to a
        plain `dict` before serialization, since a `MappingProxyType` is not
        itself JSON-serializable.

        Args:
            item: The produced crawler item to persist.

        Raises:
            PersistenceWriteError: If the item cannot be serialized or the
                destination file cannot be durably written.
        """
        try:
            payload = json.dumps(dict(item.data), sort_keys=True)
        except (TypeError, ValueError) as error:
            raise PersistenceWriteError(
                "crawl result could not be serialized for persistence"
            ) from error

        try:
            with self._destination.open("a", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
        except OSError as error:
            raise PersistenceWriteError(
                "crawl result could not be durably written"
            ) from error
