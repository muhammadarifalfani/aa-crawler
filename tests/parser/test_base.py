from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

import pytest

from aa_crawler.crawler import CrawlerItem
from aa_crawler.html import HtmlDocument
from aa_crawler.parser import (
    BaseParser,
    ParserContractError,
    ParserError,
    ParserExecutionError,
)


def _document() -> HtmlDocument:
    return HtmlDocument(
        requested_url="https://example.test/page",
        final_url="https://example.test/page",
        status_code=200,
        headers={"Content-Type": "text/html"},
        content="<secret>document content</secret>",
        encoding="utf-8",
        metadata={"credential": "secret-metadata"},
    )


class ExampleParser(BaseParser):
    def __init__(
        self,
        implementation: Callable[[HtmlDocument], Iterable[CrawlerItem]],
    ) -> None:
        self._implementation = implementation
        self.documents: list[HtmlDocument] = []

    def parse_document(self, document: HtmlDocument) -> Iterable[CrawlerItem]:
        self.documents.append(document)
        return self._implementation(document)


def test_base_parser_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="abstract"):
        BaseParser()  # type: ignore[abstract]


def test_parse_returns_iterator_and_is_lazy() -> None:
    calls = 0

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        nonlocal calls
        calls += 1
        return ()

    parser = ExampleParser(implementation)

    result = parser.parse(_document())

    assert isinstance(result, Iterator)
    assert calls == 0
    list(result)
    assert calls == 1


def test_original_document_is_passed_unchanged() -> None:
    document = _document()
    parser = ExampleParser(lambda _: ())

    list(parser.parse(document))

    assert parser.documents == [document]
    assert parser.documents[0] is document


def test_empty_output_yields_no_items() -> None:
    parser = ExampleParser(lambda _: [])

    assert list(parser.parse(_document())) == []


@pytest.mark.parametrize("container", [list, tuple])
def test_list_and_tuple_outputs_preserve_item_identity_and_order(
    container: Callable[[Iterable[CrawlerItem]], Iterable[CrawlerItem]],
) -> None:
    items = [CrawlerItem({"id": 1}), CrawlerItem({"id": 2})]
    parser = ExampleParser(lambda _: container(items))

    yielded = list(parser.parse(_document()))

    assert yielded == items
    assert all(
        actual is expected for actual, expected in zip(yielded, items, strict=True)
    )


def test_generator_output_is_supported() -> None:
    items = [CrawlerItem({"id": 1}), CrawlerItem({"id": 2})]

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        yield from items

    parser = ExampleParser(implementation)

    assert list(parser.parse(_document())) == items


def test_repeated_parse_calls_are_independent() -> None:
    call_number = 0

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        nonlocal call_number
        call_number += 1
        return [CrawlerItem({"call": call_number})]

    parser = ExampleParser(implementation)

    first = list(parser.parse(_document()))
    second = list(parser.parse(_document()))

    assert first[0].data["call"] == 1
    assert second[0].data["call"] == 2


@pytest.mark.parametrize("invalid_item", [42, {"id": 1}])
def test_invalid_output_raises_contract_error(invalid_item: object) -> None:
    parser = ExampleParser(
        lambda _: [invalid_item]  # type: ignore[list-item]
    )

    with pytest.raises(ParserContractError, match="invalid item"):
        list(parser.parse(_document()))


def test_valid_items_before_invalid_output_are_yielded_then_processing_stops() -> None:
    first = CrawlerItem({"id": 1})
    events: list[str] = []

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        events.append("first")
        yield first
        events.append("invalid")
        yield "invalid"  # type: ignore[misc]
        events.append("after")

    parser = ExampleParser(implementation)
    result = parser.parse(_document())

    assert next(result) is first
    with pytest.raises(ParserContractError):
        next(result)
    assert events == ["first", "invalid"]


def test_parser_error_propagates_unchanged() -> None:
    error = ParserContractError("implementation contract failure")

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        raise error

    parser = ExampleParser(implementation)

    with pytest.raises(ParserError) as error_info:
        list(parser.parse(_document()))

    assert error_info.value is error


def test_unexpected_exception_before_iteration_is_safely_chained() -> None:
    error = ValueError("secret-metadata")

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        raise error

    parser = ExampleParser(implementation)

    with pytest.raises(ParserExecutionError, match="implementation failed") as info:
        list(parser.parse(_document()))

    assert info.value.__cause__ is error
    assert str(info.value) == "parser implementation failed"


def test_unexpected_exception_during_iteration_stops_processing() -> None:
    item = CrawlerItem({"id": 1})
    events: list[str] = []
    error = RuntimeError("document content")

    def implementation(_document: HtmlDocument) -> Iterable[CrawlerItem]:
        events.append("first")
        yield item
        events.append("failure")
        raise error

    parser = ExampleParser(implementation)
    result = parser.parse(_document())

    assert next(result) is item
    with pytest.raises(ParserExecutionError) as error_info:
        next(result)
    assert error_info.value.__cause__ is error
    assert str(error_info.value) == "parser implementation failed"
    assert events == ["first", "failure"]
