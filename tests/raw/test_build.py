"""Tests for pyado.build module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildExpand,
    BuildLogInfo,
    BuildRecordInfo,
    BuildSearchCriteria,
    BuildStatus,
    PipelineDefinitionInfo,
    TimelineReference,
    delete_build_tag,
    get_build_api_call,
    get_build_artifact_bytes,
    get_build_details,
    get_build_log,
    iter_build_artifacts,
    iter_build_logs,
    iter_build_tags,
    iter_builds,
    iter_pipeline_definitions,
    iter_timeline_records,
    iter_work_items_between_builds,
    list_build_artifacts,
    list_build_logs,
    list_build_tags,
    list_build_work_item_ids,
    list_builds,
    list_pipeline_definitions,
    list_timeline_records,
    list_work_items_between_builds,
    post_build_tag,
)
from tests.conftest import NOW_ISO, _make_mock_response, make_build_record_dict


class TestGetBuildApiCall:
    """Tests for get_build_api_call."""

    @staticmethod
    def test_appends_build_path_and_id(api_call: ApiCall) -> None:
        """Result URL contains build path segments and build ID."""
        result = get_build_api_call(api_call, build_id=42)
        url_str = result.url.unicode_string()
        assert "build/builds/42" in url_str


class TestGetBuildLog:
    """Tests for get_build_log."""

    @staticmethod
    def test_returns_decoded_log_content(api_call: ApiCall) -> None:
        """Returns log bytes decoded as UTF-8 string."""
        build_api_call = get_build_api_call(api_call, build_id=42)
        mock_response = _make_mock_response()
        mock_response.content = b"build log line 1\nbuild log line 2\n"
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_log(build_api_call, 5)
        assert result == "build log line 1\nbuild log line 2\n"


class TestIterTimelineRecords:
    """Tests for iter_timeline_records."""

    @staticmethod
    def test_yields_parsed_build_records(api_call: ApiCall) -> None:
        """Yields BuildRecordInfo objects from parsed API response."""
        timeline_id = str(uuid4())
        record = make_build_record_dict()
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildRecordInfo)
        assert result[0].name == "Test Task"

    @staticmethod
    def test_yields_record_with_log_info(api_call: ApiCall) -> None:
        """BuildRecordInfo with a log field is parsed correctly."""
        timeline_id = str(uuid4())
        log = {
            "id": 5,
            "type": "Container",
            "url": "https://dev.azure.com/org/log/5",
        }
        record = make_build_record_dict(log=log)
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert result[0].log is not None
        assert result[0].log.id == 5

    @staticmethod
    def test_yields_record_with_task_info(api_call: ApiCall) -> None:
        """BuildRecordInfo with task details is parsed correctly."""
        timeline_id = str(uuid4())
        task = {"id": str(uuid4()), "name": "Checkout", "version": "1.0.0"}
        record = make_build_record_dict(task=task, type="Task")
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert result[0].task is not None
        assert result[0].task.name == "Checkout"

    @staticmethod
    def test_yields_record_with_issues(api_call: ApiCall) -> None:
        """BuildRecordInfo with build issues is parsed correctly."""
        timeline_id = str(uuid4())
        issues = [
            {"message": "Warning: unused var", "type": "warning"},
            {"message": "Error: build failed", "type": "error", "category": "compile"},
        ]
        record = make_build_record_dict(issues=issues)
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert result[0].issues is not None
        assert len(result[0].issues) == 2
        assert result[0].issues[0].category is None
        assert result[0].issues[1].category == "compile"

    @staticmethod
    def test_yields_record_with_previous_attempts(api_call: ApiCall) -> None:
        """BuildRecordInfo with previous attempts is parsed correctly."""
        timeline_id = str(uuid4())
        attempts = [
            {
                "attempt": 1,
                "timelineId": str(uuid4()),
                "recordId": str(uuid4()),
            }
        ]
        record = make_build_record_dict(previousAttempts=attempts)
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert len(result[0].previous_attempts) == 1

    @staticmethod
    def test_yields_record_with_timeline_reference_details(api_call: ApiCall) -> None:
        """BuildRecordInfo with a non-None details field is parsed correctly."""
        timeline_id = str(uuid4())
        details = {
            "changeId": 3,
            "id": str(uuid4()),
            "url": "https://dev.azure.com/org/proj/_apis/build/builds/1/timeline/sub",
        }
        record = make_build_record_dict(details=details)
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert isinstance(result[0].details, TimelineReference)
        assert result[0].details.change_id == 3

    @staticmethod
    def test_yields_record_ignoring_extra_ado_fields(api_call: ApiCall) -> None:
        """BuildRecordInfo silently ignores extra fields such as _links from ADO."""
        timeline_id = str(uuid4())
        record = make_build_record_dict(
            _links={"self": {"href": "https://dev.azure.com/"}}
        )
        response_json = {"id": timeline_id, "records": [record]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildRecordInfo)


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


class TestGetBuildDetails:
    """Tests for get_build_details."""

    @staticmethod
    def test_returns_build_details(api_call: ApiCall) -> None:
        """Returns a BuildDetails object from the API response."""
        response_data = make_build_details_dict()
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(api_call)
        assert isinstance(result, BuildDetails)
        assert result.id == 1001
        assert result.build_number == "20240115.1"
        assert result.status == "completed"
        assert result.result == "succeeded"
        assert result.source_branch == "refs/heads/main"
        assert result.definition.name == "my-pipeline"
        assert result.requested_by.display_name == "Alice"

    @staticmethod
    def test_returns_build_details_without_result(api_call: ApiCall) -> None:
        """Returns BuildDetails when result is None (e.g. in-progress build)."""
        response_data = make_build_details_dict(result=None, status="inProgress")
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(api_call)
        assert result.result is None
        assert result.status == "inProgress"

    @staticmethod
    def test_expand_param_forwarded_as_dollar_expand(api_call: ApiCall) -> None:
        """When expand is provided, $expand query parameter is included."""
        mock_response = _make_mock_response(make_build_details_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_build_details(api_call, expand=BuildExpand.ALL)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$expand") == BuildExpand.ALL

    @staticmethod
    def test_no_expand_param_when_expand_is_none(api_call: ApiCall) -> None:
        """When expand is None, no $expand query parameter is sent."""
        mock_response = _make_mock_response(make_build_details_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_build_details(api_call)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "$expand" not in (params or {})


class TestIterBuilds:
    """Tests for iter_builds."""

    @staticmethod
    def test_yields_build_details(api_call: ApiCall) -> None:
        """Yields BuildDetails objects from the API response."""
        response_data = {"value": [make_build_details_dict()]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildDetails)

    @staticmethod
    def test_passes_definition_id_filter(api_call: ApiCall) -> None:
        """Passes definitions query parameter when definition_id is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_builds(
                    api_call, search_criteria=BuildSearchCriteria(definition_id=42)
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("definitions") == 42

    @staticmethod
    def test_passes_status_filter(api_call: ApiCall) -> None:
        """Passes statusFilter query parameter when status_filter is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_builds(
                    api_call,
                    search_criteria=BuildSearchCriteria(
                        status_filter=BuildStatus.IN_PROGRESS
                    ),
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("statusFilter") == "inProgress"

    @staticmethod
    def test_passes_branch_name_filter(api_call: ApiCall) -> None:
        """Passes branchName query parameter when branch_name is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_builds(
                    api_call,
                    search_criteria=BuildSearchCriteria(branch_name="refs/heads/main"),
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("branchName") == "refs/heads/main"

    @staticmethod
    def test_passes_top_limit(api_call: ApiCall) -> None:
        """Passes $top query parameter when top is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_builds(api_call, search_criteria=BuildSearchCriteria(top=10)))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$top") == 10


class TestIterPipelineDefinitions:
    """Tests for iter_pipeline_definitions."""

    @staticmethod
    def test_yields_definition_objects(api_call: ApiCall) -> None:
        """Yields PipelineDefinitionInfo objects from the API response."""
        response_data = {
            "value": [
                {
                    "id": 3,
                    "name": "deploy-pipeline",
                    "path": "\\",
                    "queueStatus": "enabled",
                    "revision": 1,
                }
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_definitions(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PipelineDefinitionInfo)
        assert result[0].name == "deploy-pipeline"
        assert result[0].id == 3

    @staticmethod
    def test_passes_name_filter(api_call: ApiCall) -> None:
        """Passes the name query parameter when name_filter is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pipeline_definitions(api_call, name_filter="deploy*"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("name") == "deploy*"


class TestIterWorkItemsBetweenBuilds:
    """Tests for iter_work_items_between_builds."""

    @staticmethod
    def test_yields_work_item_refs(api_call: ApiCall) -> None:
        """Yields WorkItemRef objects from the API response."""
        response_json = {"value": [{"id": 5}, {"id": 6}]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_items_between_builds(api_call, 10, 20))
        assert [ref.id for ref in result] == [5, 6]

    @staticmethod
    def test_passes_top_parameter(api_call: ApiCall) -> None:
        """Includes $top in query parameters when top is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_work_items_between_builds(api_call, 1, 2, top=5))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$top") == 5


class TestIterBuildArtifacts:
    """Tests for iter_build_artifacts."""

    @staticmethod
    def test_yields_artifact_objects(api_call: ApiCall) -> None:
        """Yields BuildArtifact objects from the API response."""
        response_json = {
            "value": [
                {
                    "id": 1,
                    "name": "drop",
                    "resource": {
                        "type": "Container",
                        "url": "https://example.com/drop",
                    },
                }
            ]
        }
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_artifacts(api_call))
        assert len(result) == 1
        assert result[0].name == "drop"


class TestIterBuildTags:
    """Tests for iter_build_tags."""

    @staticmethod
    def test_yields_tag_strings(api_call: ApiCall) -> None:
        """Yields tag strings from the API response."""
        mock_response = _make_mock_response({"value": ["tag-a", "tag-b"]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_tags(api_call))
        assert result == ["tag-a", "tag-b"]


class TestPostBuildTag:
    """Tests for post_build_tag."""

    @staticmethod
    def test_returns_updated_tag_list(api_call: ApiCall) -> None:
        """Returns the updated tag list returned by the API."""
        mock_response = _make_mock_response({"value": ["tag-a", "new-tag"]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_build_tag(api_call, "new-tag")
        assert "new-tag" in result


class TestDeleteBuildTag:
    """Tests for delete_build_tag."""

    @staticmethod
    def test_returns_remaining_tag_list(api_call: ApiCall) -> None:
        """Returns the remaining tag list after deletion."""
        mock_response = _make_mock_response({"value": ["tag-a"]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = delete_build_tag(api_call, "tag-b")
        assert result == ["tag-a"]


class TestIterBuildLogs:
    """Tests for iter_build_logs."""

    @staticmethod
    def test_yields_build_log_info_objects(api_call: ApiCall) -> None:
        """Yields BuildLogInfo objects from the parsed API response."""
        build_api_call = get_build_api_call(api_call, build_id=42)
        log_entry = {
            "id": 7,
            "type": "Container",
            "url": "https://dev.azure.com/org/_apis/build/builds/42/logs/7",
        }
        mock_response = _make_mock_response({"value": [log_entry]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_logs(build_api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildLogInfo)
        assert result[0].id == 7

    @staticmethod
    def test_yields_empty_when_no_logs(api_call: ApiCall) -> None:
        """Yields nothing when value list is empty."""
        build_api_call = get_build_api_call(api_call, build_id=42)
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_build_logs(build_api_call))
        assert result == []


# ---------------------------------------------------------------------------
# Smoke tests — real API response shapes
# ---------------------------------------------------------------------------

_SMOKE_AUTHOR = {
    "displayName": "Test User",
    "url": (
        "https://spsprod00000.vssps.visualstudio.com/A95c5fb98-6980-481f-bc42-8d42fa882692"
        "/_apis/Identities/94820a06-c555-463f-a9ef-41d0deea959e"
    ),
    "_links": {
        "avatar": {
            "href": (
                "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
                "/aad.OTQ4MjBhMDYtYzU1NS00NjNmLWE5ZWYtNDFkMGRlZWE5NTll"
            )
        }
    },
    "id": "94820a06-c555-463f-a9ef-41d0deea959e",
    "uniqueName": "testuser@example.com",
    "imageUrl": (
        "https://dev.azure.com/example-org/_api/_common/identityImage"
        "?id=94820a06-c555-463f-a9ef-41d0deea959e"
    ),
    "descriptor": "aad.OTQ4MjBhMDYtYzU1NS00NjNmLWE5ZWYtNDFkMGRlZWE5NTll",
}

_SMOKE_PROJECT = {
    "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
    "name": "main",
    "url": "https://dev.azure.com/example-org/_apis/projects/daea58ba-4c73-4942-8d87-78e7d340bbcd",
    "state": "wellFormed",
    "revision": 20,
    "visibility": "private",
    "lastUpdateTime": "2023-01-18T16:17:39.97Z",
}

_BUILD_DEFINITIONS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/build/Definitions/1?revision=1"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
            },
            "quality": "definition",
            "authoredBy": _SMOKE_AUTHOR,
            "drafts": [],
            "queue": {
                "_links": {
                    "self": {
                        "href": "https://dev.azure.com/example-org/_apis/build/Queues/18"
                    }
                },
                "id": 18,
                "name": "Azure Pipelines",
                "url": "https://dev.azure.com/example-org/_apis/build/Queues/18",
                "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
            },
            "id": 1,
            "name": "sample-repo",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Definitions/1?revision=1"
            ),
            "uri": "vstfs:///Build/Definition/1",
            "path": "\\",
            "type": "build",
            "queueStatus": "enabled",
            "revision": 1,
            "createdDate": "2022-07-21T14:32:00.057Z",
            "project": _SMOKE_PROJECT,
        }
    ],
}

_SMOKE_COMMIT = "793c58c9db362a9af594627883270b76c27526ad"  # pragma: allowlist secret

_BUILDS_SMOKE_RESPONSE = {
    "count": 3,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/build/Builds/4"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=4"
                    )
                },
            },
            "properties": {},
            "tags": [],
            "validationResults": [],
            "plans": [{"planId": "ae711399-e2b2-448b-9b1b-cf726a1eccda"}],
            "triggerInfo": {},
            "id": 4,
            "buildNumber": "20260602.3",
            "status": "completed",
            "result": "succeeded",
            "queueTime": "2026-06-02T12:36:49.6551905Z",
            "startTime": "2026-06-02T12:36:58.4032304Z",
            "finishTime": "2026-06-02T12:37:41.9070572Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Builds/4"
            ),
            "definition": {
                "drafts": [],
                "id": 1,
                "name": "sample-repo",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/Definitions/1?revision=1"
                ),
                "uri": "vstfs:///Build/Definition/1",
                "path": "\\",
                "type": "build",
                "queueStatus": "enabled",
                "revision": 1,
                "project": _SMOKE_PROJECT,
            },
            "buildNumberRevision": 3,
            "project": _SMOKE_PROJECT,
            "uri": "vstfs:///Build/Build/4",
            "sourceBranch": "refs/heads/main",
            "sourceVersion": _SMOKE_COMMIT,
            "queue": {
                "id": 18,
                "name": "Azure Pipelines",
                "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
            },
            "priority": "normal",
            "reason": "manual",
            "requestedFor": _SMOKE_AUTHOR,
            "requestedBy": _SMOKE_AUTHOR,
            "lastChangedDate": "2026-06-02T12:37:42.37Z",
            "lastChangedBy": _SMOKE_AUTHOR,
            "orchestrationPlan": {"planId": "ae711399-e2b2-448b-9b1b-cf726a1eccda"},
            "logs": {
                "id": 0,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs"
                ),
            },
            "repository": {
                "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
                "type": "TfsGit",
                "name": "sample-repo",
                "url": "https://dev.azure.com/example-org/main/_git/sample-repo",
                "clean": None,
                "checkoutSubmodules": False,
            },
            "retainedByRelease": False,
            "triggeredByBuild": None,
            "appendCommitMessageToRunName": True,
        }
    ],
}

_TIMELINE_SMOKE_RESPONSE = {
    "records": [
        {
            "previousAttempts": [],
            "id": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "parentId": "34a9af41-25ec-4845-aaa4-857e8101e89a",
            "type": "Job",
            "name": "Job",
            "refName": "__default",
            "startTime": "2026-06-02T12:37:12.2966667Z",
            "finishTime": "2026-06-02T12:37:34.6133333Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 17,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "queueId": 18,
            "order": 1,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 10,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/10"
                ),
            },
            "task": None,
            "attempt": 1,
            "identifier": "Job.__default",
        },
        {
            "previousAttempts": [],
            "id": "a70ce1b5-1978-4ec0-895c-fa4f2dcaabd5",
            "parentId": None,
            "type": "Stage",
            "name": "__default",
            "refName": "__default",
            "startTime": "2026-06-02T12:37:12.2966667Z",
            "finishTime": "2026-06-02T12:37:41.95Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 6,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": None,
            "order": 1,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": None,
            "task": None,
            "attempt": 1,
            "identifier": "__default",
        },
        {
            "previousAttempts": [],
            "id": "82bde024-f7ac-4e22-86e0-f45856eaa301",
            "parentId": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "type": "Task",
            "name": "Checkout sample-repo@main to s",
            "refName": "__system_1",
            "startTime": "2026-06-02T12:37:12.98Z",
            "finishTime": "2026-06-02T12:37:14.01Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 11,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "order": 2,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 5,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/5"
                ),
            },
            "task": {
                "id": "a9f559fc-f0b3-4868-81b5-577d00e266d0",
                "name": "Checkout",
                "version": "1.0.0",
            },
            "attempt": 1,
            "identifier": None,
        },
        {
            "previousAttempts": [],
            "id": "7576714a-0605-4c82-9271-22dc57708107",
            "parentId": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "type": "Task",
            "name": "Finalize Job",
            "refName": "JobExtension_Final",
            "startTime": "2026-06-02T12:37:34.5833333Z",
            "finishTime": "2026-06-02T12:37:34.61Z",
            "currentOperation": None,
            "percentComplete": 100,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 13,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "order": 6,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 9,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/9"
                ),
            },
            "task": None,
            "attempt": 1,
            "identifier": None,
        },
    ],
    "lastChangedBy": "d1f6f86c-029a-4245-bb91-433a6aa79987",
    "lastChangedOn": "2026-06-02T12:37:42.35Z",
    "id": "ae711399-e2b2-448b-9b1b-cf726a1eccda",
    "changeId": 17,
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/build/builds/4/Timeline/ae711399-e2b2-448b-9b1b-cf726a1eccda"
    ),
}

_SINGLE_BUILD_SMOKE_RESPONSE = {
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Builds/14"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/results?buildId=14"
            )
        },
        "sourceVersionDisplayUri": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/builds/14/sources"
            )
        },
        "timeline": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/builds/14/Timeline"
            )
        },
        "badge": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/status/1"
            )
        },
    },
    "properties": {},
    "tags": [],
    "validationResults": [],
    "plans": [{"planId": "9893588c-860a-4da1-b5cd-b9413b8d0e76"}],
    "triggerInfo": {},
    "id": 14,
    "buildNumber": "20260602.13",
    "status": "completed",
    "result": "succeeded",
    "queueTime": "2026-06-02T14:40:57.7141572Z",
    "startTime": "2026-06-02T14:42:26.7479554Z",
    "finishTime": "2026-06-02T14:42:57.8337515Z",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/build/Builds/14"
    ),
    "definition": {
        "drafts": [],
        "id": 1,
        "name": "sample-repo",
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/Definitions/1?revision=1"
        ),
        "uri": "vstfs:///Build/Definition/1",
        "path": "\\",
        "type": "build",
        "queueStatus": "enabled",
        "revision": 1,
        "project": _SMOKE_PROJECT,
    },
    "buildNumberRevision": 13,
    "project": _SMOKE_PROJECT,
    "uri": "vstfs:///Build/Build/14",
    "sourceBranch": "refs/heads/main",
    "sourceVersion": _SMOKE_COMMIT,
    "queue": {
        "id": 18,
        "name": "Azure Pipelines",
        "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
    },
    "priority": "normal",
    "reason": "manual",
    "requestedFor": _SMOKE_AUTHOR,
    "requestedBy": _SMOKE_AUTHOR,
    "lastChangedDate": "2026-06-02T14:42:58.12Z",
    "lastChangedBy": {
        "displayName": "Microsoft.VisualStudio.Services.TFS",
        "url": (
            "https://spsprod00000.vssps.visualstudio.com"
            "/A95c5fb98-6980-481f-bc42-8d42fa882692"
            "/_apis/Identities/d1f6f86c-029a-4245-bb91-433a6aa79987"
        ),
        "_links": {
            "avatar": {
                "href": (
                    "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
                    "/s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3"
                )
            }
        },
        "id": "d1f6f86c-029a-4245-bb91-433a6aa79987",
        "uniqueName": (
            "d1f6f86c-029a-4245-bb91-433a6aa79987@87f26aee-175f-4cd2-bb9d-58e4f543bbcf"
        ),
        "imageUrl": (
            "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
            "/s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3"
        ),
        "descriptor": "s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3",
    },
    "orchestrationPlan": {"planId": "9893588c-860a-4da1-b5cd-b9413b8d0e76"},
    "logs": {
        "id": 0,
        "type": "Container",
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/builds/14/logs"
        ),
    },
    "repository": {
        "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
        "type": "TfsGit",
        "name": "sample-repo",
        "url": "https://dev.azure.com/example-org/main/_git/sample-repo",
        "clean": None,
        "checkoutSubmodules": False,
    },
    "retainedByRelease": False,
    "triggeredByBuild": None,
    "appendCommitMessageToRunName": True,
}


class TestSmokeIterPipelineDefinitions:
    """iter_pipeline_definitions parses real build definition response shapes."""

    @staticmethod
    def test_parses_definition_with_extra_fields(api_call: ApiCall) -> None:
        """Parses definition with authoredBy, queue, _links and uri extra fields."""
        mock_response = _make_mock_response(_BUILD_DEFINITIONS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_definitions(api_call))
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "sample-repo"
        assert result[0].queue_status == "enabled"
        assert result[0].path == "\\"


class TestSmokeIterBuilds:
    """iter_builds parses real build response shapes."""

    @staticmethod
    def test_parses_full_build_response(api_call: ApiCall) -> None:
        """Parses build with plans, tags, validationResults and triggerInfo fields."""
        mock_response = _make_mock_response(_BUILDS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildDetails)
        assert result[0].id == 4
        assert result[0].build_number == "20260602.3"
        assert result[0].status == "completed"
        assert result[0].result == "succeeded"

    @staticmethod
    def test_requested_by_parsed(api_call: ApiCall) -> None:
        """RequestedBy nested object is accessible on the build."""
        mock_response = _make_mock_response(_BUILDS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert result[0].requested_by.display_name == "Test User"

    @staticmethod
    def test_definition_nested_object_parsed(api_call: ApiCall) -> None:
        """Definition nested object is accessible on the build."""
        mock_response = _make_mock_response(_BUILDS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert result[0].definition.id == 1
        assert result[0].definition.name == "sample-repo"


class TestSmokeIterTimelineRecords:
    """iter_timeline_records parses real timeline containing mixed record types."""

    @staticmethod
    def test_parses_mixed_record_types(api_call: ApiCall) -> None:
        """Parses a timeline with Stage, Job, and Task record types."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        types = {record.type_name for record in result}
        assert "Stage" in types
        assert "Job" in types
        assert "Task" in types

    @staticmethod
    def test_task_record_with_task_field_parsed(api_call: ApiCall) -> None:
        """Task record with a populated task field (name, id, version) parses ok."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        task_records = [r for r in result if r.task is not None]
        assert len(task_records) == 1
        task = task_records[0].task
        assert task is not None
        assert task.name == "Checkout"

    @staticmethod
    def test_record_with_null_task_field_parses(api_call: ApiCall) -> None:
        """Records where task is null are parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        null_task_records = [r for r in result if r.task is None]
        assert len(null_task_records) == 3  # Job, Stage, and Finalize Job

    @staticmethod
    def test_percent_complete_int_parses(api_call: ApiCall) -> None:
        """A record with percentComplete=100 (integer) is parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        finalize = next(r for r in result if r.name == "Finalize Job")
        assert finalize.percent_complete == 100

    @staticmethod
    def test_record_count(api_call: ApiCall) -> None:
        """All four timeline records from the fixture are yielded."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert len(result) == 4

    @staticmethod
    def test_stage_record_has_null_parent(api_call: ApiCall) -> None:
        """Stage record has null parentId and is parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        stage = next(r for r in result if r.type_name == "Stage")
        assert isinstance(stage, BuildRecordInfo)


class TestSmokeGetBuildDetails:
    """get_build_details parses a real single-build response shape."""

    @staticmethod
    def test_parses_single_build_with_extra_links(api_call: ApiCall) -> None:
        """Single build with sourceVersionDisplayUri, timeline, badge _links parses."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert isinstance(result, BuildDetails)
        assert result.id == 14
        assert result.build_number == "20260602.13"

    @staticmethod
    def test_requested_by_and_source_branch_parsed(api_call: ApiCall) -> None:
        """RequestedBy identity and sourceBranch are accessible on the build."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert result.requested_by.display_name == "Test User"
        assert result.source_branch == "refs/heads/main"

    @staticmethod
    def test_logs_field_parsed(api_call: ApiCall) -> None:
        """Logs field (BuildLogInfo) is accessible on the result."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert result.logs is not None
        assert result.logs.id == 0


class TestListBuildArtifacts:
    """Tests for list_build_artifacts."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_build_artifacts results."""
        with patch(
            "pyado.raw.pipelines.build.iter_build_artifacts", return_value=iter([])
        ) as m:
            result = list_build_artifacts(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListBuildLogs:
    """Tests for list_build_logs."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_build_logs results."""
        with patch(
            "pyado.raw.pipelines.build.iter_build_logs", return_value=iter([])
        ) as m:
            result = list_build_logs(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListBuildTags:
    """Tests for list_build_tags."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_build_tags results."""
        with patch(
            "pyado.raw.pipelines.build.iter_build_tags", return_value=iter([])
        ) as m:
            result = list_build_tags(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListBuildWorkItemIds:
    """Tests for list_build_work_item_ids."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_build_work_item_ids results."""
        with patch(
            "pyado.raw.pipelines.build.iter_build_work_item_ids", return_value=iter([])
        ) as m:
            result = list_build_work_item_ids(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListBuilds:
    """Tests for list_builds."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_builds results."""
        with patch("pyado.raw.pipelines.build.iter_builds", return_value=iter([])) as m:
            result = list_builds(api_call)
        assert result == []
        m.assert_called_once_with(api_call, search_criteria=None)


class TestListPipelineDefinitions:
    """Tests for list_pipeline_definitions."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_pipeline_definitions results."""
        with patch(
            "pyado.raw.pipelines.build.iter_pipeline_definitions", return_value=iter([])
        ) as m:
            result = list_pipeline_definitions(api_call)
        assert result == []
        m.assert_called_once_with(api_call, name_filter=None)


class TestListTimelineRecords:
    """Tests for list_timeline_records."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_timeline_records results."""
        with patch(
            "pyado.raw.pipelines.build.iter_timeline_records", return_value=iter([])
        ) as m:
            result = list_timeline_records(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListWorkItemsBetweenBuilds:
    """Tests for list_work_items_between_builds."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_work_items_between_builds results."""
        with patch(
            "pyado.raw.pipelines.build.iter_work_items_between_builds",
            return_value=iter([]),
        ) as m:
            result = list_work_items_between_builds(api_call, 1, 2)
        assert result == []
        m.assert_called_once_with(api_call, 1, 2, top=None)


def make_build_artifact(
    download_url: str | None = "https://example.com/artifact.zip",
) -> BuildArtifact:
    """Create a minimal BuildArtifact for testing."""
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


class TestGetBuildArtifactBytes:
    """Tests for get_build_artifact_bytes."""

    @staticmethod
    def test_returns_bytes_from_download_url(api_call: ApiCall) -> None:
        """Downloads bytes from the artifact download URL."""
        artifact = make_build_artifact("https://example.com/artifact.zip")
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"artifact content"
        with patch.object(requests.Session, "get", return_value=mock_response):
            result = get_build_artifact_bytes(api_call, artifact)
        assert result == b"artifact content"

    @staticmethod
    def test_returns_none_when_no_download_url(api_call: ApiCall) -> None:
        """Returns None when the artifact has no download URL."""
        artifact = make_build_artifact(download_url=None)
        result = get_build_artifact_bytes(api_call, artifact)
        assert result is None

    @staticmethod
    def test_get_uses_download_url(api_call: ApiCall) -> None:
        """The GET request targets the artifact download URL."""
        artifact = make_build_artifact("https://example.com/artifact.zip")
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b"data"
        with patch.object(
            requests.Session, "get", return_value=mock_response
        ) as mock_get:
            get_build_artifact_bytes(api_call, artifact)
        mock_get.assert_called_once()
        assert mock_get.call_args.args[0] == "https://example.com/artifact.zip"

    @staticmethod
    def test_raises_runtime_error_on_http_error(api_call: ApiCall) -> None:
        """RuntimeError is raised when the download response has an error status."""
        artifact = make_build_artifact("https://example.com/artifact.zip")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404")
        mock_response.content = json.dumps({"message": "Not found"}).encode()
        mock_response.json.return_value = {"message": "Not found"}
        with (
            patch.object(requests.Session, "get", return_value=mock_response),
            pytest.raises(RuntimeError),
        ):
            get_build_artifact_bytes(api_call, artifact)
