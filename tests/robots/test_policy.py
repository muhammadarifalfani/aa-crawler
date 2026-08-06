from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.robotparser import RobotFileParser

import pytest

from aa_crawler.crawler import (
    CrawlerRequest,
    CrawlerResponse,
    RequestError,
    ResponseError,
)
from aa_crawler.http import HttpClient
from aa_crawler.identity import RequestIdentity
from aa_crawler.robots import RobotsError, RobotsPolicy

if TYPE_CHECKING:
    from collections.abc import Iterable

_IDENTITY = RequestIdentity(product_version="1.0.0")


def _response(status_code: int = 200, body: bytes = b"") -> CrawlerResponse:
    return CrawlerResponse(
        url="https://example.test/robots.txt",
        status_code=status_code,
        headers={},
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


def test_policy_retains_required_identity() -> None:
    policy = RobotsPolicy(http_client=FakeHttpClient([]), identity=_IDENTITY)

    assert policy.identity is _IDENTITY


@pytest.mark.parametrize(
    ("target_url", "robots_url"),
    [
        ("https://example.test/path", "https://example.test/robots.txt"),
        ("https://example.test/path?q=1", "https://example.test/robots.txt"),
        ("https://example.test/path#part", "https://example.test/robots.txt"),
        ("http://example.test:8080/path", "http://example.test:8080/robots.txt"),
    ],
)
def test_robots_url_resolution(target_url: str, robots_url: str) -> None:
    client = FakeHttpClient([_response()])
    policy = RobotsPolicy(http_client=client, identity=_IDENTITY)

    assert policy.allowed(target_url=target_url)
    assert client.requests[0].url == robots_url
    assert client.requests[0].method == "GET"
    assert client.requests[0].headers["User-Agent"] == _IDENTITY.user_agent
    assert client.requests[0].body is None


@pytest.mark.parametrize(
    "target_url",
    ["example.test/path", "https:///path", "https://example.test:invalid/path"],
)
def test_malformed_target_url_is_rejected(target_url: str) -> None:
    policy = RobotsPolicy(http_client=FakeHttpClient([]), identity=_IDENTITY)

    with pytest.raises(RobotsError, match="target URL"):
        policy.allowed(target_url=target_url)


@pytest.mark.parametrize(
    ("body", "target_url", "expected"),
    [
        (b"User-agent: *\nAllow: /public", "https://example.test/public", True),
        (b"User-agent: *\nDisallow: /private", "https://example.test/private", False),
        (b"", "https://example.test/anything", True),
    ],
)
def test_successful_rules_are_evaluated(
    body: bytes,
    target_url: str,
    expected: bool,
) -> None:
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(body=body)]),
        identity=_IDENTITY,
    )

    assert policy.allowed(target_url=target_url) is expected


def test_can_fetch_uses_the_request_identity_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_user_agents: list[str] = []
    original_can_fetch = RobotFileParser.can_fetch

    def record_can_fetch(
        parser: RobotFileParser,
        user_agent: str,
        url: str,
    ) -> bool:
        observed_user_agents.append(user_agent)
        return original_can_fetch(parser, user_agent, url)

    monkeypatch.setattr(RobotFileParser, "can_fetch", record_can_fetch)
    client = FakeHttpClient([_response(body=b"User-agent: *\nAllow: /")])
    policy = RobotsPolicy(http_client=client, identity=_IDENTITY)

    assert policy.allowed(target_url="https://example.test/page")
    assert observed_user_agents == [_IDENTITY.user_agent]
    assert client.requests[0].headers["User-Agent"] == observed_user_agents[0]


@pytest.mark.parametrize("status_code", [401, 403])
def test_unauthorized_status_denies_all(status_code: int) -> None:
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(status_code)]),
        identity=_IDENTITY,
    )

    assert not policy.allowed(target_url="https://example.test/path")


@pytest.mark.parametrize("status_code", [404, 410])
def test_missing_status_allows_all(status_code: int) -> None:
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(status_code)]),
        identity=_IDENTITY,
    )

    assert policy.allowed(target_url="https://example.test/path")


@pytest.mark.parametrize("status_code", [300, 400, 500])
def test_other_status_raises_robots_error(status_code: int) -> None:
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(status_code)]),
        identity=_IDENTITY,
    )

    with pytest.raises(RobotsError, match="unsupported status"):
        policy.allowed(target_url="https://example.test/path")


@pytest.mark.parametrize("error", [RequestError("request"), ResponseError("response")])
def test_http_client_error_propagates_unchanged(error: Exception) -> None:
    policy = RobotsPolicy(
        http_client=FakeHttpClient([error]),
        identity=_IDENTITY,
    )

    with pytest.raises(type(error)) as error_info:
        policy.allowed(target_url="https://example.test/path")

    assert error_info.value is error


def test_parser_failure_becomes_chained_robots_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ValueError("sensitive parser detail")

    def fail_parse(_parser: RobotFileParser, _lines: list[str]) -> None:
        raise error

    monkeypatch.setattr(RobotFileParser, "parse", fail_parse)
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(body=b"User-agent: *")]),
        identity=_IDENTITY,
    )

    with pytest.raises(RobotsError, match="parsing failed") as error_info:
        policy.allowed(target_url="https://example.test/path")

    assert error_info.value.__cause__ is error
    assert "sensitive" not in str(error_info.value)


def test_invalid_utf8_is_decoded_with_replacement() -> None:
    body = b"User-agent: *\n# invalid: \xff\nAllow: /"
    policy = RobotsPolicy(
        http_client=FakeHttpClient([_response(body=body)]),
        identity=_IDENTITY,
    )

    assert policy.allowed(target_url="https://example.test/path")


def test_same_origin_reuses_cached_parser_and_client() -> None:
    client = FakeHttpClient([_response(body=b"User-agent: *\nAllow: /")])
    policy = RobotsPolicy(http_client=client, identity=_IDENTITY)

    assert policy.allowed(target_url="https://example.test/one")
    assert policy.allowed(target_url="https://example.test/two")

    assert len(client.requests) == 1
    assert policy._http_client is client


def test_different_origins_use_separate_cache_entries() -> None:
    client = FakeHttpClient([_response(), _response()])
    policy = RobotsPolicy(http_client=client, identity=_IDENTITY)

    policy.allowed(target_url="https://one.example/path")
    policy.allowed(target_url="https://two.example/path")

    assert [request.url for request in client.requests] == [
        "https://one.example/robots.txt",
        "https://two.example/robots.txt",
    ]


def test_policies_with_different_identities_do_not_share_cache() -> None:
    first_client = FakeHttpClient([_response()])
    second_client = FakeHttpClient([_response()])
    first = RobotsPolicy(http_client=first_client, identity=_IDENTITY)
    second_identity = RequestIdentity(product_version="2.0.0")
    second = RobotsPolicy(http_client=second_client, identity=second_identity)

    assert first.allowed(target_url="https://example.test/page")
    assert second.allowed(target_url="https://example.test/page")

    assert len(first_client.requests) == 1
    assert len(second_client.requests) == 1
    assert first_client.requests[0].headers["User-Agent"] == _IDENTITY.user_agent
    assert second_client.requests[0].headers["User-Agent"] == second_identity.user_agent


def test_clear_cache_forces_refetch() -> None:
    client = FakeHttpClient([_response(), _response()])
    policy = RobotsPolicy(http_client=client, identity=_IDENTITY)

    policy.allowed(target_url="https://example.test/one")
    policy.clear_cache()
    policy.allowed(target_url="https://example.test/two")

    assert len(client.requests) == 2
