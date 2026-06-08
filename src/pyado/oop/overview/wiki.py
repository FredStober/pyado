"""OOP wrapper for Azure DevOps project wiki resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import WikiId, WikiInfo, WikiPage, WikiType

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Wiki"]


class Wiki:
    """An ADO project wiki.

    Wraps a single ADO wiki and exposes its pages.  Instances are
    obtained from :meth:`Project.iter_wikis` or
    :meth:`Project.list_wikis`.

    Attributes:
        _project: The Project this wiki belongs to.
        _info: Wiki metadata returned by the API.
    """

    def __init__(self, project: "Project", info: WikiInfo) -> None:
        """Construct a Wiki wrapper.

        Args:
            project: The Project this wiki belongs to.
            info: WikiInfo returned by the ADO wikis endpoint.
        """
        self._project = project
        self._info = info

    @property
    def id(self) -> WikiId:
        """Wiki UUID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Wiki name."""
        return self._info.name

    @property
    def type(self) -> WikiType | None:
        """Wiki type (``projectWiki`` or ``codeWiki``)."""
        return self._info.type

    @property
    def info(self) -> WikiInfo:
        """Full wiki data as returned by the API."""
        return self._info

    @property
    def project(self) -> "Project":
        """Project this wiki belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this wiki belongs to — zero-cost."""
        return self._project.org

    def get_pages(self, *, recursion_level: int = 2) -> list[WikiPage]:
        """Return the root page tree for this wiki.

        Args:
            recursion_level: How many levels of child pages to include.
                Defaults to 2.

        Returns:
            List of WikiPage objects at the root level, each with nested
            sub_pages up to the requested depth.
        """
        return raw.get_wiki_pages(
            self._project.api_call, self.id, recursion_level=recursion_level
        )
