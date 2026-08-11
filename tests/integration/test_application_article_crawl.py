"""Cross-package verification of application-level article crawling."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from aa_crawler.application import (
    ArticleCrawlService,
    SourceBoundaryError,
    UnsupportedSourceError,
)
from aa_crawler.composition import ParserComposer
from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument, HtmlFetcher
from aa_crawler.parser import ArticleParserError, BaseParser, JsonLdArticleParser
from aa_crawler.sources import (
    CNN_INDONESIA_PROFILE,
    DEFAULT_SOURCE_PROFILES,
    KOMPAS_PROFILE,
    SourceProfile,
    SourceRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_CNN_REQUESTED_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "invented-application-story?campaign=synthetic"
)
_CNN_CANONICAL_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "invented-application-story"
)
_PUBLISHED = "2099-01-01T08:30:00+07:00"
_MODIFIED = "2099-01-01T09:15:00+07:00"


class FakeHtmlFetcher:
    """Return deterministic documents without constructing acquisition runtime."""

    def __init__(self, documents: tuple[HtmlDocument, ...]) -> None:
        self.documents = documents
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        self.calls.append((url, metadata))
        return self.documents[len(self.calls) - 1]


class RecordingParserComposer:
    """Observe composition while delegating to the real ParserComposer."""

    def __init__(self) -> None:
        self.delegate = ParserComposer()
        self.profiles: list[SourceProfile] = []
        self.parsers: list[BaseParser] = []

    def create(self, profile: SourceProfile) -> BaseParser:
        self.profiles.append(profile)
        parser = self.delegate.create(profile)
        self.parsers.append(parser)
        return parser


def _synthetic_html(
    canonical_url: str,
    *,
    headline: str = "Invented application integration headline",
) -> str:
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical_url},
        "headline": headline,
        "description": "Invented application integration description.",
        "author": [{"name": "Synthetic Author One"}, {"name": "Author Two"}],
        "datePublished": _PUBLISHED,
        "dateModified": _MODIFIED,
        "image": {"url": "https://images.example.test/invented.jpg"},
        "articleSection": "Synthetic Section",
        "inLanguage": "id-ID",
    }
    return (
        '<html lang="id-ID"><head>'
        f'<link rel="canonical" href="{canonical_url}">'
        '<script type="application/ld+json">'
        f"{json.dumps(node)}"
        "</script></head><body></body></html>"
    )


def _document(
    *,
    requested_url: str = _CNN_REQUESTED_URL,
    final_url: str = _CNN_CANONICAL_URL,
    canonical_url: str = _CNN_CANONICAL_URL,
    headline: str = "Invented application integration headline",
) -> HtmlDocument:
    return HtmlDocument(
        requested_url=requested_url,
        final_url=final_url,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_synthetic_html(canonical_url, headline=headline),
        encoding="utf-8",
    )


def _service(
    registry: SourceRegistry,
    fetcher: FakeHtmlFetcher,
    composer: RecordingParserComposer,
) -> ArticleCrawlService:
    return ArticleCrawlService(
        source_registry=registry,
        html_fetcher=cast("HtmlFetcher", fetcher),
        parser_composer=cast("ParserComposer", composer),
    )


def test_cnn_golden_path_uses_real_registry_composer_parser_and_contracts() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    fetcher = FakeHtmlFetcher((_document(),))
    composer = RecordingParserComposer()

    result = _service(registry, fetcher, composer).crawl(_CNN_REQUESTED_URL)

    assert registry.get_by_url(_CNN_REQUESTED_URL) is CNN_INDONESIA_PROFILE
    assert fetcher.calls == [(_CNN_REQUESTED_URL, None)]
    assert composer.profiles == [CNN_INDONESIA_PROFILE]
    assert isinstance(composer.parsers[0], JsonLdArticleParser)
    assert result == (
        CrawlerItem(
            {
                "source": "cnn_indonesia",
                "source_domain": "www.cnnindonesia.com",
                "requested_url": _CNN_REQUESTED_URL,
                "canonical_url": _CNN_CANONICAL_URL,
                "headline": "Invented application integration headline",
                "published_at": "2099-01-01T01:30:00+00:00",
                "description": "Invented application integration description.",
                "author_names": ("Synthetic Author One", "Author Two"),
                "modified_at": "2099-01-01T02:15:00+00:00",
                "section": "Synthetic Section",
                "lead_image_url": "https://images.example.test/invented.jpg",
                "language": "id-ID",
            }
        ),
    )


def test_requested_query_and_parser_canonical_remain_distinct() -> None:
    fetcher = FakeHtmlFetcher((_document(),))
    result = _service(
        SourceRegistry(DEFAULT_SOURCE_PROFILES),
        fetcher,
        RecordingParserComposer(),
    ).crawl(_CNN_REQUESTED_URL)

    assert result[0].data["requested_url"] == _CNN_REQUESTED_URL
    assert result[0].data["canonical_url"] == _CNN_CANONICAL_URL
    assert "?" in str(result[0].data["requested_url"])
    assert "?" not in str(result[0].data["canonical_url"])


def test_same_profile_multi_domain_final_url_succeeds() -> None:
    profile = SourceProfile(
        source="example_news",
        domains=("news.example.test", "m.example.test"),
    )
    requested_url = "https://news.example.test/article?input=one"
    canonical_url = "https://m.example.test/article"
    document = _document(
        requested_url=requested_url,
        final_url=canonical_url,
        canonical_url=canonical_url,
    )
    composer = RecordingParserComposer()

    result = _service(
        SourceRegistry((profile,)),
        FakeHtmlFetcher((document,)),
        composer,
    ).crawl(requested_url)

    assert result[0].data["source"] == "example_news"
    assert result[0].data["source_domain"] == "m.example.test"
    assert composer.profiles == [profile]


def test_cross_profile_final_url_stops_before_parser_composition() -> None:
    first = SourceProfile(source="first_news", domains=("first.example.test",))
    second = SourceProfile(source="second_news", domains=("second.example.test",))
    requested_url = "https://first.example.test/article"
    document = _document(
        requested_url=requested_url,
        final_url="https://second.example.test/article",
        canonical_url="https://second.example.test/article",
    )
    fetcher = FakeHtmlFetcher((document,))
    composer = RecordingParserComposer()

    with pytest.raises(SourceBoundaryError):
        _service(SourceRegistry((first, second)), fetcher, composer).crawl(
            requested_url
        )

    assert fetcher.calls == [(requested_url, None)]
    assert composer.profiles == []
    assert composer.parsers == []


def test_disabled_kompas_stops_before_acquisition_or_composition() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    fetcher = FakeHtmlFetcher((_document(),))
    composer = RecordingParserComposer()
    url = "https://www.kompas.com/invented/article"

    with pytest.raises(UnsupportedSourceError):
        _service(registry, fetcher, composer).crawl(url)

    assert registry.get_by_url(url, include_disabled=True) is KOMPAS_PROFILE
    assert fetcher.calls == []
    assert composer.profiles == []


@pytest.mark.parametrize(
    "url",
    [
        "https://unknown.example.test/article",
        "http://www.cnnindonesia.com/invented/article",
    ],
)
def test_unknown_and_http_sources_stop_before_acquisition(url: str) -> None:
    fetcher = FakeHtmlFetcher((_document(),))
    composer = RecordingParserComposer()

    with pytest.raises(UnsupportedSourceError):
        _service(
            SourceRegistry(DEFAULT_SOURCE_PROFILES),
            fetcher,
            composer,
        ).crawl(url)

    assert fetcher.calls == []
    assert composer.profiles == []


def test_parser_failure_propagates_and_subsequent_crawl_succeeds() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    snapshot = registry.profiles
    fetcher = FakeHtmlFetcher(
        (
            _document(headline=""),
            _document(headline="Recovered synthetic headline"),
        )
    )
    composer = RecordingParserComposer()
    service = _service(registry, fetcher, composer)

    with pytest.raises(ArticleParserError, match="headline") as caught:
        service.crawl(_CNN_REQUESTED_URL)

    assert type(caught.value) is ArticleParserError
    recovered = service.crawl(_CNN_REQUESTED_URL)
    assert recovered[0].data["headline"] == "Recovered synthetic headline"
    assert registry.profiles is snapshot


def test_foreign_canonical_is_parser_error_not_source_boundary_error() -> None:
    document = _document(
        final_url=_CNN_CANONICAL_URL,
        canonical_url="https://foreign.example.test/article",
    )
    composer = RecordingParserComposer()

    with pytest.raises(ArticleParserError, match="canonical URL") as caught:
        _service(
            SourceRegistry(DEFAULT_SOURCE_PROFILES),
            FakeHtmlFetcher((document,)),
            composer,
        ).crawl(_CNN_REQUESTED_URL)

    assert not isinstance(caught.value, SourceBoundaryError)
    assert composer.profiles == [CNN_INDONESIA_PROFILE]
    assert isinstance(composer.parsers[0], JsonLdArticleParser)


def test_metadata_reaches_acquisition_without_governance_or_output_effects() -> None:
    metadata: dict[str, object] = {
        "source": "kompas",
        "parser_family": "unapproved",
        "trace": "synthetic",
    }
    before = dict(metadata)
    fetcher = FakeHtmlFetcher((_document(),))
    composer = RecordingParserComposer()

    result = _service(
        SourceRegistry(DEFAULT_SOURCE_PROFILES),
        fetcher,
        composer,
    ).crawl(_CNN_REQUESTED_URL, metadata=metadata)

    assert fetcher.calls[0][1] is metadata
    assert metadata == before
    assert composer.profiles == [CNN_INDONESIA_PROFILE]
    assert result[0].data["source"] == "cnn_indonesia"


def test_repeated_calls_are_deterministic_and_use_fresh_real_parsers() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    profile_snapshot = registry.profiles
    profile_values = tuple(profile.to_dict() for profile in registry.profiles)
    document = _document()
    fetcher = FakeHtmlFetcher((document, document))
    composer = RecordingParserComposer()
    service = _service(registry, fetcher, composer)

    first = service.crawl(_CNN_REQUESTED_URL)
    second = service.crawl(_CNN_REQUESTED_URL)

    assert first == second
    assert composer.parsers[0] is not composer.parsers[1]
    assert all(isinstance(parser, JsonLdArticleParser) for parser in composer.parsers)
    assert registry.profiles is profile_snapshot
    assert tuple(profile.to_dict() for profile in registry.profiles) == profile_values
    assert DEFAULT_SOURCE_PROFILES == (CNN_INDONESIA_PROFILE, KOMPAS_PROFILE)


def test_fake_acquisition_has_no_network_or_robots_runtime() -> None:
    fetcher = FakeHtmlFetcher((_document(),))

    assert not hasattr(fetcher, "http_client")
    assert not hasattr(fetcher, "robots_policy")
    assert not hasattr(fetcher, "identity")
