"""Tests for pyado.oop Organization — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

from pyado.oop import Project
from pyado.raw import GraphGroup, IdentityInfo
from tests.oop.conftest import (
    ORG_NAME,
    TOKEN,
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
        with (
            patch("pyado.oop.organization.raw.get_profile_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_my_profile") as mock_profile,
        ):
            mock_call.return_value = _api_call()
            mock_profile.return_value = MagicMock()
            svc.org.get_my_profile()
        mock_call.assert_called_once_with(TOKEN)
        mock_profile.assert_called_once()

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
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_identities") as mock_ids,
        ):
            mock_call.return_value = _api_call()
            mock_ids.return_value = [_make_identity_info()]
            result = svc.org.get_identities(["vssgp.abc"])
        assert len(result) == 1
        assert isinstance(result[0], IdentityInfo)
        mock_ids.assert_called_once()

    def test_get_identities_uses_org_name_from_url(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_identities") as mock_ids,
        ):
            mock_call.return_value = _api_call()
            mock_ids.return_value = []
            svc.org.get_identities([])
        mock_call.assert_called_once_with(TOKEN, ORG_NAME)

    def test_iter_graph_groups_delegates(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter,
        ):
            mock_call.return_value = _api_call()
            mock_iter.return_value = iter([_make_graph_group()])
            result = list(svc.org.iter_graph_groups())
        assert len(result) == 1
        assert isinstance(result[0], GraphGroup)

    def test_iter_graph_groups_uses_org_name_from_url(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter,
        ):
            mock_call.return_value = _api_call()
            mock_iter.return_value = iter([])
            list(svc.org.iter_graph_groups())
        mock_call.assert_called_once_with(TOKEN, "testorg")


class TestOrganizationListMethods:
    def test_list_projects_delegates(self) -> None:
        org = _make_service().org
        with patch.object(org, "iter_projects", return_value=iter([])):
            assert org.list_projects() == []

    def test_list_graph_groups_delegates(self) -> None:
        org = _make_service().org
        with patch.object(org, "iter_graph_groups", return_value=iter([])):
            assert org.list_graph_groups() == []
