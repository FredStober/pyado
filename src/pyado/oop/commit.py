"""OOP wrapper for Azure DevOps git commit resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import datetime
from typing import TYPE_CHECKING

from pyado.raw import CommitId, GitCommitRef

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.repository import Repository

__all__ = ["Commit"]


class Commit:
    """An Azure DevOps git commit.

    Wraps a :class:`~pyado.raw.GitCommitRef` and exposes its data as
    properties.  Instances are obtained from :meth:`Repository.get_commit`
    or :meth:`Repository.iter_commits`.

    Attributes:
        _repo: The Repository this commit belongs to.
        _info: The commit data returned from the API.
    """

    def __init__(self, repo: "Repository", info: GitCommitRef) -> None:
        """Construct a Commit wrapper.

        Args:
            repo: The Repository that contains this commit.
            info: Commit data as returned from the API.
        """
        self._repo = repo
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> GitCommitRef:
        """Commit data captured at construction time."""
        return self._info

    @property
    def sha(self) -> CommitId:
        """Commit SHA (40-character hex string)."""
        return self._info.commit_id

    @property
    def message(self) -> str | None:
        """Commit message; may be truncated for long messages.

        Check :attr:`~pyado.raw.GitCommitRef.comment_truncated` on
        :attr:`info` to detect truncation.
        """
        return self._info.comment

    @property
    def author_name(self) -> str | None:
        """Name of the commit author, or ``None`` if not present in the API response."""
        return self._info.author.name if self._info.author else None

    @property
    def author_email(self) -> str | None:
        """Email of the commit author, or ``None`` if not in the API response."""
        return self._info.author.email if self._info.author else None

    @property
    def author_date(self) -> datetime | None:
        """UTC datetime the commit was authored, or ``None``."""
        return self._info.author.date if self._info.author else None

    @property
    def committer_name(self) -> str | None:
        """Name of the committer, or ``None`` if not present in the API response."""
        return self._info.committer.name if self._info.committer else None

    @property
    def committer_email(self) -> str | None:
        """Email of the committer, or ``None`` if not present in the API response."""
        return self._info.committer.email if self._info.committer else None

    @property
    def committer_date(self) -> datetime | None:
        """UTC datetime the commit was applied, or ``None``."""
        return self._info.committer.date if self._info.committer else None

    @property
    def repo(self) -> "Repository":
        """Repository this commit belongs to — zero-cost."""
        return self._repo

    @property
    def project(self) -> "Project":
        """Project this commit belongs to — zero-cost."""
        return self._repo.project

    @property
    def org(self) -> "Organization":
        """Organisation this commit belongs to — zero-cost."""
        return self._repo.org
