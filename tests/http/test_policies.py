from dataclasses import FrozenInstanceError

import pytest

from aa_crawler.http import RetryPolicy, TimeoutPolicy


def test_timeout_policy_defaults_and_conversion() -> None:
    policy = TimeoutPolicy()

    assert policy == TimeoutPolicy(connect=5.0, read=10.0, write=10.0, pool=5.0)
    assert policy.to_httpx().as_dict() == {
        "connect": 5.0,
        "read": 10.0,
        "write": 10.0,
        "pool": 5.0,
    }


@pytest.mark.parametrize("field_name", ["connect", "read", "write", "pool"])
@pytest.mark.parametrize("value", [0, -1, True])
def test_timeout_policy_rejects_non_positive_values(
    field_name: str,
    value: float,
) -> None:
    values = {"connect": 1.0, "read": 1.0, "write": 1.0, "pool": 1.0}
    values[field_name] = value

    with pytest.raises((TypeError, ValueError)):
        TimeoutPolicy(**values)


def test_timeout_policy_is_frozen() -> None:
    policy = TimeoutPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.read = 2.0  # type: ignore[misc]


def test_retry_policy_defaults() -> None:
    policy = RetryPolicy()

    assert policy.max_attempts == 3
    assert policy.backoff_base == 0.5
    assert policy.backoff_max == 8.0
    assert policy.retry_statuses == frozenset({408, 429, 500, 502, 503, 504})
    assert policy.retryable_methods == frozenset({"GET", "HEAD"})


@pytest.mark.parametrize(
    ("overrides", "error_type"),
    [
        ({"max_attempts": 0}, ValueError),
        ({"backoff_base": -1}, ValueError),
        ({"backoff_max": -1}, ValueError),
        ({"backoff_base": 2, "backoff_max": 1}, ValueError),
        ({"retry_statuses": frozenset({"500"})}, TypeError),
    ],
)
def test_retry_policy_validation(
    overrides: dict[str, object],
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        RetryPolicy(**overrides)  # type: ignore[arg-type]


def test_retry_status_lookup() -> None:
    policy = RetryPolicy()

    assert policy.should_retry_status(503)
    assert not policy.should_retry_status(404)


@pytest.mark.parametrize("method", ["GET", "HEAD", "get", "head", "GeT", "HeAd"])
def test_retry_method_lookup_normalizes_eligible_methods(method: str) -> None:
    assert RetryPolicy().is_method_retryable(method)


@pytest.mark.parametrize(
    "method",
    ["POST", "PUT", "PATCH", "DELETE", "CONNECT", "OPTIONS", "TRACE", "CUSTOM"],
)
def test_retry_method_lookup_rejects_non_eligible_methods(method: str) -> None:
    assert not RetryPolicy().is_method_retryable(method)


def test_retryable_methods_are_fixed_and_immutable() -> None:
    policy = RetryPolicy()

    with pytest.raises(AttributeError):
        policy.retryable_methods.add("POST")  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        RetryPolicy(retryable_methods=frozenset({"POST"}))  # type: ignore[call-arg]


def test_retry_policy_exponential_backoff_and_cap() -> None:
    policy = RetryPolicy(backoff_base=1.0, backoff_max=3.0)

    assert [policy.backoff_seconds(attempt) for attempt in range(1, 6)] == [
        0.0,
        1.0,
        2.0,
        3.0,
        3.0,
    ]


def test_retry_policy_rejects_invalid_attempt_number() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        RetryPolicy().backoff_seconds(0)


def test_retry_statuses_are_defensively_frozen() -> None:
    statuses = {500}
    policy = RetryPolicy(retry_statuses=statuses)  # type: ignore[arg-type]
    statuses.add(503)

    assert policy.retry_statuses == frozenset({500})
    with pytest.raises(AttributeError):
        policy.retry_statuses.add(502)  # type: ignore[attr-defined]


def test_retry_policy_is_frozen() -> None:
    policy = RetryPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 4  # type: ignore[misc]
