from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

import aa_crawler
import aa_crawler.bootstrap as bootstrap_module
from aa_crawler import bootstrap_application
from aa_crawler.configuration import (
    ApplicationSettings,
    ConfigurationError,
    InvalidPathError,
    LoggingSetupError,
    PathSettings,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def restore_aa_crawler_logger() -> Iterator[None]:
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


def make_settings(tmp_path: Path) -> ApplicationSettings:
    return ApplicationSettings(
        paths=PathSettings(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            log_dir=tmp_path / "logs",
            config_dir=tmp_path / "config",
            temp_dir=tmp_path / ".tmp",
        )
    )


def owned_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in logging.getLogger("aa_crawler").handlers
        if getattr(handler, "_aa_crawler_owned", False)
    ]


def test_real_bootstrap_returns_frozen_resolved_settings(tmp_path: Path) -> None:
    base_dir = tmp_path / "project"
    working_directory = Path.cwd()
    environment = os.environ.copy()

    settings = bootstrap_application(base_dir=base_dir)

    assert isinstance(settings, ApplicationSettings)
    assert settings.paths.base_dir == base_dir
    assert settings.paths.data_dir == base_dir / "data"
    assert settings.paths.temp_dir == base_dir / ".tmp"
    assert settings.paths.data_dir.is_dir()
    assert settings.paths.temp_dir.is_dir()
    assert not settings.paths.log_dir.exists()
    assert not settings.paths.config_dir.exists()
    assert len(owned_handlers()) == 1
    assert Path.cwd() == working_directory
    assert os.environ == environment
    with pytest.raises(ValidationError, match="frozen"):
        settings.debug = True


def test_real_bootstrap_configures_working_file_logging(tmp_path: Path) -> None:
    settings = bootstrap_application(
        base_dir=tmp_path / "project",
        overrides={
            "logging": {
                "console_enabled": False,
                "file_enabled": True,
            }
        },
    )

    assert settings.paths.log_dir.is_dir()
    assert not settings.paths.config_dir.exists()
    logging.getLogger("aa_crawler.bootstrap.test").info("startup complete")
    log_file = settings.paths.log_dir / settings.logging.file_name
    assert "startup complete" in log_file.read_text(encoding="utf-8")


def test_source_precedence_remains_functional(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env.test"
    env_file.write_text("AA_LOG_LEVEL=INFO\n", encoding="utf-8")
    monkeypatch.setenv("AA_LOG_LEVEL", "WARNING")

    settings = bootstrap_application(
        base_dir=tmp_path / "project",
        env_file=env_file,
        overrides={"logging": {"level": "ERROR"}},
    )

    assert settings.logging.level.value == "ERROR"


def test_startup_order_and_settings_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    events: list[tuple[str, ApplicationSettings | None]] = []

    def load(**_kwargs: object) -> ApplicationSettings:
        events.append(("load", None))
        return settings

    def prepare(received: ApplicationSettings) -> None:
        events.append(("prepare", received))

    def configure(received: ApplicationSettings) -> None:
        events.append(("configure", received))

    monkeypatch.setattr(bootstrap_module, "load_settings", load)
    monkeypatch.setattr(bootstrap_module, "prepare_runtime_directories", prepare)
    monkeypatch.setattr(bootstrap_module, "configure_logging", configure)

    result = bootstrap_module.bootstrap_application(base_dir=tmp_path)

    assert events == [
        ("load", None),
        ("prepare", settings),
        ("configure", settings),
    ]
    assert result is settings


def test_configuration_failure_stops_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    error = ConfigurationError("AA_ENV", "invalid test value")
    later_calls: list[str] = []

    def fail_load(**_kwargs: object) -> ApplicationSettings:
        raise error

    monkeypatch.setattr(bootstrap_module, "load_settings", fail_load)
    monkeypatch.setattr(
        bootstrap_module,
        "prepare_runtime_directories",
        lambda _settings: later_calls.append("prepare"),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "configure_logging",
        lambda _settings: later_calls.append("configure"),
    )

    with pytest.raises(ConfigurationError) as error_info:
        bootstrap_module.bootstrap_application(base_dir=tmp_path)

    assert error_info.value is error
    assert later_calls == []


def test_directory_failure_stops_logging_and_preserves_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    cause = OSError("permission denied")
    error = InvalidPathError("data_dir", "cannot prepare")
    logging_calls: list[ApplicationSettings] = []

    def fail_preparation(_settings: ApplicationSettings) -> None:
        raise error from cause

    monkeypatch.setattr(bootstrap_module, "load_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(
        bootstrap_module,
        "prepare_runtime_directories",
        fail_preparation,
    )
    monkeypatch.setattr(bootstrap_module, "configure_logging", logging_calls.append)

    with pytest.raises(InvalidPathError) as error_info:
        bootstrap_module.bootstrap_application(base_dir=tmp_path)

    assert error_info.value is error
    assert error_info.value.__cause__ is cause
    assert logging_calls == []


def test_logging_failure_propagates_unchanged_with_cause(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    cause = OSError("permission denied")
    error = LoggingSetupError("logging.file", "cannot initialize")

    def fail_logging(_settings: ApplicationSettings) -> None:
        raise error from cause

    monkeypatch.setattr(bootstrap_module, "load_settings", lambda **_kwargs: settings)
    monkeypatch.setattr(bootstrap_module, "prepare_runtime_directories", lambda _: None)
    monkeypatch.setattr(bootstrap_module, "configure_logging", fail_logging)

    with pytest.raises(LoggingSetupError) as error_info:
        bootstrap_module.bootstrap_application(base_dir=tmp_path)

    assert error_info.value is error
    assert error_info.value.__cause__ is cause


def test_imports_have_no_startup_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    logger = logging.getLogger("aa_crawler")
    original_handlers = logger.handlers[:]
    environment = os.environ.copy()
    monkeypatch.chdir(tmp_path)

    importlib.reload(bootstrap_module)
    importlib.reload(aa_crawler)

    assert list(tmp_path.iterdir()) == []
    assert Path.cwd() == tmp_path
    assert logger.handlers == original_handlers
    assert os.environ == environment
    assert not hasattr(aa_crawler, "settings")


def test_repeated_bootstrap_preserves_directories_and_handlers(tmp_path: Path) -> None:
    base_dir = tmp_path / "project"
    first_settings = bootstrap_application(base_dir=base_dir)
    marker = first_settings.paths.data_dir / "existing.txt"
    marker.write_text("preserve", encoding="utf-8")

    second_settings = bootstrap_application(base_dir=base_dir)

    assert marker.read_text(encoding="utf-8") == "preserve"
    assert second_settings.paths.data_dir == first_settings.paths.data_dir
    assert len(owned_handlers()) == 1


def test_public_api_preserves_main_and_exports_bootstrap() -> None:
    assert aa_crawler.bootstrap_application is bootstrap_module.bootstrap_application
    assert callable(aa_crawler.main)
    assert aa_crawler.__all__ == ["bootstrap_application", "main"]
