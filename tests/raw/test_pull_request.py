"""Tests for pyado.pull_request module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any, ClassVar
from unittest.mock import patch
from uuid import uuid4

import requests
from pydantic.networks import AnyUrl

from pyado.raw import (
    ApiCall,
    GitChangeFlag,
    PullRequestCompletionOptions,
    PullRequestCreateRequest,
    PullRequestIterationChange,
    PullRequestIterationRecord,
    PullRequestListItem,
    PullRequestResponse,
    PullRequestSearchCriteria,
    PullRequestStatus,
    PullRequestStatusContext,
    PullRequestStatusInfo,
    PullRequestStatusRequest,
    PullRequestStatusState,
    PullRequestThreadCommentRequest,
    PullRequestThreadCommentResponse,
    PullRequestThreadCommentType,
    PullRequestThreadRequest,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestUpdateRequest,
    delete_pull_request_label,
    delete_pull_request_reviewer,
    get_pull_request_api_call,
    get_pull_request_details,
    get_pull_request_iteration_changes,
    get_pull_request_reviewers,
    get_pull_request_thread,
    iter_pull_request_commits,
    iter_pull_request_iterations,
    iter_pull_request_statuses,
    iter_pull_request_threads,
    iter_pull_requests,
    list_pull_request_commits,
    list_pull_request_iterations,
    list_pull_request_statuses,
    list_pull_request_threads,
    list_pull_request_work_item_ids,
    list_pull_requests,
    patch_pull_request,
    patch_pull_request_thread,
    post_pull_request,
    post_pull_request_label,
    post_pull_request_new_thread,
    post_pull_request_status,
    post_pull_request_thread_comment,
)
from tests.conftest import _make_mock_response

REPO_ID = uuid4()
PR_ID = 7

_PATCH_PR_RESPONSE: dict[str, Any] = {
    "pullRequestId": PR_ID,
    "repository": {"id": str(REPO_ID)},
    "status": "active",
    "url": "https://example.com",
    "title": "Updated title",
    "sourceRefName": "refs/heads/feature",
    "targetRefName": "refs/heads/main",
}


class TestGetPrApiCall:
    """Tests for get_pull_request_api_call."""

    @staticmethod
    def test_url_contains_pr_path_segments(api_call: ApiCall) -> None:
        """Result URL contains git/repositories/<repo_id>/pullRequests/<pr_id>."""
        result = get_pull_request_api_call(api_call, REPO_ID, PR_ID)
        url_str = result.url.unicode_string()
        assert "git/repositories" in url_str
        assert "pullRequests" in url_str


class TestCreatePrComments:
    """Tests for post_pr_thread."""

    @staticmethod
    def test_posts_comments_to_threads_endpoint(api_call: ApiCall) -> None:
        """Sends a POST to the threads endpoint with the comment payload."""
        comment = PullRequestThreadCommentRequest(
            comment_type=PullRequestThreadCommentType.TEXT,
            parent_comment_id=0,
            content="Review comment",
        )
        holder = PullRequestThreadRequest(status="active", comments=[comment])
        mock_response = _make_mock_response({})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request_new_thread(api_call, holder)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json["status"] == "active"
        assert len(sent_json["comments"]) == 1


class TestCreatePrStatusFlag:
    """Tests for post_pull_request_status."""

    @staticmethod
    def test_posts_status_to_statuses_endpoint(api_call: ApiCall) -> None:
        """Sends a POST to the statuses endpoint with the status payload."""
        status = PullRequestStatusRequest(
            context=PullRequestStatusContext(name="my-check", genre="ci"),
            description="Build passed",
            iteration_id=2,
            state="succeeded",
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request_status(api_call, status)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json["state"] == "succeeded"
        assert sent_json["iterationId"] == 2

    @staticmethod
    def test_excludes_none_fields_from_payload(api_call: ApiCall) -> None:
        """None fields (like targetUrl) are omitted from the posted payload."""
        status = PullRequestStatusRequest(
            context=PullRequestStatusContext(name="check", genre="test"),
            iteration_id=1,
            state="pending",
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request_status(api_call, status)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "targetUrl" not in sent_json

    @staticmethod
    def test_includes_target_url_when_provided(api_call: ApiCall) -> None:
        """TargetUrl is included in the payload when not None."""
        status = PullRequestStatusRequest(
            context=PullRequestStatusContext(name="check", genre="test"),
            iteration_id=1,
            state="succeeded",
            target_url=AnyUrl("https://ci.example.com/builds/42"),
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request_status(api_call, status)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "targetUrl" in sent_json


class TestPullRequestThreadCommentRequest:
    """Tests for PullRequestThreadCommentRequest model."""

    @staticmethod
    def test_instantiation_with_aliases() -> None:
        """Model can be instantiated using camelCase alias names."""
        comment = PullRequestThreadCommentRequest(
            comment_type=PullRequestThreadCommentType.CODE_CHANGE,
            parent_comment_id=0,
            content="Hello",
        )
        assert comment.comment_type == PullRequestThreadCommentType.CODE_CHANGE
        assert comment.parent_comment_id == 0


class TestIterPrs:
    """Tests for iter_pull_requests."""

    @staticmethod
    def test_yields_pr_list_items(api_call: ApiCall) -> None:
        """Yields PullRequestListItem objects from the API response."""
        pr_data = {"pullRequestId": 42, "repository": {"id": str(REPO_ID)}}
        mock_response = _make_mock_response({"value": [pr_data]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_requests(api_call))
        assert len(result) == 1
        assert result[0].pr_id == 42

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no PRs."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_requests(api_call))
        assert result == []

    @staticmethod
    def test_search_criteria_added_as_params(api_call: ApiCall) -> None:
        """Search criteria are forwarded as searchCriteria.* query parameters."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_pull_requests(
                    api_call,
                    search_criteria=PullRequestSearchCriteria(
                        status=PullRequestStatus.ACTIVE
                    ),
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "searchCriteria.status" in params
        assert params["searchCriteria.status"] == "active"

    @staticmethod
    def test_expand_parameter_forwarded_as_dollar_expand(api_call: ApiCall) -> None:
        """When expand is given, $expand query parameter is included."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pull_requests(api_call, expand="labels"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("$expand") == "labels"

    @staticmethod
    def test_paginates_when_first_page_is_full(api_call: ApiCall) -> None:
        """Fetches a second page when the first response has exactly 100 PRs."""
        pr_template = {"repository": {"id": str(REPO_ID)}}
        first_page = {
            "value": [{"pullRequestId": idx, **pr_template} for idx in range(100)]
        }
        second_page = {"value": [{"pullRequestId": 100, **pr_template}]}
        mock_first = _make_mock_response(first_page)
        mock_second = _make_mock_response(second_page)
        with patch.object(
            requests.Session, "request", side_effect=[mock_first, mock_second]
        ):
            result = list(iter_pull_requests(api_call))
        assert len(result) == 101


class TestAddPrLabel:
    """Tests for post_pull_request_label."""

    @staticmethod
    def test_posts_label_name(api_call: ApiCall) -> None:
        """Posts the label name to the labels endpoint."""
        mock_response = _make_mock_response({"name": "my-label"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request_label(api_call, "my-label")
        call = mock_req.call_args
        assert call.args[0] == "POST"
        assert call.kwargs.get("json") == {"name": "my-label"}


class TestDeletePrLabel:
    """Tests for delete_pull_request_label."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request for the given label name."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_pull_request_label(api_call, "stale")
        assert mock_req.call_args.args[0] == "DELETE"


