"""OOP wrapper for an Azure DevOps git branch."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado.raw import CommitId, GitRef

if TYPE_CHECKING:
    from pyado.oop.repos.commit import Commit
    from pyado.oop.repos.repository import Repository

__all__ = ["Branch"]


class Branch:
    """A git branch in an Azure DevOps repository.

    Wraps a :class:`~pyado.raw.GitRef` for a ``refs/heads/…`` ref and
    exposes branch-specific convenience methods.  Instances are obtained
    from :meth:`ProjectRepos.iter_branches` or
    :meth:`Repository.iter_branches`.

    Attributes:
        _repo: The Repository this branch belongs to.
        _ref: The underlying GitRef data.
    """

    def __init__(self, repo: "Repository", ref: GitRef) -> None:
        """Construct a Branch wrapper.

        Args:
            repo: The Repository that contains this branch.
            ref: GitRef for the branch (name should start with
                ``"refs/heads/"``).
        """
        self._repo = repo
        self._ref = ref

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ref(self) -> GitRef:
        """Underlying GitRef data."""
        return self._ref

    @property
    def name(self) -> str:
        """Short branch name (``refs/heads/`` prefix stripped)."""
        return self._ref.name.removeprefix("refs/heads/")

    @property
    def full_name(self) -> str:
        """Full ref name (e.g. ``"refs/heads/main"``)."""
        return self._ref.name

    @property
    def commit_id(self) -> CommitId:
        """Current HEAD commit SHA of the branch."""
        return self._ref.object_id

    @property
    def repo(self) -> "Repository":
        """Repository this branch belongs to — zero-cost."""
        return self._repo

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def get_commit(self) -> "Commit":
        """Return the HEAD commit of this branch.

        Returns:
            :class:`~pyado.oop.repos.commit.Commit` at the tip of this branch.
        """
        return self._repo.get_commit(self.commit_id)

    def delete(self) -> None:
        """Delete this branch from the repository.

        Uses the stored commit SHA as the optimistic-concurrency guard.
        """
        self._repo.delete_branch(self.name, self.commit_id)
