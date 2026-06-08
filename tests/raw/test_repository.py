"""Tests for pyado.repository module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
import requests

from pyado.oop.repos._git import (
    create_branch,
    delete_branch,
    get_file_content_at_branch,
    get_file_content_at_commit,
    get_last_commit_touching_file,
    iter_commit_diff,
)
from pyado.raw import (
    GIT_SECURITY_NAMESPACE_ID,
    ZERO_SHA,
    AccessControlList,
    AnnotatedTagInfo,
    AnnotatedTagRequest,
    ApiCall,
    BranchStatistics,
    GitCommitChange,
    GitCommitRef,
    GitCommitSearchCriteria,
    GitItem,
    GitRef,
    GitRefFilter,
    RecursionLevel,
    RepositoryInfo,
    VersionDescriptorType,
    create_tag,
    delete_tag,
    get_annotated_tag,
    get_commit_by_id,
    get_git_acl,
    get_repository_api_call,
    get_repository_commits,
    get_repository_info,
    get_repository_item,
    get_repository_statistics,
    iter_refs,
    iter_repository_details,
    iter_repository_items,
    iter_tags,
    list_refs,
    list_repository_details,
    list_repository_items,
    list_tags,
    make_git_acl_token,
    post_annotated_tag,
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
COMMIT_SHA = "abc123def456"  # pragma: allowlist secret


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
        mock.status_code = 404
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

    @staticmethod
    def test_accepts_composite_change_type(repo_api_call: ApiCall) -> None:
        """Composite change types like 'delete, sourceRename' are accepted."""
        response_data = {
            "changes": [
                {"changeType": "delete, sourceRename", "item": {"path": "/src/old.py"}}
            ],
            "allChangesIncluded": True,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_commit_diff(repo_api_call, "base123", "target456"))
        assert len(result) == 1
        assert result[0].change_type == "delete, sourceRename"


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
        """Falls back to before_commit when the API raises AzureDevopsHttpError."""
        mock_response = _make_raw_mock_response(b"", raise_error=True)
        with patch.object(requests.Session, "request", return_value=mock_response):
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

    @staticmethod
    def test_search_criteria_forwarded_as_params(api_call: ApiCall) -> None:
        """Non-None search criteria fields are forwarded as searchCriteria.* params."""
        response_data = {
            "commitId": "abc123",
            "comment": "Test commit",
            "commentTruncated": False,
        }
        mock_response = _make_mock_response(response_data)
        criteria = GitCommitSearchCriteria(item_path="/src/foo.py")
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_commit_by_id(api_call, "abc123", search_criteria=criteria)
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "searchCriteria.itemPath" in params
        assert params["searchCriteria.itemPath"] == "/src/foo.py"

    @staticmethod
    def test_no_params_when_search_criteria_is_none(api_call: ApiCall) -> None:
        """When search_criteria is None, no searchCriteria params are sent."""
        response_data = {
            "commitId": "abc123",
            "comment": "Test commit",
            "commentTruncated": False,
        }
        mock_response = _make_mock_response(response_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_commit_by_id(api_call, "abc123")
        params = mock_req.call_args.kwargs.get("params") or {}
        assert not any(key.startswith("searchCriteria") for key in params)


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


def _make_ref_dict(
    name: str = "refs/tags/v1.0", object_id: str = "abc123"
) -> dict[str, str]:
    """Create a minimal valid GitRef dict."""
    return {"name": name, "objectId": object_id}


class TestIterTags:
    """Tests for iter_tags."""

    @staticmethod
    def test_yields_tag_refs(api_call: ApiCall) -> None:
        """Yields GitRef objects for tags."""
        response_data = {"value": [_make_ref_dict("refs/tags/v1.0")]}
        mock_response = _make_mock_response(response_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_tags(api_call))
        assert len(result) == 1
        assert isinstance(result[0], GitRef)

    @staticmethod
    def test_passes_tags_filter(api_call: ApiCall) -> None:
        """Passes the 'tags/' name filter to the refs endpoint."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_tags(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("filter") == "tags/"

    @staticmethod
    def test_sends_get_request(api_call: ApiCall) -> None:
        """Sends a GET request."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_tags(api_call))
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_url_contains_refs(api_call: ApiCall) -> None:
        """Request URL contains the 'refs' path segment."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_tags(api_call))
        url = mock_req.call_args.kwargs.get("url", "")
        assert "refs" in url


