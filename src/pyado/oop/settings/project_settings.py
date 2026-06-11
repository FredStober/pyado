"""OOP wrapper for Azure DevOps project settings."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING
from uuid import UUID

from pyado import raw
from pyado.oop.repos.policy import PolicyConfiguration
from pyado.raw import (
    PolicyConfigurationId,
    PolicyConfigurationRequest,
    PolicyType,
    ProcessDetail,
    ProjectInfo,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project

__all__ = ["ProjectSettings"]


class ProjectSettings:
    """The Settings section of a project.

    Accessed via ``project.settings``.  Exposes project-level configuration,
    branch policies, process template information, and metadata operations.

    Attributes:
        _project: The owning Project.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a ProjectSettings section.

        Args:
            project: The Project this section belongs to.
        """
        self._project = project

    def get_project_info(self) -> ProjectInfo:
        """Return the raw project information record.

        Returns:
            ProjectInfo for this project.
        """
        return raw.get_project(self._project.org.api_call, self._project.name)

    # ------------------------------------------------------------------
    # Branch policies
    # ------------------------------------------------------------------

    def iter_policy_configurations(self) -> Iterator[PolicyConfiguration]:
        """Iterate over all branch policy configurations in this project.

        Yields:
            PolicyConfiguration for each configured policy.
        """
        for info in raw.iter_policy_configurations(self._project.api_call):
            yield PolicyConfiguration(self._project, info)

    def list_policy_configurations(self) -> list[PolicyConfiguration]:
        """Return all branch policy configurations as a list."""
        return list(self.iter_policy_configurations())

    def get_policy_configuration(
        self, config_id: PolicyConfigurationId
    ) -> PolicyConfiguration:
        """Return a specific branch policy configuration by numeric ID.

        Args:
            config_id: PolicyConfigurationId of the policy configuration.

        Returns:
            PolicyConfiguration wrapping the requested configuration.
        """
        api = raw.get_policy_configuration_api_call(self._project.api_call, config_id)
        info = raw.get_policy_configuration(api)
        return PolicyConfiguration(self._project, info)

    def create_policy_configuration(
        self, request: PolicyConfigurationRequest
    ) -> PolicyConfiguration:
        """Create a new branch policy configuration in this project.

        Args:
            request: Request specifying the type, settings, and blocking flag.

        Returns:
            PolicyConfiguration wrapping the newly created configuration.
        """
        info = raw.post_policy_configuration(self._project.api_call, request)
        return PolicyConfiguration(self._project, info)

    def iter_policy_types(self) -> Iterator[PolicyType]:
        """Iterate over all available policy types in this project.

        Yields:
            PolicyType for each available policy type.
        """
        yield from raw.iter_policy_types(self._project.api_call)

    def list_policy_types(self) -> list[PolicyType]:
        """Return all available policy types in this project as a list."""
        return raw.list_policy_types(self._project.api_call)

    def get_policy_type(self, type_id: UUID) -> PolicyType:
        """Return a specific policy type by UUID.

        Args:
            type_id: UUID of the policy type.

        Returns:
            The matching PolicyType.
        """
        return raw.get_policy_type(self._project.api_call, type_id)

    # ------------------------------------------------------------------
    # Process template
    # ------------------------------------------------------------------

    def get_process_info(self) -> ProcessDetail:
        """Return the process template for this project.

        Fetches the project with capabilities to discover the template
        type ID, then collects all process sub-resources.

        Returns:
            ProcessDetail with all sub-resources populated.

        Raises:
            ValueError: If the project capabilities are not available.
        """
        info = raw.get_project(
            self._project.org.api_call,
            self._project.name,
            include_capabilities=True,
        )
        if info.capabilities is None:
            msg = (
                "Process template not available — project capabilities "
                "could not be fetched"
            )
            raise ValueError(msg)
        template_type_id = UUID(info.capabilities.process_template.template_type_id)
        return raw.get_process_info(
            self._project.org.api_call,
            self._project.api_call,
            template_type_id,
        )
