"""Azure DevOps Git repository, commit, ref, diff, and push API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt

from pyado.raw._core import ADOUrl, ApiCall
from pyado.raw.project import ProjectInfo
from pyado.raw.work_item import WorkItemRef

__all__ = [
    "ZERO_SHA",
    "BranchName",
    "CommitDiffPage",
    "CommitId",
    "GitCommitChange",
    "GitCommitChangeItem",
    "GitCommitRef",
    "GitPushChange",
    "GitPushChangeItem",
    "GitPushChangeType",
    "GitPushCommit",
    "GitPushNewContent",
    "GitPushRefUpdate",
    "GitPushRequest",
    "GitPushResult",
    "GitRef",
    "GitRefUpdate",
    "GitStatus",
    "PullRequestStatusContext",
    "RepositoryId",
    "RepositoryInfo",
    "RepositoryName",
    "SshUrl",
    "get_commit_diff_page",
    "get_repository_api_call",
    "get_repository_commits",
    "get_repository_item_bytes",
    "iter_refs",
    "iter_repository_details",
    "make_ref_update",
    "post_push",
    "post_repository_refs",
]

RepositoryName = str
BranchName = str
RepositoryId = UUID
CommitId = str
SshUrl = str

ZERO_SHA: CommitId = "0000000000000000000000000000000000000000"


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


class GitCommitChangeItem(BaseModel):
    """The item (file or folder) affected by a single commit change."""

    path: str
    is_folder: bool = Field(alias="isFolder", default=False)


class GitCommitChange(BaseModel):
    """A single change entry in a commit diff."""

    change_type: str = Field(alias="changeType")
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
    state: str
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


class _GitRefResults(BaseModel):
    """Internal: container for git ref list results."""

    value: list[GitRef]


class CommitDiffPage(BaseModel):
    """One page of results from the diffs/commits endpoint."""

    changes: list[GitCommitChange] = []
    all_changes_included: bool = Field(alias="allChangesIncluded", default=True)


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

GitPushChangeType = Literal["add", "edit", "delete", "rename"]


class GitPushChangeItem(BaseModel):
    """An item path within a push change."""

    path: str


class GitPushNewContent(BaseModel):
    """New file content within a push change."""

    content: str
    content_type: Literal["rawtext", "base64encoded"] = Field(
        default="rawtext", serialization_alias="contentType"
    )


class GitPushChange(BaseModel):
    """A single file change within a push commit."""

    change_type: GitPushChangeType = Field(serialization_alias="changeType")
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
    """A ref update payload within a push request."""

    name: str
    old_object_id: CommitId = Field(serialization_alias="oldObjectId")


class GitPushResult(BaseModel):
    """The result of a successful push operation."""

    push_id: int = Field(alias="pushId")
    commits: list[GitCommitRef]


class GitPushRequest(BaseModel):
    """Request body for pushing commits to a repository."""

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


def get_repository_item_bytes(
    repository_api_call: ApiCall,
    path: str,
    version_descriptor_version: str,
    version_descriptor_type: str,
) -> bytes | None:
    """Fetch the raw bytes of a repository item.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        path: Absolute file path within the repository.
        version_descriptor_version: The version string (commit SHA or branch
            name) passed as ``versionDescriptor.version``.
        version_descriptor_type: The version type string passed as
            ``versionDescriptor.versionType`` (e.g. ``"commit"`` or
            ``"branch"``).

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


def get_repository_commits(
    repository_api_call: ApiCall,
    *,
    item_path: str | None = None,
    item_version: str | None = None,
    item_version_type: str | None = None,
    top: int | None = None,
) -> list[GitCommitRef]:
    """Search commits in a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        item_path: Filter to commits that touched this file path.
        item_version: Version string for the item version filter.
        item_version_type: Version type for the item version filter
            (e.g. ``"commit"``).
        top: Maximum number of commits to return.

    Returns:
        List of GitCommitRef objects matching the search criteria.
    """
    parameters: dict[str, int | str] = {}
    if item_path is not None:
        parameters["searchCriteria.itemPath"] = item_path
    if item_version is not None:
        parameters["searchCriteria.itemVersion.version"] = item_version
    if item_version_type is not None:
        parameters["searchCriteria.itemVersion.versionType"] = item_version_type
    if top is not None:
        parameters["searchCriteria.$top"] = top
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
    *,
    name_filter: str | None = None,
    name_contains: str | None = None,
) -> Iterator[GitRef]:
    """Iterate over git refs in a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        name_filter: Prefix filter applied by ADO, e.g. ``"heads/main"`` to
            match exactly ``refs/heads/main`` (ADO strips the ``refs/`` prefix
            before matching).
        name_contains: Substring filter applied to the full ref name.

    Yields:
        GitRef for each matching ref.
    """
    parameters: dict[str, int | str | bool] = {}
    if name_filter is not None:
        parameters["filter"] = name_filter
    if name_contains is not None:
        parameters["filterContains"] = name_contains
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
