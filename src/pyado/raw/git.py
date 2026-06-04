"""Azure DevOps Git repository, commit, ref, diff, and push API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt

from pyado.raw._core import ADOUrl, ApiCall
from pyado.raw.project import ProjectInfo
from pyado.raw.work_item import WorkItemRef

#: Security namespace GUID for git repositories.
#: Used with ``GET /_apis/accesscontrollists/{GIT_SECURITY_NAMESPACE_ID}``.
GIT_SECURITY_NAMESPACE_ID = "2e9eb7ed-3c0a-47d4-87c1-0ffdd275fd87"

__all__ = [
    "GIT_SECURITY_NAMESPACE_ID",
    "ZERO_SHA",
    "AccessControlEntry",
    "AccessControlList",
    "BranchName",
    "BranchStatistics",
    "CommitDiffPage",
    "CommitId",
    "GitChangeType",
    "GitCommitChange",
    "GitCommitChangeItem",
    "GitCommitRef",
    "GitCommitSearchCriteria",
    "GitPushChange",
    "GitPushChangeItem",
    "GitPushCommit",
    "GitPushContentType",
    "GitPushNewContent",
    "GitPushRefUpdate",
    "GitPushRequest",
    "GitPushResult",
    "GitRef",
    "GitRefFilter",
    "GitRefUpdate",
    "GitStatus",
    "GitStatusState",
    "PullRequestStatusContext",
    "RepositoryId",
    "RepositoryInfo",
    "RepositoryName",
    "SshUrl",
    "VersionDescriptorType",
    "get_commit_by_id",
    "get_commit_diff_page",
    "get_git_acl",
    "get_repository_api_call",
    "get_repository_commits",
    "get_repository_info",
    "get_repository_item_bytes",
    "get_repository_statistics",
    "iter_refs",
    "iter_repository_details",
    "make_git_acl_token",
    "make_ref_update",
    "post_push",
    "post_repository_refs",
]

RepositoryName = str
BranchName = str
RepositoryId = UUID
CommitId = str
SshUrl = str

#: Null commit SHA used to represent a non-existent ref (e.g. deleting a branch).
ZERO_SHA: CommitId = "0000000000000000000000000000000000000000"


class GitStatusState(StrEnum):
    """Possible state values for a git commit or pull request status."""

    NOT_SET = "notSet"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ERROR = "error"
    NOT_APPLICABLE = "notApplicable"


class VersionDescriptorType(StrEnum):
    """Version type for item-version descriptors in git API queries."""

    BRANCH = "branch"
    TAG = "tag"
    COMMIT = "commit"
    TIP = "tip"


class _GitRepositoryRef(BaseModel):
    """Minimal repository reference as returned in parent-repository fields."""

    id: RepositoryId
    name: RepositoryName


class RepositoryInfo(BaseModel):
    """Type to store repository details."""

    id: RepositoryId
    name: RepositoryName
    project: ProjectInfo
    default_branch: BranchName | None = Field(alias="defaultBranch", default=None)
    size: NonNegativeInt
    remote_url: ADOUrl = Field(alias="remoteUrl")
    ssh_url: SshUrl = Field(alias="sshUrl")
    web_url: ADOUrl = Field(alias="webUrl")
    is_disabled: bool = Field(alias="isDisabled")
    is_in_maintenance: bool = Field(alias="isInMaintenance")
    is_fork: bool = Field(alias="isFork", default=False)
    url: ADOUrl | None = None
    parent_repository: "_GitRepositoryRef | None" = Field(
        alias="parentRepository", default=None
    )


class _RepositoryInfoResults(BaseModel):
    """Type to read repository details results."""

    value: list[RepositoryInfo]


class GitChangeType(StrEnum):
    """Operation type for a single file change (push, diff, or PR iteration)."""

    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"
    RENAME = "rename"


class GitCommitChangeItem(BaseModel):
    """The item (file or folder) affected by a single commit change."""

    path: str
    is_folder: bool = Field(alias="isFolder", default=False)


class GitCommitChange(BaseModel):
    """A single change entry in a commit diff."""

    change_type: GitChangeType = Field(alias="changeType")
    item: GitCommitChangeItem


class _GitUserDate(BaseModel):
    """Author or committer identity and date attached to a git commit."""

    name: str
    email: str
    date: datetime | None = None


class PullRequestStatusContext(BaseModel):
    """The context identifier for a git or pull request status."""

    name: str
    genre: str | None = None


class GitStatus(BaseModel):
    """A status entry attached to a git commit."""

    id: int | None = None
    state: GitStatusState
    description: str | None = None
    context: PullRequestStatusContext | None = None
    creation_date: datetime | None = Field(alias="creationDate", default=None)
    updated_date: datetime | None = Field(alias="updatedDate", default=None)
    target_url: str | None = Field(alias="targetUrl", default=None)


class GitCommitRef(BaseModel):
    """A minimal git commit reference."""

    commit_id: CommitId = Field(alias="commitId")
    comment: str | None = None
    comment_truncated: bool = Field(alias="commentTruncated", default=False)
    author: _GitUserDate | None = None
    committer: _GitUserDate | None = None
    parents: list[CommitId] = []
    url: str | None = None
    change_counts: dict[str, int] | None = Field(alias="changeCounts", default=None)
    statuses: list[GitStatus] = []
    work_items: list[WorkItemRef] = []


class GitRef(BaseModel):
    """A git ref (branch or tag) entry returned by the refs endpoint."""

    name: str
    object_id: CommitId = Field(alias="objectId")


class GitRefFilter(BaseModel):
    """Filter criteria for listing git refs.

    All fields are optional; only non-None values are forwarded as query
    parameters.

    Attributes:
        name_filter: Prefix filter applied by ADO, e.g. ``"heads/main"`` to
            match exactly ``refs/heads/main`` (ADO strips the ``refs/`` prefix
            before matching).
        name_contains: Substring filter applied to the full ref name.
    """

    name_filter: str | None = Field(default=None, serialization_alias="filter")
    name_contains: str | None = Field(
        default=None, serialization_alias="filterContains"
    )


class _GitRefResults(BaseModel):
    """Internal: container for git ref list results."""

    value: list[GitRef]


class CommitDiffPage(BaseModel):
    """One page of results from the diffs/commits endpoint."""

    changes: list[GitCommitChange] = []
    all_changes_included: bool = Field(alias="allChangesIncluded", default=True)


class GitCommitSearchCriteria(BaseModel):
    """Search criteria for listing commits in a repository.

    All fields are optional; only non-None values are forwarded as
    ``searchCriteria.*`` query parameters.

    Attributes:
        item_path: Filter to commits that touched this file path.
        item_version: Version string for the item version filter.
        item_version_type: Version type (e.g. ``"commit"``).
        top: Maximum number of commits to return.
    """

    item_path: str | None = Field(default=None, serialization_alias="itemPath")
    item_version: str | None = Field(
        default=None, serialization_alias="itemVersion.version"
    )
    item_version_type: VersionDescriptorType | None = Field(
        default=None, serialization_alias="itemVersion.versionType"
    )
    top: int | None = Field(default=None, serialization_alias="$top")


class _GitCommitSearchResults(BaseModel):
    """Internal: container for commit search results."""

    value: list[GitCommitRef]


class GitRefUpdate(BaseModel):
    """A ref update operation for creating, updating, or deleting a branch or tag."""

    name: str
    new_object_id: CommitId = Field(serialization_alias="newObjectId")
    old_object_id: CommitId = Field(serialization_alias="oldObjectId")


# ---------------------------------------------------------------------------
# Push models
# ---------------------------------------------------------------------------


class GitPushContentType(StrEnum):
    """Content encoding for new file content in a git push."""

    RAWTEXT = "rawtext"
    BASE64ENCODED = "base64encoded"


class GitPushChangeItem(BaseModel):
    """An item path within a push change."""

    path: str


class GitPushNewContent(BaseModel):
    """New file content within a push change."""

    content: str
    content_type: GitPushContentType = Field(
        default=GitPushContentType.RAWTEXT, serialization_alias="contentType"
    )


class GitPushChange(BaseModel):
    """A single file change within a push commit."""

    change_type: GitChangeType = Field(serialization_alias="changeType")
    item: GitPushChangeItem
    new_content: GitPushNewContent | None = Field(
        default=None, serialization_alias="newContent"
    )
    source_server_item: str | None = Field(
        default=None, serialization_alias="sourceServerItem"
    )


class GitPushCommit(BaseModel):
    """A commit payload within a push request."""

    comment: str
    changes: list[GitPushChange]


class GitPushRefUpdate(BaseModel):
    """A ref update entry within a push request.

    Each entry tells ADO which branch (or tag) to advance and from which
    commit it is currently expected to point.  A single push can carry
    multiple entries, allowing several refs to be updated atomically in one
    API call — mirroring native Git push semantics
    (e.g. ``git push origin main feature/foo``).

    Attributes:
        name: Full ref name, e.g. ``"refs/heads/main"``.
        old_object_id: The commit SHA the ref currently points to.  ADO uses
            this as an optimistic-concurrency guard: the push is rejected if
            the ref has moved since you read it.  Use :data:`ZERO_SHA` when
            pushing to a ref that does not yet exist (creating a new branch).
    """

    name: str
    old_object_id: CommitId = Field(serialization_alias="oldObjectId")


class GitPushResult(BaseModel):
    """The result of a successful push operation."""

    push_id: int = Field(alias="pushId")
    commits: list[GitCommitRef]


class GitPushRequest(BaseModel):
    """Request body for ``POST .../pushes``.

    A push bundles two things together:

    * **ref_updates** — which branch/tag pointers to move.  More than one
      entry is allowed; all updates land atomically in a single push event.
    * **commits** — the new commit objects to create.  The same commit(s)
      are applied to every ref listed in *ref_updates*.

    Attributes:
        ref_updates: One entry per ref being updated.  See
            :class:`GitPushRefUpdate` for details.
        commits: Ordered list of commits to include in the push.  Each
            commit carries one or more :class:`GitPushChange` file changes.
    """

    ref_updates: list[GitPushRefUpdate] = Field(serialization_alias="refUpdates")
    commits: list[GitPushCommit]


# ---------------------------------------------------------------------------
# Repository functions
# ---------------------------------------------------------------------------


def iter_repository_details(project_api_call: ApiCall) -> Iterator[RepositoryInfo]:
    """Iterate over the repositories of the project.

    Yields:
        RepositoryInfo objects for each repository in the project.
    """
    response = project_api_call.get(
        "git",
        "repositories",
        version="7.0",
    )
    results = _RepositoryInfoResults.model_validate(response)
    yield from results.value


def get_repository_api_call(
    project_api_call: ApiCall,
    repository_id: RepositoryId,
) -> ApiCall:
    """Get repository API call.

    Returns:
        An ApiCall pointing at the repository resource for the given ID.
    """
    return project_api_call.build_call("git", "repositories", repository_id)


def get_repository_info(repository_api_call: ApiCall) -> RepositoryInfo:
    """Return details for a single repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).

    Returns:
        RepositoryInfo for the repository.
    """
    response = repository_api_call.get(version="7.0")
    return RepositoryInfo.model_validate(response)


def get_repository_item_bytes(
    repository_api_call: ApiCall,
    path: str,
    version_descriptor_version: str,
    version_descriptor_type: VersionDescriptorType,
) -> bytes | None:
    """Fetch the raw bytes of a repository item.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        path: Absolute file path within the repository.
        version_descriptor_version: The version string (commit SHA or branch
            name) passed as ``versionDescriptor.version``.
        version_descriptor_type: The version type passed as
            ``versionDescriptor.versionType``.

    Returns:
        Raw bytes of the file, or ``None`` if the item does not exist.
    """
    try:
        return cast(
            "bytes",
            repository_api_call.get_raw(
                "items",
                parameters={
                    "path": path,
                    "versionDescriptor.version": version_descriptor_version,
                    "versionDescriptor.versionType": version_descriptor_type,
                },
                version="7.1-preview.1",
            ),
        )
    except RuntimeError:
        return None


def get_commit_diff_page(
    repository_api_call: ApiCall,
    base_commit: CommitId,
    target_commit: CommitId,
    *,
    skip: int = 0,
    top: int = 100,
) -> CommitDiffPage:
    """Fetch one page of file changes between two commits.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        base_commit: The base (older) commit SHA.
        target_commit: The target (newer) commit SHA.
        skip: Number of results to skip (for pagination).
        top: Maximum number of results to return per page.

    Returns:
        CommitDiffPage containing the changes and a flag indicating whether
        all changes were returned.
    """
    response = repository_api_call.get(
        "diffs",
        "commits",
        parameters={
            "baseVersionDescriptor.version": base_commit,
            "baseVersionDescriptor.versionType": "commit",
            "targetVersionDescriptor.version": target_commit,
            "targetVersionDescriptor.versionType": "commit",
            "$top": top,
            "$skip": skip,
        },
        version="7.1-preview.1",
    )
    return CommitDiffPage.model_validate(response)


def get_commit_by_id(
    repository_api_call: ApiCall,
    commit_id: CommitId,
) -> GitCommitRef:
    """Return a single commit by its SHA.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        commit_id: Commit SHA string.

    Returns:
        GitCommitRef for the requested commit.
    """
    response = repository_api_call.get("commits", commit_id, version="7.1-preview.1")
    return GitCommitRef.model_validate(response)


def get_repository_commits(
    repository_api_call: ApiCall,
    search_criteria: GitCommitSearchCriteria | None = None,
) -> list[GitCommitRef]:
    """Search commits in a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        search_criteria: Optional search criteria model; only non-None
            fields are forwarded as ``searchCriteria.*`` query parameters.

    Returns:
        List of GitCommitRef objects matching the search criteria.
    """
    criteria_dict = (
        search_criteria.model_dump(mode="json", by_alias=True, exclude_none=True)
        if search_criteria
        else {}
    )
    parameters: dict[str, int | str] = {
        f"searchCriteria.{key}": value for key, value in criteria_dict.items()
    }
    response = repository_api_call.get(
        "commits", parameters=parameters, version="7.1-preview.1"
    )
    return _GitCommitSearchResults.model_validate(response).value


def post_repository_refs(
    repository_api_call: ApiCall,
    ref_updates: list[GitRefUpdate],
) -> None:
    """Apply one or more ref updates (create, update, or delete branches/tags).

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        ref_updates: List of ref updates, each specifying a name and old/new
            object IDs.
    """
    repository_api_call.post(
        "refs",
        version="7.1",
        json=[u.model_dump(mode="json", by_alias=True) for u in ref_updates],
    )


def iter_refs(
    repository_api_call: ApiCall,
    ref_filter: GitRefFilter | None = None,
) -> Iterator[GitRef]:
    """Iterate over git refs in a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        ref_filter: Optional filter model; only non-None fields are forwarded
            as query parameters.

    Yields:
        GitRef for each matching ref.
    """
    parameters = (
        ref_filter.model_dump(mode="json", by_alias=True, exclude_none=True)
        if ref_filter
        else {}
    )
    response = repository_api_call.get(
        "refs",
        parameters=parameters,
        version="7.1-preview.1",
    )
    yield from _GitRefResults.model_validate(response).value


# ---------------------------------------------------------------------------
# Push functions
# ---------------------------------------------------------------------------


def post_push(
    repository_api_call: ApiCall,
    request: GitPushRequest,
) -> GitPushResult:
    """Push one or more commits to a repository.

    Maps directly to ``POST .../pushes`` in the Azure DevOps Git REST API.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        request: Push request specifying the ref updates and commits.

    Returns:
        GitPushResult containing the new push ID and commit references.
    """
    response = repository_api_call.post(
        "pushes",
        version="7.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return GitPushResult.model_validate(response)


# ---------------------------------------------------------------------------
# Git ACL / security functions
# ---------------------------------------------------------------------------


class AccessControlEntry(BaseModel):
    """A single access control entry granting or denying permissions."""

    descriptor: str
    allow: int
    deny: int


class AccessControlList(BaseModel):
    """An access control list for a git security token."""

    token: str
    inheritance_deny: int = Field(alias="inheritanceDeny", default=0)
    entries: dict[str, AccessControlEntry] = {}


class _AccessControlListResults(BaseModel):
    """Internal: container for access control list results."""

    value: list[AccessControlList]


def make_git_acl_token(
    project_id: RepositoryId,
    repo_id: RepositoryId | None = None,
    branch: str | None = None,
) -> str:
    """Build a git ACL token for use with the security accesscontrollists API.

    Token formats:

    * All repositories in a project: ``repoV2/{project_id}``
    * Specific repository: ``repoV2/{project_id}/{repo_id}``
    * Specific branch: ``repoV2/{project_id}/{repo_id}/refs/heads/{encoded}``

    Branch names are encoded with ``/`` → ``^3`` as required by ADO.

    Args:
        project_id: Project UUID.
        repo_id: Repository UUID, or ``None`` for a project-scoped token.
        branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``), or
            ``None``.  The ``refs/heads/`` prefix is stripped before encoding
            when present.

    Returns:
        ACL token string.
    """
    token = f"repoV2/{project_id}"
    if repo_id is None:
        return token
    token = f"{token}/{repo_id}"
    if branch is None:
        return token
    # Strip refs/heads/ prefix if present; ADO adds it back in the token.
    branch_name = (
        branch.removeprefix("refs/heads/")
        if branch.startswith("refs/heads/")
        else branch
    )
    encoded = branch_name.replace("/", "^3")
    return f"{token}/refs/heads/{encoded}"


def get_git_acl(
    org_api_call: ApiCall,
    project_id: RepositoryId,
    repo_id: RepositoryId | None = None,
) -> list[AccessControlList]:
    """Return the access control lists for a git repository or project.

    Args:
        org_api_call: Organisation-level ADO API call (must NOT include a
            project path segment, e.g.
            ``ApiCall(access_token=…, url="https://dev.azure.com/myorg")``).
            The ACL endpoint is org-scoped, not project-scoped.
        project_id: Project UUID.
        repo_id: Repository UUID, or ``None`` to query all repositories in
            the project.

    Returns:
        List of AccessControlList objects for the requested token scope.
    """
    token = make_git_acl_token(project_id, repo_id)
    response = org_api_call.get(
        "_apis",
        "accesscontrollists",
        GIT_SECURITY_NAMESPACE_ID,
        parameters={"token": token},
        version="7.1",
    )
    return _AccessControlListResults.model_validate(response).value


class BranchStatistics(BaseModel):
    """Ahead/behind commit counts for a branch relative to its base version."""

    name: str
    ahead_count: int = Field(alias="aheadCount")
    behind_count: int = Field(alias="behindCount")
    commit: GitCommitRef | None = None


def get_repository_statistics(
    repository_api_call: ApiCall,
    branch: str,
) -> BranchStatistics:
    """Return ahead/behind statistics for a branch.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``).

    Returns:
        BranchStatistics with ahead/behind counts and the branch HEAD commit.
    """
    response = repository_api_call.get(
        "stats",
        "branches",
        parameters={"name": branch},
        version="7.1",
    )
    return BranchStatistics.model_validate(response)


def make_ref_update(branch: str, old_commit: CommitId) -> GitPushRefUpdate:
    """Return a ref-update entry for a branch.

    A ``refs/heads/`` prefix is added automatically when absent.  Pass
    :data:`ZERO_SHA` as *old_commit* when pushing to a
    branch that does not yet exist.

    Args:
        branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``).
        old_commit: Current HEAD SHA of the branch.
    """
    full_name = branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"
    return GitPushRefUpdate(name=full_name, old_object_id=old_commit)
