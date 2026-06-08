"""OOP wrappers for Azure DevOps agent pool and queue resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    AgentId,
    AgentInfo,
    AgentPoolId,
    AgentPoolInfo,
    AgentQueueId,
    AgentQueueInfo,
    ApiCall,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Agent", "AgentPool", "AgentQueue"]


class Agent:
    """An agent within an agent pool.

    **ADO concept:** an *agent* is a compute instance registered to an agent
    pool.  It runs pipeline jobs dispatched by the pool scheduler.  Agents
    are exposed at ``distributedtask/pools/{poolId}/agents/{agentId}``.

    **Why it exists:** wraps :class:`~pyado.raw.AgentInfo` and holds a
    back-reference to the owning :class:`AgentPool` for upward navigation.

    Instances are obtained from :meth:`AgentPool.iter_agents`.

    Attributes:
        _pool: The AgentPool this agent belongs to.
        _info: Agent data returned from the API.
    """

    def __init__(self, pool: "AgentPool", info: AgentInfo) -> None:
        """Construct an Agent wrapper.

        Args:
            pool: The AgentPool this agent belongs to.
            info: Agent data as returned from the API.
        """
        self._pool = pool
        self._info = info

    @property
    def info(self) -> AgentInfo:
        """Raw agent data."""
        return self._info

    @property
    def id(self) -> AgentId:
        """Numeric agent ID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Agent name."""
        return self._info.name

    @property
    def status(self) -> str | None:
        """Current agent status string (e.g. ``"online"``, ``"offline"``)."""
        return self._info.status

    @property
    def pool(self) -> "AgentPool":
        """AgentPool this agent belongs to — zero-cost."""
        return self._pool


class AgentPool:
    """An Azure DevOps agent pool.

    **ADO concept:** an *agent pool* is an org-level collection of agents
    (``distributedtask/pools/{poolId}``).  Both Microsoft-hosted
    (``isHosted=True``) and self-hosted pools are represented by this class.

    **Why it exists:** bundles pool info and the pool-level API call so that
    :meth:`iter_agents` works without the caller constructing URLs manually.

    Instances are obtained from :meth:`Organization.iter_agent_pools` or
    :meth:`Organization.get_agent_pool`.

    Attributes:
        _org: The Organisation this pool belongs to.
        _pool_api_call: Pool-level ADO API call.
        _info: Cached pool data.
    """

    def __init__(
        self,
        org: "Organization",
        pool_api_call: ApiCall,
        info: AgentPoolInfo,
    ) -> None:
        """Construct an AgentPool wrapper.

        Args:
            org: The Organisation that owns this pool.
            pool_api_call: Pool-level ADO API call (from
                raw.get_agent_pool_api_call).
            info: Pool data as returned from the API.
        """
        self._org = org
        self._pool_api_call = pool_api_call
        self._pool_id = info.id
        self._info: AgentPoolInfo | None = info

    @property
    def info(self) -> AgentPoolInfo:
        """Pool data captured at construction time."""
        if self._info is None:
            self._info = raw.get_agent_pool(self._org.api_call, self._pool_id)
        return self._info

    @property
    def id(self) -> AgentPoolId:
        """Numeric pool ID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Pool name (e.g. ``"Default"``, ``"Azure Pipelines"``)."""
        return self.info.name

    @property
    def is_hosted(self) -> bool:
        """``True`` for Microsoft-hosted pools, ``False`` for self-hosted."""
        return self.info.is_hosted

    @property
    def org(self) -> "Organization":
        """Organisation this pool belongs to — zero-cost."""
        return self._org

    def refresh(self) -> None:
        """Discard cached pool info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    def iter_agents(self) -> Iterator[Agent]:
        """Iterate over all agents registered in this pool.

        Yields:
            Agent for each agent in the pool.
        """
        for info in raw.iter_agents(self._pool_api_call):
            yield Agent(self, info)

    def list_agents(self) -> list[Agent]:
        """Return all agents in this pool as a list."""
        return list(self.iter_agents())


class AgentQueue:
    """A project-scoped agent queue.

    **ADO concept:** an *agent queue* is the project-facing view of an agent
    pool (``distributedtask/queues/{queueId}``).  Pipelines reference queues
    (not pools directly) via the ``pool`` key in YAML or the classic pipeline
    GUI.  Each queue is associated with exactly one pool.

    **Why it exists:** wraps :class:`~pyado.raw.AgentQueueInfo` and holds a
    back-reference to the owning :class:`~pyado.oop.project.Project`.

    Instances are obtained from
    :meth:`ProjectPipelines.iter_agent_queues` or
    :meth:`ProjectPipelines.get_agent_queue`.

    Attributes:
        _project: The Project this queue belongs to.
        _info: Queue data returned from the API.
    """

    def __init__(self, project: "Project", info: AgentQueueInfo) -> None:
        """Construct an AgentQueue wrapper.

        Args:
            project: The Project this queue belongs to.
            info: Queue data as returned from the API.
        """
        self._project = project
        self._info = info

    @property
    def info(self) -> AgentQueueInfo:
        """Raw queue data."""
        return self._info

    @property
    def id(self) -> AgentQueueId:
        """Numeric queue ID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Queue name (e.g. ``"Default"``)."""
        return self._info.name

    @property
    def pool_id(self) -> int | None:
        """ID of the agent pool backing this queue, or None if not available."""
        return self._info.pool.id if self._info.pool is not None else None

    @property
    def project(self) -> "Project":
        """Project this queue belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this queue belongs to — zero-cost."""
        return self._project.org
