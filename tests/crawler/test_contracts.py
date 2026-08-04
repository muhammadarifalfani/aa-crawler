from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, cast

import pytest

from aa_crawler.crawler import CrawlerItem, CrawlerRequest, CrawlerResponse

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def set_attribute(instance: object, name: str, value: object) -> None:
    setattr(instance, name, value)


def test_request_defaults() -> None:
    request = CrawlerRequest(url="https://example.test/resource")

    assert request.method == "GET"
    assert request.headers == {}
    assert request.query_params == {}
    assert request.body is None
    assert request.metadata == {}


def test_request_normalizes_method() -> None:
    request = CrawlerRequest(
        url="https://example.test/resource",
        method=" post ",
    )

    assert request.method == "POST"


@pytest.mark.parametrize("url", ["", " ", "\t\r\n"])
def test_request_rejects_empty_url(url: str) -> None:
    with pytest.raises(ValueError, match="url must not be empty"):
        CrawlerRequest(url=url)


def test_request_is_immutable_and_copies_mappings() -> None:
    headers = {"Accept": "application/json"}
    query_params = {"page": "1"}
    metadata: dict[str, object] = {"collector": "example"}
    request = CrawlerRequest(
        url="https://example.test/resource",
        headers=headers,
        query_params=query_params,
        metadata=metadata,
    )

    headers["Accept"] = "text/plain"
    query_params["page"] = "2"
    metadata["collector"] = "changed"

    assert request.headers == {"Accept": "application/json"}
    assert request.query_params == {"page": "1"}
    assert request.metadata == {"collector": "example"}
    with pytest.raises(TypeError):
        cast("MutableMapping[str, str]", request.headers)["Accept"] = "text/plain"
    with pytest.raises(FrozenInstanceError):
        set_attribute(request, "url", "https://changed.test")


def test_response_valid_creation() -> None:
    response = CrawlerResponse(
        url="https://example.test/resource",
        status_code=200,
        headers={"Content-Type": "text/plain"},
        body=b"content",
        elapsed=0.125,
        metadata={"attempt": 1},
    )

    assert response.url == "https://example.test/resource"
    assert response.status_code == 200
    assert response.headers == {"Content-Type": "text/plain"}
    assert response.body == b"content"
    assert response.elapsed == 0.125
    assert response.metadata == {"attempt": 1}


@pytest.mark.parametrize("status_code", [0, -1])
def test_response_rejects_non_positive_status(status_code: int) -> None:
    with pytest.raises(ValueError, match="status_code must be positive"):
        CrawlerResponse(
            url="https://example.test/resource",
            status_code=status_code,
            headers={},
            body=b"",
            elapsed=0.0,
        )


def test_response_is_immutable_and_copies_mappings() -> None:
    headers = {"Content-Type": "text/plain"}
    metadata: dict[str, object] = {"attempt": 1}
    response = CrawlerResponse(
        url="https://example.test/resource",
        status_code=200,
        headers=headers,
        body=b"content",
        elapsed=0.125,
        metadata=metadata,
    )

    headers.clear()
    metadata.clear()

    assert response.headers == {"Content-Type": "text/plain"}
    assert response.metadata == {"attempt": 1}
    with pytest.raises(TypeError):
        cast("MutableMapping[str, str]", response.headers)["X-Test"] = "value"
    with pytest.raises(FrozenInstanceError):
        set_attribute(response, "status_code", 201)


def test_empty_item() -> None:
    assert CrawlerItem().data == {}


def test_populated_item_is_immutable_and_copied() -> None:
    data: dict[str, object] = {"title": "Example", "views": 10}
    item = CrawlerItem(data=data)

    data["views"] = 20

    assert item.data == {"title": "Example", "views": 10}
    with pytest.raises(TypeError):
        cast("MutableMapping[str, object]", item.data)["views"] = 30
    with pytest.raises(FrozenInstanceError):
        set_attribute(item, "data", {})
