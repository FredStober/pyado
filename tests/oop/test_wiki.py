"""Tests for pyado.oop Wiki and project wiki methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import uuid4

from pyado.oop import Wiki
from pyado.raw import (
    WikiInfo,
    WikiPage,
    WikiPageAttachment,
    WikiPageDetail,
    WikiType,
)
from tests.oop.conftest import (
    _make_project,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _wiki_info(name: str = "MyProject Wiki") -> WikiInfo:
    return WikiInfo.model_validate(
        {
            "id": str(uuid4()),
            "name": name,
            "type": "projectWiki",
            "projectId": str(uuid4()),
        }
    )


def _wiki_page(path: str = "/README") -> WikiPage:
    return WikiPage.model_validate({"id": 1, "path": path, "order": 0})


# ---------------------------------------------------------------------------
# Wiki class
# ---------------------------------------------------------------------------


class TestWikiProperties:
    def test_id_returns_uuid(self) -> None:
        info = _wiki_info()
        wiki = Wiki(_make_project(), info)
        assert wiki.id == info.id

    def test_name_returns_name(self) -> None:
        info = _wiki_info("DevWiki")
        wiki = Wiki(_make_project(), info)
        assert wiki.name == "DevWiki"

    def test_type_returns_wiki_type(self) -> None:
        info = _wiki_info()
        wiki = Wiki(_make_project(), info)
        assert wiki.type == WikiType.PROJECT_WIKI

    def test_type_returns_none_when_absent(self) -> None:
        info = WikiInfo.model_validate({"id": str(uuid4()), "name": "CodeWiki"})
        wiki = Wiki(_make_project(), info)
        assert wiki.type is None

    def test_info_returns_stored_info(self) -> None:
        info = _wiki_info()
        wiki = Wiki(_make_project(), info)
        assert wiki.info is info

    def test_project_back_reference(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        assert wiki.project is proj

    def test_org_back_reference(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        assert wiki.org is proj.org


class TestWikiIterPages:
    def test_iter_pages_yields_wiki_pages(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        page = _wiki_page()
        with patch("pyado.oop.overview.wiki.raw.get_wiki_pages") as mock_get:
            mock_get.return_value = [page]
            result = list(wiki.iter_pages())
        assert len(result) == 1
        assert isinstance(result[0], WikiPage)

    def test_iter_pages_passes_recursion_level(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.get_wiki_pages") as mock_get:
            mock_get.return_value = []
            list(wiki.iter_pages(recursion_level=5))
        _, kwargs = mock_get.call_args
        assert kwargs["recursion_level"] == 5


class TestWikiListPages:
    def test_list_pages_delegates_to_iter_pages(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        page = _wiki_page()
        with patch.object(wiki, "iter_pages", return_value=iter([page])) as mock_iter:
            result = wiki.list_pages()
        mock_iter.assert_called_once_with(recursion_level=2)
        assert len(result) == 1
        assert isinstance(result[0], WikiPage)

    def test_list_pages_passes_recursion_level(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch.object(wiki, "iter_pages", return_value=iter([])) as mock_iter:
            wiki.list_pages(recursion_level=5)
        mock_iter.assert_called_once_with(recursion_level=5)


class TestWikiGetPage:
    def _make_detail(self, path: str = "/README") -> WikiPageDetail:
        return WikiPageDetail.model_validate({"id": 1, "path": path, "content": "# Hi"})

    def test_get_page_delegates_to_raw(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        detail = self._make_detail()
        with patch("pyado.oop.overview.wiki.raw.get_wiki_page") as mock_get:
            mock_get.return_value = detail
            result = wiki.get_page("/README")
        assert result is detail
        assert isinstance(result, WikiPageDetail)

    def test_get_page_forwards_include_content(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.get_wiki_page") as mock_get:
            mock_get.return_value = self._make_detail()
            wiki.get_page("/README", include_content=False)
        _, kwargs = mock_get.call_args
        assert kwargs["include_content"] is False


class TestWikiPutPage:
    def _make_detail(self) -> WikiPageDetail:
        return WikiPageDetail.model_validate(
            {"id": 2, "path": "/NewPage", "content": "hello"}
        )

    def test_put_page_delegates_to_raw(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        detail = self._make_detail()
        with patch("pyado.oop.overview.wiki.raw.put_wiki_page") as mock_put:
            mock_put.return_value = detail
            result = wiki.put_page("/NewPage", "hello")
        assert result is detail
        assert isinstance(result, WikiPageDetail)

    def test_put_page_forwards_version(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.put_wiki_page") as mock_put:
            mock_put.return_value = self._make_detail()
            wiki.put_page("/NewPage", "hello", version=42)
        _, kwargs = mock_put.call_args
        assert kwargs["version"] == 42

    def test_put_page_omits_version_by_default(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.put_wiki_page") as mock_put:
            mock_put.return_value = self._make_detail()
            wiki.put_page("/NewPage", "hello")
        _, kwargs = mock_put.call_args
        assert kwargs["version"] is None


class TestWikiDeletePage:
    def _make_detail(self) -> WikiPageDetail:
        return WikiPageDetail.model_validate({"id": 3, "path": "/Old"})

    def test_delete_page_delegates_to_raw(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        detail = self._make_detail()
        with patch("pyado.oop.overview.wiki.raw.delete_wiki_page") as mock_del:
            mock_del.return_value = detail
            result = wiki.delete_page("/Old", version=7)
        assert result is detail
        assert isinstance(result, WikiPageDetail)

    def test_delete_page_forwards_version(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.delete_wiki_page") as mock_del:
            mock_del.return_value = self._make_detail()
            wiki.delete_page("/Old", version=7)
        _, kwargs = mock_del.call_args
        assert kwargs["version"] == 7


class TestWikiListPageAttachments:
    def test_list_page_attachments_delegates_to_raw(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        attachment = WikiPageAttachment.model_validate({"name": "image.png"})
        with patch("pyado.oop.overview.wiki.raw.get_wiki_page_attachments") as mock_att:
            mock_att.return_value = [attachment]
            result = wiki.list_page_attachments(1)
        assert len(result) == 1
        assert isinstance(result[0], WikiPageAttachment)
        assert result[0].name == "image.png"

    def test_list_page_attachments_passes_page_id(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.get_wiki_page_attachments") as mock_att:
            mock_att.return_value = []
            wiki.list_page_attachments(99)
        args, _ = mock_att.call_args
        assert args[2] == 99


# ---------------------------------------------------------------------------
# Project wiki methods
# ---------------------------------------------------------------------------


class TestProjectWikis:
    def test_iter_wikis_yields_wiki_objects(self) -> None:
        proj = _make_project()
        info = _wiki_info()
        with patch("pyado.oop.project.raw.iter_wikis") as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(proj.iter_wikis())
        assert len(result) == 1
        assert isinstance(result[0], Wiki)
        assert result[0].name == info.name

    def test_iter_wikis_empty(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.iter_wikis") as mock_iter:
            mock_iter.return_value = iter([])
            result = list(proj.iter_wikis())
        assert result == []

    def test_list_wikis_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_wikis", return_value=iter([])):
            assert proj.list_wikis() == []
