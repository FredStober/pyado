"""OOP wrapper for Azure DevOps iteration classification nodes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from pyado import raw
from pyado.oop._classification import _relative_path
from pyado.raw import (
    ClassificationNode,
    ClassificationNodeAttributes,
    ClassificationNodePatchRequest,
    ClassificationNodeRequest,
    ClassificationNodeUrlType,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.team import Team

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
        self._relative_path = _relative_path(info.path)
        self._info: ClassificationNode | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> ClassificationNode:
        """Raw node data captured at construction time."""
        if self._info is None:
            self._info = raw.get_classification_node(
                self._project.api_call,
                self._relative_path,
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        return self._info

    @property
    def id(self) -> int:
        """Numeric node ID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Node name (e.g. ``"Sprint 1"``)."""
        return self.info.name

    @property
    def path(self) -> str | None:
        r"""Full path as returned by the API (e.g. ``"\\\\Proj\\\\Sprint 1"``)."""
        return self.info.path

    @property
    def start_date(self) -> date | None:
        """Iteration start date, or ``None`` if not set."""
        if self.info.attributes is None:
            return None
        return _parse_date(self.info.attributes.start_date)

    @property
    def finish_date(self) -> date | None:
        """Iteration finish (end) date, or ``None`` if not set."""
        if self.info.attributes is None:
            return None
        return _parse_date(self.info.attributes.finish_date)

    @property
    def children(self) -> "list[Iteration]":
        """Child iteration nodes embedded in the API response.

        Returns an empty list when either no children are present or the
        response was fetched at depth 0.  Call
        :meth:`Project.get_iteration_node` with a higher *depth* to populate
        children.
        """
        if self.info.children is None:
            return []
        return [Iteration(self._project, child) for child in self.info.children]

    @property
    def project(self) -> "Project":
        """Project this iteration belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this iteration belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached iteration node info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update(
        self,
        *,
        name: str | None = None,
        start_date: date | None = None,
        finish_date: date | None = None,
    ) -> None:
        """Update the name and/or dates of this iteration node.

        Args:
            name: New name for the iteration node, or ``None`` to leave
                unchanged.
            start_date: New start date, or ``None`` to leave unchanged.
            finish_date: New finish (end) date, or ``None`` to leave unchanged.
        """
        relative = self._relative_path
        attrs = None
        if start_date or finish_date:
            attrs = ClassificationNodeAttributes.model_validate(
                {
                    "startDate": start_date.isoformat() + "T00:00:00Z"
                    if start_date
                    else None,
                    "finishDate": finish_date.isoformat() + "T00:00:00Z"
                    if finish_date
                    else None,
                }
            )
        self._info = raw.patch_classification_node(
            self._project.api_call,
            relative,
            ClassificationNodePatchRequest(name=name, attributes=attrs),
            node_type=ClassificationNodeUrlType.ITERATIONS,
        )
        self._relative_path = _relative_path(self._info.path)

    def delete(self) -> None:
        """Delete this iteration node."""
        raw.delete_classification_node(
            self._project.api_call,
            self._relative_path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
        )

    def create_child(self, name: str) -> "Iteration":
        """Create a child iteration node under this node.

        Args:
            name: Name of the new child iteration node.

        Returns:
            Iteration wrapping the newly created child iteration node.
        """
        node = raw.create_classification_node(
            self._project.api_call,
            ClassificationNodeRequest(name=name),
            self._relative_path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
        )
        return Iteration(self._project, node)

    def add_to_team(self, team: "Team") -> None:
        """Assign this iteration node to a team.

        Args:
            team: The Team to assign this iteration to.

        Raises:
            ValueError: If the iteration node has no ``identifier`` (UUID).
        """
        if self.info.identifier is None:
            err_msg = (
                f"Iteration {self.info.name!r} has no identifier; "
                "cannot assign to team."
            )
            raise ValueError(err_msg)
        team.add_iteration(UUID(self.info.identifier))
