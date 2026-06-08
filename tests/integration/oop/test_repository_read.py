"""Integration tests for Repository OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado.oop import (
    AddFile,
    Branch,
    Commit,
    DeleteFile,
    EditFile,
    Project,
    ProjectRepos,
    RenameFile,
    Repository,
    Tag,
)
from pyado.raw import PullRequestStatus
from tests.integration.raw._support import _take, console


def _read_commits(repo: Repository, commits: list[Commit]) -> None:
    """Exercise commit-related read methods."""
    head_commit = commits[0]
    repo.get_commit(head_commit.sha)
    _ = head_commit.sha
    _ = head_commit.message
    _ = head_commit.author_name
    _ = head_commit.author_email
    _ = head_commit.author_date
    _ = head_commit.committer_name
    _ = head_commit.committer_email
    _ = head_commit.committer_date
    _ = head_commit.info
    _ = head_commit.repo
    _ = head_commit.project
    _ = head_commit.org

    if len(commits) >= 2:
        _take(repo.iter_commit_diff(commits[-1].sha, commits[0].sha), 10)
        repo.list_commit_diff(commits[-1].sha, commits[0].sha)
    repo.get_last_commit_touching_file("/", head_commit.sha)


def _read_files(repo: Repository, commits: list[Commit], branch: str | None) -> None:
    """Exercise file and branch-scoped read methods."""
    if not branch:
        return
    list(repo.iter_commits(branch=branch, top=3))
    # A3 — branch head / exists
    repo.get_branch_head(branch)
    repo.check_branch_exists(branch)
    if commits:
        repo.get_file_by_branch("/README.md", branch)
        repo.get_file_bytes_by_branch("/README.md", branch)
        repo.get_file_by_commit("/README.md", commits[0].sha)
        repo.get_file_bytes_by_commit("/README.md", commits[0].sha)
        repo.get_statistics(branch)
        # A5 — get_item_by_* / iter_items_by_*
        repo.get_item_by_branch("/README.md", branch)
        repo.get_item_by_commit("/README.md", commits[0].sha)
        list(repo.iter_items_by_commit(commit=commits[0].sha))
        repo.list_items_by_commit(commit=commits[0].sha)
        # A6 — check_file_exists_by_*
        repo.check_file_exists_by_branch("/README.md", branch)
        repo.check_file_exists_by_commit("/README.md", commits[0].sha)
    # iter_items_by_tag, get_item_by_tag (coverage-only; may return empty)
    tags = list(repo.iter_tags())
    if tags:
        tag_ref = tags[0].name.removeprefix("refs/tags/")
        list(repo.iter_items_by_tag(tag=tag_ref))
        repo.list_items_by_tag(tag=tag_ref)
        repo.get_item_by_tag("/README.md", tag_ref)
        repo.check_file_exists_by_tag("/README.md", tag_ref)
    # iter_items_by_ref, get_item_by_ref, check_file_exists_by_ref (PR merge ref)
    active_prs = list(
        _take(repo.iter_pull_requests(status=PullRequestStatus.ACTIVE), 1)
    )
    if active_prs:
        pr_ref = f"refs/pull/{active_prs[0].id}/merge"
        list(repo.iter_items_by_ref(ref=pr_ref))
        repo.list_items_by_ref(ref=pr_ref)
        repo.get_item_by_ref("/README.md", pr_ref)
        repo.check_file_exists_by_ref("/README.md", pr_ref)
    # iter_commits_by_commit / iter_commits_by_tag
    if commits:
        list(repo.iter_commits_by_commit(commits[0].sha))
        repo.list_commits_by_commit(commits[0].sha)
    if tags:
        tag_ref = tags[0].name.removeprefix("refs/tags/")
        list(repo.iter_commits_by_tag(tag_ref))
        repo.list_commits_by_tag(tag_ref)


def _read_commit_extras(repo: Repository, commits: list[Commit]) -> None:
    """Exercise commit.get_statuses, iter_changes and get_pr_for_commit."""
    repo.get_pr_for_commit(commits[0].sha)
    commit_obj = repo.get_commit(commits[0].sha)
    if commit_obj:
        commit_obj.get_statuses()
        changes = list(_take(commit_obj.iter_changes(), 5))
        _take(commit_obj.iter_changes(), 5)
        commit_obj.list_changes()
        if changes and changes[0].item and changes[0].item.path:
            commit_obj.get_file(changes[0].item.path)


def _read_prs(repo: Repository, branch: str | None) -> None:
    """Exercise PR read methods on the repository."""
    _take(repo.iter_pull_requests(status=PullRequestStatus.ACTIVE), 3)
    _take(repo.iter_pull_requests(status=PullRequestStatus.COMPLETED), 5)
    repo.list_pull_requests()
    repo.get_pr_for_branch(branch) if branch else None


def test_repository_read(proj: Project, rng: random.Random) -> None:
    """Exercise Repository properties, commits, files, refs, and PR listing."""
    del rng
    console.print("\n=== Repository (read) ===")
    project_repos: ProjectRepos = proj.repos
    repos = list(project_repos.iter_repositories())
    if not repos:
        return

    repo: Repository = repos[0]
    project_repos.get_repository(repo.name)

    # Properties
    _ = repo.id
    _ = repo.name
    _ = repo.default_branch
    _ = repo.web_url
    _ = repo.info
    _ = repo.api_call
    _ = repo.project
    _ = repo.org
    repo.refresh()

    # File-change to_git_change helpers (pure in-memory, no API call)
    AddFile("/smoke.txt", "x").to_git_change()
    EditFile("/smoke.txt", "y").to_git_change()
    DeleteFile("/smoke.txt").to_git_change()
    RenameFile("/smoke.txt", "/smoke2.txt").to_git_change()

    # Refs
    _take(repo.iter_refs(), 5)
    repo.list_refs()
    _take(repo.iter_refs(name_filter="heads/main"), 3)
    _take(repo.iter_refs(name_contains="main"), 3)

    # Commits
    commits = list(repo.iter_commits(top=5))
    repo.list_commits(top=5)
    if commits:
        _read_commits(repo, commits)

    # Branch filtering
    branch = None
    if repo.default_branch:
        short = repo.default_branch.removeprefix("refs/heads/")
        branch = short
        _read_files(repo, commits or [], branch)

    # ACL
    repo.get_acl()

    # Additional read methods
    _take(repo.iter_branches(), 5)
    repo.list_branches()
    repo.list_tags()
    repo.get_default_branch_commit()
    _take(repo.iter_items(), 5)
    repo.list_items()

    if commits:
        _read_commit_extras(repo, commits)

    _read_prs(repo, branch)


def test_branch_and_tag(proj: Project, repo: Repository | None) -> None:
    """Exercise Branch and Tag OOP classes."""
    if repo is None:
        return
    console.print("\n=== Branch and Tag (read) ===")

    branches = _take(proj.repos.iter_branches(repo.name), 3)
    if branches:
        branch: Branch = branches[0]
        _ = branch.name
        _ = branch.full_name
        _ = branch.commit_id
        _ = branch.ref
        _ = branch.repo
        branch.get_commit()

    tags = _take(proj.repos.iter_tags(repo.name), 3)
    if tags:
        tag: Tag = tags[0]
        _ = tag.name
        _ = tag.full_name
        _ = tag.commit_id
        _ = tag.ref
        _ = tag.repo
        tag.get_commit()
