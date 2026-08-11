"""Public application-layer contracts."""

from aa_crawler.application.errors import (
    ApplicationError,
    SourceBoundaryError,
    UnsupportedSourceError,
)

__all__ = [
    "ApplicationError",
    "SourceBoundaryError",
    "UnsupportedSourceError",
]
