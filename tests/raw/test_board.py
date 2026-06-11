"""Tests for pyado.raw.boards.board — board configuration wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch

import requests

from pyado.raw._core import ApiCall
from pyado.raw.boards.board import (
    get_board_columns,
    get_board_rows,
    get_boards,
    get_card_settings,
    put_board_columns,
    put_board_rows,
    put_card_settings,
)
from tests.conftest import _make_mock_response

_BOARD_ID = "board-guid-001"


class TestGetBoards:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"id": _BOARD_ID, "name": "Backlog"},
                {"id": "board-guid-002", "name": "Sprint"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_boards(api_call)
        assert len(result) == 2
        assert result[0]["id"] == _BOARD_ID

    @staticmethod
    def test_returns_empty_when_no_value(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response({})
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_boards(api_call)
        assert result == []


class TestGetBoardColumns:
    @staticmethod
    def test_returns_columns(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [{"id": "col-1", "name": "New"}, {"id": "col-2", "name": "Active"}]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_board_columns(api_call, _BOARD_ID)
        assert len(result) == 2
        assert result[0]["name"] == "New"


class TestPutBoardColumns:
    @staticmethod
    def test_returns_updated_columns(api_call: ApiCall) -> None:
        columns = [{"id": "col-1", "name": "New"}]
        payload: dict[str, Any] = {"value": columns}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_board_columns(api_call, _BOARD_ID, columns)
        assert result == columns


class TestGetBoardRows:
    @staticmethod
    def test_returns_rows(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"value": [{"id": "row-1", "name": "Default"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_board_rows(api_call, _BOARD_ID)
        assert len(result) == 1
        assert result[0]["name"] == "Default"


class TestPutBoardRows:
    @staticmethod
    def test_returns_updated_rows(api_call: ApiCall) -> None:
        rows = [{"id": "row-1", "name": "Default"}]
        payload: dict[str, Any] = {"value": rows}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_board_rows(api_call, _BOARD_ID, rows)
        assert result == rows


class TestGetCardSettings:
    @staticmethod
    def test_returns_settings(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"cards": {"Bug": []}}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_card_settings(api_call, _BOARD_ID)
        assert result == {"cards": {"Bug": []}}


class TestPutCardSettings:
    @staticmethod
    def test_returns_updated_settings(api_call: ApiCall) -> None:
        settings: dict[str, Any] = {"cards": {"Bug": [{"fieldIdentifier": "Title"}]}}
        payload: dict[str, Any] = settings
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_card_settings(api_call, _BOARD_ID, settings)
        assert result == settings
