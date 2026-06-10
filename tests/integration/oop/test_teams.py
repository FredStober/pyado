"""Integration tests for Team OOP class."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project, Team
from tests.integration.raw._support import _take, console


def test_teams_read(proj: Project) -> None:
    """Exercise Team properties, sprint iterations, field values, and members."""
    console.print("\n=== Teams (read) ===")
    teams = _take(proj.boards.iter_teams(), 3)
    if not teams:
        return

    team: Team = teams[0]
    proj.boards.get_team(team.name)

    _ = team.id
    _ = team.name
    _ = team.api_call
    _ = team.info
    _ = team.project
    _ = team.org
    _take(team.iter_sprint_iterations(), 5)
    team.list_sprint_iterations()
    team.list_field_values()
    _take(team.iter_members(), 5)
    team.list_members()
    _take(proj.boards.iter_team_sprint_iterations(team.name), 5)
    proj.boards.list_team_sprint_iterations(team.name)
    proj.boards.list_team_field_values(team.name)
