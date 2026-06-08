"""Integration tests for AzureDevOpsService OOP class."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import AzureDevOpsService, Build, PullRequest, Repository, WorkItem
from tests.integration.raw._support import console


def test_service_properties(svc: AzureDevOpsService) -> None:
    """Exercise AzureDevOpsService properties (org, api_call, oop_api, refresh)."""
    console.print("\n=== AzureDevOpsService ===")
    _ = svc.org
    _ = svc.api_call
    _ = svc.oop_api
    svc.refresh()


def test_service_by_url(
    svc: AzureDevOpsService,
    org_url: str,
    project_name: str,
    build: Build | None,
    existing_pr: PullRequest | None,
    repo: Repository | None,
    existing_wi: WorkItem | None,
) -> None:
    """Exercise AzureDevOpsService get-by-URL helpers."""
    console.print("\n=== AzureDevOpsService (by-URL helpers) ===")

    if build is not None:
        build_url = f"{org_url}/{project_name}/_build/results?buildId={build.id}"
        svc.get_build_by_url(build_url)
        svc.get_build_by_url(
            f"{org_url}/{project_name}/_build/results", build_id=build.id
        )

    if repo is not None:
        repo_url = f"{org_url}/{project_name}/_git/{repo.name}"
        svc.get_repository_by_url(repo_url)
        if existing_pr is not None:
            pr_url = f"{repo_url}/pullrequest/{existing_pr.id}"
            svc.get_pull_request_by_url(pr_url)
            svc.get_pull_request_by_url(repo_url, pull_request_id=existing_pr.id)

    if existing_wi is not None:
        wi_url = f"{org_url}/{project_name}/_workitems/edit/{existing_wi.id}"
        svc.get_work_item_by_url(wi_url)
        svc.get_work_item_by_url(
            f"{org_url}/{project_name}/_workitems", work_item_id=existing_wi.id
        )
