"""Integration tests for OrganizationSearch and ProjectSearch OOP classes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Organization, OrganizationSearch, Project, ProjectSearch
from pyado.raw import CodeSearchRequest, SearchRequest
from tests.integration.raw._support import _take, console


def test_search(org: Organization, proj: Project) -> None:
    """Exercise code, work-item, wiki, and package search at org and project level."""
    console.print("\n=== Search ===")
    org_search: OrganizationSearch = org.search
    proj_search: ProjectSearch = proj.search
    _take(org_search.search_code(CodeSearchRequest(search_text="def ", top=5)), 3)
    _take(org_search.search_work_items(SearchRequest(search_text="smoke", top=5)), 3)
    _take(org_search.search_wiki(SearchRequest(search_text="smoke", top=5)), 3)
    _take(org_search.search_packages(SearchRequest(search_text="pyado", top=5)), 3)
    _take(proj_search.search_code(CodeSearchRequest(search_text="def ", top=5)), 3)
    _take(proj_search.search_work_items(SearchRequest(search_text="smoke", top=5)), 3)
    _take(proj_search.search_wiki(SearchRequest(search_text="smoke", top=5)), 3)
    _take(proj_search.search_packages(SearchRequest(search_text="pyado", top=5)), 3)
