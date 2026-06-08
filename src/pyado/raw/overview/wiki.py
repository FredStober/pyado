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
    "WikiPageId",
    "WikiType",
    "get_wiki_pages",
    "iter_wikis",
    "list_wikis",
]

WikiId: TypeAlias = UUID
#: Numeric identifier for a wiki page.
WikiPageId: TypeAlias = int

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


class _WikiResults(AdoBaseModel):
    """Internal: container for wiki list results."""

    value: list[WikiInfo]


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
