"""Tests for pyado.work_item module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from pyado.oop._work_item import iter_work_item_details
from pyado.raw import (
    ApiCall,
    ClassificationNode,
    ClassificationNodeAttributes,
    ClassificationNodePatchRequest,
    ClassificationNodeRequest,
    ClassificationNodeUrlType,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    TextFormat,
    WorkItemComment,
    WorkItemExpand,
    WorkItemInfo,
    WorkItemQuery,
    WorkItemQueryExpand,
    WorkItemRef,
    WorkItemRelation,
    add_team_iteration,
    create_classification_node,
    delete_classification_node,
    delete_team_iteration,
    delete_work_item,
    delete_work_item_comment,
    get_classification_node,
    get_query_folder,
    get_query_tree,
    get_team_field_values,
    get_work_item,
    get_work_item_api_call,
    get_work_item_attachment_bytes,
    iter_sprint_iterations,
    iter_work_item_comments,
    iter_work_item_revisions,
    list_sprint_iterations,
    list_work_item_comments,
    list_work_item_revisions,
    patch_classification_node,
    patch_work_item_comment,
    post_wiql,
    post_work_item_comment,
    restore_work_item,
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


def make_single_work_item_dict(work_item_id: int = 42) -> dict[str, Any]:
    """Create a minimal valid work item dict for single-fetch tests.

    Returns:
        A dict with required WorkItemInfo fields populated.
    """
    return {"id": work_item_id, "fields": {"System.Title": "Test item"}}


def _make_wit_query_dict(query_id: str = "abc-123", **overrides: Any) -> dict[str, Any]:
    """Create a minimal valid WorkItemQuery dict."""
    data: dict[str, Any] = {
        "id": query_id,
        "name": "Shared Queries",
        "isFolder": True,
        "hasChildren": False,
        "children": [],
    }
    data.update(overrides)
    return data


def _make_work_item_comment_dict(comment_id: int = 1) -> dict[str, Any]:
    """Create a minimal valid WorkItemComment dict."""
    return {
        "id": comment_id,
        "text": "A comment",
        "version": 1,
        "createdDate": "2024-01-15T12:00:00+00:00",
        "modifiedDate": "2024-01-15T12:00:00+00:00",
        "url": f"https://dev.azure.com/org/proj/_apis/wit/workItems/42/comments/{comment_id}",
    }


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
                work_item_api_call,
                "Markdown comment",
                comment_format=TextFormat.MARKDOWN,
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("format") == "markdown"


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


class TestGetQueryTree:
    """Tests for get_query_tree."""

    @staticmethod
    def test_returns_wit_query(api_call: ApiCall) -> None:
        """Returns a list of WorkItemQuery parsed from the paged response."""
        response_data = {"count": 1, "value": [_make_wit_query_dict()]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_query_tree(api_call)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], WorkItemQuery)
        assert result[0].id == "abc-123"
        assert result[0].is_folder is True

    @staticmethod
    def test_sends_dollar_depth_parameter(api_call: ApiCall) -> None:
        """Sends $depth (not depth) as the query parameter key."""
        response_data: dict[str, Any] = {"count": 0, "value": []}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_query_tree(api_call, depth=3)
        params = mock_req.call_args[1]["params"]
        assert "$depth" in params
        assert "depth" not in {k for k in params if k != "$depth"}

    @staticmethod
    def test_sends_dollar_expand_parameter(api_call: ApiCall) -> None:
        """Sends $expand as the query parameter key."""
        response_data: dict[str, Any] = {"count": 0, "value": []}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_query_tree(api_call, expand=WorkItemQueryExpand.CLAUSES)
        params = mock_req.call_args[1]["params"]
        assert "$expand" in params
        assert params["$expand"] == WorkItemQueryExpand.CLAUSES


class TestGetQueryFolder:
    """Tests for get_query_folder."""

    @staticmethod
    def test_returns_wit_query(api_call: ApiCall) -> None:
        """Returns a WorkItemQuery parsed from the response."""
        folder_id = "folder-guid-001"
        child = _make_wit_query_dict("child-1", name="Sprint Queries", isFolder=False)
        response_data = _make_wit_query_dict(
            "folder-guid-001", name="Sprints", hasChildren=True, children=[child]
        )
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_query_folder(api_call, folder_id)
        assert isinstance(result, WorkItemQuery)
        assert result.id == folder_id
        assert len(result.children) == 1

    @staticmethod
    def test_folder_id_in_url(api_call: ApiCall) -> None:
        """The folder GUID appears in the request URL."""
        folder_id = "deadbeef-0000-0000-0000-000000000001"
        response_data = _make_wit_query_dict(folder_id)
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_query_folder(api_call, folder_id)
        url_called = mock_req.call_args[1]["url"]
        assert folder_id in url_called


class TestGetClassificationNode:
    """Tests for get_classification_node."""

    @staticmethod
    def test_returns_classification_node(api_call: ApiCall) -> None:
        """Returns a ClassificationNode with fields populated from the response."""
        node_data = {"id": 1, "name": "Iterations", "children": []}
        mock_response = _make_mock_response(node_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_classification_node(
                api_call, node_type=ClassificationNodeUrlType.ITERATIONS
            )
        assert isinstance(result, ClassificationNode)
        assert result.id == 1
        assert result.name == "Iterations"
        assert result.children == []

    @staticmethod
    def test_iterations_without_path_targets_root(api_call: ApiCall) -> None:
        """Without a path, requests the iteration tree root."""
        mock_response = _make_mock_response({"id": 1, "name": "root"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(
                api_call, node_type=ClassificationNodeUrlType.ITERATIONS
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "classificationnodes/iterations" in url
        assert url.endswith("classificationnodes/iterations")

    @staticmethod
    def test_areas_without_path_targets_root(api_call: ApiCall) -> None:
        """With AREAS node_type, requests the area tree root."""
        mock_response = _make_mock_response({"id": 1, "name": "root"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(api_call, node_type=ClassificationNodeUrlType.AREAS)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "classificationnodes/areas" in url
        assert url.endswith("classificationnodes/areas")

    @staticmethod
    def test_with_path_appends_path_to_url(api_call: ApiCall) -> None:
        """With a path, the path is appended to the URL (spaces percent-encoded)."""
        mock_response = _make_mock_response({"id": 2, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(
                api_call, "Sprint 42", node_type=ClassificationNodeUrlType.ITERATIONS
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Sprint%2042" in url

    @staticmethod
    def test_depth_passed_as_parameter(api_call: ApiCall) -> None:
        """The depth argument is forwarded as a query parameter."""
        mock_response = _make_mock_response({"id": 1, "name": "root"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_classification_node(
                api_call, depth=5, node_type=ClassificationNodeUrlType.ITERATIONS
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$depth") == 5


class TestCreateClassificationNode:
    """Tests for create_classification_node."""

    @staticmethod
    def test_returns_classification_node(api_call: ApiCall) -> None:
        """Returns a ClassificationNode with the identifier from the response."""
        guid = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
        mock_response = _make_mock_response(
            {"id": 1, "identifier": guid, "name": "Sprint 1"}
        )
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Sprint 1"),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        assert isinstance(result, ClassificationNode)
        assert result.identifier == guid

    @staticmethod
    def test_posts_name_in_body(api_call: ApiCall) -> None:
        """The request body contains the 'name' field."""
        mock_response = _make_mock_response(
            {"id": 1, "identifier": "abc", "name": "Sprint 2"}
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Sprint 2"),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["name"] == "Sprint 2"

    @staticmethod
    def test_with_attributes_includes_dates(api_call: ApiCall) -> None:
        """When attributes are given, the body includes an attributes dict."""
        mock_response = _make_mock_response(
            {"id": 1, "identifier": "abc", "name": "Sprint 3"}
        )
        attrs = ClassificationNodeAttributes(
            start_date="2024-01-01T00:00:00Z",
            finish_date="2024-01-14T00:00:00Z",
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Sprint 3", attributes=attrs),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "attributes" in sent_json
        assert sent_json["attributes"]["startDate"] == "2024-01-01T00:00:00Z"
        assert sent_json["attributes"]["finishDate"] == "2024-01-14T00:00:00Z"

    @staticmethod
    def test_without_attributes_omits_attributes(api_call: ApiCall) -> None:
        """When no attributes are given, attributes are not included in the body."""
        mock_response = _make_mock_response(
            {"id": 1, "identifier": "abc", "name": "Sprint 4"}
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Sprint 4"),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "attributes" not in sent_json

    @staticmethod
    def test_with_parent_path_appends_to_url(api_call: ApiCall) -> None:
        """When parent_path is given, it appears in the request URL (spaces encoded)."""
        mock_response = _make_mock_response(
            {"id": 1, "identifier": "abc", "name": "Child"}
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Child"),
                "Release 1",
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Release%201" in url

    @staticmethod
    def test_areas_node_type_uses_areas_url(api_call: ApiCall) -> None:
        """With AREAS node_type, the request URL contains classificationnodes/areas."""
        mock_response = _make_mock_response(
            {"id": 1, "identifier": "abc", "name": "Team A"}
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_classification_node(
                api_call,
                ClassificationNodeRequest(name="Team A"),
                node_type=ClassificationNodeUrlType.AREAS,
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert url.endswith("classificationnodes/areas")


class TestPatchClassificationNode:
    """Tests for patch_classification_node."""

    @staticmethod
    def test_returns_classification_node(api_call: ApiCall) -> None:
        """Returns a ClassificationNode with fields from the patch response."""
        node_data = {"id": 1, "name": "Sprint 42", "attributes": {}}
        mock_response = _make_mock_response(node_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_classification_node(
                api_call,
                "Sprint 42",
                ClassificationNodePatchRequest(),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
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
            patch_classification_node(
                api_call,
                "Sprint 42",
                ClassificationNodePatchRequest(),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_path_appears_in_url(api_call: ApiCall) -> None:
        """The node path is included in the request URL (spaces percent-encoded)."""
        mock_response = _make_mock_response({"id": 1, "name": "Sprint 42"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(
                api_call,
                "Sprint 42",
                ClassificationNodePatchRequest(),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "Sprint%2042" in url

    @staticmethod
    def test_attributes_serialised_to_body(api_call: ApiCall) -> None:
        """Attributes in the request are serialised into the patch body."""
        mock_response = _make_mock_response({"id": 1, "name": "Sprint 42"})
        attrs = ClassificationNodeAttributes(
            start_date="2024-03-01T00:00:00Z",
            finish_date="2024-03-14T00:00:00Z",
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(
                api_call,
                "Sprint 42",
                ClassificationNodePatchRequest(attributes=attrs),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["attributes"]["startDate"] == "2024-03-01T00:00:00Z"
        assert sent_json["attributes"]["finishDate"] == "2024-03-14T00:00:00Z"

    @staticmethod
    def test_none_path_targets_root(api_call: ApiCall) -> None:
        """When path is None, the request targets the root iterations endpoint."""
        mock_response = _make_mock_response({"id": 1, "name": "Iterations"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_classification_node(
                api_call,
                None,
                ClassificationNodePatchRequest(),
                node_type=ClassificationNodeUrlType.ITERATIONS,
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert url.endswith("classificationnodes/iterations")


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


class TestDeleteWorkItem:
    """Tests for delete_work_item."""

    @staticmethod
    def test_sends_delete_request(work_item_api_call: ApiCall) -> None:
        """Sends a DELETE request to the work item endpoint."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_work_item(work_item_api_call)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_returns_none(work_item_api_call: ApiCall) -> None:
        """Returns None on success."""
        mock_response = _make_mock_response()
        with patch.object(requests.Session, "request", return_value=mock_response):
            delete_work_item(work_item_api_call)

    @staticmethod
    def test_url_contains_work_item_id(work_item_api_call: ApiCall) -> None:
        """Request URL contains the work item ID."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_work_item(work_item_api_call)
        url = mock_req.call_args.kwargs.get("url", "")
        assert str(WORK_ITEM_ID) in url


class TestPatchWorkItemComment:
    """Tests for patch_work_item_comment."""

    @staticmethod
    def test_returns_work_item_comment(work_item_api_call: ApiCall) -> None:
        """Returns a WorkItemComment parsed from the response."""
        mock_response = _make_mock_response(_make_work_item_comment_dict(5))
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_work_item_comment(work_item_api_call, 5, "updated text")
        assert isinstance(result, WorkItemComment)
        assert result.id == 5

    @staticmethod
    def test_sends_patch_request(work_item_api_call: ApiCall) -> None:
        """Sends a PATCH request."""
        mock_response = _make_mock_response(_make_work_item_comment_dict(1))
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_work_item_comment(work_item_api_call, 1, "new text")
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_url_contains_comment_id(work_item_api_call: ApiCall) -> None:
        """Request URL path includes the comment ID."""
        mock_response = _make_mock_response(_make_work_item_comment_dict(7))
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_work_item_comment(work_item_api_call, 7, "text")
        url = mock_req.call_args.kwargs.get("url", "")
        assert "7" in url

    @staticmethod
    def test_body_contains_text(work_item_api_call: ApiCall) -> None:
        """Request body contains the new comment text."""
        mock_response = _make_mock_response(_make_work_item_comment_dict(1))
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_work_item_comment(work_item_api_call, 1, "my updated comment")
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("text") == "my updated comment"


class TestDeleteWorkItemComment:
    """Tests for delete_work_item_comment."""

    @staticmethod
    def test_sends_delete_request(work_item_api_call: ApiCall) -> None:
        """Sends a DELETE request."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_work_item_comment(work_item_api_call, 3)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_returns_none(work_item_api_call: ApiCall) -> None:
        """Returns None on success."""
        mock_response = _make_mock_response()
        with patch.object(requests.Session, "request", return_value=mock_response):
            delete_work_item_comment(work_item_api_call, 3)

    @staticmethod
    def test_url_contains_comment_id(work_item_api_call: ApiCall) -> None:
        """Request URL contains the comment ID."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_work_item_comment(work_item_api_call, 9)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "9" in url


class TestPatchClassificationNodeAreas:
    """Tests for patch_classification_node with AREAS node type."""

    @staticmethod
    def test_areas_type_uses_areas_url(api_call: ApiCall) -> None:
        """With AREAS node_type, the request URL contains classificationnodes/areas."""
        node_data = {
            "id": 5,
            "name": "Renamed Team",
            "structureType": "area",
            "hasChildren": False,
        }
        mock_response = _make_mock_response(node_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = patch_classification_node(
                api_call,
                "Team A",
                ClassificationNodePatchRequest(name="Renamed Team"),
                node_type=ClassificationNodeUrlType.AREAS,
            )
        assert isinstance(result, ClassificationNode)
        assert result.name == "Renamed Team"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "areas" in url


class TestGetWorkItemAttachmentBytes:
    """Tests for get_work_item_attachment_bytes."""

    @staticmethod
    def test_returns_raw_bytes(api_call: ApiCall) -> None:
        """Returns the raw bytes from the API response."""
        attachment_id = str(uuid4())
        mock_response = _make_mock_response()
        mock_response.content = b"attachment content"
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item_attachment_bytes(api_call, attachment_id)
        assert result == b"attachment content"

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request to the attachments endpoint."""
        attachment_id = str(uuid4())
        mock_response = _make_mock_response()
        mock_response.content = b"data"
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_work_item_attachment_bytes(api_call, attachment_id)
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_url_contains_attachment_id(api_call: ApiCall) -> None:
        """Request URL contains the attachment ID."""
        attachment_id = str(uuid4())
        mock_response = _make_mock_response()
        mock_response.content = b"data"
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_work_item_attachment_bytes(api_call, attachment_id)
        url = mock_req.call_args.kwargs.get("url", "")
        assert attachment_id in url


