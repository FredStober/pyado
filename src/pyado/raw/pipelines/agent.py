"""Azure DevOps agent pool and queue API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TypeAlias

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "AgentId",
    "AgentInfo",
    "AgentPoolId",
    "AgentPoolInfo",
    "AgentPoolRef",
    "AgentQueueId",
    "AgentQueueInfo",
    "get_agent_pool",
    "get_agent_pool_api_call",
    "get_agent_queue",
    "iter_agent_pools",
    "iter_agent_queues",
    "iter_agents",
    "list_agent_pools",
    "list_agent_queues",
    "list_agents",
]

AgentPoolId: TypeAlias = int
AgentId: TypeAlias = int
AgentQueueId: TypeAlias = int

_AGENT_POOL_API_VERSION = "7.1"
_AGENT_QUEUE_API_VERSION = "7.1"


class AgentPoolInfo(AdoBaseModel):
    """Minimal representation of an ADO agent pool."""

    id: AgentPoolId
    name: str
    is_hosted: bool = False
    pool_type: str | None = None
    size: int = 0


class AgentInfo(AdoBaseModel):
    """Minimal representation of an agent within a pool."""

    id: AgentId
    name: str
    status: str | None = None
    os_description: str | None = None
    version: str | None = None
    created_on: datetime | None = None


class AgentPoolRef(AdoBaseModel):
    """Pool reference embedded in an agent queue response."""

    id: AgentPoolId
    name: str
    is_hosted: bool = False


class AgentQueueInfo(AdoBaseModel):
    """Minimal representation of a project-scoped agent queue."""

    id: AgentQueueId
    name: str
    pool: AgentPoolRef | None = None


def get_agent_pool_api_call(
    org_api_call: ApiCall,
    pool_id: AgentPoolId,
) -> ApiCall:
    """Build an agent-pool-scoped API call.

    Args:
        org_api_call: Organisation-level ADO API call.
        pool_id: Numeric agent pool ID.

    Returns:
        An ApiCall pointing at the agent pool resource.
    """
    return org_api_call.build_call(
        "distributedtask",
        "pools",
        pool_id,
        version=_AGENT_POOL_API_VERSION,
    )


def iter_agent_pools(
    org_api_call: ApiCall,
) -> Iterator[AgentPoolInfo]:
    """Iterate over all agent pools in the organisation.

    Args:
        org_api_call: Organisation-level ADO API call.

    Yields:
        AgentPoolInfo for each agent pool.
    """
    result = org_api_call.get(
        "distributedtask",
        "pools",
        version=_AGENT_POOL_API_VERSION,
    )
    for item in result.get("value", []):
        yield AgentPoolInfo.model_validate(item)


def get_agent_pool(
    org_api_call: ApiCall,
    pool_id: AgentPoolId,
) -> AgentPoolInfo:
    """Return a single agent pool by ID.

    Args:
        org_api_call: Organisation-level ADO API call.
        pool_id: Numeric agent pool ID.

    Returns:
        AgentPoolInfo for the requested pool.
    """
    result = org_api_call.get(
        "distributedtask",
        "pools",
        pool_id,
        version=_AGENT_POOL_API_VERSION,
    )
    return AgentPoolInfo.model_validate(result)


def iter_agents(
    pool_api_call: ApiCall,
) -> Iterator[AgentInfo]:
    """Iterate over all agents in a pool.

    Args:
        pool_api_call: Agent-pool-level ADO API call (from
            get_agent_pool_api_call).

    Yields:
        AgentInfo for each agent in the pool.
    """
    result = pool_api_call.get(
        "agents",
        version=_AGENT_POOL_API_VERSION,
    )
    for item in result.get("value", []):
        yield AgentInfo.model_validate(item)


def iter_agent_queues(
    project_api_call: ApiCall,
) -> Iterator[AgentQueueInfo]:
    """Iterate over all agent queues in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        AgentQueueInfo for each agent queue.
    """
    result = project_api_call.get(
        "distributedtask",
        "queues",
        version=_AGENT_QUEUE_API_VERSION,
    )
    for item in result.get("value", []):
        yield AgentQueueInfo.model_validate(item)


def list_agent_pools(
    org_api_call: ApiCall,
) -> list[AgentPoolInfo]:
    """Return all agent pools in the organisation as a list."""
    return list(iter_agent_pools(org_api_call))


def list_agent_queues(
    project_api_call: ApiCall,
) -> list[AgentQueueInfo]:
    """Return all agent queues in the project as a list."""
    return list(iter_agent_queues(project_api_call))


def list_agents(
    pool_api_call: ApiCall,
) -> list[AgentInfo]:
    """Return all agents in a pool as a list."""
    return list(iter_agents(pool_api_call))


def get_agent_queue(
    project_api_call: ApiCall,
    queue_id: AgentQueueId,
) -> AgentQueueInfo:
    """Return a single agent queue by ID.

    Args:
        project_api_call: Project-level ADO API call.
        queue_id: Numeric agent queue ID.

    Returns:
        AgentQueueInfo for the requested queue.
    """
    result = project_api_call.get(
        "distributedtask",
        "queues",
        queue_id,
        version=_AGENT_QUEUE_API_VERSION,
    )
    return AgentQueueInfo.model_validate(result)
