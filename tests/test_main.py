from __future__ import annotations

from aa_crawler import main
from aa_crawler.cli import main as cli_main


def test_main_delegates_to_cli_entry_point() -> None:
    assert main is cli_main
