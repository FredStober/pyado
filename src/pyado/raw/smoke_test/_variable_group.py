"""Smoke tests for variable group endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import datetime
import random
import uuid

from pyado import raw
from pyado.raw.smoke_test._runner import _DIM, _RESET, _skip, console, run, run_or_skip


def _test_variable_groups_read(
    project_api_call: raw.ApiCall,
) -> list[raw.VariableGroupInfo]:
    console.print("\n=== VARIABLE GROUPS (read) ===")
    groups = run(
        "iter_variable_group_details",
        lambda: raw.list_variable_group_details(project_api_call),
    )
    return groups or []


def _test_variable_group_details_read(
    project_api_call: raw.ApiCall,
    var_groups: list[raw.VariableGroupInfo],
) -> None:
    console.print("\n=== VARIABLE GROUP DETAILS (read) ===")
    if not var_groups:
        _skip("get_variable_group_details", "no variable groups found")
        return
    vg = var_groups[0]
    vg_api = raw.get_variable_group_api_call(project_api_call, vg.id)
    run("get_variable_group_details", lambda: raw.get_variable_group_details(vg_api))


def _test_variable_group_write(
    project_api_call: raw.ApiCall,
    var_group: raw.VariableGroupInfo,
    rng: random.Random,
    project: raw.ProjectInfo | None = None,
) -> None:
    console.print("\n=== VARIABLE GROUP (write) ===")

    vg_api_call = raw.get_variable_group_api_call(project_api_call, var_group.id)
    smoke_key = f"_smoke_{rng.randint(10000, 99999)}"
    original_variables = dict(var_group.variables)
    # _smoke_last_run persists across runs as a record of the last successful
    # smoke test.
    smoke_timestamp_key = "_smoke_last_run"
    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    # If the GET response left variableGroupProjectReferences null, build a
    # minimal reference from the current project so the PUT is accepted.
    proj_refs = var_group.variable_group_refs
    if proj_refs is None and project is not None:
        proj_refs = [
            {
                "projectReference": {"id": str(project.id), "name": project.name},
                "name": var_group.name,
                "description": var_group.description or "",
            }
        ]
        console.print(
            f"  {_DIM}variableGroupProjectReferences was null; "
            f"constructed from project {project.name!r}{_RESET}"
        )

    modified = dict(original_variables)
    modified[smoke_key] = raw.VariableInfo(value="smoke_test")
    modified[smoke_timestamp_key] = raw.VariableInfo(value=timestamp)

    # final_variables = original + timestamp key (smoke_key removed).
    # _smoke_last_run is intentionally left in the variable group after the
    # test as a persistent record of the last successful smoke test run.
    final_variables = dict(original_variables)
    final_variables[smoke_timestamp_key] = raw.VariableInfo(value=timestamp)

    # put_variable_group (raw) — add a smoke variable and update the timestamp
    result = run(
        "put_variable_group [add test var]",
        lambda: raw.put_variable_group(
            vg_api_call,
            raw.VariableGroupUpdateRequest(
                name=var_group.name,
                variables=modified,
                variable_group_project_references=proj_refs,
            ),
        ),
    )
    if result:
        # put_variable_group (raw) — restore + leave timestamp (smoke_key removed)
        run(
            "put_variable_group [restore + timestamp]",
            lambda: raw.put_variable_group(
                vg_api_call,
                raw.VariableGroupUpdateRequest(
                    name=var_group.name,
                    variables=final_variables,
                    variable_group_project_references=proj_refs,
                ),
            ),
        )
    else:
        _skip("put_variable_group [restore + timestamp]", "first put failed")


def _test_variable_group_create_delete(
    project_api_call: raw.ApiCall,
    project: raw.ProjectInfo | None,
    rng: random.Random,
    pipelines: list[raw.PipelineInfo] | None = None,
) -> None:
    del rng
    console.print("\n=== VARIABLE GROUP (create/delete) ===")

    # Use a UUID-based name to avoid collisions with stale VGs from previous
    # runs: the ADO instance used for testing does not support DELETE on the
    # variablegroups endpoint, so stale VGs accumulate and a deterministic
    # (seed-based) name would collide on the second run.
    smoke_vg_name = f"_smoke_{uuid.uuid4().hex[:6]}"
    proj_refs = None
    if project is not None:
        proj_refs = [
            {
                "projectReference": {"id": str(project.id), "name": project.name},
                "name": smoke_vg_name,
                "description": "",
            }
        ]

    new_vg = run(
        "post_variable_group",
        lambda: raw.post_variable_group(
            project_api_call,
            raw.VariableGroupCreateRequest(
                name=smoke_vg_name,
                variables={"_test": raw.VariableInfo(value="smoke")},
                variable_group_project_references=proj_refs,
            ),
        ),
    )
    if new_vg:
        if pipelines:
            run_or_skip(
                "post_pipeline_permission [authorize VG]",
                lambda vg=new_vg, pid=pipelines[0].id: raw.patch_pipeline_permission(
                    project_api_call,
                    raw.PipelineResourceType.VARIABLE_GROUP,
                    str(vg.id),
                    pid,
                    authorized=True,
                ),
                "ADO endpoint rejected method",
            )
        else:
            _skip("post_pipeline_permission [authorize VG]", "no pipelines available")
        vg_api = raw.get_variable_group_api_call(project_api_call, new_vg.id)
        run_or_skip(
            "delete_variable_group",
            lambda: raw.delete_variable_group(vg_api),
            "ADO endpoint rejected method",
        )
    else:
        _skip("post_pipeline_permission [authorize VG]", "post_variable_group failed")
        _skip("delete_variable_group", "post_variable_group failed")
