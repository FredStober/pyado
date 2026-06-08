"""PipelineLibrary — the Pipeline Library sub-section object for a project."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.pipelines.secure_file import SecureFile
from pyado.oop.pipelines.variable_group import VariableGroup
from pyado.raw import (
    VariableGroupCreateRequest,
    VariableGroupId,
    VariableGroupProjectReference,
    VariableInfo,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project


class PipelineLibrary:
    """The library sub-section of a project's Pipelines section.

    Accessed via ``project.pipelines.library``.  Exposes variable group and
    secure file operations that belong to the ADO Pipeline Library.

    Attributes:
        _project: The owning Project.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a PipelineLibrary section.

        Args:
            project: The Project this section belongs to.
        """
        self._project = project

    # ------------------------------------------------------------------
    # Variable groups
    # ------------------------------------------------------------------

    def iter_variable_groups(self) -> Iterator[VariableGroup]:
        """Iterate over all variable groups in the project.

        Yields:
            VariableGroup for each variable group in the project.
        """
        for info in raw.iter_variable_group_details(self._project.api_call):
            vg_api_call = raw.get_variable_group_api_call(
                self._project.api_call, info.id
            )
            yield VariableGroup(self._project, vg_api_call, info)

    def get_variable_group(self, name: str) -> VariableGroup:
        """Return a variable group by name.

        Args:
            name: Variable group name (case-sensitive).

        Returns:
            VariableGroup wrapping the requested variable group.

        Raises:
            KeyError: If no variable group with the given name exists.
        """
        for vg in self.iter_variable_groups():
            if vg.name == name:
                return vg
        raise KeyError(name)

    def get_variable_group_by_id(
        self, variable_group_id: VariableGroupId
    ) -> VariableGroup:
        """Return a variable group by numeric ID.

        Args:
            variable_group_id: Numeric variable group ID.

        Returns:
            VariableGroup wrapping the requested variable group.
        """
        vg_api_call = raw.get_variable_group_api_call(
            self._project.api_call, variable_group_id
        )
        info = raw.get_variable_group_details(vg_api_call)
        return VariableGroup(self._project, vg_api_call, info)

    def create_variable_group(
        self,
        name: str,
        variables: dict[str, VariableInfo],
        *,
        description: str | None = None,
        var_group_type: str = "Vsts",
        provider_data: Any = None,
    ) -> VariableGroup:
        """Create a new variable group in the project.

        Args:
            name: Name for the new variable group.
            variables: Mapping of variable names to VariableInfo values.
            description: Optional description for the variable group.
            var_group_type: Variable group type (default: ``"Vsts"``).
            provider_data: Optional provider-specific configuration object
                (e.g. key vault config).

        Returns:
            VariableGroup wrapping the newly created variable group.
        """
        project_ref = VariableGroupProjectReference.model_validate(
            {
                "name": name,
                "projectReference": {
                    "id": str(self._project.id),
                    "name": self._project.name,
                },
            }
        )
        info = raw.post_variable_group(
            self._project.api_call,
            VariableGroupCreateRequest(
                name=name,
                variables=variables,
                variable_group_project_references=[project_ref],
                description=description,
                type=var_group_type,
                provider_data=provider_data,
            ),
        )
        vg_api_call = raw.get_variable_group_api_call(self._project.api_call, info.id)
        return VariableGroup(self._project, vg_api_call, info)

    def list_variable_groups(self) -> list[VariableGroup]:
        """Return all variable groups in the project as a list."""
        return list(self.iter_variable_groups())

    # ------------------------------------------------------------------
    # Secure files
    # ------------------------------------------------------------------

    def iter_secure_files(self) -> Iterator[SecureFile]:
        """Iterate over all secure files in the project.

        Yields:
            SecureFile for each secure file in the project.
        """
        for info in raw.iter_secure_files(self._project.api_call):
            sf_api_call = raw.get_secure_file_api_call(self._project.api_call, info.id)
            yield SecureFile(self._project, sf_api_call, info)

    def get_secure_file(self, name: str) -> SecureFile:
        """Return a secure file by name.

        Args:
            name: Secure file name (case-sensitive).

        Returns:
            SecureFile wrapping the requested secure file.

        Raises:
            KeyError: If no secure file with the given name exists.
        """
        for sf in self.iter_secure_files():
            if sf.name == name:
                return sf
        raise KeyError(name)

    def list_secure_files(self) -> list[SecureFile]:
        """Return all secure files in the project as a list."""
        return list(self.iter_secure_files())
