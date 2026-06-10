"""Azure DevOps task group API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "TaskGroupCreateRequest",
    "TaskGroupId",
    "TaskGroupInfo",
    "TaskGroupUpdateRequest",
    "delete_task_group",
    "get_task_group",
    "iter_task_groups",
    "list_task_groups",
    "post_task_group",
    "put_task_group",
]

_TASK_GROUP_API_VERSION = "7.1"

#: UUID identifier for a task group.
TaskGroupId: TypeAlias = UUID


class TaskGroupInfo(AdoBaseModel):
    """Minimal representation of an ADO task group."""

    id: TaskGroupId
    name: str
    revision: int | None = None
    description: str | None = None
    category: str | None = None
    comment: str | None = None
    author: str | None = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)


class TaskGroupCreateRequest(AdoBaseModel):
    """Request body for creating a task group."""

    name: str
    tasks: list[dict[str, Any]]
    description: str | None = None
    category: str | None = None
    comment: str | None = None
    author: str | None = None
    runs_on: list[str] = Field(default_factory=list)


class TaskGroupUpdateRequest(AdoBaseModel):
    """Request body for updating a task group."""

    id: TaskGroupId
    name: str
    tasks: list[dict[str, Any]]
    revision: int | None = None
    description: str | None = None
    category: str | None = None
    comment: str | None = None
    author: str | None = None
    runs_on: list[str] = Field(default_factory=list)


def iter_task_groups(
    project_api_call: ApiCall,
) -> Iterator[TaskGroupInfo]:
    """Iterate over all task groups in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        TaskGroupInfo for each task group.
    """
    result = project_api_call.get(
        "distributedtask",
        "taskgroups",
        version=_TASK_GROUP_API_VERSION,
    )
    for item in result.get("value", []):
        yield TaskGroupInfo.model_validate(item)


def list_task_groups(
    project_api_call: ApiCall,
) -> list[TaskGroupInfo]:
    """Return all task groups in a project as a list."""
    return list(iter_task_groups(project_api_call))


def get_task_group(
    project_api_call: ApiCall,
    task_group_id: TaskGroupId,
) -> TaskGroupInfo:
    """Fetch a single task group by ID.

    Args:
        project_api_call: Project-level ADO API call.
        task_group_id: UUID of the task group.

    Returns:
        TaskGroupInfo for the requested task group.
    """
    result = project_api_call.get(
        "distributedtask",
        "taskgroups",
        task_group_id,
        version=_TASK_GROUP_API_VERSION,
    )
    items = result.get("value", [])
    return TaskGroupInfo.model_validate(items[0])


def post_task_group(
    project_api_call: ApiCall,
    request: TaskGroupCreateRequest,
) -> TaskGroupInfo:
    """Create a new task group in a project.

    Args:
        project_api_call: Project-level ADO API call.
        request: Create request specifying the name and tasks.

    Returns:
        TaskGroupInfo for the newly created task group.
    """
    result = project_api_call.post(
        "distributedtask",
        "taskgroups",
        version=_TASK_GROUP_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return TaskGroupInfo.model_validate(result)


def put_task_group(
    project_api_call: ApiCall,
    task_group_id: TaskGroupId,
    request: TaskGroupUpdateRequest,
) -> TaskGroupInfo:
    """Update an existing task group.

    Args:
        project_api_call: Project-level ADO API call.
        task_group_id: UUID of the task group to update.
        request: Update request.  The ``id`` field must match
            ``task_group_id``.

    Returns:
        Updated TaskGroupInfo parsed from the API response.
    """
    result = project_api_call.put(
        "distributedtask",
        "taskgroups",
        task_group_id,
        version=_TASK_GROUP_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return TaskGroupInfo.model_validate(result)


def delete_task_group(
    project_api_call: ApiCall,
    task_group_id: TaskGroupId,
) -> None:
    """Delete a task group from a project.

    Args:
        project_api_call: Project-level ADO API call.
        task_group_id: UUID of the task group to delete.
    """
    project_api_call.delete(
        "distributedtask",
        "taskgroups",
        task_group_id,
        version=_TASK_GROUP_API_VERSION,
    )
