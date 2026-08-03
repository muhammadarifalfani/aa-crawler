"""Application-owned configuration exceptions."""


class AACrawlerError(Exception):
    """Base exception for errors raised by AA Crawler."""


class ConfigurationError(AACrawlerError):
    """Base exception for safe configuration error reporting.

    Args:
        field_name: Public name of the affected configuration field.
        constraint: Safe description of the violated constraint.
    """

    def __init__(self, field_name: str, constraint: str) -> None:
        self.field_name = field_name
        self.constraint = constraint
        super().__init__(f"Configuration error for '{field_name}': {constraint}.")


class InvalidEnvironmentValueError(ConfigurationError):
    """Raised when an environment value violates an approved constraint."""


class MissingSettingError(ConfigurationError):
    """Raised when a required configuration setting is missing."""


class InvalidPathError(ConfigurationError):
    """Raised when a configured path is invalid for its intended use."""


class LoggingSetupError(ConfigurationError):
    """Raised when requested logging infrastructure cannot be initialized."""
