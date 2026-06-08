"""OOP wrappers for build timeline stages, jobs, and tasks."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pyado.raw import (
    BuildIssue,
    BuildLogInfo,
    BuildRecordInfo,
    BuildRecordResult,
    BuildRecordState,
    BuildRecordType,
)

if TYPE_CHECKING:
    from pyado.oop.pipelines.build import Build

__all__ = ["BuildJob", "BuildPhase", "BuildStage", "BuildTask"]


class BuildTask:
    """A single task step within a build job.

    **ADO concept:** a *task* is a ``type='Task'`` record in the build
    timeline (``build/builds/{id}/timeline``).  It represents one step in a
    job — e.g. a ``UsePythonVersion`` or ``Bash`` step in YAML.  Each task
    record carries a ``task.{id, name, version}`` sub-object identifying the
    task definition, a log reference (``log.id``), and the standard state/
    result/error-count fields shared by all timeline record types.

    **Why it exists:** provides typed access to the task-level fields
    (``task``, ``log``, ``issues``, ``error_count``) and a convenience
    :meth:`get_log_text` that resolves the log ID through the parent job/
    build chain without the caller needing to manage ``BuildLogId`` values.
    Also serves as the base class for
    :class:`~pyado.oop.pipelines.distributed_task_session.DistributedTaskSession`,
    which adds write operations for external (serverless) tasks.

    Wraps one ``Task``-type timeline record.  Instances are obtained from
    :meth:`BuildJob.iter_tasks`.

    The :attr:`job` back-reference is always non-``None`` for tasks obtained
    from :meth:`BuildJob.iter_tasks`.  The :class:`DistributedTaskSession`
    subclass starts with ``job=None`` and provides
    :meth:`~DistributedTaskSession.get_job` instead.

    Attributes:
        _record: The raw timeline record for this task (``None`` until
            :meth:`_resolve` is called by a subclass).
        _job: The parent BuildJob, or ``None`` for DistributedTaskSession.
    """

    def __init__(
        self,
        record: "BuildRecordInfo | None" = None,
        *,
        job: "BuildJob | None" = None,
    ) -> None:
        """Construct a BuildTask wrapper.

        Args:
            record: The raw BuildRecordInfo for this task, or ``None`` when
                constructed by a subclass that loads the record lazily.
            job: The parent BuildJob, or ``None`` when not known at
                construction time.
        """
        self._record = record
        self._job = job

    def _resolve(self) -> BuildRecordInfo:
        """Return the underlying timeline record.

        Subclasses may override to provide lazy loading.

        Raises:
            RuntimeError: If no record has been set and this method has not
                been overridden.
        """
        if self._record is None:
            err_msg = "No timeline record available; call get_record() first."
            raise RuntimeError(err_msg)
        return self._record

    @property
    def id(self) -> UUID:
        """Unique record ID for this task."""
        return self._resolve().id

    @property
    def name(self) -> str:
        """Display name of the task."""
        return self._resolve().name

    @property
    def state(self) -> BuildRecordState:
        """Lifecycle state (pending, inProgress, completed)."""
        return self._resolve().state

    @property
    def result(self) -> BuildRecordResult | None:
        """Outcome once the task has completed, or ``None`` if still running."""
        return self._resolve().result

    @property
    def start_time(self) -> datetime | None:
        """When the task started, or ``None`` if not yet started."""
        return self._resolve().start_time

    @property
    def finish_time(self) -> datetime | None:
        """When the task finished, or ``None`` if not yet finished."""
        return self._resolve().finish_time

    @property
    def error_count(self) -> int:
        """Number of errors logged by this task."""
        return self._resolve().error_count or 0

    @property
    def warning_count(self) -> int:
        """Number of warnings logged by this task."""
        return self._resolve().warning_count or 0

    @property
    def issues(self) -> list[BuildIssue]:
        """List of issues (errors/warnings) reported by this task."""
        return self._resolve().issues or []

    @property
    def log(self) -> BuildLogInfo | None:
        """Log reference for this task, or ``None`` if unavailable."""
        return self._resolve().log

    @property
    def info(self) -> BuildRecordInfo:
        """Raw timeline record for direct inspection or raw-layer use."""
        return self._resolve()

    @property
    def job(self) -> "BuildJob | None":
        """Parent BuildJob — zero-cost.

        Always non-``None`` for tasks obtained from
        :meth:`BuildJob.iter_tasks`.  ``None`` for
        :class:`~pyado.oop.pipelines.distributed_task_session.DistributedTaskSession`
        instances (use :meth:`~DistributedTaskSession.get_job` instead).
        """
        return self._job

    def get_log_text(self) -> str | None:
        """Fetch the plain-text log content for this task.

        Returns ``None`` when no log is associated with this task (i.e.
        :attr:`log` is ``None``).  Requires :attr:`job` to be set; tasks
        obtained from :meth:`BuildJob.iter_tasks` always satisfy this.

        Returns:
            Log text, or ``None`` if no log is available.
        """
        log_info = self.log
        if log_info is None:
            return None
        if self._job is None:
            return None
        return self._job.stage.build.get_log_text(log_info.id)


class BuildPhase:
    """A phase within a build stage (YAML pipelines only).

    **ADO concept:** a *phase* is a ``type='Phase'`` record in the build
    timeline, inserted by the YAML pipeline engine between the Stage record
    and its Job records.  It represents the *deployment phase* level
    — effectively an intermediate grouping layer that carries its own
    state/result and can have child jobs.  Classic pipelines (GUI-defined)
    do not emit Phase records; in that case the Stage parent directly owns
    the Job records.

    **Why it exists:** the timeline is a flat list linked by ``parentId``.
    ``BuildPhase`` provides the tree-navigation step between a
    :class:`BuildStage` and its :class:`BuildJob` children for YAML
    pipelines, and exposes the same ``iter_jobs`` interface as a stage so
    callers can treat both pipeline styles uniformly through
    :meth:`BuildStage.iter_jobs`, which traverses phases transparently.

    In YAML pipelines a ``Phase`` record sits between a ``Stage`` and its
    ``Job`` records.  Classic pipelines do not emit Phase records — in that
    case :meth:`BuildStage.iter_phases` yields nothing and
    :meth:`BuildStage.iter_jobs` returns the jobs directly.

    Instances are obtained from :meth:`BuildStage.iter_phases`.

    Attributes:
        _record: The raw timeline record for this phase.
        _all_records: All timeline records from the same build.
        _stage: The parent BuildStage.
    """

    def __init__(
        self,
        record: BuildRecordInfo,
        all_records: list[BuildRecordInfo],
        stage: "BuildStage",
    ) -> None:
        """Construct a BuildPhase wrapper.

        Args:
            record: The raw BuildRecordInfo for this phase.
            all_records: All timeline records from the same build.
            stage: The parent BuildStage.
        """
        self._record = record
        self._all_records = all_records
        self._stage = stage

    @property
    def id(self) -> UUID:
        """Unique record ID for this phase."""
        return self._record.id

    @property
    def name(self) -> str:
        """Display name of the phase."""
        return self._record.name

    @property
    def state(self) -> BuildRecordState:
        """Lifecycle state (pending, inProgress, completed)."""
        return self._record.state

    @property
    def result(self) -> BuildRecordResult | None:
        """Outcome once the phase has completed, or ``None`` if still running."""
        return self._record.result

    @property
    def start_time(self) -> datetime | None:
        """When the phase started, or ``None`` if not yet started."""
        return self._record.start_time

    @property
    def finish_time(self) -> datetime | None:
        """When the phase finished, or ``None`` if not yet finished."""
        return self._record.finish_time

    @property
    def error_count(self) -> int:
        """Number of errors logged by this phase."""
        return self._record.error_count or 0

    @property
    def warning_count(self) -> int:
        """Number of warnings logged by this phase."""
        return self._record.warning_count or 0

    @property
    def issues(self) -> list[BuildIssue]:
        """List of issues (errors/warnings) reported by this phase."""
        return self._record.issues or []

    @property
    def log(self) -> BuildLogInfo | None:
        """Log reference for this phase, or ``None`` if unavailable."""
        return self._record.log

    @property
    def info(self) -> BuildRecordInfo:
        """Raw timeline record for direct inspection or raw-layer use."""
        return self._record

    @property
    def stage(self) -> "BuildStage":
        """Parent BuildStage — zero-cost."""
        return self._stage

    def iter_jobs(self) -> Iterator["BuildJob"]:
        """Iterate over the jobs within this phase.

        Yields:
            BuildJob for each ``Job``-type record whose parent is this phase.
        """
        for record in self._all_records:
            if (
                record.type_name == BuildRecordType.JOB
                and record.parent_id == self._record.id
            ):
                yield BuildJob(record, self._all_records, stage=self._stage, phase=self)

    def list_jobs(self) -> "list[BuildJob]":
        """Return all jobs within this phase as a list."""
        return list(self.iter_jobs())


class BuildJob:
    """A job within a build stage.

    **ADO concept:** a *job* is a ``type='Job'`` record in the build
    timeline.  It is the *unit of agent assignment* — ADO dispatches each
    job to a specific agent (recorded in ``worker_name``) and the agent
    runs all task steps sequentially within that job.  A job's parent is
    either a Stage (classic pipelines) or a Phase (YAML pipelines).  The
    ADO distributed-task variables ``SYSTEM_JOBID`` and the job feed/log
    APIs are scoped to this level.

    **Why it exists:** provides typed access to job-specific fields
    (``worker_name``, ``queue_id``), owns ``iter_tasks`` to enumerate child
    task records without additional API calls, and provides :meth:`get_log_text`
    for the aggregated job log.  Also carries both ``stage`` and ``phase``
    back-references for upward navigation.

    Wraps one ``Job``-type timeline record and provides access to its child
    tasks.  Instances are obtained from :meth:`BuildStage.iter_jobs` or
    :meth:`BuildPhase.iter_jobs`.

    Attributes:
        _record: The raw timeline record for this job.
        _all_records: All timeline records from the same build (used to find
            child tasks without additional API calls).
        _stage: The parent BuildStage.
        _phase: The parent BuildPhase, or ``None`` for classic pipelines where
            jobs are direct children of the stage.
    """

    def __init__(
        self,
        record: BuildRecordInfo,
        all_records: list[BuildRecordInfo],
        stage: "BuildStage",
        phase: "BuildPhase | None",
    ) -> None:
        """Construct a BuildJob wrapper.

        Args:
            record: The raw BuildRecordInfo for this job.
            all_records: All timeline records from the same build.
            stage: The parent BuildStage.
            phase: The parent BuildPhase, or ``None`` for jobs that are direct
                children of the stage (classic pipelines).
        """
        self._record = record
        self._all_records = all_records
        self._stage = stage
        self._phase = phase

    @property
    def id(self) -> UUID:
        """Unique record ID for this job."""
        return self._record.id

    @property
    def name(self) -> str:
        """Display name of the job."""
        return self._record.name

    @property
    def state(self) -> BuildRecordState:
        """Lifecycle state (pending, inProgress, completed)."""
        return self._record.state

    @property
    def result(self) -> BuildRecordResult | None:
        """Outcome once the job has completed, or ``None`` if still running."""
        return self._record.result

    @property
    def start_time(self) -> datetime | None:
        """When the job started, or ``None`` if not yet started."""
        return self._record.start_time

    @property
    def finish_time(self) -> datetime | None:
        """When the job finished, or ``None`` if not yet finished."""
        return self._record.finish_time

    @property
    def worker_name(self) -> str | None:
        """Name of the agent that ran this job, or ``None`` if unavailable."""
        return self._record.worker_name

    @property
    def error_count(self) -> int:
        """Number of errors logged by this job."""
        return self._record.error_count or 0

    @property
    def warning_count(self) -> int:
        """Number of warnings logged by this job."""
        return self._record.warning_count or 0

    @property
    def issues(self) -> list[BuildIssue]:
        """List of issues (errors/warnings) reported by this job."""
        return self._record.issues or []

    @property
    def log(self) -> BuildLogInfo | None:
        """Log reference for this job, or ``None`` if unavailable."""
        return self._record.log

    @property
    def info(self) -> BuildRecordInfo:
        """Raw timeline record for direct inspection or raw-layer use."""
        return self._record

    @property
    def stage(self) -> "BuildStage":
        """Parent BuildStage — zero-cost."""
        return self._stage

    @property
    def phase(self) -> "BuildPhase | None":
        """Parent BuildPhase — zero-cost.

        ``None`` for jobs that are direct children of a stage (classic
        pipelines).  Non-``None`` for jobs nested under a Phase in YAML
        pipelines.
        """
        return self._phase

    def iter_tasks(self) -> Iterator[BuildTask]:
        """Iterate over the task steps within this job.

        Yields:
            BuildTask for each ``Task``-type record whose parent is this job.
        """
        for record in self._all_records:
            if (
                record.type_name == BuildRecordType.TASK
                and record.parent_id == self._record.id
            ):
                yield BuildTask(record, job=self)

    def list_tasks(self) -> list[BuildTask]:
        """Return all task steps within this job as a list."""
        return list(self.iter_tasks())

    def get_log_text(self) -> str | None:
        """Fetch the plain-text log content for this job.

        Returns ``None`` when no log is associated with this job.

        Returns:
            Log text, or ``None`` if no log is available.
        """
        log_info = self.log
        if log_info is None:
            return None
        return self._stage.build.get_log_text(log_info.id)


class BuildStage:
    """A stage within a build timeline.

    **ADO concept:** a *stage* is a ``type='Stage'`` record in the build
    timeline (``build/builds/{id}/timeline``).  It is the top-level grouping
    unit in a multi-stage YAML pipeline (``stages:`` key) and the top of the
    four-level hierarchy: Stage → Phase (YAML only) → Job → Task.  Each stage
    has its own ``state``/``result`` and can be independently re-run or
    skipped.  Stages without explicit names in YAML still produce a
    ``__default`` Stage record.

    **Why it exists:** the timeline is returned as a **flat list** by ADO;
    the tree structure is encoded by ``parentId`` UUID links.  ``BuildStage``
    reconstructs the stage level of the tree, holds the full ``all_records``
    list so all descendant navigation is O(N) list scans without additional
    API calls, and owns the ``build`` back-reference.  :meth:`iter_jobs`
    transparently handles both classic (Stage→Job) and YAML (Stage→Phase→Job)
    layouts.

    Wraps one ``Stage``-type timeline record and provides access to its child
    jobs.  In YAML pipelines an optional ``Phase`` record may sit between the
    stage and its jobs; :meth:`iter_jobs` handles this transparently.
    Instances are obtained from :meth:`Build.iter_stages`.

    Attributes:
        _record: The raw timeline record for this stage.
        _all_records: All timeline records from the same build.
        _build: The owning Build.
    """

    def __init__(
        self,
        record: BuildRecordInfo,
        all_records: list[BuildRecordInfo],
        build: "Build",
    ) -> None:
        """Construct a BuildStage wrapper.

        Args:
            record: The raw BuildRecordInfo for this stage.
            all_records: All timeline records from the same build.
            build: The Build that owns this stage.
        """
        self._record = record
        self._all_records = all_records
        self._build = build

    @property
    def id(self) -> UUID:
        """Unique record ID for this stage."""
        return self._record.id

    @property
    def name(self) -> str:
        """Display name of the stage."""
        return self._record.name

    @property
    def state(self) -> BuildRecordState:
        """Lifecycle state (pending, inProgress, completed)."""
        return self._record.state

    @property
    def result(self) -> BuildRecordResult | None:
        """Outcome once the stage has completed, or ``None`` if still running."""
        return self._record.result

    @property
    def start_time(self) -> datetime | None:
        """When the stage started, or ``None`` if not yet started."""
        return self._record.start_time

    @property
    def finish_time(self) -> datetime | None:
        """When the stage finished, or ``None`` if not yet finished."""
        return self._record.finish_time

    @property
    def error_count(self) -> int:
        """Number of errors logged by this stage."""
        return self._record.error_count or 0

    @property
    def warning_count(self) -> int:
        """Number of warnings logged by this stage."""
        return self._record.warning_count or 0

    @property
    def issues(self) -> list[BuildIssue]:
        """List of issues (errors/warnings) reported by this stage."""
        return self._record.issues or []

    @property
    def log(self) -> BuildLogInfo | None:
        """Log reference for this stage, or ``None`` if unavailable."""
        return self._record.log

    @property
    def info(self) -> BuildRecordInfo:
        """Raw timeline record for direct inspection or raw-layer use."""
        return self._record

    @property
    def build(self) -> "Build":
        """Owning Build — zero-cost."""
        return self._build

    def iter_phases(self) -> Iterator[BuildPhase]:
        """Iterate over the phases within this stage (YAML pipelines only).

        Classic pipelines do not have Phase records; this method yields
        nothing for them.  Use :meth:`iter_jobs` to iterate jobs regardless
        of whether phases are present.

        Yields:
            BuildPhase for each ``Phase``-type record under this stage.
        """
        for record in self._all_records:
            if (
                record.type_name == BuildRecordType.PHASE
                and record.parent_id == self._record.id
            ):
                yield BuildPhase(record, self._all_records, stage=self)

    def iter_jobs(self) -> Iterator[BuildJob]:
        """Iterate over all jobs within this stage.

        Includes jobs that are direct children of the stage (classic
        pipelines) as well as jobs nested under a Phase (YAML pipelines).
        Use :meth:`iter_phases` followed by :meth:`BuildPhase.iter_jobs` if
        you need to distinguish which phase a job belongs to.

        Yields:
            BuildJob for each ``Job``-type record belonging to this stage.
        """
        phase_map: dict[UUID, BuildPhase] = {}
        for record in self._all_records:
            if (
                record.type_name == BuildRecordType.PHASE
                and record.parent_id == self._record.id
            ):
                phase_map[record.id] = BuildPhase(record, self._all_records, stage=self)

        for record in self._all_records:
            if record.type_name == BuildRecordType.JOB:
                if record.parent_id == self._record.id:
                    yield BuildJob(record, self._all_records, stage=self, phase=None)
                elif record.parent_id in phase_map:
                    yield BuildJob(
                        record,
                        self._all_records,
                        stage=self,
                        phase=phase_map[record.parent_id],
                    )

    def get_log_text(self) -> str | None:
        """Fetch the plain-text log content for this stage.

        Returns ``None`` when no log is associated with this stage.

        Returns:
            Log text, or ``None`` if no log is available.
        """
        log_info = self.log
        if log_info is None:
            return None
        return self._build.get_log_text(log_info.id)

    def list_phases(self) -> list[BuildPhase]:
        """Return all phases within this stage as a list."""
        return list(self.iter_phases())

    def list_jobs(self) -> list[BuildJob]:
        """Return all jobs within this stage as a list."""
        return list(self.iter_jobs())
