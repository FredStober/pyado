"""Module to interact with Azure DevOps work items."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.api_call import ApiCall, JsonPatchAdd

SprintIterationId: TypeAlias = UUID
SprintIterationPath: TypeAlias = str
WorkItemField: TypeAlias = str
WorkItemId: TypeAlias = int
WorkItemRelationType: TypeAlias = str


class WorkItemRelation(BaseModel):
    """Type to store work item relationships."""

    rel: WorkItemRelationType
    url: AnyUrl
    attributes: dict[str, Any] | None = None


class WorkItemInfo(BaseModel):
    """Type to store work item details."""

    id: WorkItemId
    fields: dict[WorkItemField, Any]
    relations: list[WorkItemRelation] = []


class _WorkItemInfoResults(BaseModel):
    """Type to read work item detail results."""

    value: list[WorkItemInfo]


_WORK_ITEM_BATCH_SIZE = 200


def iter_work_item_details(
    project_api_call: ApiCall,
    work_item_id_list: list[WorkItemId],
    work_item_field_list: list[WorkItemField] | None = None,
) -> Iterator[WorkItemInfo]:
    """Iterate over the work items.

    Batches requests in chunks of 200 (the ADO API limit per call).

    Yields:
        WorkItemInfo objects for each work item in the results.
    """
    for batch_start in range(0, len(work_item_id_list), _WORK_ITEM_BATCH_SIZE):
        batch = work_item_id_list[batch_start : batch_start + _WORK_ITEM_BATCH_SIZE]
        request_json: dict[str, Any] = {"ids": batch}
        if work_item_field_list:
            request_json["fields"] = work_item_field_list
        else:
            request_json["$expand"] = "relations"
        response = project_api_call.post(
            "wit",
            "workitemsbatch",
            version="7.1-preview.1",
            json=request_json,
        )
        yield from _WorkItemInfoResults.model_validate(response).value


def create_work_item(
    project_api_call: ApiCall,
    fields: dict[WorkItemField, Any],
    relations: list[WorkItemRelation] | None = None,
) -> WorkItemInfo:
    """Create work items.

    Returns:
        The created WorkItemInfo parsed from the API response.

    Raises:
        RuntimeError: If System.WorkItemType is not provided in fields.
    """
    ticket_type: str | None = fields.get("System.WorkItemType")
    if ticket_type is None:
        err_msg = f"Work item type must be specified! {fields!r}"
        raise RuntimeError(err_msg)
    json_patch_list = [
        JsonPatchAdd(path=f"/fields/{key}", value=value)
        for key, value in fields.items()
        if key != "System.WorkItemType"
    ]
    for link in relations or []:
        link_dict = link.model_dump(mode="json", exclude_defaults=True)
        json_patch_add = JsonPatchAdd(path="/relations/-", value=link_dict)
        json_patch_list.append(json_patch_add)

    response = project_api_call.post(
        "wit",
        "workitems",
        f"${ticket_type}",
        version="7.1",
        json=[json_patch.model_dump(mode="json") for json_patch in json_patch_list],
    )
    return WorkItemInfo.model_validate(response)


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


def iter_sprint_iterations(
    team_api_call: ApiCall,
    timeframe_filter: str | None = None,
) -> Iterator[SprintIterationInfo]:
    """Iterate over the sprint iterations.

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


class WiqlWorkItemRef(BaseModel):
    """A work item reference returned by a WIQL query."""

    id: WorkItemId
    url: AnyUrl


class _WiqlResults(BaseModel):
    """Internal: container for WIQL query results."""

    work_items: list[WiqlWorkItemRef] = Field(alias="workItems")


def run_wiql(
    project_api_call: ApiCall,
    query: str,
) -> list[WiqlWorkItemRef]:
    """Execute a WIQL query and return work item references.

    Args:
        project_api_call: Project-level ADO API call.
        query: WIQL query string.

    Returns:
        List of WiqlWorkItemRef objects.
    """
    response = project_api_call.post(
        "wit",
        "wiql",
        version="7.0",
        json={"query": query},
    )
    return _WiqlResults.model_validate(response).work_items


def get_work_item_api_call(
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
) -> ApiCall:
    """Get work item API call.

    Returns:
        An ApiCall pointing at the work item resource for the given ID.
    """
    return project_api_call.build_call("wit", "workitems", work_item_id)


def update_work_item(
    work_item_api_call: ApiCall,
    fields: dict[WorkItemField, Any],
    *,
    multiline_fields_format: dict[WorkItemField, str] | None = None,
) -> WorkItemInfo:
    """Update work item fields via JSON patch.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        fields: Mapping of field reference names to new values.
        multiline_fields_format: Optional mapping of multiline field
            reference names to their format — "html" or "markdown".
            When a field is set to "markdown", ADO renders its content
            as markdown in the UI. Must be accompanied by a matching
            entry in fields (ADO rejects a format-only patch).

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    json_patch_list: list[dict[str, Any]] = [
        JsonPatchAdd(path=f"/fields/{key}", value=value).model_dump(mode="json")
        for key, value in fields.items()
    ]
    for field_name, fmt in (multiline_fields_format or {}).items():
        json_patch_list.append(
            {"op": "add", "path": f"/multilineFieldsFormat/{field_name}", "value": fmt}
        )
    response = work_item_api_call.patch(
        version="7.1",
        json=json_patch_list,
    )
    return WorkItemInfo.model_validate(response)


class WorkItemComment(BaseModel):
    """A single comment on a work item."""

    id: int
    text: str
    created_date: datetime = Field(alias="createdDate")
    modified_date: datetime = Field(alias="modifiedDate")


class _WorkItemCommentResults(BaseModel):
    """Internal: container for work item comment results."""

    comments: list[WorkItemComment]
    continuation_token: str | None = Field(alias="continuationToken", default=None)


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


class WorkItemAttachmentRef(BaseModel):
    """A reference to a file attachment uploaded to ADO."""

    id: str
    url: AnyUrl


def add_work_item_attachment(
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
    filename: str,
    content: bytes,
) -> WorkItemAttachmentRef:
    """Upload a file and attach it to a work item.

    This is a two-step operation: the file is uploaded first, then a relation
    of type ``AttachedFile`` is added to the work item.

    Args:
        project_api_call: Project-level ADO API call.
        work_item_id: ID of the work item to attach the file to.
        filename: Name of the file as it will appear in ADO.
        content: Raw bytes of the file to upload.

    Returns:
        WorkItemAttachmentRef with the ID and URL of the uploaded attachment.
    """
    upload_response = project_api_call.post(
        "wit",
        "attachments",
        parameters={"fileName": filename},
        version="7.1",
        data=content,
    )
    attachment_ref = WorkItemAttachmentRef.model_validate(upload_response)
    project_api_call.patch(
        "wit",
        "workitems",
        work_item_id,
        version="7.1",
        json=[
            JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": "AttachedFile",
                    "url": str(attachment_ref.url),
                    "attributes": {"comment": filename},
                },
            ).model_dump(mode="json")
        ],
    )
    return attachment_ref


def add_work_item_comment(
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
        json={"text": text},
    )
    return WorkItemComment.model_validate(response)
