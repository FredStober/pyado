"""Module to interact with Azure DevOps builds."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json as jsonlib
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.api_call import ADOUrl, ApiCall
from pyado.work_item import WorkItemId

BuildId: TypeAlias = int
TimelineId: TypeAlias = UUID
TaskId: TypeAlias = UUID
QueueId: TypeAlias = int
BuildLogId: TypeAlias = int
BuildStatus: TypeAlias = Literal[
    "all",
    "cancelling",
    "completed",
    "inProgress",
    "none",
    "notStarted",
    "postponed",
]
BuildResult: TypeAlias = Literal[
    "canceled",
    "failed",
    "none",
    "partiallySucceeded",
    "succeeded",
]
BuildRecordType: TypeAlias = Literal[
    "Checkpoint",
    "Checkpoint.Approval",
    "Checkpoint.Authorization",
    "Checkpoint.ExtendsCheck",
    "Phase",
    "Stage",
    "Job",
    "Task",
]


def get_build_api_call(project_api_call: ApiCall, build_id: BuildId) -> ApiCall:
    """Get build API call.

    Returns:
        An ApiCall pointing at the build resource for the given build ID.
    """
    return project_api_call.build_call(
        "build",
        "builds",
        build_id,
    )


def iter_build_work_item_ids(build_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Get work items linked to the build pipeline.

    Yields:
        Integer work item IDs associated with the build.
    """
    page_size = 100
    skip = 0
    while True:
        response = build_api_call.get(
            "workitems",
            parameters={"$top": page_size, "$skip": skip},
            version="7.0",
        )
        items = response["value"]
        for entry in items:
            yield int(entry["id"])
        if len(items) < page_size:
            break
        skip += len(items)


class BuildLogInfo(BaseModel, extra="forbid"):
    """Type to store build log details."""

    id: BuildLogId
    log_type: Literal["Container"] = Field(alias="type")
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
    data: dict[str, str] | None = {}
    message: str
    type: Literal["error", "warning"]


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
    result: Literal["failed", "succeeded", "skipped", "canceled"] | None
    result_code: str | None = Field(alias="resultCode")
    start_time: datetime | None = Field(alias="startTime")
    state: Literal["completed", "pending", "inProgress"]
    task: BuildRecordTypeInfo | None
    type_name: BuildRecordType = Field(alias="type")
    url: AnyUrl | None
    warning_count: int | None = Field(default=None, alias="warningCount")
    worker_name: str | None = Field(alias="workerName")


class _BuildRecordInfoResults(BaseModel):
    """Type to read build record details results."""

    records: list[BuildRecordInfo]
    id: TimelineId


def iter_timeline_records(build_api_call: ApiCall) -> Iterator[BuildRecordInfo]:
    """Iterate over task in the timeline.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/build/7.1/build.json#L2478

    Yields:
        BuildRecordInfo objects for each record in the timeline.
    """
    response = build_api_call.get(
        "timeline",
        version="7.1",
    )
    results = _BuildRecordInfoResults.model_validate(response)
    yield from results.records


class _BuildDefinitionRef(BaseModel):
    """Internal: minimal pipeline definition reference inside a build record."""

    id: int
    name: str


class _BuildIdentityRef(BaseModel):
    """Internal: identity reference inside a build record."""

    display_name: str = Field(alias="displayName")
    id: str


class BuildDetails(BaseModel):
    """Type to store top-level build (pipeline run) details."""

    id: BuildId
    build_number: str = Field(alias="buildNumber")
    status: BuildStatus
    result: BuildResult | None = None
    queue_time: datetime | None = Field(alias="queueTime", default=None)
    start_time: datetime | None = Field(alias="startTime", default=None)
    finish_time: datetime | None = Field(alias="finishTime", default=None)
    source_branch: str = Field(alias="sourceBranch")
    source_version: str = Field(alias="sourceVersion")
    definition: _BuildDefinitionRef
    requested_by: _BuildIdentityRef = Field(alias="requestedBy")


class _BuildDetailsResults(BaseModel):
    """Internal: container for build list results."""

    value: list[BuildDetails]


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
    *,
    definition_id: int | None = None,
    status_filter: BuildStatus | None = None,
    branch_name: str | None = None,
    top: int | None = None,
) -> Iterator[BuildDetails]:
    """Iterate over build runs in the project.

    Args:
        project_api_call: Project-level ADO API call.
        definition_id: Filter to a specific pipeline definition ID.
        status_filter: Filter by build status (e.g. ``"inProgress"``).
        branch_name: Filter by source branch (e.g. ``"refs/heads/main"``).
        top: Maximum number of results to return (server default applies when
            omitted).

    Yields:
        BuildDetails for each matching build run.
    """
    parameters: dict[str, int | str | bool] = {}
    if definition_id is not None:
        parameters["definitions"] = definition_id
    if status_filter is not None:
        parameters["statusFilter"] = status_filter
    if branch_name is not None:
        parameters["branchName"] = branch_name
    if top is not None:
        parameters["$top"] = top
    response = project_api_call.get(
        "build",
        "builds",
        parameters=parameters,
        version="7.1",
    )
    yield from _BuildDetailsResults.model_validate(response).value


def queue_build(
    project_api_call: ApiCall,
    definition_id: int,
    *,
    source_branch: str | None = None,
    source_version: str | None = None,
    parameters: dict[str, str] | None = None,
) -> BuildDetails:
    """Queue a new build run for a pipeline definition.

    Args:
        project_api_call: Project-level ADO API call.
        definition_id: ID of the pipeline definition to run.
        source_branch: Source branch to build (e.g. ``"refs/heads/main"``).
            Uses the definition default when omitted.
        source_version: Commit SHA to build.  Uses the branch HEAD when omitted.
        parameters: Optional key/value pairs passed to the pipeline as
            template parameters (serialised as a JSON string by ADO).

    Returns:
        BuildDetails for the queued build run.
    """
    body: dict[str, Any] = {"definition": {"id": definition_id}}
    if source_branch is not None:
        body["sourceBranch"] = source_branch
    if source_version is not None:
        body["sourceVersion"] = source_version
    if parameters is not None:
        body["parameters"] = jsonlib.dumps(parameters)
    response = project_api_call.post(
        "build",
        "builds",
        version="7.1",
        json=body,
    )
    return BuildDetails.model_validate(response)


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
    parameters: dict[str, int | str | bool] = {}
    if name_filter is not None:
        parameters["name"] = name_filter
    response = project_api_call.get(
        "build",
        "definitions",
        parameters=parameters,
        version="7.1",
    )
    yield from _PipelineDefinitionResults.model_validate(response).value
