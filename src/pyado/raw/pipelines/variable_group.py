"""Azure DevOps distributed task variable group API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "UserId",
    "VariableGroupCreateRequest",
    "VariableGroupId",
    "VariableGroupInfo",
    "VariableGroupProjectReference",
    "VariableGroupUpdateRequest",
    "VariableGroupUserInfo",
    "VariableInfo",
    "delete_variable_group",
    "get_variable_group_api_call",
    "get_variable_group_details",
    "iter_variable_group_details",
    "post_variable_group",
    "put_variable_group",
]

UserId: TypeAlias = UUID
VariableGroupId: TypeAlias = int


class VariableGroupUserInfo(AdoBaseModel):
    """Type to store variable group user information."""

    display_name: str | None = None
    id: UserId
    unique_name: str | None = None


class VariableInfo(AdoBaseModel):
    """Type to store information about variables."""

    is_secret: bool = False
    value: str | None = None


class _VgProjectRef(AdoBaseModel):
    """Internal: project id/name pair within a variable group project reference."""

    id: str
    name: str


class VariableGroupProjectReference(AdoBaseModel):
    """A project reference entry within a variable group's project references list."""

    description: str | None = None
    name: str
    project_reference: _VgProjectRef


class VariableGroupInfo(AdoBaseModel, extra="forbid"):
    """Type to store variable group details."""

    created_by: VariableGroupUserInfo
    created_on: datetime
    description: str | None = None
    id: VariableGroupId
    is_shared: bool
    modified_by: VariableGroupUserInfo
    modified_on: datetime
    name: str
    type: str
    variable_group_refs: list[VariableGroupProjectReference] | None = Field(
        alias="variableGroupProjectReferences", default=None
    )
    variables: dict[str, VariableInfo]


class _VariableGroupInfoResults(AdoBaseModel):
    """Type to read variable group details results."""

    value: list[VariableGroupInfo]


class VariableGroupUpdateRequest(AdoBaseModel):
    """Request body for updating a variable group."""

    name: str
    variables: dict[str, VariableInfo]
    variable_group_project_references: list[VariableGroupProjectReference] | None = None
    description: str | None = None
    type: str | None = None
    provider_data: Any = None


class VariableGroupCreateRequest(AdoBaseModel):
    """Request body for creating a variable group."""

    name: str
    variables: dict[str, VariableInfo]
    variable_group_project_references: list[VariableGroupProjectReference]
    description: str | None = None
    type: str = "Vsts"
    provider_data: Any = None


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


def get_variable_group_details(
    variable_group_api_call: ApiCall,
) -> VariableGroupInfo:
    """Fetch the details of a single variable group by its API call.

    Args:
        variable_group_api_call: Variable-group-level ADO API call (from
            get_variable_group_api_call).

    Returns:
        VariableGroupInfo for the requested variable group.
    """
    response = variable_group_api_call.get(version="7.1")
    return VariableGroupInfo.model_validate(response)


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
    body = request.model_dump(mode="json", by_alias=True, exclude_none=True)
    # ADO's variable-group PUT is a full replace: omitting ``description``
    # causes ADO to clear it.  Always include the field so that a ``None``
    # (or empty-string) value is sent explicitly and the existing description
    # is not silently wiped.
    if "description" not in body:
        body["description"] = request.description
    response = variable_group_api_call.put(version="7.1", json=body)
    return VariableGroupInfo.model_validate(response)


def post_variable_group(
    project_api_call: ApiCall,
    request: VariableGroupCreateRequest,
) -> VariableGroupInfo:
    """Create a new variable group in the project.

    Args:
        project_api_call: Project-level ADO API call.
        request: Create request specifying the name, variables, project
            references, and optional metadata fields.

    Returns:
        VariableGroupInfo for the newly created variable group.
    """
    response = project_api_call.post(
        "distributedtask",
        "variablegroups",
        version="7.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return VariableGroupInfo.model_validate(response)


def delete_variable_group(
    org_api_call: ApiCall,
    var_group_id: VariableGroupId,
    project_ids: list[str],
) -> None:
    """Delete a variable group.

    The DELETE endpoint is organisation-scoped (not project-scoped) and
    requires one or more project UUIDs via the ``projectIds`` query parameter.

    Args:
        org_api_call: Organisation-level ADO API call.
        var_group_id: Numeric ID of the variable group to delete.
        project_ids: List of project UUIDs the variable group is associated with.
    """
    org_api_call.delete(
        "distributedtask",
        "variablegroups",
        var_group_id,
        parameters={"projectIds": ",".join(project_ids)},
        version="7.1",
    )


def list_variable_group_details(
    project_api_call: ApiCall,
) -> list[VariableGroupInfo]:
    """Return all variable groups for the project as a list."""
    return list(iter_variable_group_details(project_api_call))
