"""Abstract, optional persistence port for crawl results (ADR-024)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aa_crawler.crawler import CrawlerItem


class BaseCrawlResultSink(ABC):
    """Own durably persisting one produced crawl result.

    This port is optional and is never constructed or invoked by
    ``ArticleCrawlService``, ``ApplicationRuntime``, or ``aa_crawler.cli``
    (ADR-024). A caller that already holds a produced ``CrawlerItem``
    composes a concrete sink explicitly and calls ``save()`` itself.

    Idempotency is not guaranteed by this contract. Concrete sinks document
    their own behavior for repeated saves of the same result.
    """

    @abstractmethod
    def save(self, item: CrawlerItem) -> None:
        """Durably persist one crawl result.

        Args:
            item: The produced crawler item to persist.

        Raises:
            PersistenceError: If the item cannot be durably persisted.
        """
