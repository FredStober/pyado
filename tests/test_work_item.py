"""Tests for pyado.work_item module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from typing import Annotated, Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from pyado import (
    ApiCall,
    ClassificationNode,
    CustomWorkItemBase,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemExpand,
    WorkItemFieldMap,
    WorkItemInfo,
    WorkItemLink,
    WorkItemRef,
    WorkItemRelation,
    WorkItemRelationType,
    add_team_iteration,
    add_work_item_attachment,
    add_work_item_link,
    add_work_item_tag,
    create_classification_node,
    create_work_item,
    get_classification_node,
    get_team_field_values,
    get_work_item,
    get_work_item_api_call,
    get_work_item_tags,
    iter_sprint_iterations,
    iter_work_item_comments,
    iter_work_item_details,
    patch_classification_node,
    post_wiql,
    post_work_item_comment,
    query_work_items,
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
        parent_url = "https://dev.azure.com/org/proj/_apis/wit/workItems/1"
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
            list(
                iter_sprint_iterations(
                    api_call, timeframe_filter=SprintIterationTimeframe.CURRENT
                )
            )
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
            url="https://dev.azure.com/org/proj/_apis/wit/workItems/1",
        )
        assert relation.attributes is None

    @staticmethod
    def test_with_attributes() -> None:
        """Attributes field can hold arbitrary data."""
        relation = WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url="https://dev.azure.com/org/proj/_apis/wit/workItems/1",
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


class TestQueryWorkItems:
    """Tests for query_work_items."""

    @staticmethod
    def test_yields_work_item_details_for_query_results(api_call: ApiCall) -> None:
        """Runs WIQL query then fetches and yields full work item details."""
        wiql_response = _make_mock_response({"workItems": [{"id": 1}, {"id": 2}]})
        batch_response = _make_mock_response(
            {"value": [make_work_item_dict(1), make_work_item_dict(2)]}
        )
        with patch.object(
            requests.Session,
            "request",
            side_effect=[wiql_response, batch_response],
        ):
            result = list(
                query_work_items(api_call, "SELECT [System.Id] FROM WorkItems")
            )
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @staticmethod
    def test_yields_nothing_when_query_returns_no_results(api_call: ApiCall) -> None:
        """Returns immediately without making a batch call when WIQL returns empty."""
        wiql_response = _make_mock_response({"workItems": []})
        with patch.object(
            requests.Session, "request", return_value=wiql_response
        ) as mock_req:
            result = list(
                query_work_items(api_call, "SELECT [System.Id] FROM WorkItems")
            )
        assert result == []
        assert mock_req.call_count == 1


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
    def test_with_expand_adds_expand_param(
        work_item_api_call: ApiCall,
    ) -> None:
        """Includes $expand query parameter when expand is provided."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_work_item(work_item_api_call, expand=WorkItemExpand.RELATIONS)
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


class TestCustomWorkItemBase:
    """Tests for CustomWorkItemBase.to_fields."""

    @staticmethod
    def test_to_fields_maps_annotated_fields() -> None:
        """Maps WorkItemFieldMap-annotated fields to ADO field names."""

        class SimpleTicket(CustomWorkItemBase):
            title: Annotated[str, WorkItemFieldMap("System.Title")]

        result = SimpleTicket(title="My title").to_fields()
        assert result == {"System.Title": "My title"}

    @staticmethod
    def test_to_fields_skips_none_values() -> None:
        """Fields with None value are excluded from the result."""

        class OptionalTicket(CustomWorkItemBase):
            title: Annotated[str | None, WorkItemFieldMap("System.Title")] = None

        result = OptionalTicket().to_fields()
        assert "System.Title" not in result

    @staticmethod
    def test_to_fields_multiple_markers_copies_to_each_path() -> None:
        """A field with multiple WorkItemFieldMap markers maps to all ADO paths."""

        class MultiTicket(CustomWorkItemBase):
            desc: Annotated[
                str,
                WorkItemFieldMap("System.Description"),
                WorkItemFieldMap("Microsoft.VSTS.TCM.ReproSteps"),
            ]

        result = MultiTicket(desc="details").to_fields()
        assert result["System.Description"] == "details"
        assert result["Microsoft.VSTS.TCM.ReproSteps"] == "details"

    @staticmethod
    def test_to_fields_ignores_non_field_map_metadata() -> None:
        """Metadata items that are not WorkItemFieldMap are skipped."""

        class MixedMetaTicket(CustomWorkItemBase):
            title: Annotated[str, "extra-meta", WorkItemFieldMap("System.Title")]

        result = MixedMetaTicket(title="hello").to_fields()
        assert result == {"System.Title": "hello"}


