"""Azure DevOps Work API — team settings, iterations, and field values."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any

from pyado.raw._core import ApiCall

__all__ = [
    "add_team_iteration",
    "get_team_field_values",
    "get_team_iterations",
    "get_team_settings",
    "patch_team_field_values",
    "patch_team_settings",
    "remove_team_iteration",
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


def add_team_iteration(team_api: ApiCall, iteration_id: str) -> dict[str, Any]:
    """Subscribe the team to an iteration.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        iteration_id: GUID of the iteration classification node.

    Returns:
        The newly added iteration dict from the ADO Work API.
    """
    result: dict[str, Any] = team_api.post(
        "work",
        "teamsettings",
        "iterations",
        json={"id": iteration_id},
        version=_VERSION,
    )
    return result


def remove_team_iteration(team_api: ApiCall, iteration_id: str) -> None:
    """Unsubscribe the team from an iteration.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        iteration_id: GUID of the iteration classification node.
    """
    team_api.delete(
        "work",
        "teamsettings",
        "iterations",
        iteration_id,
        version=_VERSION,
    )


def get_team_field_values(team_api: ApiCall) -> dict[str, Any]:
    """Return the team field values (area-path assignments).

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.

    Returns:
        Dict with ``defaultValue`` and ``values`` from the ADO Work API.
    """
    result: dict[str, Any] = team_api.get(
        "work", "teamsettings", "teamfieldvalues", version=_VERSION
    )
    return result


def patch_team_field_values(team_api: ApiCall, body: dict[str, Any]) -> dict[str, Any]:
    """Update team field values (area-path assignments) via PATCH.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        body: Dict with ``defaultValue`` and ``values`` keys.

    Returns:
        Updated team field values dict from the ADO Work API.
    """
    result: dict[str, Any] = team_api.patch(
        "work",
        "teamsettings",
        "teamfieldvalues",
        json=body,
        version=_VERSION,
    )
    return result
