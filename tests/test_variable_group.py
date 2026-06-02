"""Tests for pyado.variable_group module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from pyado import (
    ApiCall,
    VariableGroupInfo,
    VariableInfo,
    get_variable_group_api_call,
    iter_variable_group_details,
    update_variable_group,
)
from tests.conftest import NOW_ISO, _make_mock_response

VAR_GROUP_ID = 1


@pytest.fixture
def var_group_api_call(api_call: ApiCall) -> ApiCall:
    """Return a variable-group-level ApiCall.

    Returns:
        A variable-group-level ApiCall for testing.
    """
    return get_variable_group_api_call(api_call, VAR_GROUP_ID)


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


class TestUpdateVariableGroupEntries:
    """Tests for put_variable_group."""

    @staticmethod
    def test_returns_updated_variable_group_info(var_group_api_call: ApiCall) -> None:
        """Returns a VariableGroupInfo parsed from the API PUT response."""
        vg = make_variable_group_dict(name="UpdatedGroup")
        mock_response = _make_mock_response(vg)
        variables = {"NEW_VAR": VariableInfo(value="new_val")}
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = update_variable_group(
                var_group_api_call, "UpdatedGroup", variables
            )
        assert isinstance(result, VariableGroupInfo)
        assert result.name == "UpdatedGroup"

    @staticmethod
    def test_sends_put_request(var_group_api_call: ApiCall) -> None:
        """Issues a PUT request to the API."""
        vg = make_variable_group_dict()
        mock_response = _make_mock_response(vg)
        variables = {"VAR": VariableInfo(value="val")}
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_variable_group(var_group_api_call, "MyVarGroup", variables)
        mock_req.assert_called_once()
        assert mock_req.call_args.args[0] == "PUT"


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
