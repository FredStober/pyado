"""Tests for pyado.oop.pipelines._build — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import requests

from pyado.oop import (
    Build,
    Pipeline,
    Project,
)
from pyado.oop.pipelines._build import (
    cancel_build,
    cancel_pipeline_run,
    iter_build_work_item_ids,
    start_build,
)
from pyado.oop.pipelines.pipeline import PipelineRun
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildExpand,
    BuildLogInfo,
    BuildRecordInfo,
    BuildResult,
    BuildStatus,
    PipelineApprovalStatus,
    PipelineRunInfo,
    WorkItemRef,
    get_build_api_call,
)
from tests.conftest import NOW_ISO, _make_mock_response
from tests.oop.conftest import (
    ORG_URL,
    PHASE_ID,
    STAGE_ID,
    TASK_ID,
    TASK_INSTANCE_ID,
    _api_call,
    _build_details,
    _make_all_records,
    _make_build,
    _make_project,
    _make_service,
    _make_wi,
    _pipeline_run_info,
    _project_info,
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
        with patch("pyado.oop.pipelines.build.raw.get_build_details") as mock_get:
            mock_get.return_value = new_info
            build.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = build.info
        mock_get.assert_called_once()

    def test_refresh_stores_expand_and_forwards_on_fetch(self) -> None:
        build = _make_build()
        with patch("pyado.oop.pipelines.build.raw.get_build_details") as mock_get:
            mock_get.return_value = _build_details()
            build.refresh(expand=BuildExpand.ALL)
            _ = build.info
        assert mock_get.call_args.kwargs["expand"] == BuildExpand.ALL

    def test_refresh_preserves_existing_expand_when_none_passed(self) -> None:
        build = _make_build()
        with patch("pyado.oop.pipelines.build.raw.get_build_details") as mock_get:
            mock_get.return_value = _build_details()
            build.refresh(expand=BuildExpand.VARIABLES)
            _ = build.info
            build.refresh()
            _ = build.info
        assert mock_get.call_args.kwargs["expand"] == BuildExpand.VARIABLES

    def test_iter_artifacts_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_build_artifacts") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_build().iter_artifacts())
        mock_iter.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.post_build_tag") as mock_tag:
            _make_build().add_tag("tag-a")
        mock_tag.assert_called_once()

    def test_iter_tags_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_build_tags") as mock_iter:
            mock_iter.return_value = iter(["tag-x"])
            result = list(_make_build().iter_tags())
        assert result == ["tag-x"]

    def test_remove_tag_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.delete_build_tag") as mock_del:
            _make_build().remove_tag("old-tag")
        mock_del.assert_called_once()

    def test_iter_timeline_records_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_build().iter_timeline_records())
        assert len(result) == 1

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch(
            "pyado.oop.pipelines.build._build.iter_build_work_item_ids"
        ) as mock_iter:
            mock_iter.return_value = iter([42, 43])
            result = list(_make_build().iter_work_item_ids())
        assert result == [42, 43]

    def test_iter_work_item_ids_between_delegates(self) -> None:
        ref_a = WorkItemRef(id=10, url=None)
        ref_b = WorkItemRef(id=20, url=None)
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch(
            "pyado.oop.pipelines.build.raw.iter_work_items_between_builds"
        ) as mock_iter:
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
        with patch(
            "pyado.oop.pipelines.build.raw.iter_work_items_between_builds"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            list(newer.iter_work_item_ids_between(older, top=5))
        assert mock_iter.call_args.kwargs["top"] == 5

    def test_get_log_text_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.get_build_log") as mock_log:
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

    def test_pipeline_run_returns_pipeline_run(self) -> None:
        build = _make_build(build_id=55, pipeline_id=7)
        run_info = _pipeline_run_info(run_id=55)
        with patch(
            "pyado.oop.pipelines.build.raw.get_pipeline_run", return_value=run_info
        ):
            result = build.pipeline_run
        assert isinstance(result, PipelineRun)
        assert result.id == 55


# ---------------------------------------------------------------------------
# OOP Build cancel tests
# ---------------------------------------------------------------------------


class TestBuildCancel:
    def test_cancel_delegates(self) -> None:
        build = _make_build()
        cancelled = _build_details()
        with patch("pyado.oop.pipelines.build._build.cancel_build") as mock_cancel:
            mock_cancel.return_value = cancelled
            result = build.cancel()
        mock_cancel.assert_called_once_with(build.api_call)
        assert build._info is cancelled
        assert result is build

    def test_cancel_run_delegates(self) -> None:
        build = _make_build(build_id=100, pipeline_id=5)
        run_info = _pipeline_run_info(100, 5)
        with patch(
            "pyado.oop.pipelines.build._build.cancel_pipeline_run"
        ) as mock_cancel:
            mock_cancel.return_value = run_info
            result = build.cancel_run()
        mock_cancel.assert_called_once_with(build.project.api_call, 5, 100)
        assert result is run_info

    def test_cancel_run_uses_definition_id(self) -> None:
        build = _make_build(build_id=200, pipeline_id=99)
        with patch(
            "pyado.oop.pipelines.build._build.cancel_pipeline_run"
        ) as mock_cancel:
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
            patch("pyado.oop.pipelines.build._build.start_build") as mock_start,
            patch("pyado.oop.pipelines.build.raw.get_build_api_call") as mock_api,
        ):
            mock_start.return_value = new_details
            mock_api.return_value = new_api_call
            result = _make_build(build_id=100).retry()
        assert isinstance(result, Build)
        assert result.id == 200

    def test_retry_passes_definition_id_and_branch(self) -> None:
        with (
            patch("pyado.oop.pipelines.build._build.start_build") as mock_start,
            patch("pyado.oop.pipelines.build.raw.get_build_api_call") as mock_api,
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
            patch(
                "pyado.oop.pipelines.build._build.iter_build_work_item_ids"
            ) as mock_ids,
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
        with patch(
            "pyado.oop.pipelines.build._build.iter_build_work_item_ids"
        ) as mock_ids:
            mock_ids.return_value = iter([])
            result = list(build.iter_work_items())
        assert result == []


# ---------------------------------------------------------------------------
# OOP Build update tests
# ---------------------------------------------------------------------------


class TestBuildUpdate:
    def test_update_delegates_to_patch_build(self) -> None:
        build = _make_build()
        with patch("pyado.oop.pipelines.build.raw.patch_build") as mock_patch:
            mock_patch.return_value = _build_details()
            build.update(BuildStatus.CANCELLING)
        mock_patch.assert_called_once_with(build.api_call, BuildStatus.CANCELLING)

    def test_update_stores_returned_info(self) -> None:
        build = _make_build()
        new_info = _build_details(build_id=100)
        new_info.build_number = "20240201.1"
        with patch("pyado.oop.pipelines.build.raw.patch_build") as mock_patch:
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
            patch(
                "pyado.oop.pipelines.build.raw.iter_work_items_between_builds"
            ) as mock_iter,
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
        with patch(
            "pyado.oop.pipelines.build.raw.iter_work_items_between_builds"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            list(newer.iter_work_items_between(older, top=5))
        assert mock_iter.call_args.kwargs.get("top") == 5

    def test_yields_nothing_when_no_ids(self) -> None:
        older = _make_build(build_id=1)
        newer = _make_build(build_id=2)
        with patch(
            "pyado.oop.pipelines.build.raw.iter_work_items_between_builds"
        ) as mock_iter:
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
        with patch("pyado.oop.pipelines.build.raw.iter_timeline_records") as mock_iter:
            mock_iter.return_value = iter([record])
            result = _make_build().find_task(lambda r: r.name == "Deploy")
        assert result is record

    def test_find_task_returns_none_when_no_match(self) -> None:
        record = self._record("Other")
        with patch("pyado.oop.pipelines.build.raw.iter_timeline_records") as mock_iter:
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
        with patch("pyado.oop.pipelines.build.raw.iter_build_logs") as mock_iter:
            mock_iter.return_value = iter([log_info])
            result = list(build.iter_logs())
        assert len(result) == 1
        assert result[0].id == 7
        mock_iter.assert_called_once_with(build._api_call)

    def test_yields_empty_when_no_logs(self) -> None:
        build = _make_build(build_id=100)
        with patch("pyado.oop.pipelines.build.raw.iter_build_logs") as mock_iter:
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
            patch("pyado.oop.pipelines.build.raw.iter_build_logs") as mock_iter,
            patch("pyado.oop.pipelines.build.raw.get_build_log") as mock_log,
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
            patch("pyado.oop.pipelines.build.raw.iter_build_logs") as mock_iter,
            patch("pyado.oop.pipelines.build.raw.get_build_log") as mock_log,
        ):
            mock_iter.return_value = iter([log_a])
            mock_log.return_value = "log text"
            result = build.get_all_log_text(separator="---")
        assert result == "log text"

    def test_empty_when_no_logs(self) -> None:
        build = _make_build(build_id=100)
        with patch("pyado.oop.pipelines.build.raw.iter_build_logs") as mock_iter:
            mock_iter.return_value = iter([])
            result = build.get_all_log_text()
        assert not result


class TestBuildListMethods:
    def test_list_artifacts_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_build_artifacts") as m:
            m.return_value = iter([])
            result = _make_build().list_artifacts()
        assert result == []

    def test_list_tags_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_build_tags") as m:
            m.return_value = iter([])
            result = _make_build().list_tags()
        assert result == []

    def test_list_timeline_records_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_timeline_records") as m:
            m.return_value = iter([])
            result = _make_build().list_timeline_records()
        assert result == []

    def test_list_logs_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build.raw.iter_build_logs") as m:
            m.return_value = iter([])
            result = _make_build().list_logs()
        assert result == []

    def test_list_work_item_ids_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build._build.iter_build_work_item_ids") as m:
            m.return_value = iter([])
            result = _make_build().list_work_item_ids()
        assert result == []

    def test_list_work_items_delegates(self) -> None:
        with patch("pyado.oop.pipelines.build._build.iter_build_work_item_ids") as m:
            m.return_value = iter([])
            result = _make_build().list_work_items()
        assert result == []

    def test_list_work_items_between_delegates(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.pipelines.build.raw.iter_work_items_between_builds") as m:
            m.return_value = iter([])
            result = newer.list_work_items_between(older)
        assert result == []

    def test_list_work_item_ids_between_delegates(self) -> None:
        older = _make_build(build_id=50)
        newer = _make_build(build_id=100)
        with patch("pyado.oop.pipelines.build.raw.iter_work_items_between_builds") as m:
            m.return_value = iter([])
            result = newer.list_work_item_ids_between(older)
        assert result == []


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
        with patch("pyado.oop.pipelines.build.raw.get_build_artifact_bytes") as mock_dl:
            mock_dl.return_value = b"data"
            result = build.download_artifact(artifact)
        mock_dl.assert_called_once_with(build._api_call, artifact)
        assert result == b"data"

    def test_download_artifact_returns_none_when_no_url(self) -> None:
        build = _make_build()
        artifact = _make_build_artifact(download_url=None)
        with patch("pyado.oop.pipelines.build.raw.get_build_artifact_bytes") as mock_dl:
            mock_dl.return_value = None
            result = build.download_artifact(artifact)
        assert result is None


class TestBuildIterApprovals:
    """Tests for Build.iter_approvals and Build.list_approvals."""

    def test_iter_approvals_scopes_to_build_run_id(self) -> None:
        """Passes the build ID as pipeline_run_ids to raw.iter_approvals."""
        build = _make_build(build_id=42)
        with patch(
            "pyado.oop.pipelines.build.raw.iter_approvals", return_value=iter([])
        ) as mock_iter:
            list(build.iter_approvals())
        mock_iter.assert_called_once_with(
            build._project.api_call,
            state=None,
            pipeline_run_ids=[42],
        )

    def test_iter_approvals_passes_state_filter(self) -> None:
        """Forwards the state argument to raw.iter_approvals."""
        build = _make_build(build_id=7)
        with patch(
            "pyado.oop.pipelines.build.raw.iter_approvals", return_value=iter([])
        ) as mock_iter:
            list(build.iter_approvals(state=PipelineApprovalStatus.PENDING))
        mock_iter.assert_called_once_with(
            build._project.api_call,
            state=PipelineApprovalStatus.PENDING,
            pipeline_run_ids=[7],
        )

    def test_list_approvals_delegates_to_iter(self) -> None:
        """list_approvals returns results of iter_approvals as a list."""
        build = _make_build()
        with patch.object(build, "iter_approvals", return_value=iter([])):
            assert build.list_approvals() == []


class TestTimelineHelpers:
    """Verify that the conftest timeline record helpers produce valid models."""

    def test_make_all_records_returns_stage_job_task(self) -> None:
        records = _make_all_records()
        assert len(records) == 3
        types = {r.type_name.value for r in records}
        assert types == {"Stage", "Job", "Task"}
        stage = next(r for r in records if r.type_name.value == "Stage")
        assert str(stage.id) == str(STAGE_ID)
        task = next(r for r in records if r.type_name.value == "Task")
        assert str(task.id) == str(TASK_ID)

    def test_make_all_records_with_phase(self) -> None:
        records = _make_all_records(use_phase=True)
        assert len(records) == 4
        types = [r.type_name.value for r in records]
        assert "Phase" in types
        phase = next(r for r in records if r.type_name.value == "Phase")
        assert str(phase.id) == str(PHASE_ID)

    def test_task_record_without_log(self) -> None:
        record = _task_record()
        assert str(record.id) == str(TASK_INSTANCE_ID)
        assert record.log is None

    def test_task_record_with_log(self) -> None:
        record = _task_record(log_id=7)
        assert record.log is not None
        assert record.log.id == 7
