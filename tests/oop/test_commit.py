"""Tests for pyado.oop Commit — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

from pyado.oop import Commit, Project, PullRequest, Repository
from pyado.raw import GitCommitChange, GitCommitRef, GitCommitSearchCriteria, GitStatus
from tests.conftest import NOW_ISO
from tests.oop.conftest import (
    ORG_URL,
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


class TestCommit:
    def test_sha(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        assert commit.sha == "abc123"

    def test_message(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref())
        assert commit.message == "Test commit"

    def test_info_returns_git_commit_ref(self) -> None:
        ref = _git_commit_ref()
        commit = Commit(_make_repo(), ref)
        assert commit.info is ref

    def test_repo_reference(self) -> None:
        repo = _make_repo()
        commit = Commit(repo, _git_commit_ref())
        assert commit.repo is repo

    def test_project_via_repo(self) -> None:
        proj = _make_project()
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        commit = Commit(repo, _git_commit_ref())
        assert commit.project is proj

    def test_org_via_repo(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), svc)
        commit = Commit(repo, _git_commit_ref())
        assert commit.org is svc.org

    def _commit_with_author(self) -> Commit:
        ref = GitCommitRef.model_validate(
            {
                "commitId": "abc123",
                "comment": "msg",
                "commentTruncated": False,
                "author": {
                    "name": "Alice",
                    "email": "alice@example.com",
                    "date": NOW_ISO,
                },
                "committer": {
                    "name": "Bob",
                    "email": "bob@example.com",
                    "date": NOW_ISO,
                },
            }
        )
        return Commit(_make_repo(), ref)

    def test_author_name_returns_name(self) -> None:
        assert self._commit_with_author().author_name == "Alice"

    def test_author_email_returns_email(self) -> None:
        assert self._commit_with_author().author_email == "alice@example.com"

    def test_author_date_returns_datetime(self) -> None:
        assert self._commit_with_author().author_date is not None

    def test_committer_name_returns_name(self) -> None:
        assert self._commit_with_author().committer_name == "Bob"

    def test_committer_email_returns_email(self) -> None:
        assert self._commit_with_author().committer_email == "bob@example.com"

    def test_committer_date_returns_datetime(self) -> None:
        assert self._commit_with_author().committer_date is not None

    def test_get_file_delegates_to_high(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        with patch(
            "pyado.oop.repos.commit._git.get_file_content_at_commit"
        ) as mock_get:
            mock_get.return_value = "file content"
            result = commit.get_file("/src/foo.py")
        assert result == "file content"
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "/src/foo.py"
        assert mock_get.call_args.args[2] == "abc123"

    def test_iter_changes_yields_nothing_for_root_commit(self) -> None:
        ref = _git_commit_ref("root")
        ref.parents = []
        commit = Commit(_make_repo(), ref)
        result = list(commit.iter_changes())
        assert result == []

    def test_iter_changes_delegates_to_high(self) -> None:
        ref = GitCommitRef.model_validate(
            {
                "commitId": "child123",
                "comment": "msg",
                "commentTruncated": False,
                "parents": ["parent456"],
            }
        )
        change = MagicMock(spec=GitCommitChange)
        commit = Commit(_make_repo(), ref)
        with patch("pyado.oop.repos.commit._git.iter_commit_diff") as mock_diff:
            mock_diff.return_value = iter([change])
            result = list(commit.iter_changes())
        assert result == [change]
        assert mock_diff.call_args.args[1] == "parent456"
        assert mock_diff.call_args.args[2] == "child123"

    def test_list_statuses_returns_list(self) -> None:
        status = GitStatus.model_validate({"state": "succeeded"})
        ref = _git_commit_ref()
        ref.statuses = [status]
        commit = Commit(_make_repo(), ref)
        result = commit.list_statuses()
        assert result == [status]

    def test_list_statuses_empty_when_none(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref())
        assert commit.list_statuses() == []

    def test_refresh_invalidates_and_refetches(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        with patch("pyado.oop.repos.commit.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("abc123")
            commit.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            _ = commit.info
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "abc123"

    def test_refresh_stores_search_criteria_and_forwards_on_fetch(self) -> None:
        criteria = GitCommitSearchCriteria(item_path="/src")
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        with patch("pyado.oop.repos.commit.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("abc123")
            commit.refresh(search_criteria=criteria)
            _ = commit.info
        assert mock_get.call_args.kwargs["search_criteria"] is criteria

    def test_refresh_preserves_existing_criteria_when_none_passed(self) -> None:
        criteria = GitCommitSearchCriteria(item_path="/src")
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        with patch("pyado.oop.repos.commit.raw.get_commit_by_id") as mock_get:
            mock_get.return_value = _git_commit_ref("abc123")
            commit.refresh(search_criteria=criteria)
            _ = commit.info
            commit.refresh()
            _ = commit.info
        assert mock_get.call_args.kwargs["search_criteria"] is criteria


class TestCommitGetPullRequest:
    def test_get_pull_request_returns_pull_request_when_found(self) -> None:
        pr_item = _pr_list_item(77)
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([pr_item])
            with patch(
                "pyado.oop.repos.repository.raw.get_pull_request_api_call"
            ) as mock_pr_call:
                mock_pr_call.return_value = _api_call()
                commit = Commit(repo, _git_commit_ref("abc123"))
                result = commit.get_pull_request()
        assert isinstance(result, PullRequest)

    def test_get_pull_request_returns_none_when_not_found(self) -> None:
        repo = _make_repo()
        with patch("pyado.oop.repos.repository.raw.iter_pull_requests") as mock_iter:
            mock_iter.return_value = iter([])
            commit = Commit(repo, _git_commit_ref("abc123"))
            result = commit.get_pull_request()
        assert result is None


class TestCommitListMethods:
    def test_list_changes_delegates(self) -> None:
        commit = Commit(_make_repo(), _git_commit_ref("abc123"))
        with patch.object(commit, "iter_changes", return_value=iter([])):
            assert commit.list_changes() == []
