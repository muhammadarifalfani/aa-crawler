"""Tests for the immutable exact-host source registry."""

from dataclasses import FrozenInstanceError

import pytest

from aa_crawler.sources import SourceProfile, SourceRegistry, SourceRegistryError


def _profile(
    source: str = "example_news",
    domains: tuple[str, ...] = ("news.example",),
    *,
    enabled: bool = True,
) -> SourceProfile:
    return SourceProfile(source=source, domains=domains, enabled=enabled)


def test_empty_registry_has_no_profiles_or_matches() -> None:
    registry = SourceRegistry([])

    assert registry.profiles == ()
    assert registry.enabled_profiles == ()
    assert registry.get_by_source("example_news") is None
    assert registry.get_by_host("news.example") is None
    assert registry.get_by_url("https://news.example/article") is None


@pytest.mark.parametrize("factory", [list, tuple])
def test_constructor_accepts_ordered_collection_types(factory: type) -> None:
    first = _profile()
    second = _profile("other_news", ("other.example",))

    registry = SourceRegistry(factory((first, second)))

    assert registry.profiles == (first, second)
    assert registry.get_by_source("example_news") is first
    assert registry.get_by_host("other.example") is second


def test_generator_is_consumed_exactly_once() -> None:
    profile = _profile()
    iterations = 0

    def profiles():
        nonlocal iterations
        iterations += 1
        yield profile

    registry = SourceRegistry(profiles())

    assert iterations == 1
    assert registry.profiles == (profile,)


def test_registry_and_profiles_property_are_immutable() -> None:
    profile = _profile()
    registry = SourceRegistry([profile])

    assert registry.profiles[0] is profile
    with pytest.raises(FrozenInstanceError):
        registry._profiles = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        registry.profiles.append(profile)  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        registry._source_index[profile.source] = profile  # type: ignore[index]


def test_constructor_rejects_non_profile_inputs() -> None:
    with pytest.raises(TypeError, match="SourceProfile"):
        SourceRegistry("example_news")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="SourceProfile"):
        SourceRegistry([object()])  # type: ignore[list-item]


def test_duplicate_source_is_rejected_even_with_different_domains() -> None:
    first = _profile()
    second = _profile(domains=("other.example",))

    with pytest.raises(SourceRegistryError, match="duplicate source declaration"):
        SourceRegistry([first, second])


def test_exact_duplicate_profile_is_rejected() -> None:
    profile = _profile()

    with pytest.raises(SourceRegistryError, match="duplicate source declaration"):
        SourceRegistry([profile, profile])


def test_duplicate_host_ownership_is_rejected_safely() -> None:
    first = _profile()
    second = _profile("other_news", ("news.example",))

    with pytest.raises(
        SourceRegistryError,
        match="duplicate hostname declaration",
    ) as exc:
        SourceRegistry([first, second])

    assert "other_news" not in str(exc.value)


def test_explicit_parent_and_subdomain_ownership_may_differ() -> None:
    parent = _profile("parent_news", ("news.example",))
    regional = _profile("regional_news", ("regional.news.example",))
    registry = SourceRegistry([parent, regional])

    assert registry.get_by_host("news.example") is parent
    assert registry.get_by_host("regional.news.example") is regional


def test_all_profile_domains_are_indexed() -> None:
    profile = _profile(domains=("news.example", "regional.news.example"))
    registry = SourceRegistry([profile])

    assert registry.get_by_host("news.example") is profile
    assert registry.get_by_host("regional.news.example") is profile


def test_disabled_profile_is_retained_but_excluded_by_default() -> None:
    enabled = _profile()
    disabled = _profile(
        "disabled_news",
        ("disabled.example",),
        enabled=False,
    )
    registry = SourceRegistry([enabled, disabled])

    assert registry.profiles == (enabled, disabled)
    assert registry.enabled_profiles == (enabled,)
    assert registry.get_by_source("disabled_news") is None
    assert registry.get_by_host("disabled.example") is None
    assert registry.get_by_url("https://disabled.example/article") is None
    assert registry.get_by_source("disabled_news", include_disabled=True) is disabled
    assert registry.get_by_host("disabled.example", include_disabled=True) is disabled
    assert (
        registry.get_by_url(
            "https://disabled.example/article",
            include_disabled=True,
        )
        is disabled
    )


@pytest.mark.parametrize("include_disabled", [0, 1, "true", None])
def test_include_disabled_requires_a_strict_boolean(include_disabled: object) -> None:
    registry = SourceRegistry([_profile()])

    with pytest.raises(TypeError, match="include_disabled"):
        registry.get_by_source(
            "example_news",
            include_disabled=include_disabled,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "source",
    ["unknown", "EXAMPLE_NEWS", "example-news", "", "bad\nsource", None],
)
def test_invalid_or_unknown_source_lookup_returns_none(source: object) -> None:
    assert SourceRegistry([_profile()]).get_by_source(source) is None


def test_source_lookup_returns_exact_registered_instance() -> None:
    profile = _profile()

    assert SourceRegistry([profile]).get_by_source("example_news") is profile


def test_host_lookup_normalizes_but_matches_exact_hosts_only() -> None:
    profile = _profile(domains=("news.example", "regional.news.example"))
    registry = SourceRegistry([profile])

    assert registry.get_by_host("NEWS.EXAMPLE.") is profile
    assert registry.get_by_host("regional.news.example") is profile
    assert registry.get_by_host("other.example") is None
    assert registry.get_by_host("sub.news.example") is None
    assert registry.get_by_host("example") is None


@pytest.mark.parametrize(
    "hostname",
    [
        "https://news.example",
        "news.example:443",
        "user:secret@news.example",
        "*.news.example",
        "localhost",
        "service.local",
        "127.0.0.1",
        "bad host.example",
        "",
        None,
    ],
)
def test_invalid_host_lookup_returns_none(hostname: object) -> None:
    assert SourceRegistry([_profile()]).get_by_host(hostname) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://news.example/article",
        "https://user:secret@news.example/article",
        "/relative/article",
        "https:///article",
        "https://news.example:bad/article",
        "https://other.example/article",
        "",
        None,
    ],
)
def test_invalid_or_foreign_url_lookup_returns_none(url: object) -> None:
    assert SourceRegistry([_profile()]).get_by_url(url) is None


def test_url_lookup_uses_only_normalized_exact_hostname() -> None:
    profile = _profile()
    registry = SourceRegistry([profile])

    assert registry.get_by_url("https://NEWS.EXAMPLE/article?id=1") is profile
    assert registry.get_by_url("https://news.example/article#section") is profile
    assert registry.get_by_url("https://sub.news.example/article") is None


def test_registry_scales_to_one_thousand_profiles_deterministically() -> None:
    profiles = tuple(
        _profile(f"source_{index}", (f"news-{index}.example",)) for index in range(1000)
    )

    registry = SourceRegistry(profile for profile in profiles)

    assert registry.profiles == profiles
    assert registry.get_by_source("source_999") is profiles[999]
    assert registry.get_by_host("news-500.example") is profiles[500]
    assert not hasattr(registry, "parser")
    assert not hasattr(registry, "adapter")


def test_public_api_is_explicit_and_minimal() -> None:
    import aa_crawler.sources as sources

    assert sources.__all__ == [
        "SourceProfile",
        "SourceRegistry",
        "SourceRegistryError",
    ]
    assert sources.SourceRegistry is SourceRegistry
    assert sources.SourceRegistryError is SourceRegistryError
    assert not hasattr(SourceRegistry, "register")
    assert not hasattr(SourceRegistry, "unregister")
