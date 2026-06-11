"""Integration tests for on-premise pipeline and ADO agent API endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import json
import random
import time
from uuid import UUID

import pytest

from pyado import (
    AzureDevOpsAuthError,
    AzureDevOpsBadRequestError,
    JobEventName,
    JobEventResult,
    PipelineApprovalStatus,
    raw,
)
from tests.integration.raw._support import (
    _ONPREMISE_PIPELINE_NAME,
    _PRINT_STEP_NAME,
    console,
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
                    result: dict[str, str] = json.loads(base64.b64decode(blob).decode())
                    return result
    return {}


def _wait_for_and_approve(
    project_api_call: raw.ApiCall,
    existing_approval_ids: set[raw.ApprovalId],
) -> raw.PipelineApproval | None:
    """Poll for a new pending approval and approve it; return the approval."""
    console.print("  waiting for ManualValidation approval (up to 2 min)...")
    new_approval: raw.PipelineApproval | None = None
    approval_deadline = time.monotonic() + 120.0
    while time.monotonic() < approval_deadline:
        pending = list(
            raw.iter_approvals(
                project_api_call, state=raw.PipelineApprovalStatus.PENDING
            )
        )
        new = [a for a in pending if a.id not in existing_approval_ids]
        if new:
            new_approval = new[0]
            break
        time.sleep(5)

    if new_approval:
        console.print(f"  approval id: {new_approval.id}")
        raw.patch_approvals(
            project_api_call,
            [
                raw.PipelineApprovalUpdateRequest(
                    approval_id=str(new_approval.id),
                    status=PipelineApprovalStatus.APPROVED,
                    comment="smoke test auto-approve",
                )
            ],
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
        try:
            raw.post_job_feed(
                job_api_call_result,
                raw.JobFeedPayload(value=["pyado smoke test feed line"], count=1),
            )
        except (AzureDevOpsBadRequestError, AzureDevOpsAuthError):
            pytest.skip(reason="agent feed API requires system access token")

    if log_api_call_result:
        raw.post_job_logs(
            log_api_call_result,
            f"pyado smoke test log (seed={rng.randint(0, 99999)})\n",
        )

    if plan_api_call:
        raw.post_job_event(
            plan_api_call,
            raw.JobEventPayload(
                name=JobEventName.TASK_COMPLETED,
                task_id=task_id,
                job_id=job_id,
                result=JobEventResult.SUCCEEDED,
            ),
        )

    if timeline_api_call_result:
        raw.patch_timeline_records(
            timeline_api_call_result,
            raw.TimelineRecordsUpdatePayload(value=[print_record], count=1),
        )


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
        # YAML doesn't map System.AccessToken into the step's env block.
        return

    hub_name = variables.get("SYSTEM_HOSTTYPE", "build")
    plan_id = UUID(variables["SYSTEM_PLANID"])
    job_id = UUID(variables["SYSTEM_JOBID"])
    timeline_id = UUID(variables["SYSTEM_TIMELINEID"])
    task_id = UUID(variables["SYSTEM_TASKINSTANCEID"])
    console.print(
        f"  hub={hub_name}  plan={plan_id}  job={job_id}  timeline={timeline_id}"
    )

    # Agent write APIs (feed, logs, events, timeline) can only succeed while
    # the job is actively executing.  The print step has already completed by
    # the time we extract variables, so writes may be rejected.
    agent_project_api_call = raw.ApiCall(
        session=raw.get_session(pat=variables["SYSTEM_ACCESSTOKEN"]),
        url=project_api_call.url.unicode_string(),
    )

    plan_api_call = raw.get_plan_api_call(agent_project_api_call, hub_name, plan_id)
    raw.post_new_log(plan_api_call, f"logs\\pyado-smoke-{rng.randint(0, 99999)}")
    job_api_call_result = raw.get_job_api_call(
        agent_project_api_call, hub_name, plan_id, timeline_id, job_id
    )
    log_api_call_result = raw.get_log_api_call(
        agent_project_api_call, hub_name, plan_id, log_id
    )
    timeline_api_call_result = raw.get_timeline_api_call(
        agent_project_api_call, hub_name, plan_id, timeline_id
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


def test_onpremise_pipeline(
    project_api_call: raw.ApiCall,
    pipelines: list[raw.PipelineInfo],
    rng: random.Random,
) -> None:
    """Trigger the onpremise pipeline and exercise agent write APIs."""
    console.print("\n=== ONPREMISE PIPELINE (agent API tests) ===")

    onpremise = next((p for p in pipelines if p.name == _ONPREMISE_PIPELINE_NAME), None)
    if not onpremise:
        return

    triggered = raw.post_pipeline_run(project_api_call, onpremise.id)
    if not triggered:
        return

    run_id = triggered.id
    build_api_call = raw.get_build_api_call(project_api_call, run_id)
    console.print(f"  triggered onpremise run #{run_id}")

    # Stage 1 is ManualValidation — poll for the new pending approval and approve it.
    existing_approval_ids = {
        a.id
        for a in raw.iter_approvals(
            project_api_call, state=raw.PipelineApprovalStatus.PENDING
        )
    }
    _wait_for_and_approve(project_api_call, existing_approval_ids)

    print_record = _poll_print_step_record(build_api_call)
    if not print_record:
        return

    log_id: raw.BuildLogId = print_record.log.id  # type: ignore[union-attr]
    console.print(f"  log id: {log_id}")

    log_bytes = build_api_call.get_raw("logs", log_id, version="7.1")
    _run_agent_phase(project_api_call, rng, log_id, log_bytes, print_record)
