"""Abstract synchronous parser lifecycle."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from aa_crawler.crawler import CrawlerItem
from aa_crawler.parser.errors import (
    ParserContractError,
    ParserError,
    ParserExecutionError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from aa_crawler.html import HtmlDocument


class BaseParser(ABC):
    """Validate and lazily expose items produced by parser implementations."""

    @abstractmethod
    def parse_document(self, document: HtmlDocument) -> Iterable[CrawlerItem]:
        """Convert one HTML document into zero or more crawler items."""

    def parse(self, document: HtmlDocument) -> Iterator[CrawlerItem]:
        """Lazily validate and yield items from the parser implementation."""
        try:
            for item in self.parse_document(document):
                if not isinstance(item, CrawlerItem):
                    raise ParserContractError(
                        "parser implementation yielded an invalid item"
                    )
                yield item
        except ParserError:
            raise
        except Exception as error:
            raise ParserExecutionError("parser implementation failed") from error
