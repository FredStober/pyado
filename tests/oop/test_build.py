"""Tests for pyado.oop._build — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.oop import (
    ActiveBuildTask,
    Build,
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
    Pipeline,
    Project,
)
from pyado.oop._build import (
    cancel_build,
    cancel_pipeline_run,
    iter_build_work_item_ids,
    start_build,
)
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildExpand,
    BuildIssue,
    BuildIssueType,
    BuildLogInfo,
    BuildRecordInfo,
    BuildRecordState,
    BuildRecordType,
    BuildResult,
    BuildStatus,
    PipelineRunInfo,
    WorkItemRef,
    get_build_api_call,
)
from tests.conftest import NOW_ISO, _make_mock_response
from tests.oop.conftest import (
    ACTIVE_JOB_ID,
    HUB_NAME,
    JOB_ID,
    ORG_URL,
    PHASE_ID,
    PLAN_ID,
    STAGE_ID,
    TASK_ID,
    TASK_INSTANCE_ID,
    TIMELINE_ID,
    _api_call,
    _build_details,
    _make_active_task,
    _make_all_records,
    _make_build,
    _make_project,
    _make_service,
    _make_tl_job,
    _make_tl_phase,
    _make_tl_stage,
    _make_wi,
    _pipeline_run_info,
    _project_info,
    _record,
    _task_record,
    _work_item_info,
)


def make_build_details_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid BuildDetails dict.

    Returns:
        A dict with all required BuildDetails fields populated.
    """
    details: dict[str, Any] = {
        "id": 1001,
        "buildNumber": "20240115.1",
        "status": "completed",
        "result": "succeeded",
        "queueTime": NOW_ISO,
        "startTime": NOW_ISO,
        "finishTime": NOW_ISO,
        "sourceBranch": "refs/heads/main",
        "sourceVersion": "abc123def456",  # pragma: allowlist secret
        "definition": {"id": 5, "name": "my-pipeline"},
        "requestedBy": {"id": "user-id", "displayName": "Alice"},
    }
    details.update(overrides)
    return details


class TestIterBuildWorkItemIds:
    """Tests for iter_build_work_item_ids."""

    @staticmethod
    def test_yields_work_item_ids(api_call: ApiCall) -> None:
        """Yields integer IDs from the value list."""
        response_json = {"value": [{"id": "10"}, {"id": "20"}, {"id": "30"}]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_work_item_ids(api_call))
        assert result == [10, 20, 30]

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no IDs."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_work_item_ids(api_call))
        assert result == []

    @staticmethod
    def test_paginates_when_first_page_is_full(api_call: ApiCall) -> None:
        """Fetches a second page when the first response has exactly 100 items."""
        first_page = {"value": [{"id": str(idx)} for idx in range(100)]}
        second_page = {"value": [{"id": "100"}]}
        mock_first = _make_mock_response(first_page)
        mock_second = _make_mock_response(second_page)
        with patch.object(
            requests.Session, "request", side_effect=[mock_first, mock_second]
        ):
            result = list(iter_build_work_item_ids(api_call))
        assert len(result) == 101
        assert result[0] == 0
        assert result[-1] == 100


class TestQueueBuild:
    """Tests for start_build."""

    @staticmethod
    def test_queues_build_with_definition_id(api_call: ApiCall) -> None:
        """Returns a BuildDetails for the newly queued build."""
        response_data = make_build_details_dict(id=999, status="notStarted")
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = start_build(api_call, definition_id=7)
        assert isinstance(result, BuildDetails)
        assert result.id == 999
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body["definition"]["id"] == 7

    @staticmethod
    def test_includes_source_branch_when_provided(api_call: ApiCall) -> None:
        """Includes sourceBranch in the payload when provided."""
        response_data = make_build_details_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            start_build(api_call, definition_id=7, source_branch="refs/heads/main")
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body.get("sourceBranch") == "refs/heads/main"

    @staticmethod
    def test_includes_source_version_when_provided(api_call: ApiCall) -> None:
        """Includes sourceVersion in the payload when provided."""
        response_data = make_build_details_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            start_build(api_call, definition_id=7, source_version="abc123")
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body.get("sourceVersion") == "abc123"

    @staticmethod
    def test_includes_parameters_when_provided(api_call: ApiCall) -> None:
        """Serialises the parameters dict as a JSON string in the payload."""
        response_data = make_build_details_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            start_build(api_call, definition_id=7, parameters={"env": "staging"})
        body = mock_req.call_args.kwargs.get("json") or {}
        assert json.loads(body["parameters"]) == {"env": "staging"}


