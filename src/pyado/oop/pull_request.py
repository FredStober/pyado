"""OOP wrapper for Azure DevOps pull request resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pydantic import TypeAdapter
from pydantic.networks import AnyUrl

from pyado import high, raw
from pyado.raw import (
    ApiCall,
    CommitId,
    GitCommitRef,
    IdentityIdRef,
    PrIterationChange,
    PullRequestCompletionOptions,
    PullRequestCreated,
    PullRequestId,
    PullRequestIteration,
    PullRequestIterationRecord,
    PullRequestListItem,
    PullRequestReviewer,
    PullRequestStatus,
    PullRequestStatusContext,
    PullRequestStatusInfo,
    PullRequestStatusRequest,
    PullRequestStatusState,
    PullRequestThreadCommentResponse,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestUpdateRequest,
    PullRequestVote,
    WorkItemId,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.repository import Repository
    from pyado.oop.work_item import WorkItem

__all__ = ["PullRequest"]


class PullRequest:
    """An Azure DevOps pull request resource.

    Wraps a single ADO pull request and exposes its operations as instance
    methods.  Instances are obtained from :meth:`Repository.get_pr`,
    :meth:`Repository.iter_prs`, or :meth:`Repository.create_pr`.

    Pull requests are not cached — each factory call returns a fresh instance.
    Call :meth:`refresh` to re-fetch the info from the API at any time.

    The ``info`` attribute holds either a :class:`~pyado.raw.PullRequestListItem`
    (when obtained via a list endpoint) or a :class:`~pyado.raw.PullRequestCreated`
    (when freshly created), reflecting the data available at construction time.

    Attributes:
        _repo: The Repository this pull request belongs to.
        _api_call: PR-level API call used by all operations.
        _info: PR data; type depends on how the instance was constructed.
    """

    def __init__(
        self,
        repo: "Repository",
        pr_api_call: ApiCall,
        info: PullRequestListItem | PullRequestCreated,
    ) -> None:
        """Construct a PullRequest wrapper.

        Args:
            repo: The Repository that owns this pull request.
            pr_api_call: PR-level ADO API call (from raw.get_pr_api_call).
            info: PR data; either PullRequestListItem or PullRequestCreated.
        """
        self._repo = repo
        self._api_call = pr_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> PullRequestListItem | PullRequestCreated:
        """PR data captured at construction time (or last refresh)."""
        return self._info

    @property
    def id(self) -> PullRequestId:
        """Numeric pull request ID."""
        return self._info.pr_id

    @property
    def title(self) -> str | None:
        """Pull request title."""
        return self._info.title

    @property
    def status(self) -> str | None:
        """Pull request lifecycle status (e.g. ``"active"``, ``"completed"``)."""
        return self._info.status

    @property
    def source_branch(self) -> str | None:
        """Source ref name (e.g. ``"refs/heads/feature/my-branch"``)."""
        return self._info.source_ref_name

    @property
    def target_branch(self) -> str | None:
        """Target ref name (e.g. ``"refs/heads/main"``)."""
        return self._info.target_ref_name

    @property
    def description(self) -> str | None:
        """Pull request description body, or ``None`` if not set."""
        return self._info.description

    @property
    def created_by(self) -> str | None:
        """Display name of the user who created the PR, or ``None``.

        For the full identity (id, unique name), use ``pr.info.created_by``.
        """
        return self._info.created_by.display_name if self._info.created_by else None

    @property
    def api_call(self) -> ApiCall:
        """PR-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def repo(self) -> "Repository":
        """Repository this pull request belongs to — zero-cost."""
        return self._repo

    @property
    def project(self) -> "Project":
        """Project this pull request belongs to — zero-cost."""
        return self._repo.project

    @property
    def org(self) -> "Organization":
        """Organisation this pull request belongs to — zero-cost."""
        return self._repo.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch pull request info from the API immediately."""
        self._info = raw.get_pr_details(self._api_call)

    # ------------------------------------------------------------------
    # Work item linking
    # ------------------------------------------------------------------

    def link_work_item(
        self,
        work_item: "WorkItem",
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
        relation = high.WorkItemLink.pull_request(
            self._repo.info.project.id,
            self._repo.id,
            self._info.pr_id,
            comment=comment,
        )
        high.add_work_item_link(work_item.api_call, relation)

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
        status: PullRequestThreadStatus = PullRequestThreadStatus.ACTIVE,
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

    def complete(
        self,
        last_merge_source_commit: CommitId,
        *,
        completion_options: PullRequestCompletionOptions | None = None,
    ) -> None:
        """Complete (merge) the pull request.

        Args:
            last_merge_source_commit: Current HEAD SHA of the source branch.
                Used by ADO as an optimistic-concurrency guard; obtain it from
                ``pr.info.last_merge_source_commit.commit_id`` after a
                :meth:`refresh`.
            completion_options: Merge strategy and post-completion options.
                Defaults to squash merge with source-branch deletion.
        """
        self._info = high.complete_pr(
            self._api_call,
            last_merge_source_commit,
            completion_options=completion_options,
        )

    def abandon(self) -> None:
        """Abandon the pull request."""
        self._info = high.abandon_pr(self._api_call)

    def set_work_item_refs(self, work_item_ids: list[WorkItemId]) -> None:
        """Set the work items visible on the pull request page.

        Replaces the PR's ``workItemRefs`` list so the given work items appear
        in the ADO pull request UI.  To also add the reverse link on the work
        item side, call :meth:`link_work_item` for each item.

        Args:
            work_item_ids: Numeric IDs of the work items to associate.
        """
        high.update_pr_work_item_refs(self._api_call, work_item_ids)

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

    def iter_iterations(self) -> Iterator[PullRequestIterationRecord]:
        """Iterate over the push iterations of this pull request.

        Each iteration corresponds to a force-push or new commit push to the
        source branch.  Use :meth:`get_iteration_changes` to retrieve the
        file-level diff introduced by a specific iteration.

        Yields:
            PullRequestIterationRecord for each iteration, oldest first.
        """
        yield from raw.iter_pr_iterations(self._api_call)

    def get_iteration_changes(
        self,
        iteration_id: PullRequestIteration,
    ) -> list[PrIterationChange]:
        """Return the file changes introduced by a specific PR iteration.

        Args:
            iteration_id: The 1-based iteration number.  Obtain it from
                :meth:`iter_iterations`.

        Returns:
            List of PrIterationChange entries for the iteration.
        """
        return raw.get_pr_iteration_changes(self._api_call, iteration_id)

    def enable_auto_complete(
        self,
        identity_id: str,
        *,
        completion_options: PullRequestCompletionOptions | None = None,
    ) -> None:
        """Enable auto-complete on the pull request.

        When auto-complete is set, ADO will automatically complete (merge)
        the PR once all required reviewers have approved and all policies
        pass.

        Args:
            identity_id: Object ID of the identity to record as the
                auto-complete setter (typically the calling user's ID).
            completion_options: Merge strategy and post-completion options.
                When ``None``, ADO retains the existing options.
        """
        raw.patch_pr(
            self._api_call,
            PullRequestUpdateRequest(
                auto_complete_set_by=IdentityIdRef(id=identity_id),
                completion_options=completion_options,
            ),
        )

    def update_thread_status(
        self,
        thread_id: int,
        status: PullRequestThreadStatus,
    ) -> PullRequestThreadResponse:
        """Update the status of an existing review thread.

        Args:
            thread_id: Numeric ID of the thread to update.  Obtain it from
                :meth:`iter_threads`.
            status: New status for the thread (e.g.
                ``PullRequestThreadStatus.FIXED``).

        Returns:
            Updated PullRequestThreadResponse reflecting the new status.
        """
        return raw.patch_pr_thread(self._api_call, thread_id, status)

    def iter_statuses(self) -> Iterator[PullRequestStatusInfo]:
        """Iterate over status checks posted on this pull request.

        Yields:
            PullRequestStatusInfo for each status item, in API-returned order.
        """
        yield from raw.iter_pr_statuses(self._api_call)
