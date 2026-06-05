"""Azure DevOps pull request API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import AnyUrl

from pyado.raw._core import ApiCall, _IdentityRef
from pyado.raw.git import (
    CommitId,
    GitChangeType,
    GitCommitRef,
    PullRequestStatusContext,
    RepositoryId,
)
from pyado.raw.work_item import WorkItemRef, _WorkItemRefResults

__all__ = [
    "CommitIdRef",
    "GitForkRef",
    "IdentityIdRef",
    "PrIterationChange",
    "PrIterationChangeItem",
    "PullRequestCompletionOptions",
    "PullRequestCreateRequest",
    "PullRequestId",
    "PullRequestIteration",
    "PullRequestIterationContext",
    "PullRequestIterationRecord",
    "PullRequestLabel",
    "PullRequestListItem",
    "PullRequestMergeFailureType",
    "PullRequestMergeStatus",
    "PullRequestMergeStrategy",
    "PullRequestResponse",
    "PullRequestReviewer",
    "PullRequestReviewerRequest",
    "PullRequestReviewerVoteRequest",
    "PullRequestSearchCriteria",
    "PullRequestStatus",
    "PullRequestStatusInfo",
    "PullRequestStatusRequest",
    "PullRequestStatusState",
    "PullRequestThreadCommentRequest",
    "PullRequestThreadCommentResponse",
    "PullRequestThreadCommentType",
    "PullRequestThreadContext",
    "PullRequestThreadHistoryContext",
    "PullRequestThreadPosition",
    "PullRequestThreadRequest",
    "PullRequestThreadResponse",
    "PullRequestThreadStatus",
    "PullRequestUpdateRequest",
    "PullRequestVote",
    "RepositoryRef",
    "delete_pull_request_label",
    "delete_pull_request_reviewer",
    "get_pull_request_api_call",
    "get_pull_request_details",
    "get_pull_request_iteration_changes",
    "get_pull_request_labels_details",
    "get_pull_request_reviewers",
    "get_pull_request_thread",
    "iter_pull_request_commits",
    "iter_pull_request_iterations",
    "iter_pull_request_statuses",
    "iter_pull_request_threads",
    "iter_pull_request_work_item_ids",
    "iter_pull_requests",
    "patch_pull_request",
    "patch_pull_request_thread",
    "post_pull_request",
    "post_pull_request_label",
    "post_pull_request_new_thread",
    "post_pull_request_status",
    "post_pull_request_thread_comment",
    "put_pull_request_reviewer",
    "put_pull_request_reviewer_vote",
]

PullRequestId = int
PullRequestIteration = int


class PullRequestStatusState(StrEnum):
    """Possible state values for a PR status check."""

    ERROR = "error"
    FAILED = "failed"
    NOT_APPLICABLE = "notApplicable"
    NOT_SET = "notSet"
    PENDING = "pending"
    SUCCEEDED = "succeeded"


class PullRequestMergeStatus(StrEnum):
    """Current merge status of a pull request."""

    NOT_SET = "notSet"
    QUEUED = "queued"
    CONFLICTS = "conflicts"
    SUCCEEDED = "succeeded"
    REJECTED_BY_POLICY = "rejectedByPolicy"
    FAILURE = "failure"


class PullRequestThreadStatus(StrEnum):
    """Possible status values for a PR review thread."""

    ACTIVE = "active"
    BY_DESIGN = "byDesign"
    CLOSED = "closed"
    FIXED = "fixed"
    PENDING = "pending"
    UNKNOWN = "unknown"
    WONT_FIX = "wontFix"


class PullRequestMergeFailureType(StrEnum):
    """Reason a pull request merge failed."""

    NONE = "none"
    UNKNOWN = "unknown"
    CASE_SENSITIVE = "caseSensitive"
    OBJECT_TOO_LARGE = "objectTooLarge"


class PullRequestStatus(StrEnum):
    """Lifecycle state of a pull request."""

    ACTIVE = "active"
    ABANDONED = "abandoned"
    COMPLETED = "completed"


class PullRequestMergeStrategy(StrEnum):
    """Merge strategies available when completing a pull request."""

    NO_FAST_FORWARD = "noFastForward"
    SQUASH = "squash"
    REBASE = "rebase"
    REBASE_MERGE = "rebaseMerge"


class PullRequestThreadCommentType(IntEnum):
    """ADO comment type values used when creating thread comments."""

    UNKNOWN = 0
    TEXT = 1
    CODE_CHANGE = 2
    SYSTEM = 3


class PullRequestVote(IntEnum):
    """Reviewer vote values for a pull request."""

    APPROVED = 10
    APPROVED_WITH_SUGGESTIONS = 5
    NO_VOTE = 0
    WAITING_FOR_AUTHOR = -5
    REJECTED = -10


class CommitIdRef(BaseModel):
    """Minimal commit reference for use in PR request bodies.

    Serialises to ``{"commitId": "<sha>"}`` as required by the ADO PATCH PR
    endpoint's ``lastMergeSourceCommit`` field.
    """

    commit_id: CommitId = Field(serialization_alias="commitId")


class IdentityIdRef(BaseModel):
    """Minimal identity reference for use in PR request bodies (id only).

    Serialises to ``{"id": "<uuid>"}`` as required by ADO endpoints such as
    ``autoCompleteSetBy``.
    """

    id: str


class RepositoryRef(BaseModel):
    """Minimal repository reference as returned in PR list responses."""

    id: RepositoryId
    name: str | None = None


class PullRequestThreadCommentRequest(BaseModel):
    """Type for storing a pull request comment."""

    comment_type: PullRequestThreadCommentType = Field(
        serialization_alias="commentType"
    )
    content: str
    parent_comment_id: int = Field(serialization_alias="parentCommentId")


class PullRequestStatusRequest(BaseModel):
    """Request body for posting a status item on a pull request."""

    context: PullRequestStatusContext
    description: str | None = None
    iteration_id: PullRequestIteration = Field(serialization_alias="iterationId")
    state: PullRequestStatusState
    target_url: AnyUrl | None = Field(default=None, serialization_alias="targetUrl")


class PullRequestStatusInfo(BaseModel):
    """A status item as returned by the PR statuses GET endpoint."""

    id: int | None = None
    state: PullRequestStatusState
    context: PullRequestStatusContext
    description: str | None = None
    target_url: AnyUrl | None = Field(default=None, alias="targetUrl")
    iteration_id: PullRequestIteration | None = Field(default=None, alias="iterationId")


class _PullRequestStatusResults(BaseModel):
    """Internal: container for PR status list results."""

    value: list[PullRequestStatusInfo] = []


class PullRequestReviewer(BaseModel):
    """A reviewer entry on a pull request."""

    id: str
    display_name: str = Field(alias="displayName")
    vote: int = 0
    is_required: bool = Field(alias="isRequired", default=False)
    has_declined: bool = Field(alias="hasDeclined", default=False)
    is_flagged: bool = Field(alias="isFlagged", default=False)


class PullRequestLabel(BaseModel):
    """A label (tag) associated with a pull request."""

    id: str | None = None
    name: str
    active: bool = True
    url: str | None = None


class _PullRequestLabelResults(BaseModel):
    """Internal: container for PR label list results."""

    value: list[PullRequestLabel] = []


class PullRequestListItem(BaseModel):
    """A pull request entry as returned by the project-level PR list endpoint."""

    pr_id: int = Field(alias="pullRequestId")
    repository: RepositoryRef
    title: str | None = None
    description: str | None = None
    source_ref_name: str | None = Field(alias="sourceRefName", default=None)
    target_ref_name: str | None = Field(alias="targetRefName", default=None)
    created_by: _IdentityRef | None = Field(alias="createdBy", default=None)
    creation_date: datetime | None = Field(alias="creationDate", default=None)
    status: PullRequestStatus | None = None
    is_draft: bool = Field(alias="isDraft", default=False)
    merge_status: PullRequestMergeStatus | None = Field(
        alias="mergeStatus", default=None
    )
    reviewers: list[PullRequestReviewer] = []
    labels: list[PullRequestLabel] = []
    closed_date: datetime | None = Field(alias="closedDate", default=None)
    auto_complete_set_by: _IdentityRef | None = Field(
        alias="autoCompleteSetBy", default=None
    )
    merge_failure_type: PullRequestMergeFailureType | None = Field(
        alias="mergeFailureType", default=None
    )
    merge_failure_message: str | None = Field(alias="mergeFailureMessage", default=None)
    has_multiple_merge_bases: bool = Field(alias="hasMultipleMergeBases", default=False)
    url: str | None = None
    merge_id: str | None = Field(alias="mergeId", default=None)
    last_merge_source_commit: GitCommitRef | None = Field(
        alias="lastMergeSourceCommit", default=None
    )
    last_merge_target_commit: GitCommitRef | None = Field(
        alias="lastMergeTargetCommit", default=None
    )
    last_merge_commit: GitCommitRef | None = Field(
        alias="lastMergeCommit", default=None
    )
    supports_iterations: bool = Field(alias="supportsIterations", default=False)


class PullRequestSearchCriteria(BaseModel):
    """Search criteria for listing pull requests.

    All fields are optional; only non-None values are forwarded as
    ``searchCriteria.*`` query parameters.

    Attributes:
        status: Filter by PR lifecycle state.
        creator_id: Filter by the identity UUID of the PR creator.
        reviewer_id: Filter by the identity UUID of a reviewer.
        source_ref_name: Filter by source branch ref name.
        target_ref_name: Filter by target branch ref name.
        repository_id: Filter by repository UUID.
    """

    status: PullRequestStatus | None = None
    creator_id: str | None = Field(default=None, serialization_alias="creatorId")
    reviewer_id: str | None = Field(default=None, serialization_alias="reviewerId")
    source_ref_name: str | None = Field(
        default=None, serialization_alias="sourceRefName"
    )
    target_ref_name: str | None = Field(
        default=None, serialization_alias="targetRefName"
    )
    repository_id: str | None = Field(default=None, serialization_alias="repositoryId")
    pull_request_id: int | None = Field(
        default=None, serialization_alias="pullRequestId"
    )
    source_version: str | None = Field(
        default=None, serialization_alias="sourceVersion"
    )
    min_time: datetime | None = Field(default=None, serialization_alias="minTime")
    max_time: datetime | None = Field(default=None, serialization_alias="maxTime")


class _PullRequestListResults(BaseModel):
    """Type to read PR list results."""

    value: list[PullRequestListItem]


class _PullRequestLabelRequest(BaseModel):
    """Internal: request body for adding a label to a pull request."""

    name: str


class PullRequestThreadPosition(BaseModel):
    """A position (line and offset) within a file in a PR thread context."""

    line: int
    offset: int


class PullRequestThreadContext(BaseModel):
    """File location context for a PR review thread."""

    file_path: str = Field(validation_alias="filePath", serialization_alias="filePath")
    left_file_start: PullRequestThreadPosition | None = Field(
        default=None,
        validation_alias="leftFileStart",
        serialization_alias="leftFileStart",
    )
    left_file_end: PullRequestThreadPosition | None = Field(
        default=None,
        validation_alias="leftFileEnd",
        serialization_alias="leftFileEnd",
    )
    right_file_start: PullRequestThreadPosition | None = Field(
        default=None,
        validation_alias="rightFileStart",
        serialization_alias="rightFileStart",
    )
    right_file_end: PullRequestThreadPosition | None = Field(
        default=None,
        validation_alias="rightFileEnd",
        serialization_alias="rightFileEnd",
    )


class PullRequestIterationContext(BaseModel):
    """The pair of PR iterations being compared when a thread was created."""

    first_comparing_iteration: int = Field(alias="firstComparingIteration")
    second_comparing_iteration: int = Field(alias="secondComparingIteration")


class PullRequestThreadHistoryContext(BaseModel):
    """Extended PR-specific context for a review thread (iteration tracking)."""

    change_tracking_id: int | None = Field(alias="changeTrackingId", default=None)
    iteration_context: PullRequestIterationContext | None = Field(
        alias="iterationContext", default=None
    )


class PullRequestThreadCommentResponse(BaseModel):
    """A single comment within a PR review thread."""

    id: int | None = None
    content: str | None = None
    comment_type: str | None = Field(default=None, alias="commentType")
    parent_comment_id: int = Field(alias="parentCommentId")
    author: _IdentityRef | None = None
    published_date: datetime | None = Field(alias="publishedDate", default=None)
    last_updated_date: datetime | None = Field(alias="lastUpdatedDate", default=None)
    last_content_updated_date: datetime | None = Field(
        alias="lastContentUpdatedDate", default=None
    )
    is_deleted: bool = Field(alias="isDeleted", default=False)


class PullRequestThreadResponse(BaseModel):
    """A review thread on a pull request."""

    id: int | None = None
    status: PullRequestThreadStatus | None = None
    comments: list[PullRequestThreadCommentResponse] = []
    thread_context: PullRequestThreadContext | None = Field(
        default=None, alias="threadContext"
    )
    pull_request_thread_context: PullRequestThreadHistoryContext | None = Field(
        default=None, alias="pullRequestThreadContext"
    )
    published_date: datetime | None = Field(alias="publishedDate", default=None)
    last_updated_date: datetime | None = Field(alias="lastUpdatedDate", default=None)
    is_deleted: bool = Field(alias="isDeleted", default=False)
    properties: dict[str, Any] | None = None


class PullRequestThreadRequest(BaseModel):
    """Request body for creating a new review thread on a pull request."""

    comments: list[PullRequestThreadCommentRequest]
    status: PullRequestThreadStatus
    thread_context: PullRequestThreadContext | None = Field(
        default=None, serialization_alias="threadContext"
    )


class _PullRequestThreadPatchRequest(BaseModel):
    """Internal: request body for patching a PR review thread."""

    status: PullRequestThreadStatus


class _PullRequestThreadResults(BaseModel):
    """Internal: container for PR thread list results."""

    value: list[PullRequestThreadResponse]


class PullRequestCompletionOptions(BaseModel):
    """Options applied when a pull request is completed."""

    model_config = ConfigDict(populate_by_name=True)

    squash_merge: bool = Field(default=True, alias="squashMerge")
    delete_source_branch: bool = Field(default=True, alias="deleteSourceBranch")
    merge_strategy: PullRequestMergeStrategy | None = Field(
        default=None, alias="mergeStrategy"
    )
    merge_commit_message: str | None = Field(default=None, alias="mergeCommitMessage")
    transition_work_items: bool = Field(default=False, alias="transitionWorkItems")


class PullRequestUpdateRequest(BaseModel):
    """Request body for patching a pull request.

    All fields are optional; only non-None values are sent to ADO.

    Attributes:
        title: New PR title.
        description: New PR description.
        status: Transition the PR to this status.
        is_draft: Set or clear the draft flag.
        completion_options: Merge strategy and post-completion options, used
            when completing (merging) a PR.
        last_merge_source_commit: Commit ID of the source branch tip at the
            time of the request, used for optimistic concurrency on complete.
    """

    title: str | None = None
    description: str | None = None
    status: PullRequestStatus | None = None
    is_draft: bool | None = Field(default=None, serialization_alias="isDraft")
    completion_options: PullRequestCompletionOptions | None = Field(
        default=None, serialization_alias="completionOptions"
    )
    last_merge_source_commit: CommitIdRef | None = Field(
        default=None, serialization_alias="lastMergeSourceCommit"
    )
    work_item_refs: list[WorkItemRef] | None = Field(
        default=None, serialization_alias="workItemRefs"
    )
    auto_complete_set_by: IdentityIdRef | None = Field(
        default=None, serialization_alias="autoCompleteSetBy"
    )


class PullRequestIterationRecord(BaseModel):
    """A single iteration (push) of a pull request."""

    id: int
    created_date: datetime | None = Field(default=None, alias="createdDate")
    source_ref_commit: GitCommitRef | None = Field(
        default=None, alias="sourceRefCommit"
    )
    target_ref_commit: GitCommitRef | None = Field(
        default=None, alias="targetRefCommit"
    )


class _PullRequestIterationResults(BaseModel):
    """Internal: container for PR iteration list results."""

    value: list[PullRequestIterationRecord]


class PullRequestReviewerVoteRequest(BaseModel):
    """Request body for setting a reviewer's vote on a pull request."""

    vote: PullRequestVote
    is_reapprove: bool = Field(default=False, serialization_alias="isReapprove")


