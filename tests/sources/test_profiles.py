"""Tests for the initial production source declarations."""

import json

import pytest

from aa_crawler.composition import ParserComposer, ParserCompositionError
from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import JsonLdArticleParser
from aa_crawler.sources import (
    CNN_INDONESIA_PROFILE,
    DEFAULT_SOURCE_PROFILES,
    DETIK_PROFILE,
    KOMPAS_PROFILE,
    SourceProfile,
    SourceRegistry,
)


def test_cnn_indonesia_profile_is_enabled_generic_jsonld_data() -> None:
    profile = CNN_INDONESIA_PROFILE

    assert type(profile) is SourceProfile
    assert profile.source == "cnn_indonesia"
    assert profile.domains == ("www.cnnindonesia.com",)
    assert profile.parser_family == "jsonld_article"
    assert profile.adapter_key is None
    assert profile.enabled is True
    assert profile.supports_host("www.cnnindonesia.com")
    assert not profile.supports_host("regional.cnnindonesia.com")


def test_kompas_profile_is_enabled_with_only_validated_exact_hosts() -> None:
    """Kompas was enabled in Sprint 11 (a project-owner governance decision);
    exact-host validation is otherwise unaffected by enabled state.
    """
    profile = KOMPAS_PROFILE

    assert type(profile) is SourceProfile
    assert profile.source == "kompas"
    assert profile.domains == (
        "www.kompas.com",
        "nasional.kompas.com",
        "surabaya.kompas.com",
    )
    assert profile.parser_family == "jsonld_article"
    assert profile.adapter_key is None
    assert profile.enabled is True
    assert all(profile.supports_host(hostname) for hostname in profile.domains)
    assert not profile.supports_host("regional.kompas.com")
    assert not profile.supports_host("kompas.com")


def test_detik_profile_is_enabled_with_only_validated_exact_host() -> None:
    """Detik was added in Sprint 17 (a project-owner governance decision),
    with exactly one approved host — its other verticals (e.g.
    finance.detik.com) were deliberately not included.
    """
    profile = DETIK_PROFILE

    assert type(profile) is SourceProfile
    assert profile.source == "detik"
    assert profile.domains == ("news.detik.com",)
    assert profile.parser_family == "jsonld_article"
    assert profile.adapter_key is None
    assert profile.enabled is True
    assert profile.supports_host("news.detik.com")
    assert not profile.supports_host("finance.detik.com")
    assert not profile.supports_host("www.detik.com")


def test_default_profiles_are_immutable_ordered_plain_values() -> None:
    assert isinstance(DEFAULT_SOURCE_PROFILES, tuple)
    assert DEFAULT_SOURCE_PROFILES == (
        CNN_INDONESIA_PROFILE,
        KOMPAS_PROFILE,
        DETIK_PROFILE,
    )
    assert DEFAULT_SOURCE_PROFILES[0] is CNN_INDONESIA_PROFILE
    assert DEFAULT_SOURCE_PROFILES[1] is KOMPAS_PROFILE
    assert DEFAULT_SOURCE_PROFILES[2] is DETIK_PROFILE
    assert len({profile.source for profile in DEFAULT_SOURCE_PROFILES}) == 3
    assert all(type(profile) is SourceProfile for profile in DEFAULT_SOURCE_PROFILES)
    with pytest.raises(AttributeError):
        DEFAULT_SOURCE_PROFILES.append(CNN_INDONESIA_PROFILE)  # type: ignore[attr-defined]


def test_default_profiles_construct_conflict_free_registry() -> None:
    """All current production profiles are enabled; each resolves through
    normal (non-`include_disabled`) lookup.
    """
    registry = SourceRegistry(DEFAULT_SOURCE_PROFILES)

    assert registry.profiles == DEFAULT_SOURCE_PROFILES
    assert registry.get_by_source("cnn_indonesia") is CNN_INDONESIA_PROFILE
    assert registry.get_by_host("www.cnnindonesia.com") is CNN_INDONESIA_PROFILE
    assert (
        registry.get_by_url("https://www.cnnindonesia.com/synthetic/article")
        is CNN_INDONESIA_PROFILE
    )
    assert KOMPAS_PROFILE in registry.profiles
    assert registry.get_by_source("kompas") is KOMPAS_PROFILE
    assert registry.get_by_host("www.kompas.com") is KOMPAS_PROFILE
    assert (
        registry.get_by_url("https://www.kompas.com/synthetic/article")
        is KOMPAS_PROFILE
    )
    assert DETIK_PROFILE in registry.profiles
    assert registry.get_by_source("detik") is DETIK_PROFILE
    assert registry.get_by_host("news.detik.com") is DETIK_PROFILE
    assert (
        registry.get_by_url("https://news.detik.com/synthetic/article") is DETIK_PROFILE
    )


