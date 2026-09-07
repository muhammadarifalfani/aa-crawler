"""Unit tests for the ADR-028 CLI scheduled crawl mode."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

import aa_crawler.cli.scheduler as scheduler_module
from aa_crawler.application import UnsupportedSourceError
from aa_crawler.cli.app import (
    EXIT_PERSISTENCE_FAILURE,
    EXIT_STARTUP_FAILURE,
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_FAILURE,
    EXIT_UNSUPPORTED_SOURCE,
)
from aa_crawler.cli.scheduler import run_scheduled_crawl
from aa_crawler.configuration import MissingSettingError
from aa_crawler.crawler import CrawlerItem, RequestError
from aa_crawler.observability import get_correlation_id

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from pytest import CaptureFixture, LogCaptureFixture, MonkeyPatch

_CNN_URL = "https://www.cnnindonesia.com/nasional/invented-scheduler-story"


class _FakeService:
    """Duck-typed ``ArticleCrawlService.crawl()`` stand-in with one scripted
    outcome per call, consumed in order.
    """

    def __init__(
        self, outcomes: Sequence[tuple[CrawlerItem, ...] | BaseException]
    ) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[str] = []

    def crawl(self, url: str) -> tuple[CrawlerItem, ...]:
        self.calls.append(url)
        outcome = self._outcomes.pop(0)
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

    monkeypatch.setattr(scheduler_module, "bootstrap_application", fake_bootstrap)
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

    monkeypatch.setattr(
        scheduler_module,
        "create_application_runtime",
        fake_create_runtime,
    )
    return created


def _fake_sleep(record: list[float]) -> Callable[[float], None]:
    def sleep(seconds: float) -> None:
        record.append(seconds)

    return sleep


def _item(headline: str = "Invented scheduled headline") -> CrawlerItem:
    return CrawlerItem({"source": "cnn_indonesia", "headline": headline})


# --- Immediate first crawl and interval waiting ------------------------------


def test_first_crawl_happens_immediately_without_waiting(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    waits: list[float] = []

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=300, max_runs=1, sleep=_fake_sleep(waits)
    )

    assert exit_code == EXIT_SUCCESS
    assert service.calls == [_CNN_URL]
    assert waits == []
    capsys.readouterr()


def test_interval_wait_happens_between_but_not_after_the_last_iteration(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),), (_item(),), (_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    waits: list[float] = []

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=45, max_runs=3, sleep=_fake_sleep(waits)
    )

    assert exit_code == EXIT_SUCCESS
    assert len(service.calls) == 3
    assert waits == [45, 45]
    capsys.readouterr()


# --- --max-runs bounding -------------------------------------------------------


def test_max_runs_bounds_iteration_count_and_exits_success(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),)] * 5)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=1, max_runs=3, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_SUCCESS
    assert len(service.calls) == 3
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_one_runtime_is_reused_across_all_scheduled_iterations(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),)] * 3)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    run_scheduled_crawl(_CNN_URL, interval=1, max_runs=3, sleep=_fake_sleep([]))

    assert len(runtimes) == 1
    assert runtimes[0].enter_count == 1
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


# --- Recoverable vs. terminal per-iteration failure policy (ADR-028) ---------


def test_recoverable_crawler_error_continues_to_the_next_iteration(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([RequestError("transient"), (_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=1, max_runs=2, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_SUCCESS
    assert len(service.calls) == 2
    captured = capsys.readouterr()
    # Only the second, successful iteration printed a payload.
    lines = captured.out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source"] == "cnn_indonesia"


def test_recoverable_crawler_error_is_logged(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    caplog: LogCaptureFixture,
) -> None:
    service = _FakeService([RequestError("transient"), (_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    with caplog.at_level(logging.ERROR, logger="aa_crawler.cli.scheduler"):
        run_scheduled_crawl(_CNN_URL, interval=1, max_runs=2, sleep=_fake_sleep([]))

    messages = [record.getMessage() for record in caplog.records]
    assert any("recoverable" in message for message in messages)
    capsys.readouterr()


def test_unsupported_source_stops_the_loop_immediately(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([UnsupportedSourceError()] + [(_item(),)] * 4)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=1, max_runs=5, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_UNSUPPORTED_SOURCE
    assert len(service.calls) == 1
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""


def test_unexpected_failure_stops_the_loop_immediately(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([RuntimeError("injected")] + [(_item(),)] * 4)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=1, max_runs=5, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert len(service.calls) == 1
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "items",
    [(), (CrawlerItem({"a": "1"}), CrawlerItem({"a": "2"}))],
    ids=["zero_items", "two_items"],
)
def test_unexpected_item_cardinality_stops_the_loop_immediately(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    items: tuple[CrawlerItem, ...],
) -> None:
    service = _FakeService([items])
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(_CNN_URL, interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert len(service.calls) == 1
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""


# --- CLI-triggered persistence per iteration (ADR-024/ADR-027 reuse) --------


def test_output_persists_once_per_successful_iteration_only(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    service = _FakeService(
        [(_item("first"),), RequestError("transient"), (_item("second"),)]
    )
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "results.jsonl"

    exit_code = run_scheduled_crawl(
        _CNN_URL,
        interval=1,
        max_runs=3,
        output=destination,
        sleep=_fake_sleep([]),
    )

    assert exit_code == EXIT_SUCCESS
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["headline"] == "first"
    assert json.loads(lines[1])["headline"] == "second"
    capsys.readouterr()


def test_persistence_failure_stops_the_loop_after_the_successful_crawl(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    service = _FakeService([(_item(),)] * 5)
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "missing-parent-dir" / "results.jsonl"

    exit_code = run_scheduled_crawl(
        _CNN_URL,
        interval=1,
        max_runs=5,
        output=destination,
        sleep=_fake_sleep([]),
    )

    assert exit_code == EXIT_PERSISTENCE_FAILURE
    assert len(service.calls) == 1
    assert runtimes[0].exit_count == 1
    # The stdout payload for that iteration was already printed and is not
    # retracted, matching ADR-027's existing single-shot precedent.
    captured = capsys.readouterr()
    assert json.loads(captured.out.strip())["source"] == "cnn_indonesia"


# --- Output contract: JSON Lines, one object per successful iteration -------


def test_scheduled_stdout_is_json_lines_one_object_per_iteration(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item("a"),), (_item("b"),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    run_scheduled_crawl(_CNN_URL, interval=1, max_runs=2, sleep=_fake_sleep([]))

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["headline"] == "a"
    assert json.loads(lines[1])["headline"] == "b"


# --- Clean shutdown on interrupt ---------------------------------------------


def test_keyboard_interrupt_during_crawl_exits_cleanly(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([KeyboardInterrupt()])
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(_CNN_URL, interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_SUCCESS
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_keyboard_interrupt_during_wait_exits_cleanly(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),), (_item(),)])
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    def raising_sleep(_seconds: float) -> None:
        raise KeyboardInterrupt

    exit_code = run_scheduled_crawl(_CNN_URL, interval=1, sleep=raising_sleep)

    assert exit_code == EXIT_SUCCESS
    # Interrupted during the wait after the first iteration: only one crawl
    # happened, and cleanup still ran exactly once.
    assert len(service.calls) == 1
    assert runtimes[0].exit_count == 1
    capsys.readouterr()


def test_keyboard_interrupt_is_logged(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    caplog: LogCaptureFixture,
) -> None:
    service = _FakeService([KeyboardInterrupt()])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    with caplog.at_level(logging.INFO, logger="aa_crawler.cli.scheduler"):
        run_scheduled_crawl(_CNN_URL, interval=1, sleep=_fake_sleep([]))

    messages = [record.getMessage() for record in caplog.records]
    assert "scheduled crawl interrupted, shutting down cleanly" in messages
    capsys.readouterr()


# --- Startup / bootstrap failure ----------------------------------------------


def test_bootstrap_failure_maps_to_startup_exit_code_and_skips_runtime(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=MissingSettingError("field", "constraint"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(scheduler_module, "create_application_runtime", fail_if_called)

    exit_code = run_scheduled_crawl(_CNN_URL, interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_STARTUP_FAILURE
    assert capsys.readouterr().out == ""


def test_bootstrap_unexpected_failure_maps_to_fallback_exit_code(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    _patch_bootstrap(monkeypatch, error=RuntimeError("injected"))

    def fail_if_called() -> None:
        raise AssertionError("runtime must not be created when bootstrap fails")

    monkeypatch.setattr(scheduler_module, "create_application_runtime", fail_if_called)

    exit_code = run_scheduled_crawl(_CNN_URL, interval=1, sleep=_fake_sleep([]))

    assert exit_code == EXIT_UNEXPECTED_FAILURE
    assert capsys.readouterr().out == ""


# --- max_runs edge case --------------------------------------------------------


def test_max_runs_zero_performs_no_iterations_and_exits_success(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([])
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    exit_code = run_scheduled_crawl(
        _CNN_URL, interval=1, max_runs=0, sleep=_fake_sleep([])
    )

    assert exit_code == EXIT_SUCCESS
    assert service.calls == []
    assert runtimes[0].exit_count == 1
    assert capsys.readouterr().out == ""


# --- Correlation context ------------------------------------------------------


def test_correlation_id_is_reset_after_the_scheduled_run(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService([(_item(),), (_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    assert get_correlation_id() is None
    run_scheduled_crawl(_CNN_URL, interval=1, max_runs=2, sleep=_fake_sleep([]))
    assert get_correlation_id() is None
    capsys.readouterr()


def test_correlation_id_differs_between_iterations(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    seen: list[str | None] = []

    class _RecordingService(_FakeService):
        def crawl(self, url: str) -> tuple[CrawlerItem, ...]:
            seen.append(get_correlation_id())
            return super().crawl(url)

    service = _RecordingService([(_item(),), (_item(),)])
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)

    run_scheduled_crawl(_CNN_URL, interval=1, max_runs=2, sleep=_fake_sleep([]))

    assert len(seen) == 2
    assert seen[0] is not None
    assert seen[1] is not None
    assert seen[0] != seen[1]
    capsys.readouterr()
