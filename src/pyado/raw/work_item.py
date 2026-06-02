"""Azure DevOps work item, WIQL, sprint, and attachment API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.raw._core import ApiCall, _IdentityRef

__all__ = [
    "SprintIterationAttributes",
    "SprintIterationId",
    "SprintIterationInfo",
    "SprintIterationPath",
    "WorkItemAttachmentRef",
    "WorkItemComment",
    "WorkItemField",
    "WorkItemId",
    "WorkItemInfo",
    "WorkItemRef",
    "WorkItemRelation",
    "WorkItemRelationType",
    "WorkItemsBatchRequest",
    "get_work_item",
    "get_work_item_api_call",
    "iter_sprint_iterations",
    "iter_work_item_comments",
    "patch_work_item",
    "post_wiql",
    "post_work_item",
    "post_work_item_attachment_upload",
    "post_work_item_comment",
    "post_work_items_batch",
]

SprintIterationId = UUID
SprintIterationPath = str
WorkItemField = str
WorkItemId = int
WorkItemRelationType = str


class WorkItemRelation(BaseModel):
    """Type to store work item relationships."""

    rel: WorkItemRelationType
    url: AnyUrl
    attributes: dict[str, Any] | None = None


class WorkItemInfo(BaseModel):
    """Type to store work item details."""

    id: WorkItemId
    rev: int | None = None
    url: AnyUrl | None = None
    fields: dict[WorkItemField, Any]
    relations: list[WorkItemRelation] = []


class _WorkItemInfoResults(BaseModel):
    """Internal: container for work item detail results."""

    value: list[WorkItemInfo]


class SprintIterationAttributes(BaseModel):
    """Type to store sprint attribute information."""

    start_date: datetime | None = Field(alias="startDate", default=None)
    finish_date: datetime | None = Field(alias="finishDate", default=None)
    timeframe: str = Field(alias="timeFrame")


class SprintIterationInfo(BaseModel):
    """Type to store sprint information."""

    id: SprintIterationId
    name: str
    path: SprintIterationPath
    attributes: SprintIterationAttributes


class _SprintIterationInfoResults(BaseModel):
    count: int
    value: list[SprintIterationInfo]


class WorkItemRef(BaseModel):
    """A work item reference as returned by build and PR workitems endpoints."""

    id: WorkItemId
    url: AnyUrl | None = None


class _WorkItemRefResults(BaseModel):
    """Internal: container for work item ref list results."""

    value: list[WorkItemRef]


class _WiqlResults(BaseModel):
    """Internal: container for WIQL query results."""

    work_items: list[WorkItemRef] = Field(alias="workItems")


class _WiqlRequest(BaseModel):
    """Internal: request body for a WIQL query."""

    query: str


class WorkItemComment(BaseModel):
    """A single comment on a work item."""

    id: int
    text: str
    created_by: _IdentityRef | None = Field(alias="createdBy", default=None)
    modified_by: _IdentityRef | None = Field(alias="modifiedBy", default=None)
    created_date: datetime = Field(alias="createdDate")
    modified_date: datetime = Field(alias="modifiedDate")
    is_deleted: bool = Field(alias="isDeleted", default=False)
    format: str | None = None


class _WorkItemCommentResults(BaseModel):
    """Internal: container for work item comment results."""

    comments: list[WorkItemComment]
    continuation_token: str | None = Field(alias="continuationToken", default=None)


class WorkItemAttachmentRef(BaseModel):
    """A reference to a file attachment uploaded to ADO."""

    id: str
    url: AnyUrl


class WorkItemsBatchRequest(BaseModel):
    """Request body for fetching a batch of work items.

    The ADO API accepts at most 200 IDs per call.
    """

    ids: list[WorkItemId]
    fields: list[WorkItemField] | None = None
    expand: Literal["relations"] | None = Field(
        default=None, serialization_alias="$expand"
    )


class _WorkItemCommentRequest(BaseModel):
    """Internal: request body for adding a work item comment."""

    text: str


def iter_sprint_iterations(
    team_api_call: ApiCall,
    timeframe_filter: str | None = None,
) -> Iterator[SprintIterationInfo]:
    """Iterate over the sprint iterations for a team.

    Args:
        team_api_call: Team-level ADO API call (URL includes the team segment).
        timeframe_filter: When provided, filters by timeframe (e.g.
            ``"current"``).

    Yields:
        SprintIterationInfo objects for each iteration.
    """
    parameters: dict[str, int | str] = {}
    if timeframe_filter:
        parameters["$timeframe"] = timeframe_filter
    response = team_api_call.get(
        "work",
        "teamsettings",
        "iterations",
        version="7.1",
        parameters=parameters,
    )
    results = _SprintIterationInfoResults.model_validate(response)
    yield from results.value


def post_wiql(
    project_api_call: ApiCall,
    query: str,
) -> list[WorkItemRef]:
    """Execute a WIQL query and return work item references.

    Args:
        project_api_call: Project-level ADO API call.
        query: WIQL query string.

    Returns:
        List of WorkItemRef objects.
    """
    response = project_api_call.post(
        "wit",
        "wiql",
        version="7.0",
        json=_WiqlRequest(query=query).model_dump(mode="json"),
    )
    return _WiqlResults.model_validate(response).work_items


def get_work_item_api_call(
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
) -> ApiCall:
    """Get the API call for a specific work item.

    Args:
        project_api_call: Project-level ADO API call.
        work_item_id: Numeric ID of the work item.

    Returns:
        An ApiCall pointing at the work item resource for the given ID.
    """
    return project_api_call.build_call("wit", "workitems", work_item_id)


def iter_work_item_comments(
    work_item_api_call: ApiCall,
) -> Iterator[WorkItemComment]:
    """Iterate over comments on a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).

    Yields:
        WorkItemComment objects for each comment.
    """
    parameters: dict[str, int | str | bool] = {}
    while True:
        response = work_item_api_call.get(
            "comments",
            parameters=parameters,
            version="7.0-preview.3",
        )
        results = _WorkItemCommentResults.model_validate(response)
        yield from results.comments
        if not results.continuation_token:
            break
        parameters["continuationToken"] = results.continuation_token


def get_work_item(
    work_item_api_call: ApiCall,
    *,
    expand_relations: bool = False,
) -> WorkItemInfo:
    """Fetch a single work item by ID.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        expand_relations: When True, related work item links are included in
            the response.

    Returns:
        WorkItemInfo for the work item.
    """
    parameters: dict[str, int | str | bool] = {}
    if expand_relations:
        parameters["$expand"] = "relations"
    response = work_item_api_call.get(
        parameters=parameters,
        version="7.1",
    )
    return WorkItemInfo.model_validate(response)


def post_work_items_batch(
    project_api_call: ApiCall,
    request: WorkItemsBatchRequest,
) -> list[WorkItemInfo]:
    """Fetch a batch of work items.

    Args:
        project_api_call: Project-level ADO API call.
        request: Batch request specifying IDs and optional field or expand
            settings.

    Returns:
        List of WorkItemInfo objects.
    """
    response = project_api_call.post(
        "wit",
        "workitemsbatch",
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return _WorkItemInfoResults.model_validate(response).value


def post_work_item(
    project_api_call: ApiCall,
    ticket_type: str,
    json_patches: list[dict[str, Any]],
) -> WorkItemInfo:
    """Create a new work item of the given type.

    Args:
        project_api_call: Project-level ADO API call.
        ticket_type: Work item type name (e.g. ``"Task"``, ``"Bug"``).
        json_patches: JSON Patch operations list describing the fields and
            relations for the new work item.

    Returns:
        The created WorkItemInfo.
    """
    response = project_api_call.post(
        "wit",
        "workitems",
        f"${ticket_type}",
        version="7.1",
        json=json_patches,
    )
    return WorkItemInfo.model_validate(response)


def patch_work_item(
    work_item_api_call: ApiCall,
    json_patches: list[dict[str, Any]],
) -> WorkItemInfo:
    """Update a work item via JSON Patch operations.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        json_patches: JSON Patch operations list describing the fields to
            update.

    Returns:
        Updated WorkItemInfo.
    """
    response = work_item_api_call.patch(version="7.1", json=json_patches)
    return WorkItemInfo.model_validate(response)


def post_work_item_attachment_upload(
    project_api_call: ApiCall,
    filename: str,
    content: bytes,
) -> WorkItemAttachmentRef:
    """Upload a file as a work item attachment.

    Args:
        project_api_call: Project-level ADO API call.
        filename: Name of the file as it will appear in ADO.
        content: Raw bytes of the file to upload.

    Returns:
        WorkItemAttachmentRef with the ID and URL of the uploaded attachment.
    """
    response = project_api_call.post(
        "wit",
        "attachments",
        parameters={"fileName": filename},
        version="7.1",
        data=content,
    )
    return WorkItemAttachmentRef.model_validate(response)


def post_work_item_comment(
    work_item_api_call: ApiCall,
    text: str,
    *,
    comment_format: str = "html",
) -> WorkItemComment:
    """Add a comment to a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        text: Comment text.
        comment_format: Content format — "html" (default) or "markdown". When
            "markdown", ADO renders the markdown server-side.

    Returns:
        The created WorkItemComment.
    """
    response = work_item_api_call.post(
        "comments",
        parameters={"format": comment_format},
        version="7.1-preview.4",
        json=_WorkItemCommentRequest(text=text).model_dump(mode="json"),
    )
    return WorkItemComment.model_validate(response)
