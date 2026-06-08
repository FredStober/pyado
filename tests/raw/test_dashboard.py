"""Tests for pyado.raw.dashboard — dashboard API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    DashboardInfo,
    WidgetInfo,
    get_dashboard,
    get_dashboard_api_call,
    iter_dashboards,
    list_dashboards,
)
from tests.conftest import _make_mock_response

_DASHBOARD_ID = "11111111-aaaa-bbbb-cccc-dddddddddddd"
_WIDGET_ID = "22222222-aaaa-bbbb-cccc-dddddddddddd"


class TestListDashboards:
    @staticmethod
    def test_returns_list_of_dashboards(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": _DASHBOARD_ID,
                    "name": "Team Dashboard",
                    "description": "Main dashboard",
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_dashboards(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], DashboardInfo)
        assert results[0].id == UUID(_DASHBOARD_ID)
        assert results[0].name == "Team Dashboard"

    @staticmethod
    def test_returns_empty_list_when_no_dashboards(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_dashboards(api_call)
        assert results == []

    @staticmethod
    def test_optional_description_defaults_to_empty(api_call: ApiCall) -> None:
        payload = {"value": [{"id": _DASHBOARD_ID, "name": "Minimal"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_dashboards(api_call)
        assert not results[0].description
        assert results[0].widgets == []


class TestIterDashboards:
    @staticmethod
    def test_yields_dashboards(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {"id": _DASHBOARD_ID, "name": "Dashboard A"},
                {"id": _DASHBOARD_ID, "name": "Dashboard B"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_dashboards(api_call))
        assert len(results) == 2


class TestGetDashboardApiCall:
    @staticmethod
    def test_returns_api_call(api_call: ApiCall) -> None:
        result = get_dashboard_api_call(api_call, UUID(_DASHBOARD_ID))
        assert isinstance(result, ApiCall)


class TestGetDashboard:
    @staticmethod
    def test_returns_dashboard_with_widgets(api_call: ApiCall) -> None:
        payload = {
            "id": _DASHBOARD_ID,
            "name": "Detail Dashboard",
            "widgets": [
                {
                    "id": _WIDGET_ID,
                    "name": "Burndown",
                    "typeId": "Microsoft.VisualStudioOnline.Dashboards.BurndownWidget",
                    "position": {"row": 1, "column": 1},
                    "size": {"rowSpan": 2, "columnSpan": 4},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_dashboard(api_call)
        assert isinstance(result, DashboardInfo)
        assert result.id == UUID(_DASHBOARD_ID)
        assert len(result.widgets) == 1
        assert isinstance(result.widgets[0], WidgetInfo)
        assert result.widgets[0].id == UUID(_WIDGET_ID)

    @staticmethod
    def test_returns_dashboard_without_widgets(api_call: ApiCall) -> None:
        payload = {"id": _DASHBOARD_ID, "name": "Empty Dashboard"}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_dashboard(api_call)
        assert result.widgets == []
