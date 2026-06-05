"""Smoke tests for pipeline endpoints (newer /pipelines API and build queue)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random
import time

from pyado import raw
from pyado.raw.smoke_test._runner import _skip, _take, console, run


def _test_pipelines_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> list[raw.PipelineInfo]:
    console.print("\n=== PIPELINES (read) ===")

    order_variants: list[str | None] = [None, "name asc", "name desc"]
    rng.shuffle(order_variants)

    pipelines: list[raw.PipelineInfo] = []
    for order in order_variants[:2]:
        result = run(
            f"iter_pipelines [order_by={order!r}]",
            lambda o=order: raw.list_pipelines(project_api_call, order_by=o),
        )
        if result and not pipelines:
            pipelines = result

    if pipelines:
        pipeline = pipelines[0]
        run(
            f"get_pipeline [id={pipeline.id}]",
            lambda: raw.get_pipeline(project_api_call, pipeline.id),
        )
        # get_pipeline with pipeline_version parameter
        run(
            f"get_pipeline [id={pipeline.id}, version={pipeline.revision}]",
            lambda pid=pipeline.id, rev=pipeline.revision: raw.get_pipeline(
                project_api_call, pid, pipeline_version=rev
            ),
        )
        run(
            f"iter_pipeline_runs [id={pipeline.id}]",
            lambda: _take(raw.iter_pipeline_runs(project_api_call, pipeline.id), 5),
        )
        runs = raw.list_pipeline_runs(project_api_call, pipeline.id)
        if runs:
            newest = runs[0]
            run(
                f"get_pipeline_run [pipeline={pipeline.id}, run={newest.id}]",
                lambda: raw.get_pipeline_run(project_api_call, pipeline.id, newest.id),
            )

    return pipelines


def _test_pipeline_run(
    project_api_call: raw.ApiCall,
    pipelines: list[raw.PipelineInfo],
    defs: list[raw.PipelineDefinitionInfo],
) -> None:
    """Trigger a pipeline run and verify state transitions.

    NOTE: post_job_feed, post_job_logs, post_job_event require $SYSTEM_ACCESSTOKEN
    — available only inside an ADO pipeline agent — and are always skipped here.
    Similarly, get_plan_api_call, get_job_api_call, and get_log_api_call are
    constructor helpers tested only indirectly.
    """
    console.print("\n=== PIPELINE TRIGGER (write) ===")

    # NOTE: post_job_feed, post_job_logs, post_job_event and
    # patch_timeline_records require SYSTEM_ACCESSTOKEN, which is only
    # available inside an ADO agent. They are tested exclusively in the
    # onpremise-pipeline section.

    if not pipelines and not defs:
        _skip("post_pipeline_run", "no pipelines or definitions found")
        _skip("post_build [start build API]", "no pipeline definitions found")
        return

    # Test raw.post_build (build queue API) then cancel it
    started_build = None
    if defs:
        started_build = run(
            f"post_build [start build API, definition={defs[0].id}]",
            lambda d=defs[0].id: raw.post_build(
                project_api_call, raw.BuildQueueRequest(definition_id=d)
            ),
        )
    else:
        _skip("post_build [start build API]", "no pipeline definitions found")

    if started_build:
        started_api = raw.get_build_api_call(project_api_call, started_build.id)
        run(
            "patch_build [cancel, build API]",
            lambda api=started_api: raw.patch_build(api, raw.BuildStatus.CANCELLING),
        )
    else:
        _skip("patch_build [cancel, build API]", "post_build failed or skipped")

    if not pipelines:
        _skip("post_pipeline_run", "no pipelines found")
        _skip("patch_build [raw, cancel]", "no pipelines found")
        return

    pipeline = pipelines[0]
    triggered = run(
        f"post_pipeline_run [pipeline={pipeline.id}]",
        lambda: raw.post_pipeline_run(project_api_call, pipeline.id),
    )
    if not triggered:
        return

    run_id: int = triggered.id
    build_api_call = raw.get_build_api_call(project_api_call, run_id)

    # Poll until not "unknown", timeout 60 s
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        poll_info = run(
            f"get_pipeline_run [poll, state={triggered.state!r}]",
            lambda: raw.get_pipeline_run(project_api_call, pipeline.id, run_id),
        )
        if poll_info and poll_info.state != "unknown":
            break
        time.sleep(3)

    run(
        f"get_build_details [run={run_id}]",
        lambda: raw.get_build_details(build_api_call),
    )
    run(
        f"iter_timeline_records [run={run_id}]",
        lambda: _take(raw.iter_timeline_records(build_api_call), 20),
    )

    # patch_timeline_records, update_timeline_records, post_job_feed,
    # post_job_event etc. need SYSTEM_ACCESSTOKEN — see onpremise section.

    # ---- patch_build ----
    cancel_run_a = run(
        "post_pipeline_run [run A, for patch_build test]",
        lambda: raw.post_pipeline_run(project_api_call, pipeline.id),
    )
    if cancel_run_a:
        cancel_a_api = raw.get_build_api_call(project_api_call, cancel_run_a.id)
        run(
            "patch_build [raw, cancel]",
            lambda api=cancel_a_api: raw.patch_build(api, raw.BuildStatus.CANCELLING),
        )
    else:
        _skip("patch_build [raw, cancel]", "pipeline run trigger failed")
