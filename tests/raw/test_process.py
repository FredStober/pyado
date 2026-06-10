"""Tests for pyado.raw.process — process info wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    ProcessBehaviorCreateRequest,
    ProcessBehaviorField,
    ProcessBehaviorInfo,
    ProcessBehaviorUpdateRequest,
    ProcessCreateRequest,
    ProcessDetail,
    ProcessUpdateRequest,
    ProcessWITInfo,
    ProcessWorkItemField,
    ProcessWorkItemRule,
    ProcessWorkItemState,
    ProcessWorkItemTypeCreateRequest,
    ProcessWorkItemTypeFieldAddRequest,
    ProcessWorkItemTypeFieldUpdateRequest,
    ProcessWorkItemTypeRuleAction,
    ProcessWorkItemTypeRuleCondition,
    ProcessWorkItemTypeRuleCreateRequest,
    ProcessWorkItemTypeRuleUpdateRequest,
    ProcessWorkItemTypeStateCreateRequest,
    ProcessWorkItemTypeStateUpdateRequest,
    ProcessWorkItemTypeUpdateRequest,
    ProjectFieldInfo,
    delete_behavior,
    delete_process,
    delete_work_item_type,
    delete_work_item_type_field,
    delete_work_item_type_rule,
    delete_work_item_type_state,
    get_process,
    get_process_info,
    iter_processes,
    list_processes,
    patch_behavior,
    patch_process,
    patch_work_item_type,
    patch_work_item_type_field,
    patch_work_item_type_rule,
    patch_work_item_type_state,
    post_behavior,
    post_process,
    post_work_item_type,
    post_work_item_type_field,
    post_work_item_type_rule,
    post_work_item_type_state,
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
        assert isinstance(result.work_item_types[0].states[0], ProcessWorkItemState)
        assert result.work_item_types[0].states[0].name == "Active"
        assert result.work_item_types[0].states[0].state_category == "InProgress"
        assert len(result.work_item_types[0].rules) == 0
        assert len(result.work_item_types[0].fields) == 1
        assert isinstance(result.work_item_types[0].fields[0], ProcessWorkItemField)
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
        assert isinstance(rule, ProcessWorkItemRule)
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


_WIT_REF = "Custom.MyType"
_STATE_ID = "state-uuid-1234"
_RULE_ID = "rule-uuid-5678"
_FIELD_REF = "Custom.MyField"
_BEHAVIOR_REF = "Custom.MyBehavior"

_PROCESS_PAYLOAD = {
    "typeId": _PROCESS_ID,
    "name": "MyProcess",
    "customizationType": "inherited",
}
_WIT_PAYLOAD = {"name": "My Type", "referenceName": _WIT_REF}
_STATE_PAYLOAD = {
    "name": "Active",
    "id": _STATE_ID,
    "stateCategory": "InProgress",
    "color": "00FF00",
}
_RULE_PAYLOAD = {"id": _RULE_ID, "name": "My Rule", "conditions": [], "actions": []}
_FIELD_PAYLOAD = {"name": "My Field", "referenceName": _FIELD_REF, "type": "string"}
_BEHAVIOR_PAYLOAD = {"name": "My Behavior", "referenceName": _BEHAVIOR_REF}


class TestGetProcess:
    @staticmethod
    def test_returns_process_detail(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_PROCESS_PAYLOAD)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_process(api_call, UUID(_PROCESS_ID))
        assert isinstance(result, ProcessDetail)
        assert result.type_id == UUID(_PROCESS_ID)
        assert result.name == "MyProcess"

    @staticmethod
    def test_process_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_PROCESS_PAYLOAD)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_process(api_call, UUID(_PROCESS_ID))
        assert _PROCESS_ID in mock_req.call_args.kwargs["url"]


class TestListProcesses:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_PROCESS_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = list_processes(api_call)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ProcessDetail)
        assert result[0].name == "MyProcess"

    @staticmethod
    def test_returns_empty_list(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = list_processes(api_call)
        assert result == []


class TestIterProcesses:
    @staticmethod
    def test_yields_processes(api_call: ApiCall) -> None:
        payload = {"value": [_PROCESS_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = list(iter_processes(api_call))
        assert len(result) == 1
        assert result[0].name == "MyProcess"


class TestPostProcess:
    @staticmethod
    def test_returns_process_detail(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_PROCESS_PAYLOAD)
        request = ProcessCreateRequest(
            name="MyProcess",
            parent_process_type_id=UUID(_PROCESS_ID),
        )
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_process(api_call, request)
        assert isinstance(result, ProcessDetail)
        assert result.name == "MyProcess"

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_PROCESS_PAYLOAD)
        request = ProcessCreateRequest(
            name="MyProcess",
            parent_process_type_id=UUID(_PROCESS_ID),
            description="A process",
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_process(api_call, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "MyProcess"
        assert "description" in sent_json


class TestPatchProcess:
    @staticmethod
    def test_returns_updated_process(api_call: ApiCall) -> None:
        updated = {**_PROCESS_PAYLOAD, "name": "Renamed Process"}
        mock_resp = _make_mock_response(updated)
        request = ProcessUpdateRequest(name="Renamed Process")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_process(api_call, UUID(_PROCESS_ID), request)
        assert isinstance(result, ProcessDetail)
        assert result.name == "Renamed Process"

    @staticmethod
    def test_process_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_PROCESS_PAYLOAD)
        request = ProcessUpdateRequest(name="X")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_process(api_call, UUID(_PROCESS_ID), request)
        assert _PROCESS_ID in mock_req.call_args.kwargs["url"]


class TestDeleteProcess:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_process(api_call, UUID(_PROCESS_ID))
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_process_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_process(api_call, UUID(_PROCESS_ID))
        assert _PROCESS_ID in mock_req.call_args.kwargs["url"]


class TestPostWorkItemType:
    @staticmethod
    def test_returns_wit_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_WIT_PAYLOAD)
        request = ProcessWorkItemTypeCreateRequest(name="My Type")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_work_item_type(api_call, UUID(_PROCESS_ID), request)
        assert isinstance(result, ProcessWITInfo)
        assert result.name == "My Type"

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_WIT_PAYLOAD)
        request = ProcessWorkItemTypeCreateRequest(name="My Type", description="desc")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_work_item_type(api_call, UUID(_PROCESS_ID), request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "My Type"


class TestPatchWorkItemType:
    @staticmethod
    def test_returns_updated_wit_info(api_call: ApiCall) -> None:
        updated = {**_WIT_PAYLOAD, "name": "Renamed Type"}
        mock_resp = _make_mock_response(updated)
        request = ProcessWorkItemTypeUpdateRequest(name="Renamed Type")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_work_item_type(
                api_call, UUID(_PROCESS_ID), _WIT_REF, request
            )
        assert isinstance(result, ProcessWITInfo)
        assert result.name == "Renamed Type"

    @staticmethod
    def test_wit_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_WIT_PAYLOAD)
        request = ProcessWorkItemTypeUpdateRequest(name="X")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_work_item_type(api_call, UUID(_PROCESS_ID), _WIT_REF, request)
        assert _WIT_REF in mock_req.call_args.kwargs["url"]


class TestDeleteWorkItemType:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type(api_call, UUID(_PROCESS_ID), _WIT_REF)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_wit_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type(api_call, UUID(_PROCESS_ID), _WIT_REF)
        assert _WIT_REF in mock_req.call_args.kwargs["url"]


class TestCreateWorkItemTypeState:
    @staticmethod
    def test_returns_wit_state(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_STATE_PAYLOAD)
        request = ProcessWorkItemTypeStateCreateRequest(name="Active", color="00FF00")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_work_item_type_state(
                api_call, UUID(_PROCESS_ID), _WIT_REF, request
            )
        assert isinstance(result, ProcessWorkItemState)
        assert result.name == "Active"
        assert result.id == _STATE_ID

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_STATE_PAYLOAD)
        request = ProcessWorkItemTypeStateCreateRequest(
            name="Active", color="00FF00", state_category="InProgress"
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_work_item_type_state(api_call, UUID(_PROCESS_ID), _WIT_REF, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "Active"


class TestUpdateWorkItemTypeState:
    @staticmethod
    def test_returns_updated_state(api_call: ApiCall) -> None:
        updated = {**_STATE_PAYLOAD, "name": "In Progress"}
        mock_resp = _make_mock_response(updated)
        request = ProcessWorkItemTypeStateUpdateRequest(name="In Progress")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_work_item_type_state(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _STATE_ID, request
            )
        assert isinstance(result, ProcessWorkItemState)
        assert result.name == "In Progress"

    @staticmethod
    def test_state_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_STATE_PAYLOAD)
        request = ProcessWorkItemTypeStateUpdateRequest(name="X")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_work_item_type_state(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _STATE_ID, request
            )
        assert _STATE_ID in mock_req.call_args.kwargs["url"]


class TestDeleteWorkItemTypeState:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_state(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _STATE_ID
            )
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_state_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_state(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _STATE_ID
            )
        assert _STATE_ID in mock_req.call_args.kwargs["url"]


class TestAddWorkItemTypeField:
    @staticmethod
    def test_returns_wit_field(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_FIELD_PAYLOAD)
        request = ProcessWorkItemTypeFieldAddRequest(reference_name=_FIELD_REF)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_work_item_type_field(
                api_call, UUID(_PROCESS_ID), _WIT_REF, request
            )
        assert isinstance(result, ProcessWorkItemField)
        assert result.reference_name == _FIELD_REF

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_FIELD_PAYLOAD)
        request = ProcessWorkItemTypeFieldAddRequest(
            reference_name=_FIELD_REF, is_required=True
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_work_item_type_field(api_call, UUID(_PROCESS_ID), _WIT_REF, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["referenceName"] == _FIELD_REF


class TestUpdateWorkItemTypeField:
    @staticmethod
    def test_returns_updated_field(api_call: ApiCall) -> None:
        updated = {**_FIELD_PAYLOAD, "isRequired": True}
        mock_resp = _make_mock_response(updated)
        request = ProcessWorkItemTypeFieldUpdateRequest(is_required=True)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_work_item_type_field(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _FIELD_REF, request
            )
        assert isinstance(result, ProcessWorkItemField)

    @staticmethod
    def test_field_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_FIELD_PAYLOAD)
        request = ProcessWorkItemTypeFieldUpdateRequest(is_required=True)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_work_item_type_field(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _FIELD_REF, request
            )
        assert _FIELD_REF in mock_req.call_args.kwargs["url"]


class TestRemoveWorkItemTypeField:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_field(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _FIELD_REF
            )
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_field_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_field(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _FIELD_REF
            )
        assert _FIELD_REF in mock_req.call_args.kwargs["url"]


class TestCreateWorkItemTypeRule:
    @staticmethod
    def test_returns_wit_rule(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_RULE_PAYLOAD)
        request = ProcessWorkItemTypeRuleCreateRequest(name="My Rule")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_work_item_type_rule(
                api_call, UUID(_PROCESS_ID), _WIT_REF, request
            )
        assert isinstance(result, ProcessWorkItemRule)
        assert result.id == _RULE_ID

    @staticmethod
    def test_sends_json_body_with_conditions(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_RULE_PAYLOAD)
        request = ProcessWorkItemTypeRuleCreateRequest(
            name="My Rule",
            conditions=[
                ProcessWorkItemTypeRuleCondition(condition_type="when", field="State")
            ],
            actions=[
                ProcessWorkItemTypeRuleAction(
                    action_type="setFieldValue", target_field="Reason"
                )
            ],
        )
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_work_item_type_rule(api_call, UUID(_PROCESS_ID), _WIT_REF, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "My Rule"
        assert "conditions" in sent_json


class TestUpdateWorkItemTypeRule:
    @staticmethod
    def test_returns_updated_rule(api_call: ApiCall) -> None:
        updated = {**_RULE_PAYLOAD, "name": "Renamed Rule"}
        mock_resp = _make_mock_response(updated)
        request = ProcessWorkItemTypeRuleUpdateRequest(name="Renamed Rule")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_work_item_type_rule(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _RULE_ID, request
            )
        assert isinstance(result, ProcessWorkItemRule)
        assert result.name == "Renamed Rule"

    @staticmethod
    def test_rule_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_RULE_PAYLOAD)
        request = ProcessWorkItemTypeRuleUpdateRequest(name="X")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_work_item_type_rule(
                api_call, UUID(_PROCESS_ID), _WIT_REF, _RULE_ID, request
            )
        assert _RULE_ID in mock_req.call_args.kwargs["url"]


class TestDeleteWorkItemTypeRule:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_rule(api_call, UUID(_PROCESS_ID), _WIT_REF, _RULE_ID)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_rule_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_work_item_type_rule(api_call, UUID(_PROCESS_ID), _WIT_REF, _RULE_ID)
        assert _RULE_ID in mock_req.call_args.kwargs["url"]


class TestPostBehavior:
    @staticmethod
    def test_returns_behavior_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_BEHAVIOR_PAYLOAD)
        request = ProcessBehaviorCreateRequest(name="My Behavior")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_behavior(api_call, UUID(_PROCESS_ID), request)
        assert isinstance(result, ProcessBehaviorInfo)
        assert result.name == "My Behavior"

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_BEHAVIOR_PAYLOAD)
        request = ProcessBehaviorCreateRequest(name="My Behavior", color="0000FF")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_behavior(api_call, UUID(_PROCESS_ID), request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "My Behavior"


class TestPatchBehavior:
    @staticmethod
    def test_returns_updated_behavior(api_call: ApiCall) -> None:
        updated = {**_BEHAVIOR_PAYLOAD, "name": "Renamed Behavior"}
        mock_resp = _make_mock_response(updated)
        request = ProcessBehaviorUpdateRequest(name="Renamed Behavior")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = patch_behavior(api_call, UUID(_PROCESS_ID), _BEHAVIOR_REF, request)
        assert isinstance(result, ProcessBehaviorInfo)
        assert result.name == "Renamed Behavior"

    @staticmethod
    def test_behavior_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_BEHAVIOR_PAYLOAD)
        request = ProcessBehaviorUpdateRequest(name="X")
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_behavior(api_call, UUID(_PROCESS_ID), _BEHAVIOR_REF, request)
        assert _BEHAVIOR_REF in mock_req.call_args.kwargs["url"]


class TestDeleteBehavior:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_behavior(api_call, UUID(_PROCESS_ID), _BEHAVIOR_REF)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_behavior_ref_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_behavior(api_call, UUID(_PROCESS_ID), _BEHAVIOR_REF)
        assert _BEHAVIOR_REF in mock_req.call_args.kwargs["url"]


class TestProcessWorkItemTypeRuleModels:
    @staticmethod
    def test_condition_fields() -> None:
        cond = ProcessWorkItemTypeRuleCondition(
            condition_type="when", field="State", value="Active"
        )
        assert cond.condition_type == "when"
        assert cond.field == "State"
        assert cond.value == "Active"

    @staticmethod
    def test_action_fields() -> None:
        action = ProcessWorkItemTypeRuleAction(
            action_type="setFieldValue", target_field="Reason", value="Fixed"
        )
        assert action.action_type == "setFieldValue"
        assert action.target_field == "Reason"
        assert action.value == "Fixed"
