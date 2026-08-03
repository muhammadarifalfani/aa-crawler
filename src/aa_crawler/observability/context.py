"""Async-safe correlation context for observability records."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar, Token

_CORRELATION_ID: ContextVar[str | None] = ContextVar(
    "aa_crawler_correlation_id",
    default=None,
)


def set_correlation_id(correlation_id: str) -> Token[str | None]:
    """Set the normalized correlation ID for the current execution context.

    Args:
        correlation_id: Non-empty request or task correlation identifier.

    Returns:
        A token that can restore the previous context value.

    Raises:
        ValueError: If the identifier is empty or contains only whitespace.
    """
    normalized_id = correlation_id.strip()
    if not normalized_id:
        raise ValueError("correlation ID must not be empty")
    return _CORRELATION_ID.set(normalized_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation context represented by a token.

    Args:
        token: Token returned by ``set_correlation_id``.
    """
    _CORRELATION_ID.reset(token)


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current execution context."""
    return _CORRELATION_ID.get()


@contextmanager
def _correlation_scope(correlation_id: str) -> Iterator[None]:
    token = set_correlation_id(correlation_id)
    try:
        yield
    finally:
        reset_correlation_id(token)


def correlation_context(correlation_id: str) -> AbstractContextManager[None]:
    """Create a scope that restores the prior correlation ID when it exits.

    Args:
        correlation_id: Non-empty request or task correlation identifier.

    Returns:
        A context manager for the normalized correlation identifier.
    """
    return _correlation_scope(correlation_id)
