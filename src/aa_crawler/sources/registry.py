"""Immutable exact-host registry for declarative source profiles."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from aa_crawler.sources.errors import SourceRegistryError
from aa_crawler.sources.models import (
    SourceProfile,
    _normalize_hostname,
    _normalize_identifier,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def _include_profile(profile: SourceProfile, *, include_disabled: bool) -> bool:
    if not isinstance(include_disabled, bool):
        raise TypeError("include_disabled must be a boolean")
    return profile.enabled or include_disabled


@dataclass(frozen=True, slots=True, init=False, eq=False)
class SourceRegistry:
    """Read-only source and exact-host indexes built in constructor order."""

    _profiles: tuple[SourceProfile, ...]
    _source_index: Mapping[str, SourceProfile]
    _host_index: Mapping[str, SourceProfile]

    def __init__(self, profiles: Iterable[SourceProfile]) -> None:
        ordered: list[SourceProfile] = []
        source_index: dict[str, SourceProfile] = {}
        host_index: dict[str, SourceProfile] = {}
        for profile in profiles:
            if not isinstance(profile, SourceProfile):
                raise TypeError("profiles must contain SourceProfile instances")
            if profile.source in source_index:
                raise SourceRegistryError(
                    f"duplicate source declaration: {profile.source}"
                )
            for hostname in profile.domains:
                if hostname in host_index:
                    raise SourceRegistryError(
                        f"duplicate hostname declaration: {hostname}"
                    )
            ordered.append(profile)
            source_index[profile.source] = profile
            for hostname in profile.domains:
                host_index[hostname] = profile

        object.__setattr__(self, "_profiles", tuple(ordered))
        object.__setattr__(self, "_source_index", MappingProxyType(source_index))
        object.__setattr__(self, "_host_index", MappingProxyType(host_index))

    @property
    def profiles(self) -> tuple[SourceProfile, ...]:
        """Return all profiles in deterministic constructor order."""
        return self._profiles

    @property
    def enabled_profiles(self) -> tuple[SourceProfile, ...]:
        """Return enabled profiles in deterministic constructor order."""
        return tuple(profile for profile in self._profiles if profile.enabled)

    def get_by_source(
        self,
        source: object,
        *,
        include_disabled: bool = False,
    ) -> SourceProfile | None:
        """Return the profile with an exact canonical source identifier."""
        if not isinstance(source, str):
            return None
        try:
            normalized = _normalize_identifier(source, field_name="source")
        except (TypeError, ValueError):
            return None
        profile = self._source_index.get(normalized)
        if profile is None or not _include_profile(
            profile, include_disabled=include_disabled
        ):
            return None
        return profile

    def get_by_host(
        self,
        hostname: object,
        *,
        include_disabled: bool = False,
    ) -> SourceProfile | None:
        """Return the profile that explicitly owns an exact hostname."""
        if not isinstance(hostname, str):
            return None
        try:
            normalized = _normalize_hostname(hostname)
        except (TypeError, ValueError):
            return None
        profile = self._host_index.get(normalized)
        if profile is None or not _include_profile(
            profile, include_disabled=include_disabled
        ):
            return None
        return profile

    def get_by_url(
        self,
        url: object,
        *,
        include_disabled: bool = False,
    ) -> SourceProfile | None:
        """Resolve an absolute HTTPS URL by its exact normalized hostname.

        Paths, queries, and fragments do not participate in source selection.
        """
        if not isinstance(url, str) or url != url.strip():
            return None
        try:
            parsed = urlsplit(url)
            _ = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        return self.get_by_host(
            parsed.hostname,
            include_disabled=include_disabled,
        )
