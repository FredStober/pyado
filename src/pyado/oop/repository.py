"""OOP wrapper for Azure DevOps repository resources.

Provides the :class:`Repository` class, which wraps a single ADO Git
repository and exposes its operations as methods rather than free functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado import high, raw
from pyado.oop.pull_request import PullRequest
from pyado.raw import (
    ApiCall,
    BranchName,
    CommitId,
    GitCommitChange,
    GitPushCommit,
    GitPushRefUpdate,
    GitPushResult,
    GitRef,
    PullRequestCompletionOptions,
    PullRequestId,
    RepositoryInfo,
)

__all__ = ["Repository"]


class Repository:
    """An Azure DevOps Git repository resource.

    Wraps a single ADO repository and exposes its operations as instance
    methods.  Instances are normally obtained from
    :meth:`Project.get_repository` or :meth:`Project.iter_repositories`.

    Attributes:
        _project_api_call: Project-level API call (needed for PR listing and
            creation).
        _api_call: Repository-level API call used by all git operations.
        _info: The repository data returned from the API at construction time.
    """

    def __init__(
        self,
        project_api_call: ApiCall,
        repository_api_call: ApiCall,
        info: RepositoryInfo,
    ) -> None:
        """Construct a Repository wrapper.

        Args:
            project_api_call: Project-level ADO API call.
            repository_api_call: Repository-level ADO API call (from
                raw.get_repository_api_call).
            info: Repository data as returned from the API.
        """
        self._project_api_call = project_api_call
        self._api_call = repository_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> RepositoryInfo:
        """Return the repository data fetched at construction time.

        Returns:
            RepositoryInfo snapshot captured when this object was created.
        """
        return self._info

    # ------------------------------------------------------------------
    # Pull requests
    # ------------------------------------------------------------------

    def get_pr(self, pr_id: PullRequestId) -> PullRequest:
        """Return a wrapper for a specific pull request.

        Args:
            pr_id: Numeric ID of the pull request.

        Returns:
            PullRequest wrapping the requested PR.
        """
        pr_api_call = raw.get_pr_api_call(self._project_api_call, self._info.id, pr_id)
        info = raw.get_pr_details(pr_api_call)
        return PullRequest(
            pr_api_call,
            self._api_call,
            info,
            self._info.project.id,
            self._info.id,
        )

    def iter_prs(self) -> Iterator[PullRequest]:
        """Iterate over active pull requests in this repository.

        Yields:
            PullRequest for each active PR, in API-returned order.
        """
        for item in raw.iter_prs(
            self._project_api_call,
            {"repositoryId": str(self._info.id), "status": "active"},
        ):
            pr_api_call = raw.get_pr_api_call(
                self._project_api_call, self._info.id, item.pr_id
            )
            yield PullRequest(
                pr_api_call,
                self._api_call,
                item,
                self._info.project.id,
                self._info.id,
            )

    def create_pr(
        self,
        title: str,
        source_branch: str,
        target_branch: str,
        *,
        description: str | None = None,
        completion_options: PullRequestCompletionOptions | None = None,
    ) -> PullRequest:
        """Create a new pull request in this repository.

        Args:
            title: Title of the pull request.
            source_branch: Source branch name (e.g. ``"feature/my-branch"``
                or full ``"refs/heads/feature/my-branch"``).
            target_branch: Target branch name (e.g. ``"main"``).
            description: Optional PR description.
            completion_options: Merge and post-completion behaviour; defaults
                to squash merge with source-branch deletion.

        Returns:
            PullRequest wrapping the newly created PR.
        """
        created = high.create_pr(
            self._api_call,
            title,
            source_branch,
            target_branch,
            description=description,
            completion_options=completion_options,
        )
        pr_api_call = raw.get_pr_api_call(
            self._project_api_call, self._info.id, created.pr_id
        )
        return PullRequest(
            pr_api_call,
            self._api_call,
            created,
            self._info.project.id,
            self._info.id,
        )

    # ------------------------------------------------------------------
    # File access
    # ------------------------------------------------------------------

    def get_file_at_branch(self, path: str, branch: BranchName) -> str:
        """Return the content of a file from the tip of a branch.

        Args:
            path: Absolute file path within the repository (e.g. ``/foo.py``).
            branch: Short branch name (e.g. ``"main"``).

        Returns:
            File content as a UTF-8 string, or ``""`` if the file is absent.
        """
        return high.get_file_content_at_branch(self._api_call, path, branch)

    def get_file_at_commit(self, path: str, commit: CommitId) -> str:
        """Return the content of a file at a specific commit.

        Args:
            path: Absolute file path within the repository.
            commit: Commit SHA to resolve the file at.

        Returns:
            File content as a UTF-8 string, or ``""`` if the file is absent.
        """
        return high.get_file_content_at_commit(self._api_call, path, commit)

    # ------------------------------------------------------------------
    # Refs and branches
    # ------------------------------------------------------------------

    def iter_refs(
        self,
        name_filter: str | None = None,
        name_contains: str | None = None,
    ) -> Iterator[GitRef]:
        """Iterate over git refs in the repository.

        Args:
            name_filter: Prefix filter for ref names (ADO strips ``refs/``
                before matching, e.g. ``"heads/main"``).
            name_contains: Substring filter for ref names.

        Yields:
            GitRef for each matching ref.
        """
        yield from raw.iter_refs(
            self._api_call,
            name_filter=name_filter,
            name_contains=name_contains,
        )

    def create_branch(self, name: BranchName, from_commit: CommitId) -> None:
        """Create a new branch pointing at an existing commit.

        Args:
            name: Short branch name (e.g. ``"feature/my-branch"``). A
                ``refs/heads/`` prefix is added automatically if absent.
            from_commit: Commit SHA the new branch should point at.
        """
        high.create_branch(self._api_call, name, from_commit)

    def delete_branch(self, name: BranchName, current_commit: CommitId) -> None:
        """Delete a branch from the repository.

        Args:
            name: Short branch name or full ``refs/heads/…`` name.
            current_commit: Current HEAD SHA of the branch (used for the
                optimistic-concurrency check).
        """
        high.delete_branch(self._api_call, name, current_commit)

    # ------------------------------------------------------------------
    # Commits and diffs
    # ------------------------------------------------------------------

    def iter_commit_diff(
        self,
        base_commit: CommitId,
        target_commit: CommitId,
    ) -> Iterator[GitCommitChange]:
        """Iterate over file changes between two commits.

        Paginates automatically when the API returns partial results.
        Folder entries are excluded.

        Args:
            base_commit: The older (base) commit SHA.
            target_commit: The newer (target) commit SHA.

        Yields:
            GitCommitChange for each changed file.
        """
        yield from high.iter_commit_diff(self._api_call, base_commit, target_commit)

    # ------------------------------------------------------------------
    # Pushes
    # ------------------------------------------------------------------

    def push_commits(
        self,
        ref_updates: list[GitPushRefUpdate],
        commits: list[GitPushCommit],
    ) -> GitPushResult:
        """Push one or more commits to the repository.

        Args:
            ref_updates: One entry per branch being updated.  Use
                :data:`~pyado.raw.ZERO_SHA` as ``old_object_id`` for new
                branches.  Build entries with :func:`~pyado.raw.make_ref_update`.
            commits: Commits to include in the push.  Build entries with
                :func:`~pyado.high.make_commit`.

        Returns:
            GitPushResult containing the new push ID and commit references.
        """
        return high.push_commits(self._api_call, ref_updates, commits)
