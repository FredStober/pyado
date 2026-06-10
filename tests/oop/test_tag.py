"""Tests for pyado.oop Tag — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

from pyado.exceptions import AzureDevOpsNotFoundError
from pyado.oop import Tag
from pyado.raw import AnnotatedTagInfo, GitRef
from tests.oop.conftest import _make_repo


def _make_tag(name: str = "v1.0", sha: str = "abc000") -> Tag:
    ref = GitRef.model_validate({"name": f"refs/tags/{name}", "objectId": sha})
    return Tag(_make_repo(), ref)


def _annotated_tag_info(sha: str = "abc000") -> AnnotatedTagInfo:
    return AnnotatedTagInfo.model_validate(
        {
            "objectId": sha,
            "name": "v1.0",
            "message": "Release 1.0",
        }
    )


class TestTagProperties:
    def test_name_strips_prefix(self) -> None:
        tag = _make_tag("v2.3")
        assert tag.name == "v2.3"

    def test_full_name_includes_prefix(self) -> None:
        tag = _make_tag("v2.3")
        assert tag.full_name == "refs/tags/v2.3"

    def test_commit_id_returns_sha(self) -> None:
        tag = _make_tag(sha="deadbeef")
        assert tag.commit_id == "deadbeef"

    def test_repo_reference(self) -> None:
        repo = _make_repo()
        ref = GitRef.model_validate({"name": "refs/tags/v1.0", "objectId": "abc"})
        tag = Tag(repo, ref)
        assert tag.repo is repo

    def test_ref_returns_underlying_git_ref(self) -> None:
        ref = GitRef.model_validate({"name": "refs/tags/v1.0", "objectId": "abc"})
        tag = Tag(_make_repo(), ref)
        assert tag.ref is ref


class TestTagGetAnnotatedInfo:
    def test_returns_annotated_tag_info_for_annotated_tag(self) -> None:
        tag = _make_tag(sha="abc000")
        expected = _annotated_tag_info("abc000")
        with patch("pyado.oop.repos.tag.raw.get_annotated_tag", return_value=expected):
            result = tag.get_annotated_info()
        assert result is expected

    def test_returns_none_for_lightweight_tag(self) -> None:
        tag = _make_tag(sha="abc000")
        with patch(
            "pyado.oop.repos.tag.raw.get_annotated_tag",
            side_effect=AzureDevOpsNotFoundError(404, "not found"),
        ):
            result = tag.get_annotated_info()
        assert result is None

    def test_passes_commit_id_to_raw(self) -> None:
        tag = _make_tag(sha="deadbeef")
        expected = _annotated_tag_info("deadbeef")
        with patch(
            "pyado.oop.repos.tag.raw.get_annotated_tag", return_value=expected
        ) as mock_get:
            tag.get_annotated_info()
        assert mock_get.call_args.args[1] == "deadbeef"
