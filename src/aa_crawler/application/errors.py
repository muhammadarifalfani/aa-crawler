"""Application-layer error contracts."""

from aa_crawler.crawler.errors import CrawlerError


class ApplicationError(CrawlerError):
    """Base exception for application orchestration failures."""


class UnsupportedSourceError(ApplicationError):
    """Raised when no enabled source supports a requested crawl URL."""

    def __init__(self) -> None:
        """Create an error without retaining the rejected URL."""
        super().__init__("No enabled source supports the requested URL")


class SourceBoundaryError(ApplicationError):
    """Raised when acquisition crosses the selected source boundary."""

    def __init__(self) -> None:
        """Create an error without retaining source or response details."""
        super().__init__("Acquired document crossed the selected source boundary")
