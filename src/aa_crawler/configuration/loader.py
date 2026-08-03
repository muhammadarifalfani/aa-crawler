"""Typed configuration loading with explicit source precedence."""

import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from aa_crawler.configuration.errors import (
    InvalidEnvironmentValueError,
    MissingSettingError,
)
from aa_crawler.configuration.models import (
    ApplicationSettings,
    Environment,
    LogFormat,
    LoggingSettings,
    LogLevel,
    PathSettings,
)

_APPROVED_ENVIRONMENT_VARIABLES = frozenset(
    {
        "AA_CONFIG_DIR",
        "AA_DATA_DIR",
        "AA_DEBUG",
        "AA_ENV",
        "AA_LOG_BACKUP_COUNT",
        "AA_LOG_CONSOLE_ENABLED",
        "AA_LOG_DIR",
        "AA_LOG_FILE_ENABLED",
        "AA_LOG_FILE_NAME",
        "AA_LOG_FORMAT",
        "AA_LOG_LEVEL",
        "AA_LOG_MAX_BYTES",
        "AA_TEMP_DIR",
    }
)

_OVERRIDE_FIELDS = frozenset({"environment", "debug", "paths", "logging"})
_PATH_OVERRIDE_FIELDS = frozenset({"data_dir", "log_dir", "config_dir", "temp_dir"})
_LOGGING_OVERRIDE_FIELDS = frozenset(
    {
        "level",
        "console_enabled",
        "file_enabled",
        "format",
        "file_name",
        "max_bytes",
        "backup_count",
    }
)

_FIELD_TO_ENVIRONMENT_VARIABLE = {
    "env": "AA_ENV",
    "debug": "AA_DEBUG",
    "data_dir": "AA_DATA_DIR",
    "log_dir": "AA_LOG_DIR",
    "config_dir": "AA_CONFIG_DIR",
    "temp_dir": "AA_TEMP_DIR",
    "log_level": "AA_LOG_LEVEL",
    "log_console_enabled": "AA_LOG_CONSOLE_ENABLED",
    "log_file_enabled": "AA_LOG_FILE_ENABLED",
    "log_format": "AA_LOG_FORMAT",
    "log_file_name": "AA_LOG_FILE_NAME",
    "log_max_bytes": "AA_LOG_MAX_BYTES",
    "log_backup_count": "AA_LOG_BACKUP_COUNT",
}


def _default_temp_dir() -> Path:
    return Path(tempfile.gettempdir()) / "aa-crawler"


class _LoaderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        dotenv_filtering="match_prefix",
        env_prefix="AA_",
        extra="forbid",
    )

    env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")
    config_dir: Path = Path("config")
    temp_dir: Path = Field(default_factory=_default_temp_dir)
    log_level: LogLevel = LogLevel.INFO
    log_console_enabled: bool = True
    log_file_enabled: bool = False
    log_format: LogFormat = LogFormat.TEXT
    log_file_name: str = "aa-crawler.log"
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5


def _reject_unknown_environment_variables() -> None:
    for variable_name in os.environ:
        normalized_name = variable_name.upper()
        if (
            normalized_name.startswith("AA_")
            and normalized_name not in _APPROVED_ENVIRONMENT_VARIABLES
        ):
            raise InvalidEnvironmentValueError(
                variable_name,
                "unknown AA_ environment variable",
            )


def _as_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidEnvironmentValueError(
            field_name,
            "explicit override must be a mapping",
        )
    return value


def _reject_unknown_override_fields(
    values: Mapping[str, object],
    approved_fields: frozenset[str],
    prefix: str,
) -> None:
    for field_name in values:
        if field_name not in approved_fields:
            qualified_name = f"{prefix}.{field_name}" if prefix else field_name
            raise InvalidEnvironmentValueError(
                qualified_name,
                "unknown explicit override",
            )


