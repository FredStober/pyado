"""Integration tests for team endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from uuid import UUID

from pyado import raw
from tests.integration.raw._support import console


def test_teams_read(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """List teams, members, iterations, and dashboards."""
    console.print("\n=== TEAMS (read) ===")
    teams = list(raw.iter_teams(org_api_call, project_name))
    assert teams == raw.list_teams(org_api_call, project_name)
    if not teams:
        return

    team = teams[0]
    raw.get_team(org_api_call, project_name, team.name)

    # Team-scoped API call: {org}/{project}/{team_name}/_apis
    proj_base = project_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis")
    team_api_call = raw.ApiCall(
        session=org_api_call.session,
        url=f"{proj_base}/{team.name}/_apis",
    )

    members = list(raw.iter_team_members(org_api_call, project_name, team.id))
    assert members == raw.list_team_members(org_api_call, project_name, team.id)
    list(raw.get_team_field_values(team_api_call))

    # add_team_iteration: assign an existing iteration to the team (idempotent)
    existing_iterations = raw.list_sprint_iterations(team_api_call)
    if existing_iterations:
        raw.add_team_iteration(team_api_call, existing_iterations[0].id)
        # delete_team_iteration — remove then immediately re-add so the team
        # backlog is restored to its original state.
        raw.delete_team_iteration(team_api_call, existing_iterations[0].id)
        raw.add_team_iteration(team_api_call, existing_iterations[0].id)
    else:
        # Fall back to the classification node tree to find an iteration identifier
        iter_tree = raw.get_classification_node(
            project_api_call,
            node_type=raw.ClassificationNodeUrlType.ITERATIONS,
            depth=2,
        )
        node_with_id = next(
            (child for child in (iter_tree.children or []) if child.identifier),
            iter_tree if iter_tree.identifier else None,
        )
        if node_with_id and node_with_id.identifier:
            iter_uuid = UUID(node_with_id.identifier)
            raw.add_team_iteration(team_api_call, iter_uuid)

    dashboards = list(raw.iter_dashboards(team_api_call))
    assert dashboards == raw.list_dashboards(team_api_call)
    if dashboards:
        dash = dashboards[0]
        dashboard_api_call = raw.get_dashboard_api_call(team_api_call, dash.id)
        if dashboard_api_call:
            raw.get_dashboard(dashboard_api_call)
