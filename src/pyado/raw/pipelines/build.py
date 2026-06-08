"""Azure DevOps Build API wrappers: builds, timelines, artifacts, pipeline defs."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as _json
from collections.abc import Iterator
from contextlib import suppress
from datetime import datetime
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

from pydantic import Field, field_serializer
from pydantic.networks import AnyUrl

from pyado.raw._core import AdoBaseModel, AdoUrl, ApiCall, _IdentityRef
from pyado.raw.boards.work_item import WorkItemRef, _WorkItemRefResults
from pyado.raw.core.project import ProjectInfo

__all__ = [
    "BuildArtifact",
    "BuildArtifactId",
    "BuildArtifactResource",
    "BuildAttemptInfo",
    "BuildDetails",
    "BuildExpand",
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
    "PipelineDefinitionId",
    "PipelineDefinitionInfo",
    "PlanId",
    "QueueId",
    "TaskId",
    "TimelineId",
    "TimelineReference",
    "delete_build_tag",
    "get_build_api_call",
    "get_build_artifact_bytes",
    "get_build_details",
    "get_build_log",
    "iter_build_artifacts",
    "iter_build_logs",
    "iter_build_tags",
    "iter_build_work_item_ids",
    "iter_builds",
    "iter_pipeline_definitions",
    "iter_timeline_records",
    "iter_work_items_between_builds",
    "list_build_artifacts",
    "list_build_logs",
    "list_build_tags",
    "list_build_work_item_ids",
    "list_builds",
    "list_pipeline_definitions",
    "list_timeline_records",
    "list_work_items_between_builds",
    "patch_build",
    "post_build",
    "post_build_tag",
]

BuildId: TypeAlias = int
TimelineId: TypeAlias = UUID
TaskId: TypeAlias = UUID
QueueId: TypeAlias = int
BuildLogId: TypeAlias = int
#: Numeric identifier for a pipeline (build) definition.
PipelineDefinitionId: TypeAlias = int
#: Numeric identifier for a build artifact.
BuildArtifactId: TypeAlias = int


class BuildStatus(StrEnum):
    """Possible build status values used to filter or inspect a build."""

    ALL = "all"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    IN_PROGRESS = "inProgress"
    NONE = "none"
    NOT_STARTED = "notStarted"
    POSTPONED = "postponed"


class BuildExpand(StrEnum):
    """Expand options for build fetch requests."""

    NONE = "none"
    TRIGGERS = "triggers"
    VARIABLES = "variables"
    TAGS = "tags"
    PROJECT = "project"
    RETENTION_RULES = "retentionRules"
    ALL = "all"


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

    ABANDONED = "abandoned"
    CANCELED = "canceled"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_ISSUES = "succeededWithIssues"


class BuildRecordState(StrEnum):
    """Lifecycle state values for a single timeline record within a build."""

    COMPLETED = "completed"
    IN_PROGRESS = "inProgress"
    PENDING = "pending"


PlanId: TypeAlias = UUID


class BuildArtifactResource(AdoBaseModel):
    """The downloadable resource backing a build artifact."""

    type: str
    url: str
    download_url: str | None = None
    data: str | None = None


class BuildArtifact(AdoBaseModel):
    """An artifact produced by a build."""

    id: BuildArtifactId
    name: str
    source: str | None = None
    resource: BuildArtifactResource


class _BuildArtifactResults(AdoBaseModel):
    """Internal: container for build artifact list results."""

    value: list[BuildArtifact]


class _BuildTagResults(AdoBaseModel):
    """Internal: container for build tag list results."""

    value: list[str] = Field(default_factory=list)


class BuildLogInfo(AdoBaseModel, extra="forbid"):
    """Type to store build log details."""

    id: BuildLogId
    log_type: BuildLogType = Field(alias="type")
    url: AdoUrl
    line_count: int | None = None
    created_on: datetime | None = None
    last_changed_on: datetime | None = None


class BuildRecordTypeInfo(AdoBaseModel, extra="forbid"):
    """Type to store build task type details."""

    id: TaskId
    name: str
    version: str


class BuildAttemptInfo(AdoBaseModel, extra="forbid"):
    """Type to store build attempt details."""

    attempt: int
    timeline_id: TimelineId
    record_id: TaskId


class BuildIssue(AdoBaseModel, extra="forbid"):
    """Type for build message issues."""

    category: str | None = None
    data: dict[str, str] | None = None
    message: str
    type: BuildIssueType


class TimelineReference(AdoBaseModel, extra="forbid"):
    """A reference to a sub-timeline within a build timeline record."""

    change_id: int
    id: TimelineId
    url: AnyUrl


class BuildRecordInfo(AdoBaseModel, extra="ignore"):
    """Type to store build task details."""

    attempt: int
    change_id: int | None
    current_operation: str | None
    details: TimelineReference | None
    error_count: int | None = None
    finish_time: datetime | None
    id: TaskId
    identifier: str | None
    issues: list[BuildIssue] | None = None
    last_modified: datetime
    log: BuildLogInfo | None
    name: str
    order: int | None = None
    ref_name: str | None
    parent_id: TaskId | None
    percent_complete: int | None
    previous_attempts: list[BuildAttemptInfo]
    queue_id: QueueId | None = None
    result: BuildRecordResult | None
    result_code: str | None
    start_time: datetime | None
    state: BuildRecordState
    task: BuildRecordTypeInfo | None
    type_name: BuildRecordType = Field(alias="type")
    url: AnyUrl | None
    warning_count: int | None = None
    worker_name: str | None


class _BuildRecordInfoResults(AdoBaseModel):
    """Type to read build record details results."""

    records: list[BuildRecordInfo]
    id: TimelineId


class _BuildRepository(AdoBaseModel):
    """Repository associated with a build run."""

    id: str
    name: str
    type: str
    url: str | None = None


class _BuildDefinitionRef(AdoBaseModel):
    """Internal: minimal pipeline definition reference inside a build record."""

    id: PipelineDefinitionId
    name: str


class _BuildOrchestrationPlan(AdoBaseModel):
    """Internal: orchestration plan reference embedded in build details."""

    plan_id: PlanId


class BuildDetails(AdoBaseModel):
    """Type to store top-level build (pipeline run) details."""

    id: BuildId
    build_number: str
    status: BuildStatus
    result: BuildResult | None = None
    queue_time: datetime | None = None
    start_time: datetime | None = None
    finish_time: datetime | None = None
    last_changed_date: datetime | None = None
    source_branch: str
    source_version: str
    definition: _BuildDefinitionRef
    requested_by: _IdentityRef
    requested_for: _IdentityRef | None = None
    reason: str | None = None
    priority: str | None = None
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    parameters: str | None = None
    repository: _BuildRepository | None = None
    project: ProjectInfo | None = None
    trigger_info: dict[str, str] | None = None
    orchestration_plan: _BuildOrchestrationPlan | None = None
    logs: BuildLogInfo | None = None
    deleted: bool = False
    queue_position: int | None = None
    retained_by_release: bool = False


class _BuildDetailsResults(AdoBaseModel):
    """Internal: container for build list results."""

    value: list[BuildDetails]


class BuildQueueRequest(AdoBaseModel):
    """Request body for queueing a new build run.

    ADO requires ``parameters`` to be serialised as a JSON string rather than
    an object, which is handled automatically by the field serializer.
    ADO requires ``definition`` to be a nested object; ``definition_id`` is
    serialised automatically as ``{"definition": {"id": ...}}``.
    """

    definition_id: PipelineDefinitionId = Field(serialization_alias="definition")
    source_branch: str | None = None
    source_version: str | None = None
    parameters: dict[str, str] | None = None

    @field_serializer("definition_id")
    @staticmethod
    def _serialize_definition(value: PipelineDefinitionId) -> dict[str, int]:
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


class PipelineDefinitionInfo(AdoBaseModel):
    """Type to store pipeline definition details."""

    id: PipelineDefinitionId
    name: str
    path: str
    queue_status: str
    revision: int
    url: AdoUrl | None = None
    uri: str | None = None
    type: str | None = None
    quality: str | None = None
    created_date: datetime | None = None
    authored_by: _IdentityRef | None = None
    project: ProjectInfo | None = None
    queue: dict[str, object] | None = None
    drafts: list[dict[str, object]] = Field(default_factory=list)


class _PipelineDefinitionResults(AdoBaseModel):
    """Internal: container for pipeline definition list results."""

    value: list[PipelineDefinitionInfo]


class BuildSearchCriteria(AdoBaseModel):
    """Search criteria for listing build runs.

    All fields are optional; only non-None values are forwarded as query
    parameters to the builds list endpoint.

    Attributes:
        definition_id: Filter to a specific pipeline definition ID.
        status_filter: Filter by build status.
        branch_name: Filter by source branch ref name.
        top: Maximum number of results to return.
    """

    definition_id: PipelineDefinitionId | None = Field(
        default=None, serialization_alias="definitions"
    )
    status_filter: BuildStatus | None = None
    branch_name: str | None = None
    top: int | None = Field(default=None, serialization_alias="$top")


class _BuildStatusRequest(AdoBaseModel):
    """Internal: request body for updating a build status."""

    status: BuildStatus


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

    Note:
        Issues a single HTTP request — the ADO artifacts endpoint returns all
        artifacts in one response and does not support pagination parameters.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        BuildArtifact for each artifact attached to the build.
    """
    response = build_api_call.get("artifacts", version="7.1")
    yield from _BuildArtifactResults.model_validate(response).value


