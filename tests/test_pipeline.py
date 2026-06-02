"""Tests for pyado.pipeline module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.api_call import ApiCall
from pyado.build import BuildRecordInfo
from pyado.pipeline import (
    PipelineApproval,
    _JobEventPayload,
    approve_pipeline,
    get_job_api_call,
    get_log_api_call,
    get_plan_api_call,
    get_timeline_api_call,
    iter_pending_approvals,
    send_job_event,
    send_job_feed,
    send_job_logs,
    update_timeline_records,
)

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_token"
NOW_ISO = "2024-01-15T12:00:00+00:00"

HUB_NAME = "Build"
PLAN_ID = uuid4()
TIMELINE_ID = uuid4()
JOB_ID = uuid4()
TASK_ID = uuid4()
LOG_ID = 7


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance.

    Returns:
        A minimal ApiCall instance for testing.
    """
    return ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)


def _make_mock_response(json_data: Any = None) -> MagicMock:
    """Create a minimal mock HTTP response.

    Returns:
        A MagicMock configured to behave as a requests.Response.
    """
    mock = MagicMock(spec=requests.Response)
    mock.raise_for_status.return_value = None
    if json_data is not None:
        mock.json.return_value = json_data
        mock.content = jsonlib.dumps(json_data).encode()
    else:
        mock.content = b""
        mock.json.side_effect = ValueError("empty")
    return mock


def make_build_record_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid BuildRecordInfo dict.

    Returns:
        A dict with all required BuildRecordInfo fields populated.
    """
    record: dict[str, Any] = {
        "attempt": 1,
        "changeId": None,
        "currentOperation": None,
        "details": None,
        "finishTime": NOW_ISO,
        "id": str(uuid4()),
        "identifier": None,
        "lastModified": NOW_ISO,
        "log": None,
        "name": "Test Task",
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
    record.update(overrides)
    return record


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
    """Tests for send_job_logs."""

    @staticmethod
    def test_posts_log_as_bytes(api_call: ApiCall) -> None:
        """send_job_logs POSTs the message encoded as bytes."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            send_job_logs(api_call, "Log entry")
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
            send_job_event(api_call, TASK_ID, JOB_ID, "TaskCompleted", "succeeded")
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
    """Tests for _JobEventPayload model."""

    @staticmethod
    def test_serialises_with_aliases() -> None:
        """Model serialises field names using camelCase aliases."""
        payload = _JobEventPayload(
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


class TestIterPendingApprovals:
    """Tests for iter_pending_approvals."""

    @staticmethod
    def test_yields_pending_approvals(api_call: ApiCall) -> None:
        """Yields PipelineApproval objects for each pending approval."""
        response_data = {"value": [_make_approval_dict()]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pending_approvals(api_call))
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
            result = list(iter_pending_approvals(api_call))
        assert result == []

    @staticmethod
    def test_passes_pending_state_filter(api_call: ApiCall) -> None:
        """Passes state=pending as a query parameter."""
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
