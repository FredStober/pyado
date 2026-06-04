"""OOP wrapper for an active (running) Azure DevOps pipeline task."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import high, raw
from pyado.oop.build_timeline import BuildJob, BuildTask
from pyado.raw import (
    ApiCall,
    BuildIssue,
    BuildLogId,
    BuildRecordInfo,
    BuildRecordType,
    JobEventName,
    JobEventResult,
    JobId,
    PlanId,
    TaskId,
    TimelineId,
)

if TYPE_CHECKING:
    from pyado.oop.build import Build
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["ActiveBuildTask"]


class ActiveBuildTask(BuildTask):
    """An active (running) task within an Azure DevOps pipeline.

    Used by external systems acting as a serverless ADO task — for example an
    AWS Lambda function that polls an ADO pipeline for work.  Inherits all
    read properties from :class:`~pyado.oop.build_timeline.BuildTask` (loaded
    lazily on first access).  Exposes the write operations (feed messages, log
    entries, timeline issue updates, task completion) that require the
    distributed-task runtime variables only available during pipeline
    execution.

    Instances are obtained from :meth:`Build.get_active_build_task`.

    The build timeline record is loaded lazily: the first access to any
    inherited property (e.g. ``.name``, ``.state``) triggers one API call to
    fetch the timeline records.  Call :meth:`refresh` to discard the cached
    record and re-fetch on the next access.

    ``send_feed`` and ``send_log`` use the ``7.1-preview.1`` API (preview).
    ``add_issues`` uses the stable ``7.1`` API.

    Attributes:
        _build: The Build this task belongs to.
        _hub_name: Distributed-task hub name (e.g. ``"build"``).
        _plan_id: The orchestration plan UUID.
        _timeline_id: The timeline UUID.
        _job_id: The job UUID.
        _task_instance_id: UUID identifying this task instance.
        _log_id: Lazily resolved task log ID.
    """

    def __init__(
        self,
        build: "Build",
        *,
        hub_name: str,
        plan_id: PlanId,
        timeline_id: TimelineId,
        job_id: JobId,
        task_instance_id: TaskId,
    ) -> None:
        """Construct an ActiveBuildTask.

        Args:
            build: The Build that owns this task.
            hub_name: Distributed-task hub name (e.g. ``"build"``).
            plan_id: The orchestration plan UUID.
            timeline_id: The timeline UUID.
            job_id: The job UUID.
            task_instance_id: UUID identifying this specific task instance.
        """
        super().__init__()  # _record=None, _job=None — loaded lazily
        self._build = build
        self._hub_name = hub_name
        self._plan_id = plan_id
        self._timeline_id = timeline_id
        self._job_id = job_id
        self._task_instance_id = task_instance_id
        self._log_id: BuildLogId | None = None

    # ------------------------------------------------------------------
    # Lazy record loading (overrides BuildTask._resolve)
    # ------------------------------------------------------------------

    def _resolve(self) -> BuildRecordInfo:
        """Return the timeline record, fetching it lazily on first call."""
        if self._record is None:
            self._record = self.get_record()
        return self._record

    # ------------------------------------------------------------------
    # Navigation (zero-cost)
    # ------------------------------------------------------------------

    @property
    def build(self) -> "Build":
        """Owning Build — zero-cost."""
        return self._build

    @property
    def project(self) -> "Project":
        """Project this task belongs to — zero-cost."""
        return self._build.project

    @property
    def org(self) -> "Organization":
        """Organisation this task belongs to — zero-cost."""
        return self._build.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard the cached timeline record and log ID.

        The next access to any inherited property (e.g. ``.name``,
        ``.state``) will re-fetch the timeline records from the API.
        """
        self._record = None
        self._log_id = None

    # ------------------------------------------------------------------
    # Internal API call helpers
    # ------------------------------------------------------------------

    def _make_plan_api_call(self) -> ApiCall:
        return raw.get_plan_api_call(
            self._build.project.api_call, self._hub_name, self._plan_id
        )

    def _make_timeline_api_call(self) -> ApiCall:
        return raw.get_timeline_api_call(
            self._build.project.api_call,
            self._hub_name,
            self._plan_id,
            self._timeline_id,
        )

    def _make_job_api_call(self) -> ApiCall:
        return raw.get_job_api_call(
            self._build.project.api_call,
            self._hub_name,
            self._plan_id,
            self._timeline_id,
            self._job_id,
        )

    def _make_log_api_call(self) -> ApiCall:
        """Return the log API call, resolving the log ID lazily on first use.

        Raises:
            RuntimeError: If the task has no log entry yet.
        """
        if self._log_id is None:
            record = self._resolve()
            if record.log is None:
                err_msg = f"Task {self._task_instance_id} has no log entry yet."
                raise RuntimeError(err_msg)
            self._log_id = record.log.id
        return raw.get_log_api_call(
            self._build.project.api_call,
            self._hub_name,
            self._plan_id,
            self._log_id,
        )

    # ------------------------------------------------------------------
    # Timeline record access
    # ------------------------------------------------------------------

    def get_record(self) -> BuildRecordInfo:
        """Fetch the timeline record for this task (always fresh).

        Fetches all timeline records for the build (one API call) and
        returns the ``Task``-type record whose ID matches
        :attr:`_task_instance_id`.  The result is cached by
        :meth:`_resolve`; call :meth:`refresh` to invalidate the cache.

        Returns:
            BuildRecordInfo for this task.

        Raises:
            ValueError: If no matching task record is found.
        """
        for record in raw.iter_timeline_records(self._build.api_call):
            if (
                record.type_name == BuildRecordType.TASK
                and record.id == self._task_instance_id
            ):
                return record
        err_msg = (
            f"Task record {self._task_instance_id!r} not found "
            f"in build {self._build.id}"
        )
        raise ValueError(err_msg)

    # ------------------------------------------------------------------
    # Navigation (API calls)
    # ------------------------------------------------------------------

    def get_job(self) -> BuildJob:
        """Find and return the parent BuildJob for this task.

        Fetches the build timeline (one API call via
        :meth:`Build.iter_stages`) and returns the :class:`BuildJob` whose
        ID matches the job ID supplied at construction.  The returned
        ``BuildJob`` has its full parent chain populated (``job.stage``,
        ``job.stage.build``, etc.).

        Returns:
            BuildJob for the job that owns this task.

        Raises:
            ValueError: If the job is not found in the build timeline.
        """
        for stage in self._build.iter_stages():
            for job in stage.iter_jobs():
                if job.id == self._job_id:
                    return job
        err_msg = f"Job {self._job_id!r} not found in build {self._build.id}"
        raise ValueError(err_msg)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def send_feed(self, messages: list[str]) -> None:
        """Send messages to the task's live feed.

        Uses the ``7.1-preview.1`` distributed-task API.

        Args:
            messages: Log lines to append to the feed.
        """
        high.send_job_feed(self._make_job_api_call(), messages)

    def send_log(self, message: str) -> None:
        """Append a message to the task's persistent log.

        Uses the ``7.1-preview.1`` distributed-task API.  The log ID is
        resolved lazily on first call and then cached; call :meth:`refresh`
        to clear the cache.

        Args:
            message: Text to append to the task log.
        """
        raw.post_job_logs(self._make_log_api_call(), message)

    def send_message(self, messages: list[str]) -> None:
        """Send messages to both the task feed and the task log.

        Uses the ``7.1-preview.1`` distributed-task API for both operations.

        Args:
            messages: Log lines to append to both feed and persistent log.
        """
        high.send_job_feed(self._make_job_api_call(), messages)
        log_api_call = self._make_log_api_call()
        for message in messages:
            raw.post_job_logs(log_api_call, message)

    def add_issues(self, issues: list[BuildIssue]) -> None:
        """Append issues to this task's timeline record.

        Uses the stable ``7.1`` distributed-task API.  Fetches the current
        record, merges in the new issues, then patches the timeline.

        Args:
            issues: Issues to append to the task's timeline record.
        """
        record = self._resolve()
        updated = record.model_copy(update={"issues": (record.issues or []) + issues})
        high.update_timeline_records(self._make_timeline_api_call(), [updated])

    def complete(self, *, succeeded: bool) -> None:
        """Signal task completion to the pipeline.

        Args:
            succeeded: When ``True``, reports success; otherwise reports
                failure.
        """
        result = JobEventResult.SUCCEEDED if succeeded else JobEventResult.FAILED
        high.send_job_event(
            self._make_plan_api_call(),
            self._task_instance_id,
            self._job_id,
            JobEventName.TASK_COMPLETED,
            result,
        )