def iter_build_tags(build_api_call: ApiCall) -> Iterator[str]:
    """Iterate over tags attached to a build.

    Note:
        Issues a single HTTP request — the ADO tags endpoint returns all tags
        in one response and does not support pagination parameters.

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

    Note:
        Returns the updated tag list (not ``None``) — this is intentional ADO
        behaviour.  The DELETE endpoint always returns the full list of
        remaining tags after the operation.

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

    Note:
        Issues a single HTTP request — the ADO timeline endpoint returns a
        single ``Timeline`` object containing all records at once and does not
        support pagination parameters.

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


def get_build_details(
    build_api_call: ApiCall,
    *,
    expand: BuildExpand | None = None,
) -> BuildDetails:
    """Return the top-level details of a build run.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).
        expand: Optional ``$expand`` value to request additional fields.

    Returns:
        BuildDetails for the build.
    """
    response = build_api_call.get(
        parameters={"$expand": expand} if expand is not None else None,
        version="7.1",
    )
    return BuildDetails.model_validate(response)


def get_build_log(build_api_call: ApiCall, log_id: BuildLogId) -> str:
    """Return the plain-text content of a build log.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).
        log_id: Numeric log ID from a :class:`BuildLogInfo` record.

    Returns:
        Log content as a decoded UTF-8 string.
    """
    raw_bytes: bytes = build_api_call.get_raw("logs", log_id, version="7.1")
    return raw_bytes.decode("utf-8")


def get_build_artifact_bytes(
    build_api_call: ApiCall,
    artifact: BuildArtifact,
) -> bytes | None:
    """Download the bytes of a build artifact.

    Uses the ``downloadUrl`` from ``artifact.resource``.  Returns ``None``
    when the artifact has no download URL (e.g. pipeline artifacts that
    require a separate API call to locate).

    Args:
        build_api_call: Build-level API call (for auth and timeout).
        artifact: BuildArtifact whose bytes to download.

    Returns:
        Raw artifact bytes, or ``None`` if no download URL is available.

    Raises:
        RuntimeError: If the HTTP response indicates an error.
    """
    download_url = artifact.resource.download_url
    if download_url is None:
        return None
    session = build_api_call.session
    response = session.get(str(download_url), timeout=build_api_call.timeout)
    try:
        response.raise_for_status()
    except Exception as ex:
        with suppress(Exception):
            raise RuntimeError(response.json()["message"]) from ex
        raise RuntimeError(repr(response.content)) from ex
    return response.content


class _BuildLogResults(AdoBaseModel):
    """Internal: container for build log list results."""

    value: list[BuildLogInfo]


def iter_build_logs(build_api_call: ApiCall) -> Iterator[BuildLogInfo]:
    """Iterate over all log entries for a build.

    Calls ``GET build/builds/{id}/logs``, which returns metadata for every
    log container associated with the build.

    Args:
        build_api_call: Build-level ADO API call (from get_build_api_call).

    Yields:
        BuildLogInfo for each log entry, in ADO-returned order.
    """
    response = build_api_call.get("logs", version="7.1")
    yield from _BuildLogResults.model_validate(response).value


def iter_builds(
    project_api_call: ApiCall,
    *,
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


def list_build_work_item_ids(build_api_call: ApiCall) -> list[WorkItemRef]:
    """Return all work item IDs for a build as a list."""
    return list(iter_build_work_item_ids(build_api_call))


def list_work_items_between_builds(
    project_api_call: ApiCall,
    from_build_id: BuildId,
    to_build_id: BuildId,
    top: int | None = None,
) -> list[WorkItemRef]:
    """Return all work items between two builds as a list."""
    return list(
        iter_work_items_between_builds(
            project_api_call, from_build_id, to_build_id, top=top
        )
    )


def list_build_artifacts(build_api_call: ApiCall) -> list[BuildArtifact]:
    """Return all artifacts for a build as a list."""
    return list(iter_build_artifacts(build_api_call))


def list_build_tags(build_api_call: ApiCall) -> list[str]:
    """Return all tags for a build as a list."""
    return list(iter_build_tags(build_api_call))


def list_timeline_records(build_api_call: ApiCall) -> list[BuildRecordInfo]:
    """Return all timeline records for a build as a list."""
    return list(iter_timeline_records(build_api_call))


def list_build_logs(build_api_call: ApiCall) -> list[BuildLogInfo]:
    """Return all log entries for a build as a list."""
    return list(iter_build_logs(build_api_call))


def list_builds(
    project_api_call: ApiCall,
    search_criteria: BuildSearchCriteria | None = None,
) -> list[BuildDetails]:
    """Return all builds matching the given criteria as a list."""
    return list(iter_builds(project_api_call, search_criteria=search_criteria))


def list_pipeline_definitions(
    project_api_call: ApiCall,
    name_filter: str | None = None,
) -> list[PipelineDefinitionInfo]:
    """Return all pipeline definitions as a list."""
    return list(iter_pipeline_definitions(project_api_call, name_filter=name_filter))
