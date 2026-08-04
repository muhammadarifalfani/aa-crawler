"""Immutable HTML document model."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def _immutable_mapping[Key, Value](value: Mapping[Key, Value]) -> Mapping[Key, Value]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class HtmlDocument:
    """Decoded HTML response with request and transport context."""

    requested_url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    content: str
    encoding: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.requested_url.strip():
            raise ValueError("requested_url must not be empty")
        if not self.final_url.strip():
            raise ValueError("final_url must not be empty")
        if self.status_code <= 0:
            raise ValueError("status_code must be positive")
        if not self.encoding.strip():
            raise ValueError("encoding must not be empty")
        object.__setattr__(self, "headers", _immutable_mapping(self.headers))
        object.__setattr__(self, "metadata", _immutable_mapping(self.metadata))
