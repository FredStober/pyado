"""Azure DevOps distributed task variable group API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pyado.raw._core import ApiCall

__all__ = [
    "UserId",
    "VariableGroupId",
    "VariableGroupInfo",
    "VariableGroupProjectReference",
    "VariableGroupUpdateRequest",
    "VariableGroupUserInfo",
    "VariableInfo",
    "get_variable_group_api_call",
    "iter_variable_group_details",
    "put_variable_group",
]

UserId = UUID
VariableGroupId = int


class VariableGroupUserInfo(BaseModel):
    """Type to store variable group user information."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    display_name: str | None = Field(default=None, alias="displayName")
    id: UserId
    unique_name: str | None = Field(default=None, alias="uniqueName")


class VariableInfo(BaseModel):
    """Type to store information about variables."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    is_secret: bool = Field(default=False, alias="isSecret")
    value: str | None = None


class _VgProjectRef(BaseModel):
    """Internal: project id/name pair within a variable group project reference."""

    id: str
    name: str


class VariableGroupProjectReference(BaseModel):
    """A project reference entry within a variable group's project references list."""

    description: str | None = None
    name: str
    project_reference: _VgProjectRef = Field(alias="projectReference")


class VariableGroupInfo(BaseModel):
    """Type to store variable group details."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    created_by: VariableGroupUserInfo = Field(alias="createdBy")
    created_on: datetime = Field(alias="createdOn")
    description: str | None = None
    id: VariableGroupId
    is_shared: bool = Field(alias="isShared")
    modified_by: VariableGroupUserInfo = Field(alias="modifiedBy")
    modified_on: datetime = Field(alias="modifiedOn")
    name: str
    type: str
    variable_group_refs: list[VariableGroupProjectReference] | None = Field(
        alias="variableGroupProjectReferences", default=None
    )
    variables: dict[str, VariableInfo]


class _VariableGroupInfoResults(BaseModel):
    """Type to read variable group details results."""

    value: list[VariableGroupInfo]


class VariableGroupUpdateRequest(BaseModel):
    """Request body for updating a variable group."""

    name: str
    variables: dict[str, VariableInfo]
    variable_group_project_references: list[VariableGroupProjectReference] | None = (
        Field(default=None, serialization_alias="variableGroupProjectReferences")
    )
    description: str | None = None
    type: str | None = None
    provider_data: Any = Field(default=None, serialization_alias="providerData")


def iter_variable_group_details(
    project_api_call: ApiCall,
) -> Iterator[VariableGroupInfo]:
    """Iterate over the variable groups of the project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        VariableGroupInfo objects for each variable group in the project.
    """
    response = project_api_call.get(
        "distributedtask",
        "variablegroups",
        version="7.1",
    )
    results = _VariableGroupInfoResults.model_validate(response)
    yield from results.value


def get_variable_group_api_call(
    project_api_call: ApiCall,
    var_group_id: VariableGroupId,
) -> ApiCall:
    """Get the API call for a specific variable group.

    Args:
        project_api_call: Project-level ADO API call.
        var_group_id: Numeric ID of the variable group.

    Returns:
        An ApiCall pointing at the variable group resource for the given ID.
    """
    return project_api_call.build_call(
        "distributedtask", "variablegroups", var_group_id
    )


def put_variable_group(
    variable_group_api_call: ApiCall,
    request: VariableGroupUpdateRequest,
) -> VariableGroupInfo:
    """Update a variable group.

    Args:
        variable_group_api_call: Variable-group-level ADO API call (from
            get_variable_group_api_call).
        request: Update request specifying the name, variables, and optional
            metadata fields.

    Returns:
        Updated VariableGroupInfo parsed from the API response.
    """
    response = variable_group_api_call.put(
        version="7.1",
        json=request.model_dump(mode="json", by_alias=True),
    )
    return VariableGroupInfo.model_validate(response)
