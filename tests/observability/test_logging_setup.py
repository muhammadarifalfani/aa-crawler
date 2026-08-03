from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from aa_crawler.configuration import (
    ApplicationSettings,
    LoggingSettings,
    LoggingSetupError,
    LogLevel,
    PathSettings,
)
from aa_crawler.observability import configure_logging, correlation_context

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def restore_aa_crawler_logger() -> Iterator[None]:
    logger = logging.getLogger("aa_crawler")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    original_disabled = logger.disabled
    yield
    for handler in logger.handlers:
        if handler not in original_handlers:
            handler.close()
    logger.handlers = original_handlers
    logger.setLevel(original_level)
    logger.propagate = original_propagate
    logger.disabled = original_disabled


def make_settings(
    *,
    tmp_path: Path,
    level: LogLevel = LogLevel.INFO,
    console_enabled: bool = True,
    file_enabled: bool = False,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
) -> ApplicationSettings:
    return ApplicationSettings(
        paths=PathSettings(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            log_dir=tmp_path / "logs",
            config_dir=tmp_path / "config",
            temp_dir=tmp_path / ".tmp",
        ),
        logging=LoggingSettings(
            level=level,
            console_enabled=console_enabled,
            file_enabled=file_enabled,
            max_bytes=max_bytes,
            backup_count=backup_count,
        ),
    )


def owned_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger("aa_crawler").handlers
        if getattr(handler, "_aa_crawler_owned", False)
    ]


def test_console_handler_is_enabled_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(tmp_path=tmp_path))

    logging.getLogger("aa_crawler.test").info("console message")
    captured = capsys.readouterr()

    assert captured.out == ""
    assert "INFO" in captured.err
    assert "aa_crawler.test" in captured.err
    assert "console message" in captured.err
    assert len(owned_handlers()) == 1
    assert type(owned_handlers()[0]) is logging.StreamHandler


def test_console_handler_uses_configured_level(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(tmp_path=tmp_path, level=LogLevel.WARNING))
    child_logger = logging.getLogger("aa_crawler.test")

    child_logger.info("hidden")
    child_logger.warning("visible")

    assert capsys.readouterr().err.endswith("WARNING | aa_crawler.test | - | visible\n")
    assert owned_handlers()[0].level == logging.WARNING


def test_file_handler_is_absent_when_disabled(tmp_path: Path) -> None:
    configure_logging(make_settings(tmp_path=tmp_path))

    assert not any(
        isinstance(handler, RotatingFileHandler) for handler in owned_handlers()
    )
    assert not (tmp_path / "logs").exists()


def test_rotating_file_handler_configuration_and_output(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    settings = make_settings(
        tmp_path=tmp_path,
        console_enabled=False,
        file_enabled=True,
        max_bytes=2048,
        backup_count=3,
    )

    configure_logging(settings)
    handlers = owned_handlers()
    file_handler = handlers[0]

    assert isinstance(file_handler, RotatingFileHandler)
    assert Path(file_handler.baseFilename) == log_dir / "aa-crawler.log"
    assert file_handler.maxBytes == 2048
    assert file_handler.backupCount == 3
    assert file_handler.encoding == "utf-8"
    assert not (log_dir / "aa-crawler.log").exists()

    logging.getLogger("aa_crawler.test").info("file message")
    file_handler.flush()

    output = (log_dir / "aa-crawler.log").read_text(encoding="utf-8")
    assert "INFO | aa_crawler.test | - | file message" in output


def test_file_handler_failure_is_translated_without_partial_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_file_handler(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(
        "aa_crawler.observability.logging_setup.RotatingFileHandler",
        fail_file_handler,
    )
    settings = make_settings(tmp_path=tmp_path, file_enabled=True)

    with pytest.raises(LoggingSetupError) as error_info:
        configure_logging(settings)

    assert "logging" in str(error_info.value).lower()
    assert str(tmp_path / "logs" / "aa-crawler.log") in str(error_info.value)
    assert isinstance(error_info.value.__cause__, OSError)
    assert owned_handlers() == []


def test_repeated_configuration_does_not_duplicate_handlers(tmp_path: Path) -> None:
    settings = make_settings(tmp_path=tmp_path)

    configure_logging(settings)
    first_handler = owned_handlers()[0]
    configure_logging(settings)

    assert len(owned_handlers()) == 1
    assert owned_handlers()[0] is not first_handler


def test_reconfiguration_replaces_only_owned_handlers(tmp_path: Path) -> None:
    logger = logging.getLogger("aa_crawler")
    unrelated_handler = logging.NullHandler()
    logger.addHandler(unrelated_handler)
    configure_logging(make_settings(tmp_path=tmp_path))
    first_owned_handler = owned_handlers()[0]

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    configure_logging(
        make_settings(
            tmp_path=tmp_path,
            console_enabled=False,
            file_enabled=True,
        )
    )

    assert unrelated_handler in logger.handlers
    assert first_owned_handler not in logger.handlers
    assert len(owned_handlers()) == 1
    assert isinstance(owned_handlers()[0], RotatingFileHandler)


def test_child_logger_uses_parent_without_reaching_root(
    tmp_path: Path,
) -> None:
    root_logger = logging.getLogger()
    root_records: list[logging.LogRecord] = []

    class RecordHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            root_records.append(record)

    root_handler = RecordHandler()
    root_logger.addHandler(root_handler)
    try:
        configure_logging(make_settings(tmp_path=tmp_path))
        logger = logging.getLogger("aa_crawler")
        child_logger = logging.getLogger("aa_crawler.collectors")

        child_logger.info("child message")

        assert logger.propagate is False
        assert child_logger.handlers == []
        assert root_records == []
    finally:
        root_logger.removeHandler(root_handler)
        root_handler.close()


def test_logs_use_placeholder_without_correlation_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(tmp_path=tmp_path))

    logging.getLogger("aa_crawler.test").info("context-free")

    assert "aa_crawler.test | - | context-free" in capsys.readouterr().err


def test_child_logs_include_context_and_redact_console_secrets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(tmp_path=tmp_path))

    with correlation_context("request-42"):
        logging.getLogger("aa_crawler.collectors").info(
            "Authorization: Bearer console-secret"
        )

    output = capsys.readouterr().err
    assert "aa_crawler.collectors | request-42 |" in output
    assert "[REDACTED]" in output
    assert "console-secret" not in output


def test_file_logs_include_context_and_redact_secrets(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    configure_logging(
        make_settings(
            tmp_path=tmp_path,
            console_enabled=False,
            file_enabled=True,
        )
    )

    with correlation_context("job-7"):
        logging.getLogger("aa_crawler.test").info("password=file-secret")

    output = (log_dir / "aa-crawler.log").read_text(encoding="utf-8")
    assert "aa_crawler.test | job-7 |" in output
    assert "[REDACTED]" in output
    assert "file-secret" not in output


def test_owned_handlers_receive_each_filter_once_after_reconfiguration(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path=tmp_path)

    configure_logging(settings)
    configure_logging(settings)

    filters = owned_handlers()[0].filters
    assert len(filters) == 2
    assert len({type(handler_filter) for handler_filter in filters}) == 2
