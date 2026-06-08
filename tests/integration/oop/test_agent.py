"""Integration tests for AgentPool and AgentQueue OOP classes."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib

from pyado.oop import Agent, AgentPool, AgentQueue, AgentQueueId, Organization, Project
from tests.integration.raw._support import _take, console


def test_agent_pools(org: Organization) -> None:
    """Exercise AgentPool and Agent OOP classes at organisation level."""
    console.print("\n=== Organization: Agent Pools ===")
    pools = _take(org.iter_agent_pools(), 3)
    org.list_agent_pools()

    if pools:
        pool: AgentPool = pools[0]
        _ = pool.id
        _ = pool.name
        _ = pool.is_hosted
        _ = pool.info
        _ = pool.org
        pool.refresh()
        _take(pool.iter_agents(), 5)
        pool.list_agents()
        agents = list(_take(pool.iter_agents(), 1))
        if agents:
            agent: Agent = agents[0]
            _ = agent.id
            _ = agent.name
            _ = agent.status
            _ = agent.pool
            _ = agent.info
        with contextlib.suppress(Exception):
            same_pool = org.get_agent_pool(pool.name)
            _ = same_pool


def test_agent_queues(proj: Project) -> None:
    """Exercise AgentQueue OOP class at project level."""
    console.print("\n=== Project: Agent Queues ===")
    queues = _take(proj.pipelines.iter_agent_queues(), 3)
    proj.pipelines.list_agent_queues()
    if queues:
        queue: AgentQueue = queues[0]
        _queue_id: AgentQueueId = queue.id
        _ = queue.name
        _ = queue.pool_id
        _ = queue.project
        _ = queue.org
        _ = queue.info
        with contextlib.suppress(Exception):
            proj.pipelines.get_agent_queue(queue.name)

    if queues:
        with contextlib.suppress(Exception):
            proj.pipelines.get_agent_queue_by_id(queues[0].id)
