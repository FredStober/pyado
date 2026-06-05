"""Tests for pyado.variable_group module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import requests

from pyado.raw import (
    ApiCall,
    VariableGroupCreateRequest,
    VariableGroupInfo,
    VariableGroupProjectReference,
    VariableGroupUpdateRequest,
    VariableInfo,
    delete_variable_group,
    get_variable_group_details,
    iter_variable_group_details,
    list_variable_group_details,
    post_variable_group,
    put_variable_group,
)
from tests.conftest import NOW_ISO, _make_mock_response


def make_variable_group_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid VariableGroupInfo dict.

    Returns:
        A dict with all required VariableGroupInfo fields populated.
    """
    user = {
        "id": str(uuid4()),
        "displayName": "Test User",
        "uniqueName": "test@org.com",
    }
    vg: dict[str, Any] = {
        "createdBy": user,
        "createdOn": NOW_ISO,
        "description": None,
        "id": 1,
        "isShared": False,
        "modifiedBy": user,
        "modifiedOn": NOW_ISO,
        "name": "MyVarGroup",
        "type": "Vsts",
        "variableGroupProjectReferences": [],
        "variables": {
            "MY_VAR": {"value": "hello", "isSecret": False},
            "SECRET_VAR": {"value": None, "isSecret": True},
        },
    }
    vg.update(overrides)
    return vg


