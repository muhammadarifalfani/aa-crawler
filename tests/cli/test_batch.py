"""Unit tests for the ADR-029 CLI batch/multi-URL crawl mode."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

import aa_crawler.cli.batch as batch_module
from aa_crawler.application import UnsupportedSourceError
from aa_crawler.cli.app import (
    EXIT_PERSISTENCE_FAILURE,
    EXIT_STARTUP_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_FAILURE,
)
from aa_crawler.cli.batch import run_batch_crawl, run_scheduled_batch_crawl
from aa_crawler.configuration import MissingSettingError
from aa_crawler.crawler import CrawlerItem, RequestError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from pytest import CaptureFixture, LogCaptureFixture, MonkeyPatch

_URL_A = "https://www.cnnindonesia.com/nasional/invented-batch-a"
_URL_B = "https://www.cnnindonesia.com/nasional/invented-batch-b"
_URL_C = "https://www.cnnindonesia.com/nasional/invented-batch-c"


class _FakeService:
    """Duck-typed ``ArticleCrawlService.crawl()`` stand-in: one fixed
    outcome per URL, looked up by URL and reusable across multiple passes.
    """

    def __init__(
        self, outcomes: Mapping[str, tuple[CrawlerItem, ...] | BaseException]
    ) -> None:
        self._outcomes = dict(outcomes)
        self.calls: list[str] = []

    def crawl(self, url: str) -> tuple[CrawlerItem, ...]:
        self.calls.append(url)
        outcome = self._outcomes[url]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


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

    monkeypatch.setattr(batch_module, "bootstrap_application", fake_bootstrap)
    return calls


def _patch_runtime(
    monkeypatch: MonkeyPatch,
    *,
    service: _FakeService,
) -> list[_FakeRuntime]:
    created: list[_FakeRuntime] = []

    def fake_create_runtime() -> _FakeRuntime:
        runtime = _FakeRuntime(service)
        created.append(runtime)
        return runtime

    monkeypatch.setattr(batch_module, "create_application_runtime", fake_create_runtime)
    return created


def _fake_sleep(record: list[float]) -> Callable[[float], None]:
    def sleep(seconds: float) -> None:
        record.append(seconds)

    return sleep


def _item(headline: str) -> CrawlerItem:
    return CrawlerItem({"source": "cnn_indonesia", "headline": headline})


# --- One pass over the URL list -----------------------------------------------


def test_batch_crawls_every_url_in_order(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(
        {
            _URL_A: (_item("a"),),
            _URL_B: (_item("b"),),
            _URL_C: (_item("c"),),
        }
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    exit_code = run_batch_crawl([_URL_A, _URL_B, _URL_C])

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A, _URL_B, _URL_C]
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["headline"] for line in lines] == ["a", "b", "c"]


def test_one_runtime_is_reused_across_all_urls_in_one_pass(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),), _URL_B: (_item("b"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    run_batch_crawl([_URL_A, _URL_B])

    assert len(runtimes) == 1
    assert runtimes[0].enter_count == 1
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


# --- Per-URL failure policy (ADR-029, diverging from ADR-028) ---------------


def test_recoverable_unsupported_source_skips_only_that_url_and_continues(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Unlike ADR-028's single-URL scheduled mode, UnsupportedSourceError
    is recoverable in batch mode: one bad URL should not abort the rest.
    """
    service = _FakeService(
        {
            _URL_A: (_item("a"),),
            _URL_B: UnsupportedSourceError(),
            _URL_C: (_item("c"),),
        }
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    exit_code = run_batch_crawl([_URL_A, _URL_B, _URL_C])

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A, _URL_B, _URL_C]
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["headline"] for line in lines] == ["a", "c"]


def test_recoverable_unsupported_source_is_logged(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    caplog: LogCaptureFixture,
) -> None:
    service = _FakeService({_URL_A: UnsupportedSourceError(), _URL_B: (_item("b"),)})
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    with caplog.at_level(logging.ERROR, logger="aa_crawler.cli.batch"):
        run_batch_crawl([_URL_A, _URL_B])

    messages = [record.getMessage() for record in caplog.records]
    assert any("unsupported_source" in message for message in messages)
    capsys.readouterr()


def test_recoverable_crawler_error_skips_only_that_url_and_continues(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(
        {
            _URL_A: (_item("a"),),
            _URL_B: RequestError("transient"),
            _URL_C: (_item("c"),),
        }
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    exit_code = run_batch_crawl([_URL_A, _URL_B, _URL_C])

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A, _URL_B, _URL_C]
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["headline"] for line in lines] == ["a", "c"]


def test_terminal_unexpected_failure_stops_the_batch_immediately(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(
        {
            _URL_A: (_item("a"),),
            _URL_B: RuntimeError("injected"),
            _URL_C: (_item("c"),),
        }
    )
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_batch_crawl([_URL_A, _URL_B, _URL_C])

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    # Stopped at the failing URL; the third URL was never attempted.
    assert service.calls == [_URL_A, _URL_B]
    assert runtimes[0].exit_count == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["headline"] for line in lines] == ["a"]


