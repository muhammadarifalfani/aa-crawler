"""Public synchronous command-line entry point for AA Crawler (ADR-023).

This package is the thin process boundary around the existing
``bootstrap_application()``, ``create_application_runtime()``, and
``ArticleCrawlService`` layers. It parses one URL argument (plus one
optional ``--output`` path, per ADR-027, and an optional ``--interval``/
``--max-runs`` pair selecting scheduled crawl mode, per ADR-028) and
delegates execution to :mod:`aa_crawler.cli.app` or
:mod:`aa_crawler.cli.scheduler`, returning the resulting process exit code.
It owns no source, robots, retry, identity, parser, or persistence
governance.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from aa_crawler.cli.app import run_crawl
from aa_crawler.cli.scheduler import run_scheduled_crawl

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["main"]


def _positive_float(raw: str) -> float:
    value = float(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive number of seconds")
    return value


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aa-crawler",
        description=(
            "Crawl one approved article URL and print its normalized result "
            "as a single JSON object on stdout. With --interval, repeat the "
            "same crawl on a schedule instead (ADR-028)."
        ),
    )
    parser.add_argument(
        "url",
        help="Absolute HTTPS article URL to crawl.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional file path to also append the crawl result to, as one "
            "JSON Lines record (ADR-027). Omitted by default: no file is "
            "written unless this is supplied."
        ),
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=_positive_float,
        default=None,
        help=(
            "Optional positive number of seconds between crawls. When "
            "supplied, the CLI enters scheduled crawl mode (ADR-028): the "
            "same URL is crawled immediately, then again every INTERVAL "
            "seconds, until interrupted or --max-runs is reached. Omitted "
            "by default: the CLI performs one crawl and exits, unchanged "
            "from ADR-023."
        ),
    )
    parser.add_argument(
        "--max-runs",
        type=_positive_int,
        default=None,
        help=(
            "Optional positive integer bound on the number of scheduled "
            "iterations. Only valid together with --interval. Omitted by "
            "default: scheduled mode repeats until interrupted."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and execute one or repeated synchronous crawls.

    Args:
        argv: Explicit argument vector for testing. When omitted, arguments
            are read from ``sys.argv`` by the standard-library parser.

    Returns:
        The CLI-local process exit code produced by :func:`run_crawl` (the
        default, single-shot mode) or :func:`run_scheduled_crawl` (when
        ``--interval`` is supplied, per ADR-028).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.max_runs is not None and args.interval is None:
        parser.error("--max-runs requires --interval")
    if args.interval is None:
        return run_crawl(args.url, output=args.output)
    return run_scheduled_crawl(
        args.url,
        interval=args.interval,
        output=args.output,
        max_runs=args.max_runs,
    )
