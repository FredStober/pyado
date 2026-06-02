"""OOP wrappers for Azure DevOps resources.

.. warning::
    This subpackage is in **preview**.  Import directly from
    ``pyado.oop`` rather than from ``pyado``:

    .. code-block:: python

        from pyado.oop import Client

Design
------
Each class wraps one ADO resource and delegates all HTTP calls to the
underlying :mod:`pyado.raw` and :mod:`pyado.high` layers.  The classes form
a factory hierarchy:

* :class:`Client` → :class:`Project`
* :class:`Project` → :class:`Repository`, :class:`WorkItem`,
  :class:`Build`, :class:`Pipeline`
* :class:`Repository` → :class:`PullRequest`

Quick start::

    from pyado.oop import Client

    client = Client(org_url="https://dev.azure.com/myorg", token="...")
    proj   = client.get_project("ICS")
    wi     = proj.get_work_item(153)
    proj.get_repository("myrepo").get_pr(32).link_work_item(wi)
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "Build",
    "Client",
    "Pipeline",
    "Project",
    "PullRequest",
    "Repository",
    "WorkItem",
]

from pyado.oop.build import Build as Build
from pyado.oop.client import Client as Client
from pyado.oop.pipeline import Pipeline as Pipeline
from pyado.oop.project import Project as Project
from pyado.oop.pull_request import PullRequest as PullRequest
from pyado.oop.repository import Repository as Repository
from pyado.oop.work_item import WorkItem as WorkItem
