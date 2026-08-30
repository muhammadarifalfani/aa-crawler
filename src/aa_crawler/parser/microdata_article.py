"""Third parser family: schema.org Microdata article parsing (ADR-026).

This parser proves ADR-025's multi-parser-family composition seam with a
representation that, unlike Sprint 8's synthetic `generic_json_article`,
remains real HTML (`text/html`) and is therefore acquisition-compatible
with the existing, unmodified `HtmlFetcher` boundary. It parses
`schema.org` `NewsArticle`/`Article` Microdata (`itemscope`, `itemtype`,
`itemprop` attributes) directly from `HtmlDocument.content` and produces
the exact same `ArticleItem`/`CrawlerItem` output shape as
`JsonLdArticleParser` and `GenericJsonArticleParser`.

Scope is deliberately narrow, matching only the properties `ArticleItem`
already models: `headline`, `datePublished`, `dateModified`, `description`,
`author` (plain text or one level of nested `Person` Microdata),
`image` (an attribute-resolved URL or one level of nested `ImageObject`
Microdata), `articleSection`, and identity resolution via
`mainEntityOfPage`/`url`. It does not implement the full WHATWG Microdata
model (for example, multi-valued `itemprop` attributes, `itemref`, or
arbitrarily deep nesting beyond one level) — those remain unsupported
until observed evidence requires them, matching this project's existing
"narrow, evidence-driven" parser philosophy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from aa_crawler.parser.base import BaseParser
from aa_crawler.parser.errors import ArticleParserError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from aa_crawler.crawler import CrawlerItem
    from aa_crawler.html import HtmlDocument

_SOURCE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2})?$")

_NEWS_ARTICLE_TYPES = frozenset(
    {
        "https://schema.org/NewsArticle",
        "http://schema.org/NewsArticle",
        "schema.org/NewsArticle",
        "NewsArticle",
    }
)
_GENERIC_ARTICLE_TYPES = frozenset(
    {
        "https://schema.org/Article",
        "http://schema.org/Article",
        "schema.org/Article",
        "Article",
    }
)
_ARTICLE_TYPES = _NEWS_ARTICLE_TYPES | _GENERIC_ARTICLE_TYPES

_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
_SRC_ATTR_TAGS = frozenset(
    {"audio", "embed", "iframe", "img", "source", "track", "video"}
)
_URL_ATTR_TAGS = frozenset({"a", "area", "link"})


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


def _validated_page_url(value: object, domains: frozenset[str]) -> str:
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


@dataclass
class _Scope:
    """One open `itemscope` context: its declared type and collected props."""

    itemtype: str | None
    props: dict[str, list[str]] = field(default_factory=dict)

    def add(self, prop: str, value: str | None) -> None:
        if value is None:
            return
        self.props.setdefault(prop, []).append(value)

    def first(self, prop: str) -> str | None:
        values = self.props.get(prop)
        return values[0] if values else None


@dataclass
class _Frame:
    """One open HTML element on the parser's element stack."""

    tag: str
    opened_scope: bool = False
    nested_prop: str | None = None
    capture_prop: str | None = None
    capture_parts: list[str] = field(default_factory=list)


def _first_itemprop(values: Mapping[str, str | None]) -> str | None:
    """Return the first whitespace-separated `itemprop` token, if any."""
    tokens = (values.get("itemprop") or "").split()
    return tokens[0] if tokens else None


def _resolve_nested_value(scope: _Scope) -> str | None:
    """Reduce a nested item (for example Person, ImageObject) to one value."""
    for prop in ("name", "url", "contentUrl"):
        value = scope.first(prop)
        if value is not None:
            return value
    return None


def _resolve_attr_value(tag: str, values: Mapping[str, str | None]) -> str | None:
    """Resolve an itemprop's value from this tag's conventional attribute."""
    if tag == "meta":
        return values.get("content")
    if tag in _SRC_ATTR_TAGS:
        return values.get("src")
    if tag in _URL_ATTR_TAGS:
        return values.get("href")
    if tag == "object":
        return values.get("data")
    if tag == "time":
        return values.get("datetime")
    return None


