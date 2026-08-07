"""Approved immutable production source declarations."""

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
    enabled=False,
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
