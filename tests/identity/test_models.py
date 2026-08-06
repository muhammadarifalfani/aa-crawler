"""Tests for immutable request identity models."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aa_crawler.identity import RequestIdentity


def test_default_identity_has_canonical_user_agent_without_contact() -> None:
    identity = RequestIdentity(product_version="0.1.0")

    assert identity.product_name == "AA-Crawler"
    assert identity.product_version == "0.1.0"
    assert identity.project_url == ("https://github.com/muhammadarifalfani/aa-crawler")
    assert identity.contact is None
    assert identity.user_agent == (
        "AA-Crawler/0.1.0 (+https://github.com/muhammadarifalfani/aa-crawler)"
    )


def test_custom_product_and_version_format_canonical_user_agent() -> None:
    identity = RequestIdentity(
        product_name="ExampleCrawler",
        product_version="2.1.0-beta.1",
    )

    assert identity.user_agent == (
        "ExampleCrawler/2.1.0-beta.1 "
        "(+https://github.com/muhammadarifalfani/aa-crawler)"
    )


def test_project_url_and_contact_are_separate_fields() -> None:
    identity = RequestIdentity(
        product_version="1.0.0",
        project_url="https://crawler.example.test/project",
        contact="https://crawler.example.test/contact",
    )

    assert identity.project_url == "https://crawler.example.test/project"
    assert identity.contact == "https://crawler.example.test/contact"
    assert identity.user_agent == (
        "AA-Crawler/1.0.0 (+https://crawler.example.test/project; "
        "contact=https://crawler.example.test/contact)"
    )


@pytest.mark.parametrize(
    ("product_name", "product_version"),
    [
        ("", "1.0.0"),
        ("invalid product", "1.0.0"),
        ("AA-Crawler", ""),
        ("AA-Crawler", "1.0 (preview)"),
    ],
)
def test_identity_rejects_invalid_http_tokens(
    product_name: str,
    product_version: str,
) -> None:
    with pytest.raises(ValueError, match="HTTP token"):
        RequestIdentity(
            product_name=product_name,
            product_version=product_version,
        )


@pytest.mark.parametrize("control_character", ["\r", "\n", "\0", "\x1f", "\x7f"])
def test_identity_rejects_control_characters(control_character: str) -> None:
    with pytest.raises(ValueError):
        RequestIdentity(product_version=f"1.0{control_character}")

    with pytest.raises(ValueError, match="control character"):
        RequestIdentity(
            product_version="1.0",
            project_url=f"https://example.test/{control_character}",
        )


@pytest.mark.parametrize(
    "project_url",
    [
        "",
        "example.test/project",
        "http://example.test/project",
        "https://user:secret@example.test/project",
        "https://example.test/project?token=secret",
        "https://example.test/project#details",
        "https://localhost/project",
        "https://build-machine.local/project",
        "https://127.0.0.1/project",
    ],
)
def test_identity_rejects_invalid_project_url(project_url: str) -> None:
    with pytest.raises(ValueError, match="project_url"):
        RequestIdentity(product_version="1.0", project_url=project_url)


@pytest.mark.parametrize(
    "contact",
    [
        "",
        "crawler.example.test/contact",
        "mailto:operator@example.test",
        "https://user:secret@crawler.example.test/contact",
        "https://crawler.example.test/contact?token=secret",
        "https://crawler.example.test/contact#details",
        "https://developer-machine.local/contact",
    ],
)
def test_identity_rejects_malformed_contact(contact: str) -> None:
    with pytest.raises(ValueError, match="contact"):
        RequestIdentity(product_version="1.0", contact=contact)


@pytest.mark.parametrize(
    "product_name",
    ["Mozilla", "Chrome", "Firefox", "Safari", "Googlebot", "BingBot-News"],
)
def test_identity_rejects_browser_and_third_party_bot_impersonation(
    product_name: str,
) -> None:
    with pytest.raises(ValueError, match="impersonate"):
        RequestIdentity(product_name=product_name, product_version="1.0")


def test_identity_accepts_maximum_formatted_length() -> None:
    prefix = "AA-Crawler/1 (+https://example.test/"
    suffix = ")"
    path = "a" * (256 - len(prefix) - len(suffix))
    identity = RequestIdentity(
        product_version="1",
        project_url=f"https://example.test/{path}",
    )

    assert len(identity.user_agent) == 256


def test_identity_rejects_formatted_value_over_maximum_length() -> None:
    prefix = "AA-Crawler/1 (+https://example.test/"
    suffix = ")"
    path = "a" * (257 - len(prefix) - len(suffix))

    with pytest.raises(ValueError, match="256"):
        RequestIdentity(
            product_version="1",
            project_url=f"https://example.test/{path}",
        )


def test_identity_is_immutable_hashable_value_object() -> None:
    first = RequestIdentity(product_version="1.0")
    second = RequestIdentity(product_version="1.0")

    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}
    with pytest.raises(FrozenInstanceError):
        first.product_name = "Changed"  # type: ignore[misc]


def test_string_conversion_is_safe_and_canonical() -> None:
    identity = RequestIdentity(product_version="1.0")

    assert str(identity) == identity.user_agent
    assert "secret" not in str(identity).casefold()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("product_name", 1),
        ("product_version", 1),
        ("project_url", 1),
        ("contact", 1),
    ],
)
def test_identity_rejects_non_string_values(field_name: str, value: object) -> None:
    values = {field_name: value, "product_version": "1.0"}
    if field_name == "product_version":
        values[field_name] = value

    with pytest.raises(TypeError, match=field_name):
        RequestIdentity(**cast("dict[str, str]", values))
