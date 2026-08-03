from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from aa_crawler.configuration import (
    ApplicationSettings,
    Environment,
    LogFormat,
    LoggingSettings,
    LogLevel,
    PathSettings,
)

if TYPE_CHECKING:
    from enum import StrEnum


def make_path_settings(**overrides: object) -> PathSettings:
    values: dict[str, object] = {
        "base_dir": Path("."),
        "data_dir": Path("data"),
        "log_dir": Path("logs"),
        "config_dir": Path("config"),
        "temp_dir": Path(".tmp"),
    }
    values.update(overrides)
    return PathSettings.model_validate(values)


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (Environment.DEVELOPMENT, "development"),
        (Environment.TESTING, "testing"),
        (Environment.STAGING, "staging"),
        (Environment.PRODUCTION, "production"),
        (LogLevel.DEBUG, "DEBUG"),
        (LogLevel.INFO, "INFO"),
        (LogLevel.WARNING, "WARNING"),
        (LogLevel.ERROR, "ERROR"),
        (LogLevel.CRITICAL, "CRITICAL"),
        (LogFormat.TEXT, "text"),
    ],
)
def test_enums_expose_approved_string_values(
    member: StrEnum,
    value: str,
) -> None:
    assert member.value == value
    assert str(member) == value


@pytest.mark.parametrize("value", ["DEVELOPMENT", "Testing", " staging "])
def test_environment_normalizes_input_case(value: str) -> None:
    assert Environment(value) is Environment(value.strip().lower())


@pytest.mark.parametrize("value", ["debug", "Info", " warning "])
def test_log_level_normalizes_input_case(value: str) -> None:
    assert LogLevel(value) is LogLevel(value.strip().upper())


@pytest.mark.parametrize(
    ("enum_type", "value"),
    [
        (Environment, "local"),
        (LogLevel, "TRACE"),
        (LogFormat, "json"),
    ],
)
def test_invalid_enum_values_fail(
    enum_type: type[StrEnum],
    value: str,
) -> None:
    with pytest.raises(ValueError):
        enum_type(value)


def test_application_and_logging_defaults() -> None:
    settings = ApplicationSettings(paths=make_path_settings())

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.debug is False
    assert settings.logging.console_enabled is True
    assert settings.logging.file_enabled is False
    assert settings.logging.level is LogLevel.INFO
    assert settings.logging.format is LogFormat.TEXT
    assert settings.logging.max_bytes == 10 * 1024 * 1024
    assert settings.logging.backup_count == 5


def test_application_settings_accept_valid_nested_models() -> None:
    paths = make_path_settings()
    logging = LoggingSettings(file_enabled=True)

    settings = ApplicationSettings(paths=paths, logging=logging)

    assert settings.paths is paths
    assert settings.logging is logging


def test_logging_settings_reject_disabled_handlers() -> None:
    with pytest.raises(ValidationError, match="at least one logging handler"):
        LoggingSettings(console_enabled=False, file_enabled=False)


@pytest.mark.parametrize(
    "file_name",
    ["", "   ", "logs/aa-crawler.log", "logs\\aa-crawler.log", ".", ".."],
)
def test_logging_settings_reject_unsafe_file_names(file_name: str) -> None:
    with pytest.raises(ValidationError):
        LoggingSettings(file_name=file_name)


def test_logging_settings_reject_absolute_file_name() -> None:
    absolute_name = str(Path.cwd() / "aa-crawler.log")

    with pytest.raises(ValidationError, match="must be relative"):
        LoggingSettings(file_name=absolute_name)


@pytest.mark.parametrize("max_bytes", [0, -1])
def test_logging_settings_reject_non_positive_max_bytes(max_bytes: int) -> None:
    with pytest.raises(ValidationError):
        LoggingSettings(max_bytes=max_bytes)


@pytest.mark.parametrize("backup_count", [0, -1])
def test_logging_settings_reject_non_positive_backup_count(
    backup_count: int,
) -> None:
    with pytest.raises(ValidationError):
        LoggingSettings(backup_count=backup_count)


@pytest.mark.parametrize(
    "field_name",
    ["base_dir", "data_dir", "log_dir", "config_dir", "temp_dir"],
)
def test_path_settings_reject_empty_path_values(field_name: str) -> None:
    with pytest.raises(ValidationError, match="path must not be empty"):
        make_path_settings(**{field_name: "  "})


def test_path_settings_accept_path_values() -> None:
    settings = make_path_settings()

    assert isinstance(settings.base_dir, Path)
    assert isinstance(settings.data_dir, Path)
    assert isinstance(settings.log_dir, Path)
    assert isinstance(settings.config_dir, Path)
    assert isinstance(settings.temp_dir, Path)


@pytest.mark.parametrize(
    ("settings", "field_name", "replacement"),
    [
        (make_path_settings(), "data_dir", Path("other-data")),
        (LoggingSettings(), "level", LogLevel.DEBUG),
        (
            ApplicationSettings(paths=make_path_settings()),
            "debug",
            True,
        ),
    ],
)
def test_settings_models_are_immutable(
    settings: PathSettings | LoggingSettings | ApplicationSettings,
    field_name: str,
    replacement: object,
) -> None:
    with pytest.raises(ValidationError, match="frozen"):
        setattr(settings, field_name, replacement)
