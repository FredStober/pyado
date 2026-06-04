"""Tests for the pyado.oop OOP wrapper layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from pyado.oop import (
    ActiveBuildTask,
    AddFile,
    Area,
    AzureDevOpsService,
    Build,
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
    Commit,
    DeleteFile,
    EditFile,
    Iteration,
    Organization,
    Pipeline,
    Project,
    PullRequest,
    RenameFile,
    Repository,
    Team,
    VariableGroup,
    WorkItem,
)
from pyado.raw import (
    AccessControlList,
    ApiCall,
    BranchStatistics,
    BuildDetails,
    BuildId,
    BuildIssue,
    BuildIssueType,
    BuildLogInfo,
    BuildRecordInfo,
    BuildRecordState,
    BuildRecordType,
    BuildResult,
    BuildStatus,
    ClassificationNode,
    GitCommitRef,
    GraphGroup,
    IdentityIdRef,
    IdentityInfo,
    JobId,
    PipelineInfo,
    PipelineResourcePermissions,
    PipelineResourceType,
    PipelineRunInfo,
    PlanId,
    ProjectInfo,
    PullRequestCompletionOptions,
    PullRequestCreated,
    PullRequestListItem,
    PullRequestStatus,
    PullRequestStatusInfo,
    PullRequestStatusState,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestVote,
    RepositoryInfo,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TaskId,
    TeamFieldValue,
    TeamInfo,
    TimelineId,
    VariableGroupInfo,
    VariableGroupProjectReference,
    VariableInfo,
    WorkItemComment,
    WorkItemInfo,
    WorkItemQuery,
    WorkItemQueryExpand,
    WorkItemRef,
    WorkItemRelation,
    WorkItemRelationType,
)

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

NOW_ISO = "2024-01-15T12:00:00+00:00"
ORG_URL = "https://dev.azure.com/testorg"
TOKEN = "test-token"
PROJECT_ID = uuid4()
REPO_ID = uuid4()


def _api_call(url: str = f"{ORG_URL}/_apis") -> ApiCall:
    return ApiCall(access_token=TOKEN, url=url)


def _make_service() -> AzureDevOpsService:
    return AzureDevOpsService(org=ORG_URL, pat=TOKEN)


def _project_info(name: str = "TestProject") -> ProjectInfo:
    return ProjectInfo.model_validate(
        {
            "id": str(PROJECT_ID),
            "name": name,
            "state": "wellFormed",
            "revision": 1,
            "visibility": "private",
            "lastUpdateTime": NOW_ISO,
        }
    )


def _repo_info(name: str = "myrepo") -> RepositoryInfo:
    return RepositoryInfo.model_validate(
        {
            "id": str(REPO_ID),
            "name": name,
            "project": {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": NOW_ISO,
            },
            "defaultBranch": "refs/heads/main",
            "size": 0,
            "remoteUrl": "https://dev.azure.com/testorg/_git/myrepo",
            "sshUrl": "git@ssh.dev.azure.com:v3/testorg/TestProject/myrepo",
            "webUrl": "https://dev.azure.com/testorg/TestProject/_git/myrepo",
            "isDisabled": False,
            "isInMaintenance": False,
        }
    )


def _pr_list_item(pr_id: int = 42) -> PullRequestListItem:
    return PullRequestListItem.model_validate(
        {
            "pullRequestId": pr_id,
            "repository": {"id": str(REPO_ID)},
            "title": "Test PR",
            "status": "active",
        }
    )


def _pr_created(pr_id: int = 42) -> PullRequestCreated:
    return PullRequestCreated.model_validate(
        {
            "pullRequestId": pr_id,
            "repository": {"id": str(REPO_ID)},
            "status": "active",
            "url": f"https://dev.azure.com/testorg/TestProject/_git/myrepo/pullrequests/{pr_id}",
            "title": "Test PR",
            "sourceRefName": "refs/heads/feature/x",
            "targetRefName": "refs/heads/main",
        }
    )


def _work_item_info(wi_id: int = 10) -> WorkItemInfo:
    return WorkItemInfo.model_validate(
        {"id": wi_id, "fields": {"System.Title": "My WI"}}
    )


def _build_details(build_id: int = 100, pipeline_id: int = 1) -> BuildDetails:
    return BuildDetails.model_validate(
        {
            "id": build_id,
            "buildNumber": "20240101.1",
            "status": "completed",
            "result": "succeeded",
            "queueTime": NOW_ISO,
            "lastChangedDate": NOW_ISO,
            "sourceBranch": "refs/heads/main",
            "sourceVersion": "abc123",
            "definition": {"id": pipeline_id, "name": "MyPipeline"},
            "requestedBy": {"id": str(uuid4()), "displayName": "User"},
            "requestedFor": {"id": str(uuid4()), "displayName": "User"},
            "reason": "manual",
            "priority": "normal",
            "url": "https://dev.azure.com/testorg/TestProject/_build/results?buildId=100",
            "repository": {"id": "repo-id", "name": "myrepo", "type": "TfsGit"},
            "project": {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": NOW_ISO,
            },
        }
    )


def _pipeline_info(pipeline_id: int = 7) -> PipelineInfo:
    return PipelineInfo.model_validate(
        {
            "id": pipeline_id,
            "revision": 1,
            "name": "MyPipeline",
            "folder": "\\",
            "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}",
        }
    )


def _git_commit_ref(sha: str = "abc123def456") -> GitCommitRef:
    return GitCommitRef.model_validate(
        {"commitId": sha, "comment": "Test commit", "commentTruncated": False}
    )


def _make_project(name: str = "TestProject") -> Project:
    return Project(_make_service(), name, _project_info(name))


def _make_repo(name: str = "myrepo") -> Repository:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
    return Repository(proj, api_call, _repo_info(name), proj._service)


def _make_pr(pr_id: int = 42) -> PullRequest:
    repo = _make_repo()
    api_call = _api_call(
        f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}/pullrequests/{pr_id}"
    )
    return PullRequest(repo, api_call, _pr_list_item(pr_id))


def _make_wi(wi_id: int = 10) -> WorkItem:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/{wi_id}")
    return WorkItem(proj, api_call, _work_item_info(wi_id))


def _make_build(build_id: int = 100, pipeline_id: int = 1) -> Build:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/{build_id}")
    return Build(proj, api_call, _build_details(build_id, pipeline_id), proj._service)


def _make_pipeline(pipeline_id: int = 7) -> Pipeline:
    proj = _make_project()
    return Pipeline(proj, pipeline_id, "MyPipeline", _pipeline_info(pipeline_id))


# ---------------------------------------------------------------------------
# AzureDevOpsService tests
# ---------------------------------------------------------------------------


class TestAzureDevOpsService:
    def test_init_with_explicit_org_and_pat(self) -> None:
        svc = AzureDevOpsService(org=ORG_URL, pat=TOKEN)
        assert svc.oop_api.org_url == ORG_URL
        assert svc.oop_api.token == TOKEN

    def test_init_from_env_org(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_DEVOPS_ORG", ORG_URL)
        monkeypatch.setenv("AZURE_DEVOPS_EXT_PAT", TOKEN)
        svc = AzureDevOpsService()
        assert svc.oop_api.org_url == ORG_URL

    def test_init_from_env_system_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
        monkeypatch.setenv("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", ORG_URL)
        monkeypatch.setenv("AZURE_DEVOPS_EXT_PAT", TOKEN)
        svc = AzureDevOpsService()
        assert svc.oop_api.org_url == ORG_URL

    def test_init_with_credential(self) -> None:
        credential = MagicMock()
        token_result = MagicMock()
        token_result.token = "bearer-token"
        credential.get_token.return_value = token_result
        svc = AzureDevOpsService(org=ORG_URL, credential=credential)
        assert svc.oop_api.token == "bearer-token"
        credential.get_token.assert_called_once()

    def test_init_both_pat_and_credential_raises(self) -> None:
        with pytest.raises(ValueError, match="either"):
            AzureDevOpsService(org=ORG_URL, pat=TOKEN, credential=MagicMock())

    def test_init_no_org_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
        monkeypatch.delenv("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", raising=False)
        with pytest.raises(ValueError, match="Organisation URL"):
            AzureDevOpsService(pat=TOKEN)

    def test_init_no_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_EXT_PAT", raising=False)
        with pytest.raises(ValueError, match="No access token"):
            AzureDevOpsService(org=ORG_URL)

    def test_org_is_singleton(self) -> None:
        svc = _make_service()
        assert svc.org is svc.org

    def test_org_type(self) -> None:
        svc = _make_service()
        assert isinstance(svc.org, Organization)

    def test_api_call_is_org_level(self) -> None:
        svc = _make_service()
        assert "_apis" in str(svc.api_call.url)

    def test_refresh_clears_cache(self) -> None:
        svc = _make_service()
        svc._cache["some-key"] = object()
        svc._org_view = MagicMock()
        svc.refresh()
        assert len(svc._cache) == 0
        assert svc._org_view is None

    def test_refresh_resets_org_singleton(self) -> None:
        svc = _make_service()
        org1 = svc.org
        svc.refresh()
        org2 = svc.org
        assert org1 is not org2


# ---------------------------------------------------------------------------
# Organization tests
# ---------------------------------------------------------------------------


class TestOrganization:
    def test_api_call_matches_service(self) -> None:
        svc = _make_service()
        assert svc.org.api_call is svc.api_call

    def test_get_project_fetches_and_caches(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_project") as mock_get,
        ):
            mock_get.return_value = _project_info("ICS")
            proj = svc.org.get_project("ICS")
        assert isinstance(proj, Project)
        assert proj.name == "ICS"

    def test_get_project_returns_same_instance(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_project") as mock_get:
            mock_get.return_value = _project_info("ICS")
            proj1 = svc.org.get_project("ICS")
            proj2 = svc.org.get_project("ICS")
        assert proj1 is proj2
        mock_get.assert_called_once()

    def test_iter_projects_yields_and_caches(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter(
                [_project_info("ICS"), _project_info("Other")]
            )
            projects = list(svc.org.iter_projects())
        assert len(projects) == 2
        assert projects[0].name == "ICS"

    def test_iter_projects_shares_identity_with_get_project(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter([_project_info("ICS")])
            (proj_from_iter,) = svc.org.iter_projects()
        # get_project should hit the cache and return the same object
        with patch("pyado.oop.organization.raw.get_project"):
            proj_from_get = svc.org.get_project("ICS")
        assert proj_from_iter is proj_from_get

    def test_get_my_profile_delegates(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_profile_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_my_profile") as mock_profile,
        ):
            mock_call.return_value = _api_call()
            mock_profile.return_value = MagicMock()
            svc.org.get_my_profile()
        mock_call.assert_called_once_with(TOKEN)
        mock_profile.assert_called_once()

    def test_get_connection_data_delegates(self) -> None:
        svc = _make_service()
        with patch("pyado.oop.organization.raw.get_connection_data") as mock_get:
            mock_get.return_value = MagicMock()
            result = svc.org.get_connection_data()
        mock_get.assert_called_once()
        assert result is mock_get.return_value


# ---------------------------------------------------------------------------
# Project tests
# ---------------------------------------------------------------------------


class TestProject:
    def test_name(self) -> None:
        assert _make_project("ICS").name == "ICS"

    def test_id_from_pre_fetched_info(self) -> None:
        assert _make_project().id == PROJECT_ID

    def test_id_lazy_fetch(self) -> None:
        proj = Project(_make_service(), "LazyProj")
        with patch("pyado.oop.project.raw.get_project") as mock_get:
            mock_get.return_value = _project_info("LazyProj")
            assert proj.id == PROJECT_ID
        mock_get.assert_called_once()

    def test_info_lazy_fetch_caches(self) -> None:
        proj = Project(_make_service(), "LazyProj")
        with patch("pyado.oop.project.raw.get_project") as mock_get:
            mock_get.return_value = _project_info("LazyProj")
            _ = proj.info
            _ = proj.info
        mock_get.assert_called_once()

    def test_api_call_is_project_level(self) -> None:
        proj = _make_project()
        assert "TestProject/_apis" in str(proj.api_call.url)

    def test_org_returns_organization(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        assert proj.org is svc.org

    def test_refresh_clears_info(self) -> None:
        proj = _make_project()
        proj.refresh()
        assert proj._info is None

    def test_refresh_removes_child_cache_entries(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        proj_url = str(proj.api_call.url)
        svc._cache[proj_url + "/git/repositories/abc"] = object()
        svc._cache[proj_url + "/pipelines/7"] = object()
        svc._cache["https://other.url/stuff"] = object()
        proj.refresh()
        assert proj_url + "/git/repositories/abc" not in svc._cache
        assert proj_url + "/pipelines/7" not in svc._cache
        assert "https://other.url/stuff" in svc._cache

    def test_get_repository_found(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("myrepo")])
            mock_get.return_value = _api_call()
            repo = _make_project().get_repository("myrepo")
        assert repo.name == "myrepo"

    def test_get_repository_not_found(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("other")])
            mock_get.return_value = _api_call()
            with pytest.raises(ValueError, match="notexist"):
                _make_project().get_repository("notexist")

    def test_get_work_item(self) -> None:
        with (
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
            patch("pyado.oop.project.raw.get_work_item") as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _work_item_info(99)
            wi = _make_project().get_work_item(99)
        assert wi.id == 99

    def test_create_work_item_prepends_type(self) -> None:
        with (
            patch("pyado.oop.project.high.create_work_item") as mock_create,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
        ):
            mock_create.return_value = _work_item_info(1)
            mock_call.return_value = _api_call()
            _make_project().create_work_item("Task", {"System.Title": "My Task"})
        called_fields = mock_create.call_args.args[1]
        assert called_fields["System.WorkItemType"] == "Task"
        assert called_fields["System.Title"] == "My Task"

    def test_iter_work_items_yields_work_items(self) -> None:
        with (
            patch("pyado.oop.project.raw.post_wiql") as mock_wiql,
            patch("pyado.oop.project.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
        ):
            mock_wiql.return_value = [_work_item_info(5)]
            mock_iter.return_value = iter([_work_item_info(5)])
            mock_call.return_value = _api_call()
            result = list(_make_project().iter_work_items("SELECT [System.Id]"))
        assert len(result) == 1
        assert result[0].id == 5

    def test_iter_builds_delegates(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_builds") as mock_iter,
            patch("pyado.oop.project.raw.get_build_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_build_details()])
            mock_call.return_value = _api_call()
            builds = list(
                _make_project().iter_builds(status_filter=BuildStatus.COMPLETED)
            )
        assert len(builds) == 1
        search_criteria = mock_iter.call_args.args[1]
        assert search_criteria.status_filter == BuildStatus.COMPLETED

    def test_get_build_returns_build(self) -> None:
        with (
            patch("pyado.oop.project.raw.get_build_api_call") as mock_call,
            patch("pyado.oop.project.raw.get_build_details") as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _build_details(build_id=42)
            build = _make_project().get_build(42)
        assert build.id == 42

    def test_start_build_returns_build(self) -> None:
        with (
            patch("pyado.oop.project.high.start_build") as mock_start,
            patch("pyado.oop.project.raw.get_build_api_call") as mock_call,
        ):
            mock_start.return_value = _build_details(build_id=99)
            mock_call.return_value = _api_call()
            build = _make_project().start_build(7, source_branch="refs/heads/main")
        assert mock_start.call_args.args[1] == 7
        assert mock_start.call_args.kwargs["source_branch"] == "refs/heads/main"
        assert build is not None

    def test_iter_pipeline_definitions_delegates(self) -> None:
        with patch("pyado.oop.project.raw.iter_pipeline_definitions") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_project().iter_pipeline_definitions())
        assert len(result) == 1

    def test_iter_pipelines_yields_pipeline_wrappers(self) -> None:
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([_pipeline_info(3)])
            result = list(_make_project().iter_pipelines())
        assert len(result) == 1
        assert result[0].id == 3

    def test_iter_pipelines_caches(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([_pipeline_info(3)])
            (pipe1,) = proj.iter_pipelines()
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([_pipeline_info(3)])
            (pipe2,) = proj.iter_pipelines()
        assert pipe1 is pipe2

    def test_get_pipeline_returns_pipeline(self) -> None:
        with patch("pyado.oop.project.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(5)
            result = _make_project().get_pipeline(5)
        assert result.id == 5

    def test_iter_pending_approvals_delegates(self) -> None:
        with patch("pyado.oop.project.high.iter_pending_approvals") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_project().iter_pending_approvals())
        assert len(result) == 1

    def test_iter_active_prs_yields_pull_requests(self) -> None:
        item = _pr_list_item(77)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.project.high.iter_active_prs") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_repo_call,
            patch("pyado.oop.project.raw.get_repository_info") as mock_repo_info,
            patch("pyado.oop.project.raw.get_pr_api_call") as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            prs = list(_make_project().iter_active_prs())
        assert len(prs) == 1
        assert prs[0].id == 77

    def test_iter_sprint_iterations_builds_team_call(self) -> None:
        sprint_info = MagicMock(spec=SprintIterationInfo)
        with patch("pyado.oop.project.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([sprint_info])
            result = list(_make_project().iter_sprint_iterations("MyTeam"))
        assert len(result) == 1
        team_call = mock_iter.call_args.args[0]
        assert "MyTeam" in str(team_call.url)

    def test_iter_sprint_iterations_passes_timeframe(self) -> None:
        with patch("pyado.oop.project.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([])
            list(
                _make_project().iter_sprint_iterations(
                    "MyTeam", timeframe_filter=SprintIterationTimeframe.CURRENT
                )
            )
        assert (
            mock_iter.call_args.kwargs["timeframe_filter"]
            == SprintIterationTimeframe.CURRENT
        )

    def test_get_team_field_values_delegates(self) -> None:
        with patch("pyado.oop.project.raw.get_team_field_values") as mock_get:
            mock_get.return_value = [MagicMock()]
            result = _make_project().get_team_field_values("MyTeam")
        assert len(result) == 1
        team_call = mock_get.call_args.args[0]
        assert "MyTeam" in str(team_call.url)

    def test_add_team_iteration_delegates(self) -> None:
        iteration_id = uuid4()
        with patch("pyado.oop.project.raw.add_team_iteration") as mock_add:
            _make_project().add_team_iteration("MyTeam", iteration_id)
        mock_add.assert_called_once()
        team_call = mock_add.call_args.args[0]
        assert "MyTeam" in str(team_call.url)
        assert mock_add.call_args.args[1] == iteration_id


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_id(self) -> None:
        assert _make_pipeline(7).id == 7

    def test_name(self) -> None:
        assert _make_pipeline().name == "MyPipeline"

    def test_info_from_pre_fetched(self) -> None:
        assert _make_pipeline().info.id == 7

    def test_info_lazy_fetch(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe._info is None
        with patch("pyado.oop.pipeline.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(7)
            info = pipe.info
        assert info.id == 7

    def test_api_call_is_project_level(self) -> None:
        pipe = _make_pipeline()
        assert pipe.api_call is pipe.project.api_call

    def test_project_reference(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe.org is svc.org

    def test_refresh_clears_info(self) -> None:
        pipe = _make_pipeline()
        pipe.refresh()
        assert pipe._info is None

    def test_iter_runs_delegates(self) -> None:
        with patch("pyado.oop.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_pipeline().iter_runs())
        assert mock_iter.call_args.args[1] == 7

    def test_start_run_no_args_passes_none(self) -> None:
        with patch("pyado.oop.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            _make_pipeline().start_run()
        assert mock_run.call_args.args[2] is None

    def test_start_run_with_variables_builds_request(self) -> None:
        with patch("pyado.oop.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            _make_pipeline().start_run(variables={"env": "test"})
        request_arg = mock_run.call_args.args[2]
        assert request_arg is not None
        assert request_arg.variables == {"env": "test"}

    def test_get_run_delegates(self) -> None:
        with patch("pyado.oop.pipeline.raw.get_pipeline_run") as mock_get:
            mock_get.return_value = MagicMock()
            _make_pipeline().get_run(42)
        assert mock_get.call_args.args[2] == 42


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------


class TestBuild:
    def test_id(self) -> None:
        assert _make_build(build_id=100).id == 100

    def test_status(self) -> None:
        assert _make_build().status == "completed"

    def test_number(self) -> None:
        assert _make_build().number == "20240101.1"

    def test_info_returns_details(self) -> None:
        assert _make_build().info.id == 100

    def test_api_call(self) -> None:
        build = _make_build()
        assert "build/builds" in str(build.api_call.url)

    def test_project_reference(self) -> None:
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, api_call, _build_details(), proj._service)
        assert build.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, api_call, _build_details(), svc)
        assert build.org is svc.org

    def test_pipeline_zero_cost(self) -> None:
        build = _make_build(pipeline_id=1)
        pipe = build.pipeline
        assert isinstance(pipe, Pipeline)
        assert pipe.id == 1
        assert pipe.name == "MyPipeline"

    def test_pipeline_cached(self) -> None:
        build = _make_build(pipeline_id=1)
        assert build.pipeline is build.pipeline

    def test_refresh_refetches(self) -> None:
        build = _make_build()
        new_info = _build_details(build_id=100)
        new_info.build_number = "20240102.1"
        with patch("pyado.oop.build.raw.get_build_details") as mock_get:
            mock_get.return_value = new_info
            build.refresh()
        mock_get.assert_called_once()

    def test_iter_artifacts_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_artifacts") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_build().iter_artifacts())
        mock_iter.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch("pyado.oop.build.raw.post_build_tag") as mock_tag:
            mock_tag.return_value = ["tag-a"]
            result = _make_build().add_tag("tag-a")
        assert result == ["tag-a"]

    def test_iter_tags_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_tags") as mock_iter:
            mock_iter.return_value = iter(["tag-x"])
            result = list(_make_build().iter_tags())
        assert result == ["tag-x"]

    def test_remove_tag_delegates(self) -> None:
        with patch("pyado.oop.build.raw.delete_build_tag") as mock_del:
            mock_del.return_value = ["remaining"]
            result = _make_build().remove_tag("old-tag")
        assert result == ["remaining"]

    def test_iter_timeline_records_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_build().iter_timeline_records())
        assert len(result) == 1

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.build.high.iter_build_work_item_ids") as mock_iter:
            mock_iter.return_value = iter([42, 43])
            result = list(_make_build().iter_work_item_ids())
        assert result == [42, 43]

    def test_iter_work_items_between_delegates(self) -> None:
        ref_a = WorkItemRef(id=10, url=None)
        ref_b = WorkItemRef(id=20, url=None)
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([ref_a, ref_b])
            result = list(newer.iter_work_items_between(older))
        assert result == [10, 20]
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args.args
        assert call_args[1] == 50
        assert call_args[2] == 100

    def test_iter_work_items_between_passes_top(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([])
            list(newer.iter_work_items_between(older, top=5))
        assert mock_iter.call_args.kwargs["top"] == 5

    def test_get_log_text_delegates(self) -> None:
        with patch("pyado.oop.build.raw.get_build_log") as mock_log:
            mock_log.return_value = "log line 1\nlog line 2\n"
            text = _make_build().get_log_text(3)
        assert text == "log line 1\nlog line 2\n"
        assert mock_log.call_args.args[1] == 3


# ---------------------------------------------------------------------------
# Shared identity tests
# ---------------------------------------------------------------------------


class TestSharedIdentity:
    def test_build_project_is_wi_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        proj_url = str(proj.api_call.url)
        svc._cache[proj_url] = proj

        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        wi_api = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/10")
        build = Build(proj, build_api, _build_details(), svc)
        wi = WorkItem(proj, wi_api, _work_item_info())

        assert build.project is wi.project

    def test_build_org_is_svc_org(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, build_api, _build_details(), svc)
        assert build.org is svc.org

    def test_pipeline_cached_across_build_and_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, build_api, _build_details(pipeline_id=1), svc)

        # Access build.pipeline to populate the cache
        pipe_from_build = build.pipeline

        # Access project.get_pipeline — should return same cached object
        with patch("pyado.oop.project.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(1)
            pipe_from_project = proj.get_pipeline(1)

        # Already cached so mock not called; same object
        assert pipe_from_build is pipe_from_project

    def test_pr_project_via_repo(self) -> None:
        proj = _make_project()
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        pr_api = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}/pullrequests/1"
        )
        pr = PullRequest(repo, pr_api, _pr_list_item(1))
        assert pr.project is proj
        assert pr.repo is repo


# ---------------------------------------------------------------------------
# WorkItem tests
# ---------------------------------------------------------------------------


class TestWorkItem:
    def test_id(self) -> None:
        assert _make_wi(55).id == 55

    def test_info_returns_work_item_info(self) -> None:
        wi = _make_wi()
        assert wi.info is wi._info

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        wi = WorkItem(_make_project(), api, _work_item_info())
        assert wi.api_call is api

    def test_title(self) -> None:
        assert _make_wi().title == "My WI"

    def test_title_absent_returns_none(self) -> None:
        proj = _make_project()
        api = _api_call()
        wi = WorkItem(proj, api, WorkItemInfo.model_validate({"id": 1, "fields": {}}))
        assert wi.title is None

    def test_get_field_returns_value(self) -> None:
        assert _make_wi().get_field("System.Title") == "My WI"

    def test_get_field_returns_none_for_absent(self) -> None:
        assert _make_wi().get_field("System.Missing") is None

    def test_project_reference(self) -> None:
        proj = _make_project()
        wi = WorkItem(proj, _api_call(), _work_item_info())
        assert wi.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        wi = WorkItem(proj, _api_call(), _work_item_info())
        assert wi.org is svc.org

    def test_refresh_refetches(self) -> None:
        wi = _make_wi()
        with patch("pyado.oop.work_item.raw.get_work_item") as mock_get:
            mock_get.return_value = _work_item_info()
            wi.refresh()
        mock_get.assert_called_once()

    def test_update_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.update_work_item") as mock_update:
            mock_update.return_value = _work_item_info()
            _make_wi().update({"System.Title": "New"})
        mock_update.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.add_work_item_tag") as mock_tag:
            mock_tag.return_value = ["tag-a"]
            result = _make_wi().add_tag("tag-a")
        assert result == ["tag-a"]

    def test_add_comment_delegates(self) -> None:
        with patch("pyado.oop.work_item.raw.post_work_item_comment") as mock_comment:
            mock_comment.return_value = MagicMock()
            _make_wi().add_comment("hello")
        mock_comment.assert_called_once()

    def test_get_tags_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.get_work_item_tags") as mock_tags:
            mock_tags.return_value = ["tag-a", "tag-b"]
            result = _make_wi().get_tags()
        assert result == ["tag-a", "tag-b"]

    def test_remove_tag_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.remove_work_item_tag") as mock_remove:
            mock_remove.return_value = ["tag-b"]
            result = _make_wi().remove_tag("tag-a")
        assert result == ["tag-b"]

    def test_iter_comments_delegates(self) -> None:
        with patch("pyado.oop.work_item.raw.iter_work_item_comments") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_wi().iter_comments())
        assert len(result) == 1

    def test_add_attachment_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.add_work_item_attachment") as mock_attach:
            mock_attach.return_value = MagicMock()
            _make_wi().add_attachment("report.txt", b"data")
        mock_attach.assert_called_once()

    def test_add_link_delegates(self) -> None:
        with (
            patch("pyado.oop.work_item.high.WorkItemLink.wi_link") as mock_link,
            patch("pyado.oop.work_item.high.add_work_item_link") as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().add_link(_make_wi(20), WorkItemRelationType.CHILD)
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_pull_request_delegates(self) -> None:
        with (
            patch("pyado.oop.work_item.high.WorkItemLink.pull_request") as mock_link,
            patch("pyado.oop.work_item.high.add_work_item_link") as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_pull_request(_make_pr())
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_build_delegates(self) -> None:
        with (
            patch("pyado.oop.work_item.high.WorkItemLink.build") as mock_link,
            patch("pyado.oop.work_item.high.add_work_item_link") as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_build(_make_build())
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_commit_delegates(self) -> None:
        with (
            patch("pyado.oop.work_item.high.WorkItemLink.commit") as mock_link,
            patch("pyado.oop.work_item.high.add_work_item_link") as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_commit(_make_repo(), "abc123")
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_iter_linked_work_items_yields_wi_relations(self) -> None:
        wi = _make_wi(10)
        wi._info.relations = [
            WorkItemRelation(
                rel="System.LinkTypes.Hierarchy-Forward",
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/20",
            ),
            WorkItemRelation(
                rel="ArtifactLink",
                url="vstfs:///Git/PullRequestId/abc",
            ),
        ]
        linked_info = _work_item_info(20)
        with (
            patch("pyado.oop.work_item.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([linked_info])
            mock_call.return_value = _api_call()
            result = list(wi.iter_linked_work_items())
        assert len(result) == 1
        assert result[0].id == 20
        ids_passed = mock_iter.call_args.args[1]
        assert ids_passed == [20]

    def test_iter_linked_work_items_filters_by_rel_type(self) -> None:
        wi = _make_wi(10)
        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/30",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.RELATED,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/40",
            ),
        ]
        with (
            patch("pyado.oop.work_item.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_work_item_info(30)])
            mock_call.return_value = _api_call()
            result = list(wi.iter_linked_work_items(WorkItemRelationType.CHILD))
        assert len(result) == 1
        assert mock_iter.call_args.args[1] == [30]

    def test_get_parent_returns_none_when_no_parent(self) -> None:
        wi = _make_wi(10)
        wi._info.relations = []
        result = wi.get_parent()
        assert result is None

    def test_get_parent_returns_parent_work_item(self) -> None:
        wi = _make_wi(10)
        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.PARENT,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/5",
            ),
        ]
        parent_info = _work_item_info(5)
        with (
            patch("pyado.oop.work_item.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([parent_info])
            mock_call.return_value = _api_call()
            parent = wi.get_parent()
        assert parent is not None
        assert parent.id == 5


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestRepository:
    def test_id(self) -> None:
        assert _make_repo().id == REPO_ID

    def test_name(self) -> None:
        assert _make_repo().name == "myrepo"

    def test_default_branch(self) -> None:
        assert _make_repo().default_branch == "refs/heads/main"

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        proj = _make_project()
        repo = Repository(proj, api, _repo_info(), proj._service)
        assert repo.api_call is api

    def test_web_url(self) -> None:
        assert "testorg" in str(_make_repo().web_url)

    def test_project_reference(self) -> None:
        proj = _make_project()
        api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api, _repo_info(), proj._service)
        assert repo.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api, _repo_info(), svc)
        assert repo.org is svc.org

    def test_refresh_refetches(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_repository_info") as mock_get:
            mock_get.return_value = _repo_info()
            repo.refresh()
        mock_get.assert_called_once()

    def test_get_pr_delegates_to_get_pr_details(self) -> None:
        with (
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
            patch("pyado.oop.repository.raw.get_pr_details") as mock_details,
        ):
            mock_call.return_value = _api_call()
            mock_details.return_value = _pr_created(7)
            pr = _make_repo().get_pr(7)
        assert pr.id == 7

    def test_iter_prs_filters_by_repo(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_prs") as mock_iter,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1), _pr_list_item(2)])
            mock_call.return_value = _api_call()
            prs = list(_make_repo().iter_prs())
        criteria = mock_iter.call_args.args[1]
        assert criteria.repository_id == str(REPO_ID)
        assert criteria.status == "active"
        assert len(prs) == 2

    def test_iter_prs_status_override(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_prs") as mock_iter,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([])
            mock_call.return_value = _api_call()
            list(_make_repo().iter_prs(status=PullRequestStatus.COMPLETED))
        criteria = mock_iter.call_args.args[1]
        assert criteria.status == "completed"

    def test_create_pr_returns_pull_request(self) -> None:
        with (
            patch("pyado.oop.repository.high.create_pr") as mock_create,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_create.return_value = _pr_created(5)
            mock_call.return_value = _api_call()
            pr = _make_repo().create_pr("My PR", "feature/x", "main")
        assert pr.id == 5

    def test_get_file_at_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.get_file_content_at_branch") as mock_get:
            mock_get.return_value = "file content"
            result = _make_repo().get_file_at_branch("/foo.py", "main")
        assert result == "file content"

    def test_get_file_at_commit_delegates(self) -> None:
        with patch("pyado.oop.repository.high.get_file_content_at_commit") as mock_get:
            mock_get.return_value = "commit content"
            result = _make_repo().get_file_at_commit("/bar.py", "abc123")
        assert result == "commit content"

    def test_iter_refs_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_refs(name_filter="heads/main"))
        assert len(result) == 1
        assert mock_iter.call_args.args[1].name_filter == "heads/main"

    def test_create_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.create_branch") as mock_create:
            _make_repo().create_branch("feature/new", "abc123")
        mock_create.assert_called_once()

    def test_delete_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.delete_branch") as mock_del:
            _make_repo().delete_branch("feature/old", "def456")
        mock_del.assert_called_once()

    def test_iter_commit_diff_delegates(self) -> None:
        with patch("pyado.oop.repository.high.iter_commit_diff") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_commit_diff("abc", "def"))
        assert len(result) == 1

    def test_push_commits_delegates(self) -> None:
        with patch("pyado.oop.repository.high.push_commits") as mock_push:
            mock_push.return_value = MagicMock()
            _make_repo().push_commits([], [])
        mock_push.assert_called_once()

    def test_get_file_bytes_at_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_at_branch("/img.png", "main")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "main"
        assert version_type == "branch"

    def test_get_file_bytes_at_branch_strips_refs_prefix(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"data"
            _make_repo().get_file_bytes_at_branch("/x", "refs/heads/main")
        _, _, version, _ = mock_get.call_args.args
        assert version == "main"

    def test_get_file_bytes_at_commit_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_at_commit("/img.png", "abc123")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "abc123"
        assert version_type == "commit"

    def test_get_file_bytes_returns_none_when_missing(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = None
            result = _make_repo().get_file_bytes_at_branch("/missing", "main")
        assert result is None

    def test_iter_commits_returns_commit_objects(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = [_git_commit_ref("sha1"), _git_commit_ref("sha2")]
            result = list(_make_repo().iter_commits())
        assert len(result) == 2
        assert all(isinstance(item, Commit) for item in result)
        assert result[0].sha == "sha1"
        assert result[1].sha == "sha2"

    def test_iter_commits_passes_item_path(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(_make_repo().iter_commits(item_path="/src/foo.py", top=10))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_path == "/src/foo.py"
        assert criteria.top == 10

    def test_get_commit_returns_commit_object(self) -> None:
        with patch("pyado.oop.repository.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("deadbeef")
            result = _make_repo().get_commit("deadbeef")
        assert isinstance(result, Commit)
        assert result.sha == "deadbeef"
        mock_get.assert_called_once()

    def test_make_ref_update_delegates(self) -> None:
        with patch("pyado.oop.repository.high.create_ref_update") as mock_create:
            mock_create.return_value = MagicMock()
            _make_repo().make_ref_update("main")
        mock_create.assert_called_once()

    def test_commit_delegates_to_push(self) -> None:
        with (
            patch("pyado.oop.repository.high.create_ref_update") as mock_ref,
            patch("pyado.oop.repository.high.make_commit") as mock_commit,
            patch("pyado.oop.repository.high.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("main", "My message", [EditFile("/f.py", "x")])
        mock_ref.assert_called_once()
        mock_commit.assert_called_once()
        mock_push.assert_called_once()

    def test_commit_passes_branch_and_message(self) -> None:
        with (
            patch("pyado.oop.repository.high.create_ref_update") as mock_ref,
            patch("pyado.oop.repository.high.make_commit") as mock_commit,
            patch("pyado.oop.repository.high.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("feature/x", "Fix bug", [DeleteFile("/old.py")])
        assert mock_ref.call_args.args[1] == "feature/x"
        assert mock_commit.call_args.args[0] == "Fix bug"

    def test_commit_converts_file_changes_to_git_changes(self) -> None:
        with (
            patch("pyado.oop.repository.high.create_ref_update") as mock_ref,
            patch("pyado.oop.repository.high.make_commit") as mock_commit,
            patch("pyado.oop.repository.high.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit(
                "main",
                "Multi-change",
                [AddFile("/new.py", "x"), DeleteFile("/old.py")],
            )
        git_changes = mock_commit.call_args.args[1]
        assert len(git_changes) == 2
        assert git_changes[0].change_type.value == "add"
        assert git_changes[1].change_type.value == "delete"


# ---------------------------------------------------------------------------
# Commit tests
# ---------------------------------------------------------------------------


class TestCommit:
    def test_sha(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        assert commit.sha == "abc123"

    def test_message(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref())
        assert commit.message == "Test commit"

    def test_info_returns_git_commit_ref(self) -> None:
        ref = _git_commit_ref()
        commit = Commit(_make_repo(), ref)
        assert commit.info is ref

    def test_repo_reference(self) -> None:
        repo = _make_repo()
        commit = Commit(repo, _git_commit_ref())
        assert commit.repo is repo

    def test_project_via_repo(self) -> None:
        proj = _make_project()
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        commit = Commit(repo, _git_commit_ref())
        assert commit.project is proj

    def test_org_via_repo(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), svc)
        commit = Commit(repo, _git_commit_ref())
        assert commit.org is svc.org


# ---------------------------------------------------------------------------
# FileChange tests
# ---------------------------------------------------------------------------


class TestAddFile:
    def test_to_git_change_type(self) -> None:
        change = AddFile("/foo.py", "content").to_git_change()
        assert change.change_type.value == "add"

    def test_to_git_change_path(self) -> None:
        change = AddFile("/foo.py", "content").to_git_change()
        assert change.item.path == "/foo.py"

    def test_text_content_is_rawtext(self) -> None:
        change = AddFile("/foo.py", "hello").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "hello"
        assert change.new_content.content_type.value == "rawtext"

    def test_bytes_content_is_base64(self) -> None:
        change = AddFile("/img.png", b"\x89PNG").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content_type.value == "base64encoded"
        assert base64.b64decode(change.new_content.content) == b"\x89PNG"

    def test_path_text_file_is_rawtext(self, tmp_path: Path) -> None:
        text_file = tmp_path / "hello.txt"
        text_file.write_text("hello world", encoding="utf-8")
        change = AddFile("/hello.txt", Path(text_file)).to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "hello world"
        assert change.new_content.content_type.value == "rawtext"

    def test_path_binary_file_is_base64(self, tmp_path: Path) -> None:
        bin_file = tmp_path / "data.bin"
        bin_file.write_bytes(b"\x00\x01\x02\xff")
        change = AddFile("/data.bin", Path(bin_file)).to_git_change()
        assert change.new_content is not None
        assert change.new_content.content_type.value == "base64encoded"
        assert base64.b64decode(change.new_content.content) == b"\x00\x01\x02\xff"


class TestEditFile:
    def test_to_git_change_type(self) -> None:
        change = EditFile("/foo.py", "new content").to_git_change()
        assert change.change_type.value == "edit"

    def test_to_git_change_path(self) -> None:
        change = EditFile("/src/bar.py", "x").to_git_change()
        assert change.item.path == "/src/bar.py"

    def test_text_content(self) -> None:
        change = EditFile("/f.py", "updated").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "updated"


class TestDeleteFile:
    def test_to_git_change_type(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.change_type.value == "delete"

    def test_to_git_change_path(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.item.path == "/old.py"

    def test_no_new_content(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.new_content is None


class TestRenameFile:
    def test_to_git_change_type(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.change_type.value == "rename"

    def test_new_path_in_item(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.item.path == "/new.py"

    def test_old_path_in_source_server_item(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.source_server_item == "/old.py"

    def test_no_new_content(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.new_content is None


# ---------------------------------------------------------------------------
# PullRequest tests
# ---------------------------------------------------------------------------


class TestPullRequest:
    def test_id(self) -> None:
        assert _make_pr(99).id == 99

    def test_title(self) -> None:
        assert _make_pr().title == "Test PR"

    def test_status(self) -> None:
        assert _make_pr().status == "active"

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        repo = _make_repo()
        pr = PullRequest(repo, api, _pr_list_item())
        assert pr.api_call is api

    def test_info_returns_info(self) -> None:
        pr = _make_pr(7)
        assert pr.info.pr_id == 7

    def test_repo_reference(self) -> None:
        repo = _make_repo()
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.repo is repo

    def test_project_via_repo(self) -> None:
        proj = _make_project()
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.project is proj

    def test_org_via_repo(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), svc)
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.org is svc.org

    def test_refresh_refetches(self) -> None:
        pr = _make_pr()
        with patch("pyado.oop.pull_request.raw.get_pr_details") as mock_get:
            mock_get.return_value = _pr_list_item()
            pr.refresh()
        mock_get.assert_called_once()

    def test_link_work_item_calls_add_work_item_link(self) -> None:
        with patch("pyado.oop.pull_request.high.add_work_item_link") as mock_link:
            mock_link.return_value = _work_item_info()
            pr = _make_pr(32)
            wi = _make_wi(153)
            pr.link_work_item(wi)
        mock_link.assert_called_once()
        relation = mock_link.call_args.args[1]
        assert "PullRequestId" in relation.url
        assert "32" in relation.url

    def test_link_work_item_with_comment(self) -> None:
        with patch("pyado.oop.pull_request.high.add_work_item_link") as mock_link:
            mock_link.return_value = _work_item_info()
            _make_pr(32).link_work_item(_make_wi(153), comment="Linked via PR")
        relation = mock_link.call_args.args[1]
        assert relation.attributes is not None
        assert relation.attributes.get("comment") == "Linked via PR"

    def test_get_labels_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.get_pr_labels") as mock_labels:
            mock_labels.return_value = ["label-a", "label-b"]
            labels = _make_pr().get_labels()
        assert labels == ["label-a", "label-b"]

    def test_add_label_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_label") as mock_add:
            _make_pr().add_label("my-label")
        mock_add.assert_called_once()

    def test_remove_label_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.delete_pr_label") as mock_del:
            _make_pr().remove_label("my-label")
        mock_del.assert_called_once()

    def test_add_thread_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.create_pr_thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            _make_pr().add_thread("hello")
        assert mock_thread.call_args.args[1] == "hello"

    def test_iter_threads_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.iter_pr_threads") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_pr().iter_threads())
        assert len(result) == 1

    def test_reply_to_thread_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.reply_to_pr_thread") as mock_reply:
            mock_reply.return_value = MagicMock()
            _make_pr().reply_to_thread(1, "reply text")
        assert mock_reply.call_args.args[1] == 1
        assert mock_reply.call_args.args[2] == "reply text"

    def test_get_reviewers_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.get_pr_reviewers") as mock_get:
            mock_get.return_value = [MagicMock()]
            result = _make_pr().get_reviewers()
        assert len(result) == 1

    def test_add_reviewer_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.add_pr_reviewer") as mock_add:
            _make_pr().add_reviewer("user-id", is_required=True)
        assert mock_add.call_args.args[1] == "user-id"
        assert mock_add.call_args.kwargs["is_required"] is True

    def test_remove_reviewer_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.delete_pr_reviewer") as mock_del:
            _make_pr().remove_reviewer("user-id")
        mock_del.assert_called_once()

    def test_vote_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.set_pr_reviewer_vote") as mock_vote:
            _make_pr().vote("user-id", PullRequestVote.APPROVED)
        assert mock_vote.call_args.args[1] == "user-id"
        assert mock_vote.call_args.args[2] == PullRequestVote.APPROVED

    def test_update_sends_only_non_none(self) -> None:
        with patch("pyado.oop.pull_request.raw.patch_pr") as mock_patch:
            _make_pr().update(title="New Title")
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.title == "New Title"
        assert update_arg.description is None

    def test_set_status_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_status") as mock_status:
            _make_pr().set_status(PullRequestStatusState.SUCCEEDED, "my-check")
        mock_status.assert_called_once()

    def test_set_status_with_target_url(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_status") as mock_status:
            _make_pr().set_status(
                PullRequestStatusState.SUCCEEDED,
                "my-check",
                target_url="https://example.com/build/1",
            )
        request_arg = mock_status.call_args.args[1]
        assert request_arg.target_url is not None

    def test_iter_commits_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.iter_pr_commits") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_pr().iter_commits())
        assert len(result) == 1

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.iter_pr_work_item_ids") as mock_iter:
            mock_iter.return_value = iter([10, 20])
            result = list(_make_pr().iter_work_item_ids())
        assert result == [10, 20]

    def test_iter_iterations_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.iter_pr_iterations") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_pr().iter_iterations())
        assert len(result) == 1
        mock_iter.assert_called_once()

    def test_get_iteration_changes_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.get_pr_iteration_changes") as mock_get:
            mock_get.return_value = [MagicMock(), MagicMock()]
            result = _make_pr().get_iteration_changes(2)
        assert len(result) == 2
        assert mock_get.call_args.args[1] == 2

    def test_enable_auto_complete_patches_pr(self) -> None:
        with patch("pyado.oop.pull_request.raw.patch_pr") as mock_patch:
            _make_pr().enable_auto_complete("user-id-123")
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.auto_complete_set_by == IdentityIdRef(id="user-id-123")

    def test_enable_auto_complete_with_options(self) -> None:
        opts = PullRequestCompletionOptions.model_validate(
            {"mergeStrategy": "squash", "deleteSourceBranch": True}
        )
        with patch("pyado.oop.pull_request.raw.patch_pr") as mock_patch:
            _make_pr().enable_auto_complete("user-id-123", completion_options=opts)
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.completion_options is opts


# ---------------------------------------------------------------------------
# Build timeline tests (stages, jobs, tasks)
# ---------------------------------------------------------------------------

NOW_TS = "2024-01-15T12:00:00+00:00"

STAGE_ID = uuid4()
PHASE_ID = uuid4()
JOB_ID = uuid4()
TASK_ID = uuid4()


def _record(
    record_id: UUID,
    type_name: str,
    name: str,
    parent_id: UUID | None = None,
    state: str = "completed",
    result: str | None = "succeeded",
) -> BuildRecordInfo:
    return BuildRecordInfo.model_validate(
        {
            "attempt": 1,
            "changeId": None,
            "currentOperation": None,
            "details": None,
            "finishTime": NOW_TS,
            "id": str(record_id),
            "identifier": None,
            "lastModified": NOW_TS,
            "log": None,
            "name": name,
            "refName": None,
            "parentId": str(parent_id) if parent_id else None,
            "percentComplete": None,
            "previousAttempts": [],
            "result": result,
            "resultCode": None,
            "startTime": NOW_TS,
            "state": state,
            "task": None,
            "type": type_name,
            "url": None,
            "workerName": "Hosted Agent" if type_name == "Job" else None,
        }
    )


def _make_all_records(use_phase: bool = False) -> list[BuildRecordInfo]:
    """Build a flat timeline record list with one stage, one job, one task.

    When use_phase is True, inserts a Phase between the stage and job.
    """
    stage = _record(STAGE_ID, "Stage", "Build Stage")
    task = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
    if use_phase:
        phase = _record(PHASE_ID, "Phase", "__default", parent_id=STAGE_ID)
        job = _record(JOB_ID, "Job", "CI Job", parent_id=PHASE_ID)
        return [stage, phase, job, task]
    job = _record(JOB_ID, "Job", "CI Job", parent_id=STAGE_ID)
    return [stage, job, task]


def _make_tl_stage(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    build: Build | None = None,
) -> BuildStage:
    """Helper: create a BuildStage with an optional build back-reference."""
    rec = record or next(r for r in all_records if r.type_name == "Stage")
    return BuildStage(rec, all_records, build=build or _make_build())


def _make_tl_phase(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    stage: BuildStage | None = None,
) -> BuildPhase:
    """Helper: create a BuildPhase with an optional stage back-reference."""
    rec = record or next(r for r in all_records if r.type_name == "Phase")
    return BuildPhase(rec, all_records, stage=stage or _make_tl_stage(all_records))


def _make_tl_job(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    stage: BuildStage | None = None,
    phase: BuildPhase | None = None,
) -> BuildJob:
    """Helper: create a BuildJob with stage/phase back-references."""
    rec = record or next(r for r in all_records if r.type_name == "Job")
    return BuildJob(
        rec, all_records, stage=stage or _make_tl_stage(all_records), phase=phase
    )


class TestBuildTimeline:
    # ------------------------------------------------------------------
    # Build.iter_stages
    # ------------------------------------------------------------------

    def test_iter_stages_yields_only_stages(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stages = list(_make_build().iter_stages())
        assert len(stages) == 1
        assert isinstance(stages[0], BuildStage)

    def test_iter_stages_name_and_id(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        assert stage.name == "Build Stage"
        assert stage.id == STAGE_ID

    def test_iter_stages_state_and_result(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        assert stage.state == BuildRecordState.COMPLETED
        assert stage.result is not None

    def test_stage_time_and_counts_and_log(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        assert stage.start_time is not None
        assert stage.finish_time is not None
        assert stage.error_count == 0
        assert stage.warning_count == 0
        assert stage.issues == []
        assert stage.log is None

    def test_iter_stages_info_is_raw_record(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        assert isinstance(stage.info, BuildRecordInfo)
        assert stage.info.id == STAGE_ID

    def test_iter_stages_empty_when_no_stages(self) -> None:
        task_only = [_record(TASK_ID, "Task", "t", parent_id=JOB_ID)]
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(task_only)
            stages = list(_make_build().iter_stages())
        assert stages == []

    # ------------------------------------------------------------------
    # BuildStage parent back-reference
    # ------------------------------------------------------------------

    def test_stage_build_backref(self) -> None:
        build = _make_build()
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(build.iter_stages())
        assert stage.build is build

    # ------------------------------------------------------------------
    # BuildStage.iter_jobs — direct parent
    # ------------------------------------------------------------------

    def test_stage_iter_jobs_direct(self) -> None:
        all_records = _make_all_records(use_phase=False)
        stage = _make_tl_stage(all_records)
        jobs = list(stage.iter_jobs())
        assert len(jobs) == 1
        assert isinstance(jobs[0], BuildJob)
        assert jobs[0].name == "CI Job"

    def test_stage_iter_jobs_via_phase(self) -> None:
        all_records = _make_all_records(use_phase=True)
        stage = _make_tl_stage(all_records)
        jobs = list(stage.iter_jobs())
        assert len(jobs) == 1
        assert jobs[0].id == JOB_ID

    def test_stage_iter_jobs_excludes_other_stage_jobs(self) -> None:
        other_stage_id = uuid4()
        other_job_id = uuid4()
        all_records = [
            _record(STAGE_ID, "Stage", "Stage A"),
            _record(JOB_ID, "Job", "Job A", parent_id=STAGE_ID),
            _record(other_stage_id, "Stage", "Stage B"),
            _record(other_job_id, "Job", "Job B", parent_id=other_stage_id),
        ]
        stage_a = _make_tl_stage(all_records, record=all_records[0])
        jobs = list(stage_a.iter_jobs())
        assert len(jobs) == 1
        assert jobs[0].id == JOB_ID

    # ------------------------------------------------------------------
    # BuildJob properties and parent back-references
    # ------------------------------------------------------------------

    def test_job_properties(self) -> None:
        all_records = _make_all_records()
        job = _make_tl_job(all_records)
        assert job.id == JOB_ID
        assert job.name == "CI Job"
        assert job.state == BuildRecordState.COMPLETED
        assert job.result is not None
        assert job.start_time is not None
        assert job.finish_time is not None
        assert job.worker_name == "Hosted Agent"
        assert job.error_count == 0
        assert job.warning_count == 0
        assert job.issues == []
        assert job.log is None

    def test_job_info_is_raw_record(self) -> None:
        all_records = _make_all_records()
        job_record = next(r for r in all_records if r.type_name == BuildRecordType.JOB)
        job = _make_tl_job(all_records, record=job_record)
        assert job.info is job_record

    def test_job_stage_backref(self) -> None:
        all_records = _make_all_records()
        stage = _make_tl_stage(all_records)
        job = next(stage.iter_jobs())
        assert job.stage is stage

    def test_job_phase_backref_none_for_direct_jobs(self) -> None:
        all_records = _make_all_records(use_phase=False)
        stage = _make_tl_stage(all_records)
        job = next(stage.iter_jobs())
        assert job.phase is None

    def test_job_phase_backref_set_for_yaml_pipelines(self) -> None:
        all_records = _make_all_records(use_phase=True)
        stage = _make_tl_stage(all_records)
        job = next(stage.iter_jobs())
        assert isinstance(job.phase, BuildPhase)
        assert job.phase.id == PHASE_ID

    # ------------------------------------------------------------------
    # BuildJob.iter_tasks
    # ------------------------------------------------------------------

    def test_job_iter_tasks(self) -> None:
        all_records = _make_all_records()
        job = _make_tl_job(all_records)
        tasks = list(job.iter_tasks())
        assert len(tasks) == 1
        assert isinstance(tasks[0], BuildTask)
        assert tasks[0].name == "Run tests"

    def test_job_iter_tasks_excludes_other_job_tasks(self) -> None:
        other_job_id = uuid4()
        other_task_id = uuid4()
        all_records = [
            _record(JOB_ID, "Job", "Job A"),
            _record(TASK_ID, "Task", "Task A", parent_id=JOB_ID),
            _record(other_job_id, "Job", "Job B"),
            _record(other_task_id, "Task", "Task B", parent_id=other_job_id),
        ]
        stage = _make_tl_stage(all_records, record=_record(STAGE_ID, "Stage", "S"))
        job_a = _make_tl_job(all_records, record=all_records[0], stage=stage)
        tasks = list(job_a.iter_tasks())
        assert len(tasks) == 1
        assert tasks[0].id == TASK_ID

    # ------------------------------------------------------------------
    # BuildTask properties and parent back-references
    # ------------------------------------------------------------------

    def test_task_properties(self) -> None:
        task_record = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
        task = BuildTask(task_record)
        assert task.id == TASK_ID
        assert task.name == "Run tests"
        assert task.state == BuildRecordState.COMPLETED
        assert task.result is not None
        assert task.error_count == 0
        assert task.warning_count == 0
        assert task.issues == []
        assert task.log is None

    def test_task_resolve_raises_without_record(self) -> None:
        task = BuildTask()
        with pytest.raises(RuntimeError, match="No timeline record available"):
            _ = task.id

    def test_task_info_is_raw_record(self) -> None:
        task_record = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
        task = BuildTask(task_record)
        assert task.info is task_record

    def test_task_start_and_finish_time(self) -> None:
        task_record = _record(TASK_ID, "Task", "t", parent_id=JOB_ID)
        task = BuildTask(task_record)
        assert task.start_time is not None
        assert task.finish_time is not None

    def test_task_job_backref(self) -> None:
        all_records = _make_all_records()
        stage = _make_tl_stage(all_records)
        job = next(stage.iter_jobs())
        task = next(job.iter_tasks())
        assert task.job is job

    def test_task_job_backref_none_when_not_set(self) -> None:
        task_record = _record(TASK_ID, "Task", "t", parent_id=JOB_ID)
        task = BuildTask(task_record)  # no job arg
        assert task.job is None

    # ------------------------------------------------------------------
    # BuildStage.iter_phases
    # ------------------------------------------------------------------

    def test_stage_iter_phases_classic_pipeline(self) -> None:
        # Classic pipelines have no Phase records
        all_records = _make_all_records(use_phase=False)
        stage = _make_tl_stage(all_records)
        assert list(stage.iter_phases()) == []

    def test_stage_iter_phases_yaml_pipeline(self) -> None:
        all_records = _make_all_records(use_phase=True)
        stage = _make_tl_stage(all_records)
        phases = list(stage.iter_phases())
        assert len(phases) == 1
        assert isinstance(phases[0], BuildPhase)
        assert phases[0].id == PHASE_ID
        assert phases[0].name == "__default"

    def test_stage_iter_phases_excludes_other_stage_phases(self) -> None:
        other_stage_id = uuid4()
        other_phase_id = uuid4()
        all_records = [
            _record(STAGE_ID, "Stage", "Stage A"),
            _record(PHASE_ID, "Phase", "Phase A", parent_id=STAGE_ID),
            _record(other_stage_id, "Stage", "Stage B"),
            _record(other_phase_id, "Phase", "Phase B", parent_id=other_stage_id),
        ]
        stage_a = _make_tl_stage(all_records, record=all_records[0])
        phases = list(stage_a.iter_phases())
        assert len(phases) == 1
        assert phases[0].id == PHASE_ID

    # ------------------------------------------------------------------
    # BuildPhase properties and iter_jobs
    # ------------------------------------------------------------------

    def test_phase_properties(self) -> None:
        all_records = _make_all_records(use_phase=True)
        phase = _make_tl_phase(all_records)
        assert phase.id == PHASE_ID
        assert phase.name == "__default"
        assert phase.state == BuildRecordState.COMPLETED
        assert phase.result is not None
        assert phase.start_time is not None
        assert phase.finish_time is not None
        assert phase.error_count == 0
        assert phase.warning_count == 0
        assert phase.issues == []
        assert phase.log is None

    def test_phase_info_is_raw_record(self) -> None:
        all_records = _make_all_records(use_phase=True)
        phase_record = next(
            r for r in all_records if r.type_name == BuildRecordType.PHASE
        )
        phase = _make_tl_phase(all_records, record=phase_record)
        assert phase.info is phase_record

    def test_phase_stage_backref(self) -> None:
        all_records = _make_all_records(use_phase=True)
        stage = _make_tl_stage(all_records)
        phase = next(stage.iter_phases())
        assert phase.stage is stage

    def test_phase_iter_jobs(self) -> None:
        all_records = _make_all_records(use_phase=True)
        phase = _make_tl_phase(all_records)
        jobs = list(phase.iter_jobs())
        assert len(jobs) == 1
        assert jobs[0].id == JOB_ID

    def test_phase_iter_jobs_empty_for_direct_stage_jobs(self) -> None:
        # Phase record exists but job is parented to stage, not phase
        all_records = [
            _record(STAGE_ID, "Stage", "Stage A"),
            _record(PHASE_ID, "Phase", "Phase A", parent_id=STAGE_ID),
            _record(JOB_ID, "Job", "Job A", parent_id=STAGE_ID),  # direct to stage
        ]
        stage = _make_tl_stage(all_records, record=all_records[0])
        phase = _make_tl_phase(all_records, record=all_records[1], stage=stage)
        assert list(phase.iter_jobs()) == []

    # ------------------------------------------------------------------
    # Full traversal: stage → phase → job → task
    # ------------------------------------------------------------------

    def test_full_traversal_via_phases(self) -> None:
        all_records = _make_all_records(use_phase=True)
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        phases = list(stage.iter_phases())
        assert len(phases) == 1
        jobs = list(phases[0].iter_jobs())
        assert len(jobs) == 1
        tasks = list(jobs[0].iter_tasks())
        assert len(tasks) == 1
        assert tasks[0].name == "Run tests"

    def test_full_traversal_direct_jobs(self) -> None:
        all_records = _make_all_records(use_phase=False)
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        jobs = list(stage.iter_jobs())
        assert len(jobs) == 1
        tasks = list(jobs[0].iter_tasks())
        assert len(tasks) == 1

    def test_stage_get_log_text_none_when_no_log(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        assert stage.get_log_text() is None

    def test_stage_get_log_text_delegates_to_build(self) -> None:
        log_info = BuildLogInfo.model_validate(
            {
                "id": 5,
                "type": "Container",
                "url": "https://dev.azure.com/testorg/_apis/build/builds/100/logs/5",
            }
        )
        stage_record = _record(STAGE_ID, "Stage", "Build Stage")
        stage_record.log = log_info
        all_records = [stage_record]
        with (
            patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter(all_records)
            mock_log.return_value = "stage log text"
            stage = next(_make_build().iter_stages())
            text = stage.get_log_text()
        assert text == "stage log text"
        assert mock_log.call_args.args[1] == 5

    def test_job_get_log_text_none_when_no_log(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        job = next(stage.iter_jobs())
        assert job.get_log_text() is None

    def test_job_get_log_text_delegates_to_build(self) -> None:
        log_info = BuildLogInfo.model_validate(
            {
                "id": 6,
                "type": "Container",
                "url": "https://dev.azure.com/testorg/_apis/build/builds/100/logs/6",
            }
        )
        job_record = _record(JOB_ID, "Job", "CI Job", parent_id=STAGE_ID)
        job_record.log = log_info
        all_records = [_record(STAGE_ID, "Stage", "Build Stage"), job_record]
        with (
            patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter(all_records)
            mock_log.return_value = "job log text"
            stage = next(_make_build().iter_stages())
            job = next(stage.iter_jobs())
            text = job.get_log_text()
        assert text == "job log text"
        assert mock_log.call_args.args[1] == 6

    def test_task_get_log_text_none_when_no_log(self) -> None:
        all_records = _make_all_records()
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            stage = next(_make_build().iter_stages())
        task = next(next(stage.iter_jobs()).iter_tasks())
        assert task.get_log_text() is None

    def test_task_get_log_text_none_when_job_is_none(self) -> None:
        log_info = BuildLogInfo.model_validate(
            {
                "id": 8,
                "type": "Container",
                "url": "https://dev.azure.com/testorg/_apis/build/builds/100/logs/8",
            }
        )
        task_record = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
        task_record.log = log_info
        task = BuildTask(task_record)  # no job arg — _job is None
        assert task.get_log_text() is None

    def test_task_get_log_text_delegates_to_build(self) -> None:
        log_info = BuildLogInfo.model_validate(
            {
                "id": 7,
                "type": "Container",
                "url": "https://dev.azure.com/testorg/_apis/build/builds/100/logs/7",
            }
        )
        task_record = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
        task_record.log = log_info
        all_records = [
            _record(STAGE_ID, "Stage", "Build Stage"),
            _record(JOB_ID, "Job", "CI Job", parent_id=STAGE_ID),
            task_record,
        ]
        with (
            patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter(all_records)
            mock_log.return_value = "task log text"
            stage = next(_make_build().iter_stages())
            task = next(next(stage.iter_jobs()).iter_tasks())
            text = task.get_log_text()
        assert text == "task log text"
        assert mock_log.call_args.args[1] == 7


# ---------------------------------------------------------------------------
# ActiveBuildTask tests
# ---------------------------------------------------------------------------

HUB_NAME = "build"
PLAN_ID: PlanId = uuid4()
TIMELINE_ID: TimelineId = uuid4()
ACTIVE_JOB_ID: JobId = uuid4()
ACTIVE_BUILD_ID: BuildId = 42
TASK_INSTANCE_ID: TaskId = uuid4()


def _make_active_task(build: Build | None = None) -> ActiveBuildTask:
    return ActiveBuildTask(
        build or _make_build(),
        hub_name=HUB_NAME,
        plan_id=PLAN_ID,
        timeline_id=TIMELINE_ID,
        job_id=ACTIVE_JOB_ID,
        task_instance_id=TASK_INSTANCE_ID,
    )


def _task_record(log_id: int | None = None) -> BuildRecordInfo:
    """Build a Task-type timeline record with an optional log entry."""
    raw_log = (
        {
            "id": log_id,
            "type": "Container",
            "url": f"https://dev.azure.com/testorg/_apis/build/builds/{ACTIVE_BUILD_ID}/logs/1",
        }
        if log_id is not None
        else None
    )
    return BuildRecordInfo.model_validate(
        {
            "attempt": 1,
            "changeId": None,
            "currentOperation": None,
            "details": None,
            "finishTime": NOW_TS,
            "id": str(TASK_INSTANCE_ID),
            "identifier": None,
            "lastModified": NOW_TS,
            "log": raw_log,
            "name": "My Task",
            "refName": None,
            "parentId": str(ACTIVE_JOB_ID),
            "percentComplete": None,
            "previousAttempts": [],
            "result": "succeeded",
            "resultCode": None,
            "startTime": NOW_TS,
            "state": "completed",
            "task": None,
            "type": "Task",
            "url": None,
            "workerName": None,
        }
    )


class TestActiveBuildTask:
    # ------------------------------------------------------------------
    # Navigation (zero-cost)
    # ------------------------------------------------------------------

    def test_build_property(self) -> None:
        build = _make_build()
        task = _make_active_task(build)
        assert task.build is build

    def test_project_property(self) -> None:
        build = _make_build()
        task = _make_active_task(build)
        assert task.project is build.project

    def test_org_property(self) -> None:
        build = _make_build()
        task = _make_active_task(build)
        assert task.org is build.org

    # ------------------------------------------------------------------
    # Build factory
    # ------------------------------------------------------------------

    def test_factory_on_build_returns_active_build_task(self) -> None:
        build = _make_build()
        task = build.get_active_build_task(
            hub_name=HUB_NAME,
            plan_id=PLAN_ID,
            timeline_id=TIMELINE_ID,
            job_id=ACTIVE_JOB_ID,
            task_instance_id=TASK_INSTANCE_ID,
        )
        assert isinstance(task, ActiveBuildTask)
        assert task.build is build

    # ------------------------------------------------------------------
    # Inherited read properties (lazy via _resolve)
    # ------------------------------------------------------------------

    def test_inherits_task_read_properties(self) -> None:
        record = _task_record()
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.return_value = iter([record])
            task = _make_active_task()
            assert task.name == "My Task"
            assert task.id == TASK_INSTANCE_ID
            assert task.error_count == 0

    def test_resolve_caches_record(self) -> None:
        record = _task_record()
        task = _make_active_task()
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.return_value = iter([record])
            _ = task.name
            _ = task.state  # second access — must not re-fetch
        assert mock_iter.call_count == 1

    # ------------------------------------------------------------------
    # refresh
    # ------------------------------------------------------------------

    def test_refresh_clears_record_cache(self) -> None:
        record = _task_record()
        task = _make_active_task()
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.side_effect = [iter([record]), iter([record])]
            _ = task.name
            task.refresh()
            _ = task.name
        assert mock_iter.call_count == 2

    # ------------------------------------------------------------------
    # get_record
    # ------------------------------------------------------------------

    def test_get_record_returns_matching_task(self) -> None:
        record = _task_record()
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.return_value = iter([record])
            result = _make_active_task().get_record()
        assert result.id == TASK_INSTANCE_ID

    def test_get_record_raises_when_not_found(self) -> None:
        other_id = uuid4()
        other_record = _record(other_id, "Task", "Other Task", parent_id=JOB_ID)
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.return_value = iter([other_record])
            with pytest.raises(ValueError, match=str(TASK_INSTANCE_ID)):
                _make_active_task().get_record()

    # ------------------------------------------------------------------
    # get_job
    # ------------------------------------------------------------------

    def test_get_job_returns_build_job(self) -> None:
        job_record = _record(ACTIVE_JOB_ID, "Job", "My Job", parent_id=STAGE_ID)
        all_records = [
            _record(STAGE_ID, "Stage", "Stage A"),
            job_record,
        ]
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            job = _make_active_task().get_job()
        assert isinstance(job, BuildJob)
        assert job.id == ACTIVE_JOB_ID

    def test_get_job_skips_non_matching_jobs(self) -> None:
        other_job_id = uuid4()
        all_records = [
            _record(STAGE_ID, "Stage", "Stage A"),
            _record(other_job_id, "Job", "Other Job", parent_id=STAGE_ID),
            _record(ACTIVE_JOB_ID, "Job", "My Job", parent_id=STAGE_ID),
        ]
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            job = _make_active_task().get_job()
        assert job.id == ACTIVE_JOB_ID

    def test_get_job_raises_when_not_found(self) -> None:
        all_records = [_record(STAGE_ID, "Stage", "Stage A")]
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter(all_records)
            with pytest.raises(ValueError, match=str(ACTIVE_JOB_ID)):
                _make_active_task().get_job()

    # ------------------------------------------------------------------
    # send_feed
    # ------------------------------------------------------------------

    def test_send_feed_calls_high_send_job_feed(self) -> None:
        with patch("pyado.oop.active_build_task.high.send_job_feed") as mock_feed:
            _make_active_task().send_feed(["line 1", "line 2"])
        assert mock_feed.call_count == 1
        _, messages = mock_feed.call_args.args
        assert messages == ["line 1", "line 2"]

    # ------------------------------------------------------------------
    # send_log
    # ------------------------------------------------------------------

    def test_send_log_calls_post_job_logs(self) -> None:
        record = _task_record(log_id=5)
        with (
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.active_build_task.raw.get_log_api_call"),
            patch("pyado.oop.active_build_task.raw.post_job_logs") as mock_logs,
        ):
            mock_iter.return_value = iter([record])
            _make_active_task().send_log("hello")
        assert mock_logs.call_count == 1
        _, message = mock_logs.call_args.args
        assert message == "hello"

    def test_send_log_caches_log_id(self) -> None:
        record = _task_record(log_id=7)
        task = _make_active_task()
        with (
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.active_build_task.raw.get_log_api_call"),
            patch("pyado.oop.active_build_task.raw.post_job_logs"),
        ):
            mock_iter.return_value = iter([record])
            task.send_log("first")
            # second call must not re-fetch the timeline records
            task.send_log("second")
        assert mock_iter.call_count == 1

    def test_send_log_raises_when_no_log(self) -> None:
        record = _task_record(log_id=None)
        with patch(
            "pyado.oop.active_build_task.raw.iter_timeline_records"
        ) as mock_iter:
            mock_iter.return_value = iter([record])
            with pytest.raises(RuntimeError, match="no log"):
                _make_active_task().send_log("hello")

    # ------------------------------------------------------------------
    # send_message
    # ------------------------------------------------------------------

    def test_send_message_writes_feed_and_log(self) -> None:
        record = _task_record(log_id=3)
        with (
            patch("pyado.oop.active_build_task.high.send_job_feed") as mock_feed,
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.active_build_task.raw.get_log_api_call"),
            patch("pyado.oop.active_build_task.raw.post_job_logs") as mock_logs,
        ):
            mock_iter.return_value = iter([record])
            _make_active_task().send_message(["a", "b"])
        assert mock_feed.call_count == 1
        assert mock_logs.call_count == 2

    # ------------------------------------------------------------------
    # add_issues
    # ------------------------------------------------------------------

    def test_add_issues_patches_timeline(self) -> None:
        record = _task_record()
        issue = BuildIssue(message="boom", type=BuildIssueType.ERROR)
        with (
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch(
                "pyado.oop.active_build_task.high.update_timeline_records"
            ) as mock_update,
        ):
            mock_iter.return_value = iter([record])
            _make_active_task().add_issues([issue])
        assert mock_update.call_count == 1
        _, records = mock_update.call_args.args
        assert len(records) == 1
        assert records[0].issues == [issue]

    # ------------------------------------------------------------------
    # complete
    # ------------------------------------------------------------------

    def test_complete_succeeded_sends_event(self) -> None:
        with patch("pyado.oop.active_build_task.high.send_job_event") as mock_event:
            _make_active_task().complete(succeeded=True)
        assert mock_event.call_count == 1
        _, task_id, job_id, _event_name, event_result = mock_event.call_args.args
        assert task_id == TASK_INSTANCE_ID
        assert job_id == ACTIVE_JOB_ID
        assert event_result == "succeeded"

    def test_complete_failed_sends_event(self) -> None:
        with patch("pyado.oop.active_build_task.high.send_job_event") as mock_event:
            _make_active_task().complete(succeeded=False)
        _, _task_id, _job_id, _event_name, event_result = mock_event.call_args.args
        assert event_result == "failed"


# ---------------------------------------------------------------------------
# OOP — WIT query methods on Project
# ---------------------------------------------------------------------------


def _make_wit_query(name: str = "My Queries") -> WorkItemQuery:
    return WorkItemQuery.model_validate(
        {"id": "00000000-0000-0000-0000-000000000001", "name": name}
    )


class TestProjectQueryTree:
    def test_get_query_tree_delegates(self) -> None:
        queries = [_make_wit_query()]
        with patch("pyado.oop.project.raw.get_query_tree") as mock_get:
            mock_get.return_value = queries
            result = _make_project().get_query_tree()
        assert result is queries
        mock_get.assert_called_once()

    def test_get_query_tree_forwards_depth_and_expand(self) -> None:
        with patch("pyado.oop.project.raw.get_query_tree") as mock_get:
            mock_get.return_value = _make_wit_query()
            _make_project().get_query_tree(depth=3, expand=WorkItemQueryExpand.MINIMAL)
        call = mock_get.call_args
        assert call.kwargs["depth"] == 3
        assert call.kwargs["expand"] == WorkItemQueryExpand.MINIMAL

    def test_get_query_tree_defaults(self) -> None:
        with patch("pyado.oop.project.raw.get_query_tree") as mock_get:
            mock_get.return_value = _make_wit_query()
            _make_project().get_query_tree()
        call = mock_get.call_args
        assert call.kwargs["depth"] == 2
        assert call.kwargs["expand"] == WorkItemQueryExpand.ALL

    def test_get_query_folder_delegates(self) -> None:
        folder_id = "00000000-0000-0000-0000-000000000002"
        with patch("pyado.oop.project.raw.get_query_folder") as mock_get:
            mock_get.return_value = _make_wit_query("Shared Queries")
            result = _make_project().get_query_folder(folder_id)
        assert isinstance(result, WorkItemQuery)
        assert mock_get.call_args.args[1] == folder_id

    def test_get_query_folder_forwards_depth_and_expand(self) -> None:
        folder_id = "00000000-0000-0000-0000-000000000002"
        with patch("pyado.oop.project.raw.get_query_folder") as mock_get:
            mock_get.return_value = _make_wit_query()
            _make_project().get_query_folder(
                folder_id, depth=4, expand=WorkItemQueryExpand.CLAUSES
            )
        call = mock_get.call_args
        assert call.kwargs["depth"] == 4
        assert call.kwargs["expand"] == WorkItemQueryExpand.CLAUSES


# ---------------------------------------------------------------------------
# OOP — Identity methods on Organization
# ---------------------------------------------------------------------------


def _make_identity_info(uid: str = "id-1") -> IdentityInfo:
    return IdentityInfo.model_validate(
        {
            "id": uid,
            "providerDisplayName": "User One",
            "isActive": True,
            "isContainer": False,
        }
    )


def _make_graph_group(name: str = "Readers") -> GraphGroup:
    return GraphGroup.model_validate(
        {
            "displayName": name,
            "descriptor": "vssgp.abc",
            "principalName": f"[TestProject]\\{name}",
            "subjectKind": "group",
        }
    )


class TestOrganizationIdentity:
    def test_get_identities_delegates(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_identities") as mock_ids,
        ):
            mock_call.return_value = _api_call()
            mock_ids.return_value = [_make_identity_info()]
            result = svc.org.get_identities(["vssgp.abc"])
        assert len(result) == 1
        assert isinstance(result[0], IdentityInfo)
        mock_ids.assert_called_once()

    def test_get_identities_uses_org_name_from_url(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.get_identities") as mock_ids,
        ):
            mock_call.return_value = _api_call()
            mock_ids.return_value = []
            svc.org.get_identities([])
        # org name extracted from https://dev.azure.com/testorg → "testorg"
        mock_call.assert_called_once_with(TOKEN, "testorg")

    def test_iter_graph_groups_delegates(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter,
        ):
            mock_call.return_value = _api_call()
            mock_iter.return_value = iter([_make_graph_group()])
            result = list(svc.org.iter_graph_groups())
        assert len(result) == 1
        assert isinstance(result[0], GraphGroup)

    def test_iter_graph_groups_uses_org_name_from_url(self) -> None:
        svc = _make_service()
        with (
            patch("pyado.oop.organization.raw.get_vssps_api_call") as mock_call,
            patch("pyado.oop.organization.raw.iter_graph_groups") as mock_iter,
        ):
            mock_call.return_value = _api_call()
            mock_iter.return_value = iter([])
            list(svc.org.iter_graph_groups())
        mock_call.assert_called_once_with(TOKEN, "testorg")


# ---------------------------------------------------------------------------
# OOP — ACL method on Repository
# ---------------------------------------------------------------------------


def _make_acl() -> AccessControlList:
    return AccessControlList.model_validate(
        {"token": f"repoV2/{PROJECT_ID}/{REPO_ID}", "inheritanceDeny": 0}
    )


class TestRepositoryAcl:
    def test_get_acl_delegates(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = [_make_acl()]
            result = repo.get_acl()
        assert len(result) == 1
        assert isinstance(result[0], AccessControlList)

    def test_get_acl_passes_project_and_repo_ids(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.get_acl()
        call = mock_acl.call_args
        assert call.args[1] == PROJECT_ID
        assert call.args[2] == REPO_ID

    def test_get_acl_uses_org_base_url(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.get_acl()
        org_call = mock_acl.call_args.args[0]
        assert "_apis" not in str(org_call.url)
        assert "testorg" in str(org_call.url)


# ---------------------------------------------------------------------------
# OOP — authorize_resource on Pipeline
# ---------------------------------------------------------------------------


def _make_pipeline_resource_permissions(
    authorized: bool = True,
) -> PipelineResourcePermissions:
    return PipelineResourcePermissions.model_validate(
        {"allPipelines": {"authorized": authorized}}
    )


class TestPipelineAuthorizeResource:
    def test_authorize_resource_delegates(self) -> None:
        pipe = _make_pipeline()
        with patch("pyado.oop.pipeline.raw.post_pipeline_permission") as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            result = pipe.authorize_resource(PipelineResourceType.VARIABLE_GROUP, "42")
        assert isinstance(result, PipelineResourcePermissions)
        mock_post.assert_called_once()

    def test_authorize_resource_passes_pipeline_id(self) -> None:
        pipe = _make_pipeline(pipeline_id=7)
        with patch("pyado.oop.pipeline.raw.post_pipeline_permission") as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            pipe.authorize_resource(PipelineResourceType.ENDPOINT, "svc-conn-1")
        call = mock_post.call_args
        assert call.args[3] == 7  # pipeline_id

    def test_authorize_resource_default_authorized_true(self) -> None:
        pipe = _make_pipeline()
        with patch("pyado.oop.pipeline.raw.post_pipeline_permission") as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            pipe.authorize_resource(PipelineResourceType.QUEUE, "1")
        call = mock_post.call_args
        assert call.kwargs["authorized"] is True

    def test_authorize_resource_can_deauthorize(self) -> None:
        pipe = _make_pipeline()
        with patch("pyado.oop.pipeline.raw.post_pipeline_permission") as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions(
                authorized=False
            )
            pipe.authorize_resource(
                PipelineResourceType.REPOSITORY, "proj/repo", authorized=False
            )
        call = mock_post.call_args
        assert call.kwargs["authorized"] is False


# ---------------------------------------------------------------------------
# Build — cancel / cancel_run
# ---------------------------------------------------------------------------


def _pipeline_run_info(run_id: int = 100, pipeline_id: int = 1) -> PipelineRunInfo:
    return PipelineRunInfo.model_validate(
        {
            "id": run_id,
            "name": f"20240101.{run_id}",
            "state": "canceling",
            "pipeline": {
                "id": pipeline_id,
                "revision": 1,
                "name": "MyPipeline",
                "folder": "\\",
                "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}",
            },
            "createdDate": NOW_ISO,
            "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}/runs/{run_id}",
        }
    )


class TestBuildCancel:
    def test_cancel_delegates(self) -> None:
        build = _make_build()
        cancelled = _build_details()
        with patch("pyado.oop.build.high.cancel_build") as mock_cancel:
            mock_cancel.return_value = cancelled
            result = build.cancel()
        mock_cancel.assert_called_once_with(build.api_call)
        assert result is cancelled

    def test_cancel_run_delegates(self) -> None:
        build = _make_build(build_id=100, pipeline_id=5)
        run_info = _pipeline_run_info(100, 5)
        with patch("pyado.oop.build.high.cancel_pipeline_run") as mock_cancel:
            mock_cancel.return_value = run_info
            result = build.cancel_run()
        mock_cancel.assert_called_once_with(build.project.api_call, 5, 100)
        assert result is run_info

    def test_cancel_run_uses_definition_id(self) -> None:
        build = _make_build(build_id=200, pipeline_id=99)
        with patch("pyado.oop.build.high.cancel_pipeline_run") as mock_cancel:
            mock_cancel.return_value = _pipeline_run_info(200, 99)
            build.cancel_run()
        call = mock_cancel.call_args
        assert call.args[1] == 99  # pipeline_id from definition


# ---------------------------------------------------------------------------
# PullRequest — complete / abandon / set_work_item_refs
# ---------------------------------------------------------------------------


class TestPullRequestLifecycle:
    def test_complete_delegates(self) -> None:
        pr = _make_pr()
        completed = _pr_created()
        with patch("pyado.oop.pull_request.high.complete_pr") as mock_complete:
            mock_complete.return_value = completed
            pr.complete("deadbeef")
        mock_complete.assert_called_once_with(
            pr.api_call, "deadbeef", completion_options=None
        )

    def test_complete_updates_info(self) -> None:
        pr = _make_pr()
        completed = _pr_created()
        completed.status = "completed"
        with patch("pyado.oop.pull_request.high.complete_pr") as mock_complete:
            mock_complete.return_value = completed
            pr.complete("deadbeef")
        assert pr._info is completed

    def test_abandon_delegates(self) -> None:
        pr = _make_pr()
        abandoned = _pr_created()
        abandoned.status = "abandoned"
        with patch("pyado.oop.pull_request.high.abandon_pr") as mock_abandon:
            mock_abandon.return_value = abandoned
            pr.abandon()
        mock_abandon.assert_called_once_with(pr.api_call)

    def test_abandon_updates_info(self) -> None:
        pr = _make_pr()
        abandoned = _pr_created()
        abandoned.status = "abandoned"
        with patch("pyado.oop.pull_request.high.abandon_pr") as mock_abandon:
            mock_abandon.return_value = abandoned
            pr.abandon()
        assert pr._info is abandoned

    def test_set_work_item_refs_delegates(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.pull_request.high.update_pr_work_item_refs"
        ) as mock_update:
            pr.set_work_item_refs([10, 20])
        mock_update.assert_called_once_with(pr.api_call, [10, 20])


# ---------------------------------------------------------------------------
# Repository — get_last_commit_touching_file
# ---------------------------------------------------------------------------


class TestRepositoryGetLastCommit:
    def test_delegates_to_high(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repository.high.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "abc123"
            result = repo.get_last_commit_touching_file("/src/foo.py", "abc123")
        mock_fn.assert_called_once_with(repo.api_call, "/src/foo.py", "abc123")
        assert result == "abc123"

    def test_returns_fallback_when_no_commit_found(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repository.high.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "fallback-sha"
            result = repo.get_last_commit_touching_file("/missing.py", "fallback-sha")
        assert result == "fallback-sha"


# ---------------------------------------------------------------------------
# Project — approve_pipeline / variable groups
# ---------------------------------------------------------------------------


def _variable_group_info(group_id: int = 1, name: str = "MyVars") -> VariableGroupInfo:
    user_id = str(uuid4())
    return VariableGroupInfo.model_validate(
        {
            "id": group_id,
            "name": name,
            "type": "Vsts",
            "variables": {"FOO": {"value": "bar"}},
            "createdBy": {
                "id": user_id,
                "displayName": "User",
                "uniqueName": "user@example.com",
            },
            "createdOn": NOW_ISO,
            "modifiedBy": {
                "id": user_id,
                "displayName": "User",
                "uniqueName": "user@example.com",
            },
            "modifiedOn": NOW_ISO,
            "isShared": False,
            "variableGroupProjectReferences": [],
        }
    )


def _make_variable_group(group_id: int = 1, name: str = "MyVars") -> VariableGroup:
    proj = _make_project()
    api_call = _api_call(
        f"{ORG_URL}/TestProject/_apis/distributedtask/variablegroups/{group_id}"
    )
    return VariableGroup(proj, api_call, _variable_group_info(group_id, name))


class TestProjectApprovePipeline:
    def test_approve_pipeline_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.high.approve_pipeline") as mock_approve:
            proj.approve_pipeline("approval-uuid-123")
        mock_approve.assert_called_once_with(
            proj.api_call, "approval-uuid-123", comment=""
        )

    def test_approve_pipeline_passes_comment(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.high.approve_pipeline") as mock_approve:
            proj.approve_pipeline("uuid", comment="LGTM")
        call = mock_approve.call_args
        assert call.kwargs["comment"] == "LGTM"


class TestProjectVariableGroups:
    def test_iter_variable_groups_yields_wrappers(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(1, "MyVars")
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            result = list(proj.iter_variable_groups())
        assert len(result) == 1
        assert isinstance(result[0], VariableGroup)
        assert result[0].name == "MyVars"

    def test_get_variable_group_found_by_name(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(5, "ProdVars")
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            vg = proj.get_variable_group("ProdVars")
        assert vg.name == "ProdVars"

    def test_get_variable_group_not_found_raises(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([])
            mock_ac.return_value = _api_call()
            with pytest.raises(ValueError, match="NoSuchGroup"):
                proj.get_variable_group("NoSuchGroup")

    def test_get_variable_group_by_id_found(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(7, "DevVars")
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            vg = proj.get_variable_group_by_id(7)
        assert vg.id == 7

    def test_get_variable_group_by_id_not_found_raises(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([])
            mock_ac.return_value = _api_call()
            with pytest.raises(ValueError, match="999"):
                proj.get_variable_group_by_id(999)

    def test_get_variable_group_skips_non_matching_name(self) -> None:
        proj = _make_project()
        vg_a = _variable_group_info(1, "Alpha")
        vg_b = _variable_group_info(2, "Beta")
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([vg_a, vg_b])
            mock_ac.return_value = _api_call()
            vg = proj.get_variable_group("Beta")
        assert vg.name == "Beta"

    def test_get_variable_group_by_id_skips_non_matching(self) -> None:
        proj = _make_project()
        vg_a = _variable_group_info(1, "Alpha")
        vg_b = _variable_group_info(2, "Beta")
        with (
            patch("pyado.oop.project.raw.iter_variable_group_details") as mock_iter,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_iter.return_value = iter([vg_a, vg_b])
            mock_ac.return_value = _api_call()
            vg = proj.get_variable_group_by_id(2)
        assert vg.id == 2


# ---------------------------------------------------------------------------
# VariableGroup
# ---------------------------------------------------------------------------


class TestVariableGroup:
    def test_id(self) -> None:
        assert _make_variable_group(group_id=3).id == 3

    def test_name(self) -> None:
        assert _make_variable_group(name="StagingVars").name == "StagingVars"

    def test_variables(self) -> None:
        vg = _make_variable_group()
        assert "FOO" in vg.variables
        assert vg.variables["FOO"].value == "bar"

    def test_info_returns_info(self) -> None:
        vg = _make_variable_group(group_id=9)
        assert vg.info.id == 9

    def test_api_call_accessible(self) -> None:
        api = _api_call()
        proj = _make_project()
        vg = VariableGroup(proj, api, _variable_group_info())
        assert vg.api_call is api

    def test_project_reference(self) -> None:
        proj = _make_project()
        vg = VariableGroup(proj, _api_call(), _variable_group_info())
        assert vg.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        vg = VariableGroup(proj, _api_call(), _variable_group_info())
        assert vg.org is svc.org

    def test_update_delegates(self) -> None:
        vg = _make_variable_group()
        new_vars = {"BAR": VariableInfo(value="baz")}
        updated_info = _variable_group_info()
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = updated_info
            vg.update(new_vars)
        mock_upd.assert_called_once()
        call = mock_upd.call_args
        assert call.args[2] is new_vars

    def test_update_uses_current_name_by_default(self) -> None:
        vg = _make_variable_group(name="OrigName")
        updated_info = _variable_group_info(name="OrigName")
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = updated_info
            vg.update({})
        call = mock_upd.call_args
        assert call.args[1] == "OrigName"

    def test_update_with_new_name(self) -> None:
        vg = _make_variable_group(name="OldName")
        updated_info = _variable_group_info(name="NewName")
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = updated_info
            vg.update({}, name="NewName")
        call = mock_upd.call_args
        assert call.args[1] == "NewName"

    def test_update_stores_returned_info(self) -> None:
        vg = _make_variable_group()
        new_info = _variable_group_info(group_id=1, name="Updated")
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = new_info
            vg.update({})
        assert vg._info is new_info

    def test_set_variable_merges_and_updates(self) -> None:
        vg = _make_variable_group()
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.set_variable("NEW_KEY", "new-val")
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert "FOO" in new_vars  # existing variable preserved
        assert "NEW_KEY" in new_vars
        assert new_vars["NEW_KEY"].value == "new-val"

    def test_set_variable_secret_flag(self) -> None:
        vg = _make_variable_group()
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.set_variable("SECRET", "s3cr3t", is_secret=True)
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert new_vars["SECRET"].is_secret is True

    def test_delete_variable_removes_key(self) -> None:
        vg = _make_variable_group()
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = _variable_group_info()
            vg.delete_variable("FOO")
        call = mock_upd.call_args
        new_vars: dict[str, VariableInfo] = call.args[2]
        assert "FOO" not in new_vars

    def test_delete_variable_missing_raises(self) -> None:
        vg = _make_variable_group()
        with pytest.raises(KeyError):
            vg.delete_variable("NONEXISTENT")

    def test_update_uses_existing_project_refs_when_present(self) -> None:
        """_project_refs() returns existing refs when the list is non-empty."""
        proj = _make_project()
        ref = VariableGroupProjectReference.model_validate(
            {
                "name": "MyVars",
                "projectReference": {"id": str(proj.id), "name": proj.name},
            }
        )
        info = VariableGroupInfo.model_validate(
            {
                "id": 1,
                "name": "MyVars",
                "type": "Vsts",
                "variables": {},
                "createdBy": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "displayName": "U",
                    "uniqueName": "u@x.com",
                },
                "createdOn": NOW_ISO,
                "modifiedBy": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "displayName": "U",
                    "uniqueName": "u@x.com",
                },
                "modifiedOn": NOW_ISO,
                "isShared": False,
                "variableGroupProjectReferences": [ref.model_dump(by_alias=True)],
            }
        )
        vg = VariableGroup(proj, _api_call(), info)
        with patch("pyado.oop.variable_group.high.update_variable_group") as mock_upd:
            mock_upd.return_value = info
            vg.update({})
        call = mock_upd.call_args
        passed_refs = call.args[3]
        assert passed_refs == [ref]

    def test_refresh_updates_info(self) -> None:
        vg = _make_variable_group(group_id=1)
        refreshed = _variable_group_info(group_id=1, name="Refreshed")
        with patch(
            "pyado.oop.variable_group.raw.iter_variable_group_details"
        ) as mock_iter:
            mock_iter.return_value = iter([refreshed])
            vg.refresh()
        assert vg._info is refreshed

    def test_refresh_no_match_leaves_info_unchanged(self) -> None:
        vg = _make_variable_group(group_id=1)
        original = vg._info
        with patch(
            "pyado.oop.variable_group.raw.iter_variable_group_details"
        ) as mock_iter:
            mock_iter.return_value = iter([_variable_group_info(group_id=99)])
            vg.refresh()
        assert vg._info is original


# ---------------------------------------------------------------------------
# Iteration and Area helpers
# ---------------------------------------------------------------------------


def _iteration_node(
    node_id: int = 1,
    name: str = "Sprint 1",
    path: str | None = "\\TestProject\\Sprint 1",
    start_date: str | None = "2024-01-01T00:00:00Z",
    finish_date: str | None = "2024-01-14T00:00:00Z",
    children: list[dict[str, Any]] | None = None,
) -> ClassificationNode:
    data: dict[str, Any] = {
        "id": node_id,
        "name": name,
        "structureType": "iteration",
        "hasChildren": children is not None and len(children) > 0,
        "path": path,
    }
    if start_date or finish_date:
        data["attributes"] = {}
        if start_date:
            data["attributes"]["startDate"] = start_date
        if finish_date:
            data["attributes"]["finishDate"] = finish_date
    if children is not None:
        data["children"] = children
    return ClassificationNode.model_validate(data)


def _area_node(
    node_id: int = 10,
    name: str = "Team A",
    path: str | None = "\\TestProject\\Team A",
    children: list[dict[str, Any]] | None = None,
) -> ClassificationNode:
    data: dict[str, Any] = {
        "id": node_id,
        "name": name,
        "structureType": "area",
        "hasChildren": children is not None and len(children) > 0,
        "path": path,
    }
    if children is not None:
        data["children"] = children
    return ClassificationNode.model_validate(data)


def _make_iteration(
    node_id: int = 1,
    name: str = "Sprint 1",
    path: str = "\\TestProject\\Sprint 1",
) -> Iteration:
    return Iteration(_make_project(), _iteration_node(node_id, name, path))


def _make_area(
    node_id: int = 10,
    name: str = "Team A",
    path: str = "\\TestProject\\Team A",
) -> Area:
    return Area(_make_project(), _area_node(node_id, name, path))


# ---------------------------------------------------------------------------
# Iteration tests
# ---------------------------------------------------------------------------


class TestIteration:
    def test_id(self) -> None:
        assert _make_iteration(node_id=5).id == 5

    def test_name(self) -> None:
        assert _make_iteration(name="Sprint 42").name == "Sprint 42"

    def test_path(self) -> None:
        it = _make_iteration(path="\\Proj\\Sprint 1")
        assert it.path == "\\Proj\\Sprint 1"

    def test_start_date(self) -> None:
        it = _make_iteration()
        assert it.start_date == date(2024, 1, 1)

    def test_finish_date(self) -> None:
        it = _make_iteration()
        assert it.finish_date == date(2024, 1, 14)

    def test_start_date_none_when_no_attributes(self) -> None:
        node = _iteration_node(start_date=None, finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.start_date is None

    def test_finish_date_none_when_no_attributes(self) -> None:
        node = _iteration_node(start_date=None, finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.finish_date is None

    def test_start_date_none_when_only_finish_date_set(self) -> None:
        node = _iteration_node(start_date=None, finish_date="2024-01-14T00:00:00Z")
        it = Iteration(_make_project(), node)
        assert it.start_date is None
        assert it.finish_date == date(2024, 1, 14)

    def test_finish_date_none_when_only_start_date_set(self) -> None:
        node = _iteration_node(start_date="2024-01-01T00:00:00Z", finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.start_date == date(2024, 1, 1)
        assert it.finish_date is None

    def test_start_date_none_when_attribute_value_is_none(self) -> None:
        # attributes present but startDate explicitly None
        node = ClassificationNode.model_validate(
            {
                "id": 1,
                "name": "Sprint",
                "structureType": "iteration",
                "hasChildren": False,
                "attributes": {},
            }
        )
        it = Iteration(_make_project(), node)
        assert it.start_date is None

    def test_patch_with_no_path_in_info(self) -> None:
        node = ClassificationNode.model_validate(
            {
                "id": 1,
                "name": "Sprint",
                "structureType": "iteration",
                "hasChildren": False,
            }
        )
        it = Iteration(_make_project(), node)
        updated = _iteration_node()
        with patch("pyado.oop.iteration.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = updated
            it.patch(start_date=date(2024, 1, 1))
        call = mock_patch.call_args
        assert call.args[1] is None

    def test_info_returns_node(self) -> None:
        node = _iteration_node(node_id=7)
        it = Iteration(_make_project(), node)
        assert it.info is node

    def test_project_reference(self) -> None:
        proj = _make_project()
        it = Iteration(proj, _iteration_node())
        assert it.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        it = Iteration(proj, _iteration_node())
        assert it.org is svc.org

    def test_children_empty_when_none(self) -> None:
        node = _iteration_node()
        it = Iteration(_make_project(), node)
        assert it.children == []

    def test_children_wraps_child_nodes(self) -> None:
        child_data = {
            "id": 2,
            "name": "Week 1",
            "structureType": "iteration",
            "hasChildren": False,
        }
        node = _iteration_node(children=[child_data])
        it = Iteration(_make_project(), node)
        children = it.children
        assert len(children) == 1
        assert isinstance(children[0], Iteration)
        assert children[0].name == "Week 1"

    def test_patch_delegates_with_relative_path(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        updated = _iteration_node()
        with patch("pyado.oop.iteration.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = updated
            it.patch(start_date=date(2024, 2, 1), finish_date=date(2024, 2, 14))
        call = mock_patch.call_args
        assert call.args[1] == "Sprint 1"  # relative path, project prefix stripped

    def test_patch_updates_info(self) -> None:
        it = _make_iteration()
        updated = _iteration_node(name="Updated")
        with patch("pyado.oop.iteration.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = updated
            it.patch(start_date=date(2024, 2, 1))
        assert it._info is updated

    def test_patch_root_passes_none_path(self) -> None:
        root = _iteration_node(path="\\TestProject")
        it = Iteration(_make_project(), root)
        updated = _iteration_node()
        with patch("pyado.oop.iteration.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = updated
            it.patch(start_date=date(2024, 1, 1))
        call = mock_patch.call_args
        assert call.args[1] is None  # root node → relative path is None


# ---------------------------------------------------------------------------
# Area tests
# ---------------------------------------------------------------------------


class TestArea:
    def test_id(self) -> None:
        assert _make_area(node_id=20).id == 20

    def test_name(self) -> None:
        assert _make_area(name="Backend").name == "Backend"

    def test_path(self) -> None:
        area = _make_area(path="\\Proj\\Backend")
        assert area.path == "\\Proj\\Backend"

    def test_info_returns_node(self) -> None:
        node = _area_node(node_id=15)
        area = Area(_make_project(), node)
        assert area.info is node

    def test_project_reference(self) -> None:
        proj = _make_project()
        area = Area(proj, _area_node())
        assert area.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        area = Area(proj, _area_node())
        assert area.org is svc.org

    def test_children_empty_when_none(self) -> None:
        area = _make_area()
        assert area.children == []

    def test_children_wraps_child_nodes(self) -> None:
        child_data = {
            "id": 11,
            "name": "Sub-team",
            "structureType": "area",
            "hasChildren": False,
        }
        node = _area_node(children=[child_data])
        area = Area(_make_project(), node)
        children = area.children
        assert len(children) == 1
        assert isinstance(children[0], Area)
        assert children[0].name == "Sub-team"


# ---------------------------------------------------------------------------
# Project — iteration and area methods
# ---------------------------------------------------------------------------


class TestProjectIterationArea:
    def test_get_iteration_node_returns_iteration(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _iteration_node()
            result = proj.get_iteration_node()
        assert isinstance(result, Iteration)

    def test_get_iteration_node_passes_path(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _iteration_node()
            proj.get_iteration_node("Sprint 1")
        assert mock_get.call_args.args[1] == "Sprint 1"

    def test_get_iteration_node_passes_depth(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _iteration_node()
            proj.get_iteration_node(depth=3)
        assert mock_get.call_args.kwargs["depth"] == 3

    def test_create_iteration_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.create_classification_node") as mock_create:
            mock_create.return_value = "guid-abc"
            result = proj.create_iteration(
                "Sprint 2",
                start_date=date(2024, 2, 1),
                finish_date=date(2024, 2, 14),
            )
        assert result == "guid-abc"
        assert mock_create.call_args.args[1] == "Sprint 2"

    def test_get_area_node_returns_area(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_area_node") as mock_get:
            mock_get.return_value = _area_node()
            result = proj.get_area_node()
        assert isinstance(result, Area)

    def test_get_area_node_passes_path(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_area_node") as mock_get:
            mock_get.return_value = _area_node()
            proj.get_area_node("Team A")
        assert mock_get.call_args.args[1] == "Team A"

    def test_get_area_node_passes_depth(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_area_node") as mock_get:
            mock_get.return_value = _area_node()
            proj.get_area_node(depth=2)
        assert mock_get.call_args.kwargs["depth"] == 2

    def test_create_area_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.create_area_node") as mock_create:
            mock_create.return_value = "guid-xyz"
            result = proj.create_area("Backend")
        assert result == "guid-xyz"
        assert mock_create.call_args.args[1] == "Backend"


# ---------------------------------------------------------------------------
# New OOP method tests (added in gap-fill session)
# ---------------------------------------------------------------------------


def _team_info(team_id: str = "team-001", name: str = "My Team") -> TeamInfo:
    return TeamInfo(id=team_id, name=name, description="A team")


class TestTeam:
    def test_id(self) -> None:
        team = Team(_make_project(), _team_info("abc-123"))
        assert team.id == "abc-123"

    def test_name(self) -> None:
        team = Team(_make_project(), _team_info(name="Alpha"))
        assert team.name == "Alpha"

    def test_info_returns_team_info(self) -> None:
        info = _team_info()
        team = Team(_make_project(), info)
        assert team.info is info

    def test_project_reference(self) -> None:
        proj = _make_project()
        team = Team(proj, _team_info())
        assert team.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        team = Team(proj, _team_info())
        assert team.org is svc.org

    def test_api_call_is_team_scoped(self) -> None:
        proj = _make_project()
        team = Team(proj, _team_info(name="MyTeam"))
        url = team.api_call.url.unicode_string()
        assert "MyTeam" in url


class TestWorkItemNewMethods:
    def test_iter_children_delegates_to_iter_linked(self) -> None:
        wi = _make_wi(10)
        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/20",
            ),
        ]
        with (
            patch("pyado.oop.work_item.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_work_item_info(20)])
            mock_call.return_value = _api_call()
            result = list(wi.iter_children())
        assert len(result) == 1
        assert result[0].id == 20

    def test_delete_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        with patch("pyado.oop.work_item.raw.delete_work_item") as mock_del:
            wi.delete()
        mock_del.assert_called_once_with(wi._api_call)

    def test_update_comment_returns_comment(self) -> None:
        wi = _make_wi(10)
        comment = WorkItemComment.model_validate(
            {
                "id": 3,
                "text": "Updated",
                "version": 2,
                "createdDate": NOW_ISO,
                "modifiedDate": NOW_ISO,
                "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/10/comments/3",
            }
        )
        with patch("pyado.oop.work_item.raw.patch_work_item_comment") as mock_patch:
            mock_patch.return_value = comment
            result = wi.update_comment(3, "Updated")
        mock_patch.assert_called_once_with(wi._api_call, 3, "Updated")
        assert result is comment

    def test_delete_comment_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        with patch("pyado.oop.work_item.raw.delete_work_item_comment") as mock_del:
            wi.delete_comment(5)
        mock_del.assert_called_once_with(wi._api_call, 5)


class TestPullRequestNewMethods:
    def test_update_thread_status_delegates(self) -> None:
        thread_resp = MagicMock(spec=PullRequestThreadResponse)
        with patch("pyado.oop.pull_request.raw.patch_pr_thread") as mock_patch:
            mock_patch.return_value = thread_resp
            result = _make_pr().update_thread_status(7, PullRequestThreadStatus.FIXED)
        mock_patch.assert_called_once()
        assert mock_patch.call_args.args[1] == 7
        assert mock_patch.call_args.args[2] == PullRequestThreadStatus.FIXED
        assert result is thread_resp

    def test_iter_statuses_delegates(self) -> None:
        status = PullRequestStatusInfo.model_validate(
            {
                "state": "succeeded",
                "context": {"name": "ci-check", "genre": None},
            }
        )
        with patch("pyado.oop.pull_request.raw.iter_pr_statuses") as mock_iter:
            mock_iter.return_value = iter([status])
            result = list(_make_pr().iter_statuses())
        assert len(result) == 1
        assert result[0].state == PullRequestStatusState.SUCCEEDED


class TestRepositoryNewMethods:
    def test_get_statistics_returns_branch_statistics(self) -> None:
        stats = BranchStatistics.model_validate(
            {"name": "main", "aheadCount": 2, "behindCount": 0}
        )
        with patch("pyado.oop.repository.raw.get_repository_statistics") as mock_get:
            mock_get.return_value = stats
            result = _make_repo().get_statistics("main")
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "main"
        assert result is stats

    def test_get_pr_for_branch_returns_pull_request(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_prs") as mock_iter,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(11)])
            mock_call.return_value = _api_call()
            result = _make_repo().get_pr_for_branch("feature/x")
        assert result is not None
        assert result.id == 11

    def test_get_pr_for_branch_normalises_short_branch(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_prs") as mock_iter,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1)])
            mock_call.return_value = _api_call()
            _make_repo().get_pr_for_branch("main")
        criteria = mock_iter.call_args.args[1]
        assert criteria.source_ref_name == "refs/heads/main"

    def test_get_pr_for_branch_returns_none_when_no_match(self) -> None:
        with patch("pyado.oop.repository.raw.iter_prs") as mock_iter:
            mock_iter.return_value = iter([])
            result = _make_repo().get_pr_for_branch("no-such-branch")
        assert result is None


class TestBuildRetry:
    def test_retry_returns_new_build(self) -> None:

        new_details = _build_details(build_id=200, pipeline_id=1)
        new_api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/200")
        with (
            patch("pyado.oop.build.high.start_build") as mock_start,
            patch("pyado.oop.build.raw.get_build_api_call") as mock_api,
        ):
            mock_start.return_value = new_details
            mock_api.return_value = new_api_call
            result = _make_build(build_id=100).retry()
        assert isinstance(result, Build)
        assert result.id == 200

    def test_retry_passes_definition_id_and_branch(self) -> None:
        with (
            patch("pyado.oop.build.high.start_build") as mock_start,
            patch("pyado.oop.build.raw.get_build_api_call") as mock_api,
        ):
            mock_start.return_value = _build_details(build_id=200, pipeline_id=5)
            mock_api.return_value = _api_call()
            _make_build(build_id=100, pipeline_id=5).retry()
        assert mock_start.call_args.args[1] == 5
        assert mock_start.call_args.kwargs["source_branch"] == "refs/heads/main"


class TestPipelineGetLatestRun:
    def test_returns_latest_run_when_runs_exist(self) -> None:
        run = PipelineRunInfo.model_validate(
            {
                "id": 99,
                "name": "20240101.1",
                "state": "completed",
                "result": "succeeded",
                "createdDate": NOW_ISO,
                "pipeline": {
                    "id": 7,
                    "revision": 1,
                    "name": "MyPipeline",
                    "folder": "\\",
                    "url": "https://x",
                },
                "url": "https://dev.azure.com/testorg/TestProject/_apis/pipelines/7/runs/99",
            }
        )
        with patch("pyado.oop.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([run])
            result = _make_pipeline().get_latest_run()
        assert result is run

    def test_returns_none_when_no_runs(self) -> None:
        with patch("pyado.oop.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            result = _make_pipeline().get_latest_run()
        assert result is None


class TestProjectNewMethods:
    def test_get_work_items_returns_list_of_work_items(self) -> None:
        proj = _make_project()
        wi_infos = [_work_item_info(1), _work_item_info(2)]
        with (
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_batch.return_value = wi_infos
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            result = proj.get_work_items([1, 2])
        assert len(result) == 2
        assert all(isinstance(item, WorkItem) for item in result)

    def test_get_work_items_passes_ids(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.get_work_items([10, 20, 30])
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.ids == [10, 20, 30]

    def test_iter_teams_yields_team_objects(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.iter_teams") as mock_iter:
            mock_iter.return_value = iter(
                [_team_info("t1", "Team A"), _team_info("t2", "Team B")]
            )
            result = list(proj.iter_teams())
        assert len(result) == 2
        assert all(isinstance(item, Team) for item in result)
        assert result[0].name == "Team A"

    def test_iter_teams_uses_org_api_call(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.iter_teams") as mock_iter:
            mock_iter.return_value = iter([])
            list(proj.iter_teams())
        assert mock_iter.call_args.args[1] == "TestProject"

    def test_get_team_returns_team(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_team") as mock_get:
            mock_get.return_value = _team_info("t1", "DevOps Team")
            result = proj.get_team("DevOps Team")
        assert isinstance(result, Team)
        assert result.name == "DevOps Team"

    def test_get_team_passes_name_or_id(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_team") as mock_get:
            mock_get.return_value = _team_info()
            proj.get_team("team-guid-001")
        assert mock_get.call_args.args[2] == "team-guid-001"


# ---------------------------------------------------------------------------
# Property coverage tests (new properties added in gap-fill session)
# ---------------------------------------------------------------------------


class TestBuildNewProperties:
    def test_result_returns_build_result(self) -> None:
        assert _make_build().result == BuildResult.SUCCEEDED

    def test_source_branch_returns_branch_name(self) -> None:
        assert _make_build().source_branch == "refs/heads/main"

    def test_start_time_returns_none_when_not_set(self) -> None:
        assert _make_build().start_time is None

    def test_finish_time_returns_none_when_not_set(self) -> None:
        assert _make_build().finish_time is None


class TestCommitNewProperties:
    def _commit_with_author(self) -> Commit:
        ref = GitCommitRef.model_validate(
            {
                "commitId": "abc123",
                "comment": "msg",
                "commentTruncated": False,
                "author": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": NOW_ISO,
                },
                "committer": {
                    "name": "Bob",
                    "email": "bob@example.com",
                    "date": NOW_ISO,
                },
            }
        )
        return Commit(_make_repo(), ref)

    def test_author_name_returns_name(self) -> None:
        assert self._commit_with_author().author_name == "Alice"

    def test_author_email_returns_email(self) -> None:
        assert self._commit_with_author().author_email == "alice@example.com"

    def test_author_date_returns_datetime(self) -> None:
        assert self._commit_with_author().author_date is not None

    def test_committer_name_returns_name(self) -> None:
        assert self._commit_with_author().committer_name == "Bob"

    def test_committer_email_returns_email(self) -> None:
        assert self._commit_with_author().committer_email == "bob@example.com"

    def test_committer_date_returns_datetime(self) -> None:
        assert self._commit_with_author().committer_date is not None


class TestPullRequestNewProperties:
    def _pr_with_branches(self) -> PullRequest:
        info = PullRequestListItem.model_validate(
            {
                "pullRequestId": 99,
                "repository": {"id": str(REPO_ID)},
                "title": "Test PR",
                "status": "active",
                "sourceRefName": "refs/heads/feature/x",
                "targetRefName": "refs/heads/main",
                "description": "My description",
                "createdBy": {"id": str(uuid4()), "displayName": "Alice"},
            }
        )
        repo = _make_repo()
        api_call = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}/pullrequests/99"
        )
        return PullRequest(repo, api_call, info)

    def test_source_branch_returns_ref(self) -> None:
        assert self._pr_with_branches().source_branch == "refs/heads/feature/x"

    def test_target_branch_returns_ref(self) -> None:
        assert self._pr_with_branches().target_branch == "refs/heads/main"

    def test_description_returns_text(self) -> None:
        assert self._pr_with_branches().description == "My description"

    def test_created_by_returns_display_name(self) -> None:
        assert self._pr_with_branches().created_by == "Alice"


class TestTeamNewMethods:
    def _make_team(self) -> Team:
        return Team(_make_project(), _team_info())

    def test_iter_sprint_iterations_delegates(self) -> None:
        sprint = SprintIterationInfo.model_validate(
            {
                "id": str(uuid4()),
                "name": "Sprint 1",
                "path": "proj\\Sprint 1",
                "attributes": {"timeFrame": "current"},
            }
        )
        with patch("pyado.oop.team.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([sprint])
            result = list(self._make_team().iter_sprint_iterations())
        assert len(result) == 1
        assert result[0].name == "Sprint 1"

    def test_get_field_values_delegates(self) -> None:
        fv = TeamFieldValue.model_validate(
            {"value": "proj\\Area1", "includeChildren": False}
        )
        with patch("pyado.oop.team.raw.get_team_field_values") as mock_get:
            mock_get.return_value = [fv]
            result = self._make_team().get_field_values()
        assert len(result) == 1
        assert result[0].value == "proj\\Area1"

    def test_add_iteration_delegates(self) -> None:
        iteration_id = uuid4()
        with patch("pyado.oop.team.raw.add_team_iteration") as mock_add:
            self._make_team().add_iteration(iteration_id)
        mock_add.assert_called_once_with(self._make_team().api_call, iteration_id)


class TestWorkItemNewProperties:
    def _make_wi_with_fields(self) -> WorkItem:
        info = WorkItemInfo.model_validate(
            {
                "id": 10,
                "fields": {
                    "System.Title": "My WI",
                    "System.State": "Active",
                    "System.WorkItemType": "Task",
                    "System.AssignedTo": {"displayName": "Alice"},
                    "System.AreaPath": "proj\\Area",
                    "System.IterationPath": "proj\\Sprint 1",
                },
            }
        )
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/10")
        return WorkItem(proj, api_call, info)

    def test_state_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().state == "Active"

    def test_type_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().type == "Task"

    def test_assigned_to_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().assigned_to == {"displayName": "Alice"}

    def test_area_path_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().area_path == "proj\\Area"

    def test_iteration_path_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().iteration_path == "proj\\Sprint 1"
