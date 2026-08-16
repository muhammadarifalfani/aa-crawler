"""Unit tests for the ADR-023 CLI process boundary."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import aa_crawler.cli as cli_module
import aa_crawler.cli.app as cli_app_module
from aa_crawler.application import SourceBoundaryError, UnsupportedSourceError
from aa_crawler.cli import main
from aa_crawler.cli.app import (
    EXIT_CRAWL_FAILURE,
    EXIT_STARTUP_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_FAILURE,
    EXIT_UNSUPPORTED_SOURCE,
    run_crawl,
)
from aa_crawler.configuration import LoggingSetupError, MissingSettingError
from aa_crawler.crawler import CrawlerItem, RequestError
from aa_crawler.observability import get_correlation_id
from aa_crawler.sources import SourceRegistryError

if TYPE_CHECKING:
    from pytest import CaptureFixture, LogCaptureFixture, MonkeyPatch

_CNN_URL = "https://www.cnnindonesia.com/nasional/invented-cli-story"


class _FakeService:
    """Duck-typed stand-in for ArticleCrawlService.crawl()."""

    def __init__(
        self,
        *,
        result: tuple[CrawlerItem, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.calls: list[str] = []

    def crawl(self, url: str) -> tuple[CrawlerItem, ...]:
        self.calls.append(url)
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _FakeRuntime:
    """Duck-typed stand-in for ApplicationRuntime's context-manager lifecycle."""

    def __init__(self, service: _FakeService) -> None:
        self.article_crawl_service = service
        self.enter_count = 0
        self.exit_count = 0

    def __enter__(self) -> _FakeRuntime:
        self.enter_count += 1
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.exit_count += 1


def _patch_bootstrap(
    monkeypatch: MonkeyPatch,
    *,
    error: Exception | None = None,
) -> list[Path]:
    calls: list[Path] = []

    def fake_bootstrap(*, base_dir: Path) -> None:
        calls.append(base_dir)
        if error is not None:
            raise error

    monkeypatch.setattr(cli_app_module, "bootstrap_application", fake_bootstrap)
    return calls


def _patch_runtime(
    monkeypatch: MonkeyPatch,
    *,
    service: _FakeService | None = None,
    construction_error: Exception | None = None,
) -> list[_FakeRuntime]:
    created: list[_FakeRuntime] = []

    def fake_create_runtime() -> _FakeRuntime:
        if construction_error is not None:
            raise construction_error
        assert service is not None
        runtime = _FakeRuntime(service)
        created.append(runtime)
        return runtime

    monkeypatch.setattr(
        cli_app_module,
        "create_application_runtime",
        fake_create_runtime,
    )
    return created


# --- Argument parsing -------------------------------------------------------


def test_missing_url_argument_exits_with_argparse_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2


def test_unexpected_extra_argument_exits_with_argparse_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([_CNN_URL, "unexpected-extra-argument"])

    assert excinfo.value.code == 2


def test_valid_single_url_is_parsed_and_forwarded_unchanged(
    monkeypatch: MonkeyPatch,
) -> None:
    received: list[str] = []

    def fake_run_crawl(url: str) -> int:
        received.append(url)
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_crawl", fake_run_crawl)

    exit_code = main([_CNN_URL])

    assert exit_code == EXIT_SUCCESS
    assert received == [_CNN_URL]


# --- Successful execution ----------------------------------------------------


def test_successful_crawl_serializes_one_json_object_and_exits_success(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    item = CrawlerItem(
        {
            "source": "cnn_indonesia",
            "headline": "Invented CLI headline",
            "author_names": ("Author One", "Author Two"),
        }
    )
    service = _FakeService(result=(item,))
    bootstrap_calls = _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl(_CNN_URL)

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert bootstrap_calls == [Path.cwd()]
    assert service.calls == [_CNN_URL]
    assert runtimes[0].enter_count == 1
    assert runtimes[0].exit_count == 1
    assert json.loads(captured.out) == {
        "source": "cnn_indonesia",
        "headline": "Invented CLI headline",
        "author_names": ["Author One", "Author Two"],
    }


def test_successful_crawl_does_not_contaminate_stdout_with_logs(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    caplog: LogCaptureFixture,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    with caplog.at_level(logging.INFO, logger="aa_crawler.cli.app"):
        exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_SUCCESS
    messages = [record.getMessage() for record in caplog.records]
    assert "crawl started" in messages
    assert "crawl completed" in messages
    captured = capsys.readouterr()
    expected_payload = json.dumps({"source": "cnn_indonesia"}, sort_keys=True)
    assert captured.out.strip() == expected_payload
    assert "crawl started" not in captured.out
    assert "crawl completed" not in captured.out


# --- Unsupported source ------------------------------------------------------


def test_unsupported_source_maps_to_accepted_exit_code_with_cleanup(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(error=UnsupportedSourceError())
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl("https://www.kompas.com/invented/article")

    captured = capsys.readouterr()
    assert exit_code == EXIT_UNSUPPORTED_SOURCE
    assert captured.out == ""
    assert runtimes[0].exit_count == 1


# --- Other crawl-domain failures ---------------------------------------------


@pytest.mark.parametrize("error", [SourceBoundaryError(), RequestError("boom")])
def test_crawl_domain_failures_map_to_accepted_exit_code_with_cleanup(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    error: Exception,
) -> None:
    service = _FakeService(error=error)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl(_CNN_URL)

    captured = capsys.readouterr()
    assert exit_code == EXIT_CRAWL_FAILURE
    assert captured.out == ""
    assert runtimes[0].exit_count == 1


# --- Configuration / startup failure ------------------------------------------


def test_bootstrap_failure_maps_to_startup_exit_code_and_skips_runtime(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=MissingSettingError("field", "constraint"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(cli_app_module, "create_application_runtime", fail_if_called)

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_STARTUP_FAILURE
    assert capsys.readouterr().out == ""


def test_runtime_construction_configuration_failure_maps_to_startup_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch)
    _patch_runtime(
        monkeypatch,
        construction_error=LoggingSetupError("field", "constraint"),
    )

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_STARTUP_FAILURE
    assert capsys.readouterr().out == ""


# --- Unexpected failure -------------------------------------------------------


def test_runtime_construction_unexpected_failure_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, construction_error=RuntimeError("injected"))

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""


def test_unexpected_crawl_failure_maps_to_fallback_exit_code_with_cleanup(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(error=SourceRegistryError("duplicate source declaration"))
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""
    assert runtimes[0].exit_count == 1


@pytest.mark.parametrize(
    "items",
    [(), (CrawlerItem({"a": "1"}), CrawlerItem({"a": "2"}))],
    ids=["zero_items", "two_items"],
)
def test_unexpected_item_cardinality_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    items: tuple[CrawlerItem, ...],
) -> None:
    service = _FakeService(result=items)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""
    assert runtimes[0].exit_count == 1


def test_serialization_failure_closes_runtime_and_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    item = CrawlerItem({"unserializable": object()})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""
    assert runtimes[0].exit_count == 1


# --- Correlation context ------------------------------------------------------


def test_correlation_id_is_reset_after_invocation(
    monkeypatch: MonkeyPatch,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    assert get_correlation_id() is None
    run_crawl(_CNN_URL)
    assert get_correlation_id() is None
