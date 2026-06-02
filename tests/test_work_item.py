"""Tests for pyado.work_item module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests
from pydantic.networks import AnyUrl

from pyado import (
    ApiCall,
    SprintIterationInfo,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemInfo,
    WorkItemRef,
    WorkItemRelation,
    add_artifact_link,
    add_work_item_attachment,
    add_work_item_tag,
    create_work_item,
    get_work_item,
    get_work_item_api_call,
    get_work_item_tags,
    iter_sprint_iterations,
    iter_work_item_comments,
    iter_work_item_details,
    post_wiql,
    post_work_item_comment,
    remove_work_item_tag,
    update_work_item,
)
from tests.conftest import NOW_ISO, _make_mock_response

WORK_ITEM_ID = 42


@pytest.fixture
def work_item_api_call(api_call: ApiCall) -> ApiCall:
    """Return a work-item-level ApiCall.

    Returns:
        A work-item-level ApiCall for testing.
    """
    return get_work_item_api_call(api_call, WORK_ITEM_ID)


def make_work_item_dict(work_item_id: int = 1, **fields: Any) -> dict[str, Any]:
    """Create a minimal valid WorkItemInfo dict.

    Returns:
        A dict with the required WorkItemInfo fields populated.
    """
    return {
        "id": work_item_id,
        "fields": fields or {"System.Title": "Test item"},
    }


def make_sprint_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid SprintIterationInfo dict.

    Returns:
        A dict with all required SprintIterationInfo fields populated.
    """
    sprint: dict[str, Any] = {
        "id": str(uuid4()),
        "name": "Sprint 1",
        "path": "MyProject\\Sprint 1",
        "attributes": {
            "startDate": "2024-01-01T00:00:00+00:00",
            "finishDate": "2024-01-14T00:00:00+00:00",
            "timeFrame": "current",
        },
    }
    sprint.update(overrides)
    return sprint


class TestIterWorkItemDetails:
    """Tests for iter_work_item_details."""

    @staticmethod
    def test_yields_work_item_info_objects(api_call: ApiCall) -> None:
        """Yields WorkItemInfo objects from the API response."""
        work_item = make_work_item_dict(work_item_id=42)
        mock_response = _make_mock_response({"value": [work_item]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_details(api_call, [42]))
        assert len(result) == 1
        assert isinstance(result[0], WorkItemInfo)
        assert result[0].id == 42

    @staticmethod
    def test_with_field_list_uses_fields_key(api_call: ApiCall) -> None:
        """When field list is given, payload uses 'fields' key."""
        work_item = make_work_item_dict(work_item_id=1)
        mock_response = _make_mock_response({"value": [work_item]})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_work_item_details(api_call, [1], ["System.Title"]))
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "fields" in sent_json
        assert "$expand" not in sent_json

    @staticmethod
    def test_without_field_list_uses_expand(api_call: ApiCall) -> None:
        """When no field list is given, payload uses '$expand' key."""
        work_item = make_work_item_dict()
        mock_response = _make_mock_response({"value": [work_item]})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_work_item_details(api_call, [1]))
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "$expand" in sent_json
        assert "fields" not in sent_json


class TestCreateWorkItem:
    """Tests for create_work_item."""

    @staticmethod
    def test_creates_work_item_successfully(api_call: ApiCall) -> None:
        """Returns a WorkItemInfo when creation succeeds."""
        response_data = {
            "id": 99,
            "fields": {"System.Title": "New item"},
        }
        mock_response = _make_mock_response(response_data)
        fields = {
            "System.WorkItemType": "Task",
            "System.Title": "New item",
        }
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = create_work_item(api_call, fields)
        assert isinstance(result, WorkItemInfo)
        assert result.id == 99

    @staticmethod
    def test_raises_if_work_item_type_missing(api_call: ApiCall) -> None:
        """RuntimeError is raised when System.WorkItemType is not provided."""
        with pytest.raises(RuntimeError, match="Work item type must be specified"):
            create_work_item(api_call, {"System.Title": "No type"})

    @staticmethod
    def test_creates_work_item_with_relations(api_call: ApiCall) -> None:
        """Relations are included in the JSON patch payload."""
        response_data = {"id": 100, "fields": {}}
        mock_response = _make_mock_response(response_data)
        fields = {
            "System.WorkItemType": "Task",
            "System.Title": "Child",
        }
        parent_url = AnyUrl("https://dev.azure.com/org/proj/_apis/wit/workItems/1")
        relation = WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url=parent_url,
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_work_item(api_call, fields, relations=[relation])
        sent_json = mock_req.call_args.kwargs.get("json") or []
        relation_patches = [p for p in sent_json if p.get("path") == "/relations/-"]
        assert len(relation_patches) == 1

    @staticmethod
    def test_creates_work_item_with_empty_relations(api_call: ApiCall) -> None:
        """Empty relations list results in no relation patches."""
        response_data = {"id": 101, "fields": {}}
        mock_response = _make_mock_response(response_data)
        fields = {
            "System.WorkItemType": "Task",
            "System.Title": "Solo",
        }
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_work_item(api_call, fields, relations=[])
        sent_json = mock_req.call_args.kwargs.get("json") or []
        relation_patches = [p for p in sent_json if p.get("path") == "/relations/-"]
        assert len(relation_patches) == 0


