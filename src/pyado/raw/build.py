"""Azure DevOps Build API wrappers: builds, timelines, artifacts, pipeline defs."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as _json
from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer
from pydantic.networks import AnyUrl

from pyado.raw._core import ADOUrl, ApiCall, _IdentityRef
from pyado.raw.project import ProjectInfo
from pyado.raw.work_item import WorkItemRef, _WorkItemRefResults

__all__ = [
    "BuildArtifact",
    "BuildArtifactResource",
    "BuildAttemptInfo",
    "BuildDetails",
    "BuildId",
    "BuildIssue",
    "BuildIssueType",
    "BuildLogId",
    "BuildLogInfo",
    "BuildLogType",
    "BuildQueueRequest",
    "BuildRecordInfo",
    "BuildRecordResult",
    "BuildRecordState",
    "BuildRecordType",
    "BuildRecordTypeInfo",
    "BuildResult",
    "BuildSearchCriteria",
    "BuildStatus",
    "PipelineDefinitionInfo",
    "PlanId",
    "QueueId",
    "TaskId",
    "TimelineId",
    "delete_build_tag",
    "get_build_api_call",
    "get_build_details",
    "iter_build_artifacts",
    "iter_build_tags",
    "iter_build_work_item_ids",
    "iter_builds",
    "iter_pipeline_definitions",
    "iter_timeline_records",
    "iter_work_items_between_builds",
    "patch_build",
    "post_build",
    "post_build_tag",
]

BuildId = int
TimelineId = UUID
TaskId = UUID
QueueId = int
BuildLogId = int


class BuildStatus(StrEnum):
    """Possible build status values used to filter or inspect a build."""

    ALL = "all"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    IN_PROGRESS = "inProgress"
    NONE = "none"
    NOT_STARTED = "notStarted"
    POSTPONED = "postponed"


class BuildResult(StrEnum):
    """Possible outcome values for a completed build."""

    CANCELED = "canceled"
    FAILED = "failed"
    NONE = "none"
    PARTIALLY_SUCCEEDED = "partiallySucceeded"
    SUCCEEDED = "succeeded"


class BuildRecordType(StrEnum):
    """Timeline record types present in a build's timeline."""

    CHECKPOINT = "Checkpoint"
    CHECKPOINT_APPROVAL = "Checkpoint.Approval"
    CHECKPOINT_AUTHORIZATION = "Checkpoint.Authorization"
    CHECKPOINT_EXTENDS_CHECK = "Checkpoint.ExtendsCheck"
    PHASE = "Phase"
    STAGE = "Stage"
    JOB = "Job"
    TASK = "Task"


class BuildLogType(StrEnum):
    """Log container types returned by the build log endpoint."""

    CONTAINER = "Container"


class BuildIssueType(StrEnum):
    """Severity types for a build issue."""

    ERROR = "error"
    WARNING = "warning"


class BuildRecordResult(StrEnum):
    """Outcome values for a single timeline record within a build."""

    CANCELED = "canceled"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"


class BuildRecordState(StrEnum):
    """Lifecycle state values for a single timeline record within a build."""

    COMPLETED = "completed"
    IN_PROGRESS = "inProgress"
    PENDING = "pending"


PlanId = UUID


class BuildArtifactResource(BaseModel):
    """The downloadable resource backing a build artifact."""

    type: str
    url: str
    download_url: str | None = Field(alias="downloadUrl", default=None)
    data: str | None = None


class BuildArtifact(BaseModel):
    """An artifact produced by a build."""

    id: int
    name: str
    source: str | None = None
    resource: BuildArtifactResource


class _BuildArtifactResults(BaseModel):
    """Internal: container for build artifact list results."""

    value: list[BuildArtifact]


class _BuildTagResults(BaseModel):
    """Internal: container for build tag list results."""

    value: list[str] = []


class BuildLogInfo(BaseModel, extra="forbid"):
    """Type to store build log details."""

    id: BuildLogId
    log_type: BuildLogType = Field(alias="type")
    url: ADOUrl


