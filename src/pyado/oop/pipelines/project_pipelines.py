"""ProjectPipelines — the Pipelines section object for a project."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.pipelines import _build as _build_helpers
from pyado.oop.pipelines.agent import AgentQueue
from pyado.oop.pipelines.build import Build
from pyado.oop.pipelines.environment import Environment
from pyado.oop.pipelines.pipeline import Pipeline, PipelineRun
from pyado.oop.pipelines.pipeline_library import PipelineLibrary
from pyado.oop.pipelines.service_endpoint import ServiceEndpoint
from pyado.oop.pipelines.variable_group import VariableGroup
from pyado.raw import (
    AgentQueueId,
    BuildDetails,
    BuildExpand,
    BuildId,
    BuildSearchCriteria,
    BuildStatus,
    PipelineApproval,
    PipelineApprovalStatus,
    PipelineDefinitionInfo,
    PipelineId,
    PipelineRunId,
    VariableInfo,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project


class ProjectPipelines:
    """The Pipelines section of a project.

    Accessed via ``project.pipelines``.  Exposes all pipeline, build,
    approval, environment, agent queue, and library operations that belong
    to the ADO Pipelines section.

    Attributes:
        _project: The owning Project.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a ProjectPipelines section.

        Args:
            project: The Project this section belongs to.
        """
        self._project = project

    @property
    def library(self) -> PipelineLibrary:
        """The Pipeline Library sub-section (variable groups, secure files)."""
        return PipelineLibrary(self._project)

    # ------------------------------------------------------------------
    # Pipelines
    # ------------------------------------------------------------------

    def iter_pipelines(self) -> Iterator[Pipeline]:
        """Iterate over all pipeline definitions in the project.

        Yields:
            Pipeline for each pipeline definition.
        """
        for info in raw.iter_pipelines(self._project.api_call):
            yield Pipeline(self._project, info.id, info.name, info)

    def get_pipeline(self, name: str) -> Pipeline:
        """Return a pipeline by name.

        Args:
            name: Pipeline name (case-sensitive).

        Returns:
            Pipeline wrapping the requested pipeline.

        Raises:
            KeyError: If no pipeline with the given name exists.
        """
        for pipeline in self.iter_pipelines():
            if pipeline.name == name:
                return pipeline
        raise KeyError(name)

    def get_pipeline_by_id(self, pipeline_id: PipelineId) -> Pipeline:
        """Return a pipeline by numeric ID.

        The result is stored in (or retrieved from) the service cache so
        that ``build.pipeline`` and ``project.pipelines.get_pipeline_by_id``
        return the same object for the same pipeline.

        Args:
            pipeline_id: Numeric pipeline ID.

        Returns:
            Pipeline wrapping the requested pipeline.
        """
        service = self._project._service  # noqa: SLF001
        cache_key = str(self._project.api_call.url) + "/pipelines/" + str(pipeline_id)

        def _make() -> Pipeline:
            info = raw.get_pipeline(self._project.api_call, pipeline_id)
            return Pipeline(self._project, info.id, info.name, info)

        return service.oop_api.get_or_cache(cache_key, _make)

    def list_pipelines(self) -> list[Pipeline]:
        """Return all pipeline definitions in the project as a list."""
        return list(self.iter_pipelines())

    def iter_pipeline_definitions(
        self,
        *,
        name_filter: str | None = None,
    ) -> Iterator[PipelineDefinitionInfo]:
        """Iterate over pipeline definitions (Build API) in the project.

        Returns richer definition metadata than :meth:`iter_pipelines`
        (which uses the Pipelines v2 API).  Use this when you need fields
        such as the YAML file path or the queue/pool reference.

        Args:
            name_filter: Optional name substring filter passed to the API.

        Yields:
            PipelineDefinitionInfo for each matching definition.
        """
        yield from raw.iter_pipeline_definitions(
            self._project.api_call, name_filter=name_filter
        )

    def list_pipeline_definitions(
        self,
        *,
        name_filter: str | None = None,
    ) -> list[PipelineDefinitionInfo]:
        """Return pipeline definitions in the project as a list."""
        return list(self.iter_pipeline_definitions(name_filter=name_filter))

    # ------------------------------------------------------------------
    # Builds
    # ------------------------------------------------------------------

    def iter_builds(
        self,
        *,
        definition_id: PipelineId | None = None,
        status_filter: BuildStatus | None = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> Iterator[Build]:
        """Iterate over builds in the project.

        Args:
            definition_id: Filter by pipeline definition ID.
            status_filter: Filter by build status (e.g.
                ``BuildStatus.COMPLETED``).
            branch_name: Filter by source branch ref name
                (e.g. ``"refs/heads/main"``).
            top: Maximum number of builds to return.

        Yields:
            Build for each matching build.
        """
        service = self._project._service  # noqa: SLF001
        for info in raw.iter_builds(
            self._project.api_call,
            search_criteria=BuildSearchCriteria(
                definition_id=definition_id,
                status_filter=status_filter,
                branch_name=branch_name,
                top=top,
            ),
        ):
            build_api_call = raw.get_build_api_call(self._project.api_call, info.id)
            yield Build(self._project, build_api_call, info, service)

    def get_build(self, build_id: BuildId) -> Build:
        """Return a build by numeric ID.

        Args:
            build_id: Numeric build ID.

        Returns:
            Build wrapping the requested build.
        """
        service = self._project._service  # noqa: SLF001
        build_api_call = raw.get_build_api_call(self._project.api_call, build_id)
        info = raw.get_build_details(build_api_call)
        return Build(self._project, build_api_call, info, service)

    def start_build(
        self,
        pipeline_id: PipelineId,
        *,
        source_branch: str | None = None,
        source_version: str | None = None,
        parameters: dict[str, str] | None = None,
    ) -> Build:
        """Queue a new build run for a pipeline.

        Args:
            pipeline_id: The ID of the pipeline to run.
            source_branch: Source branch to build (e.g.
                ``"refs/heads/main"``).  Uses the definition default when
                omitted.
            source_version: Commit SHA to build.  Uses the branch HEAD when
                omitted.
            parameters: Optional key/value pairs passed to the pipeline as
                template parameters.

        Returns:
            Build for the newly queued build run.
        """
        service = self._project._service  # noqa: SLF001
        details = _build_helpers.start_build(
            self._project.api_call,
            pipeline_id,
            source_branch=source_branch,
            source_version=source_version,
            parameters=parameters,
        )
        build_api_call = raw.get_build_api_call(self._project.api_call, details.id)
        return Build(self._project, build_api_call, details, service)

    def get_build_with_expand(
        self,
        build_id: BuildId,
        expand: BuildExpand,
    ) -> Build:
        """Return a build with a specific expand mode.

        Args:
            build_id: Numeric build ID.
            expand: ``$expand`` value to include extra data in the response.

        Returns:
            Build wrapping the requested build with expanded info.
        """
        service = self._project._service  # noqa: SLF001
        build_api_call = raw.get_build_api_call(self._project.api_call, build_id)
        info = raw.get_build_details(build_api_call, expand=expand)
        return Build(self._project, build_api_call, info, service)

    def get_latest_build(
        self,
        pipeline_id: PipelineId,
        *,
        branch_name: str | None = None,
    ) -> Build | None:
        """Return the most recent build for a pipeline, or ``None``.

        Args:
            pipeline_id: The ID of the pipeline to look up builds for.
            branch_name: Optional branch filter.

        Returns:
            The most recent Build, or ``None`` if no builds exist.
        """
        return next(
            iter(
                self.iter_builds(
                    definition_id=pipeline_id, branch_name=branch_name, top=1
                )
            ),
            None,
        )

    def list_builds(
        self,
        *,
        definition_id: PipelineId | None = None,
        status_filter: BuildStatus | None = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> list[Build]:
        """Return builds in the project as a list."""
        return list(
            self.iter_builds(
                definition_id=definition_id,
                status_filter=status_filter,
                branch_name=branch_name,
                top=top,
            )
        )

    # ------------------------------------------------------------------
    # Pipeline runs (Pipelines v2 API)
    # ------------------------------------------------------------------

    def iter_runs(
        self,
        pipeline_id: PipelineId,
        *,
        top: int | None = None,
    ) -> Iterator[PipelineRun]:
        """Iterate over all runs of a specific pipeline.

        Args:
            pipeline_id: The ID of the pipeline to iterate runs for.
            top: Maximum number of runs to return.

        Yields:
            PipelineRun for each run, in API-returned order (newest first).
        """
        for info in raw.iter_pipeline_runs(
            self._project.api_call, pipeline_id, top=top
        ):
            yield PipelineRun(self.get_pipeline_by_id(pipeline_id), info)

    def get_run(self, pipeline_id: PipelineId, run_id: PipelineRunId) -> PipelineRun:
        """Return a specific pipeline run by ID.

        Args:
            pipeline_id: The ID of the pipeline the run belongs to.
            run_id: Numeric run ID.

        Returns:
            PipelineRun wrapping the requested run.
        """
        info = raw.get_pipeline_run(self._project.api_call, pipeline_id, run_id)
        return PipelineRun(self.get_pipeline_by_id(pipeline_id), info)

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def iter_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> Iterator[PipelineApproval]:
        """Iterate over pipeline environment approvals in the project.

        Args:
            state: Optional status filter.  When ``None``, approvals in all
                states are returned.

        Yields:
            PipelineApproval for each matching approval.
        """
        yield from raw.iter_approvals(self._project.api_call, state=state)

    def approve(
        self,
        approval_id: str,
        *,
        comment: str = "",
    ) -> None:
        """Approve a pending pipeline environment approval.

        Args:
            approval_id: UUID string of the approval to approve.
            comment: Optional comment to attach to the approval.
        """
        _build_helpers.approve_pipeline(
            self._project.api_call, approval_id, comment=comment
        )

    def reject(
        self,
        approval_id: str,
        *,
        comment: str = "",
    ) -> None:
        """Reject a pending pipeline environment approval.

        Args:
            approval_id: UUID string of the approval to reject.
            comment: Optional comment to attach to the rejection.
        """
        _build_helpers.reject_pipeline(
            self._project.api_call, approval_id, comment=comment
        )

    def list_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> list[PipelineApproval]:
        """Return pipeline environment approvals as a list."""
        return list(self.iter_approvals(state=state))

    # ------------------------------------------------------------------
    # Environments
    # ------------------------------------------------------------------

    def iter_environments(self) -> Iterator[Environment]:
        """Iterate over all pipeline environments in the project.

        Yields:
            Environment for each environment in the project.
        """
        for info in raw.iter_environments(self._project.api_call):
            env_api_call = raw.get_environment_api_call(self._project.api_call, info.id)
            yield Environment(self._project, env_api_call, info)

    def get_environment(self, name: str) -> Environment:
        """Return a pipeline environment by name.

        Args:
            name: Environment name (case-sensitive).

        Returns:
            Environment wrapping the requested environment.

        Raises:
            KeyError: If no environment with the given name exists.
        """
        for env in self.iter_environments():
            if env.name == name:
                return env
        raise KeyError(name)

    def list_environments(self) -> list[Environment]:
        """Return all pipeline environments in the project as a list."""
        return list(self.iter_environments())

    # ------------------------------------------------------------------
    # Agent queues
    # ------------------------------------------------------------------

    def iter_agent_queues(self) -> Iterator[AgentQueue]:
        """Iterate over all agent queues in the project.

        Yields:
            AgentQueue for each agent queue in the project.
        """
        for info in raw.iter_agent_queues(self._project.api_call):
            yield AgentQueue(self._project, info)

    def get_agent_queue(self, name: str) -> AgentQueue:
        """Return an agent queue by name.

        Args:
            name: Agent queue name (case-sensitive).

        Returns:
            AgentQueue wrapping the requested queue.

        Raises:
            KeyError: If no agent queue with the given name exists.
        """
        for queue in self.iter_agent_queues():
            if queue.name == name:
                return queue
        raise KeyError(name)

    def get_agent_queue_by_id(self, queue_id: AgentQueueId) -> AgentQueue:
        """Return an agent queue by numeric ID.

        Args:
            queue_id: Numeric agent queue ID.

        Returns:
            AgentQueue wrapping the requested queue.
        """
        info = raw.get_agent_queue(self._project.api_call, queue_id)
        return AgentQueue(self._project, info)

    def list_agent_queues(self) -> list[AgentQueue]:
        """Return all agent queues in the project as a list."""
        return list(self.iter_agent_queues())

    # ------------------------------------------------------------------
    # Service endpoints
    # ------------------------------------------------------------------

    def iter_service_endpoints(self) -> Iterator[ServiceEndpoint]:
        """Iterate over all service connections in the project.

        Yields:
            ServiceEndpoint for each service connection.
        """
        for info in raw.iter_service_endpoints(self._project.api_call):
            yield ServiceEndpoint(self._project, info)

    def list_service_endpoints(self) -> list[ServiceEndpoint]:
        """Return all service connections in the project as a list."""
        return list(self.iter_service_endpoints())

    # ------------------------------------------------------------------
    # Build details (convenience aliases used by Build.retry, etc.)
    # ------------------------------------------------------------------

    def get_build_details(
        self,
        build_id: BuildId,
        *,
        expand: BuildExpand | None = None,
    ) -> "BuildDetails":
        """Return raw BuildDetails for a build ID.

        Args:
            build_id: Numeric build ID.
            expand: Optional expand mode.

        Returns:
            BuildDetails from the API.
        """
        build_api_call = raw.get_build_api_call(self._project.api_call, build_id)
        return raw.get_build_details(build_api_call, expand=expand)

    # ------------------------------------------------------------------
    # Variable groups (forwarded to library for backwards compatibility)
    # ------------------------------------------------------------------

    def create_variable_group(
        self,
        name: str,
        variables: dict[str, VariableInfo],
        *,
        description: str | None = None,
        var_group_type: str = "Vsts",
        provider_data: Any = None,
    ) -> VariableGroup:
        """Create a new variable group in the project.

        Delegates to :meth:`PipelineLibrary.create_variable_group`.

        Args:
            name: Name for the new variable group.
            variables: Mapping of variable names to VariableInfo values.
            description: Optional description for the variable group.
            var_group_type: Variable group type (default: ``"Vsts"``).
            provider_data: Optional provider data (e.g. key vault config).

        Returns:
            VariableGroup wrapping the newly created variable group.
        """
        return self.library.create_variable_group(
            name,
            variables,
            description=description,
            var_group_type=var_group_type,
            provider_data=provider_data,
        )
