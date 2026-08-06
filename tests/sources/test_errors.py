"""Tests for source-registry errors."""

from aa_crawler.sources import SourceRegistryError


def test_source_registry_error_is_a_value_error() -> None:
    error = SourceRegistryError("safe conflict")

    assert isinstance(error, ValueError)
    assert str(error) == "safe conflict"
