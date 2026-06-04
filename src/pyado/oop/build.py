"""OOP wrapper for Azure DevOps build resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING

from pyado import high, raw
from pyado.oop.active_build_task import ActiveBuildTask
from pyado.oop.build_timeline import BuildJob, BuildPhase, BuildStage, BuildTask
from pyado.oop.pipeline import Pipeline
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildLogId,
    BuildRecordInfo,
    BuildRecordType,
    BuildResult,
    BuildStatus,
    JobId,
    PipelineRunInfo,
    PlanId,
    TaskId,
    TimelineId,
    WorkItemId,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.service import AzureDevOpsService

__all__ = [
    "Build",
    "BuildJob",
    "BuildPhase",
    "BuildStage",
    "BuildTask",
]


class Build:
    """An Azure DevOps build resource.

    Wraps a single ADO build and exposes its operations as instance methods.
    Instances are obtained from :meth:`Project.get_build`,
    :meth:`Project.iter_builds`, or :meth:`Project.start_build`.

    Unlike projects and pipelines, builds are not cached — each factory call
    returns a fresh instance with the current API state.

    Attributes:
        _project: The Project this build belongs to.
        _service: The owning AzureDevOpsService (for cache access).
        _api_call: Build-level API call used by all operations.
        _info: The build data returned from the API at construction time.
    """

    def __init__(
        self,
        project: "Project",
        build_api_call: ApiCall,
        info: BuildDetails,
        service: "AzureDevOpsService",
    ) -> None:
        """Construct a Build wrapper.

        Args:
            project: The Project that owns this build.
            build_api_call: Build-level ADO API call (from
                raw.get_build_api_call).
            info: Build data as returned from the API.
            service: The AzureDevOpsService that owns this build (used for
                the object cache).
        """
        self._project = project
        self._service = service
        self._api_call = build_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> BuildDetails:
        """Build data captured at construction time (or last refresh)."""
        return self._info

    @property
    def id(self) -> int:
        """Numeric build ID."""
        return self._info.id

    @property
    def status(self) -> BuildStatus:
        """Current build status."""
        return self._info.status

    @property
    def number(self) -> str:
        """Build number string (e.g. ``"20240101.1"``)."""
        return self._info.build_number

    @property
    def result(self) -> BuildResult | None:
        """Build outcome once completed (e.g. ``"succeeded"``, ``"failed"``).

        ``None`` while the build is still running.
        """
        return self._info.result

    @property
    def source_branch(self) -> str:
        """Source branch used for this build (e.g. ``"refs/heads/main"``)."""
        return self._info.source_branch

    @property
    def start_time(self) -> datetime | None:
        """UTC datetime when the build started, or ``None`` if not yet started."""
        return self._info.start_time

    @property
    def finish_time(self) -> datetime | None:
        """UTC datetime when the build finished, or ``None`` if not yet complete."""
        return self._info.finish_time

    @property
    def api_call(self) -> ApiCall:
        """Build-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this build belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this build belongs to — zero-cost."""
        return self._project.org

    @property
    def pipeline(self) -> Pipeline:
        """Pipeline definition that produced this build — zero-cost.

        The Pipeline object is looked up from (or inserted into) the service
        cache using the definition id and name embedded in the build info.
        No API call is made unless :attr:`Pipeline.info` is accessed.
        """
        defn = self._info.definition
        cache_key = str(self._project.api_call.url) + "/pipelines/" + str(defn.id)
        return self._service.oop_api.get_or_cache(
            cache_key,
            lambda: Pipeline(self._project, defn.id, defn.name),
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-fetch build info from the API immediately."""
        self._info = raw.get_build_details(self._api_call)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cancel(self) -> BuildDetails:
        """Request cancellation of this running build.

        Returns:
            BuildDetails with status ``"cancelling"``; transitions to
            ``"completed"`` with result ``"canceled"`` once the agent
            acknowledges.
        """
        return high.cancel_build(self._api_call)

    def cancel_run(self) -> PipelineRunInfo:
        """Request cancellation of this build via the Pipelines v2 endpoint.

        Use this when the build was queued through a Pipelines v2 definition
        and you need the run to reflect a ``"canceling"`` state via that API.
        For classic builds use :meth:`cancel` instead.

        Returns:
            PipelineRunInfo with state ``"canceling"``; transitions to
            ``"completed"`` with result ``"canceled"`` once the agent
            acknowledges.
        """
        return high.cancel_pipeline_run(
            self._project.api_call,
            self._info.definition.id,
            self.id,
        )

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

    def iter_stages(self) -> Iterator[BuildStage]:
        """Iterate over the stages of the build.

        Fetches all timeline records in a single API call, then yields a
        :class:`BuildStage` for each ``Stage``-type record.  Navigate into
        jobs and tasks via :meth:`BuildStage.iter_jobs` and
        :meth:`BuildJob.iter_tasks` — no additional API calls are made.

        Yields:
            BuildStage for each stage in the build timeline.
        """
        all_records = list(raw.iter_timeline_records(self._api_call))
        for record in all_records:
            if record.type_name == BuildRecordType.STAGE:
                yield BuildStage(record, all_records, build=self)

    # ------------------------------------------------------------------
    # Work items
    # ------------------------------------------------------------------

    def get_log_text(self, log_id: BuildLogId) -> str:
        """Fetch the plain-text content of a build log.

        Args:
            log_id: Numeric log ID from a :class:`~pyado.raw.BuildLogInfo`
                record.  Obtain it via :attr:`BuildTask.log`,
                :attr:`BuildJob.log`, or :attr:`BuildStage.log`.

        Returns:
            Log content as a decoded UTF-8 string.
        """
        return raw.get_build_log(self._api_call, log_id)

    def iter_work_item_ids(self) -> Iterator[WorkItemId]:
        """Iterate over work item IDs associated with the build.

        Yields:
            Integer work item IDs linked to this build.
        """
        yield from high.iter_build_work_item_ids(self._api_call)

    def iter_work_items_between(
        self,
        older_build: "Build",
        *,
        top: int | None = None,
    ) -> Iterator[WorkItemId]:
        """Iterate over work item IDs in the range (older_build, this build].

        Returns work items associated with any build between *older_build*
        (exclusive) and this build (inclusive).  Useful for generating a
        changelog between two consecutive pipeline runs.

        Args:
            older_build: The earlier build that marks the exclusive lower
                bound of the range.
            top: Optional cap on the number of work items returned.

        Yields:
            Integer work item IDs in the range.
        """
        for ref in raw.iter_work_items_between_builds(
            self._project.api_call,
            older_build.id,
            self.id,
            top=top,
        ):
            yield ref.id

    # ------------------------------------------------------------------
    # Active build task (serverless / external task pattern)
    # ------------------------------------------------------------------

    def get_active_build_task(
        self,
        *,
        hub_name: str,
        plan_id: PlanId,
        timeline_id: TimelineId,
        job_id: JobId,
        task_instance_id: TaskId,
    ) -> ActiveBuildTask:
        """Return an ActiveBuildTask for a running pipeline task.

        This factory is intended for external systems acting as a serverless
        ADO task (e.g. an AWS Lambda polling ADO for work).  Pass the
        distributed-task runtime variables that ADO injects as pipeline
        environment variables.

        Args:
            hub_name: Distributed-task hub name (e.g. ``"build"``).
            plan_id: Value of ``$(system.planId)`` / ``SYSTEM_PLANID``.
            timeline_id: Value of ``$(system.timelineId)`` /
                ``SYSTEM_TIMELINEID``.
            job_id: Value of ``$(system.jobId)`` / ``SYSTEM_JOBID``.
            task_instance_id: Value of the task instance UUID
                (``AGENT_TASKINSTANCEID``).

        Returns:
            ActiveBuildTask bound to this build and the given task.
        """
        return ActiveBuildTask(
            self,
            hub_name=hub_name,
            plan_id=plan_id,
            timeline_id=timeline_id,
            job_id=job_id,
            task_instance_id=task_instance_id,
        )

    def retry(self) -> "Build":
        """Queue a new build run using the same definition and source branch.

        Returns:
            A new :class:`Build` object for the queued build run.
        """
        new_details = high.start_build(
            self._project.api_call,
            self._info.definition.id,
            source_branch=self._info.source_branch,
        )
        new_api_call = raw.get_build_api_call(self._project.api_call, new_details.id)
        return Build(self._project, new_api_call, new_details, self._service)
