"""Tests for pyado.oop Wiki and project wiki methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import uuid4

from pyado.oop import Wiki
from pyado.raw import WikiInfo, WikiPage, WikiType
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


class TestWikiGetPages:
    def test_get_pages_delegates_to_raw(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        page = _wiki_page()
        with patch("pyado.oop.overview.wiki.raw.get_wiki_pages") as mock_get:
            mock_get.return_value = [page]
            result = wiki.get_pages()
        assert len(result) == 1
        assert isinstance(result[0], WikiPage)

    def test_get_pages_passes_recursion_level(self) -> None:
        proj = _make_project()
        wiki = Wiki(proj, _wiki_info())
        with patch("pyado.oop.overview.wiki.raw.get_wiki_pages") as mock_get:
            mock_get.return_value = []
            wiki.get_pages(recursion_level=5)
        _, kwargs = mock_get.call_args
        assert kwargs["recursion_level"] == 5


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
