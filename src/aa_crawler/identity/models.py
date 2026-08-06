"""Immutable identity used for outbound crawler requests."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

_HTTP_TOKEN_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_DEFAULT_PRODUCT_NAME = "AA-Crawler"
_DEFAULT_PROJECT_URL = "https://github.com/muhammadarifalfani/aa-crawler"
_MAX_USER_AGENT_LENGTH = 256
_IMPERSONATED_PRODUCT_MARKERS = (
    "baiduspider",
    "bingbot",
    "chrome",
    "duckduckbot",
    "edge",
    "facebookexternalhit",
    "firefox",
    "googlebot",
    "mozilla",
    "safari",
    "twitterbot",
    "yandexbot",
)


def _validate_token(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value or not _HTTP_TOKEN_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a valid non-empty HTTP token")
    return value


def _validate_product_name(value: str) -> str:
    product_name = _validate_token(value, field_name="product_name")
    normalized = product_name.casefold()
    if any(marker in normalized for marker in _IMPERSONATED_PRODUCT_MARKERS):
        raise ValueError("product_name must not impersonate another client")
    return product_name


def _validate_public_https_url(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ValueError(f"{field_name} contains an invalid control character")

    parsed = urlsplit(value)
    hostname = parsed.hostname
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{field_name} must be an absolute HTTPS URL without credentials, "
            "query, or fragment"
        )

    normalized_hostname = hostname.casefold().rstrip(".")
    try:
        ipaddress.ip_address(normalized_hostname)
    except ValueError:
        is_ip_address = False
    else:
        is_ip_address = True
    if (
        is_ip_address
        or normalized_hostname == "localhost"
        or normalized_hostname.endswith(".local")
        or "." not in normalized_hostname
    ):
        raise ValueError(f"{field_name} must identify a public host")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestIdentity:
    """Validated identity for outbound User-Agent headers.

    The formatted value is limited to 256 characters.
    The application composition root supplies the canonical installed package
    version. Package-metadata lookup is intentionally outside this value object.
    """

    product_version: str
    product_name: str = _DEFAULT_PRODUCT_NAME
    project_url: str = _DEFAULT_PROJECT_URL
    contact: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "product_name",
            _validate_product_name(self.product_name),
        )
        object.__setattr__(
            self,
            "product_version",
            _validate_token(self.product_version, field_name="product_version"),
        )
        object.__setattr__(
            self,
            "project_url",
            _validate_public_https_url(self.project_url, field_name="project_url"),
        )
        if self.contact is not None:
            object.__setattr__(
                self,
                "contact",
                _validate_public_https_url(self.contact, field_name="contact"),
            )
        if len(self.user_agent) > _MAX_USER_AGENT_LENGTH:
            raise ValueError(
                f"formatted User-Agent must not exceed {_MAX_USER_AGENT_LENGTH} "
                "characters"
            )

    @property
    def user_agent(self) -> str:
        """Return the canonical HTTP User-Agent value."""
        identity = f"{self.product_name}/{self.product_version} (+{self.project_url}"
        if self.contact is not None:
            identity = f"{identity}; contact={self.contact}"
        return f"{identity})"

    def __str__(self) -> str:
        """Return the canonical HTTP User-Agent value."""
        return self.user_agent
