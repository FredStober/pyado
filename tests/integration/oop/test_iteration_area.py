"""Integration tests for Iteration and Area OOP classes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Area, Iteration, Project, ProjectBoards
from tests.integration.raw._support import console


def test_iteration_area_read(proj: Project) -> None:
    """Exercise Iteration and Area OOP class properties and back-navigation."""
    console.print("\n=== Iteration + Area (read) ===")
    boards: ProjectBoards = proj.boards
    iteration: Iteration | None = boards.get_iteration_node(depth=2)
    if iteration:
        _ = iteration.id
        _ = iteration.name
        _ = iteration.path
        _ = iteration.start_date
        _ = iteration.finish_date
        _ = iteration.children
        _ = iteration.project
        _ = iteration.org
        folders = proj.boards.get_query_tree()
        if folders:
            proj.boards.get_query_folder(folders[0].id)

    area: Area | None = boards.get_area_node(depth=2)
    if area:
        _ = area.id
        _ = area.name
        _ = area.path
        _ = area.children
        _ = area.project
        _ = area.org
