"""Integration tests for Project OOP class (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib
import uuid

from pyado.oop import Project, VariableGroup
from pyado.raw import (
    PolicyConfigurationRequest,
    PolicyTypeIdRef,
    VariableInfo,
)
from tests.integration.raw._support import _take, console


def test_write_project_extras(proj: Project) -> None:
    """Exercise project write extras.

    Covers create_iteration, create_area, and create_variable_group with
    cleanup.
    """
    console.print("\n=== Project (write extras) ===")

    # create_iteration and add to team
    smoke_iter_name = f"oop-smoke-iter-{uuid.uuid4().hex[:6]}"
    new_iter = proj.boards.create_iteration(smoke_iter_name)
    # Iteration.add_to_team and Team.add_iteration — use the newly created
    # iteration (which has a UUID identifier) rather than the root node (whose
    # identifier is None and which ADO rejects for team assignment).
    teams = _take(proj.boards.iter_teams(), 1)
    if new_iter and new_iter.info.identifier and teams:
        iter_uuid = uuid.UUID(new_iter.info.identifier)
        new_iter.add_to_team(teams[0])
        teams[0].add_iteration(iter_uuid)
        proj.boards.add_team_iteration(teams[0].name, iter_uuid)
        teams[0].remove_iteration(iter_uuid)

    # create_area and Area.patch
    smoke_area_name = f"oop-smoke-area-{uuid.uuid4().hex[:6]}"
    new_area = proj.boards.create_area(smoke_area_name)
    # Patch the newly created smoke area (guaranteed simple relative path).
    if new_area:
        new_area.update(new_area.name)

    # create_variable_group + delete
    smoke_vg_name = f"oop-smoke-vg-{uuid.uuid4().hex[:6]}"
    new_vg: VariableGroup | None = proj.pipelines.library.create_variable_group(
        smoke_vg_name,
        {"_smoke": VariableInfo(value="value")},
        description="OOP smoke test — safe to delete",
    )
    if new_vg:
        with contextlib.suppress(Exception):
            new_vg.delete()


def test_write_policy(proj: Project) -> None:
    """Exercise policy write lifecycle.

    Covers ProjectSettings.create_policy_configuration(), update(), and
    delete().
    """
    console.print("\n=== Project Settings (write) ===")
    configs = proj.settings.list_policy_configurations()
    if not configs:
        return

    template = configs[0]
    request = PolicyConfigurationRequest(
        is_enabled=False,
        is_blocking=False,
        type=PolicyTypeIdRef(id=template.type.id),
        settings=template.info.settings,
    )
    new_pc = proj.settings.create_policy_configuration(request)
    new_pc.update(request)
    new_pc.delete()