class BuildRecordTypeInfo(BaseModel, extra="forbid"):
    """Type to store build task type details."""

    id: TaskId
    name: str
    version: str


class BuildAttemptInfo(BaseModel, extra="forbid"):
    """Type to store build attempt details."""

    attempt: int
    timeline_id: UUID = Field(alias="timelineId")
    record_id: UUID = Field(alias="recordId")


class BuildIssue(BaseModel, extra="forbid"):
    """Type for build message issues."""

    category: str | None = None
    data: dict[str, str] | None = None
    message: str
    type: BuildIssueType


class BuildRecordInfo(BaseModel, extra="forbid"):
    """Type to store build task details."""

    attempt: int
    change_id: int | None = Field(alias="changeId")
    current_operation: Any = Field(alias="currentOperation")
    details: Any
    error_count: int | None = Field(default=None, alias="errorCount")
    finish_time: datetime | None = Field(alias="finishTime")
    id: TaskId
    identifier: str | None
    issues: list[BuildIssue] | None = None
    last_modified: datetime = Field(alias="lastModified")
    log: BuildLogInfo | None
    name: str
    order: int | None = None
    ref_name: str | None = Field(alias="refName")
    parent_id: TaskId | None = Field(alias="parentId")
    percent_complete: int | None = Field(alias="percentComplete")
    previous_attempts: list[BuildAttemptInfo] = Field(alias="previousAttempts")
    queue_id: QueueId | None = Field(default=None, alias="queueId")
    result: BuildRecordResult | None
    result_code: str | None = Field(alias="resultCode")
    start_time: datetime | None = Field(alias="startTime")
    state: BuildRecordState
    task: BuildRecordTypeInfo | None
    type_name: BuildRecordType = Field(alias="type")
    url: AnyUrl | None
    warning_count: int | None = Field(default=None, alias="warningCount")
    worker_name: str | None = Field(alias="workerName")


class _BuildRecordInfoResults(BaseModel):
    """Type to read build record details results."""

    records: list[BuildRecordInfo]
    id: TimelineId


class _BuildRepository(BaseModel):
    """Repository associated with a build run."""

    id: str
    name: str
    type: str
    url: str | None = None


class _BuildDefinitionRef(BaseModel):
    """Internal: minimal pipeline definition reference inside a build record."""

    id: int
    name: str


class _BuildOrchestrationPlan(BaseModel):
    """Internal: orchestration plan reference embedded in build details."""

    plan_id: PlanId = Field(alias="planId")


class BuildDetails(BaseModel):
    """Type to store top-level build (pipeline run) details."""

    id: BuildId
    build_number: str = Field(alias="buildNumber")
    status: BuildStatus
    result: BuildResult | None = None
    queue_time: datetime | None = Field(alias="queueTime", default=None)
    start_time: datetime | None = Field(alias="startTime", default=None)
    finish_time: datetime | None = Field(alias="finishTime", default=None)
    last_changed_date: datetime | None = Field(alias="lastChangedDate", default=None)
    source_branch: str = Field(alias="sourceBranch")
    source_version: str = Field(alias="sourceVersion")
    definition: _BuildDefinitionRef
    requested_by: _IdentityRef = Field(alias="requestedBy")
    requested_for: _IdentityRef | None = Field(alias="requestedFor", default=None)
    reason: str | None = None
    priority: str | None = None
    url: str | None = None
    tags: list[str] = []
    parameters: str | None = None
    repository: _BuildRepository | None = None
    project: ProjectInfo | None = None
    trigger_info: dict[str, str] | None = Field(alias="triggerInfo", default=None)
    orchestration_plan: _BuildOrchestrationPlan | None = Field(
        alias="orchestrationPlan", default=None
    )
    logs: BuildLogInfo | None = None
    deleted: bool = False


class _BuildDetailsResults(BaseModel):
    """Internal: container for build list results."""

    value: list[BuildDetails]


