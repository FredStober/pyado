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
    GitCommitRef,
    PullRequestStatusContext,
    RepositoryId,
)
from pyado.raw.work_item import WorkItemRef, _WorkItemRefResults

__all__ = [
    "GitForkRef",
    "GitPullRequestMergeStrategy",
    "PullRequestCompletionOptions",
    "PullRequestCreateRequest",
    "PullRequestCreated",
    "PullRequestId",
    "PullRequestIteration",
    "PullRequestIterationContext",
    "PullRequestIterationRecord",
    "PullRequestLabel",
    "PullRequestListItem",
    "PullRequestMergeFailureType",
    "PullRequestMergeStatus",
    "PullRequestReviewer",
    "PullRequestReviewerRequest",
    "PullRequestReviewerVoteRequest",
    "PullRequestSearchCriteria",
    "PullRequestStatus",
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
    "delete_pr_label",
    "delete_pr_reviewer",
    "get_pr_api_call",
    "get_pr_details",
    "get_pr_labels_details",
    "get_pr_reviewers",
    "iter_pr_commits",
    "iter_pr_iterations",
    "iter_pr_threads",
    "iter_pr_work_item_ids",
    "iter_prs",
    "patch_pr",
    "post_pr_label",
    "post_pr_new_thread",
    "post_pr_status",
    "post_pr_thread_comment",
    "post_pull_request",
    "put_pr_reviewer",
    "put_pr_reviewer_vote",
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


class GitPullRequestMergeStrategy(StrEnum):
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


class RepositoryRef(BaseModel):
    """Minimal repository reference as returned in PR list responses."""

    id: RepositoryId


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
    status: str | None = None
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


class _PullRequestThreadResults(BaseModel):
    """Internal: container for PR thread list results."""

    value: list[PullRequestThreadResponse]


class PullRequestCompletionOptions(BaseModel):
    """Options applied when a pull request is completed."""

    model_config = ConfigDict(populate_by_name=True)

    squash_merge: bool = Field(default=True, alias="squashMerge")
    delete_source_branch: bool = Field(default=True, alias="deleteSourceBranch")
    merge_strategy: GitPullRequestMergeStrategy | None = Field(
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
    last_merge_source_commit: dict[str, str] | None = Field(
        default=None, serialization_alias="lastMergeSourceCommit"
    )


class PullRequestIterationRecord(BaseModel):
    """A single iteration (push) of a pull request."""

    id: int
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


class PullRequestCreated(BaseModel):
    """A pull request as returned by the create-PR endpoint.

    Reference: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/
    pull-requests/create
    """

    pr_id: int = Field(alias="pullRequestId")
    repository: RepositoryRef
    status: str
    url: str
    title: str
    source_ref_name: str = Field(alias="sourceRefName")
    target_ref_name: str = Field(alias="targetRefName")
    is_draft: bool = Field(default=False, alias="isDraft")
    created_by: _IdentityRef | None = Field(alias="createdBy", default=None)
    creation_date: datetime | None = Field(alias="creationDate", default=None)
    closed_date: datetime | None = Field(alias="closedDate", default=None)
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
    work_item_refs: list[dict[str, str]] | None = Field(
        default=None, serialization_alias="workItemRefs"
    )


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def get_pr_details(pr_api_call: ApiCall) -> PullRequestCreated:
    """Return the full details of a single pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        PullRequestCreated populated with the current PR state.
    """
    response = pr_api_call.get(version="7.1-preview.1")
    return PullRequestCreated.model_validate(response)


def get_pr_api_call(
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


def post_pr_status(
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


def iter_prs(
    project_api_call: ApiCall,
    search_criteria: PullRequestSearchCriteria | None = None,
) -> Iterator[PullRequestListItem]:
    """Iterate over pull requests in the project matching the given criteria.

    Args:
        project_api_call: Project-level ADO API call.
        search_criteria: Optional search criteria model; only non-None
            fields are forwarded as ``searchCriteria.*`` query parameters.

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


def post_pr_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Add a label to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        label_name: Name of the label to add.
    """
    pr_api_call.post(
        "labels",
        json=_PullRequestLabelRequest(name=label_name).model_dump(mode="json"),
        version="7.1-preview.1",
    )


def delete_pr_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Remove a label from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        label_name: Name of the label to remove.
    """
    pr_api_call.delete("labels", label_name, version="7.1-preview.1")


def iter_pr_threads(pr_api_call: ApiCall) -> Iterator[PullRequestThreadResponse]:
    """Iterate over all review threads on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Yields:
        PullRequestThreadResponse objects for each thread.
    """
    response = pr_api_call.get("threads", version="7.1-preview.1")
    yield from _PullRequestThreadResults.model_validate(response).value


def post_pr_thread_comment(
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


def patch_pr(
    pr_api_call: ApiCall, update: PullRequestUpdateRequest
) -> PullRequestCreated:
    """Update fields on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        update: Fields to update; None values are omitted from the request.

    Returns:
        PullRequestCreated populated with the PR state after the update.
    """
    response = pr_api_call.patch(
        version="7.1-preview.1",
        json=update.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PullRequestCreated.model_validate(response)


def iter_pr_iterations(
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


def put_pr_reviewer_vote(
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


def put_pr_reviewer(
    pr_api_call: ApiCall,
    reviewer_id: str,
    request: PullRequestReviewerRequest,
) -> None:
    """Add or update a reviewer on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
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


def delete_pr_reviewer(pr_api_call: ApiCall, reviewer_id: str) -> None:
    """Remove a reviewer from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        reviewer_id: Identity (object) ID of the reviewer to remove.
    """
    pr_api_call.delete("reviewers", reviewer_id, version="7.1-preview.1")


def get_pr_reviewers(pr_api_call: ApiCall) -> list[PullRequestReviewer]:
    """Return all reviewers on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        List of PullRequestReviewer entries.
    """
    response = pr_api_call.get("reviewers", version="7.1-preview.1")
    return _PullRequestReviewerResults.model_validate(response).value


def iter_pr_commits(pr_api_call: ApiCall) -> Iterator[GitCommitRef]:
    """Iterate over commits included in a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Yields:
        GitCommitRef for each commit reachable from the pull request.
    """
    response = pr_api_call.get("commits", version="7.1-preview.1")
    yield from _GitCommitRefResults.model_validate(response).value


def iter_pr_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemRef]:
    """Iterate over work items linked to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

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


def get_pr_labels_details(pr_api_call: ApiCall) -> list[PullRequestLabel]:
    """Return all labels currently set on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        List of PullRequestLabel objects.
    """
    response = pr_api_call.get("labels", version="7.1-preview.1")
    return _PullRequestLabelResults.model_validate(response).value


def post_pr_new_thread(
    pr_api_call: ApiCall,
    request: PullRequestThreadRequest,
) -> PullRequestThreadResponse:
    """Create a new review thread on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
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
) -> PullRequestCreated:
    """Create a new pull request.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call).
        request: Pull request creation request specifying title, branches, and
            completion options.

    Returns:
        PullRequestCreated for the newly created pull request.
    """
    response = repository_api_call.post(
        "pullrequests",
        version="7.1-preview.1",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PullRequestCreated.model_validate(response)
