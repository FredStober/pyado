"""Tests for pyado.oop Repository — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from pyado import AzureDevOpsNotFoundError
from pyado.oop import (
    AddFile,
    Commit,
    DeleteFile,
    EditFile,
    Project,
    PullRequest,
    RenameFile,
    Repository,
    Tag,
)
from pyado.oop.repos.branch import Branch
from pyado.raw import (
    AccessControlList,
    AnnotatedTagInfo,
    BranchStatistics,
    GitCherryPickResponse,
    GitCherryPickStatus,
    GitItem,
    GitMergeResponse,
    GitMergeStatus,
    GitRef,
    GitRevertResponse,
    GitRevertStatus,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RecursionLevel,
    VersionDescriptorType,
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
        with patch("pyado.oop.repos.repository.raw.get_repository_info") as mock_get:
            mock_get.return_value = _repo_info()
            repo.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = repo.info
        mock_get.assert_called_once()

    def test_get_pull_request_delegates_to_get_pr_details(self) -> None:
        with (
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_details"
            ) as mock_details,
        ):
            mock_call.return_value = _api_call()
            mock_details.return_value = _pr_list_item(7)
            pr = _make_repo().get_pull_request(7)
        assert pr.id == 7

    def test_iter_pull_requests_filters_by_repo(self) -> None:
        with (
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
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
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
        ):
            mock_iter.return_value = iter([])
            mock_call.return_value = _api_call()
            list(_make_repo().iter_pull_requests(status=PullRequestStatus.COMPLETED))
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.status == "completed"

    def test_iter_pull_requests_passes_expand(self) -> None:
        with (
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch("pyado.oop.repos.repository.raw.get_pull_request_api_call"),
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
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
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
                "pyado.oop.repos.repository._pull_request.create_pull_request"
            ) as mock_create,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
        ):
            mock_create.return_value = _pr_list_item(5)
            mock_call.return_value = _api_call()
            pr = _make_repo().create_pull_request("My PR", "feature/x", "main")
        assert pr.id == 5

    def test_get_file_by_branch_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.repository._git.get_file_content_at_branch"
        ) as mock_get:
            mock_get.return_value = "file content"
            result = _make_repo().get_file_by_branch("/foo.py", "main")
        assert result == "file content"

    def test_get_file_by_branch_uses_default_when_none(self) -> None:
        with patch(
            "pyado.oop.repos.repository._git.get_file_content_at_branch"
        ) as mock_get:
            mock_get.return_value = "content"
            _make_repo().get_file_by_branch("/foo.py")
        _, _, branch_arg = mock_get.call_args.args
        assert branch_arg == "refs/heads/main"

    def test_get_file_by_commit_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.repository._git.get_file_content_at_commit"
        ) as mock_get:
            mock_get.return_value = "commit content"
            result = _make_repo().get_file_by_commit("/bar.py", "abc123")
        assert result == "commit content"

    def test_iter_refs_delegates(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_refs(name_filter="heads/main"))
        assert len(result) == 1
        assert mock_iter.call_args.args[1].name_filter == "heads/main"

    def test_create_branch_delegates(self) -> None:
        with patch("pyado.oop.repos.repository._git.create_branch") as mock_create:
            _make_repo().create_branch("feature/new", "abc123")
        mock_create.assert_called_once()

    def test_delete_branch_with_commit_delegates(self) -> None:
        with patch("pyado.oop.repos.repository._git.delete_branch") as mock_del:
            _make_repo().delete_branch("feature/old", "def456")
        mock_del.assert_called_once()

    def test_iter_commit_diff_delegates(self) -> None:
        with patch("pyado.oop.repos.repository._git.iter_commit_diff") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            result = list(_make_repo().iter_commit_diff("abc", "def"))
        assert len(result) == 1

    def test_push_commits_delegates(self) -> None:
        with patch("pyado.oop.repos.repository._git.push_commits") as mock_push:
            mock_push.return_value = MagicMock()
            _make_repo().push_commits([], [])
        mock_push.assert_called_once()

    def test_get_file_bytes_by_branch_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_item_bytes"
        ) as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_by_branch("/img.png", "main")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "main"
        assert version_type == "branch"

    def test_get_file_bytes_by_branch_strips_refs_prefix(self) -> None:
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_item_bytes"
        ) as mock_get:
            mock_get.return_value = b"data"
            _make_repo().get_file_bytes_by_branch("/x", "refs/heads/main")
        _, _, version, _ = mock_get.call_args.args
        assert version == "main"

    def test_get_file_bytes_by_branch_uses_default_when_none(self) -> None:
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_item_bytes"
        ) as mock_get:
            mock_get.return_value = b"data"
            _make_repo().get_file_bytes_by_branch("/x")
        _, _, version, _ = mock_get.call_args.args
        assert version == "main"

    def test_get_file_bytes_by_commit_delegates(self) -> None:
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_item_bytes"
        ) as mock_get:
            mock_get.return_value = b"binary"
            result = _make_repo().get_file_bytes_by_commit("/img.png", "abc123")
        assert result == b"binary"
        _, _, version, version_type = mock_get.call_args.args
        assert version == "abc123"
        assert version_type == "commit"

    def test_get_file_bytes_returns_none_when_missing(self) -> None:
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_item_bytes"
        ) as mock_get:
            mock_get.return_value = None
            result = _make_repo().get_file_bytes_by_branch("/missing", "main")
        assert result is None

    def test_iter_commits_returns_commit_objects(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = [_git_commit_ref("sha1"), _git_commit_ref("sha2")]
            result = list(_make_repo().iter_commits())
        assert len(result) == 2
        assert all(isinstance(item, Commit) for item in result)
        assert result[0].sha == "sha1"
        assert result[1].sha == "sha2"

    def test_iter_commits_passes_item_path(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(_make_repo().iter_commits(item_path="/src/foo.py", top=10))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_path == "/src/foo.py"
        assert criteria.top == 10

    def test_get_commit_returns_commit_object(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("deadbeef")
            result = _make_repo().get_commit("deadbeef")
        assert isinstance(result, Commit)
        assert result.sha == "deadbeef"
        mock_get.assert_called_once()

    def test_make_ref_update_delegates(self) -> None:
        with patch("pyado.oop.repos.repository._git.create_ref_update") as mock_create:
            mock_create.return_value = MagicMock()
            _make_repo().make_ref_update("main")
        mock_create.assert_called_once()

    def test_commit_delegates_to_push(self) -> None:
        with (
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
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
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("feature/x", "Fix bug", [DeleteFile("/old.py")])
        assert mock_ref.call_args.args[1] == "feature/x"
        assert mock_commit.call_args.args[0] == "Fix bug"

    def test_commit_converts_file_changes_to_git_changes(self) -> None:
        with (
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
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
        with patch(
            "pyado.oop.repos.repository.raw.get_repository_statistics"
        ) as mock_get:
            mock_get.return_value = stats
            result = _make_repo().get_statistics("main")
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "main"
        assert result is stats

    def test_get_pr_for_branch_returns_pull_request(self) -> None:
        with (
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(11)])
            mock_call.return_value = _api_call()
            result = _make_repo().get_pr_for_branch("feature/x")
        assert result is not None
        assert result.id == 11

    def test_get_pr_for_branch_normalises_short_branch(self) -> None:
        with (
            patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter,
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_call,
        ):
            mock_iter.return_value = iter([_pr_list_item(1)])
            mock_call.return_value = _api_call()
            _make_repo().get_pr_for_branch("main")
        criteria = mock_iter.call_args.kwargs["search_criteria"]
        assert criteria.source_ref_name == "refs/heads/main"

    def test_get_pr_for_branch_returns_none_when_no_match(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            result = _make_repo().get_pr_for_branch("no-such-branch")
        assert result is None


class TestRepositoryListAcl:
    def test_list_acl_delegates(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = [_make_acl()]
            result = repo.list_acl()
        assert len(result) == 1
        assert isinstance(result[0], AccessControlList)

    def test_list_acl_passes_project_and_repo_ids(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.list_acl()
        call = mock_acl.call_args
        assert call.args[1] == PROJECT_ID
        assert call.args[2] == REPO_ID

    def test_list_acl_uses_org_base_url(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_git_acl") as mock_acl:
            mock_acl.return_value = []
            repo.list_acl()
        org_call = mock_acl.call_args.args[0]
        assert "_apis" not in str(org_call.url)
        assert "testorg" in str(org_call.url)


class TestRepositoryGetLastCommit:
    def test_delegates_to_high(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository._git.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "abc123"
            result = repo.get_last_commit_touching_file("/src/foo.py", "abc123")
        mock_fn.assert_called_once_with(repo.api_call, "/src/foo.py", "abc123")
        assert result == "abc123"

    def test_returns_fallback_when_no_commit_found(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository._git.get_last_commit_touching_file"
        ) as mock_fn:
            mock_fn.return_value = "fallback-sha"
            result = repo.get_last_commit_touching_file("/missing.py", "fallback-sha")
        assert result == "fallback-sha"


class TestRepositoryGetDefaultBranchCommit:
    def test_returns_commit_at_branch_tip(self) -> None:
        ref = GitRef.model_validate({"name": "heads/main", "objectId": "deadbeef"})
        with (
            patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter,
            patch("pyado.oop.repos.repository.raw.get_commit_by_id") as mock_commit,
        ):
            mock_iter.return_value = iter([ref])
            mock_commit.return_value = _git_commit_ref("deadbeef")
            result = _make_repo().get_default_branch_commit()
        assert isinstance(result, Commit)
        assert result.sha == "deadbeef"

    def test_raises_not_found_when_no_default_branch(self) -> None:
        repo_info = _repo_info()
        repo_info.default_branch = None
        proj = _make_project()
        api_call = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, api_call, repo_info, proj._service)
        with pytest.raises(AzureDevOpsNotFoundError, match="no default branch"):
            repo.get_default_branch_commit()

    def test_raises_not_found_when_ref_not_found(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(AzureDevOpsNotFoundError):
                _make_repo().get_default_branch_commit()


class TestRepositoryCommitFileDelete:
    def test_delegates_to_commit_with_delete_change(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with patch("pyado.oop.repos.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = push_result
            result = repo.commit_file_delete("main", "/old.txt", "Remove old file")
        assert result is push_result
        mock_commit.assert_called_once()
        _branch, _msg, changes = mock_commit.call_args.args
        assert len(changes) == 1
        assert isinstance(changes[0], DeleteFile)

    def test_passes_branch_and_message(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = MagicMock()
            repo.commit_file_delete("feature/x", "/f.txt", "Delete it")
        branch, msg, _ = mock_commit.call_args.args
        assert branch == "feature/x"
        assert msg == "Delete it"


class TestRepositoryCommitFileRename:
    def test_delegates_to_commit_with_rename_change(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with patch("pyado.oop.repos.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = push_result
            result = repo.commit_file_rename("main", "/a.txt", "/b.txt", "Rename file")
        assert result is push_result
        mock_commit.assert_called_once()
        _branch, _msg, changes = mock_commit.call_args.args
        assert len(changes) == 1
        assert isinstance(changes[0], RenameFile)

    def test_passes_branch_and_message(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.Repository.commit") as mock_commit:
            mock_commit.return_value = MagicMock()
            repo.commit_file_rename("main", "/a.txt", "/b.txt", "Move file")
        branch, msg, _ = mock_commit.call_args.args
        assert branch == "main"
        assert msg == "Move file"


class TestRepositoryIterBranches:
    def test_calls_iter_refs_with_heads_filter(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_repo().iter_branches())
        ref_filter = mock_iter.call_args.args[1]
        assert ref_filter.name_filter == "heads/"

    def test_yields_branch_wrappers(self) -> None:
        ref = GitRef.model_validate({"name": "refs/heads/main", "objectId": "abc123"})
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([ref])
            result = list(_make_repo().iter_branches())
        assert len(result) == 1
        assert isinstance(result[0], Branch)
        assert result[0].ref is ref


class TestRepositoryGetPrForCommit:
    def test_returns_pull_request_when_pr_exists(self) -> None:
        repo = _make_repo()
        pr_item = _pr_list_item(55)
        with patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([pr_item])
            with patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_pr_call:
                mock_pr_call.return_value = _api_call()
                result = repo.get_pr_for_commit("abc123")
        assert isinstance(result, PullRequest)
        assert result.id == 55

    def test_returns_none_when_no_pr(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            result = repo.get_pr_for_commit("abc123")
        assert result is None


class TestRepositoryTags:
    def test_iter_git_tags_yields_tag_wrappers(self) -> None:
        ref = GitRef.model_validate({"name": "refs/tags/v1.0", "objectId": "abc123"})
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_tags") as mock_iter:
            mock_iter.return_value = iter([ref])
            result = list(repo.iter_git_tags())
        assert len(result) == 1
        assert isinstance(result[0], Tag)
        assert result[0].name == "v1.0"
        mock_iter.assert_called_once_with(repo._api_call)

    def test_create_git_tag_delegates_to_raw(self) -> None:
        with patch("pyado.oop.repos.repository.raw.post_git_tag") as mock_create:
            _make_repo().create_git_tag("v1.0", "abc123")
        mock_create.assert_called_once()
        assert mock_create.call_args.args[1] == "v1.0"
        assert mock_create.call_args.args[2] == "abc123"

    def test_delete_git_tag_delegates_to_raw(self) -> None:
        with patch("pyado.oop.repos.repository.raw.delete_git_tag") as mock_delete:
            _make_repo().delete_git_tag("v1.0", "abc123")
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

    def test_list_git_tags_delegates(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_git_tags", return_value=iter([])):
            assert repo.list_git_tags() == []

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
        with patch("pyado.oop.repos.repository.raw.iter_repository_items") as mock_iter:
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


# ---------------------------------------------------------------------------
# A3 — get_branch_head / check_branch_exists
# ---------------------------------------------------------------------------


class TestRepositoryBranchHead:
    def test_get_branch_head_returns_sha(self) -> None:
        ref = GitRef.model_validate({"name": "refs/heads/main", "objectId": "abc123"})
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([ref])
            result = _make_repo().get_branch_head("main")
        assert result == "abc123"

    def test_get_branch_head_strips_full_ref_prefix(self) -> None:
        ref = GitRef.model_validate({"name": "refs/heads/main", "objectId": "abc123"})
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([ref])
            result = _make_repo().get_branch_head("refs/heads/main")
        assert result == "abc123"

    def test_get_branch_head_raises_not_found_when_absent(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(AzureDevOpsNotFoundError):
                _make_repo().get_branch_head("no-such-branch")

    def test_check_branch_exists_returns_true(self) -> None:
        ref = GitRef.model_validate({"name": "refs/heads/main", "objectId": "abc123"})
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([ref])
            assert _make_repo().check_branch_exists("main") is True

    def test_check_branch_exists_returns_false(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            assert _make_repo().check_branch_exists("no-such") is False

    def test_check_branch_exists_strips_full_ref_prefix(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_iter:
            mock_iter.return_value = iter([])
            _make_repo().check_branch_exists("refs/heads/main")
        ref_filter = mock_iter.call_args.args[1]
        assert ref_filter.name_filter == "heads/main"


# ---------------------------------------------------------------------------
# A4 — optional current_commit on delete_branch and commit
# ---------------------------------------------------------------------------


class TestRepositoryDeleteBranchOptional:
    def test_delete_branch_with_explicit_commit_skips_head_fetch(self) -> None:
        with (
            patch("pyado.oop.repos.repository._git.delete_branch") as mock_del,
            patch.object(_make_repo().__class__, "get_branch_head") as mock_head,
        ):
            mock_del.return_value = None
            _make_repo().delete_branch("feature/old", "def456")
        mock_del.assert_called_once()
        mock_head.assert_not_called()

    def test_delete_branch_without_commit_fetches_head(self) -> None:
        repo = _make_repo()
        with (
            patch.object(
                repo, "get_branch_head", return_value="fetched-sha"
            ) as mock_head,
            patch("pyado.oop.repos.repository._git.delete_branch") as mock_del,
        ):
            repo.delete_branch("main")
        mock_head.assert_called_once_with("main")
        assert mock_del.call_args.args[2] == "fetched-sha"


class TestRepositoryCommitOptional:
    def test_commit_with_sha_uses_create_ref_from_sha(self) -> None:
        with (
            patch(
                "pyado.oop.repos.repository._git.create_ref_update_from_sha"
            ) as mock_from_sha,
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
        ):
            mock_from_sha.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit(
                "main", "msg", [EditFile("/f", "x")], current_commit="abc"
            )
        mock_from_sha.assert_called_once()
        mock_ref.assert_not_called()

    def test_commit_without_sha_uses_create_ref_update(self) -> None:
        with (
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch(
                "pyado.oop.repos.repository._git.create_ref_update_from_sha"
            ) as mock_from_sha,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit("main", "msg", [EditFile("/f", "x")])
        mock_ref.assert_called_once()
        mock_from_sha.assert_not_called()

    def test_commit_with_none_branch_uses_default_branch(self) -> None:
        with (
            patch("pyado.oop.repos.repository._git.create_ref_update") as mock_ref,
            patch("pyado.oop.repos.repository._git.make_commit") as mock_commit,
            patch("pyado.oop.repos.repository._git.push_commits") as mock_push,
        ):
            mock_ref.return_value = MagicMock()
            mock_commit.return_value = MagicMock()
            mock_push.return_value = MagicMock()
            _make_repo().commit(None, "msg", [EditFile("/f", "x")])
        # _repo_info default_branch is "refs/heads/main"
        assert mock_ref.call_args.args[1] == "refs/heads/main"


# ---------------------------------------------------------------------------
# A5 — iter_items_by_* / get_item_by_*
# ---------------------------------------------------------------------------


def _make_git_item(path: str = "/f.py") -> GitItem:
    return GitItem.model_validate(
        {
            "objectId": "a" * 40,
            "gitObjectType": "blob",
            "path": path,
            "isFolder": False,
            "isSymLink": False,
        }
    )


class TestRepositoryIterItemsBy:
    def test_iter_items_by_commit_passes_version(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_repository_items") as mock_iter:
            mock_iter.return_value = iter([])
            list(repo.iter_items_by_commit(commit="abc123"))
        assert mock_iter.call_args.kwargs["version"] == "abc123"
        assert (
            mock_iter.call_args.kwargs["version_type"] == VersionDescriptorType.COMMIT
        )

    def test_iter_items_by_tag_strips_refs_tags_prefix(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_repository_items") as mock_iter:
            mock_iter.return_value = iter([])
            list(repo.iter_items_by_tag(tag="refs/tags/v1.0"))
        assert mock_iter.call_args.kwargs["version"] == "v1.0"
        assert mock_iter.call_args.kwargs["version_type"] == VersionDescriptorType.TAG

    def test_iter_items_by_tag_short_name(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_repository_items") as mock_iter:
            mock_iter.return_value = iter([])
            list(repo.iter_items_by_tag(tag="v1.0"))
        assert mock_iter.call_args.kwargs["version"] == "v1.0"

    def test_iter_items_by_ref_resolves_to_commit(self) -> None:
        repo = _make_repo()
        ref = GitRef.model_validate(
            {"name": "refs/pull/5/merge", "objectId": "resolved-sha"}
        )
        with (
            patch("pyado.oop.repos.repository.raw.iter_refs") as mock_refs,
            patch("pyado.oop.repos.repository.raw.iter_repository_items") as mock_iter,
        ):
            mock_refs.return_value = iter([ref])
            mock_iter.return_value = iter([])
            list(repo.iter_items_by_ref(ref="refs/pull/5/merge"))
        assert mock_iter.call_args.kwargs["version"] == "resolved-sha"
        assert (
            mock_iter.call_args.kwargs["version_type"] == VersionDescriptorType.COMMIT
        )

    def test_iter_items_by_ref_raises_when_ref_not_found(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_refs:
            mock_refs.return_value = iter([])
            with pytest.raises(AzureDevOpsNotFoundError):
                list(repo.iter_items_by_ref(ref="refs/pull/999/merge"))

    def test_list_items_by_commit_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_items_by_commit", return_value=iter([])):
            assert repo.list_items_by_commit(commit="abc123") == []

    def test_list_items_by_tag_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_items_by_tag", return_value=iter([])):
            assert repo.list_items_by_tag(tag="v1.0") == []

    def test_list_items_by_ref_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_items_by_ref", return_value=iter([])):
            assert repo.list_items_by_ref(ref="refs/pull/5/merge") == []


class TestRepositoryGetItemBy:
    def test_get_item_by_branch_returns_item(self) -> None:
        item = _make_git_item()
        with patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get:
            mock_get.return_value = item
            result = _make_repo().get_item_by_branch("/f.py", "main")
        assert result is item
        _, _, version, version_type = mock_get.call_args.args
        assert version == "main"
        assert version_type == VersionDescriptorType.BRANCH

    def test_get_item_by_branch_returns_none_when_absent(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get:
            mock_get.return_value = None
            assert _make_repo().get_item_by_branch("/missing.py", "main") is None

    def test_get_item_by_branch_uses_default_when_none(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get:
            mock_get.return_value = None
            _make_repo().get_item_by_branch("/f.py")
        _, _, version, _ = mock_get.call_args.args
        # default_branch is "refs/heads/main" → stripped to "main"
        assert version == "main"

    def test_get_item_by_commit_uses_commit_type(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get:
            mock_get.return_value = None
            _make_repo().get_item_by_commit("/f.py", "abc123")
        _, _, version, version_type = mock_get.call_args.args
        assert version == "abc123"
        assert version_type == VersionDescriptorType.COMMIT

    def test_get_item_by_tag_strips_refs_tags_prefix(self) -> None:
        with patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get:
            mock_get.return_value = None
            _make_repo().get_item_by_tag("/f.py", "refs/tags/v1.0")
        _, _, version, version_type = mock_get.call_args.args
        assert version == "v1.0"
        assert version_type == VersionDescriptorType.TAG

    def test_get_item_by_ref_resolves_to_commit(self) -> None:
        ref = GitRef.model_validate(
            {"name": "refs/pull/42/merge", "objectId": "resolved-sha"}
        )
        with (
            patch("pyado.oop.repos.repository.raw.iter_refs") as mock_refs,
            patch("pyado.oop.repos.repository.raw.get_repository_item") as mock_get,
        ):
            mock_refs.return_value = iter([ref])
            mock_get.return_value = None
            _make_repo().get_item_by_ref("/f.py", "refs/pull/42/merge")
        _, _, version, version_type = mock_get.call_args.args
        assert version == "resolved-sha"
        assert version_type == VersionDescriptorType.COMMIT

    def test_get_item_by_ref_raises_when_ref_not_found(self) -> None:
        with patch("pyado.oop.repos.repository.raw.iter_refs") as mock_refs:
            mock_refs.return_value = iter([])
            with pytest.raises(AzureDevOpsNotFoundError):
                _make_repo().get_item_by_ref("/f.py", "refs/pull/999/merge")


# ---------------------------------------------------------------------------
# A6 — check_file_exists_by_*
# ---------------------------------------------------------------------------


class TestRepositoryCheckFileExists:
    def test_check_file_exists_by_branch_true(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_branch", return_value=_make_git_item()):
            assert repo.check_file_exists_by_branch("/f.py", "main") is True

    def test_check_file_exists_by_branch_false(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_branch", return_value=None):
            assert repo.check_file_exists_by_branch("/f.py", "main") is False

    def test_check_file_exists_by_commit_true(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_commit", return_value=_make_git_item()):
            assert repo.check_file_exists_by_commit("/f.py", "abc123") is True

    def test_check_file_exists_by_commit_false(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_commit", return_value=None):
            assert repo.check_file_exists_by_commit("/f.py", "abc123") is False

    def test_check_file_exists_by_tag_true(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_tag", return_value=_make_git_item()):
            assert repo.check_file_exists_by_tag("/f.py", "v1.0") is True

    def test_check_file_exists_by_tag_false(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_tag", return_value=None):
            assert repo.check_file_exists_by_tag("/f.py", "v1.0") is False

    def test_check_file_exists_by_ref_true(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_ref", return_value=_make_git_item()):
            assert repo.check_file_exists_by_ref("/f.py", "refs/pull/1/merge") is True

    def test_check_file_exists_by_ref_false(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "get_item_by_ref", return_value=None):
            assert repo.check_file_exists_by_ref("/f.py", "refs/pull/1/merge") is False


# ---------------------------------------------------------------------------
# A7 — commit_file_upsert
# ---------------------------------------------------------------------------


class TestRepositoryCommitFileUpsert:
    def test_commit_file_upsert_uses_edit_when_file_exists(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with (
            patch.object(repo, "check_file_exists_by_branch", return_value=True),
            patch.object(repo, "commit", return_value=push_result) as mock_commit,
        ):
            result = repo.commit_file_upsert(
                "main", "/f.py", "new content", "Update file"
            )
        assert result is push_result
        _branch, _msg, changes = mock_commit.call_args.args
        assert len(changes) == 1
        assert isinstance(changes[0], EditFile)

    def test_commit_file_upsert_uses_add_when_file_absent(self) -> None:
        repo = _make_repo()
        push_result = MagicMock()
        with (
            patch.object(repo, "check_file_exists_by_branch", return_value=False),
            patch.object(repo, "commit", return_value=push_result) as mock_commit,
        ):
            result = repo.commit_file_upsert("main", "/new.py", "content", "Add file")
        assert result is push_result
        _branch, _msg, changes = mock_commit.call_args.args
        assert isinstance(changes[0], AddFile)

    def test_commit_file_upsert_passes_branch_and_message(self) -> None:
        repo = _make_repo()
        with (
            patch.object(repo, "check_file_exists_by_branch", return_value=True),
            patch.object(repo, "commit", return_value=MagicMock()) as mock_commit,
        ):
            repo.commit_file_upsert("feature/x", "/f.py", "content", "My msg")
        branch, msg, _ = mock_commit.call_args.args
        assert branch == "feature/x"
        assert msg == "My msg"

    def test_commit_file_upsert_passes_current_commit(self) -> None:
        repo = _make_repo()
        with (
            patch.object(repo, "check_file_exists_by_branch", return_value=True),
            patch.object(repo, "commit", return_value=MagicMock()) as mock_commit,
        ):
            repo.commit_file_upsert(
                "main", "/f.py", "content", "msg", current_commit="sha123"
            )
        assert mock_commit.call_args.kwargs.get("current_commit") == "sha123"

    def test_commit_file_upsert_with_none_branch_checks_default_branch(self) -> None:
        repo = _make_repo()
        with (
            patch.object(
                repo, "check_file_exists_by_branch", return_value=False
            ) as mock_check,
            patch.object(repo, "commit", return_value=MagicMock()),
        ):
            repo.commit_file_upsert(None, "/new.py", "content", "Add")
        # branch=None is passed through to check_file_exists_by_branch
        mock_check.assert_called_once_with("/new.py", None)


# ---------------------------------------------------------------------------
# iter_commits_by_* / list_commits_by_*
# ---------------------------------------------------------------------------


class TestRepositoryIterCommitsBy:
    def test_iter_commits_by_commit_passes_version_type(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(repo.iter_commits_by_commit("abc123"))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_version == "abc123"
        assert criteria.item_version_type == VersionDescriptorType.COMMIT

    def test_iter_commits_by_tag_strips_refs_tags_prefix(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(repo.iter_commits_by_tag("refs/tags/v1.0"))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_version == "v1.0"
        assert criteria.item_version_type == VersionDescriptorType.TAG

    def test_iter_commits_by_tag_short_name(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = []
            list(repo.iter_commits_by_tag("v2.0"))
        criteria = mock_get.call_args.args[1]
        assert criteria.item_version == "v2.0"

    def test_iter_commits_by_commit_returns_commit_objects(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = [_git_commit_ref("sha1")]
            result = list(repo.iter_commits_by_commit("abc"))
        assert len(result) == 1
        assert isinstance(result[0], Commit)
        assert result[0].sha == "sha1"

    def test_list_commits_by_commit_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_commits_by_commit", return_value=iter([])):
            assert repo.list_commits_by_commit("abc") == []

    def test_iter_commits_by_tag_returns_commit_objects(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.get_repository_commits") as mock_get:
            mock_get.return_value = [_git_commit_ref("tagsha1")]
            result = list(repo.iter_commits_by_tag("v1.0"))
        assert len(result) == 1
        assert isinstance(result[0], Commit)
        assert result[0].sha == "tagsha1"

    def test_list_commits_by_tag_returns_list(self) -> None:
        repo = _make_repo()
        with patch.object(repo, "iter_commits_by_tag", return_value=iter([])):
            assert repo.list_commits_by_tag("v1.0") == []


class TestCreateAnnotatedTag:
    def test_returns_annotated_tag_info(self) -> None:
        repo = _make_repo()
        info = AnnotatedTagInfo.model_validate(
            {"objectId": "abc123", "name": "v1.0", "message": "Release 1.0"}
        )
        with patch(
            "pyado.oop.repos.repository.raw.post_annotated_tag",
            return_value=info,
        ) as mock_post:
            result = repo.create_annotated_tag("v1.0", "Release 1.0", "abc123")
        assert isinstance(result, AnnotatedTagInfo)
        assert result.name == "v1.0"
        assert result.message == "Release 1.0"
        mock_post.assert_called_once()

    def test_passes_annotated_tag_request_with_correct_fields(self) -> None:
        repo = _make_repo()
        info = AnnotatedTagInfo.model_validate({"objectId": "deadbeef", "name": "v2.0"})
        with patch(
            "pyado.oop.repos.repository.raw.post_annotated_tag",
            return_value=info,
        ) as mock_post:
            repo.create_annotated_tag("v2.0", "Release 2.0", "deadbeef")
        call_args = mock_post.call_args
        request = call_args.args[1]
        assert request.name == "v2.0"
        assert request.message == "Release 2.0"
        assert request.tagged_object.object_id == "deadbeef"

    def test_uses_repository_api_call(self) -> None:
        repo = _make_repo()
        info = AnnotatedTagInfo.model_validate({"objectId": "sha1", "name": "v0.1"})
        with patch(
            "pyado.oop.repos.repository.raw.post_annotated_tag",
            return_value=info,
        ) as mock_post:
            repo.create_annotated_tag("v0.1", "Initial", "sha1")
        call_args = mock_post.call_args
        assert call_args.args[0] is repo.api_call


_SHA_A = "aaaaaaaabbbbbbbbccccccccddddddddeeeeeeee"  # pragma: allowlist secret
_SHA_B = "1111111122222222333333334444444455555555"  # pragma: allowlist secret
_SHA_MERGE = "ffffffffffffffffffffffffffffffffffffffff"  # pragma: allowlist secret


def _merge_response(status: GitMergeStatus, op_id: int = 1) -> GitMergeResponse:
    return GitMergeResponse.model_validate(
        {
            "mergeOperationId": op_id,
            "status": status.value,
            **(
                {"mergeCommitId": _SHA_MERGE}
                if status == GitMergeStatus.COMPLETED
                else {}
            ),
        }
    )


def _cherry_pick_response(
    status: GitCherryPickStatus, cp_id: int = 10
) -> GitCherryPickResponse:
    return GitCherryPickResponse.model_validate(
        {
            "cherryPickId": cp_id,
            "status": status.value,
            "onto": "refs/heads/main",
            "cherryPickRef": "refs/heads/cherry-pick-branch",
        }
    )


def _revert_response(status: GitRevertStatus, revert_id: int = 20) -> GitRevertResponse:
    return GitRevertResponse.model_validate(
        {
            "revertId": revert_id,
            "status": status.value,
            "onto": "refs/heads/main",
            "revertRef": "refs/heads/revert-branch",
        }
    )


class TestRepositoryMerge:
    """Tests for start_merge, get_merge_status, check_merge_feasible."""

    def test_start_merge_returns_response(self) -> None:
        repo = _make_repo()
        response = _merge_response(GitMergeStatus.QUEUED)
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=response,
        ) as mock_post:
            result = repo.start_merge(_SHA_A, _SHA_B)
        assert isinstance(result, GitMergeResponse)
        assert result.status == GitMergeStatus.QUEUED
        request = mock_post.call_args.args[1]
        assert request.parents == [_SHA_A, _SHA_B]

    def test_start_merge_passes_comment(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=_merge_response(GitMergeStatus.QUEUED),
        ) as mock_post:
            repo.start_merge(_SHA_A, _SHA_B, comment="My merge")
        assert mock_post.call_args.args[1].comment == "My merge"

    def test_start_merge_uses_repository_api_call(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=_merge_response(GitMergeStatus.QUEUED),
        ) as mock_post:
            repo.start_merge(_SHA_A, _SHA_B)
        assert mock_post.call_args.args[0] is repo.api_call

    def test_get_merge_status_returns_response(self) -> None:
        repo = _make_repo()
        response = _merge_response(GitMergeStatus.COMPLETED)
        with patch(
            "pyado.oop.repos.repository.raw.get_git_merge",
            return_value=response,
        ) as mock_get:
            result = repo.get_merge_status(1)
        assert result.status == GitMergeStatus.COMPLETED
        mock_get.assert_called_once_with(repo.api_call, 1)

    def test_check_merge_feasible_returns_true_when_completed(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=_merge_response(GitMergeStatus.COMPLETED),
        ):
            assert repo.check_merge_feasible(_SHA_A, _SHA_B) is True

    def test_check_merge_feasible_returns_false_when_conflicts(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=_merge_response(GitMergeStatus.CONFLICTS),
        ):
            assert repo.check_merge_feasible(_SHA_A, _SHA_B) is False

    def test_check_merge_feasible_returns_false_when_failure(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_merge",
            return_value=_merge_response(GitMergeStatus.FAILURE),
        ):
            assert repo.check_merge_feasible(_SHA_A, _SHA_B) is False

    def test_check_merge_feasible_polls_until_terminal(self) -> None:
        repo = _make_repo()
        queued = _merge_response(GitMergeStatus.QUEUED, op_id=5)
        completed = _merge_response(GitMergeStatus.COMPLETED, op_id=5)
        with (
            patch(
                "pyado.oop.repos.repository.raw.post_git_merge",
                return_value=queued,
            ),
            patch(
                "pyado.oop.repos.repository.raw.get_git_merge",
                return_value=completed,
            ) as mock_get,
            patch("pyado.oop.repos.repository.time.sleep"),
        ):
            result = repo.check_merge_feasible(_SHA_A, _SHA_B)
        assert result is True
        mock_get.assert_called_once_with(repo.api_call, 5)

    def test_check_merge_feasible_raises_for_invalid_refs(self) -> None:
        repo = _make_repo()
        with (
            patch(
                "pyado.oop.repos.repository.raw.post_git_merge",
                return_value=_merge_response(GitMergeStatus.INVALID_REFS),
            ),
            pytest.raises(AzureDevOpsNotFoundError),
        ):
            repo.check_merge_feasible(_SHA_A, _SHA_B)

    def test_check_merge_feasible_raises_timeout_when_always_queued(self) -> None:
        repo = _make_repo()
        queued = _merge_response(GitMergeStatus.QUEUED, op_id=7)
        with (
            patch(
                "pyado.oop.repos.repository.raw.post_git_merge",
                return_value=queued,
            ),
            patch(
                "pyado.oop.repos.repository.raw.get_git_merge",
                return_value=queued,
            ),
            patch(
                "pyado.oop.repos.repository.time.monotonic",
                side_effect=[0.0, 0.0, 99.0],
            ),
            patch("pyado.oop.repos.repository.time.sleep"),
            pytest.raises(TimeoutError),
        ):
            repo.check_merge_feasible(_SHA_A, _SHA_B, timeout=10.0)

    def test_check_merge_feasible_skips_poll_when_operation_id_is_none(self) -> None:
        # When operation_id is None, get_git_merge is not called even inside the loop.
        # The loop runs once (not yet timed out), skips the poll, then times out.
        repo = _make_repo()
        queued_no_id = GitMergeResponse.model_validate({"status": "queued"})
        with (
            patch(
                "pyado.oop.repos.repository.raw.post_git_merge",
                return_value=queued_no_id,
            ),
            patch(
                "pyado.oop.repos.repository.time.monotonic",
                side_effect=[0.0, 0.0, 99.0],
            ),
            patch("pyado.oop.repos.repository.time.sleep"),
            patch(
                "pyado.oop.repos.repository.raw.get_git_merge",
            ) as mock_get,
            pytest.raises(TimeoutError),
        ):
            repo.check_merge_feasible(_SHA_A, _SHA_B, timeout=10.0)
        mock_get.assert_not_called()


class TestRepositoryCherryPick:
    """Tests for start_cherry_pick and get_cherry_pick_status."""

    def test_start_cherry_pick_returns_response(self) -> None:
        repo = _make_repo()
        response = _cherry_pick_response(GitCherryPickStatus.QUEUED)
        with patch(
            "pyado.oop.repos.repository.raw.post_git_cherry_pick",
            return_value=response,
        ) as mock_post:
            result = repo.start_cherry_pick("main", "cherry-pick-branch")
        assert isinstance(result, GitCherryPickResponse)
        assert result.status == GitCherryPickStatus.QUEUED
        request = mock_post.call_args.args[1]
        assert request.onto == "refs/heads/main"
        assert request.cherry_pick_ref == "refs/heads/cherry-pick-branch"

    def test_start_cherry_pick_normalises_full_refs(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_cherry_pick",
            return_value=_cherry_pick_response(GitCherryPickStatus.QUEUED),
        ) as mock_post:
            repo.start_cherry_pick("refs/heads/main", "refs/heads/cherry-pick-branch")
        request = mock_post.call_args.args[1]
        assert request.onto == "refs/heads/main"
        assert request.cherry_pick_ref == "refs/heads/cherry-pick-branch"

    def test_start_cherry_pick_uses_repository_api_call(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_cherry_pick",
            return_value=_cherry_pick_response(GitCherryPickStatus.QUEUED),
        ) as mock_post:
            repo.start_cherry_pick("main", "cherry-pick-branch")
        assert mock_post.call_args.args[0] is repo.api_call

    def test_get_cherry_pick_status_returns_response(self) -> None:
        repo = _make_repo()
        response = _cherry_pick_response(GitCherryPickStatus.COMPLETED)
        with patch(
            "pyado.oop.repos.repository.raw.get_git_cherry_pick",
            return_value=response,
        ) as mock_get:
            result = repo.get_cherry_pick_status(10)
        assert result.status == GitCherryPickStatus.COMPLETED
        mock_get.assert_called_once_with(repo.api_call, 10)


class TestRepositoryRevert:
    """Tests for start_revert and get_revert_status."""

    def test_start_revert_returns_response(self) -> None:
        repo = _make_repo()
        response = _revert_response(GitRevertStatus.QUEUED)
        with patch(
            "pyado.oop.repos.repository.raw.post_git_revert",
            return_value=response,
        ) as mock_post:
            result = repo.start_revert("main", "revert-branch")
        assert isinstance(result, GitRevertResponse)
        assert result.status == GitRevertStatus.QUEUED
        request = mock_post.call_args.args[1]
        assert request.onto == "refs/heads/main"
        assert request.revert_ref == "refs/heads/revert-branch"

    def test_start_revert_normalises_full_refs(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_revert",
            return_value=_revert_response(GitRevertStatus.QUEUED),
        ) as mock_post:
            repo.start_revert("refs/heads/main", "refs/heads/revert-branch")
        request = mock_post.call_args.args[1]
        assert request.onto == "refs/heads/main"
        assert request.revert_ref == "refs/heads/revert-branch"

    def test_start_revert_uses_repository_api_call(self) -> None:
        repo = _make_repo()
        with patch(
            "pyado.oop.repos.repository.raw.post_git_revert",
            return_value=_revert_response(GitRevertStatus.QUEUED),
        ) as mock_post:
            repo.start_revert("main", "revert-branch")
        assert mock_post.call_args.args[0] is repo.api_call

    def test_get_revert_status_returns_response(self) -> None:
        repo = _make_repo()
        response = _revert_response(GitRevertStatus.COMPLETED)
        with patch(
            "pyado.oop.repos.repository.raw.get_git_revert",
            return_value=response,
        ) as mock_get:
            result = repo.get_revert_status(20)
        assert result.status == GitRevertStatus.COMPLETED
        mock_get.assert_called_once_with(repo.api_call, 20)
