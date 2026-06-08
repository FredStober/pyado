"""Boards section of the Azure DevOps OOP layer.

Exposes :class:`ProjectBoards` — the ``project.boards`` section object —
plus re-exports of all resource classes in this sub-package.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop.boards.area import Area
from pyado.oop.boards.iteration import Iteration
from pyado.oop.boards.project_boards import ProjectBoards
from pyado.oop.boards.team import Team
from pyado.oop.boards.work_item import WorkItem
from pyado.oop.boards.work_item_type import WorkItemType

__all__ = [
    "Area",
    "Iteration",
    "ProjectBoards",
    "Team",
    "WorkItem",
    "WorkItemType",
]
