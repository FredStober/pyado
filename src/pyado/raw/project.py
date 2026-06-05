"""Azure DevOps project API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from pyado.raw._core import ApiCall

__all__ = [
    "ProjectId",
    "ProjectInfo",
    "ProjectName",
    "ProjectState",
    "ProjectVisibility",
    "get_project",
    "iter_projects",
]

ProjectName = str
ProjectId = UUID


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


class ProjectInfo(BaseModel):
    """Type to store project details."""

    id: ProjectId
    name: ProjectName
    description: str | None = None
    state: ProjectState
    revision: int
    visibility: ProjectVisibility
    last_update_time: datetime = Field(alias="lastUpdateTime")


class _ProjectListResults(BaseModel):
    """Internal: container for project list results."""

    value: list[ProjectInfo]


def get_project(org_api_call: ApiCall, name: str) -> ProjectInfo:
    """Return details for a single project by name or UUID string.

    Args:
        org_api_call: Organisation-level ADO API call.
        name: Project name (case-sensitive) or UUID string.

    Returns:
        ProjectInfo for the requested project.
    """
    response = org_api_call.get("projects", name, version="7.1-preview.1")
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
