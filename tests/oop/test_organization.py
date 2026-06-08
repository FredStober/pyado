"""Tests for pyado.oop Organization — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest

from pyado.oop import AgentPool, OrganizationSearch, Project
from pyado.raw import AgentPoolInfo, GraphGroup, IdentityInfo, NotificationSubscription
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
