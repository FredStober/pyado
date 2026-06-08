"""Tests for pyado.raw.process — process info wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    ProcessBehaviorField,
    ProcessBehaviorInfo,
    ProcessDetail,
    ProcessWITField,
    ProcessWITInfo,
    ProcessWITRule,
    ProcessWITState,
    ProjectFieldInfo,
    get_process_info,
)
from tests.conftest import _make_mock_response

_PROCESS_ID = "adcc42ab-9882-485e-a3ed-7678f01f66bc"


class TestGetProcessInfo:
    @staticmethod
    def test_returns_process_detail_with_all_sub_resources(
        api_call: ApiCall,
    ) -> None:
        process_payload = {
            "typeId": _PROCESS_ID,
            "name": "Agile",
            "referenceName": "Agile",
            "parentProcessTypeId": "adcc42ab-9882-485e-a3ed-000000000000",
            "isEnabled": True,
            "customizationType": "inherited",
        }
        wits_payload = {
            "value": [
                {
                    "name": "User Story",
                    "referenceName": "Microsoft.VSTS.WorkItemTypes.UserStory",
                }
            ]
        }
        states_payload = {"value": [{"name": "Active", "stateCategory": "InProgress"}]}
        rules_payload: dict[str, object] = {"value": []}
        wit_fields_payload = {
            "value": [
                {"name": "Title", "referenceName": "System.Title", "type": "string"}
            ]
        }
        behaviors_payload = {
            "value": [
                {
                    "name": "Backlog",
                    "referenceName": "System.RequirementBacklogBehavior",
                }
            ]
        }
        project_fields_payload = {
            "value": [
                {
                    "name": "Priority",
                    "referenceName": "Microsoft.VSTS.Common.Priority",
                    "type": "integer",
                }
            ]
        }

        responses = [
            _make_mock_response(process_payload),
            _make_mock_response(wits_payload),
            _make_mock_response(states_payload),
            _make_mock_response(rules_payload),
            _make_mock_response(wit_fields_payload),
            _make_mock_response(behaviors_payload),
            _make_mock_response(project_fields_payload),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            result = get_process_info(api_call, api_call, UUID(_PROCESS_ID))

        assert isinstance(result, ProcessDetail)
        assert result.type_id == UUID(_PROCESS_ID)
        assert result.name == "Agile"
        assert result.reference_name == "Agile"
        assert result.parent_process_type_id == "adcc42ab-9882-485e-a3ed-000000000000"
        assert result.is_enabled is True
        assert result.customization_type == "inherited"
        assert len(result.work_item_types) == 1
        assert isinstance(result.work_item_types[0], ProcessWITInfo)
        assert result.work_item_types[0].name == "User Story"
        assert len(result.work_item_types[0].states) == 1
        assert isinstance(result.work_item_types[0].states[0], ProcessWITState)
        assert result.work_item_types[0].states[0].name == "Active"
        assert result.work_item_types[0].states[0].state_category == "InProgress"
        assert len(result.work_item_types[0].rules) == 0
        assert len(result.work_item_types[0].fields) == 1
        assert isinstance(result.work_item_types[0].fields[0], ProcessWITField)
        assert result.work_item_types[0].fields[0].name == "Title"
        assert len(result.behaviors) == 1
        assert isinstance(result.behaviors[0], ProcessBehaviorInfo)
        assert result.behaviors[0].name == "Backlog"
        assert len(result.project_fields) == 1
        assert isinstance(result.project_fields[0], ProjectFieldInfo)
        assert result.project_fields[0].name == "Priority"

    @staticmethod
    def test_returns_process_detail_with_empty_sub_resources(
        api_call: ApiCall,
    ) -> None:
        process_payload = {
            "typeId": _PROCESS_ID,
            "name": "Scrum",
            "customizationType": "system",
        }
        empty: dict[str, object] = {"value": []}

        # Calls: process detail, WITs (empty), behaviors (empty), project fields (empty)
        responses = [
            _make_mock_response(process_payload),
            _make_mock_response(empty),
            _make_mock_response(empty),
            _make_mock_response(empty),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            result = get_process_info(api_call, api_call, UUID(_PROCESS_ID))

        assert isinstance(result, ProcessDetail)
        assert result.work_item_types == []
        assert result.behaviors == []
        assert result.project_fields == []

    @staticmethod
    def test_process_detail_optional_fields_default(api_call: ApiCall) -> None:
        process_payload = {"typeId": _PROCESS_ID, "name": "Minimal"}
        empty: dict[str, object] = {"value": []}

        # Calls: process detail, WITs (empty), behaviors (empty), project fields (empty)
        responses = [
            _make_mock_response(process_payload),
            _make_mock_response(empty),
            _make_mock_response(empty),
            _make_mock_response(empty),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            result = get_process_info(api_call, api_call, UUID(_PROCESS_ID))

        assert not result.description
        assert result.reference_name is None
        assert result.parent_process_type_id is None
        assert result.is_enabled is True
        assert result.customization_type is None
        assert result.is_default is False

    @staticmethod
    def test_returns_typed_rule_with_conditions_and_actions(
        api_call: ApiCall,
    ) -> None:
        process_payload = {"typeId": _PROCESS_ID, "name": "Agile"}
        wits_payload = {
            "value": [
                {"name": "Bug", "referenceName": "Microsoft.VSTS.WorkItemTypes.Bug"}
            ]
        }
        states_payload: dict[str, object] = {"value": []}
        rules_payload = {
            "value": [
                {
                    "id": "rule-1",
                    "name": "Set state on resolve",
                    "isSystem": True,
                    "isDisabled": False,
                    "conditions": [
                        {"conditionType": "when", "field": "State", "value": "Resolved"}
                    ],
                    "actions": [
                        {
                            "actionType": "setFieldValue",
                            "targetField": "Reason",
                            "value": "Fixed",
                        }
                    ],
                }
            ]
        }
        fields_payload: dict[str, object] = {"value": []}
        behaviors_payload: dict[str, object] = {"value": []}
        project_fields_payload: dict[str, object] = {"value": []}

        responses = [
            _make_mock_response(process_payload),
            _make_mock_response(wits_payload),
            _make_mock_response(states_payload),
            _make_mock_response(rules_payload),
            _make_mock_response(fields_payload),
            _make_mock_response(behaviors_payload),
            _make_mock_response(project_fields_payload),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            result = get_process_info(api_call, api_call, UUID(_PROCESS_ID))

        rule = result.work_item_types[0].rules[0]
        assert isinstance(rule, ProcessWITRule)
        assert rule.name == "Set state on resolve"
        assert rule.is_system is True
        assert rule.conditions[0].condition_type == "when"
        assert rule.actions[0].action_type == "setFieldValue"

    @staticmethod
    def test_returns_typed_behavior_fields(
        api_call: ApiCall,
    ) -> None:
        process_payload = {"typeId": _PROCESS_ID, "name": "Agile"}
        wits_payload: dict[str, object] = {"value": []}
        behaviors_payload = {
            "value": [
                {
                    "name": "Backlog",
                    "referenceName": "System.RequirementBacklogBehavior",
                    "fields": [
                        {
                            "name": "Story Points",
                            "referenceName": "Microsoft.VSTS.Scheduling.StoryPoints",
                            "defaultValue": "0",
                        }
                    ],
                }
            ]
        }
        project_fields_payload: dict[str, object] = {"value": []}

        responses = [
            _make_mock_response(process_payload),
            _make_mock_response(wits_payload),
            _make_mock_response(behaviors_payload),
            _make_mock_response(project_fields_payload),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            result = get_process_info(api_call, api_call, UUID(_PROCESS_ID))

        behavior_field = result.behaviors[0].fields[0]
        assert isinstance(behavior_field, ProcessBehaviorField)
        assert behavior_field.name == "Story Points"
        assert behavior_field.reference_name == "Microsoft.VSTS.Scheduling.StoryPoints"
        assert behavior_field.default_value == "0"
