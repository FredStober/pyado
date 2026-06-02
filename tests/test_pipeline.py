"""Tests for pyado.pipeline module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch
from uuid import uuid4

import requests

from pyado import (
    ApiCall,
    BuildRecordInfo,
    JobEventPayload,
    PipelineApproval,
    PipelineRunRequest,
    approve_pipeline,
    get_job_api_call,
    get_log_api_call,
    get_pipeline,
    get_pipeline_run,
    get_plan_api_call,
    get_timeline_api_call,
    iter_approvals,
    iter_pending_approvals,
    iter_pipeline_runs,
    iter_pipelines,
    post_job_logs,
    post_pipeline_run,
    send_job_event,
    send_job_feed,
    update_timeline_records,
)
from tests.conftest import _make_mock_response, make_build_record_dict

if TYPE_CHECKING:  # pragma: no cover
    from pyado.raw.pipeline import JobEventName, JobEventResult, PipelineApprovalStatus

HUB_NAME = "Build"
PLAN_ID = uuid4()
TIMELINE_ID = uuid4()
JOB_ID = uuid4()
TASK_ID = uuid4()
LOG_ID = 7


class TestGetPlanApiCall:
    """Tests for get_plan_api_call."""

    @staticmethod
    def test_url_contains_plan_segments(api_call: ApiCall) -> None:
        """Result URL contains distributedtask/hubs/<hub>/plans/<plan_id>."""
        result = get_plan_api_call(api_call, HUB_NAME, PLAN_ID)
        url_str = result.url.unicode_string()
        assert "distributedtask/hubs" in url_str
        assert HUB_NAME in url_str
        assert "plans" in url_str


class TestGetTimelineApiCall:
    """Tests for get_timeline_api_call."""

    @staticmethod
    def test_url_contains_timelines_segment(api_call: ApiCall) -> None:
        """Result URL contains timelines/<timeline_id>."""
        result = get_timeline_api_call(api_call, HUB_NAME, PLAN_ID, TIMELINE_ID)
        url_str = result.url.unicode_string()
        assert "timelines" in url_str


class TestGetJobApiCall:
    """Tests for get_job_api_call."""

    @staticmethod
    def test_url_contains_records_and_job_id(api_call: ApiCall) -> None:
        """Result URL contains records/<job_id>."""
        result = get_job_api_call(api_call, HUB_NAME, PLAN_ID, TIMELINE_ID, JOB_ID)
        url_str = result.url.unicode_string()
        assert "records" in url_str


class TestGetLogApiCall:
    """Tests for get_log_api_call."""

    @staticmethod
    def test_url_contains_logs_and_log_id(api_call: ApiCall) -> None:
        """Result URL contains logs/<log_id>."""
        result = get_log_api_call(api_call, HUB_NAME, PLAN_ID, LOG_ID)
        url_str = result.url.unicode_string()
        assert "logs" in url_str


class TestSendJobFeed:
    """Tests for send_job_feed."""

    @staticmethod
    def test_posts_messages_to_feed(api_call: ApiCall) -> None:
        """send_job_feed POSTs the messages payload to the feed endpoint."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            send_job_feed(api_call, ["line 1", "line 2"])
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "POST"
        # Verify payload was sent
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("count") == 2
        assert sent_json.get("value") == ["line 1", "line 2"]


class TestSendJobLogs:
    """Tests for post_job_logs."""

    @staticmethod
    def test_posts_log_as_bytes(api_call: ApiCall) -> None:
        """post_job_logs POSTs the message encoded as bytes."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_job_logs(api_call, "Log entry")
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_data = call.kwargs.get("data")
        assert sent_data == b"Log entry"


class TestSendJobEvent:
    """Tests for send_job_event."""

    @staticmethod
    def test_posts_job_event_payload(api_call: ApiCall) -> None:
        """send_job_event POSTs a correctly structured event payload."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            send_job_event(
                api_call,
                TASK_ID,
                JOB_ID,
                cast("JobEventName", "TaskCompleted"),
                cast("JobEventResult", "succeeded"),
            )
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("name") == "TaskCompleted"
        assert sent_json.get("result") == "succeeded"
        assert sent_json.get("taskId") == str(TASK_ID)
        assert sent_json.get("jobId") == str(JOB_ID)


