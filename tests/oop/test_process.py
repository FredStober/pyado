"""Tests for pyado.oop.core.process — Process OOP wrapper and Organization methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID, uuid4

from pyado.oop.core.process import Process
from pyado.oop.organization import Organization
from pyado.raw import (
    ProcessBehaviorCreateRequest,
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
    ProcessWorkItemTypeRuleCreateRequest,
    ProcessWorkItemTypeRuleUpdateRequest,
    ProcessWorkItemTypeStateCreateRequest,
    ProcessWorkItemTypeStateUpdateRequest,
    ProcessWorkItemTypeUpdateRequest,
)
from tests.oop.conftest import _make_service

_PROCESS_ID = uuid4()
_WIT_REF = "Custom.MyType"
_STATE_ID = "state-uuid-1234"
_RULE_ID = "rule-uuid-5678"
_FIELD_REF = "Custom.MyField"
_BEHAVIOR_REF = "Custom.MyBehavior"


def _process_detail(
    process_id: UUID | None = None,
    name: str = "MyProcess",
) -> ProcessDetail:
    return ProcessDetail.model_validate(
        {
            "typeId": str(process_id or _PROCESS_ID),
            "name": name,
            "customizationType": "inherited",
        }
    )


def _make_process(name: str = "MyProcess") -> Process:
    svc = _make_service()
    org = Organization(svc)
    return Process(org, _process_detail(name=name))


def _make_wit_info(name: str = "My Type") -> ProcessWITInfo:
    return ProcessWITInfo.model_validate({"name": name, "referenceName": _WIT_REF})


def _make_wit_state() -> ProcessWorkItemState:
    return ProcessWorkItemState.model_validate(
        {"name": "Active", "id": _STATE_ID, "stateCategory": "InProgress"}
    )


def _make_wit_field() -> ProcessWorkItemField:
    return ProcessWorkItemField.model_validate(
        {"name": "My Field", "referenceName": _FIELD_REF}
    )


def _make_wit_rule() -> ProcessWorkItemRule:
    return ProcessWorkItemRule.model_validate(
        {"id": _RULE_ID, "name": "My Rule", "conditions": [], "actions": []}
    )


def _make_behavior() -> ProcessBehaviorInfo:
    return ProcessBehaviorInfo.model_validate(
        {"name": "My Behavior", "referenceName": _BEHAVIOR_REF}
    )


# ---------------------------------------------------------------------------
# Process properties
# ---------------------------------------------------------------------------


class TestProcessProperties:
    def test_id_returns_type_id(self) -> None:
        proc = _make_process()
        assert proc.id == _PROCESS_ID

    def test_name_returns_name(self) -> None:
        proc = _make_process("Agile")
        assert proc.name == "Agile"

    def test_description_returns_description(self) -> None:
        proc = _make_process()
        assert not proc.description

    def test_info_returns_stored_info(self) -> None:
        info = _process_detail()
        org = Organization(_make_service())
        proc = Process(org, info)
        assert proc.info is info

    def test_org_back_reference(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        proc = Process(org, _process_detail())
        assert proc.org is org


# ---------------------------------------------------------------------------
# Process.refresh
# ---------------------------------------------------------------------------


class TestProcessRefresh:
    def test_refresh_clears_info(self) -> None:
        proc = _make_process()
        proc.refresh()
        assert proc._info is None

    def test_info_re_fetches_after_refresh(self) -> None:
        info = _process_detail()
        proc = _make_process()
        proc.refresh()
        with patch(
            "pyado.oop.core.process.raw.get_process",
            return_value=info,
        ) as mock_get:
            result = proc.info
        mock_get.assert_called_once()
        assert result is info


# ---------------------------------------------------------------------------
# Process.update / delete
# ---------------------------------------------------------------------------


class TestProcessUpdate:
    def test_update_stores_new_info(self) -> None:
        proc = _make_process()
        updated_info = _process_detail(name="Renamed")
        request = ProcessUpdateRequest(name="Renamed")
        with patch(
            "pyado.oop.core.process.raw.patch_process",
            return_value=updated_info,
        ) as mock_patch:
            proc.update(request)
        mock_patch.assert_called_once_with(proc.org.api_call, proc.id, request)
        assert proc._info is updated_info

    def test_delete_clears_info(self) -> None:
        proc = _make_process()
        with patch("pyado.oop.core.process.raw.delete_process") as mock_del:
            proc.delete()
        mock_del.assert_called_once_with(proc.org.api_call, proc.id)
        assert proc._info is None


# ---------------------------------------------------------------------------
# Work item type mutations
# ---------------------------------------------------------------------------


class TestProcessWorkItemTypeMutations:
    def test_create_work_item_type_delegates(self) -> None:
        proc = _make_process()
        info = _make_wit_info()
        request = ProcessWorkItemTypeCreateRequest(name="My Type")
        with patch(
            "pyado.oop.core.process.raw.post_work_item_type",
            return_value=info,
        ) as mock_create:
            result = proc.create_work_item_type(request)
        mock_create.assert_called_once_with(proc.org.api_call, proc.id, request)
        assert result is info

    def test_update_work_item_type_delegates(self) -> None:
        proc = _make_process()
        info = _make_wit_info("Updated")
        request = ProcessWorkItemTypeUpdateRequest(name="Updated")
        with patch(
            "pyado.oop.core.process.raw.patch_work_item_type",
            return_value=info,
        ) as mock_update:
            result = proc.update_work_item_type(_WIT_REF, request)
        mock_update.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, request
        )
        assert result is info

    def test_delete_work_item_type_delegates(self) -> None:
        proc = _make_process()
        with patch("pyado.oop.core.process.raw.delete_work_item_type") as mock_del:
            proc.delete_work_item_type(_WIT_REF)
        mock_del.assert_called_once_with(proc.org.api_call, proc.id, _WIT_REF)


# ---------------------------------------------------------------------------
# State mutations
# ---------------------------------------------------------------------------


class TestProcessStateMutations:
    def test_create_state_delegates(self) -> None:
        proc = _make_process()
        state = _make_wit_state()
        request = ProcessWorkItemTypeStateCreateRequest(name="Active", color="00FF00")
        with patch(
            "pyado.oop.core.process.raw.post_work_item_type_state",
            return_value=state,
        ) as mock_create:
            result = proc.create_work_item_type_state(_WIT_REF, request)
        mock_create.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, request
        )
        assert result is state

    def test_update_state_delegates(self) -> None:
        proc = _make_process()
        state = _make_wit_state()
        request = ProcessWorkItemTypeStateUpdateRequest(name="In Progress")
        with patch(
            "pyado.oop.core.process.raw.patch_work_item_type_state",
            return_value=state,
        ) as mock_update:
            result = proc.update_work_item_type_state(_WIT_REF, _STATE_ID, request)
        mock_update.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, _STATE_ID, request
        )
        assert result is state

    def test_delete_state_delegates(self) -> None:
        proc = _make_process()
        with patch(
            "pyado.oop.core.process.raw.delete_work_item_type_state"
        ) as mock_del:
            proc.delete_work_item_type_state(_WIT_REF, _STATE_ID)
        mock_del.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, _STATE_ID
        )


# ---------------------------------------------------------------------------
# Field mutations
# ---------------------------------------------------------------------------


class TestProcessFieldMutations:
    def test_add_field_delegates(self) -> None:
        proc = _make_process()
        field = _make_wit_field()
        request = ProcessWorkItemTypeFieldAddRequest(reference_name=_FIELD_REF)
        with patch(
            "pyado.oop.core.process.raw.post_work_item_type_field",
            return_value=field,
        ) as mock_add:
            result = proc.add_work_item_type_field(_WIT_REF, request)
        mock_add.assert_called_once_with(proc.org.api_call, proc.id, _WIT_REF, request)
        assert result is field

    def test_update_field_delegates(self) -> None:
        proc = _make_process()
        field = _make_wit_field()
        request = ProcessWorkItemTypeFieldUpdateRequest(is_required=True)
        with patch(
            "pyado.oop.core.process.raw.patch_work_item_type_field",
            return_value=field,
        ) as mock_update:
            result = proc.update_work_item_type_field(_WIT_REF, _FIELD_REF, request)
        mock_update.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, _FIELD_REF, request
        )
        assert result is field

    def test_remove_field_delegates(self) -> None:
        proc = _make_process()
        with patch(
            "pyado.oop.core.process.raw.delete_work_item_type_field"
        ) as mock_remove:
            proc.remove_work_item_type_field(_WIT_REF, _FIELD_REF)
        mock_remove.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, _FIELD_REF
        )


# ---------------------------------------------------------------------------
# Rule mutations
# ---------------------------------------------------------------------------


class TestProcessRuleMutations:
    def test_create_rule_delegates(self) -> None:
        proc = _make_process()
        rule = _make_wit_rule()
        request = ProcessWorkItemTypeRuleCreateRequest(name="My Rule")
        with patch(
            "pyado.oop.core.process.raw.post_work_item_type_rule",
            return_value=rule,
        ) as mock_create:
            result = proc.create_work_item_type_rule(_WIT_REF, request)
        mock_create.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, request
        )
        assert result is rule

    def test_update_rule_delegates(self) -> None:
        proc = _make_process()
        rule = _make_wit_rule()
        request = ProcessWorkItemTypeRuleUpdateRequest(name="Updated Rule")
        with patch(
            "pyado.oop.core.process.raw.patch_work_item_type_rule",
            return_value=rule,
        ) as mock_update:
            result = proc.update_work_item_type_rule(_WIT_REF, _RULE_ID, request)
        mock_update.assert_called_once_with(
            proc.org.api_call, proc.id, _WIT_REF, _RULE_ID, request
        )
        assert result is rule

    def test_delete_rule_delegates(self) -> None:
        proc = _make_process()
        with patch("pyado.oop.core.process.raw.delete_work_item_type_rule") as mock_del:
            proc.delete_work_item_type_rule(_WIT_REF, _RULE_ID)
        mock_del.assert_called_once_with(proc.org.api_call, proc.id, _WIT_REF, _RULE_ID)


# ---------------------------------------------------------------------------
# Behavior mutations
# ---------------------------------------------------------------------------


class TestProcessBehaviorMutations:
    def test_create_behavior_delegates(self) -> None:
        proc = _make_process()
        behavior = _make_behavior()
        request = ProcessBehaviorCreateRequest(name="My Behavior")
        with patch(
            "pyado.oop.core.process.raw.post_behavior",
            return_value=behavior,
        ) as mock_create:
            result = proc.create_behavior(request)
        mock_create.assert_called_once_with(proc.org.api_call, proc.id, request)
        assert result is behavior

    def test_update_behavior_delegates(self) -> None:
        proc = _make_process()
        behavior = _make_behavior()
        request = ProcessBehaviorUpdateRequest(name="Updated")
        with patch(
            "pyado.oop.core.process.raw.patch_behavior",
            return_value=behavior,
        ) as mock_update:
            result = proc.update_behavior(_BEHAVIOR_REF, request)
        mock_update.assert_called_once_with(
            proc.org.api_call, proc.id, _BEHAVIOR_REF, request
        )
        assert result is behavior

    def test_delete_behavior_delegates(self) -> None:
        proc = _make_process()
        with patch("pyado.oop.core.process.raw.delete_behavior") as mock_del:
            proc.delete_behavior(_BEHAVIOR_REF)
        mock_del.assert_called_once_with(proc.org.api_call, proc.id, _BEHAVIOR_REF)


# ---------------------------------------------------------------------------
# Organization process methods
# ---------------------------------------------------------------------------


class TestOrganizationProcessMethods:
    def test_iter_processes_yields_wrappers(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        info = _process_detail()
        with patch(
            "pyado.oop.organization.raw.iter_processes",
            return_value=iter([info]),
        ):
            result = list(org.iter_processes())
        assert len(result) == 1
        assert isinstance(result[0], Process)
        assert result[0].name == "MyProcess"

    def test_iter_processes_empty(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        with patch(
            "pyado.oop.organization.raw.iter_processes",
            return_value=iter([]),
        ):
            result = list(org.iter_processes())
        assert result == []

    def test_list_processes_delegates(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        with patch.object(org, "iter_processes", return_value=iter([])):
            assert org.list_processes() == []

    def test_get_process_returns_wrapper(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        info = _process_detail()
        with patch(
            "pyado.oop.organization.raw.get_process",
            return_value=info,
        ) as mock_get:
            result = org.get_process(_PROCESS_ID)
        mock_get.assert_called_once_with(org.api_call, _PROCESS_ID)
        assert isinstance(result, Process)
        assert result.id == _PROCESS_ID

    def test_create_process_returns_wrapper(self) -> None:
        svc = _make_service()
        org = Organization(svc)
        info = _process_detail()
        parent_id = uuid4()
        request = ProcessCreateRequest(
            name="MyProcess", parent_process_type_id=parent_id
        )
        with patch(
            "pyado.oop.organization.raw.post_process",
            return_value=info,
        ) as mock_create:
            result = org.create_process(request)
        mock_create.assert_called_once_with(org.api_call, request)
        assert isinstance(result, Process)
        assert result.name == "MyProcess"
