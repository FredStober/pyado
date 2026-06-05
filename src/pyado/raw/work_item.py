"""Azure DevOps work item, WIQL, sprint, and attachment API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import AnyUrl

from pyado.raw._core import ApiCall, JsonPatchAdd, JsonPatchRemove, _IdentityRef

__all__ = [
    "ClassificationNode",
    "ClassificationNodeAttributes",
    "ClassificationNodePatchRequest",
    "ClassificationNodeRequest",
    "ClassificationNodeType",
    "ClassificationNodeUrlType",
    "SprintIterationAttributes",
    "SprintIterationId",
    "SprintIterationInfo",
    "SprintIterationPath",
    "SprintIterationTimeframe",
    "TeamFieldValue",
    "TextFormat",
    "WorkItemArtifactUrlPrefix",
    "WorkItemAttachmentRef",
    "WorkItemComment",
    "WorkItemExpand",
    "WorkItemField",
    "WorkItemFieldName",
    "WorkItemId",
    "WorkItemInfo",
    "WorkItemQuery",
    "WorkItemQueryExpand",
    "WorkItemQueryType",
    "WorkItemRef",
    "WorkItemRelation",
    "WorkItemRelationType",
    "WorkItemState",
    "WorkItemType",
    "WorkItemsBatchRequest",
    "add_team_iteration",
    "create_classification_node",
    "delete_classification_node",
    "delete_team_iteration",
    "delete_work_item",
    "delete_work_item_comment",
    "get_classification_node",
    "get_query_folder",
    "get_query_tree",
    "get_team_field_values",
    "get_work_item",
    "get_work_item_api_call",
    "get_work_item_attachment_bytes",
    "iter_sprint_iterations",
    "iter_work_item_comments",
    "iter_work_item_revisions",
    "patch_classification_node",
    "patch_work_item",
    "patch_work_item_comment",
    "post_wiql",
    "post_work_item",
    "post_work_item_attachment_upload",
    "post_work_item_comment",
    "post_work_items_batch",
    "restore_work_item",
]

SprintIterationId = UUID
SprintIterationPath = str
WorkItemField = str
WorkItemId = int


class TextFormat(StrEnum):
    """Content format for multiline work item fields.

    Pass as values in the ``multiline_fields_format`` argument to
    ``create_work_item`` / ``update_work_item`` to control how ADO renders
    the field's content.
    """

    HTML = "html"
    MARKDOWN = "markdown"


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
    NODE_NAME = "System.NodeName"
    REV = "System.Rev"
    HISTORY = "System.History"
    ATTACHED_FILE_COUNT = "System.AttachedFileCount"
    HYPERLINK_COUNT = "System.HyperLinkCount"
    EXTERNAL_LINK_COUNT = "System.ExternalLinkCount"
    RELATED_LINK_COUNT = "System.RelatedLinkCount"
    # RemoteLinkCount tracks links to external work items (GitHub, etc.);
    # available on Azure DevOps Services only.
    REMOTE_LINK_COUNT = "System.RemoteLinkCount"
    TAGS = "System.Tags"
    BOARD_COLUMN = "System.BoardColumn"
    BOARD_COLUMN_DONE = "System.BoardColumnDone"
    BOARD_LANE = "System.BoardLane"
    PARENT = "System.Parent"
    # IsDeleted is set when a work item is soft-deleted (moved to recycle bin).
    IS_DELETED = "System.IsDeleted"
    # --- Microsoft.VSTS.Common fields ---
    PRIORITY = "Microsoft.VSTS.Common.Priority"
    SEVERITY = "Microsoft.VSTS.Common.Severity"
    VALUE_AREA = "Microsoft.VSTS.Common.ValueArea"
    BUSINESS_VALUE = "Microsoft.VSTS.Common.BusinessValue"
    TIME_CRITICALITY = "Microsoft.VSTS.Common.TimeCriticality"
    RISK = "Microsoft.VSTS.Common.Risk"
    ACTIVITY = "Microsoft.VSTS.Common.Activity"
    # Discipline is the CMMI equivalent of Activity (Agile/Scrum).
    DISCIPLINE = "Microsoft.VSTS.Common.Discipline"
    STACK_RANK = "Microsoft.VSTS.Common.StackRank"
    BACKLOG_PRIORITY = "Microsoft.VSTS.Common.BacklogPriority"
    CLOSED_DATE = "Microsoft.VSTS.Common.ClosedDate"
    CLOSED_BY = "Microsoft.VSTS.Common.ClosedBy"
    ACTIVATED_BY = "Microsoft.VSTS.Common.ActivatedBy"
    ACTIVATED_DATE = "Microsoft.VSTS.Common.ActivatedDate"
    RESOLVED_DATE = "Microsoft.VSTS.Common.ResolvedDate"
    RESOLVED_BY = "Microsoft.VSTS.Common.ResolvedBy"
    RESOLVED_REASON = "Microsoft.VSTS.Common.ResolvedReason"
    ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"
    STATE_CHANGE_DATE = "Microsoft.VSTS.Common.StateChangeDate"
    # Triage is CMMI-only (Pending / More Info / Info Received / Triaged).
    TRIAGE = "Microsoft.VSTS.Common.Triage"
    # Resolution describes how a Scrum Impediment was resolved.
    RESOLUTION = "Microsoft.VSTS.Common.Resolution"
    # Rating is used on Code Review Response items (1-5 scale).
    RATING = "Microsoft.VSTS.Common.Rating"
    # ClosedStatus is used on Code Review Response items.
    CLOSED_STATUS = "Microsoft.VSTS.Common.ClosedStatus"
    # --- Microsoft.VSTS.Scheduling fields ---
    REMAINING_WORK = "Microsoft.VSTS.Scheduling.RemainingWork"
    COMPLETED_WORK = "Microsoft.VSTS.Scheduling.CompletedWork"
    ORIGINAL_ESTIMATE = "Microsoft.VSTS.Scheduling.OriginalEstimate"
    # Effort, StoryPoints, and Size are process-specific names for the same
    # planning concept (all map to "Effort" in ProcessConfiguration).
    # Scrum uses EFFORT; Agile uses STORY_POINTS; CMMI uses SIZE.
    EFFORT = "Microsoft.VSTS.Scheduling.Effort"
    STORY_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"
    SIZE = "Microsoft.VSTS.Scheduling.Size"
    START_DATE = "Microsoft.VSTS.Scheduling.StartDate"
    FINISH_DATE = "Microsoft.VSTS.Scheduling.FinishDate"
    TARGET_DATE = "Microsoft.VSTS.Scheduling.TargetDate"
    # --- Microsoft.VSTS.Build fields ---
    INTEGRATION_BUILD = "Microsoft.VSTS.Build.IntegrationBuild"
    FOUND_IN = "Microsoft.VSTS.Build.FoundIn"
    # --- Microsoft.VSTS.CodeReview fields ---
    # Used on Code Review Request / Code Review Response work items.
    CODE_REVIEW_CONTEXT = "Microsoft.VSTS.CodeReview.Context"
    CODE_REVIEW_CONTEXT_OWNER = "Microsoft.VSTS.CodeReview.ContextOwner"
    CODE_REVIEW_CONTEXT_TYPE = "Microsoft.VSTS.CodeReview.ContextType"
    CODE_REVIEW_REBASED_SHA = "Microsoft.VSTS.CodeReview.RebasedSha"
    # --- Microsoft.VSTS.Feedback fields ---
    # Used on Feedback Request / Feedback Response work items.
    FEEDBACK_APPLICATION_ID = "Microsoft.VSTS.Feedback.ApplicationId"
    FEEDBACK_APPLICATION_LAUNCH_INSTRUCTIONS = (
        "Microsoft.VSTS.Feedback.ApplicationLaunchInstructions"
    )
    FEEDBACK_APPLICATION_START_INFORMATION = (
        "Microsoft.VSTS.Feedback.ApplicationStartInformation"
    )
    FEEDBACK_APPLICATION_TYPE = "Microsoft.VSTS.Feedback.ApplicationType"
    FEEDBACK_RATING = "Microsoft.VSTS.Feedback.Rating"
    FEEDBACK_USER_TEXT = "Microsoft.VSTS.Feedback.UserText"
    # --- Microsoft.VSTS.TCM fields ---
    REPRO_STEPS = "Microsoft.VSTS.TCM.ReproSteps"
    # SystemInfo captures the OS/browser environment recorded at repro time
    # (Bug work items, all process templates).
    SYSTEM_INFO = "Microsoft.VSTS.TCM.SystemInfo"
    # AutomationStatus tracks whether a test case is automated
    # (Automated / Not Automated / Planned).
    AUTOMATION_STATUS = "Microsoft.VSTS.TCM.AutomationStatus"
    AUTOMATED_TEST_ID = "Microsoft.VSTS.TCM.AutomatedTestId"
    AUTOMATED_TEST_NAME = "Microsoft.VSTS.TCM.AutomatedTestName"
    AUTOMATED_TEST_STORAGE = "Microsoft.VSTS.TCM.AutomatedTestStorage"
    AUTOMATED_TEST_TYPE = "Microsoft.VSTS.TCM.AutomatedTestType"
    # IssueUrl links a test case to an associated bug/issue URL.
    TCM_ISSUE_URL = "Microsoft.VSTS.TCM.IssueUrl"
    LOCAL_DATA_SOURCE = "Microsoft.VSTS.TCM.LocalDataSource"
    TEST_PARAMETERS = "Microsoft.VSTS.TCM.Parameters"
    TEST_STEPS = "Microsoft.VSTS.TCM.Steps"
    TEST_SUITE_AUDIT = "Microsoft.VSTS.TCM.TestSuiteAudit"
    TEST_SUITE_TYPE = "Microsoft.VSTS.TCM.TestSuiteType"
    TEST_SUITE_TYPE_ID = "Microsoft.VSTS.TCM.TestSuiteTypeId"
    # --- Microsoft.VSTS.CMMI fields ---
    # Note: despite the CMMI namespace, BLOCKED is also used by Scrum Tasks
    # (same reference name across both process templates).
    BLOCKED = "Microsoft.VSTS.CMMI.Blocked"
    # Committed and Escalate are CMMI-only.
    COMMITTED = "Microsoft.VSTS.CMMI.Committed"
    ESCALATE = "Microsoft.VSTS.CMMI.Escalate"
    CMMI_ACTION_PATH = "Microsoft.VSTS.CMMI.ActionPath"
    CMMI_APPROVED = "Microsoft.VSTS.CMMI.Approved"
    CMMI_CALLED_BY = "Microsoft.VSTS.CMMI.CalledBy"
    CMMI_CALLED_DATE = "Microsoft.VSTS.CMMI.CalledDate"
    CMMI_CHANGE_REQUEST_VALIDATED = "Microsoft.VSTS.CMMI.ChangeRequestValidated"
    CMMI_FOUND_IN_ENVIRONMENT = "Microsoft.VSTS.CMMI.FoundInEnvironment"
    CMMI_HOW_FOUND_CATEGORY = "Microsoft.VSTS.CMMI.HowFoundCategory"
    CMMI_IMPACT = "Microsoft.VSTS.CMMI.Impact"
    CMMI_IMPACT_ON_ARCHITECTURE = "Microsoft.VSTS.CMMI.ImpactOnArchitecture"
    CMMI_IMPACT_ON_DEVELOPMENT = "Microsoft.VSTS.CMMI.ImpactOnDevelopment"
    CMMI_IMPACT_ON_TECHNICAL_PUBLICATIONS = (
        "Microsoft.VSTS.CMMI.ImpactOnTechnicalPublications"
    )
    CMMI_IMPACT_ON_TEST = "Microsoft.VSTS.CMMI.ImpactOnTest"
    CMMI_IMPACT_ON_USER_EXPERIENCE = "Microsoft.VSTS.CMMI.ImpactOnUserExperience"
    CMMI_ISSUE = "Microsoft.VSTS.CMMI.Issue"
    CMMI_MINUTES = "Microsoft.VSTS.CMMI.Minutes"
    CMMI_MITIGATION_PLAN = "Microsoft.VSTS.CMMI.MitigationPlan"
    CMMI_MITIGATION_TRIGGERS = "Microsoft.VSTS.CMMI.MitigationTriggers"
    CMMI_PROBABILITY = "Microsoft.VSTS.CMMI.Probability"
    CMMI_PROPOSED_FIX = "Microsoft.VSTS.CMMI.ProposedFix"
    CMMI_PURPOSE = "Microsoft.VSTS.CMMI.Purpose"
    CMMI_ROOT_CAUSE = "Microsoft.VSTS.CMMI.RootCause"
    CMMI_SUBJECT_MATTER_EXPERT1 = "Microsoft.VSTS.CMMI.SubjectMatterExpert1"
    CMMI_SUBJECT_MATTER_EXPERT2 = "Microsoft.VSTS.CMMI.SubjectMatterExpert2"
    CMMI_SUBJECT_MATTER_EXPERT3 = "Microsoft.VSTS.CMMI.SubjectMatterExpert3"
    CMMI_TARGET_RESOLVE_DATE = "Microsoft.VSTS.CMMI.TargetResolveDate"
    CMMI_TASK_TYPE = "Microsoft.VSTS.CMMI.TaskType"
    CMMI_USER_ACCEPTANCE_TEST = "Microsoft.VSTS.CMMI.UserAcceptanceTest"


class WorkItemState(StrEnum):
    """Well-known work item state values across the four built-in ADO processes.

    States are process-template-specific and can be customised per project.
    This enum covers all states shipped with the Agile, Scrum, CMMI, and Basic
    templates.  For projects with custom states, pass the state name as a plain
    string — the field accepts any ``str`` value regardless.

    To define a project-specific state set that reuses standard values alongside
    custom ones, declare your own ``StrEnum`` and assign members from this
    class::

        from enum import StrEnum
        from pyado import WorkItemState

        class AcmeState(StrEnum):
            NEW      = WorkItemState.NEW        # "New"
            ACTIVE   = WorkItemState.ACTIVE     # "Active"
            IN_SPRINT = "In Sprint"             # custom
            CLOSED   = WorkItemState.CLOSED     # "Closed"
    """

    # --- Agile (Epic, Feature, User Story, Bug, Task, Issue) ---
    NEW = "New"  # Agile, Scrum
    ACTIVE = "Active"  # Agile, CMMI
    RESOLVED = "Resolved"  # Agile, CMMI
    CLOSED = "Closed"  # Agile, CMMI
    REMOVED = "Removed"  # Agile, Scrum

    # --- Scrum (Product Backlog Item, Bug) ---
    APPROVED = "Approved"
    COMMITTED = "Committed"

    # --- Scrum / Basic (Task, Epic, Feature) ---
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"

    # --- Basic only ---
    DOING = "Doing"

    # --- CMMI (Requirement, Change Request, Bug, Task, Issue, Risk, Review) ---
    PROPOSED = "Proposed"


class WorkItemType(StrEnum):
    """Common ADO work item type names for use with ``System.WorkItemType``.

    These are the standard types shipped with the default Azure DevOps process
    templates (Agile, Scrum, CMMI).  Custom process templates may define
    additional types not listed here; pass the type name as a plain string in
    those cases.

    Example::

        create_work_item(api, {
            WorkItemFieldName.WORK_ITEM_TYPE: WorkItemType.BUG,
            WorkItemFieldName.TITLE: "Something is broken",
        })
    """

    # --- Agile / Scrum / CMMI shared ---
    EPIC = "Epic"
    FEATURE = "Feature"
    BUG = "Bug"
    TASK = "Task"
    TEST_CASE = "Test Case"
    TEST_PLAN = "Test Plan"
    TEST_SUITE = "Test Suite"
    # --- Agile ---
    USER_STORY = "User Story"
    ISSUE = "Issue"
    # --- Scrum ---
    PRODUCT_BACKLOG_ITEM = "Product Backlog Item"
    IMPEDIMENT = "Impediment"
    # --- CMMI ---
    REQUIREMENT = "Requirement"
    CHANGE_REQUEST = "Change Request"
    REVIEW = "Review"
    RISK = "Risk"


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


class ClassificationNodeType(StrEnum):
    """Discriminates iteration nodes from area nodes in the classification tree."""

    ITERATION = "iteration"
    AREA = "area"


class ClassificationNodeUrlType(StrEnum):
    """URL path segment used to select the classification node tree type.

    Used as the ``node_type`` argument to ``get_classification_node``,
    ``create_classification_node``, and ``patch_classification_node``.
    """

    ITERATIONS = "iterations"
    AREAS = "areas"


class ClassificationNodeAttributes(BaseModel):
    """Date attributes of a classification node (sprint iteration)."""

    model_config = ConfigDict(populate_by_name=True)

    start_date: str | None = Field(alias="startDate", default=None)
    finish_date: str | None = Field(alias="finishDate", default=None)


class ClassificationNode(BaseModel):
    """A classification node as returned by the ADO API.

    The same schema is used for both **iteration** nodes (``structureType ==
    "iteration"``) and **area** nodes (``structureType == "area"``).  The
    distinction matters for the ``attributes`` field:

    - **Iterations** may carry ``attributes.startDate`` / ``attributes.finishDate``.
    - **Areas** never have ``attributes`` — the field will always be ``None``.
    """

    id: int
    identifier: str | None = None
    name: str
    path: str | None = None
    structure_type: ClassificationNodeType | None = Field(
        alias="structureType", default=None
    )
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


class ClassificationNodeRequest(BaseModel):
    """Request body for creating a classification node."""

    name: str
    attributes: ClassificationNodeAttributes | None = None


class ClassificationNodePatchRequest(BaseModel):
    """Request body for patching a classification node (rename and/or date update)."""

    name: str | None = None
    attributes: ClassificationNodeAttributes | None = None


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

    Note:
        Uses cursor-based pagination via ``continuationToken`` — this is an
        intentional ADO WIT Comments endpoint design.  The endpoint does not
        support the standard ``$skip``/``$top`` offset pagination used by
        other ADO endpoints.

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


def iter_work_item_revisions(
    work_item_api_call: ApiCall,
) -> Iterator[WorkItemInfo]:
    """Iterate over all historical revisions of a work item, oldest first.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).

    Yields:
        WorkItemInfo snapshot for each revision, oldest first.
    """
    response = work_item_api_call.get("revisions", version="7.1")
    yield from _WorkItemInfoResults.model_validate(response).value


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
    json_patches: list[JsonPatchAdd | JsonPatchRemove],
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
        json=[op.model_dump(mode="json") for op in json_patches],
    )
    return WorkItemInfo.model_validate(response)


def patch_work_item(
    work_item_api_call: ApiCall,
    json_patches: list[JsonPatchAdd | JsonPatchRemove],
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
    response = work_item_api_call.patch(
        version="7.1",
        json=[op.model_dump(mode="json") for op in json_patches],
    )
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


def get_work_item_attachment_bytes(
    project_api_call: ApiCall,
    attachment_id: str,
) -> bytes:
    """Download the raw bytes of an uploaded work item attachment.

    Args:
        project_api_call: Project-level ADO API call.
        attachment_id: The UUID string from WorkItemAttachmentRef.id.

    Returns:
        Raw attachment bytes.
    """
    return cast(
        "bytes",
        project_api_call.get_raw("wit", "attachments", attachment_id, version="7.1"),
    )


def get_classification_node(
    project_api_call: ApiCall,
    path: str | None = None,
    *,
    node_type: ClassificationNodeUrlType,
    depth: int = 1,
) -> ClassificationNode:
    """Return the classification node tree for a project.

    Args:
        project_api_call: Project-level ADO API call.
        path: Path within the tree (e.g. ``"Sprint 42"`` or ``"Team A"``), or
            None for the root.
        node_type: Whether to fetch from the iterations or areas tree.
        depth: Number of levels to fetch below the requested node (default: 1).

    Returns:
        ClassificationNode for the requested path.
    """
    args: list[str] = ["wit", "classificationnodes", node_type]
    if path:
        args.append(path)
    response = project_api_call.get(*args, parameters={"$depth": depth}, version="7.0")
    return ClassificationNode.model_validate(response)


def create_classification_node(
    project_api_call: ApiCall,
    request: ClassificationNodeRequest,
    parent_path: str | None = None,
    *,
    node_type: ClassificationNodeUrlType,
) -> ClassificationNode:
    """Create a classification node under a parent path.

    Args:
        project_api_call: Project-level ADO API call.
        request: Request body carrying the node name and optional date
            attributes.
        parent_path: Path of the parent node within the tree, or None to
            create at the root.
        node_type: Whether to create in the iterations or areas tree.

    Returns:
        The newly created ClassificationNode.
    """
    args: list[str] = ["wit", "classificationnodes", node_type]
    if parent_path:
        args.append(parent_path)
    response = project_api_call.post(
        *args,
        version="7.0",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ClassificationNode.model_validate(response)


def patch_classification_node(
    project_api_call: ApiCall,
    path: str | None,
    request: ClassificationNodePatchRequest,
    *,
    node_type: ClassificationNodeUrlType,
) -> ClassificationNode:
    """Update a classification node (rename and/or change dates).

    Args:
        project_api_call: Project-level ADO API call.
        path: Path of the node to update (e.g. ``"Sprint 42"`` or
            ``"Team A"``), or None for the root node.
        request: Patch body carrying the optional new name and/or date
            attributes.
        node_type: Whether to patch in the iterations or areas tree.

    Returns:
        Updated ClassificationNode from the ADO API.
    """
    args: list[str] = ["wit", "classificationnodes", node_type]
    if path:
        args.append(path)
    response = project_api_call.patch(
        *args,
        version="7.0",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ClassificationNode.model_validate(response)


def delete_classification_node(
    project_api_call: ApiCall,
    path: str | None,
    *,
    node_type: ClassificationNodeUrlType,
) -> None:
    """Delete a classification node (iteration or area).

    Args:
        project_api_call: Project-level ADO API call.
        path: Relative path of the node to delete (e.g. ``"Sprint 42"``),
            or None for the root node.
        node_type: Whether to delete from the iterations or areas tree.
    """
    args: list[str] = ["wit", "classificationnodes", node_type]
    if path:
        args.append(path)
    project_api_call.delete(*args, version="7.0")


def get_team_field_values(team_api_call: ApiCall) -> list[TeamFieldValue]:
    """Return the team area-path field values configuration.

    Args:
        team_api_call: Team-level ADO API call (URL includes the team segment).

    Returns:
        List of TeamFieldValue from the ``values`` key of the API response.
    """
    response = team_api_call.get(
        "work",
        "teamsettings",
        "teamfieldvalues",
        version="7.0",
    )
    return [TeamFieldValue.model_validate(v) for v in response.get("values", [])]


def delete_team_iteration(
    team_api_call: ApiCall,
    iteration_id: SprintIterationId,
) -> None:
    """Remove an iteration from a team's sprint backlog.

    ADO: DELETE {team}/_apis/work/teamsettings/iterations/{iterationId}

    Args:
        team_api_call: Team-scoped API call.
        iteration_id: UUID of the iteration to remove.
    """
    team_api_call.delete(
        "work",
        "teamsettings",
        "iterations",
        str(iteration_id),
        version="7.1",
    )


def add_team_iteration(
    team_api_call: ApiCall,
    iteration_id: SprintIterationId,
) -> None:
    """Assign an existing iteration to a team.

    Args:
        team_api_call: Team-level ADO API call (URL includes the team segment).
        iteration_id: UUID of the iteration to assign.
    """
    team_api_call.post(
        "work",
        "teamsettings",
        "iterations",
        version="7.1",
        json=_TeamIterationRef(id=str(iteration_id)).model_dump(mode="json"),
    )


class WorkItemQueryExpand(StrEnum):
    """Expand options for WIT query fetch requests.

    These are OData ``$expand`` values used with ``GET wit/queries``.
    """

    NONE = "none"
    MINIMAL = "minimal"
    CLAUSES = "clauses"
    ALL = "all"


class WorkItemQueryType(StrEnum):
    """The structural type of a WIT saved query."""

    FLAT = "flat"
    ONE_HOP = "oneHop"
    TREE = "tree"


class WorkItemQuery(BaseModel):
    """A saved query or query folder returned by the WIT queries endpoint."""

    id: str
    name: str
    path: str | None = None
    is_folder: bool = Field(alias="isFolder", default=False)
    has_children: bool = Field(alias="hasChildren", default=False)
    children: list["WorkItemQuery"] = []
    wiql: str | None = None
    query_type: WorkItemQueryType | None = Field(alias="queryType", default=None)


WorkItemQuery.model_rebuild()


def get_query_tree(
    project_api_call: ApiCall,
    *,
    depth: int = 2,
    expand: WorkItemQueryExpand = WorkItemQueryExpand.ALL,
) -> list[WorkItemQuery]:
    """Return the root-level WIT saved-query folders for a project.

    ADO's ``GET wit/queries`` endpoint returns a paged list of root folders
    (typically "My Queries" and "Shared Queries").  Use
    :func:`get_query_folder` to fetch a specific folder's contents by GUID.

    Args:
        project_api_call: Project-level ADO API call.
        depth: Number of folder levels to expand below the root folders.
            ``2`` is sufficient for the standard Shared Queries structure
            (folder → queries).  Avoid ``3`` or higher unless you know the
            project has nested sub-folders.
        expand: OData ``$expand`` value controlling which fields are populated.
            Defaults to ``WorkItemQueryExpand.ALL`` to include ``wiql`` and
            other query details.

    Returns:
        List of :class:`WorkItemQuery` objects, one per root folder.

    Note:
        The depth parameter **must** be passed as ``$depth`` (with leading
        dollar sign) to be recognised by ADO.  Using plain ``depth`` causes
        ADO to silently ignore it, returning folders with empty ``children``
        even when ``hasChildren`` is ``true``.  This function always sends
        the correctly-spelled parameter.
    """
    response = project_api_call.get(
        "wit",
        "queries",
        parameters={"$depth": depth, "$expand": expand},
        version="7.1",
    )
    return [WorkItemQuery.model_validate(item) for item in response.get("value", [])]


def get_query_folder(
    project_api_call: ApiCall,
    folder_id: str,
    *,
    depth: int = 1,
    expand: WorkItemQueryExpand = WorkItemQueryExpand.ALL,
) -> WorkItemQuery:
    """Return the children of a specific WIT query folder by GUID.

    Use this when you only need queries under a particular folder rather than
    fetching the entire tree.

    Args:
        project_api_call: Project-level ADO API call.
        folder_id: GUID of the query folder.
        depth: Number of levels to expand below the requested folder.
            ``1`` is sufficient when starting directly at a folder (you are
            already at the folder level).
        expand: OData ``$expand`` value; defaults to ``WorkItemQueryExpand.ALL``.

    Returns:
        WorkItemQuery for the folder with its children populated.
    """
    response = project_api_call.get(
        "wit",
        "queries",
        folder_id,
        parameters={"$depth": depth, "$expand": expand},
        version="7.1",
    )
    return WorkItemQuery.model_validate(response)


def post_work_item_comment(
    work_item_api_call: ApiCall,
    text: str,
    *,
    comment_format: TextFormat = TextFormat.HTML,
) -> WorkItemComment:
    """Add a comment to a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        text: Comment text.
        comment_format: Content format (default: HTML). When MARKDOWN, ADO
            renders the markdown server-side.

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


