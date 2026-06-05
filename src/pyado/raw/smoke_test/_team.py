"""Smoke tests for team endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from uuid import UUID

from pyado import raw
from pyado.raw.smoke_test._runner import _skip, console, run, run_or_skip


def _test_teams_read(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> list[raw.TeamInfo]:
    console.print("\n=== TEAMS (read) ===")
    teams = run(
        "iter_teams",
        lambda: raw.list_teams(org_api_call, project_name),
    )
    if not teams:
        for label in (
            "get_team",
            "iter_team_members",
            "get_team_field_values",
            "iter_sprint_iterations [team-level]",
            "add_team_iteration",
        ):
            _skip(label, "no teams found")
        return []

    team = teams[0]
    run(
        f"get_team [name={team.name!r}]",
        lambda n=team.name: raw.get_team(org_api_call, project_name, n),
    )

    # Team-scoped API call: {org}/{project}/{team_name}/_apis
    proj_base = project_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis")
    team_api_call = raw.ApiCall(
        access_token=org_api_call.access_token,
        url=f"{proj_base}/{team.name}/_apis",
    )

    run(
        "iter_team_members",
        lambda: raw.list_team_members(org_api_call, project_name, team.id),
    )
    run(
        "get_team_field_values",
        lambda api=team_api_call: list(raw.get_team_field_values(api)),
    )

    # add_team_iteration: assign an existing iteration to the team (idempotent)
    existing_iterations = run(
        "iter_sprint_iterations [team-level]",
        lambda api=team_api_call: raw.list_sprint_iterations(api),
    )
    if existing_iterations:
        run(
            "add_team_iteration [re-add existing]",
            lambda api=team_api_call, iid=existing_iterations[0].id: (
                raw.add_team_iteration(api, iid)
            ),
        )
        # delete_team_iteration — remove then immediately re-add so the team
        # backlog is restored to its original state.
        run(
            "delete_team_iteration [remove then restore]",
            lambda api=team_api_call, iid=existing_iterations[0].id: (
                raw.delete_team_iteration(api, iid)
            ),
        )
        run(
            "add_team_iteration [restore after delete]",
            lambda api=team_api_call, iid=existing_iterations[0].id: (
                raw.add_team_iteration(api, iid)
            ),
        )
    else:
        # Fall back to the classification node tree to find an iteration identifier
        iter_tree = raw.get_classification_node(
            project_api_call, node_type="iterations", depth=2
        )
        node_with_id = next(
            (child for child in (iter_tree.children or []) if child.identifier),
            iter_tree if iter_tree.identifier else None,
        )
        if node_with_id and node_with_id.identifier:
            iter_uuid = UUID(node_with_id.identifier)
            run_or_skip(
                "add_team_iteration [from classification tree]",
                lambda api=team_api_call, iid=iter_uuid: raw.add_team_iteration(
                    api, iid
                ),
            )
        else:
            _skip("add_team_iteration", "no iteration nodes with UUID found")

    return teams
