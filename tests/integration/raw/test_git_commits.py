"""Integration tests for git commit read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_git_commits(
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
) -> None:
    """Verify commit listing and diff page covered by the git_read fixture.

    The git_read session fixture calls _test_git_read which covers
    get_repository_commits with multiple criteria, get_commit_diff_page,
    get_repository_item, and get_repository_item_bytes.
    """
