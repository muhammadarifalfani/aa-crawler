"""Immutable domain contracts shared by crawler implementations."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


def _immutable_mapping[Key, Value](
    value: Mapping[Key, Value],
) -> Mapping[Key, Value]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class CrawlerRequest:
    """Transport-neutral input requested by a crawler."""

    url: str
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=dict)
    query_params: Mapping[str, str] = field(default_factory=dict)
    body: bytes | str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate scalar fields and freeze all request mappings."""
        if not self.url.strip():
            raise ValueError("url must not be empty")
        object.__setattr__(self, "method", self.method.strip().upper())
        object.__setattr__(self, "headers", _immutable_mapping(self.headers))
        object.__setattr__(
            self,
            "query_params",
            _immutable_mapping(self.query_params),
        )
        object.__setattr__(self, "metadata", _immutable_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class CrawlerResponse:
    """Transport-neutral response returned to crawler processing code."""

    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    elapsed: float
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate response status and freeze all response mappings."""
        if self.status_code <= 0:
            raise ValueError("status_code must be positive")
        object.__setattr__(self, "headers", _immutable_mapping(self.headers))
        object.__setattr__(self, "metadata", _immutable_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class CrawlerItem:
    """Structured data extracted by a crawler."""

    data: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze the extracted item mapping."""
        object.__setattr__(self, "data", _immutable_mapping(self.data))
