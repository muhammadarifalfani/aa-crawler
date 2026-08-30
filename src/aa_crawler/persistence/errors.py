"""Persistence boundary domain errors."""

from aa_crawler.crawler import CrawlerError


class PersistenceError(CrawlerError):
    """Base exception for persistence boundary failures."""


class PersistenceWriteError(PersistenceError):
    """Raised when a concrete sink cannot durably persist a crawl result."""
