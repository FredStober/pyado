"""Low-level models and high-level helpers for Git push operations.

Low-level models (``GitPushChange``, ``GitPushCommit``, ``GitPushRefUpdate``,
``GitPushResult``, …) mirror the Azure DevOps ``POST .../pushes`` request and
response body directly.

High-level helpers (``add_file``, ``edit_file``, ``delete_file``,
``rename_file``, ``make_commit``, ``make_ref_update``) construct those models
from simple arguments for the common cases.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from pyado.api_call import ApiCall
from pyado.repository import ZERO_SHA, CommitId, GitCommitRef  # noqa: F401

GitPushChangeType: TypeAlias = Literal["add", "edit", "delete", "rename"]


# ---------------------------------------------------------------------------
# Low-level models — mirror the REST API payload
# ---------------------------------------------------------------------------


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


class _GitPushPayload(BaseModel):
    """Internal: top-level push request body."""

    ref_updates: list[GitPushRefUpdate] = Field(serialization_alias="refUpdates")
    commits: list[GitPushCommit]


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------


def add_file(path: str, content: str) -> GitPushChange:
    """Return a change that creates a new file.

    Args:
        path: Repository-root-relative path (e.g. ``"/src/foo.py"``).
        content: UTF-8 text content for the new file.
    """
    return GitPushChange(
        change_type="add",
        item=GitPushChangeItem(path=path),
        new_content=GitPushNewContent(content=content),
    )


def edit_file(path: str, content: str) -> GitPushChange:
    """Return a change that overwrites an existing file.

    Args:
        path: Repository-root-relative path of the file to update.
        content: New UTF-8 text content.
    """
    return GitPushChange(
        change_type="edit",
        item=GitPushChangeItem(path=path),
        new_content=GitPushNewContent(content=content),
    )


def delete_file(path: str) -> GitPushChange:
    """Return a change that deletes an existing file.

    Args:
        path: Repository-root-relative path of the file to delete.
    """
    return GitPushChange(
        change_type="delete",
        item=GitPushChangeItem(path=path),
    )


def rename_file(old_path: str, new_path: str) -> GitPushChange:
    """Return a change that renames (moves) a file without altering its content.

    Args:
        old_path: Current repository-root-relative path of the file.
        new_path: Desired repository-root-relative path after the rename.
    """
    return GitPushChange(
        change_type="rename",
        item=GitPushChangeItem(path=new_path),
        source_server_item=old_path,
    )


def make_commit(message: str, changes: list[GitPushChange]) -> GitPushCommit:
    """Return a commit payload from a message and a list of changes.

    Args:
        message: Commit message.
        changes: One or more file changes to include in this commit.
    """
    return GitPushCommit(comment=message, changes=changes)


def make_ref_update(branch: str, old_commit: CommitId) -> GitPushRefUpdate:
    """Return a ref-update entry for a branch.

    A ``refs/heads/`` prefix is added automatically when absent.  Pass
    :data:`~pyado.repository.ZERO_SHA` as *old_commit* when pushing to a
    branch that does not yet exist.

    Args:
        branch: Branch name (e.g. ``"main"`` or ``"refs/heads/main"``).
        old_commit: Current HEAD SHA of the branch.
    """
    full_name = branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"
    return GitPushRefUpdate(name=full_name, old_object_id=old_commit)


# ---------------------------------------------------------------------------
# API function
# ---------------------------------------------------------------------------


def push(
    repository_api_call: ApiCall,
    ref_updates: list[GitPushRefUpdate],
    commits: list[GitPushCommit],
) -> GitPushResult:
    """Push one or more commits to a repository.

    Maps directly to ``POST .../pushes`` in the Azure DevOps Git REST API.

    Args:
        repository_api_call: Repository-level ADO API call (from
            :func:`~pyado.repository.get_repository_api_call`).
        ref_updates: One entry per branch being updated.  Use
            :data:`~pyado.repository.ZERO_SHA` as ``old_object_id`` when
            creating a new branch.  Branch names must be full refs
            (e.g. ``"refs/heads/main"``); use :func:`make_ref_update` to
            build them from short names.
        commits: Commits to include in the push, each carrying one or more
            :class:`GitPushChange` entries.

    Returns:
        GitPushResult containing the new push ID and commit references.
    """
    payload = _GitPushPayload(ref_updates=ref_updates, commits=commits)
    response = repository_api_call.post(
        "pushes",
        version="7.1",
        json=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return GitPushResult.model_validate(response)
