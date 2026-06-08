"""Higher-level wrappers for pull request operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado.oop.repos._git import _full_ref
from pyado.raw import (
    ApiCall,
    CommitId,
    CommitIdRef,
    JsonPatchAdd,
    PullRequestCompletionOptions,
    PullRequestCreateRequest,
    PullRequestResponse,
    PullRequestReviewerRequest,
    PullRequestReviewerVoteRequest,
    PullRequestStatus,
    PullRequestThreadCommentRequest,
    PullRequestThreadCommentResponse,
    PullRequestThreadCommentType,
    PullRequestThreadContext,
    PullRequestThreadPosition,
    PullRequestThreadRequest,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestUpdateRequest,
    PullRequestVote,
    WorkItemArtifactUrlPrefix,
    WorkItemId,
    WorkItemInfo,
    WorkItemRef,
    WorkItemRelationType,
    get_pull_request_details,
    get_pull_request_labels_details,
    get_work_item_api_call,
    patch_pull_request,
    patch_work_item,
    post_pull_request,
    post_pull_request_new_thread,
    post_pull_request_thread_comment,
    put_pull_request_reviewer,
    put_pull_request_reviewer_vote,
)
from pyado.raw import (
    iter_pull_request_work_item_ids as _iter_pr_work_item_ids,
)


def get_pull_request_tags(pr_api_call: ApiCall) -> list[str]:
    """Return the names of all tags currently set on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Returns:
        List of tag name strings.
    """
    return [label.name for label in get_pull_request_labels_details(pr_api_call)]


def iter_pull_request_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Iterate over work item IDs linked to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Yields:
        Integer work item IDs associated with the pull request.
    """
    for ref in _iter_pr_work_item_ids(pr_api_call):
        yield ref.id


def _project_from_api_call(api_call: ApiCall) -> str:
    """Extract the project name or ID from a project-level API call URL.

    Returns:
        The project name or UUID string embedded in the URL.
    """
    parts = (api_call.url.path or "").strip("/").split("/")
    return parts[1]


