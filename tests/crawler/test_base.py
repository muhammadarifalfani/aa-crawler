from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

import pytest

from aa_crawler.crawler import (
    BaseCrawler,
    CrawlerItem,
    CrawlerRequest,
    CrawlerResponse,
    ParsingError,
    RequestError,
    ResponseError,
)
from aa_crawler.http import HttpClient


def _response(url: str = "https://example.test") -> CrawlerResponse:
    return CrawlerResponse(
        url=url,
        status_code=200,
        headers={},
        body=b"response",
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


class ExampleCrawler(BaseCrawler):
    def __init__(
        self,
        *,
        http_client: HttpClient,
        requests: Iterable[CrawlerRequest],
        parser: Callable[[CrawlerResponse], Iterable[CrawlerItem]],
    ) -> None:
        super().__init__(http_client=http_client)
        self._requests = requests
        self._parser = parser
        self.start_calls = 0

    def start_requests(self) -> Iterable[CrawlerRequest]:
        self.start_calls += 1
        return self._requests

    def parse(self, response: CrawlerResponse) -> Iterable[CrawlerItem]:
        return self._parser(response)


class SpecializedCrawler(BaseCrawler):
    def __init__(
        self,
        *,
        http_client: HttpClient,
        requests: Iterable[CrawlerRequest],
        item: CrawlerItem,
    ) -> None:
        super().__init__(http_client=http_client)
        self._requests = requests
        self._item = item
        self.processed: list[CrawlerRequest] = []

    def start_requests(self) -> Iterable[CrawlerRequest]:
        return self._requests

    def _process_request(self, request: CrawlerRequest) -> Iterable[CrawlerItem]:
        self.processed.append(request)
        return [self._item]


def _crawler(
    *,
    client: HttpClient,
    requests: Iterable[CrawlerRequest] = (),
    parser: Callable[[CrawlerResponse], Iterable[CrawlerItem]] = lambda _: (),
) -> ExampleCrawler:
    return ExampleCrawler(http_client=client, requests=requests, parser=parser)


def test_base_crawler_cannot_be_instantiated() -> None:
    client = FakeHttpClient([])

    with pytest.raises(TypeError, match="abstract"):
        BaseCrawler(http_client=client)  # type: ignore[abstract]


def test_injected_http_client_is_retained() -> None:
    client = FakeHttpClient([])
    crawler = _crawler(client=client)

    assert crawler._http_client is client


def test_empty_start_requests_yields_no_items() -> None:
    crawler = _crawler(client=FakeHttpClient([]))

    assert list(crawler.crawl()) == []


def test_one_request_produces_original_item() -> None:
    request = CrawlerRequest(url="https://example.test/one")
    item = CrawlerItem({"id": 1})
    client = FakeHttpClient([_response(request.url)])
    crawler = _crawler(
        client=client,
        requests=[request],
        parser=lambda _: [item],
    )

    assert list(crawler.crawl()) == [item]
    assert client.requests[0] is request


def test_default_processing_sends_and_parses_once() -> None:
    request = CrawlerRequest(url="https://example.test/one")
    response = _response(request.url)
    parse_calls: list[CrawlerResponse] = []

    def parser(actual_response: CrawlerResponse) -> Iterable[CrawlerItem]:
        parse_calls.append(actual_response)
        return []

    client = FakeHttpClient([response])
    crawler = _crawler(client=client, requests=[request], parser=parser)

    list(crawler.crawl())

    assert client.requests == [request]
    assert parse_calls == [response]


def test_specialized_processing_seam_bypasses_default_send_and_parse() -> None:
    request = CrawlerRequest(url="https://example.test/one")
    item = CrawlerItem({"id": 1})
    client = FakeHttpClient([])
    crawler = SpecializedCrawler(
        http_client=client,
        requests=[request],
        item=item,
    )

    assert list(crawler.crawl()) == [item]
    assert crawler.processed == [request]
    assert client.requests == []


def test_one_response_can_produce_multiple_items_in_order() -> None:
    items = [CrawlerItem({"id": 1}), CrawlerItem({"id": 2})]
    crawler = _crawler(
        client=FakeHttpClient([_response()]),
        requests=[CrawlerRequest(url="https://example.test")],
        parser=lambda _: items,
    )

    yielded = list(crawler.crawl())

    assert yielded == items
    assert all(
        actual is expected for actual, expected in zip(yielded, items, strict=True)
    )


def test_multiple_requests_are_processed_sequentially_in_order() -> None:
    requests = [
        CrawlerRequest(url="https://example.test/one"),
        CrawlerRequest(url="https://example.test/two"),
    ]
    client = FakeHttpClient([_response(request.url) for request in requests])
    crawler = _crawler(
        client=client,
        requests=requests,
        parser=lambda response: [CrawlerItem({"url": response.url})],
    )

    items = list(crawler.crawl())

    assert client.requests == requests
    assert [item.data["url"] for item in items] == [request.url for request in requests]


def test_crawl_is_lazy_and_returns_iterator() -> None:
    request = CrawlerRequest(url="https://example.test")
    client = FakeHttpClient([_response()])
    crawler = _crawler(client=client, requests=[request])

    result = crawler.crawl()

    assert isinstance(result, Iterator)
    assert crawler.start_calls == 0
    assert client.requests == []
    next(result, None)
    assert crawler.start_calls == 1
    assert client.requests == [request]


@pytest.mark.parametrize("error", [RequestError("request"), ResponseError("response")])
def test_http_client_domain_error_propagates_unchanged(error: Exception) -> None:
    crawler = _crawler(
        client=FakeHttpClient([error]),
        requests=[CrawlerRequest(url="https://example.test")],
    )

    with pytest.raises(type(error)) as error_info:
        list(crawler.crawl())

    assert error_info.value is error


def test_parsing_error_propagates_unchanged() -> None:
    error = ParsingError("parse")

    def parser(_response: CrawlerResponse) -> Iterable[CrawlerItem]:
        raise error

    crawler = _crawler(
        client=FakeHttpClient([_response()]),
        requests=[CrawlerRequest(url="https://example.test")],
        parser=parser,
    )

    with pytest.raises(ParsingError) as error_info:
        list(crawler.crawl())

    assert error_info.value is error


def test_unexpected_parser_error_becomes_chained_parsing_error() -> None:
    error = ValueError("sensitive parser detail")

    def parser(_response: CrawlerResponse) -> Iterable[CrawlerItem]:
        raise error

    crawler = _crawler(
        client=FakeHttpClient([_response()]),
        requests=[CrawlerRequest(url="https://example.test")],
        parser=parser,
    )

    with pytest.raises(ParsingError, match="crawler response parsing failed") as info:
        list(crawler.crawl())

    assert info.value.__cause__ is error
    assert "sensitive" not in str(info.value)


def test_processing_stops_after_first_failure() -> None:
    requests = [
        CrawlerRequest(url="https://example.test/one"),
        CrawlerRequest(url="https://example.test/two"),
        CrawlerRequest(url="https://example.test/three"),
    ]
    error = RequestError("stop")
    client = FakeHttpClient([_response(), error, _response()])
    crawler = _crawler(client=client, requests=requests)

    with pytest.raises(RequestError):
        list(crawler.crawl())

    assert client.requests == requests[:2]
