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
* The System token expires at issue time + the ``timeoutInMinutes`` of the job
  it was issued to + 15 minutes; afterwards every call returns HTTP 401.  This
  was measured on *agent* jobs (the token is printed by a script); an agentless
  job runs no script, so the lifetime of its own token, and whether its timeout
  governs a token used against it, was not measured.
* Feed lines go to the **job** record, are shown live and are never stored.
* A record id that already exists is overwritten (upsert); ``type`` and
  ``parent_id`` stay as first created; a partial update of an unknown id is
  rejected; a rerun keeps the old ``result``, so give it a new id.
* The portal draws Stage -> Job -> Task only; a dynamic Job is drawn only under
  a native Phase.
* After a stage retry the old job id is gone from the timeline; never cache it.
  Records written under the old attempt move into that attempt's sub-timeline
  and are not drawn.
* Records you leave ``inProgress`` take the **build's** result when the build
  ends (``pending`` ones become ``abandoned``): finish what you start.
* ``TaskCompleted`` completes the task only, and a PAT cannot send it.
* Never create a ``Stage`` record: the portal's results page for the build then
  shows "Build not found" (this class cannot create one).
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import json
import time
import warnings
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any, Final
from uuid import UUID, uuid5

from pydantic import ConfigDict, Field, model_validator

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
    "RecordOrder",
    "StatusIcon",
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
_DRAWN_TASK_DEPTH: Final = 2


class StatusIcon(StrEnum):
    """The colour of a virtual record's status icon in the portal.

    The portal draws the icon from the record's ``refName``: a name that is
    missing or starts with the exact-case text ``JobExtension`` gives the grey
    ``system-task`` icon, any other name the green ``success`` icon.  The test
    is case-sensitive (``jobextension_init`` is green).  The members hold the
    ``refName`` that this class sends.

    The colour is a **creation-time choice**.  Measured against a live
    organisation: a ``refName`` can be set once, from nothing; a later write of a
    different value is answered 200 and ignored (eight start/target
    combinations, read back from the timeline).  Create the record with the colour
    it should keep.

    Warning:
        Measured on Tasks.  For a *running* Job in the logs tree only a missing
        ``refName`` made the icon grey; a ``JobExtension...`` name did not.  On
        the **stage card** of the Summary page a dynamic Job is coloured by its
        state and result only (running blue, succeeded green, failed red),
        whatever its ``refName``, so ``icon=`` does not change that view.
    """

    COLOURED = "CmdLine1"
    GREY = "JobExtension"