class TestIterWorkItemRevisions:
    """Tests for iter_work_item_revisions."""

    @staticmethod
    def test_yields_work_item_info_objects(work_item_api_call: ApiCall) -> None:
        """Yields WorkItemInfo objects from the revisions response."""
        response_data = {
            "value": [
                {"id": WORK_ITEM_ID, "fields": {"System.Title": "v1"}},
                {"id": WORK_ITEM_ID, "fields": {"System.Title": "v2"}},
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_revisions(work_item_api_call))
        assert len(result) == 2
        assert all(isinstance(item, WorkItemInfo) for item in result)

    @staticmethod
    def test_yields_empty_when_no_revisions(work_item_api_call: ApiCall) -> None:
        """Yields nothing when no revisions are returned."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_revisions(work_item_api_call))
        assert result == []

    @staticmethod
    def test_url_contains_revisions(work_item_api_call: ApiCall) -> None:
        """Request URL contains the 'revisions' path segment."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_work_item_revisions(work_item_api_call))
        url = mock_req.call_args.kwargs.get("url", "")
        assert "revisions" in url

    @staticmethod
    def test_sends_get_request(work_item_api_call: ApiCall) -> None:
        """Sends a GET request."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_work_item_revisions(work_item_api_call))
        assert mock_req.call_args.args[0] == "GET"


class TestDeleteClassificationNode:
    """Tests for delete_classification_node."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_classification_node(
                api_call, "Sprint 1", node_type=ClassificationNodeUrlType.ITERATIONS
            )
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_url_contains_node_type_and_path(api_call: ApiCall) -> None:
        """Request URL contains the node type and path."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_classification_node(
                api_call, "Sprint 1", node_type=ClassificationNodeUrlType.ITERATIONS
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "classificationnodes" in url
        assert "iterations" in url
        assert "Sprint" in url

    @staticmethod
    def test_url_contains_areas_for_area_node_type(api_call: ApiCall) -> None:
        """Request URL uses 'areas' segment when node_type is AREAS."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_classification_node(
                api_call, "Team A", node_type=ClassificationNodeUrlType.AREAS
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "areas" in url

    @staticmethod
    def test_omits_path_segment_when_path_is_none(api_call: ApiCall) -> None:
        """No extra path segment is appended when path is None."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_classification_node(
                api_call, None, node_type=ClassificationNodeUrlType.ITERATIONS
            )
        url = mock_req.call_args.kwargs.get("url", "")
        assert "classificationnodes" in url


class TestDeleteTeamIteration:
    """Tests for delete_team_iteration."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request to remove the iteration."""
        iteration_id = uuid4()
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_team_iteration(api_call, iteration_id)
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_url_contains_iteration_id(api_call: ApiCall) -> None:
        """Request URL contains the iteration UUID."""
        iteration_id = uuid4()
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_team_iteration(api_call, iteration_id)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "teamsettings/iterations" in url
        assert str(iteration_id) in url


