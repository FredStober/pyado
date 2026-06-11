"""Tests for pyado.oop Project — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado.oop import (
    AgentQueue,
    Area,
    Branch,
    Build,
    Environment,
    Iteration,
    Pipeline,
    PipelineRun,
    Project,
    ProjectBoards,
    ProjectPipelines,
    ProjectRepos,
    ProjectSearch,
    ProjectSettings,
    PullRequest,
    SecureFile,
    Tag,
    Team,
    VariableGroup,
    Wiki,
    WorkItem,
)
from pyado.raw import (
    AgentQueueInfo,
    ApiCall,
    BuildDetails,
    BuildExpand,
    BuildStatus,
    ClassificationNode,
    EnvironmentCheckInfo,
    EnvironmentDeploymentRecord,
    EnvironmentInfo,
    GitRef,
    PipelineDefinitionInfo,
    ProcessDetail,
    ProjectInfo,
    PullRequestSearchCriteria,
    PullRequestStatus,
    SecureFileInfo,
    SprintIterationInfo,
    SprintIterationTimeframe,
    VariableInfo,
    WikiInfo,
    WorkItemExpand,
    WorkItemQuery,
    WorkItemQueryExpand,
)
from tests.oop.conftest import (
    PROJECT_ID,
    REPO_ID,
    _api_call,
    _area_node,
    _build_details,
    _iteration_node,
    _make_project,
    _make_service,
    _pipeline_info,
    _pipeline_run_info,
    _pr_created,
    _pr_list_item,
    _project_info,
    _repo_info,
    _team_info,
    _variable_group_info,
    _work_item_info,
)


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

    def test_repos_returns_project_repos(self) -> None:
        assert isinstance(_make_project().repos, ProjectRepos)

    def test_boards_returns_project_boards(self) -> None:
        assert isinstance(_make_project().boards, ProjectBoards)

    def test_pipelines_returns_project_pipelines(self) -> None:
        assert isinstance(_make_project().pipelines, ProjectPipelines)

    def test_search_returns_project_search(self) -> None:
        assert isinstance(_make_project().search, ProjectSearch)

    def test_settings_returns_project_settings(self) -> None:
        assert isinstance(_make_project().settings, ProjectSettings)

    def test_repos_is_identity_stable(self) -> None:
        proj = _make_project()
        assert proj.repos is proj.repos

    def test_boards_is_identity_stable(self) -> None:
        proj = _make_project()
        assert proj.boards is proj.boards

    def test_pipelines_is_identity_stable(self) -> None:
        proj = _make_project()
        assert proj.pipelines is proj.pipelines

    def test_search_is_identity_stable(self) -> None:
        proj = _make_project()
        assert proj.search is proj.search

    def test_settings_is_identity_stable(self) -> None:
        proj = _make_project()
        assert proj.settings is proj.settings

    def test_settings_get_project_info_calls_raw(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.settings.project_settings.raw.get_project",
            return_value=_project_info(),
        ) as mock_get:
            result = proj.settings.get_project_info()
        assert isinstance(result, ProjectInfo)
        mock_get.assert_called_once()


class TestProjectRepos:
    def test_get_repository_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("myrepo")])
            mock_get.return_value = _api_call()
            repo = proj.repos.get_repository("myrepo")
        assert repo.name == "myrepo"

    def test_get_repository_not_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("other")])
            mock_get.return_value = _api_call()
            with pytest.raises(KeyError):
                proj.repos.get_repository("notexist")

    def test_get_repository_by_id_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_get,
        ):
            info = _repo_info("myrepo")
            mock_iter.return_value = iter([info])
            mock_get.return_value = _api_call()
            repo = proj.repos.get_repository_by_id(info.id)
        assert repo.name == "myrepo"

    def test_get_repository_by_id_not_found(self) -> None:
        proj = _make_project()
        missing_id = uuid4()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("other")])
            mock_get.return_value = _api_call()
            with pytest.raises(KeyError):
                proj.repos.get_repository_by_id(missing_id)

    def test_iter_active_prs_yields_pull_requests(self) -> None:
        proj = _make_project()
        item = _pr_list_item(77)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_info"
            ) as mock_repo_info,
            patch(
                "pyado.oop.repos.project_repos.raw.get_pull_request_api_call"
            ) as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            prs = list(proj.repos.iter_active_prs())
        assert len(prs) == 1
        assert prs[0].id == 77
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == PullRequestStatus.ACTIVE

    def test_iter_active_prs_passes_expand(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repos.project_repos.raw.get_repository_api_call"),
            patch("pyado.oop.repos.project_repos.raw.get_repository_info"),
            patch("pyado.oop.repos.project_repos.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.repos.iter_active_prs(expand="labels"))
        assert mock_iter.call_args.kwargs["expand"] == "labels"

    def test_get_pull_request_finds_pr_across_repos(self) -> None:
        proj = _make_project()
        item = _pr_list_item(99)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_info"
            ) as mock_repo_info,
            patch(
                "pyado.oop.repos.project_repos.raw.get_pull_request_api_call"
            ) as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            pr = proj.repos.get_pull_request(99)
        assert pr.id == 99
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.pull_request_id == 99

    def test_get_pull_request_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(KeyError):
                proj.repos.get_pull_request(42)

    def test_iter_pull_requests_yields_pull_requests(self) -> None:
        proj = _make_project()
        item = _pr_list_item(55)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_info"
            ) as mock_repo_info,
            patch(
                "pyado.oop.repos.project_repos.raw.get_pull_request_api_call"
            ) as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            result = list(proj.repos.iter_pull_requests())
        assert len(result) == 1
        assert result[0].id == 55

    def test_iter_pull_requests_uses_no_status_by_default(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repos.project_repos.raw.get_repository_api_call"),
            patch("pyado.oop.repos.project_repos.raw.get_repository_info"),
            patch("pyado.oop.repos.project_repos.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.repos.iter_pull_requests())
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status is None

    def test_iter_pull_requests_custom_criteria_overrides_status(self) -> None:
        proj = _make_project()
        custom = PullRequestSearchCriteria(status=PullRequestStatus.COMPLETED)
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repos.project_repos.raw.get_repository_api_call"),
            patch("pyado.oop.repos.project_repos.raw.get_repository_info"),
            patch("pyado.oop.repos.project_repos.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.repos.iter_pull_requests(criteria=custom))
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == "completed"

    def test_iter_pull_requests_passes_expand(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.repos.project_repos.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repos.project_repos.raw.get_repository_api_call"),
            patch("pyado.oop.repos.project_repos.raw.get_repository_info"),
            patch("pyado.oop.repos.project_repos.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.repos.iter_pull_requests(expand="reviewers"))
        assert mock_iter.call_args.kwargs["expand"] == "reviewers"

    def test_get_pull_request_with_repo_id_fetches_directly(self) -> None:
        proj = _make_project()
        pr_info = _pr_created(77)
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_info"
            ) as mock_repo_info,
            patch(
                "pyado.oop.repos.project_repos.raw.get_pull_request_api_call"
            ) as mock_pr_call,
            patch(
                "pyado.oop.repos.project_repos.raw.get_pull_request_details"
            ) as mock_pr_details,
        ):
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            mock_pr_details.return_value = pr_info
            result = proj.repos.get_pull_request(77, repo_id=REPO_ID)
        assert isinstance(result, PullRequest)
        mock_pr_details.assert_called_once()

    def test_list_repositories_delegates(self) -> None:
        repos = _make_project().repos
        with patch.object(repos, "iter_repositories", return_value=iter([])):
            assert repos.list_repositories() == []

    def test_list_active_prs_delegates(self) -> None:
        repos = _make_project().repos
        with patch.object(repos, "iter_active_prs", return_value=iter([])):
            assert repos.list_active_prs() == []

    def test_list_pull_requests_delegates(self) -> None:
        repos = _make_project().repos
        with patch.object(repos, "iter_pull_requests", return_value=iter([])):
            assert repos.list_pull_requests() == []


class TestProjectBoards:
    def test_get_work_item(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_call,
            patch("pyado.oop.boards.project_boards.raw.get_work_item") as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _work_item_info(99)
            wi = proj.boards.get_work_item(99)
        assert wi.id == 99

    def test_create_work_item_prepends_type(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.boards._work_item.create_work_item") as mock_create,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_call,
            patch("pyado.oop.boards.project_boards.raw.get_work_item") as mock_get,
        ):
            mock_create.return_value = _work_item_info(1)
            mock_call.return_value = _api_call()
            mock_get.return_value = _work_item_info(1)
            proj.boards.create_work_item("Task", {"System.Title": "My Task"})
        called_fields = mock_create.call_args.args[1]
        assert called_fields["System.WorkItemType"] == "Task"
        assert called_fields["System.Title"] == "My Task"

    def test_iter_work_items_yields_work_items(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.boards.project_boards.raw.post_wiql") as mock_wiql,
            patch("pyado.oop.boards._work_item.iter_work_item_details") as mock_iter,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_call,
        ):
            mock_wiql.return_value = [_work_item_info(5)]
            mock_iter.return_value = iter([_work_item_info(5)])
            mock_call.return_value = _api_call()
            result = list(proj.boards.iter_work_items("SELECT [System.Id]"))
        assert len(result) == 1
        assert result[0].id == 5

    def test_create_work_item_raises_when_type_in_fields(self) -> None:
        proj = _make_project()
        with pytest.raises(ValueError, match="WorkItemType"):
            proj.boards.create_work_item(
                "Task",
                {"System.WorkItemType": "Bug"},
            )

    def test_iter_team_sprint_iterations_builds_team_call(self) -> None:
        proj = _make_project()
        sprint_info = MagicMock(spec=SprintIterationInfo)
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_sprint_iterations"
        ) as mock_iter:
            mock_iter.return_value = iter([sprint_info])
            result = list(proj.boards.iter_team_sprint_iterations("MyTeam"))
        assert len(result) == 1
        team_call = mock_iter.call_args.args[0]
        assert "MyTeam" in str(team_call.url)

    def test_iter_team_sprint_iterations_passes_timeframe(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_sprint_iterations"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            list(
                proj.boards.iter_team_sprint_iterations(
                    "MyTeam", timeframe_filter=SprintIterationTimeframe.CURRENT
                )
            )
        assert (
            mock_iter.call_args.kwargs["timeframe_filter"]
            == SprintIterationTimeframe.CURRENT
        )

    def test_list_team_field_values_delegates(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_team_field_values"
        ) as mock_get:
            mock_get.return_value = [MagicMock()]
            result = proj.boards.list_team_field_values("MyTeam")
        assert len(result) == 1
        team_call = mock_get.call_args.args[0]
        assert "MyTeam" in str(team_call.url)

    def test_add_team_iteration_delegates(self) -> None:
        proj = _make_project()
        iteration_id = uuid4()
        with patch(
            "pyado.oop.boards.project_boards.raw.post_team_iteration"
        ) as mock_add:
            proj.boards.add_team_iteration("MyTeam", iteration_id)
        mock_add.assert_called_once()
        team_call = mock_add.call_args.args[0]
        assert "MyTeam" in str(team_call.url)
        assert mock_add.call_args.args[1] == iteration_id

    def test_list_work_items_by_ids_returns_list_of_work_items(self) -> None:
        proj = _make_project()
        wi_infos = [_work_item_info(1), _work_item_info(2)]
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.post_work_items_batch"
            ) as mock_batch,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_api,
        ):
            mock_batch.return_value = wi_infos
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            result = proj.boards.list_work_items_by_ids([1, 2])
        assert len(result) == 2
        assert all(isinstance(item, WorkItem) for item in result)

    def test_list_work_items_by_ids_passes_ids(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.post_work_items_batch"
            ) as mock_batch,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.boards.list_work_items_by_ids([10, 20, 30])
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.ids == [10, 20, 30]

    def test_list_work_items_by_ids_expands_relations_by_default(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.post_work_items_batch"
            ) as mock_batch,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.boards.list_work_items_by_ids([1])
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.expand == WorkItemExpand.RELATIONS

    def test_list_work_items_by_ids_no_expand_when_passed_none(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.post_work_items_batch"
            ) as mock_batch,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.boards.list_work_items_by_ids([1], expand=None)
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.expand is None

    def test_iter_teams_yields_team_objects(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.iter_teams") as mock_iter:
            mock_iter.return_value = iter(
                [_team_info("t1", "Team A"), _team_info("t2", "Team B")]
            )
            result = list(proj.boards.iter_teams())
        assert len(result) == 2
        assert all(isinstance(item, Team) for item in result)
        assert result[0].name == "Team A"

    def test_iter_teams_uses_project_name(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.iter_teams") as mock_iter:
            mock_iter.return_value = iter([])
            list(proj.boards.iter_teams())
        assert mock_iter.call_args.args[1] == "TestProject"

    def test_get_team_returns_team(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info("t1", "DevOps Team")
            result = proj.boards.get_team("DevOps Team")
        assert isinstance(result, Team)
        assert result.name == "DevOps Team"

    def test_get_team_passes_name(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info()
            proj.boards.get_team("DevOps Team")
        assert mock_get.call_args.args[2] == "DevOps Team"

    def test_get_team_by_id_returns_team(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info("team-guid-001", "DevOps Team")
            result = proj.boards.get_team_by_id("team-guid-001")
        assert isinstance(result, Team)

    def test_get_team_by_id_passes_id(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info()
            proj.boards.get_team_by_id("team-guid-001")
        assert mock_get.call_args.args[2] == "team-guid-001"

    def test_list_teams_delegates(self) -> None:
        boards = _make_project().boards
        with patch.object(boards, "iter_teams", return_value=iter([])):
            assert boards.list_teams() == []

    def test_iter_work_items_by_ids_yields_work_items(self) -> None:
        proj = _make_project()
        wi_infos = [_work_item_info(1), _work_item_info(2)]
        with (
            patch(
                "pyado.oop.boards.project_boards.raw.post_work_items_batch"
            ) as mock_batch,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call"
            ) as mock_api,
        ):
            mock_batch.return_value = wi_infos
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            result = list(proj.boards.iter_work_items_by_ids([1, 2]))
        assert len(result) == 2
        assert all(isinstance(item, WorkItem) for item in result)

    def test_list_work_items_by_ids_delegates_to_iter(self) -> None:
        boards = _make_project().boards
        wi = MagicMock(spec=WorkItem)
        with patch.object(boards, "iter_work_items_by_ids", return_value=iter([wi])):
            result = boards.list_work_items_by_ids([1])
        assert result == [wi]

    def test_list_work_items_delegates(self) -> None:
        boards = _make_project().boards
        with patch.object(boards, "iter_work_items", return_value=iter([])):
            assert boards.list_work_items("SELECT [Id] FROM WorkItems") == []

    def test_list_team_sprint_iterations_delegates(self) -> None:
        boards = _make_project().boards
        with patch.object(boards, "iter_team_sprint_iterations", return_value=iter([])):
            assert boards.list_team_sprint_iterations("MyTeam") == []


class TestProjectBoardsQueryTree:
    def test_get_query_tree_delegates(self) -> None:
        proj = _make_project()
        queries = [_make_wit_query()]
        with patch("pyado.oop.boards.project_boards.raw.get_query_tree") as mock_get:
            mock_get.return_value = queries
            result = proj.boards.get_query_tree()
        assert result is queries
        mock_get.assert_called_once()

    def test_get_query_tree_forwards_depth_and_expand(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_query_tree") as mock_get:
            mock_get.return_value = _make_wit_query()
            proj.boards.get_query_tree(depth=3, expand=WorkItemQueryExpand.MINIMAL)
        call = mock_get.call_args
        assert call.kwargs["depth"] == 3
        assert call.kwargs["expand"] == WorkItemQueryExpand.MINIMAL

    def test_get_query_tree_defaults(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.boards.project_boards.raw.get_query_tree") as mock_get:
            mock_get.return_value = _make_wit_query()
            proj.boards.get_query_tree()
        call = mock_get.call_args
        assert call.kwargs["depth"] == 2
        assert call.kwargs["expand"] == WorkItemQueryExpand.ALL

    def test_get_query_folder_delegates(self) -> None:
        proj = _make_project()
        folder_id = "00000000-0000-0000-0000-000000000002"
        with patch("pyado.oop.boards.project_boards.raw.get_query_folder") as mock_get:
            mock_get.return_value = _make_wit_query("Shared Queries")
            result = proj.boards.get_query_folder(folder_id)
        assert isinstance(result, WorkItemQuery)
        assert mock_get.call_args.args[1] == folder_id

    def test_get_query_folder_forwards_depth_and_expand(self) -> None:
        proj = _make_project()
        folder_id = "00000000-0000-0000-0000-000000000002"
        with patch("pyado.oop.boards.project_boards.raw.get_query_folder") as mock_get:
            mock_get.return_value = _make_wit_query()
            proj.boards.get_query_folder(
                folder_id, depth=4, expand=WorkItemQueryExpand.CLAUSES
            )
        call = mock_get.call_args
        assert call.kwargs["depth"] == 4
        assert call.kwargs["expand"] == WorkItemQueryExpand.CLAUSES


class TestProjectBoardsIterationArea:
    def test_get_iteration_node_returns_iteration(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _iteration_node()
            result = proj.boards.get_iteration_node()
        assert isinstance(result, Iteration)

    def test_get_iteration_node_passes_path(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _iteration_node()
            proj.boards.get_iteration_node("Sprint 1")
        assert mock_get.call_args.args[1] == "Sprint 1"

    def test_get_iteration_node_passes_depth(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _iteration_node()
            proj.boards.get_iteration_node(depth=3)
        assert mock_get.call_args.kwargs["depth"] == 3

    def test_create_iteration_delegates(self) -> None:
        proj = _make_project()
        node = ClassificationNode.model_validate({"id": 1, "name": "Sprint 2"})
        with patch(
            "pyado.oop.boards.project_boards.raw.post_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            result = proj.boards.create_iteration(
                "Sprint 2",
                start_date=date(2024, 2, 1),
                finish_date=date(2024, 2, 14),
            )
        assert isinstance(result, Iteration)
        assert result.name == "Sprint 2"
        assert mock_create.call_args.args[1].name == "Sprint 2"

    def test_get_area_node_returns_area(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _area_node()
            result = proj.boards.get_area_node()
        assert isinstance(result, Area)

    def test_get_area_node_passes_path(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _area_node()
            proj.boards.get_area_node("Team A")
        assert mock_get.call_args.args[1] == "Team A"

    def test_get_area_node_passes_depth(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = _area_node()
            proj.boards.get_area_node(depth=2)
        assert mock_get.call_args.kwargs["depth"] == 2

    def test_create_iteration_without_dates_passes_none_attributes(self) -> None:
        proj = _make_project()
        node = ClassificationNode.model_validate({"id": 1, "name": "Sprint 3"})
        with patch(
            "pyado.oop.boards.project_boards.raw.post_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            proj.boards.create_iteration("Sprint 3")
        assert mock_create.call_args.args[1].attributes is None

    def test_create_area_delegates(self) -> None:
        proj = _make_project()
        node = ClassificationNode.model_validate({"id": 1, "name": "Backend"})
        with patch(
            "pyado.oop.boards.project_boards.raw.post_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            result = proj.boards.create_area("Backend")
        assert isinstance(result, Area)
        assert result.name == "Backend"
        assert mock_create.call_args.args[1].name == "Backend"


class TestProjectPipelines:
    def test_iter_builds_delegates(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.pipelines.project_pipelines.raw.iter_builds") as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
        ):
            mock_iter.return_value = iter([_build_details()])
            mock_call.return_value = _api_call()
            builds = list(
                proj.pipelines.iter_builds(status_filter=BuildStatus.COMPLETED)
            )
        assert len(builds) == 1
        search_criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert search_criteria.status_filter == BuildStatus.COMPLETED

    def test_iter_builds_passes_definition_id(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.pipelines.project_pipelines.raw.iter_builds") as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.pipelines.iter_builds(definition_id=42))
        assert mock_iter.call_args.kwargs["search_criteria"].definition_id == 42

    def test_iter_builds_passes_branch_name(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.pipelines.project_pipelines.raw.iter_builds") as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.pipelines.iter_builds(branch_name="refs/heads/main"))
        assert (
            mock_iter.call_args.kwargs["search_criteria"].branch_name
            == "refs/heads/main"
        )

    def test_iter_builds_passes_top(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.pipelines.project_pipelines.raw.iter_builds") as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(proj.pipelines.iter_builds(top=5))
        assert mock_iter.call_args.kwargs["search_criteria"].top == 5

    def test_get_build_returns_build(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_details"
            ) as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _build_details(build_id=42)
            build = proj.pipelines.get_build(42)
        assert build.id == 42

    def test_start_build_returns_build(self) -> None:
        proj = _make_project()
        pipeline = MagicMock(spec=Pipeline)
        pipeline.id = 7
        with (
            patch("pyado.oop.pipelines._build.start_build") as mock_start,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
        ):
            mock_start.return_value = _build_details(build_id=99)
            mock_call.return_value = _api_call()
            build = proj.pipelines.start_build(
                pipeline.id, source_branch="refs/heads/main"
            )
        assert mock_start.call_args.args[1] == 7
        assert mock_start.call_args.kwargs["source_branch"] == "refs/heads/main"
        assert build is not None

    def test_iter_pipelines_yields_pipeline_wrappers(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipelines"
        ) as mock_iter:
            mock_iter.return_value = iter([_pipeline_info(3)])
            result = list(proj.pipelines.iter_pipelines())
        assert len(result) == 1
        assert result[0].id == 3

    def test_get_pipeline_by_id_returns_pipeline(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_pipeline"
        ) as mock_get:
            mock_get.return_value = _pipeline_info(5)
            result = proj.pipelines.get_pipeline_by_id(5)
        assert result.id == 5

    def test_get_pipeline_returns_matching_pipeline(self) -> None:
        proj = _make_project()
        info = _pipeline_info(3)
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipelines"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = proj.pipelines.get_pipeline("MyPipeline")
        assert result.id == 3
        assert result.name == "MyPipeline"

    def test_get_pipeline_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        info = _pipeline_info(3)
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipelines"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            with pytest.raises(KeyError):
                proj.pipelines.get_pipeline("MissingPipeline")

    def test_iter_approvals_delegates(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_approvals"
        ) as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(proj.pipelines.iter_approvals())
        assert len(result) == 1

    def test_approve_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.pipelines._build.approve_pipeline") as mock_approve:
            proj.pipelines.approve("approval-uuid-123")
        mock_approve.assert_called_once_with(
            proj.api_call, "approval-uuid-123", comment=""
        )

    def test_approve_passes_comment(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.pipelines._build.approve_pipeline") as mock_approve:
            proj.pipelines.approve("uuid", comment="LGTM")
        assert mock_approve.call_args.kwargs["comment"] == "LGTM"

    def test_reject_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.pipelines._build.reject_pipeline") as mock_reject:
            proj.pipelines.reject("approval-uuid-456")
        mock_reject.assert_called_once_with(
            proj.api_call, "approval-uuid-456", comment=""
        )

    def test_reject_passes_comment(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.pipelines._build.reject_pipeline") as mock_reject:
            proj.pipelines.reject("uuid", comment="Needs changes")
        assert mock_reject.call_args.kwargs["comment"] == "Needs changes"

    def test_list_builds_delegates(self) -> None:
        pipelines = _make_project().pipelines
        with patch.object(pipelines, "iter_builds", return_value=iter([])):
            assert pipelines.list_builds() == []

    def test_list_pipelines_delegates(self) -> None:
        pipelines = _make_project().pipelines
        with patch.object(pipelines, "iter_pipelines", return_value=iter([])):
            assert pipelines.list_pipelines() == []

    def test_list_approvals_delegates(self) -> None:
        pipelines = _make_project().pipelines
        with patch.object(pipelines, "iter_approvals", return_value=iter([])):
            assert pipelines.list_approvals() == []

    def test_list_environments_delegates(self) -> None:
        pipelines = _make_project().pipelines
        with patch.object(pipelines, "iter_environments", return_value=iter([])):
            assert pipelines.list_environments() == []

    def test_list_agent_queues_delegates(self) -> None:
        pipelines = _make_project().pipelines
        with patch.object(pipelines, "iter_agent_queues", return_value=iter([])):
            assert pipelines.list_agent_queues() == []

    def test_get_build_with_expand_returns_build(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_details"
            ) as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _build_details(build_id=77)
            build = proj.pipelines.get_build_with_expand(77, BuildExpand.ALL)
        assert isinstance(build, Build)
        assert build.id == 77

    def test_get_latest_build_returns_build(self) -> None:
        proj = _make_project()
        pipeline = MagicMock(spec=Pipeline)
        pipeline.id = 3
        with (
            patch("pyado.oop.pipelines.project_pipelines.raw.iter_builds") as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
        ):
            mock_iter.return_value = iter([_build_details(build_id=50)])
            mock_call.return_value = _api_call()
            result = proj.pipelines.get_latest_build(pipeline.id)
        assert isinstance(result, Build)
        assert result.id == 50

    def test_get_build_details_returns_raw_build_details(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"
            ) as mock_call,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_details"
            ) as mock_get,
        ):
            mock_call.return_value = _api_call()
            mock_get.return_value = _build_details(build_id=33)
            result = proj.pipelines.get_build_details(33)
        assert isinstance(result, BuildDetails)
        assert result.id == 33

    def test_library_returns_same_instance_on_repeated_access(self) -> None:
        proj = _make_project()
        first = proj.pipelines.library
        second = proj.pipelines.library
        assert first is second

    def test_iter_variable_groups_delegates_to_library(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(1, "MyVars")
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            result = list(proj.pipelines.iter_variable_groups())
        assert len(result) == 1
        assert isinstance(result[0], VariableGroup)

    def test_list_variable_groups_delegates(self) -> None:
        pipelines = _make_project().pipelines
        vg = MagicMock(spec=VariableGroup)
        with patch.object(pipelines, "iter_variable_groups", return_value=iter([vg])):
            assert pipelines.list_variable_groups() == [vg]

    def test_get_variable_group_delegates_to_library(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(3, "StagingVars")
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            vg = proj.pipelines.get_variable_group("StagingVars")
        assert vg.name == "StagingVars"

    def test_get_variable_group_by_id_delegates_to_library(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(7, "ProdVars")
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_details"
            ) as mock_get,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_get.return_value = vg_info
            mock_ac.return_value = _api_call()
            vg = proj.pipelines.get_variable_group_by_id(7)
        assert vg.id == 7


class TestProjectLibrary:
    def test_iter_variable_groups_yields_wrappers(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(1, "MyVars")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            result = list(proj.pipelines.library.iter_variable_groups())
        assert len(result) == 1
        assert isinstance(result[0], VariableGroup)
        assert result[0].name == "MyVars"

    def test_get_variable_group_found_by_name(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(5, "ProdVars")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([vg_info])
            mock_ac.return_value = _api_call()
            vg = proj.pipelines.library.get_variable_group("ProdVars")
        assert vg.name == "ProdVars"

    def test_get_variable_group_not_found_raises(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([])
            mock_ac.return_value = _api_call()
            with pytest.raises(KeyError):
                proj.pipelines.library.get_variable_group("NoSuchGroup")

    def test_get_variable_group_by_id_found(self) -> None:
        proj = _make_project()
        vg_info = _variable_group_info(7, "DevVars")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_details"
            ) as mock_get,
        ):
            mock_ac.return_value = _api_call()
            mock_get.return_value = vg_info
            vg = proj.pipelines.library.get_variable_group_by_id(7)
        assert vg.id == 7

    def test_get_variable_group_skips_non_matching_name(self) -> None:
        proj = _make_project()
        vg_a = _variable_group_info(1, "Alpha")
        vg_b = _variable_group_info(2, "Beta")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_variable_group_details"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([vg_a, vg_b])
            mock_ac.return_value = _api_call()
            vg = proj.pipelines.library.get_variable_group("Beta")
        assert vg.name == "Beta"

    def test_create_variable_group_returns_wrapper(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info(group_id=99, name="NewGroup")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.post_variable_group"
            ) as mock_post,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_post.return_value = created_info
            mock_ac.return_value = _api_call()
            result = proj.pipelines.library.create_variable_group(
                "NewGroup", {"KEY": VariableInfo(value="val")}
            )
        assert isinstance(result, VariableGroup)
        assert result.info is created_info

    def test_create_variable_group_passes_name_and_variables(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info(group_id=5, name="Grp")
        variables = {"K": VariableInfo(value="v")}
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.post_variable_group"
            ) as mock_post,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_variable_group_api_call"
            ),
        ):
            mock_post.return_value = created_info
            proj.pipelines.library.create_variable_group("Grp", variables)
        request = mock_post.call_args.args[1]
        assert request.name == "Grp"
        assert request.variables == variables

    def test_create_variable_group_passes_description(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info()
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.post_variable_group"
            ) as mock_post,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ),
        ):
            mock_post.return_value = created_info
            proj.pipelines.library.create_variable_group(
                "G", {}, description="My description"
            )
        request = mock_post.call_args.args[1]
        assert request.description == "My description"

    def test_create_variable_group_library_passes_provider_data(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info()
        provider = {"serviceEndpointId": "ep-123", "vault": "my-vault"}
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.post_variable_group"
            ) as mock_post,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ),
        ):
            mock_post.return_value = created_info
            proj.pipelines.library.create_variable_group(
                "G", {}, provider_data=provider
            )
        request = mock_post.call_args.args[1]
        assert request.provider_data == provider

    def test_list_variable_groups_delegates(self) -> None:
        library = _make_project().pipelines.library
        with patch.object(library, "iter_variable_groups", return_value=iter([])):
            assert library.list_variable_groups() == []

    def test_iter_secure_files_yields_secure_file_wrappers(self) -> None:
        proj = _make_project()
        file_id = uuid4()
        info = SecureFileInfo.model_validate({"id": str(file_id), "name": "cert.p12"})
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_secure_files"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_secure_file_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([info])
            mock_ac.return_value = _api_call()
            result = list(proj.pipelines.library.iter_secure_files())
        assert len(result) == 1
        assert isinstance(result[0], SecureFile)
        assert result[0].name == "cert.p12"

    def test_get_secure_file_found_by_name(self) -> None:
        proj = _make_project()
        file_id = uuid4()
        info = SecureFileInfo.model_validate({"id": str(file_id), "name": "key.p12"})
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_secure_files"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_secure_file_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([info])
            mock_ac.return_value = _api_call()
            result = proj.pipelines.library.get_secure_file("key.p12")
        assert isinstance(result, SecureFile)

    def test_get_secure_file_skips_non_matching_name(self) -> None:
        proj = _make_project()
        file_id_a = uuid4()
        file_id_b = uuid4()
        info_a = SecureFileInfo.model_validate(
            {"id": str(file_id_a), "name": "other.p12"}
        )
        info_b = SecureFileInfo.model_validate(
            {"id": str(file_id_b), "name": "target.p12"}
        )
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_secure_files"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_secure_file_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([info_a, info_b])
            mock_ac.return_value = _api_call()
            result = proj.pipelines.library.get_secure_file("target.p12")
        assert result.name == "target.p12"

    def test_get_secure_file_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_secure_files"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_secure_file_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([])
            mock_ac.return_value = _api_call()
            with pytest.raises(KeyError):
                proj.pipelines.library.get_secure_file("missing.p12")

    def test_list_secure_files_delegates(self) -> None:
        library = _make_project().pipelines.library
        with patch.object(library, "iter_secure_files", return_value=iter([])):
            assert library.list_secure_files() == []

    def test_iter_runs_yields_pipeline_runs(self) -> None:
        proj = _make_project()
        pipeline = MagicMock(spec=Pipeline)
        pipeline.id = 7
        run_info = _pipeline_run_info(100, 7)
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_pipeline_runs"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_pipeline"
            ) as mock_get_pipeline,
        ):
            mock_iter.return_value = iter([run_info])
            mock_get_pipeline.return_value = _pipeline_info(7)
            result = list(proj.pipelines.iter_runs(pipeline.id))
        mock_iter.assert_called_once_with(proj.api_call, 7, top=None)
        assert len(result) == 1
        assert isinstance(result[0], PipelineRun)

    def test_iter_runs_passes_top(self) -> None:
        proj = _make_project()
        pipeline = MagicMock(spec=Pipeline)
        pipeline.id = 7
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipeline_runs"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            list(proj.pipelines.iter_runs(pipeline.id, top=3))
        mock_iter.assert_called_once_with(proj.api_call, 7, top=3)

    def test_list_runs_delegates(self) -> None:
        proj = _make_project()
        pipelines = proj.pipelines
        with patch.object(pipelines, "iter_runs", return_value=iter([])):
            assert pipelines.list_runs(7) == []

    def test_get_run_returns_pipeline_run(self) -> None:
        proj = _make_project()
        pipeline = MagicMock(spec=Pipeline)
        pipeline.id = 7
        run_info = _pipeline_run_info(42, 7)
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_pipeline_run"
            ) as mock_get,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_pipeline"
            ) as mock_get_pipeline,
        ):
            mock_get.return_value = run_info
            mock_get_pipeline.return_value = _pipeline_info(7)
            result = proj.pipelines.get_run(pipeline.id, 42)
        mock_get.assert_called_once_with(proj.api_call, 7, 42)
        assert isinstance(result, PipelineRun)

    def test_get_environment_by_id_returns_environment(self) -> None:
        proj = _make_project()
        env_info = EnvironmentInfo.model_validate({"id": 5, "name": "Staging"})
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_environment_api_call"
            ) as mock_ac,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_environment"
            ) as mock_get,
        ):
            mock_ac.return_value = _api_call()
            mock_get.return_value = env_info
            result = proj.pipelines.get_environment_by_id(5)
        assert isinstance(result, Environment)
        assert result.id == 5
        mock_get.assert_called_once_with(proj.api_call, 5)

    def test_get_environment_skips_non_matching_name(self) -> None:
        proj = _make_project()
        env_a = EnvironmentInfo.model_validate({"id": 1, "name": "Staging"})
        env_b = EnvironmentInfo.model_validate({"id": 2, "name": "Production"})
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_environments"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_environment_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([env_a, env_b])
            mock_ac.return_value = _api_call()
            result = proj.pipelines.get_environment("Production")
        assert isinstance(result, Environment)
        assert result.name == "Production"

    def test_get_environment_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_environments"
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_environment_api_call"
            ) as mock_ac,
        ):
            mock_iter.return_value = iter([])
            mock_ac.return_value = _api_call()
            with pytest.raises(KeyError):
                proj.pipelines.get_environment("missing-env")

    def test_get_agent_queue_skips_non_matching_name(self) -> None:
        proj = _make_project()
        queue_a = AgentQueueInfo.model_validate(
            {"id": 1, "name": "Other", "poolId": 10}
        )
        queue_b = AgentQueueInfo.model_validate(
            {"id": 2, "name": "Default", "poolId": 10}
        )
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_agent_queues"
        ) as mock_iter:
            mock_iter.return_value = iter([queue_a, queue_b])
            result = proj.pipelines.get_agent_queue("Default")
        assert isinstance(result, AgentQueue)
        assert result.name == "Default"

    def test_get_agent_queue_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_agent_queues"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(KeyError):
                proj.pipelines.get_agent_queue("missing-queue")

    def test_iter_pipeline_definitions_yields_infos(self) -> None:
        proj = _make_project()
        definition = PipelineDefinitionInfo.model_validate(
            {
                "id": 5,
                "name": "CI",
                "path": "\\",
                "queueStatus": "enabled",
                "revision": 1,
            }
        )
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipeline_definitions"
        ) as mock_iter:
            mock_iter.return_value = iter([definition])
            result = list(proj.pipelines.iter_pipeline_definitions())
        assert len(result) == 1
        assert isinstance(result[0], PipelineDefinitionInfo)
        assert result[0].id == 5

    def test_iter_pipeline_definitions_passes_name_filter(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_pipeline_definitions"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            list(proj.pipelines.iter_pipeline_definitions(name_filter="CI"))
        mock_iter.assert_called_once()
        assert mock_iter.call_args.kwargs["name_filter"] == "CI"

    def test_list_pipeline_definitions_delegates(self) -> None:
        proj = _make_project()
        pipelines = proj.pipelines
        with patch.object(
            pipelines, "iter_pipeline_definitions", return_value=iter([])
        ):
            assert pipelines.list_pipeline_definitions() == []

    def test_create_variable_group_on_pipelines_returns_wrapper(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info(group_id=88, name="ProjGroup")
        with (
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.post_variable_group"
            ) as mock_post,
            patch(
                "pyado.oop.pipelines.pipeline_library.raw.get_variable_group_api_call"
            ) as mock_ac,
        ):
            mock_post.return_value = created_info
            mock_ac.return_value = _api_call()
            result = proj.pipelines.create_variable_group(
                "ProjGroup", {"KEY": VariableInfo(value="val")}
            )
        assert isinstance(result, VariableGroup)
        assert result.name == "ProjGroup"


class TestEnvironmentWrapper:
    def _make_env(self, env_id: int = 3, name: str = "prod") -> Environment:
        proj = _make_project()
        env_info = EnvironmentInfo.model_validate(
            {"id": env_id, "name": name, "description": "My env"}
        )
        return Environment(proj, _api_call(), env_info)

    def test_info_returns_stored_info(self) -> None:
        env = self._make_env()
        assert env.info.name == "prod"

    def test_info_fetches_when_cache_is_none(self) -> None:
        env = self._make_env(env_id=7, name="staging")
        env._info = None
        refreshed = EnvironmentInfo.model_validate({"id": 7, "name": "staging"})
        with patch(
            "pyado.oop.pipelines.environment.raw.get_environment",
            return_value=refreshed,
        ):
            info = env.info
        assert info.name == "staging"

    def test_id_returns_env_id(self) -> None:
        assert self._make_env(env_id=99).id == 99

    def test_name_returns_env_name(self) -> None:
        assert self._make_env(name="staging").name == "staging"

    def test_description_returns_description(self) -> None:
        assert self._make_env().description == "My env"

    def test_api_call_returns_stored_api_call(self) -> None:
        assert isinstance(self._make_env().api_call, ApiCall)

    def test_project_returns_back_reference(self) -> None:
        proj = _make_project()
        env = Environment(
            proj,
            _api_call(),
            EnvironmentInfo.model_validate({"id": 1, "name": "x"}),
        )
        assert env.project is proj

    def test_org_returns_project_org(self) -> None:
        proj = _make_project()
        env = Environment(
            proj,
            _api_call(),
            EnvironmentInfo.model_validate({"id": 1, "name": "x"}),
        )
        assert env.org is proj.org

    def test_refresh_clears_info(self) -> None:
        env = self._make_env()
        env.refresh()
        assert env._info is None

    def test_iter_deployments_delegates(self) -> None:
        env = self._make_env()
        record = EnvironmentDeploymentRecord.model_validate(
            {"id": 1, "definitionName": "CI"}
        )
        with patch(
            "pyado.oop.pipelines.environment.raw.iter_environment_deployments",
            return_value=iter([record]),
        ):
            results = list(env.iter_deployments())
        assert len(results) == 1

    def test_list_deployments_returns_list(self) -> None:
        env = self._make_env()
        with patch.object(env, "iter_deployments", return_value=iter([])):
            assert env.list_deployments() == []

    def test_iter_checks_delegates_to_raw(self) -> None:
        env = self._make_env(env_id=3)
        check = EnvironmentCheckInfo.model_validate(
            {"id": 11, "type": {"id": "1", "name": "x"}}
        )
        with patch(
            "pyado.oop.pipelines.environment.raw.iter_environment_checks",
            return_value=iter([check]),
        ) as mock_iter:
            result = list(env.iter_checks())
        assert len(result) == 1
        assert isinstance(result[0], EnvironmentCheckInfo)
        assert result[0].id == 11
        mock_iter.assert_called_once()

    def test_iter_checks_passes_env_id(self) -> None:
        env = self._make_env(env_id=7)
        with patch(
            "pyado.oop.pipelines.environment.raw.iter_environment_checks",
            return_value=iter([]),
        ) as mock_iter:
            list(env.iter_checks())
        call_args = mock_iter.call_args
        assert call_args.args[1] == 7

    def test_list_checks_returns_list(self) -> None:
        env = self._make_env()
        with patch.object(env, "iter_checks", return_value=iter([])):
            assert env.list_checks() == []


class TestProjectReposBranches:
    def test_iter_branches_yields_branch_wrappers(self) -> None:
        proj = _make_project()
        ref = GitRef.model_validate(
            {"name": "refs/heads/main", "objectId": str(uuid4())}
        )
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch("pyado.oop.repos.repository.raw.iter_refs") as mock_refs,
        ):
            mock_iter.return_value = iter([_repo_info("myrepo")])
            mock_repo_call.return_value = _api_call()
            mock_refs.return_value = iter([ref])
            result = list(proj.repos.iter_branches("myrepo"))
        assert len(result) == 1
        assert isinstance(result[0], Branch)
        assert result[0].name == "main"

    def test_list_branches_delegates(self) -> None:
        proj = _make_project()
        repos = proj.repos
        with patch.object(repos, "iter_branches", return_value=iter([])):
            assert repos.list_branches("myrepo") == []


class TestProjectReposTags:
    def test_iter_git_tags_yields_tag_wrappers(self) -> None:
        proj = _make_project()
        ref = GitRef.model_validate(
            {"name": "refs/tags/v1.0", "objectId": str(uuid4())}
        )
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.project_repos.raw.get_repository_api_call"
            ) as mock_repo_call,
            patch("pyado.oop.repos.repository.raw.iter_tags") as mock_refs,
        ):
            mock_iter.return_value = iter([_repo_info("myrepo")])
            mock_repo_call.return_value = _api_call()
            mock_refs.return_value = iter([ref])
            result = list(proj.repos.iter_git_tags("myrepo"))
        assert len(result) == 1
        assert isinstance(result[0], Tag)
        assert result[0].name == "v1.0"

    def test_list_git_tags_delegates(self) -> None:
        proj = _make_project()
        repos = proj.repos
        with patch.object(repos, "iter_git_tags", return_value=iter([])):
            assert repos.list_git_tags("myrepo") == []


# ---------------------------------------------------------------------------
# Project-level wiki and dashboard tests
# ---------------------------------------------------------------------------


class TestProjectWikis:
    def test_iter_wikis_yields_wiki_objects(self) -> None:
        proj = _make_project()
        info = WikiInfo.model_validate(
            {"id": str(uuid4()), "name": "MyWiki", "type": "projectWiki"}
        )
        with patch("pyado.oop.project.raw.iter_wikis") as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(proj.iter_wikis())
        assert len(result) == 1
        assert isinstance(result[0], Wiki)

    def test_list_wikis_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_wikis", return_value=iter([])):
            assert proj.list_wikis() == []


class TestProjectTeams:
    def test_iter_teams_delegates_to_boards(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.boards.project_boards.raw.iter_teams") as mock_iter,
        ):
            mock_iter.return_value = iter([_team_info()])
            result = list(proj.iter_teams())
        assert len(result) == 1
        assert isinstance(result[0], Team)

    def test_list_teams_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_teams", return_value=iter([])):
            assert proj.list_teams() == []

    def test_get_default_team_uses_default_team_from_info(self) -> None:
        svc = _make_service()
        proj_info = ProjectInfo.model_validate(
            {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": "2024-01-01T00:00:00Z",
                "defaultTeam": {"id": "team-001", "name": "MyTeam"},
            }
        )
        proj = Project(svc, "TestProject", proj_info)
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info(name="MyTeam")
            result = proj.get_default_team()
        assert isinstance(result, Team)
        assert result.name == "MyTeam"

    def test_get_default_team_falls_back_to_project_name_team(self) -> None:
        proj = _make_project("ICS")
        with patch("pyado.oop.boards.project_boards.raw.get_team") as mock_get:
            mock_get.return_value = _team_info(name="ICS Team")
            result = proj.get_default_team()
        assert isinstance(result, Team)
        mock_get.assert_called_once()
        assert mock_get.call_args[0][2] == "ICS Team"


# ---------------------------------------------------------------------------
# Process info
# ---------------------------------------------------------------------------


class TestProjectGetProcessInfo:
    def test_get_process_info_returns_detail(self) -> None:
        svc = _make_service()
        template_id = uuid4()
        proj_info_with_caps = ProjectInfo.model_validate(
            {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": "2024-01-01T00:00:00Z",
                "capabilities": {
                    "processTemplate": {
                        "templateName": "Agile",
                        "templateTypeId": str(template_id),
                    },
                    "versioncontrol": {
                        "sourceControlType": "Git",
                        "gitEnabled": "True",
                        "tfvcEnabled": "False",
                    },
                },
            }
        )
        process_detail = ProcessDetail.model_validate(
            {
                "typeId": str(template_id),
                "name": "Agile",
                "referenceType": "system",
            }
        )
        proj = Project(svc, "TestProject")
        with (
            patch(
                "pyado.oop.project.raw.get_project",
                return_value=proj_info_with_caps,
            ),
            patch(
                "pyado.oop.project.raw.get_process_info",
                return_value=process_detail,
            ) as mock_process,
        ):
            result = proj.get_process_info()
        assert isinstance(result, ProcessDetail)
        mock_process.assert_called_once()

    def test_get_process_info_raises_when_no_capabilities(self) -> None:
        svc = _make_service()
        proj_info_no_caps = ProjectInfo.model_validate(
            {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": "2024-01-01T00:00:00Z",
            }
        )
        proj = Project(svc, "TestProject")
        with (
            patch(
                "pyado.oop.project.raw.get_project",
                return_value=proj_info_no_caps,
            ),
            pytest.raises(ValueError, match="capabilities"),
        ):
            proj.get_process_info()


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_wit_query(name: str = "My Queries") -> WorkItemQuery:
    return WorkItemQuery.model_validate(
        {"id": "00000000-0000-0000-0000-000000000001", "name": name}
    )