class TestIterSprintIterations:
    """Tests for iter_sprint_iterations."""

    @staticmethod
    def test_yields_sprint_iteration_objects(api_call: ApiCall) -> None:
        """Yields SprintIterationInfo objects from the API response."""
        sprint = make_sprint_dict()
        mock_response = _make_mock_response({"count": 1, "value": [sprint]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], SprintIterationInfo)
        assert result[0].name == "Sprint 1"

    @staticmethod
    def test_with_timeframe_filter_adds_parameter(api_call: ApiCall) -> None:
        """Timeframe filter is included as a query parameter."""
        sprint = make_sprint_dict()
        mock_response = _make_mock_response({"count": 1, "value": [sprint]})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_sprint_iterations(api_call, timeframe_filter="current"))
        call = mock_req.call_args
        params = call.kwargs.get("params") or {}
        assert "$timeframe" in params
        assert params["$timeframe"] == "current"

    @staticmethod
    def test_without_timeframe_filter_no_timeframe_param(api_call: ApiCall) -> None:
        """Without a filter, no $timeframe parameter is sent."""
        mock_response = _make_mock_response({"count": 0, "value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_sprint_iterations(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "$timeframe" not in params

    @staticmethod
    def test_yields_empty_for_no_sprints(api_call: ApiCall) -> None:
        """Empty value list yields no sprint iterations."""
        mock_response = _make_mock_response({"count": 0, "value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        assert result == []


class TestWorkItemRelation:
    """Tests for WorkItemRelation model."""

    @staticmethod
    def test_optional_attributes_defaults_to_none() -> None:
        """Attributes field defaults to None."""
        relation = WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url=AnyUrl("https://dev.azure.com/org/proj/_apis/wit/workItems/1"),
        )
        assert relation.attributes is None

    @staticmethod
    def test_with_attributes() -> None:
        """Attributes field can hold arbitrary data."""
        relation = WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url=AnyUrl("https://dev.azure.com/org/proj/_apis/wit/workItems/1"),
            attributes={"name": "Parent"},
        )
        assert relation.attributes == {"name": "Parent"}


def make_comment_dict(comment_id: int = 1, text: str = "Hello") -> dict[str, Any]:
    """Create a minimal valid WorkItemComment dict.

    Returns:
        A dict with all required WorkItemComment fields populated.
    """
    return {
        "id": comment_id,
        "text": text,
        "createdDate": NOW_ISO,
        "modifiedDate": NOW_ISO,
    }


class TestRunWiql:
    """Tests for post_wiql."""

    @staticmethod
    def test_returns_work_item_refs(api_call: ApiCall) -> None:
        """Returns a list of WiqlWorkItemRef objects from the query result."""
        response_data = {
            "workItems": [
                {
                    "id": 1,
                    "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/1",
                },
                {
                    "id": 2,
                    "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/2",
                },
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems")
        assert len(result) == 2
        assert all(isinstance(item, WorkItemRef) for item in result)
        assert result[0].id == 1

    @staticmethod
    def test_returns_empty_list_when_no_results(api_call: ApiCall) -> None:
        """Returns an empty list when the query matches nothing."""
        response_data: dict[str, Any] = {"workItems": []}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems WHERE 1=0")
        assert result == []


class TestUpdateWorkItem:
    """Tests for update_work_item."""

    @staticmethod
    def test_patches_work_item_fields(work_item_api_call: ApiCall) -> None:
        """Returns updated WorkItemInfo with the patched fields."""
        response_data = {"id": WORK_ITEM_ID, "fields": {"System.Title": "Updated"}}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = update_work_item(work_item_api_call, {"System.Title": "Updated"})
        assert isinstance(result, WorkItemInfo)
        assert result.id == WORK_ITEM_ID
        sent_json = mock_req.call_args.kwargs.get("json") or []
        field_paths = [patch["path"] for patch in sent_json]
        assert "/fields/System.Title" in field_paths

    @staticmethod
    def test_includes_multiline_format_patches(work_item_api_call: ApiCall) -> None:
        """Multiline field formats are appended as extra patch operations."""
        response_data = {"id": WORK_ITEM_ID, "fields": {}}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_work_item(
                work_item_api_call,
                {"System.Description": "<p>text</p>"},
                multiline_fields_format={"System.Description": "html"},
            )
        sent_json = mock_req.call_args.kwargs.get("json") or []
        format_patches = [
            patch
            for patch in sent_json
            if "multilineFieldsFormat" in patch.get("path", "")
        ]
        assert len(format_patches) == 1
        assert format_patches[0]["value"] == "html"


class TestIterWorkItemComments:
    """Tests for iter_work_item_comments."""

    @staticmethod
    def test_yields_comment_objects(work_item_api_call: ApiCall) -> None:
        """Yields WorkItemComment objects from the API response."""
        response_data = {
            "comments": [make_comment_dict(1, "First comment")],
            "continuationToken": None,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_comments(work_item_api_call))
        assert len(result) == 1
        assert isinstance(result[0], WorkItemComment)
        assert result[0].text == "First comment"

    @staticmethod
    def test_paginates_using_continuation_token(work_item_api_call: ApiCall) -> None:
        """Fetches subsequent pages using the continuation token."""
        first_page = {
            "comments": [make_comment_dict(1, "Page 1 comment")],
            "continuationToken": "token-abc",
        }
        second_page = {
            "comments": [make_comment_dict(2, "Page 2 comment")],
            "continuationToken": None,
        }
        mock_first = _make_mock_response(first_page)
        mock_second = _make_mock_response(second_page)
        with patch.object(
            requests.Session, "request", side_effect=[mock_first, mock_second]
        ):
            result = list(iter_work_item_comments(work_item_api_call))
        assert len(result) == 2
        assert result[0].text == "Page 1 comment"
        assert result[1].text == "Page 2 comment"


class TestAddWorkItemComment:
    """Tests for post_work_item_comment."""

    @staticmethod
    def test_posts_comment_and_returns_result(work_item_api_call: ApiCall) -> None:
        """Posts the comment text and returns the created WorkItemComment."""
        response_data = make_comment_dict(10, "New comment")
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = post_work_item_comment(work_item_api_call, "New comment")
        assert isinstance(result, WorkItemComment)
        assert result.text == "New comment"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["text"] == "New comment"

    @staticmethod
    def test_uses_custom_comment_format(work_item_api_call: ApiCall) -> None:
        """Passes the comment_format value as a query parameter."""
        response_data = make_comment_dict(11, "Markdown comment")
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_work_item_comment(
                work_item_api_call, "Markdown comment", comment_format="markdown"
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("format") == "markdown"


def make_single_work_item_dict(work_item_id: int = 42) -> dict[str, Any]:
    """Create a minimal valid work item dict for single-fetch tests.

    Returns:
        A dict with required WorkItemInfo fields populated.
    """
    return {"id": work_item_id, "fields": {"System.Title": "Test item"}}


class TestGetWorkItem:
    """Tests for get_work_item."""

    @staticmethod
    def test_returns_work_item_info(work_item_api_call: ApiCall) -> None:
        """Returns a WorkItemInfo for the requested ID."""
        response_data = make_single_work_item_dict(WORK_ITEM_ID)
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assert isinstance(result, WorkItemInfo)
        assert result.id == WORK_ITEM_ID
        assert result.fields["System.Title"] == "Test item"

    @staticmethod
    def test_without_expand_relations_no_expand_param(
        work_item_api_call: ApiCall,
    ) -> None:
        """Does not include $expand parameter by default."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_work_item(work_item_api_call)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "$expand" not in params

    @staticmethod
    def test_with_expand_relations_adds_expand_param(
        work_item_api_call: ApiCall,
    ) -> None:
        """Includes $expand=relations when expand_relations=True."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_work_item(work_item_api_call, expand_relations=True)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$expand") == "relations"


class TestAddWorkItemAttachment:
    """Tests for add_work_item_attachment."""

    @staticmethod
    def test_uploads_and_links_attachment(api_call: ApiCall) -> None:
        """Uploads the file and patches the work item with an AttachedFile relation."""
        attachment_url = (
            "https://dev.azure.com/org/proj/_apis/wit/attachments/file-uuid"
        )
        upload_response = _make_mock_response(
            {"id": "file-uuid", "url": attachment_url}
        )
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", side_effect=[upload_response, patch_response]
        ) as mock_req:
            result = add_work_item_attachment(
                api_call, 42, "report.txt", b"report content"
            )
        assert isinstance(result, WorkItemAttachmentRef)
        assert result.id == "file-uuid"
        # First call: upload
        first_call = mock_req.call_args_list[0]
        assert first_call.args[0] == "POST"
        assert first_call.kwargs.get("data") == b"report content"
        # Second call: patch work item
        second_call = mock_req.call_args_list[1]
        assert second_call.args[0] == "PATCH"
        patch_body = second_call.kwargs.get("json") or []
        assert patch_body[0]["value"]["rel"] == "AttachedFile"


class TestGetWorkItemTags:
    """Tests for get_work_item_tags."""

    @staticmethod
    def test_returns_tag_list(work_item_api_call: ApiCall) -> None:
        """Returns parsed tags from the System.Tags field."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "alpha; beta; gamma"
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item_tags(work_item_api_call)
        assert result == ["alpha", "beta", "gamma"]

    @staticmethod
    def test_returns_empty_list_when_no_tags(work_item_api_call: ApiCall) -> None:
        """Returns empty list when System.Tags field is absent."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item_tags(work_item_api_call)
        assert result == []


class TestAddWorkItemTag:
    """Tests for add_work_item_tag."""

    @staticmethod
    def test_adds_new_tag(work_item_api_call: ApiCall) -> None:
        """Patches work item and returns updated tag list when tag is new."""
        get_response = _make_mock_response(make_single_work_item_dict())
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session,
            "request",
            side_effect=[get_response, patch_response],
        ) as mock_req:
            result = add_work_item_tag(work_item_api_call, "newtag")
        assert "newtag" in result
        patch_call = mock_req.call_args_list[1]
        sent_json = patch_call.kwargs.get("json") or []
        tag_patches = [p for p in sent_json if p.get("path") == "/fields/System.Tags"]
        assert len(tag_patches) == 1
        assert "newtag" in tag_patches[0]["value"]

    @staticmethod
    def test_skips_patch_when_tag_already_present(
        work_item_api_call: ApiCall,
    ) -> None:
        """Does not patch the work item when the tag already exists."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "existing"
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = add_work_item_tag(work_item_api_call, "Existing")
        assert result == ["existing"]
        assert mock_req.call_count == 1

    @staticmethod
    def test_tag_comparison_is_case_insensitive(work_item_api_call: ApiCall) -> None:
        """Case-insensitive match prevents duplicate tags."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "MyTag"
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = add_work_item_tag(work_item_api_call, "mytag")
        assert result == ["MyTag"]
        assert mock_req.call_count == 1


class TestRemoveWorkItemTag:
    """Tests for remove_work_item_tag."""

    @staticmethod
    def test_removes_existing_tag(work_item_api_call: ApiCall) -> None:
        """Patches work item and returns updated tag list when tag is found."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "keep; remove"
        get_response = _make_mock_response(response_data)
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session,
            "request",
            side_effect=[get_response, patch_response],
        ) as mock_req:
            result = remove_work_item_tag(work_item_api_call, "remove")
        assert result == ["keep"]
        patch_call = mock_req.call_args_list[1]
        sent_json = patch_call.kwargs.get("json") or []
        tag_patches = [p for p in sent_json if p.get("path") == "/fields/System.Tags"]
        assert len(tag_patches) == 1
        assert "remove" not in tag_patches[0]["value"]

    @staticmethod
    def test_skips_patch_when_tag_not_present(work_item_api_call: ApiCall) -> None:
        """Does not patch the work item when the tag is absent."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "alpha"
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = remove_work_item_tag(work_item_api_call, "missing")
        assert result == ["alpha"]
        assert mock_req.call_count == 1

    @staticmethod
    def test_removal_is_case_insensitive(work_item_api_call: ApiCall) -> None:
        """Case-insensitive match removes the tag regardless of original casing."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "MyTag; Other"
        get_response = _make_mock_response(response_data)
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session,
            "request",
            side_effect=[get_response, patch_response],
        ):
            result = remove_work_item_tag(work_item_api_call, "mytag")
        assert result == ["Other"]


class TestAddArtifactLink:
    """Tests for add_artifact_link."""

    @staticmethod
    def test_includes_comment_in_attributes(work_item_api_call: ApiCall) -> None:
        """Includes comment in relation attributes when provided."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        artifact_url = "vstfs:///Git/PullRequestId/proj%2Frepo%2F1"
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_artifact_link(work_item_api_call, artifact_url, comment="PR link")
        sent_json = mock_req.call_args.kwargs.get("json") or []
        relation_value = sent_json[0]["value"]
        assert relation_value["attributes"]["comment"] == "PR link"

    @staticmethod
    def test_omits_comment_when_none(work_item_api_call: ApiCall) -> None:
        """Does not include comment key in attributes when comment is None."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        artifact_url = "vstfs:///Git/PullRequestId/proj%2Frepo%2F2"
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_artifact_link(work_item_api_call, artifact_url)
        sent_json = mock_req.call_args.kwargs.get("json") or []
        relation_value = sent_json[0]["value"]
        assert "comment" not in relation_value["attributes"]
