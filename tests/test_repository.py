"""Tests for pyado.repository module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado import (
    GIT_SECURITY_NAMESPACE_ID,
    AccessControlList,
    ApiCall,
    BranchStatistics,
    GitCommitChange,
    GitCommitRef,
    GitCommitSearchCriteria,
    GitRef,
    GitRefFilter,
    RepositoryInfo,
    create_branch,
    delete_branch,
    get_commit_by_id,
    get_file_content_at_branch,
    get_file_content_at_commit,
    get_git_acl,
    get_last_commit_touching_file,
    get_repository_api_call,
    get_repository_commits,
    get_repository_info,
    get_repository_statistics,
    iter_commit_diff,
    iter_refs,
    iter_repository_details,
    make_git_acl_token,
)
from tests.conftest import _make_mock_response


def make_repository_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid RepositoryInfo dict.

    Returns:
        A dict with all required RepositoryInfo fields populated.
    """
    repo: dict[str, Any] = {
        "id": str(uuid4()),
        "name": "my-repo",
        "project": {
            "id": str(uuid4()),
            "name": "My Project",
            "description": "desc",
            "state": "wellFormed",
            "revision": 1,
            "visibility": "private",
            "lastUpdateTime": "2024-01-01T00:00:00+00:00",
        },
        "defaultBranch": "refs/heads/main",
        "size": 1024,
        "remoteUrl": "https://dev.azure.com/org/proj/_git/my-repo",
        "sshUrl": "git@ssh.dev.azure.com:v3/org/proj/my-repo",
        "webUrl": "https://dev.azure.com/org/proj/_git/my-repo",
        "isDisabled": False,
        "isInMaintenance": False,
    }
    repo.update(overrides)
    return repo


