"""Integration test: report progress into a RUNNING agentless task.

The ``onpremise`` pipeline has an ``InvokeRESTAPI`` step (job
``JobAwaitCallback``).  This test follows the ICS ADO handler's approach:

* resolve the step's own timeline record by display name (not by
  ``SYSTEM_TASKINSTANCEID``, which belongs to a different record for
  ``InvokeRESTAPI`` steps),
* wait a few seconds, then poll until the record has a log attached,
* send feed to the **job** record, append to the task log, create a dynamic
  child task with its own log, and finish with ``TaskCompleted``,

using the build's ``System.AccessToken`` (printed by the agent step) rather
than the PAT, which cannot complete a task.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import time
import uuid

import pytest
import requests

from pyado import (
    JobEventName,
    JobEventResult,
    TimelineSession,
    TimelineTarget,
    raw,
)
from pyado.raw import BuildRecordType
from tests.integration.raw._support import (
    _ONPREMISE_PIPELINE_NAME,
    _PRINT_STEP_NAME,
    console,
)
from tests.integration.raw.test_onpremise_pipeline import (
    _extract_variables_from_log,
    _wait_for_and_approve,
)

_AGENTLESS_STEP_NAME = "TaskGET public endpoint and await callback"
_READY_DELAY_SECONDS = 10.0
_LOG_ATTACH_TIMEOUT_SECONDS = 60.0


def _find_record(
    build_api_call: raw.ApiCall, name: str, *, exact_only: bool = True
) -> raw.BuildRecordInfo | None:
    """Return the timeline record with the given display name, if present.

    A slow or dropped timeline read counts as "not there yet": the callers poll,
    and a persistent problem still ends in their deadline.
    """
    try:
        return next(
            (
                r
                for r in raw.iter_timeline_records(build_api_call)
                if r.name == name or (exact_only is False and r.name.endswith(name))
            ),
            None,
        )
    except (requests.ConnectionError, requests.Timeout):
        return None


def _wait_for_record(
    build_api_call: raw.ApiCall,
    name: str,
    *,
    state: str,
    timeout: float,
    need_log: bool = False,
    exact_only: bool = True,
) -> raw.BuildRecordInfo | None:
    """Poll until the named record is in *state* (and has a log if asked)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = _find_record(build_api_call, name, exact_only=exact_only)
        if (
            record is not None
            and record.state == state
            and (not need_log or record.log is not None)
        ):
            return record
        time.sleep(3)
    return None


def _system_token(build_api_call: raw.ApiCall) -> dict[str, str]:
    """Read the variables the agent step printed (includes the System token).

    The step record turns ``completed`` a moment before ADO attaches its log
    to it, and the log may then still lack the printed variables, so both are
    waited for.
    """
    record = _wait_for_record(
        build_api_call,
        _PRINT_STEP_NAME,
        state="completed",
        timeout=300.0,
        need_log=True,
        exact_only=False,
    )
    if record is None or record.log is None:
        return {}
    deadline = time.monotonic() + _LOG_ATTACH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            log_bytes = build_api_call.get_raw("logs", record.log.id, version="7.1")
        except (requests.ConnectionError, requests.Timeout):
            log_bytes = b""
        lines = log_bytes.decode("utf-8").splitlines() if log_bytes else []
        variables = _extract_variables_from_log(lines)
        if variables.get("SYSTEM_ACCESSTOKEN"):
            return variables
        time.sleep(3)
    return {}


