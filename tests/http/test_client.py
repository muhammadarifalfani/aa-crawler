from __future__ import annotations

import httpx
import pytest

from aa_crawler.crawler import CrawlerRequest, RequestError, ResponseError
from aa_crawler.http import HttpClient, RateLimitPolicy, RetryPolicy, TimeoutPolicy
from aa_crawler.http import client as client_module


def test_client_executes_with_mocked_transport() -> None:
    observed_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        return httpx.Response(
            200,
            headers={"X-Response": "preserved"},
            content=b"response-body",
            request=request,
        )

    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(
            CrawlerRequest(
                url="https://example.test/resource",
                headers={"X-Request": "preserved"},
                body=b"request-body",
            )
        )

    assert len(observed_requests) == 1
    assert observed_requests[0].headers["X-Request"] == "preserved"
    assert observed_requests[0].content == b"request-body"
    assert response.status_code == 200
    assert response.headers["x-response"] == "preserved"
    assert response.body == b"response-body"


def test_client_delivers_url_query_string_to_transport() -> None:
    observed_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_urls.append(str(request.url))
        return httpx.Response(200, request=request)

    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        client.send(CrawlerRequest(url="https://example.test/a?id=7&page=all"))
        client.send(
            CrawlerRequest(
                url="https://example.test/b?id=7",
                query_params={"page": "2"},
            )
        )

    assert observed_urls == [
        "https://example.test/a?id=7&page=all",
        "https://example.test/b?id=7&page=2",
    ]


def test_client_applies_default_timeout_policy() -> None:
    observed_timeout: object = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_timeout
        observed_timeout = request.extensions["timeout"]
        return httpx.Response(200, request=request)

    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert observed_timeout == TimeoutPolicy().to_httpx().as_dict()


def test_client_applies_explicit_timeout_policy() -> None:
    observed_timeout: object = None
    policy = TimeoutPolicy(connect=1.0, read=2.0, write=3.0, pool=4.0)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_timeout
        observed_timeout = request.extensions["timeout"]
        return httpx.Response(200, request=request)

    with HttpClient(
        timeout_policy=policy,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert observed_timeout == policy.to_httpx().as_dict()


def test_client_reuses_transport_for_repeated_requests() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(request_count, content=b"ok", request=request)

    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        first = client.send(CrawlerRequest(url="https://example.test/first"))
        second = client.send(CrawlerRequest(url="https://example.test/second"))

    assert request_count == 2
    assert first.status_code == 1
    assert second.status_code == 2


def test_client_translates_transport_error_and_preserves_cause() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with (
        HttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RequestError, match="execution failed") as error_info,
    ):
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert isinstance(error_info.value.__cause__, httpx.ConnectError)


def test_client_preserves_request_metadata_in_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ok", request=request)

    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(
            CrawlerRequest(
                url="https://example.test/resource",
                metadata={"collector": "example", "attempt": 1},
            )
        )

    assert response.metadata == {"collector": "example", "attempt": 1}


def test_client_retries_status_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter([503, 200])
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), content=b"ok", request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(CrawlerRequest(url="https://example.test/resource"))

    assert response.status_code == 200
    assert delays == [0.5]


def test_head_retries_retryable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = iter([503, 200])
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(
            CrawlerRequest(url="https://example.test/resource", method="head")
        )

    assert response.status_code == 200
    assert delays == [0.5]


def test_client_raises_after_retryable_status_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    policy = RetryPolicy(max_attempts=3, backoff_base=1.0, backoff_max=2.0)
    transport = httpx.MockTransport(handler)
    with (
        HttpClient(retry_policy=policy, transport=transport) as client,
        pytest.raises(ResponseError, match="all attempts"),
    ):
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert attempts == 3
    assert delays == [1.0, 2.0]


def test_client_retries_transient_exception_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(CrawlerRequest(url="https://example.test/resource"))

    assert response.status_code == 200
    assert attempts == 2
    assert delays == [0.5]


