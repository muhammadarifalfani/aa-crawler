"""Synchronous process boundary around the application runtime (ADR-023).

This module owns exactly the sequence approved by ADR-023: resolve the
process working directory, bootstrap application settings and logging,
compose one application runtime, execute one article crawl, serialize the
single resulting item, and translate known exceptions into a small,
CLI-local exit-code mapping. It does not implement source, robots, retry,
identity, or parser governance of its own.

ADR-027 adds one optional, off-by-default persistence step: when a caller
supplies a destination path, the already-produced ``CrawlerItem`` is also
appended to it via the existing ``FileCrawlResultSink`` (ADR-024), after
the JSON payload has already been printed to stdout. This is one of a few
narrow, reviewed exceptions to this module's otherwise-persistence-unaware
design; ``aa_crawler.application.runtime`` and
``aa_crawler.application.service`` remain fully unaware of persistence.

ADR-031 adds an injectable ``sink_factory`` parameter, defaulting to
``FileCrawlResultSink`` to preserve this exact ADR-027 behavior: ``main()``
resolves the CLI's ``--sink`` argument to a concrete sink class once and
passes it down here, letting ``--sink sqlite`` construct
``SqliteCrawlResultSink`` instead without this function needing to know
about ``--sink`` itself.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from aa_crawler.application import UnsupportedSourceError, create_application_runtime
from aa_crawler.bootstrap import bootstrap_application
from aa_crawler.configuration import AACrawlerError
from aa_crawler.crawler import CrawlerError
from aa_crawler.observability import correlation_context
from aa_crawler.persistence import FileCrawlResultSink, PersistenceWriteError

if TYPE_CHECKING:
    from aa_crawler.persistence import BaseCrawlResultSink

logger = logging.getLogger(__name__)


class SinkFactory(Protocol):
    """Constructs a `BaseCrawlResultSink` for a given destination (ADR-031).

    `FileCrawlResultSink` and `SqliteCrawlResultSink` both satisfy this
    Protocol via their identical `__init__(self, *, destination: Path)`
    shape; no explicit registration is required.
    """

    def __call__(self, *, destination: Path) -> BaseCrawlResultSink: ...


#: CLI-local process exit codes for this command only. These values are not
#: a project-wide exception taxonomy (ADR-018 remains Deferred); they exist
#: solely to give this one process boundary a small, deterministic contract.
EXIT_SUCCESS: Final = 0
EXIT_UNEXPECTED_FAILURE: Final = 1
EXIT_UNSUPPORTED_SOURCE: Final = 2
EXIT_CRAWL_FAILURE: Final = 3
EXIT_STARTUP_FAILURE: Final = 4
EXIT_PERSISTENCE_FAILURE: Final = 5


def run_crawl(
    url: str,
    *,
    output: Path | None = None,
    sink_factory: SinkFactory = FileCrawlResultSink,
) -> int:
    """Execute one synchronous article crawl and report its CLI exit code.

    Follows the ADR-023 sequence: ``bootstrap_application()`` first, then
    ``create_application_runtime()`` as a context manager, then exactly one
    ``ArticleCrawlService.crawl(url)`` call. On success, the single produced
    item is serialized as one JSON object on stdout. On failure, a
    conservative failure category is logged (never the raw exception detail,
    never headers, cookies, or response content) and a deterministic
    CLI-local exit code is returned. The runtime is not created if bootstrap
    fails, and the runtime is always closed before this function returns
    once it has been created.

    Per ADR-027, when ``output`` is supplied, the produced item is also
    saved to it via ``sink_factory(destination=output)`` after the stdout
    payload has already been printed. A failure at that point does not
    un-print the payload; it is reported through ``EXIT_PERSISTENCE_FAILURE``
    alone.

    Args:
        url: The single article URL to crawl, exactly as supplied by the
            caller.
        output: An optional destination path. When ``None`` (the default),
            this function's behavior is unchanged from ADR-023 and no
            reference to ``aa_crawler.persistence`` is exercised.
        sink_factory: The concrete sink class to construct when ``output``
            is supplied (ADR-031). Defaults to ``FileCrawlResultSink``,
            preserving ADR-027's exact original behavior.

    Returns:
        A CLI-local process exit code (see the ``EXIT_*`` constants).
    """
    with correlation_context(uuid.uuid4().hex):
        try:
            bootstrap_application(base_dir=Path.cwd())
            with create_application_runtime() as runtime:
                logger.info("crawl started")
                items = runtime.article_crawl_service.crawl(url)
                if len(items) != 1:
                    raise ValueError(
                        "expected exactly one crawler item from the "
                        "current shipped parser family"
                    )
                item = items[0]
                payload = json.dumps(dict(item.data), sort_keys=True)
        except UnsupportedSourceError:
            logger.error("crawl failed: unsupported_source")
            return EXIT_UNSUPPORTED_SOURCE
        except CrawlerError:
            logger.error("crawl failed: crawl_domain_failure")
            return EXIT_CRAWL_FAILURE
        except AACrawlerError:
            logger.error("crawl failed: startup_failure")
            return EXIT_STARTUP_FAILURE
        except Exception:
            logger.error("crawl failed: unexpected_failure")
            return EXIT_UNEXPECTED_FAILURE
        else:
            print(payload)
            logger.info("crawl completed")
            if output is not None:
                try:
                    sink_factory(destination=output).save(item)
                except PersistenceWriteError:
                    logger.error("crawl succeeded but persistence failed")
                    return EXIT_PERSISTENCE_FAILURE
            return EXIT_SUCCESS
