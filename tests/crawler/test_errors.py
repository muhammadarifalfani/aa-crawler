import pytest

from aa_crawler.crawler import (
    CrawlerError,
    ParsingError,
    RequestError,
    ResponseError,
    TooManyRedirectsError,
)


@pytest.mark.parametrize(
    "error_type",
    [RequestError, ResponseError, ParsingError, TooManyRedirectsError],
)
def test_crawler_errors_inherit_from_base(error_type: type[CrawlerError]) -> None:
    error = error_type("crawler operation failed")

    assert isinstance(error, CrawlerError)
    assert isinstance(error, Exception)


def test_too_many_redirects_error_is_a_response_error() -> None:
    error = TooManyRedirectsError("crawler operation failed")

    assert isinstance(error, ResponseError)


@pytest.mark.parametrize(
    "error_type",
    [CrawlerError, RequestError, ResponseError, ParsingError, TooManyRedirectsError],
)
def test_crawler_error_string_representation(
    error_type: type[CrawlerError],
) -> None:
    error = error_type("crawler operation failed")

    assert str(error) == "crawler operation failed"