@pytest.mark.parametrize(
    "error_type",
    [
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        httpx.RemoteProtocolError,
    ],
)
def test_get_retries_every_approved_transient_exception(
    error_type: type[httpx.RequestError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise error_type("temporary", request=request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(CrawlerRequest(url="https://example.test/resource"))

    assert response.status_code == 200
    assert attempts == 2
    assert delays == [0.5]


def test_head_retries_transient_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("temporary", request=request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(
            CrawlerRequest(url="https://example.test/resource", method="HEAD")
        )

    assert response.status_code == 200
    assert attempts == 2
    assert delays == [0.5]


def test_eligible_retry_rebuilds_and_preserves_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_requests: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_requests.append(request)
        status_code = 503 if len(observed_requests) == 1 else 200
        return httpx.Response(status_code, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    request = CrawlerRequest(
        url="https://example.test/resource",
        method="get",
        headers={"X-Request": "preserved"},
        query_params={"page": "1"},
        body=b"request-body",
        metadata={"retry": False, "request_id": "42"},
    )
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = client.send(request)

    assert len(observed_requests) == 2
    assert observed_requests[0] is not observed_requests[1]
    for observed in observed_requests:
        assert observed.method == "GET"
        assert str(observed.url) == "https://example.test/resource?page=1"
        assert observed.headers["X-Request"] == "preserved"
        assert observed.content == b"request-body"
        assert observed.extensions["timeout"] == TimeoutPolicy().to_httpx().as_dict()
    assert response.metadata == request.metadata
    assert delays == [0.5]


def test_retryable_response_is_closed_before_next_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_response: httpx.Response | None = None
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts, first_response
        attempts += 1
        if attempts == 1:
            first_response = httpx.Response(503, request=request)
            return first_response
        assert first_response is not None
        assert first_response.is_closed
        return httpx.Response(200, request=request)

    monkeypatch.setattr(client_module, "_sleep", lambda _seconds: None)
    with HttpClient(transport=httpx.MockTransport(handler)) as client:
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert attempts == 2


def test_client_raises_chained_error_after_transient_exception_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("temporary", request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    policy = RetryPolicy(max_attempts=2, backoff_base=0.25, backoff_max=1.0)
    transport = httpx.MockTransport(handler)
    with (
        HttpClient(retry_policy=policy, transport=transport) as client,
        pytest.raises(RequestError) as error_info,
    ):
        client.send(CrawlerRequest(url="https://example.test/resource"))

    assert attempts == 2
    assert delays == [0.25]
    assert isinstance(error_info.value.__cause__, httpx.ReadTimeout)


def test_client_does_not_retry_non_transient_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.UnsupportedProtocol("unsupported", request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with (
        HttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RequestError) as error_info,
    ):
        client.send(CrawlerRequest(url="unsupported://resource"))

    assert attempts == 1
    assert delays == []
    assert isinstance(error_info.value.__cause__, httpx.UnsupportedProtocol)


@pytest.mark.parametrize(
    "method",
    ["POST", "DELETE", "OPTIONS", "TRACE", "CONNECT", "CUSTOM"],
)
def test_non_eligible_method_does_not_retry_status(
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with (
        HttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ResponseError, match="all attempts"),
    ):
        client.send(
            CrawlerRequest(
                url="https://example.test/resource",
                method=method,
                metadata={"retry": True, "max_attempts": 99},
            )
        )

    assert attempts == 1
    assert delays == []


@pytest.mark.parametrize(
    ("method", "error_type"),
    [("PUT", httpx.ConnectError), ("PATCH", httpx.ReadTimeout)],
)
def test_non_eligible_method_does_not_retry_transient_exception(
    method: str,
    error_type: type[httpx.RequestError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise error_type("temporary", request=request)

    monkeypatch.setattr(client_module, "_sleep", delays.append)
    with (
        HttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(RequestError) as error_info,
    ):
        client.send(CrawlerRequest(url="https://example.test/resource", method=method))

    assert attempts == 1
    assert delays == []
    assert isinstance(error_info.value.__cause__, error_type)


class _FakeClock:
    """Deterministic clock whose sleeps advance time instead of waiting."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=b"ok", request=request)


def _polite_client(
    clock: _FakeClock,
    handler: object = _ok_handler,
    *,
    interval: float = 2.0,
    retry_policy: RetryPolicy | None = None,
) -> HttpClient:
    return HttpClient(
        rate_limit_policy=RateLimitPolicy(min_interval_seconds=interval),
        retry_policy=retry_policy,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        clock=clock,
    )


def test_first_request_to_a_host_is_not_delayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with _polite_client(clock) as client:
        client.send(CrawlerRequest(url="https://example.test/one"))

    assert clock.sleeps == []


def test_second_request_to_same_host_waits_for_remaining_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with _polite_client(clock) as client:
        client.send(CrawlerRequest(url="https://example.test/one"))
        clock.now = 0.5
        client.send(CrawlerRequest(url="https://example.test/two"))

    assert clock.sleeps == [1.5]
    assert clock.now == 2.0


@pytest.mark.parametrize("elapsed", [2.0, 5.0])
def test_no_wait_once_the_interval_has_elapsed(
    monkeypatch: pytest.MonkeyPatch,
    elapsed: float,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with _polite_client(clock) as client:
        client.send(CrawlerRequest(url="https://example.test/one"))
        clock.now = elapsed
        client.send(CrawlerRequest(url="https://example.test/two"))

    assert clock.sleeps == []


def test_hosts_are_limited_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with _polite_client(clock) as client:
        client.send(CrawlerRequest(url="https://a.example.test/one"))
        client.send(CrawlerRequest(url="https://b.example.test/one"))
        assert clock.sleeps == []

        client.send(CrawlerRequest(url="https://A.example.test/two"))

    assert clock.sleeps == [2.0]


def test_failed_attempt_still_counts_as_contacting_the_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, request=request)

    with _polite_client(
        clock,
        handler,
        retry_policy=RetryPolicy(max_attempts=1),
    ) as client:
        with pytest.raises(RequestError):
            client.send(CrawlerRequest(url="https://example.test/one"))
        clock.now = 0.5
        client.send(CrawlerRequest(url="https://example.test/two"))

    assert clock.sleeps == [1.5]


def test_retry_waits_only_for_the_remainder_after_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)
    statuses = iter([503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), request=request)

    with _polite_client(clock, handler) as client:
        response = client.send(CrawlerRequest(url="https://example.test/one"))

    assert response.status_code == 200
    assert clock.sleeps == [0.5, 1.5]
    assert clock.now == 2.0


@pytest.mark.parametrize("policy", [None, RateLimitPolicy(min_interval_seconds=0)])
def test_disabled_rate_limit_never_waits(
    monkeypatch: pytest.MonkeyPatch,
    policy: RateLimitPolicy | None,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with HttpClient(
        rate_limit_policy=policy,
        transport=httpx.MockTransport(_ok_handler),
        clock=clock,
    ) as client:
        client.send(CrawlerRequest(url="https://example.test/one"))
        client.send(CrawlerRequest(url="https://example.test/two"))

    assert clock.sleeps == []


def test_request_without_a_host_is_not_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _FakeClock()
    monkeypatch.setattr(client_module, "_sleep", clock.sleep)

    with _polite_client(clock) as client:
        client.send(CrawlerRequest(url="unsupported:///one"))
        client.send(CrawlerRequest(url="unsupported:///two"))

    assert clock.sleeps == []


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.test/path", "example.test"),
        ("HTTPS://Example.TEST:8443/path", "example.test"),
        ("/relative", None),
        ("http://[bad", None),
    ],
)
def test_host_extraction(url: str, expected: str | None) -> None:
    assert client_module._host_of(url) == expected