def _flatten_overrides(
    overrides: Mapping[str, object] | None,
) -> dict[str, object]:
    if overrides is None:
        return {}

    _reject_unknown_override_fields(overrides, _OVERRIDE_FIELDS, "")
    flattened: dict[str, object] = {}

    if "environment" in overrides:
        flattened["env"] = overrides["environment"]
    if "debug" in overrides:
        flattened["debug"] = overrides["debug"]
    if "paths" in overrides:
        path_values = _as_mapping(overrides["paths"], "paths")
        _reject_unknown_override_fields(
            path_values,
            _PATH_OVERRIDE_FIELDS,
            "paths",
        )
        flattened.update(path_values)
    if "logging" in overrides:
        logging_values = _as_mapping(overrides["logging"], "logging")
        _reject_unknown_override_fields(
            logging_values,
            _LOGGING_OVERRIDE_FIELDS,
            "logging",
        )
        flattened.update(
            {f"log_{name}": value for name, value in logging_values.items()}
        )

    return flattened


def _safe_error_field(error: ValidationError) -> str:
    first_error = error.errors(include_input=False, include_url=False)[0]
    location = first_error.get("loc", ("configuration",))
    field_name = str(location[0]) if location else "configuration"
    error_type = first_error.get("type")
    if error_type == "extra_forbidden":
        return f"AA_{field_name.upper()}"
    return _FIELD_TO_ENVIRONMENT_VARIABLE.get(field_name, field_name)


def _translate_validation_error(error: ValidationError) -> None:
    first_error = error.errors(include_input=False, include_url=False)[0]
    field_name = _safe_error_field(error)
    if first_error.get("type") == "missing":
        raise MissingSettingError(
            field_name,
            "a required setting is missing",
        ) from error
    if first_error.get("type") == "extra_forbidden":
        raise InvalidEnvironmentValueError(
            field_name,
            "unknown AA_ environment variable",
        ) from error
    raise InvalidEnvironmentValueError(
        field_name,
        "value does not satisfy configuration constraints",
    ) from error


def _load_internal_settings(
    env_file: Path | None,
    overrides: Mapping[str, object],
) -> _LoaderSettings:
    settings_factory = cast("Callable[..., _LoaderSettings]", _LoaderSettings)
    return settings_factory(
        _env_file=env_file,
        _env_file_encoding="utf-8",
        **overrides,
    )


def load_settings(
    *,
    base_dir: Path,
    env_file: Path | None = None,
    overrides: Mapping[str, object] | None = None,
) -> ApplicationSettings:
    """Load and validate one immutable application settings instance.

    Sources are applied from highest to lowest precedence: explicit overrides,
    OS environment variables, an explicitly selected dotenv file, and model
    defaults. No dotenv file is loaded when ``env_file`` is ``None``.

    Args:
        base_dir: Explicit application base directory.
        env_file: Optional exact dotenv file to load without discovery.
        overrides: Optional ApplicationSettings-shaped explicit values.

    Returns:
        A fully validated frozen application settings model.

    Raises:
        InvalidEnvironmentValueError: If a value or variable is invalid.
        MissingSettingError: If a required setting is missing.
    """
    _reject_unknown_environment_variables()
    flattened_overrides = _flatten_overrides(overrides)

    try:
        loaded = _load_internal_settings(env_file, flattened_overrides)
        return ApplicationSettings(
            environment=loaded.env,
            debug=loaded.debug,
            paths=PathSettings(
                base_dir=base_dir,
                data_dir=loaded.data_dir,
                log_dir=loaded.log_dir,
                config_dir=loaded.config_dir,
                temp_dir=loaded.temp_dir,
            ),
            logging=LoggingSettings(
                level=loaded.log_level,
                console_enabled=loaded.log_console_enabled,
                file_enabled=loaded.log_file_enabled,
                format=loaded.log_format,
                file_name=loaded.log_file_name,
                max_bytes=loaded.log_max_bytes,
                backup_count=loaded.log_backup_count,
            ),
        )
    except ValidationError as error:
        _translate_validation_error(error)

    raise AssertionError("configuration error translation must raise")
