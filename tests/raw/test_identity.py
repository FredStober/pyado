"""Tests for pyado.raw.identity module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    AccessLevel,
    GraphGroup,
    GraphMembership,
    GraphUser,
    IdentityInfo,
    UserEntitlement,
    UserEntitlementCreateRequest,
    delete_graph_membership,
    get_graph_user,
    get_identities,
    get_session,
    get_vssps_api_call,
    iter_graph_groups,
    iter_graph_users,
    iter_user_entitlements,
    list_graph_groups,
    list_graph_users,
    list_user_entitlements,
    patch_user_entitlement,
    post_user_entitlement,
    put_graph_membership,
)
from pyado.raw._core import ApiCall
from pyado.raw.core.identity import list_graph_memberships
from tests.conftest import ACCESS_TOKEN, _make_mock_response

_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_DESCRIPTOR = "aad.dXNlcjEyMw"
_CONTAINER_DESCRIPTOR = "vssgp.Z3JvdXA"


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


def _make_graph_user_dict(descriptor: str = _DESCRIPTOR) -> dict[str, Any]:
    """Create a minimal valid GraphUser dict."""
    return {
        "descriptor": descriptor,
        "displayName": "Alice Smith",
        "subjectKind": "user",
        "principalName": "alice@example.com",
        "mailAddress": "alice@example.com",
        "origin": "aad",
        "originId": "orig-001",
        "isDeletedInOrigin": False,
    }


def _make_user_entitlement_dict(user_id: str = _USER_ID) -> dict[str, Any]:
    """Create a minimal valid UserEntitlement dict."""
    return {
        "id": user_id,
        "user": _make_graph_user_dict(),
        "accessLevel": {
            "accountLicenseType": "express",
            "licensingSource": "account",
        },
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


class TestGetGraphUser:
    """Tests for get_graph_user."""

    @staticmethod
    def test_returns_graph_user() -> None:
        """Returns a GraphUser object for the requested descriptor."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response(_make_graph_user_dict())
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_graph_user(vssps_call, _DESCRIPTOR)
        assert isinstance(result, GraphUser)
        assert result.descriptor == _DESCRIPTOR
        assert result.display_name == "Alice Smith"

    @staticmethod
    def test_descriptor_in_url() -> None:
        """The subject descriptor appears in the request URL."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response(_make_graph_user_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_graph_user(vssps_call, _DESCRIPTOR)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _DESCRIPTOR in called_url


class TestIterGraphUsers:
    """Tests for iter_graph_users."""

    @staticmethod
    def test_yields_graph_users() -> None:
        """Yields GraphUser objects for each user in the response."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {
            "value": [
                _make_graph_user_dict(),
                _make_graph_user_dict("aad.second"),
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_graph_users(vssps_call))
        assert len(result) == 2
        assert all(isinstance(item, GraphUser) for item in result)

    @staticmethod
    def test_yields_empty_when_no_users() -> None:
        """Yields nothing when the value list is empty."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_graph_users(vssps_call))
        assert result == []


class TestListGraphUsers:
    """Tests for list_graph_users."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_graph_users results."""
        with patch("pyado.raw.core.identity.iter_graph_users", return_value=iter([])):
            result = list_graph_users(api_call)
        assert result == []


class TestAddGraphMembership:
    """Tests for put_graph_membership."""

    @staticmethod
    def test_returns_membership() -> None:
        """Returns a GraphMembership linking member to container."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        payload = {
            "containerDescriptor": _CONTAINER_DESCRIPTOR,
            "memberDescriptor": _DESCRIPTOR,
        }
        mock_response = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = put_graph_membership(
                vssps_call, _DESCRIPTOR, _CONTAINER_DESCRIPTOR
            )
        assert isinstance(result, GraphMembership)
        assert result.container_descriptor == _CONTAINER_DESCRIPTOR
        assert result.member_descriptor == _DESCRIPTOR

    @staticmethod
    def test_sends_put_request() -> None:
        """Sends a PUT request to the memberships endpoint."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        payload = {
            "containerDescriptor": _CONTAINER_DESCRIPTOR,
            "memberDescriptor": _DESCRIPTOR,
        }
        mock_response = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            put_graph_membership(vssps_call, _DESCRIPTOR, _CONTAINER_DESCRIPTOR)
        assert mock_req.call_args.args[0] == "PUT"

    @staticmethod
    def test_descriptors_in_url() -> None:
        """Both subject and container descriptors appear in the request URL."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        payload = {
            "containerDescriptor": _CONTAINER_DESCRIPTOR,
            "memberDescriptor": _DESCRIPTOR,
        }
        mock_response = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            put_graph_membership(vssps_call, _DESCRIPTOR, _CONTAINER_DESCRIPTOR)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _DESCRIPTOR in called_url
        assert _CONTAINER_DESCRIPTOR in called_url


class TestRemoveGraphMembership:
    """Tests for delete_graph_membership."""

    @staticmethod
    def test_sends_delete_request() -> None:
        """Sends a DELETE request to the memberships endpoint."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_graph_membership(vssps_call, _DESCRIPTOR, _CONTAINER_DESCRIPTOR)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_descriptors_in_url() -> None:
        """Both subject and container descriptors appear in the DELETE URL."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_graph_membership(vssps_call, _DESCRIPTOR, _CONTAINER_DESCRIPTOR)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _DESCRIPTOR in called_url
        assert _CONTAINER_DESCRIPTOR in called_url


class TestIterUserEntitlements:
    """Tests for iter_user_entitlements."""

    @staticmethod
    def test_yields_user_entitlements() -> None:
        """Yields UserEntitlement objects from the members field."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        response_data = {
            "members": [
                _make_user_entitlement_dict(),
                _make_user_entitlement_dict("bbbbbbbb-cccc-dddd-eeee-ffffffffffff"),
            ],
            "totalCount": 2,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_user_entitlements(vssps_call))
        assert len(result) == 2
        assert all(isinstance(item, UserEntitlement) for item in result)

    @staticmethod
    def test_yields_empty_when_no_members() -> None:
        """Yields nothing when the members list is empty."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response({"members": [], "totalCount": 0})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_user_entitlements(vssps_call))
        assert result == []


class TestListUserEntitlements:
    """Tests for list_user_entitlements."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_user_entitlements results."""
        with patch(
            "pyado.raw.core.identity.iter_user_entitlements", return_value=iter([])
        ):
            result = list_user_entitlements(api_call)
        assert result == []


