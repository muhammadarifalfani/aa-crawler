from dataclasses import FrozenInstanceError

import pytest

from aa_crawler.html import HtmlDocument


def _document(**overrides: object) -> HtmlDocument:
    values: dict[str, object] = {
        "requested_url": "https://example.test/requested",
        "final_url": "https://example.test/final",
        "status_code": 200,
        "headers": {"Content-Type": "text/html"},
        "content": "<html></html>",
        "encoding": "utf-8",
        "metadata": {"request_id": "42"},
    }
    values.update(overrides)
    return HtmlDocument(**values)  # type: ignore[arg-type]


def test_valid_document_construction() -> None:
    document = _document(content="")

    assert document.requested_url == "https://example.test/requested"
    assert document.final_url == "https://example.test/final"
    assert document.content == ""


def test_document_defensively_copies_headers_and_metadata() -> None:
    headers = {"Content-Type": "text/html"}
    metadata: dict[str, object] = {"request_id": "42"}
    document = _document(headers=headers, metadata=metadata)
    headers["Content-Type"] = "application/json"
    metadata["request_id"] = "changed"

    assert document.headers == {"Content-Type": "text/html"}
    assert document.metadata == {"request_id": "42"}
    with pytest.raises(TypeError):
        document.headers["Other"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        document.metadata["other"] = "value"  # type: ignore[index]


def test_document_is_frozen() -> None:
    document = _document()

    with pytest.raises(FrozenInstanceError):
        document.content = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"requested_url": " "}, "requested_url"),
        ({"final_url": ""}, "final_url"),
        ({"status_code": 0}, "status_code"),
        ({"encoding": "\t"}, "encoding"),
    ],
)
def test_document_rejects_invalid_fields(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _document(**overrides)