@pytest.mark.parametrize(
    "items",
    [(), (CrawlerItem({"a": "1"}), CrawlerItem({"a": "2"}))],
    ids=["zero_items", "two_items"],
)
def test_unexpected_item_cardinality_stops_the_batch_immediately(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    items: tuple[CrawlerItem, ...],
) -> None:
    service = _FakeService({_URL_A: items, _URL_B: (_item("b"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_batch_crawl([_URL_A, _URL_B])

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert service.calls == [_URL_A]
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""


# --- CLI-triggered persistence per URL (ADR-024/ADR-027 reuse) --------------


def test_output_persists_once_per_successful_url_only(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    service = _FakeService(
        {
            _URL_A: (_item("a"),),
            _URL_B: RequestError("transient"),
            _URL_C: (_item("c"),),
        }
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "results.jsonl"

    exit_code = run_batch_crawl([_URL_A, _URL_B, _URL_C], output=destination)

    assert exit_code == EXIT_SUCCESS
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["headline"] == "a"
    assert json.loads(lines[1])["headline"] == "c"
    capsys.readouterr()


def test_persistence_failure_stops_the_batch_after_the_successful_crawl(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    service = _FakeService({_URL_A: (_item("a"),), _URL_B: (_item("b"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "missing-parent-dir" / "results.jsonl"

    exit_code = run_batch_crawl([_URL_A, _URL_B], output=destination)

    assert exit_code == EXIT_PERSISTENCE_FAILURE
    assert service.calls == [_URL_A]
    assert runtimes[0].exit_count == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip())["headline"] == "a"


# --- Startup / bootstrap failure ----------------------------------------------


def test_bootstrap_failure_maps_to_startup_exit_code_and_skips_runtime(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=MissingSettingError("field", "constraint"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(batch_module, "create_application_runtime", fail_if_called)

    exit_code = run_batch_crawl([_URL_A])

    assert exit_code == EXIT_STARTUP_FAILURE
    assert capsys.readouterr().out == ""


def test_bootstrap_unexpected_failure_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=RuntimeError("injected"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(batch_module, "create_application_runtime", fail_if_called)

    exit_code = run_batch_crawl([_URL_A])

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""


# --- Scheduled batch mode: repeated passes ------------------------------------


def test_scheduled_batch_first_pass_happens_immediately_without_waiting(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),), _URL_B: (_item("b"),)})
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    waits: list[float] = []

    exit_code = run_scheduled_batch_crawl(
        [_URL_A, _URL_B], interval=300, max_runs=1, sleep=_fake_sleep(waits)
    )

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A, _URL_B]
    assert waits == []
    capsys.readouterr()


def test_scheduled_batch_max_runs_bounds_pass_count_not_url_count(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(
        {_URL_A: (_item("a"),), _URL_B: (_item("b"),), _URL_C: (_item("c"),)}
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    waits: list[float] = []

    exit_code = run_scheduled_batch_crawl(
        [_URL_A, _URL_B, _URL_C], interval=60, max_runs=2, sleep=_fake_sleep(waits)
    )

    assert exit_code == EXIT_SUCCESS
    # Two full passes of three URLs each = six calls, one wait in between.
    assert service.calls == [_URL_A, _URL_B, _URL_C, _URL_A, _URL_B, _URL_C]
    assert waits == [60]
    capsys.readouterr()


def test_scheduled_batch_one_runtime_is_reused_across_all_passes(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    run_scheduled_batch_crawl([_URL_A], interval=1, max_runs=3, sleep=_fake_sleep([]))

    assert len(runtimes) == 1
    assert runtimes[0].enter_count == 1
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_scheduled_batch_recoverable_failure_continues_within_and_across_passes(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),), _URL_B: UnsupportedSourceError()})
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_batch_crawl(
        [_URL_A, _URL_B], interval=1, max_runs=2, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A, _URL_B, _URL_A, _URL_B]
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2  # only URL A ever succeeds, once per pass


def test_scheduled_batch_terminal_failure_stops_the_whole_run(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),), _URL_B: RuntimeError("injected")})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_batch_crawl(
        [_URL_A, _URL_B], interval=1, max_runs=5, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert service.calls == [_URL_A, _URL_B]
    assert runtimes[0].exit_count == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip())["headline"] == "a"


# --- Clean shutdown on interrupt (scheduled batch) --------------------------


def test_scheduled_batch_keyboard_interrupt_during_crawl_exits_cleanly(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: KeyboardInterrupt()})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_batch_crawl([_URL_A], interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_SUCCESS
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_scheduled_batch_keyboard_interrupt_during_wait_exits_cleanly(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    def raising_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    exit_code = run_scheduled_batch_crawl([_URL_A], interval=1, sleep=raising_sleep)

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_URL_A]
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_scheduled_batch_bootstrap_failure_maps_to_startup_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=MissingSettingError("field", "constraint"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(batch_module, "create_application_runtime", fail_if_called)

    exit_code = run_scheduled_batch_crawl([_URL_A], interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_STARTUP_FAILURE
    assert capsys.readouterr().out == ""


def test_scheduled_batch_bootstrap_unexpected_failure_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=RuntimeError("injected"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(batch_module, "create_application_runtime", fail_if_called)

    exit_code = run_scheduled_batch_crawl([_URL_A], interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""


# --- max_runs edge case --------------------------------------------------------


def test_scheduled_batch_max_runs_zero_performs_no_passes_and_exits_success(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService({_URL_A: (_item("a"),)})
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_batch_crawl(
        [_URL_A], interval=1, max_runs=0, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_SUCCESS
    assert service.calls == []
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""
