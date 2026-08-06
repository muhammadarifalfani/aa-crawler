from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from aa_crawler.crawler import (
    CrawlerItem,
    CrawlerRequest,
    CrawlerResponse,
    HtmlCrawler,
    RequestError,
    ResponseError,
)
from aa_crawler.html import (
    HtmlContentTypeError,
    HtmlDecodingError,
    HtmlDisallowedError,
    HtmlDocument,
    HtmlFetcher,
)
from aa_crawler.http import HttpClient
from aa_crawler.identity import RequestIdentity
from aa_crawler.parser import BaseParser, ParserContractError, ParserError
from aa_crawler.robots import RobotsPolicy

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

_IDENTITY = RequestIdentity(product_version="1.0.0")


def _response(url: str) -> CrawlerResponse:
    return CrawlerResponse(
        url=url,
        status_code=200,
        headers={"Content-Type": "text/html"},
        body=b"<html></html>",
        elapsed=0.1,
    )


class FakeHttpClient(HttpClient):
    def __init__(
        self,
        outcomes: Iterable[CrawlerResponse | Exception],
        events: list[str] | None = None,
    ) -> None:
        self._outcomes = iter(outcomes)
        self._events = events
        self.requests: list[CrawlerRequest] = []

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        self.requests.append(request)
        if self._events is not None:
            self._events.append(f"page:{request.url}")
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeRobotsPolicy(RobotsPolicy):
    def __init__(
        self,
        decisions: Iterable[bool],
        events: list[str],
        identity: RequestIdentity,
    ) -> None:
        self._identity = identity
        self._decisions = iter(decisions)
        self._events = events
        self.targets: list[str] = []

    def allowed(self, *, target_url: str) -> bool:
        self.targets.append(target_url)
        self._events.append(f"robots:{target_url}")
        return next(self._decisions)


class RecordingParser(BaseParser):
    def __init__(
        self,
        outputs: Iterable[Iterable[CrawlerItem] | Exception],
    ) -> None:
        self._outputs = iter(outputs)
        self.documents: list[HtmlDocument] = []

    def parse_document(self, document: HtmlDocument) -> Iterable[CrawlerItem]:
        self.documents.append(document)
        output = next(self._outputs)
        if isinstance(output, Exception):
            raise output
        return output


class RaisingHtmlFetcher(HtmlFetcher):
    def __init__(self, errors: Iterable[Exception]) -> None:
        self._errors = iter(errors)
        self.calls: list[tuple[str, object]] = []

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        self.calls.append((url, metadata))
        raise next(self._errors)


def _crawler(
    *,
    urls: Iterable[str],
    responses: Iterable[CrawlerResponse | Exception],
    outputs: Iterable[Iterable[CrawlerItem] | Exception],
    decisions: Iterable[bool] | None = None,
    metadata: Mapping[str, object] | None = None,
    events: list[str] | None = None,
) -> tuple[HtmlCrawler, FakeHttpClient, FakeRobotsPolicy, RecordingParser]:
    event_log = [] if events is None else events
    url_values = tuple(urls)
    client = FakeHttpClient(responses, event_log)
    robots = FakeRobotsPolicy(
        [True] * len(url_values) if decisions is None else decisions,
        event_log,
        _IDENTITY,
    )
    fetcher = HtmlFetcher(
        http_client=client,
        robots_policy=robots,
        identity=_IDENTITY,
    )
    parser = RecordingParser(outputs)
    crawler = HtmlCrawler(
        http_client=client,
        html_fetcher=fetcher,
        parser=parser,
        urls=url_values,
        metadata=metadata,
    )
    return crawler, client, robots, parser


def test_dependencies_are_retained_and_reused() -> None:
    crawler, client, _, parser = _crawler(urls=[], responses=[], outputs=[])

    assert crawler._http_client is client
    assert crawler._html_fetcher._http_client is client
    assert crawler._parser is parser


def test_urls_and_metadata_are_defensively_copied() -> None:
    urls = ["https://example.test/one"]
    metadata: dict[str, object] = {"request_id": "42"}
    crawler, _, _, _ = _crawler(
        urls=urls,
        responses=[],
        outputs=[],
        metadata=metadata,
    )
    urls.append("https://example.test/two")
    metadata["request_id"] = "changed"

    requests = tuple(crawler.start_requests())

    assert crawler._urls == ("https://example.test/one",)
    assert requests[0].metadata == {"request_id": "42"}
    with pytest.raises(TypeError):
        crawler._metadata["other"] = "value"  # type: ignore[index]


