"""Azure DevOps Pipelines REST API and distributed task wrappers.

Covers the newer ``/pipelines`` endpoints (pipeline runs, pipeline listing)
as well as the distributed task plane (plans, timelines, job feeds, job
events, and environment approvals).
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.raw._core import ApiCall, _IdentityRef
from pyado.raw.build import (
    BuildLogId,
    BuildRecordInfo,
    PlanId,
    TaskId,
    TimelineId,
)
from pyado.raw.variable_group import VariableInfo

__all__ = [
    "JobEventName",
    "JobEventPayload",
    "JobEventResult",
    "JobFeedPayload",
    "JobId",
    "PipelineApproval",
    "PipelineApprovalStatus",
    "PipelineApprovalStep",
    "PipelineApprovalUpdateRequest",
    "PipelineInfo",
    "PipelineRunInfo",
    "PipelineRunRequest",
    "PipelineRunResult",
    "PipelineRunState",
    "TimelineRecordsUpdatePayload",
    "get_job_api_call",
    "get_log_api_call",
    "get_pipeline",
    "get_pipeline_run",
    "get_plan_api_call",
    "get_timeline_api_call",
    "iter_approvals",
    "iter_pipeline_runs",
    "iter_pipelines",
    "patch_approvals",
    "patch_pipeline_run",
    "patch_timeline_records",
    "post_job_event",
    "post_job_feed",
    "post_job_logs",
    "post_pipeline_run",
]

JobId = UUID


class JobEventName(StrEnum):
    """Event name sent to the job completion endpoint."""

    TASK_COMPLETED = "TaskCompleted"


class JobEventResult(StrEnum):
    """Outcome value reported with a job completion event."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PipelineRunState(StrEnum):
    """Possible lifecycle states of a pipeline run."""

    UNKNOWN = "unknown"
    IN_PROGRESS = "inProgress"
    CANCELING = "canceling"
    COMPLETED = "completed"


class PipelineRunResult(StrEnum):
    """Possible outcome values for a completed pipeline run."""

    UNKNOWN = "unknown"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class PipelineApprovalStatus(StrEnum):
    """Possible status values for a pipeline approval step."""

    APPROVED = "approved"
    CANCELED = "canceled"
    FAILED = "failed"
    PENDING = "pending"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    TIMED_OUT = "timedOut"
    UNDEFINED = "undefined"


class PipelineInfo(BaseModel):
    """A pipeline definition returned by the Pipelines REST API."""

    id: int
    revision: int
    name: str
    folder: str
    url: AnyUrl


class _PipelineListResults(BaseModel):
    """Internal: container for pipeline list results."""

    value: list[PipelineInfo]


class PipelineRunInfo(BaseModel):
    """A pipeline run returned by the Pipelines REST API."""

    id: int
    name: str
    state: PipelineRunState
    result: PipelineRunResult | None = None
    pipeline: PipelineInfo
    created_date: datetime = Field(alias="createdDate")
    finished_date: datetime | None = Field(default=None, alias="finishedDate")
    url: AnyUrl
    template_parameters: dict[str, Any] | None = Field(
        alias="templateParameters", default=None
    )
    variables: dict[str, VariableInfo] | None = None


class _PipelineRunListResults(BaseModel):
    """Internal: container for pipeline run list results."""

    value: list[PipelineRunInfo]


class PipelineRunRequest(BaseModel):
    """Request body for triggering a pipeline run."""

    resources: dict[str, Any] | None = Field(
        default=None, serialization_alias="resources"
    )
    variables: dict[str, Any] | None = Field(
        default=None, serialization_alias="variables"
    )
    template_parameters: dict[str, str] | None = Field(
        default=None, serialization_alias="templateParameters"
    )
    stages_to_skip: list[str] | None = Field(
        default=None, serialization_alias="stagesToSkip"
    )


class JobFeedPayload(BaseModel):
    """Payload for the job feed (append timeline record feed) endpoint."""

    value: list[str]
    count: int


class JobEventPayload(BaseModel):
    """Payload for the job event (task completed) endpoint."""

    name: JobEventName
    task_id: TaskId = Field(serialization_alias="taskId")
    job_id: JobId = Field(serialization_alias="jobId")
    result: JobEventResult


class TimelineRecordsUpdatePayload(BaseModel):
    """Payload for the update timeline records endpoint."""

    count: int
    value: list[BuildRecordInfo]


class PipelineApprovalStep(BaseModel):
    """A single step within a pipeline approval."""

    assigned_approver: _IdentityRef = Field(alias="assignedApprover")
    status: str
    actual_approver: _IdentityRef | None = Field(alias="actualApprover", default=None)
    comment: str | None = None


