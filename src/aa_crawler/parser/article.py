"""Source-agnostic JSON-LD article parser."""

from __future__ import annotations

import json
import re
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
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 10_000


class _ArticleMetadataParser(HTMLParser):
    """Collect only the narrow metadata surface required by the parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical_url: str | None = None
        self.language: str | None = None
        self.json_ld_blocks: list[str] = []
        self.open_graph: dict[str, str] = {}
        self.article_meta: dict[str, str] = {}
        self.description: str | None = None
        self._in_json_ld = False
        self._script_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag == "html" and self.language is None:
            self.language = values.get("lang")
        elif tag == "link" and self.canonical_url is None:
            rel = values.get("rel") or ""
            if "canonical" in rel.lower().split():
                self.canonical_url = values.get("href")
        elif tag == "meta":
            self._collect_meta(values)
        elif tag == "script":
            media_type = (values.get("type") or "").split(";", maxsplit=1)[0]
            if media_type.strip().lower() == "application/ld+json":
                self._in_json_ld = True
                self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self.json_ld_blocks.append("".join(self._script_parts))
            self._in_json_ld = False
            self._script_parts = []

    def _collect_meta(self, values: Mapping[str, str | None]) -> None:
        key = values.get("property") or values.get("name")
        content = values.get("content")
        if not key or content is None:
            return
        normalized_key = key.strip().lower()
        if normalized_key.startswith("og:"):
            self.open_graph.setdefault(normalized_key, content)
        elif normalized_key in {"article:published_time", "article:modified_time"}:
            self.article_meta.setdefault(normalized_key, content)
        elif normalized_key == "description" and self.description is None:
            self.description = content


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


def _walk_json(value: object) -> Iterable[dict[str, object]]:
    stack: list[tuple[object, int]] = [(value, 0)]
    visited = 0
    while stack:
        current, depth = stack.pop()
        visited += 1
        if visited > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            raise ArticleParserError("JSON-LD structure exceeds safe traversal limits")
        if isinstance(current, dict):
            yield current
            children = list(current.values())
            stack.extend((child, depth + 1) for child in reversed(children))
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in reversed(current))


def _article_kind(node: Mapping[str, object]) -> str | None:
    value = node.get("@type")
    values = value if isinstance(value, list) else [value]
    string_values = {item for item in values if isinstance(item, str)}
    if "NewsArticle" in string_values:
        return "NewsArticle"
    if "Article" in string_values:
        return "Article"
    return None


def _identity_value(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("@id", "url"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return None


def _candidate_identity(node: Mapping[str, object]) -> str | None:
    return _identity_value(node.get("mainEntityOfPage")) or _identity_value(
        node.get("url")
    )


def _select_candidate(
    candidates: list[dict[str, object]],
    *,
    page_identity: str | None,
) -> dict[str, object]:
    news_candidates = [
        candidate
        for candidate in candidates
        if _article_kind(candidate) == "NewsArticle"
    ]
    eligible = news_candidates or candidates
    if page_identity is not None:
        matches = [
            candidate
            for candidate in eligible
            if _candidate_identity(candidate) == page_identity
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ArticleParserError("JSON-LD article candidates are ambiguous")
        if len(eligible) == 1 and _candidate_identity(eligible[0]) is None:
            return eligible[0]
        raise ArticleParserError("no JSON-LD article matches the page identity")
    if len(eligible) != 1:
        raise ArticleParserError("JSON-LD article candidates are ambiguous")
    return eligible[0]


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_language(value: object) -> str | None:
    text = _text(value)
    return text if text is not None and _LANGUAGE_PATTERN.fullmatch(text) else None


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


def _author_names(value: object) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value]
    names: list[str] = []
    for candidate in values:
        name_value: object
        if isinstance(candidate, str):
            name_value = candidate
        elif isinstance(candidate, dict):
            name_value = candidate.get("name")
        else:
            continue
        if isinstance(name_value, str) and name_value.strip():
            names.append(name_value)
    return tuple(names)


def _image_candidates(value: object) -> Iterable[object]:
    if isinstance(value, list):
        yield from value
    elif value is not None:
        yield value


def _first_valid_image(value: object) -> str | None:
    for candidate in _image_candidates(value):
        url_value: object
        if isinstance(candidate, str):
            url_value = candidate
        elif isinstance(candidate, dict):
            url_value = candidate.get("url") or candidate.get("contentUrl")
        else:
            continue
        if not isinstance(url_value, str):
            continue
        try:
            parsed = urlsplit(url_value)
            _ = parsed.port
        except ValueError:
            continue
        if (
            parsed.scheme.lower() == "https"
            and parsed.hostname is not None
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
        ):
            return url_value
    return None


class JsonLdArticleParser(BaseParser):
    """Parse one normalized article from generic JSON-LD page metadata."""

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
        """Parse and convert one article using only document-local metadata."""
        from aa_crawler.contracts import ArticleItem

        metadata = _ArticleMetadataParser()
        metadata.feed(document.content)

        candidates: list[dict[str, object]] = []
        for block in metadata.json_ld_blocks:
            try:
                decoded: object = json.loads(block)
                candidates.extend(
                    node for node in _walk_json(decoded) if _article_kind(node)
                )
            except (json.JSONDecodeError, RecursionError):
                continue
        if not candidates:
            raise ArticleParserError("no valid JSON-LD article candidate was found")

        page_identity_value = metadata.canonical_url or metadata.open_graph.get(
            "og:url"
        )
        page_identity = (
            None
            if page_identity_value is None
            else _validated_page_url(page_identity_value, self.source_domains)
        )
        candidate = _select_candidate(candidates, page_identity=page_identity)
        canonical_url = page_identity or _validated_page_url(
            _candidate_identity(candidate),
            self.source_domains,
        )
        canonical_host = urlsplit(canonical_url).hostname
        if canonical_host is None:
            raise ArticleParserError("article canonical URL is missing or invalid")

        headline = _text(candidate.get("headline")) or metadata.open_graph.get(
            "og:title"
        )
        published_at = _parse_datetime(
            candidate.get("datePublished")
        ) or _parse_datetime(metadata.article_meta.get("article:published_time"))
        if headline is None:
            raise ArticleParserError("article headline is missing or invalid")
        if published_at is None:
            raise ArticleParserError("article publication time is missing or invalid")

        modified_at = _parse_datetime(candidate.get("dateModified"))
        if modified_at is None:
            modified_at = _parse_datetime(
                metadata.article_meta.get("article:modified_time")
            )
        description = (
            _text(candidate.get("description"))
            or metadata.open_graph.get("og:description")
            or metadata.description
        )
        lead_image_url = _first_valid_image(candidate.get("image"))
        if lead_image_url is None:
            lead_image_url = _first_valid_image(metadata.open_graph.get("og:image"))
        language = _optional_language(
            candidate.get("inLanguage")
        ) or _optional_language(metadata.language)

        try:
            article = ArticleItem(
                source=self.source,
                source_domain=canonical_host,
                requested_url=document.requested_url,
                canonical_url=canonical_url,
                headline=headline,
                published_at=published_at,
                description=description,
                author_names=_author_names(candidate.get("author")),
                modified_at=modified_at,
                section=_text(candidate.get("articleSection")),
                lead_image_url=lead_image_url,
                language=language,
            )
        except (TypeError, ValueError) as error:
            raise ArticleParserError("article metadata is invalid") from error
        return (article.to_crawler_item(),)
