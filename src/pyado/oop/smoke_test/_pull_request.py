"""Smoke tests for PullRequest (read and pr.complete write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import AddFile, Project, PullRequest, Repository
from pyado.oop.smoke_test._runner import _skip, _take, console, run
from pyado.raw import (
    PullRequestCompletionOptions,
    PullRequestStatus,
)


def _test_pr_read(proj: Project, repo: Repository) -> PullRequest | None:
    del proj
    console.print("\n=== PullRequest (read, existing) ===")
    prs = _take(repo.iter_pull_requests(status=PullRequestStatus.COMPLETED), 1)
    if not prs:
        prs = _take(repo.iter_pull_requests(status=PullRequestStatus.ABANDONED), 1)
    if not prs:
        _skip("pr read tests", "no existing PRs in repo")
        return None

    pr: PullRequest = prs[0]

    run("pr.id", lambda: pr.id)
    run("pr.title", lambda: pr.title)
    run("pr.status", lambda: pr.status)
    run("pr.source_branch", lambda: pr.source_branch)
    run("pr.target_branch", lambda: pr.target_branch)
    run("pr.description", lambda: pr.description)
    run("pr.created_by", lambda: pr.created_by)
    run("pr.info", lambda: pr.info)
    run("pr.api_call", lambda: pr.api_call)
    run("pr.repo (back-nav)", lambda: pr.repo)
    run("pr.project (back-nav)", lambda: pr.project)
    run("pr.org (back-nav)", lambda: pr.org)
    run("pr.refresh()", pr.refresh)
    run("pr.get_tags()", pr.get_tags)
    run("pr.iter_threads()", lambda: _take(pr.iter_threads(), 5))
    run("pr.list_threads()", pr.list_threads)
    run("pr.get_reviewers()", pr.get_reviewers)
    run("pr.iter_commits()", lambda: _take(pr.iter_commits(), 5))
    run("pr.list_commits()", pr.list_commits)
    run("pr.iter_work_item_ids()", lambda: _take(pr.iter_work_item_ids(), 5))
    run("pr.list_work_item_ids()", pr.list_work_item_ids)
    run("pr.list_work_items()", pr.list_work_items)
    run("pr.iter_iterations()", lambda: _take(pr.iter_iterations(), 5))
    run("pr.list_iterations()", pr.list_iterations)
    iterations = list(pr.iter_iterations())
    if iterations:
        run(
            "pr.get_iteration_changes(1)",
            lambda: pr.get_iteration_changes(iterations[0].id),
        )
    run("pr.iter_statuses()", lambda: _take(pr.iter_statuses(), 5))
    run("pr.list_statuses()", pr.list_statuses)
    run("pr.get_tag_details()", pr.get_tag_details)
    run("pr.iter_files_changed()", lambda: _take(pr.iter_files_changed(), 5))
    run("pr.list_files_changed()", pr.list_files_changed)
    threads = list(pr.iter_threads())
    if threads:
        run(
            "pr.get_thread(id)",
            lambda tid=threads[0].id: pr.get_thread(tid),
        )

    # repo.get_pull_request(id) round-trip
    run("repo.get_pull_request(id)", lambda pr_id=pr.id: repo.get_pull_request(pr_id))

    return pr


def _test_write_pr_complete(proj: Project, repo: Repository) -> None:
    """Create a branch, push a file, open a PR, then complete (squash-merge) it."""
    del proj
    console.print("\n=== PullRequest.complete() (write) ===")

    if repo.default_branch is None:
        _skip("pr.complete()", "repo has no default branch")
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        _skip("pr.complete()", "repo has no commits")
        return

    head_sha = head_commits[0].sha
    branch_name = f"oop-smoke-merge-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_branch() [for complete]",
        lambda: repo.create_branch(branch_name, head_sha),
    )

    file_path = f"/oop_smoke_merge_{uuid.uuid4().hex[:10]}.txt"
    push_result = run(
        "repo.commit(branch, msg) [for complete]",
        lambda: repo.commit(
            branch_name,
            "oop-smoke: pr.complete test",
            [AddFile(file_path, "pr.complete smoke test\n")],
        ),
    )
    if push_result is None:
        run(
            "repo.delete_branch() [for complete cleanup]",
            lambda: repo.delete_branch(branch_name, head_sha),
        )
        return

    new_sha = push_result.commits[0].commit_id if push_result.commits else head_sha
    target = repo.default_branch.removeprefix("refs/heads/")
    pr: PullRequest | None = run(
        "repo.create_pull_request() [for complete]",
        lambda: repo.create_pull_request(
            f"[oop-smoke] pr.complete test {uuid.uuid4().hex[:6]}",
            branch_name,
            target,
            description="Created by smoke_test_oop.py — safe to squash-merge.",
        ),
    )
    if pr is None:
        run(
            "repo.delete_branch() [for complete cleanup]",
            lambda: repo.delete_branch(branch_name, new_sha),
        )
        return

    pr_sha = (
        pr.info.last_merge_source_commit.commit_id
        if pr.info.last_merge_source_commit
        else new_sha
    )
    run(
        "pr.complete(last_merge_source_commit)",
        lambda sha=pr_sha: pr.complete(
            sha,
            completion_options=PullRequestCompletionOptions(squash_merge=True),
        ),
    )
