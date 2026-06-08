"""OOP wrapper for Azure DevOps pipeline environment resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ApiCall,
    EnvironmentCheckInfo,
    EnvironmentDeploymentRecord,
    EnvironmentId,
    EnvironmentInfo,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Environment"]


class Environment:
    """An Azure DevOps pipeline environment.

    **ADO concept:** a *pipeline environment* is a named deployment target
    (e.g. ``"production"``, ``"staging"``) managed at
    ``distributedtask/environments/{id}``.  Environments support approval
    gates, deployment history, and resource targets (Kubernetes, virtual
    machines).

    **Why it exists:** bundles the environment ID and info together so callers
    can inspect properties and iterate deployment history without managing
    raw API calls.

    Instances are obtained from :meth:`ProjectPipelines.iter_environments` or
    :meth:`ProjectPipelines.get_environment`.

    Attributes:
        _project: The Project this environment belongs to.
        _api_call: Environment-level ADO API call.
        _info: Cached environment data.
    """

    def __init__(
        self,
        project: "Project",
        env_api_call: ApiCall,
        info: EnvironmentInfo,
    ) -> None:
        """Construct an Environment wrapper.

        Args:
            project: The Project that owns this environment.
            env_api_call: Environment-level ADO API call (from
                raw.get_environment_api_call).
            info: Environment data as returned from the API.
        """
        self._project = project
        self._api_call = env_api_call
        self._env_id = info.id
        self._info: EnvironmentInfo | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> EnvironmentInfo:
        """Environment data captured at construction time."""
        if self._info is None:
            self._info = raw.get_environment(self._project.api_call, self._env_id)
        return self._info

    @property
    def id(self) -> EnvironmentId:
        """Numeric environment ID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Environment name (e.g. ``"production"``)."""
        return self.info.name

    @property
    def description(self) -> str:
        """Environment description."""
        return self.info.description

    @property
    def api_call(self) -> ApiCall:
        """Environment-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this environment belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this environment belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached environment info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def iter_checks(self) -> Iterator[EnvironmentCheckInfo]:
        """Iterate over all check configurations for this environment.

        Yields:
            EnvironmentCheckInfo for each check configuration.
        """
        yield from raw.iter_environment_checks(self._project.api_call, self._env_id)

    def list_checks(self) -> list[EnvironmentCheckInfo]:
        """Return all check configurations for this environment as a list."""
        return list(self.iter_checks())

    # ------------------------------------------------------------------
    # Deployment records
    # ------------------------------------------------------------------

    def iter_deployments(
        self,
        *,
        top: int | None = None,
    ) -> Iterator[EnvironmentDeploymentRecord]:
        """Iterate over deployment records for this environment.

        Args:
            top: Maximum number of records to return.  When ``None``, the
                API default is used.

        Yields:
            EnvironmentDeploymentRecord for each deployment.
        """
        yield from raw.iter_environment_deployments(self._api_call, top=top)

    def list_deployments(
        self,
        *,
        top: int | None = None,
    ) -> list[EnvironmentDeploymentRecord]:
        """Return deployment records for this environment as a list."""
        return list(self.iter_deployments(top=top))
