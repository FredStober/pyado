"""OOP wrapper for Azure DevOps work item resources.

Provides the :class:`WorkItem` class, which wraps a single ADO work item
and exposes its operations as methods rather than free functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pyado import high, raw
from pyado.raw import (
    ApiCall,
    WorkItemAttachmentRef,
    WorkItemComment,
    WorkItemField,
    WorkItemId,
    WorkItemInfo,
)

__all__ = ["WorkItem"]


class WorkItem:
    """An Azure DevOps work item resource.

    Wraps a single ADO work item and exposes its operations as instance
    methods.  Instances are normally obtained from :meth:`Project.get_work_item`
    or :meth:`Project.iter_work_items`.

    Attributes:
        _api_call: Work-item-level API call used by all operations.
        _project_api_call: Project-level API call (needed for attachment
            uploads and other project-scoped calls).
        _info: The work item data returned from the API at construction time.
    """

    def __init__(
        self,
        work_item_api_call: ApiCall,
        project_api_call: ApiCall,
        info: WorkItemInfo,
    ) -> None:
        """Construct a WorkItem wrapper.

        Args:
            work_item_api_call: Work-item-level ADO API call (from
                raw.get_work_item_api_call).
            project_api_call: Project-level ADO API call.
            info: Work item data as returned from the API.
        """
        self._api_call = work_item_api_call
        self._project_api_call = project_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> WorkItemInfo:
        """Return the work item data fetched at construction time.

        Returns:
            WorkItemInfo snapshot captured when this object was created.
        """
        return self._info

    def get_api_call(self) -> ApiCall:
        """Return the work-item-level API call.

        Returns:
            ApiCall scoped to this work item's ADO endpoint.
        """
        return self._api_call

    def get_id(self) -> WorkItemId:
        """Return the numeric work item ID.

        Returns:
            Integer work item ID.
        """
        return self._info.id

    def get_field(self, field: WorkItemField) -> Any:
        """Return the current value of a work item field.

        Args:
            field: Field reference name, e.g. ``"System.Title"``.

        Returns:
            The field value, or ``None`` if the field is absent.
        """
        return self._info.fields.get(field)

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
            self._project_api_call, self._info.id, filename, content
        )
