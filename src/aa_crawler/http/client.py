"""Reusable synchronous HTTP client for crawler requests."""

import time
from collections.abc import Callable
from types import TracebackType
from typing import Self
from urllib.parse import urlsplit

import httpx

from aa_crawler.crawler import CrawlerRequest, CrawlerResponse, ResponseError
from aa_crawler.http.adapters import to_crawler_response, to_httpx_request
from aa_crawler.http.errors import translate_httpx_error
from aa_crawler.http.policies import RateLimitPolicy, RetryPolicy, TimeoutPolicy

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


def _host_of(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


class HttpClient:
    """Execute crawler requests through a reusable synchronous HTTPX client.

    Args:
        timeout_policy: Explicit timeout policy, or the default policy.
        retry_policy: Explicit retry policy, or the default policy.
        rate_limit_policy: Explicit per-host politeness policy (ADR-033), or
            the default policy, which applies no limiting.
        transport: Optional HTTPX transport, primarily for isolated testing.
        clock: Monotonic time source for the politeness interval, primarily
            for isolated testing.
    """

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_policy = timeout_policy or TimeoutPolicy()
        self._retry_policy = retry_policy or RetryPolicy()
        self._rate_limit_policy = rate_limit_policy or RateLimitPolicy()
        self._clock = clock
        self._last_request_end: dict[str, float] = {}
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
        attempt_limit = (
            self._retry_policy.max_attempts
            if self._retry_policy.is_method_retryable(request.method)
            else 1
        )
        host = _host_of(request.url)
        for attempt_number in range(1, attempt_limit + 1):
            delay = self._retry_policy.backoff_seconds(attempt_number)
            if delay > 0:
                _sleep(delay)

            try:
                response = self._send_once(request, host)
            except _RETRYABLE_EXCEPTIONS as error:
                if attempt_number == attempt_limit:
                    raise translate_httpx_error(error) from error
                continue
            except httpx.HTTPError as error:
                raise translate_httpx_error(error) from error

            if self._retry_policy.should_retry_status(response.status_code):
                if attempt_number == attempt_limit:
                    raise ResponseError(
                        "HTTP response remained retryable after all attempts"
                    )
                response.close()
                continue

            return to_crawler_response(response, metadata=request.metadata)

        raise RuntimeError("retry loop completed without a result")

    def _send_once(self, request: CrawlerRequest, host: str | None) -> httpx.Response:
        self._wait_for_host(host)
        try:
            return self._client.send(to_httpx_request(request))
        finally:
            self._mark_host_contacted(host)

    def _wait_for_host(self, host: str | None) -> None:
        interval = self._rate_limit_policy.min_interval_seconds
        if host is None or interval <= 0:
            return
        last_request_end = self._last_request_end.get(host)
        if last_request_end is None:
            return
        remaining = last_request_end + interval - self._clock()
        if remaining > 0:
            _sleep(remaining)

    def _mark_host_contacted(self, host: str | None) -> None:
        if host is None or self._rate_limit_policy.min_interval_seconds <= 0:
            return
        self._last_request_end[host] = self._clock()

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