class PipelineApproval(BaseModel):
    """A pipeline environment approval request."""

    id: str
    status: PipelineApprovalStatus
    steps: list[PipelineApprovalStep] = []
    instructions: str | None = None
    blocked_approvers: list[_IdentityRef] = Field(alias="blockedApprovers", default=[])
    min_required_approvers: int = Field(alias="minRequiredApprovers", default=1)
    created_on: datetime | None = Field(alias="createdOn", default=None)


class _PipelineApprovalResults(BaseModel):
    """Internal: container for approval list results."""

    value: list[PipelineApproval]


class PipelineApprovalUpdateRequest(BaseModel):
    """Request body item for patching a pipeline environment approval."""

    approval_id: str = Field(serialization_alias="approvalId")
    status: PipelineApprovalStatus
    comment: str = ""


class _PipelineStateRequest(BaseModel):
    """Internal: request body for updating a pipeline run state."""

    state: str


# ---------------------------------------------------------------------------
# Pipeline REST API functions
# ---------------------------------------------------------------------------


def iter_pipelines(
    project_api_call: ApiCall,
    *,
    order_by: str | None = None,
) -> Iterator[PipelineInfo]:
    """Iterate over pipelines in the project using the Pipelines REST API.

    This uses the newer ``/pipelines`` endpoint (distinct from the Build
    Definitions API at ``/build/definitions``).

    Args:
        project_api_call: Project-level ADO API call.
        order_by: Optional sort expression (e.g. ``"name asc"``).

    Yields:
        PipelineInfo for each pipeline.
    """
    response = project_api_call.get(
        "pipelines",
        parameters={"orderBy": order_by} if order_by is not None else None,
        version="7.1",
    )
    yield from _PipelineListResults.model_validate(response).value


def get_pipeline(
    project_api_call: ApiCall,
    pipeline_id: int,
    *,
    pipeline_version: int | None = None,
) -> PipelineInfo:
    """Fetch a single pipeline by ID.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID.
        pipeline_version: Optional specific revision to fetch.

    Returns:
        PipelineInfo for the requested pipeline.
    """
    response = project_api_call.get(
        "pipelines",
        str(pipeline_id),
        parameters=(
            {"pipelineVersion": pipeline_version}
            if pipeline_version is not None
            else None
        ),
        version="7.1",
    )
    return PipelineInfo.model_validate(response)


def iter_pipeline_runs(
    project_api_call: ApiCall,
    pipeline_id: int,
) -> Iterator[PipelineRunInfo]:
    """Iterate over runs for a pipeline.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID.

    Yields:
        PipelineRunInfo for each run, newest first.
    """
    response = project_api_call.get(
        "pipelines",
        str(pipeline_id),
        "runs",
        version="7.1",
    )
    yield from _PipelineRunListResults.model_validate(response).value


def get_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: int,
    run_id: int,
) -> PipelineRunInfo:
    """Fetch a single pipeline run by ID.

    The run ID is identical to the build ID — the same entity is exposed
    via both the Pipelines API (``/pipelines/{id}/runs/{runId}``) and the
    Build API (``/build/builds/{buildId}``).

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID.
        run_id: The numeric run (build) ID.

    Returns:
        PipelineRunInfo for the requested run.
    """
    response = project_api_call.get(
        "pipelines",
        str(pipeline_id),
        "runs",
        str(run_id),
        version="7.1",
    )
    return PipelineRunInfo.model_validate(response)


def patch_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: int,
    run_id: int,
    state: PipelineRunState,
) -> PipelineRunInfo:
    """Update the state of a pipeline run.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID.
        run_id: The numeric run (build) ID.
        state: New run state to set (e.g. ``"canceling"``).

    Returns:
        PipelineRunInfo reflecting the updated run state.
    """
    response = project_api_call.patch(
        "pipelines",
        str(pipeline_id),
        "runs",
        str(run_id),
        version="7.1",
        json=_PipelineStateRequest(state=state).model_dump(mode="json"),
    )
    return PipelineRunInfo.model_validate(response)


def post_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: int,
    request: PipelineRunRequest | None = None,
) -> PipelineRunInfo:
    """Trigger a new run of a pipeline.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID to trigger.
        request: Optional run parameters (variables, template parameters,
            stages to skip, etc.).  Pass ``None`` to run with defaults.

    Returns:
        PipelineRunInfo describing the newly queued run.
    """
    response = project_api_call.post(
        "pipelines",
        str(pipeline_id),
        "runs",
        version="7.1",
        json=(request or PipelineRunRequest()).model_dump(
            mode="json", by_alias=True, exclude_none=True
        ),
    )
    return PipelineRunInfo.model_validate(response)


