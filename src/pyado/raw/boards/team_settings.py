"""Azure DevOps Work API — team settings, iterations, and field values."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any

from pyado.raw._core import ApiCall
from pyado.raw.boards.work_item import TeamFieldSettings

__all__ = [
    "get_team_iterations",
    "get_team_settings",
    "patch_team_field_values",
    "patch_team_settings",
]

_VERSION = "7.1"


def get_team_settings(team_api: ApiCall) -> dict[str, Any]:
    """Return the team settings for the given team.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.

    Returns:
        Dict of raw team settings from the ADO Work API.
    """
    result: dict[str, Any] = team_api.get("work", "teamsettings", version=_VERSION)
    return result


def patch_team_settings(team_api: ApiCall, body: dict[str, Any]) -> dict[str, Any]:
    """Update team settings via PATCH.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        body: Partial team settings dict (only changed fields required).

    Returns:
        Updated team settings dict from the ADO Work API.
    """
    result: dict[str, Any] = team_api.patch(
        "work", "teamsettings", json=body, version=_VERSION
    )
    return result


def get_team_iterations(team_api: ApiCall) -> list[dict[str, Any]]:
    """Return the list of iterations the team subscribes to.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.

    Returns:
        List of iteration dicts (each has at least ``id`` and ``name``).
    """
    response: dict[str, Any] = team_api.get(
        "work", "teamsettings", "iterations", version=_VERSION
    )
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def patch_team_field_values(
    team_api: ApiCall,
    settings: TeamFieldSettings,
) -> TeamFieldSettings:
    """Update team field values (area-path assignments) via PATCH.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        settings: Default area path and the full list of assigned paths.

    Returns:
        Updated TeamFieldSettings from the ADO Work API.
    """
    result = team_api.patch(
        "work",
        "teamsettings",
        "teamfieldvalues",
        json=settings.model_dump(by_alias=True, mode="json"),
        version=_VERSION,
    )
    return TeamFieldSettings.model_validate(result)
