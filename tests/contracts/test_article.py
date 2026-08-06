"""Tests for the source-agnostic article contract."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone

import pytest

from aa_crawler.contracts import ArticleItem
from aa_crawler.crawler import CrawlerItem

_PUBLISHED = datetime(2026, 8, 6, 5, 30, tzinfo=UTC)


def _article(**overrides: object) -> ArticleItem:
    values: dict[str, object] = {
        "source": "example_news",
        "source_domain": "news.example.test",
        "requested_url": "https://news.example.test/requested?page=1",
        "canonical_url": "https://news.example.test/articles/1",
        "headline": "Synthetic article headline",
        "published_at": _PUBLISHED,
    }
    values.update(overrides)
    return ArticleItem(**values)  # type: ignore[arg-type]


def test_minimum_article_uses_normalized_defaults() -> None:
    article = _article()

    assert article.description is None
    assert article.author_names == ()
    assert article.modified_at is None
    assert article.section is None
    assert article.lead_image_url is None
    assert article.language is None


def test_complete_article_is_normalized() -> None:
    article = _article(
        source="  example_news  ",
        source_domain="NEWS.EXAMPLE.TEST.",
        headline="  Synthetic article headline  ",
        description="  Synthetic description  ",
        author_names=("  Author One  ", "Author Two"),
        modified_at=_PUBLISHED + timedelta(hours=1),
        section="  Technology  ",
        lead_image_url="https://cdn.example.test/image.jpg?size=large",
        language="ID-id",
    )

    assert article.source == "example_news"
    assert article.source_domain == "news.example.test"
    assert article.headline == "Synthetic article headline"
    assert article.description == "Synthetic description"
    assert article.author_names == ("Author One", "Author Two")
    assert article.section == "Technology"
    assert article.language == "id-ID"


def test_article_is_immutable_equal_and_hashable() -> None:
    first = _article()
    second = _article()

    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}
    with pytest.raises(FrozenInstanceError):
        first.headline = "Changed"  # type: ignore[misc]


def test_serialization_is_deterministic_and_crawler_compatible() -> None:
    article = _article(author_names=("Author One", "Author Two"))

    serialized = article.to_dict()
    crawler_item = article.to_crawler_item()

    assert list(serialized) == [
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
    ]
    assert serialized["published_at"] == "2026-08-06T05:30:00+00:00"
    assert serialized["author_names"] == ("Author One", "Author Two")
    assert isinstance(crawler_item, CrawlerItem)
    assert crawler_item.data == serialized


@pytest.mark.parametrize("source", ["", " ", "Example", "example-news", "bad\nsource"])
def test_invalid_source_is_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="source"):
        _article(source=source)


@pytest.mark.parametrize(
    "source_domain",
    [
        "",
        "https://news.example.test",
        "news.example.test/path",
        "news.example.test?query=1",
        "news.example.test#fragment",
        "user:secret@news.example.test",
        "localhost",
        "127.0.0.1",
        "-invalid.example",
    ],
)
def test_invalid_source_domain_is_rejected(source_domain: str) -> None:
    with pytest.raises(ValueError, match="source_domain"):
        _article(source_domain=source_domain)


def test_requested_and_canonical_urls_remain_distinct() -> None:
    article = _article(
        requested_url="https://news.example.test/redirect?id=1#client-fragment",
        canonical_url="https://news.example.test/articles/1?edition=web",
    )

    assert article.requested_url == (
        "https://news.example.test/redirect?id=1#client-fragment"
    )
    assert article.canonical_url == ("https://news.example.test/articles/1?edition=web")


@pytest.mark.parametrize(
    ("field_name", "url"),
    [
        ("requested_url", "http://news.example.test/article"),
        ("requested_url", "https://user:secret@news.example.test/article"),
        ("requested_url", "news.example.test/article"),
        ("requested_url", "https:///article"),
        ("canonical_url", "http://news.example.test/article"),
        ("canonical_url", "https://user:secret@news.example.test/article"),
        ("canonical_url", "https://news.example.test/article#fragment"),
        ("canonical_url", "https:///article"),
    ],
)
def test_invalid_article_urls_are_rejected(field_name: str, url: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        _article(**{field_name: url})


def test_canonical_host_must_equal_source_domain() -> None:
    with pytest.raises(ValueError, match="must equal source_domain"):
        _article(canonical_url="https://other.example.test/article")


@pytest.mark.parametrize("headline", ["", " ", "unsafe\nheadline", "unsafe\0headline"])
def test_invalid_headline_is_rejected(headline: str) -> None:
    with pytest.raises(ValueError, match="headline"):
        _article(headline=headline)


def test_aware_timestamps_are_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=7))
    article = _article(
        published_at=datetime(2026, 8, 6, 12, 30, tzinfo=offset),
        modified_at=datetime(2026, 8, 6, 13, 30, tzinfo=offset),
    )

    assert article.published_at == _PUBLISHED
    assert article.modified_at == _PUBLISHED + timedelta(hours=1)
    assert article.published_at.tzinfo is UTC


@pytest.mark.parametrize("field_name", ["published_at", "modified_at"])
def test_naive_timestamps_are_rejected(field_name: str) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _article(**{field_name: datetime(2026, 8, 6, 5, 30)})


def test_modified_at_before_publication_is_preserved() -> None:
    reported_modified = _PUBLISHED - timedelta(hours=1)
    article = _article(modified_at=reported_modified)

    assert article.modified_at == reported_modified


def test_authors_are_trimmed_deduplicated_and_empty_entries_are_omitted() -> None:
    values = [" Author One ", "", "Author Two", "Author One", "   "]
    article = _article(author_names=values)
    values.append("Changed")

    assert article.author_names == ("Author One", "Author Two")
    with pytest.raises(AttributeError):
        article.author_names.append("Other")  # type: ignore[attr-defined]


@pytest.mark.parametrize("field_name", ["description", "section"])
def test_optional_text_is_trimmed_and_empty_becomes_none(field_name: str) -> None:
    assert getattr(_article(**{field_name: "  Value  "}), field_name) == "Value"
    assert getattr(_article(**{field_name: "   "}), field_name) is None


@pytest.mark.parametrize(
    "lead_image_url",
    [
        "http://cdn.example.test/image.jpg",
        "https://user:secret@cdn.example.test/image.jpg",
        "https://cdn.example.test/image.jpg#fragment",
        "cdn.example.test/image.jpg",
    ],
)
def test_invalid_lead_image_url_is_rejected(lead_image_url: str) -> None:
    with pytest.raises(ValueError, match="lead_image_url"):
        _article(lead_image_url=lead_image_url)


def test_lead_image_may_use_a_different_https_host() -> None:
    article = _article(lead_image_url="https://cdn.example.test/image.jpg")

    assert article.lead_image_url == "https://cdn.example.test/image.jpg"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("id", "id"), ("id-ID", "id-ID"), ("ID-id", "id-ID"), ("en-us", "en-US")],
)
def test_language_is_normalized(value: str, expected: str) -> None:
    assert _article(language=value).language == expected


@pytest.mark.parametrize("language", ["", "i", "indonesia", "id_ID", "id-ID-extra"])
def test_malformed_language_is_rejected(language: str) -> None:
    with pytest.raises(ValueError, match="language"):
        _article(language=language)


def test_deferred_and_free_form_fields_are_absent() -> None:
    field_names = {field.name for field in fields(ArticleItem)}

    assert field_names.isdisjoint(
        {
            "article_body",
            "raw_html",
            "raw_json_ld",
            "tags",
            "lead_image_caption",
            "metadata",
        }
    )
