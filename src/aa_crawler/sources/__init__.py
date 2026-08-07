"""Public declarative source-profile API."""

from aa_crawler.sources.errors import SourceRegistryError
from aa_crawler.sources.models import SourceProfile
from aa_crawler.sources.profiles import (
    CNN_INDONESIA_PROFILE,
    DEFAULT_SOURCE_PROFILES,
    KOMPAS_PROFILE,
)
from aa_crawler.sources.registry import SourceRegistry

__all__ = [
    "CNN_INDONESIA_PROFILE",
    "DEFAULT_SOURCE_PROFILES",
    "KOMPAS_PROFILE",
    "SourceProfile",
    "SourceRegistry",
    "SourceRegistryError",
]
