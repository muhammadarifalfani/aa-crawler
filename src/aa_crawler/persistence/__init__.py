"""Public, optional persistence boundary API for crawl results (ADR-024).

This package is never imported by ``ArticleCrawlService``,
``ApplicationRuntime``, or ``aa_crawler.cli``. A caller that already holds a
produced ``CrawlerItem`` composes a concrete sink explicitly.
"""

from aa_crawler.persistence.base import BaseCrawlResultSink
from aa_crawler.persistence.errors import PersistenceError, PersistenceWriteError
from aa_crawler.persistence.file_sink import FileCrawlResultSink

__all__ = [
    "BaseCrawlResultSink",
    "FileCrawlResultSink",
    "PersistenceError",
    "PersistenceWriteError",
]
