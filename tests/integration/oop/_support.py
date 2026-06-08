"""Shared runner helpers for OOP integration coverage checks."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import ast
import inspect
import pathlib

from rich.console import Console
from rich.markup import escape

from pyado import oop

console = Console()

_OOP_COVERAGE_SKIP: frozenset[str] = frozenset([])


def _collect_oop_names(smoke_test_dir: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for py_file in smoke_test_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
    return names


def _find_uncovered_classes(names_used: set[str]) -> list[str]:
    uncovered: list[str] = []
    for name in dir(oop):
        if name.startswith("_") or name in _OOP_COVERAGE_SKIP:
            continue
        if not inspect.isclass(getattr(oop, name)):
            continue
        if name not in names_used:
            uncovered.append(name)
    return uncovered


def check_oop_coverage(smoke_test_dir: pathlib.Path) -> None:
    """Warn about any public OOP classes not referenced in the smoke test.

    Scans all ``*.py`` files in *smoke_test_dir* for class-name references
    (via import aliases and bare name usage), then checks whether every public
    class in ``pyado.oop`` is covered.  Prints a warning for each uncovered
    class — informational only.

    Raises:
        AssertionError: If any public OOP classes are not referenced.
    """
    uncovered = _find_uncovered_classes(_collect_oop_names(smoke_test_dir))
    if uncovered:
        console.print(
            "\n[yellow]OOP coverage gaps "
            "(classes not referenced in this smoke test):[/yellow]"
        )
        for sym in sorted(uncovered):
            console.print(f"  [dim]{escape(sym)}[/dim]")
        gap_list = ", ".join(sorted(uncovered))
        msg = f"OOP coverage: classes not referenced: {gap_list}"
        raise AssertionError(msg)
    console.print("\n[dim]OOP coverage: all public classes referenced.[/dim]")
