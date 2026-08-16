"""Public synchronous command-line entry point for AA Crawler (ADR-023).

This package is the thin process boundary around the existing
``bootstrap_application()``, ``create_application_runtime()``, and
``ArticleCrawlService`` layers. It parses one URL argument, delegates
execution to :mod:`aa_crawler.cli.app`, and returns the resulting process
exit code. It owns no source, robots, retry, identity, or parser governance.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from aa_crawler.cli.app import run_crawl

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aa-crawler",
        description=(
            "Crawl one approved article URL and print its normalized result "
            "as a single JSON object on stdout."
        ),
    )
    parser.add_argument(
        "url",
        help="Absolute HTTPS article URL to crawl.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse one URL argument and execute a single synchronous article crawl.

    Args:
        argv: Explicit argument vector for testing. When omitted, arguments
            are read from ``sys.argv`` by the standard-library parser.

    Returns:
        The CLI-local process exit code produced by :func:`run_crawl`.
    """
    args = _build_parser().parse_args(argv)
    return run_crawl(args.url)
