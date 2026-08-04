"""Robots policy domain errors."""

from aa_crawler.crawler import CrawlerError


class RobotsError(CrawlerError):
    """Raised when robots.txt policy cannot be evaluated safely."""
