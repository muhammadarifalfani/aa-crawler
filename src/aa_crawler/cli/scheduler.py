"""Optional scheduled crawl mode around the CLI process boundary (ADR-028).

This module adds a second, opt-in mode alongside :func:`aa_crawler.cli.app`'s
single-shot ``run_crawl()``: repeating the same synchronous crawl on an
interval, using one reused :class:`~aa_crawler.application.ApplicationRuntime`
for the whole run instead of one per iteration. It reuses the exact
``bootstrap_application()`` -> ``create_application_runtime()`` ->
``ArticleCrawlService.crawl()`` sequence ADR-023 already approved and the
exact CLI-local exit codes ADR-023/ADR-027 already define; no new exit code
is introduced. Persistence remains the one narrow, reviewed exception to the
application layer's persistence-unawareness (ADR-024/ADR-027): only this
module and :mod:`aa_crawler.cli.app` import :mod:`aa_crawler.persistence`.
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
    EXIT_UNSUPPORTED_SOURCE,
)
from aa_crawler.configuration import AACrawlerError
from aa_crawler.crawler import CrawlerError
from aa_crawler.observability import correlation_context
from aa_crawler.persistence import FileCrawlResultSink, PersistenceWriteError

if TYPE_CHECKING:
    from collections.abc import Callable

    from aa_crawler.application import ApplicationRuntime

logger = logging.getLogger(__name__)

__all__ = ["run_scheduled_crawl"]


def _run_iteration(
    runtime: ApplicationRuntime,
    url: str,
    sink: FileCrawlResultSink | None,
) -> int | None:
    """Run one scheduled crawl iteration and apply the ADR-028 failure policy.

    Returns:
        A terminal CLI-local exit code if the scheduled loop must stop
        immediately, or ``None`` if the loop should continue — whether this
        iteration succeeded or hit a recoverable ``CrawlerError``.
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
            logger.error("scheduled crawl failed: unsupported_source")
            return EXIT_UNSUPPORTED_SOURCE
        except CrawlerError:
            logger.error(
                "scheduled crawl iteration failed: crawl_domain_failure "
                "(recoverable, continuing)"
            )
            return None
        except Exception:
            logger.error("scheduled crawl failed: unexpected_failure")
            return EXIT_UNEXPECTED_FAILURE
        else:
            print(payload)
            logger.info("scheduled crawl iteration completed")
            if sink is not None:
                try:
                    sink.save(item)
                except PersistenceWriteError:
                    logger.error(
                        "scheduled crawl iteration succeeded but persistence failed"
                    )
                    return EXIT_PERSISTENCE_FAILURE
            return None


def run_scheduled_crawl(
    url: str,
    *,
    interval: float,
    output: Path | None = None,
    max_runs: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Repeat one synchronous article crawl on an interval (ADR-028).

    Bootstraps the application and opens exactly one
    ``ApplicationRuntime`` for the entire run, then calls
    ``ArticleCrawlService.crawl(url)`` immediately, waits ``interval``
    seconds, and repeats — until ``max_runs`` iterations complete (if
    given), a keyboard interrupt is received, or a terminal failure occurs.

    Per-iteration failure policy (ADR-028):

    - ``CrawlerError`` is recoverable: logged, no output for that
      iteration, the loop continues after the usual wait.
    - ``UnsupportedSourceError``, an unexpected ``Exception``, and a
      post-crawl persistence failure are terminal: logged, the loop stops
      immediately, and this function returns without waiting again.
    - A keyboard interrupt and reaching ``max_runs`` are both treated as a
      clean shutdown (``EXIT_SUCCESS``), not a failure.

    Args:
        url: The single article URL to crawl on every iteration, exactly
            as supplied by the caller.
        interval: Seconds to wait between the end of one iteration and the
            start of the next. The first crawl happens immediately, with
            no initial wait.
        output: An optional destination path. When supplied, each
            successful iteration's produced item is also appended to it
            via ``FileCrawlResultSink`` (ADR-024/ADR-027), after that
            iteration's JSON payload has already been printed to stdout.
        max_runs: An optional bound on the number of iterations. When
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
        logger.error("scheduled crawl failed: startup_failure")
        return EXIT_STARTUP_FAILURE
    except Exception:
        logger.error("scheduled crawl failed: unexpected_failure")
        return EXIT_UNEXPECTED_FAILURE

    sink = FileCrawlResultSink(destination=output) if output is not None else None

    try:
        with create_application_runtime() as runtime:
            logger.info("scheduled crawl started")
            run_count = 0
            while max_runs is None or run_count < max_runs:
                result = _run_iteration(runtime, url, sink)
                if result is not None:
                    return result

                run_count += 1
                if max_runs is not None and run_count >= max_runs:
                    break
                sleep(interval)

            logger.info("scheduled crawl finished: max_runs reached")
            return EXIT_SUCCESS
    except KeyboardInterrupt:
        logger.info("scheduled crawl interrupted, shutting down cleanly")
        return EXIT_SUCCESS
