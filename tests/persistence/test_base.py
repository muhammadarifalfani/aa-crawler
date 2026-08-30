"""Tests for the abstract persistence port."""

from __future__ import annotations

import pytest

from aa_crawler.persistence import BaseCrawlResultSink


def test_base_sink_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseCrawlResultSink()  # type: ignore[abstract]
