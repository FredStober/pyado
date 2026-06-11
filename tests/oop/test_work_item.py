"""Tests for pyado.oop.boards._work_item — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Annotated, Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.oop import Project, WorkItem
from pyado.oop.boards._work_item import (
    CustomWorkItemBase,
    WorkItemFieldMap,
    WorkItemLink,
    add_work_item_attachment,
    add_work_item_link,
    add_work_item_tag,
    create_work_item,
    get_work_item_tags,
    iter_work_item_details,
    query_work_items,
    remove_work_item_link,
    remove_work_item_tag,
    sync_work_item_tags,
    update_work_item,
)
from pyado.raw import (
    ApiCall,
    TextFormat,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemExpand,
    WorkItemInfo,
    WorkItemRelation,
    WorkItemRelationType,
    get_work_item_api_call,
)
from tests.conftest import NOW_ISO, _make_mock_response
from tests.oop.conftest import (
    ORG_URL,
    _api_call,
    _make_build,
    _make_pr,
    _make_project,
    _make_repo,
    _make_service,
    _make_wi,
    _project_info,
    _work_item_info,
)

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


def make_single_work_item_dict(work_item_id: int = 42) -> dict[str, Any]:
    """Create a minimal valid work item dict for single-fetch tests.

    Returns:
        A dict with required WorkItemInfo fields populated.
    """
    return {"id": work_item_id, "fields": {"System.Title": "Test item"}}


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

    @staticmethod
    def test_creates_work_item_with_multiline_fields_format(api_call: ApiCall) -> None:
        """multiline_fields_format adds format patches to the JSON payload."""
        response_data = {"id": 102, "fields": {}}
        mock_response = _make_mock_response(response_data)
        fields = {
            "System.WorkItemType": "Task",
            "System.Description": "<p>text</p>",
        }
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_work_item(
                api_call,
                fields,
                multiline_fields_format={"System.Description": TextFormat.HTML},
            )
        sent_json = mock_req.call_args.kwargs.get("json") or []
        format_patches = [
            p for p in sent_json if "multilineFieldsFormat" in p.get("path", "")
        ]
        assert len(format_patches) == 1


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
                multiline_fields_format={"System.Description": TextFormat.HTML},
            )
        sent_json = mock_req.call_args.kwargs.get("json") or []
        format_patches = [
            p for p in sent_json if "multilineFieldsFormat" in p.get("path", "")
        ]
        assert len(format_patches) == 1
        assert format_patches[0]["value"] == "html"


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
        first_call = mock_req.call_args_list[0]
        assert first_call.args[0] == "POST"
        assert first_call.kwargs.get("data") == b"report content"
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


class TestSyncWorkItemTags:
    """Tests for sync_work_item_tags."""

    @staticmethod
    def test_skips_patch_when_already_in_sync(work_item_api_call: ApiCall) -> None:
        """Does not patch the work item when tags already match desired set."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "alpha; beta"
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            sync_work_item_tags(work_item_api_call, {"alpha", "beta"})
        assert mock_req.call_count == 1

    @staticmethod
    def test_patches_once_when_tags_differ(work_item_api_call: ApiCall) -> None:
        """Issues exactly one patch when desired set differs from current."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "old-tag"
        get_response = _make_mock_response(response_data)
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session,
            "request",
            side_effect=[get_response, patch_response],
        ) as mock_req:
            sync_work_item_tags(work_item_api_call, {"new-tag"})
        assert mock_req.call_count == 2
        patch_call = mock_req.call_args_list[1]
        sent_json = patch_call.kwargs.get("json") or []
        tag_patches = [p for p in sent_json if p.get("path") == "/fields/System.Tags"]
        assert len(tag_patches) == 1
        assert "new-tag" in tag_patches[0]["value"]
        assert "old-tag" not in tag_patches[0]["value"]

    @staticmethod
    def test_patches_once_for_combined_add_and_remove(
        work_item_api_call: ApiCall,
    ) -> None:
        """One patch covers simultaneous additions and removals."""
        response_data = make_single_work_item_dict()
        response_data["fields"]["System.Tags"] = "keep; remove"
        get_response = _make_mock_response(response_data)
        patch_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session,
            "request",
            side_effect=[get_response, patch_response],
        ) as mock_req:
            sync_work_item_tags(work_item_api_call, {"keep", "added"})
        assert mock_req.call_count == 2


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


class TestRemoveWorkItemLink:
    """Tests for remove_work_item_link."""

    @staticmethod
    def test_sends_remove_patch_at_index(work_item_api_call: ApiCall) -> None:
        """Sends a PATCH with a 'remove' op at /relations/{index}."""
        mock_response = _make_mock_response(make_single_work_item_dict())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = remove_work_item_link(work_item_api_call, 2)
        assert isinstance(result, WorkItemInfo)
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["op"] == "remove"
        assert sent_json[0]["path"] == "/relations/2"


# ---------------------------------------------------------------------------
# OOP WorkItem tests
# ---------------------------------------------------------------------------


class TestWorkItem:
    def test_id(self) -> None:
        assert _make_wi(55).id == 55

    def test_info_returns_work_item_info(self) -> None:
        wi = _make_wi()
        assert wi.info is wi._info

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        wi = WorkItem(_make_project(), api, _work_item_info())
        assert wi.api_call is api

    def test_title(self) -> None:
        assert _make_wi().title == "My WI"

    def test_title_absent_returns_none(self) -> None:
        proj = _make_project()
        api = _api_call()
        wi = WorkItem(proj, api, WorkItemInfo.model_validate({"id": 1, "fields": {}}))
        assert wi.title is None

    def test_get_field_returns_value(self) -> None:
        assert _make_wi().get_field("System.Title") == "My WI"

    def test_get_field_returns_none_for_absent(self) -> None:
        assert _make_wi().get_field("System.Missing") is None

    def test_project_reference(self) -> None:
        proj = _make_project()
        wi = WorkItem(proj, _api_call(), _work_item_info())
        assert wi.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        wi = WorkItem(proj, _api_call(), _work_item_info())
        assert wi.org is svc.org

    def test_refresh_refetches(self) -> None:
        wi = _make_wi()
        with patch("pyado.oop.boards.work_item.raw.get_work_item") as mock_get:
            mock_get.return_value = _work_item_info()
            wi.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = wi.info
        mock_get.assert_called_once()

    def test_update_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.update_work_item"
        ) as mock_update:
            mock_update.return_value = _work_item_info()
            _make_wi().update({"System.Title": "New"})
        mock_update.assert_called_once()

    def test_add_tag_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.add_work_item_tag"
        ) as mock_tag:
            _make_wi().add_tag("tag-a")
        mock_tag.assert_called_once()

    def test_add_comment_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item.raw.post_work_item_comment"
        ) as mock_comment:
            mock_comment.return_value = MagicMock()
            _make_wi().add_comment("hello")
        mock_comment.assert_called_once()

    def test_iter_tags_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.get_work_item_tags"
        ) as mock_tags:
            mock_tags.return_value = ["tag-a", "tag-b"]
            result = list(_make_wi().iter_tags())
        assert result == ["tag-a", "tag-b"]

    def test_remove_tag_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.remove_work_item_tag"
        ) as mock_remove:
            _make_wi().remove_tag("tag-a")
        mock_remove.assert_called_once()

    def test_sync_tags_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.sync_work_item_tags"
        ) as mock_sync:
            _make_wi().sync_tags({"tag-a", "tag-b"})
        mock_sync.assert_called_once()

    def test_iter_comments_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item.raw.iter_work_item_comments"
        ) as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_wi().iter_comments())
        assert len(result) == 1

    def test_add_attachment_delegates(self) -> None:
        with patch(
            "pyado.oop.boards.work_item._work_item.add_work_item_attachment"
        ) as mock_attach:
            mock_attach.return_value = MagicMock()
            _make_wi().add_attachment("report.txt", b"data")
        mock_attach.assert_called_once()

    def test_add_link_delegates(self) -> None:
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.WorkItemLink.wi_link"
            ) as mock_link,
            patch(
                "pyado.oop.boards.work_item._work_item.add_work_item_link"
            ) as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().add_link(_make_wi(20), WorkItemRelationType.CHILD)
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_pull_request_delegates(self) -> None:
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.WorkItemLink.pull_request"
            ) as mock_link,
            patch(
                "pyado.oop.boards.work_item._work_item.add_work_item_link"
            ) as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_pull_request(_make_pr())
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_build_delegates(self) -> None:
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.WorkItemLink.build"
            ) as mock_link,
            patch(
                "pyado.oop.boards.work_item._work_item.add_work_item_link"
            ) as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_build(_make_build())
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_link_commit_delegates(self) -> None:
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.WorkItemLink.commit"
            ) as mock_link,
            patch(
                "pyado.oop.boards.work_item._work_item.add_work_item_link"
            ) as mock_add,
        ):
            mock_link.return_value = MagicMock()
            _make_wi().link_commit(_make_repo(), "abc123")
        mock_link.assert_called_once()
        mock_add.assert_called_once()

    def test_iter_linked_work_items_yields_wi_relations(self) -> None:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel="System.LinkTypes.Hierarchy-Forward",
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/20",
            ),
            WorkItemRelation(
                rel="ArtifactLink",
                url="vstfs:///Git/PullRequestId/abc",
            ),
        ]
        linked_info = _work_item_info(20)
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.iter_work_item_details"
            ) as mock_iter,
            patch("pyado.oop.boards.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([linked_info])
            mock_call.return_value = _api_call()
            result = list(wi.iter_linked_work_items())
        assert len(result) == 1
        assert result[0].id == 20
        ids_passed = mock_iter.call_args.args[1]
        assert ids_passed == [20]

    def test_iter_linked_work_items_filters_by_rel_type(self) -> None:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/30",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.RELATED,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/40",
            ),
        ]
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.iter_work_item_details"
            ) as mock_iter,
            patch("pyado.oop.boards.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_work_item_info(30)])
            mock_call.return_value = _api_call()
            result = list(wi.iter_linked_work_items(WorkItemRelationType.CHILD))
        assert len(result) == 1
        assert mock_iter.call_args.args[1] == [30]

    def test_get_parent_returns_none_when_no_parent(self) -> None:
        wi = _make_wi(10)
        assert wi._info is not None

        assert wi._info is not None

        wi._info.relations = []
        result = wi.get_parent()
        assert result is None

    def test_get_parent_returns_parent_work_item(self) -> None:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.PARENT,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/5",
            ),
        ]
        parent_info = _work_item_info(5)
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.iter_work_item_details"
            ) as mock_iter,
            patch("pyado.oop.boards.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([parent_info])
            mock_call.return_value = _api_call()
            parent = wi.get_parent()
        assert parent is not None
        assert parent.id == 5

    def test_iter_children_delegates_to_iter_linked(self) -> None:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/20",
            ),
        ]
        with (
            patch(
                "pyado.oop.boards.work_item._work_item.iter_work_item_details"
            ) as mock_iter,
            patch("pyado.oop.boards.work_item.raw.get_work_item_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_work_item_info(20)])
            mock_call.return_value = _api_call()
            result = list(wi.iter_children())
        assert len(result) == 1
        assert result[0].id == 20

    def test_delete_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        with patch("pyado.oop.boards.work_item.raw.delete_work_item") as mock_del:
            wi.delete()
        mock_del.assert_called_once_with(wi._api_call)

    def test_update_comment_returns_comment(self) -> None:
        wi = _make_wi(10)
        comment = WorkItemComment.model_validate(
            {
                "id": 3,
                "text": "Updated",
                "version": 2,
                "createdDate": NOW_ISO,
                "modifiedDate": NOW_ISO,
                "url": "https://dev.azure.com/org/proj/_apis/wit/workItems/10/comments/3",
            }
        )
        with patch(
            "pyado.oop.boards.work_item.raw.patch_work_item_comment"
        ) as mock_patch:
            mock_patch.return_value = comment
            result = wi.update_comment(3, "Updated")
        mock_patch.assert_called_once_with(wi._api_call, 3, "Updated")
        assert result is comment

    def test_remove_comment_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        with patch(
            "pyado.oop.boards.work_item.raw.delete_work_item_comment"
        ) as mock_del:
            wi.remove_comment(5)
        mock_del.assert_called_once_with(wi._api_call, 5)

    def test_state_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().state == "Active"

    def test_type_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().type == "Task"

    def test_assigned_to_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().assigned_to == {"displayName": "Alice"}

    def test_area_path_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().area_path == "proj\\Area"

    def test_iteration_path_returns_field_value(self) -> None:
        assert self._make_wi_with_fields().iteration_path == "proj\\Sprint 1"

    def _make_wi_with_fields(self) -> WorkItem:
        info = WorkItemInfo.model_validate(
            {
                "id": 10,
                "fields": {
                    "System.Title": "My WI",
                    "System.State": "Active",
                    "System.WorkItemType": "Task",
                    "System.AssignedTo": {"displayName": "Alice"},
                    "System.AreaPath": "proj\\Area",
                    "System.IterationPath": "proj\\Sprint 1",
                },
            }
        )
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/10")
        return WorkItem(proj, api_call, info)


# ---------------------------------------------------------------------------
# OOP WorkItemRelationMethods tests
# ---------------------------------------------------------------------------


class TestWorkItemRelationMethods:
    def _wi_with_relations(self) -> WorkItem:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.ARTIFACT_LINK,
                url="vstfs:///Git/PullRequestId/abc",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.ATTACHED_FILE,
                url="https://dev.azure.com/testorg/_apis/wit/attachments/guid",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/testorg/proj/_apis/wit/workItems/20",
            ),
        ]
        return wi

    def test_iter_relations_yields_all_when_no_filter(self) -> None:
        wi = self._wi_with_relations()
        result = list(wi.iter_relations())
        assert len(result) == 3

    def test_iter_relations_filters_by_type(self) -> None:
        wi = self._wi_with_relations()
        result = list(wi.iter_relations(WorkItemRelationType.CHILD))
        assert len(result) == 1
        assert result[0].rel == WorkItemRelationType.CHILD

    def test_iter_artifact_links_yields_artifact_links(self) -> None:
        wi = self._wi_with_relations()
        result = list(wi.iter_artifact_links())
        assert len(result) == 1
        assert result[0].rel == WorkItemRelationType.ARTIFACT_LINK

    def test_iter_attachments_yields_attachment_refs(self) -> None:
        wi = self._wi_with_relations()
        result = list(wi.iter_attachments())
        assert len(result) == 1
        assert result[0].id == "guid"

    def test_iter_relations_empty_when_no_relations(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        assert wi._info is not None

        wi._info.relations = []
        assert list(wi.iter_relations()) == []


# ---------------------------------------------------------------------------
# OOP WorkItemRefreshWithExpand tests
# ---------------------------------------------------------------------------


class TestWorkItemRefreshWithExpand:
    def test_refresh_with_expand_updates_stored_expand(self) -> None:
        wi = _make_wi()
        with patch("pyado.oop.boards.work_item.raw.get_work_item") as mock_get:
            mock_get.return_value = _work_item_info()
            wi.refresh(expand=WorkItemExpand.RELATIONS)
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = wi.info
        assert wi._expand == WorkItemExpand.RELATIONS
        assert mock_get.call_args.kwargs.get("expand") == WorkItemExpand.RELATIONS


# ---------------------------------------------------------------------------
# OOP WorkItemGetChildIds tests
# ---------------------------------------------------------------------------


class TestWorkItemGetChildIds:
    def test_returns_child_work_item_ids(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/42",
            ),
        ]
        result = wi.list_child_ids()
        assert result == [42]

    def test_returns_empty_list_when_no_children(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        assert wi._info is not None

        wi._info.relations = []
        assert wi.list_child_ids() == []


# ---------------------------------------------------------------------------
# OOP WorkItemGetParentId tests
# ---------------------------------------------------------------------------


class TestWorkItemGetParentId:
    def test_returns_parent_id_when_parent_exists(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.PARENT,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/5",
            ),
        ]
        assert wi.get_parent_id() == 5

    def test_returns_none_when_no_parent(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        wi._info.relations = []
        assert wi.get_parent_id() is None

    def test_ignores_non_parent_relations(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/20",
            ),
        ]
        assert wi.get_parent_id() is None


# ---------------------------------------------------------------------------
# OOP WorkItemRemoveLink tests
# ---------------------------------------------------------------------------


class TestWorkItemRemoveLink:
    def _wi_with_relations(self) -> WorkItem:
        wi = _make_wi(10)
        assert wi._info is not None

        wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/20",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.RELATED,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/30",
            ),
        ]
        return wi

    def test_remove_link_delegates_correct_index(self) -> None:
        wi = self._wi_with_relations()
        assert wi._info is not None

        target = wi._info.relations[1]
        with patch(
            "pyado.oop.boards.work_item._work_item.remove_work_item_link"
        ) as mock_remove:
            mock_remove.return_value = _work_item_info()
            wi.remove_link(target)
        mock_remove.assert_called_once_with(wi.api_call, 1)

    def test_remove_link_updates_info(self) -> None:
        wi = self._wi_with_relations()
        assert wi._info is not None

        target = wi._info.relations[0]
        new_info = _work_item_info(99)
        with patch(
            "pyado.oop.boards.work_item._work_item.remove_work_item_link"
        ) as mock_remove:
            mock_remove.return_value = new_info
            wi.remove_link(target)
        assert wi._info is new_info

    def test_remove_link_raises_when_not_found(self) -> None:
        wi = _make_wi()
        assert wi._info is not None

        assert wi._info is not None

        wi._info.relations = []
        missing = WorkItemRelation(
            rel=WorkItemRelationType.CHILD,
            url="https://dev.azure.com/org/proj/_apis/wit/workItems/99",
        )
        with pytest.raises(ValueError, match="Relation not found"):
            wi.remove_link(missing)


# ---------------------------------------------------------------------------
# OOP WorkItemMove tests
# ---------------------------------------------------------------------------


class TestWorkItemMove:
    def test_move_iteration_path(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.update_work_item"
        ) as mock_update:
            mock_update.return_value = _work_item_info()
            wi.move(iteration_path="Proj\\Sprint 2")
        fields = mock_update.call_args.args[1]
        assert fields.get("System.IterationPath") == "Proj\\Sprint 2"
        assert "System.AreaPath" not in fields

    def test_move_area_path(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.update_work_item"
        ) as mock_update:
            mock_update.return_value = _work_item_info()
            wi.move(area_path="Proj\\Team A")
        fields = mock_update.call_args.args[1]
        assert fields.get("System.AreaPath") == "Proj\\Team A"

    def test_move_both_paths(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.update_work_item"
        ) as mock_update:
            mock_update.return_value = _work_item_info()
            wi.move(iteration_path="Proj\\Sprint 2", area_path="Proj\\Team A")
        fields = mock_update.call_args.args[1]
        assert fields.get("System.IterationPath") == "Proj\\Sprint 2"
        assert fields.get("System.AreaPath") == "Proj\\Team A"

    def test_move_noop_when_no_args(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.update_work_item"
        ) as mock_update:
            wi.move()
        mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# OOP WorkItemRemoveWorkItemLinks tests
# ---------------------------------------------------------------------------


class TestWorkItemRemoveWorkItemLinks:
    def _wi_with_two_relations_to_other(self) -> tuple[WorkItem, WorkItem]:
        """Return (self_wi, other_wi) where self has two relations pointing at other."""
        self_wi = _make_wi(10)
        other_wi = _make_wi(20)
        assert self_wi._info is not None

        self_wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.PARENT,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/20",
            ),
            WorkItemRelation(
                rel=WorkItemRelationType.CHILD,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/20",
            ),
        ]
        return self_wi, other_wi

    def test_calls_remove_link_for_each_matching_relation(self) -> None:
        self_wi, other_wi = self._wi_with_two_relations_to_other()
        with patch.object(self_wi, "remove_link") as mock_remove:
            self_wi.remove_work_item_links(other_wi)
        assert mock_remove.call_count == 2

    def test_skips_non_matching_relations(self) -> None:
        self_wi = _make_wi(10)
        other_wi = _make_wi(99)
        assert self_wi._info is not None

        self_wi._info.relations = [
            WorkItemRelation(
                rel=WorkItemRelationType.RELATED,
                url="https://dev.azure.com/org/proj/_apis/wit/workItems/20",
            ),
        ]
        with patch.object(self_wi, "remove_link") as mock_remove:
            self_wi.remove_work_item_links(other_wi)
        mock_remove.assert_not_called()

    def test_does_nothing_when_no_relations(self) -> None:
        self_wi = _make_wi(10)
        assert self_wi._info is not None

        assert self_wi._info is not None

        self_wi._info.relations = []
        other_wi = _make_wi(20)
        with patch.object(self_wi, "remove_link") as mock_remove:
            self_wi.remove_work_item_links(other_wi)
        mock_remove.assert_not_called()


# ---------------------------------------------------------------------------
# OOP WorkItemCreateChild tests
# ---------------------------------------------------------------------------


class TestWorkItemCreateChild:
    def test_calls_create_work_item_on_project(self) -> None:
        self_wi = _make_wi(10)
        child_info = _work_item_info(20)
        with (
            patch(
                "pyado.oop.boards._work_item.create_work_item",
                return_value=child_info,
            ) as mock_create,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call",
                return_value=_api_call(),
            ),
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item",
                return_value=child_info,
            ),
            patch.object(WorkItem, "add_link"),
        ):
            result = self_wi.create_child("Task", "My Task")
        assert result.id == 20
        all_fields = mock_create.call_args.args[1]
        assert all_fields["System.WorkItemType"] == "Task"
        assert all_fields["System.Title"] == "My Task"

    def test_calls_add_link_with_parent_relation(self) -> None:
        self_wi = _make_wi(10)
        child_info = _work_item_info(20)
        with (
            patch(
                "pyado.oop.boards._work_item.create_work_item",
                return_value=child_info,
            ),
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call",
                return_value=_api_call(),
            ),
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item",
                return_value=child_info,
            ),
            patch.object(WorkItem, "add_link") as mock_add_link,
        ):
            self_wi.create_child("Task", "My Task")
        mock_add_link.assert_called_once_with(self_wi, WorkItemRelationType.PARENT)

    def test_forwards_extra_fields(self) -> None:
        self_wi = _make_wi(10)
        child_info = _work_item_info(20)
        with (
            patch(
                "pyado.oop.boards._work_item.create_work_item",
                return_value=child_info,
            ) as mock_create,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call",
                return_value=_api_call(),
            ),
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item",
                return_value=child_info,
            ),
            patch.object(WorkItem, "add_link"),
        ):
            self_wi.create_child("Task", "My Task", {"System.Description": "details"})
        all_fields = mock_create.call_args.args[1]
        assert all_fields.get("System.Description") == "details"

    def test_forwards_multiline_fields_format(self) -> None:
        self_wi = _make_wi(10)
        child_info = _work_item_info(20)
        fmt = {"System.Description": TextFormat.MARKDOWN}
        with (
            patch(
                "pyado.oop.boards._work_item.create_work_item",
                return_value=child_info,
            ) as mock_create,
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item_api_call",
                return_value=_api_call(),
            ),
            patch(
                "pyado.oop.boards.project_boards.raw.get_work_item",
                return_value=child_info,
            ),
            patch.object(WorkItem, "add_link"),
        ):
            self_wi.create_child("Task", "t", multiline_fields_format=fmt)
        assert mock_create.call_args.kwargs.get("multiline_fields_format") is fmt


# ---------------------------------------------------------------------------
# OOP WorkItemIterRevisions tests
# ---------------------------------------------------------------------------


class TestWorkItemIterRevisions:
    def test_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        rev1 = _work_item_info(10)
        with patch(
            "pyado.oop.boards.work_item.raw.iter_work_item_revisions"
        ) as mock_iter:
            mock_iter.return_value = iter([rev1])
            result = list(wi.iter_revisions())
        assert len(result) == 1
        assert result[0] is rev1
        mock_iter.assert_called_once_with(wi.api_call)

    def test_yields_empty_when_no_revisions(self) -> None:
        wi = _make_wi(10)
        with patch(
            "pyado.oop.boards.work_item.raw.iter_work_item_revisions"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(wi.iter_revisions())
        assert result == []


# ---------------------------------------------------------------------------
# OOP WorkItemGetAttachmentBytes tests
# ---------------------------------------------------------------------------


class TestWorkItemDownloadAttachment:
    def test_delegates_to_raw(self) -> None:
        wi = _make_wi(10)
        ref = WorkItemAttachmentRef.model_validate(
            {
                "id": "aaaaaaaa-0000-0000-0000-000000000099",
                "url": "https://dev.azure.com/testorg/_apis/wit/attachments/aaaaaaaa",
            }
        )
        with patch(
            "pyado.oop.boards.work_item.raw.get_work_item_attachment_bytes"
        ) as mock_dl:
            mock_dl.return_value = b"file content"
            result = wi.download_attachment(ref)
        assert result == b"file content"
        mock_dl.assert_called_once_with(wi._project.api_call, ref.id)


class TestWorkItemListMethods:
    def test_list_tags_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_tags", return_value=iter([])):
            assert wi.list_tags() == []

    def test_list_comments_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_comments", return_value=iter([])):
            assert wi.list_comments() == []

    def test_list_relations_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_relations", return_value=iter([])):
            assert wi.list_relations() == []

    def test_list_artifact_links_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_artifact_links", return_value=iter([])):
            assert wi.list_artifact_links() == []

    def test_list_attachments_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_attachments", return_value=iter([])):
            assert wi.list_attachments() == []

    def test_list_revisions_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_revisions", return_value=iter([])):
            assert wi.list_revisions() == []

    def test_list_linked_work_items_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_linked_work_items", return_value=iter([])):
            assert wi.list_linked_work_items() == []

    def test_list_children_delegates(self) -> None:
        wi = _make_wi()
        with patch.object(wi, "iter_children", return_value=iter([])):
            assert wi.list_children() == []


class TestWorkItemSyncTags:
    def test_sync_tags_delegates_to_helper(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.sync_work_item_tags"
        ) as mock_sync:
            wi.sync_tags({"alpha", "beta"})
        mock_sync.assert_called_once_with(wi._api_call, {"alpha", "beta"})

    def test_sync_tags_passes_empty_set(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item._work_item.sync_work_item_tags"
        ) as mock_sync:
            wi.sync_tags(set())
        mock_sync.assert_called_once_with(wi._api_call, set())


class TestWorkItemRestore:
    def test_restore_calls_raw(self) -> None:
        wi = _make_wi()
        with patch(
            "pyado.oop.boards.work_item.raw.patch_recycle_bin_work_item"
        ) as mock_restore:
            wi.restore()
        mock_restore.assert_called_once()

    def test_restore_passes_project_api_call_and_id(self) -> None:
        wi = _make_wi()
        wi_id = wi.id
        with patch(
            "pyado.oop.boards.work_item.raw.patch_recycle_bin_work_item"
        ) as mock_restore:
            wi.restore()
        args = mock_restore.call_args.args
        assert args[0] == wi._project.api_call
        assert args[1] == wi_id

    def test_restore_calls_refresh(self) -> None:
        wi = _make_wi()
        with (
            patch("pyado.oop.boards.work_item.raw.patch_recycle_bin_work_item"),
            patch.object(wi, "refresh") as mock_refresh,
        ):
            wi.restore()
        mock_refresh.assert_called_once()
