"""Integration tests for agent pool and queue read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_agent_pools_read(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
) -> None:
    """List agent pools, agents, and queues."""
    console.print("\n=== AGENT POOLS & QUEUES (read) ===")

    pools = list(raw.iter_agent_pools(org_api_call))
    raw.list_agent_pools(org_api_call)

    if pools:
        pool = pools[0]
        pool_api_call = raw.get_agent_pool_api_call(org_api_call, pool.id)
        raw.get_agent_pool(org_api_call, pool.id)
        if pool_api_call:
            list(raw.iter_agents(pool_api_call))
            raw.list_agents(pool_api_call)

    queues = list(raw.iter_agent_queues(project_api_call))
    raw.list_agent_queues(project_api_call)
    if queues:
        raw.get_agent_queue(project_api_call, queues[0].id)
