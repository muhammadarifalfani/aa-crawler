from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from aa_crawler.crawler import (
    CrawlerRequest,
    CrawlerResponse,
    RequestError,
    ResponseError,
)
from aa_crawler.html import (
    HtmlContentTypeError,
    HtmlDecodingError,
    HtmlDisallowedError,
    HtmlError,
    HtmlFetcher,
)
from aa_crawler.http import HttpClient
from aa_crawler.robots import RobotsPolicy

if TYPE_CHECKING:
    from collections.abc import Iterable


def _response(
    *,
    status_code: int = 200,
    content_type: str | None = "text/html",
    body: bytes = b"<html></html>",
    url: str = "https://example.test/page",
) -> CrawlerResponse:
    headers = {} if content_type is None else {"Content-Type": content_type}
    return CrawlerResponse(
        url=url,
        status_code=status_code,
        headers=headers,
        body=body,
        elapsed=0.1,
    )


class FakeHttpClient(HttpClient):
    def __init__(self, outcomes: Iterable[CrawlerResponse | Exception]) -> None:
        self._outcomes = iter(outcomes)
        self.requests: list[CrawlerRequest] = []

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        self.requests.append(request)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeRobotsPolicy(RobotsPolicy):
    def __init__(self, decisions: Iterable[bool]) -> None:
        self._decisions = iter(decisions)
        self.targets: list[str] = []

    def allowed(self, *, target_url: str) -> bool:
        self.targets.append(target_url)
        return next(self._decisions)


def _fetcher(
    *,
    responses: Iterable[CrawlerResponse | Exception],
    decisions: Iterable[bool] = (True,),
    user_agent: str = "AA-Crawler",
) -> tuple[HtmlFetcher, FakeHttpClient, FakeRobotsPolicy]:
    client = FakeHttpClient(responses)
    robots = FakeRobotsPolicy(decisions)
    return (
        HtmlFetcher(
            http_client=client,
            robots_policy=robots,
            user_agent=user_agent,
        ),
        client,
        robots,
    )


@pytest.mark.parametrize("user_agent", ["", " ", "\t"])
def test_empty_user_agent_is_rejected(user_agent: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        HtmlFetcher(
            http_client=FakeHttpClient([]),
            robots_policy=FakeRobotsPolicy([]),
            user_agent=user_agent,
        )


def test_user_agent_is_normalized() -> None:
    fetcher, _, _ = _fetcher(responses=[], user_agent="  AA-Crawler  ")

    assert fetcher._user_agent == "AA-Crawler"


@pytest.mark.parametrize(
    "url",
    ["example.test/page", "https:///page", "https://example.test:invalid/page"],
)
def test_malformed_url_is_rejected_before_policy_check(url: str) -> None:
    fetcher, client, robots = _fetcher(responses=[], decisions=[])

    with pytest.raises(HtmlError, match="HTML target URL"):
        fetcher.fetch(url=url)

    assert robots.targets == []
    assert client.requests == []


def test_allowed_url_builds_get_request_and_reuses_dependencies() -> None:
    fetcher, client, robots = _fetcher(responses=[_response()])
    metadata = {"request_id": "42"}

    document = fetcher.fetch(url="https://example.test/page", metadata=metadata)

    assert robots.targets == ["https://example.test/page"]
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.url == "https://example.test/page"
    assert request.method == "GET"
    assert request.headers["User-Agent"] == "AA-Crawler"
    assert request.body is None
    assert document.metadata == metadata
    assert fetcher._http_client is client
    assert fetcher._robots_policy is robots


def test_disallowed_url_does_not_request_page() -> None:
    fetcher, client, robots = _fetcher(responses=[], decisions=[False])

    with pytest.raises(HtmlDisallowedError, match="disallowed"):
        fetcher.fetch(url="https://example.test/private")

    assert robots.targets == ["https://example.test/private"]
    assert client.requests == []


@pytest.mark.parametrize(
    "content_type",
    ["text/html", "application/xhtml+xml", "TEXT/HTML; CHARSET=UTF-8"],
)
def test_supported_html_media_types_succeed(content_type: str) -> None:
    fetcher, _, _ = _fetcher(responses=[_response(content_type=content_type)])

    document = fetcher.fetch(url="https://example.test/page")

    assert document.content == "<html></html>"


def test_declared_charset_is_honored_and_normalized() -> None:
    fetcher, _, _ = _fetcher(
        responses=[
            _response(
                content_type="text/html; charset=iso-8859-1",
                body="café".encode("iso-8859-1"),
            )
        ]
    )

    document = fetcher.fetch(url="https://example.test/page")

    assert document.content == "café"
    assert document.encoding == "iso8859-1"


def test_utf8_is_default_and_empty_body_is_allowed() -> None:
    fetcher, _, _ = _fetcher(responses=[_response(body=b"")])

    document = fetcher.fetch(url="https://example.test/page")

    assert document.content == ""
    assert document.encoding == "utf-8"


def test_final_url_and_response_headers_are_preserved() -> None:
    final_url = "https://example.test/redirected"
    fetcher, _, _ = _fetcher(responses=[_response(url=final_url)])

    document = fetcher.fetch(url="https://example.test/original")

    assert document.requested_url == "https://example.test/original"
    assert document.final_url == final_url
    assert document.headers == {"Content-Type": "text/html"}


@pytest.mark.parametrize(
    "content_type",
    [None, "application/json", "text/plain", "image/png"],
)
def test_unsupported_or_missing_content_type_is_rejected(
    content_type: str | None,
) -> None:
    fetcher, _, _ = _fetcher(responses=[_response(content_type=content_type)])

    with pytest.raises(HtmlContentTypeError):
        fetcher.fetch(url="https://example.test/page")


def test_non_success_status_raises_response_error() -> None:
    fetcher, _, _ = _fetcher(responses=[_response(status_code=300)])

    with pytest.raises(ResponseError, match="not successful"):
        fetcher.fetch(url="https://example.test/page")


@pytest.mark.parametrize(
    ("content_type", "body", "cause_type"),
    [
        ("text/html; charset=unknown-codec", b"html", LookupError),
        ("text/html; charset=utf-8", b"\xff", UnicodeDecodeError),
    ],
)
def test_decoding_failure_is_safely_chained(
    content_type: str,
    body: bytes,
    cause_type: type[Exception],
) -> None:
    fetcher, _, _ = _fetcher(
        responses=[_response(content_type=content_type, body=body)]
    )

    with pytest.raises(HtmlDecodingError, match="decoding failed") as error_info:
        fetcher.fetch(url="https://example.test/page")

    assert isinstance(error_info.value.__cause__, cause_type)
    assert str(error_info.value) == "HTML response decoding failed"


@pytest.mark.parametrize("error", [RequestError("request"), ResponseError("response")])
def test_http_client_error_propagates_unchanged(error: Exception) -> None:
    fetcher, _, _ = _fetcher(responses=[error])

    with pytest.raises(type(error)) as error_info:
        fetcher.fetch(url="https://example.test/page")

    assert error_info.value is error


def test_repeated_fetches_reuse_dependencies() -> None:
    fetcher, client, robots = _fetcher(
        responses=[_response(), _response()],
        decisions=[True, True],
    )

    first = fetcher.fetch(url="https://example.test/one")
    second = fetcher.fetch(url="https://example.test/two")

    assert first.content == second.content
    assert len(client.requests) == 2
    assert robots.targets == ["https://example.test/one", "https://example.test/two"]
