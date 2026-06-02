"""Higher-level wrappers for work item operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pyado.raw import (
    ApiCall,
    JsonPatchAdd,
    WorkItemAttachmentRef,
    WorkItemField,
    WorkItemId,
    WorkItemInfo,
    WorkItemRelation,
    WorkItemsBatchRequest,
    get_work_item,
    get_work_item_api_call,
    patch_work_item,
    post_work_item,
    post_work_item_attachment_upload,
    post_work_items_batch,
)

__all__ = [
    "add_artifact_link",
    "add_work_item_attachment",
    "add_work_item_tag",
    "create_work_item",
    "get_work_item_tags",
    "iter_work_item_details",
    "remove_work_item_tag",
    "update_work_item",
]

_WORK_ITEM_BATCH_SIZE = 200


def add_artifact_link(
    work_item_api_call: ApiCall,
    artifact_url: str,
    *,
    comment: str | None = None,
) -> WorkItemInfo:
    """Add an ArtifactLink relation to a work item.

    Used to associate external artifacts such as pull requests with a work
    item.  The artifact URL for an ADO pull request has the form:
    ``vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}``.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).
        artifact_url: The ``vstfs://`` artifact URL to link.
        comment: Optional comment to attach to the relation.

    Returns:
        Updated WorkItemInfo parsed from the API response.
    """
    attributes: dict[str, Any] = {"name": "Pull Request"}
    if comment is not None:
        attributes["comment"] = comment
    return patch_work_item(
        work_item_api_call,
        [
            JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": "ArtifactLink",
                    "url": artifact_url,
                    "attributes": attributes,
                },
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
            request = WorkItemsBatchRequest(ids=batch, expand="relations")
        yield from post_work_items_batch(project_api_call, request)


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
                    "rel": "AttachedFile",
                    "url": str(attachment_ref.url),
                    "attributes": {"comment": filename},
                },
            ).model_dump(mode="json")
        ],
    )
    return attachment_ref