class PullRequestReviewerRequest(BaseModel):
    """Request body for adding or updating a reviewer on a pull request."""

    vote: PullRequestVote = PullRequestVote.NO_VOTE
    is_required: bool = Field(default=False, serialization_alias="isRequired")
    is_reapprove: bool = Field(default=False, serialization_alias="isReapprove")


class _PullRequestReviewerResults(BaseModel):
    """Internal: container for PR reviewer list results."""

    value: list[PullRequestReviewer] = []


class _GitCommitRefResults(BaseModel):
    """Internal: container for a list of commit references."""

    value: list[GitCommitRef] = []


class GitForkRef(BaseModel):
    """Source ref information for a PR created from a fork."""

    name: str
    object_id: CommitId = Field(alias="objectId")
    repository: RepositoryRef


class PullRequestResponse(BaseModel):
    """Full pull request resource, as returned by the ADO Git pull-requests API.

    ADO uses a single ``PullRequestResponse`` schema for the responses of all three
    operations: ``POST`` (create), ``GET`` (get details), and ``PATCH``
    (update).  This class models that shared schema.

    Reference: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/
    pull-requests
    """

    pr_id: int = Field(alias="pullRequestId")
    repository: RepositoryRef
    status: PullRequestStatus
    url: str
    title: str
    source_ref_name: str = Field(alias="sourceRefName")
    target_ref_name: str = Field(alias="targetRefName")
    is_draft: bool = Field(default=False, alias="isDraft")
    created_by: _IdentityRef | None = Field(alias="createdBy", default=None)
    creation_date: datetime | None = Field(alias="creationDate", default=None)
    closed_date: datetime | None = Field(alias="closedDate", default=None)
    closed_by: _IdentityRef | None = Field(alias="closedBy", default=None)
    reviewers: list[PullRequestReviewer] = []
    merge_status: str | None = Field(alias="mergeStatus", default=None)
    merge_id: str | None = Field(alias="mergeId", default=None)
    last_merge_source_commit: GitCommitRef | None = Field(
        alias="lastMergeSourceCommit", default=None
    )
    last_merge_target_commit: GitCommitRef | None = Field(
        alias="lastMergeTargetCommit", default=None
    )
    last_merge_commit: GitCommitRef | None = Field(
        alias="lastMergeCommit", default=None
    )
    auto_complete_set_by: _IdentityRef | None = Field(
        alias="autoCompleteSetBy", default=None
    )
    completion_options: PullRequestCompletionOptions | None = Field(
        alias="completionOptions", default=None
    )
    labels: list[PullRequestLabel] = []
    description: str | None = None
    artifact_id: str | None = Field(alias="artifactId", default=None)
    supports_iterations: bool = Field(alias="supportsIterations", default=False)
    fork_source: GitForkRef | None = Field(alias="forkSource", default=None)
    merge_failure_type: PullRequestMergeFailureType | None = Field(
        alias="mergeFailureType", default=None
    )
    merge_failure_message: str | None = Field(alias="mergeFailureMessage", default=None)
    has_multiple_merge_bases: bool = Field(alias="hasMultipleMergeBases", default=False)