class BuildQueueRequest(BaseModel):
    """Request body for queueing a new build run.

    ADO requires ``parameters`` to be serialised as a JSON string rather than
    an object, which is handled automatically by the field serializer.
    ADO requires ``definition`` to be a nested object; ``definition_id`` is
    serialised automatically as ``{"definition": {"id": ...}}``.
    """

    definition_id: int = Field(serialization_alias="definition")
    source_branch: str | None = Field(default=None, serialization_alias="sourceBranch")
    source_version: str | None = Field(
        default=None, serialization_alias="sourceVersion"
    )
    parameters: dict[str, str] | None = None

    @field_serializer("definition_id")
    @staticmethod
    def _serialize_definition(value: int) -> dict[str, int]:
        """Serialize definition_id as the nested object ADO expects.

        Returns:
            Dict with ``id`` key as required by the ADO queue-build API.
        """
        return {"id": value}

    @field_serializer("parameters")
    @staticmethod
    def _serialize_parameters(value: dict[str, str] | None) -> str | None:
        """Serialize parameters dict as a JSON string (ADO requirement).

        Returns:
            JSON string if value is provided, otherwise None.
        """
        return _json.dumps(value) if value is not None else None


class PipelineDefinitionInfo(BaseModel):
    """Type to store pipeline definition details."""

    id: int
    name: str
    path: str
    queue_status: str = Field(alias="queueStatus")
    revision: int


class _PipelineDefinitionResults(BaseModel):
    """Internal: container for pipeline definition list results."""

    value: list[PipelineDefinitionInfo]


class BuildSearchCriteria(BaseModel):
    """Search criteria for listing build runs.

    All fields are optional; only non-None values are forwarded as query
    parameters to the builds list endpoint.

    Attributes:
        definition_id: Filter to a specific pipeline definition ID.
        status_filter: Filter by build status.
        branch_name: Filter by source branch ref name.
        top: Maximum number of results to return.
    """

    definition_id: int | None = Field(default=None, serialization_alias="definitions")
    status_filter: BuildStatus | None = Field(
        default=None, serialization_alias="statusFilter"
    )
    branch_name: str | None = Field(default=None, serialization_alias="branchName")
    top: int | None = Field(default=None, serialization_alias="$top")


class _BuildStatusRequest(BaseModel):
    """Internal: request body for updating a build status."""

    status: str


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def iter_build_work_item_ids(build_api_call: ApiCall) -> Iterator[WorkItemRef]:
    """Iterate over work items linked to a build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        WorkItemRef for each work item associated with the build.
    """
    page_size = 100
    skip = 0
    while True:
        response = build_api_call.get(
            "workitems",
            parameters={"$top": page_size, "$skip": skip},
            version="7.0",
        )
        results = _WorkItemRefResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def iter_work_items_between_builds(
    project_api_call: ApiCall,
    from_build_id: BuildId,
    to_build_id: BuildId,
    *,
    top: int | None = None,
) -> Iterator[WorkItemRef]:
    """Iterate over work items associated with builds in the range (from, to].

    Args:
        project_api_call: Project-level ADO API call.
        from_build_id: The ID of the earlier build (exclusive lower bound).
        to_build_id: The ID of the later build (inclusive upper bound).
        top: Maximum number of work items to return.

    Yields:
        WorkItemRef for each work item in the build range.
    """
    response = project_api_call.get(
        "build",
        "workitems",
        parameters={
            key: value
            for key, value in {
                "fromBuildId": from_build_id,
                "toBuildId": to_build_id,
                "$top": top,
            }.items()
            if value is not None
        },
        version="7.1",
    )
    yield from _WorkItemRefResults.model_validate(response).value


def get_build_api_call(project_api_call: ApiCall, build_id: BuildId) -> ApiCall:
    """Get the API call for a specific build run.

    Args:
        project_api_call: Project-level ADO API call.
        build_id: Numeric ID of the build run.

    Returns:
        An ApiCall pointing at the build resource for the given build ID.
    """
    return project_api_call.build_call(
        "build",
        "builds",
        build_id,
    )


