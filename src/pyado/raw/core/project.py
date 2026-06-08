"""Azure DevOps project API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, AdoUrl, ApiCall

__all__ = [
    "ProjectId",
    "ProjectInfo",
    "ProjectName",
    "ProjectState",
    "ProjectVisibility",
    "get_project",
    "iter_projects",
]

ProjectName: TypeAlias = str
ProjectId: TypeAlias = UUID


class ProjectState(StrEnum):
    """Possible lifecycle states of an ADO project."""

    ALL = "all"
    CREATE_PENDING = "createPending"
    DELETED = "deleted"
    DELETING = "deleting"
    NEW = "new"
    UNCHANGED = "unchanged"
    WELL_FORMED = "wellFormed"


class ProjectVisibility(StrEnum):
    """Visibility settings for an ADO project."""

    PRIVATE = "private"
    PUBLIC = "public"
    UNCHANGED = "unchanged"


class _ProjectDefaultTeam(AdoBaseModel):
    """Default team reference embedded in a project response."""

    id: str
    name: str
    url: AdoUrl | None = None


class _ProcessTemplateCapability(AdoBaseModel):
    """Process template capability of a project."""

    template_name: str
    template_type_id: str


class _VersionControlCapability(AdoBaseModel):
    """Version control capability of a project."""

    source_control_type: str
    git_enabled: str
    tfvc_enabled: str


class _ProjectCapabilities(AdoBaseModel):
    """Capabilities block returned when includeCapabilities=true."""

    process_template: _ProcessTemplateCapability
    version_control: _VersionControlCapability = Field(alias="versioncontrol")


class ProjectInfo(AdoBaseModel):
    """Type to store project details."""

    id: ProjectId
    name: ProjectName
    description: str | None = None
    url: AdoUrl | None = None
    state: ProjectState
    revision: int
    visibility: ProjectVisibility
    last_update_time: datetime
    default_team: _ProjectDefaultTeam | None = None
    capabilities: _ProjectCapabilities | None = None


class _ProjectListResults(AdoBaseModel):
    """Internal: container for project list results."""

    value: list[ProjectInfo]


def get_project(
    org_api_call: ApiCall,
    name: str,
    *,
    include_capabilities: bool = False,
) -> ProjectInfo:
    """Return details for a single project by name or UUID string.

    Args:
        org_api_call: Organisation-level ADO API call.
        name: Project name (case-sensitive) or UUID string.
        include_capabilities: When ``True``, the response includes
            the project's process template and version control
            capabilities (default: ``False``).

    Returns:
        ProjectInfo for the requested project.
    """
    params: dict[str, int | str | bool] | None = (
        {"includeCapabilities": True} if include_capabilities else None
    )
    response = org_api_call.get(
        "projects", name, parameters=params, version="7.1-preview.1"
    )
    return ProjectInfo.model_validate(response)


def iter_projects(base_api_call: ApiCall) -> Iterator[ProjectInfo]:
    """Iterate over all projects in the ADO organisation.

    Args:
        base_api_call: Organisation-level ADO API call (URL must point at the
            org root or ``/_apis``).

    Yields:
        ProjectInfo for each project.
    """
    page_size = 100
    skip = 0
    while True:
        response = base_api_call.get(
            "projects",
            parameters={"$top": page_size, "$skip": skip},
            version="7.1-preview.1",
        )
        results = _ProjectListResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def list_projects(base_api_call: ApiCall) -> list[ProjectInfo]:
    """Return all projects as a list."""
    return list(iter_projects(base_api_call))
