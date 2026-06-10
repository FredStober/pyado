"""Tests for pyado.oop.repos._pull_request — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.oop import Commit, Project, PullRequest, Repository
from pyado.oop.repos._pull_request import (
    abandon_pull_request,
    add_pull_request_reviewer,
    complete_pull_request,
    create_pull_request,
    create_pull_request_thread,
    get_pull_request_tags,
    iter_pull_request_work_item_ids,
    link_pull_request_work_item,
    reply_to_pull_request_thread,
    set_pull_request_reviewer_vote,
    update_pull_request_work_item_refs,
)
from pyado.raw import (
    ApiCall,
    ConnectionData,
    IdentityIdRef,
    PullRequestCompletionOptions,
    PullRequestIterationChange,
    PullRequestIterationRecord,
    PullRequestLabel,
    PullRequestListItem,
    PullRequestResponse,
    PullRequestStatus,
    PullRequestStatusInfo,
    PullRequestStatusState,
    PullRequestThreadCommentResponse,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestVote,
    WorkItemInfo,
    WorkItemRelationType,
    get_pull_request_api_call,
    get_repository_api_call,
)
from tests.conftest import NOW_ISO, _make_mock_response
from tests.oop.conftest import (
    ORG_URL,
    _api_call,
    _git_commit_ref,
    _make_pr,
    _make_project,
    _make_repo,
    _make_service,
    _make_wi,
    _pr_created,
    _pr_list_item,
    _project_info,
    _repo_info,
    _work_item_info,
)
from tests.oop.conftest import (
    REPO_ID as OOP_REPO_ID,
)

REPO_ID = uuid4()
PR_ID = 7


@pytest.fixture
def repo_api_call(api_call: ApiCall) -> ApiCall:
    """Return a repository-level ApiCall.

    Returns:
        A repository-level ApiCall for testing.
    """
    return get_repository_api_call(api_call, REPO_ID)


_PATCH_PR_RESPONSE: dict[str, Any] = {
    "pullRequestId": PR_ID,
    "repository": {"id": str(REPO_ID)},
    "status": "active",
    "url": "https://example.com",
    "title": "Updated title",
    "sourceRefName": "refs/heads/feature",
    "targetRefName": "refs/heads/main",
}


class TestIterPrWorkItemIds:
    """Tests for iter_pull_request_work_item_ids."""

    @staticmethod
    def test_yields_work_item_ids(api_call: ApiCall) -> None:
        """Yields integer IDs from the value list."""
        mock_response = _make_mock_response({"value": [{"id": "101"}, {"id": "202"}]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_work_item_ids(api_call))
        assert result == [101, 202]

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no work item IDs."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pull_request_work_item_ids(api_call))
        assert result == []


class TestIterPrWorkItemIdsPagination:
    """Tests for iter_pull_request_work_item_ids pagination."""

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
            result = list(iter_pull_request_work_item_ids(api_call))
        assert len(result) == 101
        assert result[-1] == 100


class TestGetPrTags:
    """Tests for get_pull_request_tags."""

    @staticmethod
    def test_returns_tag_names(api_call: ApiCall) -> None:
        """Returns a list of tag name strings."""
        mock_response = _make_mock_response(
            {"value": [{"name": "ready"}, {"name": "wip"}]}
        )
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_tags(api_call)
        assert result == ["ready", "wip"]

    @staticmethod
    def test_returns_empty_list_when_no_tags(api_call: ApiCall) -> None:
        """Returns an empty list when no tags exist."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pull_request_tags(api_call)
        assert result == []


