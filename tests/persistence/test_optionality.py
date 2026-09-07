"""Guard ADR-024's optionality, narrowed for the CLI by ADR-027.

`ArticleCrawlService` and `ApplicationRuntime` must never import
`aa_crawler.persistence`. This is verified statically (via `ast`) rather
than by exercising runtime behavior, since the guarantee under test is
precisely that these modules have no reference to persistence at all.

`aa_crawler.cli.app` is deliberately excluded from this guarantee: ADR-027
narrows it intentionally, so the CLI can construct `FileCrawlResultSink`
when `--output` is supplied. That narrowing is itself asserted below,
rather than left as a silent gap in this guard.
"""

from __future__ import annotations

import ast
import inspect
from typing import TYPE_CHECKING

import aa_crawler.application.runtime as runtime_module
import aa_crawler.application.service as service_module
import aa_crawler.cli.app as cli_app_module

if TYPE_CHECKING:
    from types import ModuleType


def _imported_module_names(module: ModuleType) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_application_modules_never_import_persistence() -> None:
    for module in (runtime_module, service_module):
        imported = _imported_module_names(module)
        assert not any("persistence" in name for name in imported), (
            f"{module.__name__} must remain unaware of aa_crawler.persistence"
        )


def test_cli_app_deliberately_imports_persistence_per_adr_027() -> None:
    imported = _imported_module_names(cli_app_module)
    assert any("persistence" in name for name in imported), (
        "aa_crawler.cli.app is expected to import aa_crawler.persistence "
        "per ADR-027's CLI-triggered persistence decision"
    )