class TestWorkItemLink:
    """Tests for WorkItemLink factory class."""

    # --- artifact links ---

    @staticmethod
    def test_build_returns_artifact_link_relation() -> None:
        """build() produces an ArtifactLink with the build vstfs URL."""
        result = WorkItemLink.build(42)
        assert result.rel == WorkItemRelationType.ARTIFACT_LINK
        assert "Build/Build" in result.url
        assert "42" in result.url
        assert result.attributes == {"name": "Build"}

    @staticmethod
    def test_build_with_comment_includes_comment_in_attributes() -> None:
        """build() with comment adds it to the attributes dict."""
        result = WorkItemLink.build(42, comment="see build")
        assert result.attributes == {"name": "Build", "comment": "see build"}

    @staticmethod
    def test_commit_returns_artifact_link_relation() -> None:
        """commit() produces an ArtifactLink with the commit vstfs URL."""
        project_id = uuid4()
        repo_id = uuid4()
        result = WorkItemLink.commit(project_id, repo_id, "abc123")
        assert result.rel == WorkItemRelationType.ARTIFACT_LINK
        assert "Git/Commit" in result.url
        assert str(project_id) in result.url
        assert result.attributes == {"name": "Fixed in Commit"}

    @staticmethod
    def test_pull_request_returns_artifact_link_relation() -> None:
        """pull_request() produces an ArtifactLink with the PR vstfs URL."""
        project_id = uuid4()
        repo_id = uuid4()
        result = WorkItemLink.pull_request(project_id, repo_id, 7)
        assert result.rel == WorkItemRelationType.ARTIFACT_LINK
        assert "Git/PullRequestId" in result.url
        assert result.attributes == {"name": "Pull Request"}

    # --- work-item links ---

    @staticmethod
    def test_related_returns_related_link_without_comment(
        api_call: ApiCall,
    ) -> None:
        """related() produces a RELATED link whose URL encodes the WI ID."""
        result = WorkItemLink.related(api_call, 5)
        assert result.rel == WorkItemRelationType.RELATED
        assert result.url is not None
        assert result.url.endswith("/5")
        assert result.attributes is None

    @staticmethod
    def test_related_with_comment_includes_attributes(api_call: ApiCall) -> None:
        """related() with comment sets attributes dict."""
        result = WorkItemLink.related(api_call, 5, comment="related to")
        assert result.attributes == {"comment": "related to"}

    @staticmethod
    def test_parent_returns_parent_link(api_call: ApiCall) -> None:
        """parent() produces a PARENT (Hierarchy-Reverse) link."""
        result = WorkItemLink.parent(api_call, 1)
        assert result.rel == WorkItemRelationType.PARENT

    @staticmethod
    def test_child_returns_child_link(api_call: ApiCall) -> None:
        """child() produces a CHILD (Hierarchy-Forward) link."""
        result = WorkItemLink.child(api_call, 2)
        assert result.rel == WorkItemRelationType.CHILD

    @staticmethod
    def test_duplicate_returns_duplicate_link(api_call: ApiCall) -> None:
        """duplicate() produces a DUPLICATE (Duplicate-Forward) link."""
        result = WorkItemLink.duplicate(api_call, 3)
        assert result.rel == WorkItemRelationType.DUPLICATE

    @staticmethod
    def test_duplicate_of_returns_duplicate_of_link(api_call: ApiCall) -> None:
        """duplicate_of() produces a DUPLICATE_OF (Duplicate-Reverse) link."""
        result = WorkItemLink.duplicate_of(api_call, 3)
        assert result.rel == WorkItemRelationType.DUPLICATE_OF

    @staticmethod
    def test_successor_returns_successor_link(api_call: ApiCall) -> None:
        """successor() produces a SUCCESSOR (Dependency-Forward) link."""
        result = WorkItemLink.successor(api_call, 4)
        assert result.rel == WorkItemRelationType.SUCCESSOR

    @staticmethod
    def test_predecessor_returns_predecessor_link(api_call: ApiCall) -> None:
        """predecessor() produces a PREDECESSOR (Dependency-Reverse) link."""
        result = WorkItemLink.predecessor(api_call, 4)
        assert result.rel == WorkItemRelationType.PREDECESSOR

    @staticmethod
    def test_tested_by_returns_tested_by_link(api_call: ApiCall) -> None:
        """tested_by() produces a TESTED_BY (TestedBy-Forward) link."""
        result = WorkItemLink.tested_by(api_call, 10)
        assert result.rel == WorkItemRelationType.TESTED_BY

    @staticmethod
    def test_tests_returns_tests_link(api_call: ApiCall) -> None:
        """tests() produces a TESTS (TestedBy-Reverse) link."""
        result = WorkItemLink.tests(api_call, 10)
        assert result.rel == WorkItemRelationType.TESTS

    @staticmethod
    def test_test_case_returns_test_case_link(api_call: ApiCall) -> None:
        """test_case() produces a TEST_CASE link."""
        result = WorkItemLink.test_case(api_call, 10)
        assert result.rel == WorkItemRelationType.TEST_CASE

    @staticmethod
    def test_shared_parameter_referenced_by_returns_correct_link(
        api_call: ApiCall,
    ) -> None:
        """shared_parameter_referenced_by() returns SHARED_PARAMETER_REFERENCED_BY."""
        result = WorkItemLink.shared_parameter_referenced_by(api_call, 10)
        assert result.rel == WorkItemRelationType.SHARED_PARAMETER_REFERENCED_BY

    @staticmethod
    def test_affects_returns_affects_link(api_call: ApiCall) -> None:
        """affects() produces an AFFECTS (Affects-Forward) link."""
        result = WorkItemLink.affects(api_call, 11)
        assert result.rel == WorkItemRelationType.AFFECTS

    @staticmethod
    def test_affected_by_returns_affected_by_link(api_call: ApiCall) -> None:
        """affected_by() produces an AFFECTED_BY (Affects-Reverse) link."""
        result = WorkItemLink.affected_by(api_call, 11)
        assert result.rel == WorkItemRelationType.AFFECTED_BY

    # --- hyperlink ---

    @staticmethod
    def test_hyperlink_without_comment() -> None:
        """hyperlink() without comment sets attributes to None."""
        result = WorkItemLink.hyperlink("https://example.com")
        assert result.rel == WorkItemRelationType.HYPERLINK
        assert result.url == "https://example.com"
        assert result.attributes is None

    @staticmethod
    def test_hyperlink_with_comment() -> None:
        """hyperlink() with comment sets attributes dict."""
        result = WorkItemLink.hyperlink("https://example.com", comment="see docs")
        assert result.attributes == {"comment": "see docs"}


