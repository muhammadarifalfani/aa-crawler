"""Abstract synchronous crawler runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from aa_crawler.crawler.errors import ParsingError, RequestError, ResponseError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from aa_crawler.crawler.contracts import (
        CrawlerItem,
        CrawlerRequest,
        CrawlerResponse,
    )
    from aa_crawler.http import HttpClient


class BaseCrawler(ABC):
    """Orchestrate crawler contracts through an injected HTTP client."""

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client

    @abstractmethod
    def start_requests(self) -> Iterable[CrawlerRequest]:
        """Return the crawler's initial requests without executing them."""

    def parse(self, response: CrawlerResponse) -> Iterable[CrawlerItem]:
        """Convert one response when using the default request processor."""
        raise NotImplementedError(
            "subclasses using default request processing must implement parse()"
        )

    def _process_request(self, request: CrawlerRequest) -> Iterable[CrawlerItem]:
        """Send and parse one request using the default crawler lifecycle."""
        response = self._http_client.send(request)
        try:
            yield from self.parse(response)
        except (RequestError, ResponseError, ParsingError):
            raise
        except Exception as error:
            raise ParsingError("crawler response parsing failed") from error

    def crawl(self) -> Iterator[CrawlerItem]:
        """Execute initial requests sequentially and lazily yield parsed items."""
        for request in self.start_requests():
            yield from self._process_request(request)
