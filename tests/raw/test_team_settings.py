"""Tests for pyado.raw.boards.team_settings — team settings wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch

import requests

from pyado.raw._core import ApiCall
from pyado.raw.boards.team_settings import (
    get_team_iterations,
    get_team_settings,
    patch_team_field_values,
    patch_team_settings,
)
from pyado.raw.boards.work_item import TeamFieldSettings, TeamFieldValue
from tests.conftest import _make_mock_response

_ITERATION_ID = "iter-guid-001"


class TestGetTeamSettings:
    @staticmethod
    def test_returns_settings(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"bugsBehavior": "asRequirements", "workingDays": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_team_settings(api_call)
        assert result["bugsBehavior"] == "asRequirements"


class TestPatchTeamSettings:
    @staticmethod
    def test_returns_updated_settings(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"bugsBehavior": "asTasks"}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_team_settings(api_call, {"bugsBehavior": "asTasks"})
        assert result["bugsBehavior"] == "asTasks"


class TestGetTeamIterations:
    @staticmethod
    def test_returns_iterations(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"id": _ITERATION_ID, "name": "Sprint 1"},
                {"id": "iter-guid-002", "name": "Sprint 2"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_team_iterations(api_call)
        assert len(result) == 2
        assert result[0]["name"] == "Sprint 1"

    @staticmethod
    def test_returns_empty_when_no_value(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response({})
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_team_iterations(api_call)
        assert result == []


class TestPatchTeamFieldValues:
    @staticmethod
    def test_sends_typed_body_and_returns_settings(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "defaultValue": "MyProject\\New",
            "values": [{"value": "MyProject\\New", "includeChildren": True}],
        }
        mock_resp = _make_mock_response(payload)
        settings = TeamFieldSettings(
            default_value="MyProject\\New",
            values=[TeamFieldValue(value="MyProject\\New", include_children=True)],
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            result = patch_team_field_values(api_call, settings)
        assert mock_req.call_args.kwargs["json"] == payload
        assert isinstance(result, TeamFieldSettings)
        assert result.default_value == "MyProject\\New"
        assert result.values[0].include_children is True
