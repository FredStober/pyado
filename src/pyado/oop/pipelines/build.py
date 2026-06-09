"""OOP wrapper for Azure DevOps build resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import TYPE_CHECKING

from pyado import raw
from pyado.oop.pipelines import _build
from pyado.oop.pipelines.build_timeline import (
    BuildJob,
    BuildPhase,
    BuildStage,
    BuildTask,
)
from pyado.oop.pipelines.distributed_task_session import DistributedTaskSession
from pyado.oop.pipelines.pipeline import Pipeline, PipelineRun
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildDetails,
    BuildExpand,
    BuildLogId,
    BuildLogInfo,
    BuildRecordInfo,
    BuildRecordType,
    BuildResult,
    BuildStatus,
    JobId,
    PipelineApproval,
    PipelineApprovalStatus,
    PipelineRunInfo,
    PlanId,
    TaskId,
    TimelineId,
    WorkItemId,
)

if TYPE_CHECKING:
    from pyado.oop.boards.work_item import WorkItem
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

    **ADO concept:** a *build* (also called a *pipeline run*) is a single
    execution of a pipeline definition.  It is exposed by **two separate ADO
    APIs**:

    * **Build API** — ``build/builds/{buildId}`` (docs:
      `build/Builds <https://learn.microsoft.com/rest/api/azure/devops/build/builds>`_).
      Older, richer surface: artifacts, logs, tags, work-item associations,
      timeline, cancel, queue.
    * **Pipelines v2 API** — ``pipelines/{id}/runs/{runId}`` (docs:
      `pipelines/Runs <https://learn.microsoft.com/rest/api/azure/devops/pipelines/runs>`_).
      Newer, cleaner surface: ``finalYaml``, ``templateParameters``.  The
      numeric ``run id`` is identical to the ``build id``.

    ``Build`` uses the Build API surface.  When you need the Pipelines v2
    view of the same run, use :attr:`pipeline_run`.

    **Why it exists:** the raw ``build/builds`` endpoint returns a
    :class:`~pyado.raw.BuildDetails` dict of scalars.  ``Build`` adds:
    lazy-loaded caching (one HTTP call per refresh), timeline tree navigation
    (:meth:`iter_stages` → :meth:`~BuildStage.iter_jobs` → tasks, zero extra
    API calls), and the distributed-task session factory
    (:meth:`get_distributed_task_session`) that lets external systems write
    back into a running pipeline.  It also carries the back-reference to
    :attr:`project` and :attr:`pipeline` so navigation is always zero-cost.

    Unlike projects and pipelines, builds are not cached — each factory call
    returns a fresh instance with the current API state.

    Wraps a single ADO build and exposes its operations as instance methods.
    Instances are obtained from :meth:`ProjectPipelines.get_build`,
    :meth:`ProjectPipelines.iter_builds`, or
    :meth:`ProjectPipelines.start_build`.

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
        self._info: BuildDetails | None = info
        self._expand: BuildExpand | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> BuildDetails:
        """Build data captured at construction time (or last refresh)."""
        if self._info is None:
            self._info = raw.get_build_details(self._api_call, expand=self._expand)
        return self._info

    @property
    def id(self) -> int:
        """Numeric build ID."""
        return self.info.id

    @property
    def status(self) -> BuildStatus:
        """Current build status."""
        return self.info.status

    @property
    def number(self) -> str:
        """Build number string (e.g. ``"20240101.1"``)."""
        return self.info.build_number

    @property
    def result(self) -> BuildResult | None:
        """Build outcome once completed (e.g. ``"succeeded"``, ``"failed"``).

        ``None`` while the build is still running.
        """
        return self.info.result

    @property
    def source_branch(self) -> str:
        """Source branch used for this build (e.g. ``"refs/heads/main"``)."""
        return self.info.source_branch

    @property
    def start_time(self) -> datetime | None:
        """UTC datetime when the build started, or ``None`` if not yet started."""
        return self.info.start_time

    @property
    def finish_time(self) -> datetime | None:
        """UTC datetime when the build finished, or ``None`` if not yet complete."""
        return self.info.finish_time

    @property
    def queue_time(self) -> datetime | None:
        """UTC datetime when the build was queued, or ``None`` if not available."""
        return self.info.queue_time

    @property
    def source_version(self) -> str:
        """Commit SHA that triggered this build."""
        return self.info.source_version

    @property
    def requested_by(self) -> str:
        """Display name of the identity that queued the build."""
        return self.info.requested_by.display_name

    @property
    def requested_for(self) -> str | None:
        """Display name of the identity the build was requested for, or ``None``.

        For CI builds this is usually the commit author; for manually-queued
        builds it may differ from :attr:`requested_by`.
        """
        return self.info.requested_for.display_name if self.info.requested_for else None

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
        defn = self.info.definition
        cache_key = str(self._project.api_call.url) + "/pipelines/" + str(defn.id)
        return self._service.oop_api.get_or_cache(
            cache_key,
            lambda: Pipeline(self._project, defn.id, defn.name),
        )

    @property
    def pipeline_run(self) -> PipelineRun:
        """The Pipelines v2 view of this build run.

        Fetches the run via the Pipelines v2 API and returns a
        :class:`PipelineRun` bound to this build's owning pipeline.

        Returns:
            PipelineRun for this build.
        """
        pipeline = self.pipeline
        info = raw.get_pipeline_run(self.project.api_call, pipeline.id, self.id)
        return PipelineRun(pipeline, info)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self, expand: BuildExpand | None = None) -> None:
        """Discard cached build info.

        The next access to :attr:`info` re-fetches from the API.

        Args:
            expand: Optional ``$expand`` value to use on the next fetch.
                When provided, replaces any previously stored expand value;
                when ``None``, previously stored expand is preserved.
        """
        if expand is not None:
            self._expand = expand
        self._info = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def update(self, status: BuildStatus) -> None:
        """Update the status of this build.

        Args:
            status: New build status to set (e.g.
                ``BuildStatus.CANCELLING``).
        """
        self._info = raw.patch_build(self._api_call, status)

    def cancel(self) -> None:
        """Request cancellation of this running build.

        Updates the wrapper's cached info to reflect the cancelling state.
        Read :attr:`info` after the call to inspect the cancelling state
        without a separate :meth:`refresh` call.
        """
        self._info = _build.cancel_build(self._api_call)

    def cancel_run(self) -> PipelineRunInfo:
        """Cancel this build via the Pipelines v2 API.

        Delegates to :func:`~pyado.oop.pipelines._build.cancel_pipeline_run`,
        which uses the Build API to request cancellation and then re-fetches
        the run via the Pipelines API.  Use :meth:`cancel` instead when you
        only need a :class:`~pyado.raw.BuildDetails` response.

        Returns:
            PipelineRunInfo reflecting the cancelling/canceled state.
        """
        return _build.cancel_pipeline_run(
            self._project.api_call,
            self.info.definition.id,
            self.info.id,
        )

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def iter_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> Iterator[PipelineApproval]:
        """Iterate over environment approvals for this build.

        Scoped to this build's run ID, so only approvals that belong to
        this specific run are returned.

        Args:
            state: Optional status filter (e.g.
                ``PipelineApprovalStatus.PENDING``).  When ``None``, approvals
                in all states are returned.

        Yields:
            PipelineApproval for each matching approval on this build.
        """
        yield from raw.iter_approvals(
            self._project.api_call,
            state=state,
            pipeline_run_ids=[self.id],
        )

    def list_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> list[PipelineApproval]:
        """Return environment approvals for this build as a list."""
        return list(self.iter_approvals(state=state))

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def iter_artifacts(self) -> Iterator[BuildArtifact]:
        """Iterate over artifacts published by the build.

        Yields:
            BuildArtifact for each artifact associated with the build.
        """
        yield from raw.iter_build_artifacts(self._api_call)

    def download_artifact(self, artifact: BuildArtifact) -> bytes | None:
        """Download the bytes of a build artifact.

        Args:
            artifact: A BuildArtifact obtained from :meth:`iter_artifacts`.

        Returns:
            Raw artifact bytes, or ``None`` if no download URL is available.
        """
        return raw.get_build_artifact_bytes(self._api_call, artifact)

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
            Updated list of all tag name strings on the build after the
            operation.  ADO returns the full tag list; this is a direct
            pass-through.
        """
        return raw.post_build_tag(self._api_call, tag)

    def remove_tag(self, tag: str) -> list[str]:
        """Remove a tag from the build.

        Args:
            tag: Tag name to remove.

        Returns:
            Updated list of all tag name strings on the build after the
            operation.  ADO returns the full tag list; this is a direct
            pass-through.
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

    def find_task(
        self, predicate: Callable[[BuildRecordInfo], bool]
    ) -> BuildRecordInfo | None:
        """Return the first timeline record for which *predicate* returns True.

        Fetches all timeline records in one API call, then returns the first
        record for which *predicate* returns ``True``, or ``None`` if no
        record matches.

        Args:
            predicate: A callable that accepts a
                :class:`~pyado.raw.BuildRecordInfo` and returns ``True`` when
                it is the desired record.

        Returns:
            The first matching :class:`~pyado.raw.BuildRecordInfo`, or
            ``None`` if no record satisfies *predicate*.
        """
        for record in raw.iter_timeline_records(self._api_call):
            if predicate(record):
                return record
        return None

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
    # Logs
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

    def iter_logs(self) -> Iterator[BuildLogInfo]:
        """Iterate over all log entries for this build.

        Yields:
            BuildLogInfo for each log container associated with the build.
        """
        yield from raw.iter_build_logs(self._api_call)

    def get_all_log_text(self, *, separator: str = "\n") -> str:
        r"""Fetch and concatenate the text of every build log.

        Makes one API call to list all log IDs, then one call per log to
        fetch the text.  Logs are joined with *separator*.

        Args:
            separator: String inserted between consecutive log texts
                (default: ``"\n"``).

        Returns:
            All log content as a single string.
        """
        return separator.join(
            raw.get_build_log(self._api_call, log.id)
            for log in raw.iter_build_logs(self._api_call)
        )

    # ------------------------------------------------------------------
    # Work items
    # ------------------------------------------------------------------

    def iter_work_item_ids(self) -> Iterator[WorkItemId]:
        """Iterate over work item IDs associated with the build.

        Yields:
            Integer work item IDs linked to this build.
        """
        yield from _build.iter_build_work_item_ids(self._api_call)

    def iter_work_items(self) -> "Iterator[WorkItem]":
        """Iterate over work items associated with the build.

        Convenience wrapper that resolves the linked IDs via
        :meth:`iter_work_item_ids` and then fetches the work item details in
        a single batch call.

        Yields:
            WorkItem for each linked work item.
        """
        ids = list(self.iter_work_item_ids())
        if ids:
            yield from self._project.boards.get_work_items(ids)

    def iter_work_items_between(
        self,
        older_build: "Build",
        *,
        top: int | None = None,
    ) -> "Iterator[WorkItem]":
        """Iterate over work items in the range (older_build, this build].

        Fetches the work item IDs via
        :func:`~pyado.raw.iter_work_items_between_builds`, then resolves them
        in a single batch call.

        Args:
            older_build: The earlier build that marks the exclusive lower
                bound of the range.
            top: Optional cap on the number of work items returned.

        Yields:
            WorkItem for each work item in the build range.
        """
        ids = [
            ref.id
            for ref in raw.iter_work_items_between_builds(
                self._project.api_call,
                older_build.id,
                self.id,
                top=top,
            )
        ]
        if ids:
            yield from self._project.boards.get_work_items(ids)

    def iter_work_item_ids_between(
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
    # Distributed-task session (serverless / external task pattern)
    # ------------------------------------------------------------------

    def get_distributed_task_session(
        self,
        *,
        bearer_token: str = "",
        hub_name: str,
        plan_id: PlanId,
        timeline_id: TimelineId,
        job_id: JobId,
        task_instance_id: TaskId,
    ) -> DistributedTaskSession:
        """Return a DistributedTaskSession for a running pipeline task.

        This factory is intended for external systems acting as a serverless
        ADO task (e.g. an AWS Lambda polling ADO for work).  Pass the
        distributed-task runtime variables that ADO injects as pipeline
        environment variables, plus the pipeline's own bearer token.

        Args:
            bearer_token: Pipeline bearer token (``System.AccessToken``).
                Required for write operations because the distributed-task
                endpoints only accept the pipeline's own bearer token, not a
                PAT.  Defaults to ``""`` for read-only or navigation use.
            hub_name: Distributed-task hub name (e.g. ``"Build"``).
            plan_id: Value of ``$(system.planId)`` / ``SYSTEM_PLANID``.
            timeline_id: Value of ``$(system.timelineId)`` /
                ``SYSTEM_TIMELINEID``.
            job_id: Value of ``$(system.jobId)`` / ``SYSTEM_JOBID``.
            task_instance_id: Value of the task instance UUID
                (``AGENT_TASKINSTANCEID``).

        Returns:
            DistributedTaskSession bound to this build and the given task.
        """
        collection_uri = str(self._service.oop_api.org_base_api_call.url)
        return DistributedTaskSession(
            bearer_token,
            collection_uri=collection_uri,
            team_project_id=str(self._project.id),
            build_id=self.id,
            hub_name=hub_name,
            plan_id=plan_id,
            timeline_id=timeline_id,
            job_id=job_id,
            task_instance_id=task_instance_id,
            oop_build=self,
        )

    def retry(self) -> "Build":
        """Queue a new build run using the same definition and source branch.

        Returns:
            A new :class:`Build` object for the queued build run.
        """
        new_details = _build.start_build(
            self._project.api_call,
            self.info.definition.id,
            source_branch=self.info.source_branch,
        )
        new_api_call = raw.get_build_api_call(self._project.api_call, new_details.id)
        return Build(self._project, new_api_call, new_details, self._service)

    def list_artifacts(self) -> list[BuildArtifact]:
        """Return all artifacts for this build as a list."""
        return list(self.iter_artifacts())

    def list_tags(self) -> list[str]:
        """Return all tags for this build as a list."""
        return list(self.iter_tags())

    def list_timeline_records(self) -> list[BuildRecordInfo]:
        """Return all timeline records for this build as a list."""
        return list(self.iter_timeline_records())

    def list_stages(self) -> list[BuildStage]:
        """Return all stages for this build as a list."""
        return list(self.iter_stages())

    def list_logs(self) -> list[BuildLogInfo]:
        """Return all log entries for this build as a list."""
        return list(self.iter_logs())

    def list_work_item_ids(self) -> list[WorkItemId]:
        """Return all work item IDs for this build as a list."""
        return list(self.iter_work_item_ids())

    def list_work_items(self) -> "list[WorkItem]":
        """Return all work items for this build as a list."""
        return list(self.iter_work_items())

    def list_work_items_between(
        self,
        older_build: "Build",
        *,
        top: int | None = None,
    ) -> "list[WorkItem]":
        """Return all work items between two builds as a list."""
        return list(self.iter_work_items_between(older_build, top=top))

    def list_work_item_ids_between(
        self,
        older_build: "Build",
        *,
        top: int | None = None,
    ) -> list[WorkItemId]:
        """Return all work item IDs between two builds as a list."""
        return list(self.iter_work_item_ids_between(older_build, top=top))
