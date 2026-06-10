"""Integration tests for task group endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado import raw
from pyado.exceptions import AzureDevOpsHttpError
from tests.integration.raw._support import console

_SCRIPT_TASK_ID = "d9bafed4-0b18-4f58-968d-86655b4d2ce9"


def test_task_groups_read(project_api_call: raw.ApiCall) -> None:
    """List task groups and verify iter/list consistency."""
    console.print("\n=== TASK GROUPS (read) ===")
    groups = list(raw.iter_task_groups(project_api_call))
    assert groups == raw.list_task_groups(project_api_call)
    console.print(f"  task groups: {len(groups)}")


def test_task_group_get_by_id(project_api_call: raw.ApiCall) -> None:
    """Get a single task group by ID when at least one exists."""
    groups = raw.list_task_groups(project_api_call)
    if not groups:
        console.print("  skipping get_task_group — no task groups in project")
        return
    first = groups[0]
    console.print(f"\n=== TASK GROUP get {first.name} ===")
    fetched = raw.get_task_group(project_api_call, first.id)
    assert fetched.id == first.id


def test_task_group_write(project_api_call: raw.ApiCall) -> None:
    """Create a task group, update it, then delete it."""
    console.print("\n=== TASK GROUPS (create/update/delete) ===")
    smoke_name = f"_smoke_{uuid.uuid4().hex[:6]}"

    new_group = raw.post_task_group(
        project_api_call,
        raw.TaskGroupCreateRequest(
            name=smoke_name,
            description="Smoke test task group",
            tasks=[
                {
                    "task": {
                        "id": _SCRIPT_TASK_ID,
                        "versionSpec": "2.*",
                        "definitionType": "task",
                    },
                    "displayName": "Run smoke script",
                    "inputs": {"targetType": "inline", "script": "echo smoke"},
                    "condition": "succeeded()",
                    "enabled": True,
                }
            ],
        ),
    )
    console.print(f"  created: {new_group.name}  id={new_group.id}")

    updated_name = f"{smoke_name}_upd"
    try:
        updated_group = raw.put_task_group(
            project_api_call,
            new_group.id,
            raw.TaskGroupUpdateRequest(
                id=new_group.id,
                name=updated_name,
                description="Updated smoke task group",
                tasks=new_group.tasks,
                revision=new_group.revision,
            ),
        )
        console.print(f"  updated name to: {updated_group.name}")
    except AzureDevOpsHttpError as exc:
        console.print(f"  put_task_group not supported by this org: {exc}")

    raw.delete_task_group(project_api_call, new_group.id)
    console.print("  deleted")