class TestCancelPipelineRun:
    """Tests for cancel_pipeline_run."""

    @staticmethod
    def test_patches_build_then_returns_pipeline_run(api_call: ApiCall) -> None:
        """PATCHes the build with cancelling status then re-fetches the pipeline run."""
        build_response = make_build_details_dict(id=55, status="cancelling")
        run_response = {
            "id": 55,
            "name": "20240101.55",
            "state": "canceling",
            "pipeline": {
                "id": 7,
                "revision": 1,
                "name": "MyPipeline",
                "folder": "\\",
                "url": "https://dev.azure.com/org/proj/_apis/pipelines/7",
            },
            "createdDate": NOW_ISO,
            "url": "https://dev.azure.com/org/proj/_apis/pipelines/7/runs/55",
        }
        mock_patch = _make_mock_response(build_response)
        mock_get = _make_mock_response(run_response)
        with patch.object(
            requests.Session,
            "request",
            side_effect=[mock_patch, mock_get],
        ) as mock_req:
            result = cancel_pipeline_run(api_call, pipeline_id=7, run_id=55)
        assert isinstance(result, PipelineRunInfo)
        assert result.id == 55
        assert mock_req.call_args_list[0].args[0] == "PATCH"
        assert mock_req.call_args_list[1].args[0] == "GET"


class TestCancelBuild:
    """Tests for cancel_build."""

    @staticmethod
    def test_patches_build_with_cancelling_status(api_call: ApiCall) -> None:
        """Sends PATCH with status=cancelling and returns updated BuildDetails."""
        build_api_call = get_build_api_call(api_call, 100)
        response_data = make_build_details_dict(status="cancelling")
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = cancel_build(build_api_call)
        assert isinstance(result, BuildDetails)
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("status") == BuildStatus.CANCELLING


