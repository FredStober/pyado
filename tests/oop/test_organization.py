"""Tests for pyado.oop Organization — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from pyado.oop import AgentPool, OrganizationSearch, Project
from pyado.raw import (
    AccessLevel,
    AgentPoolInfo,
    GraphGroup,
    GraphMembership,
    GraphUser,
    HookPublisherInfo,
    HookSubscriptionCreateRequest,
    HookSubscriptionInfo,
    HookSubscriptionUpdateRequest,
    IdentityInfo,
    NotificationSubscription,
    UserEntitlement,
    UserEntitlementCreateRequest,
)
from tests.oop.conftest import (
    ORG_NAME,
    _api_call,
    _make_graph_group,
    _make_identity_info,
    _make_service,
    _project_info,
)


class TestOrganization:
    def test_api_call_matches_service(self) -> None:
        svc = _make_service()
        assert svc.org.api_call is svc.api_call

    def test_get_project_fetches_and_caches(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_project") as mock_get,
        ):
            mock_get.return_value = _project_info("ICS")
            proj = svc.org.get_project("ICS")
        assert isinstance(proj, Project)
        assert proj.name == "ICS"

    def test_get_project_returns_same_instance(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_project") as mock_get:
            mock_get.return_value = _project_info("ICS")
            proj1 = svc.org.get_project("ICS")
            proj2 = svc.org.get_project("ICS")
        assert proj1 is proj2
        mock_get.assert_called_once()

    def test_iter_projects_yields_and_caches(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter(
                [_project_info("ICS"), _project_info("Other")]
            )
            projects = list(svc.org.iter_projects())
        assert len(projects) == 2
        assert projects[0].name == "ICS"

    def test_iter_projects_shares_identity_with_get_project(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter([_project_info("ICS")])
            (proj_from_iter,) = svc.org.iter_projects()
        # get_project should hit the cache and return the same object
        with patch("pyado.oop.organization.raw.get_project"):
            proj_from_get = svc.org.get_project("ICS")
        assert proj_from_iter is proj_from_get

    def test_get_my_profile_delegates(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_my_profile") as mock_profile:
            mock_profile.return_value = MagicMock()
            svc.org.get_my_profile()
        mock_profile.assert_called_once()
        # The api_call passed to get_my_profile should target app.vssps.visualstudio.com
        passed_api_call = mock_profile.call_args[0][0]
        assert "app.vssps.visualstudio.com" in str(passed_api_call.url)

    def test_get_connection_data_delegates(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_connection_data") as mock_get:
            mock_get.return_value = MagicMock()
            result = svc.org.get_connection_data()
        mock_get.assert_called_once()
        assert result is mock_get.return_value


class TestOrganizationIdentity:
    def test_get_identities_delegates(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_identities") as mock_ids:
            mock_ids.return_value = [_make_identity_info()]
            result = svc.org.get_identities(["vssgp.abc"])
        assert len(result) == 1
        assert isinstance(result[0], IdentityInfo)
        mock_ids.assert_called_once()

    def test_get_identities_uses_vssps_url(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_identities") as mock_ids:
            mock_ids.return_value = []
            svc.org.get_identities([])
        passed_api_call = mock_ids.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)

    def test_iter_graph_groups_delegates(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter:
            mock_iter.return_value = iter([_make_graph_group()])
            result = list(svc.org.iter_graph_groups())
        assert len(result) == 1
        assert isinstance(result[0], GraphGroup)

    def test_iter_graph_groups_uses_vssps_url(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter:
            mock_iter.return_value = iter([])
            list(svc.org.iter_graph_groups())
        passed_api_call = mock_iter.call_args[0][0]
        assert "vssps.dev.azure.com/testorg" in str(passed_api_call.url)


class TestOrganizationListMethods:
    def test_list_projects_delegates(self) -> None:
        org = _make_service().org
        with patch.object(org, "iter_projects", return_value=iter([])):
            assert org.list_projects() == []

    def test_list_graph_groups_delegates(self) -> None:
        org = _make_service().org
        with patch.object(org, "iter_graph_groups", return_value=iter([])):
            assert org.list_graph_groups() == []


class TestOrganizationAgentPools:
    def test_get_agent_pool_returns_matching_pool(self) -> None:
        svc = _make_service()
        pool_info = AgentPoolInfo.model_validate(
            {"id": 1, "name": "Default", "isHosted": False}
        )
        with (
            patch("pyado.oop.organization.raw.iter_agent_pools") as mock_iter,
            patch("pyado.oop.organization.raw.get_agent_pool_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([pool_info])
            mock_ac.return_value = _api_call()
            result = svc.org.get_agent_pool("Default")
        assert isinstance(result, AgentPool)
        assert result.name == "Default"

    def test_get_agent_pool_raises_key_error_when_not_found(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.iter_agent_pools") as mock_iter,
            patch("pyado.oop.organization.raw.get_agent_pool_api_call") as mock_ac,
        ):
            pool_info = AgentPoolInfo.model_validate(
                {"id": 1, "name": "Other", "isHosted": False}
            )
            mock_iter.return_value = iter([pool_info])
            mock_ac.return_value = _api_call()
            with pytest.raises(KeyError):
                svc.org.get_agent_pool("Missing")

    def test_list_agent_pools_returns_list(self) -> None:
        svc = _make_service()
        with patch.object(svc.org, "iter_agent_pools", return_value=iter([])):
            assert svc.org.list_agent_pools() == []

    def test_search_property_returns_organization_search(self) -> None:
        svc = _make_service()
        assert isinstance(svc.org.search, OrganizationSearch)

    def test_search_is_identity_stable(self) -> None:
        svc = _make_service()
        assert svc.org.search is svc.org.search


class TestOrganizationNotificationSubscriptions:
    def test_iter_notification_subscriptions_yields_subscriptions(self) -> None:
        svc = _make_service()
        sub = NotificationSubscription.model_validate(
            {"id": "sub-001", "description": "Build complete"}
        )
        with patch(
            "pyado.oop.organization.raw.iter_notification_subscriptions"
        ) as mock_iter:
            mock_iter.return_value = iter([sub])
            result = list(svc.org.iter_notification_subscriptions())
        assert len(result) == 1
        assert isinstance(result[0], NotificationSubscription)
        assert result[0].id == "sub-001"

    def test_iter_notification_subscriptions_empty(self) -> None:
        svc = _make_service()
        with patch(
            "pyado.oop.organization.raw.iter_notification_subscriptions"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(svc.org.iter_notification_subscriptions())
        assert result == []

    def test_list_notification_subscriptions_delegates(self) -> None:
        svc = _make_service()
        with patch.object(
            svc.org,
            "iter_notification_subscriptions",
            return_value=iter([]),
        ):
            assert svc.org.list_notification_subscriptions() == []


# ---------------------------------------------------------------------------
# Helpers for hook / identity tests
# ---------------------------------------------------------------------------


def _hook_subscription_info(
    subscription_id: UUID | None = None,
) -> HookSubscriptionInfo:
    return HookSubscriptionInfo.model_validate(
        {
            "id": str(subscription_id or uuid4()),
            "publisherId": "tfs",
            "eventType": "build.complete",
            "consumerId": "webHooks",
            "consumerActionId": "httpRequest",
        }
    )


def _hook_publisher_info(publisher_id: str = "tfs") -> HookPublisherInfo:
    return HookPublisherInfo.model_validate(
        {"id": publisher_id, "name": "Azure DevOps"}
    )


def _graph_user(descriptor: str = "vssgp.abc") -> GraphUser:
    return GraphUser.model_validate(
        {
            "descriptor": descriptor,
            "displayName": "Test User",
            "subjectKind": "user",
            "principalName": "user@example.com",
        }
    )


def _user_entitlement(user_uuid: UUID | None = None) -> UserEntitlement:
    return UserEntitlement.model_validate(
        {
            "id": str(user_uuid or uuid4()),
            "user": {
                "descriptor": "vssgp.abc",
                "displayName": "Test User",
                "subjectKind": "user",
            },
        }
    )


def _access_level() -> AccessLevel:
    return AccessLevel.model_validate({"accountLicenseType": "express"})


def _graph_membership() -> GraphMembership:
    return GraphMembership.model_validate(
        {"containerDescriptor": "vssgp.container", "memberDescriptor": "vssgp.member"}
    )


# ---------------------------------------------------------------------------
# Hook subscriptions
# ---------------------------------------------------------------------------


class TestOrganizationHookSubscriptions:
    def test_iter_hook_subscriptions_yields_items(self) -> None:
        svc = _make_service()
        sub = _hook_subscription_info()
        with patch("pyado.oop.organization.raw.iter_hook_subscriptions") as mock_iter:
            mock_iter.return_value = iter([sub])
            result = list(svc.org.iter_hook_subscriptions())
        assert len(result) == 1
        assert isinstance(result[0], HookSubscriptionInfo)

    def test_iter_hook_subscriptions_empty(self) -> None:
        svc = _make_service()
        with patch(
            "pyado.oop.organization.raw.iter_hook_subscriptions",
            return_value=iter([]),
        ):
            assert list(svc.org.iter_hook_subscriptions()) == []

    def test_list_hook_subscriptions_delegates(self) -> None:
        svc = _make_service()
        with patch.object(svc.org, "iter_hook_subscriptions", return_value=iter([])):
            assert svc.org.list_hook_subscriptions() == []

    def test_get_hook_subscription_returns_info(self) -> None:
        svc = _make_service()
        sub = _hook_subscription_info()
        with patch(
            "pyado.oop.organization.raw.get_hook_subscription",
            return_value=sub,
        ) as mock_get:
            result = svc.org.get_hook_subscription(sub.id)
        mock_get.assert_called_once_with(svc.org.api_call, sub.id)
        assert result is sub

    def test_create_hook_subscription_returns_info(self) -> None:
        svc = _make_service()
        created = _hook_subscription_info()
        request = HookSubscriptionCreateRequest(
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
        )
        with patch(
            "pyado.oop.organization.raw.post_hook_subscription",
            return_value=created,
        ) as mock_post:
            result = svc.org.create_hook_subscription(request)
        mock_post.assert_called_once_with(svc.org.api_call, request)
        assert result is created

    def test_update_hook_subscription_returns_info(self) -> None:
        svc = _make_service()
        sub = _hook_subscription_info()
        updated = _hook_subscription_info(sub.id)
        request = HookSubscriptionUpdateRequest(
            id=sub.id,
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
        )
        with patch(
            "pyado.oop.organization.raw.put_hook_subscription",
            return_value=updated,
        ) as mock_patch:
            result = svc.org.update_hook_subscription(sub.id, request)
        mock_patch.assert_called_once_with(svc.org.api_call, sub.id, request)
        assert result is updated

    def test_delete_hook_subscription_calls_raw(self) -> None:
        svc = _make_service()
        sub = _hook_subscription_info()
        with patch("pyado.oop.organization.raw.delete_hook_subscription") as mock_del:
            svc.org.delete_hook_subscription(sub.id)
        mock_del.assert_called_once_with(svc.org.api_call, sub.id)

    def test_iter_hook_publishers_yields_items(self) -> None:
        svc = _make_service()
        pub = _hook_publisher_info()
        with patch("pyado.oop.organization.raw.iter_hook_publishers") as mock_iter:
            mock_iter.return_value = iter([pub])
            result = list(svc.org.iter_hook_publishers())
        assert len(result) == 1
        assert isinstance(result[0], HookPublisherInfo)

    def test_iter_hook_publishers_empty(self) -> None:
        svc = _make_service()
        with patch(
            "pyado.oop.organization.raw.iter_hook_publishers",
            return_value=iter([]),
        ):
            assert list(svc.org.iter_hook_publishers()) == []

    def test_list_hook_publishers_delegates(self) -> None:
        svc = _make_service()
        with patch.object(svc.org, "iter_hook_publishers", return_value=iter([])):
            assert svc.org.list_hook_publishers() == []


# ---------------------------------------------------------------------------
# Graph users
# ---------------------------------------------------------------------------


class TestOrganizationGraphUsers:
    def test_iter_graph_users_yields_items(self) -> None:
        svc = _make_service()
        user = _graph_user()
        with patch("pyado.oop.organization.raw.iter_graph_users") as mock_iter:
            mock_iter.return_value = iter([user])
            result = list(svc.org.iter_graph_users())
        assert len(result) == 1
        assert isinstance(result[0], GraphUser)

    def test_iter_graph_users_uses_vssps_url(self) -> None:
        svc = _make_service()
        with patch(
            "pyado.oop.organization.raw.iter_graph_users",
            return_value=iter([]),
        ) as mock_iter:
            list(svc.org.iter_graph_users())
        passed_api_call = mock_iter.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)

    def test_list_graph_users_delegates(self) -> None:
        svc = _make_service()
        with patch.object(svc.org, "iter_graph_users", return_value=iter([])):
            assert svc.org.list_graph_users() == []

    def test_get_graph_user_returns_user(self) -> None:
        svc = _make_service()
        user = _graph_user("vssgp.xyz")
        with patch(
            "pyado.oop.organization.raw.get_graph_user",
            return_value=user,
        ) as mock_get:
            result = svc.org.get_graph_user("vssgp.xyz")
        mock_get.assert_called_once()
        assert result is user

    def test_get_graph_user_uses_vssps_url(self) -> None:
        svc = _make_service()
        user = _graph_user()
        with patch(
            "pyado.oop.organization.raw.get_graph_user",
            return_value=user,
        ) as mock_get:
            svc.org.get_graph_user("vssgp.xyz")
        passed_api_call = mock_get.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)


# ---------------------------------------------------------------------------
# User entitlements
# ---------------------------------------------------------------------------


class TestOrganizationUserEntitlements:
    def test_iter_user_entitlements_yields_items(self) -> None:
        svc = _make_service()
        ent = _user_entitlement()
        with patch("pyado.oop.organization.raw.iter_user_entitlements") as mock_iter:
            mock_iter.return_value = iter([ent])
            result = list(svc.org.iter_user_entitlements())
        assert len(result) == 1
        assert isinstance(result[0], UserEntitlement)

    def test_iter_user_entitlements_uses_vssps_url(self) -> None:
        svc = _make_service()
        with patch(
            "pyado.oop.organization.raw.iter_user_entitlements",
            return_value=iter([]),
        ) as mock_iter:
            list(svc.org.iter_user_entitlements())
        passed_api_call = mock_iter.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)

    def test_list_user_entitlements_delegates(self) -> None:
        svc = _make_service()
        with patch.object(svc.org, "iter_user_entitlements", return_value=iter([])):
            assert svc.org.list_user_entitlements() == []

    def test_add_user_entitlement_returns_entitlement(self) -> None:
        svc = _make_service()
        created = _user_entitlement()
        request = UserEntitlementCreateRequest(
            user=_graph_user(),
            access_level=_access_level(),
        )
        with patch(
            "pyado.oop.organization.raw.add_user_entitlement",
            return_value=created,
        ) as mock_add:
            result = svc.org.add_user_entitlement(request)
        mock_add.assert_called_once()
        assert result is created

    def test_update_user_access_level_returns_entitlement(self) -> None:
        svc = _make_service()
        user_id = uuid4()
        updated = _user_entitlement(user_id)
        level = _access_level()
        with patch(
            "pyado.oop.organization.raw.update_user_access_level",
            return_value=updated,
        ) as mock_update:
            result = svc.org.update_user_access_level(user_id, level)
        mock_update.assert_called_once()
        assert result is updated


# ---------------------------------------------------------------------------
# Graph memberships
# ---------------------------------------------------------------------------


class TestOrganizationGraphMemberships:
    def test_add_graph_membership_returns_membership(self) -> None:
        svc = _make_service()
        membership = _graph_membership()
        with patch(
            "pyado.oop.organization.raw.add_graph_membership",
            return_value=membership,
        ) as mock_add:
            result = svc.org.add_graph_membership("vssgp.member", "vssgp.container")
        mock_add.assert_called_once()
        assert result is membership

    def test_add_graph_membership_uses_vssps_url(self) -> None:
        svc = _make_service()
        membership = _graph_membership()
        with patch(
            "pyado.oop.organization.raw.add_graph_membership",
            return_value=membership,
        ) as mock_add:
            svc.org.add_graph_membership("vssgp.member", "vssgp.container")
        passed_api_call = mock_add.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)

    def test_remove_graph_membership_calls_raw(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.remove_graph_membership") as mock_remove:
            svc.org.remove_graph_membership("vssgp.member", "vssgp.container")
        mock_remove.assert_called_once()

    def test_remove_graph_membership_uses_vssps_url(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.remove_graph_membership") as mock_remove:
            svc.org.remove_graph_membership("vssgp.member", "vssgp.container")
        passed_api_call = mock_remove.call_args[0][0]
        assert f"vssps.dev.azure.com/{ORG_NAME}" in str(passed_api_call.url)