class PullRequestCreateRequest(BaseModel):
    """Request body for creating a new pull request."""

    title: str
    source_ref_name: str = Field(serialization_alias="sourceRefName")
    target_ref_name: str = Field(serialization_alias="targetRefName")
    completion_options: PullRequestCompletionOptions = Field(
        serialization_alias="completionOptions"
    )
    description: str | None = None
    work_item_refs: list[WorkItemRef] | None = Field(
        default=None, serialization_alias="workItemRefs"
    )


class PrIterationChangeItem(BaseModel):
    """A file-level item in a PR iteration change entry."""

    path: str | None = None
    url: AnyUrl | None = None


class PrIterationChange(BaseModel):
    """A single file change entry from a PR iteration changes response."""

    change_type: GitChangeType = Field(alias="changeType")
    item: PrIterationChangeItem


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def get_pull_request_details(
    pr_api_call: ApiCall, *, expand: str | None = None
) -> PullRequestResponse:
    """Return the full details of a single pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        expand: Optional ``$expand`` value (e.g. ``"labels"``,
            ``"reviewers"``).  When provided, the corresponding data is
            inlined in the response.

    Returns:
        PullRequestResponse populated with the current PR state.
    """
    params: dict[str, int | str | bool] | None = (
        {"$expand": expand} if expand is not None else None
    )
    response = pr_api_call.get(parameters=params, version="7.1-preview.1")
    return PullRequestResponse.model_validate(response)


