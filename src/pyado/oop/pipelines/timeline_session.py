"""Report pipeline progress from outside the agent, into one build's timeline.

An agentless step (``InvokeRESTAPI``) can hand its work to an external system,
for example an AWS Step Functions execution that runs Lambdas and CodeBuild
projects.  :class:`TimelineSession` lets that system write progress back: it
finds the step's timeline record, streams console lines, attaches logs, adds
virtual jobs and tasks, and finally completes the step.

Everything here was measured against a live organisation; the behaviours that
shaped the design are:

* Record writes, feed and log appends work with a PAT or any bearer token.
  ``TaskCompleted`` only works with the build's ``System.AccessToken``.
* The System token expires at issue time + the printing job's
  ``timeoutInMinutes`` + 15 minutes; afterwards every call returns HTTP 401.
* Feed lines go to the **job** record, are shown live and are never stored.
* A record id that already exists is overwritten (upsert); ``type`` and
  ``parent_id`` stay as first created; a partial update of an unknown id is
  rejected; a rerun keeps the old ``result``, so give it a new id.
* The portal draws Stage -> Job -> Task only; a dynamic Job is drawn only under
  a native Phase.
* After a stage retry the old job id is gone from the timeline; never cache it.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID, uuid5

from pydantic import ConfigDict, Field

from pyado import raw
from pyado.exceptions import AzureDevOpsSessionError
from pyado.raw import (
    ApiCall,
    BuildIssue,
    BuildLogId,
    BuildRecordInfo,
    BuildRecordResult,
    BuildRecordState,
    BuildRecordType,
)
from pyado.raw._core import AdoBaseModel

__all__ = [
    "TimelineSession",
    "TimelineTarget",
    "decode_token_expiry",
]

_ADO_BASE: Final = "https://dev.azure.com"
_HUB: Final = "build"
_SAFETY_SECONDS: Final = 30.0
_LOG_WAIT_SECONDS: Final = 60.0
_MAX_DEPTH: Final = 8
_EPOCH_MIN: Final = 1.0e9
_EPOCH_MAX: Final = 4.0e9
_JWT_PARTS: Final = 3
_ID_NAMESPACE: Final = UUID("9d6e1a3c-6c0e-4d77-9a5e-5f3a1e7d2b10")


class TimelineTarget(AdoBaseModel):
    """Identifies one record of a build's timeline.

    Attributes:
        record_id: Id of the record.
        parent_id: Id of the record's parent, when known.
        type_name: Record type (Stage, Phase, Job, Task).
        name: Display name of the record.
    """

    model_config = ConfigDict(
        alias_generator=AdoBaseModel.model_config["alias_generator"],
        populate_by_name=True,
        frozen=True,
    )

    record_id: UUID
    parent_id: UUID | None = None
    type_name: BuildRecordType
    name: str


class _RecordWrite(AdoBaseModel):
    """A partial timeline record update; unset fields are not sent."""

    id: UUID
    name: str | None = None
    type_name: BuildRecordType | None = Field(default=None, alias="type")
    parent_id: UUID | None = None
    state: BuildRecordState | None = None
    result: BuildRecordResult | None = None
    percent_complete: int | None = None
    issues: list[BuildIssue] | None = None
    ref_name: str | None = None
    order: int | None = None
    attempt: int | None = None
    start_time: datetime | None = None
    finish_time: datetime | None = None
    log: dict[str, Any] | None = None
    last_modified: str | None = None
    previous_attempts: list[Any] | None = None


def decode_token_expiry(token: str) -> float | None:
    """Return the epoch at which a System.AccessToken stops working.

    The token is a JWT with a top-level ``exp`` (about 24 hours) and a nested
    ``xms_attr.<id>.ado_exp`` (issue time + job timeout + 15 minutes) that
    governs.  Only the claims are decoded; nothing is validated or logged.

    Args:
        token: The JWT.

    Returns:
        The earliest expiry found at any depth as a Unix timestamp, or None
        when the token is not a decodable JWT.
    """
    try:
        claims = json.loads(_b64(token.split(".")[1]))
    except (IndexError, ValueError):
        return None
    found: list[float] = []
    _collect_expiries(claims, found, 0)
    return min(found) if found else None


def _b64(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _collect_expiries(node: object, found: list[float], depth: int) -> None:
    """Collect every ``*exp`` claim, following nested JSON and nested JWTs."""
    if depth > _MAX_DEPTH:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                key.lower().endswith("exp")
                and isinstance(value, (int, float))
                and _EPOCH_MIN < value < _EPOCH_MAX
            ):
                found.append(float(value))
            else:
                _collect_expiries(value, found, depth + 1)
    elif (
        isinstance(node, str)
        and node.count(".") == _JWT_PARTS - 1
        and node.startswith("ey")
    ):
        try:
            _collect_expiries(json.loads(_b64(node.split(".")[1])), found, depth + 1)
        except ValueError:
            return


class TimelineSession:
    """Write progress into one build's timeline from outside the pipeline.

    Construct it with :meth:`from_tokens`.  The admin credential does every
    record, feed and log write.  The System token is only needed for
    :meth:`complete`, so it may be omitted until then.

    Example:
        >>> session = TimelineSession.from_tokens(  # doctest: +SKIP
        ...     org_name="myorg", project_id=project_uuid, build_id=123,
        ...     admin_token=pat, system_token=bridge_token,
        ... )
        >>> step = session.resolve_task("Run workflow")  # doctest: +SKIP
        >>> session.feed(step, "execution started")  # doctest: +SKIP
        >>> session.complete(step)  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        admin_call: ApiCall,
        system_call: ApiCall | None,
        build_id: int,
        system_token_expiry: float | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Construct the session from ready ``ApiCall`` objects.

        Prefer :meth:`from_tokens`; this constructor exists so tests and
        callers with their own sessions can inject calls and a clock.

        Args:
            admin_call: Project-scoped call (project **id** in the URL) using
                the admin credential.
            system_call: Same URL using the System token, or None.
            build_id: Numeric build id.
            system_token_expiry: Epoch at which the System token stops
                working, if known.
            clock: Source of the current time, replaceable in tests.
        """
        self._admin = admin_call
        self._system = system_call
        self._build_id = build_id
        self._expiry = system_token_expiry
        self._clock = clock
        self._plan_id: UUID | None = None
        self._batch: list[_RecordWrite] | None = None

    @classmethod
    def from_tokens(
        cls,
        *,
        org_name: str,
        project_id: UUID,
        build_id: int,
        admin_token: str,
        system_token: str | None = None,
    ) -> "TimelineSession":
        """Create a session from an admin token and an optional System token.

        Args:
            org_name: Organisation name.
            project_id: Project **UUID**; the write endpoints reject the name.
            build_id: Numeric build id.
            admin_token: A PAT, used for every record, feed and log write.
            system_token: The build's ``System.AccessToken``; needed only for
                :meth:`complete`.  Its expiry is read from the token.

        Returns:
            A new session.
        """
        url = f"{_ADO_BASE}/{org_name}/{project_id}/_apis"
        admin = ApiCall(session=raw.get_session(pat=admin_token), url=url)
        system = (
            ApiCall(session=raw.get_session(bearer_token=system_token), url=url)
            if system_token
            else None
        )
        expiry = decode_token_expiry(system_token) if system_token else None
        return cls(
            admin_call=admin,
            system_call=system,
            build_id=build_id,
            system_token_expiry=expiry,
        )

    # -- reading ---------------------------------------------------------------

    def _records(self) -> list[BuildRecordInfo]:
        """Read the whole timeline (one request).

        Returns:
            Every record of the build's timeline.
        """
        build_call = raw.get_build_api_call(self._admin, self._build_id)
        return list(raw.iter_timeline_records(build_call))

    def plan_id(self) -> UUID:
        """Return the plan (= timeline) id of the build.

        Returns:
            The plan id, read once and cached.

        Raises:
            AzureDevOpsSessionError: If the build has no timeline yet.
        """
        if self._plan_id is None:
            build_call = raw.get_build_api_call(self._admin, self._build_id)
            response = build_call.get("timeline", version="7.1")
            plan = response.get("id") if isinstance(response, dict) else None
            if plan is None:
                msg = f"Build {self._build_id} has no timeline yet"
                raise AzureDevOpsSessionError(msg)
            self._plan_id = UUID(str(plan))
        return self._plan_id

    @staticmethod
    def _target(record: BuildRecordInfo) -> TimelineTarget:
        return TimelineTarget(
            record_id=record.id,
            parent_id=record.parent_id,
            type_name=record.type_name,
            name=record.name,
        )

    def resolve_task(self, display_name: str) -> TimelineTarget:
        """Find the step's own timeline record by its display name.

        ``SYSTEM_TASKINSTANCEID`` is not that step's record for an
        ``InvokeRESTAPI`` step, so the record is found by name instead.  The
        job id is read fresh on every call because a stage retry replaces it.

        Args:
            display_name: The step's ``displayName``.

        Returns:
            The matching Task record.

        Raises:
            AzureDevOpsSessionError: If no, or more than one, Task matches.
        """
        matches = [
            r
            for r in self._records()
            if r.type_name == BuildRecordType.TASK and r.name == display_name
        ]
        if not matches:
            msg = f"No task named {display_name!r} in build {self._build_id}"
            raise AzureDevOpsSessionError(msg)
        if len(matches) > 1:
            msg = f"{len(matches)} tasks are named {display_name!r}; use a unique name"
            raise AzureDevOpsSessionError(msg)
        return self._target(matches[0])

    def find(self, name: str, *, under: TimelineTarget | None = None) -> TimelineTarget:
        """Find a record by name, optionally below a parent (stateless re-attach).

        Args:
            name: Display name to look for.
            under: Restrict the search to direct children of this record.

        Returns:
            The single matching record.

        Raises:
            AzureDevOpsSessionError: If none, or several, match.
        """
        matches = [
            r
            for r in self._records()
            if r.name == name and (under is None or r.parent_id == under.record_id)
        ]
        if len(matches) != 1:
            msg = f"Expected one record named {name!r}, found {len(matches)}"
            raise AzureDevOpsSessionError(msg)
        return self._target(matches[0])

    def native_phase(self, step: TimelineTarget) -> TimelineTarget:
        """Return the native Phase that contains *step*'s job.

        Dynamic jobs are only drawn by the portal under a native Phase.

        Args:
            step: A Task record, usually from :meth:`resolve_task`.

        Returns:
            The Phase record above the step's Job.

        Raises:
            AzureDevOpsSessionError: If the step has no Job and Phase above it.
        """
        by_id = {r.id: r for r in self._records()}
        job = by_id.get(step.parent_id) if step.parent_id else None
        phase = by_id.get(job.parent_id) if job and job.parent_id else None
        if job is None or phase is None or phase.type_name != BuildRecordType.PHASE:
            msg = f"{step.name!r} has no Job and Phase above it"
            raise AzureDevOpsSessionError(msg)
        return self._target(phase)

    # -- ids -------------------------------------------------------------------

    def record_id(self, key: str, *, attempt: int = 1) -> UUID:
        """Derive a stable record id from a key.

        The same key (and attempt) always gives the same id, so a stateless
        writer can update a record without looking it up.  The id depends on
        the build, so two builds never clash.  A rerun of a record that
        already completed needs a new *attempt*, because the record keeps its
        old ``result``.

        Args:
            key: Any stable string, for example an execution arn and a state
                name.
            attempt: Increase for a rerun of a completed record.

        Returns:
            A UUID.
        """
        return uuid5(_ID_NAMESPACE, f"{self._build_id}/{key}#{attempt}")

    # -- writing ---------------------------------------------------------------

    def _timeline_call(self) -> ApiCall:
        plan = self.plan_id()
        return raw.get_timeline_api_call(self._admin, _HUB, plan, plan)

    def _send(self, writes: list[_RecordWrite]) -> None:
        """Send writes now, or queue them inside :meth:`batch`."""
        if self._batch is not None:
            self._batch.extend(writes)
            return
        self._patch(writes)

    def _patch(self, writes: list[_RecordWrite]) -> None:
        if not writes:
            return
        seen: set[UUID] = set()
        for write in writes:
            if write.id in seen:
                msg = f"Record {write.id} appears twice in one batch"
                raise AzureDevOpsSessionError(msg)
            seen.add(write.id)
        self._timeline_call().patch(
            "records",
            version="7.1",
            json={
                "value": [
                    w.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for w in writes
                ],
                "count": len(writes),
            },
        )

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Send all writes made inside the block as one request.

        One request accepted 2000 records; the same record twice in one batch
        is rejected by ADO, so it is rejected here first.

        Yields:
            Nothing; writes inside the block are queued.

        Raises:
            AzureDevOpsSessionError: If called inside another batch.
        """
        if self._batch is not None:
            msg = "batch() cannot be nested"
            raise AzureDevOpsSessionError(msg)
        self._batch = []
        try:
            yield
        finally:
            pending, self._batch = self._batch, None
        self._patch(pending)

    @staticmethod
    def _check_new_id(record_id: UUID, native_ids: set[UUID]) -> None:
        if record_id in native_ids:
            msg = f"{record_id} belongs to a native record; writing it would rename it"
            raise AzureDevOpsSessionError(msg)

    def _create(
        self,
        type_name: BuildRecordType,
        name: str,
        *,
        under: TimelineTarget,
        state: BuildRecordState,
        record_id: UUID,
    ) -> TimelineTarget:
        """Create (or upsert) a record below *under*.

        Returns:
            The created record.
        """
        now = datetime.fromtimestamp(self._clock(), UTC)
        write = _RecordWrite(
            id=record_id,
            name=name,
            type_name=type_name,
            parent_id=under.record_id,
            state=state,
            attempt=1,
            start_time=now if state != BuildRecordState.PENDING else None,
            ref_name="CmdLine1",
            last_modified="0001-01-01T00:00:00",
            previous_attempts=[],
        )
        if self._batch is None:
            native = {
                r.id for r in self._records() if r.task is not None or r.identifier
            }
            self._check_new_id(record_id, native)
        self._send([write])
        return TimelineTarget(
            record_id=record_id,
            parent_id=under.record_id,
            type_name=type_name,
            name=name,
        )

    def create_job(
        self,
        name: str,
        *,
        under: TimelineTarget,
        key: str | None = None,
        attempt: int = 1,
        state: BuildRecordState = BuildRecordState.IN_PROGRESS,
    ) -> TimelineTarget:
        """Create a virtual job.

        The portal only draws a dynamic Job under a native Phase (see
        :meth:`native_phase`); under a Stage or another Job it gets no row.

        Args:
            name: Display name.
            under: A native Phase.
            key: Stable key for the id; defaults to *name*.
            attempt: Attempt number for the id (see :meth:`record_id`).
            state: Initial state.

        Returns:
            The created record.

        Raises:
            AzureDevOpsSessionError: If *under* is not a Phase.
        """
        if under.type_name != BuildRecordType.PHASE:
            msg = f"A job is only drawn under a Phase, not under a {under.type_name}"
            raise AzureDevOpsSessionError(msg)
        return self._create(
            BuildRecordType.JOB,
            name,
            under=under,
            state=state,
            record_id=self.record_id(key if key is not None else name, attempt=attempt),
        )

    def create_task(
        self,
        name: str,
        *,
        under: TimelineTarget,
        key: str | None = None,
        attempt: int = 1,
        state: BuildRecordState = BuildRecordState.IN_PROGRESS,
    ) -> TimelineTarget:
        """Create a virtual task below a Job or another Task.

        Args:
            name: Display name.
            under: A Job or Task.
            key: Stable key for the id; defaults to *name*.
            attempt: Attempt number for the id (see :meth:`record_id`).
            state: Initial state.

        Returns:
            The created record.

        Raises:
            AzureDevOpsSessionError: If *under* is a Phase or Stage, which the
                portal does not draw.
        """
        if under.type_name not in {BuildRecordType.JOB, BuildRecordType.TASK}:
            msg = (
                "A task is only drawn under a Job or Task, "
                f"not under a {under.type_name}"
            )
            raise AzureDevOpsSessionError(msg)
        return self._create(
            BuildRecordType.TASK,
            name,
            under=under,
            state=state,
            record_id=self.record_id(key if key is not None else name, attempt=attempt),
        )

    def set_state(
        self,
        target: TimelineTarget,
        *,
        state: BuildRecordState | None = None,
        result: BuildRecordResult | None = None,
        percent: int | None = None,
    ) -> None:
        """Update a record's state, result or progress.

        ``result`` cannot be cleared once set, so only send a result when the
        record is finished.  Progress shows on running rows only.

        Args:
            target: The record.
            state: New state.
            result: New result.
            percent: Progress, 0 to 100.
        """
        finishing = state == BuildRecordState.COMPLETED
        write = _RecordWrite(
            id=target.record_id,
            state=state,
            result=result,
            percent_complete=percent,
            finish_time=datetime.fromtimestamp(self._clock(), UTC)
            if finishing
            else None,
        )
        self._send([write])

    def finish(
        self,
        target: TimelineTarget,
        result: BuildRecordResult = BuildRecordResult.SUCCEEDED,
    ) -> None:
        """Mark a record completed with *result*.

        Args:
            target: The record.
            result: Outcome, ``succeeded`` by default.
        """
        self.set_state(
            target, state=BuildRecordState.COMPLETED, result=result, percent=100
        )

    def report_issues(self, target: TimelineTarget, issues: list[BuildIssue]) -> None:
        """Set a record's issues, which feed the Errors and Warnings tabs.

        The list **replaces** the existing one, on native records too, and an
        empty list is ignored by ADO.  Console lines never create issues.

        Args:
            target: The record.
            issues: The complete list of issues for the record.
        """
        self._send([_RecordWrite(id=target.record_id, issues=issues)])

    # -- live console and logs -------------------------------------------------

    def feed(self, step: TimelineTarget, *lines: str) -> None:
        """Send lines to the live console of the step's job.

        Feed lines go to the **job** record, show within a fraction of a
        second in a page that is open, and are never stored: a reload drops
        them.  Use :meth:`append_log` for anything that must stay.

        Args:
            step: A Task (its job is used) or a Job record.
            *lines: Console lines, already formatted (see ``log_format``).

        Raises:
            AzureDevOpsSessionError: If *step* has no job.
        """
        if not lines:
            return
        job_id = (
            step.record_id if step.type_name == BuildRecordType.JOB else step.parent_id
        )
        if job_id is None:
            msg = f"{step.name!r} has no job to receive feed lines"
            raise AzureDevOpsSessionError(msg)
        plan = self.plan_id()
        job_call = raw.get_job_api_call(self._admin, _HUB, plan, plan, job_id)
        raw.post_job_feed(
            job_call, raw.JobFeedPayload(value=list(lines), count=len(lines))
        )

    def _log_id(self, target: TimelineTarget, wait: float) -> BuildLogId:
        """Return the record's log id, waiting for ADO to attach it.

        Returns:
            The log id.

        Raises:
            AzureDevOpsSessionError: If no log appears within *wait* seconds.
        """
        deadline = self._clock() + wait
        while True:
            for record in self._records():
                if record.id == target.record_id and record.log is not None:
                    return record.log.id
            if self._clock() >= deadline:
                msg = f"{target.name!r} has no log after {wait:.0f} s"
                raise AzureDevOpsSessionError(msg)
            time.sleep(2.0)

    def attach_log(self, target: TimelineTarget) -> BuildLogId:
        """Allocate a log and attach it to a record that has none.

        A record you created has no log; a native task already has one.

        Args:
            target: The record.

        Returns:
            The new log id.
        """
        plan = self.plan_id()
        plan_call = raw.get_plan_api_call(self._admin, _HUB, plan)
        info = raw.post_new_log(plan_call, f"logs\\{target.record_id}")
        self._patch(
            [
                _RecordWrite(
                    id=target.record_id, log=info.model_dump(mode="json", by_alias=True)
                )
            ]
        )
        return info.id

    def append_log(
        self,
        target: TimelineTarget,
        text: str,
        *,
        create: bool = False,
        wait: float = _LOG_WAIT_SECONDS,
    ) -> None:
        """Append text to a record's persistent log.

        For a native task the log is already attached but may take a few
        seconds to appear, so the call waits.  For a record you created pass
        ``create=True`` to allocate and attach a log on first use.  Appended
        text shows in the portal after a reload, not live.

        Args:
            target: The record.
            text: Text to append; build it with ``log_format.LogLines``.
            create: Allocate and attach a log when the record has none.
            wait: Seconds to wait for ADO to attach the log of a native task.
        """
        try:
            log_id = self._log_id(target, 0.0)
        except AzureDevOpsSessionError:
            log_id = self.attach_log(target) if create else self._log_id(target, wait)
        plan = self.plan_id()
        log_call = raw.get_log_api_call(self._admin, _HUB, plan, log_id)
        raw.post_job_logs(log_call, text if text.endswith("\n") else text + "\n")

    # -- completion ------------------------------------------------------------

    def seconds_until_system_token_expires(self) -> float | None:
        """Return seconds until the System token stops working, if known."""
        if self._expiry is None:
            return None
        return self._expiry - self._clock()

    def complete(
        self,
        step: TimelineTarget,
        *,
        succeeded: bool = True,
    ) -> None:
        """Complete the agentless step so the pipeline continues.

        Only the System token can do this (a PAT gets HTTP 500).  The token
        expires at issue time + the job's ``timeoutInMinutes`` + 15 minutes;
        raise that timeout to cover the longest expected workflow.

        Args:
            step: The Task record from :meth:`resolve_task`.
            succeeded: ``False`` completes the step as failed.

        Raises:
            AzureDevOpsSessionError: If no System token was given, it has
                expired or is about to, or *step* has no parent job.
        """
        if self._system is None:
            msg = "complete() needs the build's System.AccessToken"
            raise AzureDevOpsSessionError(msg)
        remaining = self.seconds_until_system_token_expires()
        if remaining is not None and remaining < _SAFETY_SECONDS:
            msg = (
                "The System token has expired or expires within "
                f"{_SAFETY_SECONDS:.0f} s; raise the job's timeoutInMinutes "
                "so it outlives the workflow, or supply a fresh token"
            )
            raise AzureDevOpsSessionError(msg)
        if step.parent_id is None:
            msg = f"{step.name!r} has no parent job"
            raise AzureDevOpsSessionError(msg)
        plan_call = raw.get_plan_api_call(self._system, _HUB, self.plan_id())
        raw.post_job_event(
            plan_call,
            raw.JobEventPayload(
                name=raw.JobEventName.TASK_COMPLETED,
                task_id=step.record_id,
                job_id=step.parent_id,
                result=raw.JobEventResult.SUCCEEDED
                if succeeded
                else raw.JobEventResult.FAILED,
            ),
        )
