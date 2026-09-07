"""Robots-aware synchronous HTML fetcher."""

from __future__ import annotations

import codecs
from email.message import Message
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from aa_crawler.crawler import CrawlerRequest, ResponseError, TooManyRedirectsError
from aa_crawler.html.errors import (
    HtmlContentTypeError,
    HtmlDecodingError,
    HtmlDisallowedError,
    HtmlError,
)
from aa_crawler.html.models import HtmlDocument

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aa_crawler.http import HttpClient
    from aa_crawler.identity import RequestIdentity
    from aa_crawler.robots import RobotsPolicy

_HTML_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml"})

# ADR-032: bounded, robots-rechecked redirect following. Real news-site
# redirect chains observed in the wild are typically one or two hops
# (a shortlink or AMP page to its canonical article); 5 leaves comfortable
# headroom while keeping the worst case for a misconfigured or malicious
# chain far below httpx's own default of 20.
_MAX_REDIRECTS = 5


def _validate_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError as error:
        raise HtmlError("HTML target URL is malformed") from error
    if (
        not parsed.scheme
        or parsed.hostname is None
        or any(character.isspace() for character in parsed.netloc)
    ):
        raise HtmlError("HTML target URL must include a valid scheme and host")


def _location(headers: Mapping[str, str]) -> str | None:
    return next(
        (value for key, value in headers.items() if key.lower() == "location"),
        None,
    )


def _content_type(headers: Mapping[str, str]) -> tuple[str, str]:
    raw_content_type = next(
        (value for key, value in headers.items() if key.lower() == "content-type"),
        None,
    )
    if raw_content_type is None:
        raise HtmlContentTypeError("HTML response is missing Content-Type")

    message = Message()
    message["Content-Type"] = raw_content_type
    media_type = message.get_content_type().lower()
    if media_type not in _HTML_MEDIA_TYPES:
        raise HtmlContentTypeError("HTML response has an unsupported Content-Type")
    return media_type, message.get_content_charset() or "utf-8"


class HtmlFetcher:
    """Fetch and strictly decode robots-allowed HTML documents."""

    def __init__(
        self,
        *,
        http_client: HttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> None:
        if identity != robots_policy.identity:
            raise ValueError("HTML and robots request identities must match")
        self._http_client = http_client
        self._robots_policy = robots_policy
        self._identity = identity

    @property
    def identity(self) -> RequestIdentity:
        """Return the authoritative request identity for this fetcher."""
        return self._identity

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        """Fetch one robots-allowed URL, following bounded redirects.

        Per ADR-032, each hop (including the first) is independently
        URL-validated and robots-checked before it is requested; a 3xx
        response with a ``Location`` header advances to the next hop
        instead of failing, up to ``_MAX_REDIRECTS`` additional requests.
        """
        current_url = url
        request_metadata = {} if metadata is None else metadata

        for _ in range(_MAX_REDIRECTS + 1):
            _validate_url(current_url)
            if not self._robots_policy.allowed(target_url=current_url):
                raise HtmlDisallowedError("HTML request is disallowed by robots.txt")

            request = CrawlerRequest(
                url=current_url,
                headers={"User-Agent": self.identity.user_agent},
                metadata=request_metadata,
            )
            response = self._http_client.send(request)

            if 200 <= response.status_code < 300:
                _, declared_encoding = _content_type(response.headers)
                try:
                    encoding = codecs.lookup(declared_encoding).name
                    content = response.body.decode(encoding, errors="strict")
                except (LookupError, UnicodeDecodeError) as error:
                    raise HtmlDecodingError("HTML response decoding failed") from error

                return HtmlDocument(
                    requested_url=url,
                    final_url=response.url,
                    status_code=response.status_code,
                    headers=response.headers,
                    content=content,
                    encoding=encoding,
                    metadata=request.metadata,
                )

            if 300 <= response.status_code < 400:
                location = _location(response.headers)
                if location is not None:
                    current_url = urljoin(current_url, location)
                    continue

            raise ResponseError("HTML page response was not successful")

        raise TooManyRedirectsError(
            f"HTML redirect chain exceeded {_MAX_REDIRECTS} hops"
        )
