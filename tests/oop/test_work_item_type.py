"""Tests for pyado.oop WorkItemType and ProjectBoards work item type methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import pytest

from pyado.oop.boards.work_item_type import WorkItemType
from pyado.raw import (
    WorkItemFieldInfo,
    WorkItemStateInfo,
    WorkItemTypeCategoryInfo,
    WorkItemTypeInfo,
)
from tests.oop.conftest import (
    _make_project,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _wit_info(name: str = "Bug") -> WorkItemTypeInfo:
    return WorkItemTypeInfo.model_validate(
        {
            "name": name,
            "referenceName": f"Microsoft.VSTS.WorkItemTypes.{name}",
            "description": f"A {name} work item type",
            "color": "CC293D",
            "icon": {
                "id": "icon_insect",
                "url": "https://dev.azure.com/_apis/wit/workItemIcons/icon_insect",
            },
            "isDisabled": False,
        }
    )


def _state_info(name: str = "Active") -> WorkItemStateInfo:
    return WorkItemStateInfo.model_validate(
        {"name": name, "color": "0078d4", "stateCategory": "InProgress"}
    )


def _field_info(name: str = "Title") -> WorkItemFieldInfo:
    return WorkItemFieldInfo.model_validate(
        {
            "name": name,
            "referenceName": f"System.{name}",
            "type": "string",
            "readOnly": False,
            "required": True,
        }
    )


def _category_info(name: str = "Bug Category") -> WorkItemTypeCategoryInfo:
    return WorkItemTypeCategoryInfo.model_validate(
        {
            "name": name,
            "referenceName": "Microsoft.BugCategory",
        }
    )


# ---------------------------------------------------------------------------
# WorkItemType class
# ---------------------------------------------------------------------------


class TestWorkItemTypeProperties:
    def _make_wit(self, name: str = "Bug") -> WorkItemType:
        return WorkItemType(_make_project(), _wit_info(name))

    def test_name_returns_name(self) -> None:
        assert self._make_wit("Task").name == "Task"

    def test_description_returns_description(self) -> None:
        wit = self._make_wit()
        assert wit.description == "A Bug work item type"

    def test_color_returns_hex_string(self) -> None:
        assert self._make_wit().color == "CC293D"

    def test_icon_returns_icon_object(self) -> None:
        icon = self._make_wit().icon
        assert icon is not None
        assert icon.id == "icon_insect"

    def test_reference_name_returns_reference_name(self) -> None:
        wit = self._make_wit()
        assert "Bug" in wit.reference_name

    def test_info_returns_stored_info(self) -> None:
        info = _wit_info()
        wit = WorkItemType(_make_project(), info)
        assert wit.info is info

    def test_project_back_reference(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        assert wit.project is proj

    def test_org_back_reference(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        assert wit.org is proj.org

    def test_color_can_be_none(self) -> None:
        info = WorkItemTypeInfo.model_validate(
            {
                "name": "NoColor",
                "referenceName": "Custom.NoColor",
                "description": "",
                "isDisabled": False,
            }
        )
        wit = WorkItemType(_make_project(), info)
        assert wit.color is None


class TestWorkItemTypeStates:
    def test_iter_states_yields_state_infos(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        state = _state_info()
        with patch(
            "pyado.oop.boards.work_item_type.raw.iter_work_item_type_states"
        ) as mock_get:
            mock_get.return_value = [state]
            result = list(wit.iter_states())
        assert len(result) == 1
        assert isinstance(result[0], WorkItemStateInfo)

    def test_list_states_returns_list(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        state = _state_info()
        with patch(
            "pyado.oop.boards.work_item_type.raw.list_work_item_type_states"
        ) as mock_get:
            mock_get.return_value = [state]
            result = wit.list_states()
        assert len(result) == 1

    def test_iter_states_passes_type_name(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info("Task"))
        with patch(
            "pyado.oop.boards.work_item_type.raw.iter_work_item_type_states"
        ) as mock_get:
            mock_get.return_value = []
            list(wit.iter_states())
        args = mock_get.call_args[0]
        assert args[1] == "Task"


class TestWorkItemTypeFields:
    def test_iter_fields_yields_field_infos(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        field = _field_info()
        with patch(
            "pyado.oop.boards.work_item_type.raw.iter_work_item_type_fields"
        ) as mock_get:
            mock_get.return_value = [field]
            result = list(wit.iter_fields())
        assert len(result) == 1
        assert isinstance(result[0], WorkItemFieldInfo)

    def test_list_fields_returns_list(self) -> None:
        proj = _make_project()
        wit = WorkItemType(proj, _wit_info())
        field = _field_info()
        with patch(
            "pyado.oop.boards.work_item_type.raw.list_work_item_type_fields"
        ) as mock_get:
            mock_get.return_value = [field]
            result = wit.list_fields()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# ProjectBoards work item type methods
# ---------------------------------------------------------------------------


class TestProjectBoardsWorkItemTypes:
    def test_iter_work_item_types_yields_wrappers(self) -> None:
        proj = _make_project()
        info = _wit_info()
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_types"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(proj.boards.iter_work_item_types())
        assert len(result) == 1
        assert isinstance(result[0], WorkItemType)
        assert result[0].name == info.name

    def test_iter_work_item_types_empty(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_types"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(proj.boards.iter_work_item_types())
        assert result == []

    def test_list_work_item_types_delegates(self) -> None:
        proj = _make_project()
        boards = proj.boards
        with patch.object(boards, "iter_work_item_types", return_value=iter([])):
            assert boards.list_work_item_types() == []

    def test_get_work_item_type_found_by_name(self) -> None:
        proj = _make_project()
        info = _wit_info("UserStory")
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_types"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = proj.boards.get_work_item_type("UserStory")
        assert isinstance(result, WorkItemType)
        assert result.name == "UserStory"

    def test_get_work_item_type_skips_non_matching(self) -> None:
        proj = _make_project()
        info = _wit_info("Bug")
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_types"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            with pytest.raises(KeyError):
                proj.boards.get_work_item_type("Task")

    def test_get_work_item_type_raises_key_error_when_empty(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_types"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            with pytest.raises(KeyError):
                proj.boards.get_work_item_type("Anything")

    def test_iter_work_item_type_categories_yields_infos(self) -> None:
        proj = _make_project()
        cat = _category_info()
        with patch(
            "pyado.oop.boards.project_boards.raw.iter_work_item_type_categories"
        ) as mock_iter:
            mock_iter.return_value = iter([cat])
            result = list(proj.boards.iter_work_item_type_categories())
        assert len(result) == 1
        assert isinstance(result[0], WorkItemTypeCategoryInfo)

    def test_list_work_item_type_categories_delegates(self) -> None:
        proj = _make_project()
        cat = _category_info()
        boards = proj.boards
        with patch.object(
            boards, "iter_work_item_type_categories", return_value=iter([cat])
        ):
            result = boards.list_work_item_type_categories()
        assert len(result) == 1
