"""OOP wrapper for Azure DevOps work item resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.boards import _work_item
from pyado.raw import (
    ApiCall,
    CommitId,
    TextFormat,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemExpand,
    WorkItemField,
    WorkItemFieldName,
    WorkItemId,
    WorkItemInfo,
    WorkItemRelation,
    WorkItemRelationType,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.pipelines.build import Build
    from pyado.oop.project import Project
    from pyado.oop.repos.pull_request import PullRequest
    from pyado.oop.repos.repository import Repository

__all__ = ["WorkItem"]

_WI_ARTIFACT_RELS = {
    WorkItemRelationType.ARTIFACT_LINK,
    WorkItemRelationType.ATTACHED_FILE,
    WorkItemRelationType.HYPERLINK,
}


def _is_wi_relation(relation: WorkItemRelation) -> bool:
    """Return True when relation links to another work item (not an artifact)."""
    return relation.rel not in _WI_ARTIFACT_RELS


def _wi_id_from_url(url: str) -> WorkItemId:
    """Extract the numeric work item ID from a relation URL.

    ADO work item relation URLs have the form
    ``https://dev.azure.com/{org}/{proj}/_apis/wit/workItems/{id}``.

    Returns:
        Numeric work item ID.
    """
    return int(url.rstrip("/").rsplit("/", 1)[-1])


class WorkItem:
    """An Azure DevOps work item resource.

    Wraps a single ADO work item and exposes its operations as instance
    methods.  Instances are obtained from :meth:`ProjectBoards.get_work_item`,
    :meth:`ProjectBoards.iter_work_items`, or
    :meth:`ProjectBoards.create_work_item`.

    Work items are not cached — each factory call returns a fresh instance
    with the current API state. Call :meth:`refresh` to re-fetch the info
    from the API at any time.

    Attributes:
        _project: The Project this work item belongs to.
        _api_call: Work-item-level API call used by all operations.
        _info: The work item data returned from the API at construction time.
    """

    def __init__(
        self,
        project: "Project",
        work_item_api_call: ApiCall,
        info: WorkItemInfo,
        expand: WorkItemExpand | None = None,
    ) -> None:
        """Construct a WorkItem wrapper.

        Args:
            project: The Project that owns this work item.
            work_item_api_call: Work-item-level ADO API call (from
                raw.get_work_item_api_call).
            info: Work item data as returned from the API.
            expand: The expand mode used when fetching *info*, stored so that
                :meth:`refresh` can re-use it by default.
        """
        self._project = project
        self._api_call = work_item_api_call
        self._info: WorkItemInfo | None = info
        self._expand = expand

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> WorkItemInfo:
        """Work item data captured at construction time (or last refresh)."""
        if self._info is None:
            self._info = raw.get_work_item(self._api_call, expand=self._expand)
        return self._info

    @property
    def id(self) -> WorkItemId:
        """Numeric work item ID."""
        return self.info.id

    @property
    def title(self) -> str | None:
        """Value of the ``System.Title`` field, or ``None`` if absent."""
        return self.info.fields.get("System.Title")

    @property
    def state(self) -> str | None:
        """Value of the ``System.State`` field, or ``None`` if absent."""
        return self.info.fields.get("System.State")

    @property
    def type(self) -> str | None:
        """Value of the ``System.WorkItemType`` field, or ``None`` if absent."""
        return self.info.fields.get("System.WorkItemType")

    @property
    def assigned_to(self) -> Any:
        """Value of the ``System.AssignedTo`` field (identity dict), or ``None``."""
        return self.info.fields.get("System.AssignedTo")

    @property
    def area_path(self) -> str | None:
        """Value of the ``System.AreaPath`` field, or ``None`` if absent."""
        return self.info.fields.get("System.AreaPath")

    @property
    def iteration_path(self) -> str | None:
        """Value of the ``System.IterationPath`` field, or ``None`` if absent."""
        return self.info.fields.get("System.IterationPath")

    @property
    def api_call(self) -> ApiCall:
        """Work-item-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this work item belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this work item belongs to — zero-cost."""
        return self._project.org

    def get_field(self, field: WorkItemField) -> Any:
        """Return the current value of a work item field.

        Args:
            field: Field reference name, e.g. ``"System.Title"``.

        Returns:
            The field value, or ``None`` if the field is absent.
        """
        return self.info.fields.get(field)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, expand: WorkItemExpand | None = None) -> None:
        """Discard cached work item info.

        The next access to :attr:`info` re-fetches from the API.

        Args:
            expand: Expand mode to use on the next fetch.  When ``None``
                (default), re-uses the expand value from construction or the
                last explicit refresh call.  When provided, updates the stored
                expand so subsequent bare :meth:`refresh` calls use it.
        """
        if expand is not None:
            self._expand = expand
        self._info = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update(
        self,
        fields: dict[WorkItemField, Any],
        *,
        multiline_fields_format: dict[WorkItemField, TextFormat] | None = None,
    ) -> None:
        """Update work item fields.

        Args:
            fields: Mapping of field reference names to new values.
            multiline_fields_format: Optional per-field format override
                (``"html"`` or ``"markdown"``).
        """
        self._info = _work_item.update_work_item(
            self._api_call,
            fields,
            multiline_fields_format=multiline_fields_format,
        )

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def iter_tags(self) -> Iterator[str]:
        """Iterate over the tags currently set on the work item.

        Yields:
            Tag name strings; nothing when no tags are set.
        """
        yield from _work_item.get_work_item_tags(self._api_call)

    def add_tag(self, tag: str) -> list[str]:
        """Add a tag to the work item.

        If the tag is already present the work item is not modified.

        Args:
            tag: Tag name to add.

        Returns:
            Updated list of tag name strings.
        """
        return _work_item.add_work_item_tag(self._api_call, tag)

    def remove_tag(self, tag: str) -> list[str]:
        """Remove a tag from the work item.

        If the tag is not present the work item is not modified.

        Args:
            tag: Tag name to remove.

        Returns:
            Updated list of tag name strings.
        """
        return _work_item.remove_work_item_tag(self._api_call, tag)

    def sync_tags(self, desired: set[str]) -> None:
        """Synchronise work item tags to match *desired* exactly.

        Adds missing tags and removes extras so the final set matches
        *desired* exactly.  Does nothing when the current tags already match.

        Args:
            desired: The exact set of tag names the work item should have
                after the call.
        """
        _work_item.sync_work_item_tags(self._api_call, desired)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def iter_comments(self) -> Iterator[WorkItemComment]:
        """Iterate over comments on the work item.

        Yields:
            WorkItemComment for each comment, in API-returned order.
        """
        yield from raw.iter_work_item_comments(self._api_call)

    def add_comment(
        self, text: str, *, comment_format: TextFormat = TextFormat.HTML
    ) -> WorkItemComment:
        """Add a comment to the work item.

        Args:
            text: Comment body text (HTML or Markdown depending on format).
            comment_format: Format of the comment body — ``"html"`` (default)
                or ``"markdown"``.

        Returns:
            The created WorkItemComment.
        """
        return raw.post_work_item_comment(
            self._api_call, text, comment_format=comment_format
        )

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def add_attachment(self, filename: str, content: bytes) -> WorkItemAttachmentRef:
        """Upload a file and attach it to the work item.

        Args:
            filename: Name of the file as it will appear in ADO.
            content: Raw bytes of the file to upload.

        Returns:
            WorkItemAttachmentRef with the ID and URL of the uploaded file.
        """
        return _work_item.add_work_item_attachment(
            self._project.api_call, self.info.id, filename, content
        )

    def download_attachment(self, ref: WorkItemAttachmentRef) -> bytes:
        """Download the raw bytes of an uploaded attachment.

        Args:
            ref: The WorkItemAttachmentRef returned by :meth:`add_attachment`
                or :meth:`iter_attachments`.

        Returns:
            Raw file bytes.
        """
        return raw.get_work_item_attachment_bytes(self._project.api_call, ref.id)

    # ------------------------------------------------------------------
    # Linking
    # ------------------------------------------------------------------

    def add_link(
        self,
        other: "WorkItem",
        link_type: WorkItemRelationType,
        *,
        comment: str | None = None,
    ) -> None:
        """Link this work item to another with the specified relation type.

        Covers all work-item-to-work-item relation types (parent, child,
        related, successor, predecessor, duplicate, etc.).  For artifact
        links (PRs, builds, commits) use the dedicated helpers instead.

        Args:
            other: Target WorkItem to link to.
            link_type: Relation type to create (e.g.
                ``WorkItemRelationType.PARENT``).
            comment: Optional comment to attach to the relation.
        """
        relation = _work_item.WorkItemLink.wi_link(
            link_type, other.project.api_call, other.id, comment
        )
        _work_item.add_work_item_link(self._api_call, relation)

    def create_child(
        self,
        work_item_type: str,
        title: str,
        extra_fields: dict[WorkItemField, Any] | None = None,
        *,
        multiline_fields_format: dict[WorkItemField, TextFormat] | None = None,
    ) -> "WorkItem":
        """Create a new work item and link it as a child of this one.

        Creates a new work item of *work_item_type*, sets *title* (and any
        *extra_fields*), then adds a parent link from the new item back to
        ``self``.

        Args:
            work_item_type: Work item type name (e.g. ``"Task"``).
            title: Title for the new work item.
            extra_fields: Additional fields to set on the new work item.
            multiline_fields_format: Optional per-field format override
                forwarded to :meth:`ProjectBoards.create_work_item`.

        Returns:
            The newly created child :class:`WorkItem`.
        """
        fields: dict[WorkItemField, Any] = {
            WorkItemFieldName.TITLE: title,
            **(extra_fields or {}),
        }
        child = self._project.boards.create_work_item(
            work_item_type,
            fields,
            multiline_fields_format=multiline_fields_format,
        )
        child.add_link(self, WorkItemRelationType.PARENT)
        return child

    def link_pull_request(
        self,
        pr: "PullRequest",
        *,
        comment: str | None = None,
    ) -> None:
        """Link this work item to a pull request via an ArtifactLink relation.

        Args:
            pr: The PullRequest to link.
            comment: Optional comment to attach to the relation.
        """
        relation = _work_item.WorkItemLink.pull_request(
            pr.repo.info.project.id,
            pr.repo.id,
            pr.id,
            comment=comment,
        )
        _work_item.add_work_item_link(self._api_call, relation)

    def link_build(
        self,
        build: "Build",
        *,
        comment: str | None = None,
    ) -> None:
        """Link this work item to a build via an ArtifactLink relation.

        Args:
            build: The Build to link.
            comment: Optional comment to attach to the relation.
        """
        relation = _work_item.WorkItemLink.build(build.id, comment=comment)
        _work_item.add_work_item_link(self._api_call, relation)

    def link_commit(
        self,
        repo: "Repository",
        commit_id: CommitId,
        *,
        comment: str | None = None,
    ) -> None:
        """Link this work item to a git commit via an ArtifactLink relation.

        Args:
            repo: The Repository the commit belongs to.
            commit_id: Commit SHA string.
            comment: Optional comment to attach to the relation.
        """
        relation = _work_item.WorkItemLink.commit(
            repo.info.project.id,
            repo.id,
            commit_id,
            comment=comment,
        )
        _work_item.add_work_item_link(self._api_call, relation)

    # ------------------------------------------------------------------
    # Relation navigation
    # ------------------------------------------------------------------

    def iter_relations(
        self,
        rel_type: WorkItemRelationType | None = None,
    ) -> Iterator[WorkItemRelation]:
        """Iterate over all relations on this work item.

        Returns every relation regardless of type — work item links,
        artifact links (PRs, builds, commits), attached files, and
        hyperlinks.  Filter by *rel_type* to narrow the result.

        Requires the info to have been fetched with
        ``expand=WorkItemExpand.RELATIONS`` (the default for
        :meth:`ProjectBoards.get_work_item`).

        Args:
            rel_type: When provided, only relations of this type are yielded.
                When ``None``, all relation types are returned.

        Yields:
            WorkItemRelation for each matching relation.
        """
        for relation in self.info.relations:
            if rel_type is None or relation.rel == rel_type:
                yield relation

    def iter_artifact_links(self) -> Iterator[WorkItemRelation]:
        """Iterate over artifact link relations (PRs, builds, commits).

        Convenience filter around :meth:`iter_relations` for
        ``WorkItemRelationType.ARTIFACT_LINK``.

        Yields:
            WorkItemRelation for each artifact link.
        """
        yield from self.iter_relations(WorkItemRelationType.ARTIFACT_LINK)

    def iter_attachments(self) -> Iterator[WorkItemAttachmentRef]:
        """Iterate over attached-file relations as attachment references.

        Convenience filter around :meth:`iter_relations` for
        ``WorkItemRelationType.ATTACHED_FILE``.  The attachment ID is
        extracted from each relation URL so the result can be passed
        directly to :meth:`download_attachment`.

        Yields:
            WorkItemAttachmentRef for each attached file.
        """
        for relation in self.iter_relations(WorkItemRelationType.ATTACHED_FILE):
            attachment_id = relation.url.split("/")[-1].split("?")[0]
            yield WorkItemAttachmentRef.model_validate(
                {"id": attachment_id, "url": relation.url}
            )

    def iter_revisions(self) -> Iterator[WorkItemInfo]:
        """Iterate over all historical revisions of this work item, oldest first.

        Each revision is a full snapshot of the work item at that point in
        time.  Useful for audit trails and change tracking.

        Yields:
            :class:`~pyado.raw.WorkItemInfo` for each revision, oldest first.
        """
        yield from raw.iter_work_item_revisions(self._api_call)

    def iter_linked_work_items(
        self,
        rel_type: WorkItemRelationType | None = None,
    ) -> "Iterator[WorkItem]":
        """Iterate over work items linked to this one.

        Only work-item-to-work-item relations are returned.  Artifact links
        (PRs, commits, builds) are skipped automatically.  Ensure the info
        was fetched with ``expand=WorkItemExpand.RELATIONS`` (the default for
        :meth:`ProjectBoards.get_work_item`).

        Args:
            rel_type: When provided, only relations of this type are yielded
                (e.g. ``WorkItemRelationType.CHILD``).  When ``None``, all
                WI-to-WI relation types are returned.

        Yields:
            WorkItem for each linked work item.
        """
        wi_relations = [
            r
            for r in self.info.relations
            if _is_wi_relation(r) and (rel_type is None or r.rel == rel_type)
        ]
        ids = [_wi_id_from_url(r.url) for r in wi_relations]
        for info in _work_item.iter_work_item_details(self._project.api_call, ids):
            wi_api_call = raw.get_work_item_api_call(self._project.api_call, info.id)
            yield WorkItem(self._project, wi_api_call, info, WorkItemExpand.RELATIONS)

    def get_parent(self) -> "WorkItem | None":
        """Return the parent work item, or ``None`` if none exists.

        Returns:
            WorkItem for the parent, or ``None`` if this work item has no
            parent relation.
        """
        parents = list(self.iter_linked_work_items(WorkItemRelationType.PARENT))
        return parents[0] if parents else None

    def iter_children(self) -> "Iterator[WorkItem]":
        """Iterate over direct child work items.

        Convenience wrapper around :meth:`iter_linked_work_items` filtered to
        ``WorkItemRelationType.CHILD``.  Requires the info to have been fetched
        with ``expand=WorkItemExpand.RELATIONS`` (the default).

        Yields:
            WorkItem for each child.
        """
        yield from self.iter_linked_work_items(WorkItemRelationType.CHILD)

    def get_child_ids(self) -> "list[WorkItemId]":
        """Return the IDs of direct child work items without making API calls.

        Parses the relation URLs from the already-fetched work item data.
        Requires the info to have been fetched with
        ``expand=WorkItemExpand.RELATIONS`` (the default for
        :meth:`ProjectBoards.get_work_item`).

        Returns:
            List of numeric child work item IDs.
        """
        return [
            _wi_id_from_url(r.url)
            for r in self.info.relations
            if r.rel == WorkItemRelationType.CHILD
        ]

    def remove_link(self, relation: WorkItemRelation) -> None:
        """Remove a specific relation from this work item.

        Scans the current ``info.relations`` list for a matching entry by
        ``rel`` type and ``url``, then removes it via a JSON Patch remove
        operation.

        Args:
            relation: The WorkItemRelation to remove.  Must be one of the
                relations returned by :meth:`iter_relations`.

        Raises:
            ValueError: If the relation is not found on the work item.
        """
        for idx, rel in enumerate(self.info.relations):
            if rel.rel == relation.rel and rel.url == relation.url:
                self._info = _work_item.remove_work_item_link(self._api_call, idx)
                return
        err_msg = f"Relation not found: rel={relation.rel!r}, url={relation.url!r}"
        raise ValueError(err_msg)

    def remove_work_item_links(self, other: "WorkItem") -> None:
        """Remove all relations between this work item and *other*.

        Iterates over all relations on this work item and removes every entry
        whose URL refers to *other*.  Snapshots the matching relations before
        the loop so that the index passed to each :meth:`remove_link` call is
        always correct.

        Args:
            other: The work item whose links to this one should all be removed.
        """
        target_suffix = f"/{other.id}"
        to_remove = [
            rel
            for rel in self.iter_relations()
            if rel.url is not None and str(rel.url).endswith(target_suffix)
        ]
        for relation in to_remove:
            self.remove_link(relation)

    def move(
        self,
        *,
        iteration_path: str | None = None,
        area_path: str | None = None,
    ) -> None:
        r"""Move this work item to a different iteration and/or area path.

        Args:
            iteration_path: New iteration path (e.g.
                ``"MyProject\\Sprint 2"``), or ``None`` to leave unchanged.
            area_path: New area path (e.g. ``"MyProject\\Team A"``), or
                ``None`` to leave unchanged.
        """
        fields: dict[WorkItemField, Any] = {}
        if iteration_path is not None:
            fields["System.IterationPath"] = iteration_path
        if area_path is not None:
            fields["System.AreaPath"] = area_path
        if fields:
            self.update(fields)

    def delete(self) -> None:
        """Soft-delete this work item.

        The item can be restored from the ADO Recycle Bin within 30 days.
        """
        raw.delete_work_item(self._api_call)

    def restore(self) -> None:
        """Restore this work item from the Recycle Bin.

        Reverses a :meth:`delete` call.  The item is live again after this
        returns.  :meth:`refresh` is called automatically so subsequent
        accesses to :attr:`info` reflect the restored state.
        """
        raw.restore_work_item(self._project.api_call, self.id)
        self.refresh()

    def update_comment(self, comment_id: int, text: str) -> WorkItemComment:
        """Update the text of an existing comment.

        Args:
            comment_id: Numeric ID of the comment to update.  Obtain it from
                :meth:`iter_comments`.
            text: New comment body text.

        Returns:
            The updated WorkItemComment.
        """
        return raw.patch_work_item_comment(self._api_call, comment_id, text)

    def delete_comment(self, comment_id: int) -> None:
        """Delete a comment from this work item.

        Args:
            comment_id: Numeric ID of the comment to delete.  Obtain it from
                :meth:`iter_comments`.
        """
        raw.delete_work_item_comment(self._api_call, comment_id)

    def list_tags(self) -> list[str]:
        """Return all tags on this work item as a list."""
        return list(self.iter_tags())

    def list_comments(self) -> list[WorkItemComment]:
        """Return all comments on this work item as a list."""
        return list(self.iter_comments())

    def list_relations(
        self,
        rel_type: WorkItemRelationType | None = None,
    ) -> list[WorkItemRelation]:
        """Return all relations on this work item as a list."""
        return list(self.iter_relations(rel_type=rel_type))

    def list_artifact_links(self) -> list[WorkItemRelation]:
        """Return all artifact link relations as a list."""
        return list(self.iter_artifact_links())

    def list_attachments(self) -> list[WorkItemAttachmentRef]:
        """Return all attached-file relations as a list."""
        return list(self.iter_attachments())

    def list_revisions(self) -> list[WorkItemInfo]:
        """Return all historical revisions of this work item as a list."""
        return list(self.iter_revisions())

    def list_linked_work_items(
        self,
        rel_type: WorkItemRelationType | None = None,
    ) -> "list[WorkItem]":
        """Return all linked work items as a list."""
        return list(self.iter_linked_work_items(rel_type=rel_type))

    def list_children(self) -> "list[WorkItem]":
        """Return all child work items as a list."""
        return list(self.iter_children())
