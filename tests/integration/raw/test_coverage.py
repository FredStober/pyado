"""Integration test verifying raw API coverage in the smoke test helpers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import ast
import inspect
import pathlib

from pyado import raw

# Symbols intentionally excluded from coverage checking:
#   get_session        — low-level transport helper, not an ADO endpoint
#   AdoUrl             — type alias / constructor, not an endpoint function
#   delete_secure_file — destructive; no safe smoke-test without prior upload
_RAW_COVERAGE_SKIP: frozenset[str] = frozenset(["delete_secure_file"])


def check_raw_coverage(smoke_test_dir: pathlib.Path) -> None:
    """Warn about any public raw API functions not referenced in the smoke test.

    Scans all ``*.py`` files in *smoke_test_dir* for ``raw.<name>`` attribute
    accesses, then checks whether every public callable in ``pyado.raw`` is
    covered.  Prints a warning for each uncovered function — informational only.

    Raises:
        AssertionError: If any public raw API functions are not referenced.
    """
    raw_attrs_used: set[str] = set()
    for py_file in smoke_test_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "raw"
            ):
                raw_attrs_used.add(node.attr)

    uncovered: list[str] = []
    for name in dir(raw):
        if name.startswith("_") or name in _RAW_COVERAGE_SKIP:
            continue
        obj = getattr(raw, name)
        if not (inspect.isfunction(obj) or inspect.isbuiltin(obj)):
            continue
        if name not in raw_attrs_used:
            uncovered.append(name)

    if uncovered:
        gap_list = ", ".join(sorted(uncovered))
        msg = f"Raw API coverage: functions not called via raw.<name>: {gap_list}"
        raise AssertionError(msg)


def test_raw_coverage() -> None:
    """Warn about uncovered raw API functions.

    Checks that all public raw API functions are referenced in the
    integration helpers.
    """
    check_raw_coverage(pathlib.Path(__file__).parent)
