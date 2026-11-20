"""Integration tests for board, team settings, and card settings endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado import raw
from pyado.exceptions import AzureDevOpsError
from tests.integration.raw._support import console


def _team_api_call(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> raw.ApiCall:
    """Return an API call scoped to the first team of the project."""
    teams = raw.list_teams(org_api_call, project_name)
    if not teams:
        pytest.skip(reason="project has no teams")
    proj_base = project_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis")
    return raw.ApiCall(
        session=org_api_call.session,
        url=f"{proj_base}/{teams[0].name}/_apis",
    )


def test_boards_roundtrip(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Read boards and write the unchanged columns, rows, and card settings back."""
    console.print("\n=== BOARDS (read + idempotent write) ===")
    team_api = _team_api_call(org_api_call, project_api_call, project_name)
    boards = raw.get_boards(team_api)
    if not boards:
        pytest.skip(reason="team has no boards")
    board_id = str(boards[0]["id"])

    columns = raw.get_board_columns(team_api, board_id)
    rows = raw.get_board_rows(team_api, board_id)
    card_settings = raw.get_card_settings(team_api, board_id)
    console.print(f"  {len(columns)} columns, {len(rows)} rows")

    try:
        raw.put_board_columns(team_api, board_id, columns)
        raw.put_board_rows(team_api, board_id, rows)
        raw.put_card_settings(team_api, board_id, card_settings)
    except AzureDevOpsError as exc:
        pytest.skip(reason=f"board write not permitted: {exc}")


def test_team_settings_roundtrip(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Read team settings, iterations, and field values; write them back unchanged."""
    console.print("\n=== TEAM SETTINGS (read + idempotent write) ===")
    team_api = _team_api_call(org_api_call, project_api_call, project_name)
    settings = raw.get_team_settings(team_api)
    iterations = raw.get_team_iterations(team_api)
    field_settings = raw.get_team_field_settings(team_api)
    console.print(f"  {len(iterations)} team iteration(s)")

    try:
        raw.patch_team_settings(
            team_api, {"bugsBehavior": settings.get("bugsBehavior", "off")}
        )
        raw.patch_team_field_values(team_api, field_settings)
    except AzureDevOpsError as exc:
        pytest.skip(reason=f"team settings write not permitted: {exc}")
