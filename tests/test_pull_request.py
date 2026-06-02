"""Tests for pyado.pull_request module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from pydantic.networks import AnyUrl

from pyado.api_call import ApiCall
from pyado.pull_request import (
    PullRequestComment,
    PullRequestCommentHolder,
    PullRequestCommentType,
    PullRequestCreated,
    PullRequestIterationRecord,
    PullRequestStatusContext,
    PullRequestStatusInfo,
    PullRequestThread,
    PullRequestThreadComment,
    PullRequestUpdate,
    PullRequestVote,
    add_pr_label,
    add_pr_reviewer,
    create_pr,
    create_pr_comments,
    create_pr_status_flag,
    create_pr_thread,
    delete_pr_label,
    get_pr_api_call,
    get_pr_labels,
    iter_open_prs,
    iter_pr_iterations,
    iter_pr_threads,
    iter_pr_work_item_ids,
    iter_prs,
    remove_pr_reviewer,
    reply_to_pr_thread,
    set_pr_reviewer_vote,
    update_pr,
)
from pyado.repository import get_repository_api_call

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_token"
REPO_ID = uuid4()
PR_ID = 7


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance.

    Returns:
        A minimal ApiCall instance for testing.
    """
    return ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)


@pytest.fixture
def repo_api_call(api_call: ApiCall) -> ApiCall:
    """Return a repository-level ApiCall.

    Returns:
        A repository-level ApiCall for testing.
    """
    return get_repository_api_call(api_call, REPO_ID)


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


class TestGetPrApiCall:
    """Tests for get_pr_api_call."""

    @staticmethod
    def test_url_contains_pr_path_segments(api_call: ApiCall) -> None:
        """Result URL contains git/repositories/<repo_id>/pullRequests/<pr_id>."""
        result = get_pr_api_call(api_call, REPO_ID, PR_ID)
        url_str = result.url.unicode_string()
        assert "git/repositories" in url_str
        assert "pullRequests" in url_str


