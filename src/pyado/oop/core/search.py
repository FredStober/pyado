"""OOP search wrappers for the Azure DevOps Search API."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    CodeSearchRequest,
    CodeSearchResult,
    PackageSearchResult,
    SearchRequest,
    WikiSearchResult,
    WorkItemSearchResult,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project
    from pyado.oop.service import AzureDevOpsService

__all__ = ["OrganizationSearch", "ProjectSearch"]


class OrganizationSearch:
    """Org-wide search via the Azure DevOps Search API.

    **ADO concept:** the ADO Search API
    (``almsearch.dev.azure.com/{org}/_apis/search/``) allows full-text search
    across code, work items, wiki pages, and packages at the organisation level.
    Results can be filtered to specific projects via ``filters``.

    **Why it exists:** bundles the service reference and constructs the
    org-scoped search API call automatically so callers don't need to manage
    the different hostname.

    Instances are obtained from ``organization.search`` or ``service.org.search``.

    Attributes:
        _service: The AzureDevOpsService that owns this search scope.
    """

    def __init__(self, service: "AzureDevOpsService") -> None:
        """Construct an OrganizationSearch.

        Args:
            service: The AzureDevOpsService that owns this search scope.
        """
        self._service = service

    def search_code(
        self,
        request: CodeSearchRequest,
    ) -> Iterator[CodeSearchResult]:
        """Search for code across the organisation.

        Args:
            request: Search request parameters (text, filters, paging, etc.).

        Yields:
            CodeSearchResult for each matching code file.
        """
        yield from raw.post_code_search(
            self._service.oop_api.search_api_call,
            request,
        )

    def search_work_items(
        self,
        request: SearchRequest,
    ) -> Iterator[WorkItemSearchResult]:
        """Search for work items across the organisation.

        Args:
            request: Search request parameters.

        Yields:
            WorkItemSearchResult for each matching work item.
        """
        yield from raw.post_work_item_search(
            self._service.oop_api.search_api_call,
            request,
        )

    def search_wiki(
        self,
        request: SearchRequest,
    ) -> Iterator[WikiSearchResult]:
        """Search for wiki pages across the organisation.

        Args:
            request: Search request parameters.

        Yields:
            WikiSearchResult for each matching wiki page.
        """
        yield from raw.post_wiki_search(
            self._service.oop_api.search_api_call,
            request,
        )

    def search_packages(
        self,
        request: SearchRequest,
    ) -> Iterator[PackageSearchResult]:
        """Search for packages across the organisation.

        Args:
            request: Search request parameters.

        Yields:
            PackageSearchResult for each matching package.
        """
        yield from raw.post_package_search(
            self._service.oop_api.search_api_call,
            request,
        )


class ProjectSearch:
    """Project-scoped search via the Azure DevOps Search API.

    **ADO concept:** the ADO Search API supports project-scoped search at
    ``almsearch.dev.azure.com/{org}/{project}/_apis/search/``.  Results are
    automatically restricted to the owning project.

    **Why it exists:** bundles the project reference and constructs the
    project-scoped search API call automatically.

    Instances are obtained from ``project.search``.

    Attributes:
        _project: The Project that owns this search scope.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a ProjectSearch.

        Args:
            project: The Project that owns this search scope.
        """
        self._project = project

    def search_code(
        self,
        request: CodeSearchRequest,
    ) -> Iterator[CodeSearchResult]:
        """Search for code within this project.

        Args:
            request: Search request parameters.

        Yields:
            CodeSearchResult for each matching code file.
        """
        yield from raw.post_code_search(
            self._project._service.oop_api.make_search_project_api_call(  # noqa: SLF001
                self._project.name
            ),
            request,
        )

    def search_work_items(
        self,
        request: SearchRequest,
    ) -> Iterator[WorkItemSearchResult]:
        """Search for work items within this project.

        Args:
            request: Search request parameters.

        Yields:
            WorkItemSearchResult for each matching work item.
        """
        yield from raw.post_work_item_search(
            self._project._service.oop_api.make_search_project_api_call(  # noqa: SLF001
                self._project.name
            ),
            request,
        )

    def search_wiki(
        self,
        request: SearchRequest,
    ) -> Iterator[WikiSearchResult]:
        """Search for wiki pages within this project.

        Args:
            request: Search request parameters.

        Yields:
            WikiSearchResult for each matching wiki page.
        """
        yield from raw.post_wiki_search(
            self._project._service.oop_api.make_search_project_api_call(  # noqa: SLF001
                self._project.name
            ),
            request,
        )

    def search_packages(
        self,
        request: SearchRequest,
    ) -> Iterator[PackageSearchResult]:
        """Search for packages within this project.

        Args:
            request: Search request parameters.

        Yields:
            PackageSearchResult for each matching package.
        """
        yield from raw.post_package_search(
            self._project._service.oop_api.search_api_call,  # noqa: SLF001
            request,
        )