# ---------------------------------------------------------------------------
# Distributed task API call helpers
# ---------------------------------------------------------------------------


def get_plan_api_call(
    project_api_call: ApiCall,
    hub_name: str,
    plan_id: PlanId,
) -> ApiCall:
    """Get plan API call.

    Returns:
        An ApiCall pointing at the distributed task plan resource.
    """
    return project_api_call.build_call(
        "distributedtask",
        "hubs",
        hub_name,
        "plans",
        plan_id,
    )


def get_timeline_api_call(
    project_api_call: ApiCall,
    hub_name: str,
    plan_id: PlanId,
    timeline_id: TimelineId,
) -> ApiCall:
    """Get timeline API call.

    Returns:
        An ApiCall pointing at the timeline resource.
    """
    api_call = get_plan_api_call(project_api_call, hub_name, plan_id)
    return api_call.build_call("timelines", timeline_id)


def get_job_api_call(
    project_api_call: ApiCall,
    hub_name: str,
    plan_id: PlanId,
    timeline_id: TimelineId,
    job_id: JobId,
) -> ApiCall:
    """Get job API call.

    Returns:
        An ApiCall pointing at the job record resource.
    """
    api_call = get_timeline_api_call(project_api_call, hub_name, plan_id, timeline_id)
    return api_call.build_call("records", job_id)


def get_log_api_call(
    project_api_call: ApiCall,
    hub_name: str,
    plan_id: PlanId,
    log_id: BuildLogId,
) -> ApiCall:
    """Get job log API call.

    Returns:
        An ApiCall pointing at the job log resource.
    """
    api_call = get_plan_api_call(project_api_call, hub_name, plan_id)
    return api_call.build_call("logs", log_id)


# ---------------------------------------------------------------------------
# Distributed task write functions
# ---------------------------------------------------------------------------


def post_job_feed(job_api_call: ApiCall, payload: JobFeedPayload) -> None:
    """Sends messages to feed of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/feed/
    POST__distributedtask_AppendTimelineRecordFeed_.json
    """
    job_api_call.post(
        "feed",
        version="7.1-preview.1",
        json=payload.model_dump(mode="json"),
    )


def post_job_logs(log_api_call: ApiCall, message: str) -> None:
    """Sends messages to the log of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/logs/
    POST__distributedtask_AppendLogContent_.json
    """
    log_api_call.post(
        version="7.1-preview.1",
        data=message.encode("utf-8"),
    )


def post_job_event(plan_api_call: ApiCall, payload: JobEventPayload) -> None:
    """This notifies the pipeline that the task has completed.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/events/
    POST_distributedtask_PostEvent.json
    """
    plan_api_call.post(
        "events",
        version="7.1-preview.1",
        json=payload.model_dump(mode="json", by_alias=True),
    )


def patch_timeline_records(
    timeline_api_call: ApiCall,
    payload: TimelineRecordsUpdatePayload,
) -> None:
    """Update the timeline records."""
    timeline_api_call.patch(
        "records",
        version="7.1",
        json=payload.model_dump(mode="json", by_alias=True, exclude_defaults=True),
    )


# ---------------------------------------------------------------------------
# Approval functions
# ---------------------------------------------------------------------------


def iter_approvals(
    project_api_call: ApiCall,
    state: PipelineApprovalStatus | None = None,
) -> Iterator[PipelineApproval]:
    """Iterate over pipeline approvals in the project.

    Args:
        project_api_call: Project-level ADO API call.
        state: Optional status filter. If None, all approvals are returned.

    Yields:
        PipelineApproval for each matching approval.
    """
    response = project_api_call.get(
        "pipelines",
        "approvals",
        parameters={"state": state} if state is not None else None,
        version="7.1-preview.1",
    )
    yield from _PipelineApprovalResults.model_validate(response).value


def patch_approvals(
    project_api_call: ApiCall,
    updates: list[PipelineApprovalUpdateRequest],
) -> None:
    """Patch one or more pipeline environment approvals.

    Args:
        project_api_call: Project-level ADO API call.
        updates: List of approval updates to apply.
    """
    project_api_call.patch(
        "pipelines",
        "approvals",
        version="7.1-preview.1",
        json=[u.model_dump(mode="json", by_alias=True) for u in updates],
    )
