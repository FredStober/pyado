"""Higher-level wrappers for work item operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from pyado.raw import (
    ApiCall,
    BuildId,
    CommitId,
    JsonPatchAdd,
    ProjectId,
    PullRequestId,
    RepositoryId,
    WorkItemArtifactUrlPrefix,
    WorkItemAttachmentRef,
    WorkItemExpand,
    WorkItemField,
    WorkItemId,
    WorkItemInfo,
    WorkItemRelation,
    WorkItemRelationType,
    WorkItemsBatchRequest,
    get_work_item,
    get_work_item_api_call,
    patch_work_item,
    post_wiql,
    post_work_item,
    post_work_item_attachment_upload,
    post_work_items_batch,
)

__all__ = [
    "CustomWorkItemBase",
    "WorkItemFieldMap",
    "WorkItemLink",
    "add_work_item_attachment",
    "add_work_item_link",
    "add_work_item_tag",
    "create_work_item",
    "get_work_item_tags",
    "iter_work_item_details",
    "query_work_items",
    "remove_work_item_tag",
    "update_work_item",
]

_WORK_ITEM_BATCH_SIZE = 200


@dataclass
class WorkItemFieldMap:
    """Maps an annotated model field to one ADO work item field reference name.

    Use as ``Annotated`` metadata on ``CustomWorkItemBase`` subclass fields.
    Multiple ``WorkItemFieldMap`` markers on one field copy the value to each
    ADO path::

        title: Annotated[str, WorkItemFieldMap(WorkItemFieldName.TITLE)]
        description: Annotated[
            str,
            WorkItemFieldMap(WorkItemFieldName.DESCRIPTION),
            WorkItemFieldMap("Microsoft.VSTS.TCM.ReproSteps"),
        ]
    """

    work_item_field: str


class CustomWorkItemBase(BaseModel):
    """Pydantic base class that maps annotated fields to ADO work item fields.

    Subclass this and annotate each field with one or more
    ``WorkItemFieldMap`` markers.  Call ``to_fields()`` to produce the
    ``dict[WorkItemField, Any]`` expected by ``create_work_item`` and
    ``update_work_item``::

        class MyTicket(CustomWorkItemBase):
            title: Annotated[str, WorkItemFieldMap(WorkItemFieldName.TITLE)]
            state: Annotated[str, WorkItemFieldMap(WorkItemFieldName.STATE)] = "Active"

        ticket = MyTicket(title="Bug: something broke")
        create_work_item(api, ticket.to_fields())

    Fields whose value is ``None`` are omitted from the result.
    """

    def to_fields(self) -> dict[WorkItemField, Any]:
        """Return a mapping of ADO field reference names to field values.

        Iterates the model's annotated fields, collects all
        ``WorkItemFieldMap`` markers, and builds a dict suitable for
        ``create_work_item`` / ``update_work_item``.  Fields with a ``None``
        value are skipped.

        Returns:
            Mapping of ADO field reference names to their current values.
        """
        result: dict[WorkItemField, Any] = {}
        for field_name, field_info in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if value is None:
                continue
            for meta in field_info.metadata:
                if isinstance(meta, WorkItemFieldMap):
                    result[meta.work_item_field] = value
        return result


class WorkItemLink:
    """Factory for WorkItemRelation objects covering all ADO link types.

    Static methods return ready-to-use WorkItemRelation instances that can
    be passed to create_work_item (relations list) or applied to an existing
    work item via add_work_item_link.

    Artifact links (builds, commits, pull requests) use the ArtifactLink
    relation type with a ``vstfs://`` URL constructed from the supplied IDs.
    Work item links (parent, child, related, etc.) accept the target work
    item's ID and project-level API call; the URL is constructed internally.

    Examples::

        # At creation time
        create_work_item(api, fields, relations=[
            WorkItemLink.build(build_id),
            WorkItemLink.parent(project_api, parent_wi_id),
        ])

        # On an existing work item
        add_work_item_link(api, WorkItemLink.pull_request(
            project_id, repo_id, pr_id,
        ))
    """

    @staticmethod
    def _artifact(
        prefix: WorkItemArtifactUrlPrefix,
        artifact_id: str,
        name: str,
        comment: str | None,
    ) -> WorkItemRelation:
        attributes: dict[str, Any] = {"name": name}
        if comment is not None:
            attributes["comment"] = comment
        return WorkItemRelation(
            rel=WorkItemRelationType.ARTIFACT_LINK,
            url=f"{prefix}/{artifact_id}",
            attributes=attributes,
        )

    @staticmethod
    def _wi_link(
        rel_type: WorkItemRelationType,
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        comment: str | None,
    ) -> WorkItemRelation:
        work_item_url = get_work_item_api_call(
            project_api_call, work_item_id
        ).url.unicode_string()
        attributes: dict[str, Any] | None = (
            {"comment": comment} if comment is not None else None
        )
        return WorkItemRelation(
            rel=rel_type,
            url=work_item_url,
            attributes=attributes,
        )

    # --- Artifact links ---

    @staticmethod
    def build(
        build_id: BuildId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return an ArtifactLink relation targeting a build.

        Args:
            build_id: Numeric build ID.
            comment: Optional comment to attach to the relation.
        """
        return WorkItemLink._artifact(
            WorkItemArtifactUrlPrefix.BUILD, str(build_id), "Build", comment
        )

    @staticmethod
    def commit(
        project_id: ProjectId,
        repo_id: RepositoryId,
        commit_id: CommitId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return an ArtifactLink relation targeting a git commit.

        Args:
            project_id: UUID of the ADO project.
            repo_id: UUID of the git repository.
            commit_id: Commit SHA string.
            comment: Optional comment to attach to the relation.
        """
        artifact_id = f"{project_id}%2F{repo_id}%2F{commit_id}"
        return WorkItemLink._artifact(
            WorkItemArtifactUrlPrefix.COMMIT,
            artifact_id,
            "Fixed in Commit",
            comment,
        )

    @staticmethod
    def pull_request(
        project_id: ProjectId,
        repo_id: RepositoryId,
        pr_id: PullRequestId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return an ArtifactLink relation targeting a pull request.

        Args:
            project_id: UUID of the ADO project.
            repo_id: UUID of the git repository.
            pr_id: Numeric pull request ID.
            comment: Optional comment to attach to the relation.
        """
        artifact_id = f"{project_id}%2F{repo_id}%2F{pr_id}"
        return WorkItemLink._artifact(
            WorkItemArtifactUrlPrefix.PULL_REQUEST,
            artifact_id,
            "Pull Request",
            comment,
        )

    # --- Work item links ---

    @staticmethod
    def related(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Related link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.RELATED, project_api_call, work_item_id, comment
        )

    @staticmethod
    def parent(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Parent (Hierarchy-Reverse) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.PARENT, project_api_call, work_item_id, comment
        )

    @staticmethod
    def child(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Child (Hierarchy-Forward) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.CHILD, project_api_call, work_item_id, comment
        )

    @staticmethod
    def duplicate(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Duplicate-Forward link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.DUPLICATE, project_api_call, work_item_id, comment
        )

    @staticmethod
    def duplicate_of(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Duplicate-Reverse link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.DUPLICATE_OF,
            project_api_call,
            work_item_id,
            comment,
        )

    @staticmethod
    def successor(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Dependency-Forward (successor) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.SUCCESSOR, project_api_call, work_item_id, comment
        )

    @staticmethod
    def predecessor(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a Dependency-Reverse (predecessor) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.PREDECESSOR, project_api_call, work_item_id, comment
        )

    @staticmethod
    def tested_by(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a TestedBy-Forward link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.TESTED_BY, project_api_call, work_item_id, comment
        )

    @staticmethod
    def tests(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a TestedBy-Reverse (tests) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.TESTS, project_api_call, work_item_id, comment
        )

    @staticmethod
    def test_case(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a TestCase-Forward link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.TEST_CASE, project_api_call, work_item_id, comment
        )

    @staticmethod
    def shared_parameter_referenced_by(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return a SharedParameterReferencedBy-Reverse link."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.SHARED_PARAMETER_REFERENCED_BY,
            project_api_call,
            work_item_id,
            comment,
        )

    @staticmethod
    def affects(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return an Affects-Forward link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.AFFECTS, project_api_call, work_item_id, comment
        )

    @staticmethod
    def affected_by(
        project_api_call: ApiCall,
        work_item_id: WorkItemId,
        *,
        comment: str | None = None,
    ) -> WorkItemRelation:
        """Return an Affects-Reverse (affected by) link to another work item."""
        return WorkItemLink._wi_link(
            WorkItemRelationType.AFFECTED_BY, project_api_call, work_item_id, comment
        )

    # --- Other links ---

    @staticmethod
    def hyperlink(url: str, *, comment: str | None = None) -> WorkItemRelation:
        """Return a Hyperlink relation to an arbitrary URL.

        Args:
            url: The hyperlink URL.
            comment: Optional comment to attach to the relation.
        """
        attributes: dict[str, Any] | None = (
            {"comment": comment} if comment is not None else None
        )
        return WorkItemRelation(
            rel=WorkItemRelationType.HYPERLINK,
            url=url,
            attributes=attributes,
        )


def add_work_item_link(
    work_item_api_call: ApiCall,
    link: WorkItemRelation,
) -> WorkItemInfo:
    """Add a relation to a work item.

    The relation is typically constructed via WorkItemLink, e.g.:
    ``add_work_item_link(api, WorkItemLink.build(build_id))``.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        link: WorkItemRelation to add, as returned by WorkItemLink.

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    return patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/relations/-",
                value=link.model_dump(mode="json", exclude_defaults=True),
            ).model_dump(mode="json")
        ],
    )


def iter_work_item_details(
    project_api_call: ApiCall,
    work_item_id_list: list[WorkItemId],
    work_item_field_list: list[WorkItemField] | None = None,
) -> Iterator[WorkItemInfo]:
    """Iterate over the work items.

    Batches requests in chunks of 200 (the ADO API limit per call).

    Yields:
        WorkItemInfo objects for each work item in the results.
    """
    for batch_start in range(0, len(work_item_id_list), _WORK_ITEM_BATCH_SIZE):
        batch = work_item_id_list[batch_start : batch_start + _WORK_ITEM_BATCH_SIZE]
        if work_item_field_list:
            request = WorkItemsBatchRequest(ids=batch, fields=work_item_field_list)
        else:
            request = WorkItemsBatchRequest(ids=batch, expand=WorkItemExpand.RELATIONS)
        yield from post_work_items_batch(project_api_call, request)


def query_work_items(
    project_api_call: ApiCall,
    query: str,
    work_item_field_list: list[WorkItemField] | None = None,
) -> Iterator[WorkItemInfo]:
    """Execute a WIQL query and yield full work item details.

    Combines post_wiql with iter_work_item_details: runs the query, then
    fetches complete work item data in batches of 200.

    Args:
        project_api_call: Project-level ADO API call.
        query: WIQL query string.
        work_item_field_list: Optional list of field reference names to
            return.  When omitted, all fields plus relations are fetched.

    Yields:
        WorkItemInfo objects for each work item matched by the query.
    """
    refs = post_wiql(project_api_call, query)
    if not refs:
        return
    yield from iter_work_item_details(
        project_api_call,
        [ref.id for ref in refs],
        work_item_field_list,
    )


def create_work_item(
    project_api_call: ApiCall,
    fields: dict[WorkItemField, Any],
    relations: list[WorkItemRelation] | None = None,
) -> WorkItemInfo:
    """Create a work item.

    Args:
        project_api_call: Project-level ADO API call.
        fields: Mapping of field reference names to values.  Must include
            ``"System.WorkItemType"``.
        relations: Optional list of relations to add to the new work item.

    Returns:
        The created WorkItemInfo parsed from the API response.

    Raises:
        RuntimeError: If System.WorkItemType is not provided in fields.
    """
    ticket_type: str | None = fields.get("System.WorkItemType")
    if ticket_type is None:
        err_msg = f"Work item type must be specified! {fields!r}"
        raise RuntimeError(err_msg)
    json_patch_list = [
        JsonPatchAdd(path=f"/fields/{key}", value=value)
        for key, value in fields.items()
        if key != "System.WorkItemType"
    ]
    for link in relations or []:
        link_dict = link.model_dump(mode="json", exclude_defaults=True)
        json_patch_list.append(JsonPatchAdd(path="/relations/-", value=link_dict))
    return post_work_item(
        project_api_call,
        ticket_type,
        [patch.model_dump(mode="json") for patch in json_patch_list],
    )


def update_work_item(
    work_item_api_call: ApiCall,
    fields: dict[WorkItemField, Any],
    *,
    multiline_fields_format: dict[WorkItemField, str] | None = None,
) -> WorkItemInfo:
    """Update work item fields via JSON patch.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        fields: Mapping of field reference names to new values.
        multiline_fields_format: Optional mapping of multiline field
            reference names to their format — "html" or "markdown".
            When a field is set to "markdown", ADO renders its content
            as markdown in the UI. Must be accompanied by a matching
            entry in fields (ADO rejects a format-only patch).

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    json_patch_list: list[dict[str, Any]] = [
        JsonPatchAdd(path=f"/fields/{key}", value=value).model_dump(mode="json")
        for key, value in fields.items()
    ]
    for field_name, fmt in (multiline_fields_format or {}).items():
        json_patch_list.append(
            {"op": "add", "path": f"/multilineFieldsFormat/{field_name}", "value": fmt}
        )
    return patch_work_item(work_item_api_call, json_patch_list)


def _parse_work_item_tags(raw_value: str | None) -> list[str]:
    """Parse a semicolon-separated ADO tag string into a list of tag names.

    Returns:
        List of stripped tag name strings; empty list when input is falsy.
    """
    if not raw_value:
        return []
    return [tag.strip() for tag in raw_value.split(";") if tag.strip()]


def _format_work_item_tags(tags: list[str]) -> str:
    """Format a list of tag names into the ADO semicolon-separated string.

    Returns:
        Semicolon-and-space-separated tag string as expected by ADO.
    """
    return "; ".join(tags)


def get_work_item_tags(work_item_api_call: ApiCall) -> list[str]:
    """Return the tags currently set on a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).

    Returns:
        List of tag name strings.  Empty list when no tags are set.
    """
    item = get_work_item(work_item_api_call)
    return _parse_work_item_tags(item.fields.get("System.Tags"))


def add_work_item_tag(
    work_item_api_call: ApiCall,
    tag: str,
) -> list[str]:
    """Add a tag to a work item.

    If the tag is already present (case-insensitive comparison) the work item
    is not updated and the existing tag list is returned unchanged.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        tag: Tag name to add.

    Returns:
        Updated list of tag name strings.
    """
    current_tags = get_work_item_tags(work_item_api_call)
    tag_lower = tag.lower()
    if any(existing.lower() == tag_lower for existing in current_tags):
        return current_tags
    updated_tags = [*current_tags, tag]
    patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/fields/System.Tags",
                value=_format_work_item_tags(updated_tags),
            ).model_dump(mode="json")
        ],
    )
    return updated_tags


