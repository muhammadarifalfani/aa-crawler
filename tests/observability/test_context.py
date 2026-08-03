from __future__ import annotations

from contextvars import copy_context
from typing import TYPE_CHECKING

import pytest

from aa_crawler.observability import (
    correlation_context,
    get_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def clear_correlation_context() -> Iterator[None]:
    token = set_correlation_id("test-isolation")
    reset_correlation_id(token)
    yield
    assert get_correlation_id() is None


def test_default_correlation_id_is_none() -> None:
    assert get_correlation_id() is None


def test_setter_normalizes_and_reset_restores_value() -> None:
    outer_token = set_correlation_id("outer")
    inner_token = set_correlation_id("  request-42  ")

    assert get_correlation_id() == "request-42"
    reset_correlation_id(inner_token)
    assert get_correlation_id() == "outer"
    reset_correlation_id(outer_token)
    assert get_correlation_id() is None


@pytest.mark.parametrize("correlation_id", ["", " ", "\t\r\n"])
def test_empty_correlation_ids_fail(correlation_id: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        set_correlation_id(correlation_id)


def test_nested_contexts_restore_prior_values() -> None:
    with correlation_context("outer"):
        assert get_correlation_id() == "outer"
        with correlation_context("inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"

    assert get_correlation_id() is None


def test_context_restores_state_after_exception() -> None:
    with (
        pytest.raises(RuntimeError, match="expected"),
        correlation_context("failed-task"),
    ):
        raise RuntimeError("expected")

    assert get_correlation_id() is None


def test_copied_contexts_do_not_leak_values() -> None:
    first_context = copy_context()
    second_context = copy_context()

    def set_and_read(value: str) -> str | None:
        set_correlation_id(value)
        return get_correlation_id()

    assert first_context.run(set_and_read, "first") == "first"
    assert second_context.run(set_and_read, "second") == "second"
    assert first_context.run(get_correlation_id) == "first"
    assert second_context.run(get_correlation_id) == "second"
    assert get_correlation_id() is None