class TestCreateTag:
    """Tests for create_tag."""

    @staticmethod
    def test_posts_to_refs_endpoint(api_call: ApiCall) -> None:
        """POSTs to the refs endpoint."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_tag(api_call, "v1.0", "abc123")
        assert mock_req.call_args.args[0] == "POST"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "refs" in url

    @staticmethod
    def test_uses_refs_tags_prefix(api_call: ApiCall) -> None:
        """The ref name in the request body uses refs/tags/ prefix."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_tag(api_call, "v1.0", "abc123")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["name"] == "refs/tags/v1.0"

    @staticmethod
    def test_preserves_full_refs_tags_name(api_call: ApiCall) -> None:
        """Leaves ref name unchanged when refs/tags/ prefix is already present."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_tag(api_call, "refs/tags/v2.0", "deadbeef")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["name"] == "refs/tags/v2.0"

    @staticmethod
    def test_uses_zero_sha_as_old_object_id(api_call: ApiCall) -> None:
        """Sets oldObjectId to ZERO_SHA for new tag creation."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_tag(api_call, "v1.0", "abc123")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["oldObjectId"] == ZERO_SHA


class TestDeleteTag:
    """Tests for delete_tag."""

    @staticmethod
    def test_posts_to_refs_endpoint(api_call: ApiCall) -> None:
        """POSTs to the refs endpoint."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_tag(api_call, "v1.0", "abc123")
        assert mock_req.call_args.args[0] == "POST"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "refs" in url

    @staticmethod
    def test_uses_zero_sha_as_new_object_id(api_call: ApiCall) -> None:
        """Sets newObjectId to ZERO_SHA to delete the tag."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_tag(api_call, "v1.0", "abc123")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["newObjectId"] == ZERO_SHA

    @staticmethod
    def test_uses_commit_id_as_old_object_id(api_call: ApiCall) -> None:
        """Sets oldObjectId to the provided commit_id."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_tag(api_call, "v1.0", "abc123")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["oldObjectId"] == "abc123"

    @staticmethod
    def test_uses_refs_tags_prefix(api_call: ApiCall) -> None:
        """The ref name in the request body uses refs/tags/ prefix."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            delete_tag(api_call, "v1.0", "abc123")
        body = mock_req.call_args.kwargs.get("json") or []
        assert body[0]["name"] == "refs/tags/v1.0"


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

_REPO_MAIN = {
    "id": "452ec40a-3193-4a54-ae89-71105e503a67",
    "name": "main",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
    ),
    "project": _SMOKE_PROJECT,
    "defaultBranch": "refs/heads/main",
    "size": 201,
    "remoteUrl": "https://example-org@dev.azure.com/example-org/main/_git/main",
    "sshUrl": "git@ssh.dev.azure.com:v3/example-org/main/main",
    "webUrl": "https://dev.azure.com/example-org/main/_git/main",
    "isDisabled": False,
    "isInMaintenance": False,
}

_REPOSITORIES_SMOKE_RESPONSE = {
    "count": 2,
    "value": [_REPO_MAIN],
}

_COMMIT_ID_1 = "22f23cb2b634ebeff81a61b51c45db4736c581dc"  # pragma: allowlist secret
_COMMIT_ID_2 = "92003447d253defc6365da9f9b164042cf28c9e3"  # pragma: allowlist secret
_OBJECT_ID_MAIN = "a552f5aed0bc38f8c5fb75f3b4c615cc8889f748"  # pragma: allowlist secret
_OBJECT_ID_PR = "2e6ade2719c5756dc50c68c16e01519923b744c9"  # pragma: allowlist secret

_COMMITS_SMOKE_RESPONSE = {
    "count": 3,
    "value": [
        {
            "commitId": _COMMIT_ID_1,
            "author": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:54Z",
            },
            "committer": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:54Z",
            },
            "comment": "Merge pull request 12 from branch into main",
            "changeCounts": {"Add": 1, "Edit": 0, "Delete": 0},
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/commits/22f23cb2b634ebeff81a61b51c45db4736c581dc"
            ),
            "remoteUrl": (
                "https://dev.azure.com/example-org/main/_git/main/commit"
                "/22f23cb2b634ebeff81a61b51c45db4736c581dc"
            ),
        },
        {
            "commitId": _COMMIT_ID_2,
            "author": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:53Z",
            },
            "committer": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:53Z",
            },
            "comment": "[smoke-test] edit file",
            "changeCounts": {"Add": 0, "Edit": 1, "Delete": 0},
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/commits/92003447d253defc6365da9f9b164042cf28c9e3"
            ),
            "remoteUrl": (
                "https://dev.azure.com/example-org/main/_git/main/commit"
                "/92003447d253defc6365da9f9b164042cf28c9e3"
            ),
        },
    ],
}

