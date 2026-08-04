from __future__ import annotations

import httpx
import pytest

from aa_crawler.crawler import CrawlerRequest, RequestError, ResponseError
from aa_crawler.http import HttpClient, RetryPolicy, TimeoutPolicy
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
