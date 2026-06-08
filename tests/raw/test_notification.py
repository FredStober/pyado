"""Tests for pyado.raw.notification — notification subscription wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado.raw import (
    ApiCall,
    NotificationSubscription,
    iter_notification_subscriptions,
    list_notification_subscriptions,
)
from tests.conftest import _make_mock_response


class TestListNotificationSubscriptions:
    @staticmethod
    def test_returns_list_of_subscriptions(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": "sub-1",
                    "description": "Build completed",
                    "filter": {"eventType": "ms.vss-build.build-completed-event"},
                    "subscriber": {"id": "user-1", "displayName": "Alice"},
                    "channel": {"type": "EmailHtml"},
                    "scope": {"type": "project", "id": "proj-1"},
                    "status": "enabled",
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_notification_subscriptions(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], NotificationSubscription)
        assert results[0].id == "sub-1"
        assert results[0].description == "Build completed"
        assert results[0].status == "enabled"

    @staticmethod
    def test_returns_empty_list_when_no_subscriptions(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_notification_subscriptions(api_call)
        assert results == []

    @staticmethod
    def test_optional_fields_default_correctly(api_call: ApiCall) -> None:
        payload = {"value": [{"id": "sub-2"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_notification_subscriptions(api_call)
        assert not results[0].description
        assert results[0].status is None
        assert results[0].url is None
        assert results[0].flags is None
        assert results[0].permissions is None
        assert results[0].admin_settings == {}
        assert results[0].diagnostics == {}
        assert results[0].extended_properties == {}
        assert results[0].user_settings == {}

    @staticmethod
    def test_extra_fields_parsed(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "id": "sub-5",
                    "url": "https://dev.azure.com/_apis/notification/subscriptions/sub-5",
                    "flags": "groupSubscription, canOptOut",
                    "permissions": "view",
                    "adminSettings": {"blockUserOptOut": False},
                    "diagnostics": {"deliveryResults": {}},
                    "extendedProperties": {},
                    "userSettings": {"optedOut": False},
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_notification_subscriptions(api_call)
        assert results[0].flags == "groupSubscription, canOptOut"
        assert results[0].permissions == "view"
        assert results[0].admin_settings == {"blockUserOptOut": False}
        assert results[0].user_settings == {"optedOut": False}


class TestIterNotificationSubscriptions:
    @staticmethod
    def test_yields_subscriptions(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {"id": "sub-3", "description": "PR created"},
                {"id": "sub-4", "description": "PR updated"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_notification_subscriptions(api_call))
        assert len(results) == 2
        assert results[0].id == "sub-3"
        assert results[1].id == "sub-4"
