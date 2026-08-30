"""Tests for the immutable source-profile contract."""

from dataclasses import FrozenInstanceError, fields

import pytest

from aa_crawler.sources import SourceProfile


def _profile(**overrides: object) -> SourceProfile:
    values: dict[str, object] = {
        "source": "example_news",
        "domains": ("news.example",),
    }
    values.update(overrides)
    return SourceProfile(**values)  # type: ignore[arg-type]


def test_minimum_profile_uses_narrow_defaults() -> None:
    profile = _profile()

    assert profile.parser_family == "jsonld_article"
    assert profile.adapter_key is None
    assert profile.enabled is True
    assert profile.primary_domain == "news.example"


def test_complete_profile_preserves_declarative_values() -> None:
    profile = _profile(
        domains=("news.example", "regional.news.example"),
        parser_family="jsonld_article",
        adapter_key="special_author_shape",
        enabled=False,
    )

    assert profile.domains == ("news.example", "regional.news.example")
    assert profile.adapter_key == "special_author_shape"
    assert profile.enabled is False


def test_profile_is_immutable_equal_hashable_and_keyword_only() -> None:
    first = _profile()
    second = _profile()

    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}
    with pytest.raises(FrozenInstanceError):
        first.source = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        SourceProfile("example_news", ("news.example",))  # type: ignore[call-arg]


def test_public_export_is_explicit() -> None:
    import aa_crawler.sources as sources

    assert sources.__all__ == [
        "CNN_INDONESIA_PROFILE",
        "DEFAULT_SOURCE_PROFILES",
        "KOMPAS_PROFILE",
        "SourceProfile",
        "SourceRegistry",
        "SourceRegistryError",
    ]
    assert sources.SourceProfile is SourceProfile


@pytest.mark.parametrize(
    "source",
    ["example", "example_news", "regional_news_01", "a", "a" * 64],
)
def test_valid_source_identifiers(source: str) -> None:
    assert _profile(source=source).source == source


@pytest.mark.parametrize(
    "source",
    [
        "",
        "Example",
        "example-news",
        "01_news",
        "example.news",
        "example news",
        "example\nnews",
        "a" * 65,
    ],
)
def test_invalid_source_identifiers_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="source"):
        _profile(source=source)


def test_domains_are_normalized_deduplicated_and_ordered() -> None:
    supplied = [
        "NEWS.EXAMPLE.",
        "regional.news.example",
        "news.example",
    ]
    profile = _profile(domains=supplied)
    supplied.append("other.example")

    assert profile.domains == ("news.example", "regional.news.example")
    with pytest.raises(AttributeError):
        profile.domains.append("other.example")  # type: ignore[attr-defined]


def test_idna_hostname_is_normalized_safely() -> None:
    profile = _profile(domains=("münchen.example",))

    assert profile.domains == ("xn--mnchen-3ya.example",)
    assert profile.supports_host("MÜNCHEN.EXAMPLE.")


@pytest.mark.parametrize(
    "domains",
    [
        (),
        ("",),
        ("https://news.example",),
        ("news.example:443",),
        ("news.example/path",),
        ("news.example?query=1",),
        ("news.example#fragment",),
        ("user:secret@news.example",),
        ("*.news.example",),
        ("-invalid.example",),
        ("localhost",),
        ("service.local",),
        ("service.internal",),
        ("127.0.0.1",),
        ("::1",),
    ],
)
def test_invalid_domain_boundaries_are_rejected(domains: tuple[str, ...]) -> None:
    with pytest.raises((TypeError, ValueError), match="domain|hostname|hostnames"):
        _profile(domains=domains)


def test_domains_reject_scalar_string_and_non_string_entries() -> None:
    with pytest.raises(TypeError, match="domains"):
        _profile(domains="news.example")
    with pytest.raises(TypeError, match="domains"):
        _profile(domains=(42,))


@pytest.mark.parametrize("parser_family", ["", "article", "module.Parser"])
def test_unknown_parser_families_are_rejected(parser_family: str) -> None:
    with pytest.raises(ValueError, match="parser_family"):
        _profile(parser_family=parser_family)


def test_parser_family_requires_a_string() -> None:
    with pytest.raises(TypeError, match="parser_family"):
        _profile(parser_family=object())


def test_generic_json_article_is_a_supported_parser_family() -> None:
    profile = _profile(parser_family="generic_json_article")

    assert profile.parser_family == "generic_json_article"


def test_microdata_article_is_a_supported_parser_family() -> None:
    profile = _profile(parser_family="microdata_article")

    assert profile.parser_family == "microdata_article"


def test_supported_parser_families_lists_exactly_the_three_shipped_families() -> None:
    assert SourceProfile.supported_parser_families == frozenset(
        {"jsonld_article", "generic_json_article", "microdata_article"}
    )


def test_adapter_key_is_optional_and_declarative() -> None:
    assert _profile(adapter_key=None).adapter_key is None
    assert _profile(adapter_key="legacy_canonical").adapter_key == "legacy_canonical"


@pytest.mark.parametrize(
    "adapter_key",
    ["", "Adapter", "module.adapter", "adapter-name", " adapter", "1adapter"],
)
def test_malformed_adapter_keys_are_rejected(adapter_key: str) -> None:
    with pytest.raises(ValueError, match="adapter_key"):
        _profile(adapter_key=adapter_key)


@pytest.mark.parametrize("adapter_key", [object(), lambda: None])
def test_adapter_key_rejects_non_strings(adapter_key: object) -> None:
    with pytest.raises(TypeError, match="adapter_key"):
        _profile(adapter_key=adapter_key)


@pytest.mark.parametrize("enabled", [0, 1, "true", None])
def test_enabled_requires_a_strict_boolean(enabled: object) -> None:
    with pytest.raises(TypeError, match="enabled"):
        _profile(enabled=enabled)


def test_supports_host_uses_exact_matching_only() -> None:
    profile = _profile(domains=("news.example", "regional.news.example"))

    assert profile.supports_host("NEWS.EXAMPLE.")
    assert profile.supports_host("regional.news.example")
    assert not profile.supports_host("other.example")
    assert not profile.supports_host("sub.news.example")
    assert not profile.supports_host("example")


@pytest.mark.parametrize(
    "hostname",
    [
        "https://news.example",
        "news.example:443",
        "user:secret@news.example",
        "*.news.example",
        "localhost",
        "127.0.0.1",
        "bad host.example",
        "",
        None,
    ],
)
def test_supports_host_returns_false_for_invalid_runtime_input(
    hostname: object,
) -> None:
    assert not _profile().supports_host(hostname)


def test_serialization_is_deterministic() -> None:
    profile = _profile(adapter_key="special_author_shape", enabled=False)

    assert profile.to_dict() == {
        "source": "example_news",
        "domains": ("news.example",),
        "parser_family": "jsonld_article",
        "adapter_key": "special_author_shape",
        "enabled": False,
    }


def test_contract_has_no_runtime_or_free_form_fields() -> None:
    field_names = {item.name for item in fields(SourceProfile)}

    assert field_names == {
        "source",
        "domains",
        "parser_family",
        "adapter_key",
        "enabled",
    }
