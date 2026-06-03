"""Azure DevOps work item, WIQL, sprint, and attachment API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import date, datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.raw._core import ApiCall, _IdentityRef

__all__ = [
    "ClassificationNode",
    "ClassificationNodeAttributes",
    "SprintIterationAttributes",
    "SprintIterationId",
    "SprintIterationInfo",
    "SprintIterationPath",
    "SprintIterationTimeframe",
    "TeamFieldValue",
    "WorkItemArtifactUrlPrefix",
    "WorkItemAttachmentRef",
    "WorkItemComment",
    "WorkItemExpand",
    "WorkItemField",
    "WorkItemFieldName",
    "WorkItemId",
    "WorkItemInfo",
    "WorkItemRef",
    "WorkItemRelation",
    "WorkItemRelationType",
    "WorkItemsBatchRequest",
    "add_team_iteration",
    "create_classification_node",
    "get_classification_node",
    "get_team_field_values",
    "get_work_item",
    "get_work_item_api_call",
    "iter_sprint_iterations",
    "iter_work_item_comments",
    "patch_classification_node",
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


class WorkItemFieldName(StrEnum):
    """Well-known ADO work item field reference names.

    Use these as keys when reading ``WorkItemInfo.fields`` or building
    ``fields`` dicts for ``create_work_item`` / ``update_work_item``.

    Example::

        title = wi.fields[WorkItemFieldName.TITLE]
        update_work_item(api, {WorkItemFieldName.STATE: "Active"})
    """

    # --- System fields ---
    ID = "System.Id"
    TITLE = "System.Title"
    DESCRIPTION = "System.Description"
    WORK_ITEM_TYPE = "System.WorkItemType"
    STATE = "System.State"
    REASON = "System.Reason"
    ASSIGNED_TO = "System.AssignedTo"
    CREATED_DATE = "System.CreatedDate"
    CREATED_BY = "System.CreatedBy"
    CHANGED_DATE = "System.ChangedDate"
    CHANGED_BY = "System.ChangedBy"
    COMMENT_COUNT = "System.CommentCount"
    TEAM_PROJECT = "System.TeamProject"
    AREA_PATH = "System.AreaPath"
    AREA_ID = "System.AreaId"
    ITERATION_PATH = "System.IterationPath"
    ITERATION_ID = "System.IterationId"
    REV = "System.Rev"
    HISTORY = "System.History"
    ATTACHED_FILE_COUNT = "System.AttachedFileCount"
    HYPERLINK_COUNT = "System.HyperLinkCount"
    EXTERNAL_LINK_COUNT = "System.ExternalLinkCount"
    RELATED_LINK_COUNT = "System.RelatedLinkCount"
    TAGS = "System.Tags"
    BOARD_COLUMN = "System.BoardColumn"
    BOARD_COLUMN_DONE = "System.BoardColumnDone"
    BOARD_LANE = "System.BoardLane"
    PARENT = "System.Parent"
    # --- Microsoft.VSTS.Common fields ---
    PRIORITY = "Microsoft.VSTS.Common.Priority"
    SEVERITY = "Microsoft.VSTS.Common.Severity"
    VALUE_AREA = "Microsoft.VSTS.Common.ValueArea"
    BUSINESS_VALUE = "Microsoft.VSTS.Common.BusinessValue"
    TIME_CRITICALITY = "Microsoft.VSTS.Common.TimeCriticality"
    RISK = "Microsoft.VSTS.Common.Risk"
    EFFORT = "Microsoft.VSTS.Common.Effort"
    ACTIVITY = "Microsoft.VSTS.Common.Activity"
    STACK_RANK = "Microsoft.VSTS.Common.StackRank"
    BACKLOG_PRIORITY = "Microsoft.VSTS.Common.BacklogPriority"
    CLOSED_DATE = "Microsoft.VSTS.Common.ClosedDate"
    CLOSED_BY = "Microsoft.VSTS.Common.ClosedBy"
    RESOLVED_DATE = "Microsoft.VSTS.Common.ResolvedDate"
    RESOLVED_BY = "Microsoft.VSTS.Common.ResolvedBy"
    RESOLVED_REASON = "Microsoft.VSTS.Common.ResolvedReason"
    ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"
    STATE_CHANGE_DATE = "Microsoft.VSTS.Common.StateChangeDate"
    # --- Microsoft.VSTS.Scheduling fields ---
    REMAINING_WORK = "Microsoft.VSTS.Scheduling.RemainingWork"
    COMPLETED_WORK = "Microsoft.VSTS.Scheduling.CompletedWork"
    ORIGINAL_ESTIMATE = "Microsoft.VSTS.Scheduling.OriginalEstimate"
    STORY_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
    START_DATE = "Microsoft.VSTS.Scheduling.StartDate"
    FINISH_DATE = "Microsoft.VSTS.Scheduling.FinishDate"
    TARGET_DATE = "Microsoft.VSTS.Scheduling.TargetDate"
    # --- Microsoft.VSTS.Build fields ---
    INTEGRATION_BUILD = "Microsoft.VSTS.Build.IntegrationBuild"
    FOUND_IN = "Microsoft.VSTS.Build.FoundIn"


class WorkItemRelationType(StrEnum):
    """Well-known work item relation type strings for WorkItemRelation.rel.

    External artifact links (pull requests, builds, commits) use ARTIFACT_LINK
    with a ``vstfs://`` URL built from WorkItemArtifactUrlPrefix.
    """

    # External artifact and attachment links
    ARTIFACT_LINK = "ArtifactLink"
    ATTACHED_FILE = "AttachedFile"
    HYPERLINK = "Hyperlink"
    # Work item link types (ADO built-ins)
    RELATED = "System.LinkTypes.Related"
    DUPLICATE = "System.LinkTypes.Duplicate-Forward"
    DUPLICATE_OF = "System.LinkTypes.Duplicate-Reverse"
    SUCCESSOR = "System.LinkTypes.Dependency-Forward"
    PREDECESSOR = "System.LinkTypes.Dependency-Reverse"
    CHILD = "System.LinkTypes.Hierarchy-Forward"
    PARENT = "System.LinkTypes.Hierarchy-Reverse"
    # VSTS / Azure Boards process template link types
    TESTED_BY = "Microsoft.VSTS.Common.TestedBy-Forward"
    TESTS = "Microsoft.VSTS.Common.TestedBy-Reverse"
    TEST_CASE = "Microsoft.VSTS.TestCase.SharedParameterReferencedBy-Forward"
    SHARED_PARAMETER_REFERENCED_BY = (
        "Microsoft.VSTS.TestCase.SharedParameterReferencedBy-Reverse"
    )
    AFFECTS = "Microsoft.VSTS.Common.Affects-Forward"
    AFFECTED_BY = "Microsoft.VSTS.Common.Affects-Reverse"


class WorkItemArtifactUrlPrefix(StrEnum):
    """vstfs:/// URL prefixes for work item artifact links.

    Append ``/{artifact_id}`` to form a complete artifact URL:
    ``f"{WorkItemArtifactUrlPrefix.BUILD}/{build_id}"``.
    """

    BUILD = "vstfs:///Build/Build"
    COMMIT = "vstfs:///Git/Commit"
    PULL_REQUEST = "vstfs:///Git/PullRequestId"


class WorkItemRelation(BaseModel):
    """Type to store work item relationships."""

    rel: str
    url: str
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


class SprintIterationTimeframe(StrEnum):
    """Relative timeframe values for filtering sprint iterations.

    Only ``CURRENT`` is currently supported as a filter value by ADO.
    All three values appear in the ``timeFrame`` field of
    ``SprintIterationAttributes``.
    """

    PAST = "past"
    CURRENT = "current"
    FUTURE = "future"


class SprintIterationAttributes(BaseModel):
    """Type to store sprint attribute information."""

    start_date: datetime | None = Field(alias="startDate", default=None)
    finish_date: datetime | None = Field(alias="finishDate", default=None)
    timeframe: SprintIterationTimeframe = Field(alias="timeFrame")


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


class WorkItemExpand(StrEnum):
    """Expand options for work item fetch requests."""

    NONE = "none"
    RELATIONS = "relations"
    FIELDS = "fields"
    LINKS = "links"
    ALL = "all"


class WorkItemsBatchRequest(BaseModel):
    """Request body for fetching a batch of work items.

    The ADO API accepts at most 200 IDs per call.
    """

    ids: list[WorkItemId]
    fields: list[WorkItemField] | None = None
    expand: WorkItemExpand | None = Field(default=None, serialization_alias="$expand")


class ClassificationNodeAttributes(BaseModel):
    """Date attributes of a classification node (sprint iteration)."""

    start_date: str | None = Field(alias="startDate", default=None)
    finish_date: str | None = Field(alias="finishDate", default=None)


class ClassificationNode(BaseModel):
    """A classification node (iteration or area) as returned by the ADO API."""

    id: int
    identifier: str | None = None
    name: str
    path: str | None = None
    structure_type: str | None = Field(alias="structureType", default=None)
    has_children: bool | None = Field(alias="hasChildren", default=None)
    attributes: ClassificationNodeAttributes | None = None
    children: list["ClassificationNode"] | None = None
    url: AnyUrl | None = None


ClassificationNode.model_rebuild()


class TeamFieldValue(BaseModel):
    """A single team area-path field value."""

    value: str
    include_children: bool = Field(alias="includeChildren")


class _WorkItemCommentRequest(BaseModel):
    """Internal: request body for adding a work item comment."""

    text: str


class _ClassificationNodeAttributes(BaseModel):
    """Internal: date attributes for a classification node request."""

    start_date: str | None = Field(default=None, serialization_alias="startDate")
    finish_date: str | None = Field(default=None, serialization_alias="finishDate")


class _ClassificationNodeRequest(BaseModel):
    """Internal: request body for creating a classification node."""

    name: str
    attributes: _ClassificationNodeAttributes | None = None


class _ClassificationNodePatchRequest(BaseModel):
    """Internal: request body for patching a classification node."""

    attributes: _ClassificationNodeAttributes


class _TeamIterationRef(BaseModel):
    """Internal: request body for assigning an iteration to a team."""

    id: str


def iter_sprint_iterations(
    team_api_call: ApiCall,
    timeframe_filter: SprintIterationTimeframe | None = None,
) -> Iterator[SprintIterationInfo]:
    """Iterate over the sprint iterations for a team.

    Args:
        team_api_call: Team-level ADO API call (URL includes the team segment).
        timeframe_filter: When provided, filters by timeframe. Only
            ``SprintIterationTimeframe.CURRENT`` is supported by ADO.

    Yields:
        SprintIterationInfo objects for each iteration.
    """
    response = team_api_call.get(
        "work",
        "teamsettings",
        "iterations",
        version="7.1",
        parameters=({"$timeframe": timeframe_filter} if timeframe_filter else None),
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
    continuation_token: str | None = None
    while True:
        response = work_item_api_call.get(
            "comments",
            parameters=(
                {"continuationToken": continuation_token}
                if continuation_token
                else None
            ),
            version="7.0-preview.3",
        )
        results = _WorkItemCommentResults.model_validate(response)
        yield from results.comments
        continuation_token = results.continuation_token
        if not continuation_token:
            break


def get_work_item(
    work_item_api_call: ApiCall,
    *,
    expand: WorkItemExpand | None = None,
) -> WorkItemInfo:
    """Fetch a single work item by ID.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        expand: Optional expand mode; controls which extra data ADO includes
            in the response (e.g. ``WorkItemExpand.RELATIONS`` to include
            related work item links, ``WorkItemExpand.ALL`` for everything).

    Returns:
        WorkItemInfo for the work item.
    """
    response = work_item_api_call.get(
        parameters={"$expand": expand} if expand is not None else None,
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


def get_classification_node(
    project_call: ApiCall,
    path: str | None = None,
    *,
    depth: int = 1,
) -> ClassificationNode:
    """Return the classification node tree for a project's iterations.

    Args:
        project_call: Project-level ADO API call.
        path: Path within the iteration tree (e.g. ``"Sprint 42"``), or None
            for the root.
        depth: Number of levels to fetch below the requested node (default: 1).

    Returns:
        ClassificationNode for the requested path.
    """
    args: list[str] = ["wit", "classificationnodes", "iterations"]
    if path:
        args.append(path)
    response = project_call.get(*args, parameters={"$depth": depth}, version="7.0")
    return ClassificationNode.model_validate(response)


def create_classification_node(
    project_call: ApiCall,
    name: str,
    parent_path: str | None = None,
    *,
    start_date: date | None = None,
    finish_date: date | None = None,
) -> str:
    """Create a classification node (sprint iteration) under a parent path.

    Args:
        project_call: Project-level ADO API call.
        name: Name of the new iteration node.
        parent_path: Path of the parent node within the iteration tree, or
            None to create at the root.
        start_date: Optional start date for the iteration.
        finish_date: Optional end date for the iteration.

    Returns:
        The GUID identifier string of the created node.
    """
    args: list[str] = ["wit", "classificationnodes", "iterations"]
    if parent_path:
        args.append(parent_path)
    node_attrs = _ClassificationNodeAttributes(
        start_date=start_date.isoformat() + "T00:00:00Z" if start_date else None,
        finish_date=finish_date.isoformat() + "T00:00:00Z" if finish_date else None,
    )
    body = _ClassificationNodeRequest(
        name=name,
        attributes=node_attrs if (start_date or finish_date) else None,
    )
    response = project_call.post(
        *args,
        version="7.0",
        json=body.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return cast("str", response["identifier"])


def patch_classification_node(
    project_call: ApiCall,
    path: str,
    *,
    start_date: date | None = None,
    finish_date: date | None = None,
) -> ClassificationNode:
    """Update the dates of a classification node (sprint iteration).

    Args:
        project_call: Project-level ADO API call.
        path: Path of the iteration node to update (e.g. ``"Sprint 42"``).
        start_date: New start date, or None to leave unchanged.
        finish_date: New end date, or None to leave unchanged.

    Returns:
        Updated ClassificationNode from the ADO API.
    """
    patch = _ClassificationNodePatchRequest(
        attributes=_ClassificationNodeAttributes(
            start_date=start_date.isoformat() + "T00:00:00Z" if start_date else None,
            finish_date=finish_date.isoformat() + "T00:00:00Z" if finish_date else None,
        )
    )
    response = project_call.patch(
        "wit",
        "classificationnodes",
        "iterations",
        path,
        version="7.0",
        json=patch.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ClassificationNode.model_validate(response)


def get_team_field_values(team_call: ApiCall) -> list[TeamFieldValue]:
    """Return the team area-path field values configuration.

    Args:
        team_call: Team-level ADO API call (URL includes the team segment).

    Returns:
        List of TeamFieldValue from the ``values`` key of the API response.
    """
    response = team_call.get(
        "work",
        "teamsettings",
        "teamfieldvalues",
        version="7.0",
    )
    return [TeamFieldValue.model_validate(v) for v in response.get("values", [])]


def add_team_iteration(
    team_call: ApiCall,
    iteration_id: SprintIterationId,
) -> None:
    """Assign an existing iteration to a team.

    Args:
        team_call: Team-level ADO API call (URL includes the team segment).
        iteration_id: UUID of the iteration to assign.
    """
    team_call.post(
        "work",
        "teamsettings",
        "iterations",
        version="7.1",
        json=_TeamIterationRef(id=str(iteration_id)).model_dump(mode="json"),
    )


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
