"""Explicit AA Crawler application startup composition."""

from collections.abc import Mapping
from pathlib import Path

from aa_crawler.configuration import (
    ApplicationSettings,
    load_settings,
    prepare_runtime_directories,
)
from aa_crawler.observability import configure_logging


def bootstrap_application(
    *,
    base_dir: Path,
    env_file: Path | None = None,
    overrides: Mapping[str, object] | None = None,
) -> ApplicationSettings:
    """Load settings and initialize required application infrastructure.

    Startup occurs explicitly in dependency order: settings are loaded first,
    required runtime directories are prepared second, and logging is configured
    last. The same frozen settings instance is used throughout and returned to
    the composition root.

    Args:
        base_dir: Explicit application base directory.
        env_file: Optional exact dotenv file to load without discovery.
        overrides: Optional highest-precedence configuration values.

    Returns:
        The resolved frozen application settings used during startup.

    Raises:
        ConfigurationError: If configuration loading or validation fails.
        InvalidPathError: If required runtime directories cannot be prepared.
        LoggingSetupError: If enabled logging infrastructure cannot be configured.
    """
    settings = load_settings(
        base_dir=base_dir,
        env_file=env_file,
        overrides=overrides,
    )
    prepare_runtime_directories(settings)
    configure_logging(settings)
    return settings
