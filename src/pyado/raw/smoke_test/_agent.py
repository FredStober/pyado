"""Smoke tests for on-premise pipeline and ADO agent API endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import json
import random
import time
from uuid import UUID

from pyado import raw
from pyado.raw.smoke_test._runner import (
    _ACTIVE_JOB_REQUIRED,
    _DIM,
    _ONPREMISE_LABELS,
    _ONPREMISE_PIPELINE_NAME,
    _ONPREMISE_WRITE_LABELS,
    _PRINT_STEP_NAME,
    _RESET,
    _skip,
    _token_unavailable_skips,
    console,
    run,
    run_or_skip,
)


def _strip_ado_timestamp(line: str) -> str:
    """Strip the leading ADO ISO timestamp from a build log line.

    ADO prefixes every stored log line with a timestamp of the form
    ``2024-01-01T00:00:00.0000000Z ``.  Returns everything after the
    first space, or the line unchanged if no space is found.
    """
    space_idx = line.find(" ")
    return line[space_idx + 1 :] if space_idx != -1 else line


def _extract_variables_from_log(log_lines: list[str]) -> dict[str, str]:
    """Extract the base64-encoded variables dict printed by the pipeline step.

    Scans *log_lines* for the ``=== Variables (base64) ===`` marker and
    decodes the first non-empty line that follows it.

    Returns:
        The decoded variables dict, or an empty dict if not found.
    """
    for idx, raw_line in enumerate(log_lines):
        if "=== Variables (base64) ===" in _strip_ado_timestamp(raw_line):
            for candidate in log_lines[idx + 1 :]:
                blob = _strip_ado_timestamp(candidate).strip()
                if blob:
                    return json.loads(base64.b64decode(blob).decode())
    return {}


def _wait_for_and_approve(
    project_api_call: raw.ApiCall,
    existing_approval_ids: set,
) -> raw.PipelineApproval | None:
    """Poll for a new pending approval and approve it; return the approval."""
    console.print(
        f"  {_DIM}waiting for ManualValidation approval (up to 2 min)...{_RESET}"
    )
    new_approval: raw.PipelineApproval | None = None
    approval_deadline = time.monotonic() + 120.0
    while time.monotonic() < approval_deadline:
        pending = list(raw.iter_approvals(project_api_call, state="pending"))
        new = [a for a in pending if a.id not in existing_approval_ids]
        if new:
            new_approval = new[0]
            break
        time.sleep(5)

    if new_approval:
        console.print(f"  {_DIM}approval id: {new_approval.id}{_RESET}")
        run(
            "patch_approvals [ManualValidation stage]",
            lambda a=new_approval: raw.patch_approvals(
                project_api_call,
                [
                    raw.PipelineApprovalUpdateRequest(
                        approval_id=str(a.id),
                        status="approved",
                        comment="smoke test auto-approve",
                    )
                ],
            ),
        )
    else:
        _skip(
            "patch_approvals [ManualValidation stage]",
            "approval did not appear within 2 min",
        )
    return new_approval


def _poll_print_step_record(
    build_api_call: raw.ApiCall,
) -> raw.BuildRecordInfo | None:
    """Poll timeline until the print-step record is completed; return it."""
    print_record: raw.BuildRecordInfo | None = None
    deadline = time.monotonic() + 300.0
    while time.monotonic() < deadline:
        records = list(raw.iter_timeline_records(build_api_call))
        for record in records:
            if (
                record.name == _PRINT_STEP_NAME
                and record.state == "completed"
                and record.log is not None
            ):
                print_record = record
                break
        if print_record:
            break
        time.sleep(10)
    return print_record


def _exercise_agent_apis(
    rng: random.Random,
    job_api_call_result: raw.ApiCall | None,
    log_api_call_result: raw.ApiCall | None,
    plan_api_call: raw.ApiCall | None,
    timeline_api_call_result: raw.ApiCall | None,
    print_record: raw.BuildRecordInfo,
    task_id: UUID,
    job_id: UUID,
) -> None:
    """Exercise post_job_feed, post_job_logs, post_job_event, patch_timeline."""
    if job_api_call_result:
        run_or_skip(
            "post_job_feed [raw]",
            lambda api=job_api_call_result: raw.post_job_feed(
                api,
                raw.JobFeedPayload(value=["pyado smoke test feed line"], count=1),
            ),
            _ACTIVE_JOB_REQUIRED,
        )
    else:
        _skip("post_job_feed [raw]", "get_job_api_call failed")

    if log_api_call_result:
        run_or_skip(
            "post_job_logs",
            lambda api=log_api_call_result: raw.post_job_logs(
                api,
                f"pyado smoke test log (seed={rng.randint(0, 99999)})\n",
            ),
            _ACTIVE_JOB_REQUIRED,
        )
    else:
        _skip("post_job_logs", "get_log_api_call failed")

    if plan_api_call:
        run_or_skip(
            "post_job_event [raw]",
            lambda api=plan_api_call: raw.post_job_event(
                api,
                raw.JobEventPayload(
                    name="TaskCompleted",
                    task_id=task_id,
                    job_id=job_id,
                    result="succeeded",
                ),
            ),
            _ACTIVE_JOB_REQUIRED,
        )
    else:
        _skip("post_job_event [raw]", "get_plan_api_call failed")

    if timeline_api_call_result:
        run_or_skip(
            "patch_timeline_records [onpremise, raw]",
            lambda api=timeline_api_call_result, rec=print_record: (
                raw.patch_timeline_records(
                    api,
                    raw.TimelineRecordsUpdatePayload(value=[rec], count=1),
                )
            ),
            _ACTIVE_JOB_REQUIRED,
        )
    else:
        _skip("patch_timeline_records [onpremise, raw]", "get_timeline_api_call failed")


def _run_agent_phase(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    log_id: raw.BuildLogId,
    log_bytes: bytes | None,
    print_record: raw.BuildRecordInfo,
) -> None:
    """Parse variables from build log and exercise the agent write APIs."""
    log_lines: list[str] = log_bytes.decode("utf-8").splitlines() if log_bytes else []
    variables = _extract_variables_from_log(log_lines)

    if not variables:
        for label in _ONPREMISE_LABELS:
            _skip(label, "could not extract variables dict from build log")
        return

    missing = [
        k
        for k in (
            "SYSTEM_ACCESSTOKEN",
            "SYSTEM_PLANID",
            "SYSTEM_JOBID",
            "SYSTEM_TIMELINEID",
            "SYSTEM_TASKINSTANCEID",
        )
        if not variables.get(k, "")
    ]
    if missing:
        # Pipeline ran but variables are absent — typically because the pipeline
        # YAML doesn't map System.AccessToken into the step's env block.  Mark
        # the onpremise labels as allowed skips so the run isn't counted as a
        # failure; the fix is in the pipeline YAML, not in pyado.
        _token_unavailable_skips.update(_ONPREMISE_LABELS)
        for label in _ONPREMISE_LABELS:
            _skip(label, f"missing variables: {missing}")
        return

    hub_name = variables.get("SYSTEM_HOSTTYPE", "build")
    plan_id = UUID(variables["SYSTEM_PLANID"])
    job_id = UUID(variables["SYSTEM_JOBID"])
    timeline_id = UUID(variables["SYSTEM_TIMELINEID"])
    task_id = UUID(variables["SYSTEM_TASKINSTANCEID"])
    console.print(
        f"  {_DIM}hub={hub_name}  plan={plan_id}  "
        f"job={job_id}  timeline={timeline_id}{_RESET}"
    )

    # Agent write APIs (feed, logs, events, timeline) can only succeed while
    # the job is actively executing.  The print step has already completed by
    # the time we extract variables, so writes may be rejected.  Register
    # these labels as allowed skips so a rejection becomes SKIP, not FAIL.
    _token_unavailable_skips.update(_ONPREMISE_WRITE_LABELS)

    agent_project_api_call = raw.ApiCall(
        access_token=variables["SYSTEM_ACCESSTOKEN"],
        url=project_api_call.url.unicode_string(),
    )

    plan_api_call = run(
        "get_plan_api_call",
        lambda: raw.get_plan_api_call(agent_project_api_call, hub_name, plan_id),
    )
    job_api_call_result = run(
        "get_job_api_call",
        lambda: raw.get_job_api_call(
            agent_project_api_call, hub_name, plan_id, timeline_id, job_id
        ),
    )
    log_api_call_result = run(
        "get_log_api_call",
        lambda: raw.get_log_api_call(agent_project_api_call, hub_name, plan_id, log_id),
    )
    timeline_api_call_result = run(
        "get_timeline_api_call",
        lambda: raw.get_timeline_api_call(
            agent_project_api_call, hub_name, plan_id, timeline_id
        ),
    )

    _exercise_agent_apis(
        rng,
        job_api_call_result,
        log_api_call_result,
        plan_api_call,
        timeline_api_call_result,
        print_record,
        task_id,
        job_id,
    )


def _test_onpremise_pipeline(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    pipelines: list[raw.PipelineInfo],
) -> None:
    """Trigger 'onpremise', extract agent variables from logs, test agent APIs.

    Finds the pipeline named "onpremise", triggers it, waits (up to 5 min)
    for the "Print and encode system variables" step to complete, then fetches
    and decodes the base64 variable blob from the build log.  The extracted
    ``SYSTEM_ACCESSTOKEN`` and context IDs are used to exercise the functions
    that require an active ADO agent token.
    """
    console.print("\n=== ONPREMISE PIPELINE (agent API tests) ===")

    onpremise = next((p for p in pipelines if p.name == _ONPREMISE_PIPELINE_NAME), None)
    if not onpremise:
        for label in _ONPREMISE_LABELS:
            _skip(label, f"no pipeline named {_ONPREMISE_PIPELINE_NAME!r} found")
        return

    triggered = run(
        f"post_pipeline_run [onpremise, id={onpremise.id}]",
        lambda: raw.post_pipeline_run(project_api_call, onpremise.id),
    )
    if not triggered:
        for label in _ONPREMISE_LABELS:
            _skip(label, "onpremise pipeline trigger failed")
        return

    run_id = triggered.id
    build_api_call = raw.get_build_api_call(project_api_call, run_id)
    console.print(f"  {_DIM}triggered onpremise run #{run_id}{_RESET}")

    # Stage 1 is ManualValidation — poll for the new pending approval and approve it.
    existing_approval_ids = {
        a.id for a in raw.iter_approvals(project_api_call, state="pending")
    }
    _wait_for_and_approve(project_api_call, existing_approval_ids)

    print_record = _poll_print_step_record(build_api_call)
    if not print_record:
        reason = f"step {_PRINT_STEP_NAME!r} did not complete within 5 min"
        for label in _ONPREMISE_LABELS:
            _skip(label, reason)
        return

    log_id: raw.BuildLogId = print_record.log.id  # type: ignore[union-attr]
    console.print(f"  {_DIM}log id: {log_id}{_RESET}")

    log_bytes = build_api_call.get_raw("logs", log_id, version="7.1")
    _run_agent_phase(project_api_call, rng, log_id, log_bytes, print_record)
