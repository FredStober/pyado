"""Integration tests for build log endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_build_logs_read(
    project_api_call: raw.ApiCall,
    builds_read: tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]],
) -> None:
    """List build logs and fetch the first log entry."""
    _, builds = builds_read
    console.print("\n=== BUILD LOGS (read) ===")
    if not builds:
        return

    build = builds[0]
    build_api_call = raw.get_build_api_call(project_api_call, build.id)
    logs = list(raw.iter_build_logs(build_api_call))
    assert logs == raw.list_build_logs(build_api_call)
    if logs:
        raw.get_build_log(build_api_call, logs[0].id)
