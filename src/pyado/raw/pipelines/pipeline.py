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
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import Field, field_serializer
from pydantic.networks import AnyUrl

from pyado.raw._core import AdoBaseModel, ApiCall, _IdentityRef
from pyado.raw.pipelines.build import (
    BuildLogId,
    BuildRecordInfo,
    PlanId,
    TaskId,
    TimelineId,
)
from pyado.raw.pipelines.variable_group import VariableInfo

__all__ = [
    "ApprovalId",
    "JobEventName",
    "JobEventPayload",
    "JobEventResult",
    "JobFeedPayload",
    "JobId",
    "PipelineApproval",
    "PipelineApprovalStatus",
    "PipelineApprovalStep",
    "PipelineApprovalUpdateRequest",
    "PipelineId",
    "PipelineInfo",
    "PipelinePermissionEntry",
    "PipelineResourcePermissions",
    "PipelineResourceType",
    "PipelineRunId",
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
    "list_approvals",
    "list_pipeline_runs",
    "list_pipelines",
    "patch_approvals",
    "patch_pipeline_permission",
    "patch_timeline_records",
    "post_job_event",
    "post_job_feed",
    "post_job_logs",
    "post_pipeline_run",
]

JobId: TypeAlias = UUID
PipelineId: TypeAlias = int
#: Numeric identifier for a pipeline run instance.
PipelineRunId: TypeAlias = int
#: String identifier for a pipeline approval gate.
ApprovalId: TypeAlias = str


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


class PipelineInfo(AdoBaseModel):
    """A pipeline definition returned by the Pipelines REST API."""

    id: PipelineId
    revision: int
    name: str
    folder: str
    url: AnyUrl


class _PipelineListResults(AdoBaseModel):
    """Internal: container for pipeline list results."""

    value: list[PipelineInfo]


class PipelineRunInfo(AdoBaseModel):
    """A pipeline run returned by the Pipelines REST API."""

    id: PipelineRunId
    name: str
    state: PipelineRunState
    result: PipelineRunResult | None = None
    pipeline: PipelineInfo
    created_date: datetime
    finished_date: datetime | None = None
    url: AnyUrl
    template_parameters: dict[str, str] | None = None
    variables: dict[str, VariableInfo] | None = None
    final_yaml: str | None = None


class _PipelineRunListResults(AdoBaseModel):
    """Internal: container for pipeline run list results."""

    value: list[PipelineRunInfo]


class PipelineRunRequest(AdoBaseModel):
    """Request body for triggering a pipeline run."""

    resources: dict[str, Any] | None = None
    variables: dict[str, VariableInfo] | None = None
    template_parameters: dict[str, str] | None = None
    stages_to_skip: list[str] | None = None


class JobFeedPayload(AdoBaseModel):
    """Payload for the job feed (append timeline record feed) endpoint."""

    value: list[str]
    count: int


class JobEventPayload(AdoBaseModel):
    """Payload for the job event (task completed) endpoint."""

    name: JobEventName
    task_id: TaskId
    job_id: JobId
    result: JobEventResult


class TimelineRecordsUpdatePayload(AdoBaseModel):
    """Payload for the update timeline records endpoint."""

    count: int
    value: list[BuildRecordInfo]


class PipelineApprovalStep(AdoBaseModel):
    """A single step within a pipeline approval."""

    assigned_approver: _IdentityRef
    status: PipelineApprovalStatus
    actual_approver: _IdentityRef | None = None
    comment: str | None = None


class PipelineApproval(AdoBaseModel):
    """A pipeline environment approval request."""

    id: ApprovalId
    status: PipelineApprovalStatus
    steps: list[PipelineApprovalStep] = Field(default_factory=list)
    instructions: str | None = None
    blocked_approvers: list[_IdentityRef] = Field(default_factory=list)
    min_required_approvers: int = 1
    created_on: datetime | None = None


class _PipelineApprovalResults(AdoBaseModel):
    """Internal: container for approval list results."""

    value: list[PipelineApproval]


class _ApprovalsQuery(AdoBaseModel):
    """Internal: query parameters for the approvals list endpoint."""

    state: PipelineApprovalStatus | None = None
    pipeline_run_ids: list[int] | None = Field(
        default=None, serialization_alias="pipelineIds"
    )

    @field_serializer("pipeline_run_ids")
    @staticmethod
    def _serialise_run_ids(value: list[int] | None) -> str | None:
        """Serialise run IDs to a comma-separated string.

        Returns:
            Comma-separated string of run IDs, or ``None`` if the list is ``None``.
        """
        return ",".join(str(rid) for rid in value) if value is not None else None


