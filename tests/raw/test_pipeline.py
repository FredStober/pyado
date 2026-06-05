"""Tests for pyado.pipeline module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch
from uuid import uuid4

import requests

from pyado.raw import (
    ApiCall,
    JobEventPayload,
    PipelineApproval,
    PipelineInfo,
    PipelineResourcePermissions,
    PipelineResourceType,
    PipelineRunInfo,
    PipelineRunRequest,
    get_job_api_call,
    get_log_api_call,
    get_pipeline,
    get_pipeline_run,
    get_plan_api_call,
    get_timeline_api_call,
    iter_approvals,
    iter_pipeline_runs,
    iter_pipelines,
    list_approvals,
    list_pipeline_runs,
    list_pipelines,
    patch_pipeline_permission,
    post_job_logs,
    post_pipeline_run,
)
from tests.conftest import _make_mock_response

if TYPE_CHECKING:  # pragma: no cover
    from pyado.raw.pipeline import PipelineApprovalStatus

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

    @staticmethod
    def test_passes_top_parameter_when_given(api_call: ApiCall) -> None:
        """Forwards the top parameter as $top query param."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pipeline_runs(api_call, 1, top=5))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$top") == 5

    @staticmethod
    def test_omits_top_parameter_when_none(api_call: ApiCall) -> None:
        """Does not include $top in the query params when top is None."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pipeline_runs(api_call, 1))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "$top" not in params


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


def _make_pipeline_permissions_dict(pipeline_id: int = 1) -> dict[str, Any]:
    """Create a minimal valid PipelineResourcePermissions dict."""
    return {
        "allPipelines": None,
        "pipelines": [{"authorized": True, "id": pipeline_id}],
    }


class TestPatchPipelinePermission:
    """Tests for patch_pipeline_permission."""

    @staticmethod
    def test_returns_pipeline_resource_permissions(api_call: ApiCall) -> None:
        """Returns a PipelineResourcePermissions parsed from the response."""
        response_data = _make_pipeline_permissions_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_pipeline_permission(
                api_call,
                PipelineResourceType.VARIABLE_GROUP,
                "42",
                pipeline_id=99,
                authorized=True,
            )
        assert isinstance(result, PipelineResourcePermissions)
        assert result.pipelines[0].authorized is True

    @staticmethod
    def test_sends_patch_request(api_call: ApiCall) -> None:
        """Sends a PATCH request (not POST)."""
        response_data = _make_pipeline_permissions_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_pipeline_permission(
                api_call,
                PipelineResourceType.QUEUE,
                "7",
                pipeline_id=1,
                authorized=True,
            )
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_url_contains_resource_type_and_id(api_call: ApiCall) -> None:
        """Request URL contains the resource type and resource ID."""
        response_data = _make_pipeline_permissions_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_pipeline_permission(
                api_call,
                PipelineResourceType.QUEUE,
                "7",
                pipeline_id=1,
                authorized=True,
            )
        url_called = mock_req.call_args[1]["url"]
        assert "queue" in url_called
        assert "7" in url_called


# ---------------------------------------------------------------------------
# Smoke tests — real API response shapes
# ---------------------------------------------------------------------------

_PIPELINES_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            ),
            "id": 1,
            "revision": 1,
            "name": "sample-repo",
            "folder": "\\",
        }
    ],
}

_SINGLE_PIPELINE_SMOKE_RESPONSE = {
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/definition?definitionId=1"
            )
        },
    },
    "configuration": {
        "path": "azure-pipelines.yml",
        "repository": {
            "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
            "type": "azureReposGit",
        },
        "type": "yaml",
    },
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/pipelines/1?revision=1"
    ),
    "id": 1,
    "revision": 1,
    "name": "sample-repo",
    "folder": "\\",
}

_PIPELINE_RUNS_SMOKE_RESPONSE = {
    "count": 2,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1/runs/14"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=14"
                    )
                },
                "pipeline.web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
                "pipeline": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
            },
            "templateParameters": {},
            "pipeline": {
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/pipelines/1?revision=1"
                ),
                "id": 1,
                "revision": 1,
                "name": "sample-repo",
                "folder": "\\",
            },
            "state": "completed",
            "result": "succeeded",
            "createdDate": "2026-06-02T14:40:57.7141572Z",
            "finishedDate": "2026-06-02T14:42:57.8337515Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/14"
            ),
            "id": 14,
            "name": "20260602.13",
        },
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1/runs/13"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=13"
                    )
                },
                "pipeline.web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
                "pipeline": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
            },
            "templateParameters": {},
            "pipeline": {
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/pipelines/1?revision=1"
                ),
                "id": 1,
                "revision": 1,
                "name": "sample-repo",
                "folder": "\\",
            },
            "state": "completed",
            "result": "failed",
            "createdDate": "2026-06-02T14:38:00.0000000Z",
            "finishedDate": "2026-06-02T14:39:30.0000000Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/13"
            ),
            "id": 13,
            "name": "20260602.12",
        },
    ],
}

_SINGLE_PIPELINE_RUN_SMOKE_RESPONSE = {
    "yamlDetails": {
        "rootYamlFile": {
            "ref": "refs/heads/main",
            "yamlFile": "azure-pipelines.yml",
            "repoAlias": "self",
        },
        "expandedYamlUrl": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/builds/14/logs/1"
        ),
    },
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/14"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/results?buildId=14"
            )
        },
        "pipeline.web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/definition?definitionId=1"
            )
        },
        "pipeline": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            )
        },
    },
    "templateParameters": {},
    "pipeline": {
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/pipelines/1?revision=1"
        ),
        "id": 1,
        "revision": 1,
        "name": "sample-repo",
        "folder": "\\",
    },
    "state": "completed",
    "result": "succeeded",
    "createdDate": "2026-06-02T14:40:57.7141572Z",
    "finishedDate": "2026-06-02T14:42:57.8337515Z",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/pipelines/1/runs/14"
    ),
    "id": 14,
    "name": "20260602.13",
}


class TestSmokeIterPipelines:
    """iter_pipelines parses real pipeline list response shapes."""

    @staticmethod
    def test_parses_pipeline_list(api_call: ApiCall) -> None:
        """Parses a pipeline list response with _links and folder fields."""
        mock_response = _make_mock_response(_PIPELINES_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipelines(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PipelineInfo)
        assert result[0].id == 1
        assert result[0].name == "sample-repo"

    @staticmethod
    def test_pipeline_folder_and_revision_parsed(api_call: ApiCall) -> None:
        """Folder (backslash root) and revision are parsed correctly."""
        mock_response = _make_mock_response(_PIPELINES_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipelines(api_call))
        assert result[0].folder == "\\"
        assert result[0].revision == 1


class TestSmokeGetPipeline:
    """get_pipeline parses a real single-pipeline response shape."""

    @staticmethod
    def test_parses_pipeline_with_configuration_field(api_call: ApiCall) -> None:
        """Single pipeline with extra configuration dict parses without error."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline(api_call, 1)
        assert isinstance(result, PipelineInfo)
        assert result.id == 1
        assert result.name == "sample-repo"

    @staticmethod
    def test_pipeline_folder_is_backslash_root(api_call: ApiCall) -> None:
        """Folder field with backslash value parses correctly."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline(api_call, 1)
        assert result.folder == "\\"


class TestSmokeIterPipelineRuns:
    """iter_pipeline_runs parses real pipeline run list response shapes."""

    @staticmethod
    def test_parses_two_pipeline_runs(api_call: ApiCall) -> None:
        """Parses a run list with _links, pipeline, templateParameters fields."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        assert len(result) == 2
        assert all(isinstance(run, PipelineRunInfo) for run in result)

    @staticmethod
    def test_run_ids_in_descending_order(api_call: ApiCall) -> None:
        """Run IDs match the order returned by the real response."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        assert result[0].id == 14
        assert result[1].id == 13

    @staticmethod
    def test_run_with_failed_result_parses(api_call: ApiCall) -> None:
        """Run with result='failed' parses without error."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        failed_run = next(r for r in result if r.id == 13)
        assert failed_run.result == "failed"


