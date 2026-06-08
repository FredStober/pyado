"""Tests for pyado.oop SecureFile — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID, uuid4

from pyado.oop.pipelines.secure_file import SecureFile
from pyado.raw import SecureFileInfo
from tests.oop.conftest import _api_call, _make_project

_FILE_ID = uuid4()


def _secure_file_info(
    file_id: UUID | None = None,
) -> SecureFileInfo:
    return SecureFileInfo.model_validate(
        {"id": str(file_id or _FILE_ID), "name": "signing.p12"}
    )


def _make_secure_file(info: SecureFileInfo | None = None) -> SecureFile:
    proj = _make_project()
    sf_api_call = _api_call()
    return SecureFile(proj, sf_api_call, info or _secure_file_info())


class TestSecureFile:
    def test_constructor_stores_project_api_call_and_info(self) -> None:
        proj = _make_project()
        sf_api_call = _api_call()
        info = _secure_file_info()
        sf = SecureFile(proj, sf_api_call, info)
        assert sf._project is proj
        assert sf._api_call is sf_api_call
        assert sf._info is info
        assert sf._file_id == _FILE_ID

    def test_info_returns_cached_info(self) -> None:
        info = _secure_file_info()
        sf = _make_secure_file(info)
        assert sf.info is info

    def test_info_lazy_fetches_when_none(self) -> None:
        proj = _make_project()
        sf_api_call = _api_call()
        info = _secure_file_info()
        sf = SecureFile(proj, sf_api_call, info)
        sf._info = None
        with patch("pyado.oop.pipelines.secure_file.raw.get_secure_file") as mock_get:
            mock_get.return_value = _secure_file_info()
            result = sf.info
        mock_get.assert_called_once()
        assert result is not None

    def test_id_returns_file_id(self) -> None:
        sf = _make_secure_file()
        assert sf.id == _FILE_ID

    def test_name_returns_file_name(self) -> None:
        sf = _make_secure_file()
        assert sf.name == "signing.p12"

    def test_api_call_returns_stored_api_call(self) -> None:
        sf_api_call = _api_call()
        proj = _make_project()
        sf = SecureFile(proj, sf_api_call, _secure_file_info())
        assert sf.api_call is sf_api_call

    def test_project_returns_back_reference(self) -> None:
        proj = _make_project()
        sf = SecureFile(proj, _api_call(), _secure_file_info())
        assert sf.project is proj

    def test_org_returns_project_org(self) -> None:
        proj = _make_project()
        sf = SecureFile(proj, _api_call(), _secure_file_info())
        assert sf.org is proj.org

    def test_refresh_clears_cached_info(self) -> None:
        sf = _make_secure_file()
        sf.refresh()
        assert sf._info is None

    def test_delete_calls_raw_delete(self) -> None:
        sf = _make_secure_file()
        with patch(
            "pyado.oop.pipelines.secure_file.raw.delete_secure_file"
        ) as mock_del:
            sf.delete()
        mock_del.assert_called_once_with(sf._api_call)
