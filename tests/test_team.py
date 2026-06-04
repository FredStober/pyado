"""Tests for pyado.raw.team module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado import ApiCall, TeamInfo, get_team, iter_teams
from tests.conftest import _make_mock_response


def _make_team_dict(
    team_id: str = "team-001", name: str = "My Team"
) -> dict[str, str | None]:
    """Create a minimal valid TeamInfo dict."""
    return {"id": team_id, "name": name, "description": "A test team", "url": None}


class TestIterTeams:
    """Tests for iter_teams."""

    @staticmethod
    def test_yields_team_info_objects(api_call: ApiCall) -> None:
        """Yields TeamInfo objects from the value list."""
        response_data = {
            "value": [_make_team_dict("t1", "Alpha"), _make_team_dict("t2", "Beta")]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_teams(api_call, "MyProject"))
        assert len(result) == 2
        assert all(isinstance(item, TeamInfo) for item in result)
        assert result[0].name == "Alpha"
        assert result[1].name == "Beta"

    @staticmethod
    def test_yields_empty_when_no_teams(api_call: ApiCall) -> None:
        """Yields nothing when no teams are returned."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_teams(api_call, "MyProject"))
        assert result == []

    @staticmethod
    def test_url_contains_project_name(api_call: ApiCall) -> None:
        """Request URL contains the project name and teams path."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_teams(api_call, "SpecialProject"))
        url = mock_req.call_args.kwargs.get("url", "")
        assert "SpecialProject" in url
        assert "teams" in url

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_teams(api_call, "MyProject"))
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_paginates_when_full_page_returned(api_call: ApiCall) -> None:
        """Issues a second request when the first page is full (100 items)."""
        page1 = {"value": [_make_team_dict(f"t{i}", f"Team{i}") for i in range(100)]}
        page2 = {"value": [_make_team_dict("t100", "Team100")]}
        responses = [_make_mock_response(page1), _make_mock_response(page2)]
        with patch.object(
            requests.Session, "request", side_effect=responses
        ) as mock_req:
            result = list(iter_teams(api_call, "MyProject"))
        assert len(result) == 101
        assert mock_req.call_count == 2


class TestGetTeam:
    """Tests for get_team."""

    @staticmethod
    def test_returns_team_info(api_call: ApiCall) -> None:
        """Returns a TeamInfo parsed from the API response."""
        mock_response = _make_mock_response(_make_team_dict("team-abc", "DevOps"))
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_team(api_call, "MyProject", "DevOps")
        assert isinstance(result, TeamInfo)
        assert result.id == "team-abc"
        assert result.name == "DevOps"

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request."""
        mock_response = _make_mock_response(_make_team_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_team(api_call, "MyProject", "my-team")
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_url_contains_team_name_or_id(api_call: ApiCall) -> None:
        """Request URL contains the team name or ID."""
        mock_response = _make_mock_response(_make_team_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_team(api_call, "MyProject", "my-special-team")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "my-special-team" in url

    @staticmethod
    def test_url_contains_project_name(api_call: ApiCall) -> None:
        """Request URL contains the project name."""
        mock_response = _make_mock_response(_make_team_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_team(api_call, "SpecialProject", "some-team")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "SpecialProject" in url
