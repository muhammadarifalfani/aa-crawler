"""Synthetic tests for the source-agnostic JSON-LD article parser."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import ArticleParserError, BaseParser, JsonLdArticleParser

_CANONICAL = "https://news.example/articles/one"
_REQUESTED = "https://news.example/redirect?id=one"
_PUBLISHED = "2026-08-06T12:30:00+07:00"


def _node(**overrides: object) -> dict[str, object]:
    node: dict[str, object] = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CANONICAL},
        "headline": "Synthetic headline",
        "datePublished": _PUBLISHED,
    }
    node.update(overrides)
    return node


def _html(
    *blocks: object,
    canonical: str | None = _CANONICAL,
    open_graph: dict[str, str] | None = None,
    article_meta: dict[str, str] | None = None,
    description: str | None = None,
    language: str | None = "id-ID",
) -> str:
    parts = ["<html"]
    if language is not None:
        parts.append(f' lang="{language}"')
    parts.append("><head>")
    if canonical is not None:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    for key, value in (open_graph or {}).items():
        parts.append(f'<meta property="{key}" content="{value}">')
    for key, value in (article_meta or {}).items():
        parts.append(f'<meta property="{key}" content="{value}">')
    if description is not None:
        parts.append(f'<meta name="description" content="{description}">')
    for block in blocks:
        payload = block if isinstance(block, str) else json.dumps(block)
        parts.append(f'<script type="application/ld+json">{payload}</script>')
    parts.append("</head><body><p>Unrelated synthetic body.</p></body></html>")
    return "".join(parts)


def _document(
    content: str, *, metadata: dict[str, object] | None = None
) -> HtmlDocument:
    return HtmlDocument(
        requested_url=_REQUESTED,
        final_url=_CANONICAL,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=content,
        encoding="utf-8",
        metadata={} if metadata is None else metadata,
    )


def _parser(*domains: str) -> JsonLdArticleParser:
    return JsonLdArticleParser(
        source="example_news",
        source_domains=domains or ("news.example",),
    )


def _parse(content: str, *, parser: JsonLdArticleParser | None = None) -> CrawlerItem:
    items = list((parser or _parser()).parse(_document(content)))
    assert len(items) == 1
    return items[0]


def test_parser_construction_retains_normalized_source_boundary() -> None:
    parser = JsonLdArticleParser(
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
        JsonLdArticleParser(source=source, source_domains=domains)


def test_parser_integrates_with_lazy_base_parser_lifecycle() -> None:
    parser = _parser()

    result = parser.parse(_document(_html(_node())))

    assert isinstance(parser, BaseParser)
    assert isinstance(result, Iterator)
    assert next(result).data["headline"] == "Synthetic headline"


def test_repeated_calls_are_independent_and_deterministic() -> None:
    parser = _parser()
    document = _document(_html(_node()))

    first = list(parser.parse(document))
    second = list(parser.parse(document))

    assert first == second
    assert first[0] is not second[0]


def test_output_is_deterministic_crawler_item_data() -> None:
    item = _parse(_html(_node()))

    assert isinstance(item, CrawlerItem)
    assert item.data == {
        "source": "example_news",
        "source_domain": "news.example",
        "requested_url": _REQUESTED,
        "canonical_url": _CANONICAL,
        "headline": "Synthetic headline",
        "published_at": "2026-08-06T05:30:00+00:00",
        "description": None,
        "author_names": (),
        "modified_at": None,
        "section": None,
        "lead_image_url": None,
        "language": "id-ID",
    }


@pytest.mark.parametrize(
    "block",
    [
        [_node()],
        {"@graph": [_node()]},
        {"nested": [{"deeper": [_node()]}]},
        {**_node(), "@type": ["Thing", "NewsArticle"]},
    ],
)
def test_json_ld_shapes_and_type_lists_are_supported(block: object) -> None:
    assert _parse(_html(block)).data["headline"] == "Synthetic headline"


def test_news_article_is_preferred_over_generic_article() -> None:
    generic = _node(
        **{
            "@type": "Article",
            "mainEntityOfPage": {"@id": "https://news.example/articles/generic"},
            "headline": "Generic synthetic headline",
        }
    )

    item = _parse(_html([generic, _node()]))

    assert item.data["headline"] == "Synthetic headline"


def test_generic_article_is_accepted_as_secondary_type() -> None:
    item = _parse(_html(_node(**{"@type": "Article"})))

    assert item.data["headline"] == "Synthetic headline"


def test_malformed_unrelated_block_is_ignored() -> None:
    item = _parse(_html("{malformed", _node()))

    assert item.data["canonical_url"] == _CANONICAL


def test_no_valid_candidate_fails_without_exposing_content() -> None:
    secret = "sensitive-headline-value"
    parser = _parser()

    with pytest.raises(ArticleParserError) as error_info:
        list(parser.parse(_document(_html("{malformed", {"secret": secret}))))

    assert secret not in str(error_info.value)
    assert "synthetic body" not in str(error_info.value).lower()


def test_multiple_candidates_without_identity_authority_are_ambiguous() -> None:
    first = _node(mainEntityOfPage={"@id": "https://news.example/articles/one"})
    second = _node(mainEntityOfPage={"@id": "https://news.example/articles/two"})

    with pytest.raises(ArticleParserError, match="ambiguous"):
        list(_parser().parse(_document(_html([first, second], canonical=None))))


def test_canonical_identity_selects_one_candidate() -> None:
    selected = _node()
    other = _node(
        mainEntityOfPage={"@id": "https://news.example/articles/two"},
        headline="Other synthetic headline",
    )

    item = _parse(_html([other, selected]))

    assert item.data["headline"] == "Synthetic headline"


def test_canonical_link_is_preferred_over_open_graph_url() -> None:
    item = _parse(
        _html(
            _node(),
            open_graph={"og:url": "https://news.example/articles/other"},
        )
    )

    assert item.data["canonical_url"] == _CANONICAL


def test_open_graph_url_is_canonical_fallback() -> None:
    item = _parse(
        _html(
            _node(),
            canonical=None,
            open_graph={"og:url": _CANONICAL},
        )
    )

    assert item.data["canonical_url"] == _CANONICAL


@pytest.mark.parametrize(
    "node",
    [
        _node(),
        _node(mainEntityOfPage=None, url=_CANONICAL),
    ],
)
def test_candidate_identity_is_final_canonical_fallback(node: object) -> None:
    item = _parse(_html(node, canonical=None))

    assert item.data["canonical_url"] == _CANONICAL


def test_requested_and_canonical_urls_remain_distinct() -> None:
    item = _parse(_html(_node()))

    assert item.data["requested_url"] == _REQUESTED
    assert item.data["canonical_url"] == _CANONICAL


@pytest.mark.parametrize(
    "canonical",
    [
        "https://foreign.example/articles/one",
        "http://news.example/articles/one",
        "https://news.example/articles/one#fragment",
        "https:///articles/one",
    ],
)
def test_invalid_or_foreign_canonical_is_rejected(canonical: str) -> None:
    with pytest.raises(ArticleParserError, match="canonical URL"):
        list(_parser().parse(_document(_html(_node(), canonical=canonical))))


def test_cross_subdomain_requires_explicit_constructor_approval() -> None:
    canonical = "https://regional.news.example/articles/one"
    node = _node(mainEntityOfPage={"@id": canonical})

    with pytest.raises(ArticleParserError):
        list(_parser().parse(_document(_html(node, canonical=canonical))))

    item = _parse(
        _html(node, canonical=canonical),
        parser=_parser("news.example", "regional.news.example"),
    )
    assert item.data["source_domain"] == "regional.news.example"


def test_json_ld_headline_is_preferred_over_open_graph() -> None:
    item = _parse(_html(_node(), open_graph={"og:title": "Fallback synthetic title"}))

    assert item.data["headline"] == "Synthetic headline"


def test_open_graph_title_is_headline_fallback() -> None:
    item = _parse(
        _html(
            _node(headline=None),
            open_graph={"og:title": "Fallback synthetic title"},
        )
    )

    assert item.data["headline"] == "Fallback synthetic title"


@pytest.mark.parametrize("headline", [None, "   "])
def test_missing_or_empty_headline_fails(headline: object) -> None:
    with pytest.raises(ArticleParserError, match="headline"):
        list(_parser().parse(_document(_html(_node(headline=headline)))))


def test_article_meta_is_publication_time_fallback() -> None:
    item = _parse(
        _html(
            _node(datePublished=None),
            article_meta={"article:published_time": _PUBLISHED},
        )
    )

    assert item.data["published_at"] == "2026-08-06T05:30:00+00:00"


@pytest.mark.parametrize("published", [None, "invalid", "2026-08-06T12:30:00"])
def test_missing_malformed_or_naive_publication_time_fails(
    published: object,
) -> None:
    with pytest.raises(ArticleParserError, match="publication time"):
        list(_parser().parse(_document(_html(_node(datePublished=published)))))


def test_utc_and_offset_publication_times_preserve_the_same_instant() -> None:
    offset_item = _parse(_html(_node(datePublished=_PUBLISHED)))
    utc_item = _parse(_html(_node(datePublished="2026-08-06T05:30:00Z")))

    assert offset_item.data["published_at"] == utc_item.data["published_at"]


@pytest.mark.parametrize(
    ("node_description", "open_graph", "standard", "expected"),
    [
        (
            "JSON-LD synthetic description",
            "OG description",
            "Meta description",
            "JSON-LD synthetic description",
        ),
        (None, "OG description", "Meta description", "OG description"),
        (None, None, "Meta description", "Meta description"),
        (None, None, None, None),
    ],
)
def test_description_uses_narrow_fallback_order(
    node_description: object,
    open_graph: str | None,
    standard: str | None,
    expected: str | None,
) -> None:
    og = {} if open_graph is None else {"og:description": open_graph}
    item = _parse(
        _html(
            _node(description=node_description),
            open_graph=og,
            description=standard,
        )
    )

    assert item.data["description"] == expected


@pytest.mark.parametrize(
    ("author", "expected"),
    [
        ({"name": "Author One"}, ("Author One",)),
        (
            [{"name": "Author One"}, {"name": "Author Two"}],
            ("Author One", "Author Two"),
        ),
        ("Author One", ("Author One",)),
        (["Author One", "Author Two"], ("Author One", "Author Two")),
        (
            [
                {"name": "Author One"},
                {"url": "https://profiles.example/one"},
                42,
                "Author One",
            ],
            ("Author One",),
        ),
    ],
)
def test_author_shapes_are_normalized(
    author: object, expected: tuple[str, ...]
) -> None:
    item = _parse(_html(_node(author=author, publisher={"name": "Not an author"})))

    assert item.data["author_names"] == expected


def test_modified_time_is_preserved_even_before_publication() -> None:
    item = _parse(_html(_node(dateModified="2026-08-06T04:30:00+00:00")))

    assert item.data["modified_at"] == "2026-08-06T04:30:00+00:00"


def test_malformed_modified_time_is_omitted_or_uses_valid_meta_fallback() -> None:
    omitted = _parse(_html(_node(dateModified="invalid")))
    fallback = _parse(
        _html(
            _node(dateModified="invalid"),
            article_meta={"article:modified_time": "2026-08-06T06:30:00Z"},
        )
    )

    assert omitted.data["modified_at"] is None
    assert fallback.data["modified_at"] == "2026-08-06T06:30:00+00:00"


@pytest.mark.parametrize(
    "image",
    [
        "https://images.example/one.jpg",
        {"url": "https://images.example/one.jpg"},
        {"contentUrl": "https://images.example/one.jpg"},
        [
            "http://images.example/invalid.jpg",
            {"url": "https://images.example/one.jpg"},
        ],
    ],
)
def test_image_shapes_select_first_valid_https_url(image: object) -> None:
    item = _parse(_html(_node(image=image)))

    assert item.data["lead_image_url"] == "https://images.example/one.jpg"


def test_open_graph_image_is_optional_fallback() -> None:
    with_image = _parse(
        _html(
            _node(image=None),
            open_graph={"og:image": "https://images.example/fallback.jpg"},
        )
    )
    without_image = _parse(_html(_node(image="http://images.example/invalid.jpg")))

    assert with_image.data["lead_image_url"] == ("https://images.example/fallback.jpg")
    assert without_image.data["lead_image_url"] is None


def test_language_uses_json_ld_then_html_and_omits_malformed_values() -> None:
    primary = _parse(_html(_node(inLanguage="en-US"), language="id-ID"))
    fallback = _parse(_html(_node(inLanguage=None), language="id-ID"))
    malformed = _parse(_html(_node(inLanguage="invalid-tag-extra"), language=None))

    assert primary.data["language"] == "en-US"
    assert fallback.data["language"] == "id-ID"
    assert malformed.data["language"] is None


def test_section_uses_only_json_ld_article_section() -> None:
    present = _parse(_html(_node(articleSection="Synthetic Section")))
    missing = _parse(_html(_node(articleSection=None)))

    assert present.data["section"] == "Synthetic Section"
    assert missing.data["section"] is None


def test_deferred_fields_and_document_metadata_are_not_emitted() -> None:
    node = _node(
        articleBody="Copyrighted synthetic body",
        keywords=["tag-one"],
    )
    parser = _parser()
    item = list(
        parser.parse(
            _document(
                _html(node),
                metadata={"canonical_url": "https://foreign.example/override"},
            )
        )
    )[0]

    assert "article_body" not in item.data
    assert "tags" not in item.data
    assert "metadata" not in item.data
    assert item.data["canonical_url"] == _CANONICAL


def test_parser_does_not_retain_document_or_leak_state() -> None:
    parser = _parser()
    first = _document(_html(_node(headline="First synthetic headline")))
    second = _document(_html(_node(headline="Second synthetic headline")))

    first_item = list(parser.parse(first))[0]
    second_item = list(parser.parse(second))[0]

    assert first_item.data["headline"] == "First synthetic headline"
    assert second_item.data["headline"] == "Second synthetic headline"
    assert not hasattr(parser, "document")
    assert not hasattr(parser, "content")
