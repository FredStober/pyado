"""Tests for pyado.project module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.api_call import ApiCall
from pyado.project import ProjectInfo, iter_projects

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_token"


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance.

    Returns:
        A minimal ApiCall instance for testing.
    """
    return ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)


def _make_mock_response(json_data: Any) -> MagicMock:
    """Create a minimal mock HTTP response.

    Returns:
        A MagicMock configured to behave as a requests.Response.
    """
    mock = MagicMock(spec=requests.Response)
    mock.raise_for_status.return_value = None
    mock.json.return_value = json_data
    mock.content = jsonlib.dumps(json_data).encode()
    return mock


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
