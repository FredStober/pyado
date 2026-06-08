"""Tests for pyado.profile module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import pytest
import requests

from pyado.raw import (
    ApiCall,
    ConnectionData,
    UserProfile,
    get_connection_data,
    get_my_profile,
    get_profile_api_call,
    get_session,
)
from tests.conftest import _make_mock_response

BASE_URL = "https://app.vssps.visualstudio.com/_apis/"


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance for the profile base URL.

    Returns:
        A minimal ApiCall instance for testing.
    """
    return ApiCall(url=BASE_URL)


class TestGetProfileApiCall:
    """Tests for get_profile_api_call."""

    @staticmethod
    def test_returns_api_call_with_vssps_url() -> None:
        """Returns an ApiCall targeting the VSSPS profile endpoint."""
        session = get_session(pat="mytoken")
        api_call = get_profile_api_call(session)
        assert isinstance(api_call, ApiCall)
        assert "app.vssps.visualstudio.com" in api_call.url.unicode_string()
        assert api_call.session is session


class TestGetMyProfile:
    """Tests for get_my_profile."""

    @staticmethod
    def test_returns_user_profile(api_call: ApiCall) -> None:
        """Returns a UserProfile with all fields populated."""
        response_data = {
            "id": "user-id-123",
            "displayName": "Alice Example",
            "emailAddress": "alice@example.com",
            "publicAlias": "alice",
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_my_profile(api_call)
        assert isinstance(result, UserProfile)
        assert result.display_name == "Alice Example"
        assert result.email_address == "alice@example.com"
        assert result.public_alias == "alice"
        assert result.id == "user-id-123"


class TestGetConnectionData:
    """Tests for get_connection_data."""

    @staticmethod
    def test_returns_connection_data_with_authenticated_user(api_call: ApiCall) -> None:
        """Returns a ConnectionData with the authenticatedUser populated."""
        response_data = {
            "authenticatedUser": {
                "id": "user-guid-456",
                "providerDisplayName": "Bob Example",
            }
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_connection_data(api_call)
        assert isinstance(result, ConnectionData)
        assert result.authenticated_user.id == "user-guid-456"
        assert result.authenticated_user.provider_display_name == "Bob Example"

    @staticmethod
    def test_sends_get_request_to_connection_data_endpoint(
        api_call: ApiCall,
    ) -> None:
        """Sends a GET request to the _apis/connectionData endpoint."""
        response_data = {"authenticatedUser": {"id": "x", "providerDisplayName": "Y"}}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_connection_data(api_call)
        call = mock_req.call_args
        assert call.args[0] == "GET"
        assert "connectionData" in call.kwargs.get("url", "")