class TestRestoreWorkItem:
    """Tests for restore_work_item."""

    @staticmethod
    def test_sends_patch_request(api_call: ApiCall) -> None:
        """Sends a PATCH request to the recycleBin endpoint."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            restore_work_item(api_call, 42)
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_url_contains_recycle_bin_and_id(api_call: ApiCall) -> None:
        """Request URL contains recycleBin and the work item ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            restore_work_item(api_call, 99)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "recycleBin" in url
        assert "99" in url

    @staticmethod
    def test_sends_is_deleted_false(api_call: ApiCall) -> None:
        """Request body contains isDeleted: false."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            restore_work_item(api_call, 42)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("isDeleted") is False


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

_WIQL_SMOKE_RESPONSE = {
    "queryType": "flat",
    "queryResultType": "workItem",
    "asOf": "2026-06-02T12:47:24.313Z",
    "columns": [
        {
            "referenceName": "System.Id",
            "name": "ID",
            "url": "https://dev.azure.com/example-org/_apis/wit/fields/System.Id",
        }
    ],
    "sortColumns": [
        {
            "field": {
                "referenceName": "System.ChangedDate",
                "name": "Changed Date",
                "url": (
                    "https://dev.azure.com/example-org/_apis/wit/fields/System.ChangedDate"
                ),
            },
            "descending": True,
        }
    ],
    "workItems": [
        {
            "id": idx,
            "url": (
                f"https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                f"/_apis/wit/workItems/{idx}"
            ),
        }
        for idx in [105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93]
    ],
}

_WORK_ITEMS_BATCH_SMOKE_RESPONSE = {
    "count": 5,
    "value": [
        {
            "id": 101,
            "rev": 10,
            "fields": {
                "System.Id": 101,
                "System.AssignedTo": _SMOKE_AUTHOR,
                "System.Title": "[smoke-test] work item 101",
                "System.Description": "**Smoke test** description",
            },
            "multilineFieldsFormat": {},
            "url": "https://dev.azure.com/example-org/_apis/wit/workItems/101",
        },
        {
            "id": 102,
            "rev": 10,
            "fields": {
                "System.Id": 102,
                "System.AssignedTo": _SMOKE_AUTHOR,
                "System.Title": "[smoke-test] work item 102",
                "System.Description": "**Smoke test** description",
            },
            "multilineFieldsFormat": {},
            "url": "https://dev.azure.com/example-org/_apis/wit/workItems/102",
        },
    ],
}

_WORK_ITEM_SINGLE_SMOKE_RESPONSE = {
    "id": 97,
    "rev": 4,
    "fields": {
        "System.AreaPath": "main",
        "System.TeamProject": "main",
        "System.IterationPath": "main",
        "System.WorkItemType": "Task",
        "System.State": "Proposed",
        "System.Reason": "New",
        "System.AssignedTo": _SMOKE_AUTHOR,
        "System.CreatedDate": "2026-06-02T04:13:13.043Z",
        "System.CreatedBy": _SMOKE_AUTHOR,
        "System.ChangedDate": "2026-06-02T04:13:13.433Z",
        "System.ChangedBy": _SMOKE_AUTHOR,
        "System.CommentCount": 1,
        "System.Title": "[smoke-test] work-item-title (updated)",
        "Microsoft.VSTS.Common.Priority": 2,
        "System.Description": "Auto-created by smoke_test.py",
    },
    "multilineFieldsFormat": {"System.Description": "html"},
    "relations": [
        {
            "rel": "AttachedFile",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/attachments/bcf74d7a-5ada-4121-afd2-b7a48d9fe5b9"
            ),
            "attributes": {
                "authorizedDate": "2026-06-02T04:13:13.433Z",
                "id": 31732840,
                "resourceSize": 35,
                "comment": "smoke_test.txt",
                "name": "smoke_test.txt",
            },
        }
    ],
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/workItems/97"
            )
        }
    },
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/wit/workItems/97"
    ),
}

_WORK_ITEM_COMMENTS_SMOKE_RESPONSE = {
    "totalCount": 1,
    "count": 1,
    "comments": [
        {
            "mentions": [],
            "workItemId": 97,
            "id": 24884249,
            "version": 1,
            "text": "<p>pyado smoke test comment</p>",
            "createdBy": _SMOKE_AUTHOR,
            "createdDate": "2026-06-02T04:13:13.227Z",
            "modifiedBy": _SMOKE_AUTHOR,
            "modifiedDate": "2026-06-02T04:13:13.227Z",
            "format": "html",
            "renderedText": "",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/workItems/97/comments/24884249"
            ),
        }
    ],
}

_SPRINT_ITERATIONS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": "9c9cea0c-2ca1-4789-a091-250e8fe46024",
            "name": "Iteration 0",
            "path": "main\\Iteration 0",
            "attributes": {
                "startDate": "2023-01-01T00:00:00Z",
                "finishDate": "2023-02-25T00:00:00Z",
                "timeFrame": "current",
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/d64a3ce0-30a1-46d5-93ed-748bb80e3b0d/_apis/work/teamsettings"
                "/iterations/9c9cea0c-2ca1-4789-a091-250e8fe46024"
            ),
        }
    ],
}


class TestSmokePostWiql:
    """post_wiql parses real WIQL response shapes."""

    @staticmethod
    def test_parses_thirteen_work_item_refs(api_call: ApiCall) -> None:
        """Returns all 13 work item refs from a real WIQL response."""
        mock_response = _make_mock_response(_WIQL_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems")
        assert len(result) == 13
        assert all(isinstance(ref, WorkItemRef) for ref in result)

    @staticmethod
    def test_work_item_ids_in_descending_order(api_call: ApiCall) -> None:
        """Work item IDs match the order returned by the real WIQL response."""
        mock_response = _make_mock_response(_WIQL_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems")
        ids = [ref.id for ref in result]
        assert ids == [105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93]


class TestSmokeIterWorkItemDetails:
    """iter_work_item_details parses real work item batch response shapes."""

    @staticmethod
    def test_parses_work_items_with_nested_assigned_to(api_call: ApiCall) -> None:
        """Work items with a nested identity in System.AssignedTo parse correctly."""
        mock_response = _make_mock_response(_WORK_ITEMS_BATCH_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_details(api_call, [101, 102]))
        assert len(result) == 2
        assert all(isinstance(item, WorkItemInfo) for item in result)
        assert result[0].id == 101
        assert result[1].id == 102

    @staticmethod
    def test_system_id_accessible_in_fields(api_call: ApiCall) -> None:
        """System.Id field value (integer) is accessible in the fields dict."""
        mock_response = _make_mock_response(_WORK_ITEMS_BATCH_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_details(api_call, [101, 102]))
        assert result[0].fields["System.Id"] == 101


class TestSmokeGetWorkItem:
    """get_work_item parses a real single work item response shape."""

    @staticmethod
    def test_parses_work_item_with_relations_and_multiline_format(
        api_call: ApiCall,
    ) -> None:
        """Work item with relations list and multilineFieldsFormat dict parses ok."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assert isinstance(result, WorkItemInfo)
        assert result.id == 97

    @staticmethod
    def test_relations_list_parsed(api_call: ApiCall) -> None:
        """Relations list with AttachedFile entry is accessible."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assert result.relations is not None
        assert len(result.relations) == 1
        assert result.relations[0].rel == "AttachedFile"

    @staticmethod
    def test_fields_with_nested_identity_object_parsed(api_call: ApiCall) -> None:
        """System.AssignedTo nested identity dict in fields is preserved as-is."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assigned_to = result.fields["System.AssignedTo"]
        assert isinstance(assigned_to, dict)
        assert assigned_to["displayName"] == "Test User"


