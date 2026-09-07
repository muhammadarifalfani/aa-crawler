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
    EXIT_PERSISTENCE_FAILURE,
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
    received_output: list[Path | None] = []

    def fake_run_crawl(url: str, *, output: Path | None = None) -> int:
        received.append(url)
        received_output.append(output)
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_crawl", fake_run_crawl)

    exit_code = main([_CNN_URL])

    assert exit_code == EXIT_SUCCESS
    assert received == [_CNN_URL]
    assert received_output == [None]


def test_output_argument_is_parsed_and_forwarded_as_a_path(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    received_output: list[Path | None] = []

    def fake_run_crawl(url: str, *, output: Path | None = None) -> int:
        del url
        received_output.append(output)
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_crawl", fake_run_crawl)
    destination = tmp_path / "results.jsonl"

    exit_code = main([_CNN_URL, "--output", str(destination)])

    assert exit_code == EXIT_SUCCESS
    assert received_output == [destination]


# --- Scheduled crawl mode dispatch (ADR-028) ----------------------------------


def test_default_invocation_dispatches_to_single_shot_run_crawl(
    monkeypatch: MonkeyPatch,
) -> None:
    single_shot_calls: list[str] = []

    def fake_run_crawl(url: str, *, output: Path | None = None) -> int:
        del output
        single_shot_calls.append(url)
        return EXIT_SUCCESS

    def fail_if_scheduled_mode_runs(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("scheduled mode must not run")

    monkeypatch.setattr(cli_module, "run_crawl", fake_run_crawl)
    monkeypatch.setattr(cli_module, "run_scheduled_crawl", fail_if_scheduled_mode_runs)

    exit_code = main([_CNN_URL])

    assert exit_code == EXIT_SUCCESS
    assert single_shot_calls == [_CNN_URL]


def test_interval_argument_dispatches_to_scheduled_crawl_not_single_shot(
    monkeypatch: MonkeyPatch,
) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(
        cli_module,
        "run_crawl",
        lambda *_args, **_kwargs: pytest.fail("single-shot mode must not run"),
    )

    def fake_run_scheduled_crawl(
        url: str,
        *,
        interval: float,
        output: Path | None = None,
        max_runs: int | None = None,
    ) -> int:
        received["url"] = url
        received["interval"] = interval
        received["output"] = output
        received["max_runs"] = max_runs
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_scheduled_crawl", fake_run_scheduled_crawl)

    exit_code = main([_CNN_URL, "--interval", "5"])

    assert exit_code == EXIT_SUCCESS
    assert received == {
        "url": _CNN_URL,
        "interval": 5.0,
        "output": None,
        "max_runs": None,
    }


def test_interval_output_and_max_runs_are_all_forwarded_together(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    received: dict[str, object] = {}

    def fake_run_scheduled_crawl(
        url: str,
        *,
        interval: float,
        output: Path | None = None,
        max_runs: int | None = None,
    ) -> int:
        received["url"] = url
        received["interval"] = interval
        received["output"] = output
        received["max_runs"] = max_runs
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_scheduled_crawl", fake_run_scheduled_crawl)
    destination = tmp_path / "results.jsonl"

    exit_code = main(
        [
            _CNN_URL,
            "--interval",
            "30",
            "--max-runs",
            "10",
            "--output",
            str(destination),
        ]
    )

    assert exit_code == EXIT_SUCCESS
    assert received == {
        "url": _CNN_URL,
        "interval": 30.0,
        "output": destination,
        "max_runs": 10,
    }


def test_max_runs_without_interval_is_rejected_by_argument_parsing() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([_CNN_URL, "--max-runs", "3"])

    assert excinfo.value.code == 2


@pytest.mark.parametrize("raw_interval", ["0", "-5"])
def test_non_positive_interval_is_rejected_by_argument_parsing(
    raw_interval: str,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([_CNN_URL, "--interval", raw_interval])

    assert excinfo.value.code == 2


@pytest.mark.parametrize("raw_max_runs", ["0", "-1"])
def test_non_positive_max_runs_is_rejected_by_argument_parsing(
    raw_max_runs: str,
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([_CNN_URL, "--interval", "5", "--max-runs", raw_max_runs])

    assert excinfo.value.code == 2


# --- Batch/multi-URL input dispatch (ADR-029) --------------------------------


def test_supplying_neither_url_nor_urls_file_is_rejected() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])

    assert excinfo.value.code == 2


def test_supplying_both_url_and_urls_file_is_rejected(tmp_path: Path) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"{_CNN_URL}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main([_CNN_URL, "--urls-file", str(urls_file)])

    assert excinfo.value.code == 2


def test_urls_file_argument_dispatches_to_batch_crawl_not_single_shot(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(
        f"{_CNN_URL}\nhttps://www.cnnindonesia.com/b\n", encoding="utf-8"
    )
    received: dict[str, object] = {}

    def fake_run_batch_crawl(urls: list[str], *, output: Path | None = None) -> int:
        received["urls"] = list(urls)
        received["output"] = output
        return EXIT_SUCCESS

    def fail_if_called(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("this mode must not run")

    monkeypatch.setattr(cli_module, "run_batch_crawl", fake_run_batch_crawl)
    monkeypatch.setattr(cli_module, "run_scheduled_batch_crawl", fail_if_called)
    monkeypatch.setattr(cli_module, "run_crawl", fail_if_called)
    monkeypatch.setattr(cli_module, "run_scheduled_crawl", fail_if_called)

    exit_code = main(["--urls-file", str(urls_file)])

    assert exit_code == EXIT_SUCCESS
    assert received == {
        "urls": [_CNN_URL, "https://www.cnnindonesia.com/b"],
        "output": None,
    }


def test_urls_file_with_interval_dispatches_to_scheduled_batch_crawl(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"{_CNN_URL}\n", encoding="utf-8")
    received: dict[str, object] = {}

    def fake_run_scheduled_batch_crawl(
        urls: list[str],
        *,
        interval: float,
        output: Path | None = None,
        max_runs: int | None = None,
    ) -> int:
        received["urls"] = list(urls)
        received["interval"] = interval
        received["output"] = output
        received["max_runs"] = max_runs
        return EXIT_SUCCESS

    def fail_if_called(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("this mode must not run")

    monkeypatch.setattr(
        cli_module, "run_scheduled_batch_crawl", fake_run_scheduled_batch_crawl
    )
    monkeypatch.setattr(cli_module, "run_batch_crawl", fail_if_called)
    monkeypatch.setattr(cli_module, "run_crawl", fail_if_called)
    monkeypatch.setattr(cli_module, "run_scheduled_crawl", fail_if_called)

    exit_code = main(
        ["--urls-file", str(urls_file), "--interval", "60", "--max-runs", "3"]
    )

    assert exit_code == EXIT_SUCCESS
    assert received == {
        "urls": [_CNN_URL],
        "interval": 60.0,
        "output": None,
        "max_runs": 3,
    }


def test_urls_file_parses_urls_skipping_blank_lines_and_comments(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(
        "\n".join(
            [
                "# a comment line",
                "",
                _CNN_URL,
                "   ",
                "# another comment",
                "https://www.cnnindonesia.com/b",
                "",
            ]
        ),
        encoding="utf-8",
    )
    received: dict[str, object] = {}

    def fake_run_batch_crawl(urls: list[str], *, output: Path | None = None) -> int:
        del output
        received["urls"] = list(urls)
        return EXIT_SUCCESS

    monkeypatch.setattr(cli_module, "run_batch_crawl", fake_run_batch_crawl)

    exit_code = main(["--urls-file", str(urls_file)])

    assert exit_code == EXIT_SUCCESS
    assert received["urls"] == [_CNN_URL, "https://www.cnnindonesia.com/b"]


def test_urls_file_that_does_not_exist_is_rejected_with_clear_error(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "does-not-exist.txt"

    with pytest.raises(SystemExit) as excinfo:
        main(["--urls-file", str(missing)])

    assert excinfo.value.code == 2


def test_urls_file_containing_no_urls_is_rejected_with_clear_error(
    tmp_path: Path,
) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("# only comments\n\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["--urls-file", str(urls_file)])

    assert excinfo.value.code == 2


def test_max_runs_with_urls_file_but_without_interval_is_rejected(
    tmp_path: Path,
) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(f"{_CNN_URL}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["--urls-file", str(urls_file), "--max-runs", "3"])

    assert excinfo.value.code == 2


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


# --- CLI-triggered persistence (ADR-027) -------------------------------------


def test_default_invocation_never_writes_a_file(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    monkeypatch.chdir(tmp_path)

    exit_code = run_crawl(_CNN_URL)

    assert exit_code == EXIT_SUCCESS
    assert capsys.readouterr().out.strip() == json.dumps(
        {"source": "cnn_indonesia"}, sort_keys=True
    )
    assert list(tmp_path.iterdir()) == []


def test_output_argument_persists_the_produced_item(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia", "headline": "Invented headline"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "results.jsonl"

    exit_code = run_crawl(_CNN_URL, output=destination)

    captured = capsys.readouterr()
    assert exit_code == EXIT_SUCCESS
    assert json.loads(captured.out) == {
        "source": "cnn_indonesia",
        "headline": "Invented headline",
    }
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "source": "cnn_indonesia",
        "headline": "Invented headline",
    }


def test_output_argument_appends_without_deduplication(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "results.jsonl"

    run_crawl(_CNN_URL, output=destination)
    _patch_runtime(monkeypatch, service=_FakeService(result=(item,)))
    run_crawl(_CNN_URL, output=destination)

    capsys.readouterr()
    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == lines[1]


def test_persistence_failure_after_successful_crawl_still_prints_stdout(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    # A destination whose parent directory does not exist makes the real
    # FileCrawlResultSink raise PersistenceWriteError deterministically,
    # without needing to fake the sink itself.
    destination = tmp_path / "does-not-exist-as-a-directory" / "results.jsonl"

    exit_code = run_crawl(_CNN_URL, output=destination)

    captured = capsys.readouterr()
    assert exit_code == EXIT_PERSISTENCE_FAILURE
    assert json.loads(captured.out) == {"source": "cnn_indonesia"}


def test_persistence_failure_is_logged_conservatively(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    caplog: LogCaptureFixture,
    tmp_path: Path,
) -> None:
    item = CrawlerItem({"source": "cnn_indonesia"})
    service = _FakeService(result=(item,))
    _patch_bootstrap(monkeypatch)
    _patch_runtime(monkeypatch, service=service)
    destination = tmp_path / "does-not-exist-as-a-directory" / "results.jsonl"

    with caplog.at_level(logging.ERROR, logger="aa_crawler.cli.app"):
        exit_code = run_crawl(_CNN_URL, output=destination)

    assert exit_code == EXIT_PERSISTENCE_FAILURE
    messages = [record.getMessage() for record in caplog.records]
    assert "crawl succeeded but persistence failed" in messages
    capsys.readouterr()


# --- Unsupported source ------------------------------------------------------


def test_unsupported_source_maps_to_accepted_exit_code_with_cleanup(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    service = _FakeService(error=UnsupportedSourceError())
    _patch_bootstrap(monkeypatch)
    runtimes = _patch_runtime(monkeypatch, service=service)

    # The fake service raises regardless of URL; this host is an arbitrary
    # placeholder, not evidence of any real source's governance state.
    exit_code = run_crawl("https://unsupported.example.test/invented/article")

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