class TestIterRepositoryDetails:
    """Tests for iter_repository_details."""

    @staticmethod
    def test_yields_repository_info_objects(api_call: ApiCall) -> None:
        """Yields RepositoryInfo objects from the API response."""
        repo = make_repository_dict()
        mock_response = _make_mock_response({"value": [repo]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert len(result) == 1
        assert isinstance(result[0], RepositoryInfo)
        assert result[0].name == "my-repo"

    @staticmethod
    def test_yields_nothing_for_empty_value(api_call: ApiCall) -> None:
        """Empty value list yields no repositories."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert result == []

    @staticmethod
    def test_repository_with_no_default_branch(api_call: ApiCall) -> None:
        """Repository without a default branch is parsed correctly."""
        repo = make_repository_dict(defaultBranch=None)
        mock_response = _make_mock_response({"value": [repo]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert result[0].default_branch is None

    @staticmethod
    def test_multiple_repositories(api_call: ApiCall) -> None:
        """Multiple repositories are all yielded."""
        repos = [
            make_repository_dict(name="repo-a"),
            make_repository_dict(name="repo-b"),
        ]
        mock_response = _make_mock_response({"value": repos})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert len(result) == 2
        assert result[0].name == "repo-a"
        assert result[1].name == "repo-b"


def test_get_repository_info_returns_repository_info(api_call: ApiCall) -> None:
    """get_repository_info returns a RepositoryInfo for a repository-level call."""
    data = make_repository_dict(name="my-repo")
    mock_response = _make_mock_response(data)
    repo_api_call = get_repository_api_call(api_call, uuid4())
    with patch.object(requests.Session, "request", return_value=mock_response):
        result = get_repository_info(repo_api_call)
    assert isinstance(result, RepositoryInfo)
    assert result.name == "my-repo"


REPO_ID = uuid4()
COMMIT_SHA = "abc123def456"


@pytest.fixture
def repo_api_call(api_call: ApiCall) -> ApiCall:
    """Return a repository-level ApiCall.

    Returns:
        A repository-level ApiCall for testing.
    """
    return get_repository_api_call(api_call, REPO_ID)


def _make_raw_mock_response(content: bytes, *, raise_error: bool = False) -> MagicMock:
    """Create a mock response for raw (non-JSON) GET requests.

    Returns:
        A MagicMock that returns raw bytes or raises HTTPError.
    """
    mock = MagicMock(spec=requests.Response)
    mock.content = content
    if raise_error:
        mock.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock.json.return_value = {"message": "Not found"}
    else:
        mock.raise_for_status.return_value = None
    return mock


class TestGetFileContentAtCommit:
    """Tests for get_file_content_at_commit."""

    @staticmethod
    def test_returns_file_content_on_success(repo_api_call: ApiCall) -> None:
        """Returns decoded file content when the API call succeeds."""
        mock_response = _make_raw_mock_response(b"print('hello')")
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_file_content_at_commit(
                repo_api_call, "/src/foo.py", COMMIT_SHA
            )
        assert result == "print('hello')"

    @staticmethod
    def test_returns_empty_string_on_runtime_error(repo_api_call: ApiCall) -> None:
        """Returns an empty string when the API raises RuntimeError (e.g. 404)."""
        mock_response = _make_raw_mock_response(b"", raise_error=True)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_file_content_at_commit(
                repo_api_call, "/missing.py", COMMIT_SHA
            )
        assert not result

    @staticmethod
    def test_returns_empty_string_when_content_is_empty(repo_api_call: ApiCall) -> None:
        """Returns an empty string when the response has empty content."""
        mock_response = _make_raw_mock_response(b"")
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_file_content_at_commit(repo_api_call, "/empty.py", COMMIT_SHA)
        assert not result


def _make_commit_change(path: str, *, is_folder: bool = False) -> dict[str, Any]:
    """Build a minimal commit change dict.

    Returns:
        A dict representing a single GitCommitChange entry.
    """
    return {
        "changeType": "edit",
        "item": {"path": path, "isFolder": is_folder},
    }


class TestIterCommitDiff:
    """Tests for iter_commit_diff."""

    @staticmethod
    def test_yields_file_changes(repo_api_call: ApiCall) -> None:
        """Yields GitCommitChange objects for file changes."""
        response_data = {
            "changes": [_make_commit_change("/src/foo.py")],
            "allChangesIncluded": True,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_commit_diff(repo_api_call, "base123", "target456"))
        assert len(result) == 1
        assert isinstance(result[0], GitCommitChange)
        assert result[0].item.path == "/src/foo.py"

    @staticmethod
    def test_excludes_folder_entries(repo_api_call: ApiCall) -> None:
        """Folder changes are excluded from the results."""
        response_data = {
            "changes": [
                _make_commit_change("/src/", is_folder=True),
                _make_commit_change("/src/bar.py"),
            ],
            "allChangesIncluded": True,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_commit_diff(repo_api_call, "base123", "target456"))
        assert len(result) == 1
        assert result[0].item.path == "/src/bar.py"

    @staticmethod
    def test_paginates_when_not_all_changes_included(repo_api_call: ApiCall) -> None:
        """Fetches additional pages when allChangesIncluded is False."""
        first_page = {
            "changes": [_make_commit_change(f"/src/file{idx}.py") for idx in range(5)],
            "allChangesIncluded": False,
        }
        second_page = {
            "changes": [_make_commit_change("/src/last.py")],
            "allChangesIncluded": True,
        }
        mock_first = _make_mock_response(first_page)
        mock_second = _make_mock_response(second_page)
        with patch.object(
            requests.Session, "request", side_effect=[mock_first, mock_second]
        ):
            result = list(iter_commit_diff(repo_api_call, "base123", "target456"))
        assert len(result) == 6
        assert result[-1].item.path == "/src/last.py"

    @staticmethod
    def test_yields_nothing_for_empty_changes(repo_api_call: ApiCall) -> None:
        """Empty changes list yields no results."""
        response_data = {"changes": [], "allChangesIncluded": True}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_commit_diff(repo_api_call, "base123", "target456"))
        assert result == []


class TestGetLastCommitTouchingFile:
    """Tests for get_last_commit_touching_file."""

    @staticmethod
    def test_returns_commit_id_when_found(repo_api_call: ApiCall) -> None:
        """Returns the commit ID of the most recent commit touching the file."""
        response_data = {"value": [{"commitId": "found123"}]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_last_commit_touching_file(
                repo_api_call, "/src/foo.py", "before456"
            )
        assert result == "found123"

    @staticmethod
    def test_returns_before_commit_when_no_result(repo_api_call: ApiCall) -> None:
        """Falls back to before_commit when no commits are found."""
        response_data: dict[str, Any] = {"value": []}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_last_commit_touching_file(
                repo_api_call, "/missing.py", "before456"
            )
        assert result == "before456"

    @staticmethod
    def test_returns_before_commit_on_api_error(repo_api_call: ApiCall) -> None:
        """Falls back to before_commit when the API raises a RuntimeError."""
        with patch.object(requests.Session, "request", side_effect=RuntimeError("404")):
            result = get_last_commit_touching_file(
                repo_api_call, "/missing.py", "before456"
            )
        assert result == "before456"


class TestIterRefs:
    """Tests for iter_refs."""

    @staticmethod
    def test_yields_all_refs(repo_api_call: ApiCall) -> None:
        """Yields GitRef objects for each ref in the response."""
        response_data = {
            "value": [
                {"name": "refs/heads/main", "objectId": "sha1"},
                {"name": "refs/heads/dev", "objectId": "sha2"},
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        assert len(result) == 2
        assert isinstance(result[0], GitRef)
        assert result[0].name == "refs/heads/main"
        assert result[0].object_id == "sha1"

    @staticmethod
    def test_passes_name_filter(repo_api_call: ApiCall) -> None:
        """Passes the filter query parameter when name_filter is provided."""
        response_data = {"value": [{"name": "refs/heads/main", "objectId": "sha1"}]}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_refs(repo_api_call, GitRefFilter(name_filter="heads/main")))
        called_params = mock_req.call_args.kwargs["params"]
        assert called_params.get("filter") == "heads/main"

    @staticmethod
    def test_passes_name_contains(repo_api_call: ApiCall) -> None:
        """Passes the filterContains query parameter when name_contains is provided."""
        response_data: dict[str, Any] = {"value": []}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_refs(repo_api_call, GitRefFilter(name_contains="feature")))
        called_params = mock_req.call_args.kwargs["params"]
        assert called_params.get("filterContains") == "feature"


class TestCreateBranch:
    """Tests for create_branch."""

    @staticmethod
    def test_posts_correct_payload(repo_api_call: ApiCall) -> None:
        """Posts a ref update with newObjectId set and oldObjectId as zero SHA."""
        mock_response = _make_mock_response(None)
        mock_response.content = b""
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_branch(repo_api_call, "feature/abc", "deadbeef")
        body = mock_req.call_args.kwargs["json"]
        assert body[0]["name"] == "refs/heads/feature/abc"
        assert body[0]["newObjectId"] == "deadbeef"
        assert body[0]["oldObjectId"] == "0" * 40

    @staticmethod
    def test_accepts_full_refs_prefix(repo_api_call: ApiCall) -> None:
        """Does not double-add refs/heads/ when already present."""
        mock_response = _make_mock_response(None)
        mock_response.content = b""
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_branch(repo_api_call, "refs/heads/feature/abc", "deadbeef")
        body = mock_req.call_args.kwargs["json"]
        assert body[0]["name"] == "refs/heads/feature/abc"


class TestDeleteBranch:
    """Tests for delete_branch."""

    @staticmethod
    def test_posts_zero_new_object_id(repo_api_call: ApiCall) -> None:
        """Posts a ref update with newObjectId as zero SHA to delete the branch."""
        mock_response = _make_mock_response(None)
        mock_response.content = b""
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_branch(repo_api_call, "feature/abc", "deadbeef")
        body = mock_req.call_args.kwargs["json"]
        assert body[0]["name"] == "refs/heads/feature/abc"
        assert body[0]["newObjectId"] == "0" * 40
        assert body[0]["oldObjectId"] == "deadbeef"


class TestGetFileContentAtBranch:
    """Tests for get_file_content_at_branch."""

    @staticmethod
    def test_returns_file_content(repo_api_call: ApiCall) -> None:
        """Returns decoded file content from the branch tip."""
        mock_response = _make_raw_mock_response(b'{"key": "value"}')
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_file_content_at_branch(repo_api_call, "/config/x.json", "main")
        assert result == '{"key": "value"}'

    @staticmethod
    def test_strips_refs_heads_prefix(repo_api_call: ApiCall) -> None:
        """Strips the refs/heads/ prefix before passing to the API."""
        mock_response = _make_raw_mock_response(b"content")
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_file_content_at_branch(repo_api_call, "/f.txt", "refs/heads/main")
        called_params = mock_req.call_args.kwargs["params"]
        assert called_params["versionDescriptor.version"] == "main"

    @staticmethod
    def test_returns_empty_string_on_error(repo_api_call: ApiCall) -> None:
        """Returns empty string when the file does not exist on the branch."""
        mock_response = _make_raw_mock_response(b"", raise_error=True)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_file_content_at_branch(repo_api_call, "/missing.txt", "main")
        assert not result


class TestGetRepositoryCommits:
    """Tests for get_repository_commits."""

    @staticmethod
    def test_returns_commits_with_all_params(repo_api_call: ApiCall) -> None:
        """Returns GitCommitRef list when all optional parameters are provided."""
        response_data = {"value": [{"commitId": "abc123"}]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(
                repo_api_call,
                GitCommitSearchCriteria(
                    item_path="/src/foo.py",
                    item_version="abc123",
                    item_version_type="commit",
                    top=1,
                ),
            )
        assert len(result) == 1
        assert isinstance(result[0], GitCommitRef)
        assert result[0].commit_id == "abc123"

    @staticmethod
    def test_returns_commits_with_no_params(repo_api_call: ApiCall) -> None:
        """Returns GitCommitRef list when no optional parameters are provided."""
        response_data = {"value": [{"commitId": "def456"}]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(repo_api_call)
        assert len(result) == 1
        assert result[0].commit_id == "def456"


PROJECT_ID = uuid4()
REPO_ID = uuid4()


class TestMakeGitAclToken:
    """Tests for make_git_acl_token."""

    @staticmethod
    def test_project_only_token() -> None:
        """Returns repoV2/{project_id} when no repo_id is given."""
        token = make_git_acl_token(PROJECT_ID)
        assert token == f"repoV2/{PROJECT_ID}"

    @staticmethod
    def test_project_and_repo_token() -> None:
        """Returns repoV2/{project}/{repo} when repo_id is given."""
        token = make_git_acl_token(PROJECT_ID, REPO_ID)
        assert token == f"repoV2/{PROJECT_ID}/{REPO_ID}"

    @staticmethod
    def test_branch_token() -> None:
        """Returns token with refs/heads/ and encoded branch name."""
        token = make_git_acl_token(PROJECT_ID, REPO_ID, branch="main")
        assert token == f"repoV2/{PROJECT_ID}/{REPO_ID}/refs/heads/main"

    @staticmethod
    def test_branch_token_strips_refs_heads_prefix() -> None:
        """Strips refs/heads/ prefix before encoding."""
        token = make_git_acl_token(PROJECT_ID, REPO_ID, branch="refs/heads/main")
        assert token == f"repoV2/{PROJECT_ID}/{REPO_ID}/refs/heads/main"

    @staticmethod
    def test_branch_slash_encoded() -> None:
        """Encodes forward slashes in branch names as ^3."""
        token = make_git_acl_token(PROJECT_ID, REPO_ID, branch="feature/my-branch")
        assert token == f"repoV2/{PROJECT_ID}/{REPO_ID}/refs/heads/feature^3my-branch"


class TestGetGitAcl:
    """Tests for get_git_acl."""

    @staticmethod
    def test_returns_acl_list(api_call: ApiCall) -> None:
        """Returns a list of AccessControlList objects."""
        response_data = {
            "value": [
                {
                    "token": f"repoV2/{PROJECT_ID}/{REPO_ID}",
                    "entries": {},
                }
            ]
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_git_acl(api_call, PROJECT_ID, REPO_ID)
        assert isinstance(result, list)
        assert isinstance(result[0], AccessControlList)

    @staticmethod
    def test_url_contains_security_namespace(api_call: ApiCall) -> None:
        """Request URL path contains the git security namespace GUID."""
        response_data = {"value": [{"token": f"repoV2/{PROJECT_ID}", "entries": {}}]}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_git_acl(api_call, PROJECT_ID)
        call_kwargs = mock_req.call_args[1]
        url_called = call_kwargs["url"]
        params = call_kwargs.get("params", {})
        assert GIT_SECURITY_NAMESPACE_ID in url_called or any(
            GIT_SECURITY_NAMESPACE_ID in str(v) for v in params.values()
        )


class TestGetCommitById:
    """Tests for get_commit_by_id."""

    @staticmethod
    def test_returns_git_commit_ref(api_call: ApiCall) -> None:
        """Returns a GitCommitRef parsed from the API response."""
        response_data = {
            "commitId": "abc123",
            "comment": "Test commit",
            "commentTruncated": False,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_commit_by_id(api_call, "abc123")
        assert isinstance(result, GitCommitRef)
        assert result.commit_id == "abc123"


class TestGetRepositoryStatistics:
    """Tests for get_repository_statistics."""

    @staticmethod
    def test_returns_branch_statistics(api_call: ApiCall) -> None:
        """Returns a BranchStatistics parsed from the API response."""
        response_data = {
            "name": "main",
            "aheadCount": 3,
            "behindCount": 1,
            "commit": {
                "commitId": "abc123",
                "comment": "Latest commit",
                "commentTruncated": False,
            },
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_statistics(api_call, "main")
        assert isinstance(result, BranchStatistics)
        assert result.name == "main"
        assert result.ahead_count == 3
        assert result.behind_count == 1

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request to the stats/branches endpoint."""
        response_data = {"name": "main", "aheadCount": 0, "behindCount": 0}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_repository_statistics(api_call, "main")
        assert mock_req.call_args.args[0] == "GET"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "stats" in url
        assert "branches" in url

    @staticmethod
    def test_passes_branch_name_as_param(api_call: ApiCall) -> None:
        """Passes the branch name as a query parameter."""
        response_data = {"name": "feature/x", "aheadCount": 5, "behindCount": 0}
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_repository_statistics(api_call, "feature/x")
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("name") == "feature/x"
