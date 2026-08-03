"""Immutable configuration models for AA Crawler."""

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Environment(StrEnum):
    """Supported AA Crawler runtime environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return next((member for member in cls if member.value == normalized), None)
        return None


class LogLevel(StrEnum):
    """Supported application logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return next((member for member in cls if member.value == normalized), None)
        return None


class LogFormat(StrEnum):
    """Supported application log output formats."""

    TEXT = "text"


class PathSettings(BaseModel):
    """Immutable paths used by AA Crawler subsystems."""

    model_config = ConfigDict(frozen=True)

    base_dir: Path
    data_dir: Path
    log_dir: Path
    config_dir: Path
    temp_dir: Path

    @field_validator(
        "base_dir",
        "data_dir",
        "log_dir",
        "config_dir",
        "temp_dir",
        mode="before",
    )
    @classmethod
    def reject_empty_paths(cls, value: object) -> object:
        """Reject empty string path inputs before conversion to ``Path``.

        Args:
            value: Raw value supplied for a path field.

        Returns:
            The unchanged value for normal Pydantic path validation.

        Raises:
            ValueError: If the supplied path is an empty string.
        """
        if isinstance(value, str) and not value.strip():
            raise ValueError("path must not be empty")
        return value


class LoggingSettings(BaseModel):
    """Immutable settings controlling application logging behavior."""

    model_config = ConfigDict(frozen=True)

    level: LogLevel = LogLevel.INFO
    console_enabled: bool = True
    file_enabled: bool = False
    format: LogFormat = LogFormat.TEXT
    file_name: str = "aa-crawler.log"
    max_bytes: int = Field(default=10_485_760, gt=0)
    backup_count: int = Field(default=5, gt=0)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        """Validate that a log filename cannot escape the log directory.

        Args:
            value: Candidate log filename.

        Returns:
            The validated filename.

        Raises:
            ValueError: If the filename is empty, absolute, or contains traversal.
        """
        if not value.strip():
            raise ValueError("log file name must not be empty")
        if Path(value).is_absolute():
            raise ValueError("log file name must be relative")
        if "/" in value or "\\" in value:
            raise ValueError("log file name must not contain directory separators")
        if value in {".", ".."}:
            raise ValueError("log file name must not contain parent traversal")
        return value

    @model_validator(mode="after")
    def require_enabled_handler(self) -> Self:
        """Require at least one logging handler to be enabled.

        Returns:
            The validated logging settings instance.

        Raises:
            ValueError: If both console and file logging are disabled.
        """
        if not self.console_enabled and not self.file_enabled:
            raise ValueError("at least one logging handler must be enabled")
        return self


class ApplicationSettings(BaseModel):
    """Immutable effective configuration for one AA Crawler process."""

    model_config = ConfigDict(frozen=True)

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    paths: PathSettings
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
