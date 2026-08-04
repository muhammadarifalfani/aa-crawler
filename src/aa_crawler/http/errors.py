"""Translation from HTTPX failures to crawler domain errors."""

import httpx

from aa_crawler.crawler import CrawlerError, RequestError, ResponseError


def translate_httpx_error(error: httpx.HTTPError) -> CrawlerError:
    """Translate an HTTPX failure into an existing crawler domain error."""
    if isinstance(error, httpx.RequestError):
        return RequestError("HTTP request execution failed")
    return ResponseError("HTTP response processing failed")
