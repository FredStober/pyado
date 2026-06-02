"""OOP wrapper for Azure DevOps build resources.

Provides the :class:`Build` class, which wraps a single ADO build and
exposes its operations as methods rather than free functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado import high, raw
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildRecordInfo,
    WorkItemId,
)

__all__ = ["Build"]


class Build:
    """An Azure DevOps build resource.

    Wraps a single ADO build and exposes its operations as instance methods.
    Instances are normally obtained from :meth:`Project.start_build` or
    :meth:`Project.iter_builds`.

    Attributes:
        _api_call: Build-level API call used by all operations.
        _info: The build data returned from the API at construction time.
    """

    def __init__(self, build_api_call: ApiCall, info: BuildDetails) -> None:
        """Construct a Build wrapper.

        Args:
            build_api_call: Build-level ADO API call (from
                raw.get_build_api_call).
            info: Build data as returned from the API.
        """
        self._api_call = build_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> BuildDetails:
        """Return the build data fetched at construction time.

        Returns:
            BuildDetails snapshot captured when this object was created.
        """
        return self._info

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def iter_artifacts(self) -> Iterator[BuildArtifact]:
        """Iterate over artifacts published by the build.

        Yields:
            BuildArtifact for each artifact associated with the build.
        """
        yield from raw.iter_build_artifacts(self._api_call)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def iter_tags(self) -> Iterator[str]:
        """Iterate over the tags set on the build.

        Yields:
            Tag name strings.
        """
        yield from raw.iter_build_tags(self._api_call)

    def add_tag(self, tag: str) -> list[str]:
        """Add a tag to the build.

        Args:
            tag: Tag name to add.

        Returns:
            Updated list of tag name strings.
        """
        return raw.post_build_tag(self._api_call, tag)

    def remove_tag(self, tag: str) -> list[str]:
        """Remove a tag from the build.

        Args:
            tag: Tag name to remove.

        Returns:
            Updated list of tag name strings.
        """
        return raw.delete_build_tag(self._api_call, tag)

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def iter_timeline_records(self) -> Iterator[BuildRecordInfo]:
        """Iterate over the timeline records (stages, jobs, tasks) of the build.

        Yields:
            BuildRecordInfo for each timeline entry.
        """
        yield from raw.iter_timeline_records(self._api_call)

    # ------------------------------------------------------------------
    # Work items
    # ------------------------------------------------------------------

    def iter_work_item_ids(self) -> Iterator[WorkItemId]:
        """Iterate over work item IDs associated with the build.

        Yields:
            Integer work item IDs linked to this build.
        """
        yield from high.iter_build_work_item_ids(self._api_call)