class TestIterVariableGroupDetails:
    """Tests for iter_variable_group_details."""

    @staticmethod
    def test_yields_variable_group_info_objects(api_call: ApiCall) -> None:
        """Yields VariableGroupInfo objects from the API response."""
        vg = make_variable_group_dict()
        mock_response = _make_mock_response({"value": [vg]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert len(result) == 1
        assert isinstance(result[0], VariableGroupInfo)
        assert result[0].name == "MyVarGroup"

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no variable groups."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert result == []

    @staticmethod
    def test_variable_group_contains_variables(api_call: ApiCall) -> None:
        """VariableGroupInfo correctly parses variables dict."""
        vg = make_variable_group_dict()
        mock_response = _make_mock_response({"value": [vg]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        variables = result[0].variables
        assert "MY_VAR" in variables
        assert variables["MY_VAR"].value == "hello"
        assert variables["MY_VAR"].is_secret is False
        assert variables["SECRET_VAR"].is_secret is True


class TestGetVariableGroupDetails:
    """Tests for get_variable_group_details."""

    @staticmethod
    def test_returns_variable_group_info(api_call: ApiCall) -> None:
        """Returns a VariableGroupInfo parsed from the API GET response."""
        vg = make_variable_group_dict()
        mock_response = _make_mock_response(vg)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_variable_group_details(api_call)
        assert isinstance(result, VariableGroupInfo)
        assert result.name == "MyVarGroup"

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Issues a GET request to the variable group endpoint."""
        mock_response = _make_mock_response(make_variable_group_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_variable_group_details(api_call)
        assert mock_req.call_args.args[0] == "GET"


class TestPostVariableGroup:
    """Tests for post_variable_group."""

    @staticmethod
    def _make_request() -> VariableGroupCreateRequest:
        ref = VariableGroupProjectReference.model_validate(
            {
                "name": "NewGroup",
                "projectReference": {
                    "id": str(uuid4()),
                    "name": "TestProject",
                },
            }
        )
        return VariableGroupCreateRequest(
            name="NewGroup",
            variables={"FOO": VariableInfo(value="bar")},
            variable_group_project_references=[ref],
        )

    def test_returns_variable_group_info(self, api_call: ApiCall) -> None:
        """Returns a VariableGroupInfo parsed from the API POST response."""
        vg = make_variable_group_dict(name="NewGroup")
        mock_response = _make_mock_response(vg)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_variable_group(api_call, self._make_request())
        assert isinstance(result, VariableGroupInfo)
        assert result.name == "NewGroup"

    def test_sends_post_request(self, api_call: ApiCall) -> None:
        """Issues a POST request to the variable groups endpoint."""
        mock_response = _make_mock_response(make_variable_group_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_variable_group(api_call, self._make_request())
        assert mock_req.call_args.args[0] == "POST"

    def test_excludes_none_fields_from_payload(self, api_call: ApiCall) -> None:
        """None optional fields (description, providerData) are omitted from POST."""
        mock_response = _make_mock_response(make_variable_group_dict(name="NewGroup"))
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_variable_group(api_call, self._make_request())
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "description" not in sent_json
        assert "providerData" not in sent_json


class TestPutVariableGroup:
    """Tests for put_variable_group."""

    @staticmethod
    def _make_update_request() -> VariableGroupUpdateRequest:
        return VariableGroupUpdateRequest(
            name="UpdatedGroup",
            variables={"FOO": VariableInfo(value="bar")},
        )

    def test_returns_variable_group_info(self, api_call: ApiCall) -> None:
        """Returns a VariableGroupInfo parsed from the API PUT response."""
        vg = make_variable_group_dict(name="UpdatedGroup")
        mock_response = _make_mock_response(vg)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = put_variable_group(api_call, self._make_update_request())
        assert isinstance(result, VariableGroupInfo)
        assert result.name == "UpdatedGroup"

    def test_sends_put_request(self, api_call: ApiCall) -> None:
        """Issues a PUT request to the variable group endpoint."""
        mock_response = _make_mock_response(make_variable_group_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            put_variable_group(api_call, self._make_update_request())
        assert mock_req.call_args.args[0] == "PUT"

    def test_excludes_none_fields_from_payload(self, api_call: ApiCall) -> None:
        """None optional fields (description, providerData) are omitted from PUT."""
        mock_response = _make_mock_response(make_variable_group_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            put_variable_group(api_call, self._make_update_request())
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "description" not in sent_json
        assert "providerData" not in sent_json


class TestDeleteVariableGroup:
    """Tests for delete_variable_group."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Issues a DELETE request to the variable group endpoint."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_variable_group(api_call)
        assert mock_req.call_args.args[0] == "DELETE"


class TestVariableInfo:
    """Tests for VariableInfo model."""

    @staticmethod
    def test_default_is_not_secret() -> None:
        """VariableInfo defaults is_secret to False."""
        info = VariableInfo(value="hello")
        assert info.is_secret is False

    @staticmethod
    def test_secret_variable() -> None:
        """VariableInfo with is_secret=True and no value."""
        info = VariableInfo(is_secret=True)
        assert info.is_secret is True
        assert info.value is None


# ---------------------------------------------------------------------------
# Smoke tests — real API response shapes
# ---------------------------------------------------------------------------

_VARIABLE_GROUPS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "variables": {"test": {"value": "test"}},
            "id": 1,
            "type": "Vsts",
            "name": "smoke-test-group",
            "description": "",
            "createdBy": {
                "displayName": "Test User",
                "id": "94820a06-c555-463f-a9ef-41d0deea959e",
                "uniqueName": "testuser@example.com",
            },
            "createdOn": "2026-06-02T11:58:28.7633333Z",
            "modifiedBy": {
                "displayName": "Test User",
                "id": "94820a06-c555-463f-a9ef-41d0deea959e",
                "uniqueName": "testuser@example.com",
            },
            "modifiedOn": "2026-06-02T12:57:02.47Z",
            "isShared": False,
            "variableGroupProjectReferences": None,
        }
    ],
}


class TestSmokeIterVariableGroupDetails:
    """iter_variable_group_details parses real variable group response shapes."""

    @staticmethod
    def test_parses_group_with_null_project_references(
        api_call: ApiCall,
    ) -> None:
        """Variable group with variableGroupProjectReferences=null parses."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert len(result) == 1
        assert isinstance(result[0], VariableGroupInfo)
        assert result[0].id == 1
        assert result[0].name == "smoke-test-group"

    @staticmethod
    def test_variable_group_refs_is_none(api_call: ApiCall) -> None:
        """variable_group_refs field is None when API returns null."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert result[0].variable_group_refs is None

    @staticmethod
    def test_variables_dict_parsed(api_call: ApiCall) -> None:
        """Variables dict with a single key-value entry is accessible."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert "test" in result[0].variables
        assert result[0].variables["test"].value == "test"


class TestListVariableGroupDetails:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.variable_group.iter_variable_group_details",
            return_value=iter([]),
        ) as m:
            result = list_variable_group_details(api_call)
        assert result == []
        m.assert_called_once_with(api_call)
