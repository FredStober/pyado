"""Integration tests for pipeline trigger (write) endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import time

from pyado import raw
from tests.integration.raw._support import _take, console


def test_pipeline_run(
    project_api_call: raw.ApiCall,
    pipelines: list[raw.PipelineInfo],
    builds_read: tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]],
) -> None:
    """Trigger a pipeline run, poll for state, then cancel it."""
    defs, _ = builds_read
    console.print("\n=== PIPELINE TRIGGER (write) ===")

    # NOTE: post_job_feed, post_job_logs, post_job_event and
    # patch_timeline_records require SYSTEM_ACCESSTOKEN, which is only
    # available inside an ADO agent. They are tested exclusively in the
    # onpremise-pipeline section.

    if not pipelines and not defs:
        return

    # Test raw.post_build (build queue API) then cancel it
    started_build = None
    if defs:
        started_build = raw.post_build(
            project_api_call, raw.BuildQueueRequest(definition_id=defs[0].id)
        )

    if started_build:
        started_api = raw.get_build_api_call(project_api_call, started_build.id)
        raw.patch_build(started_api, raw.BuildStatus.CANCELLING)

    if not pipelines:
        return

    pipeline = pipelines[0]
    triggered = raw.post_pipeline_run(project_api_call, pipeline.id)
    if not triggered:
        return

    run_id: int = triggered.id
    build_api_call = raw.get_build_api_call(project_api_call, run_id)

    # Poll until not "unknown", timeout 60 s
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        poll_info = raw.get_pipeline_run(project_api_call, pipeline.id, run_id)
        if poll_info and poll_info.state != raw.PipelineRunState.UNKNOWN:
            break
        time.sleep(3)

    raw.get_build_details(build_api_call)
    _take(raw.iter_timeline_records(build_api_call), 20)

    # patch_timeline_records, update_timeline_records, post_job_feed,
    # post_job_event etc. need SYSTEM_ACCESSTOKEN — see onpremise section.

    # ---- patch_build ----
    cancel_run_a = raw.post_pipeline_run(project_api_call, pipeline.id)
    if cancel_run_a:
        cancel_a_api = raw.get_build_api_call(project_api_call, cancel_run_a.id)
        raw.patch_build(cancel_a_api, raw.BuildStatus.CANCELLING)
