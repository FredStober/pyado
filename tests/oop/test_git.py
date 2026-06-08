"""Tests for pyado.oop._git — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from pyado.oop import AddFile, DeleteFile, EditFile, RenameFile
from pyado.oop.repos._git import (
    add_file,
    create_ref_update,
    create_ref_update_from_sha,
    delete_file,
    edit_file,
    make_commit,
    push_commits,
    rename_file,
)
from pyado.raw import (
    ZERO_SHA,
    ApiCall,
    GitPushRefUpdate,
    GitPushResult,
    get_repository_api_call,
    make_ref_update,
)
from tests.conftest import _make_mock_response

REPO_ID = uuid4()


@pytest.fixture
def repo_api_call(api_call: ApiCall) -> ApiCall:
    """Return a repository-level ApiCall.

    Returns:
        A repository-level ApiCall for testing.
    """
    return get_repository_api_call(api_call, REPO_ID)


class TestPush:
    """Tests for post_push."""

    @staticmethod
    def _make_push_response() -> dict[str, Any]:
        """Return a minimal push API response dict."""
        return {
            "pushId": 42,
            "commits": [{"commitId": "newsha123"}],
        }

    def test_returns_git_push_result(self, repo_api_call: ApiCall) -> None:
        """Returns a GitPushResult with pushId and commits."""
        mock_response = _make_mock_response(self._make_push_response())
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = push_commits(
                repo_api_call,
                [make_ref_update("main", "oldsha")],
                [
                    make_commit(
                        "Update config",
                        [edit_file("/config/x.json", '{"key": "value"}')],
                    )
                ],
            )
        assert isinstance(result, GitPushResult)
        assert result.push_id == 42
        assert result.commits[0].commit_id == "newsha123"

    def test_serialises_ref_update(self, repo_api_call: ApiCall) -> None:
        """ref_updates are serialised with the correct camelCase keys."""
        mock_response = _make_mock_response(self._make_push_response())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            push_commits(
                repo_api_call,
                [make_ref_update("refs/heads/main", "oldsha")],
                [make_commit("msg", [edit_file("/f.txt", "x")])],
            )
        body = mock_req.call_args.kwargs["json"]
        assert body["refUpdates"][0]["name"] == "refs/heads/main"
        assert body["refUpdates"][0]["oldObjectId"] == "oldsha"

    def test_delete_change_omits_new_content(self, repo_api_call: ApiCall) -> None:
        """A delete change does not include newContent in the payload."""
        mock_response = _make_mock_response(self._make_push_response())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            push_commits(
                repo_api_call,
                [make_ref_update("main", "oldsha")],
                [make_commit("Delete file", [delete_file("/f.txt")])],
            )
        body = mock_req.call_args.kwargs["json"]
        change = body["commits"][0]["changes"][0]
        assert "newContent" not in change

    def test_multiple_changes_in_one_commit(self, repo_api_call: ApiCall) -> None:
        """Multiple file changes can be submitted in a single commit."""
        mock_response = _make_mock_response(self._make_push_response())
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            push_commits(
                repo_api_call,
                [make_ref_update("main", "oldsha")],
                [
                    make_commit(
                        "Batch update",
                        [edit_file("/a.txt", "a"), add_file("/b.txt", "b")],
                    )
                ],
            )
        body = mock_req.call_args.kwargs["json"]
        assert len(body["commits"][0]["changes"]) == 2


class TestCreateRefUpdate:
    """Tests for create_ref_update."""

    @staticmethod
    def _make_refs_response(sha: str) -> dict[str, Any]:
        return {"value": [{"name": "refs/heads/main", "objectId": sha}]}

    def test_returns_ref_update_with_fetched_sha(self, repo_api_call: ApiCall) -> None:
        """Returns a GitPushRefUpdate with the SHA returned by the refs endpoint."""
        mock_response = _make_mock_response(self._make_refs_response("abc123"))
        with patch.object(requests.Session, "request", return_value=mock_response):
            ref = create_ref_update(repo_api_call, "main")
        assert ref.name == "refs/heads/main"
        assert ref.old_object_id == "abc123"

    def test_adds_refs_heads_prefix(self, repo_api_call: ApiCall) -> None:
        """A bare branch name is normalised to a full ref."""
        mock_response = _make_mock_response(self._make_refs_response("sha999"))
        with patch.object(requests.Session, "request", return_value=mock_response):
            ref = create_ref_update(repo_api_call, "feature/my-branch")
        assert ref.name == "refs/heads/feature/my-branch"

    def test_passes_name_filter_to_refs_endpoint(self, repo_api_call: ApiCall) -> None:
        """The refs endpoint is called with the correct name_filter."""
        mock_response = _make_mock_response(self._make_refs_response("sha999"))
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            create_ref_update(repo_api_call, "main")
        assert "heads/main" in mock_req.call_args.kwargs["params"]["filter"]


class TestCreateRefUpdateFromSha:
    """Tests for create_ref_update_from_sha."""

    def test_returns_ref_update_with_given_sha(self, repo_api_call: ApiCall) -> None:
        result = create_ref_update_from_sha(repo_api_call, "main", "abc123sha")
        assert isinstance(result, GitPushRefUpdate)
        assert result.old_object_id == "abc123sha"

    def test_normalises_short_branch_name(self, repo_api_call: ApiCall) -> None:
        result = create_ref_update_from_sha(repo_api_call, "feature/x", "sha456")
        assert isinstance(result, GitPushRefUpdate)
        assert result.name == "refs/heads/feature/x"


class TestHighLevelHelpers:
    """Tests for add_file, edit_file, delete_file, rename_file, make_commit.

    Also covers make_ref_update.
    """

    @staticmethod
    def test_add_file_sets_change_type_and_content() -> None:
        """add_file produces changeType 'add' with newContent."""
        change = add_file("/src/new.py", "print('hello')")
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["changeType"] == "add"
        assert dumped["item"]["path"] == "/src/new.py"
        assert dumped["newContent"]["content"] == "print('hello')"

    @staticmethod
    def test_edit_file_sets_change_type_and_content() -> None:
        """edit_file produces changeType 'edit' with newContent."""
        change = edit_file("/src/foo.py", "x = 1")
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["changeType"] == "edit"
        assert dumped["item"]["path"] == "/src/foo.py"
        assert dumped["newContent"]["content"] == "x = 1"

    @staticmethod
    def test_delete_file_omits_new_content() -> None:
        """delete_file produces changeType 'delete' with no newContent."""
        change = delete_file("/src/old.py")
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["changeType"] == "delete"
        assert dumped["item"]["path"] == "/src/old.py"
        assert "newContent" not in dumped

    @staticmethod
    def test_rename_file_sets_source_server_item() -> None:
        """rename_file produces changeType 'rename' with sourceServerItem."""
        change = rename_file("/old/path.py", "/new/path.py")
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["changeType"] == "rename"
        assert dumped["item"]["path"] == "/new/path.py"
        assert dumped["sourceServerItem"] == "/old/path.py"
        assert "newContent" not in dumped

    @staticmethod
    def test_make_commit_sets_comment_and_changes() -> None:
        """make_commit wraps changes with the given message."""
        commit = make_commit("My message", [delete_file("/x.txt")])
        assert commit.comment == "My message"
        assert len(commit.changes) == 1

    @staticmethod
    def test_make_ref_update_adds_refs_heads_prefix() -> None:
        """make_ref_update normalises a bare branch name to a full ref."""
        ref = make_ref_update("main", "abc123")
        assert ref.name == "refs/heads/main"
        assert ref.old_object_id == "abc123"

    @staticmethod
    def test_make_ref_update_preserves_full_ref() -> None:
        """make_ref_update leaves an already-qualified ref unchanged."""
        ref = make_ref_update("refs/heads/main", "abc123")
        assert ref.name == "refs/heads/main"

    @staticmethod
    def test_make_ref_update_accepts_zero_sha() -> None:
        """make_ref_update accepts ZERO_SHA for new-branch pushes."""
        ref = make_ref_update("feature/new", ZERO_SHA)
        assert ref.old_object_id == ZERO_SHA


# ---------------------------------------------------------------------------
# OOP AddFile, EditFile, DeleteFile, RenameFile tests
# ---------------------------------------------------------------------------


class TestAddFile:
    def test_to_git_change_type(self) -> None:
        change = AddFile("/foo.py", "content").to_git_change()
        assert change.change_type.value == "add"

    def test_to_git_change_path(self) -> None:
        change = AddFile("/foo.py", "content").to_git_change()
        assert change.item.path == "/foo.py"

    def test_text_content_is_rawtext(self) -> None:
        change = AddFile("/foo.py", "hello").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "hello"
        assert change.new_content.content_type.value == "rawtext"

    def test_bytes_content_is_base64(self) -> None:
        change = AddFile("/img.png", b"\x89PNG").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content_type.value == "base64encoded"
        assert base64.b64decode(change.new_content.content) == b"\x89PNG"

    def test_path_text_file_is_rawtext(self, tmp_path: Path) -> None:
        text_file = tmp_path / "hello.txt"
        text_file.write_text("hello world", encoding="utf-8")
        change = AddFile("/hello.txt", Path(text_file)).to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "hello world"
        assert change.new_content.content_type.value == "rawtext"

    def test_path_binary_file_is_base64(self, tmp_path: Path) -> None:
        bin_file = tmp_path / "data.bin"
        bin_file.write_bytes(b"\x00\x01\x02\xff")
        change = AddFile("/data.bin", Path(bin_file)).to_git_change()
        assert change.new_content is not None
        assert change.new_content.content_type.value == "base64encoded"
        assert base64.b64decode(change.new_content.content) == b"\x00\x01\x02\xff"


class TestEditFile:
    def test_to_git_change_type(self) -> None:
        change = EditFile("/foo.py", "new content").to_git_change()
        assert change.change_type.value == "edit"

    def test_to_git_change_path(self) -> None:
        change = EditFile("/src/bar.py", "x").to_git_change()
        assert change.item.path == "/src/bar.py"

    def test_text_content(self) -> None:
        change = EditFile("/f.py", "updated").to_git_change()
        assert change.new_content is not None
        assert change.new_content.content == "updated"


class TestDeleteFile:
    def test_to_git_change_type(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.change_type.value == "delete"

    def test_to_git_change_path(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.item.path == "/old.py"

    def test_no_new_content(self) -> None:
        change = DeleteFile("/old.py").to_git_change()
        assert change.new_content is None


class TestRenameFile:
    def test_to_git_change_type(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.change_type.value == "rename"

    def test_new_path_in_item(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.item.path == "/new.py"

    def test_old_path_in_source_server_item(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.source_server_item == "/old.py"

    def test_no_new_content(self) -> None:
        change = RenameFile("/old.py", "/new.py").to_git_change()
        assert change.new_content is None
