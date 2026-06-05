"""Tests for pyado.git_push module — raw layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.raw import (
    GitPushChange,
    GitPushChangeItem,
    GitPushCommit,
    GitPushNewContent,
    GitPushRefUpdate,
)


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
