"""Tests for pyado.oop TaskGroup and ProjectPipelines task group methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from pyado.oop.pipelines.task_group import TaskGroup
from pyado.raw import (
    TaskGroupCreateRequest,
    TaskGroupId,
    TaskGroupInfo,
    TaskGroupUpdateRequest,
)
from tests.oop.conftest import _make_project

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _task_group_info(
    name: str = "My Task Group",
    task_group_id: TaskGroupId | None = None,
    tasks: list[dict[str, Any]] | None = None,
) -> TaskGroupInfo:
    return TaskGroupInfo.model_validate(
        {
            "id": str(task_group_id or uuid4()),
            "name": name,
            "description": "A test task group",
            "category": "Build",
            "tasks": tasks or [],
        }
    )


def _make_task_group(name: str = "My Task Group") -> TaskGroup:
    return TaskGroup(_make_project(), _task_group_info(name))


def _make_update_request(task_group_id: TaskGroupId) -> TaskGroupUpdateRequest:
    return TaskGroupUpdateRequest(
        id=task_group_id,
        name="Updated Task Group",
        tasks=[],
    )


def _make_create_request() -> TaskGroupCreateRequest:
    return TaskGroupCreateRequest(
        name="New Task Group",
        tasks=[],
    )


# ---------------------------------------------------------------------------
# TaskGroup class properties
# ---------------------------------------------------------------------------


class TestTaskGroupProperties:
    def test_id_returns_uuid(self) -> None:
        info = _task_group_info()
        tg = TaskGroup(_make_project(), info)
        assert tg.id == info.id

    def test_name_returns_name(self) -> None:
        info = _task_group_info("CI Steps")
        tg = TaskGroup(_make_project(), info)
        assert tg.name == "CI Steps"

    def test_description_returns_description(self) -> None:
        tg = _make_task_group()
        assert tg.description == "A test task group"

    def test_category_returns_category(self) -> None:
        tg = _make_task_group()
        assert tg.category == "Build"

    def test_description_none_when_absent(self) -> None:
        info = TaskGroupInfo.model_validate(
            {"id": str(uuid4()), "name": "Minimal", "tasks": []}
        )
        tg = TaskGroup(_make_project(), info)
        assert tg.description is None

    def test_category_none_when_absent(self) -> None:
        info = TaskGroupInfo.model_validate(
            {"id": str(uuid4()), "name": "Minimal", "tasks": []}
        )
        tg = TaskGroup(_make_project(), info)
        assert tg.category is None

    def test_info_returns_stored_info(self) -> None:
        info = _task_group_info()
        tg = TaskGroup(_make_project(), info)
        assert tg.info is info

    def test_project_back_reference(self) -> None:
        proj = _make_project()
        tg = TaskGroup(proj, _task_group_info())
        assert tg.project is proj

    def test_org_back_reference(self) -> None:
        proj = _make_project()
        tg = TaskGroup(proj, _task_group_info())
        assert tg.org is proj.org


# ---------------------------------------------------------------------------
# TaskGroup.refresh
# ---------------------------------------------------------------------------


class TestTaskGroupRefresh:
    def test_refresh_clears_info(self) -> None:
        tg = _make_task_group()
        tg.refresh()
        assert tg._info is None

    def test_info_re_fetches_after_refresh(self) -> None:
        info = _task_group_info()
        tg = TaskGroup(_make_project(), info)
        tg.refresh()
        with patch(
            "pyado.oop.pipelines.task_group.raw.get_task_group",
            return_value=info,
        ) as mock_get:
            result = tg.info
        mock_get.assert_called_once()
        assert result is info


# ---------------------------------------------------------------------------
# TaskGroup.update
# ---------------------------------------------------------------------------


class TestTaskGroupUpdate:
    def test_update_refreshes_cached_info(self) -> None:
        info = _task_group_info()
        proj = _make_project()
        tg = TaskGroup(proj, info)
        updated_info = _task_group_info("Updated Task Group")
        request = _make_update_request(info.id)
        with patch(
            "pyado.oop.pipelines.task_group.raw.put_task_group",
            return_value=updated_info,
        ) as mock_put:
            tg.update(request)
        mock_put.assert_called_once_with(proj.api_call, info.id, request)
        assert tg._info is updated_info

    def test_update_uses_project_api_call(self) -> None:
        info = _task_group_info()
        proj = _make_project()
        tg = TaskGroup(proj, info)
        request = _make_update_request(info.id)
        captured: list[object] = []

        def _side_effect(api_call: object, *_a: object, **_kw: object) -> TaskGroupInfo:
            captured.append(api_call)
            return _task_group_info()

        with patch(
            "pyado.oop.pipelines.task_group.raw.put_task_group",
            side_effect=_side_effect,
        ):
            tg.update(request)
        assert captured[0] is proj.api_call


# ---------------------------------------------------------------------------
# TaskGroup.delete
# ---------------------------------------------------------------------------


class TestTaskGroupDelete:
    def test_delete_calls_raw(self) -> None:
        info = _task_group_info()
        proj = _make_project()
        tg = TaskGroup(proj, info)
        with patch("pyado.oop.pipelines.task_group.raw.delete_task_group") as mock_del:
            tg.delete()
        mock_del.assert_called_once_with(proj.api_call, info.id)

    def test_delete_clears_info(self) -> None:
        tg = _make_task_group()
        with patch("pyado.oop.pipelines.task_group.raw.delete_task_group"):
            tg.delete()
        assert tg._info is None


# ---------------------------------------------------------------------------
# ProjectPipelines task group methods
# ---------------------------------------------------------------------------


class TestProjectPipelinesTaskGroups:
    def test_iter_task_groups_yields_wrappers(self) -> None:
        proj = _make_project()
        info = _task_group_info()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_task_groups"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(proj.pipelines.iter_task_groups())
        assert len(result) == 1
        assert isinstance(result[0], TaskGroup)
        assert result[0].name == info.name

    def test_iter_task_groups_empty(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_task_groups"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(proj.pipelines.iter_task_groups())
        assert result == []

    def test_list_task_groups_delegates(self) -> None:
        proj = _make_project()
        pipelines = proj.pipelines
        with patch.object(pipelines, "iter_task_groups", return_value=iter([])):
            assert pipelines.list_task_groups() == []

    def test_get_task_group_returns_matching(self) -> None:
        proj = _make_project()
        info = _task_group_info("Deploy Steps")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_task_groups",
            return_value=iter([info]),
        ):
            result = proj.pipelines.get_task_group("Deploy Steps")
        assert isinstance(result, TaskGroup)
        assert result.name == "Deploy Steps"

    def test_get_task_group_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_task_groups",
                return_value=iter([]),
            ),
            pytest.raises(KeyError),
        ):
            proj.pipelines.get_task_group("Missing")

    def test_get_task_group_raises_key_error_when_name_not_in_list(self) -> None:
        proj = _make_project()
        other_info = _task_group_info("Other Group")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_task_groups",
                return_value=iter([other_info]),
            ),
            pytest.raises(KeyError),
        ):
            proj.pipelines.get_task_group("Missing")

    def test_get_task_group_by_id_returns_wrapper(self) -> None:
        proj = _make_project()
        info = _task_group_info("By ID Group")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_task_group",
            return_value=info,
        ) as mock_get:
            result = proj.pipelines.get_task_group_by_id(info.id)
        mock_get.assert_called_once_with(proj.api_call, info.id)
        assert isinstance(result, TaskGroup)
        assert result.id == info.id

    def test_create_task_group_returns_wrapper(self) -> None:
        proj = _make_project()
        created_info = _task_group_info("New Task Group")
        request = _make_create_request()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.post_task_group",
            return_value=created_info,
        ) as mock_post:
            result = proj.pipelines.create_task_group(request)
        mock_post.assert_called_once_with(proj.api_call, request)
        assert isinstance(result, TaskGroup)
        assert result.name == "New Task Group"

    def test_create_task_group_uses_project_api_call(self) -> None:
        proj = _make_project()
        created_info = _task_group_info()
        request = _make_create_request()
        captured: list[object] = []

        def _side_effect(api_call: object, *_a: object, **_kw: object) -> TaskGroupInfo:
            captured.append(api_call)
            return created_info

        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.post_task_group",
            side_effect=_side_effect,
        ):
            proj.pipelines.create_task_group(request)
        assert captured[0] is proj.api_call
