"""Tests for pyado.oop.pipelines.timeline_session using an in-memory fake ADO."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import contextlib
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
import requests

from pyado.exceptions import (
    AzureDevOpsBadRequestError,
    AzureDevOpsHttpError,
    AzureDevOpsSessionError,
)
from pyado.oop import TimelineSession, TimelineTarget
from pyado.oop.pipelines.timeline_session import decode_token_expiry
from pyado.raw import (
    ApiCall,
    BuildIssue,
    BuildIssueType,
    BuildRecordResult,
    BuildRecordState,
    BuildRecordType,
)
from tests.conftest import NOW_ISO

if TYPE_CHECKING:
    from collections.abc import Callable

BUILD_ID = 77
PAT = "unit-test-credential"
PLAN_ID = uuid4()
PROJECT_URL = f"https://dev.azure.com/org/{uuid4()}/_apis"
STAGE, PHASE, JOB, STEP = (uuid4() for _ in range(4))
NOW = 1_000_000_000.0 + 5_000.0


def _record(
    record_id: UUID, name: str, type_name: str, parent: UUID | None, **extra: Any
) -> dict[str, Any]:
    """Return a timeline record dict in the shape the API returns."""
    record: dict[str, Any] = {
        "attempt": 1,
        "changeId": None,
        "currentOperation": None,
        "details": None,
        "finishTime": None,
        "id": str(record_id),
        "identifier": None,
        "lastModified": NOW_ISO,
        "log": None,
        "name": name,
        "refName": None,
        "parentId": str(parent) if parent else None,
        "percentComplete": None,
        "previousAttempts": [],
        "result": None,
        "resultCode": None,
        "startTime": None,
        "state": "inProgress",
        "task": None,
        "type": type_name,
        "url": None,
        "workerName": None,
    }
    record.update(extra)
    return record


class FakeAdo(requests.Session):
    """A tiny in-memory Azure DevOps: timeline, records, logs, feed, events."""

    def __init__(self) -> None:
        """Create the fake with a stage, phase, job and one native step."""
        super().__init__()
        self.records: dict[str, dict[str, Any]] = {}
        self.logs: dict[int, list[str]] = {}
        self.feed: list[tuple[str, list[str]]] = []
        self.events: list[dict[str, Any]] = []
        self.requests_seen: list[tuple[str, str]] = []
        self.patched: list[dict[str, Any]] = []
        self.hide_log_polls = 0
        self.fail_events_with: int | None = None
        for rec in (
            _record(STAGE, "Stage", "Stage", None),
            _record(PHASE, "Phase", "Phase", STAGE),
            _record(JOB, "Job", "Job", PHASE),
            _record(
                STEP,
                "Run workflow",
                "Task",
                JOB,
                identifier="native",
                task={"id": str(uuid4()), "name": "InvokeRESTAPI", "version": "1"},
            ),
        ):
            self.records[rec["id"]] = rec

    def request(
        self,
        method: str | bytes,
        url: str | bytes,
        *_args: Any,
        **kwargs: Any,
    ) -> Any:
        """Answer one request from the in-memory state.

        Returns:
            A mock response.

        Raises:
            AssertionError: If a test triggers an endpoint the fake lacks.
        """
        method = method.decode() if isinstance(method, bytes) else method
        url = url.decode() if isinstance(url, bytes) else url
        self.requests_seen.append((method, url))
        json_body: dict[str, Any] = kwargs.get("json") or {}
        data: bytes = kwargs.get("data") or b""
        route = (method, url.rsplit("/", 1)[-1])
        if method == "POST" and "/logs/" in url:
            route = ("POST", "append")
        handlers: dict[tuple[str, str], Callable[[], Any]] = {
            ("GET", "timeline"): lambda: _response(200, self._timeline()),
            ("PATCH", "records"): lambda: self._patch_records(json_body["value"]),
            ("POST", "logs"): lambda: self._new_log(json_body["path"]),
            ("POST", "append"): lambda: self._append(url, data),
            ("POST", "feed"): lambda: self._feed(url, json_body["value"]),
            ("POST", "events"): lambda: self._event(json_body),
        }
        if route not in handlers:
            msg = f"unexpected request {method} {url}"
            raise AssertionError(msg)
        return handlers[route]()

    def _new_log(self, path: str) -> Any:
        """Allocate a log id.

        Returns:
            A mock response with the new log id.
        """
        log_id = len(self.logs) + 100
        self.logs[log_id] = []
        return _response(200, {"id": log_id, "path": path})

    def _append(self, url: str, data: bytes) -> Any:
        """Append content to a log.

        Returns:
            An empty mock response.
        """
        self.logs[int(url.rsplit("/", 1)[1])].append(data.decode())
        return _response(200, {})

    def _feed(self, url: str, lines: list[str]) -> Any:
        """Record feed lines.

        Returns:
            An empty mock response.
        """
        self.feed.append((url, lines))
        return _response(200, {})

    def _event(self, body: dict[str, Any]) -> Any:
        """Record a pipeline event, or fail it when a test asks for that.

        Returns:
            A mock response.
        """
        if self.fail_events_with:
            return _response(self.fail_events_with, {"message": "nope"})
        self.events.append(body)
        return _response(200, {})

    def _timeline(self) -> dict[str, Any]:
        """Return the timeline, hiding logs for the first few polls on request.

        Returns:
            The timeline body.
        """
        if self.hide_log_polls > 0:
            self.hide_log_polls -= 1
            visible = [dict(r, log=None) for r in self.records.values()]
        else:
            visible = list(self.records.values())
        return {"id": str(PLAN_ID), "records": visible}

    def _patch_records(self, writes: list[dict[str, Any]]) -> Any:
        """Apply record writes: upsert; type and parent stay as first created.

        Returns:
            A mock response, HTTP 400 for a partial write of an unknown record.
        """
        self.patched.extend(writes)
        for write in writes:
            current = self.records.get(write["id"])
            if current is None:
                if "type" not in write:
                    return _response(400, {"message": "unknown record"})
                current = _record(
                    UUID(write["id"]), write.get("name", ""), write["type"], None
                )
                self.records[write["id"]] = current
            for key, value in write.items():
                immutable = key in {"type", "parentId"} and key in current
                if immutable and current[key] is not None:
                    continue
                current[key] = value
        return _response(200, {})


def _response(status: int, body: Any) -> MagicMock:
    """Build a mock ``requests.Response``.

    Returns:
        A mock response carrying *body*.
    """
    mock = MagicMock(spec=requests.Response)
    mock.status_code = status
    mock.ok = status < 400
    mock.url = PROJECT_URL
    mock.headers = {"Content-Type": "application/json"}
    mock.content = json.dumps(body).encode()
    mock.text = json.dumps(body)
    mock.json.return_value = body
    if status >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    else:
        mock.raise_for_status.return_value = None
    return mock


def _jwt(claims: dict[str, Any]) -> str:
    """Return an unsigned JWT-shaped string carrying *claims*.

    Returns:
        A string with three dot-separated parts.
    """
    part = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJub25lIn0.{part}.sig"


class Clock:
    """A controllable clock; ``sleep`` advances it."""

    def __init__(self, now: float = NOW) -> None:
        """Start the clock at *now*."""
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def ado() -> FakeAdo:
    """Return a fresh fake ADO.

    Returns:
        The fake.
    """
    return FakeAdo()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """Return a clock and make ``time.sleep`` advance it instead of waiting.

    Returns:
        The controllable clock.
    """
    c = Clock()
    monkeypatch.setattr(
        "pyado.oop.pipelines.timeline_session.time.sleep",
        lambda s: setattr(c, "now", c.now + s),
    )
    return c


def _session(
    ado: FakeAdo,
    clock: Clock,
    *,
    system: FakeAdo | None = None,
    expiry: float | None = None,
) -> TimelineSession:
    admin_call = ApiCall(session=ado, url=PROJECT_URL)
    system_call = (
        ApiCall(session=system, url=PROJECT_URL) if system is not None else None
    )
    return TimelineSession(
        admin_call=admin_call,
        system_call=system_call,
        build_id=BUILD_ID,
        system_token_expiry=expiry,
        clock=clock,
    )


@pytest.fixture
def session(ado: FakeAdo, clock: Clock) -> TimelineSession:
    """Return a session bound to the fake with a System credential.

    Returns:
        A session whose System token expires one hour from the fake clock.
    """
    return _session(ado, clock, system=ado, expiry=NOW + 3600)


class TestResolve:
    """Finding records by name."""

    def test_resolve_task_returns_the_step(self, session: TimelineSession) -> None:
        step = session.resolve_task("Run workflow")
        assert step.record_id == STEP
        assert step.parent_id == JOB
        assert step.type_name == BuildRecordType.TASK

    def test_resolve_task_unknown_name_raises(self, session: TimelineSession) -> None:
        with pytest.raises(AzureDevOpsSessionError, match="No task named"):
            session.resolve_task("missing")

    def test_resolve_task_ambiguous_name_raises(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        dup = _record(uuid4(), "Run workflow", "Task", JOB)
        ado.records[dup["id"]] = dup
        with pytest.raises(AzureDevOpsSessionError, match=r"2 tasks"):
            session.resolve_task("Run workflow")

    def test_find_by_name_under_parent(self, session: TimelineSession) -> None:
        job = session.find(
            "Job", under=session.native_phase(session.resolve_task("Run workflow"))
        )
        assert job.record_id == JOB

    def test_find_requires_exactly_one(self, session: TimelineSession) -> None:
        with pytest.raises(AzureDevOpsSessionError, match="Expected one"):
            session.find("nothing here")

    def test_native_phase_of_step(self, session: TimelineSession) -> None:
        phase = session.native_phase(session.resolve_task("Run workflow"))
        assert phase.record_id == PHASE
        assert phase.type_name == BuildRecordType.PHASE

    def test_native_phase_needs_job_and_phase(self, session: TimelineSession) -> None:
        orphan = TimelineTarget(
            record_id=uuid4(), parent_id=None, type_name=BuildRecordType.TASK, name="x"
        )
        with pytest.raises(AzureDevOpsSessionError, match="no Job and Phase"):
            session.native_phase(orphan)
        under_stage = TimelineTarget(
            record_id=uuid4(), parent_id=JOB, type_name=BuildRecordType.TASK, name="y"
        )
        assert session.native_phase(under_stage).record_id == PHASE

    def test_plan_id_is_read_once(self, session: TimelineSession, ado: FakeAdo) -> None:
        assert session.plan_id() == PLAN_ID
        assert session.plan_id() == PLAN_ID
        assert sum(1 for m, u in ado.requests_seen if u.endswith("/timeline")) == 1

    def test_plan_id_missing_timeline_raises(
        self, ado: FakeAdo, clock: Clock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session = _session(ado, clock)
        monkeypatch.setattr(ApiCall, "get", lambda *_args, **_kwargs: [])
        with pytest.raises(AzureDevOpsSessionError, match="no timeline"):
            session.plan_id()


class TestIds:
    """Stable record ids."""

    def test_same_key_same_id(self, session: TimelineSession) -> None:
        assert session.record_id("arn/StateA") == session.record_id("arn/StateA")

    def test_attempt_changes_id(self, session: TimelineSession) -> None:
        assert session.record_id("k") != session.record_id("k", attempt=2)

    def test_build_changes_id(self, ado: FakeAdo, clock: Clock) -> None:
        other = TimelineSession(
            admin_call=ApiCall(session=ado, url=PROJECT_URL),
            system_call=None,
            build_id=BUILD_ID + 1,
            clock=clock,
        )
        assert other.record_id("k") != _session(ado, clock).record_id("k")


class TestCreate:
    """Creating virtual jobs and tasks."""

    def test_job_under_phase(self, session: TimelineSession, ado: FakeAdo) -> None:
        phase = session.native_phase(session.resolve_task("Run workflow"))
        job = session.create_job("Branch A", under=phase)
        stored = ado.records[str(job.record_id)]
        assert stored["type"] == "Job"
        assert stored["parentId"] == str(PHASE)
        assert stored["state"] == "inProgress"

    def test_job_not_under_phase_raises(self, session: TimelineSession) -> None:
        step = session.resolve_task("Run workflow")
        with pytest.raises(AzureDevOpsSessionError, match="only drawn under a Phase"):
            session.create_job("bad", under=step)

    def test_task_under_job_and_under_task(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        job = session.find("Job")
        task = session.create_task("Validate", under=job)
        nested = session.create_task("Detail", under=task)
        assert ado.records[str(nested.record_id)]["parentId"] == str(task.record_id)

    def test_task_under_phase_raises(self, session: TimelineSession) -> None:
        phase = session.native_phase(session.resolve_task("Run workflow"))
        with pytest.raises(
            AzureDevOpsSessionError, match="only drawn under a Job or Task"
        ):
            session.create_task("bad", under=phase)

    def test_pending_task_has_no_start_time(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task(
            "Later", under=session.find("Job"), state=BuildRecordState.PENDING
        )
        assert ado.records[str(task.record_id)].get("startTime") is None

    def test_same_key_is_an_upsert(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        job = session.find("Job")
        first = session.create_task("State A", under=job, key="arn/A")
        second = session.create_task("State A renamed", under=job, key="arn/A")
        assert first.record_id == second.record_id
        assert ado.records[str(first.record_id)]["name"] == "State A renamed"

    def test_rerun_with_new_attempt_gets_new_record(
        self, session: TimelineSession
    ) -> None:
        job = session.find("Job")
        first = session.create_task("State A", under=job, key="arn/A")
        again = session.create_task("State A", under=job, key="arn/A", attempt=2)
        assert first.record_id != again.record_id

    def test_refuses_native_record_id(
        self, session: TimelineSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            TimelineSession, "record_id", lambda *_args, **_kwargs: STEP
        )
        with pytest.raises(AzureDevOpsSessionError, match="native record"):
            session.create_task("hijack", under=session.find("Job"))


class TestWireFormat:
    """The JSON the API receives must use the API's own field names."""

    def test_new_record_uses_type_not_typename(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        session.create_task("T", under=session.find("Job"))
        sent = ado.patched[0]
        assert sent["type"] == "Task"
        assert "typeName" not in sent
        assert {
            "id",
            "name",
            "parentId",
            "state",
            "attempt",
            "startTime",
        } <= sent.keys()

    def test_unset_fields_are_not_sent(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task("T", under=session.find("Job"))
        ado.patched.clear()
        session.set_state(task, percent=10)
        assert ado.patched == [{"id": str(task.record_id), "percentComplete": 10}]


class TestUpdate:
    """State, result, progress and issues."""

    def test_finish_sets_state_result_progress_and_time(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task("T", under=session.find("Job"))
        session.finish(task)
        stored = ado.records[str(task.record_id)]
        assert (stored["state"], stored["result"], stored["percentComplete"]) == (
            "completed",
            "succeeded",
            100,
        )
        assert stored["finishTime"] is not None

    def test_finish_with_failure(self, session: TimelineSession, ado: FakeAdo) -> None:
        task = session.create_task("T", under=session.find("Job"))
        session.finish(task, BuildRecordResult.FAILED)
        assert ado.records[str(task.record_id)]["result"] == "failed"

    def test_set_state_running_has_no_finish_time(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task("T", under=session.find("Job"))
        session.set_state(task, percent=40)
        stored = ado.records[str(task.record_id)]
        assert stored["percentComplete"] == 40
        assert "finishTime" not in stored or stored["finishTime"] is None

    def test_report_issues_replaces(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task("T", under=session.find("Job"))
        session.report_issues(
            task, [BuildIssue(type=BuildIssueType.ERROR, message="first")]
        )
        session.report_issues(
            task, [BuildIssue(type=BuildIssueType.WARNING, message="second")]
        )
        assert [i["message"] for i in ado.records[str(task.record_id)]["issues"]] == [
            "second"
        ]


class TestBatch:
    """Several writes in one request."""

    def test_batch_sends_one_patch(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        job = session.find("Job")
        before = sum(1 for m, u in ado.requests_seen if m == "PATCH")
        with session.batch():
            for i in range(5):
                session.create_task(f"T{i}", under=job, key=f"k{i}")
        assert sum(1 for m, u in ado.requests_seen if m == "PATCH") - before == 1
        assert sum(1 for r in ado.records.values() if r["name"].startswith("T")) == 5

    def test_batch_rejects_duplicate_id(self, session: TimelineSession) -> None:
        job = session.find("Job")

        def write_the_same_record_twice() -> None:
            with session.batch():
                session.create_task("A", under=job, key="same")
                session.create_task("B", under=job, key="same")

        with pytest.raises(AzureDevOpsSessionError, match="twice in one batch"):
            write_the_same_record_twice()

    def test_batch_cannot_nest(self, session: TimelineSession) -> None:
        with contextlib.ExitStack() as stack:
            stack.enter_context(session.batch())
            with pytest.raises(AzureDevOpsSessionError, match="nested"):
                stack.enter_context(session.batch())

    def test_empty_batch_sends_nothing(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        before = len(ado.requests_seen)
        with session.batch():
            pass
        assert len(ado.requests_seen) == before


class TestFeedAndLog:
    """Live console and persistent log."""

    def test_feed_goes_to_the_job_record(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        session.feed(session.resolve_task("Run workflow"), "hello", "world")
        url, lines = ado.feed[0]
        assert f"/records/{JOB}/feed" in url
        assert lines == ["hello", "world"]

    def test_feed_for_a_job_target_uses_its_own_id(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        session.feed(session.find("Job"), "x")
        assert f"/records/{JOB}/feed" in ado.feed[0][0]

    def test_feed_without_lines_sends_nothing(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        session.feed(session.resolve_task("Run workflow"))
        assert ado.feed == []

    def test_feed_without_a_job_raises(self, session: TimelineSession) -> None:
        orphan = TimelineTarget(
            record_id=uuid4(), parent_id=None, type_name=BuildRecordType.TASK, name="x"
        )
        with pytest.raises(AzureDevOpsSessionError, match="no job"):
            session.feed(orphan, "x")

    def test_append_to_native_log(self, session: TimelineSession, ado: FakeAdo) -> None:
        ado.records[str(STEP)]["log"] = {
            "id": 5,
            "type": "Container",
            "url": "https://dev.azure.com/org/p/_apis/build/builds/1/logs/5",
        }
        ado.logs[5] = []
        session.append_log(session.resolve_task("Run workflow"), "line one")
        assert ado.logs[5] == ["line one\n"]

    def test_append_keeps_an_existing_newline(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        ado.records[str(STEP)]["log"] = {
            "id": 5,
            "type": "Container",
            "url": "https://dev.azure.com/org/p/_apis/build/builds/1/logs/5",
        }
        ado.logs[5] = []
        session.append_log(session.resolve_task("Run workflow"), "a\nb\n")
        assert ado.logs[5] == ["a\nb\n"]

    def test_append_waits_for_the_log_to_attach(
        self, session: TimelineSession, ado: FakeAdo, clock: Clock
    ) -> None:
        ado.records[str(STEP)]["log"] = {
            "id": 6,
            "type": "Container",
            "url": "https://dev.azure.com/org/p/_apis/build/builds/1/logs/6",
        }
        ado.logs[6] = []
        ado.hide_log_polls = 3
        session.append_log(session.resolve_task("Run workflow"), "late")
        assert ado.logs[6] == ["late\n"]
        assert clock.now > NOW

    def test_append_gives_up_when_no_log_appears(
        self, session: TimelineSession
    ) -> None:
        with pytest.raises(AzureDevOpsSessionError, match="no log after"):
            session.append_log(session.resolve_task("Run workflow"), "x", wait=5)

    def test_append_creates_and_attaches_a_log_for_a_new_record(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        task = session.create_task("T", under=session.find("Job"))
        session.append_log(task, "first", create=True)
        session.append_log(task, "second", create=True)
        log = ado.records[str(task.record_id)]["log"]
        assert ado.logs[log["id"]] == ["first\n", "second\n"]


class TestComplete:
    """Completing the agentless step."""

    def test_complete_sends_task_completed_with_the_step_ids(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        session.complete(session.resolve_task("Run workflow"))
        event = ado.events[0]
        assert event["name"] == "TaskCompleted"
        assert event["taskId"] == str(STEP)
        assert event["jobId"] == str(JOB)
        assert event["result"] == "succeeded"

    def test_complete_as_failed(self, session: TimelineSession, ado: FakeAdo) -> None:
        session.complete(session.resolve_task("Run workflow"), succeeded=False)
        assert ado.events[0]["result"] == "failed"

    def test_complete_needs_a_system_token(self, ado: FakeAdo, clock: Clock) -> None:
        session = _session(ado, clock)
        with pytest.raises(AzureDevOpsSessionError, match=r"System\.AccessToken"):
            session.complete(session.resolve_task("Run workflow"))

    def test_complete_refuses_an_expired_token(
        self, ado: FakeAdo, clock: Clock
    ) -> None:
        session = _session(ado, clock, system=ado, expiry=NOW - 1)
        with pytest.raises(AzureDevOpsSessionError, match="timeoutInMinutes"):
            session.complete(session.resolve_task("Run workflow"))
        assert ado.events == []

    def test_complete_refuses_a_token_about_to_expire(
        self, ado: FakeAdo, clock: Clock
    ) -> None:
        session = _session(ado, clock, system=ado, expiry=NOW + 10)
        with pytest.raises(AzureDevOpsSessionError, match="expires within"):
            session.complete(session.resolve_task("Run workflow"))

    def test_complete_with_unknown_expiry_still_sends(
        self, ado: FakeAdo, clock: Clock
    ) -> None:
        session = _session(ado, clock, system=ado, expiry=None)
        session.complete(session.resolve_task("Run workflow"))
        assert len(ado.events) == 1
        assert session.seconds_until_system_token_expires() is None

    def test_complete_without_a_parent_job_raises(
        self, session: TimelineSession
    ) -> None:
        orphan = TimelineTarget(
            record_id=uuid4(), parent_id=None, type_name=BuildRecordType.TASK, name="x"
        )
        with pytest.raises(AzureDevOpsSessionError, match="no parent job"):
            session.complete(orphan)

    def test_seconds_until_expiry(self, session: TimelineSession) -> None:
        assert session.seconds_until_system_token_expires() == 3600


class TestHttpFailures:
    """What happens when ADO rejects a call."""

    def test_a_rejected_task_completed_is_not_swallowed(
        self, session: TimelineSession, ado: FakeAdo
    ) -> None:
        ado.fail_events_with = 500
        with pytest.raises(AzureDevOpsHttpError) as raised:
            session.complete(session.resolve_task("Run workflow"))
        assert raised.value.status_code == 500

    def test_a_partial_update_of_an_unknown_record_is_a_bad_request(
        self, session: TimelineSession
    ) -> None:
        ghost = TimelineTarget(
            record_id=uuid4(),
            parent_id=JOB,
            type_name=BuildRecordType.TASK,
            name="ghost",
        )
        with pytest.raises(AzureDevOpsBadRequestError):
            session.set_state(ghost, percent=5)

    def test_the_fake_rejects_endpoints_it_does_not_know(self, ado: FakeAdo) -> None:
        with pytest.raises(AssertionError, match="unexpected request"):
            ado.request("DELETE", f"{PROJECT_URL}/anything")


class TestTokenExpiry:
    """Reading the System token's expiry."""

    def test_nested_expiry_is_the_earliest(self) -> None:
        token = _jwt(
            {"exp": 2_000_000_000, "xms_attr": {"abc": {"ado_exp": 1_900_000_000}}}
        )
        assert decode_token_expiry(token) == 1_900_000_000

    def test_expiry_inside_a_nested_jwt(self) -> None:
        inner = _jwt({"exp": 1_800_000_000})
        assert (
            decode_token_expiry(_jwt({"exp": 2_000_000_000, "wrapped": inner}))
            == 1_800_000_000
        )

    def test_not_a_jwt(self) -> None:
        assert decode_token_expiry("not-a-token") is None

    def test_garbage_payload(self) -> None:
        assert decode_token_expiry("a.@@@.c") is None

    def test_no_time_claims(self) -> None:
        assert decode_token_expiry(_jwt({"sub": "x"})) is None

    def test_deeply_nested_claims_are_not_followed_forever(self) -> None:
        node: dict[str, Any] = {"exp": 1_700_000_000}
        for _ in range(20):
            node = {"x": node}
        assert decode_token_expiry(_jwt(node)) is None

    def test_broken_nested_jwt_is_ignored(self) -> None:
        assert (
            decode_token_expiry(_jwt({"w": "eyJa.@@@.sig", "exp": 1_900_000_000}))
            == 1_900_000_000
        )


class TestFromTokens:
    """Building a session from tokens."""

    def test_from_tokens_with_and_without_system_token(self) -> None:
        both = TimelineSession.from_tokens(
            org_name="org",
            project_id=uuid4(),
            build_id=1,
            admin_token=PAT,
            system_token=_jwt({"exp": 1_900_000_000}),
        )
        assert both.seconds_until_system_token_expires() is not None
        only_admin = TimelineSession.from_tokens(
            org_name="org", project_id=uuid4(), build_id=1, admin_token=PAT
        )
        assert only_admin.seconds_until_system_token_expires() is None
