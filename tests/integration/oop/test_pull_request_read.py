"""Integration tests for PullRequest OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project, PullRequest, Repository
from pyado.raw import PullRequestStatus
from tests.integration.raw._support import _take, console


def test_pr_read(proj: Project, repo: Repository | None) -> None:
    """Exercise PullRequest read properties, threads, commits, iterations, statuses."""
    if repo is None:
        return
    del proj
    console.print("\n=== PullRequest (read, existing) ===")
    prs = _take(repo.iter_pull_requests(status=PullRequestStatus.COMPLETED), 1)
    if not prs:
        prs = _take(repo.iter_pull_requests(status=PullRequestStatus.ABANDONED), 1)
    if not prs:
        return

    pr: PullRequest = prs[0]

    _ = pr.id
    _ = pr.title
    _ = pr.status
    _ = pr.source_branch
    _ = pr.target_branch
    _ = pr.description
    _ = pr.created_by
    _ = pr.info
    _ = pr.api_call
    _ = pr.repo
    _ = pr.project
    _ = pr.org
    pr.refresh()
    _take(pr.iter_tags(), 5)
    pr.list_tags()
    _take(pr.iter_threads(), 5)
    pr.list_threads()
    pr.list_reviewers()
    _take(pr.iter_commits(), 5)
    pr.list_commits()
    _take(pr.iter_work_item_ids(), 5)
    pr.list_work_item_ids()
    pr.list_work_items()
    _take(pr.iter_iterations(), 5)
    pr.list_iterations()
    iterations = list(pr.iter_iterations())
    if iterations:
        pr.get_iteration_changes(iterations[0].id)
    _take(pr.iter_statuses(), 5)
    pr.list_statuses()
    pr.list_tag_details()
    _take(pr.iter_files_changed(), 5)
    pr.list_files_changed()
    threads = list(pr.iter_threads())
    if threads and threads[0].id is not None:
        pr.get_thread(threads[0].id)

    # repo.get_pull_request(id) round-trip
    repo.get_pull_request(pr.id)