_REFS_SMOKE_RESPONSE = {
    "value": [
        {
            "name": "refs/heads/main",
            "objectId": _OBJECT_ID_MAIN,
            "creator": _SMOKE_AUTHOR,
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/refs?filter=heads%2Fmain"
            ),
        },
        {
            "name": "refs/pull/2/merge",
            "objectId": _OBJECT_ID_PR,
            "creator": {
                "displayName": "Microsoft.VisualStudio.Services.TFS",
                "url": (
                    "https://spsprod00000.vssps.visualstudio.com"
                    "/A95c5fb98-6980-481f-bc42-8d42fa882692"
                    "/_apis/Identities/d1f6f86c-029a-4245-bb91-433a6aa79987"
                ),
                "_links": {
                    "avatar": {
                        "href": (
                            "https://dev.azure.com/example-org/_apis/GraphProfile"
                            "/MemberAvatars/s2s.MDAwMDAwMDItMDAwMC04ODg4LTgwMDA"
                        )
                    }
                },
                "id": "d1f6f86c-029a-4245-bb91-433a6aa79987",
                "uniqueName": (
                    "d1f6f86c-029a-4245-bb91-433a6aa79987"
                    "@87f26aee-175f-4cd2-bb9d-58e4f543bbcf"
                ),
                "imageUrl": (
                    "https://dev.azure.com/example-org/_api/_common/identityImage"
                    "?id=d1f6f86c-029a-4245-bb91-433a6aa79987"
                ),
                "descriptor": "s2s.MDAwMDAwMDItMDAwMC04ODg4LTgwMDA",
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/refs?filter=pull%2F2%2Fmerge"
            ),
        },
    ],
    "count": 2,
}


