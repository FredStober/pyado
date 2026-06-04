"""Azure DevOps Teams API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pydantic import BaseModel

from pyado.raw._core import ApiCall

__all__ = [
    "TeamInfo",
    "get_team",
    "iter_teams",
]


class TeamInfo(BaseModel):
    """An Azure DevOps team within a project."""

    id: str
    name: str
    description: str | None = None
    url: str | None = None


class _TeamInfoResults(BaseModel):
    """Internal: container for team list results."""

    value: list[TeamInfo]


def iter_teams(org_api_call: ApiCall, project_name: str) -> Iterator[TeamInfo]:
    """Iterate over all teams in a project.

    Args:
        org_api_call: Organisation-level ADO API call (from
            AzureDevOpsService.api_call).
        project_name: Name of the project.

    Yields:
        TeamInfo for each team in the project.
    """
    page_size = 100
    skip = 0
    while True:
        response = org_api_call.get(
            "projects",
            project_name,
            "teams",
            parameters={"$top": page_size, "$skip": skip},
            version="7.1",
        )
        results = _TeamInfoResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def get_team(
    org_api_call: ApiCall,
    project_name: str,
    team_name_or_id: str,
) -> TeamInfo:
    """Return a specific team by name or ID.

    Args:
        org_api_call: Organisation-level ADO API call (from
            AzureDevOpsService.api_call).
        project_name: Name of the project.
        team_name_or_id: Team name or UUID string.

    Returns:
        TeamInfo for the requested team.
    """
    response = org_api_call.get(
        "projects",
        project_name,
        "teams",
        team_name_or_id,
        version="7.1",
    )
    return TeamInfo.model_validate(response)
