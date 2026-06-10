"""OOP wrapper for the Azure DevOps organisation scope."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast
from uuid import UUID

from pyado import raw
from pyado.oop.core.process import Process
from pyado.oop.core.search import OrganizationSearch
from pyado.oop.pipelines.agent import AgentPool
from pyado.oop.project import Project
from pyado.raw import (
    AccessLevel,
    ApiCall,
    ConnectionData,
    GraphGroup,
    GraphMembership,
    GraphUser,
    HookPublisherInfo,
    HookSubscriptionCreateRequest,
    HookSubscriptionId,
    HookSubscriptionInfo,
    HookSubscriptionUpdateRequest,
    IdentityInfo,
    NotificationSubscription,
    ProcessCreateRequest,
    ProcessDetail,
    ProcessId,
    UserEntitlement,
    UserEntitlementCreateRequest,
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
        self._search: OrganizationSearch | None = None

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
        if self._search is None:
            self._search = OrganizationSearch(self._service)
        return self._search

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

    # ------------------------------------------------------------------
    # Hook subscriptions
    # ------------------------------------------------------------------

    def iter_hook_subscriptions(self) -> Iterator[HookSubscriptionInfo]:
        """Iterate over all service-hooks subscriptions in this organisation.

        Yields:
            HookSubscriptionInfo for each subscription.
        """
        yield from raw.iter_hook_subscriptions(self.api_call)

    def list_hook_subscriptions(self) -> list[HookSubscriptionInfo]:
        """Return all service-hooks subscriptions as a list."""
        return list(self.iter_hook_subscriptions())

    def get_hook_subscription(
        self, subscription_id: HookSubscriptionId
    ) -> HookSubscriptionInfo:
        """Fetch a single service-hooks subscription by ID.

        Args:
            subscription_id: UUID of the subscription.

        Returns:
            HookSubscriptionInfo for the requested subscription.
        """
        return raw.get_hook_subscription(self.api_call, subscription_id)

    def create_hook_subscription(
        self, request: HookSubscriptionCreateRequest
    ) -> HookSubscriptionInfo:
        """Create a new service-hooks subscription.

        Args:
            request: Create request specifying the publisher, event type,
                consumer, and consumer action.

        Returns:
            HookSubscriptionInfo for the newly created subscription.
        """
        return raw.post_hook_subscription(self.api_call, request)

    def update_hook_subscription(
        self,
        subscription_id: HookSubscriptionId,
        request: HookSubscriptionUpdateRequest,
    ) -> HookSubscriptionInfo:
        """Update an existing service-hooks subscription.

        Args:
            subscription_id: UUID of the subscription to update.
            request: Update request.

        Returns:
            Updated HookSubscriptionInfo.
        """
        return raw.put_hook_subscription(self.api_call, subscription_id, request)

    def delete_hook_subscription(self, subscription_id: HookSubscriptionId) -> None:
        """Delete a service-hooks subscription.

        Args:
            subscription_id: UUID of the subscription to delete.
        """
        raw.delete_hook_subscription(self.api_call, subscription_id)

    def iter_hook_publishers(self) -> Iterator[HookPublisherInfo]:
        """Iterate over all service-hooks publishers in this organisation.

        Yields:
            HookPublisherInfo for each publisher.
        """
        yield from raw.iter_hook_publishers(self.api_call)

    def list_hook_publishers(self) -> list[HookPublisherInfo]:
        """Return all service-hooks publishers as a list."""
        return list(self.iter_hook_publishers())

    # ------------------------------------------------------------------
    # Graph users
    # ------------------------------------------------------------------

    def iter_graph_users(self) -> Iterator[GraphUser]:
        """Iterate over all graph users in this organisation.

        Yields:
            GraphUser for each user in the organisation.
        """
        yield from raw.iter_graph_users(self._service.oop_api.vssps_api_call)

    def list_graph_users(self) -> list[GraphUser]:
        """Return all graph users in this organisation as a list."""
        return list(self.iter_graph_users())

    def get_graph_user(self, descriptor: str) -> GraphUser:
        """Return a single graph user by subject descriptor.

        Args:
            descriptor: Subject descriptor of the user to retrieve.

        Returns:
            GraphUser for the requested descriptor.
        """
        return raw.get_graph_user(self._service.oop_api.vssps_api_call, descriptor)

    # ------------------------------------------------------------------
    # User entitlements
    # ------------------------------------------------------------------

    def iter_user_entitlements(self) -> Iterator[UserEntitlement]:
        """Iterate over all user entitlements in this organisation.

        Yields:
            UserEntitlement for each user in the organisation.
        """
        yield from raw.iter_user_entitlements(self._service.oop_api.vssps_api_call)

    def list_user_entitlements(self) -> list[UserEntitlement]:
        """Return all user entitlements as a list."""
        return list(self.iter_user_entitlements())

    def add_user_entitlement(
        self, request: UserEntitlementCreateRequest
    ) -> UserEntitlement:
        """Add a user to the organisation with an access level.

        Args:
            request: Create request specifying the user and desired
                access level.

        Returns:
            UserEntitlement for the newly added user.
        """
        return raw.add_user_entitlement(self._service.oop_api.vssps_api_call, request)

    def update_user_access_level(
        self, user_id: UUID, access_level: AccessLevel
    ) -> UserEntitlement:
        """Update the access level for an existing user entitlement.

        Args:
            user_id: UUID of the user whose access level should be updated.
            access_level: New access level to apply.

        Returns:
            Updated UserEntitlement.
        """
        return raw.update_user_access_level(
            self._service.oop_api.vssps_api_call, user_id, access_level
        )

    # ------------------------------------------------------------------
    # Graph memberships
    # ------------------------------------------------------------------

    def add_graph_membership(
        self, subject_descriptor: str, container_descriptor: str
    ) -> GraphMembership:
        """Add a user (or group) to a group.

        Args:
            subject_descriptor: Descriptor of the member to add.
            container_descriptor: Descriptor of the group to add the
                member to.

        Returns:
            GraphMembership describing the new membership link.
        """
        return raw.add_graph_membership(
            self._service.oop_api.vssps_api_call,
            subject_descriptor,
            container_descriptor,
        )

    def remove_graph_membership(
        self, subject_descriptor: str, container_descriptor: str
    ) -> None:
        """Remove a user (or group) from a group.

        Args:
            subject_descriptor: Descriptor of the member to remove.
            container_descriptor: Descriptor of the group to remove the
                member from.
        """
        raw.remove_graph_membership(
            self._service.oop_api.vssps_api_call,
            subject_descriptor,
            container_descriptor,
        )

    # ------------------------------------------------------------------
    # Work process templates
    # ------------------------------------------------------------------

    def iter_processes(self) -> Iterator[Process]:
        """Iterate over all work process templates in this organisation.

        Yields:
            Process for each process template.
        """
        for info in raw.iter_processes(self._service.api_call):
            yield Process(self, info)

    def list_processes(self) -> list[Process]:
        """Return all work process templates as a list."""
        return list(self.iter_processes())

    def get_process(self, process_id: ProcessId) -> Process:
        """Return a process template by UUID.

        Args:
            process_id: UUID of the process template.

        Returns:
            Process wrapping the requested process.
        """
        info = raw.get_process(self._service.api_call, process_id)
        return Process(self, info)

    def create_process(self, request: ProcessCreateRequest) -> Process:
        """Create a new inherited process template.

        Args:
            request: Create request specifying name and parent process.

        Returns:
            Process wrapping the newly created process.
        """
        info: ProcessDetail = raw.post_process(self._service.api_call, request)
        return Process(self, info)