class TestSmokeIterRepositoryDetails:
    """iter_repository_details parses real repository response shapes."""

    @staticmethod
    def test_parses_two_repositories(api_call: ApiCall) -> None:
        """Parses a response containing two fully-populated repository objects."""
        mock_response = _make_mock_response(_REPOSITORIES_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert len(result) == 1  # fixture only has one entry
        assert isinstance(result[0], RepositoryInfo)
        assert result[0].name == "main"
        assert result[0].default_branch == "refs/heads/main"
        assert result[0].size == 201

    @staticmethod
    def test_project_fields_parsed_correctly(api_call: ApiCall) -> None:
        """Nested project fields are accessible on the repository object."""
        mock_response = _make_mock_response(_REPOSITORIES_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        repo = result[0]
        assert repo.project.name == "main"
        assert repo.project.state == "wellFormed"


class TestSmokeGetRepositoryCommits:
    """get_repository_commits parses real commit response shapes."""

    @staticmethod
    def test_parses_three_commits(api_call: ApiCall) -> None:
        """Parses a commit list response with changeCounts and full author info."""
        mock_response = _make_mock_response(_COMMITS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(api_call)
        assert len(result) == 2  # fixture has 2 commits
        assert result[0].commit_id == "22f23cb2b634ebeff81a61b51c45db4736c581dc"
        assert result[1].commit_id == "92003447d253defc6365da9f9b164042cf28c9e3"

    @staticmethod
    def test_commit_comment_parsed(api_call: ApiCall) -> None:
        """The commit comment field is populated from the real response."""
        mock_response = _make_mock_response(_COMMITS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(api_call)
        assert result[0].comment is not None
        assert "merge pull request" in result[0].comment.lower()


class TestSmokeIterRefs:
    """iter_refs parses real repository ref response shapes."""

    @staticmethod
    def test_parses_branch_and_pr_merge_refs(api_call: ApiCall) -> None:
        """Parses both a user-created branch ref and a system-created PR merge ref."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        assert len(result) == 2
        assert all(isinstance(ref, GitRef) for ref in result)

    @staticmethod
    def test_branch_ref_name_and_object_id_parsed(api_call: ApiCall) -> None:
        """Branch ref has name and objectId populated."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        branch = result[0]
        assert branch.name == "refs/heads/main"
        assert branch.object_id == "a552f5aed0bc38f8c5fb75f3b4c615cc8889f748"

    @staticmethod
    def test_pr_merge_ref_has_system_creator(api_call: ApiCall) -> None:
        """PR merge ref created by system TFS identity parses without error."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_SMOKE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        pr_merge_ref = result[1]
        assert pr_merge_ref.name == "refs/pull/2/merge"


class TestListRepositoryDetails:
    """Tests for list_repository_details."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_repository_details results."""
        with patch(
            "pyado.raw.repos.git.iter_repository_details", return_value=iter([])
        ):
            result = list_repository_details(api_call)
        assert result == []


class TestListRefs:
    """Tests for list_refs."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_refs results."""
        with patch("pyado.raw.repos.git.iter_refs", return_value=iter([])):
            result = list_refs(api_call)
        assert result == []


class TestListTags:
    """Tests for list_tags."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_tags results."""
        with patch("pyado.raw.repos.git.iter_tags", return_value=iter([])):
            result = list_tags(api_call)
        assert result == []


def make_git_item_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid GitItem dict."""
    item: dict[str, Any] = {
        "objectId": "a" * 40,
        "gitObjectType": "blob",
        "path": "/README.md",
        "isFolder": False,
        "isSymLink": False,
    }
    item.update(overrides)
    return item


class TestIterRepositoryItems:
    """Tests for iter_repository_items."""

    @staticmethod
    def test_yields_git_item_objects(api_call: ApiCall) -> None:
        """Yields GitItem objects from the API response."""
        item = make_git_item_dict()
        mock_response = _make_mock_response({"value": [item]})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_items(api_call))
        assert len(result) == 1
        assert isinstance(result[0], GitItem)
        assert result[0].path == "/README.md"

    @staticmethod
    def test_sends_get_to_items_endpoint(api_call: ApiCall) -> None:
        """Sends a GET request to the items endpoint."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call))
        url = mock_req.call_args.kwargs.get("url", "")
        assert "items" in url
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_scope_path_sent_as_parameter(api_call: ApiCall) -> None:
        """scope_path is forwarded as scopePath query parameter."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call, "/src"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("scopePath") == "/src"

    @staticmethod
    def test_branch_adds_version_descriptor_params(api_call: ApiCall) -> None:
        """When branch is set, version descriptor parameters are included."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call, branch="main"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("versionDescriptor.version") == "main"
        assert params.get("versionDescriptor.versionType") == "branch"

    @staticmethod
    def test_full_ref_branch_strips_prefix(api_call: ApiCall) -> None:
        """refs/heads/ prefix is stripped from the branch name."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call, branch="refs/heads/main"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("versionDescriptor.version") == "main"

    @staticmethod
    def test_no_branch_omits_version_descriptor(api_call: ApiCall) -> None:
        """When branch is None, no version descriptor parameters are added."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "versionDescriptor.version" not in params

    @staticmethod
    def test_recursion_level_is_sent(api_call: ApiCall) -> None:
        """RecursionLevel is forwarded as a query parameter."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call, recursion_level=RecursionLevel.FULL))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("recursionLevel") == "full"


class TestListRepositoryItems:
    """Tests for list_repository_items."""

    @staticmethod
    def test_returns_list(api_call: ApiCall) -> None:
        """Returns a list wrapping iter_repository_items results."""
        with patch("pyado.raw.repos.git.iter_repository_items", return_value=iter([])):
            result = list_repository_items(api_call)
        assert result == []


class TestIterRepositoryItemsByVersion:
    """Tests for iter_repository_items version/version_type parameters."""

    @staticmethod
    def test_commit_version_adds_version_descriptor_params(api_call: ApiCall) -> None:
        """Version + version_type=COMMIT sends versionDescriptor params."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_repository_items(
                    api_call,
                    version="abc123",
                    version_type=VersionDescriptorType.COMMIT,
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("versionDescriptor.version") == "abc123"
        assert params.get("versionDescriptor.versionType") == "commit"

    @staticmethod
    def test_tag_version_adds_version_descriptor_params(api_call: ApiCall) -> None:
        """Version + version_type=TAG sends versionDescriptor params."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(
                iter_repository_items(
                    api_call,
                    version="v1.0",
                    version_type=VersionDescriptorType.TAG,
                )
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("versionDescriptor.version") == "v1.0"
        assert params.get("versionDescriptor.versionType") == "tag"

    @staticmethod
    def test_version_without_version_type_omits_descriptor(api_call: ApiCall) -> None:
        """Version alone (no version_type) does not add version descriptor params."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_repository_items(api_call, version="abc123"))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert "versionDescriptor.version" not in params


class TestGetRepositoryItem:
    """Tests for get_repository_item."""

    @staticmethod
    def test_returns_git_item_on_success(repo_api_call: ApiCall) -> None:
        """Returns a GitItem when the file exists."""
        item_data = {
            "objectId": "a" * 40,
            "gitObjectType": "blob",
            "path": "/README.md",
            "isFolder": False,
            "isSymLink": False,
        }
        mock_response = _make_mock_response(item_data)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_item(
                repo_api_call,
                "/README.md",
                "main",
                VersionDescriptorType.BRANCH,
            )
        assert isinstance(result, GitItem)
        assert result.path == "/README.md"

    @staticmethod
    def test_returns_none_on_404(repo_api_call: ApiCall) -> None:
        """Returns None when the API responds with 404."""
        mock_response = _make_raw_mock_response(b"", raise_error=True)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_item(
                repo_api_call,
                "/missing.py",
                "main",
                VersionDescriptorType.BRANCH,
            )
        assert result is None

    @staticmethod
    def test_passes_version_descriptor_parameters(repo_api_call: ApiCall) -> None:
        """Passes path and version descriptor as query parameters."""
        item_data = {
            "objectId": "b" * 40,
            "gitObjectType": "blob",
            "path": "/src/foo.py",
            "isFolder": False,
            "isSymLink": False,
        }
        mock_response = _make_mock_response(item_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_repository_item(
                repo_api_call,
                "/src/foo.py",
                "abc123",
                VersionDescriptorType.COMMIT,
            )
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("path") == "/src/foo.py"
        assert params.get("versionDescriptor.version") == "abc123"
        assert params.get("versionDescriptor.versionType") == "commit"

    @staticmethod
    def test_sends_get_to_items_endpoint(repo_api_call: ApiCall) -> None:
        """Sends a GET request to the items endpoint."""
        item_data = {
            "objectId": "c" * 40,
            "gitObjectType": "blob",
            "path": "/f.txt",
            "isFolder": False,
            "isSymLink": False,
        }
        mock_response = _make_mock_response(item_data)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            get_repository_item(
                repo_api_call,
                "/f.txt",
                "main",
                VersionDescriptorType.BRANCH,
            )
        assert mock_req.call_args.args[0] == "GET"
        url = mock_req.call_args.kwargs.get("url", "")
        assert "items" in url


class TestAnnotatedTagRequest:
    def test_from_commit_builds_request(self) -> None:
        req = AnnotatedTagRequest.from_commit("v1.0", "abc123sha", "Release 1.0")
        assert req.name == "v1.0"
        assert req.message == "Release 1.0"
        assert req.tagged_object.object_id == "abc123sha"
        assert req.tagged_object.object_type == "commit"


class TestPostAnnotatedTag:
    def test_returns_annotated_tag_info(self, api_call: ApiCall) -> None:
        payload = {
            "name": "v1.0",
            "objectId": "deadbeef",
            "message": "Release 1.0",
            "taggedObject": {"objectId": "abc123", "objectType": "commit"},
        }
        mock_resp = _make_mock_response(payload)
        req = AnnotatedTagRequest.from_commit("v1.0", "abc123", "Release 1.0")
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_annotated_tag(api_call, req)
        assert isinstance(result, AnnotatedTagInfo)
        assert result.name == "v1.0"


class TestGetAnnotatedTag:
    def test_returns_annotated_tag_info(self, api_call: ApiCall) -> None:
        payload = {
            "name": "v1.0",
            "objectId": "deadbeef",
            "message": "Release 1.0",
            "taggedObject": {"objectId": "abc123", "objectType": "commit"},
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_annotated_tag(api_call, "deadbeef")
        assert isinstance(result, AnnotatedTagInfo)
        assert result.name == "v1.0"
        assert result.tagged_object is not None
        assert result.tagged_object.object_id == "abc123"