class _Ctx:
    """Identifiers shared by the write helpers."""

    def __init__(
        self,
        agent_call: raw.ApiCall,
        build_api_call: raw.ApiCall,
        hub: str,
        plan_id: uuid.UUID,
        timeline_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> None:
        """Remember the calls and ids the helpers write with."""
        self.agent_call = agent_call
        self.build_api_call = build_api_call
        self.hub = hub
        self.plan_id = plan_id
        self.timeline_id = timeline_id
        self.job_id = job_id

    def build_log(self, log_id: raw.BuildLogId) -> str:
        """Read a build log back through the PAT-authenticated build call."""
        content: bytes = self.build_api_call.get_raw("logs", log_id, version="7.1")
        return content.decode("utf-8")


def _write_feed_and_log(ctx: _Ctx, step: raw.BuildRecordInfo) -> None:
    """Feed goes to the JOB record; the log append is read back."""
    assert step.log is not None
    job_call = raw.get_job_api_call(
        ctx.agent_call, ctx.hub, ctx.plan_id, ctx.timeline_id, ctx.job_id
    )
    raw.post_job_feed(
        job_call, raw.JobFeedPayload(value=["pyado agentless feed"], count=1)
    )
    marker = f"pyado agentless log {uuid.uuid4().hex[:8]}"
    log_call = raw.get_log_api_call(ctx.agent_call, ctx.hub, ctx.plan_id, step.log.id)
    raw.post_job_logs(log_call, marker + "\n")
    assert marker in ctx.build_log(step.log.id)


def _write_child_task(session: TimelineSession, step_name: str) -> None:
    """Create a virtual task below the step's job, give it a log, and finish it."""
    step = session.resolve_task(step_name)
    assert step.parent_id is not None
    job = TimelineTarget(
        record_id=step.parent_id,
        parent_id=None,
        type_name=BuildRecordType.JOB,
        name="job of the step",
    )
    child = session.create_task("pyado child task", under=job, key="smoke/child")
    marker = f"child log {uuid.uuid4().hex[:8]}"
    session.append_log(child, marker, create=True)
    session.finish(child)
    assert child.record_id == session.record_id("smoke/child")


def test_agentless_task_reporting(
    project_api_call: raw.ApiCall,
    pipelines: list[raw.PipelineInfo],
    org_url: str,
    token: str,
) -> None:
    """Send feed, log, a child task and TaskCompleted into a running task."""
    console.print("\n=== AGENTLESS TASK (feed / log / child task / complete) ===")
    pipeline = next((p for p in pipelines if p.name == _ONPREMISE_PIPELINE_NAME), None)
    if pipeline is None:
        pytest.skip(reason="onpremise pipeline not found")

    existing = {
        a.id
        for a in raw.iter_approvals(
            project_api_call, state=raw.PipelineApprovalStatus.PENDING
        )
    }
    triggered = raw.post_pipeline_run(project_api_call, pipeline.id)
    assert triggered is not None
    build_api_call = raw.get_build_api_call(project_api_call, triggered.id)
    _wait_for_and_approve(project_api_call, existing)

    variables = _system_token(build_api_call)
    if not variables.get("SYSTEM_ACCESSTOKEN"):
        pytest.skip(reason="System.AccessToken not printed by the pipeline")
    plan_id = uuid.UUID(variables["SYSTEM_PLANID"])
    timeline_id = uuid.UUID(variables["SYSTEM_TIMELINEID"])
    # The write endpoints reject the project NAME (HTTP 400, empty body): the
    # URL must carry the project id that the step printed.
    agent_call = raw.ApiCall(
        session=raw.get_session(pat=variables["SYSTEM_ACCESSTOKEN"]),
        url=f"{org_url}/{variables['SYSTEM_TEAMPROJECTID']}/_apis",
    )

    # The agentless step starts after the agent job; wait for it to be live.
    step = _wait_for_record(
        build_api_call, _AGENTLESS_STEP_NAME, state="inProgress", timeout=420.0
    )
    assert step is not None, "agentless step never reached inProgress"
    assert step.parent_id is not None
    job_id = step.parent_id
    time.sleep(_READY_DELAY_SECONDS)  # the ICS handler's ensure_ado_is_ready

    # The log is attached by ADO; poll for it instead of assuming it exists.
    step = _wait_for_record(
        build_api_call,
        _AGENTLESS_STEP_NAME,
        state="inProgress",
        timeout=_LOG_ATTACH_TIMEOUT_SECONDS,
        need_log=True,
    )
    assert step is not None
    assert step.log is not None
    hub = variables.get("SYSTEM_HOSTTYPE", "build")

    ctx = _Ctx(agent_call, build_api_call, hub, plan_id, timeline_id, job_id)
    _write_feed_and_log(ctx, step)
    session = TimelineSession.from_tokens(
        org_name=org_url.rsplit("/", 1)[-1],
        project_id=uuid.UUID(variables["SYSTEM_TEAMPROJECTID"]),
        build_id=triggered.id,
        admin_token=token,
        system_token=variables["SYSTEM_ACCESSTOKEN"],
    )
    _write_child_task(session, _AGENTLESS_STEP_NAME)

    # finish the step with the System token (the PAT is rejected here)
    raw.post_job_event(
        raw.get_plan_api_call(agent_call, hub, plan_id),
        raw.JobEventPayload(
            name=JobEventName.TASK_COMPLETED,
            task_id=step.id,
            job_id=job_id,
            result=JobEventResult.SUCCEEDED,
        ),
    )
    done = _wait_for_record(
        build_api_call, _AGENTLESS_STEP_NAME, state="completed", timeout=120.0
    )
    assert done is not None
    assert done.result == "succeeded"
