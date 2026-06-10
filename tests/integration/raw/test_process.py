"""Integration tests for process info endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid
from uuid import UUID

from pyado import raw
from pyado.exceptions import AzureDevOpsHttpError
from tests.integration.raw._support import console


def test_process_read(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Fetch process template information for the project."""
    console.print("\n=== PROCESS (read) ===")
    project_info = raw.get_project(org_api_call, project_name)
    if (
        project_info
        and project_info.capabilities
        and project_info.capabilities.process_template.template_type_id
    ):
        template_id = UUID(project_info.capabilities.process_template.template_type_id)
        raw.get_process_info(org_api_call, project_api_call, template_id)


def test_list_processes(org_api_call: raw.ApiCall) -> None:
    """List all process templates in the organisation."""
    console.print("\n=== PROCESS list_processes ===")
    processes = raw.list_processes(org_api_call)
    console.print(f"Found {len(processes)} process(es)")
    for proc in processes:
        console.print(f"  {proc.name} ({proc.type_id}) [{proc.customization_type}]")
    assert isinstance(processes, list)


def test_get_process(org_api_call: raw.ApiCall) -> None:
    """Get a single process by ID fetched from the list."""
    console.print("\n=== PROCESS get_process ===")
    processes = raw.list_processes(org_api_call)
    if not processes:
        return
    proc = raw.get_process(org_api_call, processes[0].type_id)
    assert proc.type_id == processes[0].type_id
    console.print(f"Fetched: {proc.name}")


def _smoke_state_cycle(
    org_api_call: raw.ApiCall,
    proc_id: UUID,
    wit_ref: str,
    suffix: str,
) -> None:
    """Create, update, and delete a WIT state."""
    new_state = raw.post_work_item_type_state(
        org_api_call,
        proc_id,
        wit_ref,
        raw.ProcessWorkItemTypeStateCreateRequest(
            name=f"SmState{suffix}", color="FF0000", state_category="InProgress"
        ),
    )
    console.print(f"  created state: {new_state.name}  id={new_state.id}")
    assert new_state.id is not None
    raw.patch_work_item_type_state(
        org_api_call,
        proc_id,
        wit_ref,
        new_state.id,
        raw.ProcessWorkItemTypeStateUpdateRequest(color="00FF00"),
    )
    raw.delete_work_item_type_state(org_api_call, proc_id, wit_ref, new_state.id)
    console.print("  deleted state")


def _smoke_field_cycle(
    org_api_call: raw.ApiCall,
    proc_id: UUID,
    wit_ref: str,
) -> None:
    """Add, update, and remove a WIT field."""
    added = raw.post_work_item_type_field(
        org_api_call,
        proc_id,
        wit_ref,
        raw.ProcessWorkItemTypeFieldAddRequest(reference_name="System.AreaPath"),
    )
    console.print(f"  added field: {added.reference_name}")
    assert added.reference_name is not None
    raw.patch_work_item_type_field(
        org_api_call,
        proc_id,
        wit_ref,
        added.reference_name,
        raw.ProcessWorkItemTypeFieldUpdateRequest(is_required=False),
    )
    raw.delete_work_item_type_field(
        org_api_call, proc_id, wit_ref, added.reference_name
    )
    console.print("  removed field")


def _smoke_rule_cycle(
    org_api_call: raw.ApiCall,
    proc_id: UUID,
    wit_ref: str,
    suffix: str,
) -> None:
    """Create, update, and delete a WIT rule."""
    new_rule = raw.post_work_item_type_rule(
        org_api_call,
        proc_id,
        wit_ref,
        raw.ProcessWorkItemTypeRuleCreateRequest(name=f"SmRule{suffix}"),
    )
    console.print(f"  created rule: {new_rule.name}  id={new_rule.id}")
    assert new_rule.id is not None
    try:
        raw.patch_work_item_type_rule(
            org_api_call,
            proc_id,
            wit_ref,
            new_rule.id,
            raw.ProcessWorkItemTypeRuleUpdateRequest(name=f"SmRule{suffix}_upd"),
        )
    except AzureDevOpsHttpError as exc:
        console.print(f"  rule update not supported by this org: {exc}")
    try:
        raw.delete_work_item_type_rule(org_api_call, proc_id, wit_ref, new_rule.id)
    except AzureDevOpsHttpError as exc:
        console.print(f"  rule delete not supported by this org: {exc}")
    console.print("  rule cycle done")


