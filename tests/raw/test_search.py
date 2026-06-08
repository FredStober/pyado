"""Tests for pyado.raw.search — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado.raw import (
    ApiCall,
    CodeSearchRequest,
    CodeSearchResult,
    PackageSearchResult,
    SearchRequest,
    WikiSearchResult,
    WorkItemSearchResult,
    get_search_api_call,
    post_code_search,
    post_package_search,
    post_wiki_search,
    post_work_item_search,
)
from tests.conftest import _make_mock_response


class TestGetSearchApiCall:
    @staticmethod
    def test_returns_api_call() -> None:
        session = requests.Session()
        result = get_search_api_call(session, "myorg")
        assert isinstance(result, ApiCall)
        assert "almsearch.dev.azure.com" in str(result.url)
        assert "myorg" in str(result.url)


class TestPostCodeSearch:
    @staticmethod
    def test_yields_code_search_results(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "results": [
                {
                    "fileName": "main.py",
                    "path": "/src/main.py",
                    "project": {"name": "MyProject", "id": "proj-1"},
                    "repository": {"name": "MyRepo", "id": "repo-1", "type": "git"},
                    "versions": [{"branchName": "main", "changeId": "abc123"}],
                    "matches": {"content": [{"charOffset": 0, "length": 3}]},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        req = CodeSearchRequest(search_text="def foo")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_code_search(api_call, req))
        assert len(results) == 1
        assert isinstance(results[0], CodeSearchResult)
        assert results[0].file_name == "main.py"
        assert results[0].project.name == "MyProject"
        assert results[0].repository.type == "git"
        assert results[0].versions[0].branch_name == "main"
        assert results[0].versions[0].change_id == "abc123"

    @staticmethod
    def test_returns_empty_when_no_results(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "results": []}
        mock_resp = _make_mock_response(payload)
        req = CodeSearchRequest(search_text="nonexistent")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_code_search(api_call, req))
        assert results == []


class TestPostWorkItemSearch:
    @staticmethod
    def test_yields_work_item_results(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "results": [
                {
                    "fields": {"System.Title": "Fix bug"},
                    "hits": [
                        {
                            "fieldReferenceName": "System.Title",
                            "highlights": ["Fix <em>bug</em>"],
                        }
                    ],
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="Fix bug")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_work_item_search(api_call, req))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemSearchResult)
        assert results[0].hits[0].field_reference_name == "System.Title"
        assert results[0].hits[0].highlights == ["Fix <em>bug</em>"]

    @staticmethod
    def test_returns_empty_when_no_results(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "results": []}
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="nothing")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_work_item_search(api_call, req))
        assert results == []


class TestPostWikiSearch:
    @staticmethod
    def test_yields_wiki_results(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "results": [
                {
                    "fileName": "Home.md",
                    "path": "/Home.md",
                    "project": {"name": "MyProject", "id": "proj-1"},
                    "wiki": {"id": "wiki-1", "name": "MyWiki", "mappedPath": "/"},
                    "collection": {"name": "DefaultCollection"},
                    "hits": [
                        {
                            "fieldReferenceName": "content",
                            "highlights": ["introduction"],
                        }
                    ],
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="introduction")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_wiki_search(api_call, req))
        assert len(results) == 1
        assert isinstance(results[0], WikiSearchResult)
        assert results[0].file_name == "Home.md"
        assert results[0].project.name == "MyProject"
        assert results[0].wiki.name == "MyWiki"
        assert results[0].wiki.mapped_path == "/"
        assert results[0].collection.name == "DefaultCollection"
        assert results[0].hits[0].field_reference_name == "content"

    @staticmethod
    def test_returns_empty_when_no_results(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "results": []}
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="nothing")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_wiki_search(api_call, req))
        assert results == []


class TestPostPackageSearch:
    @staticmethod
    def test_yields_package_results(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "results": [
                {
                    "name": "my-package",
                    "description": "A test package",
                    "protocolType": "NuGet",
                    "views": [{"name": "Release"}],
                    "versions": [{"version": "1.0.0"}],
                    "feeds": [{"name": "my-feed", "id": "feed-1"}],
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="my-package")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_package_search(api_call, req))
        assert len(results) == 1
        assert isinstance(results[0], PackageSearchResult)
        assert results[0].name == "my-package"
        assert results[0].views[0].name == "Release"
        assert results[0].versions[0].version == "1.0.0"
        assert results[0].feeds[0].name == "my-feed"
        assert results[0].feeds[0].id == "feed-1"

    @staticmethod
    def test_returns_empty_when_no_results(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "results": []}
        mock_resp = _make_mock_response(payload)
        req = SearchRequest(search_text="nothing")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(post_package_search(api_call, req))
        assert results == []
