"""OOP wrapper for Azure DevOps project wiki resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    WikiId,
    WikiInfo,
    WikiPage,
    WikiPageAttachment,
    WikiPageDetail,
    WikiPageId,
    WikiPageVersion,
    WikiType,
)

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

    def iter_pages(self, *, recursion_level: int = 2) -> Iterator[WikiPage]:
        """Iterate over root pages for this wiki.

        Args:
            recursion_level: How many levels of child pages to include.
                Defaults to 2.

        Yields:
            WikiPage objects at the root level, each with nested sub_pages
            up to the requested depth.
        """
        yield from raw.get_wiki_pages(
            self._project.api_call, self.id, recursion_level=recursion_level
        )

    def list_pages(self, *, recursion_level: int = 2) -> list[WikiPage]:
        """Return the root page tree for this wiki.

        Args:
            recursion_level: How many levels of child pages to include.
                Defaults to 2.

        Returns:
            List of WikiPage objects at the root level, each with nested
            sub_pages up to the requested depth.
        """
        return list(self.iter_pages(recursion_level=recursion_level))

    def get_page(self, path: str, *, include_content: bool = True) -> WikiPageDetail:
        """Fetch a single wiki page by path.

        Args:
            path: Page path relative to the wiki root (e.g. ``"/README"``).
            include_content: Whether to include the page content in the
                response.  Defaults to ``True``.

        Returns:
            WikiPageDetail for the requested page.
        """
        return raw.get_wiki_page(
            self._project.api_call, self.id, path, include_content=include_content
        )

    def put_page(
        self, path: str, content: str, *, version: WikiPageVersion | None = None
    ) -> WikiPageDetail:
        """Create or update a wiki page.

        Args:
            path: Page path relative to the wiki root.
            content: New Markdown content for the page.
            version: Current ETag version of the page.  Omit when creating
                a new page.

        Returns:
            WikiPageDetail reflecting the created or updated page.
        """
        return raw.put_wiki_page(
            self._project.api_call, self.id, path, content, version=version
        )

    def delete_page(self, path: str, *, version: WikiPageVersion) -> WikiPageDetail:
        """Delete a wiki page by path.

        Args:
            path: Page path relative to the wiki root.
            version: Current ETag version of the page.

        Returns:
            WikiPageDetail of the deleted page.
        """
        return raw.delete_wiki_page(
            self._project.api_call, self.id, path, version=version
        )

    def list_page_attachments(self, page_id: WikiPageId) -> list[WikiPageAttachment]:
        """Return all attachments for a wiki page.

        Args:
            page_id: Numeric ID of the wiki page.

        Returns:
            List of WikiPageAttachment objects for the page.
        """
        return raw.get_wiki_page_attachments(self._project.api_call, self.id, page_id)
