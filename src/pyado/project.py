"""Module to interact with Azure DevOps projects."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field

from pyado.api_call import ApiCall

ProjectName: TypeAlias = str
ProjectId: TypeAlias = UUID


class ProjectInfo(BaseModel):
    """Type to store project details."""

    id: ProjectId
    name: ProjectName
    description: str | None = None
    state: Literal["wellFormed"]
    revision: int
    visibility: Literal["private"]
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
