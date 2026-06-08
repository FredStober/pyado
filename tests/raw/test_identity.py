"""Tests for pyado.raw.identity module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch

import requests

from pyado.raw import (
    GraphGroup,
    IdentityInfo,
    get_identities,
    get_session,
    get_vssps_api_call,
    iter_graph_groups,
    list_graph_groups,
)
from pyado.raw._core import ApiCall
from tests.conftest import ACCESS_TOKEN, _make_mock_response


def _make_identity_dict(identity_id: str = "id-001") -> dict[str, Any]:
    """Create a minimal valid IdentityInfo dict."""
    return {
        "id": identity_id,
        "providerDisplayName": "Test User",
        "subjectDescriptor": "aad.desc",
        "isActive": True,
        "isContainer": False,
    }


def _make_graph_group_dict(descriptor: str = "group-desc-001") -> dict[str, Any]:
    """Create a minimal valid GraphGroup dict."""
    return {
        "displayName": "My Group",
        "descriptor": descriptor,
        "principalName": "[Project]\\My Group",
        "subjectKind": "group",
    }


class TestGetVsspsApiCall:
    """Tests for get_vssps_api_call."""

    @staticmethod
    def test_url_contains_vssps_host() -> None:
        """Returned ApiCall URL uses the vssps.dev.azure.com host."""
        api_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        assert "vssps.dev.azure.com" in api_call.url.unicode_string()

    @staticmethod
    def test_url_contains_org_name() -> None:
        """Returned ApiCall URL contains the organisation name."""
        api_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "acme-corp")
        assert "acme-corp" in api_call.url.unicode_string()


class TestGetIdentities:
    """Tests for get_identities."""

    @staticmethod
    def test_returns_identity_list() -> None:
        """Returns a list of IdentityInfo objects."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {
            "value": [_make_identity_dict(), _make_identity_dict("id-002")]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_identities(vssps_call, ["aad.desc", "aad.desc2"])
        assert len(result) == 2
        assert all(isinstance(item, IdentityInfo) for item in result)

    @staticmethod
    def test_filters_none_identity_values() -> None:
        """None entries in the value list are excluded from the returned list."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {
            "value": [
                _make_identity_dict("id-001"),
                None,
                _make_identity_dict("id-002"),
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_identities(vssps_call, ["aad.desc1", "aad.desc2", "aad.desc3"])
        assert len(result) == 2
        assert all(isinstance(item, IdentityInfo) for item in result)

    @staticmethod
    def test_descriptors_joined_in_params() -> None:
        """Descriptor list is joined with commas in the query parameters."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {"value": [_make_identity_dict()]}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_identities(vssps_call, ["desc-a", "desc-b"])
        params = mock_req.call_args[1]["params"]
        assert "desc-a" in params.get("descriptors", "")
        assert "desc-b" in params.get("descriptors", "")


class TestIterGraphGroups:
    """Tests for iter_graph_groups."""

    @staticmethod
    def test_yields_graph_groups() -> None:
        """Yields GraphGroup objects for each group in the response."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {
            "value": [_make_graph_group_dict(), _make_graph_group_dict("g-002")]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_graph_groups(vssps_call))
        assert len(result) == 2
        assert all(isinstance(item, GraphGroup) for item in result)
        assert result[0].display_name == "My Group"


class TestListGraphGroups:
    """Tests for list_graph_groups."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_graph_groups results."""
        with patch("pyado.raw.core.identity.iter_graph_groups", return_value=iter([])):
            result = list_graph_groups(api_call)
        assert result == []
