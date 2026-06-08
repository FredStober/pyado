"""OOP wrapper for Azure DevOps variable group resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.pipelines import _variable_group
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

    **ADO concept:** a *variable group* is a named, project-scoped store of
    key-value pairs managed at
    ``distributedtask/variablegroups/{variableGroupId}`` (docs:
    `distributedtask/variablegroups
    <https://learn.microsoft.com/rest/api/azure/devops/distributedtask/variablegroups>`_).
    Each entry is a :class:`~pyado.raw.VariableInfo` with a string value and
    an optional ``isSecret`` flag.  When ``isSecret`` is ``True`` ADO stores
    the value encrypted and returns ``null`` on subsequent GETs — the value
    is **write-only**.  A variable group may be backed by Azure Key Vault
    (``type='AzureKeyVault'``) instead of the native ADO store
    (``type='Vsts'``); in that case ``providerData`` carries the Key Vault
    configuration.  Pipeline permission grants for variable groups are
    **additive** — the API can never remove a grant made by another pipeline
    or via the portal.

    **Why it exists:** the ADO variable-group PUT endpoint has two quirks that
    ``VariableGroup`` hides from callers:

    * **Full-replace semantics** — every PUT must carry the *complete* set of
      variables, not just the changed ones.  :meth:`set_variable` and
      :meth:`delete_variable` fetch the current state, apply the targeted
      change, then write back the full set.

    * **Mandatory project references** — the PUT body must contain at least
      one entry in ``variableGroupProjectReferences`` even though the GET
      response often omits the field (returns ``null``).
      :meth:`_project_refs` synthesises a minimal entry from the owning
      :class:`~pyado.oop.project.Project` when the GET response is silent.

    Wraps a single ADO variable group and exposes its operations as instance
    methods.  Instances are obtained from
    :meth:`ProjectPipelines.library.iter_variable_groups` or
    :meth:`ProjectPipelines.library.get_variable_group`.

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
        self._info: VariableGroupInfo | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> VariableGroupInfo:
        """Variable group data captured at construction time."""
        if self._info is None:
            self._info = raw.get_variable_group_details(self._api_call)
        return self._info

    @property
    def id(self) -> VariableGroupId:
        """Numeric variable group ID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Variable group name."""
        return self.info.name

    @property
    def variables(self) -> dict[str, VariableInfo]:
        """Current variable mapping (name → VariableInfo)."""
        return self.info.variables

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
        if self.info.variable_group_refs:
            return self.info.variable_group_refs
        return [
            VariableGroupProjectReference.model_validate(
                {
                    "name": self.info.name,
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
        self._info = _variable_group.update_variable_group(
            self._api_call,
            name if name is not None else self.info.name,
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
        updated = dict(self.info.variables)
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
        updated = dict(self.info.variables)
        if var_name not in updated:
            raise KeyError(var_name)
        del updated[var_name]
        self.update(updated)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached variable group info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    def delete(self) -> None:
        """Delete this variable group from the project.

        The deletion is permanent and cannot be undone via the API.
        """
        raw.delete_variable_group(
            self._project.org.api_call,
            self.id,
            [str(self._project.id)],
        )
