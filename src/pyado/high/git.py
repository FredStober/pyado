"""Higher-level wrappers for Git repository operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado.raw import (
    ZERO_SHA,
    ApiCall,
    BranchName,
    CommitDiffPage,
    CommitId,
    GitCommitChange,
    GitPushChange,
    GitPushChangeItem,
    GitPushCommit,
    GitPushNewContent,
    GitPushRefUpdate,
    GitPushRequest,
    GitPushResult,
    GitRefUpdate,
    get_commit_diff_page,
    get_repository_commits,
    get_repository_item_bytes,
    iter_refs,
    post_push,
    post_repository_refs,
)

__all__ = [
    "add_file",
    "create_branch",
    "create_ref_update",
    "delete_branch",
    "delete_file",
    "edit_file",
    "get_file_content_at_branch",
    "get_file_content_at_commit",
    "get_last_commit_touching_file",
    "iter_commit_diff",
    "make_commit",
    "push_commits",
    "rename_file",
]


def _full_ref(branch: str) -> str:
    return branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"


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


def create_ref_update(
    repository_api_call: ApiCall,
    branch: BranchName,
) -> GitPushRefUpdate:
    """Return a ref-update entry for a branch, fetching its current SHA.

    Looks up the current HEAD commit of *branch* via the refs endpoint and
    returns a :class:`~pyado.raw.GitPushRefUpdate` ready to pass to
    :func:`push_commits`.

    Args:
        repository_api_call: Repository-level ADO API call (from
            :func:`~pyado.raw.get_repository_api_call`).
        branch: Short branch name (e.g. ``"main"``).  A ``refs/heads/``
            prefix is added automatically if absent.

    Returns:
        GitPushRefUpdate with the branch's current commit SHA as
        ``old_object_id``.  Raises ``StopIteration`` if no ref
        matching *branch* is found.
    """
    full_name = _full_ref(branch)
    name_filter = full_name.removeprefix("refs/")
    ref = next(iter_refs(repository_api_call, name_filter=name_filter))
    return GitPushRefUpdate(name=full_name, old_object_id=ref.object_id)


def push_commits(
    repository_api_call: ApiCall,
    ref_updates: list[GitPushRefUpdate],
    commits: list[GitPushCommit],
) -> GitPushResult:
    """Push one or more commits to a repository.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        ref_updates: One entry per branch being updated. Use
            :data:`ZERO_SHA` as ``old_object_id`` when creating a new branch.
            Branch names must be full refs (e.g. ``"refs/heads/main"``); use
            ``make_ref_update`` to build them from short names.
        commits: Commits to include in the push, each carrying one or more
            ``GitPushChange`` entries.

    Returns:
        GitPushResult containing the new push ID and commit references.
    """
    return post_push(
        repository_api_call,
        GitPushRequest(ref_updates=ref_updates, commits=commits),
    )


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
        path: Absolute file path within the repository (e.g. ``/src/foo.py``).
        commit_sha: Commit SHA to resolve the file at.

    Returns:
        File content as a UTF-8 string, or ``""`` if the file is not found.
    """
    raw = get_repository_item_bytes(repository_api_call, path, commit_sha, "commit")
    return raw.decode("utf-8") if raw else ""


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
    raw = get_repository_item_bytes(repository_api_call, path, short_name, "branch")
    return raw.decode("utf-8") if raw else ""


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
        page: CommitDiffPage = get_commit_diff_page(
            repository_api_call, base_commit, target_commit, skip=skip
        )
        total_in_page = len(page.changes)
        yield from (c for c in page.changes if not c.item.is_folder)
        if page.all_changes_included or not page.changes:
            break
        skip += total_in_page


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
        commits = get_repository_commits(
            repository_api_call,
            item_path=path,
            item_version=before_commit,
            item_version_type="commit",
            top=1,
        )
    except RuntimeError:
        return before_commit
    return commits[0].commit_id if commits else before_commit


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
    post_repository_refs(
        repository_api_call,
        [
            GitRefUpdate(
                name=_full_ref(branch_name),
                new_object_id=from_commit,
                old_object_id=ZERO_SHA,
            )
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
    post_repository_refs(
        repository_api_call,
        [
            GitRefUpdate(
                name=_full_ref(branch_name),
                new_object_id=ZERO_SHA,
                old_object_id=current_commit,
            )
        ],
    )
