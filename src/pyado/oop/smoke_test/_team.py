"""Smoke tests for Team."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project, Team
from pyado.oop.smoke_test._runner import _skip, _take, console, run


def _test_teams_read(proj: Project) -> Team | None:
    console.print("\n=== Teams (read) ===")
    teams = run("proj.iter_teams()", lambda: _take(proj.iter_teams(), 3))
    if not teams:
        _skip("team read tests", "no teams found")
        return None

    team: Team = teams[0]
    run("proj.get_team(name)", lambda: proj.get_team(team.name))

    run("team.id", lambda: team.id)
    run("team.name", lambda: team.name)
    run("team.api_call", lambda: team.api_call)
    run("team.info", lambda: team.info)
    run("team.project (back-nav)", lambda: team.project)
    run("team.org (back-nav)", lambda: team.org)
    run(
        "team.iter_sprint_iterations()",
        lambda: _take(team.iter_sprint_iterations(), 5),
    )
    run("team.list_sprint_iterations()", team.list_sprint_iterations)
    run("team.get_field_values()", team.get_field_values)
    run("team.iter_members()", lambda: _take(team.iter_members(), 5))
    run("team.list_members()", team.list_members)
    run(
        "proj.iter_team_sprint_iterations(team)",
        lambda tn=team.name: _take(proj.iter_team_sprint_iterations(tn), 5),
    )
    run(
        "proj.list_team_sprint_iterations(team)",
        lambda tn=team.name: proj.list_team_sprint_iterations(tn),
    )
    run(
        "proj.get_team_field_values(team)",
        lambda tn=team.name: proj.get_team_field_values(tn),
    )
    return team