class TestCreatePrThread:
    """Tests for create_pull_request_thread."""

    @staticmethod
    def test_creates_pr_level_thread(api_call: ApiCall) -> None:
        """Creates a PR-level thread without file context."""
        thread_data = {"id": 5, "status": "active", "comments": []}
        mock_response = _make_mock_response(thread_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = create_pull_request_thread(api_call, "PR-level comment")
        assert isinstance(result, PullRequestThreadResponse)
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
            result = create_pull_request_thread(
                api_call, "Inline comment", file_path="/src/foo.py", line=10
            )
        assert isinstance(result, PullRequestThreadResponse)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert "threadContext" in sent_json
        assert sent_json["threadContext"]["filePath"] == "/src/foo.py"
        assert sent_json["threadContext"]["rightFileStart"]["line"] == 10

    @staticmethod
    def test_raises_when_line_set_without_file_path(api_call: ApiCall) -> None:
        """Raises ValueError when line is given without file_path."""
        with pytest.raises(ValueError, match="file_path"):
            create_pull_request_thread(api_call, "comment", line=5)


class TestReplyToPrThreadHighLevel:
    """Tests for reply_to_pull_request_thread."""

    @staticmethod
    def test_posts_plain_text_reply(api_call: ApiCall) -> None:
        """Sends a text reply to the specified thread."""
        comment_data = {
            "id": 3,
            "content": "High-level reply",
            "commentType": "text",
            "parentCommentId": 1,
        }
        mock_response = _make_mock_response(comment_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = reply_to_pull_request_thread(api_call, 5, "High-level reply")
        assert isinstance(result, PullRequestThreadCommentResponse)
        assert result.content == "High-level reply"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["parentCommentId"] == 1


class TestSetPrReviewerVote:
    """Tests for put_pull_request_reviewer_vote."""

    @staticmethod
    def test_puts_vote_for_reviewer(api_call: ApiCall) -> None:
        """Sends a PUT request with the reviewer ID and vote value."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            set_pull_request_reviewer_vote(
                api_call, reviewer_id="user-uuid-123", vote=PullRequestVote.APPROVED
            )
        assert mock_req.call_args.args[0] == "PUT"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["vote"] == PullRequestVote.APPROVED


class TestAddPrReviewer:
    """Tests for put_pull_request_reviewer."""

    @staticmethod
    def test_adds_optional_reviewer(api_call: ApiCall) -> None:
        """Sends a PUT request with isRequired=False by default."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            add_pull_request_reviewer(api_call, "reviewer-uuid")
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
            add_pull_request_reviewer(api_call, "reviewer-uuid", is_required=True)
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json["isRequired"] is True


class TestCreatePr:
    """Tests for create_pull_request."""

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
        """Returns a PullRequestResponse after posting the PR payload."""
        mock_response = _make_mock_response(
            self._pr_response(99, "My PR", "refs/heads/feature/abc", "refs/heads/main")
        )
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = create_pull_request(repo_api_call, "My PR", "feature/abc", "main")
        assert isinstance(result, PullRequestResponse)
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
            create_pull_request(
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
            create_pull_request(repo_api_call, "No desc PR", "feat", "main")
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
            create_pull_request(
                repo_api_call,
                "Full ref PR",
                "refs/heads/feature/full",
                "refs/heads/main",
            )
        body = mock_req.call_args.kwargs.get("json") or {}
        assert body["sourceRefName"] == "refs/heads/feature/full"
        assert body["targetRefName"] == "refs/heads/main"


class TestCompletePr:
    """Tests for complete_pull_request."""

    @staticmethod
    def test_patches_pr_with_completed_status(api_call: ApiCall) -> None:
        """Sends PATCH with status=completed and the merge source commit ID."""
        response_data = {**_PATCH_PR_RESPONSE, "status": "completed"}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = complete_pull_request(api_call, "abc123sha")
        assert isinstance(result, PullRequestResponse)
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("status") == "completed"
        assert sent_json.get("lastMergeSourceCommit") == {"commitId": "abc123sha"}


class TestAbandonPr:
    """Tests for abandon_pull_request."""

    @staticmethod
    def test_patches_pr_with_abandoned_status(api_call: ApiCall) -> None:
        """Sends PATCH with status=abandoned and returns updated PullRequestResponse."""
        response_data = {**_PATCH_PR_RESPONSE, "status": "abandoned"}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = abandon_pull_request(api_call)
        assert isinstance(result, PullRequestResponse)
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("status") == "abandoned"


class TestLinkPrWorkItem:
    """Tests for link_pull_request_work_item."""

    @staticmethod
    def test_adds_pr_artifact_link_to_work_item() -> None:
        """Fetches PR details then patches the work item with an ArtifactLink."""
        repo_id = uuid4()
        pr_data = {
            "pullRequestId": 7,
            "repository": {"id": str(repo_id)},
            "status": "active",
            "url": "https://dev.azure.com/org/myproject/_apis/git/pullRequests/7",
            "title": "My PR",
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main",
        }
        wi_data: dict[str, Any] = {"id": 42, "fields": {"System.Title": "Task"}}
        project_api_call = ApiCall(
            url="https://dev.azure.com/org/myproject/",
        )
        pr_api_call = get_pull_request_api_call(project_api_call, repo_id, 7)
        pr_response = _make_mock_response(pr_data)
        wi_response = _make_mock_response(wi_data)
        with patch.object(
            requests.Session,
            "request",
            side_effect=[pr_response, wi_response],
        ) as mock_req:
            result = link_pull_request_work_item(pr_api_call, project_api_call, 42)
        assert isinstance(result, WorkItemInfo)
        patch_call = mock_req.call_args_list[1]
        assert patch_call.args[0] == "PATCH"
        patch_body = patch_call.kwargs.get("json") or []
        assert patch_body[0]["value"]["rel"] == WorkItemRelationType.ARTIFACT_LINK
        assert "myproject" in patch_body[0]["value"]["url"]

    @staticmethod
    def test_includes_comment_in_link_attributes() -> None:
        """Optional comment is included in the artifact link attributes."""
        repo_id = uuid4()
        pr_data = {
            "pullRequestId": 3,
            "repository": {"id": str(repo_id)},
            "status": "active",
            "url": "https://dev.azure.com/org/myproject/_apis/git/pullRequests/3",
            "title": "PR",
            "sourceRefName": "refs/heads/feature",
            "targetRefName": "refs/heads/main",
        }
        wi_data: dict[str, Any] = {"id": 1, "fields": {}}
        project_api_call = ApiCall(
            url="https://dev.azure.com/org/myproject/",
        )
        pr_api_call = get_pull_request_api_call(project_api_call, repo_id, 3)
        with patch.object(
            requests.Session,
            "request",
            side_effect=[_make_mock_response(pr_data), _make_mock_response(wi_data)],
        ) as mock_req:
            link_pull_request_work_item(
                pr_api_call, project_api_call, 1, comment="reviewed"
            )
        patch_body = mock_req.call_args_list[1].kwargs.get("json") or []
        assert patch_body[0]["value"]["attributes"]["comment"] == "reviewed"


class TestUpdatePrWorkItemRefs:
    """Tests for update_pull_request_work_item_refs."""

    @staticmethod
    def test_sends_patch_with_work_item_refs(api_call: ApiCall) -> None:
        """Sends a PATCH request whose body includes workItemRefs."""
        pr_response = {
            "pullRequestId": PR_ID,
            "repository": {"id": str(REPO_ID)},
            "status": "active",
            "url": "https://dev.azure.com/org/proj/_apis/git/pullRequests/7",
            "title": "My PR",
            "sourceRefName": "refs/heads/feat",
            "targetRefName": "refs/heads/main",
        }
        mock_response = _make_mock_response(pr_response)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_pull_request_work_item_refs(api_call, [101, 202])
        call = mock_req.call_args
        assert call.args[0] == "PATCH"
        sent_json = call.kwargs.get("json") or {}
        assert "workItemRefs" in sent_json
        assert {"id": 101} in sent_json["workItemRefs"]
        assert {"id": 202} in sent_json["workItemRefs"]

    @staticmethod
    def test_empty_work_item_ids_sends_empty_refs(api_call: ApiCall) -> None:
        """Passing an empty list sends workItemRefs as an empty list."""
        pr_response = {
            "pullRequestId": PR_ID,
            "repository": {"id": str(REPO_ID)},
            "status": "active",
            "url": "https://dev.azure.com/org/proj/_apis/git/pullRequests/7",
            "title": "My PR",
            "sourceRefName": "refs/heads/feat",
            "targetRefName": "refs/heads/main",
        }
        mock_response = _make_mock_response(pr_response)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_pull_request_work_item_refs(api_call, [])
        sent_json = mock_req.call_args.kwargs.get("json") or {}
        assert sent_json.get("workItemRefs") == []


# ---------------------------------------------------------------------------
# OOP PullRequest tests
# ---------------------------------------------------------------------------


class TestPullRequest:
    def test_id(self) -> None:
        assert _make_pr(99).id == 99

    def test_title(self) -> None:
        assert _make_pr().title == "Test PR"

    def test_status(self) -> None:
        assert _make_pr().status == "active"

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        repo = _make_repo()
        pr = PullRequest(repo, api, _pr_list_item())
        assert pr.api_call is api

    def test_info_returns_info(self) -> None:
        pr = _make_pr(7)
        assert pr.info.pr_id == 7

    def test_repo_reference(self) -> None:
        repo = _make_repo()
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.repo is repo

    def test_project_via_repo(self) -> None:
        proj = _make_project()
        repo_api = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{OOP_REPO_ID}"
        )
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.project is proj

    def test_org_via_repo(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        repo_api = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{OOP_REPO_ID}"
        )
        repo = Repository(proj, repo_api, _repo_info(), svc)
        pr_api = _api_call()
        pr = PullRequest(repo, pr_api, _pr_list_item())
        assert pr.org is svc.org

    def test_refresh_refetches(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_details"
        ) as mock_get:
            mock_get.return_value = _pr_list_item()
            pr.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = pr.info
        mock_get.assert_called_once()

    def test_link_work_item_calls_add_work_item_link(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._work_item.add_work_item_link"
        ) as mock_link:
            mock_link.return_value = _work_item_info()
            pr = _make_pr(32)
            wi = _make_wi(153)
            pr.link_work_item(wi)
        mock_link.assert_called_once()
        relation = mock_link.call_args.args[1]
        assert "PullRequestId" in relation.url
        assert "32" in relation.url

    def test_link_work_item_with_comment(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._work_item.add_work_item_link"
        ) as mock_link:
            mock_link.return_value = _work_item_info()
            _make_pr(32).link_work_item(_make_wi(153), comment="Linked via PR")
        relation = mock_link.call_args.args[1]
        assert relation.attributes is not None
        assert relation.attributes.get("comment") == "Linked via PR"

    def test_iter_tag_details_yields_labels(self) -> None:
        label = PullRequestLabel(id="abc", name="ready", active=True)
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_labels_details"
        ) as mock_labels:
            mock_labels.return_value = [label]
            result = list(_make_pr().iter_tag_details())
        assert result == [label]

    def test_list_tag_details_delegates_to_iter(self) -> None:
        label = PullRequestLabel(id="abc", name="ready", active=True)
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_labels_details"
        ) as mock_labels:
            mock_labels.return_value = [label]
            result = _make_pr().list_tag_details()
        assert result == [label]

    def test_iter_tags_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.get_pull_request_tags"
        ) as mock_tags:
            mock_tags.return_value = ["tag-a", "tag-b"]
            tags = list(_make_pr().iter_tags())
        assert tags == ["tag-a", "tag-b"]

    def test_list_tags_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.get_pull_request_tags"
        ) as mock_tags:
            mock_tags.return_value = ["tag-a", "tag-b"]
            tags = _make_pr().list_tags()
        assert tags == ["tag-a", "tag-b"]

    def test_add_tag_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.post_pull_request_label"
        ) as mock_add:
            _make_pr().add_tag("my-tag")
        mock_add.assert_called_once()

    def test_remove_tag_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.delete_pull_request_label"
        ) as mock_del:
            _make_pr().remove_tag("my-tag")
        mock_del.assert_called_once()

    def test_add_thread_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.create_pull_request_thread"
        ) as mock_thread:
            mock_thread.return_value = MagicMock()
            _make_pr().add_thread("hello")
        assert mock_thread.call_args.args[1] == "hello"

    def test_iter_threads_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_threads"
        ) as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_pr().iter_threads())
        assert len(result) == 1

    def test_reply_to_thread_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.reply_to_pull_request_thread"
        ) as mock_reply:
            mock_reply.return_value = MagicMock()
            _make_pr().reply_to_thread(1, "reply text")
        assert mock_reply.call_args.args[1] == 1
        assert mock_reply.call_args.args[2] == "reply text"

    def test_list_reviewers_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_reviewers"
        ) as mock_get:
            mock_get.return_value = [MagicMock()]
            result = _make_pr().list_reviewers()
        assert len(result) == 1

    def test_add_reviewer_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.add_pull_request_reviewer"
        ) as mock_add:
            _make_pr().add_reviewer("user-id", is_required=True)
        assert mock_add.call_args.args[1] == "user-id"
        assert mock_add.call_args.kwargs["is_required"] is True

    def test_remove_reviewer_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.delete_pull_request_reviewer"
        ) as mock_del:
            _make_pr().remove_reviewer("user-id")
        mock_del.assert_called_once()

    def test_vote_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.set_pull_request_reviewer_vote"
        ) as mock_vote:
            _make_pr().vote("user-id", PullRequestVote.APPROVED)
        assert mock_vote.call_args.args[1] == "user-id"
        assert mock_vote.call_args.args[2] == PullRequestVote.APPROVED

    def test_update_sends_only_non_none(self) -> None:
        with patch("pyado.oop.repos.pull_request.raw.patch_pull_request") as mock_patch:
            _make_pr().update(title="New Title")
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.title == "New Title"
        assert update_arg.description is None

    def test_update_refreshes_cached_info(self) -> None:
        pr = _make_pr()
        updated_response = _pr_created(pr.id)
        updated_response = PullRequestResponse.model_validate(
            {
                **updated_response.model_dump(by_alias=True),
                "title": "Renamed Title",
            }
        )
        with patch(
            "pyado.oop.repos.pull_request.raw.patch_pull_request",
            return_value=updated_response,
        ):
            pr.update(title="Renamed Title")
        assert pr.title == "Renamed Title"

    def test_set_status_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.post_pull_request_status"
        ) as mock_status:
            _make_pr().set_status(PullRequestStatusState.SUCCEEDED, "my-check")
        mock_status.assert_called_once()

    def test_set_status_with_target_url(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.post_pull_request_status"
        ) as mock_status:
            _make_pr().set_status(
                PullRequestStatusState.SUCCEEDED,
                "my-check",
                target_url="https://example.com/build/1",
            )
        request_arg = mock_status.call_args.args[1]
        assert request_arg.target_url is not None

    def test_iter_commits_returns_commit_objects(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_commits"
        ) as mock_iter:
            mock_iter.return_value = iter(
                [_git_commit_ref("abc123"), _git_commit_ref("def456")]
            )
            result = list(_make_pr().iter_commits())
        assert len(result) == 2
        assert all(isinstance(item, Commit) for item in result)
        assert result[0].sha == "abc123"

    def test_iter_commits_back_reference_is_pr_repo(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_commits"
        ) as mock_iter:
            mock_iter.return_value = iter([_git_commit_ref("abc123")])
            result = list(pr.iter_commits())
        assert result[0].repo is pr.repo

    def test_iter_work_item_ids_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request._pull_request.iter_pull_request_work_item_ids"
        ) as mock_iter:
            mock_iter.return_value = iter([10, 20])
            result = list(_make_pr().iter_work_item_ids())
        assert result == [10, 20]

    def test_iter_iterations_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_iterations"
        ) as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_pr().iter_iterations())
        assert len(result) == 1
        mock_iter.assert_called_once()

    def test_get_iteration_changes_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_iteration_changes"
        ) as mock_get:
            mock_get.return_value = [MagicMock(), MagicMock()]
            result = _make_pr().get_iteration_changes(2)
        assert len(result) == 2
        assert mock_get.call_args.args[1] == 2

    def test_enable_auto_complete_patches_pr(self) -> None:
        with patch("pyado.oop.repos.pull_request.raw.patch_pull_request") as mock_patch:
            _make_pr().enable_auto_complete("user-id-123")
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.auto_complete_set_by == IdentityIdRef(id="user-id-123")

    def test_enable_auto_complete_uses_own_identity_when_no_id_given(self) -> None:
        conn_data = ConnectionData.model_validate(
            {"authenticatedUser": {"id": "auto-id-456", "providerDisplayName": "Me"}}
        )
        with (
            patch("pyado.oop.repos.pull_request.raw.patch_pull_request") as mock_patch,
            patch(
                "pyado.oop.organization.raw.get_connection_data",
                return_value=conn_data,
            ),
        ):
            _make_pr().enable_auto_complete()
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.auto_complete_set_by == IdentityIdRef(id="auto-id-456")

    def test_enable_auto_complete_with_options(self) -> None:
        opts = PullRequestCompletionOptions.model_validate(
            {"mergeStrategy": "squash", "deleteSourceBranch": True}
        )
        with patch("pyado.oop.repos.pull_request.raw.patch_pull_request") as mock_patch:
            _make_pr().enable_auto_complete("user-id-123", completion_options=opts)
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.completion_options is opts

    def test_disable_auto_complete_patches_pr(self) -> None:
        with patch("pyado.oop.repos.pull_request.raw.patch_pull_request") as mock_patch:
            _make_pr().disable_auto_complete()
        update_arg = mock_patch.call_args.args[1]
        assert update_arg.auto_complete_set_by == IdentityIdRef(
            id="00000000-0000-0000-0000-000000000000"
        )

    def test_update_thread_status_delegates(self) -> None:
        thread_resp = MagicMock(spec=PullRequestThreadResponse)
        with patch(
            "pyado.oop.repos.pull_request.raw.patch_pull_request_thread"
        ) as mock_patch:
            mock_patch.return_value = thread_resp
            result = _make_pr().update_thread_status(7, PullRequestThreadStatus.FIXED)
        mock_patch.assert_called_once()
        assert mock_patch.call_args.args[1] == 7
        assert mock_patch.call_args.args[2] == PullRequestThreadStatus.FIXED
        assert result is thread_resp

    def test_iter_statuses_delegates(self) -> None:
        status = PullRequestStatusInfo.model_validate(
            {
                "state": "succeeded",
                "context": {"name": "ci-check", "genre": None},
            }
        )
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_statuses"
        ) as mock_iter:
            mock_iter.return_value = iter([status])
            result = list(_make_pr().iter_statuses())
        assert len(result) == 1
        assert result[0].state == PullRequestStatusState.SUCCEEDED

    def _pr_with_branches(self) -> PullRequest:
        info = PullRequestListItem.model_validate(
            {
                "pullRequestId": 99,
                "repository": {"id": str(OOP_REPO_ID)},
                "title": "Test PR",
                "status": "active",
                "sourceRefName": "refs/heads/feature/x",
                "targetRefName": "refs/heads/main",
                "description": "My description",
                "createdBy": {"id": str(uuid4()), "displayName": "Alice"},
            }
        )
        repo = _make_repo()
        api_call = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{OOP_REPO_ID}/pullrequests/99"
        )
        return PullRequest(repo, api_call, info)

    def test_source_branch_returns_ref(self) -> None:
        assert self._pr_with_branches().source_branch == "refs/heads/feature/x"

    def test_target_branch_returns_ref(self) -> None:
        assert self._pr_with_branches().target_branch == "refs/heads/main"

    def test_description_returns_text(self) -> None:
        assert self._pr_with_branches().description == "My description"

    def test_created_by_returns_display_name(self) -> None:
        assert self._pr_with_branches().created_by == "Alice"

    def test_list_tag_details_delegates_to_raw(self) -> None:
        label = PullRequestLabel(name="my-tag")
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_labels_details"
        ) as mock_get:
            mock_get.return_value = [label]
            result = _make_pr().list_tag_details()
        assert result == [label]
        mock_get.assert_called_once()

    def test_iter_files_changed_yields_changes(self) -> None:
        iteration = PullRequestIterationRecord.model_validate(
            {"id": 3, "createdDate": NOW_ISO, "updatedDate": NOW_ISO}
        )
        change = MagicMock(spec=PullRequestIterationChange)
        with (
            patch(
                "pyado.oop.repos.pull_request.raw.iter_pull_request_iterations"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.pull_request.raw.get_pull_request_iteration_changes"
            ) as mock_changes,
        ):
            mock_iter.return_value = iter([iteration])
            mock_changes.return_value = [change]
            result = list(_make_pr().iter_files_changed())
        assert result == [change]
        assert mock_changes.call_args.args[1] == 3

    def test_iter_files_changed_empty_when_no_iterations(self) -> None:
        with patch(
            "pyado.oop.repos.pull_request.raw.iter_pull_request_iterations"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(_make_pr().iter_files_changed())
        assert result == []

    def test_iter_files_changed_uses_last_iteration(self) -> None:
        iter1 = PullRequestIterationRecord.model_validate(
            {"id": 1, "createdDate": NOW_ISO, "updatedDate": NOW_ISO}
        )
        iter2 = PullRequestIterationRecord.model_validate(
            {"id": 5, "createdDate": NOW_ISO, "updatedDate": NOW_ISO}
        )
        with (
            patch(
                "pyado.oop.repos.pull_request.raw.iter_pull_request_iterations"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.pull_request.raw.get_pull_request_iteration_changes"
            ) as mock_changes,
        ):
            mock_iter.return_value = iter([iter1, iter2])
            mock_changes.return_value = []
            list(_make_pr().iter_files_changed())
        assert mock_changes.call_args.args[1] == 5


# ---------------------------------------------------------------------------
# OOP PullRequestLifecycle tests
# ---------------------------------------------------------------------------


class TestPullRequestLifecycle:
    def test_complete_delegates(self) -> None:
        pr = _make_pr()
        completed = _pr_created()
        with patch(
            "pyado.oop.repos.pull_request._pull_request.complete_pull_request"
        ) as mock_complete:
            mock_complete.return_value = completed
            pr.complete("deadbeef")
        mock_complete.assert_called_once_with(
            pr.api_call, "deadbeef", completion_options=None
        )

    def test_complete_updates_info(self) -> None:
        pr = _make_pr()
        completed = _pr_created()
        completed.status = PullRequestStatus.COMPLETED
        with patch(
            "pyado.oop.repos.pull_request._pull_request.complete_pull_request"
        ) as mock_complete:
            mock_complete.return_value = completed
            pr.complete("deadbeef")
        assert pr._info is completed

    def test_abandon_delegates(self) -> None:
        pr = _make_pr()
        abandoned = _pr_created()
        abandoned.status = PullRequestStatus.ABANDONED
        with patch(
            "pyado.oop.repos.pull_request._pull_request.abandon_pull_request"
        ) as mock_abandon:
            mock_abandon.return_value = abandoned
            pr.abandon()
        mock_abandon.assert_called_once_with(pr.api_call)

    def test_abandon_updates_info(self) -> None:
        pr = _make_pr()
        abandoned = _pr_created()
        abandoned.status = PullRequestStatus.ABANDONED
        with patch(
            "pyado.oop.repos.pull_request._pull_request.abandon_pull_request"
        ) as mock_abandon:
            mock_abandon.return_value = abandoned
            pr.abandon()
        assert pr._info is abandoned

    def test_set_work_item_refs_delegates(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.repos.pull_request._pull_request.update_pull_request_work_item_refs"
        ) as mock_update:
            pr.set_work_item_refs([10, 20])
        mock_update.assert_called_once_with(pr.api_call, [10, 20])

    def test_add_work_item_ref_appends_when_not_present(self) -> None:
        pr = _make_pr()
        with (
            patch(
                "pyado.oop.repos.pull_request._pull_request.iter_pull_request_work_item_ids"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.pull_request._pull_request.update_pull_request_work_item_refs"
            ) as mock_update,
        ):
            mock_iter.return_value = iter([10])
            pr.add_work_item_ref(20)
        mock_update.assert_called_once_with(pr.api_call, [10, 20])

    def test_add_work_item_ref_noop_when_already_present(self) -> None:
        pr = _make_pr()
        with (
            patch(
                "pyado.oop.repos.pull_request._pull_request.iter_pull_request_work_item_ids"
            ) as mock_iter,
            patch(
                "pyado.oop.repos.pull_request._pull_request.update_pull_request_work_item_refs"
            ) as mock_update,
        ):
            mock_iter.return_value = iter([10, 20])
            pr.add_work_item_ref(20)
        mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# OOP PullRequestRefreshWithExpand tests
# ---------------------------------------------------------------------------


class TestPullRequestRefreshWithExpand:
    def test_refresh_with_expand_updates_stored_expand(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_details"
        ) as mock_get:
            mock_get.return_value = _pr_created()
            pr.refresh(expand="reviewers")
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = pr.info
        assert pr._expand == "reviewers"
        assert mock_get.call_args.kwargs.get("expand") == "reviewers"


# ---------------------------------------------------------------------------
# OOP PullRequestSyncLabels tests
# ---------------------------------------------------------------------------


class TestPullRequestSyncTags:
    def test_sync_tags_removes_tags_not_in_desired(self) -> None:
        pr = _make_pr()
        with (
            patch(
                "pyado.oop.repos.pull_request._pull_request.get_pull_request_tags"
            ) as mock_tags,
            patch(
                "pyado.oop.repos.pull_request.raw.delete_pull_request_label"
            ) as mock_delete,
            patch("pyado.oop.repos.pull_request.raw.post_pull_request_label"),
        ):
            mock_tags.return_value = ["old-tag"]
            pr.sync_tags({"new-tag"})
        mock_delete.assert_called_once()

    def test_sync_tags_uses_cached_tags_when_expand_set(self) -> None:
        repo = _make_repo()
        api_call = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{OOP_REPO_ID}/pullrequests/42"
        )
        info = _pr_list_item(42)
        info.labels = [PullRequestLabel(name="cached-tag")]
        pr = PullRequest(repo, api_call, info, expand="labels")
        with (
            patch(
                "pyado.oop.repos.pull_request.raw.post_pull_request_label"
            ) as mock_add,
            patch(
                "pyado.oop.repos.pull_request.raw.delete_pull_request_label"
            ) as mock_remove,
        ):
            pr.sync_tags({"cached-tag", "new-tag"})
        mock_add.assert_called_once_with(api_call, "new-tag")
        mock_remove.assert_not_called()

    def test_sync_tags_noop_when_already_in_sync(self) -> None:
        pr = _make_pr()
        with (
            patch(
                "pyado.oop.repos.pull_request._pull_request.get_pull_request_tags"
            ) as mock_tags,
            patch(
                "pyado.oop.repos.pull_request.raw.post_pull_request_label"
            ) as mock_add,
            patch(
                "pyado.oop.repos.pull_request.raw.delete_pull_request_label"
            ) as mock_remove,
        ):
            mock_tags.return_value = ["foo"]
            pr.sync_tags({"foo"})
        mock_add.assert_not_called()
        mock_remove.assert_not_called()


