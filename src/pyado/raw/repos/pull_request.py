"""Azure DevOps pull request API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any, TypeAlias

from pydantic import Field
from pydantic.networks import AnyUrl

from pyado.raw._core import AdoBaseModel, ApiCall, _IdentityRef
from pyado.raw.boards.work_item import WorkItemRef, _WorkItemRefResults
from pyado.raw.repos.git import (
    ChangeTypeList,
    CommitId,
    GitCommitRef,
    PullRequestStatusContext,
    RepositoryId,
)

__all__ = [
    "CommentId",
    "CommitIdRef",
    "GitForkRef",
    "IdentityIdRef",
    "PullRequestCompletionOptions",
    "PullRequestCreateRequest",
    "PullRequestId",
    "PullRequestIteration",
    "PullRequestIterationChange",
    "PullRequestIterationChangeItem",
    "PullRequestIterationContext",
    "PullRequestIterationRecord",
    "PullRequestLabel",
    "PullRequestLabelId",
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
    "PullRequestStatusId",
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
    "ThreadId",
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
    "list_pull_request_commits",
    "list_pull_request_iterations",
    "list_pull_request_statuses",
    "list_pull_request_threads",
    "list_pull_request_work_item_ids",
    "list_pull_requests",
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

PullRequestId: TypeAlias = int
PullRequestIteration: TypeAlias = int
#: Numeric identifier for a pull request review thread.
ThreadId: TypeAlias = int
#: Numeric identifier for a comment within a pull request thread.
CommentId: TypeAlias = int
#: String identifier for a pull request label.
PullRequestLabelId: TypeAlias = str
#: Numeric identifier for a pull request status check entry.
PullRequestStatusId: TypeAlias = int


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


class PullRequestThreadCommentType(StrEnum):
    """ADO comment type values for PR thread comments."""

    UNKNOWN = "unknown"
    TEXT = "text"
    CODE_CHANGE = "codeChange"
    SYSTEM = "system"


class PullRequestVote(IntEnum):
    """Reviewer vote values for a pull request."""

    APPROVED = 10
    APPROVED_WITH_SUGGESTIONS = 5
    NO_VOTE = 0
    WAITING_FOR_AUTHOR = -5
    REJECTED = -10


class CommitIdRef(AdoBaseModel):
    """Minimal commit reference for use in PR request bodies.

    Serialises to ``{"commitId": "<sha>"}`` as required by the ADO PATCH PR
    endpoint's ``lastMergeSourceCommit`` field.
    """

    commit_id: CommitId


class IdentityIdRef(AdoBaseModel):
    """Minimal identity reference for use in PR request bodies (id only).

    Serialises to ``{"id": "<uuid>"}`` as required by ADO endpoints such as
    ``autoCompleteSetBy``.
    """

    id: str


class RepositoryRef(AdoBaseModel):
    """Minimal repository reference as returned in PR list responses."""

    id: RepositoryId
    name: str | None = None


class PullRequestThreadCommentRequest(AdoBaseModel):
    """Type for storing a pull request comment."""

    comment_type: PullRequestThreadCommentType
    content: str
    parent_comment_id: int


class PullRequestStatusRequest(AdoBaseModel):
    """Request body for posting a status item on a pull request."""

    context: PullRequestStatusContext
    description: str | None = None
    iteration_id: PullRequestIteration
    state: PullRequestStatusState
    target_url: AnyUrl | None = None


class PullRequestStatusInfo(AdoBaseModel):
    """A status item as returned by the PR statuses GET endpoint."""

    id: PullRequestStatusId | None = None
    state: PullRequestStatusState
    context: PullRequestStatusContext
    description: str | None = None
    target_url: AnyUrl | None = None
    iteration_id: PullRequestIteration | None = None


class _PullRequestStatusResults(AdoBaseModel):
    """Internal: container for PR status list results."""

    value: list[PullRequestStatusInfo] = Field(default_factory=list)


class PullRequestReviewer(AdoBaseModel):
    """A reviewer entry on a pull request."""

    id: str
    display_name: str
    vote: PullRequestVote = PullRequestVote.NO_VOTE
    is_required: bool = False
    has_declined: bool = False
    is_flagged: bool = False


class PullRequestLabel(AdoBaseModel):
    """A label (tag) associated with a pull request."""

    id: PullRequestLabelId | None = None
    name: str
    active: bool = True
    url: str | None = None


class _PullRequestLabelResults(AdoBaseModel):
    """Internal: container for PR label list results."""

    value: list[PullRequestLabel] = Field(default_factory=list)


class PullRequestListItem(AdoBaseModel):
    """A pull request entry as returned by the project-level PR list endpoint."""

    pr_id: PullRequestId = Field(alias="pullRequestId")
    repository: RepositoryRef
    title: str | None = None
    description: str | None = None
    source_ref_name: str | None = None
    target_ref_name: str | None = None
    created_by: _IdentityRef | None = None
    creation_date: datetime | None = None
    status: PullRequestStatus | None = None
    is_draft: bool = False
    merge_status: PullRequestMergeStatus | None = None
    reviewers: list[PullRequestReviewer] = Field(default_factory=list)
    labels: list[PullRequestLabel] = Field(default_factory=list)
    closed_date: datetime | None = None
    auto_complete_set_by: _IdentityRef | None = None
    merge_failure_type: PullRequestMergeFailureType | None = None
    merge_failure_message: str | None = None
    has_multiple_merge_bases: bool = False
    url: str | None = None
    merge_id: str | None = None
    last_merge_source_commit: GitCommitRef | None = None
    last_merge_target_commit: GitCommitRef | None = None
    last_merge_commit: GitCommitRef | None = None
    supports_iterations: bool = False


class PullRequestSearchCriteria(AdoBaseModel):
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
    creator_id: str | None = None
    reviewer_id: str | None = None
    source_ref_name: str | None = None
    target_ref_name: str | None = None
    repository_id: str | None = None
    pull_request_id: int | None = None
    source_version: str | None = None
    min_time: datetime | None = None
    max_time: datetime | None = None


class _PullRequestListResults(AdoBaseModel):
    """Type to read PR list results."""

    value: list[PullRequestListItem]


class _PullRequestLabelRequest(AdoBaseModel):
    """Internal: request body for adding a label to a pull request."""

    name: str


class PullRequestThreadPosition(AdoBaseModel):
    """A position (line and offset) within a file in a PR thread context."""

    line: int
    offset: int


class PullRequestThreadContext(AdoBaseModel):
    """File location context for a PR review thread."""

    file_path: str
    left_file_start: PullRequestThreadPosition | None = None
    left_file_end: PullRequestThreadPosition | None = None
    right_file_start: PullRequestThreadPosition | None = None
    right_file_end: PullRequestThreadPosition | None = None


class PullRequestIterationContext(AdoBaseModel):
    """The pair of PR iterations being compared when a thread was created."""

    first_comparing_iteration: int
    second_comparing_iteration: int


class PullRequestThreadHistoryContext(AdoBaseModel):
    """Extended PR-specific context for a review thread (iteration tracking)."""

    change_tracking_id: int | None = None
    iteration_context: PullRequestIterationContext | None = None


class PullRequestThreadCommentResponse(AdoBaseModel):
    """A single comment within a PR review thread."""

    id: CommentId | None = None
    content: str | None = None
    comment_type: PullRequestThreadCommentType | None = None
    parent_comment_id: int
    author: _IdentityRef | None = None
    published_date: datetime | None = None
    last_updated_date: datetime | None = None
    last_content_updated_date: datetime | None = None
    is_deleted: bool = False


class PullRequestThreadResponse(AdoBaseModel):
    """A review thread on a pull request."""

    id: ThreadId | None = None
    status: PullRequestThreadStatus | None = None
    comments: list[PullRequestThreadCommentResponse] = Field(default_factory=list)
    thread_context: PullRequestThreadContext | None = None
    pull_request_thread_context: PullRequestThreadHistoryContext | None = None
    published_date: datetime | None = None
    last_updated_date: datetime | None = None
    is_deleted: bool = False
    properties: dict[str, Any] | None = None


class PullRequestThreadRequest(AdoBaseModel):
    """Request body for creating a new review thread on a pull request."""

    comments: list[PullRequestThreadCommentRequest]
    status: PullRequestThreadStatus
    thread_context: PullRequestThreadContext | None = None


class _PullRequestThreadPatchRequest(AdoBaseModel):
    """Internal: request body for patching a PR review thread."""

    status: PullRequestThreadStatus


class _PullRequestThreadResults(AdoBaseModel):
    """Internal: container for PR thread list results."""

    value: list[PullRequestThreadResponse]


class PullRequestCompletionOptions(AdoBaseModel):
    """Options applied when a pull request is completed."""

    squash_merge: bool = True
    delete_source_branch: bool = True
    merge_strategy: PullRequestMergeStrategy | None = None
    merge_commit_message: str | None = None
    transition_work_items: bool = False


class PullRequestUpdateRequest(AdoBaseModel):
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
    is_draft: bool | None = None
    completion_options: PullRequestCompletionOptions | None = None
    last_merge_source_commit: CommitIdRef | None = None
    work_item_refs: list[WorkItemRef] | None = None
    auto_complete_set_by: IdentityIdRef | None = None


class PullRequestIterationRecord(AdoBaseModel):
    """A single iteration (push) of a pull request."""

    id: PullRequestIteration
    created_date: datetime | None = None
    source_ref_commit: GitCommitRef | None = None
    target_ref_commit: GitCommitRef | None = None


class _PullRequestIterationResults(AdoBaseModel):
    """Internal: container for PR iteration list results."""

    value: list[PullRequestIterationRecord]


class PullRequestReviewerVoteRequest(AdoBaseModel):
    """Request body for setting a reviewer's vote on a pull request."""

    vote: PullRequestVote
    is_reapprove: bool = False


