"""Integration tests for git repository, ref, and commit read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_git_read(
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
) -> None:
    """List repositories, refs, and commits.

    The git_read session fixture calls _test_git_read which covers:
    list_repository_details, list_refs (with multiple filters),
    get_repository_commits (with multiple criteria), get_repository_item_bytes,
    get_repository_item, and get_commit_diff_page.
    """
