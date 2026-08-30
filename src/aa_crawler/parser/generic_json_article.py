"""Synthetic second parser family proving multi-family composition (ADR-025).

This parser demonstrates that `SourceProfile`/`ParserComposer` can dispatch
to more than one closed, statically-mapped parser family while still
producing the exact same `ArticleItem`/`CrawlerItem` output shape as
`JsonLdArticleParser`. It parses a flat JSON object directly from
`HtmlDocument.content` instead of extracting JSON-LD from HTML markup.

It is exercised only through synthetic, in-test `HtmlDocument` fixtures.
`HtmlFetcher` still accepts only `text/html`/`application/xhtml+xml`
responses, so this family is never reachable through real network
acquisition under this decision (ADR-025).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from aa_crawler.parser.base import BaseParser
from aa_crawler.parser.errors import ArticleParserError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from aa_crawler.crawler import CrawlerItem
    from aa_crawler.html import HtmlDocument

_SOURCE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2})?$")


def _normalize_source(source: str) -> str:
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    normalized = source.strip()
    if not _SOURCE_PATTERN.fullmatch(normalized):
        raise ValueError("source must be a lowercase machine-readable identifier")
    return normalized


def _normalize_domain(domain: str) -> str:
    if not isinstance(domain, str):
        raise TypeError("source domains must be strings")
    normalized = domain.strip().lower().rstrip(".")
    labels = normalized.split(".")
    if len(labels) < 2 or any(
        not _HOST_LABEL_PATTERN.fullmatch(label) for label in labels
    ):
        raise ValueError("source domains must be valid hostnames")
    return normalized


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _validated_canonical_url(value: object, domains: frozenset[str]) -> str:
    if not isinstance(value, str):
        raise ArticleParserError("article canonical URL is missing or invalid")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as error:
        raise ArticleParserError(
            "article canonical URL is missing or invalid"
        ) from error
    hostname = parsed.hostname.lower().rstrip(".") if parsed.hostname else None
    if (
        parsed.scheme.lower() != "https"
        or hostname not in domains
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.fragment)
    ):
        raise ArticleParserError(
            "article canonical URL is outside the approved boundary"
        )
    return value


def _optional_image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.fragment)
    ):
        return None
    return value


def _parse_datetime(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _optional_language(value: object) -> str | None:
    text = _text(value)
    return text if text is not None and _LANGUAGE_PATTERN.fullmatch(text) else None


def _author_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(name for name in value if isinstance(name, str) and name.strip())


class GenericJsonArticleParser(BaseParser):
    """Parse one normalized article from a flat, non-JSON-LD JSON payload."""

    def __init__(self, *, source: str, source_domains: Iterable[str]) -> None:
        self._source = _normalize_source(source)
        self._source_domains = frozenset(
            _normalize_domain(domain) for domain in source_domains
        )
        if not self._source_domains:
            raise ValueError("at least one source domain is required")

    @property
    def source(self) -> str:
        """Return the injected stable source identifier."""
        return self._source

    @property
    def source_domains(self) -> frozenset[str]:
        """Return the exact approved canonical-host boundary."""
        return self._source_domains

    def parse_document(self, document: HtmlDocument) -> Iterable[CrawlerItem]:
        """Parse one article from a flat JSON payload in `document.content`."""
        from aa_crawler.contracts import ArticleItem

        try:
            payload: object = json.loads(document.content)
        except json.JSONDecodeError as error:
            raise ArticleParserError("article JSON payload is invalid") from error
        if not isinstance(payload, dict):
            raise ArticleParserError("article JSON payload must be an object")

        canonical_url = _validated_canonical_url(
            payload.get("url"), self.source_domains
        )
        canonical_host = urlsplit(canonical_url).hostname
        if canonical_host is None:
            raise ArticleParserError("article canonical URL is missing or invalid")

        headline = _text(payload.get("headline"))
        published_at = _parse_datetime(payload.get("published_at"))
        if headline is None:
            raise ArticleParserError("article headline is missing or invalid")
        if published_at is None:
            raise ArticleParserError("article publication time is missing or invalid")

        try:
            article = ArticleItem(
                source=self.source,
                source_domain=canonical_host,
                requested_url=document.requested_url,
                canonical_url=canonical_url,
                headline=headline,
                published_at=published_at,
                description=_text(payload.get("description")),
                author_names=_author_names(payload.get("authors")),
                modified_at=_parse_datetime(payload.get("modified_at")),
                section=_text(payload.get("section")),
                lead_image_url=_optional_image_url(payload.get("lead_image_url")),
                language=_optional_language(payload.get("language")),
            )
        except (TypeError, ValueError) as error:
            raise ArticleParserError("article metadata is invalid") from error
        return (article.to_crawler_item(),)
