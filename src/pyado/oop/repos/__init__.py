"""Repos section of the Azure DevOps OOP layer.

Exposes :class:`ProjectRepos` — the ``project.repos`` section object — plus
re-exports of all resource classes in this sub-package.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop.repos.branch import Branch
from pyado.oop.repos.commit import Commit
from pyado.oop.repos.file_change import AddFile, DeleteFile, EditFile, RenameFile
from pyado.oop.repos.policy import PolicyConfiguration
from pyado.oop.repos.project_repos import ProjectRepos
from pyado.oop.repos.pull_request import PullRequest
from pyado.oop.repos.repository import Repository
from pyado.oop.repos.tag import Tag

__all__ = [
    "AddFile",
    "Branch",
    "Commit",
    "DeleteFile",
    "EditFile",
    "PolicyConfiguration",
    "ProjectRepos",
    "PullRequest",
    "RenameFile",
    "Repository",
    "Tag",
]
