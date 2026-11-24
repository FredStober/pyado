"""Integration tests for the raw functions that fill the build page's tabs.

Covers task summaries (Extensions), test runs/results/attachments (Tests), the
coverage report and container files (Code Coverage, Artifacts), plan timelines,
timeline record writes and build tags.

All writes go to the newest *finished* build of the project (a PAT may write to
a finished build), so no pipeline has to be queued.  Run this module alone::

    uv run pytest tests/integration/raw/test_build_tabs.py --no-cov
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import time
import uuid
from collections.abc import Iterator

import pytest

from pyado import raw
from tests.integration.raw._support import console

_PREFIX = "pyado-it-"


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def build(project_api_call: raw.ApiCall) -> raw.BuildDetails:
    """A freshly queued and cancelled build of the ``onpremise`` definition.

    ADO refuses timeline writes some hours after a build finished, so an old
    build cannot be reused.  A cancelled build ends within seconds, has task
    records and a plan, and its writes are accepted (measured).
    """
    definition = next(
        iter(raw.iter_pipeline_definitions(project_api_call, name_filter="onpremise")),
        None,
    )
    if definition is None:
        pytest.skip(reason="no 'onpremise' pipeline definition")
    queued = raw.post_build(
        project_api_call, raw.BuildQueueRequest(definition_id=definition.id)
    )
    call = raw.get_build_api_call(project_api_call, queued.id)
    time.sleep(3)
    raw.patch_build(call, raw.BuildStatus.CANCELLING)
    deadline = time.monotonic() + 120.0
    details = raw.get_build_details(call)
    while details.status != raw.BuildStatus.COMPLETED:
        assert time.monotonic() < deadline, "build did not finish after cancel"
        time.sleep(3)
        details = raw.get_build_details(call)
    console.print(f"  target build #{details.id}")
    assert details.orchestration_plan is not None
    return details


@pytest.fixture(scope="module")
def build_api_call(
    project_api_call: raw.ApiCall, build: raw.BuildDetails
) -> raw.ApiCall:
    """Build-level call of the target build."""
    return raw.get_build_api_call(project_api_call, build.id)


@pytest.fixture(scope="module")
def project_id_api_call(
    org_api_call: raw.ApiCall, token: str, org_url: str, project_name: str
) -> raw.ApiCall:
    """Project call addressed by project *id*.

    The ``distributedtask`` routes answer an empty HTTP 400 when the URL has
    the project *name*; only the id works (measured).
    """
    project = raw.get_project(org_api_call, project_name)
    return raw.ApiCall(
        session=raw.get_session(pat=token), url=f"{org_url}/{project.id}/_apis"
    )


@pytest.fixture(scope="module")
def plan_api_call(
    project_id_api_call: raw.ApiCall, build: raw.BuildDetails
) -> raw.ApiCall:
    """Plan-level call of the target build."""
    assert build.orchestration_plan is not None
    return raw.get_plan_api_call(
        project_id_api_call, "build", build.orchestration_plan.plan_id
    )


@pytest.fixture(scope="module")
def timeline_api_call(
    project_id_api_call: raw.ApiCall, build: raw.BuildDetails
) -> raw.ApiCall:
    """Root-timeline call (the root timeline id equals the plan id)."""
    assert build.orchestration_plan is not None
    plan_id = build.orchestration_plan.plan_id
    return raw.get_timeline_api_call(project_id_api_call, "build", plan_id, plan_id)


@pytest.fixture(scope="module")
def task_record(build_api_call: raw.ApiCall) -> raw.BuildRecordInfo:
    """An existing Task record of the target build."""
    for record in raw.iter_timeline_records(build_api_call):
        if record.type_name == raw.BuildRecordType.TASK:
            return record
    pytest.skip(reason="the target build has no task record")


@pytest.fixture(scope="module")
def container_id(project_api_call: raw.ApiCall, build: raw.BuildDetails) -> int:
    """Id of the build's own container (``BUILD_<id>``), found without an artifact.

    Returns:
        The container id.
    """
    found = raw.get_build_container_id(project_api_call, build.id)
    assert found is not None
    return found


@pytest.fixture
def test_run(
    project_api_call: raw.ApiCall, build: raw.BuildDetails
) -> Iterator[raw.TestRunInfo]:
    """A fresh in-progress test run, deleted afterwards.

    Yields:
        The created run.
    """
    run = raw.post_test_run(
        project_api_call,
        raw.TestRunCreate(
            name=f"{_PREFIX}run-{_suffix()}",
            build={"id": build.id},
            state=raw.TestRunState.IN_PROGRESS,
        ),
    )
    try:
        yield run
    finally:
        raw.delete_test_run(project_api_call, run.id)


# ---------------------------------------------------------------------------
# Extensions tab: summaries
# ---------------------------------------------------------------------------


def test_record_summaries(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    timeline_api_call: raw.ApiCall,
    task_record: raw.BuildRecordInfo,
) -> None:
    """Several summaries: names are separate, a repeated name is replaced.

    A summary is identified by record + name (measured), so the same name on a
    second record is a second summary and its ``record_id`` tells them apart.
    """
    suffix = _suffix()
    first, second, shared = (
        f"{_PREFIX}one-{suffix}.md",
        f"{_PREFIX}two-{suffix}.md",
        f"{_PREFIX}shared-{suffix}.md",
    )
    job_id = str(task_record.parent_id)
    stored = raw.put_record_summaries(
        timeline_api_call,
        str(task_record.id),
        {first: "# one\n", second: b"# two\n", shared: "on the task"},
    )
    assert [a.name for a in stored] == [first, second, shared]
    raw.put_record_summaries(
        timeline_api_call, str(task_record.id), {first: "# replaced\n"}
    )
    raw.put_record_summaries(timeline_api_call, job_id, {shared: "on the job"})

    mine = [
        a
        for a in raw.iter_build_summaries(project_api_call, build.id)
        if a.name in {first, second, shared}
    ]
    by_name = sorted(a.name for a in mine)
    assert by_name == sorted([first, second, shared, shared])
    assert {a.record_id for a in mine if a.name == shared} == {
        str(task_record.id),
        job_id,
    }
    replaced = next(a for a in mine if a.name == first)
    assert replaced.href is not None
    assert (
        project_api_call.session.get(replaced.href, timeout=30).text == "# replaced\n"
    )


# ---------------------------------------------------------------------------
# Tests tab
# ---------------------------------------------------------------------------


def test_run_lifecycle(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    test_run: raw.TestRunInfo,
) -> None:
    """Create, read, list and complete a run."""
    assert raw.get_test_run(project_api_call, test_run.id).name == test_run.name
    assert test_run.id in {
        r.id for r in raw.list_build_test_runs(project_api_call, build.id)
    }
    assert test_run.id in {
        r.id for r in raw.iter_build_test_runs(project_api_call, build.id)
    }
    closed = raw.patch_test_run(
        project_api_call,
        test_run.id,
        raw.TestRunUpdate(state=raw.TestRunState.COMPLETED, comment="done"),
    )
    assert closed.id == test_run.id
    assert raw.get_test_run(project_api_call, test_run.id).state == (
        raw.TestRunState.COMPLETED
    )


def test_run_created_completed_is_rejected() -> None:
    """The model refuses state=Completed before a request is sent."""
    with pytest.raises(ValueError, match="state"):
        raw.TestRunCreate(
            name="x",
            build={"id": 1},
            state=raw.TestRunState.COMPLETED,
        )


def test_results_roundtrip(
    project_api_call: raw.ApiCall, test_run: raw.TestRunInfo
) -> None:
    """Post results with all outcomes, read them back, then patch one."""
    outcomes = [raw.TestOutcome.PASSED, raw.TestOutcome.FAILED]
    created = raw.post_test_results(
        project_api_call,
        test_run.id,
        [
            raw.TestResultCreate(
                test_case_title=f"case {index}",
                automated_test_name=f"{_PREFIX}case.{index}",
                test_case={"name": f"case {index}"},
                outcome=outcome,
                comment="comment" if outcome == raw.TestOutcome.FAILED else None,
                error_message="boom" if outcome == raw.TestOutcome.FAILED else None,
                stack_trace="at x" if outcome == raw.TestOutcome.FAILED else None,
                computer_name="pyado-host",
            )
            for index, outcome in enumerate(outcomes)
        ],
    )
    assert len(created) == len(outcomes)

    listed = raw.list_test_results(project_api_call, test_run.id)
    assert {r.id for r in listed} == {r.id for r in created}
    assert [r.id for r in raw.iter_test_results(project_api_call, test_run.id)] == [
        r.id for r in listed
    ]
    assert (
        len(list(raw.iter_test_results(project_api_call, test_run.id, page_size=1)))
        == 2
    )

    failed = next(r for r in listed if r.outcome == "Failed")
    detail = raw.get_test_result(project_api_call, test_run.id, failed.id)
    assert detail.error_message == "boom"
    assert detail.stack_trace == "at x"
    assert detail.computer_name == "pyado-host"

    raw.patch_test_results(
        project_api_call,
        test_run.id,
        [raw.TestResultUpdate(id=failed.id, comment="patched")],
    )
    assert (
        raw.get_test_result(project_api_call, test_run.id, failed.id).comment
        == "patched"
    )


def test_result_and_run_attachments(
    project_api_call: raw.ApiCall, test_run: raw.TestRunInfo
) -> None:
    """Binary attachments come back byte for byte for a result and for a run."""
    [ref] = raw.post_test_results(
        project_api_call,
        test_run.id,
        [
            raw.TestResultCreate(
                test_case_title="att",
                automated_test_name=f"{_PREFIX}att",
                test_case={"name": "att"},
                outcome=raw.TestOutcome.PASSED,
            )
        ],
    )
    payload = bytes([0, 1, 2, 0xFF, 0xFE, 0]) + "ä€".encode()

    result_att = raw.post_test_result_attachment(
        project_api_call,
        test_run.id,
        ref.id,
        raw.make_attachment_request("result.bin", payload),
    )
    run_att = raw.post_test_run_attachment(
        project_api_call,
        test_run.id,
        raw.make_attachment_request("run.bin", payload),
    )

    result_files = list(
        raw.iter_test_result_attachments(project_api_call, test_run.id, ref.id)
    )
    run_files = list(raw.iter_test_run_attachments(project_api_call, test_run.id))
    assert "result.bin" in {a.file_name for a in result_files}
    assert "run.bin" in {a.file_name for a in run_files}
    assert (
        raw.get_test_attachment_bytes(
            project_api_call, test_run.id, result_att, result_id=ref.id
        )
        == payload
    )
    assert (
        raw.get_test_attachment_bytes(project_api_call, test_run.id, run_att) == payload
    )


def test_deleted_run_is_gone(
    project_api_call: raw.ApiCall, build: raw.BuildDetails
) -> None:
    """delete_test_run removes the run; the build listing still shows state 255."""
    run = raw.post_test_run(
        project_api_call,
        raw.TestRunCreate(
            name=f"{_PREFIX}delete-{_suffix()}",
            build={"id": build.id},
        ),
    )
    raw.delete_test_run(project_api_call, run.id)
    leftover = [
        r
        for r in raw.list_build_test_runs(project_api_call, build.id)
        if r.id == run.id
    ]
    assert all(r.state == raw.TestRunState.OTHER for r in leftover)
    with pytest.raises(raw.AzureDevOpsHttpError):
        raw.get_test_run(project_api_call, run.id)


def test_code_coverage_read(
    project_api_call: raw.ApiCall, build: raw.BuildDetails
) -> None:
    """get_code_coverage answers (an empty list when nothing was stored)."""
    summary = raw.get_code_coverage(project_api_call, build.id)
    assert isinstance(summary.coverage_data, list)


# ---------------------------------------------------------------------------
# Code Coverage report and Artifacts tab
# ---------------------------------------------------------------------------


def test_container_files(
    org_url: str,
    token: str,
    container_id: int,
) -> None:
    """Upload, list and read back files whose paths contain a space."""
    org_call = raw.ApiCall(session=raw.get_session(pat=token), url=org_url)
    container = raw.get_container_api_call(org_call, container_id)
    folder = f"{_PREFIX}files {_suffix()}"
    text = "héllo wörld\n"
    binary = bytes([0, 0xFF, 0x1F, 0x8B, 0])
    raw.put_container_file(container, f"{folder}/a b.txt", text.encode())
    raw.put_container_file(container, f"{folder}/bin.dat", binary)

    paths = {item.path for item in raw.iter_container_items(container, folder)}
    assert f"{folder}/a b.txt" in paths
    assert raw.get_container_item_text(container, f"{folder}/a b.txt") == text
    assert raw.get_container_item_bytes(container, f"{folder}/bin.dat") == binary
    with pytest.raises(ValueError, match="empty"):
        raw.put_container_file(container, f"{folder}/empty", b"")


def test_publish_coverage_report(
    org_url: str,
    token: str,
    project_api_call: raw.ApiCall,
    container_id: int,
    build: raw.BuildDetails,
) -> None:
    """publish_coverage_report uploads the folder and links the artifact."""
    org_call = raw.ApiCall(session=raw.get_session(pat=token), url=org_url)
    html = b"<html><body><h1>pyado integration report</h1></body></html>"
    artifact = raw.publish_coverage_report(
        org_call,
        project_api_call,
        build.id,
        container_id,
        {"index.html": html, "sub/page.html": b"<html>page</html>"},
    )
    assert artifact.name == f"Code Coverage Report_{build.id}"
    assert artifact.name in {
        a.name
        for a in raw.list_build_artifacts(
            raw.get_build_api_call(project_api_call, build.id)
        )
    }
    container = raw.get_container_api_call(org_call, container_id)
    assert (
        raw.get_container_item_bytes(container, f"{artifact.name}/index.html") == html
    )
    with pytest.raises(ValueError, match=r"index\.html"):
        raw.publish_coverage_report(
            org_call, project_api_call, build.id, container_id, {"x.html": b"x"}
        )


# ---------------------------------------------------------------------------
# Timeline records, plan timelines, tags
# ---------------------------------------------------------------------------


def test_patch_timeline_records_unchanged(
    build_api_call: raw.ApiCall,
    timeline_api_call: raw.ApiCall,
    task_record: raw.BuildRecordInfo,
) -> None:
    """Re-sending an existing record unchanged is accepted and changes nothing."""
    raw.patch_timeline_records(
        timeline_api_call,
        raw.TimelineRecordsUpdatePayload(value=[task_record], count=1),
    )
    after = next(
        r for r in raw.iter_timeline_records(build_api_call) if r.id == task_record.id
    )
    assert after.name == task_record.name
    assert after.result == task_record.result


def test_plan_timelines(plan_api_call: raw.ApiCall, build: raw.BuildDetails) -> None:
    """The root timeline is listed; a created one appears and is readable."""
    assert build.orchestration_plan is not None
    before = {t.id for t in raw.iter_plan_timelines(plan_api_call)}
    assert build.orchestration_plan.plan_id in before
    new_id = uuid.uuid4()
    raw.post_plan_timeline(plan_api_call, new_id)
    after = {t.id for t in raw.iter_plan_timelines(plan_api_call)}
    assert after == before | {new_id}


def test_build_tag_cycle(build_api_call: raw.ApiCall) -> None:
    """put_build_tag / delete_build_tag round trip."""
    tag = f"{_PREFIX}tag-{_suffix()}"
    assert tag in raw.put_build_tag(build_api_call, tag)
    assert tag in raw.list_build_tags(build_api_call)
    assert tag not in raw.delete_build_tag(build_api_call, tag)
    assert tag not in list(raw.iter_build_tags(build_api_call))


# ---------------------------------------------------------------------------
# Coverage figures (what PublishCodeCoverageResults@2 does, without the task)
# ---------------------------------------------------------------------------

_HOLD_PIPELINE = """
trigger: none
pr: none
pool: {vmImage: ubuntu-latest}
steps:
- checkout: self
- script: sleep 45
  displayName: hold
