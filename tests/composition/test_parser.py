"""Tests for deterministic source-to-parser composition."""

import json
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aa_crawler.composition import ParserComposer, ParserCompositionError
from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import (
    ArticleParserError,
    BaseParser,
    GenericJsonArticleParser,
    JsonLdArticleParser,
)
from aa_crawler.sources import SourceProfile


def _profile(**overrides: object) -> SourceProfile:
    values: dict[str, object] = {
        "source": "example_news",
        "domains": ("news.example",),
    }
    values.update(overrides)
    return SourceProfile(**values)  # type: ignore[arg-type]


def _document(*, headline: str = "Synthetic headline") -> HtmlDocument:
    canonical_url = "https://regional.news.example/articles/one"
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical_url},
        "headline": headline,
        "datePublished": "2026-08-07T12:30:00+07:00",
    }
    content = (
        '<html lang="id-ID"><head>'
        f'<link rel="canonical" href="{canonical_url}">'
        '<script type="application/ld+json">'
        f"{json.dumps(node)}"
        "</script></head><body></body></html>"
    )
    return HtmlDocument(
        requested_url="https://news.example/redirect?id=one",
        final_url=canonical_url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=content,
        encoding="utf-8",
    )


def _json_document(*, headline: str = "Synthetic headline") -> HtmlDocument:
    payload = {
        "url": "https://news.example/articles/one",
        "headline": headline,
        "published_at": "2026-08-07T12:30:00+07:00",
    }
    return HtmlDocument(
        requested_url="https://news.example/articles/one",
        final_url="https://news.example/articles/one",
        status_code=200,
        headers={"Content-Type": "application/json"},
        content=json.dumps(payload),
        encoding="utf-8",
    )


def test_composer_is_stateless_immutable_and_has_minimal_public_api() -> None:
    composer = ParserComposer()

    assert not hasattr(composer, "registry")
    assert not hasattr(composer, "register_parser")
    with pytest.raises((FrozenInstanceError, TypeError)):
        composer.registry = object()  # type: ignore[attr-defined]

    import aa_crawler.composition as composition

    assert composition.__all__ == ["ParserComposer", "ParserCompositionError"]
    assert composition.ParserComposer is ParserComposer
    assert composition.ParserCompositionError is ParserCompositionError


def test_jsonld_profile_creates_base_parser_with_exact_context() -> None:
    profile = _profile(domains=("news.example", "regional.news.example"))

    parser = ParserComposer().create(profile)

    assert isinstance(parser, JsonLdArticleParser)
    assert isinstance(parser, BaseParser)
    assert parser.source == "example_news"
    assert parser.source_domains == frozenset({"news.example", "regional.news.example"})
    assert profile.domains == ("news.example", "regional.news.example")


def test_generic_json_article_profile_creates_base_parser_with_exact_context() -> None:
    profile = _profile(parser_family="generic_json_article")

    parser = ParserComposer().create(profile)

    assert isinstance(parser, GenericJsonArticleParser)
    assert isinstance(parser, BaseParser)
    assert parser.source == "example_news"
    assert parser.source_domains == frozenset({"news.example"})


def test_composed_generic_json_article_parser_executes_synthetic_flow() -> None:
    profile = _profile(parser_family="generic_json_article")
    composer = ParserComposer()
    document = _json_document()

    parser = composer.create(profile)
    items = list(parser.parse(document))

    assert len(items) == 1
    assert isinstance(items[0], CrawlerItem)
    assert items[0].data["source"] == "example_news"
    assert items[0].data["headline"] == "Synthetic headline"
    assert items[0].data["canonical_url"] == "https://news.example/articles/one"


def test_jsonld_and_generic_json_article_families_do_not_interfere() -> None:
    composer = ParserComposer()
    jsonld_profile = _profile(domains=("news.example", "regional.news.example"))
    generic_profile = _profile(parser_family="generic_json_article")

    jsonld_parser = composer.create(jsonld_profile)
    generic_parser = composer.create(generic_profile)

    assert isinstance(jsonld_parser, JsonLdArticleParser)
    assert isinstance(generic_parser, GenericJsonArticleParser)
    assert list(jsonld_parser.parse(_document())) != []
    assert list(generic_parser.parse(_json_document())) != []


def test_create_returns_a_new_parser_each_time() -> None:
    composer = ParserComposer()
    profile = _profile()

    first = composer.create(profile)
    second = composer.create(profile)

    assert first is not second
    assert type(first) is type(second) is JsonLdArticleParser


def test_adapter_key_is_rejected_without_loading_or_fallback() -> None:
    profile = _profile(adapter_key="special_author_shape")

    with pytest.raises(ParserCompositionError, match="adapters are not supported"):
        ParserComposer().create(profile)


def test_disabled_profile_is_rejected_without_mutation() -> None:
    profile = _profile(enabled=False)

    with pytest.raises(ParserCompositionError, match="disabled"):
        ParserComposer().create(profile)

    assert profile.enabled is False


def test_defensive_unknown_family_fails_safely() -> None:
    profile = object.__new__(SourceProfile)
    object.__setattr__(profile, "source", "example_news")
    object.__setattr__(profile, "domains", ("news.example",))
    object.__setattr__(profile, "parser_family", "unsupported_family")
    object.__setattr__(profile, "adapter_key", None)
    object.__setattr__(profile, "enabled", True)

    with pytest.raises(ParserCompositionError, match="unsupported parser family"):
        ParserComposer().create(profile)


def test_invalid_composition_input_fails_safely() -> None:
    with pytest.raises(ParserCompositionError, match="valid source profile"):
        ParserComposer().create(object())  # type: ignore[arg-type]


def test_composed_parser_executes_synthetic_article_flow() -> None:
    profile = _profile(domains=("news.example", "regional.news.example"))
    composer = ParserComposer()
    document = _document()

    parser = composer.create(profile)
    items = list(parser.parse(document))

    assert len(items) == 1
    assert isinstance(items[0], CrawlerItem)
    assert items[0].data == {
        "source": "example_news",
        "source_domain": "regional.news.example",
        "requested_url": "https://news.example/redirect?id=one",
        "canonical_url": "https://regional.news.example/articles/one",
        "headline": "Synthetic headline",
        "published_at": "2026-08-07T05:30:00+00:00",
        "description": None,
        "author_names": (),
        "modified_at": None,
        "section": None,
        "lead_image_url": None,
        "language": "id-ID",
    }
    assert not hasattr(composer, "document")


def test_parser_execution_errors_are_not_wrapped_by_composer() -> None:
    parser = ParserComposer().create(
        _profile(domains=("news.example", "regional.news.example"))
    )
    document = _document(headline="")

    with pytest.raises(ArticleParserError, match="headline"):
        list(parser.parse(document))


def test_composition_scales_without_source_specific_classes_or_state() -> None:
    profiles = tuple(
        SourceProfile(
            source=f"source_{index}",
            domains=(f"news-{index}.example",),
        )
        for index in range(1000)
    )
    composer = ParserComposer()

    parsers = [composer.create(profiles[index]) for index in (0, 499, 999)]

    assert all(type(parser) is JsonLdArticleParser for parser in parsers)
    assert [cast("JsonLdArticleParser", parser).source for parser in parsers] == [
        "source_0",
        "source_499",
        "source_999",
    ]
    assert not hasattr(composer, "adapters")
    assert not hasattr(composer, "profiles")
