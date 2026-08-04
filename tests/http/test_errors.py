import httpx

from aa_crawler.crawler import RequestError, ResponseError
from aa_crawler.http.errors import translate_httpx_error


def test_request_error_translation() -> None:
    request = httpx.Request("GET", "https://example.test")

    translated = translate_httpx_error(
        httpx.ConnectError("connection failed", request=request)
    )

    assert isinstance(translated, RequestError)
    assert str(translated) == "HTTP request execution failed"


def test_response_error_translation() -> None:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(500, request=request)

    translated = translate_httpx_error(
        httpx.HTTPStatusError(
            "server error",
            request=request,
            response=response,
        )
    )

    assert isinstance(translated, ResponseError)
    assert str(translated) == "HTTP response processing failed"
