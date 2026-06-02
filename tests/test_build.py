"""Tests for pyado.build module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import requests

from pyado import (
    ApiCall,
    BuildDetails,
    BuildRecordInfo,
    PipelineDefinitionInfo,
    delete_build_tag,
    get_build_api_call,
    get_build_details,
    iter_build_artifacts,
    iter_build_tags,
    iter_build_work_item_ids,
    iter_builds,
    iter_pipeline_definitions,
    iter_timeline_records,
    iter_work_items_between_builds,
    post_build_tag,
    start_build,
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
        "sourceVersion": "abc123def456",
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
            list(iter_builds(api_call, definition_id=42))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("definitions") == 42

    @staticmethod
    def test_passes_status_filter(api_call: ApiCall) -> None:
        """Passes statusFilter query parameter when status_filter is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_builds(api_call, status_filter="inProgress"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("statusFilter") == "inProgress"

    @staticmethod
    def test_passes_branch_name_filter(api_call: ApiCall) -> None:
        """Passes branchName query parameter when branch_name is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_builds(api_call, branch_name="refs/heads/main"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("branchName") == "refs/heads/main"

    @staticmethod
    def test_passes_top_limit(api_call: ApiCall) -> None:
        """Passes $top query parameter when top is provided."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_builds(api_call, top=10))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$top") == 10


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
