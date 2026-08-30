"""Guard ADR-024's optionality: persistence must remain fully optional.

`ArticleCrawlService`, `ApplicationRuntime`, and `aa_crawler.cli` must never
import `aa_crawler.persistence`. This is verified statically (via `ast`)
rather than by exercising runtime behavior, since the guarantee under test is
precisely that these modules have no reference to persistence at all.
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


def test_application_and_cli_modules_never_import_persistence() -> None:
    for module in (runtime_module, service_module, cli_app_module):
        imported = _imported_module_names(module)
        assert not any("persistence" in name for name in imported), (
            f"{module.__name__} must remain unaware of aa_crawler.persistence"
        )