"""

_SOURCES = {
    "src/shop/cart.py": "def add(a, b):\n    return a + b\n",
    "src/shop/pricing.py": "def price(x):\n    return x\n",
}
_CHECKOUT = "/home/runner/work/1/s"


def test_publish_code_coverage_without_the_task(
    project_api_call: raw.ApiCall,
    project_id_api_call: raw.ApiCall,
) -> None:
    """Write coverage from outside while an agent job runs; the service finalises it.

    Needs a build that really runs an agent job (a cancelled build is never
    finalised), so this pushes a throwaway branch with a 45 s job.
    """
    repo = next(
        (
            r
            for r in raw.iter_repository_details(project_api_call)
            if r.name == "onpremise"
        ),
        None,
    )
    if repo is None:
        pytest.skip(reason="no 'onpremise' repository")
    repo_call = raw.get_repository_api_call(project_api_call, repo.id)
    branch = f"{_PREFIX}cov-{_suffix()}"
    raw.post_push(
        repo_call,
        raw.GitPushRequest(
            ref_updates=[
                raw.GitPushRefUpdate(
                    name=f"refs/heads/{branch}", old_object_id=raw.ZERO_SHA
                )
            ],
            commits=[
                raw.GitPushCommit(
                    comment="pyado integration test: coverage",
                    changes=[
                        raw.GitPushChange(
                            change_type=raw.GitChangeType.ADD,
                            item=raw.GitPushChangeItem(path=f"/{path}"),
                            new_content=raw.GitPushNewContent(content=content),
                        )
                        for path, content in {
                            "azure-pipelines.yml": _HOLD_PIPELINE,
                            **_SOURCES,
                        }.items()
                    ],
                )
            ],
        ),
    )
    try:
        queued = raw.post_build(
            project_api_call,
            raw.BuildQueueRequest(
                definition_id=1, source_branch=f"refs/heads/{branch}"
            ),
        )
        build_call = raw.get_build_api_call(project_api_call, queued.id)
        deadline = time.monotonic() + 240
        while not any(
            r.name == "hold" and r.state == raw.BuildRecordState.IN_PROGRESS
            for r in raw.iter_timeline_records(build_call)
        ):
            assert time.monotonic() < deadline, "the agent job never started"
            time.sleep(4)

        raw.publish_code_coverage(
            project_id_api_call,
            queued.id,
            [
                raw.FileCoverage(
                    file_path=f"{_CHECKOUT}/src/shop/cart.py",
                    line_coverage_status={"1": "covered", "2": "covered"},
                ),
                raw.FileCoverage(
                    file_path=f"{_CHECKOUT}/src/shop/pricing.py",
                    line_coverage_status={"1": "covered", "2": "notCovered"},
                ),
            ],
        )
        during = raw.get_code_coverage(project_api_call, queued.id)
        assert [
            (s.covered, s.total) for d in during.coverage_data for s in d.coverage_stats
        ] == [(3, 4)]

        deadline = time.monotonic() + 300
        final = during
        while final.status != "finalized":
            assert time.monotonic() < deadline, f"never finalised: {final.status}"
            time.sleep(4)
            final = raw.get_code_coverage(project_api_call, queued.id)
        stats = [s for d in final.coverage_data for s in d.coverage_stats]
        assert [(s.label, s.covered, s.total) for s in stats] == [("Lines", 3, 4)]
        # the Files tab reads the coverage service, which maps the paths to the checkout
        org, project = project_id_api_call.url.unicode_string().split("/")[3:5]
        url = f"https://vstmr.dev.azure.com/{org}/{project}/_apis/coverage/summary"
        deadline = time.monotonic() + 120
        while True:
            summary = project_id_api_call.session.get(
                url,
                params={
                    "pipelineRunId": str(queued.id),
                    "api-version": "6.0-preview.1",
                },
                timeout=60,
            ).json()
            if summary.get("summary") or time.monotonic() > deadline:
                break
            time.sleep(5)
        assert summary.get("summary") == {"covered": 3, "notCovered": 1}, summary
    finally:
        head = next(
            raw.iter_refs(repo_call, raw.GitRefFilter(name_filter=f"heads/{branch}")),
            None,
        )
        if head is not None:
            raw.post_repository_refs(
                repo_call,
                [
                    raw.GitRefUpdate(
                        name=head.name,
                        new_object_id=raw.ZERO_SHA,
                        old_object_id=head.object_id,
                    )
                ],
            )


# ---------------------------------------------------------------------------
# Low-level building blocks behind the wrappers above
# ---------------------------------------------------------------------------


def test_record_attachment_of_custom_type(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    timeline_api_call: raw.ApiCall,
    task_record: raw.BuildRecordInfo,
) -> None:
    """A custom-typed attachment is listed under its type and not as a summary."""
    attachment_type = f"{_PREFIX}type-{_suffix()}"
    name = f"{_PREFIX}custom.txt"
    raw.put_record_attachment(
        timeline_api_call, str(task_record.id), attachment_type, name, b"custom"
    )
    listed = list(
        raw.iter_build_attachments(project_api_call, build.id, attachment_type)
    )
    assert [a.name for a in listed] == [name]
    summaries = {
        a.name
        for a in raw.iter_build_attachments(
            project_api_call, build.id, raw.SUMMARY_ATTACHMENT_TYPE
        )
    }
    assert name not in summaries


def test_container_artifact_request(
    org_url: str,
    token: str,
    project_api_call: raw.ApiCall,
    container_id: int,
    build: raw.BuildDetails,
) -> None:
    """A folder in the build container is linked as an artifact by hand."""
    org_call = raw.ApiCall(session=raw.get_session(pat=token), url=org_url)
    container = raw.get_container_api_call(org_call, container_id)
    folder = f"{_PREFIX}artifact-{_suffix()}"
    content = b"artifact content"
    raw.put_container_file(container, f"{folder}/data.txt", content)

    assert (
        raw.make_container_artifact_data(container_id, folder)
        == f"#/{container_id}/{folder}"
    )
    request = raw.make_report_artifact_request(
        container_id, folder, size=len(content), browsable=False
    )
    artifact = raw.post_build_artifact(project_api_call, build.id, request)
    assert artifact.name == folder


def test_coverage_figures_and_files(
    project_id_api_call: raw.ApiCall, build: raw.BuildDetails
) -> None:
    """The figures and the per-file data are accepted by the coverage service."""
    results = raw.get_test_results_api_call(project_id_api_call)
    assert results.url.host == "vstmr.dev.azure.com"
    raw.post_code_coverage(
        results,
        build.id,
        [raw.CodeCoverageStats(label="line", position=4, total=2, covered=1)],
    )
    blob = raw.post_file_coverage(
        results,
        build.id,
        [
            raw.FileCoverage(
                file_path=f"{_CHECKOUT}/src/shop/cart.py",
                line_coverage_status={"1": "covered", "2": "notCovered"},
            )
        ],
    )
    assert blob.endswith(".cjson")
