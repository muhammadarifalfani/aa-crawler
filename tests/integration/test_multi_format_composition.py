"""End-to-end multi-parser-family integration tests (ADR-025/ADR-026).

These tests exercise the real `SourceRegistry` -> `ParserComposer` -> parser
-> `ArticleItem` -> `CrawlerItem` flow for all three shipped parser families
side by side, prove the persistence boundary (ADR-024) can durably store a
result produced by any of them without knowing which family produced it, and
confirm the existing production `jsonld_article` flow (CNN Indonesia) is
completely unaffected by the two families added in Sprint 8/9. No test
contacts a real network; `HttpClient`, `RobotsPolicy`, and `HtmlFetcher` are
never instantiated.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from aa_crawler.composition import ParserComposer
from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument, HtmlFetcher
from aa_crawler.http import HttpClient
from aa_crawler.parser import (
    ArticleParserError,
    GenericJsonArticleParser,
    JsonLdArticleParser,
    MicrodataArticleParser,
)
from aa_crawler.persistence import FileCrawlResultSink
from aa_crawler.robots import RobotsPolicy
from aa_crawler.sources import (
    CNN_INDONESIA_PROFILE,
    DEFAULT_SOURCE_PROFILES,
    SourceProfile,
    SourceRegistry,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_CNN_REQUESTED_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "synthetic-story?campaign=synthetic"
)
_CNN_CANONICAL_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/synthetic-story"
)
_PUBLISHED = "2099-01-01T08:30:00+07:00"


def _cnn_document() -> HtmlDocument:
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CNN_CANONICAL_URL},
        "headline": "Invented integration headline",
        "datePublished": _PUBLISHED,
    }
    content = (
        '<html lang="id-ID"><head>'
        f'<link rel="canonical" href="{_CNN_CANONICAL_URL}">'
        '<script type="application/ld+json">'
        f"{json.dumps(node)}"
        "</script></head><body></body></html>"
    )
    return HtmlDocument(
        requested_url=_CNN_REQUESTED_URL,
        final_url=_CNN_CANONICAL_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=content,
        encoding="utf-8",
    )


def _generic_json_document(
    url: str, *, headline: str = "Generic headline"
) -> HtmlDocument:
    payload = {"url": url, "headline": headline, "published_at": _PUBLISHED}
    return HtmlDocument(
        requested_url=url,
        final_url=url,
        status_code=200,
        headers={"Content-Type": "application/json"},
        content=json.dumps(payload),
        encoding="utf-8",
    )


def _microdata_document(
    url: str, *, headline: str = "Microdata headline"
) -> HtmlDocument:
    content = (
        "<html><head>"
        f'<link rel="canonical" href="{url}">'
        "</head><body>"
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        f'<link itemprop="mainEntityOfPage" href="{url}">'
        f'<h1 itemprop="headline">{headline}</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div></body></html>"
    )
    return HtmlDocument(
        requested_url=url,
        final_url=url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=content,
        encoding="utf-8",
    )


def test_microdata_source_resolves_composes_and_parses_end_to_end() -> None:
    url = "https://news.example/articles/one"
    profile = SourceProfile(
        source="microdata_news",
        domains=("news.example",),
        parser_family="microdata_article",
    )
    registry = SourceRegistry((profile,))

    resolved = registry.get_by_url(url)
    assert resolved is profile

    parser = ParserComposer().create(resolved)
    assert isinstance(parser, MicrodataArticleParser)

    items = list(parser.parse(_microdata_document(url)))
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, CrawlerItem)
    assert item.data == {
        "source": "microdata_news",
        "source_domain": "news.example",
        "requested_url": url,
        "canonical_url": url,
        "headline": "Microdata headline",
        "published_at": "2099-01-01T01:30:00+00:00",
        "description": None,
        "author_names": (),
        "modified_at": None,
        "section": None,
        "lead_image_url": None,
        "language": None,
    }


def test_all_three_parser_families_coexist_in_one_registry() -> None:
    jsonld_url = "https://jsonld.example/articles/one"
    generic_url = "https://generic.example/articles/one"
    microdata_url = "https://microdata.example/articles/one"
    profiles = (
        SourceProfile(source="jsonld_source", domains=("jsonld.example",)),
        SourceProfile(
            source="generic_source",
            domains=("generic.example",),
            parser_family="generic_json_article",
        ),
        SourceProfile(
            source="microdata_source",
            domains=("microdata.example",),
            parser_family="microdata_article",
        ),
    )
    registry = SourceRegistry(profiles)
    composer = ParserComposer()

    jsonld_node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": jsonld_url},
        "headline": "JSON-LD headline",
        "datePublished": _PUBLISHED,
    }
    jsonld_document = HtmlDocument(
        requested_url=jsonld_url,
        final_url=jsonld_url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=(
            "<html><head>"
            f'<link rel="canonical" href="{jsonld_url}">'
            '<script type="application/ld+json">'
            f"{json.dumps(jsonld_node)}</script></head><body></body></html>"
        ),
        encoding="utf-8",
    )

    results: dict[str, CrawlerItem] = {}
    parsers: dict[str, object] = {}
    for url, document in (
        (jsonld_url, jsonld_document),
        (generic_url, _generic_json_document(generic_url)),
        (microdata_url, _microdata_document(microdata_url)),
    ):
        profile = registry.get_by_url(url)
        assert profile is not None
        parser = composer.create(profile)
        items = list(parser.parse(document))
        assert len(items) == 1
        results[profile.source] = items[0]
        parsers[profile.source] = parser

    assert isinstance(parsers["jsonld_source"], JsonLdArticleParser)
    assert isinstance(parsers["generic_source"], GenericJsonArticleParser)
    assert isinstance(parsers["microdata_source"], MicrodataArticleParser)
    assert results["jsonld_source"].data["headline"] == "JSON-LD headline"
    assert results["generic_source"].data["headline"] == "Generic headline"
    assert results["microdata_source"].data["headline"] == "Microdata headline"
    assert registry.profiles == profiles


def test_existing_production_jsonld_flow_is_unaffected_by_new_families() -> None:
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)

    profile = registry.get_by_url(_CNN_REQUESTED_URL)
    assert profile is CNN_INDONESIA_PROFILE

    parser = ParserComposer().create(profile)
    assert isinstance(parser, JsonLdArticleParser)

    items = list(parser.parse(_cnn_document()))
    assert len(items) == 1
    assert items[0].data["source"] == "cnn_indonesia"
    assert items[0].data["headline"] == "Invented integration headline"
    assert registry.profiles == DEFAULT_SOURCE_PROFILES


@pytest.mark.parametrize(
    "parser_family",
    ["jsonld_article", "generic_json_article", "microdata_article"],
)
def test_persistence_stores_any_family_result_without_knowing_which_one(
    parser_family: str,
    tmp_path: Path,
) -> None:
    url = "https://news.example/articles/one"
    documents: dict[str, HtmlDocument] = {
        "jsonld_article": HtmlDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=(
                "<html><head>"
                f'<link rel="canonical" href="{url}">'
                '<script type="application/ld+json">'
                + json.dumps(
                    {
                        "@type": "NewsArticle",
                        "mainEntityOfPage": {"@id": url},
                        "headline": "Persisted headline",
                        "datePublished": _PUBLISHED,
                    }
                )
                + "</script></head><body></body></html>"
            ),
            encoding="utf-8",
        ),
        "generic_json_article": _generic_json_document(
            url, headline="Persisted headline"
        ),
        "microdata_article": _microdata_document(url, headline="Persisted headline"),
    }
    profile = SourceProfile(
        source="persistable_news",
        domains=("news.example",),
        parser_family=parser_family,
    )
    registry = SourceRegistry((profile,))
    resolved = registry.get_by_url(url)
    assert resolved is not None
    parser = ParserComposer().create(resolved)
    items = list(parser.parse(documents[parser_family]))
    assert len(items) == 1

    destination = tmp_path / "results.jsonl"
    FileCrawlResultSink(destination=destination).save(items[0])

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    # Compare through the same JSON round trip the sink itself performs,
    # since CrawlerItem.data stores author_names as a tuple, not a list.
    assert json.loads(lines[0]) == json.loads(json.dumps(dict(items[0].data)))
    assert json.loads(lines[0])["headline"] == "Persisted headline"


def test_microdata_parser_failure_is_deterministic_and_does_not_mutate_registry() -> (
    None
):
    url = "https://news.example/articles/one"
    profile = SourceProfile(
        source="microdata_news",
        domains=("news.example",),
        parser_family="microdata_article",
    )
    registry = SourceRegistry((profile,))
    resolved = registry.get_by_url(url)
    assert resolved is not None
    parser = ParserComposer().create(resolved)
    malformed = _microdata_document(url, headline="")

    with pytest.raises(ArticleParserError, match="headline"):
        list(parser.parse(malformed))

    assert registry.get_by_url(url) is profile
    valid_items = list(parser.parse(_microdata_document(url)))
    assert len(valid_items) == 1
    assert valid_items[0].data["headline"] == "Microdata headline"


def test_multi_format_composition_does_not_instantiate_acquisition_components(
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

    url = "https://news.example/articles/one"
    profile = SourceProfile(
        source="microdata_news",
        domains=("news.example",),
        parser_family="microdata_article",
    )
    registry = SourceRegistry((profile,))
    resolved = registry.get_by_url(url)
    assert resolved is not None
    parser = ParserComposer().create(resolved)
    items = list(parser.parse(_microdata_document(url)))

    assert items[0].data["source"] == "microdata_news"
    assert instantiated == []
