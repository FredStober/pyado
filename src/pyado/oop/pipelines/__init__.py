"""Pipelines section of the Azure DevOps OOP layer.

Exposes :class:`ProjectPipelines` — the ``project.pipelines`` section object
— and :class:`PipelineLibrary` — the ``project.pipelines.library`` section
object — plus re-exports of all resource classes in this sub-package.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop.pipelines.agent import Agent, AgentPool, AgentQueue
from pyado.oop.pipelines.build import Build
from pyado.oop.pipelines.build_timeline import (
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
)
from pyado.oop.pipelines.distributed_task_session import DistributedTaskSession
from pyado.oop.pipelines.environment import Environment
from pyado.oop.pipelines.pipeline import Pipeline, PipelineRun
from pyado.oop.pipelines.pipeline_library import PipelineLibrary
from pyado.oop.pipelines.project_pipelines import ProjectPipelines
from pyado.oop.pipelines.secure_file import SecureFile
from pyado.oop.pipelines.task_group import TaskGroup
from pyado.oop.pipelines.variable_group import VariableGroup
from pyado.oop.settings.service_endpoint import ServiceEndpoint

__all__ = [
    "Agent",
    "AgentPool",
    "AgentQueue",
    "Build",
    "BuildJob",
    "BuildPhase",
    "BuildStage",
    "BuildTask",
    "DistributedTaskSession",
    "Environment",
    "Pipeline",
    "PipelineLibrary",
    "PipelineRun",
    "ProjectPipelines",
    "SecureFile",
    "ServiceEndpoint",
    "TaskGroup",
    "VariableGroup",
]
