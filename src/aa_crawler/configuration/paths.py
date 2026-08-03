"""Deterministic runtime path resolution and directory preparation."""

import os
from pathlib import Path

from aa_crawler.configuration.errors import InvalidPathError
from aa_crawler.configuration.models import ApplicationSettings, PathSettings


def _normalize_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(path)))


def _resolve_relative_path(
    *,
    field_name: str,
    configured_path: Path,
    base_dir: Path,
) -> Path:
    if configured_path.is_absolute():
        return configured_path

    resolved_path = _normalize_absolute(base_dir / configured_path)
    if not resolved_path.is_relative_to(base_dir):
        raise InvalidPathError(
            field_name,
            "relative path must remain within base_dir",
        )
    return resolved_path


def resolve_runtime_paths(settings: ApplicationSettings) -> ApplicationSettings:
    """Return a new settings model with normalized, anchored runtime paths.

    Relative runtime paths are anchored beneath an absolute normalized base
    directory. Absolute configured paths remain absolute and may be outside the
    base directory. This function performs no filesystem operations.

    Args:
        settings: Frozen application settings containing unresolved paths.

    Returns:
        A new frozen application settings instance with resolved paths.

    Raises:
        InvalidPathError: If a relative path would escape the base directory.
    """
    base_dir = _normalize_absolute(settings.paths.base_dir)
    paths = PathSettings(
        base_dir=base_dir,
        data_dir=_resolve_relative_path(
            field_name="data_dir",
            configured_path=settings.paths.data_dir,
            base_dir=base_dir,
        ),
        log_dir=_resolve_relative_path(
            field_name="log_dir",
            configured_path=settings.paths.log_dir,
            base_dir=base_dir,
        ),
        config_dir=_resolve_relative_path(
            field_name="config_dir",
            configured_path=settings.paths.config_dir,
            base_dir=base_dir,
        ),
        temp_dir=_resolve_relative_path(
            field_name="temp_dir",
            configured_path=settings.paths.temp_dir,
            base_dir=base_dir,
        ),
    )
    return ApplicationSettings(
        environment=settings.environment,
        debug=settings.debug,
        paths=paths,
        logging=settings.logging,
    )


def prepare_runtime_directories(settings: ApplicationSettings) -> None:
    """Create the runtime directories required by enabled subsystems.

    The data and temporary directories are always prepared. The log directory
    is prepared only when file logging is enabled. The configuration directory
    is never created by this function.

    Args:
        settings: Application settings whose runtime directories are prepared.

    Raises:
        InvalidPathError: If a required directory cannot be created.
    """
    resolved_settings = resolve_runtime_paths(settings)
    directories = [
        ("data_dir", resolved_settings.paths.data_dir),
        ("temp_dir", resolved_settings.paths.temp_dir),
    ]
    if resolved_settings.logging.file_enabled:
        directories.append(("log_dir", resolved_settings.paths.log_dir))

    for field_name, directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise InvalidPathError(
                field_name,
                "runtime directory could not be prepared",
            ) from error
