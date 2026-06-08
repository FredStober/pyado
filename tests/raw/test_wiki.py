"""Tests for pyado.raw.wiki — wiki API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    WikiInfo,
    WikiPage,
    get_wiki_pages,
    iter_wikis,
    list_wikis,
)
from tests.conftest import _make_mock_response

_WIKI_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class TestListWikis:
    @staticmethod
    def test_returns_list_of_wikis(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": _WIKI_ID,
                    "name": "ProjectWiki",
                    "type": "projectWiki",
                    "projectId": "proj-id",
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_wikis(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], WikiInfo)
        assert results[0].id == UUID(_WIKI_ID)
        assert results[0].name == "ProjectWiki"
        assert results[0].type == "projectWiki"

    @staticmethod
    def test_returns_empty_list_when_no_wikis(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_wikis(api_call)
        assert results == []

    @staticmethod
    def test_optional_fields_default_to_none(api_call: ApiCall) -> None:
        payload = {"value": [{"id": _WIKI_ID, "name": "MinimalWiki"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_wikis(api_call)
        assert results[0].type is None
        assert results[0].project_id is None
        assert results[0].repository_id is None


class TestIterWikis:
    @staticmethod
    def test_yields_wikis(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {"id": _WIKI_ID, "name": "Wiki1"},
                {"id": _WIKI_ID, "name": "Wiki2"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_wikis(api_call))
        assert len(results) == 2


class TestGetWikiPages:
    @staticmethod
    def test_returns_sub_pages(api_call: ApiCall) -> None:
        payload = {
            "id": 1,
            "path": "/",
            "isParentPage": True,
            "subPages": [
                {"id": 2, "path": "/Overview", "isParentPage": False, "subPages": []},
                {"id": 3, "path": "/Setup", "isParentPage": False, "subPages": []},
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            pages = get_wiki_pages(api_call, UUID(_WIKI_ID))
        assert len(pages) == 2
        assert all(isinstance(page, WikiPage) for page in pages)
        assert pages[0].path == "/Overview"
        assert pages[1].path == "/Setup"

    @staticmethod
    def test_returns_empty_list_when_no_sub_pages(api_call: ApiCall) -> None:
        payload = {"id": 1, "path": "/", "isParentPage": True, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            pages = get_wiki_pages(api_call, UUID(_WIKI_ID))
        assert pages == []

    @staticmethod
    def test_returns_empty_list_when_response_is_empty(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            pages = get_wiki_pages(api_call, UUID(_WIKI_ID))
        assert pages == []
