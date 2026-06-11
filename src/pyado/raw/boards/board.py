"""Azure DevOps Work API — board configuration (columns, swimlanes, card settings)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any

from pyado.raw._core import ApiCall

__all__ = [
    "get_board_columns",
    "get_board_rows",
    "get_boards",
    "get_card_settings",
    "put_board_columns",
    "put_board_rows",
    "put_card_settings",
]

_VERSION = "7.1"


def get_boards(team_api: ApiCall) -> list[dict[str, Any]]:
    """Return all boards visible to the team.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.

    Returns:
        List of board summary dicts (each has at least ``id`` and ``name``).
    """
    response: dict[str, Any] = team_api.get("work", "boards", version=_VERSION)
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def get_board_columns(team_api: ApiCall, board_id: str) -> list[dict[str, Any]]:
    """Return the column definitions for a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.

    Returns:
        List of column dicts from the ADO Work API.
    """
    response: dict[str, Any] = team_api.get(
        "work", "boards", board_id, "columns", version=_VERSION
    )
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def put_board_columns(
    team_api: ApiCall,
    board_id: str,
    columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace all column definitions on a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.
        columns: List of column definition dicts to set.

    Returns:
        Updated list of column dicts from the ADO Work API.
    """
    response: dict[str, Any] = team_api.put(
        "work",
        "boards",
        board_id,
        "columns",
        json=columns,
        version=_VERSION,
    )
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def get_board_rows(team_api: ApiCall, board_id: str) -> list[dict[str, Any]]:
    """Return the swimlane (row) definitions for a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.

    Returns:
        List of swimlane dicts from the ADO Work API.
    """
    response: dict[str, Any] = team_api.get(
        "work", "boards", board_id, "rows", version=_VERSION
    )
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def put_board_rows(
    team_api: ApiCall,
    board_id: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace all swimlane (row) definitions on a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.
        rows: List of swimlane dicts to set.

    Returns:
        Updated list of swimlane dicts from the ADO Work API.
    """
    response: dict[str, Any] = team_api.put(
        "work",
        "boards",
        board_id,
        "rows",
        json=rows,
        version=_VERSION,
    )
    result: list[dict[str, Any]] = response.get("value", [])
    return result


def get_card_settings(team_api: ApiCall, board_id: str) -> dict[str, Any]:
    """Return the card settings for a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.

    Returns:
        Card settings dict from the ADO Work API.
    """
    result: dict[str, Any] = team_api.get(
        "work", "boards", board_id, "cardsettings", version=_VERSION
    )
    return result


def put_card_settings(
    team_api: ApiCall,
    board_id: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    """Replace card settings on a board.

    Args:
        team_api: ApiCall whose URL is ``{org}/{project_id}/{team_id}/_apis``.
        board_id: ADO board GUID.
        settings: Card settings dict to set.

    Returns:
        Updated card settings dict from the ADO Work API.
    """
    result: dict[str, Any] = team_api.put(
        "work",
        "boards",
        board_id,
        "cardsettings",
        json=settings,
        version=_VERSION,
    )
    return result
