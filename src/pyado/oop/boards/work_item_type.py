"""OOP wrapper for Azure DevOps work item type metadata resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    WorkItemFieldInfo,
    WorkItemStateInfo,
    WorkItemTypeIcon,
    WorkItemTypeInfo,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["WorkItemType"]


class WorkItemType:
    """Metadata about an ADO work item type.

    This class is exported from ``pyado.oop`` only — not from
    ``pyado`` directly, where ``pyado.WorkItemType`` refers to the
    raw model alias.

    Instances are obtained from
    :meth:`ProjectBoards.iter_work_item_types` or
    :meth:`ProjectBoards.get_work_item_type`.

    Attributes:
        _project: The Project this work item type belongs to.
        _info: Work item type metadata.
    """

    def __init__(self, project: "Project", info: WorkItemTypeInfo) -> None:
        """Construct a WorkItemType wrapper.

        Args:
            project: The Project this work item type belongs to.
            info: WorkItemTypeInfo returned by the ADO WIT endpoint.
        """
        self._project = project
        self._info = info

    @property
    def name(self) -> str:
        """Work item type display name (e.g. ``"Bug"``)."""
        return self._info.name

    @property
    def description(self) -> str:
        """Work item type description."""
        return self._info.description

    @property
    def color(self) -> str | None:
        """Hex color code for this work item type."""
        return self._info.color

    @property
    def icon(self) -> WorkItemTypeIcon | None:
        """Icon descriptor for this work item type."""
        return self._info.icon

    @property
    def reference_name(self) -> str:
        """Fully-qualified reference name.

        Example: ``"Microsoft.VSTS.WorkItemTypes.Bug"``.
        """
        return self._info.reference_name

    @property
    def info(self) -> WorkItemTypeInfo:
        """Full work item type data as returned by the API."""
        return self._info

    @property
    def project(self) -> "Project":
        """Project this work item type belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this work item type belongs to — zero-cost."""
        return self._project.org

    def iter_states(self) -> Iterator[WorkItemStateInfo]:
        """Iterate over state definitions for this work item type.

        Yields:
            WorkItemStateInfo for each state.
        """
        yield from raw.iter_work_item_type_states(self._project.api_call, self.name)

    def list_states(self) -> list[WorkItemStateInfo]:
        """Return all state definitions for this work item type as a list."""
        return raw.list_work_item_type_states(self._project.api_call, self.name)

    def iter_fields(self) -> Iterator[WorkItemFieldInfo]:
        """Iterate over field definitions for this work item type.

        Yields:
            WorkItemFieldInfo for each field.
        """
        yield from raw.iter_work_item_type_fields(self._project.api_call, self.name)

    def list_fields(self) -> list[WorkItemFieldInfo]:
        """Return all field definitions for this work item type as a list."""
        return raw.list_work_item_type_fields(self._project.api_call, self.name)
