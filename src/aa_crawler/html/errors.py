"""HTML fetching domain errors."""

from aa_crawler.crawler import CrawlerError


class HtmlError(CrawlerError):
    """Base exception for HTML fetching failures."""


class HtmlDisallowedError(HtmlError):
    """Raised when robots.txt disallows an HTML request."""


class HtmlContentTypeError(HtmlError):
    """Raised when a response does not contain supported HTML content."""


class HtmlDecodingError(HtmlError):
    """Raised when HTML bytes cannot be decoded safely."""
