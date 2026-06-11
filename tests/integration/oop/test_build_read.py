"""Integration tests for Build OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import (
    Build,
    Project,
)
from pyado.raw import BuildArtifact, BuildExpand
from tests.integration.raw._support import _take, console


def _exercise_build_artifacts_and_approvals(
    build: Build, artifacts: list[BuildArtifact] | None
) -> None:
    """Exercise artifact download and approval iteration on *build*."""
    if artifacts:
        build.download_artifact(artifacts[0])
    _take(build.iter_approvals(), 5)
    build.list_approvals()


def _exercise_project_build_lookups(proj: Project, build: Build) -> None:
    proj.pipelines.get_build(build.id)
    proj.pipelines.get_build_with_expand(build.id, BuildExpand.ALL)
    proj.pipelines.get_build_details(build.id)
    proj.pipelines.get_latest_build(build.pipeline.id)


def test_build_read(proj: Project) -> None:
    """Exercise Build properties, stages, jobs, tasks, artifacts, tags, and logs."""
    console.print("\n=== Build (read) ===")
    builds = _take(proj.pipelines.iter_builds(), 1)
    if not builds:
        return

    build: Build = builds[0]
    _exercise_project_build_lookups(proj, build)

    _ = build.id
    _ = build.status
    _ = build.number
    _ = build.result
    _ = build.source_branch
    _ = build.start_time
    _ = build.finish_time
    _ = build.info
    _ = build.api_call
    _ = build.project
    _ = build.org
    _ = build.pipeline
    build.refresh()
    artifacts = _take(build.iter_artifacts(), 5)
    build.list_artifacts()
    _exercise_build_artifacts_and_approvals(build, artifacts)
    _take(build.iter_tags(), 5)
    build.list_tags()
    _take(build.iter_timeline_records(), 5)
    build.list_timeline_records()

    _take(build.iter_work_item_ids(), 5)
    build.list_work_item_ids()
    build.list_work_items()
    _take(build.iter_logs(), 5)
    build.list_logs()
    build.get_all_log_text()
    build.find_task(lambda _: True)
    _ = build.queue_time
    _ = build.requested_by
    _ = build.requested_for
    _ = build.source_version

    older_builds = _take(proj.pipelines.iter_builds(), 2)
    if len(older_builds) >= 2:
        older = older_builds[1]
        _take(build.iter_work_items_between(older), 5)
        build.list_work_items_between(older)
        _take(build.iter_work_item_ids_between(older), 5)
        build.list_work_item_ids_between(older)


def test_build_pipeline_run(build: Build | None) -> None:
    """Exercise Build.pipeline_run back-navigation."""
    if build is None:
        return
    console.print("\n=== Build.pipeline_run ===")
    _ = build.pipeline_run
