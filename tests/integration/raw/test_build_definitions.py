"""Integration tests for pipeline definition endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_build_definitions(
    builds_read: tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]],
) -> None:
    """List and iterate pipeline definitions.

    The builds_read session fixture exercises list_pipeline_definitions,
    iter_pipeline_definitions, and multiple list_builds variants.
    This test verifies those calls succeeded without error.
    """
