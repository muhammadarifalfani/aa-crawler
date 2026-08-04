"""Crawler domain exception hierarchy."""


class CrawlerError(Exception):
    """Base exception for crawler domain failures."""


class RequestError(CrawlerError):
    """Raised when a crawler request cannot be produced or accepted."""


class ResponseError(CrawlerError):
    """Raised when a crawler response cannot be processed safely."""


class ParsingError(CrawlerError):
    """Raised when response content cannot be parsed into crawler items."""
