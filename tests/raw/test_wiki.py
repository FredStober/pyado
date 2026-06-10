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
    WikiPageAttachment,
    WikiPageDetail,
    delete_wiki_page,
    get_wiki_page,
    get_wiki_page_attachments,
    get_wiki_pages,
    iter_wikis,
    list_wikis,
    put_wiki_page,
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


class TestGetWikiPage:
    @staticmethod
    def test_returns_wiki_page_detail(api_call: ApiCall) -> None:
        payload = {
            "id": 42,
            "path": "/Overview",
            "isParentPage": False,
            "subPages": [],
            "content": "# Overview\nHello.",
            "gitItemPath": "/Overview.md",
            "remoteUrl": "https://dev.azure.com/org/proj/_wiki/wikis/w/42/Overview",
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            page = get_wiki_page(api_call, UUID(_WIKI_ID), "/Overview")
        assert isinstance(page, WikiPageDetail)
        assert page.id == 42
        assert page.path == "/Overview"
        assert page.content == "# Overview\nHello."
        assert page.git_item_path == "/Overview.md"

    @staticmethod
    def test_content_absent_when_include_content_false(api_call: ApiCall) -> None:
        payload = {"id": 5, "path": "/Setup", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            page = get_wiki_page(
                api_call, UUID(_WIKI_ID), "/Setup", include_content=False
            )
        assert page.content is None

    @staticmethod
    def test_passes_include_content_parameter(api_call: ApiCall) -> None:
        payload = {"id": 1, "path": "/"}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_wiki_page(api_call, UUID(_WIKI_ID), "/", include_content=False)
        _, call_kwargs = mock_req.call_args
        assert call_kwargs["params"]["includeContent"] is False


class TestPutWikiPage:
    @staticmethod
    def test_create_new_page_returns_detail(api_call: ApiCall) -> None:
        payload = {"id": 10, "path": "/NewPage", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            page = put_wiki_page(api_call, UUID(_WIKI_ID), "/NewPage", "# New")
        assert isinstance(page, WikiPageDetail)
        assert page.path == "/NewPage"

    @staticmethod
    def test_update_page_sends_if_match_header(api_call: ApiCall) -> None:
        payload = {"id": 10, "path": "/NewPage", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_wiki_page(api_call, UUID(_WIKI_ID), "/NewPage", "# Updated", version=3)
        _, call_kwargs = mock_req.call_args
        assert call_kwargs["headers"]["If-Match"] == '"3"'

    @staticmethod
    def test_create_page_sends_no_if_match_header(api_call: ApiCall) -> None:
        payload = {
            "id": 11,
            "path": "/AnotherPage",
            "isParentPage": False,
            "subPages": [],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_wiki_page(api_call, UUID(_WIKI_ID), "/AnotherPage", "# Content")
        _, call_kwargs = mock_req.call_args
        assert "If-Match" not in call_kwargs["headers"]

    @staticmethod
    def test_sends_content_in_body(api_call: ApiCall) -> None:
        payload = {"id": 12, "path": "/Page", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_wiki_page(api_call, UUID(_WIKI_ID), "/Page", "My content")
        _, call_kwargs = mock_req.call_args
        assert call_kwargs["json"]["content"] == "My content"


class TestDeleteWikiPage:
    @staticmethod
    def test_returns_wiki_page_detail(api_call: ApiCall) -> None:
        payload = {"id": 20, "path": "/OldPage", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            page = delete_wiki_page(api_call, UUID(_WIKI_ID), "/OldPage", version=7)
        assert isinstance(page, WikiPageDetail)
        assert page.id == 20

    @staticmethod
    def test_sends_if_match_header(api_call: ApiCall) -> None:
        payload = {"id": 20, "path": "/OldPage", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_wiki_page(api_call, UUID(_WIKI_ID), "/OldPage", version=7)
        _, call_kwargs = mock_req.call_args
        assert call_kwargs["headers"]["If-Match"] == '"7"'

    @staticmethod
    def test_uses_delete_method(api_call: ApiCall) -> None:
        payload = {"id": 20, "path": "/OldPage", "isParentPage": False, "subPages": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_wiki_page(api_call, UUID(_WIKI_ID), "/OldPage", version=1)
        (method,) = mock_req.call_args.args
        assert method == "DELETE"


class TestGetWikiPageAttachments:
    @staticmethod
    def test_returns_list_of_attachments(api_call: ApiCall) -> None:
        payload = {
            "count": 2,
            "value": [{"name": "diagram.png"}, {"name": "notes.txt"}],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            attachments = get_wiki_page_attachments(api_call, UUID(_WIKI_ID), 42)
        assert len(attachments) == 2
        assert all(isinstance(att, WikiPageAttachment) for att in attachments)
        assert attachments[0].name == "diagram.png"
        assert attachments[1].name == "notes.txt"

    @staticmethod
    def test_returns_empty_list_when_no_attachments(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            attachments = get_wiki_page_attachments(api_call, UUID(_WIKI_ID), 1)
        assert attachments == []
