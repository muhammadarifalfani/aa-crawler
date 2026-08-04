"""Public synchronous HTML fetching API."""

from aa_crawler.html.errors import (
    HtmlContentTypeError,
    HtmlDecodingError,
    HtmlDisallowedError,
    HtmlError,
)
from aa_crawler.html.fetcher import HtmlFetcher
from aa_crawler.html.models import HtmlDocument

__all__ = [
    "HtmlContentTypeError",
    "HtmlDecodingError",
    "HtmlDisallowedError",
    "HtmlDocument",
    "HtmlError",
    "HtmlFetcher",
]
