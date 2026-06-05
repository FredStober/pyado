"""Smoke tests for Project."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

import pyado.raw as _raw
from pyado.oop import Project, VariableGroup
from pyado.oop.smoke_test._runner import _ok, _skip, _take, console, run
from pyado.raw import VariableInfo


def _test_project_read(proj: Project) -> None:
    console.print("\n=== Project (properties & read) ===")
    run("proj.name", lambda: proj.name)
    run("proj.id", lambda: proj.id)
    run("proj.info", lambda: proj.info)
    run("proj.api_call", lambda: proj.api_call)
    run("proj.org (back-nav)", lambda: proj.org)
    run("proj.refresh()", proj.refresh)
    run(
        "proj.iter_pipeline_definitions()",
        lambda: _take(proj.iter_pipeline_definitions(), 5),
    )
    run("proj.list_pipeline_definitions()", proj.list_pipeline_definitions)
    run("proj.get_query_tree()", proj.get_query_tree)
    run("proj.get_iteration_node()", lambda: proj.get_iteration_node(depth=2))
    run("proj.get_area_node()", lambda: proj.get_area_node(depth=2))
    run(
        "proj.iter_pending_approvals()", lambda: _take(proj.iter_pending_approvals(), 3)
    )
    run("proj.list_pending_approvals()", proj.list_pending_approvals)
    run("proj.list_builds()", proj.list_builds)
    run("proj.list_pipelines()", proj.list_pipelines)
    run("proj.list_repositories()", proj.list_repositories)
    run("proj.list_teams()", proj.list_teams)
    run("proj.list_variable_groups()", proj.list_variable_groups)
    repos = proj.list_repositories()
    if repos:
        run(
            "proj.get_repository_by_id(id)",
            lambda rid=repos[0].id: proj.get_repository_by_id(rid),
        )
    teams = proj.list_teams()
    if teams:
        run(
            "proj.get_team_by_id(id)",
            lambda tid=str(teams[0].id): proj.get_team_by_id(tid),
        )
        run(
            "proj.iter_team_sprint_iterations(team_name)",
            lambda tn=teams[0].name: _take(proj.iter_team_sprint_iterations(tn), 5),
        )
        run(
            "proj.list_team_sprint_iterations(team_name)",
            lambda tn=teams[0].name: proj.list_team_sprint_iterations(tn),
        )
    approvals = proj.list_pending_approvals()
    if approvals:
        approval_id = str(approvals[0].id)
        run(
            "proj.approve_pipeline(id)",
            lambda aid=approval_id: proj.approve_pipeline(aid, comment="oop-smoke"),
        )
        if len(approvals) >= 2:
            reject_id = str(approvals[1].id)
            run(
                "proj.reject_pipeline(id)",
                lambda rid=reject_id: proj.reject_pipeline(rid, comment="oop-smoke"),
            )
        else:
            _skip("proj.reject_pipeline(id)", "only one pending approval available")
    else:
        _skip("proj.approve_pipeline(id)", "no pending approvals")
        _skip("proj.reject_pipeline(id)", "no pending approvals")


def _test_project_active_prs(proj: Project) -> None:
    console.print("\n=== Project.iter_active_prs() ===")
    run("proj.iter_active_prs()", lambda: _take(proj.iter_active_prs(), 5))
    run("proj.list_active_prs()", proj.list_active_prs)
    run("proj.list_pull_requests()", proj.list_pull_requests)
    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.Id] DESC"
    )
    run("proj.list_work_items(wiql)", lambda q=wiql: proj.list_work_items(q))


def _test_write_project_extras(proj: Project) -> None:
    """Exercise Project write methods not covered elsewhere."""
    console.print("\n=== Project (write extras) ===")

    # create_iteration and add to team
    smoke_iter_name = f"oop-smoke-iter-{uuid.uuid4().hex[:6]}"
    new_iter = run(
        "proj.create_iteration()",
        lambda: proj.create_iteration(smoke_iter_name),
    )
    # Iteration.add_to_team and Team.add_iteration — use the newly created
    # iteration (which has a UUID identifier) rather than the root node (whose
    # identifier is None and which ADO rejects for team assignment).
    teams = _take(proj.iter_teams(), 1)
    if new_iter and new_iter.info.identifier and teams:
        iter_uuid = uuid.UUID(new_iter.info.identifier)
        run(
            "iteration.add_to_team(team)",
            lambda it=new_iter, t=teams[0]: it.add_to_team(t),
        )
        run(
            "team.add_iteration(iteration_id)",
            lambda t=teams[0], iid=iter_uuid: t.add_iteration(iid),
        )
        run(
            "proj.add_team_iteration(team_name, iteration_id)",
            lambda t=teams[0], iid=iter_uuid: proj.add_team_iteration(t.name, iid),
        )
    else:
        _skip("iteration.add_to_team(team)", "create_iteration returned no identifier")
        _skip(
            "team.add_iteration(iteration_id)",
            "create_iteration returned no identifier",
        )
        _skip(
            "proj.add_team_iteration(team_name, iteration_id)",
            "create_iteration returned no identifier",
        )

    # create_area and Area.patch
    smoke_area_name = f"oop-smoke-area-{uuid.uuid4().hex[:6]}"
    new_area = run(
        "proj.create_area()",
        lambda: proj.create_area(smoke_area_name),
    )
    # Patch the newly created smoke area (guaranteed simple relative path).
    # Patching an existing child area like "Platform" fails because the ADO
    # classification node API requires paths that reference direct children of
    # the project root.
    if new_area:
        run(
            "area.patch(name)",
            lambda a=new_area: a.update(a.name),
        )

    # create_variable_group + delete
    smoke_vg_name = f"oop-smoke-vg-{uuid.uuid4().hex[:6]}"
    new_vg: VariableGroup | None = run(
        "proj.create_variable_group()",
        lambda: proj.create_variable_group(
            smoke_vg_name,
            {"_smoke": VariableInfo(value="value")},
            description="OOP smoke test — safe to delete",
        ),
    )
    if new_vg:
        vg_api = _raw.get_variable_group_api_call(proj.api_call, new_vg.id)
        try:
            _raw.delete_variable_group(vg_api)
            _ok("delete_variable_group() [cleanup]")
        except Exception:
            _skip(
                "delete_variable_group() [cleanup]",
                "ADO endpoint does not support DELETE",
            )