def link_pull_request_work_item(
    pr_api_call: ApiCall,
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
    *,
    comment: str | None = None,
) -> WorkItemInfo:
    """Link a work item to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        project_api_call: Project-level ADO API call.
        work_item_id: Numeric ID of the work item to link.
        comment: Optional comment to attach to the relation.

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    pr = get_pull_request_details(pr_api_call)
    project = _project_from_api_call(project_api_call)
    artifact_url = (
        f"{WorkItemArtifactUrlPrefix.PULL_REQUEST}/{project}"
        f"%2F{pr.repository.id}%2F{pr.pr_id}"
    )
    attributes: dict[str, str] = {"name": "Pull Request"}
    if comment is not None:
        attributes["comment"] = comment
    work_item_api_call = get_work_item_api_call(project_api_call, work_item_id)
    return patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": WorkItemRelationType.ARTIFACT_LINK,
                    "url": artifact_url,
                    "attributes": attributes,
                },
            )
        ],
    )


def create_pull_request_thread(
    pr_api_call: ApiCall,
    content: str,
    *,
    file_path: str | None = None,
    line: int | None = None,
    status: PullRequestThreadStatus = PullRequestThreadStatus.ACTIVE,
) -> PullRequestThreadResponse:
    """Create a new review thread on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        content: Text content of the first comment.
        file_path: File path to anchor the thread to, or None for PR-level.
        line: Line number within the file, used when file_path is set.
        status: Initial thread status (default: "active").

    Returns:
        The created PullRequestThreadResponse.

    Raises:
        ValueError: If ``line`` is given without ``file_path``.
    """
    if line is not None and file_path is None:
        err_msg = "line requires file_path to be set"
        raise ValueError(err_msg)
    thread_context: PullRequestThreadContext | None = None
    if file_path is not None:
        position = PullRequestThreadPosition(line=line or 1, offset=1)
        thread_context = PullRequestThreadContext.model_validate(
            {
                "filePath": file_path,
                "rightFileStart": position,
                "rightFileEnd": position,
            }
        )
    return post_pull_request_new_thread(
        pr_api_call,
        PullRequestThreadRequest(
            comments=[
                PullRequestThreadCommentRequest(
                    content=content,
                    comment_type=PullRequestThreadCommentType.TEXT,
                    parent_comment_id=0,
                )
            ],
            status=status,
            thread_context=thread_context,
        ),
    )


def reply_to_pull_request_thread(
    pr_api_call: ApiCall,
    thread_id: int,
    content: str,
    *,
    parent_comment_id: int = 1,
) -> PullRequestThreadCommentResponse:
    """Add a plain-text reply to an existing PR review thread.

    Args:
        pr_api_call: PR-level ADO API call.
        thread_id: ID of the thread to reply to.
        content: Text content of the reply.
        parent_comment_id: ID of the comment being replied to (default: 1).

    Returns:
        The created PullRequestThreadCommentResponse.
    """
    return post_pull_request_thread_comment(
        pr_api_call,
        thread_id,
        PullRequestThreadCommentRequest(
            content=content,
            comment_type=PullRequestThreadCommentType.TEXT,
            parent_comment_id=parent_comment_id,
        ),
    )


def create_pull_request(
    repository_api_call: ApiCall,
    title: str,
    source_branch: str,
    target_branch: str,
    *,
    description: str | None = None,
    completion_options: PullRequestCompletionOptions | None = None,
    work_item_ids: list[WorkItemId] | None = None,
) -> PullRequestResponse:
    """Create a new pull request.

    Args:
        repository_api_call: Repository-level ADO API call.
        title: Title of the pull request.
        source_branch: Source branch name.
        target_branch: Target branch name.
        description: Optional PR description.
        completion_options: Merge and post-completion behaviour.
        work_item_ids: Optional list of work item IDs to link at creation.

    Returns:
        PullRequestResponse for the newly created pull request.
    """
    opts = (
        completion_options
        if completion_options is not None
        else PullRequestCompletionOptions()
    )
    work_item_refs = (
        [WorkItemRef(id=wi_id) for wi_id in work_item_ids]
        if work_item_ids is not None
        else None
    )
    return post_pull_request(
        repository_api_call,
        PullRequestCreateRequest(
            title=title,
            source_ref_name=_full_ref(source_branch),
            target_ref_name=_full_ref(target_branch),
            completion_options=opts,
            description=description,
            work_item_refs=work_item_refs,
        ),
    )


def set_pull_request_reviewer_vote(
    pr_api_call: ApiCall,
    reviewer_id: str,
    vote: PullRequestVote,
    *,
    is_reapprove: bool = False,
) -> None:
    """Set a reviewer's vote on a pull request.

    Args:
        pr_api_call: PR-level ADO API call.
        reviewer_id: Identity ID of the reviewer.
        vote: Vote to cast.
        is_reapprove: When True, the approval is processed even if unchanged.
    """
    put_pull_request_reviewer_vote(
        pr_api_call,
        reviewer_id,
        PullRequestReviewerVoteRequest(vote=vote, is_reapprove=is_reapprove),
    )


def complete_pull_request(
    pr_api_call: ApiCall,
    last_merge_source_commit: CommitId,
    *,
    completion_options: PullRequestCompletionOptions | None = None,
) -> PullRequestResponse:
    """Complete (merge) a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        last_merge_source_commit: Current HEAD SHA of the source branch.
        completion_options: Merge strategy and post-completion options.

    Returns:
        PullRequestResponse populated with the PR state after completion.
    """
    opts = (
        completion_options
        if completion_options is not None
        else PullRequestCompletionOptions()
    )
    return patch_pull_request(
        pr_api_call,
        PullRequestUpdateRequest(
            status=PullRequestStatus.COMPLETED,
            last_merge_source_commit=CommitIdRef(commit_id=last_merge_source_commit),
            completion_options=opts,
        ),
    )


def abandon_pull_request(pr_api_call: ApiCall) -> PullRequestResponse:
    """Abandon a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).

    Returns:
        PullRequestResponse populated with the PR state after abandonment.
    """
    return patch_pull_request(
        pr_api_call,
        PullRequestUpdateRequest(status=PullRequestStatus.ABANDONED),
    )


def add_pull_request_reviewer(
    pr_api_call: ApiCall,
    reviewer_id: str,
    *,
    is_required: bool = False,
    is_reapprove: bool = False,
) -> None:
    """Add or update a reviewer on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        reviewer_id: Identity (object) ID of the reviewer.
        is_required: When True the reviewer is marked as required.
        is_reapprove: When True, the approval is processed even if unchanged.
    """
    put_pull_request_reviewer(
        pr_api_call,
        reviewer_id,
        PullRequestReviewerRequest(is_required=is_required, is_reapprove=is_reapprove),
    )


def update_pull_request_work_item_refs(
    pr_api_call: ApiCall,
    work_item_ids: list[WorkItemId],
) -> None:
    """Set the work items linked to a pull request (visible on the PR page).

    Args:
        pr_api_call: PR-level ADO API call (from get_pull_request_api_call).
        work_item_ids: Numeric IDs of the work items to associate.
    """
    patch_pull_request(
        pr_api_call,
        PullRequestUpdateRequest(
            work_item_refs=[WorkItemRef(id=wi_id) for wi_id in work_item_ids],
        ),
    )