def iter_build_artifacts(build_api_call: ApiCall) -> Iterator[BuildArtifact]:
    """Iterate over artifacts produced by a build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        BuildArtifact for each artifact attached to the build.
    """
    response = build_api_call.get("artifacts", version="7.1")
    yield from _BuildArtifactResults.model_validate(response).value


def iter_build_tags(build_api_call: ApiCall) -> Iterator[str]:
    """Iterate over tags attached to a build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        Each tag string associated with the build.
    """
    response = build_api_call.get("tags", version="7.1")
    yield from _BuildTagResults.model_validate(response).value


def post_build_tag(build_api_call: ApiCall, tag: str) -> list[str]:
    """Add a tag to a build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).
        tag: The tag string to add.

    Returns:
        Updated list of all tags on the build.
    """
    response = build_api_call.put("tags", tag, version="7.1")
    return _BuildTagResults.model_validate(response).value


def delete_build_tag(build_api_call: ApiCall, tag: str) -> list[str]:
    """Remove a tag from a build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).
        tag: The tag string to remove.

    Returns:
        Updated list of all remaining tags on the build.
    """
    response = build_api_call.delete("tags", tag, version="7.1")
    return _BuildTagResults.model_validate(response).value


def iter_timeline_records(build_api_call: ApiCall) -> Iterator[BuildRecordInfo]:
    """Iterate over task records in the build timeline.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/build/7.1/build.json#L2478

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        BuildRecordInfo objects for each record in the timeline.
    """
    response = build_api_call.get(
        "timeline",
        version="7.1",
    )
    results = _BuildRecordInfoResults.model_validate(response)
    yield from results.records


def get_build_details(build_api_call: ApiCall) -> BuildDetails:
    """Return the top-level details of a build run.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Returns:
        BuildDetails for the build.
    """
    response = build_api_call.get(version="7.1")
    return BuildDetails.model_validate(response)


def iter_builds(
    project_api_call: ApiCall,
    search_criteria: BuildSearchCriteria | None = None,
) -> Iterator[BuildDetails]:
    """Iterate over build runs in the project.

    Args:
        project_api_call: Project-level ADO API call.
        search_criteria: Optional search criteria model; only non-None
            fields are forwarded as query parameters.

    Yields:
        BuildDetails for each matching build run.
    """
    parameters: dict[str, int | str | bool] = (
        search_criteria.model_dump(mode="json", by_alias=True, exclude_none=True)
        if search_criteria
        else {}
    )
    response = project_api_call.get(
        "build",
        "builds",
        parameters=parameters,
        version="7.1",
    )
    yield from _BuildDetailsResults.model_validate(response).value


def post_build(
    project_api_call: ApiCall,
    request: BuildQueueRequest,
) -> BuildDetails:
    """Queue a new build run for a pipeline definition.

    Args:
        project_api_call: Project-level ADO API call.
        request: Build queue request specifying the definition and options.

    Returns:
        BuildDetails for the queued build run.
    """
    response = project_api_call.post(
        "build",
        "builds",
        version="7.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return BuildDetails.model_validate(response)


def patch_build(build_api_call: ApiCall, status: BuildStatus) -> BuildDetails:
    """Update the status of a build run.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).
        status: New build status to set (e.g. ``"cancelling"``).

    Returns:
        BuildDetails reflecting the updated build state.
    """
    response = build_api_call.patch(
        version="7.1",
        json=_BuildStatusRequest(status=status).model_dump(mode="json"),
    )
    return BuildDetails.model_validate(response)


def iter_pipeline_definitions(
    project_api_call: ApiCall,
    *,
    name_filter: str | None = None,
) -> Iterator[PipelineDefinitionInfo]:
    """Iterate over pipeline definitions in the project.

    Args:
        project_api_call: Project-level ADO API call.
        name_filter: Optional name substring filter.

    Yields:
        PipelineDefinitionInfo for each matching definition.
    """
    response = project_api_call.get(
        "build",
        "definitions",
        parameters={"name": name_filter} if name_filter is not None else None,
        version="7.1",
    )
    yield from _PipelineDefinitionResults.model_validate(response).value
