"""Transport adapters between crawler contracts and HTTPX objects."""

from collections.abc import Mapping

import httpx

from aa_crawler.crawler import CrawlerRequest, CrawlerResponse


def to_httpx_request(request: CrawlerRequest) -> httpx.Request:
    """Convert an immutable crawler request into an HTTPX request.

    Args:
        request: Transport-neutral crawler request.

    Returns:
        An HTTPX request containing the same method, URL, headers, query
        parameters, and body.
    """
    return httpx.Request(
        method=request.method,
        url=request.url,
        headers=request.headers,
        params=request.query_params,
        content=request.body,
    )


def _elapsed_seconds(response: httpx.Response) -> float:
    try:
        return response.elapsed.total_seconds()
    except RuntimeError:
        return 0.0


def to_crawler_response(
    response: httpx.Response,
    *,
    metadata: Mapping[str, object] | None = None,
) -> CrawlerResponse:
    """Convert a fully-read HTTPX response into a crawler response.

    Args:
        response: Completed, non-streaming HTTPX response.
        metadata: Optional request metadata to carry into the response.

    Returns:
        An immutable crawler response preserving transport response data.
    """
    return CrawlerResponse(
        url=str(response.url),
        status_code=response.status_code,
        headers=dict(response.headers),
        body=response.content,
        elapsed=_elapsed_seconds(response),
        metadata={} if metadata is None else metadata,
    )
