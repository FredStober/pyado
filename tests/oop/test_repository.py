"""Tests for pyado.oop Repository — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from pyado.oop import (
    AddFile,
    Commit,
    DeleteFile,
    EditFile,
    Project,
    PullRequest,
    RenameFile,
    Repository,
)
from pyado.raw import (
    AccessControlList,
    BranchStatistics,
    GitItem,
    GitRef,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RecursionLevel,
)
from tests.oop.conftest import (
    ORG_URL,
    PROJECT_ID,
    REPO_ID,
    _api_call,
    _git_commit_ref,
    _make_project,
    _make_repo,
    _make_service,
    _pr_list_item,
    _project_info,
    _repo_info,
)


class TestRepository:
    def test_id(self) -> None:
        assert _make_repo().id == REPO_ID

    def test_name(self) -> None:
        assert _make_repo().name == "myrepo"

    def test_default_branch(self) -> None:
        assert _make_repo().default_branch == "refs/heads/main"

    def test_api_call_returns_api_call(self) -> None:
        api = _api_call()
        proj = _make_project()
        repo = Repository(proj, api, _repo_info(), proj._service)
        assert repo.api_call is api

    def test_web_url(self) -> None:
        assert "testorg" in str(_make_repo().web_url)

    def test_project_reference(self) -> None:
        proj = _make_project()
        api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api, _repo_info(), proj._service)
        assert repo.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api, _repo_info(), svc)
        assert repo.org is svc.org

    def test_refresh_refetches(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_repository_info") as mock_get:
            mock_get.return_value = _repo_info()
            repo.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = repo.info
        mock_get.assert_called_once()

    def test_get_pull_request_delegates_to_get_pr_details(self) -> None:
        with (
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
            patch("pyado.oop.repository.raw.get_pull_request_details") as mock_details,
        ):
            mock_call.return_value = _api_call()
            mock_details.return_value = _pr_list_item(7)
            pr = _make_repo().get_pull_request(7)
        assert pr.id == 7

    def test_iter_pull_requests_filters_by_repo(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1), _pr_list_item(2)])
            mock_call.return_value = _api_call()
            prs = list(_make_repo().iter_pull_requests())
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.repository_id == str(REPO_ID)
        assert criteria.status is None
        assert len(prs) == 2

    def test_iter_pull_requests_status_override(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([])
            mock_call.return_value = _api_call()
            list(_make_repo().iter_pull_requests(status=PullRequestStatus.COMPLETED))
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == "completed"

    def test_iter_pull_requests_passes_expand(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call"),
        ):
            mock_iter.return_value = iter([])
            list(_make_repo().iter_pull_requests(expand="labels"))
        assert mock_iter.call_args.kwargs["expand"] == "labels"

    def test_iter_pull_requests_custom_criteria_overrides_status(self) -> None:
        min_time = datetime(2024, 1, 1, tzinfo=UTC)
        custom = PullRequestSearchCriteria(
            status=PullRequestStatus.COMPLETED, min_time=min_time
        )
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([])
            mock_call.return_value = _api_call()
            list(_make_repo().iter_pull_requests(criteria=custom))
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == "completed"
        assert criteria.repository_id == str(REPO_ID)
        assert criteria.min_time == min_time

    def test_create_pull_request_returns_pull_request(self) -> None:
        with (
            patch(
                "pyado.oop.repository._pull_request.create_pull_request"
            ) as mock_create,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_create.return_value = _pr_list_item(5)
            mock_call.return_value = _api_call()
            pr = _make_repo().create_pull_request("My PR", "feature/x", "main")
        assert pr.id == 5

    def test_get_file_at_branch_delegates(self) -> None:
        with patch("pyado.oop.repository._git.get_file_content_at_branch") as mock_get:
            mock_get.return_value = "file content"
            result = _make_repo().get_file_at_branch("/foo.py", "main")
        assert result == "file content"

    def test_get_file_at_commit_delegates(self) -> None:
        with patch("pyado.oop.repository._git.get_file_content_at_commit") as mock_get:
            mock_get.return_value = "commit content"
            result = _make_repo().get_file_at_commit("/bar.py", "abc123")
        assert result == "commit content"

    def test_iter_refs_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_refs(name_filter="heads/main"))
        assert len(result) == 1
        assert mock_iter.call_args.args[1].name_filter == "heads/main"

    def test_create_branch_delegates(self) -> None:
        with patch("pyado.oop.repository._git.create_branch") as mock_create:
            _make_repo().create_branch("feature/new", "abc123")
        mock_create.assert_called_once()

    def test_delete_branch_delegates(self) -> None:
        with patch("pyado.oop.repository._git.delete_branch") as mock_del:
            _make_repo().delete_branch("feature/old", "def456")
        mock_del.assert_called_once()

    def test_iter_commit_diff_delegates(self) -> None:
        with patch("pyado.oop.repository._git.iter_commit_diff") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_commit_diff("abc", "def"))
        assert len(result) == 1

    def test_push_commits_delegates(self) -> None:
        with patch("pyado.oop.repository._git.push_commits") as mock_push:
            mock_push.return_value = MagicMock()
            _make_repo().push_commits([], [])
        mock_push.assert_called_once()

    def test_get_file_bytes_at_branch_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_at_branch("/img.png", "main")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "main"
        assert version_type == "branch"

    def test_get_file_bytes_at_branch_strips_refs_prefix(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"data"
            _make_repo().get_file_bytes_at_branch("/x", "refs/heads/main")
        _, _, version, _ = mock_get.call_args.args
        assert version == "main"

    def test_get_file_bytes_at_commit_delegates(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_at_commit("/img.png", "abc123")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "abc123"
        assert version_type == "commit"

    def test_get_file_bytes_returns_none_when_missing(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_item_bytes") as mock_get:
            mock_get.return_value = None
            result = _make_repo().get_file_bytes_at_branch("/missing", "main")
        assert result is None

    def test_iter_commits_returns_commit_objects(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = [_git_commit_ref("sha1"), _git_commit_ref("sha2")]
            result = list(_make_repo().iter_commits())
        assert len(result) == 2
        assert all(isinstance(item, Commit) for item in result)
        assert result[0].sha == "sha1"
        assert result[1].sha == "sha2"

    def test_iter_commits_passes_item_path(self) -> None:
        with patch("pyado.oop.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(_make_repo().iter_commits(item_path="/src/foo.py", top=10))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_path == "/src/foo.py"
        assert criteria.top == 10

    def test_get_commit_returns_commit_object(self) -> None:
        with patch("pyado.oop.repository.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("deadbeef")
            result = _make_repo().get_commit("deadbeef")
        assert isinstance(result, Commit)
        assert result.sha == "deadbeef"
        mock_get.assert_called_once()

    def test_make_ref_update_delegates(self) -> None:
        with patch("pyado.oop.repository._git.create_ref_update") as mock_create:
            mock_create.return_value = MagicMock()
            _make_repo().make_ref_update("main")
        mock_create.assert_called_once()

    def test_commit_delegates_to_push(self) -> None:
        with (
            patch("pyado.oop.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("main", "My message", [EditFile("/f.py", "x")])
        mock_ref.assert_called_once()
        mock_commit.assert_called_once()
        mock_push.assert_called_once()

    def test_commit_passes_branch_and_message(self) -> None:
        with (
            patch("pyado.oop.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("feature/x", "Fix bug", [DeleteFile("/old.py")])
        assert mock_ref.call_args.args[1] == "feature/x"
        assert mock_commit.call_args.args[0] == "Fix bug"

    def test_commit_converts_file_changes_to_git_changes(self) -> None:
        with (
            patch("pyado.oop.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit(
                "main",
                "Multi-change",
                [AddFile("/new.py", "x"), DeleteFile("/old.py")],
            )
        git_changes = mock_commit.call_args.args[1]
        assert len(git_changes) == 2
        assert git_changes[0].change_type.value == "add"
        assert git_changes[1].change_type.value == "delete"

    def test_get_statistics_returns_branch_statistics(self) -> None:
        stats = BranchStatistics.model_validate(
            {"name": "main", "aheadCount": 2, "behindCount": 0}
        )
        with patch("pyado.oop.repository.raw.get_repository_statistics") as mock_get:
            mock_get.return_value = stats
            result = _make_repo().get_statistics("main")
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "main"
        assert result is stats

    def test_get_pr_for_branch_returns_pull_request(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(11)])
            mock_call.return_value = _api_call()
            result = _make_repo().get_pr_for_branch("feature/x")
        assert result is not None
        assert result.id == 11

    def test_get_pr_for_branch_normalises_short_branch(self) -> None:
        with (
            patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repository.raw.get_pull_request_api_call") as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1)])
            mock_call.return_value = _api_call()
            _make_repo().get_pr_for_branch("main")
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.source_ref_name == "refs/heads/main"

    def test_get_pr_for_branch_returns_none_when_no_match(self) -> None:
        with patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            result = _make_repo().get_pr_for_branch("no-such-branch")
        assert result is None


class TestRepositoryAcl:
    def test_get_acl_delegates(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = [_make_acl()]
            result = repo.get_acl()
        assert len(result) == 1
        assert isinstance(result[0], AccessControlList)

    def test_get_acl_passes_project_and_repo_ids(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.get_acl()
        call = mock_acl.call_args
        assert call.args[1] == PROJECT_ID
        assert call.args[2] == REPO_ID

    def test_get_acl_uses_org_base_url(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.get_acl()
        org_call = mock_acl.call_args.args[0]
        assert "_apis" not in str(org_call.url)
        assert "testorg" in str(org_call.url)


class TestRepositoryGetLastCommit:
    def test_delegates_to_high(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repository._git.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "abc123"
            result = repo.get_last_commit_touching_file("/src/foo.py", "abc123")
        mock_fn.assert_called_once_with(repo.api_call, "/src/foo.py", "abc123")
        assert result == "abc123"

    def test_returns_fallback_when_no_commit_found(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repository._git.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "fallback-sha"
            result = repo.get_last_commit_touching_file("/missing.py", "fallback-sha")
        assert result == "fallback-sha"


class TestRepositoryGetDefaultBranchCommit:
    def test_returns_commit_at_branch_tip(self) -> None:
        ref = GitRef.model_validate({"name": "heads/main", "objectId": "deadbeef"})
        with (
            patch("pyado.oop.repository.raw.iter_refs") as mock_iter,
            patch("pyado.oop.repository.raw.get_commit_by_id") as mock_commit,
        ):
            mock_iter.return_value = iter([ref])
            mock_commit.return_value = _git_commit_ref("deadbeef")
            result = _make_repo().get_default_branch_commit()
        assert isinstance(result, Commit)
        assert result.sha == "deadbeef"

    def test_raises_value_error_when_no_default_branch(self) -> None:
        repo_info = _repo_info()
        repo_info.default_branch = None
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api_call, repo_info, proj._service)
        with pytest.raises(ValueError, match="no default branch"):
            repo.get_default_branch_commit()

    def test_raises_key_error_when_ref_not_found(self) -> None:
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(KeyError):
                _make_repo().get_default_branch_commit()


class TestRepositoryDeleteFile:
    def test_delegates_to_commit_with_delete_change(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with patch("pyado.oop.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = push_result
            result = repo.delete_file("main", "/old.txt", "Remove old file")
        assert result is push_result
        mock_commit.assert_called_once()
        _branch, _msg, changes = mock_commit.call_args.args
        assert len(changes) == 1
        assert isinstance(changes[0], DeleteFile)

    def test_passes_branch_and_message(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = MagicMock()
            repo.delete_file("feature/x", "/f.txt", "Delete it")
        branch, msg, _ = mock_commit.call_args.args
        assert branch == "feature/x"
        assert msg == "Delete it"


class TestRepositoryRenameFile:
    def test_delegates_to_commit_with_rename_change(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with patch("pyado.oop.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = push_result
            result = repo.rename_file("main", "/a.txt", "/b.txt", "Rename file")
        assert result is push_result
        mock_commit.assert_called_once()
        _branch, _msg, changes = mock_commit.call_args.args
        assert len(changes) == 1
        assert isinstance(changes[0], RenameFile)

    def test_passes_branch_and_message(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = MagicMock()
            repo.rename_file("main", "/a.txt", "/b.txt", "Move file")
        branch, msg, _ = mock_commit.call_args.args
        assert branch == "main"
        assert msg == "Move file"


class TestRepositoryIterBranches:
    def test_calls_iter_refs_with_heads_filter(self) -> None:
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_repo().iter_branches())
        ref_filter = mock_iter.call_args.args[1]
        assert ref_filter.name_filter == "heads/"

    def test_yields_git_refs(self) -> None:
        ref = GitRef.model_validate({"name": "refs/heads/main", "objectId": "abc123"})
        with patch("pyado.oop.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([ref])
            result = list(_make_repo().iter_branches())
        assert len(result) == 1
        assert result[0] is ref


class TestRepositoryGetPrForCommit:
    def test_returns_pull_request_when_pr_exists(self) -> None:
        repo = _make_repo()
        pr_item = _pr_list_item(55)
        with patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([pr_item])
            with patch(
                "pyado.oop.repository.raw.get_pull_request_api_call"
            ) as mock_pr_call:
                mock_pr_call.return_value = _api_call()
                result = repo.get_pr_for_commit("abc123")
        assert isinstance(result, PullRequest)
        assert result.id == 55

    def test_returns_none_when_no_pr(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            result = repo.get_pr_for_commit("abc123")
        assert result is None


class TestRepositoryTags:
    def test_iter_tags_delegates_to_raw(self) -> None:
        tag = GitRef.model_validate({"name": "refs/tags/v1.0", "objectId": "abc123"})
        with patch("pyado.oop.repository.raw.iter_tags") as mock_iter:
            mock_iter.return_value = iter([tag])
            result = list(_make_repo().iter_tags())
        assert len(result) == 1
        assert result[0] is tag
        mock_iter.assert_called_once_with(_make_repo()._api_call)

    def test_create_tag_delegates_to_raw(self) -> None:
        with patch("pyado.oop.repository.raw.create_tag") as mock_create:
            _make_repo().create_tag("v1.0", "abc123")
        mock_create.assert_called_once()
        assert mock_create.call_args.args[1] == "v1.0"
        assert mock_create.call_args.args[2] == "abc123"

    def test_delete_tag_delegates_to_raw(self) -> None:
        with patch("pyado.oop.repository.raw.delete_tag") as mock_delete:
            _make_repo().delete_tag("v1.0", "abc123")
        mock_delete.assert_called_once()
        assert mock_delete.call_args.args[1] == "v1.0"
        assert mock_delete.call_args.args[2] == "abc123"


class TestRepositoryListMethods:
    def test_list_pull_requests_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_pull_requests", return_value=iter([])):
            assert repo.list_pull_requests() == []

    def test_list_refs_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_refs", return_value=iter([])):
            assert repo.list_refs() == []

    def test_list_branches_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_branches", return_value=iter([])):
            assert repo.list_branches() == []

    def test_list_tags_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_tags", return_value=iter([])):
            assert repo.list_tags() == []

    def test_list_commit_diff_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_commit_diff", return_value=iter([])):
            assert repo.list_commit_diff("abc", "def") == []

    def test_list_commits_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_commits", return_value=iter([])):
            assert repo.list_commits() == []


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_acl() -> AccessControlList:
    return AccessControlList.model_validate(
        {"token": f"repoV2/{PROJECT_ID}/{REPO_ID}", "inheritanceDeny": 0}
    )


class TestRepositoryIterItems:
    def test_iter_items_delegates_to_raw(self) -> None:
        repo = _make_repo()
        item = GitItem.model_validate(
            {
                "objectId": "a" * 40,
                "gitObjectType": "blob",
                "path": "/README.md",
                "isFolder": False,
                "isSymLink": False,
            }
        )
        with patch("pyado.oop.repository.raw.iter_repository_items") as mock_iter:
            mock_iter.return_value = iter([item])
            result = list(repo.iter_items("/", branch="main"))
        mock_iter.assert_called_once_with(
            repo._api_call,
            "/",
            branch="main",
            recursion_level=RecursionLevel.ONE_LEVEL,
        )
        assert len(result) == 1
        assert result[0].path == "/README.md"

    def test_list_items_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_items", return_value=iter([])):
            result = repo.list_items()
        assert result == []

    def test_list_items_passes_args(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_items", return_value=iter([])) as mock_iter:
            repo.list_items("/src", branch="main", recursion_level=RecursionLevel.FULL)
        mock_iter.assert_called_once_with(
            "/src", branch="main", recursion_level=RecursionLevel.FULL
        )