class PipelineApprovalUpdateRequest(AdoBaseModel):
    """Request body item for patching a pipeline environment approval."""

    approval_id: ApprovalId
    status: PipelineApprovalStatus
    comment: str = ""


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
    pipeline_id: PipelineId,
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
    pipeline_id: PipelineId,
    *,
    top: int | None = None,
) -> Iterator[PipelineRunInfo]:
    """Iterate over runs for a pipeline.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: The numeric pipeline ID.
        top: Maximum number of runs to return.  When ``None`` the API default
            is used.

    Yields:
        PipelineRunInfo for each run, newest first.
    """
    parameters: dict[str, int | str | bool] = {}
    if top is not None:
        parameters["$top"] = top
    response = project_api_call.get(
        "pipelines",
        str(pipeline_id),
        "runs",
        parameters=parameters or None,
        version="7.1",
    )
    yield from _PipelineRunListResults.model_validate(response).value


def get_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: PipelineId,
    run_id: PipelineRunId,
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


def post_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: PipelineId,
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
    pipeline_run_ids: list[int] | None = None,
) -> Iterator[PipelineApproval]:
    """Iterate over pipeline approvals in the project.

    Args:
        project_api_call: Project-level ADO API call.
        state: Optional status filter. If None, all approvals are returned.
        pipeline_run_ids: Optional list of pipeline run IDs (identical to
            build IDs for Pipelines v2 runs) to restrict results to approvals
            belonging to those runs.

    Yields:
        PipelineApproval for each matching approval.
    """
    query = _ApprovalsQuery(state=state, pipeline_run_ids=pipeline_run_ids)
    parameters = query.model_dump(mode="json", by_alias=True, exclude_none=True)
    response = project_api_call.get(
        "pipelines",
        "approvals",
        parameters=parameters or None,
        version="7.1-preview.1",
    )
    yield from _PipelineApprovalResults.model_validate(response).value


class PipelineResourceType(StrEnum):
    """Resource type values for the pipeline resource permissions endpoint."""

    ENDPOINT = "endpoint"
    ENVIRONMENT = "environment"
    QUEUE = "queue"
    REPOSITORY = "repository"
    SECURE_FILE = "securefile"
    VARIABLE_GROUP = "variablegroup"


class PipelinePermissionEntry(AdoBaseModel):
    """Authorization state for a single pipeline or the all-pipelines wildcard."""

    authorized: bool
    authorized_by: _IdentityRef | None = None
    authorized_on: datetime | None = None
    id: PipelineId | None = None


class _PipelineResourceRef(AdoBaseModel):
    """Resource descriptor returned in the pipelinepermissions response body."""

    type: str
    id: str


class PipelineResourcePermissions(AdoBaseModel):
    """Resource-level permissions response from the pipelinepermissions endpoint."""

    resource: _PipelineResourceRef | None = None
    all_pipelines: PipelinePermissionEntry | None = None
    pipelines: list[PipelinePermissionEntry] = Field(default_factory=list)


class _PipelinePermissionRequest(AdoBaseModel):
    """Internal: single-pipeline authorization request body."""

    authorized: bool
    id: PipelineId


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


def patch_pipeline_permission(
    project_api_call: ApiCall,
    resource_type: PipelineResourceType,
    resource_id: str,
    pipeline_id: PipelineId,
    *,
    authorized: bool,
) -> PipelineResourcePermissions:
    """Authorize or de-authorize a pipeline to use a protected resource.

    Maps to ``PATCH /{project}/_apis/pipelines/pipelinepermissions/{type}/{id}``.

    **Important — additive semantics:** this endpoint only *adds* authorizations;
    it never removes existing ones.  There is no bulk-replace endpoint.  To
    remove a pipeline authorization you must use the ADO web UI or compare the
    current ADO state against your expected configuration and handle the delta
    manually.

    Args:
        project_api_call: Project-level ADO API call.
        resource_type: The resource category (e.g.
            ``PipelineResourceType.VARIABLE_GROUP``).
        resource_id: String identifier of the resource (numeric ID as a string
            for variable groups and queues; GUID string for environments).
        pipeline_id: Numeric pipeline ID to authorize.
        authorized: ``True`` to grant access, ``False`` to revoke.

    Returns:
        PipelineResourcePermissions reflecting the updated state of the
        resource's authorization list.
    """
    body = {
        "pipelines": [
            _PipelinePermissionRequest(
                authorized=authorized, id=pipeline_id
            ).model_dump(mode="json", by_alias=True)
        ]
    }
    response = project_api_call.patch(
        "pipelines",
        "pipelinepermissions",
        str(resource_type),
        resource_id,
        version="7.1-preview.1",
        json=body,
    )
    return PipelineResourcePermissions.model_validate(response)


def list_pipelines(
    project_api_call: ApiCall,
    order_by: str | None = None,
) -> list[PipelineInfo]:
    """Return all pipelines as a list."""
    return list(iter_pipelines(project_api_call, order_by=order_by))


def list_pipeline_runs(
    project_api_call: ApiCall,
    pipeline_id: PipelineId,
    top: int | None = None,
) -> list[PipelineRunInfo]:
    """Return all runs for a pipeline as a list."""
    return list(iter_pipeline_runs(project_api_call, pipeline_id, top=top))


def list_approvals(project_api_call: ApiCall) -> list[PipelineApproval]:
    """Return all pending approvals as a list."""
    return list(iter_approvals(project_api_call))
