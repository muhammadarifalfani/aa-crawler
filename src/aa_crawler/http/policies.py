"""Explicit timeout and retry policies for synchronous HTTP requests."""

from dataclasses import dataclass, field

import httpx

_DEFAULT_RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


def _validated_seconds(value: float, *, field_name: str, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")
    normalized = float(value)
    minimum_is_invalid = normalized <= 0 if positive else normalized < 0
    if minimum_is_invalid:
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be {qualifier}")
    return normalized


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """Timeout limits, in seconds, for each HTTP transport phase."""

    connect: float = 5.0
    read: float = 10.0
    write: float = 10.0
    pool: float = 5.0

    def __post_init__(self) -> None:
        for field_name in ("connect", "read", "write", "pool"):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                _validated_seconds(value, field_name=field_name, positive=True),
            )

    def to_httpx(self) -> httpx.Timeout:
        """Convert this policy to HTTPX's native timeout configuration."""
        return httpx.Timeout(
            connect=self.connect,
            read=self.read,
            write=self.write,
            pool=self.pool,
        )


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Deterministic retry limits for transient HTTP failures."""

    max_attempts: int = 3
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    retry_statuses: frozenset[int] = field(
        default_factory=lambda: _DEFAULT_RETRY_STATUSES
    )

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(
            self.max_attempts, int
        ):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        base = _validated_seconds(
            self.backoff_base,
            field_name="backoff_base",
            positive=False,
        )
        maximum = _validated_seconds(
            self.backoff_max,
            field_name="backoff_max",
            positive=False,
        )
        if maximum < base:
            raise ValueError("backoff_max must not be lower than backoff_base")

        statuses = frozenset(self.retry_statuses)
        if any(
            isinstance(status, bool) or not isinstance(status, int)
            for status in statuses
        ):
            raise TypeError("retry_statuses must contain integers")

        object.__setattr__(self, "backoff_base", base)
        object.__setattr__(self, "backoff_max", maximum)
        object.__setattr__(self, "retry_statuses", statuses)

    def should_retry_status(self, status_code: int) -> bool:
        """Return whether a response status is eligible for retry."""
        return status_code in self.retry_statuses

    def backoff_seconds(self, attempt_number: int) -> float:
        """Return the delay before a 1-based attempt number."""
        if isinstance(attempt_number, bool) or not isinstance(attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        if attempt_number == 1:
            return 0.0
        uncapped_backoff = self.backoff_base * float(2 ** (attempt_number - 2))
        return min(uncapped_backoff, self.backoff_max)
