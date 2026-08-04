"""Generic synchronous HTML crawler composition."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from aa_crawler.crawler.base import BaseCrawler
from aa_crawler.crawler.contracts import CrawlerRequest

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from aa_crawler.crawler.contracts import CrawlerItem
    from aa_crawler.html import HtmlFetcher
    from aa_crawler.http import HttpClient
    from aa_crawler.parser import BaseParser


class HtmlCrawler(BaseCrawler):
    """Compose HTML fetching and parsing for an ordered URL collection."""

    def __init__(
        self,
        *,
        http_client: HttpClient,
        html_fetcher: HtmlFetcher,
        parser: BaseParser,
        urls: Iterable[str],
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(http_client=http_client)
        copied_urls = tuple(urls)
        if any(not url.strip() for url in copied_urls):
            raise ValueError("urls must not contain empty values")
        self._html_fetcher = html_fetcher
        self._parser = parser
        self._urls = copied_urls
        self._metadata = MappingProxyType({} if metadata is None else dict(metadata))

    def start_requests(self) -> Iterable[CrawlerRequest]:
        """Create one ordered GET request per configured URL."""
        return tuple(
            CrawlerRequest(url=url, metadata=self._metadata) for url in self._urls
        )

    def _process_request(self, request: CrawlerRequest) -> Iterable[CrawlerItem]:
        """Fetch and parse one request through the specialized boundaries."""
        document = self._html_fetcher.fetch(
            url=request.url,
            metadata=request.metadata,
        )
        return self._parser.parse(document)
