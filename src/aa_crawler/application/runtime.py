"""Synchronous application runtime composition and resource ownership."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Self

from aa_crawler.application.service import ArticleCrawlService
from aa_crawler.composition import ParserComposer
from aa_crawler.html import HtmlFetcher
from aa_crawler.http import HttpClient, RetryPolicy, TimeoutPolicy
from aa_crawler.identity import RequestIdentity
from aa_crawler.robots import RobotsPolicy
from aa_crawler.sources import DEFAULT_SOURCE_PROFILES, SourceRegistry

if TYPE_CHECKING:
    from types import TracebackType


@dataclass(frozen=True, slots=True, eq=False)
class ApplicationRuntime:
    """Own the lifecycle of one composed synchronous application graph."""

    _article_crawl_service: ArticleCrawlService
    _cleanup_stack: ExitStack = field(repr=False)

    @property
    def article_crawl_service(self) -> ArticleCrawlService:
        """Return the runtime's application-level article crawl service."""
        return self._article_crawl_service

    def close(self) -> None:
        """Release all resources owned by this runtime."""
        self._cleanup_stack.close()

    def __enter__(self) -> Self:
        """Return this runtime for synchronous context management."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release owned resources when leaving a synchronous context."""
        self.close()


def create_application_runtime() -> ApplicationRuntime:
    """Compose one independent application runtime with explicit ownership."""
    product_version = metadata.version("aa-crawler")
    identity = RequestIdentity(product_version=product_version)
    timeout_policy = TimeoutPolicy()
    retry_policy = RetryPolicy()
    source_registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    parser_composer = ParserComposer()

    with ExitStack() as stack:
        http_client = stack.enter_context(
            HttpClient(
                timeout_policy=timeout_policy,
                retry_policy=retry_policy,
            )
        )
        robots_policy = RobotsPolicy(
            http_client=http_client,
            identity=identity,
        )
        html_fetcher = HtmlFetcher(
            http_client=http_client,
            robots_policy=robots_policy,
            identity=identity,
        )
        article_crawl_service = ArticleCrawlService(
            source_registry=source_registry,
            html_fetcher=html_fetcher,
            parser_composer=parser_composer,
        )
        return ApplicationRuntime(
            _article_crawl_service=article_crawl_service,
            _cleanup_stack=stack.pop_all(),
        )


__all__ = ["ApplicationRuntime", "create_application_runtime"]
