"""Higher-level wrappers for pull request operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado.high.git import _full_ref
from pyado.raw import (
    ApiCall,
    CommitId,
    PullRequestCompletionOptions,
    PullRequestCreated,
    PullRequestCreateRequest,
    PullRequestListItem,
    PullRequestReviewerRequest,
    PullRequestReviewerVoteRequest,
    PullRequestSearchCriteria,
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
    WorkItemRelationType,
    get_pr_details,
    get_pr_labels_details,
    get_work_item_api_call,
    iter_prs,
    patch_pr,
    patch_work_item,
    post_pr_new_thread,
    post_pr_thread_comment,
    post_pull_request,
    put_pr_reviewer,
    put_pr_reviewer_vote,
)
from pyado.raw import (
    iter_pr_work_item_ids as _iter_pr_work_item_ids,
)

__all__ = [
    "abandon_pr",
    "add_pr_reviewer",
    "complete_pr",
    "create_pr",
    "create_pr_thread",
    "get_pr_labels",
    "iter_open_prs",
    "iter_pr_work_item_ids",
    "link_pr_work_item",
    "reply_to_pr_thread",
    "set_pr_reviewer_vote",
]


def iter_open_prs(project_api_call: ApiCall) -> Iterator[PullRequestListItem]:
    """Iterate over all active pull requests in the project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        PullRequestListItem for each active pull request.
    """
    yield from iter_prs(
        project_api_call,
        PullRequestSearchCriteria(status=PullRequestStatus.ACTIVE),
    )


def get_pr_labels(pr_api_call: ApiCall) -> list[str]:
    """Return the names of all labels currently set on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        List of label name strings.
    """
    return [label.name for label in get_pr_labels_details(pr_api_call)]


def iter_pr_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Iterate over work item IDs linked to a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Yields:
        Integer work item IDs associated with the pull request.
    """
    for ref in _iter_pr_work_item_ids(pr_api_call):
        yield ref.id


def _project_from_api_call(api_call: ApiCall) -> str:
    """Extract the project name or ID from a project-level API call URL.

    ADO does not expose a project-info endpoint reachable from a project-level
    URL, so the project identifier is read directly from the URL path.  The
    ADO URL convention is stable across hosted and on-premises instances:

    * Hosted:    ``https://dev.azure.com/{org}/{project}/_apis/...``
    * On-prem:   ``https://{server}/{collection}/{project}/_apis/...``

    In both cases the project occupies the second path segment (index 1 after
    stripping the leading slash).  ADO accepts either a project name or a
    project UUID in artifact URLs, so whichever form is present in the URL
    will work.

    Returns:
        The project name or UUID string embedded in the URL.
    """
    parts = (api_call.url.path or "").strip("/").split("/")
    return parts[1]


def link_pr_work_item(
    pr_api_call: ApiCall,
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
    *,
    comment: str | None = None,
) -> WorkItemInfo:
    """Link a work item to a pull request.

    Reads the repository ID and PR ID from the PR itself and derives the
    project identifier from the ``project_api_call`` URL path (see
    :func:`_project_from_api_call`), then adds an ``ArtifactLink`` relation on
    the work item.  After this call the work item appears in the PR's linked
    work items list (``iter_pr_work_item_ids``).

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        project_api_call: Project-level ADO API call.  Used both to build
            the work item API call and to derive the project identifier for
            the artifact URL.  The project name or UUID is read from the
            second path segment of the URL
            (``/{org}/{project}/_apis/...``); no separate REST call is made
            to resolve it.
        work_item_id: Numeric ID of the work item to link.
        comment: Optional comment to attach to the relation.

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    pr = get_pr_details(pr_api_call)
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
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": WorkItemRelationType.ARTIFACT_LINK,
                    "url": artifact_url,
                    "attributes": attributes,
                },
            }
        ],
    )


def create_pr_thread(
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
    return post_pr_new_thread(
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


def reply_to_pr_thread(
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
        parent_comment_id: ID of the comment being replied to (default: 1,
            the first comment in the thread).

    Returns:
        The created PullRequestThreadCommentResponse.
    """
    return post_pr_thread_comment(
        pr_api_call,
        thread_id,
        PullRequestThreadCommentRequest(
            content=content,
            comment_type=PullRequestThreadCommentType.TEXT,
            parent_comment_id=parent_comment_id,
        ),
    )


