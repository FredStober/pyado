"""Azure DevOps project API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from pyado.raw._core import ApiCall

__all__ = [
    "ProjectId",
    "ProjectInfo",
    "ProjectName",
    "iter_projects",
]

ProjectName = str
ProjectId = UUID


class ProjectInfo(BaseModel):
    """Type to store project details."""

    id: ProjectId
    name: ProjectName
    description: str | None = None
    state: Literal[
        "all",
        "createPending",
        "deleted",
        "deleting",
        "new",
        "unchanged",
        "wellFormed",
    ]
    revision: int
    visibility: Literal["private", "public", "unchanged"]
    last_update_time: datetime = Field(alias="lastUpdateTime")


class _ProjectListResults(BaseModel):
    """Internal: container for project list results."""

    value: list[ProjectInfo]


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