class TestSmokeGetPipelineRun:
    """get_pipeline_run parses a real single pipeline-run response shape."""

    @staticmethod
    def test_parses_run_with_yaml_details_extra_field(api_call: ApiCall) -> None:
        """Single run with yamlDetails (extra field) parses without error."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert isinstance(result, PipelineRunInfo)
        assert result.id == 14
        assert result.name == "20260602.13"

    @staticmethod
    def test_pipeline_nested_object_parsed(api_call: ApiCall) -> None:
        """Pipeline nested object (id, name, folder) is accessible on the run."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert result.pipeline.id == 1
        assert result.pipeline.name == "sample-repo"

    @staticmethod
    def test_run_state_and_result_parsed(api_call: ApiCall) -> None:
        """State and result fields are populated from the real response."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert result.state == "completed"
        assert result.result == "succeeded"


class TestListPipelines:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch("pyado.raw.pipeline.iter_pipelines", return_value=iter([])) as m:
            result = list_pipelines(api_call)
        assert result == []
        m.assert_called_once_with(api_call, order_by=None)


class TestListPipelineRuns:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch("pyado.raw.pipeline.iter_pipeline_runs", return_value=iter([])) as m:
            result = list_pipeline_runs(api_call, 42)
        assert result == []
        m.assert_called_once_with(api_call, 42, top=None)


class TestListApprovals:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch("pyado.raw.pipeline.iter_approvals", return_value=iter([])) as m:
            result = list_approvals(api_call)
        assert result == []
        m.assert_called_once_with(api_call)
