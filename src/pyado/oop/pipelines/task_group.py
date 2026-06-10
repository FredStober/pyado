"""OOP wrapper for Azure DevOps task group resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING
from uuid import UUID

from pyado import raw
from pyado.raw import TaskGroupInfo, TaskGroupUpdateRequest

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["TaskGroup"]


class TaskGroup:
    """An ADO task group.

    Wraps a single ADO task group in a project.  Instances are obtained
    from :meth:`ProjectPipelines.iter_task_groups`.

    Attributes:
        _project: The Project this task group belongs to.
        _id: Task group UUID (always known).
        _info: Cached task group data; ``None`` after :meth:`refresh`.
    """

    def __init__(self, project: "Project", info: TaskGroupInfo) -> None:
        """Construct a TaskGroup wrapper.

        Args:
            project: The Project this task group belongs to.
            info: TaskGroupInfo returned by the ADO task groups API.
        """
        self._project = project
        self._id = info.id
        self._info: TaskGroupInfo | None = info

    @property
    def id(self) -> UUID:
        """Task group UUID — always known, no API call."""
        return self._id

    @property
    def name(self) -> str:
        """Task group name."""
        return self.info.name

    @property
    def description(self) -> str | None:
        """Task group description."""
        return self.info.description

    @property
    def category(self) -> str | None:
        """Task group category."""
        return self.info.category

    @property
    def info(self) -> TaskGroupInfo:
        """Full task group data as returned by the API.

        Fetched lazily by re-querying the API if :meth:`refresh` was
        called since the last access.
        """
        if self._info is None:
            self._info = raw.get_task_group(self._project.api_call, self._id)
        return self._info

    @property
    def project(self) -> "Project":
        """Project this task group belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this task group belongs to — zero-cost."""
        return self._project.org

    def refresh(self) -> None:
        """Discard cached task group info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    def update(self, request: TaskGroupUpdateRequest) -> None:
        """Update this task group.

        Args:
            request: Update request.  The ``id`` field must match this
                task group's :attr:`id`.
        """
        self._info = raw.put_task_group(self._project.api_call, self._id, request)

    def delete(self) -> None:
        """Delete this task group from the project."""
        raw.delete_task_group(self._project.api_call, self._id)
        self._info = None
