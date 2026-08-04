import pytest

from aa_crawler.crawler import CrawlerError
from aa_crawler.html import (
    HtmlContentTypeError,
    HtmlDecodingError,
    HtmlDisallowedError,
    HtmlError,
)


@pytest.mark.parametrize(
    "error_type",
    [HtmlError, HtmlDisallowedError, HtmlContentTypeError, HtmlDecodingError],
)
def test_html_errors_inherit_crawler_error(error_type: type[HtmlError]) -> None:
    error = error_type("safe failure")

    assert isinstance(error, CrawlerError)
    assert str(error) == "safe failure"