def get_pull_request_api_call(
    project_api_call: ApiCall,
    repository_id: RepositoryId,
    pr_id: PullRequestId,
) -> ApiCall:
    """Get pull request API call.

    Returns:
        An ApiCall pointing at the pull request resource.
    """
    return project_api_call.build_call(
        "git",
        "repositories",
        repository_id,
        "pullRequests",
        pr_id,
    )


def post_pull_request_status(
    pr_api_call: ApiCall,
    request: PullRequestStatusRequest,
) -> None:
    """Create a status item on the PR.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/git/7.1/httpExamples/pullRequestStatuses/
    POST_git_pullRequestStatuses_statusIterationInBody.json
    """
    pr_api_call.post(
        "statuses",
        version="7.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


def iter_pull_requests(
    project_api_call: ApiCall,
    *,
    search_criteria: PullRequestSearchCriteria | None = None,
    expand: str | None = None,
) -> Iterator[PullRequestListItem]:
    """Iterate over pull requests in the project matching the given criteria.

    Args:
        project_api_call: Project-level ADO API call.
        search_criteria: Optional search criteria model; only non-None
            fields are forwarded as ``searchCriteria.*`` query parameters.
        expand: Optional ``$expand`` value (e.g. ``"labels"``,
            ``"reviewers"``).  Multiple values can be combined with a comma.

    Yields:
        PullRequestListItem for each matching pull request.
    """
    page_size = 100
    criteria_dict = (
        search_criteria.model_dump(mode="json", by_alias=True, exclude_none=True)
        if search_criteria
        else {}
    )
    parameters: dict[str, int | str | bool] = {
        f"searchCriteria.{key}": value for key, value in criteria_dict.items()
    }
    parameters["$top"] = page_size
    if expand is not None:
        parameters["$expand"] = expand
    skip = 0
    while True:
        parameters["$skip"] = skip
        response = project_api_call.get(
            "git",
            "pullrequests",
            parameters=parameters,
            version="7.1",
        )
        results = _PullRequestListResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def post_pull_request_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Add a label to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        label_name: Name of the label to add.
    """
    pr_api_call.post(
        "labels",
        json=_PullRequestLabelRequest(name=label_name).model_dump(mode="json"),
        version="7.1-preview.1",
    )


def delete_pull_request_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Remove a label from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        label_name: Name of the label to remove.
    """
    pr_api_call.delete("labels", label_name, version="7.1-preview.1")


def iter_pull_request_threads(
    pr_api_call: ApiCall,
) -> Iterator[PullRequestThreadResponse]:
    """Iterate over all review threads on a pull request.

    Note:
        Issues a single HTTP request — the ADO threads endpoint returns all
        threads in one response.  The ``$iteration`` and ``$baseIteration``
        query params control which diff context is included in each thread but
        do not act as pagination parameters.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Yields:
        PullRequestThreadResponse objects for each thread.
    """
    response = pr_api_call.get("threads", version="7.1-preview.1")
    yield from _PullRequestThreadResults.model_validate(response).value


def get_pull_request_thread(
    pr_api_call: ApiCall, thread_id: int
) -> PullRequestThreadResponse:
    """Return a single review thread by ID.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        thread_id: Numeric ID of the thread to fetch.

    Returns:
        PullRequestThreadResponse for the requested thread.
    """
    response = pr_api_call.get("threads", thread_id, version="7.1-preview.1")
    return PullRequestThreadResponse.model_validate(response)


def post_pull_request_thread_comment(
    pr_api_call: ApiCall,
    thread_id: int,
    comment: PullRequestThreadCommentRequest,
) -> PullRequestThreadCommentResponse:
    """Add a reply comment to an existing PR review thread.

    Args:
        pr_api_call: PR-level ADO API call.
        thread_id: ID of the thread to reply to.
        comment: The comment to post, including content, type, and parent ID.

    Returns:
        The created PullRequestThreadCommentResponse.
    """
    response = pr_api_call.post(
        "threads",
        thread_id,
        "comments",
        version="7.1-preview.1",
        json=comment.model_dump(mode="json", by_alias=True),
    )
    return PullRequestThreadCommentResponse.model_validate(response)


def patch_pull_request(
    pr_api_call: ApiCall, update: PullRequestUpdateRequest
) -> PullRequestResponse:
    """Update fields on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        update: Fields to update; None values are omitted from the request.

    Returns:
        PullRequestResponse populated with the PR state after the update.
    """
    response = pr_api_call.patch(
        version="7.1-preview.1",
        json=update.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PullRequestResponse.model_validate(response)


def iter_pull_request_iterations(
    pr_api_call: ApiCall,
) -> Iterator[PullRequestIterationRecord]:
    """Iterate over the iterations (commit pushes) of a pull request.

    Args:
        pr_api_call: PR-level ADO API call.

    Yields:
        PullRequestIterationRecord for each iteration.
    """
    response = pr_api_call.get("iterations", version="7.1-preview.1")
    yield from _PullRequestIterationResults.model_validate(response).value


def get_pull_request_iteration_changes(
    pr_api_call: ApiCall,
    iteration_id: PullRequestIteration,
) -> list[PrIterationChange]:
    """Return the file changes introduced by a specific PR iteration.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        iteration_id: The iteration number to query.

    Returns:
        List of PrIterationChange from the ``changeEntries`` key of the
        API response.
    """
    response = pr_api_call.get(
        "iterations",
        iteration_id,
        "changes",
        version="7.1-preview.1",
    )
    return [
        PrIterationChange.model_validate(e) for e in response.get("changeEntries", [])
    ]


def put_pull_request_reviewer_vote(
    pr_api_call: ApiCall,
    reviewer_id: str,
    request: PullRequestReviewerVoteRequest,
) -> None:
    """Set a reviewer's vote on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        reviewer_id: Identity ID of the reviewer.
        request: Vote request specifying the vote value and reapprove flag.
    """
    pr_api_call.put(
        "reviewers",
        reviewer_id,
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True),
    )


def put_pull_request_reviewer(
    pr_api_call: ApiCall,
    reviewer_id: str,
    request: PullRequestReviewerRequest,
) -> None:
    """Add or update a reviewer on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        reviewer_id: Identity (object) ID of the reviewer.
        request: Reviewer request specifying vote, required flag, and reapprove
            flag.
    """
    pr_api_call.put(
        "reviewers",
        reviewer_id,
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True),
    )


