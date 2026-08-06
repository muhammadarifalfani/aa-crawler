"""Public declarative source-profile API."""

from aa_crawler.sources.errors import SourceRegistryError
from aa_crawler.sources.models import SourceProfile
from aa_crawler.sources.registry import SourceRegistry

__all__ = ["SourceProfile", "SourceRegistry", "SourceRegistryError"]
