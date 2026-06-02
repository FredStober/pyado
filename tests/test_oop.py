"""Tests for the pyado.oop OOP wrapper layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado.oop import (
    Build,
    Client,
    Pipeline,
    Project,
    PullRequest,
    Repository,
    WorkItem,
)
from pyado.raw import (
    ApiCall,
    BuildDetails,
    PipelineInfo,
    ProjectInfo,
    PullRequestCreated,
    PullRequestListItem,
    PullRequestVote,
    RepositoryInfo,
    WorkItemInfo,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW_ISO = "2024-01-15T12:00:00+00:00"
ORG_URL = "https://dev.azure.com/testorg"
TOKEN = "test-token"
PROJECT_ID = uuid4()
REPO_ID = uuid4()


def _api_call(url: str = f"{ORG_URL}/_apis") -> ApiCall:
    """Return a minimal ApiCall for testing."""
    return ApiCall(access_token=TOKEN, url=url)


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


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestClient:
    def test_get_project_found(self) -> None:
        """get_project returns a Project when the name matches."""
        with patch("pyado.oop.client.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter(
                [_project_info("ICS"), _project_info("Other")]
            )
            client = Client(org_url=ORG_URL, token=TOKEN)
            project = client.get_project("ICS")
        assert project.get_name() == "ICS"

    def test_get_project_not_found(self) -> None:
        """get_project raises ValueError when name is absent."""
        with patch("pyado.oop.client.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter([_project_info("Other")])
            client = Client(org_url=ORG_URL, token=TOKEN)
            with pytest.raises(ValueError, match="ICS"):
                client.get_project("ICS")

    def test_iter_projects_yields_project_instances(self) -> None:
        """iter_projects yields Project instances with correct info."""
        with patch("pyado.oop.client.raw.iter_projects") as mock_iter:
            mock_iter.return_value = iter([_project_info("ICS")])
            client = Client(org_url=ORG_URL, token=TOKEN)
            projects = list(client.iter_projects())
        assert len(projects) == 1
        assert projects[0].get_name() == "ICS"

    def test_get_my_profile_delegates(self) -> None:
        """get_my_profile delegates to get_profile_api_call and get_my_profile."""
        with (
            patch("pyado.oop.client.raw.get_profile_api_call") as mock_get_call,
            patch("pyado.oop.client.raw.get_my_profile") as mock_get_profile,
        ):
            mock_get_call.return_value = _api_call()
            mock_get_profile.return_value = MagicMock()
            client = Client(org_url=ORG_URL, token=TOKEN)
            client.get_my_profile()
        mock_get_call.assert_called_once_with(TOKEN)
        mock_get_profile.assert_called_once()


# ---------------------------------------------------------------------------
# Project tests
# ---------------------------------------------------------------------------


class TestProject:
    def _make_project(self, name: str = "TestProject") -> Project:
        return Project(_api_call(f"{ORG_URL}/{name}/_apis"), _project_info(name))

    def test_get_name(self) -> None:
        assert self._make_project("ICS").get_name() == "ICS"

    def test_get_id(self) -> None:
        assert self._make_project().get_id() == PROJECT_ID

    def test_get_repository_found(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("myrepo")])
            mock_get.return_value = _api_call()
            repo = self._make_project().get_repository("myrepo")
        assert repo.get_info().name == "myrepo"

    def test_get_repository_not_found(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("other")])
            mock_get.return_value = _api_call()
            with pytest.raises(ValueError, match="notexist"):
                self._make_project().get_repository("notexist")

    def test_get_work_item(self) -> None:
        with (
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
            patch("pyado.oop.project.raw.get_work_item") as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _work_item_info(99)
            wi = self._make_project().get_work_item(99)
        assert wi.get_id() == 99

    def test_create_work_item_prepends_type(self) -> None:
        """create_work_item merges ticket_type into the fields dict."""
        with (
            patch("pyado.oop.project.high.create_work_item") as mock_create,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
        ):
            mock_create.return_value = _work_item_info(1)
            mock_call.return_value = _api_call()
            self._make_project().create_work_item("Task", {"System.Title": "My Task"})
        called_fields = mock_create.call_args.args[1]
        assert called_fields["System.WorkItemType"] == "Task"
        assert called_fields["System.Title"] == "My Task"


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestRepository:
    def _make_repo(self) -> Repository:
        return Repository(
            _api_call(f"{ORG_URL}/TestProject/_apis"),
            _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}"),
            _repo_info(),
        )

    def test_get_pr_delegates_to_get_pr_details(self) -> None:
        with (
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
            patch("pyado.oop.repository.raw.get_pr_details") as mock_details,
        ):
            mock_call.return_value = _api_call()
            mock_details.return_value = _pr_created(7)
            pr = self._make_repo().get_pr(7)
        assert pr.get_id() == 7

    def test_iter_prs_filters_by_repo(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_prs") as mock_iter,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1), _pr_list_item(2)])
            mock_call.return_value = _api_call()
            prs = list(self._make_repo().iter_prs())
        criteria = mock_iter.call_args.args[1]
        assert criteria["repositoryId"] == str(REPO_ID)
        assert criteria["status"] == "active"
        assert len(prs) == 2

    def test_create_pr_returns_pull_request(self) -> None:
        with (
            patch("pyado.oop.repository.high.create_pr") as mock_create,
            patch("pyado.oop.repository.raw.get_pr_api_call") as mock_call,
        ):
            mock_create.return_value = _pr_created(5)
            mock_call.return_value = _api_call()
            pr = self._make_repo().create_pr("My PR", "feature/x", "main")
        assert pr.get_id() == 5


# ---------------------------------------------------------------------------
# PullRequest tests
# ---------------------------------------------------------------------------


class TestPullRequest:
    def _make_pr(self, pr_id: int = 42) -> PullRequest:
        return PullRequest(
            _api_call(),
            _api_call(),
            _pr_list_item(pr_id),
            PROJECT_ID,
            REPO_ID,
        )

    def test_get_id(self) -> None:
        assert self._make_pr(99).get_id() == 99

    def test_link_work_item_calls_add_artifact_link(self) -> None:
        """link_work_item delegates to high.add_artifact_link with correct URL."""
        with patch("pyado.oop.pull_request.high.add_artifact_link") as mock_link:
            mock_link.return_value = _work_item_info()
            pr = self._make_pr(32)
            wi = WorkItem(_api_call(), _api_call(), _work_item_info(153))
            pr.link_work_item(wi)
        mock_link.assert_called_once()
        call_url: str = mock_link.call_args.args[1]
        assert "PullRequestId" in call_url
        assert "32" in call_url

    def test_get_labels_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.get_pr_labels") as mock_labels:
            mock_labels.return_value = ["label-a", "label-b"]
            labels = self._make_pr().get_labels()
        assert labels == ["label-a", "label-b"]

    def test_add_label_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_label") as mock_add:
            self._make_pr().add_label("my-label")
        mock_add.assert_called_once()

    def test_remove_label_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.delete_pr_label") as mock_del:
            self._make_pr().remove_label("my-label")
        mock_del.assert_called_once()

    def test_add_thread_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.create_pr_thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            self._make_pr().add_thread("hello")
        mock_thread.assert_called_once()
        assert mock_thread.call_args.args[1] == "hello"

    def test_update_sends_only_non_none(self) -> None:
        with patch("pyado.oop.pull_request.raw.patch_pr") as mock_patch:
            self._make_pr().update(title="New Title")
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.title == "New Title"
        assert update_arg.description is None


# ---------------------------------------------------------------------------
# WorkItem tests
# ---------------------------------------------------------------------------


class TestWorkItem:
    def _make_wi(self, wi_id: int = 10) -> WorkItem:
        return WorkItem(_api_call(), _api_call(), _work_item_info(wi_id))

    def test_get_id(self) -> None:
        assert self._make_wi(55).get_id() == 55

    def test_get_field_returns_value(self) -> None:
        assert self._make_wi().get_field("System.Title") == "My WI"

    def test_get_field_returns_none_for_absent(self) -> None:
        assert self._make_wi().get_field("System.Missing") is None

    def test_update_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.update_work_item") as mock_update:
            mock_update.return_value = _work_item_info()
            self._make_wi().update({"System.Title": "New"})
        mock_update.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.add_work_item_tag") as mock_tag:
            mock_tag.return_value = ["tag-a"]
            result = self._make_wi().add_tag("tag-a")
        assert result == ["tag-a"]

    def test_add_comment_delegates(self) -> None:
        with patch("pyado.oop.work_item.raw.post_work_item_comment") as mock_comment:
            mock_comment.return_value = MagicMock()
            self._make_wi().add_comment("hello")
        mock_comment.assert_called_once()


# ---------------------------------------------------------------------------
# Build tests
# ---------------------------------------------------------------------------


class TestBuild:
    def _make_build(self) -> Build:
        details = BuildDetails.model_validate(
            {
                "id": 100,
                "buildNumber": "20240101.1",
                "status": "completed",
                "result": "succeeded",
                "queueTime": NOW_ISO,
                "lastChangedDate": NOW_ISO,
                "sourceBranch": "refs/heads/main",
                "sourceVersion": "abc123",
                "definition": {"id": 1, "name": "MyPipeline"},
                "requestedBy": {
                    "id": str(uuid4()),
                    "displayName": "User",
                },
                "requestedFor": {
                    "id": str(uuid4()),
                    "displayName": "User",
                },
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
        return Build(_api_call(), details)

    def test_get_info_returns_details(self) -> None:
        build = self._make_build()
        assert build.get_info().id == 100

    def test_iter_artifacts_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_artifacts") as mock_iter:
            mock_iter.return_value = iter([])
            list(self._make_build().iter_artifacts())
        mock_iter.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch("pyado.oop.build.raw.post_build_tag") as mock_tag:
            mock_tag.return_value = ["tag-a"]
            result = self._make_build().add_tag("tag-a")
        assert result == ["tag-a"]


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------


class TestPipeline:
    def _make_pipeline(self) -> Pipeline:
        info = PipelineInfo.model_validate(
            {
                "id": 7,
                "revision": 1,
                "name": "MyPipeline",
                "folder": "\\",
                "url": "https://dev.azure.com/testorg/TestProject/_apis/pipelines/7",
            }
        )
        return Pipeline(_api_call(), info)

    def test_get_info_returns_info(self) -> None:
        pipeline = self._make_pipeline()
        assert pipeline.get_info().id == 7

    def test_iter_runs_delegates(self) -> None:
        with patch("pyado.oop.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            list(self._make_pipeline().iter_runs())
        mock_iter.assert_called_once()
        pipeline_id_arg = mock_iter.call_args.args[1]
        assert pipeline_id_arg == 7

    def test_start_run_no_args_passes_none(self) -> None:
        """start_run with no arguments passes request=None to post_pipeline_run."""
        with patch("pyado.oop.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            self._make_pipeline().start_run()
        mock_run.assert_called_once()
        assert mock_run.call_args.args[2] is None

    def test_start_run_with_variables_builds_request(self) -> None:
        """start_run with variables creates a PipelineRunRequest."""
        with patch("pyado.oop.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            self._make_pipeline().start_run(variables={"env": "test"})
        request_arg = mock_run.call_args.args[2]
        assert request_arg is not None
        assert request_arg.variables == {"env": "test"}

    def test_get_run_delegates(self) -> None:
        """get_run delegates to raw.get_pipeline_run."""
        with patch("pyado.oop.pipeline.raw.get_pipeline_run") as mock_get:
            mock_get.return_value = MagicMock()
            self._make_pipeline().get_run(42)
        mock_get.assert_called_once()
        assert mock_get.call_args.args[2] == 42


# ---------------------------------------------------------------------------
# Extended Project tests
# ---------------------------------------------------------------------------


class TestProjectExtended:
    def _make_project(self, name: str = "TestProject") -> Project:
        return Project(_api_call(f"{ORG_URL}/{name}/_apis"), _project_info(name))

    def test_get_info_returns_project_info(self) -> None:
        info = self._make_project().get_info()
        assert info.name == "TestProject"

    def test_iter_work_items_yields_work_items(self) -> None:
        with (
            patch("pyado.oop.project.raw.post_wiql") as mock_wiql,
            patch("pyado.oop.project.high.iter_work_item_details") as mock_iter,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
        ):
            mock_wiql.return_value = [_work_item_info(5)]
            mock_iter.return_value = iter([_work_item_info(5)])
            mock_call.return_value = _api_call()
            result = list(self._make_project().iter_work_items("SELECT [System.Id]"))
        assert len(result) == 1
        assert result[0].get_id() == 5

    def test_iter_builds_delegates(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_builds") as mock_iter,
            patch("pyado.oop.project.raw.get_build_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([MagicMock(id=1)])
            mock_call.return_value = _api_call()
            builds = list(self._make_project().iter_builds(status_filter="completed"))
        assert len(builds) == 1
        mock_iter.assert_called_once()
        assert mock_iter.call_args.kwargs.get("status_filter") == "completed"

    def test_start_build_returns_build(self) -> None:
        with (
            patch("pyado.oop.project.high.start_build") as mock_start,
            patch("pyado.oop.project.raw.get_build_api_call") as mock_call,
        ):
            mock_start.return_value = MagicMock(id=99)
            mock_call.return_value = _api_call()
            build = self._make_project().start_build(7, source_branch="refs/heads/main")
        assert mock_start.call_args.args[1] == 7
        assert mock_start.call_args.kwargs["source_branch"] == "refs/heads/main"
        assert build is not None

    def test_iter_pipeline_definitions_delegates(self) -> None:
        with patch("pyado.oop.project.raw.iter_pipeline_definitions") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_project().iter_pipeline_definitions())
        assert len(result) == 1

    def test_iter_pipelines_yields_pipeline_wrappers(self) -> None:
        pipeline_info = PipelineInfo.model_validate(
            {
                "id": 3,
                "revision": 1,
                "name": "MyPipe",
                "folder": "\\",
                "url": "https://dev.azure.com/org/proj/_apis/pipelines/3",
            }
        )
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([pipeline_info])
            result = list(self._make_project().iter_pipelines())
        assert len(result) == 1
        assert result[0].get_info().id == 3

    def test_get_pipeline_returns_pipeline(self) -> None:
        pipeline_info = PipelineInfo.model_validate(
            {
                "id": 5,
                "revision": 1,
                "name": "Pipe5",
                "folder": "\\",
                "url": "https://dev.azure.com/org/proj/_apis/pipelines/5",
            }
        )
        with patch("pyado.oop.project.raw.get_pipeline") as mock_get:
            mock_get.return_value = pipeline_info
            result = self._make_project().get_pipeline(5)
        assert result.get_info().id == 5

    def test_iter_pending_approvals_delegates(self) -> None:
        with patch("pyado.oop.project.high.iter_pending_approvals") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_project().iter_pending_approvals())
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Extended PullRequest tests
# ---------------------------------------------------------------------------


class TestPullRequestExtended:
    def _make_pr(self, pr_id: int = 42) -> PullRequest:
        return PullRequest(
            _api_call(),
            _api_call(),
            _pr_list_item(pr_id),
            PROJECT_ID,
            REPO_ID,
        )

    def test_get_info_returns_info(self) -> None:
        pr = self._make_pr(7)
        info = pr.get_info()
        assert info.pr_id == 7

    def test_iter_threads_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.iter_pr_threads") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_pr().iter_threads())
        assert len(result) == 1

    def test_reply_to_thread_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.reply_to_pr_thread") as mock_reply:
            mock_reply.return_value = MagicMock()
            self._make_pr().reply_to_thread(1, "reply text")
        mock_reply.assert_called_once()
        assert mock_reply.call_args.args[1] == 1
        assert mock_reply.call_args.args[2] == "reply text"

    def test_get_reviewers_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.get_pr_reviewers") as mock_get:
            mock_get.return_value = [MagicMock()]
            result = self._make_pr().get_reviewers()
        assert len(result) == 1

    def test_add_reviewer_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.add_pr_reviewer") as mock_add:
            self._make_pr().add_reviewer("user-id", is_required=True)
        mock_add.assert_called_once()
        assert mock_add.call_args.args[1] == "user-id"
        assert mock_add.call_args.kwargs["is_required"] is True

    def test_remove_reviewer_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.delete_pr_reviewer") as mock_del:
            self._make_pr().remove_reviewer("user-id")
        mock_del.assert_called_once()

    def test_vote_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.set_pr_reviewer_vote") as mock_vote:
            self._make_pr().vote("user-id", PullRequestVote.APPROVED)
        mock_vote.assert_called_once()
        assert mock_vote.call_args.args[1] == "user-id"
        assert mock_vote.call_args.args[2] == PullRequestVote.APPROVED

    def test_set_status_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_status") as mock_status:
            self._make_pr().set_status("succeeded", "my-check")
        mock_status.assert_called_once()

    def test_set_status_with_target_url(self) -> None:
        with patch("pyado.oop.pull_request.raw.post_pr_status") as mock_status:
            self._make_pr().set_status(
                "succeeded",
                "my-check",
                target_url="https://example.com/build/1",
            )
        mock_status.assert_called_once()
        request_arg = mock_status.call_args.args[1]
        assert request_arg.target_url is not None

    def test_iter_commits_delegates(self) -> None:
        with patch("pyado.oop.pull_request.raw.iter_pr_commits") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_pr().iter_commits())
        assert len(result) == 1

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.pull_request.high.iter_pr_work_item_ids") as mock_iter:
            mock_iter.return_value = iter([10, 20])
            result = list(self._make_pr().iter_work_item_ids())
        assert result == [10, 20]

    def test_link_work_item_with_comment(self) -> None:
        """link_work_item passes comment through to add_artifact_link."""
        with patch("pyado.oop.pull_request.high.add_artifact_link") as mock_link:
            mock_link.return_value = _work_item_info()
            pr = self._make_pr(32)
            wi = WorkItem(_api_call(), _api_call(), _work_item_info(153))
            pr.link_work_item(wi, comment="Linked via PR")
        mock_link.assert_called_once()
        assert mock_link.call_args.kwargs.get("comment") == "Linked via PR"


# ---------------------------------------------------------------------------
# Extended Repository tests
# ---------------------------------------------------------------------------


class TestRepositoryExtended:
    def _make_repo(self) -> Repository:
        return Repository(
            _api_call(f"{ORG_URL}/TestProject/_apis"),
            _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}"),
            _repo_info(),
        )

    def test_get_file_at_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.get_file_content_at_branch") as mock_get:
            mock_get.return_value = "file content"
            result = self._make_repo().get_file_at_branch("/foo.py", "main")
        assert result == "file content"

    def test_get_file_at_commit_delegates(self) -> None:
        with patch("pyado.oop.repository.high.get_file_content_at_commit") as mock_get:
            mock_get.return_value = "commit content"
            result = self._make_repo().get_file_at_commit("/bar.py", "abc123")
        assert result == "commit content"

    def test_iter_refs_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_repo().iter_refs(name_filter="heads/main"))
        assert len(result) == 1
        assert mock_iter.call_args.kwargs.get("name_filter") == "heads/main"

    def test_create_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.create_branch") as mock_create:
            self._make_repo().create_branch("feature/new", "abc123")
        mock_create.assert_called_once()

    def test_delete_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.high.delete_branch") as mock_del:
            self._make_repo().delete_branch("feature/old", "def456")
        mock_del.assert_called_once()

    def test_iter_commit_diff_delegates(self) -> None:
        with patch("pyado.oop.repository.high.iter_commit_diff") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_repo().iter_commit_diff("abc", "def"))
        assert len(result) == 1

    def test_push_commits_delegates(self) -> None:
        with patch("pyado.oop.repository.high.push_commits") as mock_push:
            mock_push.return_value = MagicMock()
            self._make_repo().push_commits([], [])
        mock_push.assert_called_once()


# ---------------------------------------------------------------------------
# Extended WorkItem tests
# ---------------------------------------------------------------------------


class TestWorkItemExtended:
    def _make_wi(self, wi_id: int = 10) -> WorkItem:
        return WorkItem(_api_call(), _api_call(), _work_item_info(wi_id))

    def test_get_info_returns_work_item_info(self) -> None:
        info = self._make_wi(99).get_info()
        assert info.id == 99

    def test_get_tags_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.get_work_item_tags") as mock_tags:
            mock_tags.return_value = ["tag-a", "tag-b"]
            result = self._make_wi().get_tags()
        assert result == ["tag-a", "tag-b"]

    def test_remove_tag_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.remove_work_item_tag") as mock_remove:
            mock_remove.return_value = ["tag-b"]
            result = self._make_wi().remove_tag("tag-a")
        assert result == ["tag-b"]

    def test_iter_comments_delegates(self) -> None:
        with patch("pyado.oop.work_item.raw.iter_work_item_comments") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_wi().iter_comments())
        assert len(result) == 1

    def test_add_attachment_delegates(self) -> None:
        with patch("pyado.oop.work_item.high.add_work_item_attachment") as mock_attach:
            mock_attach.return_value = MagicMock()
            self._make_wi().add_attachment("report.txt", b"data")
        mock_attach.assert_called_once()


# ---------------------------------------------------------------------------
# Extended Build tests
# ---------------------------------------------------------------------------


class TestBuildExtended:
    def _make_build(self) -> Build:
        details = BuildDetails.model_validate(
            {
                "id": 100,
                "buildNumber": "20240101.1",
                "status": "completed",
                "result": "succeeded",
                "queueTime": NOW_ISO,
                "lastChangedDate": NOW_ISO,
                "sourceBranch": "refs/heads/main",
                "sourceVersion": "abc123",
                "definition": {"id": 1, "name": "MyPipeline"},
                "requestedBy": {
                    "id": str(uuid4()),
                    "displayName": "User",
                },
                "requestedFor": {
                    "id": str(uuid4()),
                    "displayName": "User",
                },
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
        return Build(_api_call(), details)

    def test_iter_tags_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_tags") as mock_iter:
            mock_iter.return_value = iter(["tag-x"])
            result = list(self._make_build().iter_tags())
        assert result == ["tag-x"]

    def test_remove_tag_delegates(self) -> None:
        with patch("pyado.oop.build.raw.delete_build_tag") as mock_del:
            mock_del.return_value = ["remaining"]
            result = self._make_build().remove_tag("old-tag")
        assert result == ["remaining"]

    def test_iter_timeline_records_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(self._make_build().iter_timeline_records())
        assert len(result) == 1

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.build.high.iter_build_work_item_ids") as mock_iter:
            mock_iter.return_value = iter([42, 43])
            result = list(self._make_build().iter_work_item_ids())
        assert result == [42, 43]
