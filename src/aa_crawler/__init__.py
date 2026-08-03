"""Public application APIs for AA Crawler."""

from aa_crawler.bootstrap import bootstrap_application

__all__ = ["bootstrap_application", "main"]


def main() -> None:
    print("Hello from aa-crawler!")
