"""Application-owned logging configuration."""

import logging
from logging.handlers import RotatingFileHandler

from aa_crawler.configuration import (
    ApplicationSettings,
    LoggingSetupError,
    LogLevel,
)

_LOGGER_NAME = "aa_crawler"
_HANDLER_OWNER_ATTRIBUTE = "_aa_crawler_owned"
_TEXT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_LOG_LEVELS = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}


def _mark_owned(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _HANDLER_OWNER_ATTRIBUTE, True)
    return handler


def _is_owned(handler: logging.Handler) -> bool:
    return bool(getattr(handler, _HANDLER_OWNER_ATTRIBUTE, False))


def _close_handlers(handlers: list[logging.Handler]) -> None:
    for handler in handlers:
        handler.close()


def _create_handlers(settings: ApplicationSettings) -> list[logging.Handler]:
    level = _LOG_LEVELS[settings.logging.level]
    formatter = logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT)
    handlers: list[logging.Handler] = []

    if settings.logging.console_enabled:
        console_handler = _mark_owned(logging.StreamHandler())
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if settings.logging.file_enabled:
        log_path = settings.paths.log_dir / settings.logging.file_name
        try:
            file_handler = _mark_owned(
                RotatingFileHandler(
                    log_path,
                    maxBytes=settings.logging.max_bytes,
                    backupCount=settings.logging.backup_count,
                    encoding="utf-8",
                    delay=True,
                )
            )
        except OSError as error:
            _close_handlers(handlers)
            raise LoggingSetupError(
                "logging.file",
                f"could not initialize rotating file handler for '{log_path}'",
            ) from error
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    return handlers


def configure_logging(settings: ApplicationSettings) -> None:
    """Configure handlers owned by the AA Crawler logger hierarchy.

    Existing handlers installed by AA Crawler are replaced, while unrelated
    handlers remain attached. Handler construction completes before the active
    logger configuration is changed, preventing partial reconfiguration.

    Args:
        settings: Validated application and logging settings.

    Raises:
        LoggingSetupError: If an enabled file handler cannot be initialized.
    """
    level = _LOG_LEVELS[settings.logging.level]
    replacement_handlers = _create_handlers(settings)
    logger = logging.getLogger(_LOGGER_NAME)
    previous_handlers = [handler for handler in logger.handlers if _is_owned(handler)]

    for handler in previous_handlers:
        logger.removeHandler(handler)
    for handler in replacement_handlers:
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    _close_handlers(previous_handlers)
