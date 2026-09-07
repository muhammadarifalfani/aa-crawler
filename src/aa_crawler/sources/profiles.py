"""Approved immutable production source declarations.

Kompas was enabled in Sprint 11: an explicit project-owner governance
decision (not an architectural change) to activate a real second
production source, made after the project owner confirmed there was no
objection to crawling it. Enablement records governance state only; it
does not itself constitute legal authorization, publisher permission,
robots authorization, rate-limit approval, or operational approval — see
ADR-020's "Enabled and disabled governance" section.
"""

from aa_crawler.sources.models import SourceProfile

CNN_INDONESIA_PROFILE = SourceProfile(
    source="cnn_indonesia",
    domains=("www.cnnindonesia.com",),
    parser_family="jsonld_article",
    adapter_key=None,
    enabled=True,
)

KOMPAS_PROFILE = SourceProfile(
    source="kompas",
    domains=(
        "www.kompas.com",
        "nasional.kompas.com",
        "surabaya.kompas.com",
    ),
    parser_family="jsonld_article",
    adapter_key=None,
    enabled=True,
)

DEFAULT_SOURCE_PROFILES = (
    CNN_INDONESIA_PROFILE,
    KOMPAS_PROFILE,
)

__all__ = [
    "CNN_INDONESIA_PROFILE",
    "DEFAULT_SOURCE_PROFILES",
    "KOMPAS_PROFILE",
]
