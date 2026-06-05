"""Smoke tests for Build."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import Build, BuildJob, BuildStage, BuildTask, Project
from pyado.oop.smoke_test._runner import _skip, _take, console, run


def _exercise_task(build: Build, task: BuildTask) -> None:
    run("task.name", lambda: task.name)
    run("task.state", lambda: task.state)
    run("task.result", lambda: task.result)
    run("task.job (back-nav)", lambda: task.job)
    run("task.error_count", lambda: task.error_count)
    run("task.warning_count", lambda: task.warning_count)
    run("task.issues", lambda: task.issues)
    if task.log is not None:
        run(
            "build.get_log_text(task.log.id)",
            lambda lid=task.log.id: build.get_log_text(lid),
        )


def _exercise_job(build: Build, job: BuildJob) -> None:
    run("job.name", lambda: job.name)
    run("job.state", lambda: job.state)
    run("job.result", lambda: job.result)
    run("job.stage (back-nav)", lambda: job.stage)
    run("job.error_count", lambda: job.error_count)
    run("job.warning_count", lambda: job.warning_count)
    run("job.issues", lambda: job.issues)
    run("job.phase", lambda: job.phase)
    run("job.worker_name", lambda: job.worker_name)
    run("job.iter_tasks()", lambda: _take(job.iter_tasks(), 5))
    run("job.list_tasks()", job.list_tasks)
    tasks = list(job.iter_tasks())
    if tasks:
        _exercise_task(build, tasks[0])


def _exercise_stage(build: Build, stage: BuildStage) -> None:
    run("stage.name", lambda: stage.name)
    run("stage.state", lambda: stage.state)
    run("stage.result", lambda: stage.result)
    run("stage.build (back-nav)", lambda: stage.build)
    run("stage.error_count", lambda: stage.error_count)
    run("stage.warning_count", lambda: stage.warning_count)
    run("stage.issues", lambda: stage.issues)
    phases = list(stage.iter_phases())
    run("stage.iter_phases()", lambda: _take(stage.iter_phases(), 3))
    run("stage.list_phases()", stage.list_phases)
    if phases:
        phase = phases[0]
        run("phase.warning_count", lambda: phase.warning_count)
    run("stage.iter_jobs()", lambda: _take(stage.iter_jobs(), 3))
    run("stage.list_jobs()", stage.list_jobs)
    jobs = list(stage.iter_jobs())
    if jobs:
        _exercise_job(build, jobs[0])


def _test_build_read(proj: Project) -> Build | None:
    console.print("\n=== Build (read) ===")
    builds = run("proj.iter_builds()", lambda: _take(proj.iter_builds(), 1))
    if not builds:
        _skip("build read tests", "no builds found")
        return None

    build: Build = builds[0]
    run("proj.get_build(id)", lambda bid=build.id: proj.get_build(bid))

    run("build.id", lambda: build.id)
    run("build.status", lambda: build.status)
    run("build.number", lambda: build.number)
    run("build.result", lambda: build.result)
    run("build.source_branch", lambda: build.source_branch)
    run("build.start_time", lambda: build.start_time)
    run("build.finish_time", lambda: build.finish_time)
    run("build.info", lambda: build.info)
    run("build.api_call", lambda: build.api_call)
    run("build.project (back-nav)", lambda: build.project)
    run("build.org (back-nav)", lambda: build.org)
    run("build.pipeline (back-nav, cached)", lambda: build.pipeline)
    run("build.refresh()", build.refresh)
    run("build.iter_artifacts()", lambda: _take(build.iter_artifacts(), 5))
    run("build.list_artifacts()", build.list_artifacts)
    run("build.iter_tags()", lambda: _take(build.iter_tags(), 5))
    run("build.list_tags()", build.list_tags)
    run(
        "build.iter_timeline_records()", lambda: _take(build.iter_timeline_records(), 5)
    )
    run("build.list_timeline_records()", build.list_timeline_records)
    run("build.iter_stages()", lambda: _take(build.iter_stages(), 3))
    run("build.list_stages()", build.list_stages)

    stages = list(build.iter_stages())
    if stages:
        _exercise_stage(build, stages[0])

    run("build.iter_work_item_ids()", lambda: _take(build.iter_work_item_ids(), 5))
    run("build.list_work_item_ids()", build.list_work_item_ids)
    run("build.list_work_items()", build.list_work_items)
    run("build.iter_logs()", lambda: _take(build.iter_logs(), 5))
    run("build.list_logs()", build.list_logs)
    run("build.get_all_log_text()", build.get_all_log_text)
    run("build.find_task(predicate)", lambda: build.find_task(lambda _: True))
    run("build.queue_time", lambda: build.queue_time)
    run("build.requested_by", lambda: build.requested_by)
    run("build.requested_for", lambda: build.requested_for)
    run("build.source_version", lambda: build.source_version)

    older_builds = _take(proj.iter_builds(), 2)
    if len(older_builds) >= 2:
        older = older_builds[1]
        run(
            "build.iter_work_items_between(older_build)",
            lambda ob=older: _take(build.iter_work_items_between(ob), 5),
        )
        run(
            "build.list_work_items_between(older_build)",
            lambda ob=older: build.list_work_items_between(ob),
        )
        run(
            "build.iter_work_item_ids_between(older_build)",
            lambda ob=older: _take(build.iter_work_item_ids_between(ob), 5),
        )
        run(
            "build.list_work_item_ids_between(older_build)",
            lambda ob=older: build.list_work_item_ids_between(ob),
        )
    return build


def _test_write_build_tags(build: Build) -> None:
    smoke_tag = f"oop-smoke-{uuid.uuid4().hex[:6]}"
    run("build.add_tag()", lambda: build.add_tag(smoke_tag))
    run("build.iter_tags() after add", lambda: list(build.iter_tags()))
    run("build.remove_tag()", lambda: build.remove_tag(smoke_tag))