class _MicrodataMetadataParser(HTMLParser):
    """Collect standalone itemscope items and page-level fallback metadata."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.language: str | None = None
        self.canonical_url: str | None = None
        self.description: str | None = None
        self.open_graph: dict[str, str] = {}
        self.items: list[_Scope] = []
        self._stack: list[_Frame] = []
        self._scopes: list[_Scope] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.lower(): value for key, value in attrs}
        self._collect_page_metadata(tag, values)
        if tag in _VOID_TAGS:
            self._handle_void_tag(tag, values)
        else:
            self._handle_scoped_tag(tag, values)

    def _collect_page_metadata(
        self,
        tag: str,
        values: Mapping[str, str | None],
    ) -> None:
        if tag == "html" and self.language is None:
            self.language = values.get("lang")
        elif tag == "link" and self.canonical_url is None:
            rel = values.get("rel") or ""
            if "canonical" in rel.lower().split():
                self.canonical_url = values.get("href")
        elif tag == "meta":
            self._collect_meta(values)

    def _handle_void_tag(self, tag: str, values: Mapping[str, str | None]) -> None:
        itemprop_name = _first_itemprop(values)
        if itemprop_name and self._scopes:
            self._scopes[-1].add(itemprop_name, _resolve_attr_value(tag, values))

    def _handle_scoped_tag(self, tag: str, values: Mapping[str, str | None]) -> None:
        has_scope = "itemscope" in values
        itemprop_name = _first_itemprop(values)

        frame = _Frame(tag=tag)
        if has_scope:
            frame.opened_scope = True
            frame.nested_prop = itemprop_name
            self._scopes.append(_Scope(itemtype=values.get("itemtype")))
        elif itemprop_name:
            resolved = _resolve_attr_value(tag, values)
            if resolved is not None:
                if self._scopes:
                    self._scopes[-1].add(itemprop_name, resolved)
            else:
                frame.capture_prop = itemprop_name
        self._stack.append(frame)

    def handle_data(self, data: str) -> None:
        for frame in reversed(self._stack):
            if frame.capture_prop:
                frame.capture_parts.append(data)
                break

    def handle_endtag(self, _tag: str) -> None:
        if not self._stack:
            return
        frame = self._stack.pop()
        if frame.capture_prop and self._scopes:
            self._scopes[-1].add(frame.capture_prop, "".join(frame.capture_parts))
        if frame.opened_scope:
            scope = self._scopes.pop()
            if frame.nested_prop and self._scopes:
                self._scopes[-1].add(frame.nested_prop, _resolve_nested_value(scope))
            elif frame.nested_prop is None:
                self.items.append(scope)

    def _collect_meta(self, values: Mapping[str, str | None]) -> None:
        key = values.get("property") or values.get("name")
        content = values.get("content")
        if not key or content is None:
            return
        normalized_key = key.strip().lower()
        if normalized_key.startswith("og:"):
            self.open_graph.setdefault(normalized_key, content)
        elif normalized_key == "description" and self.description is None:
            self.description = content


def _select_candidate(
    candidates: list[_Scope],
    *,
    page_identity: str | None,
) -> _Scope:
    if page_identity is not None:
        matches = [
            candidate
            for candidate in candidates
            if (candidate.first("mainEntityOfPage") or candidate.first("url"))
            == page_identity
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ArticleParserError("Microdata article candidates are ambiguous")
        if len(candidates) == 1 and not (
            candidates[0].first("mainEntityOfPage") or candidates[0].first("url")
        ):
            return candidates[0]
        raise ArticleParserError("no Microdata article matches the page identity")
    if len(candidates) != 1:
        raise ArticleParserError("Microdata article candidates are ambiguous")
    return candidates[0]


class MicrodataArticleParser(BaseParser):
    """Parse one normalized article from schema.org Microdata (ADR-026)."""

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
        """Parse and convert one article using only document-local Microdata."""
        from aa_crawler.contracts import ArticleItem

        metadata = _MicrodataMetadataParser()
        metadata.feed(document.content)

        candidates = [
            item for item in metadata.items if item.itemtype in _ARTICLE_TYPES
        ]
        if not candidates:
            raise ArticleParserError("no valid Microdata article candidate was found")

        news_candidates = [
            candidate
            for candidate in candidates
            if candidate.itemtype in _NEWS_ARTICLE_TYPES
        ]
        eligible = news_candidates or candidates

        page_identity_value = metadata.canonical_url or metadata.open_graph.get(
            "og:url"
        )
        page_identity = (
            None
            if page_identity_value is None
            else _validated_page_url(page_identity_value, self.source_domains)
        )
        candidate = _select_candidate(eligible, page_identity=page_identity)
        identity_value = candidate.first("mainEntityOfPage") or candidate.first("url")
        canonical_url = page_identity or _validated_page_url(
            identity_value, self.source_domains
        )
        canonical_host = urlsplit(canonical_url).hostname
        if canonical_host is None:
            raise ArticleParserError("article canonical URL is missing or invalid")

        headline = _text(candidate.first("headline")) or metadata.open_graph.get(
            "og:title"
        )
        published_at = _parse_datetime(candidate.first("datePublished"))
        if headline is None:
            raise ArticleParserError("article headline is missing or invalid")
        if published_at is None:
            raise ArticleParserError("article publication time is missing or invalid")

        modified_at = _parse_datetime(candidate.first("dateModified"))
        description = (
            _text(candidate.first("description"))
            or metadata.open_graph.get("og:description")
            or metadata.description
        )
        author_names = tuple(
            name
            for name in candidate.props.get("author", [])
            if isinstance(name, str) and name.strip()
        )
        lead_image_url = None
        for image_value in candidate.props.get("image", []):
            lead_image_url = _optional_image_url(image_value)
            if lead_image_url is not None:
                break
        if lead_image_url is None:
            lead_image_url = _optional_image_url(metadata.open_graph.get("og:image"))
        section = _text(candidate.first("articleSection"))
        language = _optional_language(metadata.language)

        try:
            article = ArticleItem(
                source=self.source,
                source_domain=canonical_host,
                requested_url=document.requested_url,
                canonical_url=canonical_url,
                headline=headline,
                published_at=published_at,
                description=description,
                author_names=author_names,
                modified_at=modified_at,
                section=section,
                lead_image_url=lead_image_url,
                language=language,
            )
        except (TypeError, ValueError) as error:
            raise ArticleParserError("article metadata is invalid") from error
        return (article.to_crawler_item(),)