def _smoke_behavior_cycle(
    org_api_call: raw.ApiCall,
    proc_id: UUID,
    suffix: str,
) -> None:
    """Create, update, and delete a process behavior."""
    try:
        new_beh = raw.post_behavior(
            org_api_call,
            proc_id,
            raw.ProcessBehaviorCreateRequest(
                name=f"SmBehavior{suffix}", color="7F1725"
            ),
        )
    except AzureDevOpsHttpError as exc:
        console.print(f"  behavior create not supported by this org: {exc}")
        return
    console.print(f"  created behavior: {new_beh.name}  ref={new_beh.reference_name}")
    try:
        raw.patch_behavior(
            org_api_call,
            proc_id,
            new_beh.reference_name,
            raw.ProcessBehaviorUpdateRequest(description="Updated smoke behavior"),
        )
    except AzureDevOpsHttpError as exc:
        console.print(f"  behavior update not supported by this org: {exc}")
    try:
        raw.delete_behavior(org_api_call, proc_id, new_beh.reference_name)
    except AzureDevOpsHttpError as exc:
        console.print(f"  behavior delete not supported by this org: {exc}")
    console.print("  behavior cycle done")


def _smoke_wit_cycle(
    org_api_call: raw.ApiCall,
    proc_id: UUID,
    suffix: str,
) -> None:
    """Create a WIT, exercise all sub-resource mutations, then delete it."""
    new_wit = raw.post_work_item_type(
        org_api_call,
        proc_id,
        raw.ProcessWorkItemTypeCreateRequest(
            name=f"SmWit{suffix}",
            description="Smoke WIT",
            color="009CCC",
            icon="icon_airplane",
        ),
    )
    console.print(f"  created WIT: {new_wit.name}  ref={new_wit.reference_name}")
    wit_ref = new_wit.reference_name
    raw.patch_work_item_type(
        org_api_call,
        proc_id,
        wit_ref,
        raw.ProcessWorkItemTypeUpdateRequest(description="Updated smoke WIT"),
    )
    _smoke_state_cycle(org_api_call, proc_id, wit_ref, suffix)
    _smoke_field_cycle(org_api_call, proc_id, wit_ref)
    _smoke_rule_cycle(org_api_call, proc_id, wit_ref, suffix)
    raw.delete_work_item_type(org_api_call, proc_id, wit_ref)
    console.print("  deleted WIT")


def test_process_write(org_api_call: raw.ApiCall) -> None:
    """Create an inherited process and exercise all sub-resource mutations.

    Lifecycle: process → WIT → state/field/rule → behavior → cleanup.
    """
    console.print("\n=== PROCESS (write: full lifecycle) ===")

    system_process = next(
        (
            proc
            for proc in raw.iter_processes(org_api_call)
            if proc.customization_type == raw.ProcessType.SYSTEM
        ),
        None,
    )
    if system_process is None:
        console.print("  skipping — no system process found")
        return

    suffix = uuid.uuid4().hex[:6]
    smoke_name = f"_smoke_{suffix}"

    new_proc = raw.post_process(
        org_api_call,
        raw.ProcessCreateRequest(
            name=smoke_name,
            parent_process_type_id=system_process.type_id,
            description="Smoke test inherited process",
        ),
    )
    console.print(f"  created process: {new_proc.name}  id={new_proc.type_id}")
    proc_id = new_proc.type_id
    try:
        raw.patch_process(
            org_api_call,
            proc_id,
            raw.ProcessUpdateRequest(description="Updated smoke process"),
        )
        console.print("  updated process description")
        _smoke_wit_cycle(org_api_call, proc_id, suffix)
        _smoke_behavior_cycle(org_api_call, proc_id, suffix)
    finally:
        raw.delete_process(org_api_call, proc_id)
        console.print(f"  deleted process: {smoke_name}")
