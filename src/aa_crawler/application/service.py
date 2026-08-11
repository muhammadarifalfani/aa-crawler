"""Synchronous application-level article crawl orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aa_crawler.application.errors import SourceBoundaryError, UnsupportedSourceError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aa_crawler.composition import ParserComposer
    from aa_crawler.crawler import CrawlerItem
    from aa_crawler.html import HtmlFetcher
    from aa_crawler.sources import SourceRegistry


@dataclass(frozen=True, slots=True, eq=False)
class ArticleCrawlService:
    """Coordinate one synchronous article crawl through existing boundaries."""

    source_registry: SourceRegistry
    html_fetcher: HtmlFetcher
    parser_composer: ParserComposer

    def crawl(
        self,
        url: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CrawlerItem, ...]:
        """Acquire and parse one URL within its registered source boundary."""
        profile = self.source_registry.get_by_url(url)
        if profile is None:
            raise UnsupportedSourceError

        document = self.html_fetcher.fetch(url=url, metadata=metadata)
        final_profile = self.source_registry.get_by_url(document.final_url)
        if final_profile is not profile:
            raise SourceBoundaryError

        parser = self.parser_composer.create(profile)
        return tuple(parser.parse(document))
