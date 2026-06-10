"""OOP wrapper for Azure DevOps pull request resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pydantic import TypeAdapter
from pydantic.networks import AnyUrl

from pyado import raw
from pyado.oop.boards import _work_item
from pyado.oop.repos import _pull_request
from pyado.oop.repos.commit import Commit
from pyado.raw import (
    ApiCall,
    CommitId,
    IdentityIdRef,
    PullRequestCompletionOptions,
    PullRequestId,
    PullRequestIteration,
    PullRequestIterationChange,
    PullRequestIterationRecord,
    PullRequestLabel,
    PullRequestListItem,
    PullRequestResponse,
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
    from pyado.oop.boards.work_item import WorkItem
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.repos.repository import Repository

__all__ = ["PullRequest"]


class PullRequest:
    """An Azure DevOps pull request resource.

    Wraps a single ADO pull request and exposes its operations as instance
    methods.  Instances are obtained from :meth:`Repository.get_pull_request`,
    :meth:`Repository.iter_pull_requests`, or
    :meth:`Repository.create_pull_request`.

    Pull requests are not cached — each factory call returns a fresh instance.
    Call :meth:`refresh` to re-fetch the info from the API at any time.

    The ``info`` attribute holds either a :class:`~pyado.raw.PullRequestListItem`
    (when obtained via a list endpoint) or a :class:`~pyado.raw.PullRequestResponse`
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
        info: PullRequestListItem | PullRequestResponse,
        expand: str | None = None,
    ) -> None:
        """Construct a PullRequest wrapper.

        Args:
            repo: The Repository that owns this pull request.
            pr_api_call: PR-level ADO API call (from raw.get_pull_request_api_call).
            info: PR data; either PullRequestListItem or PullRequestResponse.
            expand: The ``$expand`` value used when fetching *info*, stored so
                that :meth:`refresh` can re-use it by default.
        """
        self._repo = repo
        self._api_call = pr_api_call
        self._info: PullRequestListItem | PullRequestResponse | None = info
        self._expand = expand

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> PullRequestListItem | PullRequestResponse:
        """PR data captured at construction time (or last refresh)."""
        if self._info is None:
            self._info = raw.get_pull_request_details(
                self._api_call, expand=self._expand
            )
        return self._info

    @property
    def id(self) -> PullRequestId:
        """Numeric pull request ID."""
        return self.info.pr_id

    @property
    def title(self) -> str | None:
        """Pull request title."""
        return self.info.title

    @property
    def status(self) -> PullRequestStatus | None:
        """Pull request lifecycle status (e.g. ``"active"``, ``"completed"``)."""
        return self.info.status

    @property
    def source_branch(self) -> str | None:
        """Source ref name (e.g. ``"refs/heads/feature/my-branch"``)."""
        return self.info.source_ref_name

    @property
    def target_branch(self) -> str | None:
        """Target ref name (e.g. ``"refs/heads/main"``)."""
        return self.info.target_ref_name

    @property
    def description(self) -> str | None:
        """Pull request description body, or ``None`` if not set."""
        return self.info.description

    @property
    def created_by(self) -> str | None:
        """Display name of the user who created the PR, or ``None``.

        For the full identity (id, unique name), use ``pr.info.created_by``.
        """
        return self.info.created_by.display_name if self.info.created_by else None

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

    def refresh(self, expand: str | None = None) -> None:
        """Discard cached pull request info.

        The next access to :attr:`info` re-fetches from the API.

        Args:
            expand: ``$expand`` value to use on the next fetch.  When ``None``
                (default), re-uses the expand value from construction or the
                last explicit refresh call.  When provided, updates the stored
                expand so subsequent bare :meth:`refresh` calls use it.
        """
        if expand is not None:
            self._expand = expand
        self._info = None

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
        relation = _work_item.WorkItemLink.pull_request(
            self._repo.info.project.id,
            self._repo.id,
            self.info.pr_id,
            comment=comment,
        )
        _work_item.add_work_item_link(work_item.api_call, relation)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def iter_tags(self) -> Iterator[str]:
        """Iterate over the tag names set on the pull request.

        Yields:
            Tag name strings; nothing when no tags are set.
        """
        yield from _pull_request.get_pull_request_tags(self._api_call)

    def iter_tag_details(self) -> Iterator[PullRequestLabel]:
        """Iterate over full tag objects for all tags set on the pull request.

        Use this instead of :meth:`iter_tags` when you need the tag ID,
        URL, or active status, not just the name string.

        Yields:
            PullRequestLabel for each tag set on the pull request.
        """
        yield from raw.get_pull_request_labels_details(self._api_call)

    def list_tag_details(self) -> list[PullRequestLabel]:
        """Return full tag objects for all tags set on the pull request."""
        return list(self.iter_tag_details())

    def add_tag(self, name: str) -> None:
        """Add a tag to the pull request.

        Args:
            name: Tag name to add.

        Note:
            The ADO tag endpoints return no body, so this method returns
            ``None``.  Call :meth:`get_tags` afterwards if you need the
            updated tag list.
        """
        raw.post_pull_request_label(self._api_call, name)

    def remove_tag(self, name: str) -> None:
        """Remove a tag from the pull request.

        Args:
            name: Tag name to remove.

        Note:
            The ADO tag endpoints return no body, so this method returns
            ``None``.  Call :meth:`get_tags` afterwards if you need the
            updated tag list.
        """
        raw.delete_pull_request_label(self._api_call, name)

    def sync_tags(self, desired: set[str]) -> None:
        """Synchronise the PR tags to match *desired*.

        Adds missing tags and removes extras so the final set matches
        *desired* exactly.  When the object was constructed or last refreshed
        with an ``expand`` that includes ``"labels"``, the tags cached in
        ``_info`` are used and the GET /labels call is skipped entirely.

        Args:
            desired: The exact set of tag names the PR should have after
                the call.
        """
        if self._expand and "labels" in self._expand.split(","):
            current = {label.name for label in self.info.labels}
        else:
            current = set(self.iter_tags())
        to_add = desired - current
        to_remove = current - desired
        if not to_add and not to_remove:
            return
        for tag in to_add:
            self.add_tag(tag)
        for tag in to_remove:
            self.remove_tag(tag)

    # ------------------------------------------------------------------
    # Threads and comments
    # ------------------------------------------------------------------

    def iter_threads(self) -> Iterator[PullRequestThreadResponse]:
        """Iterate over all review threads on the pull request.

        Yields:
            PullRequestThreadResponse for each thread.
        """
        yield from raw.iter_pull_request_threads(self._api_call)

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
        return _pull_request.create_pull_request_thread(
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
        return _pull_request.reply_to_pull_request_thread(
            self._api_call,
            thread_id,
            content,
            parent_comment_id=parent_comment_id,
        )

    # ------------------------------------------------------------------
    # Reviewers
    # ------------------------------------------------------------------

    def list_reviewers(self) -> list[PullRequestReviewer]:
        """Return all reviewers on the pull request.

        Returns:
            List of PullRequestReviewer entries.
        """
        return raw.get_pull_request_reviewers(self._api_call)

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
        _pull_request.add_pull_request_reviewer(
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
        raw.delete_pull_request_reviewer(self._api_call, reviewer_id)

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
        _pull_request.set_pull_request_reviewer_vote(
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
        self._info = raw.patch_pull_request(
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
        self._info = _pull_request.complete_pull_request(
            self._api_call,
            last_merge_source_commit,
            completion_options=completion_options,
        )

    def abandon(self) -> None:
        """Abandon the pull request."""
        self._info = _pull_request.abandon_pull_request(self._api_call)

    def set_work_item_refs(self, work_item_ids: list[WorkItemId]) -> None:
        """Set the work items visible on the pull request page.

        Replaces the PR's ``workItemRefs`` list so the given work items appear
        in the ADO pull request UI.  To also add the reverse link on the work
        item side, call :meth:`link_work_item` for each item.

        Args:
            work_item_ids: Numeric IDs of the work items to associate.
        """
        _pull_request.update_pull_request_work_item_refs(self._api_call, work_item_ids)

    def add_work_item_ref(self, wi_id: WorkItemId) -> None:
        """Add a single work item to the pull request's work item refs.

        Reads the current work item refs, adds *wi_id* if not already present,
        and writes the updated list back.  The operation is idempotent — if
        *wi_id* is already linked, no PATCH is made.

        This wraps :meth:`iter_work_item_ids` and :meth:`set_work_item_refs`:
        two API calls (one GET, one PATCH) when the item is not yet linked;
        one API call (GET only) when it is already present.

        Args:
            wi_id: Numeric ID of the work item to add.
        """
        current = list(self.iter_work_item_ids())
        if wi_id not in current:
            self.set_work_item_refs([*current, wi_id])

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
        raw.post_pull_request_status(
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

    def iter_commits(self) -> Iterator[Commit]:
        """Iterate over commits included in the pull request.

        Yields:
            Commit for each commit reachable from the PR.
        """
        for ref in raw.iter_pull_request_commits(self._api_call):
            yield Commit(self._repo, ref)

    def iter_work_item_ids(self) -> Iterator[WorkItemId]:
        """Iterate over work item IDs linked to the pull request.

        Yields:
            Integer work item IDs associated with the PR.
        """
        yield from _pull_request.iter_pull_request_work_item_ids(self._api_call)

    def iter_work_items(self) -> "Iterator[WorkItem]":
        """Iterate over work items linked to the pull request.

        Convenience wrapper that resolves the linked IDs via
        :meth:`iter_work_item_ids` and then fetches the work item details in
        a single batch call.

        Yields:
            WorkItem for each linked work item.
        """
        ids = list(self.iter_work_item_ids())
        if ids:
            yield from self._repo.project.boards.list_work_items_by_ids(ids)

    def iter_iterations(self) -> Iterator[PullRequestIterationRecord]:
        """Iterate over the push iterations of this pull request.

        Each iteration corresponds to a force-push or new commit push to the
        source branch.  Use :meth:`get_iteration_changes` to retrieve the
        file-level diff introduced by a specific iteration.

        Yields:
            PullRequestIterationRecord for each iteration, oldest first.
        """
        yield from raw.iter_pull_request_iterations(self._api_call)

    def get_iteration_changes(
        self,
        iteration_id: PullRequestIteration,
    ) -> list[PullRequestIterationChange]:
        """Return the file changes introduced by a specific PR iteration.

        Args:
            iteration_id: The 1-based iteration number.  Obtain it from
                :meth:`iter_iterations`.

        Returns:
            List of PullRequestIterationChange entries for the iteration.
        """
        return raw.get_pull_request_iteration_changes(self._api_call, iteration_id)

    def iter_files_changed(self) -> Iterator[PullRequestIterationChange]:
        """Iterate over files changed in this pull request.

        Fetches the latest iteration (one API call) and then returns its
        changes, which represent the full diff from the merge base to the
        current source branch HEAD.  This is the equivalent of the "Files"
        tab in the ADO pull request UI.

        Yields:
            PullRequestIterationChange for each changed file.
        """
        iterations = list(self.iter_iterations())
        if not iterations:
            return
        last_id = max(it.id for it in iterations)
        yield from self.get_iteration_changes(last_id)

    def enable_auto_complete(
        self,
        identity_id: str | None = None,
        *,
        completion_options: PullRequestCompletionOptions | None = None,
    ) -> None:
        """Enable auto-complete on the pull request.

        When auto-complete is set, ADO will automatically complete (merge)
        the PR once all required reviewers have approved and all policies
        pass.

        Args:
            identity_id: Object ID of the identity to record as the
                auto-complete setter.  When ``None`` (the default), the
                authenticated user's identity is resolved via
                ``get_connection_data`` and used automatically.
            completion_options: Merge strategy and post-completion options.
                When ``None``, ADO retains the existing options.
        """
        resolved_id = (
            identity_id
            if identity_id is not None
            else self.org.get_connection_data().authenticated_user.id
        )
        raw.patch_pull_request(
            self._api_call,
            PullRequestUpdateRequest(
                auto_complete_set_by=IdentityIdRef(id=resolved_id),
                completion_options=completion_options,
            ),
        )

    def disable_auto_complete(self) -> None:
        """Disable auto-complete on the pull request.

        Clears the auto-complete setter so the PR will no longer be merged
        automatically when policies pass.  Has no effect if auto-complete
        was not set.  ADO requires an all-zeros GUID to unset auto-complete.
        """
        raw.patch_pull_request(
            self._api_call,
            PullRequestUpdateRequest(
                auto_complete_set_by=IdentityIdRef(
                    id="00000000-0000-0000-0000-000000000000"
                ),
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
        return raw.patch_pull_request_thread(self._api_call, thread_id, status)

    def get_thread(self, thread_id: int) -> PullRequestThreadResponse:
        """Return a single review thread by ID.

        Args:
            thread_id: Numeric ID of the thread to fetch.  Obtain it from
                :meth:`iter_threads`.

        Returns:
            PullRequestThreadResponse for the requested thread.
        """
        return raw.get_pull_request_thread(self._api_call, thread_id)

    def iter_statuses(self) -> Iterator[PullRequestStatusInfo]:
        """Iterate over status checks posted on this pull request.

        Yields:
            PullRequestStatusInfo for each status item, in API-returned order.
        """
        yield from raw.iter_pull_request_statuses(self._api_call)

    def list_tags(self) -> list[str]:
        """Return all tag names set on this pull request as a list."""
        return list(self.iter_tags())

    def list_threads(self) -> list[PullRequestThreadResponse]:
        """Return all review threads on this pull request as a list."""
        return list(self.iter_threads())

    def list_commits(self) -> list[Commit]:
        """Return all commits in this pull request as a list."""
        return list(self.iter_commits())

    def list_work_item_ids(self) -> list[WorkItemId]:
        """Return all linked work item IDs as a list."""
        return list(self.iter_work_item_ids())

    def list_work_items(self) -> "list[WorkItem]":
        """Return all linked work items as a list."""
        return list(self.iter_work_items())

    def list_iterations(self) -> list[PullRequestIterationRecord]:
        """Return all iterations for this pull request as a list."""
        return list(self.iter_iterations())

    def list_files_changed(self) -> list[PullRequestIterationChange]:
        """Return all files changed in this pull request as a list."""
        return list(self.iter_files_changed())

    def list_statuses(self) -> list[PullRequestStatusInfo]:
        """Return all status checks on this pull request as a list."""
        return list(self.iter_statuses())
