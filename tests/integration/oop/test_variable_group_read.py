"""Integration tests for VariableGroup OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project, VariableGroup
from tests.integration.raw._support import _take, console


def test_variable_group_read(proj: Project) -> None:
    """Exercise VariableGroup read properties: id, name, variables, refresh."""
    console.print("\n=== VariableGroup (read) ===")
    vgs = _take(proj.pipelines.library.iter_variable_groups(), 3)
    if not vgs:
        return

    vg: VariableGroup = vgs[0]
    proj.pipelines.library.get_variable_group(vg.name)
    proj.pipelines.library.get_variable_group_by_id(vg.id)

    _ = vg.id
    _ = vg.name
    _ = vg.variables
    _ = vg.info
    _ = vg.api_call
    _ = vg.project
    _ = vg.org
    vg.refresh()
