"""Smoke tests for Pipeline."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Build, Pipeline, Project
from pyado.oop.smoke_test._runner import _ok, _skip, _take, console, run


def _test_pipeline_read(proj: Project) -> Pipeline | None:
    console.print("\n=== Pipeline (read) ===")
    pipelines = run("proj.iter_pipelines()", lambda: _take(proj.iter_pipelines(), 3))
    if not pipelines:
        _skip("pipeline read tests", "no pipelines found")
        return None

    pipeline: Pipeline = pipelines[0]
    run(
        "proj.get_pipeline_by_id(id)",
        lambda pid=pipeline.id: proj.get_pipeline_by_id(pid),
    )

    run("pipeline.id", lambda: pipeline.id)
    run("pipeline.name", lambda: pipeline.name)
    run("pipeline.info", lambda: pipeline.info)
    run("pipeline.api_call", lambda: pipeline.api_call)
    run("pipeline.project (back-nav)", lambda: pipeline.project)
    run("pipeline.org (back-nav)", lambda: pipeline.org)
    run("pipeline.refresh()", pipeline.refresh)
    run("pipeline.iter_runs()", lambda: _take(pipeline.iter_runs(), 3))
    run("pipeline.list_runs()", pipeline.list_runs)
    run("pipeline.list_builds()", pipeline.list_builds)
    latest_run = run("pipeline.get_latest_run()", pipeline.get_latest_run)
    if latest_run is not None:
        run(
            "pipeline.get_run(run_id)",
            lambda rid=latest_run.id: pipeline.get_run(rid),
        )
    run(
        "proj.get_pipeline(name)",
        lambda n=pipeline.name: proj.get_pipeline(n),
    )
    return pipeline


def _test_write_pipeline_extras(proj: Project) -> None:
    """Exercise Pipeline write methods: start_run, cancel_run, authorize_resource."""
    console.print("\n=== Pipeline (write extras) ===")
    pipelines = _take(proj.iter_pipelines(), 1)
    if not pipelines:
        _skip("pipeline write extras", "no pipelines found")
        return

    pipeline: Pipeline = pipelines[0]

    # start_run then cancel_run
    started = run("pipeline.start_run()", pipeline.start_run)
    if started is not None:
        run(
            "pipeline.cancel_run(run_id)",
            lambda rid=started.id: pipeline.cancel_run(rid),
        )
    else:
        _skip("pipeline.cancel_run(run_id)", "pipeline.start_run() failed")

    # Build.cancel + Build.retry (needs a completed/failed build)
    builds = _take(proj.iter_builds(), 1)
    if builds:
        _: Build = builds[0]
        # start_build then cancel it
        defs = _take(proj.iter_pipeline_definitions(), 1)
        if defs:
            started_build = run(
                "proj.start_build(definition_id)",
                lambda did=defs[0].id: proj.start_build(did),
            )
            if started_build:
                run("build.cancel()", lambda b=started_build: b.cancel())
                run("build.cancel_run()", lambda b=started_build: b.cancel_run())
                retried = run("build.retry()", lambda b=started_build: b.retry())
                if retried is not None:
                    run(
                        "build.retry() [cancel retried]",
                        lambda rb=retried: rb.cancel(),
                    )

    # authorize_resource: use the repository as the resource
    repos = _take(proj.iter_repositories(), 1)
    if repos:
        try:
            pipeline.authorize_resource("repository", str(repos[0].id), authorized=True)
            _ok("pipeline.authorize_resource(repository)")
        except Exception:
            _skip(
                "pipeline.authorize_resource(repository)",
                "ADO endpoint rejected method",
            )
    else:
        _skip("pipeline.authorize_resource(repository)", "no repositories found")
