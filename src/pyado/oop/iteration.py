"""OOP wrapper for Azure DevOps iteration classification nodes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import ClassificationNode

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Iteration"]


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string from ADO (``"2024-01-15T00:00:00Z"``) to a date.

    Args:
        value: ISO datetime string, or None.

    Returns:
        Parsed date, or None if *value* is None.
    """
    if value is None:
        return None
    return date.fromisoformat(value[:10])


def _relative_path(full_path: str | None) -> str | None:
    r"""Strip the leading project-name prefix from a classification node path.

    ADO returns paths like ``"\\\\ProjectName\\\\Sprint 1"``.
    The raw API expects only the relative portion, e.g. ``"Sprint 1"``.

    Args:
        full_path: Full path string from the API response, or None.

    Returns:
        Relative path string, or None for a root node.
    """
    if not full_path:
        return None
    parts = full_path.lstrip("\\").split("\\")
    relative = "\\".join(parts[1:])  # drop the project-name segment
    return relative or None


class Iteration:
    """An Azure DevOps iteration classification node.

    Wraps a single iteration node and exposes its properties and patch
    operation.  Instances are obtained from
    :meth:`Project.get_iteration_node`.

    Iteration nodes may carry start and finish dates.  Child nodes are
    returned as :class:`Iteration` instances wrapping the ``children`` list
    embedded in the API response (no extra API call is made).  To fetch
    children at a specific depth, call :meth:`Project.get_iteration_node`
    with a higher *depth* argument.

    Attributes:
        _project: The Project this iteration belongs to.
        _info: The ClassificationNode data for this node.
    """

    def __init__(self, project: "Project", info: ClassificationNode) -> None:
        """Construct an Iteration wrapper.

        Args:
            project: The Project that owns this iteration node.
            info: ClassificationNode data as returned from the API.
        """
        self._project = project
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> ClassificationNode:
        """Raw node data captured at construction time."""
        return self._info

    @property
    def id(self) -> int:
        """Numeric node ID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Node name (e.g. ``"Sprint 1"``)."""
        return self._info.name

    @property
    def path(self) -> str | None:
        r"""Full path as returned by the API (e.g. ``"\\\\Proj\\\\Sprint 1"``)."""
        return self._info.path

    @property
    def start_date(self) -> date | None:
        """Iteration start date, or ``None`` if not set."""
        if self._info.attributes is None:
            return None
        return _parse_date(self._info.attributes.start_date)

    @property
    def finish_date(self) -> date | None:
        """Iteration finish (end) date, or ``None`` if not set."""
        if self._info.attributes is None:
            return None
        return _parse_date(self._info.attributes.finish_date)

    @property
    def children(self) -> "list[Iteration]":
        """Child iteration nodes embedded in the API response.

        Returns an empty list when either no children are present or the
        response was fetched at depth 0.  Call
        :meth:`Project.get_iteration_node` with a higher *depth* to populate
        children.
        """
        if self._info.children is None:
            return []
        return [Iteration(self._project, child) for child in self._info.children]

    @property
    def project(self) -> "Project":
        """Project this iteration belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this iteration belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def patch(
        self,
        *,
        start_date: date | None = None,
        finish_date: date | None = None,
    ) -> None:
        """Update the start and/or finish dates of this iteration node.

        Args:
            start_date: New start date, or ``None`` to leave unchanged.
            finish_date: New finish (end) date, or ``None`` to leave unchanged.
        """
        relative = _relative_path(self._info.path)
        self._info = raw.patch_classification_node(
            self._project.api_call,
            relative,
            start_date=start_date,
            finish_date=finish_date,
        )
