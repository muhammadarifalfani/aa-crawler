"""Reusable synchronous HTTP client for crawler requests."""

import time
from types import TracebackType
from typing import Self

import httpx

from aa_crawler.crawler import CrawlerRequest, CrawlerResponse, ResponseError
from aa_crawler.http.adapters import to_crawler_response, to_httpx_request
from aa_crawler.http.errors import translate_httpx_error
from aa_crawler.http.policies import RetryPolicy, TimeoutPolicy

_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


class HttpClient:
    """Execute crawler requests through a reusable synchronous HTTPX client.

    Args:
        timeout_policy: Explicit timeout policy, or the default policy.
        retry_policy: Explicit retry policy, or the default policy.
        transport: Optional HTTPX transport, primarily for isolated testing.
    """

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout_policy = timeout_policy or TimeoutPolicy()
        self._retry_policy = retry_policy or RetryPolicy()
        self._client = httpx.Client(
            timeout=self._timeout_policy.to_httpx(),
            transport=transport,
        )

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
        for attempt_number in range(1, self._retry_policy.max_attempts + 1):
            delay = self._retry_policy.backoff_seconds(attempt_number)
            if delay > 0:
                _sleep(delay)

            try:
                response = self._client.send(to_httpx_request(request))
            except _RETRYABLE_EXCEPTIONS as error:
                if attempt_number == self._retry_policy.max_attempts:
                    raise translate_httpx_error(error) from error
                continue
            except httpx.HTTPError as error:
                raise translate_httpx_error(error) from error

            if self._retry_policy.should_retry_status(response.status_code):
                if attempt_number == self._retry_policy.max_attempts:
                    raise ResponseError(
                        "HTTP response remained retryable after all attempts"
                    )
                response.close()
                continue

            return to_crawler_response(response, metadata=request.metadata)

        raise RuntimeError("retry loop completed without a result")

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
