"""OOP wrapper for Azure DevOps area classification nodes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.oop.boards._classification import _relative_path
from pyado.raw import (
    ClassificationNode,
    ClassificationNodePatchRequest,
    ClassificationNodeRequest,
    ClassificationNodeUrlType,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Area"]


class Area:
    """An Azure DevOps area classification node.

    Wraps a single area node and exposes its properties.  Instances are
    obtained from :meth:`ProjectBoards.get_area_node`.

    Unlike iteration nodes, area nodes carry no date attributes.  Child nodes
    are returned as :class:`Area` instances wrapping the ``children`` list
    embedded in the API response (no extra API call is made).  To fetch
    children at a specific depth, call :meth:`ProjectBoards.get_area_node`
    with a higher *depth* argument.

    Attributes:
        _project: The Project this area belongs to.
        _info: The ClassificationNode data for this node.
    """

    def __init__(self, project: "Project", info: ClassificationNode) -> None:
        """Construct an Area wrapper.

        Args:
            project: The Project that owns this area node.
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
                node_type=ClassificationNodeUrlType.AREAS,
            )
        return self._info

    @property
    def id(self) -> int:
        """Numeric node ID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Node name (e.g. ``"Team A"``)."""
        return self.info.name

    @property
    def path(self) -> str | None:
        r"""Full path as returned by the API (e.g. ``"\\\\Proj\\\\Team A"``)."""
        return self.info.path

    @property
    def children(self) -> "list[Area]":
        """Child area nodes embedded in the API response.

        Returns an empty list when either no children are present or the
        response was fetched at depth 0.  Call
        :meth:`ProjectBoards.get_area_node` with a higher *depth* to populate
        children.
        """
        if self.info.children is None:
            return []
        return [Area(self._project, child) for child in self.info.children]

    @property
    def project(self) -> "Project":
        """Project this area belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this area belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached area node info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update(self, name: str) -> None:
        """Rename this area node.

        Args:
            name: New name for the area node.
        """
        self._info = raw.patch_classification_node(
            self._project.api_call,
            self._relative_path,
            ClassificationNodePatchRequest(name=name),
            node_type=ClassificationNodeUrlType.AREAS,
        )
        self._relative_path = _relative_path(self._info.path)

    def delete(self) -> None:
        """Delete this area node."""
        raw.delete_classification_node(
            self._project.api_call,
            self._relative_path,
            node_type=ClassificationNodeUrlType.AREAS,
        )

    def create_child(self, name: str) -> "Area":
        """Create a child area node under this node.

        Args:
            name: Name of the new child area node.

        Returns:
            Area wrapping the newly created child area node.
        """
        node = raw.post_classification_node(
            self._project.api_call,
            ClassificationNodeRequest(name=name),
            self._relative_path,
            node_type=ClassificationNodeUrlType.AREAS,
        )
        return Area(self._project, node)
