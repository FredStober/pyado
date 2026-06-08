"""Integration test verifying OOP class coverage in the smoke test helpers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pathlib

from tests.integration.oop._support import check_oop_coverage


def test_oop_coverage() -> None:
    """Warn about uncovered OOP classes.

    Checks that all public OOP classes are referenced in the
    integration helpers.
    """
    check_oop_coverage(pathlib.Path(__file__).parent)
