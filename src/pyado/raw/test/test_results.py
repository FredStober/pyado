"""Test runs, test results and code coverage (the build page's Tests tab).

Everything here was measured against a live organisation (Azure DevOps
Services) with a PAT; no storage key is involved.  Writes are accepted on a
build that has already finished.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
import json
from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, TypeAlias
from uuid import uuid4

import requests
from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall
from pyado.raw.pipelines.build import BuildId

__all__ = [
    "CodeCoverageData",
    "CodeCoverageStats",
    "CodeCoverageSummary",
    "FileCoverage",
    "TestAttachmentInfo",
    "TestAttachmentRequest",
    "TestAttachmentType",
    "TestIdentity",
    "TestOutcome",
    "TestResultCreate",
    "TestResultInfo",
    "TestResultRef",
    "TestResultUpdate",
    "TestRunCreate",
    "TestRunId",
    "TestRunInfo",
    "TestRunState",
    "TestRunUpdate",
    "delete_test_run",
    "get_code_coverage",
    "get_test_attachment_bytes",
    "get_test_result",
    "get_test_results_api_call",
    "get_test_run",
    "iter_build_test_runs",
    "iter_test_result_attachments",
    "iter_test_results",
    "iter_test_run_attachments",
    "list_build_test_runs",
    "list_test_results",
    "make_attachment_request",
    "patch_test_results",
    "patch_test_run",
    "post_code_coverage",
    "post_file_coverage",
    "post_test_result_attachment",
    "post_test_results",
    "post_test_run",
    "post_test_run_attachment",
    "publish_code_coverage",
]

TestRunId: TypeAlias = int

_VERSION = "7.1"
_COVERAGE_VERSION = "7.1-preview.1"


class TestRunState(StrEnum):
    """Lifecycle state of a test run."""

    __test__ = False

    NOT_STARTED = "NotStarted"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    ABORTED = "Aborted"
    OTHER = "Other"
    """Any state this enum does not know.

    A *deleted* run is still listed by ``iter_build_test_runs`` with the state
    ``"255"`` (measured), which would otherwise fail validation of the whole list.
    """

    @classmethod
    def _missing_(cls, value: object) -> "TestRunState":  # ruff: ignore[unused-class-method-argument]
        """Map any unknown state to :attr:`OTHER`.

        Returns:
            :attr:`OTHER`, whatever *value* is.
        """
        return cls.OTHER


class TestOutcome(StrEnum):
    """Outcome of one test result; each has its own icon in the Tests tab."""

    __test__ = False

    PASSED = "Passed"
    FAILED = "Failed"
    NOT_EXECUTED = "NotExecuted"
    INCONCLUSIVE = "Inconclusive"
    BLOCKED = "Blocked"
    TIMEOUT = "Timeout"
    ERROR = "Error"
    ABORTED = "Aborted"
    NOT_APPLICABLE = "NotApplicable"
    WARNING = "Warning"
    PAUSED = "Paused"


class TestAttachmentType(StrEnum):
    """Attachment kinds accepted on a run or a result."""

    __test__ = False

    GENERAL = "GeneralAttachment"
    CONSOLE_LOG = "ConsoleLog"


class TestIdentity(AdoBaseModel):
    """A user reference (owner, run-by).  Shown as the **Owner** in the detail pane."""

    __test__ = False

    id: str
    display_name: str | None = None


class _BuildRef(AdoBaseModel):
    id: BuildId


class _NameRef(AdoBaseModel):
    name: str


class TestRunCreate(AdoBaseModel):
    """Body of :func:`post_test_run`.

    Measured: a zero-GUID ``dtlTestEnvironment`` (and ``runTimeout``) makes the
    server answer HTTP 500 "Value cannot be null. Parameter name: testRun", so
    those fields are deliberately not modelled.  ``state`` is limited to
    ``NotStarted`` and ``InProgress``: a run created ``Completed`` is rejected
    with HTTP 400 ("Test Run cannot be created with Completed state ... use
    update to mark it completed"); close it with :func:`patch_test_run`.
    """

    __test__ = False

    name: str
    build: _BuildRef
    is_automated: bool = True
    state: Literal[TestRunState.NOT_STARTED, TestRunState.IN_PROGRESS] = (
        TestRunState.IN_PROGRESS
    )
    started_date: datetime | None = None
    comment: str | None = None
    build_platform: str | None = None
    build_flavor: str | None = None
    owner: TestIdentity | None = None


class TestRunUpdate(AdoBaseModel):
    """Body of :func:`patch_test_run` (partial update)."""

    __test__ = False

    state: TestRunState | None = None
    comment: str | None = None
    completed_date: datetime | None = None


class TestRunInfo(AdoBaseModel, extra="ignore"):
    """A test run as returned by the API."""

    __test__ = False

    id: TestRunId
    name: str
    state: TestRunState | None = None
    total_tests: int | None = None
    passed_tests: int | None = None
    unanalyzed_tests: int | None = None


class _TestRunResults(AdoBaseModel):
    value: list[TestRunInfo]


class TestResultCreate(AdoBaseModel):
    """One result of :func:`post_test_results`.

    ``owner`` and ``comment`` / ``error_message`` / ``stack_trace`` fill the
    detail pane (Owner, Comments, Error message, Stack trace); ``computer_name``
    shows as "on <name>".  Post **one clean set**: every row becomes a test in
    the run.

    The **duration is computed by the server** from ``completed_date -
    started_date`` (measured: a separate duration value, sent under either
    ``durationInMilliseconds`` or ``durationInMs``, was ignored; a result with
    only the two dates got the difference).  Set both dates to give a result a
    duration; without them the duration reads back as ``None``.
    """

    __test__ = False

    test_case_title: str
    automated_test_name: str
    test_case: _NameRef
    outcome: TestOutcome
    state: str = "Completed"
    started_date: datetime | None = None
    completed_date: datetime | None = None
    priority: int | None = None
    automated_test_storage: str | None = None
    computer_name: str | None = None
    comment: str | None = None
    error_message: str | None = None
    stack_trace: str | None = None
    failure_type: str | None = None
    owner: TestIdentity | None = None
    run_by: TestIdentity | None = None


class _BugRef(AdoBaseModel):
    id: int


class TestResultUpdate(AdoBaseModel):
    """One partial update of :func:`patch_test_results`.

    ``associated_bugs`` links work items (the PATCH answers 200; whether the
    *Work items* sub-tab shows them was not confirmed).  ``iteration_details``
    is **not** modelled: the server answered HTTP 500 ``TF400898`` for it.
    """

    __test__ = False

    id: int
    outcome: TestOutcome | None = None
    comment: str | None = None
    associated_bugs: list[_BugRef] | None = None


class TestResultRef(AdoBaseModel, extra="ignore"):
    """The id the server assigned to a posted result."""

    __test__ = False

    id: int
    automated_test_name: str | None = None
    outcome: str | None = None


class _TestResultRefs(AdoBaseModel):
    value: list[TestResultRef]


class _Named(AdoBaseModel, extra="ignore"):
    name: str | None = None


class _UserRef(AdoBaseModel, extra="ignore"):
    display_name: str | None = None
    id: str | None = None


class TestResultInfo(AdoBaseModel, extra="ignore"):
    """A test result as the Tests tab shows it.

    ``outcome`` is kept as text so a value this version does not know still
    reads.  Fields the server omits are ``None``; ``duration_in_ms`` is a float
    (the server sends ``2000.0``).
    """

    __test__ = False

    id: int
    outcome: str | None = None
    state: str | None = None
    test_case_title: str | None = None
    automated_test_name: str | None = None
    automated_test_storage: str | None = None
    test_case: _Named | None = None
    comment: str | None = None
    error_message: str | None = None
    stack_trace: str | None = None
    failure_type: str | None = None
    computer_name: str | None = None
    priority: int | None = None
    duration_in_ms: float | None = None
    started_date: datetime | None = None
    completed_date: datetime | None = None
    owner: _UserRef | None = None
    run_by: _UserRef | None = None
    last_updated_by: _UserRef | None = None


class _TestResultInfos(AdoBaseModel):
    value: list[TestResultInfo]


class TestAttachmentInfo(AdoBaseModel, extra="ignore"):
    """An attachment of a test run or a test result."""

    __test__ = False

    id: int
    file_name: str
    size: int | None = None
    comment: str | None = None
    url: str | None = None


class _TestAttachmentInfos(AdoBaseModel):
    value: list[TestAttachmentInfo]


class TestAttachmentRequest(AdoBaseModel):
    """Body of the attachment calls; ``stream`` is the base64 file content."""

    __test__ = False

    stream: str
    file_name: str
    attachment_type: TestAttachmentType = TestAttachmentType.GENERAL
    comment: str | None = None


class _AttachmentRef(AdoBaseModel, extra="ignore"):
    id: int


class CodeCoverageStats(AdoBaseModel):
    """One coverage figure (``Lines``, ``Branches`` ...)."""

    label: str
    position: int
    total: int
    covered: int
    is_delta_available: bool = False


class CodeCoverageData(AdoBaseModel):
    """Coverage of one flavor/platform combination."""

    build_flavor: str = ""
    build_platform: str = ""
    coverage_stats: list[CodeCoverageStats] = Field(default_factory=list)


class CodeCoverageSummary(AdoBaseModel, extra="ignore"):
    """What :func:`get_code_coverage` returns for a build."""

    coverage_data: list[CodeCoverageData] = Field(default_factory=list)
    status: str | None = None


def post_test_run(project_api_call: ApiCall, request: TestRunCreate) -> TestRunInfo:
    """Create a test run for a build.

    Returns:
        The created run (use its ``id`` for the result calls).

    Reference:
        POST .../test/runs
    """
    response = project_api_call.post(
        "test",
        "runs",
        version=_VERSION,
        json=request.model_dump(by_alias=True, mode="json", exclude_none=True),
    )
    return TestRunInfo.model_validate(response)


def patch_test_run(
    project_api_call: ApiCall, run_id: TestRunId, request: TestRunUpdate
) -> TestRunInfo:
    """Update a run, e.g. ``state=Completed`` to close it.

    Returns:
        The updated run.
    """
    response = project_api_call.patch(
        "test",
        "runs",
        run_id,
        version=_VERSION,
        json=request.model_dump(by_alias=True, mode="json", exclude_none=True),
    )
    return TestRunInfo.model_validate(response)


def get_test_run(project_api_call: ApiCall, run_id: TestRunId) -> TestRunInfo:
    """Read one run.

    Returns:
        The run with its counters.
    """
    response = project_api_call.get("test", "runs", run_id, version=_VERSION)
    return TestRunInfo.model_validate(response)


def iter_build_test_runs(
    project_api_call: ApiCall, build_id: BuildId
) -> Iterator[TestRunInfo]:
    """Iterate over the test runs of a build.

    Yields:
        Each run attached to ``build_id``.
    """
    response = project_api_call.get(
        "test",
        "runs",
        parameters={"buildUri": f"vstfs:///Build/Build/{build_id}"},
        version=_VERSION,
    )
    yield from _TestRunResults.model_validate(response).value


def list_build_test_runs(
    project_api_call: ApiCall, build_id: BuildId
) -> list[TestRunInfo]:
    """List the test runs of a build.

    Returns:
        All runs attached to ``build_id``.
    """
    return list(iter_build_test_runs(project_api_call, build_id))


def post_test_results(
    project_api_call: ApiCall,
    run_id: TestRunId,
    results: list[TestResultCreate],
) -> list[TestResultRef]:
    """Add results to a run.

    Returns:
        The server-assigned ids, in the order sent.
    """
    response = project_api_call.post(
        "test",
        "runs",
        run_id,
        "results",
        version=_VERSION,
        json=[
            r.model_dump(by_alias=True, mode="json", exclude_none=True) for r in results
        ],
    )
    return _TestResultRefs.model_validate(response).value


def patch_test_results(
    project_api_call: ApiCall,
    run_id: TestRunId,
    updates: list[TestResultUpdate],
) -> list[TestResultRef]:
    """Update existing results (outcome, comment, linked bugs).

    Returns:
        The updated result references.
    """
    response = project_api_call.patch(
        "test",
        "runs",
        run_id,
        "results",
        version=_VERSION,
        json=[
            u.model_dump(by_alias=True, mode="json", exclude_none=True) for u in updates
        ],
    )
    return _TestResultRefs.model_validate(response).value


def make_attachment_request(
    file_name: str,
    content: bytes,
    *,
    attachment_type: TestAttachmentType = TestAttachmentType.GENERAL,
    comment: str | None = None,
) -> TestAttachmentRequest:
    """Build an attachment request from raw bytes (base64-encodes them).

    Returns:
        The request for the attachment calls.
    """
    return TestAttachmentRequest(
        stream=base64.b64encode(content).decode("ascii"),
        file_name=file_name,
        attachment_type=attachment_type,
        comment=comment,
    )


def post_test_result_attachment(
    project_api_call: ApiCall,
    run_id: TestRunId,
    result_id: int,
    request: TestAttachmentRequest,
) -> int:
    """Attach a file to one result (listed in the detail pane's Attachments sub-tab).

    Returns:
        The attachment id.
    """
    response = project_api_call.post(
        "test",
        "runs",
        run_id,
        "results",
        result_id,
        "attachments",
        version=_VERSION,
        json=request.model_dump(by_alias=True, mode="json", exclude_none=True),
    )
    return _AttachmentRef.model_validate(response).id


def post_test_run_attachment(
    project_api_call: ApiCall,
    run_id: TestRunId,
    request: TestAttachmentRequest,
) -> int:
    """Attach a file to a whole run.

    Returns:
        The attachment id.
    """
    response = project_api_call.post(
        "test",
        "runs",
        run_id,
        "attachments",
        version=_VERSION,
        json=request.model_dump(by_alias=True, mode="json", exclude_none=True),
    )
    return _AttachmentRef.model_validate(response).id


def iter_test_results(
    project_api_call: ApiCall, run_id: TestRunId, *, page_size: int = 1000
) -> Iterator[TestResultInfo]:
    """Iterate over the results of a run, page by page.

    Args:
        project_api_call: Project-level call (``{org}/{project}/_apis``).
        run_id: The run.
        page_size: Results per request.

    Yields:
        Each result of the run, in server order.
    """
    skip = 0
    while True:
        response = project_api_call.get(
            "test",
            "runs",
            run_id,
            "results",
            parameters={"$top": page_size, "$skip": skip},
            version=_VERSION,
        )
        page = _TestResultInfos.model_validate(response).value
        yield from page
        if len(page) < page_size:
            return
        skip += page_size


def list_test_results(
    project_api_call: ApiCall, run_id: TestRunId
) -> list[TestResultInfo]:
    """List every result of a run.

    Returns:
        All results of the run.
    """
    return list(iter_test_results(project_api_call, run_id))


def get_test_result(
    project_api_call: ApiCall, run_id: TestRunId, result_id: int
) -> TestResultInfo:
    """Read one result.

    Returns:
        The result with its error text, owner and dates.
    """
    response = project_api_call.get(
        "test", "runs", run_id, "results", result_id, version=_VERSION
    )
    return TestResultInfo.model_validate(response)


def iter_test_result_attachments(
    project_api_call: ApiCall, run_id: TestRunId, result_id: int
) -> Iterator[TestAttachmentInfo]:
    """Iterate over the attachments of one result.

    Yields:
        Each attachment (name, size, id).
    """
    response = project_api_call.get(
        "test",
        "runs",
        run_id,
        "results",
        result_id,
        "attachments",
        version="7.1-preview.1",
    )
    yield from _TestAttachmentInfos.model_validate(response).value


def iter_test_run_attachments(
    project_api_call: ApiCall, run_id: TestRunId
) -> Iterator[TestAttachmentInfo]:
    """Iterate over the attachments of a whole run.

    Yields:
        Each attachment (name, size, id).
    """
    response = project_api_call.get(
        "test", "runs", run_id, "attachments", version="7.1-preview.1"
    )
    yield from _TestAttachmentInfos.model_validate(response).value


def get_test_attachment_bytes(
    project_api_call: ApiCall,
    run_id: TestRunId,
    attachment_id: int,
    *,
    result_id: int | None = None,
) -> bytes:
    """Download the content of a run or result attachment.

    Args:
        project_api_call: Project-level call.
        run_id: The run.
        attachment_id: The attachment's id (from the attachment listing).
        result_id: Set it for an attachment of a *result*; leave it out for a run
            attachment.

    Returns:
        The file content.
    """
    path: list[str | int] = ["test", "runs", run_id]
    if result_id is not None:
        path += ["results", result_id]
    path += ["attachments", attachment_id]
    content: bytes = project_api_call.get_raw(*path, version="7.1-preview.1")
    return content


def delete_test_run(project_api_call: ApiCall, run_id: TestRunId) -> None:
    """Delete a test run with its results.

    Reference:
        DELETE .../test/runs/{id}
    """
    project_api_call.delete("test", "runs", run_id, version=_VERSION)


def get_code_coverage(
    project_api_call: ApiCall, build_id: BuildId
) -> CodeCoverageSummary:
    """Read the coverage summary stored for a build.

    ``status`` is ``completed`` while the build runs and ``finalized`` once it
    ended; the stats label is ``line`` first and ``Lines`` after finalisation.
    To write figures see :func:`publish_code_coverage`.

    Returns:
        The stored summary (``coverage_data`` is empty when none was stored).
    """
    response: Any = project_api_call.get(
        "test",
        "codecoverage",
        parameters={"buildId": build_id, "deltaBuildId": 0},
        version=_COVERAGE_VERSION,
    )
    return CodeCoverageSummary.model_validate(response)


# ---------------------------------------------------------------------------
# Writing the coverage figures (what PublishCodeCoverageResults@2 sends)
# ---------------------------------------------------------------------------

_TEST_RESULTS_HOST = "https://vstmr.dev.azure.com"
_COVERAGE_WRITE_VERSION = "7.2-preview.1"
_BLOB_VERSION = "2019-07-07"


class FileCoverage(AdoBaseModel):
    """Line coverage of one source file (an entry of the ``.cjson`` blob).

    ``line_coverage_status`` maps a line number (as text) to ``"covered"``,
    ``"notCovered"`` or ``"partiallyCovered"``.

    ``file_path`` must be the **absolute path on the agent** of a file that the
    build checked out (for example ``/home/runner/work/1/s/src/shop/cart.py``;
    ``Build.SourcesDirectory`` plus the repository path).  A repository-relative
    path, or an absolute path of a file that is not in the checkout, still fills
    the **Details** tab but leaves **Files** empty (measured).
    """

    file_path: str
    line_coverage_status: dict[str, str]
    branch_coverage_status: dict[str, str] | None = None


def get_test_results_api_call(project_api_call: ApiCall) -> ApiCall:
    """Return the call for the test-results service of a project.

    The coverage routes live on ``vstmr.dev.azure.com/{org}``, a different host
    than ``dev.azure.com``.  The project segment must be the project **id**.

    Args:
        project_api_call: Project call (``https://dev.azure.com/{org}/{project}/_apis``).

    Returns:
        A call for ``https://vstmr.dev.azure.com/{org}/{project}/_apis/testresults``
        that uses the same session and credentials.
    """
    parts = project_api_call.url.unicode_string().rstrip("/").split("/")
    org_and_project = "/".join(parts[3:5])
    return ApiCall(
        session=project_api_call.session,
        timeout=project_api_call.timeout,
        url=f"{_TEST_RESULTS_HOST}/{org_and_project}/_apis/testresults",
    )


def post_code_coverage(
    test_results_api_call: ApiCall,
    build_id: BuildId,
    stats: list[CodeCoverageStats],
    *,
    build_platform: str = "",
    build_flavor: str = "",
) -> None:
    """Store the coverage figures (header percentage and Details table) of a build.

    This is the request ``PublishCodeCoverageResults@2`` makes: ``POST
    testresults/codecoverage`` on the test-results host.  The older
    ``POST test/codecoverage`` answers 204 and stores **nothing**.  Behaviour
    measured against a live organisation:

    * A PAT works.  The answer is HTTP 204.
    * The figures read ``completed`` / label ``line``.  When the build **ends
      after it ran an agent job**, the service finalises them (``finalized``,
      label ``Lines``) a few seconds later.  A build that is cancelled before any
      job ran is never finalised.
    * On their own the figures do **not** fill the Code Coverage tab: it needs
      the per-file data of :func:`post_file_coverage` as well; use
      :func:`publish_code_coverage` for both.

    Args:
        test_results_api_call: From :func:`get_test_results_api_call`.
        build_id: The build.
        stats: The figures, for example ``label="line"``, ``position=4``.
        build_platform: Platform text (usually empty).
        build_flavor: Flavor text (usually empty).
    """
    body = {
        "coverageStats": [
            {**s.model_dump(by_alias=True, mode="json"), "delta": 0.0} for s in stats
        ],
        "buildPlatform": build_platform,
        "buildFlavor": build_flavor,
    }
    test_results_api_call.post(
        "codecoverage",
        parameters={"buildId": build_id},
        version=_COVERAGE_WRITE_VERSION,
        json=body,
    )


def post_file_coverage(
    test_results_api_call: ApiCall,
    build_id: BuildId,
    files: list[FileCoverage],
) -> str:
    """Upload the per-file line coverage that fills the Files/Details tabs.

    Two steps, as the task does them: ``POST testlogstoreendpoint`` returns a
    short-lived signed container URL, then the JSON is put into
    ``Intermediate/<guid><buildId><guid>.cjson`` there.  The blob host gets **no
    credentials** from this function except the signature in the URL.  Without
    this upload the tab stays "No code coverage data available", even when the
    figures are stored.

    Args:
        test_results_api_call: From :func:`get_test_results_api_call`.
        build_id: The build.
        files: Line status per source file.

    Returns:
        The blob name that was written.
    """
    response = test_results_api_call.post(
        "testlogstoreendpoint",
        parameters={"buildId": build_id, "testLogStoreOperationType": "ReadAndCreate"},
        version=_COVERAGE_WRITE_VERSION,
    )
    base, _, query = str(response["endpointSASUri"]).partition("?")
    name = f"{uuid4()}{build_id}{uuid4()}.cjson"
    payload = json.dumps(
        [f.model_dump(by_alias=True, mode="json") for f in files]
    ).encode()
    with requests.Session() as blob_session:
        reply = blob_session.put(
            f"{base}/Intermediate/{name}?{query}",
            data=payload,
            headers={"x-ms-blob-type": "BlockBlob", "x-ms-version": _BLOB_VERSION},
            timeout=test_results_api_call.timeout,
        )
        reply.raise_for_status()
    return name


def publish_code_coverage(
    project_api_call: ApiCall,
    build_id: BuildId,
    files: list[FileCoverage],
    *,
    label: str = "line",
) -> None:
    """Write the coverage of a build the way ``PublishCodeCoverageResults@2`` does.

    Computes the line totals from ``files`` and calls :func:`post_file_coverage`
    and then :func:`post_code_coverage`.  Do it **while the build runs** (or
    shortly after).  What it fills, measured against a live organisation:

    * **Details** (percentage, line counts, a table per file) and the Code
      Coverage tab's sub-tabs: when the build has run an **agent job** and ended
      normally (a build cancelled before a job ran is never finalised).
    * **Files** (a folder tree with per-folder coverage): additionally the build
      must have **checked out the sources** (``checkout: self``; with
      ``checkout: none`` the tab stays empty), and every ``file_path`` must be
      the absolute agent path of a checked-out file (see :class:`FileCoverage`).
    * The Summary page's **"N % covered"** next to "Tests and coverage": only
      when the build also has a test run with results; without one it reads
      "Get started".

    Args:
        project_api_call: Project call; the project must be addressed by id.
        build_id: The build.
        files: Line status per source file.
        label: Label of the figure; the service rewrites ``line`` to ``Lines``.
    """
    results = get_test_results_api_call(project_api_call)
    covered = sum(
        1 for f in files for v in f.line_coverage_status.values() if v == "covered"
    )
    total = sum(len(f.line_coverage_status) for f in files)
    post_file_coverage(results, build_id, files)
    post_code_coverage(
        results,
        build_id,
        [CodeCoverageStats(label=label, position=4, total=total, covered=covered)],
    )
