"""Integration tests for git repository extras (statistics, items, ACL)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from tests.integration.raw._support import console


def test_git_extras_read(
    project_api_call: raw.ApiCall,
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
    rng: random.Random,
) -> None:
    """Fetch repository info, statistics, items, tags, and ACL."""
    repo, repo_api_call, commits = git_read
    del project_api_call, rng
    console.print("\n=== GIT EXTRAS (read) ===")
    if repo is None or repo_api_call is None:
        return

    raw.get_repository_info(repo_api_call)

    short_branch = (repo.default_branch or "refs/heads/main").removeprefix(
        "refs/heads/"
    )
    raw.get_repository_statistics(repo_api_call, short_branch)

    # iter/list_repository_items — root listing (default one-level), then
    # a branch-scoped call
    items = list(raw.iter_repository_items(repo_api_call))
    assert items == raw.list_repository_items(repo_api_call)
    raw.list_repository_items(
        repo_api_call, branch=short_branch, recursion_level=raw.RecursionLevel.ONE_LEVEL
    )

    tags = list(raw.iter_tags(repo_api_call))
    assert tags == raw.list_tags(repo_api_call)

    if commits:
        raw.get_commit_by_id(repo_api_call, commits[0].commit_id)

    # ACL — get_git_acl needs an org-level ApiCall (no /_apis, no project segment)
    # repo_api_call.url is like https://dev.azure.com/{org}/{project}/_apis/git/...
    # Split at /_apis to get {org}/{project}, then strip the project segment.
    proj_with_org = repo_api_call.url.unicode_string().split("/_apis")[0]
    org_base = proj_with_org.rsplit("/", 1)[0]
    org_base_api_call = raw.ApiCall(
        session=repo_api_call.session,
        url=org_base,
    )
    raw.make_git_acl_token(repo.project.id)
    raw.make_git_acl_token(repo.project.id, repo.id)
    raw.get_git_acl(org_base_api_call, repo.project.id)
    raw.get_git_acl(org_base_api_call, repo.project.id, repo.id)

    # Commit.iter_changes
    if commits:
        _ = None