class TestUpdateTimelineRecords:
    """Tests for update_timeline_records."""

    @staticmethod
    def test_patches_records_endpoint(api_call: ApiCall) -> None:
        """update_timeline_records PATCHes the records endpoint."""
        record = BuildRecordInfo.model_validate(make_build_record_dict())
        mock_response = _make_mock_response(json_data={"count": 1, "value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_timeline_records(api_call, [record])
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "PATCH"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("count") == 1


class TestJobEventPayload:
    """Tests for JobEventPayload model."""

    @staticmethod
    def test_serialises_with_aliases() -> None:
        """Model serialises field names using camelCase aliases."""
        payload = JobEventPayload(
            name="TaskCompleted",
            task_id=TASK_ID,
            job_id=JOB_ID,
            result="failed",
        )
        dumped = payload.model_dump(mode="json", by_alias=True)
        assert "taskId" in dumped
        assert "jobId" in dumped


def _make_approval_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid PipelineApproval dict.

    Returns:
        A dict with required PipelineApproval fields populated.
    """
    approval: dict[str, Any] = {
        "id": "approval-uuid-1",
        "status": "pending",
        "steps": [
            {
                "assignedApprover": {
                    "id": "approver-uuid",
                    "displayName": "Bob Approver",
                },
                "status": "pending",
            }
        ],
        "minRequiredApprovers": 1,
        "blockedApprovers": [],
    }
    approval.update(overrides)
    return approval


class TestIterApprovals:
    """Tests for iter_approvals."""

    @staticmethod
    def test_yields_approvals(api_call: ApiCall) -> None:
        """Yields PipelineApproval objects for each approval."""
        response_data = {"value": [_make_approval_dict()]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_approvals(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PipelineApproval)
        assert result[0].id == "approval-uuid-1"
        assert result[0].status == "pending"
        assert result[0].steps[0].assigned_approver.display_name == "Bob Approver"

    @staticmethod
    def test_yields_nothing_when_no_approvals(api_call: ApiCall) -> None:
        """Empty value list yields no approvals."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_approvals(api_call))
        assert result == []

    @staticmethod
    def test_passes_state_filter(api_call: ApiCall) -> None:
        """Passes state as a query parameter when provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_approvals(
                    api_call, state=cast("PipelineApprovalStatus", "approved")
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("state") == "approved"

    @staticmethod
    def test_omits_state_filter_when_none(api_call: ApiCall) -> None:
        """Omits state query parameter when state is None."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_approvals(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "state" not in params


class TestIterPendingApprovals:
    """Tests for iter_pending_approvals."""

    @staticmethod
    def test_delegates_to_iter_approvals_with_pending_state(
        api_call: ApiCall,
    ) -> None:
        """Delegates to iter_approvals with state=pending."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pending_approvals(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("state") == "pending"


class TestApprovePipeline:
    """Tests for approve_pipeline."""

    @staticmethod
    def test_patches_approval_with_approved_status(api_call: ApiCall) -> None:
        """Sends a PATCH with status=approved for the given approval ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            approve_pipeline(api_call, "approval-uuid-1")
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["approvalId"] == "approval-uuid-1"
        assert sent_json[0]["status"] == "approved"

    @staticmethod
    def test_includes_comment_in_payload(api_call: ApiCall) -> None:
        """Includes the provided comment in the approval payload."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            approve_pipeline(api_call, "approval-uuid-2", comment="LGTM")
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["comment"] == "LGTM"


def _make_pipeline_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid PipelineInfo dict.

    Returns:
        A dict with required PipelineInfo fields populated.
    """
    pipeline: dict[str, Any] = {
        "id": 1,
        "revision": 1,
        "name": "my-pipeline",
        "folder": "\\",
        "url": "https://dev.azure.com/org/project/_apis/pipelines/1",
    }
    pipeline.update(overrides)
    return pipeline


def _make_pipeline_run_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid PipelineRunInfo dict.

    Returns:
        A dict with required PipelineRunInfo fields populated.
    """
    run: dict[str, Any] = {
        "id": 100,
        "name": "20240115.1",
        "state": "completed",
        "result": "succeeded",
        "pipeline": _make_pipeline_dict(),
        "createdDate": "2024-01-15T12:00:00+00:00",
        "url": "https://dev.azure.com/org/project/_apis/pipelines/1/runs/100",
    }
    run.update(overrides)
    return run


class TestIterPipelines:
    """Tests for iter_pipelines."""

    @staticmethod
    def test_yields_pipeline_objects(api_call: ApiCall) -> None:
        """Yields PipelineInfo objects from the API response."""
        response_json = {"value": [_make_pipeline_dict()]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipelines(api_call))
        assert len(result) == 1
        assert result[0].name == "my-pipeline"

    @staticmethod
    def test_passes_order_by_parameter(api_call: ApiCall) -> None:
        """Includes orderBy in query parameters when order_by is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pipelines(api_call, order_by="name asc"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("orderBy") == "name asc"


class TestGetPipeline:
    """Tests for get_pipeline."""

    @staticmethod
    def test_returns_pipeline_info(api_call: ApiCall) -> None:
        """Returns a PipelineInfo object from the API response."""
        mock_response = _make_mock_response(_make_pipeline_dict(id=7))
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline(api_call, 7)
        assert result.id == 7

    @staticmethod
    def test_passes_pipeline_version_parameter(api_call: ApiCall) -> None:
        """Includes pipelineVersion in query parameters when provided."""
        mock_response = _make_mock_response(_make_pipeline_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_pipeline(api_call, 1, pipeline_version=3)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("pipelineVersion") == 3


class TestIterPipelineRuns:
    """Tests for iter_pipeline_runs."""

    @staticmethod
    def test_yields_run_objects(api_call: ApiCall) -> None:
        """Yields PipelineRunInfo objects from the API response."""
        response_json = {"value": [_make_pipeline_run_dict()]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        assert len(result) == 1
        assert result[0].id == 100


class TestGetPipelineRun:
    """Tests for get_pipeline_run."""

    @staticmethod
    def test_returns_run_info(api_call: ApiCall) -> None:
        """Returns a PipelineRunInfo object from the API response."""
        mock_response = _make_mock_response(_make_pipeline_run_dict(id=42))
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 42)
        assert result.id == 42


class TestPostPipelineRun:
    """Tests for post_pipeline_run."""

    @staticmethod
    def test_posts_to_runs_endpoint(api_call: ApiCall) -> None:
        """Sends a POST to the pipeline runs endpoint."""
        mock_response = _make_mock_response(_make_pipeline_run_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pipeline_run(api_call, 1)
        assert mock_req.call_args.args[0] == "POST"

    @staticmethod
    def test_serialises_request_body(api_call: ApiCall) -> None:
        """Includes request fields in the POST body when request is provided."""
        request = PipelineRunRequest(template_parameters={"env": "prod"})
        mock_response = _make_mock_response(_make_pipeline_run_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pipeline_run(api_call, 1, request=request)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("templateParameters") == {"env": "prod"}
