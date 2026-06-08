"""Integration tests for pull request read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from pyado.raw import PipelineApprovalStatus, PullRequestStatus
from tests.integration.raw._support import _take, console


def test_prs_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Iterate pull requests with various status filters and fetch PR details."""
    console.print("\n=== PULL REQUESTS (read) ===")

    _take(
        raw.iter_pull_requests(
            project_api_call,
            search_criteria=raw.PullRequestSearchCriteria(
                status=PullRequestStatus.ACTIVE
            ),
        ),
        5,
    )
    _take(raw.iter_approvals(project_api_call, state=PipelineApprovalStatus.PENDING), 5)

    pr_criteria_variants: list[tuple[str, raw.PullRequestSearchCriteria | None]] = [
        ("iter_pull_requests [no criteria]", None),
        (
            "iter_pull_requests [status=active]",
            raw.PullRequestSearchCriteria(status=PullRequestStatus.ACTIVE),
        ),
        (
            "iter_pull_requests [status=completed]",
            raw.PullRequestSearchCriteria(status=PullRequestStatus.COMPLETED),
        ),
        (
            "iter_pull_requests [status=abandoned]",
            raw.PullRequestSearchCriteria(status=PullRequestStatus.ABANDONED),
        ),
    ]
    rng.shuffle(pr_criteria_variants)

    pr_item: raw.PullRequestListItem | None = None
    for _, criteria in pr_criteria_variants[:3]:
        result = _take(
            raw.iter_pull_requests(project_api_call, search_criteria=criteria), 5
        )
        if result and not pr_item:
            pr_item = result[0]

    if pr_item:
        console.print(f"  PR: #{pr_item.pr_id}  {pr_item.title!r}")
        pr_api_call = raw.get_pull_request_api_call(
            project_api_call, pr_item.repository.id, pr_item.pr_id
        )
        _take(raw.iter_pull_request_threads(pr_api_call), 20)
        _take(raw.iter_pull_request_iterations(pr_api_call), 5)
        _take(raw.list_pull_request_commits(pr_api_call), 10)
        raw.get_pull_request_labels_details(pr_api_call)
        raw.get_pull_request_reviewers(pr_api_call)
        _take(raw.list_pull_request_work_item_ids(pr_api_call), 10)


def test_pr_extras_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Fetch PR statuses, iteration changes, and thread details."""
    del rng
    console.print("\n=== PR EXTRAS (read) ===")
    prs = raw.list_pull_requests(
        project_api_call,
        search_criteria=raw.PullRequestSearchCriteria(
            status=PullRequestStatus.COMPLETED
        ),
    )
    if not prs:
        return

    pr = prs[0]
    pr_api_call = raw.get_pull_request_api_call(
        project_api_call, pr.repository.id, pr.pr_id
    )
    statuses = list(raw.iter_pull_request_statuses(pr_api_call))
    assert statuses == raw.list_pull_request_statuses(pr_api_call)

    iterations = raw.list_pull_request_iterations(pr_api_call)
    if iterations:
        raw.get_pull_request_iteration_changes(pr_api_call, iterations[0].id)

    threads = raw.list_pull_request_threads(pr_api_call)
    if threads and threads[0].id:
        raw.get_pull_request_thread(pr_api_call, threads[0].id)
