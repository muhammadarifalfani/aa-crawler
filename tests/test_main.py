from __future__ import annotations

from typing import TYPE_CHECKING

from aa_crawler import main

if TYPE_CHECKING:
    from pytest import CaptureFixture


def test_main_prints_greeting(capsys: CaptureFixture[str]) -> None:
    main()

    captured = capsys.readouterr()

    assert captured.out == "Hello from aa-crawler!\n"
