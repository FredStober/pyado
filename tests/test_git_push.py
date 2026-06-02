"""Tests for pyado.git_push module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests

from pyado.api_call import ApiCall
from pyado.git_push import (
    GitPushChange,
    GitPushChangeItem,
    GitPushCommit,
    GitPushNewContent,
    GitPushRefUpdate,
    GitPushResult,
    add_file,
    delete_file,
    edit_file,
    make_commit,
    make_ref_update,
    push,
    rename_file,
)
from pyado.repository import ZERO_SHA, get_repository_api_call

REPO_ID = uuid4()


def _make_mock_response(json_data: Any) -> MagicMock:
    """Create a minimal mock HTTP response.

    Returns:
        A MagicMock configured to behave as a requests.Response.
    """
    mock = MagicMock(spec=requests.Response)
    mock.raise_for_status.return_value = None
    mock.json.return_value = json_data
    mock.content = jsonlib.dumps(json_data).encode()
    return mock


@pytest.fixture
def repo_api_call(api_call: ApiCall) -> ApiCall:
    """Return a repository-level ApiCall.

    Returns:
        A repository-level ApiCall for testing.
    """
    return get_repository_api_call(api_call, REPO_ID)


class TestPush:
    """Tests for push."""

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
            result = push(
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
            push(
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
            push(
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
            push(
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


class TestLowLevelModels:
    """Serialisation tests for the low-level REST models."""

    @staticmethod
    def test_git_push_change_serialises_camel_case() -> None:
        """GitPushChange serialises field names to camelCase aliases."""
        change = GitPushChange(
            change_type="edit",
            item=GitPushChangeItem(path="/f.txt"),
            new_content=GitPushNewContent(content="hello"),
        )
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["changeType"] == "edit"
        assert dumped["item"]["path"] == "/f.txt"
        assert dumped["newContent"]["content"] == "hello"
        assert dumped["newContent"]["contentType"] == "rawtext"

    @staticmethod
    def test_git_push_ref_update_serialises_old_object_id() -> None:
        """GitPushRefUpdate serialises oldObjectId correctly."""
        ref = GitPushRefUpdate(name="refs/heads/main", old_object_id="abc123")
        dumped = ref.model_dump(mode="json", by_alias=True)
        assert dumped["oldObjectId"] == "abc123"

    @staticmethod
    def test_git_push_commit_contains_changes() -> None:
        """GitPushCommit preserves all changes passed to it."""
        commit = GitPushCommit(
            comment="msg",
            changes=[
                GitPushChange(
                    change_type="add",
                    item=GitPushChangeItem(path="/a.txt"),
                    new_content=GitPushNewContent(content="a"),
                ),
                GitPushChange(
                    change_type="delete",
                    item=GitPushChangeItem(path="/b.txt"),
                ),
            ],
        )
        assert len(commit.changes) == 2

    @staticmethod
    def test_rename_change_includes_source_server_item() -> None:
        """A rename change serialises sourceServerItem."""
        change = GitPushChange(
            change_type="rename",
            item=GitPushChangeItem(path="/new.txt"),
            source_server_item="/old.txt",
        )
        dumped = change.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert dumped["sourceServerItem"] == "/old.txt"
        assert dumped["item"]["path"] == "/new.txt"


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
