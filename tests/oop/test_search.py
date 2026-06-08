"""Tests for pyado.oop.core.search — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

from pyado.oop.core.search import OrganizationSearch, ProjectSearch
from pyado.raw import (
    CodeSearchRequest,
    CodeSearchResult,
    PackageSearchResult,
    SearchRequest,
    WikiSearchResult,
    WorkItemSearchResult,
)
from tests.oop.conftest import _make_project, _make_service


def _code_result() -> CodeSearchResult:
    return CodeSearchResult.model_validate({"fileName": "f.py", "path": "/f.py"})


def _wi_result() -> WorkItemSearchResult:
    return WorkItemSearchResult.model_validate({"fields": {"System.Title": "T"}})


def _wiki_result() -> WikiSearchResult:
    return WikiSearchResult.model_validate({"fileName": "Home.md", "path": "/Home.md"})


def _pkg_result() -> PackageSearchResult:
    return PackageSearchResult.model_validate({"name": "pkg", "protocolType": "NuGet"})


class TestOrganizationSearch:
    def test_search_code_yields_results(self) -> None:
        svc = _make_service()
        org_search = OrganizationSearch(svc)
        req = CodeSearchRequest(search_text="foo")
        with patch(
            "pyado.oop.core.search.raw.post_code_search",
            return_value=iter([_code_result()]),
        ):
            results = list(org_search.search_code(req))
        assert len(results) == 1
        assert isinstance(results[0], CodeSearchResult)

    def test_search_work_items_yields_results(self) -> None:
        svc = _make_service()
        org_search = OrganizationSearch(svc)
        req = SearchRequest(search_text="bug")
        with patch(
            "pyado.oop.core.search.raw.post_work_item_search",
            return_value=iter([_wi_result()]),
        ):
            results = list(org_search.search_work_items(req))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemSearchResult)

    def test_search_wiki_yields_results(self) -> None:
        svc = _make_service()
        org_search = OrganizationSearch(svc)
        req = SearchRequest(search_text="intro")
        with patch(
            "pyado.oop.core.search.raw.post_wiki_search",
            return_value=iter([_wiki_result()]),
        ):
            results = list(org_search.search_wiki(req))
        assert len(results) == 1
        assert isinstance(results[0], WikiSearchResult)

    def test_search_packages_yields_results(self) -> None:
        svc = _make_service()
        org_search = OrganizationSearch(svc)
        req = SearchRequest(search_text="my-pkg")
        with patch(
            "pyado.oop.core.search.raw.post_package_search",
            return_value=iter([_pkg_result()]),
        ):
            results = list(org_search.search_packages(req))
        assert len(results) == 1
        assert isinstance(results[0], PackageSearchResult)


class TestProjectSearch:
    def test_search_code_yields_results(self) -> None:
        proj = _make_project()
        proj_search = ProjectSearch(proj)
        req = CodeSearchRequest(search_text="foo")
        with patch(
            "pyado.oop.core.search.raw.post_code_search",
            return_value=iter([_code_result()]),
        ):
            results = list(proj_search.search_code(req))
        assert len(results) == 1
        assert isinstance(results[0], CodeSearchResult)

    def test_search_work_items_yields_results(self) -> None:
        proj = _make_project()
        proj_search = ProjectSearch(proj)
        req = SearchRequest(search_text="bug")
        with patch(
            "pyado.oop.core.search.raw.post_work_item_search",
            return_value=iter([_wi_result()]),
        ):
            results = list(proj_search.search_work_items(req))
        assert len(results) == 1

    def test_search_wiki_yields_results(self) -> None:
        proj = _make_project()
        proj_search = ProjectSearch(proj)
        req = SearchRequest(search_text="intro")
        with patch(
            "pyado.oop.core.search.raw.post_wiki_search",
            return_value=iter([_wiki_result()]),
        ):
            results = list(proj_search.search_wiki(req))
        assert len(results) == 1

    def test_search_packages_yields_results(self) -> None:
        proj = _make_project()
        proj_search = ProjectSearch(proj)
        req = SearchRequest(search_text="my-pkg")
        with patch(
            "pyado.oop.core.search.raw.post_package_search",
            return_value=iter([_pkg_result()]),
        ):
            results = list(proj_search.search_packages(req))
        assert len(results) == 1