class TestAddWorkItemLink:
    """Tests for add_work_item_link."""

    @staticmethod
    def test_patches_work_item_with_relation(
        api_call: ApiCall, work_item_api_call: ApiCall
    ) -> None:
        """Sends a PATCH with the relation serialised at /relations/-."""
        link = WorkItemLink.related(api_call, 5)
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = add_work_item_link(work_item_api_call, link)
        assert isinstance(result, WorkItemInfo)
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["path"] == "/relations/-"
        assert sent_json[0]["value"]["rel"] == WorkItemRelationType.RELATED


class TestGetClassificationNode:
    """Tests for get_classification_node."""

    @staticmethod
    def test_returns_classification_node(api_call: ApiCall) -> None:
        """Returns a ClassificationNode with fields populated from the response."""
        node_data = {"id": 1, "name": "Iterations", "children": []}
        mock_response = _make_mock_response(node_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_classification_node(api_call)
        assert isinstance(result, ClassificationNode)
        assert result.id == 1
        assert result.name == "Iterations"
        assert result.children == []

    @staticmethod
    def test_without_path_targets_root(api_call: ApiCall) -> None:
        """Without a path, requests the iteration tree root."""
        mock_response = _make_mock_response({"id": 1, "name": "root"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(api_call)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "classificationnodes/iterations" in url
        assert url.endswith("classificationnodes/iterations")

    @staticmethod
    def test_with_path_appends_path_to_url(api_call: ApiCall) -> None:
        """With a path, the path is appended to the URL (spaces percent-encoded)."""
        mock_response = _make_mock_response({"id": 2, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(api_call, "Sprint 42")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Sprint%2042" in url

    @staticmethod
    def test_depth_passed_as_parameter(api_call: ApiCall) -> None:
        """The depth argument is forwarded as a query parameter."""
        mock_response = _make_mock_response({"id": 1, "name": "root"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(api_call, depth=5)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$depth") == 5


class TestCreateClassificationNode:
    """Tests for create_classification_node."""

    @staticmethod
    def test_returns_identifier_guid(api_call: ApiCall) -> None:
        """Returns the 'identifier' value from the response."""
        guid = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
        mock_response = _make_mock_response({"identifier": guid, "name": "Sprint 1"})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = create_classification_node(api_call, "Sprint 1")
        assert result == guid

    @staticmethod
    def test_posts_name_in_body(api_call: ApiCall) -> None:
        """The request body contains the 'name' field."""
        mock_response = _make_mock_response({"identifier": "abc", "name": "Sprint 2"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(api_call, "Sprint 2")
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["name"] == "Sprint 2"

    @staticmethod
    def test_with_dates_includes_attributes(api_call: ApiCall) -> None:
        """When dates are given, the body includes an attributes dict."""
        mock_response = _make_mock_response({"identifier": "abc", "name": "Sprint 3"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                "Sprint 3",
                start_date=date(2024, 1, 1),
                finish_date=date(2024, 1, 14),
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "attributes" in sent_json
        assert sent_json["attributes"]["startDate"] == "2024-01-01T00:00:00Z"
        assert sent_json["attributes"]["finishDate"] == "2024-01-14T00:00:00Z"

    @staticmethod
    def test_without_dates_omits_attributes(api_call: ApiCall) -> None:
        """When no dates are given, attributes are not included in the body."""
        mock_response = _make_mock_response({"identifier": "abc", "name": "Sprint 4"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(api_call, "Sprint 4")
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "attributes" not in sent_json

    @staticmethod
    def test_with_parent_path_appends_to_url(api_call: ApiCall) -> None:
        """When parent_path is given, it appears in the request URL (spaces encoded)."""
        mock_response = _make_mock_response({"identifier": "abc", "name": "Child"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(api_call, "Child", "Release 1")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Release%201" in url


class TestPatchClassificationNode:
    """Tests for patch_classification_node."""

    @staticmethod
    def test_returns_classification_node(api_call: ApiCall) -> None:
        """Returns a ClassificationNode with fields from the patch response."""
        node_data = {"id": 1, "name": "Sprint 42", "attributes": {}}
        mock_response = _make_mock_response(node_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_classification_node(api_call, "Sprint 42")
        assert isinstance(result, ClassificationNode)
        assert result.id == 1
        assert result.name == "Sprint 42"

    @staticmethod
    def test_sends_patch_request(api_call: ApiCall) -> None:
        """Sends a PATCH request to the classification node endpoint."""
        mock_response = _make_mock_response({"id": 1, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(api_call, "Sprint 42")
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_path_appears_in_url(api_call: ApiCall) -> None:
        """The node path is included in the request URL (spaces percent-encoded)."""
        mock_response = _make_mock_response({"id": 1, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(api_call, "Sprint 42")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Sprint%2042" in url

    @staticmethod
    def test_start_and_finish_dates_in_attributes(api_call: ApiCall) -> None:
        """start_date and finish_date are serialised into the attributes body."""
        mock_response = _make_mock_response({"id": 1, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(
                api_call,
                "Sprint 42",
                start_date=date(2024, 3, 1),
                finish_date=date(2024, 3, 14),
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["attributes"]["startDate"] == "2024-03-01T00:00:00Z"
        assert sent_json["attributes"]["finishDate"] == "2024-03-14T00:00:00Z"


class TestGetTeamFieldValues:
    """Tests for get_team_field_values."""

    @staticmethod
    def test_returns_values_list(api_call: ApiCall) -> None:
        """Returns a list of TeamFieldValue from the 'values' key of the response."""
        values = [{"value": "MyProject\\TeamA", "includeChildren": False}]
        mock_response = _make_mock_response({"values": values})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_team_field_values(api_call)
        assert len(result) == 1
        assert isinstance(result[0], TeamFieldValue)
        assert result[0].value == "MyProject\\TeamA"
        assert result[0].include_children is False

    @staticmethod
    def test_returns_empty_list_when_values_missing(api_call: ApiCall) -> None:
        """Returns an empty list when the response has no 'values' key."""
        mock_response = _make_mock_response({})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_team_field_values(api_call)
        assert result == []

    @staticmethod
    def test_sends_get_to_teamfieldvalues_endpoint(api_call: ApiCall) -> None:
        """Sends a GET request to the teamfieldvalues endpoint."""
        mock_response = _make_mock_response({"values": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_team_field_values(api_call)
        url = mock_req.call_args.kwargs.get("url", "")
        assert mock_req.call_args.args[0] == "GET"
        assert "teamfieldvalues" in url


class TestAddTeamIteration:
    """Tests for add_team_iteration."""

    @staticmethod
    def test_posts_iteration_id_to_endpoint(api_call: ApiCall) -> None:
        """Posts the iteration ID to the teamsettings/iterations endpoint."""
        iteration_id = uuid4()
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_team_iteration(api_call, iteration_id)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json["id"] == str(iteration_id)

    @staticmethod
    def test_targets_iterations_endpoint(api_call: ApiCall) -> None:
        """The request targets the teamsettings/iterations endpoint."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_team_iteration(api_call, uuid4())
        url = mock_req.call_args.kwargs.get("url", "")
        assert "teamsettings/iterations" in url