def remove_work_item_tag(
    work_item_api_call: ApiCall,
    tag: str,
) -> list[str]:
    """Remove a tag from a work item.

    If the tag is not present (case-insensitive comparison) the work item is
    not updated and the existing tag list is returned unchanged.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        tag: Tag name to remove.

    Returns:
        Updated list of tag name strings.
    """
    current_tags = get_work_item_tags(work_item_api_call)
    tag_lower = tag.lower()
    updated_tags = [
        existing for existing in current_tags if existing.lower() != tag_lower
    ]
    if len(updated_tags) == len(current_tags):
        return current_tags
    patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/fields/System.Tags",
                value=_format_work_item_tags(updated_tags),
            ).model_dump(mode="json")
        ],
    )
    return updated_tags


def add_work_item_attachment(
    project_api_call: ApiCall,
    work_item_id: WorkItemId,
    filename: str,
    content: bytes,
) -> WorkItemAttachmentRef:
    """Upload a file and attach it to a work item.

    This is a two-step operation: the file is uploaded first, then a relation
    of type ``AttachedFile`` is added to the work item.

    Args:
        project_api_call: Project-level ADO API call.
        work_item_id: ID of the work item to attach the file to.
        filename: Name of the file as it will appear in ADO.
        content: Raw bytes of the file to upload.

    Returns:
        WorkItemAttachmentRef with the ID and URL of the uploaded attachment.
    """
    attachment_ref = post_work_item_attachment_upload(
        project_api_call, filename, content
    )
    work_item_api_call = get_work_item_api_call(project_api_call, work_item_id)
    patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": WorkItemRelationType.ATTACHED_FILE,
                    "url": str(attachment_ref.url),
                    "attributes": {"comment": filename},
                },
            ).model_dump(mode="json")
        ],
    )
    return attachment_ref
