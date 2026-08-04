from datetime import timedelta

import httpx

from aa_crawler.crawler import CrawlerRequest
from aa_crawler.http.adapters import to_crawler_response, to_httpx_request


def test_request_conversion_preserves_transport_fields() -> None:
    request = CrawlerRequest(
        url="https://example.test/resource",
        method="post",
        headers={"X-Test": "request-header"},
        query_params={"page": "2"},
        body=b"request-body",
    )

    converted = to_httpx_request(request)

    assert converted.method == "POST"
    assert converted.url == "https://example.test/resource?page=2"
    assert converted.headers["X-Test"] == "request-header"
    assert converted.content == b"request-body"


def test_request_conversion_does_not_interpret_metadata() -> None:
    request = CrawlerRequest(
        url="https://example.test/resource",
        metadata={"transport_hint": "domain-data"},
    )

    converted = to_httpx_request(request)

    assert converted.extensions == {}


def test_response_conversion_preserves_response_data() -> None:
    request = httpx.Request("GET", "https://example.test/final")
    response = httpx.Response(
        201,
        headers={"X-Test": "response-header"},
        content=b"response-body",
        request=request,
    )
    response.elapsed = timedelta(seconds=0.125)

    converted = to_crawler_response(response, metadata={"request_id": "42"})

    assert converted.url == "https://example.test/final"
    assert converted.status_code == 201
    assert converted.headers["x-test"] == "response-header"
    assert converted.body == b"response-body"
    assert converted.elapsed == 0.125
    assert converted.metadata == {"request_id": "42"}
