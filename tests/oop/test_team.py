"""Tests for pyado.oop Team — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import uuid4

from pyado.oop import Project, Team
from pyado.raw import SprintIterationInfo, TeamFieldValue, TeamMember
from tests.oop.conftest import (
    _make_project,
    _make_service,
    _project_info,
    _team_info,
)


class TestTeam:
    def test_id(self) -> None:
        team = Team(_make_project(), _team_info("abc-123"), _make_service())
        assert team.id == "abc-123"

    def test_name(self) -> None:
        team = Team(_make_project(), _team_info(name="Alpha"), _make_service())
        assert team.name == "Alpha"

    def test_info_returns_team_info(self) -> None:
        info = _team_info()
        team = Team(_make_project(), info, _make_service())
        assert team.info is info

    def test_project_reference(self) -> None:
        proj = _make_project()
        team = Team(proj, _team_info(), _make_service())
        assert team.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        team = Team(proj, _team_info(), svc)
        assert team.org is svc.org

    def test_api_call_is_team_scoped(self) -> None:
        svc = _make_service()
        proj = _make_project()
        team = Team(proj, _team_info(name="MyTeam"), svc)
        url = team.api_call.url.unicode_string()
        assert "MyTeam" in url

    def _make_team(self) -> Team:
        return Team(_make_project(), _team_info(), _make_service())

    def test_iter_sprint_iterations_delegates(self) -> None:
        sprint = SprintIterationInfo.model_validate(
            {
                "id": str(uuid4()),
                "name": "Sprint 1",
                "path": "proj\\Sprint 1",
                "attributes": {"timeFrame": "current"},
            }
        )
        with patch("pyado.oop.team.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([sprint])
            result = list(self._make_team().iter_sprint_iterations())
        assert len(result) == 1
        assert result[0].name == "Sprint 1"

    def test_get_field_values_delegates(self) -> None:
        fv = TeamFieldValue.model_validate(
            {"value": "proj\\Area1", "includeChildren": False}
        )
        with patch("pyado.oop.team.raw.get_team_field_values") as mock_get:
            mock_get.return_value = [fv]
            result = self._make_team().get_field_values()
        assert len(result) == 1
        assert result[0].value == "proj\\Area1"

    def test_add_iteration_delegates(self) -> None:
        iteration_id = uuid4()
        with patch("pyado.oop.team.raw.add_team_iteration") as mock_add:
            self._make_team().add_iteration(iteration_id)
        mock_add.assert_called_once_with(self._make_team().api_call, iteration_id)

    def test_remove_iteration_delegates(self) -> None:
        iteration_id = uuid4()
        with patch("pyado.oop.team.raw.delete_team_iteration") as mock_del:
            self._make_team().remove_iteration(iteration_id)
        mock_del.assert_called_once_with(self._make_team().api_call, iteration_id)

    def test_refresh_updates_info(self) -> None:
        team = self._make_team()
        refreshed = _team_info(name="Refreshed")
        with patch("pyado.oop.team.raw.get_team") as mock_get:
            mock_get.return_value = refreshed
            team.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = team.info
        assert team._info is refreshed
        assert mock_get.call_args.args[2] == team.id


class TestTeamMembers:
    def _make_team(self) -> Team:
        return Team(_make_project(), _team_info(), _make_service())

    def test_iter_members_delegates(self) -> None:
        member = _team_member("Alice")
        with patch("pyado.oop.team.raw.iter_team_members") as mock_iter:
            mock_iter.return_value = iter([member])
            result = list(self._make_team().iter_members())
        assert len(result) == 1
        assert result[0].identity.display_name == "Alice"
        mock_iter.assert_called_once()

    def test_iter_members_empty(self) -> None:
        with patch("pyado.oop.team.raw.iter_team_members") as mock_iter:
            mock_iter.return_value = iter([])
            result = list(self._make_team().iter_members())
        assert result == []


class TestTeamListMethods:
    def _make_team(self) -> Team:
        return Team(_make_project(), _team_info(), _make_service())

    def test_list_sprint_iterations_delegates(self) -> None:
        team = self._make_team()
        with patch.object(team, "iter_sprint_iterations", return_value=iter([])):
            assert team.list_sprint_iterations() == []

    def test_list_members_delegates(self) -> None:
        team = self._make_team()
        with patch.object(team, "iter_members", return_value=iter([])):
            assert team.list_members() == []


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _team_member(display_name: str = "Alice") -> TeamMember:
    return TeamMember.model_validate(
        {
            "identity": {
                "id": str(uuid4()),
                "displayName": display_name,
                "uniqueName": f"{display_name.lower()}@example.com",
            },
            "isTeamAdmin": False,
        }
    )
