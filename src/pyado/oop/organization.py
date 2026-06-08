"""OOP wrapper for the Azure DevOps organisation scope."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast

from pyado import raw
from pyado.oop.core.search import OrganizationSearch
from pyado.oop.pipelines.agent import AgentPool
from pyado.oop.project import Project
from pyado.raw import (
    ApiCall,
    ConnectionData,
    GraphGroup,
    IdentityInfo,
    NotificationSubscription,
    UserProfile,
)

if TYPE_CHECKING:
    from pyado.oop.service import AzureDevOpsService

__all__ = ["Organization"]


class Organization:
    """The Azure DevOps organisation scope.

    **ADO concept:** an ADO organisation (also called a *collection* in older
    docs) is the top-level tenant at ``https://dev.azure.com/{org}``.
    It owns projects, agent pools (org-scoped), user profiles, and graph
    groups.  All other resources are nested under a project, which is itself
    nested here.

    **Why it exists:** the ADO API distinguishes between org-scoped endpoints
    (pools, profile, connection data, graph groups) and project-scoped
    endpoints (builds, repos, pipelines, …).  ``Organization`` is the natural
    home for org-scoped operations and acts as the factory for
    :class:`~pyado.oop.project.Project` objects so the service cache is
    populated consistently.

    Obtained via :attr:`AzureDevOpsService.org`. Acts as the factory for
    :class:`~pyado.oop.project.Project` objects and caches them through the
    owning service so that repeated calls return the same instance.

    Attributes:
        _service: The AzureDevOpsService that owns this Organisation.
    """

    def __init__(self, service: "AzureDevOpsService") -> None:
        """Construct an Organisation view.

        Args:
            service: The AzureDevOpsService that owns this Organisation.
        """
        self._service = service

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def api_call(self) -> ApiCall:
        """Organisation-level API call for direct use with pyado.raw functions."""
        return self._service.api_call

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_project(self, name: str) -> Project:
        """Return a wrapper for a project by name, fetching details from the API.

        The project is cached in the service — subsequent calls with the same
        name return the same :class:`~pyado.oop.project.Project` instance.

        Args:
            name: Project name (case-sensitive, as it appears in ADO).

        Returns:
            Project wrapping the requested project.
        """
        api_call = self._service.oop_api.make_project_api_call(name)
        cache_key = str(api_call.url)

        def factory() -> Project:
            info = raw.get_project(self._service.api_call, name)
            return Project(self._service, info.name, info)

        return self._service.oop_api.get_or_cache(cache_key, factory)

    def iter_projects(self) -> Iterator[Project]:
        """Iterate over all projects in the organisation.

        Each yielded project is cached in the service so that repeated access
        returns the same instance.

        Yields:
            Project for each ADO project in the organisation.
        """
        for info in raw.iter_projects(self._service.api_call):
            api_call = self._service.oop_api.make_project_api_call(info.name)
            cache_key = str(api_call.url)
            proj: Project = self._service.oop_api.get_or_cache(
                cache_key,
                cast(
                    "Callable[[], Project]",
                    lambda i=info: Project(self._service, i.name, i),
                ),
            )
            yield proj

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_connection_data(self) -> ConnectionData:
        """Return connection metadata for this organisation.

        Includes the authenticated user identity, deployment type, and
        instance ID.  Useful to confirm authentication and discover
        organisation-level metadata without querying a specific project.

        Returns:
            ConnectionData for the organisation.
        """
        return raw.get_connection_data(self._service.oop_api.org_base_api_call)

    def get_my_profile(self) -> UserProfile:
        """Return the profile of the currently authenticated user.

        Returns:
            UserProfile for the authenticated user.
        """
        return raw.get_my_profile(self._service.oop_api.profile_api_call)

    # ------------------------------------------------------------------
    # Identity / graph
    # ------------------------------------------------------------------

    def get_identities(self, descriptors: list[str]) -> list[IdentityInfo]:
        """Return identity info for a list of subject descriptors.

        Args:
            descriptors: List of subject descriptor strings to look up.

        Returns:
            List of IdentityInfo objects, one per resolved descriptor.
        """
        return raw.get_identities(self._service.oop_api.vssps_api_call, descriptors)

    def iter_graph_groups(self) -> Iterator[GraphGroup]:
        """Iterate over all graph groups in the organisation.

        Yields:
            GraphGroup for each group in the organisation.
        """
        yield from raw.iter_graph_groups(self._service.oop_api.vssps_api_call)

    def list_projects(self) -> list[Project]:
        """Return all projects in this organisation as a list."""
        return list(self.iter_projects())

    def list_graph_groups(self) -> list[GraphGroup]:
        """Return all graph groups in this organisation as a list."""
        return list(self.iter_graph_groups())

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @property
    def search(self) -> OrganizationSearch:
        """Org-wide search (code, work items, wiki, packages)."""
        return OrganizationSearch(self._service)

    # ------------------------------------------------------------------
    # Agent pools
    # ------------------------------------------------------------------

    def iter_agent_pools(self) -> Iterator[AgentPool]:
        """Iterate over all agent pools in the organisation.

        Yields:
            AgentPool for each agent pool.
        """
        for info in raw.iter_agent_pools(self._service.api_call):
            pool_api_call = raw.get_agent_pool_api_call(self._service.api_call, info.id)
            yield AgentPool(self, pool_api_call, info)

    def get_agent_pool(self, name: str) -> AgentPool:
        """Return an agent pool by name.

        Args:
            name: Agent pool name (case-sensitive).

        Returns:
            AgentPool wrapping the requested pool.

        Raises:
            KeyError: If no agent pool with the given name exists.
        """
        for pool in self.iter_agent_pools():
            if pool.name == name:
                return pool
        raise KeyError(name)

    def list_agent_pools(self) -> list[AgentPool]:
        """Return all agent pools in the organisation as a list."""
        return list(self.iter_agent_pools())

    # ------------------------------------------------------------------
    # Notification subscriptions
    # ------------------------------------------------------------------

    def iter_notification_subscriptions(
        self,
    ) -> Iterator[NotificationSubscription]:
        """Iterate over all notification subscriptions in this organisation.

        Yields:
            NotificationSubscription for each subscription.
        """
        yield from raw.iter_notification_subscriptions(self.api_call)

    def list_notification_subscriptions(self) -> list[NotificationSubscription]:
        """Return all notification subscriptions as a list."""
        return list(self.iter_notification_subscriptions())
