"""Tests for synchronous article crawl orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

import aa_crawler.application.service as service_module
from aa_crawler.application import (
    ArticleCrawlService,
    SourceBoundaryError,
    UnsupportedSourceError,
)
from aa_crawler.composition import ParserComposer, ParserCompositionError
from aa_crawler.crawler import CrawlerItem, RequestError
from aa_crawler.html import (
    HtmlContentTypeError,
    HtmlDisallowedError,
    HtmlDocument,
    HtmlFetcher,
)
from aa_crawler.parser import ArticleParserError, BaseParser
from aa_crawler.robots import RobotsError
from aa_crawler.sources import SourceProfile, SourceRegistry

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

REQUESTED_URL = "https://news.example.com/articles/one"
FINAL_URL = "https://news.example.com/articles/one-final"


class RecordingRegistry:
    """Record lookups while preserving real SourceRegistry behavior."""

    def __init__(
        self,
        profiles: tuple[SourceProfile, ...],
        events: list[str] | None = None,
    ) -> None:
        self.delegate = SourceRegistry(profiles)
        self.events = events

    def get_by_url(
        self,
        url: object,
        *,
        include_disabled: bool = False,
    ) -> SourceProfile | None:
        if self.events is not None:
            self.events.append(f"lookup:{url}")
        return self.delegate.get_by_url(url, include_disabled=include_disabled)


class StubFetcher:
    """Return one document or propagate one configured acquisition error."""

    def __init__(
        self,
        document: HtmlDocument,
        *,
        events: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.document = document
        self.events = events
        self.error = error
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        self.calls.append((url, metadata))
        if self.events is not None:
            self.events.append("fetch")
        if self.error is not None:
            raise self.error
        return self.document


class StubParser(BaseParser):
    """Return configured items while recording the received document."""

    def __init__(
        self,
        items: tuple[CrawlerItem, ...],
        *,
        events: list[str] | None = None,
        error: ArticleParserError | None = None,
    ) -> None:
        self.items = items
        self.events = events
        self.error = error
        self.documents: list[HtmlDocument] = []

    def parse_document(self, document: HtmlDocument) -> Iterable[CrawlerItem]:
        self.documents.append(document)
        if self.events is not None:
            self.events.append("parse")
        if self.error is not None:
            raise self.error
        return self.items


class StubComposer:
    """Return one parser or propagate one configured composition error."""

    def __init__(
        self,
        parser: BaseParser,
        *,
        events: list[str] | None = None,
        error: ParserCompositionError | None = None,
    ) -> None:
        self.parser = parser
        self.events = events
        self.error = error
        self.profiles: list[SourceProfile] = []

    def create(self, profile: SourceProfile) -> BaseParser:
        self.profiles.append(profile)
        if self.events is not None:
            self.events.append("compose")
        if self.error is not None:
            raise self.error
        return self.parser


def make_profile(
    *,
    source: str = "example_news",
    domains: tuple[str, ...] = ("news.example.com",),
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(source=source, domains=domains, enabled=enabled)


def make_document(*, final_url: str = FINAL_URL) -> HtmlDocument:
    return HtmlDocument(
        requested_url=REQUESTED_URL,
        final_url=final_url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content="<html></html>",
        encoding="utf-8",
    )


def make_service(
    registry: RecordingRegistry,
    fetcher: StubFetcher,
    composer: StubComposer,
) -> ArticleCrawlService:
    return ArticleCrawlService(
        source_registry=cast("SourceRegistry", registry),
        html_fetcher=cast("HtmlFetcher", fetcher),
        parser_composer=cast("ParserComposer", composer),
    )


def test_public_api_exports_article_crawl_service() -> None:
    from aa_crawler import application

    assert application.__all__ == [
        "ApplicationError",
        "ArticleCrawlService",
        "SourceBoundaryError",
        "UnsupportedSourceError",
    ]


def test_constructor_retains_exact_read_only_collaborators() -> None:
    registry = RecordingRegistry((make_profile(),))
    fetcher = StubFetcher(make_document())
    composer = StubComposer(StubParser(()))
    registry_dependency = cast("SourceRegistry", registry)
    fetcher_dependency = cast("HtmlFetcher", fetcher)
    composer_dependency = cast("ParserComposer", composer)
    service = ArticleCrawlService(
        source_registry=registry_dependency,
        html_fetcher=fetcher_dependency,
        parser_composer=composer_dependency,
    )

    assert service.source_registry is registry_dependency
    assert service.html_fetcher is fetcher_dependency
    assert service.parser_composer is composer_dependency


def test_happy_path_preserves_sequence_document_items_and_order() -> None:
    events: list[str] = []
    profile = make_profile()
    document = make_document()
    items = (CrawlerItem({"position": 1}), CrawlerItem({"position": 2}))
    registry = RecordingRegistry((profile,), events)
    fetcher = StubFetcher(document, events=events)
    parser = StubParser(items, events=events)
    composer = StubComposer(parser, events=events)

    result = make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert result == items
    assert fetcher.calls == [(REQUESTED_URL, None)]
    assert composer.profiles == [profile]
    assert composer.profiles[0] is profile
    assert parser.documents == [document]
    assert events == [
        f"lookup:{REQUESTED_URL}",
        "fetch",
        f"lookup:{FINAL_URL}",
        "compose",
        "parse",
    ]


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "http://news.example.com/articles/one",
        "https://unknown.example.com/articles/one",
        "https://disabled.example.com/articles/one",
    ],
)
def test_unsupported_source_stops_before_acquisition(url: str) -> None:
    profiles = (
        make_profile(),
        make_profile(
            source="disabled_news",
            domains=("disabled.example.com",),
            enabled=False,
        ),
    )
    registry = RecordingRegistry(profiles)
    fetcher = StubFetcher(make_document())
    composer = StubComposer(StubParser(()))

    with pytest.raises(UnsupportedSourceError):
        make_service(registry, fetcher, composer).crawl(url)

    assert fetcher.calls == []
    assert composer.profiles == []


@pytest.mark.parametrize(
    ("final_url", "extra_profiles"),
    [
        ("https://unknown.example.com/final", ()),
        (
            "https://other.example.com/final",
            (make_profile(source="other_news", domains=("other.example.com",)),),
        ),
        (
            "https://disabled.example.com/final",
            (
                make_profile(
                    source="disabled_news",
                    domains=("disabled.example.com",),
                    enabled=False,
                ),
            ),
        ),
    ],
)
def test_final_source_boundary_stops_before_parser_composition(
    final_url: str,
    extra_profiles: tuple[SourceProfile, ...],
) -> None:
    profile = make_profile()
    registry = RecordingRegistry((profile, *extra_profiles))
    fetcher = StubFetcher(make_document(final_url=final_url))
    parser = StubParser(())
    composer = StubComposer(parser)

    with pytest.raises(SourceBoundaryError):
        make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert fetcher.calls == [(REQUESTED_URL, None)]
    assert composer.profiles == []
    assert parser.documents == []


def test_same_profile_multi_domain_transition_is_allowed() -> None:
    profile = make_profile(domains=("news.example.com", "cdn.example.com"))
    document = make_document(final_url="https://cdn.example.com/final")
    item = CrawlerItem({"source": "example_news"})
    registry = RecordingRegistry((profile,))
    fetcher = StubFetcher(document)
    parser = StubParser((item,))
    composer = StubComposer(parser)

    result = make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert result == (item,)
    assert composer.profiles == [profile]
    assert parser.documents == [document]


@pytest.mark.parametrize(
    "error",
    [
        HtmlDisallowedError("HTML request is disallowed by robots.txt"),
        RobotsError("robots.txt policy evaluation failed"),
        RequestError("HTTP request execution failed"),
        HtmlContentTypeError("HTML response has an unsupported Content-Type"),
    ],
)
def test_acquisition_errors_propagate_unchanged(error: Exception) -> None:
    registry = RecordingRegistry((make_profile(),))
    fetcher = StubFetcher(make_document(), error=error)
    composer = StubComposer(StubParser(()))

    with pytest.raises(type(error)) as caught:
        make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert caught.value is error
    assert composer.profiles == []


def test_parser_composition_error_propagates_unchanged() -> None:
    error = ParserCompositionError("safe composition failure")
    registry = RecordingRegistry((make_profile(),))
    fetcher = StubFetcher(make_document())
    composer = StubComposer(StubParser(()), error=error)

    with pytest.raises(ParserCompositionError) as caught:
        make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert caught.value is error


def test_article_parser_error_propagates_unchanged() -> None:
    error = ArticleParserError("article metadata is invalid")
    registry = RecordingRegistry((make_profile(),))
    fetcher = StubFetcher(make_document())
    parser = StubParser((), error=error)
    composer = StubComposer(parser)

    with pytest.raises(ArticleParserError) as caught:
        make_service(registry, fetcher, composer).crawl(REQUESTED_URL)

    assert caught.value is error


@pytest.mark.parametrize("metadata", [None, {"trace": "stable", "attempt": 1}])
def test_metadata_is_forwarded_by_identity_without_mutation(
    metadata: Mapping[str, object] | None,
) -> None:
    registry = RecordingRegistry((make_profile(),))
    fetcher = StubFetcher(make_document())
    composer = StubComposer(StubParser(()))

    make_service(registry, fetcher, composer).crawl(
        REQUESTED_URL,
        metadata=metadata,
    )

    assert fetcher.calls[0][1] is metadata
    if metadata is not None:
        assert metadata == {"trace": "stable", "attempt": 1}


def test_service_is_reusable_without_operation_state_leakage() -> None:
    profile = make_profile()
    registry = RecordingRegistry((profile,))
    fetcher = StubFetcher(make_document())
    parser = StubParser((CrawlerItem({"ok": True}),))
    composer = StubComposer(parser)
    service = make_service(registry, fetcher, composer)

    first = service.crawl(REQUESTED_URL)
    second = service.crawl(REQUESTED_URL)

    assert first == second == (CrawlerItem({"ok": True}),)
    assert fetcher.calls == [(REQUESTED_URL, None), (REQUESTED_URL, None)]
    assert composer.profiles == [profile, profile]
    assert parser.documents == [fetcher.document, fetcher.document]


def test_service_module_has_no_direct_runtime_boundary_dependencies() -> None:
    excluded_names = (
        "HttpClient",
        "RetryPolicy",
        "RobotsPolicy",
        "RequestIdentity",
        "DEFAULT_SOURCE_PROFILES",
        "bootstrap_application",
    )

    assert all(not hasattr(service_module, name) for name in excluded_names)
