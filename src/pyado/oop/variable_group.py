"""OOP wrapper for Azure DevOps variable group resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any

from pyado import high, raw
from pyado.raw import (
    ApiCall,
    VariableGroupId,
    VariableGroupInfo,
    VariableGroupProjectReference,
    VariableInfo,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["VariableGroup"]


class VariableGroup:
    """An Azure DevOps variable group resource.

    Wraps a single ADO variable group and exposes its operations as instance
    methods.  Instances are obtained from
    :meth:`Project.iter_variable_groups` or
    :meth:`Project.get_variable_group`.

    Variable groups are not cached — each factory call returns a fresh
    instance.

    Attributes:
        _project: The Project this variable group belongs to.
        _api_call: Variable-group-level API call used by all operations.
        _info: The variable group data returned from the API at construction
            time.
    """

    def __init__(
        self,
        project: "Project",
        variable_group_api_call: ApiCall,
        info: VariableGroupInfo,
    ) -> None:
        """Construct a VariableGroup wrapper.

        Args:
            project: The Project that owns this variable group.
            variable_group_api_call: Variable-group-level ADO API call (from
                raw.get_variable_group_api_call).
            info: Variable group data as returned from the API.
        """
        self._project = project
        self._api_call = variable_group_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> VariableGroupInfo:
        """Variable group data captured at construction time."""
        return self._info

    @property
    def id(self) -> VariableGroupId:
        """Numeric variable group ID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Variable group name."""
        return self._info.name

    @property
    def variables(self) -> dict[str, VariableInfo]:
        """Current variable mapping (name → VariableInfo)."""
        return self._info.variables

    @property
    def api_call(self) -> ApiCall:
        """Variable-group-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this variable group belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this variable group belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def _project_refs(self) -> list[VariableGroupProjectReference]:
        """Return project references to include in PUT requests.

        ADO's variable group PUT endpoint requires at least one entry in
        ``variableGroupProjectReferences``.  When the GET response omits this
        field (returns ``null``), we construct the entry from the owning
        project's id and name.
        """
        if self._info.variable_group_refs:
            return self._info.variable_group_refs
        return [
            VariableGroupProjectReference.model_validate(
                {
                    "name": self._info.name,
                    "projectReference": {
                        "id": str(self._project.id),
                        "name": self._project.name,
                    },
                }
            )
        ]

    def update(
        self,
        variables: dict[str, VariableInfo],
        *,
        name: str | None = None,
        description: str | None = None,
        var_group_type: str | None = None,
        provider_data: Any = None,
    ) -> None:
        """Replace the variable group's variables (and optionally its metadata).

        Args:
            variables: New variable mapping to apply.  Replaces the existing
                set entirely.
            name: New name for the variable group.  Defaults to the current
                name if not supplied.
            description: Updated description, or ``None`` to leave unchanged.
            var_group_type: Optional type string (e.g. ``"Vsts"``,
                ``"AzureKeyVault"``).
            provider_data: Optional provider-specific configuration object
                (e.g. key vault settings).
        """
        self._info = high.update_variable_group(
            self._api_call,
            name if name is not None else self._info.name,
            variables,
            self._project_refs(),
            description=description,
            var_group_type=var_group_type,
            provider_data=provider_data,
        )

    def set_variable(
        self, var_name: str, value: str, *, is_secret: bool = False
    ) -> None:
        """Set or update a single variable in the group.

        Fetches all current variables, merges the update, then writes back.

        Args:
            var_name: Name of the variable to set.
            value: New value for the variable.
            is_secret: When ``True`` the variable is marked as secret.
        """
        updated = dict(self._info.variables)
        updated[var_name] = VariableInfo.model_validate(
            {"value": value, "isSecret": is_secret}
        )
        self.update(updated)

    def delete_variable(self, var_name: str) -> None:
        """Remove a variable from the group.

        Args:
            var_name: Name of the variable to remove.

        Raises:
            KeyError: If the variable does not exist in the group.
        """
        updated = dict(self._info.variables)
        if var_name not in updated:
            raise KeyError(var_name)
        del updated[var_name]
        self.update(updated)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch variable group info from the API immediately."""
        for info in raw.iter_variable_group_details(self._project.api_call):
            if info.id == self._info.id:
                self._info = info
                return
