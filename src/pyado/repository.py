"""Module to interact with Azure DevOps repositories."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt

from pyado.api_call import ADOUrl, ApiCall
from pyado.project import ProjectInfo

RepositoryName: TypeAlias = str
BranchName: TypeAlias = str
RepositoryId: TypeAlias = UUID
CommitId: TypeAlias = str
SshUrl: TypeAlias = str

ZERO_SHA: CommitId = "0000000000000000000000000000000000000000"


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


class _RepositoryInfoResults(BaseModel):
    """Type to read repository details results."""

    value: list[RepositoryInfo]


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


def get_file_content_at_commit(
    repository_api_call: ApiCall,
    path: str,
    commit_sha: CommitId,
) -> str:
    """Return the raw text content of a file at a specific commit.

    Returns an empty string when the file does not exist at that commit.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        path: Absolute file path within the repository (e.g. /src/foo.py).
        commit_sha: Commit SHA to resolve the file at.

    Returns:
        File content as a UTF-8 string, or "" if the file is not found.
    """
    try:
        raw = repository_api_call.get_raw(
            "items",
            parameters={
                "path": path,
                "versionDescriptor.version": commit_sha,
                "versionDescriptor.versionType": "commit",
            },
            version="7.1-preview.1",
        )
    except RuntimeError:
        return ""
    return raw.decode("utf-8") if raw else ""


class GitCommitChangeItem(BaseModel):
    """The item (file or folder) affected by a single commit change."""

    path: str
    is_folder: bool = Field(alias="isFolder", default=False)


class GitCommitChange(BaseModel):
    """A single change entry in a commit diff."""

    change_type: str = Field(alias="changeType")
    item: GitCommitChangeItem


class _CommitDiffResults(BaseModel):
    """Internal: response model for the diffs/commits endpoint."""

    changes: list[GitCommitChange] = []
    all_changes_included: bool = Field(alias="allChangesIncluded", default=True)


def iter_commit_diff(
    repository_api_call: ApiCall,
    base_commit: CommitId,
    target_commit: CommitId,
) -> Iterator[GitCommitChange]:
    """Iterate over file changes between two commits (base → target).

    Paginates automatically when the API returns partial results.
    Folder entries are excluded from the results.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        base_commit: The base (older) commit SHA.
        target_commit: The target (newer) commit SHA.

    Yields:
        GitCommitChange for each changed file.
    """
    skip = 0
    while True:
        response = repository_api_call.get(
            "diffs",
            "commits",
            parameters={
                "baseVersionDescriptor.version": base_commit,
                "baseVersionDescriptor.versionType": "commit",
                "targetVersionDescriptor.version": target_commit,
                "targetVersionDescriptor.versionType": "commit",
                "$top": 100,
                "$skip": skip,
            },
            version="7.1-preview.1",
        )
        results = _CommitDiffResults.model_validate(response)
        total_in_page = len(results.changes)
        yield from (c for c in results.changes if not c.item.is_folder)
        if results.all_changes_included or not results.changes:
            break
        skip += total_in_page


class GitCommitRef(BaseModel):
    """A minimal git commit reference."""

    commit_id: CommitId = Field(alias="commitId")


class _GitCommitSearchResults(BaseModel):
    """Internal: container for commit search results."""

    value: list[GitCommitRef]


def get_last_commit_touching_file(
    repository_api_call: ApiCall,
    path: str,
    before_commit: CommitId,
) -> CommitId:
    """Return the most recent commit that touched a file, at or before a given commit.

    Falls back to returning *before_commit* when no commit is found.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        path: Absolute file path within the repository.
        before_commit: The commit SHA to search at or before.

    Returns:
        Commit SHA of the most recent touching commit, or before_commit.
    """
    try:
        response = repository_api_call.get(
            "commits",
            parameters={
                "searchCriteria.itemPath": path,
                "searchCriteria.itemVersion.version": before_commit,
                "searchCriteria.itemVersion.versionType": "commit",
                "searchCriteria.$top": 1,
            },
            version="7.1-preview.1",
        )
    except RuntimeError:
        return before_commit
    results = _GitCommitSearchResults.model_validate(response)
    if results.value:
        return results.value[0].commit_id
    return before_commit


class GitRef(BaseModel):
    """A git ref (branch or tag) entry returned by the refs endpoint."""

    name: str
    object_id: CommitId = Field(alias="objectId")


class _GitRefResults(BaseModel):
    """Internal: container for git ref list results."""

    value: list[GitRef]


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


def create_branch(
    repository_api_call: ApiCall,
    branch_name: BranchName,
    from_commit: CommitId,
) -> None:
    """Create a new branch pointing at an existing commit.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        branch_name: Short branch name (e.g. ``"feature/my-branch"``).
            A ``refs/heads/`` prefix is added automatically if absent.
        from_commit: Commit SHA the new branch should point at.
    """
    full_name = (
        branch_name
        if branch_name.startswith("refs/heads/")
        else f"refs/heads/{branch_name}"
    )
    repository_api_call.post(
        "refs",
        version="7.1",
        json=[
            {
                "name": full_name,
                "newObjectId": from_commit,
                "oldObjectId": ZERO_SHA,
            }
        ],
    )


def delete_branch(
    repository_api_call: ApiCall,
    branch_name: BranchName,
    current_commit: CommitId,
) -> None:
    """Delete a branch from a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        branch_name: Short branch name or full ``refs/heads/…`` name.
        current_commit: Current HEAD SHA of the branch (used as the old object
            ID for the optimistic-concurrency check).
    """
    full_name = (
        branch_name
        if branch_name.startswith("refs/heads/")
        else f"refs/heads/{branch_name}"
    )
    repository_api_call.post(
        "refs",
        version="7.1",
        json=[
            {
                "name": full_name,
                "newObjectId": ZERO_SHA,
                "oldObjectId": current_commit,
            }
        ],
    )


def get_file_content_at_branch(
    repository_api_call: ApiCall,
    path: str,
    branch_name: BranchName,
) -> str:
    """Return the raw text content of a file from the tip of a branch.

    Returns an empty string when the file does not exist on the branch.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        path: Absolute file path within the repository (e.g. ``/config/x.json``).
        branch_name: Short branch name (e.g. ``"main"``).  A ``refs/heads/``
            prefix is stripped automatically.

    Returns:
        File content as a UTF-8 string, or ``""`` if the file is not found.
    """
    short_name = branch_name.removeprefix("refs/heads/")
    try:
        raw = repository_api_call.get_raw(
            "items",
            parameters={
                "path": path,
                "versionDescriptor.version": short_name,
                "versionDescriptor.versionType": "branch",
            },
            version="7.1",
        )
    except RuntimeError:
        return ""
    return raw.decode("utf-8") if raw else ""
