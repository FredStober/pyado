"""OOP wrapper for Azure DevOps branch policy configuration resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import ApiCall

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["PolicyConfiguration"]


class PolicyConfiguration:
    """An ADO branch policy configuration.

    Also exported from ``pyado`` directly as ``pyado.PolicyConfiguration``.
    The underlying raw Pydantic model is ``pyado.PolicyConfigurationInfo``.

    Wraps a single branch policy configuration and exposes read,
    update, and delete operations.  Instances are obtained from
    :meth:`ProjectSettings.iter_policy_configurations` or
    :meth:`ProjectSettings.get_policy_configuration`.

    Attributes:
        _project: The Project this policy configuration belongs to.
        _id: Numeric configuration ID (always known).
        _info: Cached policy configuration data; ``None`` after
            :meth:`refresh`.
    """

    def __init__(self, project: "Project", info: raw.PolicyConfigurationInfo) -> None:
        """Construct a PolicyConfiguration wrapper.

        Args:
            project: The Project this configuration belongs to.
            info: raw.PolicyConfigurationInfo returned by the ADO policy endpoint.
        """
        self._project = project
        self._id = info.id
        self._info: raw.PolicyConfigurationInfo | None = info

    @property
    def id(self) -> int:
        """Numeric policy configuration ID — always known, no API call."""
        return self._id

    @property
    def type(self) -> raw.PolicyType:
        """Policy type definition."""
        return self.info.type

    @property
    def is_enabled(self) -> bool:
        """Whether this policy configuration is enabled."""
        return self.info.is_enabled

    @property
    def is_blocking(self) -> bool:
        """Whether this policy blocks completion when violated."""
        return self.info.is_blocking

    @property
    def revision(self) -> int | None:
        """Policy configuration revision number."""
        return self.info.revision

    @property
    def created_by(self) -> raw.PolicyCreatedBy | None:
        """Identity reference of the creator."""
        return self.info.created_by

    @property
    def info(self) -> raw.PolicyConfigurationInfo:
        """Full policy configuration data as returned by the API.

        Fetched lazily from the API if :meth:`refresh` was called since
        the last access.
        """
        if self._info is None:
            self._info = raw.get_policy_configuration(self.api_call)
        return self._info

    @property
    def api_call(self) -> ApiCall:
        """Policy-configuration-level API call for use with raw functions."""
        return raw.get_policy_configuration_api_call(self._project.api_call, self._id)

    @property
    def project(self) -> "Project":
        """Project this configuration belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this configuration belongs to — zero-cost."""
        return self._project.org

    def refresh(self) -> None:
        """Discard cached policy configuration info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    def update(self, request: raw.PolicyConfigurationRequest) -> None:
        """Update this policy configuration with new settings.

        Args:
            request: Updated settings for the policy configuration.
        """
        self._info = raw.update_policy_configuration(self.api_call, request)

    def delete(self) -> None:
        """Delete this policy configuration from the project."""
        raw.delete_policy_configuration(self.api_call)
