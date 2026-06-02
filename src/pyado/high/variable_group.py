"""Higher-level wrappers for variable group operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any

from pyado.raw import (
    ApiCall,
    VariableGroupInfo,
    VariableGroupUpdateRequest,
    VariableInfo,
    put_variable_group,
)

__all__ = [
    "update_variable_group",
]


def update_variable_group(
    variable_group_api_call: ApiCall,
    name: str,
    variables: dict[str, VariableInfo],
    variable_group_project_references: Any = None,
    *,
    description: str | None = None,
    var_group_type: str | None = None,
    provider_data: Any = None,
) -> VariableGroupInfo:
    """Update a variable group.

    Args:
        variable_group_api_call: Variable-group-level ADO API call (from
            get_variable_group_api_call).
        name: Name of the variable group (required by the API).
        variables: Mapping of variable names to updated VariableInfo values.
        variable_group_project_references: Project reference list as returned
            by the GET response (``variableGroupProjectReferences`` field).
            Required by the ADO PUT API to identify the target project.
        description: Optional updated description for the variable group.
        var_group_type: Optional type string (e.g. ``"Vsts"``,
            ``"AzureKeyVault"``).
        provider_data: Optional provider-specific configuration object (e.g.
            key vault settings).

    Returns:
        Updated VariableGroupInfo parsed from the API response.
    """
    return put_variable_group(
        variable_group_api_call,
        VariableGroupUpdateRequest(
            name=name,
            variables=variables,
            variable_group_project_references=variable_group_project_references,
            description=description,
            type=var_group_type,
            provider_data=provider_data,
        ),
    )
