"""Tests for pyado.profile module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from pyado.api_call import ApiCall
from pyado.profile import UserProfile, get_my_profile

BASE_URL = "https://app.vssps.visualstudio.com/_apis/"
ACCESS_TOKEN = "test_token"


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance for the profile base URL.

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
