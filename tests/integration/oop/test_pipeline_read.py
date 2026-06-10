"""Integration tests for Pipeline OOP class and pipeline library (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib

from pyado.oop import (
    Environment,
    Pipeline,
    PipelineLibrary,
    PipelineRun,
    Project,
    ProjectPipelines,
    SecureFile,
    ServiceEndpoint,
    TaskGroup,
)
from tests.integration.raw._support import _take, console


def test_pipeline_read(proj: Project) -> None:
    """Exercise Pipeline properties, runs, builds, and service endpoints."""
    console.print("\n=== Pipeline (read) ===")
    pipelines = _take(proj.pipelines.iter_pipelines(), 3)
    if not pipelines:
        return

    pipelines_section: ProjectPipelines = proj.pipelines
    pipeline: Pipeline = pipelines[0]
    pipelines_section.get_pipeline_by_id(pipeline.id)

    _ = pipeline.id
    _ = pipeline.name
    _ = pipeline.info
    _ = pipeline.api_call
    _ = pipeline.project
    _ = pipeline.org
    pipeline.refresh()
    _take(pipeline.iter_runs(), 3)
    pipeline.list_runs()
    pipeline.list_builds()
    latest_run: PipelineRun | None = pipeline.get_latest_run()
    if latest_run is not None:
        pipeline.get_run(latest_run.id)
    pipelines_section.get_pipeline(pipeline.name)
    _take(pipelines_section.iter_pipeline_definitions(), 3)
    pipelines_section.list_pipeline_definitions()
    _take(pipelines_section.iter_service_endpoints(), 3)
    endpoints = pipelines_section.list_service_endpoints()
    if endpoints:
        ep: ServiceEndpoint = endpoints[0]
        _ = ep.url
        _ = ep.is_ready
        _ = ep.is_shared
        _ = ep.authorization_scheme


def test_environments(proj: Project) -> None:
    """Exercise Environment OOP class: deployments and checks."""
    console.print("\n=== Pipeline Environments ===")
    envs = _take(proj.pipelines.iter_environments(), 3)
    proj.pipelines.list_environments()
    if envs:
        env: Environment = envs[0]
        _ = env.id
        _ = env.name
        _ = env.description
        _ = env.info
        _ = env.api_call
        _ = env.project
        _ = env.org
        env.refresh()
        _take(env.iter_deployments(), 3)
        env.list_deployments()
        _take(env.iter_checks(), 3)
        env.list_checks()
        with contextlib.suppress(Exception):
            proj.pipelines.get_environment(env.name)


def test_task_groups(proj: Project) -> None:
    """Exercise TaskGroup OOP class (read-only)."""
    console.print("\n=== Pipeline: Task Groups ===")
    groups = _take(proj.pipelines.iter_task_groups(), 3)
    proj.pipelines.list_task_groups()
    if groups:
        tg: TaskGroup = groups[0]
        _ = tg.id
        _ = tg.name
        _ = tg.description
        _ = tg.category
        _ = tg.info
        _ = tg.project
        _ = tg.org
        tg.refresh()
        with contextlib.suppress(Exception):
            proj.pipelines.get_task_group(tg.name)
        proj.pipelines.get_task_group_by_id(tg.id)


def test_secure_files(proj: Project) -> None:
    """Exercise SecureFile OOP class (read-only)."""
    console.print("\n=== Pipeline Library: Secure Files ===")
    library: PipelineLibrary = proj.pipelines.library
    files = _take(library.iter_secure_files(), 3)
    library.list_secure_files()
    if files:
        sf: SecureFile = files[0]
        _ = sf.id
        _ = sf.name
        _ = sf.info
        _ = sf.api_call
        _ = sf.project
        _ = sf.org
        sf.refresh()
        with contextlib.suppress(Exception):
            library.get_secure_file(sf.name)