def create_pr(
    repository_api_call: ApiCall,
    title: str,
    source_branch: str,
    target_branch: str,
    *,
    description: str | None = None,
    completion_options: PullRequestCompletionOptions | None = None,
    work_item_ids: list[WorkItemId] | None = None,
) -> PullRequestCreated:
    """Create a new pull request.

    Args:
        repository_api_call: Repository-level ADO API call (from
            get_repository_api_call in pyado.raw.api).
        title: Title of the pull request.
        source_branch: Source branch name (e.g. ``"feature/my-branch"`` or
            full ``"refs/heads/feature/my-branch"``).
        target_branch: Target branch name (e.g. ``"main"``).
        description: Optional PR description.
        completion_options: Merge and post-completion behaviour; defaults to
            squash merge with source-branch deletion.
        work_item_ids: Optional list of work item IDs to link to the PR at
            creation time.  This uses the same API mechanism as the ADO UI;
            the linked items are immediately visible via iter_pr_work_item_ids.

    Returns:
        PullRequestCreated for the newly created pull request.
    """
    opts = (
        completion_options
        if completion_options is not None
        else PullRequestCompletionOptions()
    )
    work_item_refs = (
        [{"id": str(wi_id)} for wi_id in work_item_ids]
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


def set_pr_reviewer_vote(
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
        is_reapprove: When True, the approval is processed even if the vote
            has not changed since the last submission.
    """
    put_pr_reviewer_vote(
        pr_api_call,
        reviewer_id,
        PullRequestReviewerVoteRequest(vote=vote, is_reapprove=is_reapprove),
    )


def complete_pr(
    pr_api_call: ApiCall,
    last_merge_source_commit: CommitId,
    *,
    completion_options: PullRequestCompletionOptions | None = None,
) -> PullRequestCreated:
    """Complete (merge) a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        last_merge_source_commit: Current HEAD SHA of the source branch.
            ADO uses this as an optimistic-concurrency guard; obtain it from
            ``get_pr_details(pr_api_call).last_merge_source_commit.commit_id``.
        completion_options: Merge strategy and post-completion options.
            Defaults to squash merge with source-branch deletion.

    Returns:
        PullRequestCreated populated with the PR state after completion.
    """
    opts = (
        completion_options
        if completion_options is not None
        else PullRequestCompletionOptions()
    )
    return patch_pr(
        pr_api_call,
        PullRequestUpdateRequest(
            status=PullRequestStatus.COMPLETED,
            last_merge_source_commit={"commitId": last_merge_source_commit},
            completion_options=opts,
        ),
    )


def abandon_pr(pr_api_call: ApiCall) -> PullRequestCreated:
    """Abandon a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).

    Returns:
        PullRequestCreated populated with the PR state after abandonment.
    """
    return patch_pr(
        pr_api_call,
        PullRequestUpdateRequest(status=PullRequestStatus.ABANDONED),
    )


def add_pr_reviewer(
    pr_api_call: ApiCall,
    reviewer_id: str,
    *,
    is_required: bool = False,
    is_reapprove: bool = False,
) -> None:
    """Add or update a reviewer on a pull request.

    Args:
        pr_api_call: PR-level ADO API call (from get_pr_api_call).
        reviewer_id: Identity (object) ID of the reviewer.
        is_required: When True the reviewer is marked as required.
        is_reapprove: When True, the approval is processed even if the vote
            has not changed since the last submission.
    """
    put_pr_reviewer(
        pr_api_call,
        reviewer_id,
        PullRequestReviewerRequest(is_required=is_required, is_reapprove=is_reapprove),
    )