class TestAddUserEntitlement:
    """Tests for post_user_entitlement."""

    @staticmethod
    def _make_request() -> UserEntitlementCreateRequest:
        user = GraphUser(
            descriptor=_DESCRIPTOR,
            display_name="Alice Smith",
            subject_kind="user",
            principal_name="alice@example.com",
        )
        access_level = AccessLevel(account_license_type="express")
        return UserEntitlementCreateRequest(user=user, access_level=access_level)

    @staticmethod
    def test_returns_user_entitlement() -> None:
        """Returns the UserEntitlement from the operation result."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {
            "isSuccess": True,
            "result": _make_user_entitlement_dict(),
        }
        mock_response = _make_mock_response(op_result)
        request = TestAddUserEntitlement._make_request()
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_user_entitlement(vssps_call, request)
        assert isinstance(result, UserEntitlement)
        assert result.id == UUID(_USER_ID)

    @staticmethod
    def test_sends_post_request() -> None:
        """Sends a POST request to the userentitlements endpoint."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {"isSuccess": True, "result": _make_user_entitlement_dict()}
        mock_response = _make_mock_response(op_result)
        request = TestAddUserEntitlement._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_user_entitlement(vssps_call, request)
        assert mock_req.call_args.args[0] == "POST"

    @staticmethod
    def test_sends_json_body() -> None:
        """Sends the request body as JSON with camelCase keys."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {"isSuccess": True, "result": _make_user_entitlement_dict()}
        mock_response = _make_mock_response(op_result)
        request = TestAddUserEntitlement._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_user_entitlement(vssps_call, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert "user" in sent_json
        assert "accessLevel" in sent_json


class TestUpdateUserAccessLevel:
    """Tests for patch_user_entitlement."""

    @staticmethod
    def test_returns_updated_entitlement() -> None:
        """Returns the updated UserEntitlement from the operation result."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {
            "isSuccess": True,
            "result": _make_user_entitlement_dict(),
        }
        mock_response = _make_mock_response(op_result)
        access_level = AccessLevel(account_license_type="express")
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_user_entitlement(vssps_call, UUID(_USER_ID), access_level)
        assert isinstance(result, UserEntitlement)
        assert result.id == UUID(_USER_ID)

    @staticmethod
    def test_sends_patch_request() -> None:
        """Sends a PATCH request to the userentitlements endpoint."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {"isSuccess": True, "result": _make_user_entitlement_dict()}
        mock_response = _make_mock_response(op_result)
        access_level = AccessLevel(account_license_type="express")
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_user_entitlement(vssps_call, UUID(_USER_ID), access_level)
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_user_id_in_url() -> None:
        """The user UUID appears in the PATCH request URL."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {"isSuccess": True, "result": _make_user_entitlement_dict()}
        mock_response = _make_mock_response(op_result)
        access_level = AccessLevel(account_license_type="express")
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_user_entitlement(vssps_call, UUID(_USER_ID), access_level)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _USER_ID in called_url

    @staticmethod
    def test_sends_json_patch_body() -> None:
        """Sends a JSON Patch document replacing the /accessLevel path."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        op_result = {"isSuccess": True, "result": _make_user_entitlement_dict()}
        mock_response = _make_mock_response(op_result)
        access_level = AccessLevel(account_license_type="express")
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_user_entitlement(vssps_call, UUID(_USER_ID), access_level)
        sent_json = mock_req.call_args.kwargs["json"]
        assert isinstance(sent_json, list)
        assert sent_json[0]["op"] == "replace"
        assert sent_json[0]["path"] == "/accessLevel"
        assert sent_json[0]["value"]["accountLicenseType"] == "express"


class TestListGraphMemberships:
    """Tests for list_graph_memberships."""

    @staticmethod
    def test_returns_sorted_member_descriptors() -> None:
        """Returns sorted member descriptor strings."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        payload = {
            "value": [
                {
                    "containerDescriptor": _CONTAINER_DESCRIPTOR,
                    "memberDescriptor": "aad.zzz",
                },
                {
                    "containerDescriptor": _CONTAINER_DESCRIPTOR,
                    "memberDescriptor": "aad.aaa",
                },
            ]
        }
        mock_response = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list_graph_memberships(vssps_call, _CONTAINER_DESCRIPTOR)
        assert result == ["aad.aaa", "aad.zzz"]

    @staticmethod
    def test_returns_empty_list_when_no_response() -> None:
        """Returns empty list when API returns no body."""
        vssps_call = get_vssps_api_call(get_session(pat=ACCESS_TOKEN), "myorg")
        mock_response = _make_mock_response(None)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list_graph_memberships(vssps_call, _CONTAINER_DESCRIPTOR)
        assert result == []
