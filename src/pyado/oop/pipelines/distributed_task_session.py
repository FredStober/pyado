"""OOP wrapper for an Azure DevOps distributed-task session."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ApiCall,
    BuildId,
    BuildIssue,
    BuildLogId,
    BuildRecordInfo,
    BuildRecordType,
    JobId,
    PlanId,
    TaskId,
    TimelineId,
)
from pyado.raw._core import _ADO_URL_ADAPTER

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.pipelines.build import Build
    from pyado.oop.project import Project

__all__ = ["DistributedTaskSession"]


class DistributedTaskSession:
    """A distributed-task session for an external system acting as a pipeline task.

    **ADO concept:** ADO's *distributed task* (also called *agentless* or
    *serverless*) pattern lets an external system (e.g. an AWS Lambda) act as
    a pipeline task.  ADO injects five runtime UUIDs as environment variables
    when the pipeline step starts:

    * ``SYSTEM_PLANID`` — identifies the *orchestration plan* root
      (``distributedtask/hubs/{hub}/plans/{planId}``).
    * ``SYSTEM_TIMELINEID`` — identifies the timeline inside that plan.
    * ``SYSTEM_JOBID`` — identifies the job record whose child this task is.
    * ``AGENT_TASKINSTANCEID`` — identifies this specific task instance.
    * Hub name — ``"Build"`` for YAML pipelines.

    The external system uses these UUIDs to call back into ADO via three
    write endpoints: **feed** (live console output), **log** (persistent
    log), and **events** (``TaskCompleted`` signal that unblocks ADO).  It
    can also patch the timeline record to attach issues.

    **Authentication:** the distributed-task write endpoints require the
    pipeline's own ``System.AccessToken`` bearer token, not a PAT.  Pass
    it as *bearer_token*.

    **URL:** ADO's distributed-task API requires a project-UUID-scoped URL
    (``{collection_uri}/{team_project_id}/_apis/distributedtask/...``).
    Using the org-only URL returns HTTP 404; using the project-name URL
    returns HTTP 400.  This class constructs the correct URL from
    *collection_uri* and *team_project_id* at initialisation.

    Instances are obtained either directly (external systems) or via
    :meth:`Build.get_distributed_task_session` (OOP callers).

    The build timeline record is loaded lazily: the first call to
    :meth:`get_record` or :meth:`add_issues` fetches all timeline records.
    Call :meth:`refresh` to discard the cached record and re-fetch on the
    next access.

    ``send_feed``, ``send_log``, and ``send_message`` use the
    ``7.1-preview.1`` API (preview).  ``add_issues`` uses the stable
    ``7.1`` API.

    Attributes:
        _project_api_call: Project-UUID-scoped API call authenticated with
            the pipeline bearer token.
        _build_id: Numeric build ID (used to resolve the log ID).
        _hub_name: Distributed-task hub name (e.g. ``"Build"``).
        _plan_id: The orchestration plan UUID.
        _timeline_id: The timeline UUID.
        _job_id: The job UUID.
        _task_instance_id: UUID identifying this task instance.
        _log_id: Lazily resolved task log ID.
        _record: Lazily loaded timeline record for this task.
    """

    def __init__(
        self,
        bearer_token: str,
        *,
        collection_uri: str,
        team_project_id: str,
        build_id: BuildId,
        hub_name: str,
        plan_id: PlanId,
        timeline_id: TimelineId,
        job_id: JobId,
        task_instance_id: TaskId,
        log_id: BuildLogId | None = None,
        oop_build: "Build | None" = None,
    ) -> None:
        """Construct a DistributedTaskSession.

        Args:
            bearer_token: Pipeline bearer token (``System.AccessToken``).
            collection_uri: ADO organisation root URL
                (e.g. ``"https://dev.azure.com/myorg/"``).  Available as
                ``SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`` in pipeline variables.
            team_project_id: Project UUID string (``System.TeamProjectId``).
            build_id: Numeric build ID (``Build.BuildId``).
            hub_name: Distributed-task hub name (e.g. ``"Build"``).
            plan_id: The orchestration plan UUID (``System.PlanId``).
            timeline_id: The timeline UUID (``System.TimelineId``).
            job_id: The job UUID (``System.JobId``).
            task_instance_id: UUID identifying this task instance
                (``Agent.TaskInstanceId``).
            log_id: Pre-resolved log ID.  When ``None`` (default) the log
                ID is resolved lazily on the first :meth:`send_log` or
                :meth:`send_message` call by iterating the build timeline.
                Call :meth:`refresh` to clear the cached ID.
            oop_build: OOP :class:`~pyado.oop.pipelines.build.Build` instance
                that created this session.  Populated only when the session is
                obtained via :meth:`Build.get_distributed_task_session`;
                ``None`` for externally-constructed sessions.
        """
        session = raw.get_session(bearer_token=bearer_token)
        api_url = f"{collection_uri.rstrip('/')}/{team_project_id}/_apis"
        self._project_api_call = ApiCall(
            session=session, url=_ADO_URL_ADAPTER.validate_python(api_url)
        )
        self._build_id = build_id
        self._hub_name = hub_name
        self._plan_id = plan_id
        self._timeline_id = timeline_id
        self._job_id = job_id
        self._task_instance_id = task_instance_id
        self._log_id = log_id
        self._record: BuildRecordInfo | None = None
        self._oop_build: Build | None = oop_build

    # ------------------------------------------------------------------
    # Internal API call helpers
    # ------------------------------------------------------------------

    def _make_plan_api_call(self) -> ApiCall:
        return raw.get_plan_api_call(
            self._project_api_call, self._hub_name, self._plan_id
        )

    def _make_timeline_api_call(self) -> ApiCall:
        return raw.get_timeline_api_call(
            self._project_api_call,
            self._hub_name,
            self._plan_id,
            self._timeline_id,
        )

    def _make_job_api_call(self) -> ApiCall:
        return raw.get_job_api_call(
            self._project_api_call,
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
            build_api_call = raw.get_build_api_call(
                self._project_api_call, self._build_id
            )
            for record in raw.iter_timeline_records(build_api_call):
                if record.id == self._task_instance_id and record.log is not None:
                    self._log_id = record.log.id
                    break
        if self._log_id is None:
            err_msg = f"Task {self._task_instance_id} has no log entry yet."
            raise RuntimeError(err_msg)
        return raw.get_log_api_call(
            self._project_api_call,
            self._hub_name,
            self._plan_id,
            self._log_id,
        )

    # ------------------------------------------------------------------
    # Timeline record access
    # ------------------------------------------------------------------

    def _resolve(self) -> BuildRecordInfo:
        """Return the timeline record, fetching it lazily on first call."""
        if self._record is None:
            self._record = self.get_record()
        return self._record

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
        build_api_call = raw.get_build_api_call(self._project_api_call, self._build_id)
        for record in raw.iter_timeline_records(build_api_call):
            if (
                record.type_name == BuildRecordType.TASK
                and record.id == self._task_instance_id
            ):
                return record
        err_msg = (
            f"Task record {self._task_instance_id!r} not found "
            f"in build {self._build_id}"
        )
        raise ValueError(err_msg)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard the cached timeline record and log ID.

        The next access to any cached data (e.g. via :meth:`get_record`,
        :meth:`add_issues`, :meth:`send_log`) will re-fetch from the API.
        """
        self._record = None
        self._log_id = None

    # ------------------------------------------------------------------
    # OOP back-references (populated only via Build.get_distributed_task_session)
    # ------------------------------------------------------------------

    @property
    def build(self) -> "Build":
        """OOP Build that created this session.

        Returns:
            The owning :class:`~pyado.oop.pipelines.build.Build`.

        Raises:
            RuntimeError: If the session was not created via
                :meth:`Build.get_distributed_task_session`.
        """
        if self._oop_build is None:
            err_msg = (
                "build is only available on sessions created via"
                " Build.get_distributed_task_session"
            )
            raise RuntimeError(err_msg)
        return self._oop_build

    @property
    def project(self) -> "Project":
        """Project that owns the build — zero-cost.

        Returns:
            The owning :class:`~pyado.oop.project.Project`.
        """
        return self.build.project

    @property
    def org(self) -> "Organization":
        """Organisation that owns the build — zero-cost.

        Returns:
            The owning :class:`~pyado.oop.organization.Organization`.
        """
        return self.build.org

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def send_feed(self, messages: list[str]) -> None:
        """Send messages to the task's live feed.

        Uses the ``7.1-preview.1`` distributed-task API.

        Args:
            messages: Log lines to append to the feed.
        """
        raw.post_job_feed(
            self._make_job_api_call(),
            raw.JobFeedPayload(value=messages, count=len(messages)),
        )

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
        All messages are joined with newlines into a single log entry.

        Args:
            messages: Log lines to append to both feed and persistent log.
        """
        self.send_feed(messages)
        raw.post_job_logs(self._make_log_api_call(), "\n".join(messages))

    def add_issues(self, issues: list[BuildIssue]) -> None:
        """Append issues to this task's timeline record.

        Uses the stable ``7.1`` distributed-task API.  Fetches the current
        record, merges in the new issues, then patches the timeline.

        Args:
            issues: Issues to append to the task's timeline record.
        """
        record = self._resolve()
        updated = record.model_copy(update={"issues": (record.issues or []) + issues})
        raw.patch_timeline_records(
            self._make_timeline_api_call(),
            raw.TimelineRecordsUpdatePayload(value=[updated], count=1),
        )

    def complete(self, *, succeeded: bool) -> None:
        """Signal task completion to the pipeline.

        Args:
            succeeded: When ``True``, reports success; otherwise reports
                failure.
        """
        result = (
            raw.JobEventResult.SUCCEEDED if succeeded else raw.JobEventResult.FAILED
        )
        raw.post_job_event(
            self._make_plan_api_call(),
            raw.JobEventPayload(
                name=raw.JobEventName.TASK_COMPLETED,
                task_id=self._task_instance_id,
                job_id=self._job_id,
                result=result,
            ),
        )
