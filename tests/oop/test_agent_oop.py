"""Tests for pyado.oop Agent, AgentPool, AgentQueue — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

from pyado.oop.pipelines.agent import Agent, AgentPool, AgentQueue
from pyado.oop.pipelines.project_pipelines import ProjectPipelines
from pyado.raw import AgentInfo, AgentPoolInfo, AgentQueueInfo
from tests.oop.conftest import _api_call, _make_project, _make_service


def _agent_info(agent_id: int = 1, name: str = "Agent1") -> AgentInfo:
    return AgentInfo.model_validate({"id": agent_id, "name": name, "status": "online"})


def _pool_info(pool_id: int = 10, name: str = "Default") -> AgentPoolInfo:
    return AgentPoolInfo.model_validate(
        {"id": pool_id, "name": name, "isHosted": False}
    )


def _queue_info(
    queue_id: int = 5, name: str = "Default", pool_id: int = 10
) -> AgentQueueInfo:
    return AgentQueueInfo.model_validate(
        {"id": queue_id, "name": name, "pool": {"id": pool_id, "name": "Default"}}
    )


def _make_pool(pool_id: int = 10, name: str = "Default") -> AgentPool:
    svc = _make_service()
    return AgentPool(svc.org, _api_call(), _pool_info(pool_id, name))


class TestAgent:
    def test_constructor_stores_pool_and_info(self) -> None:
        pool = _make_pool()
        info = _agent_info()
        agent = Agent(pool, info)
        assert agent._pool is pool
        assert agent._info is info

    def test_info_returns_stored_info(self) -> None:
        pool = _make_pool()
        info = _agent_info()
        agent = Agent(pool, info)
        assert agent.info is info

    def test_id_returns_agent_id(self) -> None:
        agent = Agent(_make_pool(), _agent_info(agent_id=42))
        assert agent.id == 42

    def test_name_returns_agent_name(self) -> None:
        agent = Agent(_make_pool(), _agent_info(name="MyAgent"))
        assert agent.name == "MyAgent"

    def test_status_returns_status_string(self) -> None:
        agent = Agent(_make_pool(), _agent_info())
        assert agent.status == "online"

    def test_pool_returns_back_reference(self) -> None:
        pool = _make_pool()
        agent = Agent(pool, _agent_info())
        assert agent.pool is pool


class TestAgentPool:
    def test_info_returns_stored_info(self) -> None:
        pool = _make_pool()
        assert pool.info.name == "Default"

    def test_id_returns_pool_id(self) -> None:
        pool = _make_pool(pool_id=7)
        assert pool.id == 7

    def test_name_returns_pool_name(self) -> None:
        pool = _make_pool(name="Azure Pipelines")
        assert pool.name == "Azure Pipelines"

    def test_is_hosted_false_for_self_hosted(self) -> None:
        pool = _make_pool()
        assert pool.is_hosted is False

    def test_org_returns_back_reference(self) -> None:
        svc = _make_service()
        pool = AgentPool(svc.org, _api_call(), _pool_info())
        assert pool.org is svc.org

    def test_refresh_clears_info(self) -> None:
        pool = _make_pool()
        pool.refresh()
        assert pool._info is None

    def test_info_fetches_when_cache_is_none(self) -> None:
        pool = _make_pool(pool_id=5)
        pool._info = None
        refreshed = _pool_info(pool_id=5, name="Refreshed")
        with patch(
            "pyado.oop.pipelines.agent.raw.get_agent_pool", return_value=refreshed
        ):
            info = pool.info
        assert info.name == "Refreshed"

    def test_iter_agents_yields_agent_wrappers(self) -> None:
        pool = _make_pool()
        with patch("pyado.oop.pipelines.agent.raw.iter_agents") as mock_iter:
            mock_iter.return_value = iter([_agent_info(1, "A"), _agent_info(2, "B")])
            agents = list(pool.iter_agents())
        assert len(agents) == 2
        assert all(isinstance(item, Agent) for item in agents)
        assert agents[0].name == "A"

    def test_list_agents_delegates(self) -> None:
        pool = _make_pool()
        with patch.object(pool, "iter_agents", return_value=iter([])):
            assert pool.list_agents() == []


class TestAgentQueue:
    def test_info_returns_stored_info(self) -> None:
        proj = _make_project()
        info = _queue_info()
        queue = AgentQueue(proj, info)
        assert queue.info is info

    def test_id_returns_queue_id(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, _queue_info(queue_id=99))
        assert queue.id == 99

    def test_name_returns_queue_name(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, _queue_info(name="MyQueue"))
        assert queue.name == "MyQueue"

    def test_pool_id_returns_pool_id(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, _queue_info(pool_id=42))
        assert queue.pool_id == 42

    def test_pool_id_returns_none_when_no_pool(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, AgentQueueInfo.model_validate({"id": 1, "name": "Q"}))
        assert queue.pool_id is None

    def test_project_returns_back_reference(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, _queue_info())
        assert queue.project is proj

    def test_org_returns_project_org(self) -> None:
        proj = _make_project()
        queue = AgentQueue(proj, _queue_info())
        assert queue.org is proj.org


class TestProjectPipelinesGetAgentQueueById:
    def test_returns_agent_queue_wrapping_fetched_info(self) -> None:
        proj = _make_project()
        pipelines = ProjectPipelines(proj)
        info = _queue_info(queue_id=7, name="MyQueue")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_agent_queue",
            return_value=info,
        ) as mock_get:
            result = pipelines.get_agent_queue_by_id(7)
        mock_get.assert_called_once_with(proj.api_call, 7)
        assert isinstance(result, AgentQueue)
        assert result.id == 7
        assert result.name == "MyQueue"

    def test_returned_queue_has_correct_project_reference(self) -> None:
        proj = _make_project()
        pipelines = ProjectPipelines(proj)
        info = _queue_info(queue_id=3)
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_agent_queue",
            return_value=info,
        ):
            result = pipelines.get_agent_queue_by_id(3)
        assert result.project is proj
