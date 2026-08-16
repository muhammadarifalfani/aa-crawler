"""Public application APIs for AA Crawler."""

from aa_crawler.bootstrap import bootstrap_application
from aa_crawler.cli import main

__all__ = ["bootstrap_application", "main"]
