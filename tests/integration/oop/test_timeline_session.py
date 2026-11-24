"""Integration tests for TimelineSession and the log formatting helpers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado import AzureDevOpsSessionError
from pyado.oop import (
    LogLines,
    Project,
    RecordOrder,
    StatusIcon,
    TimelineSession,
    TimelineTarget,
)
from pyado.oop.pipelines.log_format import Ansi, ansi
from pyado.raw import BuildRecordType
from tests.integration.raw._support import _take, console


def test_log_lines_render_a_group() -> None:
    """LogLines produce the markers the portal expects (no ADO call)."""
    console.print("\n=== LogLines ===")
    lines = LogLines()
    lines.section("Deploy")
    with lines.group("Details"):
        lines.add(ansi("image ok", Ansi.GREEN))
    assert lines.lines()[0] == "##[section]Deploy"
    assert lines.lines()[-1] == "##[endgroup]"


def test_icon_and_order_constants() -> None:
    """The measured ``refName`` and ``order`` values (no ADO call)."""
    console.print("\n=== StatusIcon / RecordOrder ===")
    assert StatusIcon.COLOURED.value == "CmdLine1"
    assert StatusIcon.GREY.value.startswith("JobExtension")
    assert int(RecordOrder.FIRST) == 0
    assert int(RecordOrder.LAST) == 2_147_483_646


def test_session_resolves_a_step_in_a_finished_build(
    proj: Project, org_url: str, project_name: str, token: str
) -> None:
    """Resolve a native step by name and check the guards (read-only)."""
    console.print("\n=== TimelineSession (read-only) ===")
    builds = _take(proj.pipelines.iter_builds(), 5)
    if not builds:
        pytest.skip(reason="no builds to inspect")
    build = builds[0]
    project_id = proj.id
    session = TimelineSession.from_tokens(
        org_name=org_url.rsplit("/", 1)[-1],
        project_id=project_id,
        build_id=build.id,
        admin_token=token,
    )
    records = list(build.iter_timeline_records())
    task = next((r for r in records if r.type_name == BuildRecordType.TASK), None)
    if task is None:
        pytest.skip(reason="build has no task records")
    matches = [
        r for r in records if r.name == task.name and r.type_name == task.type_name
    ]
    if len(matches) == 1:
        target: TimelineTarget = session.resolve_task(task.name)
        assert target.record_id == task.id
    with pytest.raises(AzureDevOpsSessionError):
        session.resolve_task("no such step " + project_name)
    with pytest.raises(AzureDevOpsSessionError):
        session.complete(
            TimelineTarget(
                record_id=task.id,
                parent_id=task.parent_id,
                type_name=task.type_name,
                name=task.name,
            )
        )
