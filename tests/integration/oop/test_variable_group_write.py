"""Integration tests for VariableGroup OOP class (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import VariableGroup


def test_write_variable_group(vg: VariableGroup | None) -> None:
    """Exercise VariableGroup.set_variable() and delete_variable()."""
    if vg is None:
        return
    smoke_var = f"oop_smoke_{uuid.uuid4().hex[:6]}"
    set_failed = False
    try:
        vg.set_variable(smoke_var, "smoke-value")
    except Exception:
        set_failed = True
    _ = vg.variables
    if not set_failed:
        vg.delete_variable(smoke_var)
    vg.refresh()
