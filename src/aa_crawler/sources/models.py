"""Immutable declarations for approved news-source boundaries."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_MAX_IDENTIFIER_LENGTH = 64
_PARSER_FAMILY = "jsonld_article"
_LOCAL_HOST_SUFFIXES = (".home", ".internal", ".lan", ".local", ".localhost")


def _normalize_identifier(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if len(value) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(
            f"{field_name} must not exceed {_MAX_IDENTIFIER_LENGTH} characters"
        )
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must begin with a lowercase ASCII letter and contain "
            "only lowercase ASCII letters, digits, and underscores"
        )
    return value


def _encode_idna_hostname(value: str) -> str:
    try:
        return value.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise ValueError("domains must contain valid IDNA hostnames") from error


def _reject_ip_address(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return
    raise ValueError("domains must contain hostnames, not IP addresses")


def _normalize_hostname(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("domains must contain strings")
    if not value:
        raise ValueError("domains must not contain empty hostnames")
    if value != value.strip() or any(ord(character) < 32 for character in value):
        raise ValueError("domains must contain valid hostnames")
    if any(character in value for character in "/?#@:*\\"):
        raise ValueError("domains must contain hostnames without URL components")

    hostname = value.rstrip(".")
    if not hostname:
        raise ValueError("domains must contain valid hostnames")
    normalized = _encode_idna_hostname(hostname)
    _reject_ip_address(normalized)

    labels = normalized.split(".")
    if (
        len(normalized) > 253
        or len(labels) < 2
        or any(not _HOST_LABEL_PATTERN.fullmatch(label) for label in labels)
    ):
        raise ValueError("domains must contain valid hostnames")
    if normalized == "localhost" or normalized.endswith(_LOCAL_HOST_SUFFIXES):
        raise ValueError("domains must not contain local or private-style hostnames")
    return normalized


def _normalize_domains(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("domains must be a collection of hostnames")
    if not isinstance(values, Iterable):
        raise TypeError("domains must be a collection of hostnames")
    candidates = tuple(values)
    if not candidates:
        raise ValueError("at least one domain is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise TypeError("domains must contain strings")
        hostname = _normalize_hostname(candidate)
        if hostname not in seen:
            normalized.append(hostname)
            seen.add(hostname)
    return tuple(normalized)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceProfile:
    """Declarative participation contract for one approved news source."""

    source: str
    domains: tuple[str, ...]
    parser_family: str = _PARSER_FAMILY
    adapter_key: str | None = None
    enabled: bool = True

    supported_parser_families: ClassVar[frozenset[str]] = frozenset({_PARSER_FAMILY})

    def __post_init__(self) -> None:
        source = _normalize_identifier(self.source, field_name="source")
        domains = _normalize_domains(self.domains)
        if not isinstance(self.parser_family, str):
            raise TypeError("parser_family must be a string")
        if self.parser_family not in self.supported_parser_families:
            raise ValueError("parser_family must be jsonld_article")
        adapter_key = self.adapter_key
        if adapter_key is not None:
            adapter_key = _normalize_identifier(adapter_key, field_name="adapter_key")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a boolean")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "domains", domains)
        object.__setattr__(self, "adapter_key", adapter_key)

    @property
    def primary_domain(self) -> str:
        """Return the first explicitly approved hostname."""
        return self.domains[0]

    def supports_host(self, hostname: object) -> bool:
        """Return whether a runtime hostname exactly matches this profile."""
        if not isinstance(hostname, str):
            return False
        try:
            normalized = _normalize_hostname(hostname)
        except (TypeError, ValueError):
            return False
        return normalized in self.domains

    def to_dict(self) -> dict[str, object]:
        """Serialize the profile deterministically without runtime behavior."""
        return {
            "source": self.source,
            "domains": self.domains,
            "parser_family": self.parser_family,
            "adapter_key": self.adapter_key,
            "enabled": self.enabled,
        }
