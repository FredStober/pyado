"""Tests for pyado.oop Iteration and Area — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from datetime import date
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest

from pyado.oop import Area, Iteration, Project, Team
from pyado.raw import ClassificationNode, ClassificationNodeUrlType
from tests.oop.conftest import (
    _area_node,
    _iteration_node,
    _make_area,
    _make_iteration,
    _make_project,
    _make_service,
    _project_info,
    _team_info,
)


class TestIteration:
    def test_id(self) -> None:
        assert _make_iteration(node_id=5).id == 5

    def test_name(self) -> None:
        assert _make_iteration(name="Sprint 42").name == "Sprint 42"

    def test_path(self) -> None:
        it = _make_iteration(path="\\Proj\\Sprint 1")
        assert it.path == "\\Proj\\Sprint 1"

    def test_start_date(self) -> None:
        it = _make_iteration()
        assert it.start_date == date(2024, 1, 1)

    def test_finish_date(self) -> None:
        it = _make_iteration()
        assert it.finish_date == date(2024, 1, 14)

    def test_start_date_none_when_no_attributes(self) -> None:
        node = _iteration_node(start_date=None, finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.start_date is None

    def test_finish_date_none_when_no_attributes(self) -> None:
        node = _iteration_node(start_date=None, finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.finish_date is None

    def test_start_date_none_when_only_finish_date_set(self) -> None:
        node = _iteration_node(start_date=None, finish_date="2024-01-14T00:00:00Z")
        it = Iteration(_make_project(), node)
        assert it.start_date is None
        assert it.finish_date == date(2024, 1, 14)

    def test_finish_date_none_when_only_start_date_set(self) -> None:
        node = _iteration_node(start_date="2024-01-01T00:00:00Z", finish_date=None)
        it = Iteration(_make_project(), node)
        assert it.start_date == date(2024, 1, 1)
        assert it.finish_date is None

    def test_start_date_none_when_attribute_value_is_none(self) -> None:
        # attributes present but startDate explicitly None
        node = ClassificationNode.model_validate(
            {
                "id": 1,
                "name": "Sprint",
                "structureType": "iteration",
                "hasChildren": False,
                "attributes": {},
            }
        )
        it = Iteration(_make_project(), node)
        assert it.start_date is None

    def test_update_with_no_path_in_info(self) -> None:
        node = ClassificationNode.model_validate(
            {
                "id": 1,
                "name": "Sprint",
                "structureType": "iteration",
                "hasChildren": False,
            }
        )
        it = Iteration(_make_project(), node)
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(start_date=date(2024, 1, 1))
        call = mock_patch.call_args
        assert call.args[1] is None

    def test_info_returns_node(self) -> None:
        node = _iteration_node(node_id=7)
        it = Iteration(_make_project(), node)
        assert it.info is node

    def test_project_reference(self) -> None:
        proj = _make_project()
        it = Iteration(proj, _iteration_node())
        assert it.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        it = Iteration(proj, _iteration_node())
        assert it.org is svc.org

    def test_children_empty_when_none(self) -> None:
        node = _iteration_node()
        it = Iteration(_make_project(), node)
        assert it.children == []

    def test_children_wraps_child_nodes(self) -> None:
        child_data = {
            "id": 2,
            "name": "Week 1",
            "structureType": "iteration",
            "hasChildren": False,
        }
        node = _iteration_node(children=[child_data])
        it = Iteration(_make_project(), node)
        children = it.children
        assert len(children) == 1
        assert isinstance(children[0], Iteration)
        assert children[0].name == "Week 1"

    def test_update_delegates_with_relative_path(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(start_date=date(2024, 2, 1), finish_date=date(2024, 2, 14))
        call = mock_patch.call_args
        assert call.args[1] == "Sprint 1"  # relative path, project prefix stripped

    def test_update_strips_iteration_type_segment(self) -> None:
        # ADO includes an "Iteration" segment for root-level nodes.
        it = _make_iteration(path="\\TestProject\\Iteration\\Sprint 1")
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(start_date=date(2024, 2, 1))
        assert mock_patch.call_args.args[1] == "Sprint 1"

    def test_update_updates_info(self) -> None:
        it = _make_iteration()
        updated = _iteration_node(name="Updated")
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(start_date=date(2024, 2, 1))
        assert it._info is updated

    def test_update_root_passes_none_path(self) -> None:
        root = _iteration_node(path="\\TestProject")
        it = Iteration(_make_project(), root)
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(start_date=date(2024, 1, 1))
        call = mock_patch.call_args
        assert call.args[1] is None  # root node → relative path is None

    def test_update_without_dates_passes_none_attributes(self) -> None:
        it = _make_iteration()
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update()
        assert mock_patch.call_args.args[2].attributes is None

    def test_update_name_sends_rename(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        updated = _iteration_node(name="Sprint 1 Renamed")
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update(name="Sprint 1 Renamed")
        request = mock_patch.call_args.args[2]
        assert request.name == "Sprint 1 Renamed"

    def test_update_name_none_omits_name(self) -> None:
        it = _make_iteration()
        updated = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.patch_classification_node"
        ) as mock_patch:
            mock_patch.return_value = updated
            it.update()
        request = mock_patch.call_args.args[2]
        assert request.name is None

    def test_refresh_re_fetches_info(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        refreshed = _iteration_node(name="Sprint 1 Updated")
        with patch(
            "pyado.oop.boards.iteration.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = refreshed
            it.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            assert it.info is refreshed
            mock_get.assert_called_once()
            assert mock_get.call_args.args[1] == "Sprint 1"

    def test_refresh_uses_none_path_for_root(self) -> None:
        it = _make_iteration(path=None)
        refreshed = _iteration_node()
        with patch(
            "pyado.oop.boards.iteration.raw.get_classification_node"
        ) as mock_get:
            mock_get.return_value = refreshed
            it.refresh()
            # refresh() lazily invalidates; trigger the fetch inside the mock context
            _ = it.info
        assert mock_get.call_args.args[1] is None


class TestArea:
    def test_id(self) -> None:
        assert _make_area(node_id=20).id == 20

    def test_name(self) -> None:
        assert _make_area(name="Backend").name == "Backend"

    def test_path(self) -> None:
        area = _make_area(path="\\Proj\\Backend")
        assert area.path == "\\Proj\\Backend"

    def test_info_returns_node(self) -> None:
        node = _area_node(node_id=15)
        area = Area(_make_project(), node)
        assert area.info is node

    def test_project_reference(self) -> None:
        proj = _make_project()
        area = Area(proj, _area_node())
        assert area.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        area = Area(proj, _area_node())
        assert area.org is svc.org

    def test_children_empty_when_none(self) -> None:
        area = _make_area()
        assert area.children == []

    def test_children_wraps_child_nodes(self) -> None:
        child_data = {
            "id": 11,
            "name": "Sub-team",
            "structureType": "area",
            "hasChildren": False,
        }
        node = _area_node(children=[child_data])
        area = Area(_make_project(), node)
        children = area.children
        assert len(children) == 1
        assert isinstance(children[0], Area)
        assert children[0].name == "Sub-team"

    def test_refresh_re_fetches_info(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        refreshed = _area_node(name="Team A Updated")
        with patch("pyado.oop.boards.area.raw.get_classification_node") as mock_get:
            mock_get.return_value = refreshed
            area.refresh()
            # refresh() lazily invalidates; trigger the fetch inside the mock context
            assert area.info is refreshed
        mock_get.assert_called_once()
        assert mock_get.call_args.args[1] == "Team A"

    def test_refresh_uses_none_path_for_root(self) -> None:
        area = Area(_make_project(), _area_node(path=None))
        refreshed = _area_node()
        with patch("pyado.oop.boards.area.raw.get_classification_node") as mock_get:
            mock_get.return_value = refreshed
            area.refresh()
            # refresh() lazily invalidates; trigger the fetch inside the mock context
            _ = area.info
        assert mock_get.call_args.args[1] is None


class TestAreaCreateChild:
    def test_create_child_delegates_to_raw(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        node = ClassificationNode.model_validate({"id": 1, "name": "Sub-team"})
        with patch(
            "pyado.oop.boards.area.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            result = area.create_child("Sub-team")
        assert isinstance(result, Area)
        assert result.name == "Sub-team"
        mock_create.assert_called_once()
        assert mock_create.call_args.args[1].name == "Sub-team"

    def test_create_child_passes_relative_path(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        node = ClassificationNode.model_validate({"id": 1, "name": "Child"})
        with patch(
            "pyado.oop.boards.area.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            area.create_child("Child")
        assert mock_create.call_args.args[2] == "Team A"

    def test_create_child_with_root_path(self) -> None:
        area = _make_area(path="\\TestProject")
        node = ClassificationNode.model_validate({"id": 1, "name": "NewArea"})
        with patch(
            "pyado.oop.boards.area.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            area.create_child("NewArea")
        # root node has no relative path — parent_path is None (create under root)
        assert mock_create.call_args.args[2] is None


class TestAreaUpdate:
    def test_update_renames_node_with_relative_path(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        new_node = _area_node(name="Renamed")
        with patch("pyado.oop.boards.area.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = new_node
            area.update("Renamed")
        mock_patch.assert_called_once()
        assert mock_patch.call_args.args[1] == "Team A"
        assert mock_patch.call_args.args[2].name == "Renamed"

    def test_update_strips_area_type_segment(self) -> None:
        # ADO includes an "Area" segment for root-level nodes.
        area = _make_area(path="\\TestProject\\Area\\Team A")
        new_node = _area_node(name="Renamed")
        with patch("pyado.oop.boards.area.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = new_node
            area.update("Renamed")
        assert mock_patch.call_args.args[1] == "Team A"

    def test_update_with_none_path_passes_none(self) -> None:
        area = Area(_make_project(), _area_node(path=None))
        new_node = _area_node(name="Root")
        with patch("pyado.oop.boards.area.raw.patch_classification_node") as mock_patch:
            mock_patch.return_value = new_node
            area.update("Root")
        assert mock_patch.call_args.args[1] is None


class TestIterationCreateChild:
    def test_create_child_delegates_to_raw(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        node = ClassificationNode.model_validate({"id": 2, "name": "Sub-sprint"})
        with patch(
            "pyado.oop.boards.iteration.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            result = it.create_child("Sub-sprint")
        assert isinstance(result, Iteration)
        assert result.name == "Sub-sprint"
        mock_create.assert_called_once()
        assert mock_create.call_args.args[1].name == "Sub-sprint"

    def test_create_child_passes_relative_path(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        node = ClassificationNode.model_validate({"id": 2, "name": "Week 1"})
        with patch(
            "pyado.oop.boards.iteration.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            it.create_child("Week 1")
        assert mock_create.call_args.args[2] == "Sprint 1"

    def test_create_child_with_root_path(self) -> None:
        it = Iteration(_make_project(), _iteration_node(path="\\TestProject"))
        node = ClassificationNode.model_validate({"id": 2, "name": "Sprint 1"})
        with patch(
            "pyado.oop.boards.iteration.raw.create_classification_node"
        ) as mock_create:
            mock_create.return_value = node
            it.create_child("Sprint 1")
        assert mock_create.call_args.args[2] is None


class TestIterationDelete:
    def test_delete_calls_raw(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        with patch(
            "pyado.oop.boards.iteration.raw.delete_classification_node"
        ) as mock_del:
            it.delete()
        mock_del.assert_called_once()

    def test_delete_passes_relative_path(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        with patch(
            "pyado.oop.boards.iteration.raw.delete_classification_node"
        ) as mock_del:
            it.delete()
        assert mock_del.call_args.args[1] == "Sprint 1"

    def test_delete_passes_iterations_node_type(self) -> None:
        it = _make_iteration(path="\\TestProject\\Sprint 1")
        with patch(
            "pyado.oop.boards.iteration.raw.delete_classification_node"
        ) as mock_del:
            it.delete()
        assert (
            mock_del.call_args.kwargs["node_type"]
            == ClassificationNodeUrlType.ITERATIONS
        )


class TestAreaDelete:
    def test_delete_calls_raw(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        with patch("pyado.oop.boards.area.raw.delete_classification_node") as mock_del:
            area.delete()
        mock_del.assert_called_once()

    def test_delete_passes_relative_path(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        with patch("pyado.oop.boards.area.raw.delete_classification_node") as mock_del:
            area.delete()
        assert mock_del.call_args.args[1] == "Team A"

    def test_delete_passes_areas_node_type(self) -> None:
        area = _make_area(path="\\TestProject\\Team A")
        with patch("pyado.oop.boards.area.raw.delete_classification_node") as mock_del:
            area.delete()
        assert mock_del.call_args.kwargs["node_type"] == ClassificationNodeUrlType.AREAS


class TestIterationAddToTeam:
    def _make_iteration_with_id(
        self, identifier: str | None = "aaaaaaaa-0000-0000-0000-000000000001"
    ) -> Iteration:
        data: dict[str, Any] = {
            "id": 1,
            "name": "Sprint 1",
            "structureType": "iteration",
            "hasChildren": False,
        }
        if identifier is not None:
            data["identifier"] = identifier
        return Iteration(_make_project(), ClassificationNode.model_validate(data))

    def test_add_to_team_delegates(self) -> None:
        it = self._make_iteration_with_id()
        team = Team(_make_project(), _team_info(), _make_service())
        with patch("pyado.oop.boards.iteration.raw.add_team_iteration") as mock_add:
            it.add_to_team(team)
        mock_add.assert_called_once_with(
            team.api_call, UUID("aaaaaaaa-0000-0000-0000-000000000001")
        )

    def test_add_to_team_raises_when_no_identifier(self) -> None:
        it = self._make_iteration_with_id(identifier=None)
        team = Team(_make_project(), _team_info(), _make_service())
        with pytest.raises(ValueError, match="no identifier"):
            it.add_to_team(team)
