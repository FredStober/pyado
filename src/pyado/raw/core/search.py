"""Azure DevOps Search API wrappers (almsearch.dev.azure.com)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any, Generic, TypeVar

import requests
from pydantic import Field

from pyado.raw._core import _ADO_URL_ADAPTER as _URL_ADAPTER
from pyado.raw._core import AdoBaseModel, AdoUrl, ApiCall

__all__ = [
    "CodeSearchRequest",
    "CodeSearchResponse",
    "CodeSearchResult",
    "PackageSearchResponse",
    "PackageSearchResult",
    "SearchFacetResult",
    "SearchRequest",
    "SearchResponse",
    "SearchSortOption",
    "WikiSearchResponse",
    "WikiSearchResult",
    "WorkItemSearchResponse",
    "WorkItemSearchResult",
    "get_search_api_call",
    "post_code_search",
    "post_package_search",
    "post_wiki_search",
    "post_work_item_search",
]

_SEARCH_BASE_URL = "https://almsearch.dev.azure.com"
_CODE_SEARCH_API_VERSION = "7.1"
_WORK_ITEM_SEARCH_API_VERSION = "7.1"
_WIKI_SEARCH_API_VERSION = "7.1"
_PACKAGE_SEARCH_API_VERSION = "7.1"

_ResultT = TypeVar("_ResultT", bound=AdoBaseModel)


class _SearchProjectRef(AdoBaseModel):
    """Project reference embedded in a search result."""

    name: str = ""
    id: str = ""


class _SearchRepositoryRef(AdoBaseModel):
    """Repository reference embedded in a code search result."""

    name: str = ""
    id: str = ""
    type: str | None = None


class _SearchVersion(AdoBaseModel):
    """Branch version entry in a code search result."""

    branch_name: str | None = None
    change_id: str | None = None


class _SearchWikiRef(AdoBaseModel):
    """Wiki reference embedded in a wiki search result."""

    id: str = ""
    name: str = ""
    mapped_path: str | None = None


class _SearchCollectionRef(AdoBaseModel):
    """Collection reference embedded in a search result."""

    name: str = ""


class _SearchHit(AdoBaseModel):
    """A single field hit in a work-item or wiki search result."""

    field_reference_name: str | None = None
    highlights: list[str] | None = None


class _PackageView(AdoBaseModel):
    """A feed view entry in a package search result."""

    name: str = ""


class _PackageVersion(AdoBaseModel):
    """A version entry in a package search result."""

    version: str = ""


class _PackageFeed(AdoBaseModel):
    """A feed entry in a package search result."""

    name: str = ""
    id: str = ""


class SearchSortOption(AdoBaseModel):
    """Sort option for search requests."""

    field: str
    sort_order: str = "ASC"


class SearchFacetResult(AdoBaseModel):
    """A single facet bucket in a search response."""

    name: str
    id: str
    result_count: int = 0


class SearchRequest(AdoBaseModel):
    """Shared request body for all ADO search APIs.

    All four search endpoints (code, work item, wiki, package) accept
    this schema.  Pass a ``SearchRequest`` directly to the work-item,
    wiki, and package search functions; use ``CodeSearchRequest`` for
    code search, which adds the ``include_snippet`` flag.
    """

    search_text: str
    skip: int = 0
    top: int = Field(default=25, alias="$top")
    filters: dict[str, list[str]] | None = None
    order_by: list[SearchSortOption] | None = Field(default=None, alias="$orderBy")
    include_facets: bool = False


class CodeSearchRequest(SearchRequest):
    """Request body for the ADO code search API.

    Extends ``SearchRequest`` with ``include_snippet``, which controls
    whether matched code snippets are included in results.
    """

    include_snippet: bool = False


class CodeSearchResult(AdoBaseModel):
    """A single result from the code search API."""

    file_name: str = ""
    path: str = ""
    project: _SearchProjectRef = Field(default_factory=_SearchProjectRef)
    repository: _SearchRepositoryRef = Field(default_factory=_SearchRepositoryRef)
    versions: list[_SearchVersion] = Field(default_factory=list)
    matches: dict[str, Any] = Field(default_factory=dict)
    content_id: str = ""


class WorkItemSearchResult(AdoBaseModel):
    """A single result from the work item search API."""

    fields: dict[str, str] = Field(default_factory=dict)
    hits: list[_SearchHit] = Field(default_factory=list)
    url: str | None = None


class WikiSearchResult(AdoBaseModel):
    """A single result from the wiki search API."""

    file_name: str = ""
    path: str = ""
    project: _SearchProjectRef = Field(default_factory=_SearchProjectRef)
    wiki: _SearchWikiRef = Field(default_factory=_SearchWikiRef)
    hits: list[_SearchHit] = Field(default_factory=list)
    collection: _SearchCollectionRef = Field(default_factory=_SearchCollectionRef)


class PackageSearchResult(AdoBaseModel):
    """A single result from the package search API."""

    name: str = ""
    description: str = ""
    views: list[_PackageView] = Field(default_factory=list)
    versions: list[_PackageVersion] = Field(default_factory=list)
    feeds: list[_PackageFeed] = Field(default_factory=list)
    protocol_type: str = ""


class SearchResponse(AdoBaseModel, Generic[_ResultT]):
    """Shared response shape for all ADO search APIs."""

    count: int = 0
    results: list[_ResultT] = Field(default_factory=list)


class CodeSearchResponse(SearchResponse[CodeSearchResult]):
    """Response from the code search API."""


class WorkItemSearchResponse(SearchResponse[WorkItemSearchResult]):
    """Response from the work item search API."""


class WikiSearchResponse(SearchResponse[WikiSearchResult]):
    """Response from the wiki search API."""


class PackageSearchResponse(SearchResponse[PackageSearchResult]):
    """Response from the package search API."""


def get_search_api_call(
    session: requests.Session,
    org_name: str,
) -> ApiCall:
    """Build the org-scoped search API call (almsearch.dev.azure.com).

    Args:
        session: Authenticated ``requests.Session`` (from
            :func:`~pyado.raw.get_session` or
            :func:`~pyado.raw.get_bearer_session`).
        org_name: Organisation name (e.g. ``"myorg"``).

    Returns:
        ApiCall pointing at the org-level search endpoint.
    """
    url: AdoUrl = _URL_ADAPTER.validate_python(f"{_SEARCH_BASE_URL}/{org_name}/_apis")
    return ApiCall(session=session, url=url)


def post_code_search(
    search_api_call: ApiCall,
    request: CodeSearchRequest,
) -> Iterator[CodeSearchResult]:
    """Search for code across the organisation or project.

    Args:
        search_api_call: Org-scoped or project-scoped search API call (from
            get_search_api_call or service.make_search_project_api_call).
        request: Search request parameters.

    Yields:
        CodeSearchResult for each matching code file.
    """
    body = request.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
    )
    body["searchText"] = request.search_text
    body["skip"] = request.skip
    body["$top"] = request.top
    result = search_api_call.post(
        "search",
        "codesearchresults",
        version=_CODE_SEARCH_API_VERSION,
        json=body,
    )
    response = CodeSearchResponse.model_validate(result)
    yield from response.results


def post_work_item_search(
    search_api_call: ApiCall,
    request: SearchRequest,
) -> Iterator[WorkItemSearchResult]:
    """Search for work items across the organisation or project.

    Args:
        search_api_call: Org-scoped or project-scoped search API call (from
            get_search_api_call or service.make_search_project_api_call).
        request: Search request parameters.

    Yields:
        WorkItemSearchResult for each matching work item.
    """
    body = request.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
    )
    body["searchText"] = request.search_text
    body["skip"] = request.skip
    body["$top"] = request.top
    result = search_api_call.post(
        "search",
        "workitemsearchresults",
        version=_WORK_ITEM_SEARCH_API_VERSION,
        json=body,
    )
    response = WorkItemSearchResponse.model_validate(result)
    yield from response.results


def post_wiki_search(
    search_api_call: ApiCall,
    request: SearchRequest,
) -> Iterator[WikiSearchResult]:
    """Search for wiki pages across the organisation or project.

    Args:
        search_api_call: Org-scoped or project-scoped search API call (from
            get_search_api_call or service.make_search_project_api_call).
        request: Search request parameters.

    Yields:
        WikiSearchResult for each matching wiki page.
    """
    body = request.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
    )
    body["searchText"] = request.search_text
    body["skip"] = request.skip
    body["$top"] = request.top
    result = search_api_call.post(
        "search",
        "wikisearchresults",
        version=_WIKI_SEARCH_API_VERSION,
        json=body,
    )
    response = WikiSearchResponse.model_validate(result)
    yield from response.results


def post_package_search(
    search_api_call: ApiCall,
    request: SearchRequest,
) -> Iterator[PackageSearchResult]:
    """Search for packages across the organisation or project.

    Args:
        search_api_call: Org-scoped or project-scoped search API call (from
            get_search_api_call or service.make_search_project_api_call).
        request: Search request parameters.

    Yields:
        PackageSearchResult for each matching package.
    """
    body = request.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
    )
    body["searchText"] = request.search_text
    body["skip"] = request.skip
    body["$top"] = request.top
    result = search_api_call.post(
        "search",
        "packagesearchresults",
        version=_PACKAGE_SEARCH_API_VERSION,
        json=body,
    )
    response = PackageSearchResponse.model_validate(result)
    yield from response.results
