"""Integration tests for TestRun, TestResult and CodeCoverage (read-only)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Build, CodeCoverage, Project, TestResult, TestRun
from pyado.raw import SUMMARY_ATTACHMENT_TYPE
from tests.integration.raw._support import _take, console

_SCAN_BUILDS = 40


def _exercise_run(run: TestRun) -> None:
    """Read a run's pair, results and attachments."""
    assert isinstance(run.name, str)
    for result in _take(run.iter_results(), 3):
        assert isinstance(result, TestResult)
        assert result.run is run
        _ = (result.id, result.outcome, result.name)
        result.list_attachments()
    run.list_attachments()


def _exercise_coverage(build: Build, entry: CodeCoverage) -> None:
    """Read one coverage entry and its lookups."""
    _ = (entry.flavor, entry.platform, entry.status, entry.stats)
    entry.percent("line")
    entry.stat("branch")
    assert entry.build is build


def test_build_tests_read(proj: Project) -> None:
    """Find a build with test runs / coverage and read them through the OOP layer."""
    console.print("\n=== Build tests and coverage (read) ===")
    builds = _take(proj.pipelines.iter_builds(), _SCAN_BUILDS)
    with_runs = False
    with_coverage = False
    for build in builds:
        runs = build.list_test_runs()
        if runs and not with_runs:
            with_runs = True
            for run in runs[:3]:
                _exercise_run(run)
            build.list_test_results()
        entries = build.list_code_coverage()
        if entries and not with_coverage:
            with_coverage = True
            for entry in entries:
                _exercise_coverage(build, entry)
        if with_runs and with_coverage:
            break
    if builds:
        build = builds[0]
        build.list_attachments(SUMMARY_ATTACHMENT_TYPE)
        build.list_container_items()
