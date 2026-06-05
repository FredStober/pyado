#!/usr/bin/env python3
"""Live integration smoke test for pyado raw layer.

Exercises every public raw API function (READ and WRITE) against the real
Azure DevOps instance described by test.json.

Usage::

    python smoke_test_raw.py [--seed N] [--skip-pipeline-trigger]

Different seeds exercise different optional-parameter combinations, giving
broader code-path coverage over multiple runs.

The ``--skip-pipeline-trigger`` flag skips any test that would queue a real
build, including the onpremise-pipeline section that triggers the pipeline
named "onpremise", waits for it to print its agent variables, and then
exercises the following functions that otherwise require a live ADO agent:
    raw: get_plan_api_call, get_job_api_call, get_log_api_call,
         get_timeline_api_call, post_job_feed, post_job_logs, post_job_event
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import argparse
import datetime
import pathlib
import random
import sys

from pyado import raw
from pyado.raw.smoke_test._agent import _test_onpremise_pipeline
from pyado.raw.smoke_test._approvals import (
    _test_approvals_read,
    _test_sprint_iterations_read,
)
from pyado.raw.smoke_test._build import _test_build_logs_read, _test_builds_read
from pyado.raw.smoke_test._git import (
    _test_git_extras_read,
    _test_git_extras_write,
    _test_git_read,
)
from pyado.raw.smoke_test._pipeline import _test_pipeline_run, _test_pipelines_read
from pyado.raw.smoke_test._profile import _test_profile
from pyado.raw.smoke_test._projects import (
    _test_connection_data,
    _test_project_read,
    _test_projects,
)
from pyado.raw.smoke_test._pull_request import (
    _test_git_pr_write,
    _test_pr_extras_read,
    _test_prs_read,
)
from pyado.raw.smoke_test._runner import (
    _ONPREMISE_LABELS,
    _allowed_skips,
    _install_recorder,
    _load_config,
    _print_summary,
    _results,
    _save_recordings,
    _skip,
    check_raw_coverage,
    console,
)
from pyado.raw.smoke_test._team import _test_teams_read
from pyado.raw.smoke_test._variable_group import (
    _test_variable_group_create_delete,
    _test_variable_group_details_read,
    _test_variable_group_write,
    _test_variable_groups_read,
)
from pyado.raw.smoke_test._work_item import (
    _test_classification_write,
    _test_query_classification_read,
    _test_work_item_extras_read,
    _test_work_item_write,
    _test_work_items_read,
)


def _run_read_phase(
    token: str,
    org_url: str,
    project_name: str,
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> tuple:
    """Run all read-only smoke tests; return results needed by write phase."""
    profile, _vssps_api_call = _test_profile(token, org_url)
    reviewer_id: str | None = profile.id if profile else None

    if reviewer_id is None:
        for status in ("completed", "abandoned", "active"):
            for pr in raw.iter_pull_requests(
                project_api_call,
                search_criteria=raw.PullRequestSearchCriteria(status=status),
            ):
                if pr.created_by and pr.created_by.id:
                    reviewer_id = str(pr.created_by.id)
                    console.print(
                        f"  [dim]reviewer_id from PR history: "
                        f"{reviewer_id} ({pr.created_by.display_name})[/dim]"
                    )
                    break
            if reviewer_id:
                break

    projects = _test_projects(org_api_call)
    repo, repo_api_call, commits = _test_git_read(project_api_call, rng)

    default_branch = repo.default_branch if repo else None
    defs, builds = _test_builds_read(
        project_api_call, rng, default_branch=default_branch
    )

    var_groups = _test_variable_groups_read(project_api_call)
    _test_prs_read(project_api_call, rng)
    _test_work_items_read(project_api_call, rng)
    _test_sprint_iterations_read(project_api_call, rng)
    _test_approvals_read(project_api_call, rng)
    pipelines = _test_pipelines_read(project_api_call, rng)

    # ---- READ extras ----
    _test_connection_data(org_api_call)
    _test_project_read(org_api_call, project_name)
    _test_teams_read(org_api_call, project_api_call, project_name)
    _test_git_extras_read(project_api_call, repo_api_call, repo, commits, rng)
    _test_query_classification_read(project_api_call)
    _test_variable_group_details_read(project_api_call, var_groups)
    _test_pr_extras_read(project_api_call, rng)
    _test_work_item_extras_read(project_api_call, rng)
    _test_build_logs_read(project_api_call, builds)

    return (
        reviewer_id,
        projects,
        repo,
        repo_api_call,
        commits,
        defs,
        var_groups,
        pipelines,
    )


def _run_write_phase(
    project_api_call: raw.ApiCall,
    project_name: str,
    rng: random.Random,
    run_ts: str,
    skip_pipeline_trigger: bool,
    read_results: tuple,
) -> None:
    """Run all write smoke tests."""
    (
        reviewer_id,
        projects,
        repo,
        repo_api_call,
        commits,
        defs,
        var_groups,
        pipelines,
    ) = read_results
    del defs

    if skip_pipeline_trigger:
        for label in (
            "post_pipeline_run / iter_timeline_records (write)",
            "patch_build [raw, cancel]",
        ):
            _skip(label, "--skip-pipeline-trigger set")
    else:
        _test_pipeline_run(project_api_call, pipelines, [])

    _test_work_item_write(project_api_call, rng, run_ts)

    if repo and repo_api_call:
        _test_git_pr_write(
            project_api_call,
            repo_api_call,
            repo,
            commits,
            rng,
            run_ts,
            reviewer_id=reviewer_id,
        )
    else:
        _skip("git/PR write tests", "no repository found")

    if var_groups:
        vg_for_write = next(
            (g for g in var_groups if g.variable_group_refs is not None),
            var_groups[0],
        )
        current_project = next((p for p in projects if p.name == project_name), None)
        _test_variable_group_write(
            project_api_call, vg_for_write, rng, project=current_project
        )
    else:
        _skip("variable group write tests", "no variable groups found")

    current_project = next((p for p in projects if p.name == project_name), None)
    _test_variable_group_create_delete(
        project_api_call, current_project, rng, pipelines=pipelines
    )
    _test_git_extras_write(project_api_call, repo_api_call, repo, commits, rng)
    _test_classification_write(project_api_call, rng)

    if skip_pipeline_trigger:
        for label in _ONPREMISE_LABELS:
            _skip(label, "--skip-pipeline-trigger set")
    else:
        _test_onpremise_pipeline(project_api_call, rng, pipelines)


def main() -> int:
    """Run the raw smoke test suite and return an exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed (default: 42). Different seeds exercise different paths.",
    )
    parser.add_argument(
        "--record",
        metavar="FILE",
        default=None,
        help=(
            "Write all API request/response pairs to FILE as JSON "
            "(default: ado_smoke_seed<N>.json).  Pass an empty string to disable."
        ),
    )
    parser.add_argument(
        "--skip-pipeline-trigger",
        action="store_true",
        default=False,
        help=(
            "Skip all tests that queue real builds, including post_pipeline_run "
            "and the onpremise agent-only API section."
        ),
    )
    args = parser.parse_args()

    record_path: pathlib.Path | None
    if not args.record:
        record_path = None
    elif args.record is None:
        record_path = pathlib.Path(f"ado_smoke_seed{args.seed}.json")
    else:
        record_path = pathlib.Path(args.record)

    _install_recorder()

    rng = random.Random(args.seed)
    check_raw_coverage(pathlib.Path(__file__).parent)
    run_ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    console.print(f"pyado smoke test  |  seed={args.seed}  |  run={run_ts}\n")

    org_url, project_name, token = _load_config()

    org_api_call = raw.ApiCall(access_token=token, url=f"{org_url}/_apis")
    project_api_call = raw.ApiCall(
        access_token=token, url=f"{org_url}/{project_name}/_apis"
    )

    read_results = _run_read_phase(
        token, org_url, project_name, org_api_call, project_api_call, rng
    )

    _run_write_phase(
        project_api_call,
        project_name,
        rng,
        run_ts,
        args.skip_pipeline_trigger,
        read_results,
    )

    allowed = _allowed_skips(args.skip_pipeline_trigger)
    unexpected = [
        (label, reason)
        for label, status, reason in _results
        if status == "SKIP" and label not in allowed
    ]

    if record_path:
        _save_recordings(record_path)

    return _print_summary(unexpected=unexpected)


if __name__ == "__main__":
    sys.exit(main())
