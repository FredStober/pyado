"""Tests for pyado.raw.hook — service hooks wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado.raw import (
    ApiCall,
    HookPublisherInfo,
    HookSubscriptionCreateRequest,
    HookSubscriptionId,
    HookSubscriptionInfo,
    HookSubscriptionUpdateRequest,
    delete_hook_subscription,
    get_hook_subscription,
    iter_hook_publishers,
    iter_hook_subscriptions,
    list_hook_publishers,
    list_hook_subscriptions,
    post_hook_subscription,
    put_hook_subscription,
)
from tests.conftest import _make_mock_response

_SUBSCRIPTION_ID = "11111111-2222-3333-4444-555555555555"

_SUBSCRIPTION_PAYLOAD = {
    "id": _SUBSCRIPTION_ID,
    "status": "enabled",
    "publisherId": "tfs",
    "eventType": "build.complete",
    "consumerId": "webHooks",
    "consumerActionId": "httpRequest",
    "resourceVersion": "1.0",
    "actionDescription": "To target",
    "publisherInputs": {"projectId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
    "consumerInputs": {"url": "https://example.com/hook"},
}


class TestListHookSubscriptions:
    @staticmethod
    def test_returns_list_of_subscriptions(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [_SUBSCRIPTION_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_hook_subscriptions(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], HookSubscriptionInfo)
        assert results[0].id == UUID(_SUBSCRIPTION_ID)
        assert results[0].publisher_id == "tfs"
        assert results[0].event_type == "build.complete"
        assert results[0].consumer_id == "webHooks"
        assert results[0].status == "enabled"

    @staticmethod
    def test_returns_empty_list_when_no_subscriptions(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_hook_subscriptions(api_call)
        assert results == []


class TestIterHookSubscriptions:
    @staticmethod
    def test_yields_subscriptions(api_call: ApiCall) -> None:
        payload = {"value": [_SUBSCRIPTION_PAYLOAD]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_hook_subscriptions(api_call))
        assert len(results) == 1
        assert results[0].consumer_action_id == "httpRequest"


class TestGetHookSubscription:
    @staticmethod
    def test_returns_subscription_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID))
        assert isinstance(result, HookSubscriptionInfo)
        assert result.id == UUID(_SUBSCRIPTION_ID)
        assert result.event_type == "build.complete"

    @staticmethod
    def test_subscription_id_appears_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID))
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _SUBSCRIPTION_ID in called_url


class TestPostHookSubscription:
    @staticmethod
    def _make_request() -> HookSubscriptionCreateRequest:
        return HookSubscriptionCreateRequest(
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
            publisher_inputs={"projectId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
            consumer_inputs={"url": "https://example.com/hook"},
        )

    @staticmethod
    def test_returns_subscription_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        request = TestPostHookSubscription._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_hook_subscription(api_call, request)
        assert isinstance(result, HookSubscriptionInfo)
        assert result.id == UUID(_SUBSCRIPTION_ID)

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        request = TestPostHookSubscription._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_hook_subscription(api_call, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["publisherId"] == "tfs"
        assert sent_json["eventType"] == "build.complete"
        assert sent_json["consumerId"] == "webHooks"


class TestPutHookSubscription:
    @staticmethod
    def _make_request() -> HookSubscriptionUpdateRequest:
        return HookSubscriptionUpdateRequest(
            id=UUID(_SUBSCRIPTION_ID),
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
            consumer_inputs={"url": "https://example.com/hook2"},
        )

    @staticmethod
    def test_returns_updated_info(api_call: ApiCall) -> None:
        updated = {
            **_SUBSCRIPTION_PAYLOAD,
            "consumerInputs": {"url": "https://example.com/hook2"},
        }
        mock_resp = _make_mock_response(updated)
        request = TestPutHookSubscription._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID), request)
        assert isinstance(result, HookSubscriptionInfo)

    @staticmethod
    def test_subscription_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        request = TestPutHookSubscription._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID), request)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _SUBSCRIPTION_ID in called_url

    @staticmethod
    def test_sends_put_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        request = TestPutHookSubscription._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID), request)
        assert mock_req.call_args.args[0] == "PUT"

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_SUBSCRIPTION_PAYLOAD)
        request = TestPutHookSubscription._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_hook_subscription(api_call, UUID(_SUBSCRIPTION_ID), request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["id"] == _SUBSCRIPTION_ID


class TestDeleteHookSubscription:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        subscription_id: HookSubscriptionId = UUID(_SUBSCRIPTION_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_hook_subscription(api_call, subscription_id)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_subscription_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        subscription_id: HookSubscriptionId = UUID(_SUBSCRIPTION_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_hook_subscription(api_call, subscription_id)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _SUBSCRIPTION_ID in called_url


class TestListHookPublishers:
    @staticmethod
    def test_returns_list_of_publishers(api_call: ApiCall) -> None:
        payload = {
            "count": 2,
            "value": [
                {"id": "tfs", "name": "Azure DevOps", "description": "ADO events"},
                {
                    "id": "rm",
                    "name": "Azure Pipelines",
                    "description": "Pipeline events",
                },
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_hook_publishers(api_call)
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], HookPublisherInfo)
        assert results[0].id == "tfs"
        assert results[0].name == "Azure DevOps"

    @staticmethod
    def test_returns_empty_list_when_no_publishers(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_hook_publishers(api_call)
        assert results == []


class TestIterHookPublishers:
    @staticmethod
    def test_yields_publishers(api_call: ApiCall) -> None:
        payload = {"value": [{"id": "tfs", "name": "Azure DevOps"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_hook_publishers(api_call))
        assert len(results) == 1
        assert results[0].id == "tfs"
