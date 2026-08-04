"""Reusable synchronous HTTP client for crawler requests."""

from types import TracebackType
from typing import Self

import httpx

from aa_crawler.crawler import CrawlerRequest, CrawlerResponse
from aa_crawler.http.adapters import to_crawler_response, to_httpx_request
from aa_crawler.http.errors import translate_httpx_error


class HttpClient:
    """Execute crawler requests through a reusable synchronous HTTPX client.

    Args:
        transport: Optional HTTPX transport, primarily for isolated testing.
    """

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self._client = httpx.Client(transport=transport)

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        """Execute one crawler request and return its immutable response.

        Args:
            request: Transport-neutral crawler request to execute.

        Returns:
            The completed response converted to a crawler contract.

        Raises:
            RequestError: If HTTPX cannot execute the request.
            ResponseError: If HTTPX reports a response-level failure.
        """
        httpx_request = to_httpx_request(request)
        try:
            response = self._client.send(httpx_request)
            return to_crawler_response(response, metadata=request.metadata)
        except httpx.HTTPError as error:
            raise translate_httpx_error(error) from error

    def close(self) -> None:
        """Release resources owned by the underlying HTTPX client."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
