from __future__ import annotations

import logging

import pytest

from aa_crawler.observability.redaction import SensitiveDataFilter, redact_text


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("Authorization: Bearer top-secret", "top-secret"),
        ("password=hunter2", "hunter2"),
        ("API_KEY: 'abc123'", "abc123"),
        ('api-key="key-value"', "key-value"),
        ("apikey=compact", "compact"),
        ("access_token: access-value", "access-value"),
        ("refresh_token=refresh-value", "refresh-value"),
        ("client_secret: client-value", "client-value"),
        ("TOKEN=token-value", "token-value"),
        ("Cookie: session-value", "session-value"),
        ("Set-Cookie=session-value", "session-value"),
        ("Proxy-Authorization: Basic encoded-value", "encoded-value"),
    ],
)
def test_sensitive_key_value_pairs_are_redacted(message: str, secret: str) -> None:
    redacted = redact_text(message)

    assert secret not in redacted
    assert "[REDACTED]" in redacted


def test_unrelated_text_and_token_substrings_remain_unchanged() -> None:
    message = "tokenizer processed safe path /tokens/archive and status=ok"

    assert redact_text(message) == message


def test_mapping_arguments_are_not_mutated() -> None:
    arguments = {"password": "secret-value", "user": "alice"}
    record = logging.LogRecord(
        "aa_crawler.test",
        logging.INFO,
        __file__,
        1,
        "password=%(password)s user=%(user)s",
        arguments,
        None,
    )

    SensitiveDataFilter().filter(record)

    assert arguments == {"password": "secret-value", "user": "alice"}
    assert "secret-value" not in record.getMessage()
    assert "user=alice" in record.getMessage()


def test_formatting_failure_is_suppressed_safely() -> None:
    record = logging.LogRecord(
        "aa_crawler.test",
        logging.INFO,
        __file__,
        1,
        "password=%s extra=%s",
        ("secret-value",),
        None,
    )

    assert SensitiveDataFilter().filter(record) is True
    assert "secret-value" not in record.getMessage()
    assert "SUPPRESSED" in record.getMessage()