@pytest.mark.parametrize("url", ["", " ", "\t"])
def test_empty_url_is_rejected(url: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        _crawler(urls=[url], responses=[], outputs=[])


def test_empty_urls_yield_no_items() -> None:
    crawler, client, robots, parser = _crawler(urls=[], responses=[], outputs=[])

    assert list(crawler.crawl()) == []
    assert client.requests == []
    assert robots.targets == []
    assert parser.documents == []


def test_crawl_is_lazy() -> None:
    url = "https://example.test/page"
    crawler, client, robots, parser = _crawler(
        urls=[url],
        responses=[_response(url)],
        outputs=[[]],
    )

    result = crawler.crawl()

    assert client.requests == []
    assert robots.targets == []
    assert parser.documents == []
    next(result, None)
    assert len(client.requests) == 1


def test_one_url_yields_items_unchanged_in_order() -> None:
    url = "https://example.test/page"
    items = [CrawlerItem({"id": 1}), CrawlerItem({"id": 2})]
    crawler, client, _, _ = _crawler(
        urls=[url],
        responses=[_response(url)],
        outputs=[items],
    )

    yielded = list(crawler.crawl())

    assert len(client.requests) == 1
    assert yielded == items
    assert all(
        actual is expected for actual, expected in zip(yielded, items, strict=True)
    )


def test_multiple_urls_preserve_order_and_boundary_sequence() -> None:
    urls = ["https://example.test/one", "https://example.test/two"]
    events: list[str] = []
    crawler, client, robots, parser = _crawler(
        urls=urls,
        responses=[_response(url) for url in urls],
        outputs=[[CrawlerItem({"url": url})] for url in urls],
        events=events,
    )

    items = list(crawler.crawl())

    assert [request.url for request in client.requests] == urls
    assert robots.targets == urls
    assert [item.data["url"] for item in items] == urls
    assert events == [
        "robots:https://example.test/one",
        "page:https://example.test/one",
        "robots:https://example.test/two",
        "page:https://example.test/two",
    ]
    assert len(parser.documents) == 2


def test_metadata_and_redirected_url_reach_parser_document() -> None:
    requested_url = "https://example.test/original"
    final_url = "https://example.test/final"
    metadata = {"request_id": "42"}
    crawler, client, _, parser = _crawler(
        urls=[requested_url],
        responses=[_response(final_url)],
        outputs=[[]],
        metadata=metadata,
    )

    list(crawler.crawl())

    assert client.requests[0].metadata == metadata
    assert parser.documents[0].requested_url == requested_url
    assert parser.documents[0].final_url == final_url
    assert parser.documents[0].metadata == metadata


def test_repeated_crawls_are_independent_and_reuse_dependencies() -> None:
    url = "https://example.test/page"
    crawler, client, robots, parser = _crawler(
        urls=[url],
        responses=[_response(url), _response(url)],
        outputs=[[CrawlerItem({"run": 1})], [CrawlerItem({"run": 2})]],
        decisions=[True, True],
    )

    first = list(crawler.crawl())
    second = list(crawler.crawl())

    assert first[0].data["run"] == 1
    assert second[0].data["run"] == 2
    assert len(client.requests) == 2
    assert len(robots.targets) == 2
    assert len(parser.documents) == 2


@pytest.mark.parametrize(
    "error",
    [
        RequestError("request"),
        ResponseError("response"),
        HtmlDisallowedError("disallowed"),
        HtmlContentTypeError("content type"),
        HtmlDecodingError("decoding"),
    ],
)
def test_fetch_errors_propagate_unchanged(error: Exception) -> None:
    client = FakeHttpClient([])
    fetcher = RaisingHtmlFetcher([error])
    parser = RecordingParser([])
    crawler = HtmlCrawler(
        http_client=client,
        html_fetcher=fetcher,
        parser=parser,
        urls=["https://example.test/page"],
        metadata={"secret": "metadata-value"},
    )

    with pytest.raises(type(error)) as error_info:
        list(crawler.crawl())

    assert error_info.value is error
    assert client.requests == []
    assert parser.documents == []


def test_parser_error_propagates_unchanged_and_stops_processing() -> None:
    urls = ["https://example.test/one", "https://example.test/two"]
    error = ParserContractError("parser failure")
    crawler, client, robots, _ = _crawler(
        urls=urls,
        responses=[_response(url) for url in urls],
        outputs=[error],
    )

    with pytest.raises(ParserError) as error_info:
        list(crawler.crawl())

    assert error_info.value is error
    assert len(client.requests) == 1
    assert len(robots.targets) == 1
    assert "metadata-value" not in str(error_info.value)
