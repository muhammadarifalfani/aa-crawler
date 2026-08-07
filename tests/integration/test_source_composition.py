"""End-to-end tests for explicit source-to-item composition."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from aa_crawler.composition import ParserComposer, ParserCompositionError
from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument, HtmlFetcher
from aa_crawler.http import HttpClient
from aa_crawler.parser import ArticleParserError, JsonLdArticleParser
from aa_crawler.robots import RobotsPolicy
from aa_crawler.sources import (
    CNN_INDONESIA_PROFILE,
    DEFAULT_SOURCE_PROFILES,
    KOMPAS_PROFILE,
    SourceProfile,
    SourceRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_CNN_REQUESTED_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "synthetic-story?campaign=synthetic"
)
_CNN_CANONICAL_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/synthetic-story"
)
_PUBLISHED = "2099-01-01T08:30:00+07:00"
_MODIFIED = "2099-01-01T09:15:00+07:00"


def _synthetic_html(
    canonical_url: str,
    *,
    headline: str = "Invented integration headline",
) -> str:
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical_url},
        "headline": headline,
        "description": "Invented integration description.",
        "author": {"name": "Synthetic Author"},
        "datePublished": _PUBLISHED,
        "dateModified": _MODIFIED,
        "image": {"url": "https://images.example/synthetic.jpg"},
        "publisher": {"name": "Untrusted Synthetic Publisher"},
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
    requested_url: str,
    canonical_url: str,
    *,
    headline: str = "Invented integration headline",
) -> HtmlDocument:
    return HtmlDocument(
        requested_url=requested_url,
        final_url=canonical_url,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=_synthetic_html(canonical_url, headline=headline),
        encoding="utf-8",
    )


def _resolve_compose_parse(
    registry: SourceRegistry,
    url: str,
    document: HtmlDocument,
) -> tuple[SourceProfile, JsonLdArticleParser, CrawlerItem]:
    profile = registry.get_by_url(url)
    assert profile is not None
    parser = ParserComposer().create(profile)
    assert isinstance(parser, JsonLdArticleParser)
    items = list(parser.parse(document))
    assert len(items) == 1
    return profile, parser, items[0]


def test_cnn_golden_path_resolves_composes_and_serializes() -> None:
    defaults_before = DEFAULT_SOURCE_PROFILES
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    document = _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL)

    profile, parser, item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        document,
    )

    assert profile is CNN_INDONESIA_PROFILE
    assert parser.source == CNN_INDONESIA_PROFILE.source
    assert parser.source_domains == frozenset(CNN_INDONESIA_PROFILE.domains)
    assert isinstance(item, CrawlerItem)
    assert item.data == {
        "source": "cnn_indonesia",
        "source_domain": "www.cnnindonesia.com",
        "requested_url": _CNN_REQUESTED_URL,
        "canonical_url": _CNN_CANONICAL_URL,
        "headline": "Invented integration headline",
        "published_at": "2099-01-01T01:30:00+00:00",
        "description": "Invented integration description.",
        "author_names": ("Synthetic Author",),
        "modified_at": "2099-01-01T02:15:00+00:00",
        "section": "Synthetic Section",
        "lead_image_url": "https://images.example/synthetic.jpg",
        "language": "id-ID",
    }
    assert item.data["source"] != "Untrusted Synthetic Publisher"
    assert DEFAULT_SOURCE_PROFILES is defaults_before
    assert DEFAULT_SOURCE_PROFILES == (CNN_INDONESIA_PROFILE, KOMPAS_PROFILE)


def test_requested_query_and_canonical_identity_remain_distinct() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    document = _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL)

    profile, _, item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        document,
    )

    assert profile is CNN_INDONESIA_PROFILE
    assert item.data["requested_url"] == _CNN_REQUESTED_URL
    assert item.data["canonical_url"] == _CNN_CANONICAL_URL
    assert "?" in str(item.data["requested_url"])
    assert "?" not in str(item.data["canonical_url"])


@pytest.mark.parametrize(
    "url",
    [
        "https://unknown.example/synthetic",
        "https://regional.cnnindonesia.com/synthetic",
        "http://www.cnnindonesia.com/synthetic",
        "not-an-absolute-url",
    ],
)
def test_unknown_or_unsafe_urls_stop_before_composition(url: str) -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)

    assert registry.get_by_url(url) is None


def test_disabled_kompas_stays_blocked_through_composition() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    url = "https://www.kompas.com/synthetic/article"

    assert registry.get_by_url(url) is None
    profile = registry.get_by_url(url, include_disabled=True)
    assert profile is KOMPAS_PROFILE
    with pytest.raises(ParserCompositionError, match="disabled"):
        ParserComposer().create(profile)


def test_all_explicit_kompas_hosts_share_disabled_profile_without_wildcards() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)

    for hostname in KOMPAS_PROFILE.domains:
        assert registry.get_by_host(hostname, include_disabled=True) is KOMPAS_PROFILE
    assert registry.get_by_host("regional.kompas.com", include_disabled=True) is None
    assert registry.get_by_host("kompas.com", include_disabled=True) is None


def test_synthetic_source_uses_identical_generic_flow() -> None:
    profile = SourceProfile(
        source="synthetic_news",
        domains=("news.example",),
        parser_family="jsonld_article",
    )
    registry = SourceRegistry((profile,))
    requested_url = "https://news.example/synthetic?input=one"
    canonical_url = "https://news.example/synthetic"

    resolved, parser, item = _resolve_compose_parse(
        registry,
        requested_url,
        _document(requested_url, canonical_url),
    )

    assert resolved is profile
    assert parser.source == "synthetic_news"
    assert item.data["source"] == "synthetic_news"
    assert item.data["source_domain"] == "news.example"


def test_parser_failure_propagates_without_mutating_registry() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    profile = registry.get_by_url(_CNN_REQUESTED_URL)
    assert profile is CNN_INDONESIA_PROFILE
    parser = ParserComposer().create(profile)
    malformed = _document(
        _CNN_REQUESTED_URL,
        _CNN_CANONICAL_URL,
        headline="",
    )

    with pytest.raises(ArticleParserError, match="headline"):
        list(parser.parse(malformed))

    assert registry.get_by_url(_CNN_REQUESTED_URL) is CNN_INDONESIA_PROFILE
    _, _, valid_item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL),
    )
    assert valid_item.data["headline"] == "Invented integration headline"


def test_repeated_composition_is_deterministic_and_stateless() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    composer = ParserComposer()
    profile = registry.get_by_url(_CNN_REQUESTED_URL)
    assert profile is CNN_INDONESIA_PROFILE
    document = _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL)

    first_parser = composer.create(profile)
    second_parser = composer.create(profile)
    first = list(first_parser.parse(document))
    second = list(second_parser.parse(document))

    assert first_parser is not second_parser
    assert first == second
    assert first[0] is not second[0]
    assert registry.profiles == DEFAULT_SOURCE_PROFILES


def test_composition_does_not_instantiate_acquisition_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instantiated: list[str] = []

    def forbidden(name: str) -> Callable[..., None]:
        def record(*args: object, **kwargs: object) -> None:
            del args, kwargs
            instantiated.append(name)
            raise AssertionError(f"{name} must not be instantiated")

        return record

    monkeypatch.setattr(HttpClient, "__init__", forbidden("HttpClient"))
    monkeypatch.setattr(RobotsPolicy, "__init__", forbidden("RobotsPolicy"))
    monkeypatch.setattr(HtmlFetcher, "__init__", forbidden("HtmlFetcher"))

    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    _, _, item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL),
    )

    assert item.data["source"] == "cnn_indonesia"
    assert instantiated == []


def test_output_mapping_remains_read_only() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    _, _, item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL),
    )

    with pytest.raises(TypeError):
        item.data["source"] = "changed"  # type: ignore[index]


def test_golden_output_keys_follow_article_serialization_order() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    _, _, item = _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL),
    )

    expected_order: tuple[str, ...] = (
        "source",
        "source_domain",
        "requested_url",
        "canonical_url",
        "headline",
        "published_at",
        "description",
        "author_names",
        "modified_at",
        "section",
        "lead_image_url",
        "language",
    )
    assert tuple(item.data) == expected_order


def test_registry_profile_snapshot_is_unchanged_after_composition() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)
    snapshot: tuple[Mapping[str, object], ...] = tuple(
        profile.to_dict() for profile in registry.profiles
    )

    _resolve_compose_parse(
        registry,
        _CNN_REQUESTED_URL,
        _document(_CNN_REQUESTED_URL, _CNN_CANONICAL_URL),
    )

    assert tuple(profile.to_dict() for profile in registry.profiles) == snapshot
