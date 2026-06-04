"""OOP wrapper for Azure DevOps work item resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import high, raw
from pyado.raw import (
    ApiCall,
    CommitId,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemExpand,
    WorkItemField,
    WorkItemId,
    WorkItemInfo,
    WorkItemRelation,
    WorkItemRelationType,
)

if TYPE_CHECKING:
    from pyado.oop.build import Build
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.pull_request import PullRequest
    from pyado.oop.repository import Repository

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
    methods.  Instances are obtained from :meth:`Project.get_work_item`,
    :meth:`Project.iter_work_items`, or :meth:`Project.create_work_item`.

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
    ) -> None:
        """Construct a WorkItem wrapper.

        Args:
            project: The Project that owns this work item.
            work_item_api_call: Work-item-level ADO API call (from
                raw.get_work_item_api_call).
            info: Work item data as returned from the API.
        """
        self._project = project
        self._api_call = work_item_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> WorkItemInfo:
        """Work item data captured at construction time (or last refresh)."""
        return self._info

    @property
    def id(self) -> WorkItemId:
        """Numeric work item ID."""
        return self._info.id

    @property
    def title(self) -> str | None:
        """Value of the ``System.Title`` field, or ``None`` if absent."""
        return self._info.fields.get("System.Title")

    @property
    def state(self) -> str | None:
        """Value of the ``System.State`` field, or ``None`` if absent."""
        return self._info.fields.get("System.State")

    @property
    def type(self) -> str | None:
        """Value of the ``System.WorkItemType`` field, or ``None`` if absent."""
        return self._info.fields.get("System.WorkItemType")

    @property
    def assigned_to(self) -> Any:
        """Value of the ``System.AssignedTo`` field (identity dict), or ``None``."""
        return self._info.fields.get("System.AssignedTo")

    @property
    def area_path(self) -> str | None:
        """Value of the ``System.AreaPath`` field, or ``None`` if absent."""
        return self._info.fields.get("System.AreaPath")

    @property
    def iteration_path(self) -> str | None:
        """Value of the ``System.IterationPath`` field, or ``None`` if absent."""
        return self._info.fields.get("System.IterationPath")

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
        return self._info.fields.get(field)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch work item info from the API immediately."""
        self._info = raw.get_work_item(self._api_call, expand=WorkItemExpand.RELATIONS)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update(
        self,
        fields: dict[WorkItemField, Any],
        *,
        multiline_fields_format: dict[WorkItemField, str] | None = None,
    ) -> None:
        """Update work item fields.

        Args:
            fields: Mapping of field reference names to new values.
            multiline_fields_format: Optional per-field format override
                (``"html"`` or ``"markdown"``).
        """
        self._info = high.update_work_item(
            self._api_call,
            fields,
            multiline_fields_format=multiline_fields_format,
        )

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def get_tags(self) -> list[str]:
        """Return the tags currently set on the work item.

        Returns:
            List of tag name strings; empty when no tags are set.
        """
        return high.get_work_item_tags(self._api_call)

    def add_tag(self, tag: str) -> list[str]:
        """Add a tag to the work item.

        If the tag is already present the work item is not modified.

        Args:
            tag: Tag name to add.

        Returns:
            Updated list of tag name strings.
        """
        return high.add_work_item_tag(self._api_call, tag)

    def remove_tag(self, tag: str) -> list[str]:
        """Remove a tag from the work item.

        If the tag is not present the work item is not modified.

        Args:
            tag: Tag name to remove.

        Returns:
            Updated list of tag name strings.
        """
        return high.remove_work_item_tag(self._api_call, tag)

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
        self, text: str, *, comment_format: str = "html"
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
        return high.add_work_item_attachment(
            self._project.api_call, self._info.id, filename, content
        )

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
        relation = high.WorkItemLink.wi_link(
            link_type, other.project.api_call, other.id, comment
        )
        high.add_work_item_link(self._api_call, relation)

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
        relation = high.WorkItemLink.pull_request(
            pr.repo.info.project.id,
            pr.repo.id,
            pr.id,
            comment=comment,
        )
        high.add_work_item_link(self._api_call, relation)

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
        relation = high.WorkItemLink.build(build.id, comment=comment)
        high.add_work_item_link(self._api_call, relation)

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
        relation = high.WorkItemLink.commit(
            repo.info.project.id,
            repo.id,
            commit_id,
            comment=comment,
        )
        high.add_work_item_link(self._api_call, relation)

    # ------------------------------------------------------------------
    # Relation navigation
    # ------------------------------------------------------------------

    def iter_linked_work_items(
        self,
        rel_type: WorkItemRelationType | None = None,
    ) -> "Iterator[WorkItem]":
        """Iterate over work items linked to this one.

        Only work-item-to-work-item relations are returned.  Artifact links
        (PRs, commits, builds) are skipped automatically.  Ensure the info
        was fetched with ``expand=WorkItemExpand.RELATIONS`` (the default for
        :meth:`Project.get_work_item` and :meth:`refresh`).

        Args:
            rel_type: When provided, only relations of this type are yielded
                (e.g. ``WorkItemRelationType.CHILD``).  When ``None``, all
                WI-to-WI relation types are returned.

        Yields:
            WorkItem for each linked work item.
        """
        wi_relations = [
            r
            for r in self._info.relations
            if _is_wi_relation(r) and (rel_type is None or r.rel == rel_type)
        ]
        ids = [_wi_id_from_url(r.url) for r in wi_relations]
        for info in high.iter_work_item_details(self._project.api_call, ids):
            wi_api_call = raw.get_work_item_api_call(self._project.api_call, info.id)
            yield WorkItem(self._project, wi_api_call, info)

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

    def delete(self) -> None:
        """Soft-delete this work item.

        The item can be restored from the ADO Recycle Bin within 30 days.
        """
        raw.delete_work_item(self._api_call)

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
