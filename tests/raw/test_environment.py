"""Tests for pyado.raw.environment — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado.raw import (
    ApiCall,
    ApprovalCheckSettings,
    EnvironmentCheckInfo,
    EnvironmentDeploymentRecord,
    EnvironmentInfo,
    get_environment,
    get_environment_api_call,
    iter_environment_checks,
    iter_environment_deployments,
    list_environment_checks,
    list_environment_deployments,
    list_environments,
)
from tests.conftest import _make_mock_response


class TestListEnvironments:
    @staticmethod
    def test_returns_list_of_environment_infos(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": 1,
                    "name": "prod",
                    "createdBy": {
                        "id": "abc",
                        "displayName": "Alice",
                        "uniqueName": "alice@example.com",
                    },
                    "lastModifiedBy": {"id": "abc", "displayName": "Alice"},
                    "project": {"id": "p1", "name": "MyProject"},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environments(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], EnvironmentInfo)
        assert results[0].created_by is not None
        assert results[0].created_by.display_name == "Alice"
        assert results[0].project is not None
        assert results[0].project.name == "MyProject"

    @staticmethod
    def test_returns_environment_without_optional_fields(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [{"id": 1, "name": "prod"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environments(api_call)
        assert results[0].created_by is None
        assert results[0].last_modified_by is None
        assert results[0].project is None


class TestListEnvironmentDeployments:
    @staticmethod
    def test_returns_list_of_deployment_records(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [{"id": 7, "definitionName": "CI"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environment_deployments(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], EnvironmentDeploymentRecord)

    @staticmethod
    def test_passes_top_parameter(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            list_environment_deployments(api_call, top=3)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("top") == 3


class TestIterEnvironmentDeployments:
    @staticmethod
    def test_yields_deployment_records(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [{"id": 1, "definitionName": "MyPipeline"}],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_environment_deployments(api_call))
        assert len(results) == 1
        assert isinstance(results[0], EnvironmentDeploymentRecord)

    @staticmethod
    def test_passes_top_parameter_when_given(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            list(iter_environment_deployments(api_call, top=5))
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs.get("params") or {}
        assert params.get("top") == 5

    @staticmethod
    def test_no_top_parameter_when_not_given(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            list(iter_environment_deployments(api_call))
        call_kwargs = mock_req.call_args.kwargs
        params = call_kwargs.get("params") or {}
        assert "top" not in params


class TestGetEnvironmentApiCall:
    @staticmethod
    def test_returns_api_call(api_call: ApiCall) -> None:
        result = get_environment_api_call(api_call, 3)
        assert isinstance(result, ApiCall)


class TestGetEnvironment:
    @staticmethod
    def test_returns_environment_info(api_call: ApiCall) -> None:
        payload = {"id": 3, "name": "staging"}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_environment(api_call, 3)
        assert isinstance(result, EnvironmentInfo)
        assert result.id == 3
        assert result.name == "staging"


class TestListEnvironmentChecks:
    @staticmethod
    def test_returns_list_of_checks(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": 10,
                    "type": {"id": "abc", "name": "Approval"},
                    "settings": {
                        "approvers": [{"id": "user-1", "displayName": "Alice"}],
                        "instructions": "Please review",
                        "requesterCannotBeApprover": True,
                        "requiredApproverCount": 1,
                        "allowApproversToApproveTheirOwnRuns": False,
                    },
                    "timeout": 43200,
                    "createdBy": {"id": "user-1", "displayName": "Alice"},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environment_checks(api_call, 5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], EnvironmentCheckInfo)
        assert results[0].id == 10
        assert results[0].type.name == "Approval"
        assert results[0].timeout == 43200
        assert results[0].settings is not None
        assert results[0].settings.approvers[0].display_name == "Alice"

    @staticmethod
    def test_returns_empty_list_when_no_checks(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environment_checks(api_call, 5)
        assert results == []

    @staticmethod
    def test_check_without_optional_fields(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "id": 11,
                    "type": {"id": "def", "name": "InvokeRestAPI"},
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_environment_checks(api_call, 5)
        assert results[0].timeout is None
        assert results[0].created_by is None
        assert results[0].settings is None

    @staticmethod
    def test_passes_resource_parameters(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            list_environment_checks(api_call, 7)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("resourceType") == "environment"
        assert params.get("resourceId") == 7


class TestIterEnvironmentChecks:
    @staticmethod
    def test_yields_checks(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {"id": 20, "type": {"id": "xyz", "name": "Approval"}},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_environment_checks(api_call, 5))
        assert len(results) == 1
        assert isinstance(results[0], EnvironmentCheckInfo)


class TestApprovalCheckSettings:
    @staticmethod
    def test_defaults() -> None:
        settings = ApprovalCheckSettings()
        assert settings.approvers == []
        assert not settings.instructions
        assert settings.required_approver_count == 1
