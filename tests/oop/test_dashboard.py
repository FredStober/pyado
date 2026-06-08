"""Tests for pyado.oop Dashboard and team/project dashboard methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import uuid4

from pyado.oop import Dashboard, Team
from pyado.raw import DashboardId, DashboardInfo
from tests.oop.conftest import (
    _make_project,
    _make_service,
    _project_info,
    _team_info,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _dashboard_info(name: str = "Overview") -> DashboardInfo:
    return DashboardInfo.model_validate(
        {
            "id": str(uuid4()),
            "name": name,
            "widgets": [
                {"id": str(uuid4()), "name": "Chart"},
            ],
        }
    )


def _make_team() -> Team:
    return Team(_make_project(), _team_info(), _make_service())


# ---------------------------------------------------------------------------
# Dashboard class
# ---------------------------------------------------------------------------


class TestDashboardProperties:
    def test_id_returns_uuid(self) -> None:
        info = _dashboard_info()
        dash = Dashboard(_make_team(), info)
        assert dash.id == info.id

    def test_name_returns_name(self) -> None:
        info = _dashboard_info("My Dashboard")
        dash = Dashboard(_make_team(), info)
        assert dash.name == "My Dashboard"

    def test_widgets_returns_widget_list(self) -> None:
        info = _dashboard_info()
        dash = Dashboard(_make_team(), info)
        assert isinstance(dash.widgets, list)
        assert len(dash.widgets) == 1

    def test_info_returns_stored_info(self) -> None:
        info = _dashboard_info()
        dash = Dashboard(_make_team(), info)
        assert dash.info is info

    def test_info_fetches_when_none(self) -> None:
        team = _make_team()
        info = _dashboard_info()
        dash = Dashboard(team, info)
        dash.refresh()
        refreshed = _dashboard_info("Refreshed")
        with patch("pyado.oop.overview.dashboard.raw.get_dashboard") as mock_get:
            mock_get.return_value = refreshed
            result = dash.info
        assert result is refreshed

    def test_team_back_reference(self) -> None:
        team = _make_team()
        dash = Dashboard(team, _dashboard_info())
        assert dash.team is team

    def test_project_back_reference(self) -> None:
        team = _make_team()
        dash = Dashboard(team, _dashboard_info())
        assert dash.project is team.project

    def test_org_back_reference(self) -> None:
        team = _make_team()
        dash = Dashboard(team, _dashboard_info())
        assert dash.org is team.org

    def test_api_call_includes_dashboard_id(self) -> None:
        team = _make_team()
        info = _dashboard_info()
        dash = Dashboard(team, info)
        with patch(
            "pyado.oop.overview.dashboard.raw.get_dashboard_api_call"
        ) as mock_ac:
            mock_ac.return_value = MagicMock()
            _ = dash.api_call
        mock_ac.assert_called_once_with(team.api_call, info.id)


class TestDashboardRefresh:
    def test_refresh_clears_info(self) -> None:
        dash = Dashboard(_make_team(), _dashboard_info())
        dash.refresh()
        assert dash._info is None

    def test_info_re_fetches_after_refresh(self) -> None:
        team = _make_team()
        dash = Dashboard(team, _dashboard_info())
        dash.refresh()
        new_info = _dashboard_info("After refresh")
        with patch("pyado.oop.overview.dashboard.raw.get_dashboard") as mock_get:
            mock_get.return_value = new_info
            _ = dash.info
        mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# Team dashboard methods
# ---------------------------------------------------------------------------


class TestTeamDashboards:
    def test_iter_dashboards_yields_dashboards(self) -> None:
        team = _make_team()
        info = _dashboard_info()
        with patch("pyado.oop.boards.team.raw.iter_dashboards") as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(team.iter_dashboards())
        assert len(result) == 1
        assert isinstance(result[0], Dashboard)
        assert result[0].name == info.name

    def test_iter_dashboards_empty(self) -> None:
        team = _make_team()
        with patch("pyado.oop.boards.team.raw.iter_dashboards") as mock_iter:
            mock_iter.return_value = iter([])
            result = list(team.iter_dashboards())
        assert result == []

    def test_list_dashboards_delegates(self) -> None:
        team = _make_team()
        with patch.object(team, "iter_dashboards", return_value=iter([])):
            assert team.list_dashboards() == []

    def test_get_dashboard_returns_dashboard(self) -> None:
        team = _make_team()
        info = _dashboard_info()
        dashboard_id: DashboardId = uuid4()
        with (
            patch("pyado.oop.boards.team.raw.get_dashboard_api_call") as mock_ac,
            patch("pyado.oop.boards.team.raw.get_dashboard") as mock_get,
        ):
            mock_ac.return_value = MagicMock()
            mock_get.return_value = info
            result = team.get_dashboard(dashboard_id)
        assert isinstance(result, Dashboard)
        assert result.name == info.name

    def test_get_dashboard_passes_id_to_api_call(self) -> None:
        team = _make_team()
        dashboard_id: DashboardId = uuid4()
        with (
            patch("pyado.oop.boards.team.raw.get_dashboard_api_call") as mock_ac,
            patch("pyado.oop.boards.team.raw.get_dashboard") as mock_get,
        ):
            mock_ac.return_value = MagicMock()
            mock_get.return_value = _dashboard_info()
            team.get_dashboard(dashboard_id)
        mock_ac.assert_called_once_with(team.api_call, dashboard_id)


# ---------------------------------------------------------------------------
# Project dashboard methods
# ---------------------------------------------------------------------------


class TestProjectDashboards:
    def test_iter_dashboards_via_teams(self) -> None:
        proj = _make_project()
        info = _dashboard_info()
        team_inf = _team_info()
        with (
            patch("pyado.oop.boards.project_boards.raw.iter_teams") as mock_teams,
            patch("pyado.oop.boards.team.raw.iter_dashboards") as mock_dashes,
        ):
            mock_teams.return_value = iter([team_inf])
            mock_dashes.return_value = iter([info])
            result = list(proj.iter_dashboards())
        assert len(result) == 1
        assert isinstance(result[0], Dashboard)

    def test_iter_dashboards_with_explicit_team(self) -> None:
        proj = _make_project()
        svc = _make_service()
        team = Team(proj, _team_info(), svc)
        info = _dashboard_info()
        with patch("pyado.oop.boards.team.raw.iter_dashboards") as mock_dashes:
            mock_dashes.return_value = iter([info])
            result = list(proj.iter_dashboards(team=team))
        assert len(result) == 1

    def test_list_dashboards_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_dashboards", return_value=iter([])):
            assert proj.list_dashboards() == []

    def test_get_dashboard_uses_default_team_when_none(self) -> None:
        proj = _make_project()
        info = _dashboard_info()
        team_inf = _team_info()
        dashboard_id: DashboardId = uuid4()
        with (
            patch("pyado.oop.boards.project_boards.raw.get_team") as mock_team,
            patch("pyado.oop.project.raw.get_project") as mock_proj,
            patch("pyado.oop.project.raw.get_dashboard_api_call") as mock_ac,
            patch("pyado.oop.project.raw.get_dashboard") as mock_get,
        ):
            mock_team.return_value = team_inf
            mock_proj.return_value = _project_info()
            mock_ac.return_value = MagicMock()
            mock_get.return_value = info
            result = proj.get_dashboard(dashboard_id)
        assert isinstance(result, Dashboard)

    def test_get_dashboard_with_explicit_team(self) -> None:
        proj = _make_project()
        svc = _make_service()
        team = Team(proj, _team_info(), svc)
        info = _dashboard_info()
        dashboard_id: DashboardId = uuid4()
        with (
            patch("pyado.oop.project.raw.get_dashboard_api_call") as mock_ac,
            patch("pyado.oop.project.raw.get_dashboard") as mock_get,
        ):
            mock_ac.return_value = MagicMock()
            mock_get.return_value = info
            result = proj.get_dashboard(dashboard_id, team=team)
        assert isinstance(result, Dashboard)
