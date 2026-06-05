"""Tests for pyado.project module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import requests

from pyado.raw import ApiCall, ProjectInfo, get_project, iter_projects, list_projects
from tests.conftest import _make_mock_response


def make_project_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid ProjectInfo dict.

    Returns:
        A dict with all required ProjectInfo fields populated.
    """
    project: dict[str, Any] = {
        "id": str(uuid4()),
        "name": "My Project",
        "description": "A test project",
        "state": "wellFormed",
        "revision": 1,
        "visibility": "private",
        "lastUpdateTime": "2024-01-01T00:00:00+00:00",
    }
    project.update(overrides)
    return project


def test_get_project_returns_project_info(api_call: ApiCall) -> None:
    """get_project returns a ProjectInfo for the named project."""
    data = make_project_dict(name="MyProject")
    mock_response = _make_mock_response(data)
    with patch.object(requests.Session, "request", return_value=mock_response):
        result = get_project(api_call, "MyProject")
    assert isinstance(result, ProjectInfo)
    assert result.name == "MyProject"


def test_project_info_parses_from_dict() -> None:
    """ProjectInfo can be instantiated from a raw API-style dict."""
    data = {
        "id": str(uuid4()),
        "name": "My Project",
        "description": "A test project",
        "state": "wellFormed",
        "revision": 42,
        "visibility": "private",
        "lastUpdateTime": "2024-01-01T00:00:00+00:00",
    }
    project = ProjectInfo.model_validate(data)
    assert project.name == "My Project"
    assert project.state == "wellFormed"
    assert project.visibility == "private"
    assert project.revision == 42


class TestIterProjects:
    """Tests for iter_projects."""

    @staticmethod
    def test_yields_project_info_objects(api_call: ApiCall) -> None:
        """Yields ProjectInfo objects from the API response."""
        project = make_project_dict(name="Alpha")
        mock_response = _make_mock_response({"value": [project]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        assert len(result) == 1
        assert isinstance(result[0], ProjectInfo)
        assert result[0].name == "Alpha"

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no projects."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        assert result == []

    @staticmethod
    def test_paginates_when_first_page_is_full(api_call: ApiCall) -> None:
        """Fetches a second page when the first response has exactly 100 projects."""
        first_page = {
            "value": [make_project_dict(name=f"proj-{idx}") for idx in range(100)]
        }
        second_page = {"value": [make_project_dict(name="proj-extra")]}
        mock_first = _make_mock_response(first_page)
        mock_second = _make_mock_response(second_page)
        with patch.object(
            requests.Session, "request", side_effect=[mock_first, mock_second]
        ):
            result = list(iter_projects(api_call))
        assert len(result) == 101
        assert result[-1].name == "proj-extra"


# ---------------------------------------------------------------------------
# Smoke tests — real API response shapes
# ---------------------------------------------------------------------------

_PROJECTS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
            "name": "main",
            "url": (
                "https://dev.azure.com/example-org/_apis/projects"
                "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            ),
            "collection": {
                "id": "42d6cb5c-6ed4-494b-9fc9-e3b11fcff454",
                "name": "example-org",
                "url": (
                    "https://dev.azure.com/example-org/_apis/projectCollections"
                    "/42d6cb5c-6ed4-494b-9fc9-e3b11fcff454"
                ),
                "collectionUrl": "https://dev.azure.com/example-org/",
            },
            "state": "wellFormed",
            "defaultTeam": {
                "id": "d64a3ce0-30a1-46d5-93ed-748bb80e3b0d",
                "name": "main Team",
                "url": (
                    "https://dev.azure.com/example-org/_apis/projects"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd/teams"
                    "/d64a3ce0-30a1-46d5-93ed-748bb80e3b0d"
                ),
            },
            "revision": 20,
            "visibility": "private",
            # Note: sentinel value "0001-01-01T00:00:00" with no timezone —
            # tests that datetime parsing is lenient enough to handle it.
            "lastUpdateTime": "0001-01-01T00:00:00",
        }
    ],
}


class TestSmokeIterProjects:
    """iter_projects parses real project response shapes."""

    @staticmethod
    def test_parses_project_with_collection_and_default_team(
        api_call: ApiCall,
    ) -> None:
        """Parses a project response including collection and defaultTeam fields."""
        mock_response = _make_mock_response(_PROJECTS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        assert len(result) == 1
        assert isinstance(result[0], ProjectInfo)
        assert result[0].name == "main"
        assert result[0].state == "wellFormed"
        assert result[0].revision == 20

    @staticmethod
    def test_parses_sentinel_last_update_time(api_call: ApiCall) -> None:
        """Parses lastUpdateTime '0001-01-01T00:00:00' (ADO sentinel with no tz)."""
        mock_response = _make_mock_response(_PROJECTS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        # The sentinel date-time must parse without error; year is 1.
        assert result[0].last_update_time.year == 1


class TestListProjects:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch("pyado.raw.project.iter_projects", return_value=iter([])) as m:
            result = list_projects(api_call)
        assert result == []
        m.assert_called_once_with(api_call)
