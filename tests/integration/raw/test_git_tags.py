"""Integration tests for git tag write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from tests.integration.raw._support import console


def test_git_tags_write(
    project_api_call: raw.ApiCall,
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
    rng: random.Random,
) -> None:
    """Create and delete lightweight and annotated tags."""
    repo, repo_api_call, commits = git_read
    del project_api_call
    console.print("\n=== GIT EXTRAS (write) ===")
    if repo is None or repo_api_call is None or not commits:
        return

    tag_name = f"smoke-tag-{rng.randint(10000, 99999)}"
    head_sha = commits[0].commit_id
    raw.post_tag(repo_api_call, tag_name, head_sha)
    raw.delete_git_tag(repo_api_call, tag_name, head_sha)
    annotated_name = f"smoke-atag-{rng.randint(10000, 99999)}"
    atag = raw.post_annotated_tag(
        repo_api_call,
        raw.AnnotatedTagRequest.from_commit(
            annotated_name, head_sha, "pyado smoke test annotated tag"
        ),
    )
    if atag:
        raw.get_annotated_tag(repo_api_call, atag.object_id)
        # Clean up the annotated tag ref using delete_git_tag (zeroes the ref).
        raw.delete_git_tag(repo_api_call, annotated_name, head_sha)