class TestSmokeIterWorkItemComments:
    """iter_work_item_comments parses real work item comment response shapes."""

    @staticmethod
    def test_parses_comment_with_html_format_and_rendered_text(
        api_call: ApiCall,
    ) -> None:
        """Comment with format='html' and renderedText fields parses without error."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_COMMENTS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_comments(work_item_api_call))
        assert len(result) == 1
        assert isinstance(result[0], WorkItemComment)
        assert result[0].text == "<p>pyado smoke test comment</p>"

    @staticmethod
    def test_comment_id_parsed(api_call: ApiCall) -> None:
        """The large integer comment ID is parsed correctly."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_COMMENTS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_comments(work_item_api_call))
        assert result[0].id == 24884249


class TestSmokeIterSprintIterations:
    """iter_sprint_iterations parses real sprint iteration response shapes."""

    @staticmethod
    def test_parses_iteration_with_backslash_path(api_call: ApiCall) -> None:
        """Sprint iteration with a backslash-delimited path parses correctly."""
        mock_response = _make_mock_response(_SPRINT_ITERATIONS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], SprintIterationInfo)
        assert result[0].name == "Iteration 0"
        assert result[0].path == "main\\Iteration 0"

    @staticmethod
    def test_sprint_attributes_parsed(api_call: ApiCall) -> None:
        """Sprint attributes (startDate, finishDate, timeFrame) are accessible."""
        mock_response = _make_mock_response(_SPRINT_ITERATIONS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        sprint = result[0]
        assert sprint.attributes.timeframe == "current"
        assert sprint.attributes.start_date is not None


class TestListSprintIterations:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.work_item.iter_sprint_iterations", return_value=iter([])
        ) as m:
            result = list_sprint_iterations(api_call)
        assert result == []
        m.assert_called_once_with(api_call, timeframe_filter=None)


class TestListWorkItemComments:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.work_item.iter_work_item_comments", return_value=iter([])
        ) as m:
            result = list_work_item_comments(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListWorkItemRevisions:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.work_item.iter_work_item_revisions", return_value=iter([])
        ) as m:
            result = list_work_item_revisions(api_call)
        assert result == []
        m.assert_called_once_with(api_call)
