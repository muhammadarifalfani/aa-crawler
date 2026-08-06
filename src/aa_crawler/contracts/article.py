"""Source-agnostic immutable online-news article contract."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

from aa_crawler.crawler import CrawlerItem

_SOURCE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_LANGUAGE_PATTERN = re.compile(
    r"^(?P<language>[A-Za-z]{2,3})(?:-(?P<region>[A-Za-z]{2}))?$"
)


def _contains_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _required_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if _contains_control_characters(normalized):
        raise ValueError(f"{field_name} contains an invalid control character")
    return normalized


def _optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if _contains_control_characters(normalized):
        raise ValueError(f"{field_name} contains an invalid control character")
    return normalized


def _normalize_source(value: str) -> str:
    normalized = _required_text(value, field_name="source")
    if not _SOURCE_PATTERN.fullmatch(normalized):
        raise ValueError("source must be a lowercase machine-readable identifier")
    return normalized


def _normalize_hostname(value: str, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name).lower().rstrip(".")
    if any(character in normalized for character in "/?#@:"):
        raise ValueError(f"{field_name} must contain only a hostname")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise ValueError(f"{field_name} must be a hostname, not an IP address")
    labels = normalized.split(".")
    if len(labels) < 2 or any(
        not _HOST_LABEL_PATTERN.fullmatch(label) for label in labels
    ):
        raise ValueError(f"{field_name} must be a valid hostname")
    return normalized


def _validate_https_url(
    value: str,
    *,
    field_name: str,
    allow_fragment: bool,
) -> tuple[str, str]:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if value != value.strip() or _contains_control_characters(value):
        raise ValueError(f"{field_name} contains invalid whitespace or control data")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid absolute HTTPS URL") from error
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or (parsed.fragment and not allow_fragment)
    ):
        raise ValueError(
            f"{field_name} must be an absolute HTTPS URL without credentials"
        )
    hostname = _normalize_hostname(parsed.hostname, field_name=f"{field_name} host")
    return value, hostname


def _normalize_datetime(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _normalize_authors(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError("author_names must contain strings")
        name = value.strip()
        if not name:
            continue
        if _contains_control_characters(name):
            raise ValueError("author_names contains an invalid control character")
        if name not in seen:
            normalized.append(name)
            seen.add(name)
    return tuple(normalized)


def _normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _required_text(value, field_name="language")
    match = _LANGUAGE_PATTERN.fullmatch(normalized)
    if match is None:
        raise ValueError("language must be a valid language tag")
    language = match.group("language").lower()
    region = match.group("region")
    return language if region is None else f"{language}-{region.upper()}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleItem:
    """Normalized metadata for one online-news article.

    Source-reported ``modified_at`` values are preserved even when they predate
    ``published_at``; chronology assessment belongs to a later quality layer.
    """

    source: str
    source_domain: str
    requested_url: str
    canonical_url: str
    headline: str
    published_at: datetime
    description: str | None = None
    author_names: tuple[str, ...] = field(default_factory=tuple)
    modified_at: datetime | None = None
    section: str | None = None
    lead_image_url: str | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        source = _normalize_source(self.source)
        source_domain = _normalize_hostname(
            self.source_domain,
            field_name="source_domain",
        )
        requested_url, _ = _validate_https_url(
            self.requested_url,
            field_name="requested_url",
            allow_fragment=True,
        )
        canonical_url, canonical_host = _validate_https_url(
            self.canonical_url,
            field_name="canonical_url",
            allow_fragment=False,
        )
        if canonical_host != source_domain:
            raise ValueError("canonical_url host must equal source_domain")

        lead_image_url = None
        if self.lead_image_url is not None:
            lead_image_url, _ = _validate_https_url(
                self.lead_image_url,
                field_name="lead_image_url",
                allow_fragment=False,
            )

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_domain", source_domain)
        object.__setattr__(self, "requested_url", requested_url)
        object.__setattr__(self, "canonical_url", canonical_url)
        object.__setattr__(
            self, "headline", _required_text(self.headline, field_name="headline")
        )
        object.__setattr__(
            self,
            "published_at",
            _normalize_datetime(self.published_at, field_name="published_at"),
        )
        object.__setattr__(
            self,
            "description",
            _optional_text(self.description, field_name="description"),
        )
        object.__setattr__(
            self, "author_names", _normalize_authors(tuple(self.author_names))
        )
        if self.modified_at is not None:
            object.__setattr__(
                self,
                "modified_at",
                _normalize_datetime(self.modified_at, field_name="modified_at"),
            )
        object.__setattr__(
            self, "section", _optional_text(self.section, field_name="section")
        )
        object.__setattr__(self, "lead_image_url", lead_image_url)
        object.__setattr__(self, "language", _normalize_language(self.language))

    def to_dict(self) -> dict[str, object]:
        """Serialize this article deterministically using transport-safe values."""
        return {
            "source": self.source,
            "source_domain": self.source_domain,
            "requested_url": self.requested_url,
            "canonical_url": self.canonical_url,
            "headline": self.headline,
            "published_at": self.published_at.isoformat(),
            "description": self.description,
            "author_names": self.author_names,
            "modified_at": (
                None if self.modified_at is None else self.modified_at.isoformat()
            ),
            "section": self.section,
            "lead_image_url": self.lead_image_url,
            "language": self.language,
        }

    def to_crawler_item(self) -> CrawlerItem:
        """Wrap this typed article in the existing generic crawler item envelope."""
        return CrawlerItem(self.to_dict())
