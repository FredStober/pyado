"""Azure DevOps Teams API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TypeAlias

from pyado.raw._core import AdoBaseModel, ApiCall, _IdentityRef

__all__ = [
    "TeamId",
    "TeamInfo",
    "TeamMember",
    "get_team",
    "iter_team_members",
    "iter_teams",
    "list_team_members",
    "list_teams",
]

#: String identifier for an ADO team.
TeamId: TypeAlias = str


class TeamInfo(AdoBaseModel):
    """An Azure DevOps team within a project."""

    id: TeamId
    name: str
    description: str | None = None
    url: str | None = None


class _TeamInfoResults(AdoBaseModel):
    """Internal: container for team list results."""

    value: list[TeamInfo]


class TeamMember(AdoBaseModel):
    """A single member of an Azure DevOps team."""

    identity: _IdentityRef
    is_team_admin: bool = False


class _TeamMemberResults(AdoBaseModel):
    """Internal: container for team member list results."""

    value: list[TeamMember]


def iter_teams(org_api_call: ApiCall, project_name: str) -> Iterator[TeamInfo]:
    """Iterate over all teams in a project.

    The ADO teams endpoint is ``GET {org}/_apis/projects/{project}/teams``.
    The project identifier sits *under* ``/_apis/``, so a project-scoped
    ``ApiCall`` (whose base URL is ``{org}/{project}/_apis``) cannot be used
    here — it would produce the wrong path ``{org}/{project}/_apis/teams``.
    An organisation-level ``ApiCall`` is required so that ``project_name`` can
    be appended after ``/_apis/projects/``.

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

    See :func:`iter_teams` for an explanation of why an organisation-level
    ``ApiCall`` is required rather than a project-scoped one.

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


def iter_team_members(
    org_api_call: ApiCall,
    project_name: str,
    team_id: str,
) -> Iterator[TeamMember]:
    """Iterate over all members of a team.

    The ADO team-members endpoint is
    ``GET {org}/_apis/projects/{project}/teams/{team}/members``.
    An organisation-level ``ApiCall`` is required because the project and team
    identifiers both sit *under* ``/_apis/``.

    Args:
        org_api_call: Organisation-level ADO API call (from
            :attr:`AzureDevOpsService.api_call`).
        project_name: Project name or UUID string.
        team_id: Team name or UUID string.

    Yields:
        TeamMember for each member of the team.
    """
    response = org_api_call.get(
        "projects", project_name, "teams", team_id, "members", version="7.1"
    )
    yield from _TeamMemberResults.model_validate(response).value


def list_teams(org_api_call: ApiCall, project_name: str) -> list[TeamInfo]:
    """Return all teams for the project as a list."""
    return list(iter_teams(org_api_call, project_name))


def list_team_members(
    org_api_call: ApiCall,
    project_name: str,
    team_id: str,
) -> list[TeamMember]:
    """Return all members of a team as a list."""
    return list(iter_team_members(org_api_call, project_name, team_id))
