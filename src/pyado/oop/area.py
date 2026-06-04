"""OOP wrapper for Azure DevOps area classification nodes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado.raw import ClassificationNode

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Area"]


class Area:
    """An Azure DevOps area classification node.

    Wraps a single area node and exposes its properties.  Instances are
    obtained from :meth:`Project.get_area_node`.

    Unlike iteration nodes, area nodes carry no date attributes.  Child nodes
    are returned as :class:`Area` instances wrapping the ``children`` list
    embedded in the API response (no extra API call is made).  To fetch
    children at a specific depth, call :meth:`Project.get_area_node` with a
    higher *depth* argument.

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
        """Node name (e.g. ``"Team A"``)."""
        return self._info.name

    @property
    def path(self) -> str | None:
        r"""Full path as returned by the API (e.g. ``"\\\\Proj\\\\Team A"``)."""
        return self._info.path

    @property
    def children(self) -> "list[Area]":
        """Child area nodes embedded in the API response.

        Returns an empty list when either no children are present or the
        response was fetched at depth 0.  Call
        :meth:`Project.get_area_node` with a higher *depth* to populate
        children.
        """
        if self._info.children is None:
            return []
        return [Area(self._project, child) for child in self._info.children]

    @property
    def project(self) -> "Project":
        """Project this area belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this area belongs to — zero-cost."""
        return self._project.org
