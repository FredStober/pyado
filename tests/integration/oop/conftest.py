"""Session-scoped OOP object fixtures for integration tests."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado.oop import (
    AzureDevOpsService,
    Build,
    Organization,
    Project,
    PullRequest,
    Repository,
    VariableGroup,
    WorkItem,
)
from pyado.raw import PullRequestStatus
from tests.integration.raw._support import _take


@pytest.fixture(scope="session")
def svc(org_url: str, token: str) -> AzureDevOpsService:
    """Construct an AzureDevOpsService for the configured instance."""
    return AzureDevOpsService(org=org_url, pat=token)


@pytest.fixture(scope="session")
def org(svc: AzureDevOpsService) -> Organization:
    """Return the Organisation from the service."""
    return svc.org


@pytest.fixture(scope="session")
def proj(org: Organization, project_name: str) -> Project:
    """Return the configured Project, skipping the suite if not found."""
    result = org.get_project(project_name)
    if result is None:
        pytest.skip(f"Project {project_name!r} not found in ADO instance")
    return result


@pytest.fixture(scope="session")
def repo(proj: Project) -> Repository | None:
    """Return the first repository in the project, or None."""
    repos = proj.repos.list_repositories()
    return repos[0] if repos else None


@pytest.fixture(scope="session")
def existing_pr(repo: Repository | None) -> PullRequest | None:
    """Return a completed or abandoned PR from the first repo, or None."""
    if repo is None:
        return None
    prs = _take(repo.iter_pull_requests(status=PullRequestStatus.COMPLETED), 1)
    if not prs:
        prs = _take(repo.iter_pull_requests(status=PullRequestStatus.ABANDONED), 1)
    return prs[0] if prs else None


@pytest.fixture(scope="session")
def existing_wi(proj: Project) -> WorkItem | None:
    """Return the most recent work item in the project, or None."""
    wiql = (
        "SELECT [System.Id], [System.Title], [System.State] "
        "FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.Id] DESC"
    )
    wis = _take(proj.boards.iter_work_items(wiql), 1)
    return wis[0] if wis else None


@pytest.fixture(scope="session")
def build(proj: Project) -> Build | None:
    """Return the most recent build in the project, or None."""
    builds = _take(proj.pipelines.iter_builds(), 1)
    return builds[0] if builds else None


@pytest.fixture(scope="session")
def vg(proj: Project) -> VariableGroup | None:
    """Return the first variable group in the project, or None."""
    vgs = _take(proj.pipelines.library.iter_variable_groups(), 1)
    return vgs[0] if vgs else None
