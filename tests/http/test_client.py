from __future__ import annotations

import httpx
import pytest

from aa_crawler.crawler import CrawlerRequest, RequestError
from aa_crawler.http import HttpClient


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
