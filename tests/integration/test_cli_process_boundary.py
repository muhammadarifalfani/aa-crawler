"""Process-boundary integration test for the ADR-023 CLI entry point.

Exercises the real top-level ``aa_crawler.main()`` delegator, the real
``aa_crawler.cli`` argument boundary, real ``bootstrap_application()``,
the real cross-package composition inside ``create_application_runtime()``
(identity, policies, source registry, parser composer, application
service), and the real ``JsonLdArticleParser``. Only the deepest
acquisition leaf (``HtmlFetcher``) is replaced with a synthetic, network-free
double; ``HttpClient`` is additionally guarded so any attempted network
call fails the test immediately. This does not duplicate the Sprint 5
application/runtime integration suites — it proves the process boundary
itself, not lower-layer behavior already covered there.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

import aa_crawler.application.runtime as runtime_module
from aa_crawler import main
from aa_crawler.html import HtmlDocument
from aa_crawler.http import HttpClient, RetryPolicy, TimeoutPolicy

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from pytest import CaptureFixture, MonkeyPatch

    from aa_crawler.crawler import CrawlerRequest, CrawlerResponse
    from aa_crawler.identity import RequestIdentity
    from aa_crawler.robots import RobotsPolicy

_CNN_URL = (
    "https://www.cnnindonesia.com/nasional/20990101010101-20-9999999/"
    "invented-cli-process-boundary-story"
)


@pytest.fixture(autouse=True)
def restore_aa_crawler_logger() -> Iterator[None]:
    """Keep real bootstrap logging isolated from the process test state."""
    logger = logging.getLogger("aa_crawler")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    yield
    for handler in logger.handlers:
        if handler not in original_handlers:
            handler.close()
    logger.handlers = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate


class NetworkGuardHttpClient(HttpClient):
    """Use the real client lifecycle while rejecting every send attempt."""

    def __init__(
        self,
        *,
        timeout_policy: TimeoutPolicy,
        retry_policy: RetryPolicy,
    ) -> None:
        super().__init__(timeout_policy=timeout_policy, retry_policy=retry_policy)
        self.send_count = 0

    def send(self, request: CrawlerRequest) -> CrawlerResponse:
        self.send_count += 1
        raise AssertionError(
            f"CLI process boundary attempted network access: {request}"
        )


class FakeHtmlFetcher:
    """Return one deterministic document without acquisition or network access."""

    def __init__(self, document: HtmlDocument) -> None:
        self._document = document
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []
        self.wiring: tuple[HttpClient, RobotsPolicy, RequestIdentity] | None = None

    def fetch(
        self,
        *,
        url: str,
        metadata: Mapping[str, object] | None = None,
    ) -> HtmlDocument:
        self.calls.append((url, metadata))
        return self._document


def _synthetic_document() -> HtmlDocument:
    node = {
        "@type": "NewsArticle",
        "mainEntityOfPage": {"@id": _CNN_URL},
        "headline": "Invented CLI process-boundary headline",
        "datePublished": "2099-01-01T08:30:00+07:00",
    }
    content = (
        '<html lang="id-ID"><head>'
        f'<link rel="canonical" href="{_CNN_URL}">'
        '<script type="application/ld+json">'
        f"{json.dumps(node)}"
        "</script></head><body></body></html>"
    )
    return HtmlDocument(
        requested_url=_CNN_URL,
        final_url=_CNN_URL,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        content=content,
        encoding="utf-8",
    )


def _install_fake_acquisition(monkeypatch: MonkeyPatch) -> FakeHtmlFetcher:
    fetcher = FakeHtmlFetcher(_synthetic_document())
    monkeypatch.setattr(runtime_module, "HttpClient", NetworkGuardHttpClient)

    def create_fetcher(
        *,
        http_client: HttpClient,
        robots_policy: RobotsPolicy,
        identity: RequestIdentity,
    ) -> FakeHtmlFetcher:
        fetcher.wiring = (http_client, robots_policy, identity)
        return fetcher

    monkeypatch.setattr(runtime_module, "HtmlFetcher", create_fetcher)
    return fetcher


def test_cli_process_boundary_produces_json_and_success_exit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Drive the real aa_crawler.main() delegator through a fake acquisition leaf."""
    fetcher = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main([_CNN_URL])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["source"] == "cnn_indonesia"
    assert payload["headline"] == "Invented CLI process-boundary headline"
    assert fetcher.calls == [(_CNN_URL, None)]


def test_cli_process_boundary_rejects_disabled_source_before_acquisition(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """A disabled production profile must fail before the fake fetcher is used."""
    fetcher = _install_fake_acquisition(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["https://www.kompas.com/invented/article"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert fetcher.calls == []
