"""Tests for pyado.oop Project — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado.oop import (
    Area,
    Iteration,
    Project,
    PullRequest,
    Team,
    VariableGroup,
    WorkItem,
)
from pyado.raw import (
    BuildStatus,
    ClassificationNode,
    PullRequestSearchCriteria,
    PullRequestStatus,
    SprintIterationInfo,
    SprintIterationTimeframe,
    VariableInfo,
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

    def test_get_repository_by_id_found(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            info = _repo_info("myrepo")
            mock_iter.return_value = iter([info])
            mock_get.return_value = _api_call()
            repo = _make_project().get_repository_by_id(info.id)
        assert repo.name == "myrepo"

    def test_get_repository_by_id_not_found(self) -> None:
        missing_id = uuid4()
        with (
            patch("pyado.oop.project.raw.iter_repository_details") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_get,
        ):
            mock_iter.return_value = iter([_repo_info("other")])
            mock_get.return_value = _api_call()
            with pytest.raises(ValueError, match=str(missing_id)):
                _make_project().get_repository_by_id(missing_id)

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
            patch("pyado.oop.project._work_item.create_work_item") as mock_create,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_call,
            patch("pyado.oop.project.raw.get_work_item") as mock_get,
        ):
            mock_create.return_value = _work_item_info(1)
            mock_call.return_value = _api_call()
            mock_get.return_value = _work_item_info(1)
            _make_project().create_work_item("Task", {"System.Title": "My Task"})
        called_fields = mock_create.call_args.args[1]
        assert called_fields["System.WorkItemType"] == "Task"
        assert called_fields["System.Title"] == "My Task"

    def test_iter_work_items_yields_work_items(self) -> None:
        with (
            patch("pyado.oop.project.raw.post_wiql") as mock_wiql,
            patch("pyado.oop.project._work_item.iter_work_item_details") as mock_iter,
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
        search_criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert search_criteria.status_filter == BuildStatus.COMPLETED

    def test_iter_builds_passes_definition_id(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_builds") as mock_iter,
            patch("pyado.oop.project.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_builds(definition_id=42))
        assert mock_iter.call_args.kwargs["search_criteria"].definition_id == 42

    def test_iter_builds_passes_branch_name(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_builds") as mock_iter,
            patch("pyado.oop.project.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_builds(branch_name="refs/heads/main"))
        assert (
            mock_iter.call_args.kwargs["search_criteria"].branch_name
            == "refs/heads/main"
        )

    def test_iter_builds_passes_top(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_builds") as mock_iter,
            patch("pyado.oop.project.raw.get_build_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_builds(top=5))
        assert mock_iter.call_args.kwargs["search_criteria"].top == 5

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
            patch("pyado.oop.project._build.start_build") as mock_start,
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

    def test_get_pipeline_by_id_returns_pipeline(self) -> None:
        with patch("pyado.oop.project.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(5)
            result = _make_project().get_pipeline_by_id(5)
        assert result.id == 5

    def test_iter_pending_approvals_delegates(self) -> None:
        with patch("pyado.oop.project._build.iter_pending_approvals") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_project().iter_pending_approvals())
        assert len(result) == 1

    def test_iter_active_prs_yields_pull_requests(self) -> None:
        item = _pr_list_item(77)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_repo_call,
            patch("pyado.oop.project.raw.get_repository_info") as mock_repo_info,
            patch("pyado.oop.project.raw.get_pull_request_api_call") as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            prs = list(_make_project().iter_active_prs())
        assert len(prs) == 1
        assert prs[0].id == 77
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == PullRequestStatus.ACTIVE

    def test_iter_active_prs_passes_expand(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call"),
            patch("pyado.oop.project.raw.get_repository_info"),
            patch("pyado.oop.project.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_active_prs(expand="labels"))
        assert mock_iter.call_args.kwargs["expand"] == "labels"

    def test_get_pull_request_finds_pr_across_repos(self) -> None:
        item = _pr_list_item(99)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_repo_call,
            patch("pyado.oop.project.raw.get_repository_info") as mock_repo_info,
            patch("pyado.oop.project.raw.get_pull_request_api_call") as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            pr = _make_project().get_pull_request(99)
        assert pr.id == 99
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.pull_request_id == 99

    def test_get_pull_request_raises_value_error_when_not_found(self) -> None:
        with patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(ValueError, match="42"):
                _make_project().get_pull_request(42)

    def test_iter_team_sprint_iterations_builds_team_call(self) -> None:
        sprint_info = MagicMock(spec=SprintIterationInfo)
        with patch("pyado.oop.project.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([sprint_info])
            result = list(_make_project().iter_team_sprint_iterations("MyTeam"))
        assert len(result) == 1
        team_call = mock_iter.call_args.args[0]
        assert "MyTeam" in str(team_call.url)

    def test_iter_team_sprint_iterations_passes_timeframe(self) -> None:
        with patch("pyado.oop.project.raw.iter_sprint_iterations") as mock_iter:
            mock_iter.return_value = iter([])
            list(
                _make_project().iter_team_sprint_iterations(
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

    def test_get_work_items_expands_relations_by_default(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.get_work_items([1])
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.expand == WorkItemExpand.RELATIONS

    def test_get_work_items_no_expand_when_passed_none(self) -> None:
        proj = _make_project()
        with (
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_batch.return_value = []
            mock_api.side_effect = lambda _call, _wi_id: _api_call()
            proj.get_work_items([1], expand=None)
        batch_request = mock_batch.call_args.args[1]
        assert batch_request.expand is None

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

    def test_get_team_passes_name(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_team") as mock_get:
            mock_get.return_value = _team_info()
            proj.get_team("DevOps Team")
        assert mock_get.call_args.args[2] == "DevOps Team"

    def test_get_team_by_id_returns_team(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_team") as mock_get:
            mock_get.return_value = _team_info("team-guid-001", "DevOps Team")
            result = proj.get_team_by_id("team-guid-001")
        assert isinstance(result, Team)

    def test_get_team_by_id_passes_id(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_team") as mock_get:
            mock_get.return_value = _team_info()
            proj.get_team_by_id("team-guid-001")
        assert mock_get.call_args.args[2] == "team-guid-001"


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


class TestProjectApprovePipeline:
    def test_approve_pipeline_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project._build.approve_pipeline") as mock_approve:
            proj.approve_pipeline("approval-uuid-123")
        mock_approve.assert_called_once_with(
            proj.api_call, "approval-uuid-123", comment=""
        )

    def test_approve_pipeline_passes_comment(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project._build.approve_pipeline") as mock_approve:
            proj.approve_pipeline("uuid", comment="LGTM")
        call = mock_approve.call_args
        assert call.kwargs["comment"] == "LGTM"

    def test_reject_pipeline_delegates(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project._build.reject_pipeline") as mock_reject:
            proj.reject_pipeline("approval-uuid-456")
        mock_reject.assert_called_once_with(
            proj.api_call, "approval-uuid-456", comment=""
        )

    def test_reject_pipeline_passes_comment(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project._build.reject_pipeline") as mock_reject:
            proj.reject_pipeline("uuid", comment="Needs changes")
        call = mock_reject.call_args
        assert call.kwargs["comment"] == "Needs changes"


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

    def test_create_variable_group_returns_wrapper(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info(group_id=99, name="NewGroup")
        with (
            patch("pyado.oop.project.raw.post_variable_group") as mock_post,
            patch("pyado.oop.project.raw.get_variable_group_api_call") as mock_ac,
        ):
            mock_post.return_value = created_info
            mock_ac.return_value = _api_call()
            result = proj.create_variable_group(
                "NewGroup", {"KEY": VariableInfo(value="val")}
            )
        assert isinstance(result, VariableGroup)
        assert result.info is created_info

    def test_create_variable_group_passes_name_and_variables(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info(group_id=5, name="Grp")
        variables = {"K": VariableInfo(value="v")}
        with (
            patch("pyado.oop.project.raw.post_variable_group") as mock_post,
            patch("pyado.oop.project.raw.get_variable_group_api_call"),
        ):
            mock_post.return_value = created_info
            proj.create_variable_group("Grp", variables)
        request = mock_post.call_args.args[1]
        assert request.name == "Grp"
        assert request.variables == variables

    def test_create_variable_group_passes_description(self) -> None:
        proj = _make_project()
        created_info = _variable_group_info()
        with (
            patch("pyado.oop.project.raw.post_variable_group") as mock_post,
            patch("pyado.oop.project.raw.get_variable_group_api_call"),
        ):
            mock_post.return_value = created_info
            proj.create_variable_group("G", {}, description="My description")
        request = mock_post.call_args.args[1]
        assert request.description == "My description"


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
        node = ClassificationNode.model_validate({"id": 1, "name": "Sprint 2"})
        with patch("pyado.oop.project.raw.create_classification_node") as mock_create:
            mock_create.return_value = node
            result = proj.create_iteration(
                "Sprint 2",
                start_date=date(2024, 2, 1),
                finish_date=date(2024, 2, 14),
            )
        assert isinstance(result, Iteration)
        assert result.name == "Sprint 2"
        assert mock_create.call_args.args[1].name == "Sprint 2"

    def test_get_area_node_returns_area(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _area_node()
            result = proj.get_area_node()
        assert isinstance(result, Area)

    def test_get_area_node_passes_path(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _area_node()
            proj.get_area_node("Team A")
        assert mock_get.call_args.args[1] == "Team A"

    def test_get_area_node_passes_depth(self) -> None:
        proj = _make_project()
        with patch("pyado.oop.project.raw.get_classification_node") as mock_get:
            mock_get.return_value = _area_node()
            proj.get_area_node(depth=2)
        assert mock_get.call_args.kwargs["depth"] == 2

    def test_create_iteration_without_dates_passes_none_attributes(self) -> None:
        proj = _make_project()
        node = ClassificationNode.model_validate({"id": 1, "name": "Sprint 3"})
        with patch("pyado.oop.project.raw.create_classification_node") as mock_create:
            mock_create.return_value = node
            proj.create_iteration("Sprint 3")
        assert mock_create.call_args.args[1].attributes is None

    def test_create_area_delegates(self) -> None:
        proj = _make_project()
        node = ClassificationNode.model_validate({"id": 1, "name": "Backend"})
        with patch("pyado.oop.project.raw.create_classification_node") as mock_create:
            mock_create.return_value = node
            result = proj.create_area("Backend")
        assert isinstance(result, Area)
        assert result.name == "Backend"
        assert mock_create.call_args.args[1].name == "Backend"


class TestProjectIterPullRequests:
    def test_iter_pull_requests_yields_pull_requests(self) -> None:
        item = _pr_list_item(55)
        item.repository = MagicMock()
        item.repository.id = REPO_ID
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_repo_call,
            patch("pyado.oop.project.raw.get_repository_info") as mock_repo_info,
            patch("pyado.oop.project.raw.get_pull_request_api_call") as mock_pr_call,
        ):
            mock_iter.return_value = iter([item])
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            result = list(_make_project().iter_pull_requests())
        assert len(result) == 1
        assert result[0].id == 55

    def test_iter_pull_requests_uses_no_status_by_default(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call"),
            patch("pyado.oop.project.raw.get_repository_info"),
            patch("pyado.oop.project.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_pull_requests())
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status is None

    def test_iter_pull_requests_custom_criteria_overrides_status(self) -> None:
        custom = PullRequestSearchCriteria(status=PullRequestStatus.COMPLETED)
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call"),
            patch("pyado.oop.project.raw.get_repository_info"),
            patch("pyado.oop.project.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_pull_requests(criteria=custom))
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == "completed"

    def test_iter_pull_requests_passes_expand(self) -> None:
        with (
            patch("pyado.oop.project.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.project.raw.get_repository_api_call"),
            patch("pyado.oop.project.raw.get_repository_info"),
            patch("pyado.oop.project.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_project().iter_pull_requests(expand="reviewers"))
        assert mock_iter.call_args.kwargs["expand"] == "reviewers"


class TestProjectCreateWorkItemRaises:
    def test_raises_when_work_item_type_in_fields(self) -> None:
        with pytest.raises(ValueError, match="WorkItemType"):
            _make_project().create_work_item(
                "Task",
                {"System.WorkItemType": "Bug"},
            )


class TestProjectGetPullRequestWithRepoId:
    def test_get_pull_request_with_repo_id_fetches_directly(self) -> None:
        pr_info = _pr_created(77)
        with (
            patch("pyado.oop.project.raw.get_repository_api_call") as mock_repo_call,
            patch("pyado.oop.project.raw.get_repository_info") as mock_repo_info,
            patch("pyado.oop.project.raw.get_pull_request_api_call") as mock_pr_call,
            patch("pyado.oop.project.raw.get_pull_request_details") as mock_pr_details,
        ):
            mock_repo_call.return_value = _api_call()
            mock_repo_info.return_value = _repo_info()
            mock_pr_call.return_value = _api_call()
            mock_pr_details.return_value = pr_info
            result = _make_project().get_pull_request(77, repo_id=REPO_ID)
        assert isinstance(result, PullRequest)
        mock_pr_details.assert_called_once()


class TestProjectGetPipeline:
    def test_returns_matching_pipeline(self) -> None:
        proj = _make_project()
        info = _pipeline_info(3)
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([info])
            result = proj.get_pipeline("MyPipeline")
        assert result.id == 3
        assert result.name == "MyPipeline"

    def test_raises_value_error_when_not_found(self) -> None:
        proj = _make_project()
        info = _pipeline_info(3)
        with patch("pyado.oop.project.raw.iter_pipelines") as mock_iter:
            mock_iter.return_value = iter([info])
            with pytest.raises(ValueError, match="MissingPipeline"):
                proj.get_pipeline("MissingPipeline")


class TestProjectListMethods:
    def test_list_repositories_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_repositories", return_value=iter([])):
            assert proj.list_repositories() == []

    def test_list_active_prs_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_active_prs", return_value=iter([])):
            assert proj.list_active_prs() == []

    def test_list_pull_requests_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_pull_requests", return_value=iter([])):
            assert proj.list_pull_requests() == []

    def test_list_work_items_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_work_items", return_value=iter([])):
            assert proj.list_work_items("SELECT [Id] FROM WorkItems") == []

    def test_list_builds_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_builds", return_value=iter([])):
            assert proj.list_builds() == []

    def test_list_pipeline_definitions_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_pipeline_definitions", return_value=iter([])):
            assert proj.list_pipeline_definitions() == []

    def test_list_pipelines_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_pipelines", return_value=iter([])):
            assert proj.list_pipelines() == []

    def test_list_pending_approvals_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_pending_approvals", return_value=iter([])):
            assert proj.list_pending_approvals() == []

    def test_list_variable_groups_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_variable_groups", return_value=iter([])):
            assert proj.list_variable_groups() == []

    def test_list_team_sprint_iterations_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_team_sprint_iterations", return_value=iter([])):
            assert proj.list_team_sprint_iterations("MyTeam") == []

    def test_list_teams_delegates(self) -> None:
        proj = _make_project()
        with patch.object(proj, "iter_teams", return_value=iter([])):
            assert proj.list_teams() == []


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_wit_query(name: str = "My Queries") -> WorkItemQuery:
    return WorkItemQuery.model_validate(
        {"id": "00000000-0000-0000-0000-000000000001", "name": name}
    )
