"""Reusable synchronous robots.txt policy."""

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from aa_crawler.crawler import CrawlerRequest, CrawlerResponse
from aa_crawler.http import HttpClient
from aa_crawler.robots.errors import RobotsError


def _resolve_origin(target_url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(target_url)
        port = parsed.port
    except ValueError as error:
        raise RobotsError("target URL is malformed") from error

    if (
        not parsed.scheme
        or parsed.hostname is None
        or any(character.isspace() for character in parsed.netloc)
    ):
        raise RobotsError("target URL must include a valid scheme and host")

    hostname = parsed.hostname
    formatted_host = f"[{hostname}]" if ":" in hostname else hostname
    authority = formatted_host if port is None else f"{formatted_host}:{port}"
    origin = f"{parsed.scheme}://{authority}"
    return origin, f"{origin}/robots.txt"


class RobotsPolicy:
    """Fetch, cache, and evaluate robots.txt rules by origin."""

    def __init__(self, *, http_client: HttpClient, user_agent: str) -> None:
        normalized_user_agent = user_agent.strip()
        if not normalized_user_agent:
            raise ValueError("user_agent must not be empty")
        self._http_client = http_client
        self._user_agent = normalized_user_agent
        self._cache: dict[str, RobotFileParser] = {}

    def allowed(self, *, target_url: str) -> bool:
        """Return whether the configured user agent may fetch a target URL."""
        origin, robots_url = _resolve_origin(target_url)
        parser = self._cache.get(origin)
        if parser is None:
            response = self._http_client.send(CrawlerRequest(url=robots_url))
            parser = self._parser_from_response(response, robots_url=robots_url)
            self._cache[origin] = parser
        return parser.can_fetch(self._user_agent, target_url)

    def clear_cache(self) -> None:
        """Discard all cached robots rules for this policy instance."""
        self._cache.clear()

    @staticmethod
    def _parser_from_response(
        response: CrawlerResponse,
        *,
        robots_url: str,
    ) -> RobotFileParser:
        parser = RobotFileParser(robots_url)
        status_code = response.status_code

        if not 200 <= status_code < 300 and status_code not in {
            401,
            403,
            404,
            410,
        }:
            raise RobotsError("robots.txt returned an unsupported status")

        try:
            if status_code in {401, 403}:
                parser.parse(["User-agent: *", "Disallow: /"])
            elif status_code in {404, 410}:
                parser.parse(["User-agent: *", "Disallow:"])
            else:
                text = response.body.decode("utf-8", errors="replace")
                lines = (
                    text.splitlines()
                    if text.strip()
                    else ["User-agent: *", "Disallow:"]
                )
                parser.parse(lines)
        except Exception as error:
            raise RobotsError("robots.txt parsing failed") from error
        return parser
