"""Public synchronous command-line entry point for AA Crawler (ADR-023).

This package is the thin process boundary around the existing
``bootstrap_application()``, ``create_application_runtime()``, and
``ArticleCrawlService`` layers. It parses either a single positional URL
or a ``--urls-file`` batch (ADR-029, mutually exclusive with each other),
plus one optional ``--output`` path (ADR-027) and an optional
``--interval``/``--max-runs`` pair selecting scheduled crawl mode
(ADR-028). It delegates execution to :mod:`aa_crawler.cli.app`,
:mod:`aa_crawler.cli.scheduler`, or :mod:`aa_crawler.cli.batch`,
returning the resulting process exit code. It owns no source, robots,
retry, identity, parser, or persistence governance.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from aa_crawler.cli.app import run_crawl
from aa_crawler.cli.batch import run_batch_crawl, run_scheduled_batch_crawl
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


def _read_urls_file(path: Path) -> list[str]:
    """Parse a ``--urls-file`` into an ordered, non-empty list of URLs.

    One URL per line; blank lines and lines starting with ``#`` are
    skipped as comments.

    Raises:
        ValueError: The file cannot be read, or contains no URLs after
            skipping blank lines and comments.
    """
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"could not read --urls-file {path}: {error}") from error

    urls = [
        stripped
        for line in raw_lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]
    if not urls:
        raise ValueError(f"--urls-file {path} contains no URLs")
    return urls


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aa-crawler",
        description=(
            "Crawl one approved article URL (or, with --urls-file, a batch "
            "of URLs; ADR-029) and print each normalized result as JSON. "
            "With --interval, repeat the crawl(s) on a schedule instead "
            "(ADR-028)."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help=(
            "Absolute HTTPS article URL to crawl. Exactly one of url or "
            "--urls-file is required."
        ),
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=None,
        help=(
            "Optional file path containing one absolute HTTPS URL per "
            "line (blank lines and lines starting with # are skipped) to "
            "crawl as a batch (ADR-029). Mutually exclusive with the "
            "positional url; exactly one of the two is required."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional file path to also append each crawl result to, as "
            "one JSON Lines record per result (ADR-027). Omitted by "
            "default: no file is written unless this is supplied."
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
            "same URL (or the whole --urls-file list, once per pass) is "
            "crawled immediately, then again every INTERVAL seconds, "
            "until interrupted or --max-runs is reached. Omitted by "
            "default: the CLI performs one crawl (or one batch pass) and "
            "exits."
        ),
    )
    parser.add_argument(
        "--max-runs",
        type=_positive_int,
        default=None,
        help=(
            "Optional positive integer bound on the number of scheduled "
            "iterations (or, with --urls-file, full batch passes). Only "
            "valid together with --interval. Omitted by default: "
            "scheduled mode repeats until interrupted."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and execute one or repeated synchronous crawls.

    Args:
        argv: Explicit argument vector for testing. When omitted, arguments
            are read from ``sys.argv`` by the standard-library parser.

    Returns:
        The CLI-local process exit code produced by :func:`run_crawl`,
        :func:`run_scheduled_crawl`, :func:`run_batch_crawl`, or
        :func:`run_scheduled_batch_crawl`, depending on which of
        ``--urls-file`` and ``--interval`` were supplied.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.max_runs is not None and args.interval is None:
        parser.error("--max-runs requires --interval")

    if (args.url is None) == (args.urls_file is None):
        parser.error("exactly one of url or --urls-file is required")

    if args.urls_file is not None:
        try:
            urls = _read_urls_file(args.urls_file)
        except ValueError as error:
            parser.error(str(error))
        if args.interval is None:
            return run_batch_crawl(urls, output=args.output)
        return run_scheduled_batch_crawl(
            urls,
            interval=args.interval,
            output=args.output,
            max_runs=args.max_runs,
        )

    if args.interval is None:
        return run_crawl(args.url, output=args.output)
    return run_scheduled_crawl(
        args.url,
        interval=args.interval,
        output=args.output,
        max_runs=args.max_runs,
    )
