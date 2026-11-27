"""OOP wrapper for Azure DevOps build resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator, Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pyado import raw
from pyado.oop.pipelines import _build
from pyado.oop.pipelines.build_tests import CodeCoverage, TestResult, TestRun
from pyado.oop.pipelines.pipeline import Pipeline, PipelineRun
from pyado.raw import (
    ApiCall,
    BuildArtifact,
    BuildAttachmentInfo,
    BuildDetails,
    BuildExpand,
    BuildLogId,
    BuildLogInfo,
    BuildRecordInfo,
    BuildResult,
    BuildStatus,
    ContainerItem,
    FileCoverage,
    PipelineApproval,
    PipelineApprovalStatus,
    PipelineRunInfo,
    TestRunCreate,
    TestRunState,
    WorkItemId,
)

if TYPE_CHECKING:
    from pyado.oop.boards.work_item import WorkItem
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.service import AzureDevOpsService

__all__ = [
    "Build",
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
    lazy-loaded caching (one HTTP call per refresh),
    It also carries the back-reference to :attr:`project` and :attr:`pipeline`
    so navigation is always zero-cost.

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

    def cancel(self) -> "Build":
        """Request cancellation of this running build.

        Updates the wrapper's cached info to reflect the cancelling state.
        Read :attr:`info` after the call to inspect the cancelling state
        without a separate :meth:`refresh` call.

        Returns:
            ``self`` with status ``"cancelling"``; transitions to
            ``"completed"`` once the agent acknowledges.
        """
        self._info = _build.cancel_build(self._api_call)
        return self

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

        The underlying endpoint has no filter for the pipeline run
        (build) an approval belongs to, so this fetches approvals
        across the whole project (scoped by *state*, to stay under
        that endpoint's 250-row cap) and filters to this build's id
        locally.

        Args:
            state: Optional status filter (e.g.
                ``PipelineApprovalStatus.PENDING``).  When ``None``, approvals
                in all states are returned — subject to the endpoint's
                250-row cap across the whole project, so pass a *state*
                whenever the caller only cares about one status.

        Yields:
            PipelineApproval for each matching approval on this build.
        """
        for approval in raw.iter_approvals(
            self._project.api_call,
            state=state,
        ):
            if approval.build_id == self.id:
                yield approval

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
    # Tests tab and Code Coverage tab
    # ------------------------------------------------------------------

    def iter_test_runs(self, *, include_deleted: bool = False) -> Iterator[TestRun]:
        """Iterate over the test runs of the build (the Tests tab groups).

        A build can have many runs, for example one per matrix job.  A deleted
        run is still listed by the API (state ``"255"``) but cannot be read, so
        it is skipped like the portal does.

        Args:
            include_deleted: Also yield the deleted runs.

        Yields:
            A :class:`TestRun` for each run.
        """
        for info in raw.iter_build_test_runs(self._project.api_call, self.id):
            run = TestRun(self, info)
            if include_deleted or not run.is_deleted:
                yield run

    def list_test_runs(self, *, include_deleted: bool = False) -> list[TestRun]:
        """Return the test runs of this build as a list."""
        return list(self.iter_test_runs(include_deleted=include_deleted))

    def add_test_run(
        self,
        name: str,
        *,
        comment: str | None = None,
        state: Literal[TestRunState.NOT_STARTED, TestRunState.IN_PROGRESS] = (
            TestRunState.IN_PROGRESS
        ),
    ) -> TestRun:
        """Create a test run for this build.

        There is no flavor/platform argument.  A pair on a test run is stored by
        Azure DevOps but not shown by the Tests tab (it groups by run name), and
        tagged runs together with coverage written only under non-empty pairs
        left the coverage ``inProgress`` for 15 minutes in two lab builds, so
        trying to use them can cause finalisation problems.

        A run is created
        ``InProgress``; close it with :meth:`TestRun.complete` after its results
        are added.  An in-progress run without results was not listed by the portal
        (measured; the two causes were not separated).

        Args:
            name: Run name, shown as the group row of the Tests tab.
            comment: Optional run comment.
            state: ``NotStarted`` or ``InProgress`` (a run cannot start completed).

        Returns:
            The created run.
        """
        request = TestRunCreate(
            name=name,
            build={"id": self.id},
            comment=comment,
            state=state,
        )
        info = raw.post_test_run(self._project.api_call, request)
        return TestRun(self, info)

    def iter_test_results(self) -> Iterator["TestResult"]:
        """Iterate over the results of all runs, like the flat Tests tab.

        Yields:
            A :class:`TestResult` for each result; ``result.run`` tells which
            run it belongs to.
        """
        for run in self.iter_test_runs():
            yield from run.iter_results()

    def list_test_results(self) -> list["TestResult"]:
        """Return the results of all runs as a list."""
        return list(self.iter_test_results())

    def iter_code_coverage(self) -> Iterator[CodeCoverage]:
        """Iterate over the coverage entries (one per flavor/platform pair).

        One entry per flavor/platform pair the API holds; pyado writes only the
        entry without a pair.  Nothing is yielded when the build has no coverage.

        Yields:
            A :class:`CodeCoverage` for each pair.
        """
        summary = raw.get_code_coverage(self._project.api_call, self.id)
        for data in summary.coverage_data:
            yield CodeCoverage(self, data, summary.status)

    def list_code_coverage(self) -> list[CodeCoverage]:
        """Return all coverage entries of this build as a list."""
        return list(self.iter_code_coverage())

    def publish_code_coverage(
        self,
        files: list[FileCoverage],
        *,
        label: str = "line",
    ) -> None:
        """Write the coverage of this build the way the publish task does.

        Stores the per-file line status and one figure (computed from the files)
        under the empty flavor/platform pair, as the real publish task does.  Do
        it while the build runs, or shortly after.  There is no pair argument: a
        pair cannot be shown in Azure DevOps, and coverage written only under
        non-empty pairs, together with tagged test runs, stayed ``inProgress``
        for 15 minutes in two lab builds.  When the build ends after an agent
        job, the service adds an entry derived from the files.

        Args:
            files: Line status per source file (absolute agent paths).
            label: Figure label; the service renames ``line`` to ``Lines``.
        """
        raw.publish_code_coverage(
            self._project.api_call,
            self.id,
            files,
            label=label,
        )

    def publish_coverage_report(self, files: dict[str, bytes]) -> "raw.BuildArtifact":
        """Upload a coverage report folder, so the Code Coverage tab shows it.

        Args:
            files: Path inside the report folder to content; needs an
                ``index.html`` and no empty file.

        Returns:
            The created artifact.

        Raises:
            ValueError: If the build has no file container.
        """
        container_id = raw.get_build_container_id(self._project.api_call, self.id)
        if container_id is None:
            msg = f"build {self.id} has no file container"
            raise ValueError(msg)
        return raw.publish_coverage_report(
            self._service.oop_api.org_base_api_call,
            self._project.api_call,
            self.id,
            container_id,
            files,
        )

    # ------------------------------------------------------------------
    # Timeline attachments and the build file container
    # ------------------------------------------------------------------

    def iter_attachments(self, attachment_type: str) -> Iterator[BuildAttachmentInfo]:
        """Iterate over the timeline attachments of one type.

        Args:
            attachment_type: For example ``raw.SUMMARY_ATTACHMENT_TYPE`` for the
                task summaries of the Extensions tab.

        Yields:
            BuildAttachmentInfo for each attachment.
        """
        yield from raw.iter_build_attachments(
            self._project.api_call, self.id, attachment_type
        )

    def list_attachments(self, attachment_type: str) -> list[BuildAttachmentInfo]:
        """Return the timeline attachments of one type as a list."""
        return list(self.iter_attachments(attachment_type))

    def iter_summaries(self) -> Iterator[BuildAttachmentInfo]:
        """Iterate over the task summaries (cards of the Extensions tab).

        Yields:
            BuildAttachmentInfo for each summary; ``record_id`` tells which
            timeline record owns it (a name can appear on several records).
        """
        yield from raw.iter_build_summaries(self._project.api_call, self.id)

    def list_summaries(self) -> list[BuildAttachmentInfo]:
        """Return all task summaries of this build as a list."""
        return list(self.iter_summaries())

    def add_summaries(
        self, record_id: UUID, summaries: Mapping[str, str | bytes]
    ) -> None:
        """Attach summaries (markdown cards) to a Task or Job record.

        Each entry becomes a card of the Extensions tab, titled by the file name.
        A summary is identified by record plus name: an existing name is
        replaced.  This also works on a build that has already finished.  A
        summary cannot be deleted.

        Args:
            record_id: Id of a Task or Job record (see :meth:`find_task`).
            summaries: File name to markdown or HTML (text is sent as UTF-8).

        Raises:
            ValueError: If the build has no timeline yet.
        """
        timeline = self._api_call.get("timeline", version="7.1")
        plan = timeline.get("id") if isinstance(timeline, dict) else None
        if plan is None:
            msg = f"build {self.id} has no timeline yet"
            raise ValueError(msg)
        timeline_call = raw.get_timeline_api_call(
            self._project_id_api_call(), "build", UUID(str(plan)), UUID(str(plan))
        )
        raw.put_record_summaries(timeline_call, str(record_id), summaries)

    def _project_id_api_call(self) -> ApiCall:
        """Project call addressed by the project *id*.

        The ``distributedtask`` write routes answer an empty HTTP 400 when the URL
        carries the project name (measured), so they need this call.

        Returns:
            The project-level call with the project UUID in the URL.
        """
        return self._service.oop_api.make_project_api_call(str(self._project.id))

    def _container_api_call(self) -> ApiCall | None:
        """Call for the build's file container, or ``None`` if it has none.

        Returns:
            The container call, or ``None``.
        """
        container_id = raw.get_build_container_id(self._project.api_call, self.id)
        if container_id is None:
            return None
        return raw.get_container_api_call(
            self._service.oop_api.org_base_api_call, container_id
        )

    def iter_container_items(self, path: str = "") -> Iterator[ContainerItem]:
        """Iterate over the files and folders of the build's file container.

        Args:
            path: Folder below the container root; empty for the root.

        Yields:
            A ContainerItem for each file or folder (nothing without a container).
        """
        container = self._container_api_call()
        if container is not None:
            yield from raw.iter_container_items(container, path)

    def list_container_items(self, path: str = "") -> list[ContainerItem]:
        """Return the container items below ``path`` as a list."""
        return list(self.iter_container_items(path))

    def get_container_file(self, path: str) -> bytes | None:
        """Read one file of the build's file container.

        Args:
            path: File path inside the container.

        Returns:
            The bytes, or ``None`` when the build has no container.
        """
        container = self._container_api_call()
        if container is None:
            return None
        return raw.get_container_item_bytes(container, path)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def iter_tags(self) -> Iterator[str]:
        """Iterate over the tags set on the build.

        Yields:
            Tag name strings.
        """
        yield from raw.iter_build_tags(self._api_call)

    def add_tag(self, tag: str) -> None:
        """Add a tag to the build.

        Args:
            tag: Tag name to add.
        """
        raw.put_build_tag(self._api_call, tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the build.

        Args:
            tag: Tag name to remove.
        """
        raw.delete_build_tag(self._api_call, tag)

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

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def get_log_text(self, log_id: BuildLogId) -> str:
        """Fetch the plain-text content of a build log.

        Args:
            log_id: Numeric log ID from a :class:`~pyado.raw.BuildLogInfo`
                record.  Obtain it from the ``log`` field of a record returned
                by :meth:`iter_timeline_records`.

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

    def iter_work_item_ids(self, *, top: int = 10000) -> Iterator[WorkItemId]:
        """Iterate over work item IDs associated with the build.

        Args:
            top: Maximum number of work item ids to return.

        Yields:
            Integer work item IDs linked to this build.
        """
        yield from _build.iter_build_work_item_ids(self._api_call, top=top)

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
            yield from self._project.boards.list_work_items_by_ids(ids)

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
            yield from self._project.boards.list_work_items_by_ids(ids)

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

    def list_logs(self) -> list[BuildLogInfo]:
        """Return all log entries for this build as a list."""
        return list(self.iter_logs())

    def list_work_item_ids(self, *, top: int = 10000) -> list[WorkItemId]:
        """Return all work item IDs for this build as a list."""
        return list(self.iter_work_item_ids(top=top))

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
