"""OOP wrapper for Azure DevOps repository resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.exceptions import AzureDevOpsNotFoundError
from pyado.oop.repos import _git, _pull_request
from pyado.oop.repos._git import _full_ref as _make_full_ref
from pyado.oop.repos.branch import Branch
from pyado.oop.repos.commit import Commit
from pyado.oop.repos.file_change import AddFile, DeleteFile, EditFile, RenameFile
from pyado.oop.repos.pull_request import PullRequest
from pyado.oop.repos.tag import Tag
from pyado.raw import (
    AccessControlList,
    AdoUrl,
    AnnotatedTagInfo,
    AnnotatedTagRequest,
    ApiCall,
    BranchName,
    BranchStatistics,
    CommitId,
    GitCherryPickRequest,
    GitCherryPickResponse,
    GitCommitChange,
    GitCommitSearchCriteria,
    GitItem,
    GitMergeRequest,
    GitMergeResponse,
    GitMergeStatus,
    GitPushCommit,
    GitPushRefUpdate,
    GitPushResult,
    GitRef,
    GitRefFilter,
    GitRefName,
    GitRevertRequest,
    GitRevertResponse,
    PullRequestCompletionOptions,
    PullRequestId,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RecursionLevel,
    RepositoryId,
    RepositoryInfo,
    TagName,
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
    methods.  Instances are obtained from :meth:`ProjectRepos.iter_repositories`
    or :meth:`ProjectRepos.get_repository`.

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
        self._info: RepositoryInfo | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> RepositoryInfo:
        """Repository data captured at construction time (or last refresh)."""
        if self._info is None:
            self._info = raw.get_repository_info(self._api_call)
        return self._info

    @property
    def id(self) -> RepositoryId:
        """Repository UUID."""
        return self.info.id

    @property
    def name(self) -> str:
        """Repository name."""
        return self.info.name

    @property
    def default_branch(self) -> BranchName | None:
        """Default branch name (e.g. ``"refs/heads/main"``), or ``None`` if unset."""
        return self.info.default_branch

    @property
    def web_url(self) -> AdoUrl:
        """Web URL of the repository in the ADO portal."""
        return self.info.web_url

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
        """Discard cached repository info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Pull requests
    # ------------------------------------------------------------------

    def get_pull_request(self, pull_request_id: PullRequestId) -> PullRequest:
        """Return a wrapper for a specific pull request.

        Args:
            pull_request_id: Numeric ID of the pull request.

        Returns:
            PullRequest wrapping the requested PR.
        """
        pr_api_call = raw.get_pull_request_api_call(
            self._project.api_call, self.info.id, pull_request_id
        )
        info = raw.get_pull_request_details(pr_api_call)
        return PullRequest(self, pr_api_call, info)

    def iter_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> Iterator[PullRequest]:
        """Iterate over pull requests in this repository.

        Args:
            status: Filter by PR lifecycle status.  When ``None`` (default),
                all PRs are returned regardless of status.  Ignored when
                *criteria* is provided.
            criteria: Full search criteria; ``repository_id`` is always
                overridden to this repository's ID.  Use this to apply
                date-range filters (``min_time``/``max_time``) or other
                ``PullRequestSearchCriteria`` fields.
            expand: Optional ``$expand`` value (e.g. ``"labels"``,
                ``"reviewers"``).

        Yields:
            PullRequest for each matching PR, in API-returned order.
        """
        if criteria is not None:
            effective = criteria.model_copy(update={"repository_id": str(self.info.id)})
        else:
            effective = PullRequestSearchCriteria(
                repository_id=str(self.info.id),
                status=status,
            )
        for item in raw.iter_pull_requests(
            self._project.api_call,
            search_criteria=effective,
            expand=expand,
        ):
            pr_api_call = raw.get_pull_request_api_call(
                self._project.api_call, self.info.id, item.pr_id
            )
            yield PullRequest(self, pr_api_call, item, expand)

    def create_pull_request(
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
        created = _pull_request.create_pull_request(
            self._api_call,
            title,
            source_branch,
            target_branch,
            description=description,
            completion_options=completion_options,
        )
        pr_api_call = raw.get_pull_request_api_call(
            self._project.api_call, self.info.id, created.pr_id
        )
        return PullRequest(self, pr_api_call, created)

    # ------------------------------------------------------------------
    # File content access
    # ------------------------------------------------------------------

    def get_file_by_branch(self, path: str, branch: BranchName | None = None) -> str:
        """Return the content of a file from the tip of a branch.

        Use when latest content is acceptable and mutability is not a concern.
        ``branch`` defaults to ``None``, which resolves to the repository's
        default branch (``self.info.default_branch``).  The result is mutable
        and may differ between calls as the branch advances.

        Args:
            path: Absolute file path within the repository (e.g. ``/foo.py``).
            branch: Short branch name or full ref (e.g. ``"main"`` or
                ``"refs/heads/main"``).  ``None`` → repository default branch.

        Returns:
            File content as a UTF-8 string, or ``""`` if the file is absent.
        """
        effective = branch if branch is not None else (self.info.default_branch or "")
        return _git.get_file_content_at_branch(self._api_call, path, effective)

    def get_file_by_commit(self, path: str, commit: CommitId) -> str:
        """Return the content of a file at a specific commit.

        Fully immutable.  Use for reproducible references, audit trails,
        diffing, or any context where the result must not change.

        Args:
            path: Absolute file path within the repository.
            commit: Commit SHA to resolve the file at.

        Returns:
            File content as a UTF-8 string, or ``""`` if the file is absent.
        """
        return _git.get_file_content_at_commit(self._api_call, path, commit)

    def get_file_bytes_by_branch(
        self, path: str, branch: BranchName | None = None
    ) -> bytes | None:
        """Return the raw bytes of a file from the tip of a branch.

        Use when latest content is acceptable and the file may contain
        non-UTF-8 data (e.g. images, compiled artefacts).  ``branch``
        defaults to ``None``, which resolves to the repository's default
        branch.  The result is mutable and may differ between calls.

        Args:
            path: Absolute file path within the repository (e.g. ``/img.png``).
            branch: Short branch name or full ref.  ``None`` → repository
                default branch.

        Returns:
            Raw file bytes, or ``None`` if the file does not exist.
        """
        effective = branch if branch is not None else (self.info.default_branch or "")
        short = effective.removeprefix("refs/heads/")
        return raw.get_repository_item_bytes(
            self._api_call, path, short, VersionDescriptorType.BRANCH
        )

    def get_file_bytes_by_commit(self, path: str, commit: CommitId) -> bytes | None:
        """Return the raw bytes of a file at a specific commit.

        Fully immutable.  Use when the file may contain non-UTF-8 data and
        the result must not change across calls.

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

    def iter_branches(self) -> "Iterator[Branch]":
        """Iterate over all branches (``refs/heads/…``) in the repository.

        Convenience wrapper over :meth:`iter_refs` that pre-applies the
        ``heads/`` name filter so callers do not need to know the ADO ref
        filter format.

        Yields:
            :class:`~pyado.oop.repos.branch.Branch` for each branch.
        """
        for ref in self.iter_refs(name_filter="heads/"):
            yield Branch(self, ref)

    def create_branch(self, name: BranchName, from_commit: CommitId) -> None:
        """Create a new branch pointing at an existing commit.

        Args:
            name: Short branch name (e.g. ``"feature/my-branch"``). A
                ``refs/heads/`` prefix is added automatically if absent.
            from_commit: Commit SHA the new branch should point at.
        """
        _git.create_branch(self._api_call, name, from_commit)

    def get_branch_head(self, name: BranchName) -> CommitId:
        """Return the current HEAD commit SHA of a branch.

        Args:
            name: Short branch name (e.g. ``"main"``) or full ref
                (e.g. ``"refs/heads/main"``).

        Returns:
            Commit SHA string at the tip of the branch.

        Raises:
            AzureDevOpsNotFoundError: If the branch does not exist.
        """
        short = name.removeprefix("refs/heads/")
        ref = next(
            raw.iter_refs(self._api_call, GitRefFilter(name_filter=f"heads/{short}")),
            None,
        )
        if ref is None:
            raise AzureDevOpsNotFoundError(404, f"Branch not found: {name!r}")
        return ref.object_id

    def check_branch_exists(self, name: BranchName) -> bool:
        """Return True if the branch exists in this repository.

        Args:
            name: Short branch name (e.g. ``"main"``) or full ref
                (e.g. ``"refs/heads/main"``).

        Returns:
            True if the branch exists, False otherwise.
        """
        short = name.removeprefix("refs/heads/")
        return any(
            raw.iter_refs(self._api_call, GitRefFilter(name_filter=f"heads/{short}"))
        )

    def delete_branch(
        self,
        name: BranchName,
        current_commit: CommitId | None = None,
    ) -> None:
        """Delete a branch from the repository.

        When *current_commit* is supplied it is used directly as the
        optimistic-concurrency guard (zero extra API calls).  When omitted,
        the current HEAD SHA is fetched automatically via
        :meth:`get_branch_head` (one extra ``GET /refs`` call).

        Args:
            name: Short branch name or full ``refs/heads/…`` name.
            current_commit: Current HEAD SHA of the branch.  ``None`` →
                fetched automatically.
        """
        sha = (
            current_commit if current_commit is not None else self.get_branch_head(name)
        )
        _git.delete_branch(self._api_call, name, sha)

    def iter_git_tags(self) -> Iterator[Tag]:
        """Iterate over all git tags in the repository.

        Yields:
            :class:`~pyado.oop.repos.tag.Tag` for each tag.
        """
        for ref in raw.iter_tags(self._api_call):
            yield Tag(self, ref)

    def create_git_tag(self, name: str, commit_id: CommitId) -> None:
        """Create a lightweight tag pointing at an existing commit.

        Args:
            name: Short tag name (e.g. ``"v1.0"``).  A ``refs/tags/`` prefix
                is added automatically if absent.
            commit_id: Commit SHA the tag should point at.
        """
        raw.post_git_tag(self._api_call, name, commit_id)

    def delete_git_tag(self, name: str, commit_id: CommitId) -> None:
        """Delete a git tag from the repository.

        Args:
            name: Short tag name (e.g. ``"v1.0"``).  A ``refs/tags/`` prefix
                is added automatically if absent.
            commit_id: Current object ID of the tag (optimistic-concurrency
                check).
        """
        raw.delete_git_tag(self._api_call, name, commit_id)

    def create_annotated_tag(
        self,
        name: str,
        message: str,
        commit_sha: CommitId,
    ) -> AnnotatedTagInfo:
        """Create an annotated tag in this repository.

        An annotated tag is a full git object (not just a lightweight ref
        pointer) and carries a message and tagger identity.  Use
        :meth:`create_git_tag` for lightweight tags.

        Args:
            name: Tag name without ``refs/tags/`` prefix (e.g. ``"v1.0"``).
            message: Annotation message for the tag.
            commit_sha: Commit SHA the tag should point at.

        Returns:
            AnnotatedTagInfo describing the newly created annotated tag.
        """
        return raw.post_annotated_tag(
            self._api_call,
            AnnotatedTagRequest.from_commit(name, commit_sha, message),
        )

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
        return _git.get_last_commit_touching_file(self._api_call, path, before_commit)

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
        yield from _git.iter_commit_diff(self._api_call, base_commit, target_commit)

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

    def get_default_branch_commit(self) -> Commit:
        """Return the HEAD commit of the default branch.

        Convenience shortcut that avoids a separate :meth:`iter_refs` call
        followed by :meth:`get_commit`.

        Returns:
            :class:`Commit` at the tip of the default branch.

        Raises:
            AzureDevOpsNotFoundError: If the repository has no default branch
                configured, or if the default branch ref is not found (e.g.
                empty repository).
        """
        branch = self.info.default_branch
        if branch is None:
            err_msg = f"Repository {self.info.name!r} has no default branch."
            raise AzureDevOpsNotFoundError(404, err_msg)
        short = branch.removeprefix("refs/")
        ref = next(raw.iter_refs(self._api_call, GitRefFilter(name_filter=short)), None)
        if ref is None:
            err_msg = f"Default branch ref {branch!r} not found."
            raise AzureDevOpsNotFoundError(404, err_msg)
        return self.get_commit(ref.object_id)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------

    def list_acl(self) -> list[AccessControlList]:
        """Return the access control lists for this repository.

        The ACL endpoint is organisation-scoped; this method handles the
        required org-level API call internally.

        Returns:
            List of AccessControlList objects for this repository.
        """
        org_base_call = self._service.oop_api.org_base_api_call
        return raw.get_git_acl(org_base_call, self._project.id, self.info.id)

    # ------------------------------------------------------------------
    # Pushes
    # ------------------------------------------------------------------

    def make_ref_update(self, branch: BranchName) -> GitPushRefUpdate:
        """Return a ref-update entry for a branch, fetching its current SHA.

        Convenience wrapper around :func:`~pyado.oop.repos._git.create_ref_update`
        that supplies the repository API call automatically.  Use this when
        building a push manually via :meth:`push_commits`.

        Args:
            branch: Short branch name (e.g. ``"main"``).  A ``refs/heads/``
                prefix is added automatically if absent.

        Returns:
            GitPushRefUpdate with the branch's current commit SHA as
            ``old_object_id``.
        """
        return _git.create_ref_update(self._api_call, branch)

    def commit(
        self,
        branch: BranchName | None,
        message: str,
        changes: list[AddFile | EditFile | DeleteFile | RenameFile],
        current_commit: CommitId | None = None,
    ) -> GitPushResult:
        """Push a single commit to an existing branch.

        When *current_commit* is supplied it is used directly as the
        optimistic-concurrency guard (zero extra API calls).  When omitted,
        the branch's current HEAD SHA is fetched automatically via
        ``GET /refs`` (one extra call).

        Args:
            branch: Short branch name (e.g. ``"main"``).  ``None`` →
                repository default branch.
            message: Commit message.
            changes: One or more file changes to include in the commit.
                Use :class:`AddFile`, :class:`EditFile`, :class:`DeleteFile`,
                or :class:`RenameFile`.
            current_commit: Current HEAD SHA of the branch used for the
                optimistic-concurrency check.  ``None`` → fetched
                automatically.

        Returns:
            GitPushResult containing the new push ID and commit references.

        Example::

            repo.commit("main", "Update config", [
                EditFile("/config.json", "{}"),
                DeleteFile("/old_config.json"),
            ])
        """
        effective_branch = (
            branch if branch is not None else (self.info.default_branch or "")
        )
        ref_update = (
            _git.create_ref_update_from_sha(
                self._api_call, effective_branch, current_commit
            )
            if current_commit is not None
            else _git.create_ref_update(self._api_call, effective_branch)
        )
        push_commit = _git.make_commit(message, [c.to_git_change() for c in changes])
        return _git.push_commits(self._api_call, [ref_update], [push_commit])

    def commit_file_delete(
        self, branch: BranchName, path: str, message: str
    ) -> GitPushResult:
        """Delete a file from a branch in a single commit.

        Args:
            branch: Short branch name (e.g. ``"main"``).
            path: Absolute file path within the repository (e.g.
                ``"/config.json"``).
            message: Commit message.

        Returns:
            GitPushResult containing the new push ID and commit references.
        """
        return self.commit(branch, message, [DeleteFile(path)])

    def commit_file_rename(
        self,
        branch: BranchName,
        old_path: str,
        new_path: str,
        message: str,
    ) -> GitPushResult:
        """Rename (move) a file on a branch in a single commit.

        Args:
            branch: Short branch name (e.g. ``"main"``).
            old_path: Current absolute file path within the repository.
            new_path: New absolute file path within the repository.
            message: Commit message.

        Returns:
            GitPushResult containing the new push ID and commit references.
        """
        return self.commit(branch, message, [RenameFile(old_path, new_path)])

    def push_commits(
        self,
        ref_updates: list[GitPushRefUpdate],
        commits: list[GitPushCommit],
    ) -> GitPushResult:
        """Push one or more commits to the repository.

        Args:
            ref_updates: One entry per branch being updated.  Use
                :data:`~pyado.raw.ZERO_SHA` as ``old_object_id`` for new
                branches.  Build entries with :meth:`make_ref_update`.
            commits: Commits to include in the push.  Build entries with
                :func:`~pyado.oop.repos._git.make_commit`.

        Returns:
            GitPushResult containing the new push ID and commit references.
        """
        return _git.push_commits(self._api_call, ref_updates, commits)

    def iter_items(
        self,
        scope_path: str = "/",
        *,
        branch: BranchName | None = None,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> Iterator[GitItem]:
        """Iterate over files and folders at *scope_path*.

        Args:
            scope_path: Directory path to list (default: root ``"/"``).
            branch: Short branch name or full ref.  When ``None``, the
                repository default branch is used.
            recursion_level: Depth of recursion (default: one level).

        Yields:
            GitItem for each file or folder entry.
        """
        yield from raw.iter_repository_items(
            self._api_call,
            scope_path,
            branch=branch,
            recursion_level=recursion_level,
        )

    def list_items(
        self,
        scope_path: str = "/",
        *,
        branch: BranchName | None = None,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> list[GitItem]:
        """Return all items at *scope_path* as a list.

        Args:
            scope_path: Directory path to list (default: root ``"/"``).
            branch: Short branch name or full ref.  When ``None``, the
                repository default branch is used.
            recursion_level: Depth of recursion (default: one level).

        Returns:
            List of GitItem for each file or folder entry.
        """
        return list(
            self.iter_items(scope_path, branch=branch, recursion_level=recursion_level)
        )

    def iter_items_by_commit(
        self,
        scope_path: str = "/",
        *,
        commit: CommitId,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> Iterator[GitItem]:
        """Iterate over files and folders at *scope_path* at a specific commit.

        Fully immutable.  Use for reproducible references, audit trails, or
        any context where the listing must not change between calls.

        Args:
            scope_path: Directory path to list (default: root ``"/"``).
            commit: Commit SHA to resolve the listing at.
            recursion_level: Depth of recursion (default: one level).

        Yields:
            GitItem for each file or folder entry.
        """
        yield from raw.iter_repository_items(
            self._api_call,
            scope_path,
            recursion_level=recursion_level,
            version=commit,
            version_type=VersionDescriptorType.COMMIT,
        )

    def list_items_by_commit(
        self,
        scope_path: str = "/",
        *,
        commit: CommitId,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> list[GitItem]:
        """Return items at *scope_path* at a specific commit as a list."""
        return list(
            self.iter_items_by_commit(
                scope_path, commit=commit, recursion_level=recursion_level
            )
        )

    def iter_items_by_tag(
        self,
        scope_path: str = "/",
        *,
        tag: TagName,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> Iterator[GitItem]:
        """Iterate over files and folders at *scope_path* at a tagged version.

        Resolves to the tagged object.  Note that lightweight tags are mutable
        (can be deleted and re-created pointing elsewhere); callers that
        require true immutability should resolve the tag to a commit SHA and
        use :meth:`iter_items_by_commit` instead.

        Args:
            scope_path: Directory path to list (default: root ``"/"``).
            tag: Short tag name (e.g. ``"v1.0"``) or full ref
                (e.g. ``"refs/tags/v1.0"``); the ``refs/tags/`` prefix is
                stripped automatically.
            recursion_level: Depth of recursion (default: one level).

        Yields:
            GitItem for each file or folder entry.
        """
        short = tag.removeprefix("refs/tags/")
        yield from raw.iter_repository_items(
            self._api_call,
            scope_path,
            recursion_level=recursion_level,
            version=short,
            version_type=VersionDescriptorType.TAG,
        )

    def list_items_by_tag(
        self,
        scope_path: str = "/",
        *,
        tag: TagName,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> list[GitItem]:
        """Return items at *scope_path* at a tagged version as a list."""
        return list(
            self.iter_items_by_tag(scope_path, tag=tag, recursion_level=recursion_level)
        )

    def iter_items_by_ref(
        self,
        scope_path: str = "/",
        *,
        ref: GitRefName,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> Iterator[GitItem]:
        """Iterate over files and folders at *scope_path* at an arbitrary ref.

        Escape hatch for refs outside the typed categories (e.g. pull-request
        merge refs ``"refs/pull/{id}/merge"``).  The ref is resolved to a
        commit SHA via the refs API before fetching items, which ensures
        the ADO items endpoint can handle all ref types (branch, PR merge,
        etc.).

        Args:
            scope_path: Directory path to list (default: root ``"/"``).
            ref: Arbitrary full git ref string (e.g. ``"refs/pull/42/merge"``).
            recursion_level: Depth of recursion (default: one level).

        Yields:
            GitItem for each file or folder entry.

        Raises:
            AzureDevOpsNotFoundError: If the ref cannot be resolved.
        """
        filter_name = ref.removeprefix("refs/")
        resolved = next(
            raw.iter_refs(self._api_call, GitRefFilter(name_filter=filter_name)), None
        )
        if resolved is None:
            raise AzureDevOpsNotFoundError(404, f"Ref not found: {ref!r}")
        yield from raw.iter_repository_items(
            self._api_call,
            scope_path,
            recursion_level=recursion_level,
            version=resolved.object_id,
            version_type=VersionDescriptorType.COMMIT,
        )

    def list_items_by_ref(
        self,
        scope_path: str = "/",
        *,
        ref: GitRefName,
        recursion_level: RecursionLevel = RecursionLevel.ONE_LEVEL,
    ) -> list[GitItem]:
        """Return items at *scope_path* at an arbitrary ref as a list."""
        return list(
            self.iter_items_by_ref(scope_path, ref=ref, recursion_level=recursion_level)
        )

    # ------------------------------------------------------------------
    # Single-file metadata (A5)
    # ------------------------------------------------------------------

    def get_item_by_branch(
        self, path: str, branch: BranchName | None = None
    ) -> GitItem | None:
        """Return metadata for a single file at the tip of a branch, or None.

        Fetches metadata only (no file content), so this is cheap enough to
        use for existence checks.  ``branch`` defaults to ``None``, which
        resolves to the repository's default branch.  The result is mutable
        and may differ between calls as the branch advances.

        Args:
            path: Absolute file path within the repository.
            branch: Short branch name or full ref.  ``None`` → repository
                default branch.

        Returns:
            GitItem for the file, or None if it does not exist.
        """
        effective = branch if branch is not None else (self.info.default_branch or "")
        short = effective.removeprefix("refs/heads/")
        return raw.get_repository_item(
            self._api_call, path, short, VersionDescriptorType.BRANCH
        )

    def get_item_by_commit(self, path: str, commit: CommitId) -> GitItem | None:
        """Return metadata for a single file at a specific commit, or None.

        Fully immutable.  Use for reproducible references, audit trails,
        diffing, or any context where the result must not change.

        Args:
            path: Absolute file path within the repository.
            commit: Commit SHA to resolve the file at.

        Returns:
            GitItem for the file, or None if it does not exist.
        """
        return raw.get_repository_item(
            self._api_call, path, commit, VersionDescriptorType.COMMIT
        )

    def get_item_by_tag(self, path: str, tag: TagName) -> GitItem | None:
        """Return metadata for a single file at a tagged version, or None.

        Resolves to the tagged object.  Note that lightweight tags are mutable
        (can be deleted and re-created pointing elsewhere); callers requiring
        true immutability should resolve the tag to a commit SHA first and use
        :meth:`get_item_by_commit`.

        Args:
            path: Absolute file path within the repository.
            tag: Short tag name (e.g. ``"v1.0"``) or full ref
                (e.g. ``"refs/tags/v1.0"``); the ``refs/tags/`` prefix is
                stripped automatically.

        Returns:
            GitItem for the file, or None if it does not exist.
        """
        short = tag.removeprefix("refs/tags/")
        return raw.get_repository_item(
            self._api_call, path, short, VersionDescriptorType.TAG
        )

    def get_item_by_ref(self, path: str, ref: GitRefName) -> GitItem | None:
        """Return metadata for a single file at an arbitrary ref, or None.

        Escape hatch for refs outside the typed categories (e.g. pull-request
        merge refs ``"refs/pull/{id}/merge"``).  The ref is resolved to a
        commit SHA via the refs API before fetching the item.

        Args:
            path: Absolute file path within the repository.
            ref: Arbitrary full git ref string (e.g. ``"refs/pull/42/merge"``).

        Returns:
            GitItem for the file, or None if the file does not exist at the ref.

        Raises:
            AzureDevOpsNotFoundError: If the ref cannot be resolved.
        """
        filter_name = ref.removeprefix("refs/")
        resolved = next(
            raw.iter_refs(self._api_call, GitRefFilter(name_filter=filter_name)), None
        )
        if resolved is None:
            raise AzureDevOpsNotFoundError(404, f"Ref not found: {ref!r}")
        return raw.get_repository_item(
            self._api_call, path, resolved.object_id, VersionDescriptorType.COMMIT
        )

    # ------------------------------------------------------------------
    # File existence checks (A6)
    # ------------------------------------------------------------------

    def check_file_exists_by_branch(
        self, path: str, branch: BranchName | None = None
    ) -> bool:
        """Return True if a file exists at the tip of a branch.

        Thin boolean wrapper over :meth:`get_item_by_branch`.  Fetches
        metadata only (no file content), so this is cheap.

        Args:
            path: Absolute file path within the repository.
            branch: Short branch name or full ref.  ``None`` → repository
                default branch.

        Returns:
            True if the file exists, False otherwise.
        """
        return self.get_item_by_branch(path, branch) is not None

    def check_file_exists_by_commit(self, path: str, commit: CommitId) -> bool:
        """Return True if a file exists at a specific commit.

        Thin boolean wrapper over :meth:`get_item_by_commit`.  Fully
        immutable — the result will not change for the same commit SHA.

        Args:
            path: Absolute file path within the repository.
            commit: Commit SHA to resolve the file at.

        Returns:
            True if the file exists, False otherwise.
        """
        return self.get_item_by_commit(path, commit) is not None

    def check_file_exists_by_tag(self, path: str, tag: TagName) -> bool:
        """Return True if a file exists at a tagged version.

        Thin boolean wrapper over :meth:`get_item_by_tag`.  Note that
        lightweight tags are mutable; see :meth:`get_item_by_tag`.

        Args:
            path: Absolute file path within the repository.
            tag: Short tag name or full ref.

        Returns:
            True if the file exists, False otherwise.
        """
        return self.get_item_by_tag(path, tag) is not None

    def check_file_exists_by_ref(self, path: str, ref: GitRefName) -> bool:
        """Return True if a file exists at an arbitrary ref.

        Thin boolean wrapper over :meth:`get_item_by_ref`.

        Args:
            path: Absolute file path within the repository.
            ref: Arbitrary full git ref string.

        Returns:
            True if the file exists, False otherwise.
        """
        return self.get_item_by_ref(path, ref) is not None

    # ------------------------------------------------------------------
    # Smart file commit (A7)
    # ------------------------------------------------------------------

    def commit_file_upsert(
        self,
        branch: BranchName | None,
        path: str,
        content: str,
        message: str,
        current_commit: CommitId | None = None,
    ) -> GitPushResult:
        """Create or update a single file on a branch in one commit.

        Detects whether the file already exists (using
        :meth:`check_file_exists_by_branch`) and applies an ``EditFile``
        change if it does, or an ``AddFile`` change if it does not.  Unlike
        the ``_by_branch`` read methods, *branch* here accepts ``None`` which
        also resolves to the repository's default branch — consistent with
        the read API.

        Note: unlike the ``_by_branch`` read methods, writing always targets
        a specific branch; there is no tag or commit variant because git
        objects are immutable after creation.

        *current_commit* supports optimistic concurrency: supply the HEAD SHA
        you observed to ensure ADO rejects the push if a concurrent write
        landed in the meantime; omit to let :meth:`commit` fetch the current
        HEAD automatically.

        Args:
            branch: Target branch name.  ``None`` → repository default branch.
            path: Absolute file path within the repository.
            content: New UTF-8 text content for the file.
            message: Commit message.
            current_commit: Current HEAD SHA for optimistic-concurrency.
                ``None`` → fetched automatically.

        Returns:
            GitPushResult containing the new push ID and commit references.
        """
        change: EditFile | AddFile = (
            EditFile(path, content)
            if self.check_file_exists_by_branch(path, branch)
            else AddFile(path, content)
        )
        return self.commit(branch, message, [change], current_commit=current_commit)

    def get_statistics(self, branch: BranchName) -> BranchStatistics:
        """Return ahead/behind commit counts for a branch.

        Args:
            branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``).

        Returns:
            BranchStatistics with ahead/behind counts and the branch HEAD
            commit.
        """
        return raw.get_repository_statistics(self._api_call, branch)

    def get_pr_for_commit(self, sha: CommitId) -> "PullRequest | None":
        """Return the first active PR whose source branch contains *sha*, or ``None``.

        Uses ``searchCriteria.sourceVersion`` to restrict the search to PRs
        that include the given commit.

        Args:
            sha: Commit SHA string to search for.

        Returns:
            PullRequest for the first active PR whose source version matches
            *sha*, or ``None`` if no such PR exists.
        """
        for item in raw.iter_pull_requests(
            self._project.api_call,
            search_criteria=PullRequestSearchCriteria(
                repository_id=str(self.info.id),
                source_version=sha,
                status=PullRequestStatus.ACTIVE,
            ),
        ):
            pr_api_call = raw.get_pull_request_api_call(
                self._project.api_call, self.info.id, item.pr_id
            )
            return PullRequest(self, pr_api_call, item)
        return None

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
        for item in raw.iter_pull_requests(
            self._project.api_call,
            search_criteria=PullRequestSearchCriteria(
                repository_id=str(self.info.id),
                source_ref_name=full_ref,
                status=PullRequestStatus.ACTIVE,
            ),
        ):
            pr_api_call = raw.get_pull_request_api_call(
                self._project.api_call, self.info.id, item.pr_id
            )
            return PullRequest(self, pr_api_call, item)
        return None

    def list_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> list[PullRequest]:
        """Return all pull requests in this repository as a list."""
        return list(
            self.iter_pull_requests(status=status, criteria=criteria, expand=expand)
        )

    def list_refs(
        self,
        name_filter: str | None = None,
        name_contains: str | None = None,
    ) -> list[GitRef]:
        """Return all refs matching the filter as a list."""
        return list(
            self.iter_refs(name_filter=name_filter, name_contains=name_contains)
        )

    def list_branches(self) -> "list[Branch]":
        """Return all branches in this repository as a list."""
        return list(self.iter_branches())

    def list_git_tags(self) -> list[Tag]:
        """Return all git tags in this repository as a list."""
        return list(self.iter_git_tags())

    def list_commit_diff(
        self,
        base_commit: CommitId,
        target_commit: CommitId,
    ) -> list[GitCommitChange]:
        """Return all file changes between two commits as a list."""
        return list(self.iter_commit_diff(base_commit, target_commit))

    def list_commits(
        self,
        *,
        item_path: str | None = None,
        top: int | None = None,
        branch: str | None = None,
    ) -> list[Commit]:
        """Return all commits matching the given criteria as a list."""
        return list(self.iter_commits(item_path=item_path, top=top, branch=branch))

    def iter_commits_by_commit(
        self,
        commit: CommitId,
        *,
        item_path: str | None = None,
        top: int | None = None,
    ) -> Iterator[Commit]:
        """Iterate over commits reachable from a specific commit.

        Fully immutable.  Use for reproducible references, audit trails,
        or any context where the commit list must not change.

        Args:
            commit: Commit SHA to search from.
            item_path: When set, only commits that touched this file path are
                returned.
            top: Maximum number of commits to return; ``None`` means no limit.

        Yields:
            :class:`Commit` for each matching commit.
        """
        criteria = GitCommitSearchCriteria(
            item_path=item_path,
            top=top,
            item_version=commit,
            item_version_type=VersionDescriptorType.COMMIT,
        )
        for ref in raw.get_repository_commits(self._api_call, criteria):
            yield Commit(self, ref)

    def list_commits_by_commit(
        self,
        commit: CommitId,
        *,
        item_path: str | None = None,
        top: int | None = None,
    ) -> list[Commit]:
        """Return commits reachable from a specific commit as a list."""
        return list(self.iter_commits_by_commit(commit, item_path=item_path, top=top))

    def iter_commits_by_tag(
        self,
        tag: TagName,
        *,
        item_path: str | None = None,
        top: int | None = None,
    ) -> Iterator[Commit]:
        """Iterate over commits reachable from a tagged version.

        Resolves to the tagged object.  Note that lightweight tags are mutable
        (can be deleted and re-created pointing elsewhere); callers requiring
        true immutability should resolve the tag to a commit SHA and use
        :meth:`iter_commits_by_commit` instead.

        Args:
            tag: Short tag name (e.g. ``"v1.0"``) or full ref
                (e.g. ``"refs/tags/v1.0"``); the ``refs/tags/`` prefix is
                stripped automatically.
            item_path: When set, only commits that touched this file path are
                returned.
            top: Maximum number of commits to return; ``None`` means no limit.

        Yields:
            :class:`Commit` for each matching commit.
        """
        short = tag.removeprefix("refs/tags/")
        criteria = GitCommitSearchCriteria(
            item_path=item_path,
            top=top,
            item_version=short,
            item_version_type=VersionDescriptorType.TAG,
        )
        for ref in raw.get_repository_commits(self._api_call, criteria):
            yield Commit(self, ref)

    def list_commits_by_tag(
        self,
        tag: TagName,
        *,
        item_path: str | None = None,
        top: int | None = None,
    ) -> list[Commit]:
        """Return commits reachable from a tagged version as a list."""
        return list(self.iter_commits_by_tag(tag, item_path=item_path, top=top))

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def start_merge(
        self,
        source: CommitId,
        target: CommitId,
        *,
        comment: str | None = None,
    ) -> GitMergeResponse:
        """Queue a merge of two commits and return immediately.

        ADO processes merges asynchronously.  The response status is typically
        ``GitMergeStatus.QUEUED`` on return.  Poll with :meth:`get_merge_status`
        or use :meth:`check_merge_feasible` to wait for the result.

        Args:
            source: Commit SHA of the source (feature) branch tip.
            target: Commit SHA of the target (base) branch tip.
            comment: Optional merge commit message.

        Returns:
            GitMergeResponse with the initial operation status.
        """
        return raw.post_git_merge(
            self._api_call,
            GitMergeRequest(comment=comment, parents=[source, target]),
        )

    def get_merge_status(self, merge_operation_id: int) -> GitMergeResponse:
        """Return the current status of a queued merge operation.

        Args:
            merge_operation_id: The operation ID from :meth:`start_merge`.

        Returns:
            GitMergeResponse with the current status.
        """
        return raw.get_git_merge(self._api_call, merge_operation_id)

    def check_merge_feasible(
        self,
        source: CommitId,
        target: CommitId,
        *,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Return True if *source* can be merged into *target* without conflicts.

        Queues a merge via ADO and polls until the operation reaches a terminal
        status or *timeout* seconds elapse.  Returns ``True`` for
        ``COMPLETED``, ``False`` for ``CONFLICTS`` or ``FAILURE``.

        Args:
            source: Commit SHA of the source branch tip.
            target: Commit SHA of the target branch tip.
            timeout: Maximum number of seconds to wait for ADO to complete the
                merge check.  Defaults to 10 s.
            poll_interval: Seconds between poll attempts.  Defaults to 0.5 s.

        Returns:
            True if the merge can be applied cleanly, False if it cannot.

        Raises:
            AzureDevOpsNotFoundError: If either commit SHA is not found by ADO
                (``INVALID_REFS`` status).
            TimeoutError: If the operation is still ``QUEUED`` after *timeout*
                seconds.
        """
        response = self.start_merge(source, target)
        operation_id = response.merge_operation_id
        deadline = time.monotonic() + timeout
        while response.status == GitMergeStatus.QUEUED:
            if time.monotonic() >= deadline:
                msg = f"Merge operation {operation_id} still queued after {timeout}s."
                raise TimeoutError(msg)
            time.sleep(poll_interval)
            if operation_id is not None:
                response = self.get_merge_status(operation_id)
        if response.status == GitMergeStatus.INVALID_REFS:
            raise AzureDevOpsNotFoundError(
                404,
                f"Merge check failed: one or both commit SHAs not found "
                f"(source={source!r}, target={target!r}).",
            )
        return response.status == GitMergeStatus.COMPLETED

    # ------------------------------------------------------------------
    # Cherry-pick
    # ------------------------------------------------------------------

    def start_cherry_pick(
        self,
        onto: str,
        cherry_pick_ref: str,
    ) -> GitCherryPickResponse:
        """Queue a cherry-pick and return immediately.

        ADO cherry-picks asynchronously.  The response status is typically
        ``GitCherryPickStatus.QUEUED`` on return.  Poll with
        :meth:`get_cherry_pick_status` to check for completion.

        Args:
            onto: Target branch name (e.g. ``"main"`` or
                ``"refs/heads/main"``).  The ``refs/heads/`` prefix is added
                automatically when absent.
            cherry_pick_ref: Name of the new branch ADO will create containing
                the cherry-picked commit (short name or full ref).

        Returns:
            GitCherryPickResponse with the initial operation status.
        """
        return raw.post_git_cherry_pick(
            self._api_call,
            GitCherryPickRequest(
                onto=_make_full_ref(onto),
                cherry_pick_ref=_make_full_ref(cherry_pick_ref),
            ),
        )

    def get_cherry_pick_status(self, cherry_pick_id: int) -> GitCherryPickResponse:
        """Return the current status of a queued cherry-pick operation.

        Args:
            cherry_pick_id: The operation ID from :meth:`start_cherry_pick`.

        Returns:
            GitCherryPickResponse with the current status.
        """
        return raw.get_git_cherry_pick(self._api_call, cherry_pick_id)

    # ------------------------------------------------------------------
    # Revert
    # ------------------------------------------------------------------

    def start_revert(
        self,
        onto: str,
        revert_ref: str,
    ) -> GitRevertResponse:
        """Queue a revert and return immediately.

        ADO reverts asynchronously.  The response status is typically
        ``GitRevertStatus.QUEUED`` on return.  Poll with
        :meth:`get_revert_status` to check for completion.

        Args:
            onto: Target branch name (e.g. ``"main"`` or
                ``"refs/heads/main"``).  The ``refs/heads/`` prefix is added
                automatically when absent.
            revert_ref: Name of the new branch ADO will create containing the
                revert commit (short name or full ref).

        Returns:
            GitRevertResponse with the initial operation status.
        """
        return raw.post_git_revert(
            self._api_call,
            GitRevertRequest(
                onto=_make_full_ref(onto),
                revert_ref=_make_full_ref(revert_ref),
            ),
        )

    def get_revert_status(self, revert_id: int) -> GitRevertResponse:
        """Return the current status of a queued revert operation.

        Args:
            revert_id: The operation ID from :meth:`start_revert`.

        Returns:
            GitRevertResponse with the current status.
        """
        return raw.get_git_revert(self._api_call, revert_id)