# ---------------------------------------------------------------------------
# OOP Build tests
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

    def test_source_version(self) -> None:
        assert _make_build().source_version == "abc123"

    def test_queue_time_returns_datetime(self) -> None:
        build = _make_build()
        assert build.queue_time is not None

    def test_queue_time_none_when_absent(self) -> None:
        details = _build_details()
        details.queue_time = None
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, api_call, details, proj._service)
        assert build.queue_time is None

    def test_requested_by_display_name(self) -> None:
        assert _make_build().requested_by == "User"

    def test_requested_for_display_name(self) -> None:
        assert _make_build().requested_for == "User"

    def test_requested_for_none_when_absent(self) -> None:
        details = _build_details()
        details.requested_for = None
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, api_call, details, proj._service)
        assert build.requested_for is None

    def test_refresh_refetches(self) -> None:
        build = _make_build()
        new_info = _build_details(build_id=100)
        new_info.build_number = "20240102.1"
        with patch("pyado.oop.build.raw.get_build_details") as mock_get:
            mock_get.return_value = new_info
            build.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = build.info
        mock_get.assert_called_once()

    def test_refresh_stores_expand_and_forwards_on_fetch(self) -> None:
        build = _make_build()
        with patch("pyado.oop.build.raw.get_build_details") as mock_get:
            mock_get.return_value = _build_details()
            build.refresh(expand=BuildExpand.ALL)
            _ = build.info
        assert mock_get.call_args.kwargs["expand"] == BuildExpand.ALL

    def test_refresh_preserves_existing_expand_when_none_passed(self) -> None:
        build = _make_build()
        with patch("pyado.oop.build.raw.get_build_details") as mock_get:
            mock_get.return_value = _build_details()
            build.refresh(expand=BuildExpand.VARIABLES)
            _ = build.info
            build.refresh()
            _ = build.info
        assert mock_get.call_args.kwargs["expand"] == BuildExpand.VARIABLES

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
        with patch("pyado.oop.build._build.iter_build_work_item_ids") as mock_iter:
            mock_iter.return_value = iter([42, 43])
            result = list(_make_build().iter_work_item_ids())
        assert result == [42, 43]

    def test_iter_work_item_ids_between_delegates(self) -> None:
        ref_a = WorkItemRef(id=10, url=None)
        ref_b = WorkItemRef(id=20, url=None)
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([ref_a, ref_b])
            result = list(newer.iter_work_item_ids_between(older))
        assert result == [10, 20]
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args.args
        assert call_args[1] == 50
        assert call_args[2] == 100

    def test_iter_work_item_ids_between_passes_top(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([])
            list(newer.iter_work_item_ids_between(older, top=5))
        assert mock_iter.call_args.kwargs["top"] == 5

    def test_get_log_text_delegates(self) -> None:
        with patch("pyado.oop.build.raw.get_build_log") as mock_log:
            mock_log.return_value = "log line 1\nlog line 2\n"
            text = _make_build().get_log_text(3)
        assert text == "log line 1\nlog line 2\n"
        assert mock_log.call_args.args[1] == 3

    def test_result_returns_build_result(self) -> None:
        assert _make_build().result == BuildResult.SUCCEEDED

    def test_source_branch_returns_branch_name(self) -> None:
        assert _make_build().source_branch == "refs/heads/main"

    def test_start_time_returns_none_when_not_set(self) -> None:
        assert _make_build().start_time is None

    def test_finish_time_returns_none_when_not_set(self) -> None:
        assert _make_build().finish_time is None


# ---------------------------------------------------------------------------
# OOP Build timeline tests
# ---------------------------------------------------------------------------


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
# OOP ActiveBuildTask tests
# ---------------------------------------------------------------------------


class TestActiveBuildTask:
    # ------------------------------------------------------------------
    # Navigation

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
        with patch("pyado.oop.active_build_task._build.send_job_feed") as mock_feed:
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
            patch("pyado.oop.active_build_task._build.send_job_feed") as mock_feed,
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch("pyado.oop.active_build_task.raw.get_log_api_call"),
            patch("pyado.oop.active_build_task.raw.post_job_logs") as mock_logs,
        ):
            mock_iter.return_value = iter([record])
            _make_active_task().send_message(["a", "b"])
        assert mock_feed.call_count == 1
        # Messages are joined into a single post_job_logs call.
        assert mock_logs.call_count == 1
        assert mock_logs.call_args[0][1] == "a\nb"

    # ------------------------------------------------------------------
    # add_issues
    # ------------------------------------------------------------------

    def test_add_issues_patches_timeline(self) -> None:
        record = _task_record()
        issue = BuildIssue(message="boom", type=BuildIssueType.ERROR)
        with (
            patch("pyado.oop.active_build_task.raw.iter_timeline_records") as mock_iter,
            patch(
                "pyado.oop.active_build_task._build.update_timeline_records"
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
        with patch("pyado.oop.active_build_task._build.send_job_event") as mock_event:
            _make_active_task().complete(succeeded=True)
        assert mock_event.call_count == 1
        _, task_id, job_id, _event_name, event_result = mock_event.call_args.args
        assert task_id == TASK_INSTANCE_ID
        assert job_id == ACTIVE_JOB_ID
        assert event_result == "succeeded"

    def test_complete_failed_sends_event(self) -> None:
        with patch("pyado.oop.active_build_task._build.send_job_event") as mock_event:
            _make_active_task().complete(succeeded=False)
        _, _task_id, _job_id, _event_name, event_result = mock_event.call_args.args
        assert event_result == "failed"


# ---------------------------------------------------------------------------
# OOP Build cancel tests
# ---------------------------------------------------------------------------


class TestBuildCancel:
    def test_cancel_delegates(self) -> None:
        build = _make_build()
        cancelled = _build_details()
        with patch("pyado.oop.build._build.cancel_build") as mock_cancel:
            mock_cancel.return_value = cancelled
            build.cancel()
        mock_cancel.assert_called_once_with(build.api_call)
        assert build._info is cancelled

    def test_cancel_run_delegates(self) -> None:
        build = _make_build(build_id=100, pipeline_id=5)
        run_info = _pipeline_run_info(100, 5)
        with patch("pyado.oop.build._build.cancel_pipeline_run") as mock_cancel:
            mock_cancel.return_value = run_info
            result = build.cancel_run()
        mock_cancel.assert_called_once_with(build.project.api_call, 5, 100)
        assert result is run_info

    def test_cancel_run_uses_definition_id(self) -> None:
        build = _make_build(build_id=200, pipeline_id=99)
        with patch("pyado.oop.build._build.cancel_pipeline_run") as mock_cancel:
            mock_cancel.return_value = _pipeline_run_info(200, 99)
            build.cancel_run()
        call = mock_cancel.call_args
        assert call.args[1] == 99  # pipeline_id from definition


# ---------------------------------------------------------------------------
# OOP Build retry tests
# ---------------------------------------------------------------------------


class TestBuildRetry:
    def test_retry_returns_new_build(self) -> None:

        new_details = _build_details(build_id=200, pipeline_id=1)
        new_api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/200")
        with (
            patch("pyado.oop.build._build.start_build") as mock_start,
            patch("pyado.oop.build.raw.get_build_api_call") as mock_api,
        ):
            mock_start.return_value = new_details
            mock_api.return_value = new_api_call
            result = _make_build(build_id=100).retry()
        assert isinstance(result, Build)
        assert result.id == 200

    def test_retry_passes_definition_id_and_branch(self) -> None:
        with (
            patch("pyado.oop.build._build.start_build") as mock_start,
            patch("pyado.oop.build.raw.get_build_api_call") as mock_api,
        ):
            mock_start.return_value = _build_details(build_id=200, pipeline_id=5)
            mock_api.return_value = _api_call()
            _make_build(build_id=100, pipeline_id=5).retry()
        assert mock_start.call_args.args[1] == 5
        assert mock_start.call_args.kwargs["source_branch"] == "refs/heads/main"


# ---------------------------------------------------------------------------
# OOP Build iter_work_items tests
# ---------------------------------------------------------------------------


class TestBuildIterWorkItems:
    def test_iter_work_items_yields_work_items(self) -> None:
        build = _make_build(build_id=100)
        wi_info = _work_item_info(5)
        with (
            patch("pyado.oop.build._build.iter_build_work_item_ids") as mock_ids,
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_ids.return_value = iter([5])
            mock_batch.return_value = [wi_info]
            mock_api.return_value = _api_call()
            result = list(build.iter_work_items())
        assert len(result) == 1
        assert result[0].id == 5

    def test_iter_work_items_empty_when_no_ids(self) -> None:
        build = _make_build(build_id=100)
        with patch("pyado.oop.build._build.iter_build_work_item_ids") as mock_ids:
            mock_ids.return_value = iter([])
            result = list(build.iter_work_items())
        assert result == []


# ---------------------------------------------------------------------------
# OOP Build update tests
# ---------------------------------------------------------------------------


class TestBuildUpdate:
    def test_update_delegates_to_patch_build(self) -> None:
        build = _make_build()
        with patch("pyado.oop.build.raw.patch_build") as mock_patch:
            mock_patch.return_value = _build_details()
            build.update(BuildStatus.CANCELLING)
        mock_patch.assert_called_once_with(build.api_call, BuildStatus.CANCELLING)

    def test_update_stores_returned_info(self) -> None:
        build = _make_build()
        new_info = _build_details(build_id=100)
        new_info.build_number = "20240201.1"
        with patch("pyado.oop.build.raw.patch_build") as mock_patch:
            mock_patch.return_value = new_info
            build.update(BuildStatus.CANCELLING)
        assert build.info is new_info


# ---------------------------------------------------------------------------
# OOP Build iter_work_items_between tests
# ---------------------------------------------------------------------------


class TestBuildIterWorkItemsBetween:
    def test_yields_work_items(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        ref_a = WorkItemRef(id=10, url=None)
        ref_b = WorkItemRef(id=20, url=None)
        wi_a = _make_wi(10)
        wi_b = _make_wi(20)
        with (
            patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter,
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_iter.return_value = iter([ref_a, ref_b])
            mock_batch.return_value = [wi_a.info, wi_b.info]
            mock_api.side_effect = lambda _call, _id: _api_call()
            result = list(newer.iter_work_items_between(older))
        assert len(result) == 2
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args.args
        assert call_args[1] == 50
        assert call_args[2] == 100

    def test_passes_top_parameter(self) -> None:
        older = _make_build(build_id=1)
        newer = _make_build(build_id=2)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([])
            list(newer.iter_work_items_between(older, top=5))
        assert mock_iter.call_args.kwargs.get("top") == 5

    def test_yields_nothing_when_no_ids(self) -> None:
        older = _make_build(build_id=1)
        newer = _make_build(build_id=2)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as mock_iter:
            mock_iter.return_value = iter([])
            result = list(newer.iter_work_items_between(older))
        assert result == []


# ---------------------------------------------------------------------------
# OOP Build find_task tests
# ---------------------------------------------------------------------------


class TestBuildFindTask:
    @staticmethod
    def _record(name: str) -> BuildRecordInfo:

        return BuildRecordInfo.model_validate(
            {
                "attempt": 1,
                "changeId": None,
                "currentOperation": None,
                "details": None,
                "finishTime": NOW_ISO,
                "id": str(uuid4()),
                "identifier": None,
                "lastModified": NOW_ISO,
                "log": None,
                "name": name,
                "refName": None,
                "parentId": None,
                "percentComplete": None,
                "previousAttempts": [],
                "result": None,
                "resultCode": None,
                "startTime": None,
                "state": "pending",
                "task": None,
                "type": "Task",
                "url": None,
                "workerName": None,
            }
        )

    def test_find_task_returns_matching_record(self) -> None:
        record = self._record("Deploy")
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([record])
            result = _make_build().find_task(lambda r: r.name == "Deploy")
        assert result is record

    def test_find_task_returns_none_when_no_match(self) -> None:
        record = self._record("Other")
        with patch("pyado.oop.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([record])
            result = _make_build().find_task(lambda r: r.name == "Deploy")
        assert result is None


# ---------------------------------------------------------------------------
# OOP Build iter_logs tests
# ---------------------------------------------------------------------------


class TestBuildIterLogs:
    def test_yields_build_log_info(self) -> None:
        build = _make_build(build_id=100)
        log_info = BuildLogInfo.model_validate(
            {
                "id": 7,
                "type": "Container",
                "url": "https://dev.azure.com/org/_apis/build/builds/100/logs/7",
            }
        )
        with patch("pyado.oop.build.raw.iter_build_logs") as mock_iter:
            mock_iter.return_value = iter([log_info])
            result = list(build.iter_logs())
        assert len(result) == 1
        assert result[0].id == 7
        mock_iter.assert_called_once_with(build._api_call)

    def test_yields_empty_when_no_logs(self) -> None:
        build = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_build_logs") as mock_iter:
            mock_iter.return_value = iter([])
            result = list(build.iter_logs())
        assert result == []


class TestBuildGetAllLogText:
    def test_joins_all_log_texts(self) -> None:
        build = _make_build(build_id=100)
        log_a = BuildLogInfo.model_validate(
            {
                "id": 1,
                "type": "Container",
                "url": "https://dev.azure.com/org/_apis/build/builds/100/logs/1",
            }
        )
        log_b = BuildLogInfo.model_validate(
            {
                "id": 2,
                "type": "Container",
                "url": "https://dev.azure.com/org/_apis/build/builds/100/logs/2",
            }
        )
        with (
            patch("pyado.oop.build.raw.iter_build_logs") as mock_iter,
            patch("pyado.oop.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter([log_a, log_b])
            mock_log.side_effect = lambda _call, log_id: f"text-{log_id}"
            result = build.get_all_log_text()
        assert result == "text-1\ntext-2"

    def test_custom_separator(self) -> None:
        build = _make_build(build_id=100)
        log_a = BuildLogInfo.model_validate(
            {
                "id": 1,
                "type": "Container",
                "url": "https://dev.azure.com/org/_apis/build/builds/100/logs/1",
            }
        )
        with (
            patch("pyado.oop.build.raw.iter_build_logs") as mock_iter,
            patch("pyado.oop.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter([log_a])
            mock_log.return_value = "log text"
            result = build.get_all_log_text(separator="---")
        assert result == "log text"

    def test_empty_when_no_logs(self) -> None:
        build = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_build_logs") as mock_iter:
            mock_iter.return_value = iter([])
            result = build.get_all_log_text()
        assert not result


class TestBuildListMethods:
    def test_list_artifacts_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_artifacts") as m:
            m.return_value = iter([])
            result = _make_build().list_artifacts()
        assert result == []

    def test_list_tags_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_tags") as m:
            m.return_value = iter([])
            result = _make_build().list_tags()
        assert result == []

    def test_list_timeline_records_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_timeline_records") as m:
            m.return_value = iter([])
            result = _make_build().list_timeline_records()
        assert result == []

    def test_list_logs_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_build_logs") as m:
            m.return_value = iter([])
            result = _make_build().list_logs()
        assert result == []

    def test_list_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.build._build.iter_build_work_item_ids") as m:
            m.return_value = iter([])
            result = _make_build().list_work_item_ids()
        assert result == []

    def test_list_work_items_delegates(self) -> None:
        with patch("pyado.oop.build._build.iter_build_work_item_ids") as m:
            m.return_value = iter([])
            result = _make_build().list_work_items()
        assert result == []

    def test_list_stages_delegates(self) -> None:
        with patch("pyado.oop.build.raw.iter_timeline_records") as m:
            m.return_value = iter([])
            result = _make_build().list_stages()
        assert result == []

    def test_list_work_items_between_delegates(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as m:
            m.return_value = iter([])
            result = newer.list_work_items_between(older)
        assert result == []

    def test_list_work_item_ids_between_delegates(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.build.raw.iter_work_items_between_builds") as m:
            m.return_value = iter([])
            result = newer.list_work_item_ids_between(older)
        assert result == []


class TestBuildTimelineListMethods:
    def test_stage_list_phases_delegates(self) -> None:
        all_records = _make_all_records()
        stage = _make_tl_stage(all_records)
        with patch.object(stage, "iter_phases", return_value=iter([])):
            assert stage.list_phases() == []

    def test_stage_list_jobs_delegates(self) -> None:
        all_records = _make_all_records()
        stage = _make_tl_stage(all_records)
        with patch.object(stage, "iter_jobs", return_value=iter([])):
            assert stage.list_jobs() == []

    def test_phase_list_jobs_delegates(self) -> None:
        all_records = _make_all_records(use_phase=True)
        phase = _make_tl_phase(all_records)
        with patch.object(phase, "iter_jobs", return_value=iter([])):
            assert phase.list_jobs() == []

    def test_job_list_tasks_delegates(self) -> None:
        all_records = _make_all_records()
        job = _make_tl_job(all_records)
        with patch.object(job, "iter_tasks", return_value=iter([])):
            assert job.list_tasks() == []


def _make_build_artifact(
    download_url: str | None = "https://example.com/artifact.zip",
) -> BuildArtifact:
    return BuildArtifact.model_validate(
        {
            "id": 1,
            "name": "drop",
            "resource": {
                "type": "Container",
                "url": "https://example.com/container",
                "downloadUrl": download_url,
            },
        }
    )


class TestBuildDownloadArtifact:
    def test_download_artifact_delegates_to_raw(self) -> None:
        build = _make_build()
        artifact = _make_build_artifact()
        with patch("pyado.oop.build.raw.get_build_artifact_bytes") as mock_dl:
            mock_dl.return_value = b"data"
            result = build.download_artifact(artifact)
        mock_dl.assert_called_once_with(build._api_call, artifact)
        assert result == b"data"

    def test_download_artifact_returns_none_when_no_url(self) -> None:
        build = _make_build()
        artifact = _make_build_artifact(download_url=None)
        with patch("pyado.oop.build.raw.get_build_artifact_bytes") as mock_dl:
            mock_dl.return_value = None
            result = build.download_artifact(artifact)
        assert result is None