def test_disabled_profile_lookup_mechanism_still_works_for_a_synthetic_source() -> None:
    """`include_disabled` itself remains fully covered using a synthetic
    profile, independent of any current production source's real state.
    """
    disabled_profile = SourceProfile(
        source="disabled_example",
        domains=("disabled.example",),
        enabled=False,
    )
    registry = SourceRegistry((CNN_INDONESIA_PROFILE, disabled_profile))

    assert registry.get_by_source("disabled_example") is None
    assert registry.get_by_host("disabled.example") is None
    assert registry.get_by_url("https://disabled.example/synthetic/article") is None
    assert (
        registry.get_by_source("disabled_example", include_disabled=True)
        is disabled_profile
    )
    assert (
        registry.get_by_host("disabled.example", include_disabled=True)
        is disabled_profile
    )


def test_cnn_profile_composes_without_source_specific_parser() -> None:
    parser = ParserComposer().create(CNN_INDONESIA_PROFILE)

    assert type(parser) is JsonLdArticleParser
    assert parser.source == "cnn_indonesia"
    assert parser.source_domains == frozenset({"www.cnnindonesia.com"})


def test_kompas_profile_now_composes_like_any_other_enabled_source() -> None:
    """Kompas is enabled (Sprint 11); composition succeeds like CNN's."""
    parser = ParserComposer().create(KOMPAS_PROFILE)

    assert type(parser) is JsonLdArticleParser
    assert parser.source == "kompas"
    assert parser.source_domains == frozenset(KOMPAS_PROFILE.domains)


def test_detik_profile_composes_like_any_other_enabled_source() -> None:
    """Detik is enabled (Sprint 17); composition succeeds like CNN's."""
    parser = ParserComposer().create(DETIK_PROFILE)

    assert type(parser) is JsonLdArticleParser
    assert parser.source == "detik"
    assert parser.source_domains == frozenset(DETIK_PROFILE.domains)


def test_disabled_profile_cannot_be_composed() -> None:
    disabled_profile = SourceProfile(
        source="disabled_example",
        domains=("disabled.example",),
        enabled=False,
    )

    with pytest.raises(ParserCompositionError, match="disabled"):
        ParserComposer().create(disabled_profile)


def test_cnn_profile_executes_synthetic_generic_article_flow() -> None:
    canonical_url = "https://www.cnnindonesia.com/synthetic/article"
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": canonical_url},
        "headline": "Synthetic production-profile headline",
        "datePublished": "2026-08-07T12:30:00+07:00",
    }
    document = HtmlDocument(
        requested_url="https://www.cnnindonesia.com/synthetic/redirect",
        final_url=canonical_url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        content=(
            '<html lang="id-ID"><head>'
            f'<link rel="canonical" href="{canonical_url}">'
            '<script type="application/ld+json">'
            f"{json.dumps(node)}"
            "</script></head><body></body></html>"
        ),
        encoding="utf-8",
    )

    items = list(ParserComposer().create(CNN_INDONESIA_PROFILE).parse(document))

    assert len(items) == 1
    assert isinstance(items[0], CrawlerItem)
    assert items[0].data == {
        "source": "cnn_indonesia",
        "source_domain": "www.cnnindonesia.com",
        "requested_url": "https://www.cnnindonesia.com/synthetic/redirect",
        "canonical_url": canonical_url,
        "headline": "Synthetic production-profile headline",
        "published_at": "2026-08-07T05:30:00+00:00",
        "description": None,
        "author_names": (),
        "modified_at": None,
        "section": None,
        "lead_image_url": None,
        "language": "id-ID",
    }


def test_profiles_module_exports_only_approved_constants() -> None:
    import aa_crawler.sources.profiles as profiles

    assert profiles.__all__ == [
        "CNN_INDONESIA_PROFILE",
        "DEFAULT_SOURCE_PROFILES",
        "DETIK_PROFILE",
        "KOMPAS_PROFILE",
    ]
    assert not hasattr(profiles, "DEFAULT_SOURCE_REGISTRY")
    assert not hasattr(profiles, "CNNParser")
    assert not hasattr(profiles, "KompasParser")
    assert not hasattr(profiles, "DetikParser")
