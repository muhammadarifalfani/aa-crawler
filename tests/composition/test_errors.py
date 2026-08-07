"""Tests for parser composition errors."""

from aa_crawler.composition import ParserCompositionError


def test_parser_composition_error_is_a_value_error() -> None:
    error = ParserCompositionError("safe composition failure")

    assert isinstance(error, ValueError)
    assert str(error) == "safe composition failure"
