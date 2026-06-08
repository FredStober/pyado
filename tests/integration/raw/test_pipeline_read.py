"""Integration tests for pipeline (newer API) read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_pipeline_read(
    pipelines: list[raw.PipelineInfo],
) -> None:
    """List pipelines, get individual pipeline, and list/get pipeline runs.

    The pipelines session fixture calls _test_pipelines_read which covers:
    list_pipelines (multiple order variants), get_pipeline, iter_pipeline_runs,
    list_pipeline_runs, get_pipeline_run.
    """