class RecordOrder(IntEnum):
    """Sort positions among sibling records, as measured.

    Native tasks of an agent job are numbered ``1..N`` without gaps
    (``Initialize job`` is 1), so no integer lies between the last step you wrote
    and ``Post-job``.  ``null`` is not "last": the portal puts such records
    between ``1`` and ``2``.
    """

    FIRST = 0
    LAST = 2_147_483_646


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

    @model_validator(mode="after")
    def _no_stage(self) -> "_RecordWrite":
        """Refuse a ``Stage`` record: it breaks the build's results page.

        Returns:
            The validated write.

        Raises:
            AzureDevOpsSessionError: If the record type is ``Stage``.
        """
        if self.type_name == BuildRecordType.STAGE:
            msg = (
                "Refusing to write a Stage record.  Azure DevOps accepts it, but "
                "the build's results page then shows 'Build not found' (no "
                "summary, tabs or stage list), also after the build ends; no way "
                "to undo this is known.  Write a Job under a native Phase instead"
            )
            raise AzureDevOpsSessionError(msg)
        return self


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

    Pitfalls (each measured against a live organisation):

    * **Ids**: the id of a virtual record comes from a key, not from the parent
      or the job attempt (see :meth:`record_id`).  After a stage retry, records
      of the earlier attempt move into its sub-timeline and are not drawn.
    * **Closing**: a record left ``inProgress`` takes the **build's** result when
      the build ends, so a crashed writer looks successful in a successful
      build; ``pending`` ones become ``abandoned``.  :meth:`complete` finishes
      the task only, never your records.
    * **What is drawn**: Stage -> Job -> Task; a Job only under a native Phase,
      Task nesting two levels deep.  A *Stage* record would make the build's
      results page show "Build not found"; this class never creates one.
    * **Credentials**: a PAT writes records, feed and logs but cannot complete
      the task (HTTP 500).  Both the PAT and the System token can still write
      into a finished build, and the records are drawn.
    * **Native records**: their ``refName`` cannot be changed, a non-empty
      ``issues`` list replaces and ``[]`` is ignored, and they cannot be
      cleared of issues.

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
        attempt: int = 1,
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
            attempt: Default attempt mixed into every derived record id (see
                :meth:`for_attempt`).
        """
        self._attempt = attempt
        self._admin = admin_call
        self._system = system_call
        self._build_id = build_id
        self._expiry = system_token_expiry
        self._clock = clock
        self._plan_id: UUID | None = None
        self._batch: list[_RecordWrite] | None = None
        self._native_ids: set[UUID] | None = None
        self._log_ids: dict[UUID, BuildLogId] = {}

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

    @property
    def attempt(self) -> int:
        """The default attempt that this session mixes into record ids.

        Returns:
            ``1`` unless the session came from :meth:`for_attempt`.
        """
        return self._attempt

    def for_attempt(self, attempt: int) -> "TimelineSession":
        """Return a session whose record ids carry a job attempt.

        After a stage or job retry the job gets a new id, but a key that does not
        change still names the record written under the *old* job (it moved to
        the earlier attempt's sub-timeline and is not drawn).  A session from
        this method mixes *attempt* into every id it derives, so a retried job
        writes new records even with explicit keys.  Pass the job attempt
        (``SYSTEM_JOBATTEMPT``).

        Attempt ``1`` derives the same ids as a plain session, so adding
        ``for_attempt(1)`` changes nothing for a writer that exists already.  A
        ``attempt=`` argument of :meth:`record_id`, :meth:`create_job` or
        :meth:`create_task` still wins over the session's attempt.

        The record's own ``attempt`` field stays ``1``: ADO owns it.

        Args:
            attempt: The job attempt, at least 1.

        Returns:
            A new session over the same calls and clock.  Its caches start
            empty, because a retry changes the timeline.

        Raises:
            ValueError: If *attempt* is below 1.
        """
        if attempt < 1:
            msg = f"attempt must be at least 1, got {attempt}"
            raise ValueError(msg)
        return TimelineSession(
            admin_call=self._admin,
            system_call=self._system,
            build_id=self._build_id,
            system_token_expiry=self._expiry,
            clock=self._clock,
            attempt=attempt,
        )

    def for_current_attempt(self, step: TimelineTarget) -> "TimelineSession":
        """Return a session bound to the attempt of a native record's job.

        Reads the ``attempt`` of the native Job that owns *step* (a Task, or the
        Job itself) from the timeline, so a writer outside the agent does not
        have to know the number.  A job that was never retried reports 1, which
        derives the same ids as a plain session; after a retry the new job
        reports 2 and every id this session derives is a new record.

        Inside a running job you can also pass ``SYSTEM_JOBATTEMPT`` to
        :meth:`for_attempt`.

        Args:
            step: A native Task or Job (for example from :meth:`resolve_task`).

        Returns:
            A session from :meth:`for_attempt`.

        Raises:
            AzureDevOpsSessionError: If no job can be found for *step*.
        """
        job_id = (
            step.record_id if step.type_name == BuildRecordType.JOB else step.parent_id
        )
        for record in self._records():
            if record.id == job_id and record.type_name == BuildRecordType.JOB:
                return self.for_attempt(max(record.attempt, 1))
        msg = f"{step.name!r} has no job in the timeline to read an attempt from"
        raise AzureDevOpsSessionError(msg)

    def record_id(self, key: str, *, attempt: int | None = None) -> UUID:
        """Derive a stable record id from a key.

        The same key (and attempt) always gives the same id, so a stateless
        writer can update a record without looking it up.  The id depends on
        the build, so two builds never clash.  A rerun of a record that
        already completed needs a new *attempt*, because the record keeps its
        old ``result``.

        Warning:
            The id does **not** depend on the parent.  Two ``create_*`` calls
            with the same key under *different* parents are the same record:
            ADO upserts it, keeps the **first** parent (the parent of an
            existing record cannot change) and overwrites name and state, so
            nothing appears under the second parent.  :meth:`create_job` and
            :meth:`create_task` therefore default the key to the parent id plus
            the name; build a key that is unique per parent yourself when you
            pass one.

        Warning:
            The id does not depend on the job attempt either.  After a stage or
            job retry the job gets a new id; a key that stays the same still
            names the record that was written under the *old* job (it now lives
            in the earlier attempt's sub-timeline and is not drawn).  Put the
            attempt (``SYSTEM_JOBATTEMPT``) or the current job id into the key,
            or use :meth:`for_current_attempt` / :meth:`for_attempt`, which do it
            for every id.  With the default key (no ``key=``) you need nothing: the
            parent id is in the key and changes with the retried job.

        Args:
            key: Any stable string, for example an execution arn and a state
                name.
            attempt: Increase for a rerun of a completed record.  ``None`` takes
                the session's attempt (see :meth:`for_attempt`).

        Returns:
            A UUID.
        """
        used = self._attempt if attempt is None else attempt
        return uuid5(_ID_NAMESPACE, f"{self._build_id}/{key}#{used}")

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

    def _native(self) -> set[UUID]:
        """Return the ids of the records ADO created, read once per session.

        A record counts as native when it has a task definition, an
        ``identifier`` or a ``worker_name``, none of which this class ever
        sets.  Records created after the first read are not in the set.

        Returns:
            The native record ids.
        """
        if self._native_ids is None:
            self._native_ids = {
                r.id
                for r in self._records()
                if r.task is not None or r.identifier or r.worker_name
            }
        return self._native_ids

    def _check_new_id(self, record_id: UUID) -> None:
        """Refuse an id that belongs to a native record.

        Raises:
            AzureDevOpsSessionError: If writing the id would rename a native
                record.
        """
        if record_id in self._native():
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
        ref_name: str | None,
        order: int | None,
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
            ref_name=ref_name,
            order=order,
            last_modified="0001-01-01T00:00:00",
            previous_attempts=[],
        )
        self._check_new_id(record_id)
        self._send([write])
        return TimelineTarget(
            record_id=record_id,
            parent_id=under.record_id,
            type_name=type_name,
            name=name,
        )

    @staticmethod
    def _default_key(under: TimelineTarget, name: str) -> str:
        """Return the key used when the caller gives none: parent id + name.

        Returns:
            A key that is unique per parent and name.
        """
        return f"{under.record_id}/{name}"

    def create_job(
        self,
        name: str,
        *,
        under: TimelineTarget,
        key: str | None = None,
        attempt: int | None = None,
        state: BuildRecordState = BuildRecordState.IN_PROGRESS,
        icon: StatusIcon | str = StatusIcon.COLOURED,
        order: int | None = None,
    ) -> TimelineTarget:
        """Create a virtual job.

        The portal only draws a dynamic Job under a native Phase (see
        :meth:`native_phase`); under a Stage or another Job it gets no row.  A
        Job under a native Phase is also listed on the stage card and in the
        Jobs tab, whether it is running or completed.

        Warning:
            A job that you create already ``COMPLETED`` is drawn as a plain row
            at the top level, not as an expandable job with children, and a
            :class:`UserWarning` is issued.  Create it ``IN_PROGRESS`` and finish
            it afterwards.

        Warning:
            While a Job is running the portal's icon followed only a missing
            ``refName`` (grey); see :class:`StatusIcon`.

        Args:
            name: Display name.
            under: A native Phase.
            key: Stable key for the id; defaults to the parent id and *name*.
                See the warnings of :meth:`record_id`: the same key under two
                parents is one record, and a key that does not change survives
                a retry only as a record under the *old* job.
            attempt: Attempt number for the id; ``None`` takes the session's
                attempt (see :meth:`for_attempt` and :meth:`record_id`).
            state: Initial state.
            icon: A :class:`StatusIcon`, or any ``refName`` string.  The icon is
                chosen **here and cannot be changed later**: ADO stores a
                ``refName`` only the first time it is set.
            order: Sort position among the siblings (see :class:`RecordOrder`).

        Returns:
            The created record.

        Raises:
            AzureDevOpsSessionError: If *under* is not a Phase.
        """
        if under.type_name != BuildRecordType.PHASE:
            msg = f"A job is only drawn under a Phase, not under a {under.type_name}"
            raise AzureDevOpsSessionError(msg)
        if state == BuildRecordState.COMPLETED:
            warnings.warn(
                "A Job created COMPLETED is drawn as a plain row without children; "
                "create it IN_PROGRESS and finish it afterwards",
                UserWarning,
                stacklevel=2,
            )
        return self._create(
            BuildRecordType.JOB,
            name,
            under=under,
            state=state,
            record_id=self.record_id(
                key if key is not None else self._default_key(under, name),
                attempt=attempt,
            ),
            ref_name=str(icon),
            order=order,
        )

    def create_task(
        self,
        name: str,
        *,
        under: TimelineTarget,
        key: str | None = None,
        attempt: int | None = None,
        state: BuildRecordState = BuildRecordState.IN_PROGRESS,
        icon: StatusIcon | str = StatusIcon.COLOURED,
        order: int | None = None,
    ) -> TimelineTarget:
        """Create a virtual task below a Job or another Task.

        Warning:
            The portal draws Task nesting two levels deep (a task under a task);
            a third and fourth level are stored but **not drawn**, and a
            :class:`UserWarning` is issued for a task whose parent is already a
            task of a task.  Nothing below a Phase or Stage is drawn either.

        Args:
            name: Display name.
            under: A Job or Task.
            key: Stable key for the id; defaults to the parent id and *name*.
                See the warnings of :meth:`record_id`.
            attempt: Attempt number for the id; ``None`` takes the session's
                attempt (see :meth:`for_attempt` and :meth:`record_id`).
            state: Initial state.
            icon: A :class:`StatusIcon`, or any ``refName`` string.  The icon is
                chosen **here and cannot be changed later**: ADO stores a
                ``refName`` only the first time it is set.
            order: Sort position among the siblings (see :class:`RecordOrder`).

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
        if under.type_name == BuildRecordType.TASK and self._task_depth(under) >= (
            _DRAWN_TASK_DEPTH
        ):
            warnings.warn(
                "The portal draws Task nesting two levels deep; this task is "
                "stored but not drawn",
                UserWarning,
                stacklevel=2,
            )
        return self._create(
            BuildRecordType.TASK,
            name,
            under=under,
            state=state,
            record_id=self.record_id(
                key if key is not None else self._default_key(under, name),
                attempt=attempt,
            ),
            ref_name=str(icon),
            order=order,
        )

    def _task_depth(self, target: TimelineTarget) -> int:
        """Count the Task ancestors of *target*, itself included.

        Returns:
            1 for a task directly under a Job, 2 for a task under that, ...
        """
        by_id = {r.id: r for r in self._records()}
        depth, current = 0, by_id.get(target.record_id)
        while current is not None and current.type_name == BuildRecordType.TASK:
            depth += 1
            current = by_id.get(current.parent_id) if current.parent_id else None
        return depth

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

        The list **replaces** the existing one, on native records too.  Console
        lines never create issues.

        Warning:
            An empty list does not always clear: it is ignored on native records
            and on completed records, and it clears only a *virtual* record
            that is still ``inProgress``.  Once a record is completed its issues
            cannot be removed.

        Warning:
            ``warning_count`` and ``error_count`` are worked out when an issue
            list is written and are **not** recomputed when the list is
            replaced by a shorter one (two warnings replaced by one error read
            back as one error and two warnings); on a virtual record they are
            not writable.

        Warning:
            An issue of an unknown ``type`` is stored as ``error`` by ADO, yet
            appears in neither the Errors nor the Warnings tab of the summary
            page.  :class:`~pyado.raw.BuildIssueType` only allows the two real
            types.

        Note:
            Issues of a Job or Task show in the summary with the record's name
            as breadcrumb.  Issues of Phase, Checkpoint and Stage records were
            not measured, and a Stage record must not be written at all (see
            :class:`~pyado.raw.BuildRecordType`).

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
        them.  Use :meth:`append_log` for anything that must stay.  Lines sent
        after the step was completed are accepted and never shown.

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

    def add_summaries(
        self, target: TimelineTarget, summaries: Mapping[str, str | bytes]
    ) -> None:
        """Attach summaries (markdown cards) to a Task or Job record.

        Each entry becomes its own card in the build page's **Extensions** tab,
        titled by the file name, exactly like ``##vso[task.uploadsummary]``.
        A summary is identified by **record + name**: a name the record already
        has is replaced, the same name on another record is a second summary.
        Works with the admin token and on a build that has already finished.
        A summary cannot be deleted, only replaced.

        The Extensions tab has its own renderer, not the wiki's.  GitHub-style
        markdown and a sanitized subset of HTML (``details``, ``table``,
        ``span style``, ``font``, ``br``, ``img`` with an ``https`` source)
        render; mermaid, math, footnotes, ``:emoji:`` shortcodes and ``data:``
        images do not, and scripts, ``style``, ``svg``, ``iframe`` and ``on*``
        handlers are removed.  See ``docs/usage.md``, section "What a summary
        can contain", and :func:`pyado.raw.put_record_summaries`.

        Args:
            target: The record (Task or Job) that owns the files.
            summaries: File name to markdown or HTML (text is sent as UTF-8).
        """
        raw.put_record_summaries(
            self._timeline_call(), str(target.record_id), summaries
        )

    def iter_summaries(self) -> Iterator[raw.BuildAttachmentInfo]:
        """Iterate over every summary of the build, whoever wrote it.

        Yields:
            Each summary; ``record_id`` tells which record owns it.
        """
        yield from raw.iter_build_summaries(self._admin, self._build_id)

    def _log_id(self, target: TimelineTarget, wait: float) -> BuildLogId:
        """Return the record's log id, waiting for ADO to attach it.

        Returns:
            The log id.

        Raises:
            AzureDevOpsSessionError: If no log appears within *wait* seconds.
        """
        cached = self._log_ids.get(target.record_id)
        if cached is not None:
            return cached
        deadline = self._clock() + wait
        while True:
            for record in self._records():
                if record.id == target.record_id and record.log is not None:
                    self._log_ids[target.record_id] = record.log.id
                    return record.log.id
            if self._clock() >= deadline:
                msg = f"{target.name!r} has no log after {wait:.0f} s"
                raise AzureDevOpsSessionError(msg)
            time.sleep(2.0)

    def attach_log(self, target: TimelineTarget) -> BuildLogId:
        """Allocate a log and attach it to a record that has none.

        A record you created has no log; a native task already has one.  This
        also works for the *running task of an agent job*, whose ``log`` is
        ``null`` while it runs: allocate, attach and append worked from outside.

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
        self._log_ids[target.record_id] = info.id
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
        text shows in the portal after a reload, not live.  The log id is
        remembered, so only the first append of a record reads the timeline.

        Warning:
            ADO ends every append with a CR LF pair, so two appends are never
            joined into one line; a text is always sent with a final newline
            here.  A multibyte character must not be split across two calls, and
            one call should stay near 1 MiB (16 MiB timed out).  Text appended
            after :meth:`complete` can be read through the logs API but is not
            shown in the task pane.

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
        result: raw.JobEventResult | None = None,
    ) -> None:
        """Complete the agentless step so the pipeline continues.

        Only the System token can do this (a PAT gets HTTP 500).  The token
        expires at issue time + the ``timeoutInMinutes`` of the job it was
        issued to + 15 minutes (measured on agent jobs; for an agentless job
        that was not measured), so make sure that job outlives the workflow.

        This completes the task and nothing else.  Records you created and left
        ``inProgress`` are closed by ADO when the build ends, with the build's
        result; finish them first (:meth:`finish`).

        Warning:
            ``step`` must be the ``InvokeRESTAPI`` task's **own** record: the
            task id is resolved by ADO, so a made-up id with the real job id is
            rejected with HTTP 404 ``No job found with identifier ...``, as is a
            job that has already ended.  An unknown event is not an error: ADO
            answers 204 and does nothing.

        Args:
            step: The Task record from :meth:`resolve_task`.
            succeeded: ``False`` completes the step as failed.  Ignored when
                *result* is given.
            result: The outcome: ``SUCCEEDED``, ``FAILED`` (task and job fail)
                or ``SKIPPED`` (the task is skipped, the job still succeeds and
                the pipeline continues).

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
                f"{_SAFETY_SECONDS:.0f} s; raise the timeoutInMinutes of the job "
                "it was issued to so it outlives the workflow, or supply a "
                "fresh token"
            )
            raise AzureDevOpsSessionError(msg)
        if step.parent_id is None:
            msg = f"{step.name!r} has no parent job"
            raise AzureDevOpsSessionError(msg)
        outcome = result or (
            raw.JobEventResult.SUCCEEDED if succeeded else raw.JobEventResult.FAILED
        )
        plan_call = raw.get_plan_api_call(self._system, _HUB, self.plan_id())
        raw.post_job_event(
            plan_call,
            raw.JobEventPayload(
                name=raw.JobEventName.TASK_COMPLETED,
                task_id=step.record_id,
                job_id=step.parent_id,
                result=outcome,
            ),
        )
