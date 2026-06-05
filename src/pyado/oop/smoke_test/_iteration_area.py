"""Smoke tests for Iteration and Area."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project
from pyado.oop.smoke_test._runner import _skip, console, run


def _test_iteration_area_read(proj: Project) -> None:
    console.print("\n=== Iteration + Area (read) ===")
    iteration = run(
        "proj.get_iteration_node(depth=2)", lambda: proj.get_iteration_node(depth=2)
    )
    if iteration:
        run("iteration.id", lambda: iteration.id)
        run("iteration.name", lambda: iteration.name)
        run("iteration.path", lambda: iteration.path)
        run("iteration.start_date", lambda: iteration.start_date)
        run("iteration.finish_date", lambda: iteration.finish_date)
        run("iteration.children", lambda: iteration.children)
        run("iteration.project (back-nav)", lambda: iteration.project)
        run("iteration.org (back-nav)", lambda: iteration.org)
        folders = proj.get_query_tree()
        if folders:
            run(
                "proj.get_query_folder(root_id)",
                lambda fid=folders[0].id: proj.get_query_folder(fid),
            )
        else:
            _skip("proj.get_query_folder(root_id)", "no root folders")

    area = run("proj.get_area_node(depth=2)", lambda: proj.get_area_node(depth=2))
    if area:
        run("area.id", lambda: area.id)
        run("area.name", lambda: area.name)
        run("area.path", lambda: area.path)
        run("area.children", lambda: area.children)
        run("area.project (back-nav)", lambda: area.project)
        run("area.org (back-nav)", lambda: area.org)
