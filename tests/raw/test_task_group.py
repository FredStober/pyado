"""Tests for pyado.raw.pipelines.task_group — task group wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    TaskGroupCreateRequest,
    TaskGroupId,
    TaskGroupInfo,
    TaskGroupUpdateRequest,
    delete_task_group,
    get_task_group,
    iter_task_groups,
    list_task_groups,
    post_task_group,
    put_task_group,
)
from tests.conftest import _make_mock_response

_TASK_GROUP_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_TASK_GROUP_PAYLOAD = {
    "id": _TASK_GROUP_ID,
    "name": "My Task Group",
    "description": "A reusable task sequence",
    "category": "Build",
    "comment": "Initial version",
    "author": "user@example.com",
    "tasks": [
        {
            "task": {
                "id": "11111111-2222-3333-4444-555555555555",
                "versionSpec": "1.*",
            },
            "displayName": "Run script",
            "inputs": {"script": "echo hello"},
        }
    ],
}


class TestListTaskGroups:
    @staticmethod
    def test_returns_list_of_task_groups(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_TASK_GROUP_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_task_groups(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], TaskGroupInfo)
        assert results[0].id == UUID(_TASK_GROUP_ID)
        assert results[0].name == "My Task Group"
        assert results[0].category == "Build"

    @staticmethod
    def test_returns_empty_list_when_no_task_groups(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_task_groups(api_call)
        assert results == []


class TestIterTaskGroups:
    @staticmethod
    def test_yields_task_groups(api_call: ApiCall) -> None:
        payload = {"value": [_TASK_GROUP_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_task_groups(api_call))
        assert len(results) == 1
        assert results[0].description == "A reusable task sequence"


class TestGetTaskGroup:
    @staticmethod
    def test_returns_task_group_info(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_TASK_GROUP_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_task_group(api_call, UUID(_TASK_GROUP_ID))
        assert isinstance(result, TaskGroupInfo)
        assert result.id == UUID(_TASK_GROUP_ID)
        assert result.name == "My Task Group"

    @staticmethod
    def test_task_group_id_appears_in_url(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_TASK_GROUP_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_task_group(api_call, UUID(_TASK_GROUP_ID))
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _TASK_GROUP_ID in called_url


class TestPostTaskGroup:
    @staticmethod
    def _make_request() -> TaskGroupCreateRequest:
        return TaskGroupCreateRequest(
            name="My Task Group",
            tasks=[
                {
                    "task": {
                        "id": "11111111-2222-3333-4444-555555555555",
                        "versionSpec": "1.*",
                    },
                    "displayName": "Run script",
                    "inputs": {"script": "echo hello"},
                }
            ],
            description="A reusable task sequence",
            category="Build",
        )

    @staticmethod
    def test_returns_task_group_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_TASK_GROUP_PAYLOAD)
        request = TestPostTaskGroup._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_task_group(api_call, request)
        assert isinstance(result, TaskGroupInfo)
        assert result.id == UUID(_TASK_GROUP_ID)

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_TASK_GROUP_PAYLOAD)
        request = TestPostTaskGroup._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_task_group(api_call, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "My Task Group"
        assert "tasks" in sent_json


class TestPutTaskGroup:
    @staticmethod
    def _make_request() -> TaskGroupUpdateRequest:
        return TaskGroupUpdateRequest(
            id=UUID(_TASK_GROUP_ID),
            name="Updated Task Group",
            tasks=[],
            description="Updated description",
        )

    @staticmethod
    def test_returns_updated_info(api_call: ApiCall) -> None:
        updated = {**_TASK_GROUP_PAYLOAD, "name": "Updated Task Group"}
        mock_resp = _make_mock_response(updated)
        request = TestPutTaskGroup._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_task_group(api_call, UUID(_TASK_GROUP_ID), request)
        assert isinstance(result, TaskGroupInfo)

    @staticmethod
    def test_task_group_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_TASK_GROUP_PAYLOAD)
        request = TestPutTaskGroup._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_task_group(api_call, UUID(_TASK_GROUP_ID), request)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _TASK_GROUP_ID in called_url

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_TASK_GROUP_PAYLOAD)
        request = TestPutTaskGroup._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_task_group(api_call, UUID(_TASK_GROUP_ID), request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["id"] == _TASK_GROUP_ID
        assert sent_json["name"] == "Updated Task Group"


class TestDeleteTaskGroup:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        task_group_id: TaskGroupId = UUID(_TASK_GROUP_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_task_group(api_call, task_group_id)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_task_group_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        task_group_id: TaskGroupId = UUID(_TASK_GROUP_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_task_group(api_call, task_group_id)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _TASK_GROUP_ID in called_url
