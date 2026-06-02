"""Module to interact with Azure DevOps pull requests."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from enum import IntEnum
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl

from pyado.api_call import ApiCall
from pyado.repository import RepositoryId
from pyado.work_item import WorkItemId

PullRequestId: TypeAlias = int
PullRequestIteration: TypeAlias = int
PullRequestStatusState: TypeAlias = Literal[
    "error",
    "failed",
    "notApplicable",
    "notSet",
    "pending",
    "succeeded",
]
PullRequestThreadStatus: TypeAlias = Literal[
    "active", "byDesign", "closed", "fixed", "pending", "unknown", "wontFix"
]


class PullRequestCommentType(IntEnum):
    """ADO comment type values used when creating thread comments."""

    UNKNOWN = 0
    TEXT = 1
    CODE_CHANGE = 2
    SYSTEM = 3


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


def iter_pr_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Get work items linked to the PR.

    Yields:
        Integer work item IDs associated with the pull request.
    """
    page_size = 100
    skip = 0
    while True:
        response = pr_api_call.get(
            "workitems",
            parameters={"$top": page_size, "$skip": skip},
            version="6.0",
        )
        items = response["value"]
        for entry in items:
            yield int(entry["id"])
        if len(items) < page_size:
            break
        skip += len(items)


class PullRequestComment(BaseModel):
    """Type for storing a pull request comment."""

    comment_type: PullRequestCommentType = Field(serialization_alias="commentType")
    content: str
    parent_comment_id: int = Field(serialization_alias="parentCommentId")


class PullRequestCommentHolder(BaseModel):
    """Type for storing pull request comment information."""

    status: PullRequestThreadStatus
    comments: list[PullRequestComment]


def create_pr_comments(
    pr_api_call: ApiCall,
    pr_comments_info: PullRequestCommentHolder,
) -> None:
    """Create comments on a PR.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/git/7.1/httpExamples/pullRequestThreads/
    POST__git_repositories__repositoryId__pullRequests__pullRequestId__threads
    .json
    """
    pr_api_call.post(
        "threads",
        version="7.1-preview.1",
        json=pr_comments_info.model_dump(mode="json"),
    )


class PullRequestStatusContext(BaseModel):
    """Type for storing pull request status context information."""

    name: str
    genre: str


class PullRequestStatusInfo(BaseModel):
    """Type for storing pull request status information."""

    context: PullRequestStatusContext
    description: str | None = None
    iteration_id: PullRequestIteration = Field(serialization_alias="iterationId")
    state: PullRequestStatusState
    target_url: AnyUrl | None = Field(default=None, serialization_alias="targetUrl")


def create_pr_status_flag(
    pr_api_call: ApiCall,
    pr_status_info: PullRequestStatusInfo,
) -> None:
    """Create a status item on the PR.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/git/7.1/httpExamples/pullRequestStatuses/
    POST_git_pullRequestStatuses_statusIterationInBody.json
    """
    pr_status_payload = pr_status_info.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )
    pr_api_call.post("statuses", version="7.1", json=pr_status_payload)


class RepositoryRef(BaseModel):
    """Minimal repository reference as returned in PR list responses."""

    id: RepositoryId


class PullRequestListItem(BaseModel):
    """A pull request entry as returned by the project-level PR list endpoint."""

    pr_id: int = Field(alias="pullRequestId")
    repository: RepositoryRef


class _PullRequestListResults(BaseModel):
    """Type to read PR list results."""

    value: list[PullRequestListItem]


def iter_prs(
    project_api_call: ApiCall,
    search_criteria: dict[str, int | str | bool] | None = None,
) -> Iterator[PullRequestListItem]:
    """Iterate over pull requests in the project matching the given criteria.

    Args:
        project_api_call: Project-level ADO API call.
        search_criteria: Optional mapping of ``searchCriteria.*`` query
            parameters (without the ``searchCriteria.`` prefix), e.g.
            ``{"status": "active", "creatorId": "…"}``.

    Yields:
        PullRequestListItem for each matching pull request.
    """
    page_size = 100
    skip = 0
    parameters: dict[str, int | str | bool] = {
        f"searchCriteria.{key}": value for key, value in (search_criteria or {}).items()
    }
    while True:
        response = project_api_call.get(
            "git",
            "pullrequests",
            parameters=parameters | {"$top": page_size, "$skip": skip},
            version="7.1",
        )
        results = _PullRequestListResults.model_validate(response)
        yield from results.value
        if len(results.value) < page_size:
            break
        skip += len(results.value)


