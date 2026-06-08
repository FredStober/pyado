"""Tests for pyado.raw.secure_file — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import uuid4

import requests

from pyado.raw import (
    ApiCall,
    SecureFileInfo,
    delete_secure_file,
    get_secure_file,
    get_secure_file_api_call,
    iter_secure_files,
    list_secure_files,
)
from tests.conftest import _make_mock_response

_FILE_ID = uuid4()


class TestGetSecureFileApiCall:
    @staticmethod
    def test_url_contains_secure_file_id(api_call: ApiCall) -> None:
        result = get_secure_file_api_call(api_call, _FILE_ID)
        assert str(_FILE_ID) in result.url.unicode_string()

    @staticmethod
    def test_url_contains_securefiles_segment(api_call: ApiCall) -> None:
        result = get_secure_file_api_call(api_call, _FILE_ID)
        assert "securefiles" in result.url.unicode_string()


class TestListSecureFiles:
    @staticmethod
    def test_returns_list_of_secure_file_infos(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [{"id": str(_FILE_ID), "name": "cert.p12"}],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_secure_files(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], SecureFileInfo)


class TestIterSecureFiles:
    @staticmethod
    def test_yields_secure_file_infos(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [{"id": str(_FILE_ID), "name": "cert.p12"}],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_secure_files(api_call))
        assert len(results) == 1
        assert isinstance(results[0], SecureFileInfo)
        assert results[0].name == "cert.p12"

    @staticmethod
    def test_returns_empty_when_no_files(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_secure_files(api_call))
        assert results == []


class TestGetSecureFile:
    @staticmethod
    def test_returns_secure_file_info(api_call: ApiCall) -> None:
        payload = {"id": str(_FILE_ID), "name": "key.pem"}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_secure_file(api_call, _FILE_ID)
        assert isinstance(result, SecureFileInfo)
        assert result.id == _FILE_ID
        assert result.name == "key.pem"

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        payload = {"id": str(_FILE_ID), "name": "x.pem"}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_secure_file(api_call, _FILE_ID)
        assert mock_req.call_args.args[0] == "GET"


class TestDeleteSecureFile:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_secure_file(api_call)
        assert mock_req.call_args.args[0] == "DELETE"