class TestIterPrThreads:
    """Tests for iter_pull_request_threads."""

    @staticmethod
    def test_yields_thread_objects(api_call: ApiCall) -> None:
        """Yields PullRequestThreadResponse objects from the API response."""
        thread_data = {
            "id": 1,
            "status": "active",
            "comments": [
                {
                    "id": 10,
                    "content": "Review note",
                    "commentType": "text",
                    "parentCommentId": 0,
                }
            ],
        }
        mock_response = _make_mock_response({"value": [thread_data]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_threads(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestThreadResponse)
        assert result[0].id == 1

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty thread list yields no results."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_threads(api_call))
        assert result == []


class TestReplyToPrThread:
    """Tests for post_pull_request_thread_comment."""

    @staticmethod
    def test_posts_reply_to_thread(api_call: ApiCall) -> None:
        """Posts a reply comment to the specified thread."""
        comment_data = {
            "id": 2,
            "content": "Reply text",
            "commentType": "text",
            "parentCommentId": 1,
        }
        mock_response = _make_mock_response(comment_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = post_pull_request_thread_comment(
                api_call,
                7,
                PullRequestThreadCommentRequest(
                    comment_type=PullRequestThreadCommentType.TEXT,
                    parent_comment_id=1,
                    content="Reply text",
                ),
            )
        assert isinstance(result, PullRequestThreadCommentResponse)
        assert result.content == "Reply text"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["parentCommentId"] == 1


class TestUpdatePr:
    """Tests for patch_pull_request."""

    @staticmethod
    def test_patches_pr_fields(api_call: ApiCall) -> None:
        """Sends PATCH request with given fields, returns PullRequestResponse."""
        mock_response = _make_mock_response(_PATCH_PR_RESPONSE)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = patch_pull_request(
                api_call, PullRequestUpdateRequest(title="Updated title")
            )
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["title"] == "Updated title"
        assert isinstance(result, PullRequestResponse)
        assert result.pr_id == PR_ID


_CREATE_PR_REQUEST = PullRequestCreateRequest(
    title="New PR",
    source_ref_name="refs/heads/feature",
    target_ref_name="refs/heads/main",
    completion_options=PullRequestCompletionOptions(),
)


class TestPostPr:
    """Tests for post_pull_request."""

    @staticmethod
    def test_returns_pull_request_response(api_call: ApiCall) -> None:
        """Returns a PullRequestResponse parsed from the API POST response."""
        mock_response = _make_mock_response(_PATCH_PR_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_pull_request(api_call, _CREATE_PR_REQUEST)
        assert isinstance(result, PullRequestResponse)
        assert result.pr_id == PR_ID

    @staticmethod
    def test_sends_post_request(api_call: ApiCall) -> None:
        """Issues a POST request to the pullrequests endpoint."""
        mock_response = _make_mock_response(_PATCH_PR_RESPONSE)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            post_pull_request(api_call, _CREATE_PR_REQUEST)
        assert mock_req.call_args.args[0] == "POST"


class TestIterPrIterations:
    """Tests for iter_pull_request_iterations."""

    @staticmethod
    def test_yields_iteration_records(api_call: ApiCall) -> None:
        """Yields PullRequestIterationRecord objects from the API response."""
        iteration_data = {
            "id": 3,
            "sourceRefCommit": {"commitId": "abc123"},
            "targetRefCommit": {"commitId": "def456"},
        }
        mock_response = _make_mock_response({"value": [iteration_data]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestIterationRecord)
        assert result[0].id == 3
        assert result[0].source_ref_commit is not None
        assert result[0].source_ref_commit.commit_id == "abc123"

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty iteration list yields no results."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_iterations(api_call))
        assert result == []


class TestRemovePrReviewer:
    """Tests for delete_pull_request_reviewer."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request for the given reviewer ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_pull_request_reviewer(api_call, "reviewer-uuid")
        assert mock_req.call_args.args[0] == "DELETE"
        called_url: str = mock_req.call_args.kwargs.get("url") or ""
        assert "reviewer-uuid" in called_url


class TestGetPrReviewers:
    """Tests for get_pull_request_reviewers."""

    @staticmethod
    def test_returns_reviewer_list(api_call: ApiCall) -> None:
        """Returns a list of PullRequestReviewer objects."""
        response_json = {"value": [{"id": "rev-1", "displayName": "Alice", "vote": 10}]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_reviewers(api_call)
        assert len(result) == 1
        assert result[0].display_name == "Alice"


class TestIterPrCommits:
    """Tests for iter_pull_request_commits."""

    @staticmethod
    def test_yields_commit_refs(api_call: ApiCall) -> None:
        """Yields GitCommitRef objects from the API response."""
        commit_id = str(uuid4())
        response_json = {"value": [{"commitId": commit_id}]}
        mock_response = _make_mock_response(response_json)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_commits(api_call))
        assert len(result) == 1
        assert str(result[0].commit_id) == commit_id


class TestGetPrDetails:
    """Tests for get_pull_request_details."""

    @staticmethod
    def test_returns_pull_request_created(api_call: ApiCall) -> None:
        """Returns a PullRequestResponse from the API response."""
        pr_data = {
            "pullRequestId": 77,
            "repository": {"id": str(uuid4())},
            "status": "active",
            "url": "https://dev.azure.com/org/proj/_apis/git/pullRequests/77",
            "title": "Fix bug",
            "sourceRefName": "refs/heads/feature/fix",
            "targetRefName": "refs/heads/main",
        }
        mock_response = _make_mock_response(pr_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_details(api_call)
        assert isinstance(result, PullRequestResponse)
        assert result.pr_id == 77
        assert result.title == "Fix bug"


class TestGetPullRequestIterationChanges:
    """Tests for get_pull_request_iteration_changes."""

    @staticmethod
    def test_returns_change_entries_list(api_call: ApiCall) -> None:
        """Returns a list of PullRequestIterationChange from changeEntries."""
        entries = [{"changeType": "add", "item": {"path": "/src/foo.py"}}]
        mock_response = _make_mock_response({"changeEntries": entries})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_iteration_changes(api_call, 2)
        assert len(result) == 1
        assert isinstance(result[0], PullRequestIterationChange)
        assert result[0].change_type == [GitChangeFlag.ADD]
        assert result[0].item.path == "/src/foo.py"

    @staticmethod
    def test_accepts_composite_change_type(api_call: ApiCall) -> None:
        """Composite change types like 'edit, rename' are split into a list."""
        entries = [{"changeType": "edit, rename", "item": {"path": "/src/bar.py"}}]
        mock_response = _make_mock_response({"changeEntries": entries})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_iteration_changes(api_call, 2)
        assert len(result) == 1
        assert result[0].change_type == [GitChangeFlag.EDIT, GitChangeFlag.RENAME]

    @staticmethod
    def test_returns_empty_list_when_no_change_entries(api_call: ApiCall) -> None:
        """Returns an empty list when the response has no changeEntries key."""
        mock_response = _make_mock_response({})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_iteration_changes(api_call, 1)
        assert result == []

    @staticmethod
    def test_sends_get_to_iteration_changes_endpoint(api_call: ApiCall) -> None:
        """Sends a GET to the iterations/{id}/changes endpoint."""
        mock_response = _make_mock_response({"changeEntries": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_pull_request_iteration_changes(api_call, 3)
        call = mock_req.call_args
        assert call.args[0] == "GET"
        url = call.kwargs.get("url", "")
        assert "iterations/3/changes" in url


class TestPatchPrThread:
    """Tests for patch_pull_request_thread."""

    @staticmethod
    def test_returns_thread_response(api_call: ApiCall) -> None:
        """Returns a PullRequestThreadResponse parsed from the response."""
        response_data = {
            "id": 11,
            "status": "fixed",
            "publishedDate": "2024-01-15T12:00:00+00:00",
            "lastUpdatedDate": "2024-01-15T12:00:00+00:00",
            "comments": [],
            "isDeleted": False,
            "identities": None,
            "properties": None,
            "pullRequestThreadContext": None,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = patch_pull_request_thread(
                api_call, 11, PullRequestThreadStatus.FIXED
            )
        assert isinstance(result, PullRequestThreadResponse)

    @staticmethod
    def test_sends_patch_request(api_call: ApiCall) -> None:
        """Sends a PATCH request."""
        response_data = {
            "id": 1,
            "status": "active",
            "publishedDate": "2024-01-15T12:00:00+00:00",
            "lastUpdatedDate": "2024-01-15T12:00:00+00:00",
            "comments": [],
            "isDeleted": False,
            "identities": None,
            "properties": None,
            "pullRequestThreadContext": None,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_pull_request_thread(api_call, 1, PullRequestThreadStatus.ACTIVE)
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_url_contains_thread_id(api_call: ApiCall) -> None:
        """Request URL contains the thread ID."""
        response_data = {
            "id": 5,
            "status": "active",
            "publishedDate": "2024-01-15T12:00:00+00:00",
            "lastUpdatedDate": "2024-01-15T12:00:00+00:00",
            "comments": [],
            "isDeleted": False,
            "identities": None,
            "properties": None,
            "pullRequestThreadContext": None,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_pull_request_thread(api_call, 5, PullRequestThreadStatus.ACTIVE)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "5" in url

    @staticmethod
    def test_body_contains_status(api_call: ApiCall) -> None:
        """Request body contains the status field."""
        response_data = {
            "id": 1,
            "status": "byDesign",
            "publishedDate": "2024-01-15T12:00:00+00:00",
            "lastUpdatedDate": "2024-01-15T12:00:00+00:00",
            "comments": [],
            "isDeleted": False,
            "identities": None,
            "properties": None,
            "pullRequestThreadContext": None,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            patch_pull_request_thread(api_call, 1, PullRequestThreadStatus.BY_DESIGN)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "status" in sent_json


class TestIterPrStatuses:
    """Tests for iter_pull_request_statuses."""

    @staticmethod
    def test_yields_status_info_objects(api_call: ApiCall) -> None:
        """Yields PullRequestStatusInfo objects from the value list."""
        response_data = {
            "value": [
                {
                    "id": 1,
                    "state": "succeeded",
                    "context": {"name": "my-check", "genre": None},
                    "description": "All good",
                }
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_statuses(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestStatusInfo)
        assert result[0].state == PullRequestStatusState.SUCCEEDED

    @staticmethod
    def test_yields_empty_when_no_statuses(api_call: ApiCall) -> None:
        """Yields nothing when the value list is empty."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_statuses(api_call))
        assert result == []

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request to the statuses endpoint."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pull_request_statuses(api_call))
        assert mock_req.call_args.args[0] == "GET"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "statuses" in url


class TestGetPrThread:
    """Tests for get_pull_request_thread."""

    _THREAD_DATA: ClassVar[dict[str, Any]] = {
        "id": 7,
        "status": "active",
        "comments": [
            {
                "id": 1,
                "content": "Nice change",
                "commentType": "text",
                "parentCommentId": 0,
            }
        ],
    }

    @staticmethod
    def test_returns_thread_response(api_call: ApiCall) -> None:
        """Returns a PullRequestThreadResponse with the thread data."""
        thread_data = TestGetPrThread._THREAD_DATA
        mock_response = _make_mock_response(thread_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_thread(api_call, 7)
        assert isinstance(result, PullRequestThreadResponse)
        assert result.id == 7

    @staticmethod
    def test_url_contains_thread_id(api_call: ApiCall) -> None:
        """Sends a GET to a URL that includes the thread ID."""
        thread_data = TestGetPrThread._THREAD_DATA
        mock_response = _make_mock_response(thread_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_pull_request_thread(api_call, 7)
        url = mock_req.call_args.kwargs.get("url", "")
        assert "threads" in url
        assert "7" in url


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

_PR_THREADS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "pullRequestThreadContext": None,
            "id": 7,
            "publishedDate": "2026-06-02T11:56:05.68Z",
            "lastUpdatedDate": "2026-06-02T11:56:05.68Z",
            "comments": [
                {
                    "id": 1,
                    "parentCommentId": 0,
                    "author": _SMOKE_AUTHOR,
                    "content": "Test User updated the pull request status to Completed",
                    "publishedDate": "2026-06-02T11:56:05.68Z",
                    "lastUpdatedDate": "2026-06-02T11:56:05.68Z",
                    "lastContentUpdatedDate": "2026-06-02T11:56:05.68Z",
                    "commentType": "system",
                    "usersLiked": [],
                    "_links": {
                        "self": {
                            "href": (
                                "https://dev.azure.com/example-org/_apis/git/repositories"
                                "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                                "/pullRequests/4/threads/7/comments/1"
                            )
                        }
                    },
                }
            ],
            "threadContext": None,
            "properties": {
                "CodeReviewThreadType": {
                    "$type": "System.String",
                    "$value": "StatusUpdate",
                },
                "CodeReviewStatus": {
                    "$type": "System.String",
                    "$value": "Completed",
                },
                "BypassPolicy": {"$type": "System.String", "$value": "False"},
            },
            "identities": {"1": _SMOKE_AUTHOR},
            "isDeleted": False,
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/_apis/git/repositories"
                        "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906/pullRequests/4/threads/7"
                    )
                }
            },
        }
    ],
}

_COMMIT_SOURCE = "484abe3d12855809c2e1169557e0505fa179cedb"  # pragma: allowlist secret
_COMMIT_TARGET = "b4a8a9c1a41cf98c882adef818f3d00e0eb76587"  # pragma: allowlist secret
_COMMIT_MERGE = "793c58c9db362a9af594627883270b76c27526ad"  # pragma: allowlist secret

_PR_ITERATIONS_SMOKE_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": 1,
            "description": "Update azure-pipelines.yml for Azure Pipelines",
            "author": _SMOKE_AUTHOR,
            "createdDate": "2026-06-02T11:56:00.6300795Z",
            "updatedDate": "2026-06-02T11:56:00.6300795Z",
            "sourceRefCommit": {"commitId": _COMMIT_SOURCE},
            "targetRefCommit": {"commitId": _COMMIT_TARGET},
            "commonRefCommit": {"commitId": _COMMIT_TARGET},
            "hasMoreCommits": False,
            "reason": "push",
        }
    ],
}

