"""OOP wrapper for Azure DevOps repository resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import high, raw
from pyado.high.git import _full_ref as _make_full_ref
from pyado.oop.commit import Commit
from pyado.oop.file_change import AddFile, DeleteFile, EditFile, RenameFile
from pyado.oop.pull_request import PullRequest
from pyado.raw import (
    AccessControlList,
    ADOUrl,
    ApiCall,
    BranchName,
    BranchStatistics,
    CommitId,
    GitCommitChange,
    GitCommitSearchCriteria,
    GitPushCommit,
    GitPushRefUpdate,
    GitPushResult,
    GitRef,
    GitRefFilter,
    PullRequestCompletionOptions,
    PullRequestId,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RepositoryId,
    RepositoryInfo,
    VersionDescriptorType,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.service import AzureDevOpsService

__all__ = ["Repository"]


class Repository:
    """An Azure DevOps Git repository resource.

    Wraps a single ADO repository and exposes its operations as instance
    methods.  Instances are obtained from :meth:`Project.iter_repositories`
    or :meth:`Project.get_repository`.

    Repositories are cached in the service — the same instance is returned
    on repeated access. Call :meth:`refresh` to re-fetch the info from the
    API.

    Attributes:
        _project: The Project this repository belongs to.
        _service: The owning AzureDevOpsService (for org-level API calls).
        _api_call: Repository-level API call used by all git operations.
        _info: The repository data returned from the API at construction time.
    """

    def __init__(
        self,
        project: "Project",
        repository_api_call: ApiCall,
        info: RepositoryInfo,
        service: "AzureDevOpsService",
    ) -> None:
        """Construct a Repository wrapper.

        Args:
            project: The Project that owns this repository.
            repository_api_call: Repository-level ADO API call (from
                raw.get_repository_api_call).
            info: Repository data as returned from the API.
            service: The AzureDevOpsService that owns this repository (used
                for org-level API calls such as ACL lookups).
        """
        self._project = project
        self._service = service
        self._api_call = repository_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> RepositoryInfo:
        """Repository data captured at construction time (or last refresh)."""
        return self._info

    @property
    def id(self) -> RepositoryId:
        """Repository UUID."""
        return self._info.id

    @property
    def name(self) -> str:
        """Repository name."""
        return self._info.name

    @property
    def default_branch(self) -> BranchName | None:
        """Default branch name (e.g. ``"refs/heads/main"``), or ``None`` if unset."""
        return self._info.default_branch

    @property
    def web_url(self) -> ADOUrl:
        """Web URL of the repository in the ADO portal."""
        return self._info.web_url

    @property
    def api_call(self) -> ApiCall:
        """Repository-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this repository belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this repository belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch repository info from the API immediately."""
        self._info = raw.get_repository_info(self._api_call)

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
        pr_api_call = raw.get_pr_api_call(self._project.api_call, self._info.id, pr_id)
        info = raw.get_pr_details(pr_api_call)
        return PullRequest(self, pr_api_call, info)

    def iter_prs(
        self,
        status: PullRequestStatus = PullRequestStatus.ACTIVE,
    ) -> Iterator[PullRequest]:
        """Iterate over pull requests in this repository.

        Args:
            status: Filter by PR lifecycle status (default: ``"active"``).
                Pass ``PullRequestStatus.ALL`` to return PRs of every status.

        Yields:
            PullRequest for each matching PR, in API-returned order.
        """
        for item in raw.iter_prs(
            self._project.api_call,
            PullRequestSearchCriteria(
                repository_id=str(self._info.id),
                status=status,
            ),
        ):
            pr_api_call = raw.get_pr_api_call(
                self._project.api_call, self._info.id, item.pr_id
            )
            yield PullRequest(self, pr_api_call, item)

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
            self._project.api_call, self._info.id, created.pr_id
        )
        return PullRequest(self, pr_api_call, created)

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

    def get_file_bytes_at_branch(self, path: str, branch: BranchName) -> bytes | None:
        """Return the raw bytes of a file from the tip of a branch.

        Use this instead of :meth:`get_file_at_branch` when the file may
        contain non-UTF-8 data (e.g. images, compiled artefacts).

        Args:
            path: Absolute file path within the repository (e.g. ``/img.png``).
            branch: Short branch name (e.g. ``"main"``).

        Returns:
            Raw file bytes, or ``None`` if the file does not exist.
        """
        short = branch.removeprefix("refs/heads/")
        return raw.get_repository_item_bytes(
            self._api_call, path, short, VersionDescriptorType.BRANCH
        )

    def get_file_bytes_at_commit(self, path: str, commit: CommitId) -> bytes | None:
        """Return the raw bytes of a file at a specific commit.

        Use this instead of :meth:`get_file_at_commit` when the file may
        contain non-UTF-8 data (e.g. images, compiled artefacts).

        Args:
            path: Absolute file path within the repository.
            commit: Commit SHA to resolve the file at.

        Returns:
            Raw file bytes, or ``None`` if the file does not exist.
        """
        return raw.get_repository_item_bytes(
            self._api_call, path, commit, VersionDescriptorType.COMMIT
        )

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
            GitRefFilter(name_filter=name_filter, name_contains=name_contains),
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

    def get_last_commit_touching_file(
        self,
        path: str,
        before_commit: CommitId,
    ) -> CommitId:
        """Return the most recent commit that touched a file at or before a commit.

        Falls back to returning *before_commit* when no matching commit is
        found (e.g. the file did not exist at that point).

        Args:
            path: Absolute file path within the repository (e.g.
                ``"/src/foo.py"``).
            before_commit: The commit SHA to search at or before.

        Returns:
            Commit SHA of the most recent touching commit, or *before_commit*.
        """
        return high.get_last_commit_touching_file(self._api_call, path, before_commit)

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

    def iter_commits(
        self,
        *,
        item_path: str | None = None,
        top: int | None = None,
        branch: str | None = None,
    ) -> Iterator[Commit]:
        """Iterate over commits in the repository.

        Args:
            item_path: When set, only commits that touched this file path are
                returned (e.g. ``"/src/foo.py"``).
            top: Maximum number of commits to return; ``None`` means no limit.
            branch: When set, only commits reachable from this branch are
                returned.  Accepts a short name (``"main"``) or a full ref
                (``"refs/heads/main"``); the ``refs/heads/`` prefix is stripped
                automatically.

        Yields:
            :class:`Commit` for each matching commit.
        """
        short_branch = branch.removeprefix("refs/heads/") if branch else None
        criteria = GitCommitSearchCriteria(
            item_path=item_path,
            top=top,
            item_version=short_branch,
            item_version_type=VersionDescriptorType.BRANCH if short_branch else None,
        )
        for ref in raw.get_repository_commits(self._api_call, criteria):
            yield Commit(self, ref)

    def get_commit(self, sha: CommitId) -> Commit:
        """Return a wrapper for a specific commit.

        Args:
            sha: Commit SHA string.

        Returns:
            :class:`Commit` wrapping the requested commit.
        """
        return Commit(self, raw.get_commit_by_id(self._api_call, sha))

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def get_acl(self) -> list[AccessControlList]:
        """Return the access control lists for this repository.

        The ACL endpoint is organisation-scoped; this method handles the
        required org-level API call internally.

        Returns:
            List of AccessControlList objects for this repository.
        """
        org_base_call = self._service.oop_api.org_base_api_call
        return raw.get_git_acl(org_base_call, self._project.id, self._info.id)

    # ------------------------------------------------------------------
    # Pushes
    # ------------------------------------------------------------------

    def make_ref_update(self, branch: BranchName) -> GitPushRefUpdate:
        """Return a ref-update entry for a branch, fetching its current SHA.

        Convenience wrapper around :func:`~pyado.high.create_ref_update` that
        supplies the repository API call automatically.  Use this when building
        a push manually via :meth:`push_commits`.

        Args:
            branch: Short branch name (e.g. ``"main"``).  A ``refs/heads/``
                prefix is added automatically if absent.

        Returns:
            GitPushRefUpdate with the branch's current commit SHA as
            ``old_object_id``.
        """
        return high.create_ref_update(self._api_call, branch)

    def commit(
        self,
        branch: BranchName,
        message: str,
        changes: list[AddFile | EditFile | DeleteFile | RenameFile],
    ) -> GitPushResult:
        """Push a single commit to an existing branch.

        Fetches the branch's current HEAD automatically and pushes the given
        changes as one commit.  For advanced cases (multiple commits, new
        branches, or multi-ref updates) use :meth:`push_commits` directly.

        Args:
            branch: Short branch name (e.g. ``"main"``).
            message: Commit message.
            changes: One or more file changes to include in the commit.
                Use :class:`AddFile`, :class:`EditFile`, :class:`DeleteFile`,
                or :class:`RenameFile`.

        Returns:
            GitPushResult containing the new push ID and commit references.

        Example::

            repo.commit("main", "Update config", [
                EditFile("/config.json", "{}"),
                DeleteFile("/old_config.json"),
            ])
        """
        ref_update = high.create_ref_update(self._api_call, branch)
        push_commit = high.make_commit(message, [c.to_git_change() for c in changes])
        return high.push_commits(self._api_call, [ref_update], [push_commit])

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

    def get_statistics(self, branch: str) -> BranchStatistics:
        """Return ahead/behind commit counts for a branch.

        Args:
            branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``).

        Returns:
            BranchStatistics with ahead/behind counts and the branch HEAD
            commit.
        """
        return raw.get_repository_statistics(self._api_call, branch)

    def get_pr_for_branch(self, source_branch: str) -> "PullRequest | None":
        """Return the first active PR for the given source branch, or ``None``.

        Args:
            source_branch: Short branch name or full ref.  A
                ``refs/heads/`` prefix is added automatically when absent.

        Returns:
            PullRequest for the first active PR from that source branch, or
            ``None`` if none exists.
        """
        full_ref = _make_full_ref(source_branch)
        for item in raw.iter_prs(
            self._project.api_call,
            PullRequestSearchCriteria(
                repository_id=str(self._info.id),
                source_ref_name=full_ref,
                status=PullRequestStatus.ACTIVE,
            ),
        ):
            pr_api_call = raw.get_pr_api_call(
                self._project.api_call, self._info.id, item.pr_id
            )
            return PullRequest(self, pr_api_call, item)
        return None
