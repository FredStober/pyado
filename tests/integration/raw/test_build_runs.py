"""Integration tests for build listing and per-build detail endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_build_runs(
    builds_read: tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]],
) -> None:
    """List builds and exercise per-build details, timeline, artifacts, and tags.

    The builds_read session fixture calls _test_builds_read which covers:
    list_builds with multiple criteria, get_build_details, list_timeline_records,
    list_build_work_item_ids, list_build_artifacts, get_build_artifact_bytes,
    list_build_tags, post_build_tag, delete_build_tag, list_work_items_between_builds.
    """
