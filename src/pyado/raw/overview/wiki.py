"""Azure DevOps wiki API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "WikiId",
    "WikiInfo",
    "WikiPage",
    "WikiPageAttachment",
    "WikiPageDetail",
    "WikiPageId",
    "WikiPageVersion",
    "WikiType",
    "delete_wiki_page",
    "get_wiki_page",
    "get_wiki_page_attachments",
    "get_wiki_pages",
    "iter_wikis",
    "list_wikis",
    "put_wiki_page",
]

WikiId: TypeAlias = UUID
#: Numeric identifier for a wiki page.
WikiPageId: TypeAlias = int
#: Integer version (ETag) for a wiki page, used for conflict detection.
WikiPageVersion: TypeAlias = int

_WIKI_API_VERSION = "7.1"


class WikiType(StrEnum):
    """Type discriminator for an ADO wiki.

    ``PROJECT_WIKI`` is the built-in wiki created automatically for a
    project.  ``CODE_WIKI`` is a wiki backed by a Git repository.
    """

    PROJECT_WIKI = "projectWiki"
    CODE_WIKI = "codeWiki"


class WikiInfo(AdoBaseModel):
    """Minimal representation of an ADO wiki."""

    id: WikiId
    name: str
    type: WikiType | None = None
    project_id: str | None = None
    repository_id: str | None = None
    mapped_path: str | None = None


class WikiPage(AdoBaseModel):
    """A page in an ADO wiki."""

    id: WikiPageId | None = None
    path: str | None = None
    order: int | None = None
    is_parent_page: bool = False
    sub_pages: "list[WikiPage]" = Field(default_factory=list)


WikiPage.model_rebuild()


class WikiPageDetail(WikiPage):
    """A wiki page returned by the get-page or put-page endpoint.

    Extends :class:`WikiPage` with fields that are only present when
    fetching or mutating a single page (rather than listing a tree).
    """

    content: str | None = None
    git_item_path: str | None = None
    remote_url: str | None = None


class WikiPageAttachment(AdoBaseModel):
    """An attachment reference for a wiki page."""

    name: str


class _WikiPageRequest(AdoBaseModel):
    """Internal: request body for creating or updating a wiki page."""

    content: str


class _WikiResults(AdoBaseModel):
    """Internal: container for wiki list results."""

    value: list[WikiInfo]


class _WikiPageAttachmentResults(AdoBaseModel):
    """Internal: container for wiki page attachment list results."""

    value: list[WikiPageAttachment]


def iter_wikis(
    project_api_call: ApiCall,
) -> Iterator[WikiInfo]:
    """Iterate over all wikis in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        WikiInfo for each wiki in the project.
    """
    result = project_api_call.get("wiki", "wikis", version=_WIKI_API_VERSION)
    for item in result.get("value", []):
        yield WikiInfo.model_validate(item)


def list_wikis(
    project_api_call: ApiCall,
) -> list[WikiInfo]:
    """Return all wikis in a project as a list."""
    return list(iter_wikis(project_api_call))


def get_wiki_page(
    project_api_call: ApiCall,
    wiki_id: WikiId,
    path: str,
    *,
    include_content: bool = True,
) -> WikiPageDetail:
    """Fetch a single wiki page by path.

    Args:
        project_api_call: Project-level ADO API call.
        wiki_id: UUID of the wiki.
        path: Page path (e.g. ``"/Overview"``).
        include_content: Whether to include page markdown content.
            Defaults to ``True``.

    Returns:
        WikiPageDetail for the requested page.
    """
    result = project_api_call.get(
        "wiki",
        "wikis",
        wiki_id,
        "pages",
        parameters={"path": path, "includeContent": include_content},
        version=_WIKI_API_VERSION,
    )
    return WikiPageDetail.model_validate(result)


def put_wiki_page(
    project_api_call: ApiCall,
    wiki_id: WikiId,
    path: str,
    content: str,
    *,
    version: WikiPageVersion | None = None,
) -> WikiPageDetail:
    """Create or update a wiki page.

    Pass ``version`` (the integer ETag obtained from a prior
    :func:`get_wiki_page` call) when updating an existing page; omit it
    when creating a new page.

    Args:
        project_api_call: Project-level ADO API call.
        wiki_id: UUID of the wiki.
        path: Page path (e.g. ``"/Overview"``).
        content: Markdown content for the page.
        version: Page version for conflict detection.  Required when
            updating an existing page; omit for new pages.

    Returns:
        WikiPageDetail for the created or updated page.
    """
    extra_headers: dict[str, str] | None = None
    if version is not None:
        extra_headers = {"If-Match": f'"{version}"'}
    body = _WikiPageRequest(content=content)
    result = project_api_call.put(
        "wiki",
        "wikis",
        wiki_id,
        "pages",
        parameters={"path": path},
        version=_WIKI_API_VERSION,
        json=body.model_dump(by_alias=True),
        extra_headers=extra_headers,
    )
    return WikiPageDetail.model_validate(result)


def delete_wiki_page(
    project_api_call: ApiCall,
    wiki_id: WikiId,
    path: str,
    *,
    version: WikiPageVersion,
) -> WikiPageDetail:
    """Delete a wiki page by path.

    Args:
        project_api_call: Project-level ADO API call.
        wiki_id: UUID of the wiki.
        path: Page path (e.g. ``"/Overview"``).
        version: Page version (ETag) for conflict detection.

    Returns:
        WikiPageDetail for the deleted page.
    """
    result = project_api_call.delete(
        "wiki",
        "wikis",
        wiki_id,
        "pages",
        parameters={"path": path},
        version=_WIKI_API_VERSION,
        extra_headers={"If-Match": f'"{version}"'},
    )
    return WikiPageDetail.model_validate(result)


def get_wiki_page_attachments(
    project_api_call: ApiCall,
    wiki_id: WikiId,
    page_id: WikiPageId,
) -> list[WikiPageAttachment]:
    """Return all attachments for a wiki page.

    Args:
        project_api_call: Project-level ADO API call.
        wiki_id: UUID of the wiki.
        page_id: Numeric identifier of the wiki page.

    Returns:
        List of WikiPageAttachment objects for the page.
    """
    result = project_api_call.get(
        "wiki",
        "wikis",
        wiki_id,
        "pages",
        page_id,
        "attachments",
        version=_WIKI_API_VERSION,
    )
    return _WikiPageAttachmentResults.model_validate(result).value


def get_wiki_pages(
    project_api_call: ApiCall,
    wiki_id: WikiId,
    *,
    recursion_level: int = 2,
) -> list[WikiPage]:
    """Return the root page tree for a wiki.

    Args:
        project_api_call: Project-level ADO API call.
        wiki_id: UUID of the wiki.
        recursion_level: How many levels of child pages to include.
            Defaults to 2.

    Returns:
        List of WikiPage objects at the root level, each with nested
        sub_pages up to the requested recursion depth.
    """
    result = project_api_call.get(
        "wiki",
        "wikis",
        wiki_id,
        "pages",
        parameters={"path": "/", "recursionLevel": recursion_level},
        version=_WIKI_API_VERSION,
    )
    sub_pages: list[WikiPage] = []
    if isinstance(result, dict):
        root = WikiPage.model_validate(result)
        sub_pages = root.sub_pages
    return sub_pages