def iter_open_prs(project_api_call: ApiCall) -> Iterator[PullRequestListItem]:
    """Iterate over all active pull requests in the project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        PullRequestListItem for each active pull request.
    """
    yield from iter_prs(project_api_call, {"status": "active"})


def get_pr_labels(pr_api_call: ApiCall) -> list[str]:
    """Return the names of all labels currently set on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        List of label name strings.
    """
    response = pr_api_call.get("labels", version="7.1-preview.1")
    return [entry["name"] for entry in response.get("value", [])]


def add_pr_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Add a label to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        label_name: Name of the label to add.
    """
    pr_api_call.post("labels", json={"name": label_name}, version="7.1-preview.1")


def delete_pr_label(pr_api_call: ApiCall, label_name: str) -> None:
    """Remove a label from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        label_name: Name of the label to remove.
    """
    pr_api_call.delete("labels", label_name, version="7.1-preview.1")


class PullRequestThreadPosition(BaseModel):
    """A position (line and offset) within a file in a PR thread context."""

    line: int
    offset: int


class PullRequestThreadContext(BaseModel):
    """File location context for a PR review thread."""

    file_path: str = Field(alias="filePath")
    right_file_start: PullRequestThreadPosition | None = Field(
        default=None, alias="rightFileStart"
    )
    right_file_end: PullRequestThreadPosition | None = Field(
        default=None, alias="rightFileEnd"
    )


class PullRequestThreadComment(BaseModel):
    """A single comment within a PR review thread."""

    id: int | None = None
    content: str | None = None
    comment_type: str = Field(alias="commentType")
    parent_comment_id: int = Field(alias="parentCommentId")


class PullRequestThread(BaseModel):
    """A review thread on a pull request."""

    id: int | None = None
    status: PullRequestThreadStatus | None = None
    comments: list[PullRequestThreadComment] = []
    thread_context: PullRequestThreadContext | None = Field(
        default=None, alias="threadContext"
    )


class _PullRequestThreadResults(BaseModel):
    """Internal: container for PR thread list results."""

    value: list[PullRequestThread]


def iter_pr_threads(pr_api_call: ApiCall) -> Iterator[PullRequestThread]:
    """Iterate over all review threads on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Yields:
        PullRequestThread objects for each thread.
    """
    response = pr_api_call.get("threads", version="7.1-preview.1")
    yield from _PullRequestThreadResults.model_validate(response).value


def create_pr_thread(
    pr_api_call: ApiCall,
    content: str,
    *,
    file_path: str | None = None,
    line: int | None = None,
    status: PullRequestThreadStatus = "active",
) -> PullRequestThread:
    """Create a new review thread on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        content: Text content of the first comment.
        file_path: File path to anchor the thread to, or None for PR-level.
        line: Line number within the file, used when file_path is set.
        status: Initial thread status (default: "active").

    Returns:
        The created PullRequestThread.

    Raises:
        ValueError: If ``line`` is given without ``file_path``.
    """
    if line is not None and file_path is None:
        err_msg = "line requires file_path to be set"
        raise ValueError(err_msg)
    body: dict[str, Any] = {
        "comments": [{"content": content, "commentType": 1, "parentCommentId": 0}],
        "status": status,
    }
    if file_path is not None:
        body["threadContext"] = {
            "filePath": file_path,
            "rightFileStart": {"line": line or 1, "offset": 1},
            "rightFileEnd": {"line": line or 1, "offset": 1},
        }
    response = pr_api_call.post("threads", version="7.1-preview.1", json=body)
    return PullRequestThread.model_validate(response)


def reply_to_pr_thread(
    pr_api_call: ApiCall,
    thread_id: int,
    parent_comment_id: int,
    content: str,
) -> PullRequestThreadComment:
    """Add a reply comment to an existing PR review thread.

    Args:
        pr_api_call: PR-level ADO API call.
        thread_id: ID of the thread to reply to.
        parent_comment_id: ID of the comment being replied to.
        content: Text content of the reply.

    Returns:
        The created PullRequestThreadComment.
    """
    body = {
        "content": content,
        "commentType": 1,
        "parentCommentId": parent_comment_id,
    }
    response = pr_api_call.post(
        "threads",
        thread_id,
        "comments",
        version="7.1-preview.1",
        json=body,
    )
    return PullRequestThreadComment.model_validate(response)


PullRequestStatus: TypeAlias = Literal["active", "abandoned", "completed"]


class PullRequestUpdate(BaseModel):
    """Fields that can be patched on a pull request.

    All fields are optional; only non-None values are sent to ADO.

    Attributes:
        title: New PR title.
        description: New PR description.
        status: Transition the PR to this status.
        is_draft: Set or clear the draft flag.
    """

    title: str | None = None
    description: str | None = None
    status: PullRequestStatus | None = None
    is_draft: bool | None = Field(default=None, serialization_alias="isDraft")


def update_pr(pr_api_call: ApiCall, update: PullRequestUpdate) -> None:
    """Update fields on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        update: Fields to update; None values are omitted from the request.
    """
    pr_api_call.patch(
        version="7.1-preview.1",
        json=update.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


class _PullRequestCommitRef(BaseModel):
    """Internal: a commit reference within a PR iteration."""

    commit_id: str = Field(alias="commitId")


class PullRequestIterationRecord(BaseModel):
    """A single iteration (push) of a pull request."""

    id: int
    source_ref_commit: _PullRequestCommitRef | None = Field(
        default=None, alias="sourceRefCommit"
    )
    target_ref_commit: _PullRequestCommitRef | None = Field(
        default=None, alias="targetRefCommit"
    )


class _PullRequestIterationResults(BaseModel):
    """Internal: container for PR iteration list results."""

    value: list[PullRequestIterationRecord]


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


class PullRequestVote(IntEnum):
    """Reviewer vote values for a pull request."""

    APPROVED = 10
    APPROVED_WITH_SUGGESTIONS = 5
    NO_VOTE = 0
    WAITING_FOR_AUTHOR = -5
    REJECTED = -10


def set_pr_reviewer_vote(
    pr_api_call: ApiCall,
    reviewer_id: str,
    vote: PullRequestVote,
) -> None:
    """Set a reviewer's vote on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        reviewer_id: Identity ID of the reviewer.
        vote: Vote to cast.
    """
    pr_api_call.put(
        "reviewers",
        reviewer_id,
        version="7.1-preview.1",
        json={"vote": vote},
    )


def add_pr_reviewer(
    pr_api_call: ApiCall,
    reviewer_id: str,
    *,
    is_required: bool = False,
) -> None:
    """Add a reviewer to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        reviewer_id: Identity (object) ID of the reviewer to add.
        is_required: When True the reviewer is marked as required.
    """
    pr_api_call.put(
        "reviewers",
        reviewer_id,
        version="7.1-preview.1",
        json={"vote": PullRequestVote.NO_VOTE, "isRequired": is_required},
    )


def remove_pr_reviewer(pr_api_call: ApiCall, reviewer_id: str) -> None:
    """Remove a reviewer from a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        reviewer_id: Identity (object) ID of the reviewer to remove.
    """
    pr_api_call.delete("reviewers", reviewer_id, version="7.1-preview.1")


class PrCompletionOptions(BaseModel):
    """Options applied when a pull request is completed."""

    squash_merge: bool = Field(default=True, serialization_alias="squashMerge")
    delete_source_branch: bool = Field(
        default=True, serialization_alias="deleteSourceBranch"
    )


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


def create_pr(
    repository_api_call: ApiCall,
    title: str,
    source_branch: str,
    target_branch: str,
    *,
    description: str | None = None,
    completion_options: PrCompletionOptions | None = None,
) -> PullRequestCreated:
    """Create a new pull request.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call in pyado.repository).
        title: Title of the pull request.
        source_branch: Source branch name (e.g. ``"feature/my-branch"`` or
            full ``"refs/heads/feature/my-branch"``).
        target_branch: Target branch name (e.g. ``"main"``).
        description: Optional PR description.
        completion_options: Merge and post-completion behaviour; defaults to
            squash merge with source-branch deletion.

    Returns:
        PullRequestCreated for the newly created pull request.
    """

    def _full_ref(branch: str) -> str:
        return branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"

    opts = (
        completion_options if completion_options is not None else PrCompletionOptions()
    )
    body: dict[str, Any] = {
        "title": title,
        "sourceRefName": _full_ref(source_branch),
        "targetRefName": _full_ref(target_branch),
        "completionOptions": opts.model_dump(mode="json", by_alias=True),
    }
    if description is not None:
        body["description"] = description
    response = repository_api_call.post(
        "pullrequests",
        version="7.1-preview.1",
        json=body,
    )
    return PullRequestCreated.model_validate(response)
