"""Smoke tests for VariableGroup."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import Project, VariableGroup
from pyado.oop.smoke_test._runner import _fail, _ok, _skip, _take, console, run


def _test_variable_group_read(proj: Project) -> VariableGroup | None:
    console.print("\n=== VariableGroup (read) ===")
    vgs = run(
        "proj.iter_variable_groups()", lambda: _take(proj.iter_variable_groups(), 3)
    )
    if not vgs:
        _skip("variable group read tests", "no variable groups found")
        return None

    vg: VariableGroup = vgs[0]
    run("proj.get_variable_group(name)", lambda: proj.get_variable_group(vg.name))
    run(
        "proj.get_variable_group_by_id(id)",
        lambda vgid=vg.id: proj.get_variable_group_by_id(vgid),
    )

    run("vg.id", lambda: vg.id)
    run("vg.name", lambda: vg.name)
    run("vg.variables", lambda: vg.variables)
    run("vg.info", lambda: vg.info)
    run("vg.api_call", lambda: vg.api_call)
    run("vg.project (back-nav)", lambda: vg.project)
    run("vg.org (back-nav)", lambda: vg.org)
    run("vg.refresh()", vg.refresh)
    return vg


def _test_write_variable_group(vg: VariableGroup) -> None:
    console.print("\n=== VariableGroup (write) ===")
    smoke_var = f"oop_smoke_{uuid.uuid4().hex[:6]}"
    set_failed = False
    try:
        vg.set_variable(smoke_var, "smoke-value")
        _ok("vg.set_variable()")
    except Exception as ex:
        _fail("vg.set_variable()", ex)
        set_failed = True
    run("vg.variables after set", lambda: vg.variables)
    if not set_failed:
        run("vg.delete_variable()", lambda: vg.delete_variable(smoke_var))
    else:
        _skip("vg.delete_variable()", "set_variable failed")
    run("vg.refresh()", vg.refresh)
