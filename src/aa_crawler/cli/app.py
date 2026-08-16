"""Synchronous process boundary around the application runtime (ADR-023).

This module owns exactly the sequence approved by ADR-023: resolve the
process working directory, bootstrap application settings and logging,
compose one application runtime, execute one article crawl, serialize the
single resulting item, and translate known exceptions into a small,
CLI-local exit-code mapping. It does not implement source, robots, retry,
identity, or parser governance of its own.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Final

from aa_crawler.application import UnsupportedSourceError, create_application_runtime
from aa_crawler.bootstrap import bootstrap_application
from aa_crawler.configuration import AACrawlerError
from aa_crawler.crawler import CrawlerError
from aa_crawler.observability import correlation_context

logger = logging.getLogger(__name__)

#: CLI-local process exit codes for this command only. These values are not
#: a project-wide exception taxonomy (ADR-018 remains Deferred); they exist
#: solely to give this one process boundary a small, deterministic contract.
EXIT_SUCCESS: Final = 0
EXIT_UNEXPECTED_FAILURE: Final = 1
EXIT_UNSUPPORTED_SOURCE: Final = 2
EXIT_CRAWL_FAILURE: Final = 3
EXIT_STARTUP_FAILURE: Final = 4


def run_crawl(url: str) -> int:
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

    Args:
        url: The single article URL to crawl, exactly as supplied by the
            caller.

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
                payload = json.dumps(dict(items[0].data), sort_keys=True)
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
            return EXIT_SUCCESS
