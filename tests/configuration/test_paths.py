from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aa_crawler.configuration import (
    ApplicationSettings,
    InvalidPathError,
    LoggingSettings,
    LogLevel,
    PathSettings,
    prepare_runtime_directories,
    resolve_runtime_paths,
)


def make_settings(
    *,
    base_dir: Path,
    data_dir: Path = Path("data"),
    log_dir: Path = Path("logs"),
    config_dir: Path = Path("config"),
    temp_dir: Path = Path(".tmp"),
    file_logging: bool = False,
) -> ApplicationSettings:
    return ApplicationSettings(
        paths=PathSettings(
            base_dir=base_dir,
            data_dir=data_dir,
            log_dir=log_dir,
            config_dir=config_dir,
            temp_dir=temp_dir,
        ),
        logging=LoggingSettings(file_enabled=file_logging),
    )


def test_relative_default_paths_are_anchored_under_base_dir(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "project"

    resolved = resolve_runtime_paths(make_settings(base_dir=base_dir))

    assert resolved.paths.base_dir == base_dir
    assert resolved.paths.data_dir == base_dir / "data"
    assert resolved.paths.log_dir == base_dir / "logs"
    assert resolved.paths.config_dir == base_dir / "config"
    assert resolved.paths.temp_dir == base_dir / ".tmp"


def test_explicit_relative_paths_are_anchored(tmp_path: Path) -> None:
    base_dir = tmp_path / "project"
    settings = make_settings(
        base_dir=base_dir,
        data_dir=Path("runtime/data"),
        log_dir=Path("runtime/logs"),
        config_dir=Path("settings"),
        temp_dir=Path("runtime/temp"),
    )

    resolved = resolve_runtime_paths(settings)

    assert resolved.paths.data_dir == base_dir / "runtime/data"
    assert resolved.paths.log_dir == base_dir / "runtime/logs"
    assert resolved.paths.config_dir == base_dir / "settings"
    assert resolved.paths.temp_dir == base_dir / "runtime/temp"


def test_absolute_paths_remain_unchanged(tmp_path: Path) -> None:
    external = tmp_path / "external"
    settings = make_settings(
        base_dir=tmp_path / "project",
        data_dir=external / "data",
        log_dir=external / "logs",
        config_dir=external / "config",
        temp_dir=external / "temp",
    )

    resolved = resolve_runtime_paths(settings)

    assert resolved.paths.data_dir == external / "data"
    assert resolved.paths.log_dir == external / "logs"
    assert resolved.paths.config_dir == external / "config"
    assert resolved.paths.temp_dir == external / "temp"


def test_mixed_relative_and_absolute_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "project"
    external_logs = tmp_path / "external-logs"
    settings = make_settings(
        base_dir=base_dir,
        data_dir=Path("runtime-data"),
        log_dir=external_logs,
    )

    resolved = resolve_runtime_paths(settings)

    assert resolved.paths.data_dir == base_dir / "runtime-data"
    assert resolved.paths.log_dir == external_logs


def test_relative_base_dir_becomes_absolute(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    resolved = resolve_runtime_paths(make_settings(base_dir=Path("project")))

    assert resolved.paths.base_dir == tmp_path / "project"
    assert resolved.paths.base_dir.is_absolute()


def test_resolution_does_not_mutate_original_settings(tmp_path: Path) -> None:
    settings = make_settings(base_dir=tmp_path / "project")

    resolved = resolve_runtime_paths(settings)

    assert resolved is not settings
    assert settings.paths.data_dir == Path("data")
    assert resolved.paths.data_dir != settings.paths.data_dir


def test_resolved_settings_remain_frozen(tmp_path: Path) -> None:
    resolved = resolve_runtime_paths(make_settings(base_dir=tmp_path / "project"))

    with pytest.raises(ValidationError, match="frozen"):
        resolved.debug = True
    with pytest.raises(ValidationError, match="frozen"):
        resolved.paths.data_dir = Path("other")
    with pytest.raises(ValidationError, match="frozen"):
        resolved.logging.level = LogLevel.DEBUG


def test_resolution_requires_no_existing_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "missing-project"

    resolved = resolve_runtime_paths(make_settings(base_dir=base_dir))

    assert resolved.paths.data_dir == base_dir / "data"
    assert not base_dir.exists()


@pytest.mark.parametrize(
    "escaping_path",
    [Path("..") / "outside", Path("nested") / ".." / ".." / "outside"],
)
def test_relative_path_cannot_escape_base_dir(
    escaping_path: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(InvalidPathError) as error_info:
        resolve_runtime_paths(
            make_settings(
                base_dir=tmp_path / "project",
                data_dir=escaping_path,
            )
        )

    assert error_info.value.field_name == "data_dir"
    assert "base_dir" in str(error_info.value)


def test_traversal_normalizing_inside_base_dir_is_allowed(tmp_path: Path) -> None:
    base_dir = tmp_path / "project"
    settings = make_settings(
        base_dir=base_dir,
        data_dir=Path("nested") / ".." / "data",
    )

    resolved = resolve_runtime_paths(settings)

    assert resolved.paths.data_dir == base_dir / "data"


def test_resolution_does_not_create_directories(tmp_path: Path) -> None:
    base_dir = tmp_path / "missing-project"

    resolve_runtime_paths(make_settings(base_dir=base_dir))

    assert not base_dir.exists()


def test_preparation_creates_data_and_temp_but_not_other_directories(
    tmp_path: Path,
) -> None:
    resolved = resolve_runtime_paths(make_settings(base_dir=tmp_path / "project"))

    prepare_runtime_directories(resolved)

    assert resolved.paths.data_dir.is_dir()
    assert resolved.paths.temp_dir.is_dir()
    assert not resolved.paths.log_dir.exists()
    assert not resolved.paths.config_dir.exists()


def test_preparation_creates_log_directory_when_file_logging_enabled(
    tmp_path: Path,
) -> None:
    resolved = resolve_runtime_paths(
        make_settings(base_dir=tmp_path / "project", file_logging=True)
    )

    prepare_runtime_directories(resolved)

    assert resolved.paths.log_dir.is_dir()
    assert not resolved.paths.config_dir.exists()


def test_preparation_is_idempotent_and_preserves_contents(tmp_path: Path) -> None:
    resolved = resolve_runtime_paths(make_settings(base_dir=tmp_path / "project"))
    prepare_runtime_directories(resolved)
    existing_file = resolved.paths.data_dir / "existing.txt"
    existing_file.write_text("preserve me", encoding="utf-8")

    prepare_runtime_directories(resolved)

    assert existing_file.read_text(encoding="utf-8") == "preserve me"


def test_preparation_translates_filesystem_errors(tmp_path: Path) -> None:
    resolved = resolve_runtime_paths(make_settings(base_dir=tmp_path / "project"))
    resolved.paths.data_dir.parent.mkdir(parents=True)
    resolved.paths.data_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(InvalidPathError) as error_info:
        prepare_runtime_directories(resolved)

    assert error_info.value.field_name == "data_dir"
    assert isinstance(error_info.value.__cause__, OSError)
