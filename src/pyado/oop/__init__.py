"""OOP wrappers for Azure DevOps resources.

All classes are re-exported from the top-level ``pyado`` package::

    import pyado
    svc = pyado.AzureDevOpsService(org="https://dev.azure.com/myorg", pat="...")

or import directly from this subpackage::

    from pyado.oop import AzureDevOpsService

Design
------
Each class wraps one ADO resource and delegates all HTTP calls to the
underlying :mod:`pyado.raw` and :mod:`pyado.high` layers.  The classes form
a scope hierarchy:

* :class:`AzureDevOpsService` → :class:`Organization`
* :class:`Organization` → :class:`Project`
* :class:`Project` → :class:`Repository`, :class:`WorkItem`,
  :class:`Build`, :class:`Pipeline`, :class:`VariableGroup`,
  :class:`Iteration`, :class:`Area`
* :class:`Repository` → :class:`PullRequest`

Navigation back up the hierarchy is always zero-cost (no API calls):
``build.project``, ``pr.repo``, ``wi.org``, etc.

Resource objects obtained from different factory paths share identity when
they represent the same ADO resource:
``build.project is wi.project`` is guaranteed.

Quick start::

    from pyado.oop import AzureDevOpsService

    svc  = AzureDevOpsService(org="https://dev.azure.com/myorg", pat="...")
    org  = svc.org
    proj = org.get_project("ICS")
    print(proj.name)                         # "ICS"

    repo = proj.get_repository("myrepo")
    print(repo.default_branch)               # "refs/heads/main"

    pr = repo.get_pr(32)
    print(pr.title, pr.status)              # "My PR"  "active"

    wi = proj.get_work_item(153)
    print(wi.title)                          # "Fix the bug"
    wi.update({"System.Title": "Fixed"})

    pr.link_work_item(wi)

    build = proj.get_build(456)
    assert build.project is wi.project       # shared identity
    print(build.pipeline.name)               # zero-cost back-navigation
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "ActiveBuildTask",
    "AddFile",
    "Area",
    "AzureDevOpsService",
    "Build",
    "BuildJob",
    "BuildPhase",
    "BuildStage",
    "BuildTask",
    "Commit",
    "DeleteFile",
    "EditFile",
    "Iteration",
    "Organization",
    "Pipeline",
    "Project",
    "PullRequest",
    "RenameFile",
    "Repository",
    "Team",
    "VariableGroup",
    "WorkItem",
]

from pyado.oop.active_build_task import ActiveBuildTask as ActiveBuildTask
from pyado.oop.area import Area as Area
from pyado.oop.build import Build as Build
from pyado.oop.build_timeline import BuildJob as BuildJob
from pyado.oop.build_timeline import BuildPhase as BuildPhase
from pyado.oop.build_timeline import BuildStage as BuildStage
from pyado.oop.build_timeline import BuildTask as BuildTask
from pyado.oop.commit import Commit as Commit
from pyado.oop.file_change import AddFile as AddFile
from pyado.oop.file_change import DeleteFile as DeleteFile
from pyado.oop.file_change import EditFile as EditFile
from pyado.oop.file_change import RenameFile as RenameFile
from pyado.oop.iteration import Iteration as Iteration
from pyado.oop.organization import Organization as Organization
from pyado.oop.pipeline import Pipeline as Pipeline
from pyado.oop.project import Project as Project
from pyado.oop.pull_request import PullRequest as PullRequest
from pyado.oop.repository import Repository as Repository
from pyado.oop.service import AzureDevOpsService as AzureDevOpsService
from pyado.oop.team import Team as Team
from pyado.oop.variable_group import VariableGroup as VariableGroup
from pyado.oop.work_item import WorkItem as WorkItem
