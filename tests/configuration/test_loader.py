from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from aa_crawler.configuration import (
    Environment,
    InvalidEnvironmentValueError,
    LogFormat,
    LogLevel,
    load_settings,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(autouse=True)
def isolate_aa_environment(monkeypatch: MonkeyPatch) -> Iterator[None]:
    for variable_name in tuple(os.environ):
        if variable_name.upper().startswith("AA_"):
            monkeypatch.delenv(variable_name, raising=False)
    yield


def test_load_settings_uses_defaults_and_explicit_base_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "application"

    settings = load_settings(base_dir=base_dir)

    assert settings.environment is Environment.DEVELOPMENT
    assert settings.debug is False
    assert settings.paths.base_dir == base_dir
    assert settings.paths.data_dir == Path("data")
    assert settings.paths.log_dir == Path("logs")
    assert settings.paths.config_dir == Path("config")
    assert settings.logging.level is LogLevel.INFO
    assert settings.logging.console_enabled is True
    assert settings.logging.file_enabled is False


def test_env_file_none_does_not_discover_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("AA_ENV=production\n", encoding="utf-8")

    settings = load_settings(base_dir=tmp_path / "child", env_file=None)

    assert settings.environment is Environment.DEVELOPMENT


def test_explicit_env_file_is_loaded_without_mutating_environment(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "selected.env"
    env_file.write_text(
        "AA_ENV=staging\nAA_DEBUG=true\nAA_DATA_DIR=dotenv-data\n",
        encoding="utf-8",
    )

    settings = load_settings(base_dir=tmp_path, env_file=env_file)

    assert settings.environment is Environment.STAGING
    assert settings.debug is True
    assert settings.paths.data_dir == Path("dotenv-data")
    assert "AA_ENV" not in os.environ
    assert "AA_DEBUG" not in os.environ
    assert "AA_DATA_DIR" not in os.environ


def test_sibling_dotenv_is_ignored_unless_selected(tmp_path: Path) -> None:
    selected_file = tmp_path / "selected.env"
    sibling_file = tmp_path / ".env"
    selected_file.write_text("AA_ENV=testing\n", encoding="utf-8")
    sibling_file.write_text("AA_ENV=production\n", encoding="utf-8")

    settings = load_settings(base_dir=tmp_path, env_file=selected_file)

    assert settings.environment is Environment.TESTING


def test_os_environment_overrides_explicit_env_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "selected.env"
    env_file.write_text("AA_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("AA_LOG_LEVEL", "error")

    settings = load_settings(base_dir=tmp_path, env_file=env_file)

    assert settings.logging.level is LogLevel.ERROR


def test_explicit_overrides_override_os_environment(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AA_ENV", "production")
    monkeypatch.setenv("AA_LOG_LEVEL", "WARNING")

    settings = load_settings(
        base_dir=tmp_path,
        overrides={
            "environment": "testing",
            "logging": {"level": "debug"},
        },
    )

    assert settings.environment is Environment.TESTING
    assert settings.logging.level is LogLevel.DEBUG


def test_env_file_overrides_defaults_and_preserves_unspecified_defaults(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "selected.env"
    env_file.write_text("AA_DEBUG=true\n", encoding="utf-8")

    settings = load_settings(base_dir=tmp_path, env_file=env_file)

    assert settings.debug is True
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.logging.level is LogLevel.INFO


def test_environment_values_map_to_nested_models(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    values = {
        "AA_ENV": "PRODUCTION",
        "AA_DEBUG": "true",
        "AA_DATA_DIR": "runtime-data",
        "AA_LOG_DIR": "runtime-logs",
        "AA_CONFIG_DIR": "runtime-config",
        "AA_TEMP_DIR": "runtime-temp",
        "AA_LOG_LEVEL": "warning",
        "AA_LOG_CONSOLE_ENABLED": "false",
        "AA_LOG_FILE_ENABLED": "true",
        "AA_LOG_FORMAT": "text",
        "AA_LOG_FILE_NAME": "crawler.log",
        "AA_LOG_MAX_BYTES": "2048",
        "AA_LOG_BACKUP_COUNT": "3",
    }
    for variable_name, value in values.items():
        monkeypatch.setenv(variable_name, value)

    settings = load_settings(base_dir=tmp_path)

    assert settings.environment is Environment.PRODUCTION
    assert settings.debug is True
    assert settings.paths.data_dir == Path("runtime-data")
    assert settings.paths.log_dir == Path("runtime-logs")
    assert settings.paths.config_dir == Path("runtime-config")
    assert settings.paths.temp_dir == Path("runtime-temp")
    assert settings.logging.level is LogLevel.WARNING
    assert settings.logging.console_enabled is False
    assert settings.logging.file_enabled is True
    assert settings.logging.format is LogFormat.TEXT
    assert settings.logging.file_name == "crawler.log"
    assert settings.logging.max_bytes == 2048
    assert settings.logging.backup_count == 3


@pytest.mark.parametrize(
    ("variable_name", "value"),
    [
        ("AA_ENV", "local"),
        ("AA_DEBUG", "sometimes"),
        ("AA_LOG_LEVEL", "TRACE"),
        ("AA_LOG_MAX_BYTES", "many"),
    ],
)
def test_invalid_environment_values_raise_application_error(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    variable_name: str,
    value: str,
) -> None:
    monkeypatch.setenv(variable_name, value)

    with pytest.raises(InvalidEnvironmentValueError) as error_info:
        load_settings(base_dir=tmp_path)

    assert variable_name in str(error_info.value)
    assert value not in str(error_info.value)
    assert error_info.value.__cause__ is not None


@pytest.mark.parametrize(
    "variable_name",
    ["AA_LOG_LEVL", "AA_UNKNOWN_SETTING", "AA_DATABASE_URL"],
)
def test_unknown_aa_environment_variable_is_rejected(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    variable_name: str,
) -> None:
    unrelated_value = "must-not-appear"
    monkeypatch.setenv(variable_name, "offending-value")
    monkeypatch.setenv("UNRELATED_VARIABLE", unrelated_value)

    with pytest.raises(InvalidEnvironmentValueError) as error_info:
        load_settings(base_dir=tmp_path)

    assert variable_name in str(error_info.value)
    assert unrelated_value not in str(error_info.value)


def test_unknown_aa_dotenv_variable_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / "selected.env"
    env_file.write_text("AA_UNKNOWN_SETTING=value\n", encoding="utf-8")

    with pytest.raises(InvalidEnvironmentValueError, match="AA_UNKNOWN_SETTING"):
        load_settings(base_dir=tmp_path, env_file=env_file)


def test_unrelated_environment_variable_is_ignored(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("UNRELATED_VARIABLE", "unrelated-value")

    settings = load_settings(base_dir=tmp_path)

    assert settings.environment is Environment.DEVELOPMENT


def test_returned_settings_and_nested_models_remain_frozen(
    tmp_path: Path,
) -> None:
    settings = load_settings(base_dir=tmp_path)

    with pytest.raises(ValidationError, match="frozen"):
        settings.debug = True
    with pytest.raises(ValidationError, match="frozen"):
        settings.paths.data_dir = Path("other-data")
    with pytest.raises(ValidationError, match="frozen"):
        settings.logging.level = LogLevel.DEBUG
