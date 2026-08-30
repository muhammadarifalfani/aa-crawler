"""Synthetic tests for the second, non-JSON-LD parser family (ADR-025)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import ArticleParserError, BaseParser, GenericJsonArticleParser

_CANONICAL = "https://news.example/articles/one"
_REQUESTED = "https://news.example/redirect?id=one"
_PUBLISHED = "2026-08-06T12:30:00+07:00"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "url": _CANONICAL,
        "headline": "Synthetic headline",
        "published_at": _PUBLISHED,
    }
    payload.update(overrides)
    return payload


def _document(
    payload: dict[str, object] | str, *, requested: str = _REQUESTED
) -> HtmlDocument:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return HtmlDocument(
        requested_url=requested,
        final_url=requested,
        status_code=200,
        headers={"Content-Type": "application/json"},
        content=content,
        encoding="utf-8",
    )


def _parser(**overrides: object) -> GenericJsonArticleParser:
    values: dict[str, object] = {
        "source": "example_news",
        "source_domains": ["news.example"],
    }
    values.update(overrides)
    return GenericJsonArticleParser(**values)  # type: ignore[arg-type]


def _parse(payload: dict[str, object], **parser_overrides: object) -> CrawlerItem:
    items = list(_parser(**parser_overrides).parse(_document(payload)))
    assert len(items) == 1
    return items[0]


def test_parser_construction_retains_normalized_source_boundary() -> None:
    parser = GenericJsonArticleParser(
        source="  example_news  ",
        source_domains=["NEWS.EXAMPLE.", "regional.news.example"],
    )

    assert parser.source == "example_news"
    assert parser.source_domains == frozenset({"news.example", "regional.news.example"})


@pytest.mark.parametrize(
    ("source", "domains"),
    [
        ("Invalid Source", ["news.example"]),
        ("example_news", []),
        ("example_news", ["localhost"]),
    ],
)
def test_parser_rejects_invalid_constructor_context(
    source: str,
    domains: list[str],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        GenericJsonArticleParser(source=source, source_domains=domains)


def test_parser_integrates_with_lazy_base_parser_lifecycle() -> None:
    parser = _parser()

    result = parser.parse(_document(_payload()))

    assert isinstance(parser, BaseParser)
    assert isinstance(result, Iterator)
    assert next(result).data["headline"] == "Synthetic headline"


def test_repeated_calls_are_independent_and_deterministic() -> None:
    parser = _parser()
    document = _document(_payload())

    first = list(parser.parse(document))
    second = list(parser.parse(document))

    assert first == second
    assert first[0] is not second[0]


def test_output_is_deterministic_crawler_item_data() -> None:
    item = _parse(
        _payload(
            description="A synthetic description.",
            authors=["Jane Doe", "John Roe"],
            modified_at="2026-08-06T13:00:00+07:00",
            section="World",
            lead_image_url="https://news.example/image.jpg",
            language="id-ID",
        )
    )

    assert isinstance(item, CrawlerItem)
    assert item.data == {
        "source": "example_news",
        "source_domain": "news.example",
        "requested_url": _REQUESTED,
        "canonical_url": _CANONICAL,
        "headline": "Synthetic headline",
        "published_at": "2026-08-06T05:30:00+00:00",
        "description": "A synthetic description.",
        "author_names": ("Jane Doe", "John Roe"),
        "modified_at": "2026-08-06T06:00:00+00:00",
        "section": "World",
        "lead_image_url": "https://news.example/image.jpg",
        "language": "id-ID",
    }


def test_deferred_fields_default_to_none_or_empty_when_absent() -> None:
    item = _parse(_payload())

    assert item.data["description"] is None
    assert item.data["author_names"] == ()
    assert item.data["modified_at"] is None
    assert item.data["section"] is None
    assert item.data["lead_image_url"] is None
    assert item.data["language"] is None


def test_malformed_json_payload_fails_without_exposing_content() -> None:
    parser = _parser()

    with pytest.raises(ArticleParserError, match="JSON payload is invalid"):
        list(parser.parse(_document("{not valid json")))


@pytest.mark.parametrize("payload", [["not", "an", "object"], "a string", 42, None])
def test_non_object_json_payload_fails(payload: object) -> None:
    parser = _parser()

    with pytest.raises(ArticleParserError, match="must be an object"):
        list(parser.parse(_document(json.dumps(payload))))


@pytest.mark.parametrize(
    "url",
    [
        "http://news.example/articles/one",
        "https://foreign.example/articles/one",
        "https://news.example/articles/one#fragment",
        "https://user:pass@news.example/articles/one",
        None,
        123,
    ],
)
def test_invalid_or_foreign_canonical_url_is_rejected(url: object) -> None:
    with pytest.raises(ArticleParserError, match="canonical URL"):
        _parse(_payload(url=url))


@pytest.mark.parametrize("headline", [None, "", "   ", 123])
def test_missing_or_empty_headline_fails(headline: object) -> None:
    with pytest.raises(ArticleParserError, match="headline"):
        _parse(_payload(headline=headline))


@pytest.mark.parametrize(
    "published_at",
    [None, "", "not-a-datetime", "2026-08-06T12:30:00"],
)
def test_missing_malformed_or_naive_publication_time_fails(
    published_at: object,
) -> None:
    with pytest.raises(ArticleParserError, match="publication time"):
        _parse(_payload(published_at=published_at))


def test_utc_and_z_suffixed_publication_times_are_accepted() -> None:
    item = _parse(_payload(published_at="2026-08-06T05:30:00Z"))

    assert item.data["published_at"] == "2026-08-06T05:30:00+00:00"


def test_modified_time_is_preserved_even_before_publication() -> None:
    item = _parse(
        _payload(
            published_at="2026-08-06T12:30:00+07:00",
            modified_at="2020-01-01T00:00:00+00:00",
        )
    )

    assert item.data["modified_at"] == "2020-01-01T00:00:00+00:00"


def test_malformed_modified_time_is_omitted() -> None:
    item = _parse(_payload(modified_at="not-a-datetime"))

    assert item.data["modified_at"] is None


@pytest.mark.parametrize(
    ("authors", "expected"),
    [
        (["Jane Doe", "", "  ", 123, None], ("Jane Doe",)),
        ("not-a-list", ()),
        (None, ()),
        ([], ()),
    ],
)
def test_author_shapes_are_normalized(
    authors: object, expected: tuple[str, ...]
) -> None:
    item = _parse(_payload(authors=authors))

    assert item.data["author_names"] == expected


@pytest.mark.parametrize(
    "lead_image_url",
    [
        "http://news.example/image.jpg",
        "https://user:pass@news.example/image.jpg",
        "not-a-url-at-all",
        123,
    ],
)
def test_invalid_lead_image_url_is_omitted_rather_than_fatal(
    lead_image_url: object,
) -> None:
    item = _parse(_payload(lead_image_url=lead_image_url))

    assert item.data["lead_image_url"] is None


def test_lead_image_url_is_not_restricted_to_source_domains() -> None:
    item = _parse(_payload(lead_image_url="https://cdn.other.example/image.jpg"))

    assert item.data["lead_image_url"] == "https://cdn.other.example/image.jpg"


@pytest.mark.parametrize("language", ["not a language", "toolongxx", 123, ""])
def test_malformed_language_is_omitted(language: object) -> None:
    item = _parse(_payload(language=language))

    assert item.data["language"] is None


def test_section_is_passed_through_when_present() -> None:
    item = _parse(_payload(section="World"))

    assert item.data["section"] == "World"


def test_requested_and_canonical_urls_remain_distinct() -> None:
    item = _parse(_payload())

    assert item.data["requested_url"] == _REQUESTED
    assert item.data["canonical_url"] == _CANONICAL
    assert item.data["requested_url"] != item.data["canonical_url"]


def test_parser_does_not_retain_document_or_leak_state() -> None:
    parser = _parser()

    list(parser.parse(_document(_payload())))

    assert not hasattr(parser, "document")
    assert not hasattr(parser, "_document")
