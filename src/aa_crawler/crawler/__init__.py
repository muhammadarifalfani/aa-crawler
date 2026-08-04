"""Public crawler domain contracts and errors."""

from aa_crawler.crawler.base import BaseCrawler
from aa_crawler.crawler.contracts import CrawlerItem, CrawlerRequest, CrawlerResponse
from aa_crawler.crawler.errors import (
    CrawlerError,
    ParsingError,
    RequestError,
    ResponseError,
)
from aa_crawler.crawler.html import HtmlCrawler

__all__ = [
    "BaseCrawler",
    "CrawlerError",
    "CrawlerItem",
    "CrawlerRequest",
    "CrawlerResponse",
    "HtmlCrawler",
    "ParsingError",
    "RequestError",
    "ResponseError",
]
