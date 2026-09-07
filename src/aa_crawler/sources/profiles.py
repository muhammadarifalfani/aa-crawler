"""Approved immutable production source declarations.

Kompas was enabled in Sprint 11: an explicit project-owner governance
decision (not an architectural change) to activate a real second
production source, made after the project owner confirmed there was no
objection to crawling it. Detik was added in Sprint 17 as a third
production source, following the same governance decision — the project
owner chose Detik specifically and confirmed the exact host
(`news.detik.com`; Detik's other verticals, e.g. `finance.detik.com`,
`health.detik.com`, are deliberately not included, since ADR-020 requires
exact hosts and none of those were approved). Enablement records
governance state only; it does not itself constitute legal authorization,
publisher permission, robots authorization, rate-limit approval, or
operational approval — see ADR-020's "Enabled and disabled governance"
section. Detik's `jsonld_article` parser-family assignment follows
ADR-020's "ordinary source onboarding" path (structurally compatible with
the existing generic `jsonld_article` parser, like CNN Indonesia and
Kompas); this has not yet been confirmed against a live fetch, consistent
with this project's standing no-live-network-request testing constraint —
real-world content-shape verification remains pending until live crawling
is separately authorized.
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

DETIK_PROFILE = SourceProfile(
    source="detik",
    domains=("news.detik.com",),
    parser_family="jsonld_article",
    adapter_key=None,
    enabled=True,
)

DEFAULT_SOURCE_PROFILES = (
    CNN_INDONESIA_PROFILE,
    KOMPAS_PROFILE,
    DETIK_PROFILE,
)

__all__ = [
    "CNN_INDONESIA_PROFILE",
    "DEFAULT_SOURCE_PROFILES",
    "DETIK_PROFILE",
    "KOMPAS_PROFILE",
]