_PRS_SMOKE_RESPONSE = {
    "value": [
        {
            "repository": {
                "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
                "name": "sample-repo",
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                ),
                "project": {
                    "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
                    "name": "main",
                    "state": "unchanged",
                    "visibility": "unchanged",
                    "lastUpdateTime": "0001-01-01T00:00:00",
                },
            },
            "pullRequestId": 4,
            "codeReviewId": 4,
            "status": "completed",
            "createdBy": _SMOKE_AUTHOR,
            "creationDate": "2026-06-02T11:56:00.6261407Z",
            "closedDate": "2026-06-02T11:56:05.4597475Z",
            "title": "test",
            "sourceRefName": "refs/heads/azure-pipelines",
            "targetRefName": "refs/heads/main",
            "mergeStatus": "succeeded",
            "isDraft": False,
            "mergeId": "600027e8-bc90-46ec-ae80-dbd593fd7234",
            "lastMergeSourceCommit": {
                "commitId": _COMMIT_SOURCE,
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/484abe3d12855809c2e1169557e0505fa179cedb"
                ),
            },
            "lastMergeTargetCommit": {
                "commitId": _COMMIT_TARGET,
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/b4a8a9c1a41cf98c882adef818f3d00e0eb76587"
                ),
            },
            "lastMergeCommit": {
                "commitId": _COMMIT_MERGE,
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/793c58c9db362a9af594627883270b76c27526ad"
                ),
            },
            "reviewers": [],
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                "/pullRequests/4"
            ),
            "completionOptions": {
                "mergeCommitMessage": "Merged PR 4: test",
                "deleteSourceBranch": True,
                "mergeStrategy": "noFastForward",
                "transitionWorkItems": True,
                "autoCompleteIgnoreConfigIds": [],
            },
            "supportsIterations": True,
        }
    ],
    "count": 1,
}


