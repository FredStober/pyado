"""Module to interact with Azure DevOps work items."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field

from pyado.api_call import ApiCall
from pyado.build import (
    BuildLogId,
    BuildRecordInfo,
    TaskId,
    TimelineId,
)

PlanId: TypeAlias = UUID
JobId: TypeAlias = UUID
JobEventName: TypeAlias = Literal["TaskCompleted"]
JobEventResult: TypeAlias = Literal["succeeded", "failed"]


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


def send_job_feed(job_api_call: ApiCall, messages: list[str]) -> None:
    """Sends messages to feed of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/feed/
    POST__distributedtask_AppendTimelineRecordFeed_.json
    """
    feed_payload = {
        "value": messages,
        "count": len(messages),
    }
    job_api_call.post(
        "feed",
        version="7.1-preview.1",
        json=feed_payload,
    )


def send_job_logs(log_api_call: ApiCall, message: str) -> None:
    """Sends messages to the log of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/logs/
    POST__distributedtask_AppendLogContent_.json
    """
    log_api_call.post(
        version="7.1-preview.1",
        data=message.encode("utf-8"),
    )


class _JobEventPayload(BaseModel):
    """Type to store the job event payload."""

    name: JobEventName
    task_id: TaskId = Field(serialization_alias="taskId")
    job_id: JobId = Field(serialization_alias="jobId")
    result: JobEventResult


def send_job_event(
    plan_api_call: ApiCall,
    task_id: TaskId,
    job_id: JobId,
    job_event_name: JobEventName,
    job_event_result: JobEventResult,
) -> None:
    """This notifies the pipeline that the task has completed.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/events/
    POST_distributedtask_PostEvent.json
    """
    job_event_payload = _JobEventPayload(
        name=job_event_name,
        task_id=task_id,
        job_id=job_id,
        result=job_event_result,
    )
    plan_api_call.post(
        "events",
        version="7.1-preview.1",
        json=job_event_payload.model_dump(mode="json", by_alias=True),
    )


class _TimelineRecordsUpdatePayload(BaseModel):
    """Type to update timeline records."""

    count: int
    value: list[BuildRecordInfo]


def update_timeline_records(
    timeline_api_call: ApiCall,
    records: list[BuildRecordInfo],
) -> None:
    """Update the timeline records."""
    payload = _TimelineRecordsUpdatePayload(value=records, count=len(records))
    payload_dict = payload.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    timeline_api_call.patch(
        "records",
        version="7.1",
        json=payload_dict,
    )


class _ApprovalIdentityRef(BaseModel):
    """Internal: identity reference within an approval."""

    id: str
    display_name: str = Field(alias="displayName")


class PipelineApprovalStep(BaseModel):
    """A single step within a pipeline approval."""

    assigned_approver: _ApprovalIdentityRef = Field(alias="assignedApprover")
    status: str
    actual_approver: _ApprovalIdentityRef | None = Field(
        alias="actualApprover", default=None
    )
    comment: str | None = None


PipelineApprovalStatus: TypeAlias = Literal[
    "approved",
    "canceled",
    "failed",
    "pending",
    "rejected",
    "skipped",
    "timedOut",
    "undefined",
]


class PipelineApproval(BaseModel):
    """A pipeline environment approval request."""

    id: str
    status: PipelineApprovalStatus
    steps: list[PipelineApprovalStep] = []
    instructions: str | None = None
    blocked_approvers: list[_ApprovalIdentityRef] = Field(
        alias="blockedApprovers", default=[]
    )
    min_required_approvers: int = Field(alias="minRequiredApprovers", default=1)


class _PipelineApprovalResults(BaseModel):
    """Internal: container for approval list results."""

    value: list[PipelineApproval]


def iter_pending_approvals(project_api_call: ApiCall) -> Iterator[PipelineApproval]:
    """Iterate over pending pipeline approvals in the project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        PipelineApproval for each pending approval.
    """
    response = project_api_call.get(
        "pipelines",
        "approvals",
        parameters={"state": "pending"},
        version="7.1-preview.1",
    )
    yield from _PipelineApprovalResults.model_validate(response).value


def approve_pipeline(
    project_api_call: ApiCall,
    approval_id: str,
    *,
    comment: str = "",
) -> None:
    """Approve a pending pipeline environment approval.

    Args:
        project_api_call: Project-level ADO API call.
        approval_id: UUID string of the approval to approve.
        comment: Optional comment to attach to the approval.
    """
    project_api_call.patch(
        "pipelines",
        "approvals",
        version="7.1-preview.1",
        json=[{"approvalId": approval_id, "status": "approved", "comment": comment}],
    )
