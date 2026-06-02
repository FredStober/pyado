"""OOP wrapper for Azure DevOps pull request resources.

Provides the :class:`PullRequest` class, which wraps a single ADO pull
request and exposes its operations as methods rather than free functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from urllib.parse import quote
from uuid import UUID

from pydantic import TypeAdapter
from pydantic.networks import AnyUrl

from pyado import high, raw
from pyado.oop.work_item import WorkItem
from pyado.raw import (
    ApiCall,
    GitCommitRef,
    PullRequestCreated,
    PullRequestId,
    PullRequestIteration,
    PullRequestListItem,
    PullRequestReviewer,
    PullRequestStatus,
    PullRequestStatusContext,
    PullRequestStatusRequest,
    PullRequestStatusState,
    PullRequestThreadCommentResponse,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestUpdateRequest,
    PullRequestVote,
    WorkItemId,
)

__all__ = ["PullRequest"]


def _pr_artifact_url(project_id: UUID, repo_id: UUID, pr_id: PullRequestId) -> str:
    """Build the vstfs:// artifact URL that ADO uses to identify a pull request.

    Returns:
        A string of the form
        ``vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}``.
    """
    encoded = quote(f"{project_id}/{repo_id}/{pr_id}", safe="")
    return f"vstfs:///Git/PullRequestId/{encoded}"


class PullRequest:
    """An Azure DevOps pull request resource.

    Wraps a single ADO pull request and exposes its operations as instance
    methods.  Instances are normally obtained from
    :meth:`Repository.get_pr`, :meth:`Repository.iter_prs`, or
    :meth:`Repository.create_pr`.

    The ``info`` attribute holds either a :class:`~pyado.raw.PullRequestListItem`
    (when obtained via a list endpoint) or a :class:`~pyado.raw.PullRequestCreated`
    (when freshly created), reflecting the data available at construction time.

    Attributes:
        _api_call: PR-level API call used by all operations.
        _repo_api_call: Repository-level API call (needed for PR creation).
        _info: PR data; type depends on how the instance was constructed.
        _project_id: UUID of the containing project (used for artifact links).
        _repo_id: UUID of the containing repository (used for artifact links).
    """

    def __init__(
        self,
        pr_api_call: ApiCall,
        repo_api_call: ApiCall,
        info: PullRequestListItem | PullRequestCreated,
        project_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Construct a PullRequest wrapper.

        Args:
            pr_api_call: PR-level ADO API call (from raw.get_pr_api_call).
            repo_api_call: Repository-level ADO API call.
            info: PR data; either PullRequestListItem or PullRequestCreated.
            project_id: UUID of the project that owns this PR.
            repo_id: UUID of the repository that owns this PR.
        """
        self._api_call = pr_api_call
        self._repo_api_call = repo_api_call
        self._info = info
        self._project_id = project_id
        self._repo_id = repo_id

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> PullRequestListItem | PullRequestCreated:
        """Return the PR data fetched at construction time.

        Returns:
            Either PullRequestListItem or PullRequestCreated, depending on
            how this object was constructed.
        """
        return self._info

    def get_id(self) -> PullRequestId:
        """Return the numeric pull request ID.

        Returns:
            Integer pull request ID.
        """
        return self._info.pr_id

    # ------------------------------------------------------------------
    # Work item linking
    # ------------------------------------------------------------------

    def link_work_item(
        self,
        work_item: WorkItem,
        *,
        comment: str | None = None,
    ) -> None:
        """Link this pull request to a work item via an ArtifactLink relation.

        Adds the PR as an ``ArtifactLink`` relation on the work item so that
        the association appears in both the PR timeline and the work item links.

        Args:
            work_item: The WorkItem to link to this pull request.
            comment: Optional comment to attach to the relation.
        """
        artifact_url = _pr_artifact_url(
            self._project_id, self._repo_id, self._info.pr_id
        )
        high.add_artifact_link(work_item.get_api_call(), artifact_url, comment=comment)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self) -> list[str]:
        """Return the names of all labels set on the pull request.

        Returns:
            List of label name strings; empty when no labels are set.
        """
        return high.get_pr_labels(self._api_call)

    def add_label(self, name: str) -> None:
        """Add a label to the pull request.

        Args:
            name: Label name to add.
        """
        raw.post_pr_label(self._api_call, name)

    def remove_label(self, name: str) -> None:
        """Remove a label from the pull request.

        Args:
            name: Label name to remove.
        """
        raw.delete_pr_label(self._api_call, name)

    # ------------------------------------------------------------------
    # Threads and comments
    # ------------------------------------------------------------------

    def iter_threads(self) -> Iterator[PullRequestThreadResponse]:
        """Iterate over all review threads on the pull request.

        Yields:
            PullRequestThreadResponse for each thread.
        """
        yield from raw.iter_pr_threads(self._api_call)

    def add_thread(
        self,
        content: str,
        *,
        file_path: str | None = None,
        line: int | None = None,
        status: PullRequestThreadStatus = "active",
    ) -> PullRequestThreadResponse:
        """Create a new review thread on the pull request.

        Args:
            content: Text content of the first comment.
            file_path: File path to anchor the thread to, or ``None`` for a
                PR-level thread.
            line: Line number within the file; only meaningful when
                *file_path* is set.
            status: Initial thread status (default: ``"active"``).

        Returns:
            The created PullRequestThreadResponse.
        """
        return high.create_pr_thread(
            self._api_call,
            content,
            file_path=file_path,
            line=line,
            status=status,
        )

    def reply_to_thread(
        self,
        thread_id: int,
        content: str,
        *,
        parent_comment_id: int = 1,
    ) -> PullRequestThreadCommentResponse:
        """Add a reply to an existing review thread.

        Args:
            thread_id: ID of the thread to reply to.
            content: Text content of the reply.
            parent_comment_id: ID of the comment being replied to (default:
                ``1``, the thread's first comment).

        Returns:
            The created PullRequestThreadCommentResponse.
        """
        return high.reply_to_pr_thread(
            self._api_call,
            thread_id,
            content,
            parent_comment_id=parent_comment_id,
        )

    # ------------------------------------------------------------------
    # Reviewers
    # ------------------------------------------------------------------

    def get_reviewers(self) -> list[PullRequestReviewer]:
        """Return all reviewers on the pull request.

        Returns:
            List of PullRequestReviewer entries.
        """
        return raw.get_pr_reviewers(self._api_call)

    def add_reviewer(
        self,
        reviewer_id: str,
        *,
        is_required: bool = False,
        is_reapprove: bool = False,
    ) -> None:
        """Add or update a reviewer on the pull request.

        Args:
            reviewer_id: Identity (object) ID of the reviewer.
            is_required: When ``True`` the reviewer is marked as required.
            is_reapprove: When ``True``, the approval is processed even if
                the vote has not changed.
        """
        high.add_pr_reviewer(
            self._api_call,
            reviewer_id,
            is_required=is_required,
            is_reapprove=is_reapprove,
        )

    def remove_reviewer(self, reviewer_id: str) -> None:
        """Remove a reviewer from the pull request.

        Args:
            reviewer_id: Identity (object) ID of the reviewer.
        """
        raw.delete_pr_reviewer(self._api_call, reviewer_id)

    def vote(
        self,
        reviewer_id: str,
        vote: PullRequestVote,
        *,
        is_reapprove: bool = False,
    ) -> None:
        """Cast a reviewer vote on the pull request.

        Args:
            reviewer_id: Identity ID of the reviewer casting the vote.
            vote: Vote value to submit.
            is_reapprove: When ``True``, the approval is processed even if
                the vote has not changed.
        """
        high.set_pr_reviewer_vote(
            self._api_call, reviewer_id, vote, is_reapprove=is_reapprove
        )

    # ------------------------------------------------------------------
    # Metadata mutations
    # ------------------------------------------------------------------

    def update(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        status: PullRequestStatus | None = None,
        is_draft: bool | None = None,
    ) -> None:
        """Update pull request metadata.

        Only non-``None`` arguments are sent to ADO.

        Args:
            title: New PR title.
            description: New PR description.
            status: New PR status (``"active"``, ``"abandoned"``, or
                ``"completed"``).
            is_draft: Set or clear the draft flag.
        """
        raw.patch_pr(
            self._api_call,
            PullRequestUpdateRequest(
                title=title,
                description=description,
                status=status,
                is_draft=is_draft,
            ),
        )

    def set_status(
        self,
        state: PullRequestStatusState,
        context_name: str,
        *,
        description: str | None = None,
        iteration_id: PullRequestIteration = 1,
        target_url: str | None = None,
        genre: str | None = None,
    ) -> None:
        """Post a status check result on the pull request.

        Args:
            state: Status state to report.
            context_name: Unique name for the status context (e.g. the CI
                check name).
            description: Optional human-readable description.
            iteration_id: PR iteration the status applies to (default: 1).
            target_url: Optional URL to link to for details.
            genre: Optional genre grouping for the context.
        """
        url_value = (
            TypeAdapter(AnyUrl).validate_python(target_url) if target_url else None
        )
        raw.post_pr_status(
            self._api_call,
            PullRequestStatusRequest(
                context=PullRequestStatusContext(name=context_name, genre=genre),
                description=description,
                iteration_id=iteration_id,
                state=state,
                target_url=url_value,
            ),
        )

    # ------------------------------------------------------------------
    # Iteration access
    # ------------------------------------------------------------------

    def iter_commits(self) -> Iterator[GitCommitRef]:
        """Iterate over commits included in the pull request.

        Yields:
            GitCommitRef for each commit reachable from the PR.
        """
        yield from raw.iter_pr_commits(self._api_call)

    def iter_work_item_ids(self) -> Iterator[WorkItemId]:
        """Iterate over work item IDs linked to the pull request.

        Yields:
            Integer work item IDs associated with the PR.
        """
        yield from high.iter_pr_work_item_ids(self._api_call)
