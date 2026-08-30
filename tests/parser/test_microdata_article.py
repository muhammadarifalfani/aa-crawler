"""Synthetic tests for the third, Microdata parser family (ADR-026)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import ArticleParserError, BaseParser, MicrodataArticleParser

_CANONICAL = "https://news.example/articles/one"
_REQUESTED = "https://news.example/redirect?id=one"
_PUBLISHED = "2026-08-06T12:30:00+07:00"


def _author_markup(author: object | None, *, nested: bool) -> str:
    if author is None:
        return ""
    if nested:
        return (
            '<span itemprop="author" itemscope '
            'itemtype="https://schema.org/Person">'
            f'<span itemprop="name">{author}</span></span>'
        )
    return f'<span itemprop="author">{author}</span>'


def _image_markup(image: object | None, *, via_meta: bool) -> str:
    if image is None:
        return ""
    if via_meta:
        return f'<meta itemprop="image" content="{image}">'
    return f'<img itemprop="image" src="{image}">'


def _html(
    *,
    itemtype: str = "https://schema.org/NewsArticle",
    canonical: str | None = _CANONICAL,
    headline: object = "Synthetic headline",
    published: object = _PUBLISHED,
    modified: object | None = None,
    description: object | None = None,
    author: object | None = "Jane Doe",
    author_nested: bool = False,
    image: object | None = "https://news.example/image.jpg",
    image_via_meta: bool = False,
    section: object | None = None,
    identity: str | None = _CANONICAL,
    identity_prop: str = "mainEntityOfPage",
    language: str | None = "id-ID",
    open_graph: dict[str, str] | None = None,
    extra_body: str = "",
) -> str:
    head_lang = f' lang="{language}"' if language is not None else ""
    canonical_link = (
        f'<link rel="canonical" href="{canonical}">' if canonical is not None else ""
    )
    og_meta = "".join(
        f'<meta property="{key}" content="{value}">'
        for key, value in (open_graph or {}).items()
    )
    identity_link = (
        f'<link itemprop="{identity_prop}" href="{identity}">'
        if identity is not None
        else ""
    )
    headline_markup = f'<h1 itemprop="headline">{headline or ""}</h1>'
    published_markup = (
        f'<time itemprop="datePublished" datetime="{published}"></time>'
        if published is not None
        else ""
    )
    modified_markup = (
        f'<time itemprop="dateModified" datetime="{modified}"></time>'
        if modified is not None
        else ""
    )
    description_markup = (
        f'<div itemprop="description">{description}</div>'
        if description is not None
        else ""
    )
    section_markup = (
        f'<span itemprop="articleSection">{section}</span>'
        if section is not None
        else ""
    )

    return (
        f"<html{head_lang}><head>{canonical_link}{og_meta}</head><body>"
        f'<div itemscope itemtype="{itemtype}">'
        f"{identity_link}{headline_markup}{published_markup}{modified_markup}"
        f"{description_markup}"
        f"{_author_markup(author, nested=author_nested)}"
        f"{_image_markup(image, via_meta=image_via_meta)}"
        f"{section_markup}{extra_body}"
        "</div></body></html>"
    )


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


def _parser(**overrides: object) -> MicrodataArticleParser:
    values: dict[str, object] = {
        "source": "example_news",
        "source_domains": ["news.example"],
    }
    values.update(overrides)
    return MicrodataArticleParser(**values)  # type: ignore[arg-type]


def _parse(content: str, **parser_overrides: object) -> CrawlerItem:
    items = list(_parser(**parser_overrides).parse(_document(content)))
    assert len(items) == 1
    return items[0]


def test_parser_construction_retains_normalized_source_boundary() -> None:
    parser = MicrodataArticleParser(
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
        MicrodataArticleParser(source=source, source_domains=domains)


def test_parser_integrates_with_lazy_base_parser_lifecycle() -> None:
    parser = _parser()

    result = parser.parse(_document(_html()))

    assert isinstance(parser, BaseParser)
    assert isinstance(result, Iterator)
    assert next(result).data["headline"] == "Synthetic headline"


def test_repeated_calls_are_independent_and_deterministic() -> None:
    parser = _parser()
    document = _document(_html())

    first = list(parser.parse(document))
    second = list(parser.parse(document))

    assert first == second
    assert first[0] is not second[0]


def test_output_is_deterministic_crawler_item_data() -> None:
    item = _parse(
        _html(
            modified="2026-08-06T13:00:00+07:00",
            description="A synthetic description.",
            section="World",
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
        "author_names": ("Jane Doe",),
        "modified_at": "2026-08-06T06:00:00+00:00",
        "section": "World",
        "lead_image_url": "https://news.example/image.jpg",
        "language": "id-ID",
    }


@pytest.mark.parametrize("itemtype", ["https://schema.org/NewsArticle", "Article"])
def test_news_article_and_article_types_are_supported(itemtype: str) -> None:
    item = _parse(_html(itemtype=itemtype))

    assert item.data["headline"] == "Synthetic headline"


def test_unrelated_itemscope_is_ignored() -> None:
    content = _html(
        extra_body=(
            '<nav itemscope itemtype="https://schema.org/SiteNavigationElement">'
            "<span>Home</span></nav>"
        )
    )

    item = _parse(content)

    assert item.data["headline"] == "Synthetic headline"


def test_no_valid_candidate_fails_without_exposing_content() -> None:
    content = (
        '<html><body><div itemscope itemtype="https://schema.org/Person">'
        '<span itemprop="name">Not an article</span></div></body></html>'
    )

    with pytest.raises(ArticleParserError, match="no valid Microdata"):
        _parse(content)


def test_multiple_candidates_without_identity_authority_are_ambiguous() -> None:
    content = (
        "<html><body>"
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        '<h1 itemprop="headline">First</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div>"
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        '<h1 itemprop="headline">Second</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div>"
        "</body></html>"
    )

    with pytest.raises(ArticleParserError, match="ambiguous"):
        _parse(content)


def test_multiple_candidates_matching_identity_are_ambiguous() -> None:
    content = (
        '<html><head><link rel="canonical" href="' + _CANONICAL + '"></head><body>'
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        f'<link itemprop="mainEntityOfPage" href="{_CANONICAL}">'
        '<h1 itemprop="headline">First</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div>"
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        f'<link itemprop="mainEntityOfPage" href="{_CANONICAL}">'
        '<h1 itemprop="headline">Second</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div>"
        "</body></html>"
    )

    with pytest.raises(ArticleParserError, match="ambiguous"):
        _parse(content)


def test_candidate_not_matching_page_identity_fails() -> None:
    content = (
        '<html><head><link rel="canonical" href="' + _CANONICAL + '"></head><body>'
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        '<link itemprop="mainEntityOfPage" href="https://news.example/other">'
        '<h1 itemprop="headline">Mismatched</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div></body></html>"
    )

    with pytest.raises(ArticleParserError, match="matches the page identity"):
        _parse(content)


def test_nested_author_person_is_resolved_to_name() -> None:
    item = _parse(_html(author="John Roe", author_nested=True))

    assert item.data["author_names"] == ("John Roe",)


def test_plain_text_author_is_accepted() -> None:
    item = _parse(_html(author="Plain Author", author_nested=False))

    assert item.data["author_names"] == ("Plain Author",)


def test_image_via_meta_content_is_accepted() -> None:
    item = _parse(
        _html(image="https://news.example/meta-image.jpg", image_via_meta=True)
    )

    assert item.data["lead_image_url"] == "https://news.example/meta-image.jpg"


@pytest.mark.parametrize(
    "image",
    ["http://news.example/image.jpg", "not-a-url", None],
)
def test_invalid_or_missing_image_is_omitted_rather_than_fatal(
    image: str | None,
) -> None:
    item = _parse(_html(image=image))

    assert item.data["lead_image_url"] is None


def test_open_graph_image_is_optional_fallback() -> None:
    item = _parse(
        _html(image=None, open_graph={"og:image": "https://news.example/og.jpg"})
    )

    assert item.data["lead_image_url"] == "https://news.example/og.jpg"


@pytest.mark.parametrize("headline", ["", "   "])
def test_missing_or_empty_headline_fails(headline: str) -> None:
    with pytest.raises(ArticleParserError, match="headline"):
        _parse(_html(headline=headline))


def test_open_graph_title_is_headline_fallback() -> None:
    content = (
        '<html><head><link rel="canonical" href="'
        + _CANONICAL
        + '"><meta property="og:title" content="OG headline"></head><body>'
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        f'<link itemprop="mainEntityOfPage" href="{_CANONICAL}">'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div></body></html>"
    )

    item = _parse(content)

    assert item.data["headline"] == "OG headline"


@pytest.mark.parametrize(
    "published",
    [None, "", "not-a-datetime", "2026-08-06T12:30:00"],
)
def test_missing_malformed_or_naive_publication_time_fails(
    published: object,
) -> None:
    with pytest.raises(ArticleParserError, match="publication time"):
        _parse(_html(published=published))


def test_utc_and_z_suffixed_publication_times_are_accepted() -> None:
    item = _parse(_html(published="2026-08-06T05:30:00Z"))

    assert item.data["published_at"] == "2026-08-06T05:30:00+00:00"


def test_modified_time_is_preserved_even_before_publication() -> None:
    item = _parse(_html(modified="2020-01-01T00:00:00+00:00"))

    assert item.data["modified_at"] == "2020-01-01T00:00:00+00:00"


def test_description_falls_back_to_open_graph_then_meta_description() -> None:
    content = (
        '<html><head><link rel="canonical" href="'
        + _CANONICAL
        + '"><meta name="description" content="Meta description."></head><body>'
        '<div itemscope itemtype="https://schema.org/NewsArticle">'
        f'<link itemprop="mainEntityOfPage" href="{_CANONICAL}">'
        '<h1 itemprop="headline">Synthetic headline</h1>'
        f'<time itemprop="datePublished" datetime="{_PUBLISHED}"></time>'
        "</div></body></html>"
    )

    item = _parse(content)

    assert item.data["description"] == "Meta description."


@pytest.mark.parametrize(
    "canonical",
    [
        "http://news.example/articles/one",
        "https://foreign.example/articles/one",
    ],
)
def test_invalid_or_foreign_canonical_is_rejected(canonical: str) -> None:
    content = _html(canonical=None, identity=canonical)

    with pytest.raises(ArticleParserError, match="canonical URL"):
        _parse(content)


def test_cross_subdomain_requires_explicit_constructor_approval() -> None:
    content = _html(
        canonical=None, identity="https://regional.news.example/articles/one"
    )

    with pytest.raises(ArticleParserError, match="approved boundary"):
        _parse(content)

    item = _parse(content, source_domains=["news.example", "regional.news.example"])
    assert item.data["source_domain"] == "regional.news.example"


def test_url_itemprop_is_identity_fallback_when_no_main_entity() -> None:
    content = _html(identity_prop="url")

    item = _parse(content)

    assert item.data["canonical_url"] == _CANONICAL


def test_malformed_language_is_omitted() -> None:
    item = _parse(_html(language="not a language"))

    assert item.data["language"] is None


def test_section_uses_only_microdata_article_section() -> None:
    item = _parse(_html(section="World"))

    assert item.data["section"] == "World"


def test_deferred_fields_default_to_none_or_empty_when_absent() -> None:
    item = _parse(_html(author=None, image=None))

    assert item.data["description"] is None
    assert item.data["author_names"] == ()
    assert item.data["modified_at"] is None
    assert item.data["section"] is None
    assert item.data["lead_image_url"] is None


def test_requested_and_canonical_urls_remain_distinct() -> None:
    item = _parse(_html())

    assert item.data["requested_url"] == _REQUESTED
    assert item.data["canonical_url"] == _CANONICAL
    assert item.data["requested_url"] != item.data["canonical_url"]


def test_parser_does_not_retain_document_or_leak_state() -> None:
    parser = _parser()

    list(parser.parse(_document(_html())))

    assert not hasattr(parser, "document")
    assert not hasattr(parser, "_document")
