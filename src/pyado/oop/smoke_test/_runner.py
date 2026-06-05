"""Shared test infrastructure: state, runner helpers, coverage check."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import ast
import inspect
import pathlib

import pyado.oop as _oop_pkg
from pyado.raw.smoke_test._runner import (
    _fail,
    _load_config,
    _ok,
    _print_summary,
    _report_coverage_gaps,
    _results,
    _skip,
    _take,
    console,
    run,
)

__all__ = [
    "_fail",
    "_load_config",
    "_ok",
    "_print_summary",
    "_report_coverage_gaps",
    "_results",
    "_skip",
    "_take",
    "console",
    "run",
]

# ---------------------------------------------------------------------------
# OOP API coverage check
# ---------------------------------------------------------------------------

# Symbols excluded from OOP coverage checking because they require
# SYSTEM_ACCESSTOKEN which is only available inside an ADO agent process.
_OOP_COVERAGE_SKIP: frozenset[str] = frozenset(
    [
        "ActiveBuildTask.add_issues",
        "ActiveBuildTask.error_count",
        "ActiveBuildTask.get_job",
        "ActiveBuildTask.get_record",
        "ActiveBuildTask.issues",
        "ActiveBuildTask.send_feed",
        "ActiveBuildTask.send_log",
        "ActiveBuildTask.send_message",
        "ActiveBuildTask.warning_count",
        "Build.get_active_build_task",
    ]
)

_OOP_CLASSES_TO_CHECK: list[type] = []


def _collect_oop_classes() -> None:
    """Populate _OOP_CLASSES_TO_CHECK from pyado.oop at import time."""
    for name in dir(_oop_pkg):
        obj = getattr(_oop_pkg, name)
        if (
            inspect.isclass(obj)
            and not name.startswith("_")
            and obj.__module__.startswith("pyado.oop")
        ):
            _OOP_CLASSES_TO_CHECK.append(obj)


_collect_oop_classes()


def _collect_labels(smoke_test_dir: pathlib.Path) -> set[str]:
    """Return all string literals and attribute names found in *smoke_test_dir*.

    Scans every ``*.py`` file for AST constants (strings) and attribute
    accesses, collecting names used in the smoke test suite.
    """
    labels: set[str] = set()
    for py_file in smoke_test_dir.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.s, str):
                labels.add(node.s)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                labels.add(node.attr)
    return labels


def check_oop_coverage(smoke_test_dir: pathlib.Path) -> None:
    """Warn about any public OOP methods/properties not referenced in the smoke test.

    Scans all ``*.py`` files in *smoke_test_dir*, collects every string
    literal and attribute access, then checks whether each public
    method/property name of every OOP class appears at least once.
    Prints a warning for each uncovered symbol — this is informational only
    and does not affect the exit code.
    """
    labels_in_source = _collect_labels(smoke_test_dir)

    uncovered: list[str] = []
    for cls in _OOP_CLASSES_TO_CHECK:
        for member_name, _ in inspect.getmembers(cls):
            if member_name.startswith("_"):
                continue
            sym = f"{cls.__name__}.{member_name}"
            if sym in _OOP_COVERAGE_SKIP:
                continue
            if member_name not in labels_in_source:
                uncovered.append(sym)

    _report_coverage_gaps(
        uncovered,
        "OOP API coverage",
        "symbols not referenced in this smoke test",
    )
