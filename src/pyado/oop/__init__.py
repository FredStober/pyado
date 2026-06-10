"""OOP wrappers for Azure DevOps resources.

All classes are re-exported from the top-level ``pyado`` package::

    import pyado
    svc = pyado.AzureDevOpsService(org="myorg", pat="...")

or import directly from this subpackage::

    from pyado.oop import AzureDevOpsService

Design
------
Each class wraps one ADO resource and delegates all HTTP calls to the
underlying :mod:`pyado.raw` layer.  The classes form a scope hierarchy:

* :class:`AzureDevOpsService` → :class:`Organization`
* :class:`Organization` → :class:`Project`
* :class:`Project` exposes five section objects:
  - :attr:`~Project.repos` (:class:`ProjectRepos`) — repositories, pull
    requests, branches, and tags
  - :attr:`~Project.boards` (:class:`ProjectBoards`) — work items, iterations,
    areas, and teams
  - :attr:`~Project.pipelines` (:class:`ProjectPipelines`) — builds, pipeline
    runs, approvals, environments, agent queues, and the library sub-section
    (:class:`PipelineLibrary`) with variable groups and secure files
  - :attr:`~Project.search` (:class:`ProjectSearch`) — full-text search
  - :attr:`~Project.settings` (:class:`ProjectSettings`) — project settings

Navigation back up the hierarchy is always zero-cost (no API calls):
``build.project``, ``pr.repo``, ``wi.org``, etc.

Resource objects obtained from different factory paths share identity when
they represent the same ADO resource:
``build.project is wi.project`` is guaranteed.

Quick start::

    from pyado.oop import AzureDevOpsService

    svc  = AzureDevOpsService(org="myorg", pat="...")
    org  = svc.org
    proj = org.get_project("ICS")
    print(proj.name)                         # "ICS"

    repo = proj.repos.get_repository("myrepo")
    print(repo.default_branch)               # "refs/heads/main"

    pr = repo.get_pull_request(32)
    print(pr.title, pr.status)              # "My PR"  "active"

    wi = proj.boards.get_work_item(153)
    print(wi.title)                          # "Fix the bug"
    wi.update({"System.Title": "Fixed"})

    build = proj.pipelines.get_build(456)
    assert build.project is wi.project       # shared identity
    print(build.pipeline.name)               # zero-cost back-navigation
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "AddFile",
    "Agent",
    "AgentPool",
    "AgentQueue",
    "AgentQueueId",
    "Area",
    "AzureDevOpsService",
    "BasePolicyModel",
    "Branch",
    "Build",
    "BuildJob",
    "BuildPhase",
    "BuildPolicy",
    "BuildStage",
    "BuildTask",
    "CommentRequirementsPolicy",
    "Commit",
    "CommitAuthorEmailPolicy",
    "Dashboard",
    "DeleteFile",
    "DistributedTaskSession",
    "EditFile",
    "Environment",
    "FileNamePolicy",
    "FileSizeRestrictionPolicy",
    "GitRepositoryPolicy",
    "Iteration",
    "MergeStrategyPolicy",
    "MinimumReviewersPolicy",
    "Organization",
    "OrganizationSearch",
    "PathLengthPolicy",
    "Pipeline",
    "PipelineLibrary",
    "PipelineRun",
    "PolicyConfiguration",
    "Process",
    "Project",
    "ProjectBoards",
    "ProjectPipelines",
    "ProjectRepos",
    "ProjectSearch",
    "ProjectSettings",
    "PullRequest",
    "RenameFile",
    "RepoPolicyScope",
    "Repository",
    "RequiredReviewersPolicy",
    "ReservedNamesPolicy",
    "SearchBranchesPolicy",
    "SecureFile",
    "ServiceEndpoint",
    "StatusPolicy",
    "Tag",
    "TaskGroup",
    "Team",
    "VariableGroup",
    "Wiki",
    "WorkItem",
    "WorkItemLinkingPolicy",
    "WorkItemType",
]

from pyado.oop.boards import ProjectBoards
from pyado.oop.boards.area import Area
from pyado.oop.boards.iteration import Iteration
from pyado.oop.boards.team import Team
from pyado.oop.boards.work_item import WorkItem
from pyado.oop.boards.work_item_type import WorkItemType
from pyado.oop.core.process import Process
from pyado.oop.core.search import OrganizationSearch, ProjectSearch
from pyado.oop.organization import Organization
from pyado.oop.overview.dashboard import Dashboard
from pyado.oop.overview.wiki import Wiki
from pyado.oop.pipelines import PipelineLibrary, ProjectPipelines
from pyado.oop.pipelines.agent import Agent, AgentPool, AgentQueue
from pyado.oop.pipelines.build import Build
from pyado.oop.pipelines.build_timeline import (
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
)
from pyado.oop.pipelines.distributed_task_session import (
    DistributedTaskSession,
)
from pyado.oop.pipelines.environment import Environment
from pyado.oop.pipelines.pipeline import Pipeline, PipelineRun
from pyado.oop.pipelines.secure_file import SecureFile
from pyado.oop.pipelines.task_group import TaskGroup
from pyado.oop.pipelines.variable_group import VariableGroup
from pyado.oop.project import Project
from pyado.oop.repos import ProjectRepos
from pyado.oop.repos.branch import Branch
from pyado.oop.repos.commit import Commit
from pyado.oop.repos.file_change import AddFile, DeleteFile, EditFile, RenameFile
from pyado.oop.repos.policy import PolicyConfiguration
from pyado.oop.repos.policy_types import (
    BasePolicyModel,
    BuildPolicy,
    CommentRequirementsPolicy,
    CommitAuthorEmailPolicy,
    FileNamePolicy,
    FileSizeRestrictionPolicy,
    GitRepositoryPolicy,
    MergeStrategyPolicy,
    MinimumReviewersPolicy,
    PathLengthPolicy,
    RepoPolicyScope,
    RequiredReviewersPolicy,
    ReservedNamesPolicy,
    SearchBranchesPolicy,
    StatusPolicy,
    WorkItemLinkingPolicy,
)
from pyado.oop.repos.pull_request import PullRequest
from pyado.oop.repos.repository import Repository
from pyado.oop.repos.tag import Tag
from pyado.oop.service import AzureDevOpsService
from pyado.oop.settings import ProjectSettings
from pyado.oop.settings.service_endpoint import ServiceEndpoint
from pyado.raw import AgentQueueId