def delete_pull_request_reviewer(pr_api_call: ApiCall, reviewer_id: str) -> None:
    """Remove a reviewer from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        reviewer_id: Identity (object) ID of the reviewer to remove.
    """
    pr_api_call.delete("reviewers", reviewer_id, version="7.1-preview.1")


def get_pull_request_reviewers(pr_api_call: ApiCall) -> list[PullRequestReviewer]:
    """Return all reviewers on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Returns:
        List of PullRequestReviewer entries.
    """
    response = pr_api_call.get("reviewers", version="7.1-preview.1")
    return _PullRequestReviewerResults.model_validate(response).value


def iter_pull_request_commits(pr_api_call: ApiCall) -> Iterator[GitCommitRef]:
    """Iterate over commits included in a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Yields:
        GitCommitRef for each commit reachable from the pull request.
    """
    response = pr_api_call.get("commits", version="7.1-preview.1")
    yield from _GitCommitRefResults.model_validate(response).value


def iter_pull_request_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemRef]:
    """Iterate over work items linked to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Yields:
        WorkItemRef for each work item associated with the pull request.
    """
    page_size = 100
    skip = 0
    while True:
        response = pr_api_call.get(
            "workitems",
            parameters={"$top": page_size, "$skip": skip},
            version="7.1",
        )
        results = _WorkItemRefResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def get_pull_request_labels_details(pr_api_call: ApiCall) -> list[PullRequestLabel]:
    """Return all labels currently set on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Returns:
        List of PullRequestLabel objects.
    """
    response = pr_api_call.get("labels", version="7.1-preview.1")
    return _PullRequestLabelResults.model_validate(response).value


