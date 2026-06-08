"""Tests for pyado.oop Branch and Tag — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado import AzureDevOpsNotFoundError
from pyado.oop.repos.branch import Branch
from pyado.oop.repos.tag import Tag
from pyado.raw import AnnotatedTagInfo, GitRef
from tests.oop.conftest import _make_repo

_COMMIT_ID = uuid4()


def _make_git_ref(name: str) -> GitRef:
    return GitRef.model_validate({"name": name, "objectId": str(_COMMIT_ID)})


def _make_branch(name: str = "refs/heads/main") -> Branch:
    return Branch(_make_repo(), _make_git_ref(name))


def _make_tag(name: str = "refs/tags/v1.0") -> Tag:
    return Tag(_make_repo(), _make_git_ref(name))


class TestBranch:
    def test_ref_returns_underlying_ref(self) -> None:
        ref = _make_git_ref("refs/heads/main")
        branch = Branch(_make_repo(), ref)
        assert branch.ref is ref

    def test_name_strips_prefix(self) -> None:
        branch = _make_branch("refs/heads/feature/x")
        assert branch.name == "feature/x"

    def test_full_name_returns_full_ref(self) -> None:
        branch = _make_branch("refs/heads/main")
        assert branch.full_name == "refs/heads/main"

    def test_commit_id_returns_object_id(self) -> None:
        branch = _make_branch()
        assert branch.commit_id == str(_COMMIT_ID)

    def test_repo_returns_back_reference(self) -> None:
        repo = _make_repo()
        branch = Branch(repo, _make_git_ref("refs/heads/main"))
        assert branch.repo is repo

    def test_get_commit_delegates_to_repo(self) -> None:
        repo = _make_repo()
        branch = Branch(repo, _make_git_ref("refs/heads/main"))
        mock_commit = MagicMock()
        with patch.object(repo, "get_commit", return_value=mock_commit) as mock_get:
            result = branch.get_commit()
        assert result is mock_commit
        mock_get.assert_called_once_with(str(_COMMIT_ID))

    def test_delete_delegates_to_repo(self) -> None:
        repo = _make_repo()
        branch = Branch(repo, _make_git_ref("refs/heads/main"))
        with patch.object(repo, "delete_branch") as mock_del:
            branch.delete()
        mock_del.assert_called_once_with("main", str(_COMMIT_ID))


class TestTag:
    def test_constructor_stores_repo_and_ref(self) -> None:
        repo = _make_repo()
        ref = _make_git_ref("refs/tags/v1.0")
        tag = Tag(repo, ref)
        assert tag._repo is repo
        assert tag._ref is ref

    def test_ref_returns_underlying_ref(self) -> None:
        ref = _make_git_ref("refs/tags/v2.0")
        tag = Tag(_make_repo(), ref)
        assert tag.ref is ref

    def test_name_strips_prefix(self) -> None:
        tag = _make_tag("refs/tags/v1.2.3")
        assert tag.name == "v1.2.3"

    def test_full_name_returns_full_ref(self) -> None:
        tag = _make_tag("refs/tags/v1.0")
        assert tag.full_name == "refs/tags/v1.0"

    def test_commit_id_returns_object_id(self) -> None:
        tag = _make_tag()
        assert tag.commit_id == str(_COMMIT_ID)

    def test_repo_returns_back_reference(self) -> None:
        repo = _make_repo()
        tag = Tag(repo, _make_git_ref("refs/tags/v1.0"))
        assert tag.repo is repo

    def test_get_commit_delegates_to_repo(self) -> None:
        repo = _make_repo()
        tag = Tag(repo, _make_git_ref("refs/tags/v1.0"))
        mock_commit = MagicMock()
        with patch.object(repo, "get_commit", return_value=mock_commit) as mock_get:
            result = tag.get_commit()
        assert result is mock_commit
        mock_get.assert_called_once_with(str(_COMMIT_ID))

    def test_get_commit_falls_back_for_annotated_tag(self) -> None:
        # When get_commit raises NotFoundError, dereference via get_annotated_tag.
        commit_sha = str(uuid4())
        mock_commit = MagicMock()
        tag_info = AnnotatedTagInfo.model_validate(
            {
                "objectId": str(_COMMIT_ID),
                "name": "v1.0",
                "taggedObject": {"objectId": commit_sha, "objectType": "commit"},
            }
        )
        repo = _make_repo()
        tag = Tag(repo, _make_git_ref("refs/tags/v1.0"))

        def _get_commit_side_effect(sha: str) -> MagicMock:
            if sha == str(_COMMIT_ID):
                raise AzureDevOpsNotFoundError(404, "not found")
            return mock_commit

        with (
            patch.object(repo, "get_commit", side_effect=_get_commit_side_effect),
            patch("pyado.oop.repos.tag.raw.get_annotated_tag", return_value=tag_info),
        ):
            result = tag.get_commit()
        assert result is mock_commit

    def test_get_commit_reraises_when_tagged_object_none(self) -> None:
        tag_info = AnnotatedTagInfo.model_validate(
            {"objectId": str(_COMMIT_ID), "name": "v1.0"}
        )
        repo = _make_repo()
        tag = Tag(repo, _make_git_ref("refs/tags/v1.0"))
        with (
            patch.object(
                repo,
                "get_commit",
                side_effect=AzureDevOpsNotFoundError(404, "not found"),
            ),
            patch("pyado.oop.repos.tag.raw.get_annotated_tag", return_value=tag_info),
            pytest.raises(AzureDevOpsNotFoundError),
        ):
            tag.get_commit()

    def test_delete_delegates_to_repo(self) -> None:
        repo = _make_repo()
        tag = Tag(repo, _make_git_ref("refs/tags/v1.0"))
        with patch.object(repo, "delete_tag") as mock_del:
            tag.delete()
        mock_del.assert_called_once_with("v1.0", str(_COMMIT_ID))
