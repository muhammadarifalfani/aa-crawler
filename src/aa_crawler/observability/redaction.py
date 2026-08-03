"""Defensive redaction for sensitive logging material."""

import logging
import re
from collections.abc import Mapping
from typing import Final

_REDACTION: Final = "[REDACTED]"
_FORMAT_FAILURE: Final = "[LOG MESSAGE SUPPRESSED: unsafe formatting]"
_SENSITIVE_KEYS: Final = frozenset(
    {
        "access_token",
        "api-key",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "cookie",
        "password",
        "passwd",
        "proxy-authorization",
        "refresh_token",
        "secret",
        "set-cookie",
        "token",
    }
)
_KEY_PATTERN = "|".join(
    re.escape(key) for key in sorted(_SENSITIVE_KEYS, key=len, reverse=True)
)
_KEY_VALUE_PATTERN = re.compile(
    rf"(?P<prefix>(?<![\w-])(?:{_KEY_PATTERN})(?![\w-])\s*[:=]\s*)"
    r"(?:"
    r"(?P<quote>['\"])(?P<quoted>.*?)(?P=quote)"
    r"|(?P<scheme>(?:Bearer|Basic)\s+[^\s,;}\]]+)"
    r"|(?P<plain>(?!%\()[^\s,;}\]]+)"
    r")",
    re.IGNORECASE,
)


def redact_text(value: str) -> str:
    """Return text with recognized sensitive key/value pairs redacted.

    Args:
        value: Log message text to sanitize.

    Returns:
        Sanitized text preserving unrelated content.
    """
    return _KEY_VALUE_PATTERN.sub(
        lambda match: f"{match.group('prefix')}{_REDACTION}",
        value,
    )


def _redact_mapping(arguments: Mapping[str, object]) -> dict[str, object]:
    return {
        key: _REDACTION
        if isinstance(key, str) and key.casefold() in _SENSITIVE_KEYS
        else value
        for key, value in arguments.items()
    }


def _copy_and_redact_arguments(
    arguments: tuple[object, ...] | Mapping[str, object] | None,
) -> tuple[object, ...] | Mapping[str, object]:
    if arguments is None:
        return ()
    if isinstance(arguments, Mapping):
        return _redact_mapping(arguments)
    return tuple(
        _redact_mapping(argument) if isinstance(argument, dict) else argument
        for argument in arguments
    )


class SensitiveDataFilter(logging.Filter):
    """Sanitize log messages and arguments without mutating caller-owned data."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact a record and always allow it to proceed to its handler."""
        try:
            record.args = _copy_and_redact_arguments(record.args)
            rendered_message = record.getMessage()
            record.msg = redact_text(rendered_message)
        except Exception:
            record.msg = _FORMAT_FAILURE
        record.args = ()
        return True