class TestSmokeIterPrThreads:
    """iter_pull_request_threads parses real PR thread response shapes."""

    @staticmethod
    def test_parses_system_comment_type(api_call: ApiCall) -> None:
        """Thread comment with commentType='system' parses without error."""
        mock_response = _make_mock_response(_PR_THREADS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_threads(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestThreadResponse)
        assert result[0].comments[0].comment_type == PullRequestThreadCommentType.SYSTEM

    @staticmethod
    def test_parses_thread_id_and_comment_count(api_call: ApiCall) -> None:
        """Thread ID and comment list are populated from the real response."""
        mock_response = _make_mock_response(_PR_THREADS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_threads(api_call))
        assert result[0].id == 7
        assert len(result[0].comments) == 1

    @staticmethod
    def test_parses_null_thread_context(api_call: ApiCall) -> None:
        """Thread with null threadContext is parsed without error."""
        mock_response = _make_mock_response(_PR_THREADS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_threads(api_call))
        assert result[0].thread_context is None


class TestSmokeIterPrIterations:
    """iter_pull_request_iterations parses real PR iteration response shapes."""

    @staticmethod
    def test_parses_iteration_with_common_ref_commit(api_call: ApiCall) -> None:
        """Iteration with commonRefCommit (extra field) parses without error."""
        mock_response = _make_mock_response(_PR_ITERATIONS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestIterationRecord)
        assert result[0].id == 1

    @staticmethod
    def test_source_and_target_ref_commits_parsed(api_call: ApiCall) -> None:
        """SourceRefCommit and targetRefCommit are both accessible."""
        mock_response = _make_mock_response(_PR_ITERATIONS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_iterations(api_call))
        iteration = result[0]
        assert iteration.source_ref_commit is not None
        assert (
            iteration.source_ref_commit.commit_id
            == "484abe3d12855809c2e1169557e0505fa179cedb"  # pragma: allowlist secret
        )
        assert iteration.target_ref_commit is not None
        assert (
            iteration.target_ref_commit.commit_id
            == "b4a8a9c1a41cf98c882adef818f3d00e0eb76587"  # pragma: allowlist secret
        )


class TestSmokeIterPrs:
    """iter_pull_requests parses real pull request list response shapes."""

    @staticmethod
    def test_parses_completed_pr(api_call: ApiCall) -> None:
        """Completed PR with closedDate and completionOptions parses correctly."""
        mock_response = _make_mock_response(_PRS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_requests(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestListItem)
        assert result[0].pr_id == 4
        assert result[0].status == "completed"

    @staticmethod
    def test_merge_id_and_last_merge_commits_parsed(api_call: ApiCall) -> None:
        """MergeId and lastMerge* commit refs are accessible on the PR."""
        mock_response = _make_mock_response(_PRS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_requests(api_call))
        pr = result[0]
        assert pr.merge_id is not None
        assert pr.last_merge_source_commit is not None
        assert (
            pr.last_merge_source_commit.commit_id
            == "484abe3d12855809c2e1169557e0505fa179cedb"  # pragma: allowlist secret
        )
        assert pr.last_merge_commit is not None

    @staticmethod
    def test_source_and_target_ref_names_parsed(api_call: ApiCall) -> None:
        """SourceRefName and targetRefName are populated from the real response."""
        mock_response = _make_mock_response(_PRS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_requests(api_call))
        assert result[0].source_ref_name == "refs/heads/azure-pipelines"
        assert result[0].target_ref_name == "refs/heads/main"


class TestListPullRequests:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_requests", return_value=iter([])
        ) as m:
            result = list_pull_requests(api_call)
        assert result == []
        m.assert_called_once_with(api_call, search_criteria=None, expand=None)


class TestListPullRequestThreads:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_request_threads",
            return_value=iter([]),
        ) as m:
            result = list_pull_request_threads(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListPullRequestIterations:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_request_iterations",
            return_value=iter([]),
        ) as m:
            result = list_pull_request_iterations(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListPullRequestCommits:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_request_commits",
            return_value=iter([]),
        ) as m:
            result = list_pull_request_commits(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListPullRequestWorkItemIds:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_request_work_item_ids",
            return_value=iter([]),
        ) as m:
            result = list_pull_request_work_item_ids(api_call)
        assert result == []
        m.assert_called_once_with(api_call)


class TestListPullRequestStatuses:
    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        with patch(
            "pyado.raw.repos.pull_request.iter_pull_request_statuses",
            return_value=iter([]),
        ) as m:
            result = list_pull_request_statuses(api_call)
        assert result == []
        m.assert_called_once_with(api_call)
