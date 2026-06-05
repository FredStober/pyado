#!/usr/bin/env python3
"""Live integration smoke test for the pyado OOP layer.

Exercises every public method and property of every OOP class against the real
Azure DevOps instance described by test.json.

Usage::

    python smoke_test_oop.py [--no-write] [--seed N]

The ``--no-write`` flag skips all tests that mutate state (create/update/delete
work items, pull requests, branches, variable-group variables, etc.).  Read-only
tests always run.

Write tests create their own resources and clean up after themselves.  A test
PR is created on a throw-away branch, exercised, then abandoned.  A test work
item is created, exercised, then soft-deleted.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import argparse
import pathlib
import random
import sys

from pyado.oop.smoke_test._build import _test_build_read, _test_write_build_tags
from pyado.oop.smoke_test._iteration_area import _test_iteration_area_read
from pyado.oop.smoke_test._organization import _test_organization
from pyado.oop.smoke_test._pipeline import (
    _test_pipeline_read,
    _test_write_pipeline_extras,
)
from pyado.oop.smoke_test._project import (
    _test_project_active_prs,
    _test_project_read,
    _test_write_project_extras,
)
from pyado.oop.smoke_test._pull_request import _test_pr_read, _test_write_pr_complete
from pyado.oop.smoke_test._repository import (
    _test_repository_read,
    _test_write_branch_and_pr,
    _test_write_pr_extra_scenarios,
    _test_write_repo_extras,
)
from pyado.oop.smoke_test._runner import (
    _load_config,
    _print_summary,
    _skip,
    check_oop_coverage,
    console,
    run,
)
from pyado.oop.smoke_test._service import _test_service
from pyado.oop.smoke_test._team import _test_teams_read
from pyado.oop.smoke_test._variable_group import (
    _test_variable_group_read,
    _test_write_variable_group,
)
from pyado.oop.smoke_test._work_item import _test_work_item_read, _test_write_work_item


def main() -> int:
    """Run the OOP smoke test suite and return an exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Skip all write/mutation tests.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for shuffling test variants.",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    check_oop_coverage(pathlib.Path(__file__).parent)
    org_url, project_name, token = _load_config()
    console.print(f"Organisation : {org_url}")
    console.print(f"Project      : {project_name}")
    console.print(f"Write tests  : {'disabled' if args.no_write else 'enabled'}")

    # --- AzureDevOpsService ---
    svc = _test_service(org_url, token)

    # --- Organization ---
    org = svc.org
    _test_organization(org)

    # --- Project ---
    proj = run("org.get_project(name)", lambda: org.get_project(project_name))
    if proj is None:
        console.print("[red]Cannot continue — project lookup failed.[/red]")
        return _print_summary(
            note=(
                "write tests skipped — run without --no-write to include"
                if args.no_write
                else None
            )
        )

    _test_project_read(proj)

    # --- Repository ---
    repo, _ = _test_repository_read(proj, rng)

    # --- PullRequest (read) ---
    existing_pr = None
    if repo:
        existing_pr = _test_pr_read(proj, repo)

    # --- WorkItem (read) ---
    existing_wi = _test_work_item_read(proj)

    # --- Build (read) ---
    build = _test_build_read(proj)

    # --- Pipeline (read) ---
    _test_pipeline_read(proj)

    # --- VariableGroup (read) ---
    vg = _test_variable_group_read(proj)

    # --- Iteration + Area (read) ---
    _test_iteration_area_read(proj)

    # --- Teams (read) ---
    _test_teams_read(proj)

    # --- Project.iter_active_prs() ---
    _test_project_active_prs(proj)

    # --- WRITE TESTS ---
    if not args.no_write:
        _test_write_work_item(proj, repo, build, existing_pr)
        if repo:
            _test_write_branch_and_pr(proj, repo, existing_wi)
            _test_write_repo_extras(repo)
            _test_write_pr_complete(proj, repo)
            _test_write_pr_extra_scenarios(proj, repo)
        if vg:
            _test_write_variable_group(vg)
        if build:
            _test_write_build_tags(build)
        _test_write_project_extras(proj)
        _test_write_pipeline_extras(proj)
    else:
        for label in [
            "proj.create_work_item(Task)",
            "wi.update(title)",
            "wi.add_tag()",
            "wi.remove_tag()",
            "wi.add_comment()",
            "wi.update_comment()",
            "wi.delete_comment()",
            "wi.add_attachment()",
            "wi.get_attachment_bytes(ref)",
            "wi.create_child(Task)",
            "wi.get_child_ids() after create_child",
            "wi.add_link(RELATED)",
            "wi.iter_relations() after add_link",
            "wi.remove_work_item_links(wi2)",
            "wi.link_build()",
            "wi.link_commit()",
            "wi.iter_artifact_links() after link",
            "wi.remove_link(artifact_link)",
            "wi.link_pull_request(existing_pr)",
            "wi.delete()",
            "repo.create_branch()",
            "repo.commit()",
            "repo.create_pull_request()",
            "repo.push_commits()",
            "repo.rename_file()",
            "repo.delete_file()",
            "repo.create_tag()",
            "repo.delete_tag()",
            "pr.update()",
            "pr.add_label()",
            "pr.remove_label()",
            "pr.add_thread()",
            "pr.reply_to_thread()",
            "pr.update_thread_status()",
            "pr.set_status()",
            "pr.link_work_item()",
            "pr.set_work_item_refs()",
            "pr.iter_files_changed()",
            "pr.get_label_details()",
            "pr.sync_labels({'oop-smoke-x'})",
            "pr.sync_labels({}) [clear]",
            "pr.enable_auto_complete(identity_id)",
            "pr.disable_auto_complete()",
            "pr.abandon()",
            "repo.delete_branch()",
            "vg.set_variable()",
            "vg.delete_variable()",
            "build.add_tag()",
            "build.remove_tag()",
            "proj.create_iteration()",
            "iteration.add_to_team(team)",
            "team.add_iteration(iteration_id)",
            "proj.add_team_iteration(team_name, iteration_id)",
            "proj.create_area()",
            "area.patch(name)",
            "proj.create_variable_group()",
            "delete_variable_group() [cleanup]",
            "wi.move(iteration_path=None)",
            "pr.complete(last_merge_source_commit)",
            "repo.create_branch() [for complete]",
            "repo.commit(branch, msg) [for complete]",
            "repo.create_pull_request() [for complete]",
            "pr.add_reviewer(reviewer_id)",
            "pr.vote(reviewer_id, APPROVED)",
            "pr.vote(reviewer_id, NO_VOTE) [reset]",
            "pr.remove_reviewer(reviewer_id)",
            "pipeline.start_run()",
            "pipeline.cancel_run(run_id)",
            "pipeline.authorize_resource(repository)",
            "proj.start_build(definition_id)",
            "build.cancel()",
            "build.cancel_run()",
            "repo.create_branch() [draft scenario]",
            "repo.commit() [draft scenario]",
            "repo.create_pull_request() [draft scenario]",
            "pr.update(is_draft=True)",
            "pr.info.is_draft (True)",
            "pr.update(title=...)",
            "pr.update(is_draft=False)",
            "pr.info.is_draft (False)",
            "pr.abandon() [draft scenario]",
            "repo.delete_branch() [draft scenario]",
            "repo.create_branch() [multi-iter scenario]",
            "repo.commit() iteration 1 [multi-iter scenario]",
            "repo.create_pull_request() [multi-iter scenario]",
            "repo.commit() iteration 2 [multi-iter scenario]",
            "pr.iter_iterations() ≥ 2 [multi-iter scenario]",
            "pr.get_iteration_changes(2) [multi-iter scenario]",
            "pr.abandon() [multi-iter scenario]",
            "repo.delete_branch() [multi-iter scenario]",
            "repo.create_branch() [anchored-thread scenario]",
            "repo.commit() [anchored-thread scenario]",
            "repo.create_pull_request() [anchored-thread scenario]",
            "pr.add_thread(file_path=...) [anchored-thread scenario]",
            "pr.iter_threads() has file-anchored thread",
            "pr.get_thread(id) [anchored-thread scenario]",
            "pr.abandon() [anchored-thread scenario]",
            "repo.delete_branch() [anchored-thread scenario]",
        ]:
            _skip(label, "--no-write")

    return _print_summary(
        note=(
            "write tests skipped — run without --no-write to include"
            if args.no_write
            else None
        )
    )


if __name__ == "__main__":
    sys.exit(main())
