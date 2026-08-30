"""Deterministic composition of source profiles into parser instances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aa_crawler.composition.errors import ParserCompositionError
from aa_crawler.parser import GenericJsonArticleParser, JsonLdArticleParser
from aa_crawler.sources import SourceProfile

if TYPE_CHECKING:
    from aa_crawler.parser import BaseParser


@dataclass(frozen=True, slots=True, eq=False)
class ParserComposer:
    """Construct new parsers from validated declarative source profiles."""

    def create(self, profile: SourceProfile) -> BaseParser:
        """Create a new parser for one enabled, adapter-free source profile."""
        if not isinstance(profile, SourceProfile):
            raise ParserCompositionError("a valid source profile is required")
        if not profile.enabled:
            raise ParserCompositionError("disabled source profiles cannot be composed")
        if profile.adapter_key is not None:
            raise ParserCompositionError("source adapters are not supported")
        if profile.parser_family == "jsonld_article":
            return JsonLdArticleParser(
                source=profile.source,
                source_domains=profile.domains,
            )
        if profile.parser_family == "generic_json_article":
            return GenericJsonArticleParser(
                source=profile.source,
                source_domains=profile.domains,
            )
        raise ParserCompositionError("unsupported parser family")
