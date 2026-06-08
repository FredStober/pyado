"""OOP wrapper for Azure DevOps git commit resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING

from pyado import raw
from pyado.oop.repos import _git
from pyado.raw import (
    CommitId,
    GitCommitChange,
    GitCommitRef,
    GitCommitSearchCriteria,
    GitStatus,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.repos.pull_request import PullRequest
    from pyado.oop.repos.repository import Repository

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
        self._sha = info.commit_id
        self._info: GitCommitRef | None = info
        self._search_criteria: GitCommitSearchCriteria | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> GitCommitRef:
        """Commit data captured at construction time."""
        if self._info is None:
            self._info = raw.get_commit_by_id(
                self._repo.api_call,
                self._sha,
                search_criteria=self._search_criteria,
            )
        return self._info

    @property
    def sha(self) -> CommitId:
        """Commit SHA (40-character hex string)."""
        return self._sha

    @property
    def message(self) -> str | None:
        """Commit message; may be truncated for long messages.

        Check :attr:`~pyado.raw.GitCommitRef.comment_truncated` on
        :attr:`info` to detect truncation.
        """
        return self.info.comment

    @property
    def author_name(self) -> str | None:
        """Name of the commit author, or ``None`` if not present in the API response."""
        return self.info.author.name if self.info.author else None

    @property
    def author_email(self) -> str | None:
        """Email of the commit author, or ``None`` if not in the API response."""
        return self.info.author.email if self.info.author else None

    @property
    def author_date(self) -> datetime | None:
        """UTC datetime the commit was authored, or ``None``."""
        return self.info.author.date if self.info.author else None

    @property
    def committer_name(self) -> str | None:
        """Name of the committer, or ``None`` if not present in the API response."""
        return self.info.committer.name if self.info.committer else None

    @property
    def committer_email(self) -> str | None:
        """Email of the committer, or ``None`` if not present in the API response."""
        return self.info.committer.email if self.info.committer else None

    @property
    def committer_date(self) -> datetime | None:
        """UTC datetime the commit was applied, or ``None``."""
        return self.info.committer.date if self.info.committer else None

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

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, search_criteria: GitCommitSearchCriteria | None = None) -> None:
        """Discard cached commit info.

        The next access to :attr:`info` re-fetches from the API.

        Args:
            search_criteria: Optional search criteria to use on the next
                fetch.  When provided, replaces any previously stored
                criteria; when ``None``, previously stored criteria are
                preserved.
        """
        if search_criteria is not None:
            self._search_criteria = search_criteria
        self._info = None

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def get_file(self, path: str) -> str:
        """Return the content of a file at this commit.

        Args:
            path: Absolute file path within the repository (e.g.
                ``"/src/foo.py"``).

        Returns:
            File content as a UTF-8 string, or ``""`` if the file is absent.
        """
        return _git.get_file_content_at_commit(self._repo.api_call, path, self.sha)

    def iter_changes(self) -> Iterator[GitCommitChange]:
        """Iterate over files changed by this commit.

        Uses the first parent commit as the diff base.  Yields nothing for
        root commits (no parents).

        Yields:
            GitCommitChange for each changed file.
        """
        if not self.info.parents:
            return
        yield from _git.iter_commit_diff(
            self._repo.api_call, self.info.parents[0], self.sha
        )

    def get_pull_request(self) -> "PullRequest | None":
        """Return the first active PR whose source branch contains this commit.

        Delegates to :meth:`Repository.get_pr_for_commit`.

        Returns:
            PullRequest for the first active PR containing this commit, or
            ``None`` if no such PR exists.
        """
        return self._repo.get_pr_for_commit(self.sha)

    def get_statuses(self) -> list[GitStatus]:
        """Return the CI statuses attached to this commit.

        Statuses are populated when the commit was fetched via an endpoint
        that includes status data.  Call :meth:`Repository.get_commit` (which
        uses ``get_commit_by_id``) to ensure statuses are included.

        Returns:
            List of GitStatus objects; empty when none are present.
        """
        return self.info.statuses

    def list_changes(self) -> list[GitCommitChange]:
        """Return all file changes in this commit as a list."""
        return list(self.iter_changes())