def delete_work_item(work_item_api_call: ApiCall) -> None:
    """Soft-delete a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
    """
    work_item_api_call.delete(version="7.1")


def restore_work_item(
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
) -> None:
    """Restore a soft-deleted work item from the Recycle Bin.

    ADO: PATCH {project}/_apis/wit/recycleBin/{id}

    Args:
        project_api_call: Project-level API call.
        work_item_id: Numeric ID of the work item to restore.
    """
    project_api_call.patch(
        "wit",
        "recycleBin",
        str(work_item_id),
        version="7.0",
        json={"isDeleted": False},
    )


def patch_work_item_comment(
    work_item_api_call: ApiCall,
    comment_id: int,
    text: str,
) -> WorkItemComment:
    """Update the text of an existing work item comment.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        comment_id: Numeric ID of the comment to update.
        text: New comment body text.

    Returns:
        The updated WorkItemComment.
    """
    response = work_item_api_call.patch(
        "comments",
        comment_id,
        version="7.1-preview.4",
        json=_WorkItemCommentRequest(text=text).model_dump(mode="json"),
    )
    return WorkItemComment.model_validate(response)


def delete_work_item_comment(
    work_item_api_call: ApiCall,
    comment_id: int,
) -> None:
    """Delete a comment from a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        comment_id: Numeric ID of the comment to delete.
    """
    work_item_api_call.delete("comments", comment_id, version="7.1-preview.4")


def list_sprint_iterations(
    team_api_call: ApiCall,
    timeframe_filter: SprintIterationTimeframe | None = None,
) -> list[SprintIterationInfo]:
    """Return all sprint iterations for a team as a list."""
    return list(
        iter_sprint_iterations(team_api_call, timeframe_filter=timeframe_filter)
    )


def list_work_item_comments(
    work_item_api_call: ApiCall,
) -> list[WorkItemComment]:
    """Return all comments on a work item as a list."""
    return list(iter_work_item_comments(work_item_api_call))


def list_work_item_revisions(
    work_item_api_call: ApiCall,
) -> list[WorkItemInfo]:
    """Return all revisions of a work item as a list."""
    return list(iter_work_item_revisions(work_item_api_call))
