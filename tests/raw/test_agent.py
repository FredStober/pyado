"""Tests for pyado.raw.agent — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado.raw import (
    AgentInfo,
    AgentPoolInfo,
    AgentPoolRef,
    AgentQueueInfo,
    ApiCall,
    get_agent_pool,
    get_agent_pool_api_call,
    get_agent_queue,
    iter_agents,
    list_agent_pools,
    list_agent_queues,
    list_agents,
)
from tests.conftest import _make_mock_response


class TestListAgentPools:
    @staticmethod
    def test_returns_list_of_pool_infos(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [{"id": 1, "name": "Pool1"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_agent_pools(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], AgentPoolInfo)


class TestListAgentQueues:
    @staticmethod
    def test_returns_list_of_queue_infos(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": 10,
                    "name": "Queue1",
                    "pool": {"id": 2, "name": "Pool1", "isHosted": False},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_agent_queues(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], AgentQueueInfo)
        assert isinstance(results[0].pool, AgentPoolRef)
        assert results[0].pool.name == "Pool1"
        assert results[0].pool.is_hosted is False

    @staticmethod
    def test_returns_queue_with_no_pool(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [{"id": 10, "name": "Queue1"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_agent_queues(api_call)
        assert results[0].pool is None


class TestListAgents:
    @staticmethod
    def test_returns_list_of_agent_infos(api_call: ApiCall) -> None:
        payload = {"count": 1, "value": [{"id": 5, "name": "MyAgent"}]}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_agents(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], AgentInfo)


class TestIterAgents:
    @staticmethod
    def test_yields_agent_infos(api_call: ApiCall) -> None:
        payload = {
            "count": 2,
            "value": [
                {"id": 1, "name": "Agent1"},
                {"id": 2, "name": "Agent2"},
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_agents(api_call))
        assert len(results) == 2
        assert all(isinstance(item, AgentInfo) for item in results)
        assert results[0].name == "Agent1"

    @staticmethod
    def test_returns_empty_when_no_agents(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_agents(api_call))
        assert results == []


class TestGetAgentPoolApiCall:
    @staticmethod
    def test_returns_api_call(api_call: ApiCall) -> None:
        result = get_agent_pool_api_call(api_call, 5)
        assert isinstance(result, ApiCall)


class TestGetAgentPool:
    @staticmethod
    def test_returns_pool_info(api_call: ApiCall) -> None:
        payload = {"id": 5, "name": "MyPool", "isHosted": True}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_agent_pool(api_call, 5)
        assert isinstance(result, AgentPoolInfo)
        assert result.id == 5
        assert result.name == "MyPool"


class TestGetAgentQueue:
    @staticmethod
    def test_returns_queue_info(api_call: ApiCall) -> None:
        payload = {"id": 10, "name": "MyQueue"}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_agent_queue(api_call, 10)
        assert isinstance(result, AgentQueueInfo)
        assert result.id == 10
        assert result.name == "MyQueue"
