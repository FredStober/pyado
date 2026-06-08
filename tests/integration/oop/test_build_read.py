"""Integration tests for Build OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import (
    Build,
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
    DistributedTaskSession,
    Project,
)
from pyado.raw import BuildArtifact, BuildExpand
from tests.integration.raw._support import _take, console


def _exercise_task(build: Build, task: BuildTask) -> None:
    _ = task.name
    _ = task.state
    _ = task.result
    _ = task.job
    _ = task.error_count
    _ = task.warning_count
    _ = task.issues
    if task.log is not None:
        build.get_log_text(task.log.id)


def _exercise_job(build: Build, job: BuildJob) -> None:
    _ = job.name
    _ = job.state
    _ = job.result
    _ = job.stage
    _ = job.error_count
    _ = job.warning_count
    _ = job.issues
    _ = job.phase
    _ = job.worker_name
    _take(job.iter_tasks(), 5)
    job.list_tasks()
    tasks = list(job.iter_tasks())
    if tasks:
        _exercise_task(build, tasks[0])


def _exercise_stage(build: Build, stage: BuildStage) -> None:
    _ = stage.name
    _ = stage.state
    _ = stage.result
    _ = stage.build
    _ = stage.error_count
    _ = stage.warning_count
    _ = stage.issues
    phases = list(stage.iter_phases())
    _take(stage.iter_phases(), 3)
    stage.list_phases()
    if phases:
        phase: BuildPhase = phases[0]
        _ = phase.warning_count
    _take(stage.iter_jobs(), 3)
    stage.list_jobs()
    jobs = list(stage.iter_jobs())
    if jobs:
        _exercise_job(build, jobs[0])


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
    _take(build.iter_stages(), 3)
    build.list_stages()

    stages = list(build.iter_stages())
    if stages:
        _exercise_stage(build, stages[0])

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


def test_distributed_task_session(build: Build | None) -> None:
    """Exercise DistributedTaskSession construction and zero-cost navigation."""
    if build is None:
        return
    console.print("\n=== DistributedTaskSession ===")
    session: DistributedTaskSession = build.get_distributed_task_session(
        hub_name="Build",
        plan_id=uuid.uuid4(),
        timeline_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        task_instance_id=uuid.uuid4(),
    )
    _ = session.build
    _ = session.project
    _ = session.org
    session.refresh()