class TestIterPrWorkItemIds:
    """Tests for iter_pr_work_item_ids."""

    @staticmethod
    def test_yields_work_item_ids(api_call: ApiCall) -> None:
        """Yields integer IDs from the value list."""
        mock_response = _make_mock_response({"value": [{"id": "101"}, {"id": "202"}]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_work_item_ids(api_call))
        assert result == [101, 202]

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no work item IDs."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_work_item_ids(api_call))
        assert result == []


class TestCreatePrComments:
    """Tests for create_pr_comments."""

    @staticmethod
    def test_posts_comments_to_threads_endpoint(api_call: ApiCall) -> None:
        """Sends a POST to the threads endpoint with the comment payload."""
        comment = PullRequestComment(
            comment_type=PullRequestCommentType.TEXT,
            parent_comment_id=0,
            content="Review comment",
        )
        holder = PullRequestCommentHolder(status="active", comments=[comment])
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr_comments(api_call, holder)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json["status"] == "active"
        assert len(sent_json["comments"]) == 1


class TestCreatePrStatusFlag:
    """Tests for create_pr_status_flag."""

    @staticmethod
    def test_posts_status_to_statuses_endpoint(api_call: ApiCall) -> None:
        """Sends a POST to the statuses endpoint with the status payload."""
        status = PullRequestStatusInfo(
            context=PullRequestStatusContext(name="my-check", genre="ci"),
            description="Build passed",
            iteration_id=2,
            state="succeeded",
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr_status_flag(api_call, status)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json["state"] == "succeeded"
        assert sent_json["iterationId"] == 2

    @staticmethod
    def test_excludes_none_fields_from_payload(api_call: ApiCall) -> None:
        """None fields (like targetUrl) are omitted from the posted payload."""
        status = PullRequestStatusInfo(
            context=PullRequestStatusContext(name="check", genre="test"),
            iteration_id=1,
            state="pending",
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr_status_flag(api_call, status)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "targetUrl" not in sent_json

    @staticmethod
    def test_includes_target_url_when_provided(api_call: ApiCall) -> None:
        """TargetUrl is included in the payload when not None."""
        status = PullRequestStatusInfo(
            context=PullRequestStatusContext(name="check", genre="test"),
            iteration_id=1,
            state="succeeded",
            target_url=AnyUrl("https://ci.example.com/builds/42"),
        )
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr_status_flag(api_call, status)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "targetUrl" in sent_json


class TestPullRequestComment:
    """Tests for PullRequestComment model."""

    @staticmethod
    def test_instantiation_with_aliases() -> None:
        """Model can be instantiated using camelCase alias names."""
        comment = PullRequestComment(
            comment_type=2, parent_comment_id=0, content="Hello"
        )
        assert comment.comment_type == 2
        assert comment.parent_comment_id == 0


class TestIterPrWorkItemIdsPagination:
    """Tests for iter_pr_work_item_ids pagination."""

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
            result = list(iter_pr_work_item_ids(api_call))
        assert len(result) == 101
        assert result[-1] == 100


class TestIterPrs:
    """Tests for iter_prs."""

    @staticmethod
    def test_yields_pr_list_items(api_call: ApiCall) -> None:
        """Yields PullRequestListItem objects from the API response."""
        pr_data = {"pullRequestId": 42, "repository": {"id": str(REPO_ID)}}
        mock_response = _make_mock_response({"value": [pr_data]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_prs(api_call))
        assert len(result) == 1
        assert result[0].pr_id == 42

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no PRs."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_prs(api_call))
        assert result == []

    @staticmethod
    def test_search_criteria_added_as_params(api_call: ApiCall) -> None:
        """Search criteria are forwarded as searchCriteria.* query parameters."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_prs(api_call, search_criteria={"status": "active"}))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "searchCriteria.status" in params
        assert params["searchCriteria.status"] == "active"

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
            result = list(iter_prs(api_call))
        assert len(result) == 101


class TestIterOpenPrs:
    """Tests for iter_open_prs."""

    @staticmethod
    def test_passes_active_status_criteria(api_call: ApiCall) -> None:
        """Passes searchCriteria.status=active to the underlying API call."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_open_prs(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("searchCriteria.status") == "active"


class TestGetPrLabels:
    """Tests for get_pr_labels."""

    @staticmethod
    def test_returns_label_names(api_call: ApiCall) -> None:
        """Returns a list of label name strings."""
        mock_response = _make_mock_response(
            {"value": [{"name": "ready"}, {"name": "wip"}]}
        )
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pr_labels(api_call)
        assert result == ["ready", "wip"]

    @staticmethod
    def test_returns_empty_list_when_no_labels(api_call: ApiCall) -> None:
        """Returns an empty list when no labels exist."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pr_labels(api_call)
        assert result == []


class TestAddPrLabel:
    """Tests for add_pr_label."""

    @staticmethod
    def test_posts_label_name(api_call: ApiCall) -> None:
        """Posts the label name to the labels endpoint."""
        mock_response = _make_mock_response({"name": "my-label"})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_pr_label(api_call, "my-label")
        call = mock_req.call_args
        assert call.args[0] == "POST"
        assert call.kwargs.get("json") == {"name": "my-label"}


class TestDeletePrLabel:
    """Tests for delete_pr_label."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request for the given label name."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_pr_label(api_call, "stale")
        assert mock_req.call_args.args[0] == "DELETE"


class TestIterPrThreads:
    """Tests for iter_pr_threads."""

    @staticmethod
    def test_yields_thread_objects(api_call: ApiCall) -> None:
        """Yields PullRequestThread objects from the API response."""
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
            result = list(iter_pr_threads(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestThread)
        assert result[0].id == 1

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty thread list yields no results."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_threads(api_call))
        assert result == []


class TestCreatePrThread:
    """Tests for create_pr_thread."""

    @staticmethod
    def test_creates_pr_level_thread(api_call: ApiCall) -> None:
        """Creates a PR-level thread without file context."""
        thread_data = {"id": 5, "status": "active", "comments": []}
        mock_response = _make_mock_response(thread_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = create_pr_thread(api_call, "PR-level comment")
        assert isinstance(result, PullRequestThread)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "threadContext" not in sent_json

    @staticmethod
    def test_creates_file_anchored_thread(api_call: ApiCall) -> None:
        """Creates a thread anchored to a specific file and line."""
        thread_data = {"id": 6, "status": "active", "comments": []}
        mock_response = _make_mock_response(thread_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = create_pr_thread(
                api_call, "Inline comment", file_path="/src/foo.py", line=10
            )
        assert isinstance(result, PullRequestThread)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "threadContext" in sent_json
        assert sent_json["threadContext"]["filePath"] == "/src/foo.py"
        assert sent_json["threadContext"]["rightFileStart"]["line"] == 10

    @staticmethod
    def test_raises_when_line_set_without_file_path(api_call: ApiCall) -> None:
        """Raises ValueError when line is given without file_path."""
        with pytest.raises(ValueError, match="file_path"):
            create_pr_thread(api_call, "comment", line=5)


class TestReplyToPrThread:
    """Tests for reply_to_pr_thread."""

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
            result = reply_to_pr_thread(
                api_call, thread_id=7, parent_comment_id=1, content="Reply text"
            )
        assert isinstance(result, PullRequestThreadComment)
        assert result.content == "Reply text"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["parentCommentId"] == 1


class TestUpdatePr:
    """Tests for update_pr."""

    @staticmethod
    def test_patches_pr_fields(api_call: ApiCall) -> None:
        """Sends a PATCH request with the given fields."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_pr(api_call, PullRequestUpdate(title="Updated title"))
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["title"] == "Updated title"


class TestIterPrIterations:
    """Tests for iter_pr_iterations."""

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
            result = list(iter_pr_iterations(api_call))
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
            result = list(iter_pr_iterations(api_call))
        assert result == []


class TestSetPrReviewerVote:
    """Tests for set_pr_reviewer_vote."""

    @staticmethod
    def test_puts_vote_for_reviewer(api_call: ApiCall) -> None:
        """Sends a PUT request with the reviewer ID and vote value."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            set_pr_reviewer_vote(
                api_call, reviewer_id="user-uuid-123", vote=PullRequestVote.APPROVED
            )
        assert mock_req.call_args.args[0] == "PUT"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["vote"] == PullRequestVote.APPROVED


class TestAddPrReviewer:
    """Tests for add_pr_reviewer."""

    @staticmethod
    def test_adds_optional_reviewer(api_call: ApiCall) -> None:
        """Sends a PUT request with isRequired=False by default."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_pr_reviewer(api_call, "reviewer-uuid")
        assert mock_req.call_args.args[0] == "PUT"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["isRequired"] is False
        assert sent_json["vote"] == PullRequestVote.NO_VOTE

    @staticmethod
    def test_adds_required_reviewer(api_call: ApiCall) -> None:
        """Sends a PUT request with isRequired=True when specified."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_pr_reviewer(api_call, "reviewer-uuid", is_required=True)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["isRequired"] is True


class TestRemovePrReviewer:
    """Tests for remove_pr_reviewer."""

    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        """Sends a DELETE request for the given reviewer ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            remove_pr_reviewer(api_call, "reviewer-uuid")
        assert mock_req.call_args.args[0] == "DELETE"
        called_url: str = mock_req.call_args.kwargs.get("url") or ""
        assert "reviewer-uuid" in called_url


class TestCreatePr:
    """Tests for create_pr."""

    @staticmethod
    def _pr_response(
        pr_id: int, title: str, source: str, target: str
    ) -> dict[str, Any]:
        return {
            "pullRequestId": pr_id,
            "repository": {"id": str(REPO_ID)},
            "status": "active",
            "url": f"https://dev.azure.com/org/proj/_apis/git/pullRequests/{pr_id}",
            "title": title,
            "sourceRefName": source,
            "targetRefName": target,
        }

    def test_creates_pr_with_required_fields(self, repo_api_call: ApiCall) -> None:
        """Returns a PullRequestCreated after posting the PR payload."""
        mock_response = _make_mock_response(
            self._pr_response(99, "My PR", "refs/heads/feature/abc", "refs/heads/main")
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = create_pr(repo_api_call, "My PR", "feature/abc", "main")
        assert isinstance(result, PullRequestCreated)
        assert result.pr_id == 99
        assert result.status == "active"
        assert result.title == "My PR"
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body["title"] == "My PR"
        assert body["sourceRefName"] == "refs/heads/feature/abc"
        assert body["targetRefName"] == "refs/heads/main"

    def test_includes_description_when_provided(self, repo_api_call: ApiCall) -> None:
        """Includes description in the payload when supplied."""
        mock_response = _make_mock_response(
            self._pr_response(
                100, "PR with desc", "refs/heads/feature/xyz", "refs/heads/main"
            )
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr(
                repo_api_call,
                "PR with desc",
                "feature/xyz",
                "main",
                description="Some description",
            )
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body["description"] == "Some description"

    def test_omits_description_when_none(self, repo_api_call: ApiCall) -> None:
        """Does not include description key when description is None."""
        mock_response = _make_mock_response(
            self._pr_response(101, "No desc PR", "refs/heads/feat", "refs/heads/main")
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr(repo_api_call, "No desc PR", "feat", "main")
        body = mock_req.call_args.kwargs.get("json") or {}
        assert "description" not in body

    def test_accepts_full_refs_heads_prefix(self, repo_api_call: ApiCall) -> None:
        """Does not double-add refs/heads/ when already present in branch names."""
        mock_response = _make_mock_response(
            self._pr_response(
                102,
                "Full ref PR",
                "refs/heads/feature/full",
                "refs/heads/main",
            )
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_pr(
                repo_api_call,
                "Full ref PR",
                "refs/heads/feature/full",
                "refs/heads/main",
            )
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body["sourceRefName"] == "refs/heads/feature/full"
        assert body["targetRefName"] == "refs/heads/main"
