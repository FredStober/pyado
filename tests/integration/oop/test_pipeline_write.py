"""Integration tests for Pipeline OOP class (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib

from pyado.oop import Build, Pipeline, Project
from pyado.raw import PipelineResourceType
from tests.integration.raw._support import _take, console


def test_write_pipeline_extras(proj: Project) -> None:
    """Exercise pipeline write methods.

    Covers start_run, cancel_run, start_build, cancel_build, and
    authorize_resource.
    """
    console.print("\n=== Pipeline (write extras) ===")
    pipelines = _take(proj.pipelines.iter_pipelines(), 1)
    if not pipelines:
        return

    pipeline: Pipeline = pipelines[0]

    # start_run then cancel_run
    started = pipeline.start_run()
    pipeline.cancel_run(started.id)

    # Build.cancel + Build.retry (needs a completed/failed build)
    builds = _take(proj.pipelines.iter_builds(), 1)
    if builds:
        _: Build = builds[0]
        # start_build then cancel it
        defs = _take(proj.pipelines.iter_pipelines(), 1)
        if defs:
            started_build = proj.pipelines.start_build(defs[0].id)
            if started_build:
                started_build.cancel()
                started_build.cancel_run()
                retried = started_build.retry()
                if retried is not None:
                    retried.cancel()

    # authorize_resource: use the repository as the resource
    repos = _take(proj.repos.iter_repositories(), 1)
    if repos:
        with contextlib.suppress(Exception):
            pipeline.authorize_resource(
                PipelineResourceType.REPOSITORY, str(repos[0].id), authorized=True
            )
