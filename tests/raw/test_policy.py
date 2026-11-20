"""Tests for pyado.raw.policy — branch policy configuration wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    PolicyConfigurationInfo,
    PolicyConfigurationRequest,
    PolicyCreatedBy,
    PolicyEvaluationStatus,
    PolicyScope,
    PolicyScopeMatchKind,
    PolicyType,
    PolicyTypeIdRef,
    delete_policy_configuration,
    get_policy_configuration,
    get_policy_configuration_api_call,
    get_policy_type,
    iter_policy_configurations,
    iter_policy_evaluations,
    iter_policy_types,
    list_policy_configurations,
    list_policy_evaluations,
    list_policy_types,
    make_pull_request_policy_artifact_id,
    post_policy_configuration,
    put_policy_configuration,
)
from tests.conftest import _make_mock_response

_TYPE_ID = "fa4e907d-c16b-452d-8106-7efa0cb84489"
_CONFIG_ID = 17


def _make_config_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": _CONFIG_ID,
        "isEnabled": True,
        "isBlocking": False,
        "type": {
            "id": _TYPE_ID,
            "displayName": "Minimum number of reviewers",
        },
        "settings": {"minimumApproverCount": 1},
    }
    base.update(overrides)
    return base


class TestListPolicyConfigurations:
    @staticmethod
    def test_returns_list_of_policy_configurations(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_make_config_dict()]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_configurations(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], PolicyConfigurationInfo)
        assert results[0].id == _CONFIG_ID
        assert results[0].is_enabled is True
        assert results[0].is_blocking is False

    @staticmethod
    def test_returns_empty_list_when_no_policies(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_configurations(api_call)
        assert results == []

    @staticmethod
    def test_policy_type_is_parsed(api_call: ApiCall) -> None:
        payload = {
            "value": [
                _make_config_dict(
                    type={
                        "id": _TYPE_ID,
                        "displayName": "Required reviewers",
                    }
                )
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_configurations(api_call)
        assert isinstance(results[0].type, PolicyType)
        assert results[0].type.id == UUID(_TYPE_ID)
        assert results[0].type.display_name == "Required reviewers"

    @staticmethod
    def test_optional_fields_are_populated_when_present(
        api_call: ApiCall,
    ) -> None:
        payload = {
            "value": [
                _make_config_dict(
                    isDeleted=False,
                    isEnterpriseManaged=True,
                    revision=3,
                    url="https://dev.azure.com/org/proj/_apis/policy/configurations/17",
                    createdDate="2023-01-12T15:32:50Z",
                    createdBy={
                        "id": "41abade2-6e57-64c3-8936-09e5e5309a71",
                        "displayName": "Alice",
                    },
                )
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_configurations(api_call)
        config = results[0]
        assert config.is_deleted is False
        assert config.is_enterprise_managed is True
        assert config.revision == 3
        assert config.url is not None
        assert config.created_date == "2023-01-12T15:32:50Z"
        assert isinstance(config.created_by, PolicyCreatedBy)
        assert config.created_by.display_name == "Alice"

    @staticmethod
    def test_optional_fields_default_when_absent(api_call: ApiCall) -> None:
        payload = {"value": [_make_config_dict()]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_configurations(api_call)
        config = results[0]
        assert config.is_deleted is False
        assert config.is_enterprise_managed is False
        assert config.revision is None
        assert config.url is None
        assert config.created_by is None
        assert config.created_date is None


class TestIterPolicyConfigurations:
    @staticmethod
    def test_yields_policy_configurations(api_call: ApiCall) -> None:
        payload = {
            "value": [
                _make_config_dict(
                    id=3,
                    isEnabled=False,
                    settings={"requireVoteOnLastIteration": True},
                )
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_policy_configurations(api_call))
        assert len(results) == 1
        assert isinstance(results[0], PolicyConfigurationInfo)
        assert results[0].settings == {"requireVoteOnLastIteration": True}


class TestGetPolicyConfiguration:
    @staticmethod
    def test_returns_single_configuration(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_make_config_dict())
        with patch.object(requests.Session, "request", return_value=mock_resp):
            config_api = get_policy_configuration_api_call(api_call, _CONFIG_ID)
            result = get_policy_configuration(config_api)
        assert isinstance(result, PolicyConfigurationInfo)
        assert result.id == _CONFIG_ID


class TestCreatePolicyConfiguration:
    @staticmethod
    def test_returns_created_configuration(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_make_config_dict(id=42))
        request = PolicyConfigurationRequest(
            is_enabled=True,
            is_blocking=False,
            type=PolicyTypeIdRef(id=UUID(_TYPE_ID)),
            settings={"minimumApproverCount": 2},
        )
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_policy_configuration(api_call, request)
        assert isinstance(result, PolicyConfigurationInfo)
        assert result.id == 42

    @staticmethod
    def test_request_serialises_type_as_nested_id(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_make_config_dict())
        request = PolicyConfigurationRequest(
            is_enabled=True,
            is_blocking=True,
            type=PolicyTypeIdRef(id=UUID(_TYPE_ID)),
            settings={},
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_request:
            post_policy_configuration(api_call, request)
        call_kwargs = mock_request.call_args
        sent_json = call_kwargs.kwargs.get("json") or call_kwargs.args[2]
        assert sent_json["type"]["id"] == _TYPE_ID
        assert sent_json["isEnabled"] is True
        assert sent_json["isBlocking"] is True


class TestUpdatePolicyConfiguration:
    @staticmethod
    def test_returns_updated_configuration(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_make_config_dict(isBlocking=True, revision=2))
        request = PolicyConfigurationRequest(
            is_enabled=True,
            is_blocking=True,
            type=PolicyTypeIdRef(id=UUID(_TYPE_ID)),
            settings={"minimumApproverCount": 3},
        )
        with patch.object(requests.Session, "request", return_value=mock_resp):
            config_api = get_policy_configuration_api_call(api_call, _CONFIG_ID)
            result = put_policy_configuration(config_api, request)
        assert isinstance(result, PolicyConfigurationInfo)
        assert result.revision == 2


class TestDeletePolicyConfiguration:
    @staticmethod
    def test_returns_none(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            config_api = get_policy_configuration_api_call(api_call, _CONFIG_ID)
            delete_policy_configuration(config_api)


class TestListPolicyTypes:
    @staticmethod
    def test_returns_list_when_value_wrapped(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "id": _TYPE_ID,
                    "displayName": "Minimum number of reviewers",
                    "description": "Require a minimum number of reviewers.",
                    "url": "https://dev.azure.com/org/proj/_apis/policy/types/fa4e907d",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_types(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], PolicyType)
        assert results[0].id == UUID(_TYPE_ID)
        assert results[0].description == "Require a minimum number of reviewers."

    @staticmethod
    def test_returns_list_when_array_response(api_call: ApiCall) -> None:
        payload = [
            {
                "id": _TYPE_ID,
                "displayName": "Minimum number of reviewers",
            }
        ]
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_types(api_call)
        assert len(results) == 1
        assert results[0].display_name == "Minimum number of reviewers"

    @staticmethod
    def test_returns_empty_list_when_no_types(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_policy_types(api_call)
        assert results == []


class TestIterPolicyTypes:
    @staticmethod
    def test_yields_policy_types(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "id": _TYPE_ID,
                    "displayName": "Build",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_policy_types(api_call))
        assert len(results) == 1
        assert isinstance(results[0], PolicyType)


class TestGetPolicyType:
    @staticmethod
    def test_returns_single_type(api_call: ApiCall) -> None:
        payload = {
            "id": _TYPE_ID,
            "displayName": "Required reviewers",
            "description": "Require specific reviewers on pull requests.",
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_policy_type(api_call, UUID(_TYPE_ID))
        assert isinstance(result, PolicyType)
        assert result.id == UUID(_TYPE_ID)
        assert result.display_name == "Required reviewers"
        assert result.description == "Require specific reviewers on pull requests."


_REPO_ID = UUID("bc255735-8b6e-436c-9c08-2554416a23ba")


class TestPolicyScopeMatchKind:
    @staticmethod
    def test_enum_values() -> None:
        assert PolicyScopeMatchKind.EXACT.value == "Exact"
        assert PolicyScopeMatchKind.PREFIX.value == "Prefix"
        assert PolicyScopeMatchKind.DEFAULT_BRANCH.value == "DefaultBranch"


class TestPolicyScope:
    @staticmethod
    def test_for_branch_exact_match() -> None:
        scope = PolicyScope.for_branch(_REPO_ID, "refs/heads/main")
        assert scope.repository_id == _REPO_ID
        assert scope.ref_name == "refs/heads/main"
        assert scope.match_kind == PolicyScopeMatchKind.EXACT

    @staticmethod
    def test_for_branch_custom_match_kind() -> None:
        scope = PolicyScope.for_branch(
            _REPO_ID, "refs/heads/", PolicyScopeMatchKind.PREFIX
        )
        assert scope.match_kind == PolicyScopeMatchKind.PREFIX

    @staticmethod
    def test_for_default_branch() -> None:
        scope = PolicyScope.for_default_branch(_REPO_ID)
        assert scope.repository_id == _REPO_ID
        assert scope.ref_name is None
        assert scope.match_kind == PolicyScopeMatchKind.DEFAULT_BRANCH

    @staticmethod
    def test_for_all_branches() -> None:
        scope = PolicyScope.for_all_branches(_REPO_ID)
        assert scope.repository_id == _REPO_ID
        assert scope.ref_name == "refs/heads/"
        assert scope.match_kind == PolicyScopeMatchKind.PREFIX

    @staticmethod
    def test_serializes_with_camel_case_aliases() -> None:
        scope = PolicyScope.for_branch(_REPO_ID, "refs/heads/main")
        data = scope.model_dump(by_alias=True, exclude_none=True)
        assert data == {
            "repositoryId": _REPO_ID,
            "refName": "refs/heads/main",
            "matchKind": "Exact",
        }

    @staticmethod
    def test_deserializes_branch_scope_from_ado_response() -> None:
        raw_data = {
            "repositoryId": str(_REPO_ID),
            "refName": "refs/heads/development",
            "matchKind": "Exact",
        }
        scope = PolicyScope.model_validate(raw_data)
        assert scope.repository_id == _REPO_ID
        assert scope.ref_name == "refs/heads/development"
        assert scope.match_kind == PolicyScopeMatchKind.EXACT

    @staticmethod
    def test_deserializes_repo_wide_scope_from_ado_response() -> None:
        raw_data = {"repositoryId": str(_REPO_ID)}
        scope = PolicyScope.model_validate(raw_data)
        assert scope.repository_id == _REPO_ID
        assert scope.ref_name is None
        assert scope.match_kind is None


def _make_evaluation_dict(
    status: str = "approved", *, blocking: bool = True
) -> dict[str, Any]:
    return {
        "evaluationId": "11111111-2222-3333-4444-555555555555",
        "status": status,
        "configuration": {
            "id": _CONFIG_ID,
            "isBlocking": blocking,
            "type": {"id": _TYPE_ID, "displayName": "Build"},
        },
        "startedDate": "2026-01-01T00:00:00Z",
    }


class TestPolicyEvaluations:
    """Tests for the policy evaluation endpoints."""

    @staticmethod
    def test_artifact_id_format() -> None:
        """The PR artifact id follows the vstfs CodeReview format."""
        assert make_pull_request_policy_artifact_id("proj-guid", 7) == (
            "vstfs:///CodeReview/CodeReviewId/proj-guid/7"
        )

    @staticmethod
    def test_iter_parses_evaluations_and_sends_artifact_id(api_call: ApiCall) -> None:
        """Evaluations are parsed and artifactId is forwarded as a parameter."""
        response = _make_mock_response(
            {
                "value": [
                    _make_evaluation_dict("approved"),
                    _make_evaluation_dict("notApplicable", blocking=False),
                ]
            }
        )
        with patch.object(requests.Session, "request", return_value=response) as m:
            result = list(iter_policy_evaluations(api_call, "art-1"))
        assert [e.status for e in result] == [
            PolicyEvaluationStatus.APPROVED,
            PolicyEvaluationStatus.NOT_APPLICABLE,
        ]
        assert result[0].configuration.is_blocking is True
        assert result[0].configuration.type.display_name == "Build"
        assert m.call_args.kwargs["params"]["artifactId"] == "art-1"
        assert m.call_args.kwargs["url"].endswith("/policy/evaluations")

    @staticmethod
    def test_list_returns_list(api_call: ApiCall) -> None:
        """list_policy_evaluations materialises the iterator."""
        response = _make_mock_response({"value": [_make_evaluation_dict()]})
        with patch.object(requests.Session, "request", return_value=response):
            assert len(list_policy_evaluations(api_call, "art-1")) == 1

    @staticmethod
    def test_iter_handles_missing_value(api_call: ApiCall) -> None:
        """A response without ``value`` yields nothing."""
        response = _make_mock_response({"count": 0})
        with patch.object(requests.Session, "request", return_value=response):
            assert list(iter_policy_evaluations(api_call, "art-1")) == []
