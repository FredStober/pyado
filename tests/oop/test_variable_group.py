"""Tests for pyado.oop.pipelines._variable_group — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from pyado.oop import Project, VariableGroup
from pyado.oop.pipelines._variable_group import update_variable_group
from pyado.raw import (
    ApiCall,
    VariableGroupInfo,
    VariableGroupProjectReference,
    VariableInfo,
    get_variable_group_api_call,
)
from tests.conftest import NOW_ISO, _make_mock_response
from tests.oop.conftest import (
    _api_call,
    _make_project,
    _make_service,
    _make_variable_group,
    _project_info,
    _variable_group_info,
)

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


# ---------------------------------------------------------------------------
# OOP VariableGroup tests
# ---------------------------------------------------------------------------


class TestVariableGroup:
    def test_id(self) -> None:
        assert _make_variable_group(group_id=3).id == 3

    def test_name(self) -> None:
        assert _make_variable_group(name="StagingVars").name == "StagingVars"

    def test_variables(self) -> None:
        vg = _make_variable_group()
        assert "FOO" in vg.variables
        assert vg.variables["FOO"].value == "bar"

    def test_info_returns_info(self) -> None:
        vg = _make_variable_group(group_id=9)
        assert vg.info.id == 9

    def test_api_call_accessible(self) -> None:
        api = _api_call()
        proj = _make_project()
        vg = VariableGroup(proj, api, _variable_group_info())
        assert vg.api_call is api

    def test_project_reference(self) -> None:
        proj = _make_project()
        vg = VariableGroup(proj, _api_call(), _variable_group_info())
        assert vg.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        vg = VariableGroup(proj, _api_call(), _variable_group_info())
        assert vg.org is svc.org

    def test_update_delegates(self) -> None:
        vg = _make_variable_group()
        new_vars = {"BAR": VariableInfo(value="baz")}
        updated_info = _variable_group_info()
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = updated_info
            vg.update(new_vars)
        mock_upd.assert_called_once()
        call = mock_upd.call_args
        assert call.args[2] is new_vars

    def test_update_uses_current_name_by_default(self) -> None:
        vg = _make_variable_group(name="OrigName")
        updated_info = _variable_group_info(name="OrigName")
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = updated_info
            vg.update({})
        call = mock_upd.call_args
        assert call.args[1] == "OrigName"

    def test_update_with_new_name(self) -> None:
        vg = _make_variable_group(name="OldName")
        updated_info = _variable_group_info(name="NewName")
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = updated_info
            vg.update({}, name="NewName")
        call = mock_upd.call_args
        assert call.args[1] == "NewName"

    def test_update_stores_returned_info(self) -> None:
        vg = _make_variable_group()
        new_info = _variable_group_info(group_id=1, name="Updated")
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = new_info
            vg.update({})
        assert vg._info is new_info

    def test_set_variable_merges_and_updates(self) -> None:
        vg = _make_variable_group()
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.set_variable("NEW_KEY", "new-val")
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert "FOO" in new_vars  # existing variable preserved
        assert "NEW_KEY" in new_vars
        assert new_vars["NEW_KEY"].value == "new-val"

    def test_set_variable_secret_flag(self) -> None:
        vg = _make_variable_group()
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.set_variable("SECRET", "s3cr3t", is_secret=True)
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert new_vars["SECRET"].is_secret is True

    def test_unset_variable_removes_key(self) -> None:
        vg = _make_variable_group()
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.unset_variable("FOO")
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert "FOO" not in new_vars

    def test_unset_variable_missing_raises(self) -> None:
        vg = _make_variable_group()
        with pytest.raises(KeyError):
            vg.unset_variable("NONEXISTENT")

    def test_update_uses_existing_project_refs_when_present(self) -> None:
        """_project_refs() returns existing refs when the list is non-empty."""
        proj = _make_project()
        ref = VariableGroupProjectReference.model_validate(
            {
                "name": "MyVars",
                "projectReference": {"id": str(proj.id), "name": proj.name},
            }
        )
        info = VariableGroupInfo.model_validate(
            {
                "id": 1,
                "name": "MyVars",
                "type": "Vsts",
                "variables": {},
                "createdBy": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "displayName": "U",
                    "uniqueName": "u@x.com",
                },
                "createdOn": NOW_ISO,
                "modifiedBy": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "displayName": "U",
                    "uniqueName": "u@x.com",
                },
                "modifiedOn": NOW_ISO,
                "isShared": False,
                "variableGroupProjectReferences": [ref.model_dump(by_alias=True)],
            }
        )
        vg = VariableGroup(proj, _api_call(), info)
        with patch(
            "pyado.oop.pipelines.variable_group._variable_group.update_variable_group"
        ) as mock_upd:
            mock_upd.return_value = info
            vg.update({})
        call = mock_upd.call_args
        passed_refs = call.args[3]
        assert passed_refs == [ref]

    def test_refresh_updates_info(self) -> None:
        vg = _make_variable_group(group_id=1)
        refreshed = _variable_group_info(group_id=1, name="Refreshed")
        with patch(
            "pyado.oop.pipelines.variable_group.raw.get_variable_group_details"
        ) as mock_get:
            mock_get.return_value = refreshed
            vg.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = vg.info
        mock_get.assert_called_once_with(vg.api_call)
        assert vg._info is refreshed

    def test_delete_delegates(self) -> None:
        vg = _make_variable_group()
        with patch(
            "pyado.oop.pipelines.variable_group.raw.delete_variable_group"
        ) as mock_del:
            vg.delete()
        mock_del.assert_called_once_with(
            vg._project._service.api_call,
            vg.id,
            [str(vg._project.id)],
        )
