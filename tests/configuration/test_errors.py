from __future__ import annotations

import pytest

from aa_crawler.configuration import (
    AACrawlerError,
    ConfigurationError,
    InvalidEnvironmentValueError,
    InvalidPathError,
    LoggingSetupError,
    MissingSettingError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        ConfigurationError,
        InvalidEnvironmentValueError,
        MissingSettingError,
        InvalidPathError,
        LoggingSetupError,
    ],
)
def test_configuration_errors_inherit_from_application_error(
    error_type: type[ConfigurationError],
) -> None:
    assert issubclass(error_type, AACrawlerError)


def test_application_error_behaves_like_exception() -> None:
    error = AACrawlerError("application failed")

    assert isinstance(error, Exception)
    assert str(error) == "application failed"


def test_configuration_error_message_contains_only_safe_context() -> None:
    secret_value = "super-secret-token"

    error = MissingSettingError("api_key", "a value is required")

    assert error.field_name == "api_key"
    assert error.constraint == "a value is required"
    assert "api_key" in str(error)
    assert "a value is required" in str(error)
    assert secret_value not in str(error)
