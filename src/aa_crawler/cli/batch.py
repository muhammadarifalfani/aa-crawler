"""Optional batch/multi-URL crawl mode around the CLI process boundary
(ADR-029).

This module adds a third, opt-in mode alongside
:func:`aa_crawler.cli.app.run_crawl` (single-URL, single-shot) and
:func:`aa_crawler.cli.scheduler.run_scheduled_crawl` (single-URL,
scheduled): crawling a list of URLs, once (:func:`run_batch_crawl`) or
repeatedly on an interval (:func:`run_scheduled_batch_crawl`). It reuses
the exact ``bootstrap_application()`` -> ``create_application_runtime()``
-> ``ArticleCrawlService.crawl()`` sequence ADR-023 already approved, one
reused ``ApplicationRuntime`` for the whole run (never one per URL or per
pass), and the exact CLI-local exit codes ADR-023/ADR-027/ADR-028 already
define; no new exit code is introduced. Persistence remains one of the
few reviewed exceptions to the application layer's persistence-
unawareness (ADR-024/ADR-027): only this module,
:mod:`aa_crawler.cli.app`, and :mod:`aa_crawler.cli.scheduler` import
:mod:`aa_crawler.persistence`.

Per ADR-029, this module's per-URL failure policy deliberately differs
from :mod:`aa_crawler.cli.scheduler`'s for one condition:
``UnsupportedSourceError`` is recoverable here (skip that URL, continue
the pass) rather than terminal, since one bad URL among many should not
abort the rest of the list — unlike single-URL scheduled mode, where
retrying the *same* unsupported URL forever would be pointless.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from aa_crawler.application import UnsupportedSourceError, create_application_runtime
from aa_crawler.bootstrap import bootstrap_application
from aa_crawler.cli.app import (
    EXIT_PERSISTENCE_FAILURE,
    EXIT_STARTUP_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_FAILURE,
)
from aa_crawler.configuration import AACrawlerError
from aa_crawler.crawler import CrawlerError
from aa_crawler.observability import correlation_context
from aa_crawler.persistence import FileCrawlResultSink, PersistenceWriteError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from aa_crawler.application import ApplicationRuntime

logger = logging.getLogger(__name__)

__all__ = ["run_batch_crawl", "run_scheduled_batch_crawl"]


def _run_one_url(
    runtime: ApplicationRuntime,
    url: str,
    sink: FileCrawlResultSink | None,
) -> int | None:
    """Crawl one URL within a batch pass and apply the ADR-029 failure policy.

    Returns:
        A terminal CLI-local exit code if the batch run must stop
        immediately, or ``None`` if the pass should continue to the next
        URL — whether this URL succeeded or hit a recoverable failure.
    """
    with correlation_context(uuid.uuid4().hex):
        try:
            items = runtime.article_crawl_service.crawl(url)
            if len(items) != 1:
                raise ValueError(
                    "expected exactly one crawler item from the current "
                    "shipped parser family"
                )
            item = items[0]
            payload = json.dumps(dict(item.data), sort_keys=True)
        except UnsupportedSourceError:
            logger.error(
                "batch crawl url failed: unsupported_source "
                "(recoverable in batch mode, continuing)"
            )
            return None
        except CrawlerError:
            logger.error(
                "batch crawl url failed: crawl_domain_failure (recoverable, continuing)"
            )
            return None
        except Exception:
            logger.error("batch crawl failed: unexpected_failure")
            return EXIT_UNEXPECTED_FAILURE
        else:
            print(payload)
            logger.info("batch crawl url completed")
            if sink is not None:
                try:
                    sink.save(item)
                except PersistenceWriteError:
                    logger.error("batch crawl url succeeded but persistence failed")
                    return EXIT_PERSISTENCE_FAILURE
            return None


def _run_one_pass(
    runtime: ApplicationRuntime,
    urls: Sequence[str],
    sink: FileCrawlResultSink | None,
) -> int | None:
    """Crawl every URL in order and return the first terminal exit code.

    Returns:
        A terminal CLI-local exit code if any URL produced one, or
        ``None`` once every URL in the list has been attempted.
    """
    for url in urls:
        result = _run_one_url(runtime, url, sink)
        if result is not None:
            return result
    return None


def run_batch_crawl(urls: Sequence[str], *, output: Path | None = None) -> int:
    """Crawl a list of URLs once, in order, then exit (ADR-029).

    Bootstraps the application and opens exactly one
    ``ApplicationRuntime`` for the whole pass, then crawls each URL in
    ``urls`` in order, applying the ADR-029 per-URL failure policy. A
    recoverable failure for one URL is logged and skipped; the pass
    continues to the next URL. Reaching the end of the list with no
    terminal failure returns ``EXIT_SUCCESS``, even if some URLs were
    skipped along the way.

    Args:
        urls: The URLs to crawl, in order. Must be non-empty.
        output: An optional destination path. When supplied, each
            successful URL's produced item is also appended to it via
            ``FileCrawlResultSink`` (ADR-024/ADR-027), after that URL's
            JSON payload has already been printed to stdout.

    Returns:
        A CLI-local process exit code (see the ``EXIT_*`` constants in
        :mod:`aa_crawler.cli.app`).
    """
    try:
        bootstrap_application(base_dir=Path.cwd())
    except AACrawlerError:
        logger.error("batch crawl failed: startup_failure")
        return EXIT_STARTUP_FAILURE
    except Exception:
        logger.error("batch crawl failed: unexpected_failure")
        return EXIT_UNEXPECTED_FAILURE

    sink = FileCrawlResultSink(destination=output) if output is not None else None

    with create_application_runtime() as runtime:
        logger.info("batch crawl started")
        result = _run_one_pass(runtime, urls, sink)
        logger.info("batch crawl finished")
        return result if result is not None else EXIT_SUCCESS


def run_scheduled_batch_crawl(
    urls: Sequence[str],
    *,
    interval: float,
    output: Path | None = None,
    max_runs: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Repeat one pass over a list of URLs on an interval (ADR-029).

    Bootstraps the application and opens exactly one
    ``ApplicationRuntime`` for the entire run, then crawls every URL in
    ``urls`` immediately, waits ``interval`` seconds, and repeats — until
    ``max_runs`` full passes complete (if given), a keyboard interrupt is
    received, or a terminal failure occurs. ``max_runs`` bounds the number
    of full passes over the list, not the number of individual URLs
    crawled.

    Args:
        urls: The URLs to crawl on every pass, in order. Must be
            non-empty.
        interval: Seconds to wait between the end of one full pass and
            the start of the next. The first pass happens immediately,
            with no initial wait.
        output: An optional destination path. When supplied, each
            successful URL's produced item is also appended to it via
            ``FileCrawlResultSink`` (ADR-024/ADR-027).
        max_runs: An optional bound on the number of full passes. When
            ``None`` (the default), the loop continues until interrupted
            or a terminal failure occurs.
        sleep: The interval-wait callable, defaulting to ``time.sleep``.
            Tests substitute a deterministic double instead of a real
            wall-clock wait.

    Returns:
        A CLI-local process exit code (see the ``EXIT_*`` constants in
        :mod:`aa_crawler.cli.app`).
    """
    try:
        bootstrap_application(base_dir=Path.cwd())
    except AACrawlerError:
        logger.error("scheduled batch crawl failed: startup_failure")
        return EXIT_STARTUP_FAILURE
    except Exception:
        logger.error("scheduled batch crawl failed: unexpected_failure")
        return EXIT_UNEXPECTED_FAILURE

    sink = FileCrawlResultSink(destination=output) if output is not None else None

    try:
        with create_application_runtime() as runtime:
            logger.info("scheduled batch crawl started")
            run_count = 0
            while max_runs is None or run_count < max_runs:
                result = _run_one_pass(runtime, urls, sink)
                if result is not None:
                    return result

                run_count += 1
                if max_runs is not None and run_count >= max_runs:
                    break
                sleep(interval)

            logger.info("scheduled batch crawl finished: max_runs reached")
            return EXIT_SUCCESS
    except KeyboardInterrupt:
        logger.info("scheduled batch crawl interrupted, shutting down cleanly")
        return EXIT_SUCCESS