def post_pull_request_new_thread(
    pr_api_call: ApiCall,
    request: PullRequestThreadRequest,
) -> PullRequestThreadResponse:
    """Create a new review thread on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        request: Thread creation request specifying comments, status, and
            optional file context.

    Returns:
        The created PullRequestThreadResponse.
    """
    response = pr_api_call.post(
        "threads",
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PullRequestThreadResponse.model_validate(response)


def post_pull_request(
    repository_api_call: ApiCall,
    request: PullRequestCreateRequest,
) -> PullRequestResponse:
    """Create a new pull request.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        request: Pull request creation request specifying title, branches, and
            completion options.

    Returns:
        PullRequestResponse for the newly created pull request.
    """
    response = repository_api_call.post(
        "pullrequests",
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PullRequestResponse.model_validate(response)


def patch_pull_request_thread(
    pr_api_call: ApiCall,
    thread_id: int,
    status: PullRequestThreadStatus,
) -> PullRequestThreadResponse:
    """Update the status of an existing PR review thread.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        thread_id: Numeric ID of the thread to update.
        status: New thread status (e.g. ``PullRequestThreadStatus.FIXED``).

    Returns:
        Updated PullRequestThreadResponse.
    """
    response = pr_api_call.patch(
        "threads",
        thread_id,
        version="7.1-preview.1",
        json=_PullRequestThreadPatchRequest(status=status).model_dump(mode="json"),
    )
    return PullRequestThreadResponse.model_validate(response)


def iter_pull_request_statuses(pr_api_call: ApiCall) -> Iterator[PullRequestStatusInfo]:
    """Iterate over status checks posted on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Yields:
        PullRequestStatusInfo for each status item on the PR.
    """
    response = pr_api_call.get("statuses", version="7.1-preview.1")
    yield from _PullRequestStatusResults.model_validate(response).value


def list_pull_requests(
    project_api_call: ApiCall,
    search_criteria: PullRequestSearchCriteria | None = None,
    expand: str | None = None,
) -> list[PullRequestListItem]:
    """Return all pull requests matching the given criteria as a list."""
    return list(
        iter_pull_requests(
            project_api_call, search_criteria=search_criteria, expand=expand
        )
    )


def list_pull_request_threads(
    pr_api_call: ApiCall,
) -> list[PullRequestThreadResponse]:
    """Return all review threads for a pull request as a list."""
    return list(iter_pull_request_threads(pr_api_call))


def list_pull_request_iterations(
    pr_api_call: ApiCall,
) -> list[PullRequestIterationRecord]:
    """Return all iterations for a pull request as a list."""
    return list(iter_pull_request_iterations(pr_api_call))


def list_pull_request_commits(pr_api_call: ApiCall) -> list[GitCommitRef]:
    """Return all commits for a pull request as a list."""
    return list(iter_pull_request_commits(pr_api_call))


def list_pull_request_work_item_ids(pr_api_call: ApiCall) -> list[WorkItemRef]:
    """Return all work item IDs linked to a pull request as a list."""
    return list(iter_pull_request_work_item_ids(pr_api_call))


def list_pull_request_statuses(pr_api_call: ApiCall) -> list[PullRequestStatusInfo]:
    """Return all statuses for a pull request as a list."""
    return list(iter_pull_request_statuses(pr_api_call))
