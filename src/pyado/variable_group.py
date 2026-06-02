"""Module to interact with Azure DevOps variable groups."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from pyado.api_call import ApiCall

UserId: TypeAlias = UUID
VariableGroupId: TypeAlias = int


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
    type: Literal["Vsts"]
    variable_group_refs: Any = Field(alias="variableGroupProjectReferences")
    variables: dict[str, VariableInfo]


class _VariableGroupInfoResults(BaseModel):
    """Type to read variable group details results."""

    value: list[VariableGroupInfo]


def iter_variable_group_details(
    project_api_call: ApiCall,
) -> Iterator[VariableGroupInfo]:
    """Iterate over the variable groups of the project.

    Yields:
        VariableGroupInfo objects for each variable group in the project.
    """
    response = project_api_call.get(
        "distributedtask",
        "variablegroups",
        version="5.1-preview.1",
    )
    results = _VariableGroupInfoResults.model_validate(response)
    yield from results.value


class _VariableGroupUpdateInfo(BaseModel):
    """Type to store updates for variable group values."""

    name: str
    variables: dict[str, VariableInfo]


def get_variable_group_api_call(
    project_api_call: ApiCall,
    var_group_id: VariableGroupId,
) -> ApiCall:
    """Get variable group API call.

    Returns:
        An ApiCall pointing at the variable group resource for the given ID.
    """
    return project_api_call.build_call(
        "distributedtask", "variablegroups", var_group_id
    )


def update_variable_group_entries(
    variable_group_api_call: ApiCall,
    var_group_name: str,
    variables: dict[str, VariableInfo],
) -> VariableGroupInfo:
    """Update variables in the variable group.

    Args:
        variable_group_api_call: Variable-group-level ADO API call (from
            get_variable_group_api_call).
        var_group_name: Name of the variable group (required by the API).
        variables: Mapping of variable names to updated VariableInfo values.

    Returns:
        Updated VariableGroupInfo parsed from the API response.
    """
    update_info = _VariableGroupUpdateInfo(name=var_group_name, variables=variables)
    response = variable_group_api_call.put(
        version="5.1-preview.1",
        json=update_info.model_dump(mode="json", by_alias=True),
    )
    return VariableGroupInfo.model_validate(response)