# ---------------------------------------------------------------------------
# OOP PullRequestGetThread tests
# ---------------------------------------------------------------------------


class TestPullRequestGetThread:
    def test_delegates_to_raw(self) -> None:
        pr = _make_pr()
        thread = PullRequestThreadResponse.model_validate(
            {
                "id": 7,
                "status": "active",
                "comments": [],
            }
        )
        with patch(
            "pyado.oop.repos.pull_request.raw.get_pull_request_thread"
        ) as mock_get:
            mock_get.return_value = thread
            result = pr.get_thread(7)
        mock_get.assert_called_once_with(pr.api_call, 7)
        assert result.id == 7


# ---------------------------------------------------------------------------
# OOP PullRequestIterWorkItems tests
# ---------------------------------------------------------------------------


class TestPullRequestIterWorkItems:
    def test_yields_work_items(self) -> None:
        pr = _make_pr()
        wi_a = _make_wi(10)
        wi_b = _make_wi(20)
        with (
            patch(
                "pyado.oop.repos.pull_request._pull_request.iter_pull_request_work_item_ids"
            ) as mock_ids,
            patch("pyado.oop.project.raw.post_work_items_batch") as mock_batch,
            patch("pyado.oop.project.raw.get_work_item_api_call") as mock_api,
        ):
            mock_ids.return_value = iter([10, 20])
            mock_batch.return_value = [wi_a.info, wi_b.info]
            mock_api.side_effect = lambda _call, _id: _api_call()
            result = list(pr.iter_work_items())
        assert len(result) == 2
        mock_ids.assert_called_once_with(pr.api_call)

    def test_yields_nothing_when_no_linked_items(self) -> None:
        pr = _make_pr()
        with patch(
            "pyado.oop.repos.pull_request._pull_request.iter_pull_request_work_item_ids"
        ) as mock_ids:
            mock_ids.return_value = iter([])
            result = list(pr.iter_work_items())
        assert result == []


class TestPullRequestListMethods:
    def test_list_threads_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_threads", return_value=iter([])):
            assert pr.list_threads() == []

    def test_list_commits_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_commits", return_value=iter([])):
            assert pr.list_commits() == []

    def test_list_work_item_ids_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_work_item_ids", return_value=iter([])):
            assert pr.list_work_item_ids() == []

    def test_list_work_items_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_work_items", return_value=iter([])):
            assert pr.list_work_items() == []

    def test_list_iterations_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_iterations", return_value=iter([])):
            assert pr.list_iterations() == []

    def test_list_files_changed_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_files_changed", return_value=iter([])):
            assert pr.list_files_changed() == []

    def test_list_statuses_delegates(self) -> None:
        pr = _make_pr()
        with patch.object(pr, "iter_statuses", return_value=iter([])):
            assert pr.list_statuses() == []