class PullRequestReviewerRequest(AdoBaseModel):
    """Request body for adding or updating a reviewer on a pull request."""

    vote: PullRequestVote = PullRequestVote.NO_VOTE
    is_required: bool = False
    is_reapprove: bool = False


class _PullRequestReviewerResults(AdoBaseModel):
    """Internal: container for PR reviewer list results."""

    value: list[PullRequestReviewer] = Field(default_factory=list)


class _GitCommitRefResults(AdoBaseModel):
    """Internal: container for a list of commit references."""

    value: list[GitCommitRef] = Field(default_factory=list)


class GitForkRef(AdoBaseModel):
    """Source ref information for a PR created from a fork."""

    name: str
    object_id: CommitId
    repository: RepositoryRef


class PullRequestResponse(AdoBaseModel):
    """Full pull request resource, as returned by the ADO Git pull-requests API.

    ADO uses a single ``PullRequestResponse`` schema for the responses of all three
    operations: ``POST`` (create), ``GET`` (get details), and ``PATCH``
    (update).  This class models that shared schema.

    Reference: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/
    pull-requests
    """

    pr_id: PullRequestId = Field(alias="pullRequestId")
    repository: RepositoryRef
    status: PullRequestStatus
    url: str
    title: str
    source_ref_name: str
    target_ref_name: str
    is_draft: bool = False
    created_by: _IdentityRef | None = None
    creation_date: datetime | None = None
    closed_date: datetime | None = None
    closed_by: _IdentityRef | None = None
    reviewers: list[PullRequestReviewer] = Field(default_factory=list)
    merge_status: PullRequestMergeStatus | None = None
    merge_id: str | None = None
    last_merge_source_commit: GitCommitRef | None = None
    last_merge_target_commit: GitCommitRef | None = None
    last_merge_commit: GitCommitRef | None = None
    auto_complete_set_by: _IdentityRef | None = None
    completion_options: PullRequestCompletionOptions | None = None
    labels: list[PullRequestLabel] = Field(default_factory=list)
    description: str | None = None
    artifact_id: str | None = None
    supports_iterations: bool = False
    fork_source: GitForkRef | None = None
    merge_failure_type: PullRequestMergeFailureType | None = None
    merge_failure_message: str | None = None
    has_multiple_merge_bases: bool = False


class PullRequestCreateRequest(AdoBaseModel):
    """Request body for creating a new pull request."""

    title: str
    source_ref_name: str
    target_ref_name: str
    completion_options: PullRequestCompletionOptions
    description: str | None = None
    work_item_refs: list[WorkItemRef] | None = None


class PullRequestIterationChangeItem(AdoBaseModel):
    """A file-level item in a PR iteration change entry."""

    path: str | None = None
    url: AnyUrl | None = None


class PullRequestIterationChange(AdoBaseModel):
    """A single file change entry from a PR iteration changes response."""

    change_type: ChangeTypeList
    item: PullRequestIterationChangeItem


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
    pr_api_call: ApiCall, thread_id: ThreadId
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
    thread_id: ThreadId,
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
) -> list[PullRequestIterationChange]:
    """Return the file changes introduced by a specific PR iteration.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        iteration_id: The iteration number to query.

    Returns:
        List of PullRequestIterationChange from the ``changeEntries`` key of the
        API response.
    """
    response = pr_api_call.get(
        "iterations",
        iteration_id,
        "changes",
        version="7.1-preview.1",
    )
    return [
        PullRequestIterationChange.model_validate(e)
        for e in response.get("changeEntries", [])
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
    thread_id: ThreadId,
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
