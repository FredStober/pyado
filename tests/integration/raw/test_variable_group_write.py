"""Integration tests for variable group write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import datetime
import random
import uuid

from pyado import raw
from tests.integration.raw._support import console


def test_variable_group_write(
    project_api_call: raw.ApiCall,
    var_groups: list[raw.VariableGroupInfo],
    projects: list[raw.ProjectInfo],
    project_name: str,
    rng: random.Random,
) -> None:
    """Add a smoke variable to an existing group then restore it."""
    if not var_groups:
        return
    vg_for_write = next(
        (g for g in var_groups if g.variable_group_refs is not None),
        var_groups[0],
    )
    current_project = next((p for p in projects if p.name == project_name), None)
    console.print("\n=== VARIABLE GROUP (write) ===")

    var_group = vg_for_write
    project = current_project
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
            raw.VariableGroupProjectReference.model_validate(
                {
                    "projectReference": {"id": str(project.id), "name": project.name},
                    "name": var_group.name,
                    "description": var_group.description or "",
                }
            )
        ]
        console.print(
            f"  variableGroupProjectReferences was null; "
            f"constructed from project {project.name!r}"
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
    result = raw.put_variable_group(
        vg_api_call,
        raw.VariableGroupUpdateRequest(
            name=var_group.name,
            variables=modified,
            variable_group_project_references=proj_refs,
        ),
    )
    if result:
        # put_variable_group (raw) — restore + leave timestamp (smoke_key removed)
        raw.put_variable_group(
            vg_api_call,
            raw.VariableGroupUpdateRequest(
                name=var_group.name,
                variables=final_variables,
                variable_group_project_references=proj_refs,
            ),
        )


def test_variable_group_create_delete(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    projects: list[raw.ProjectInfo],
    project_name: str,
    pipelines: list[raw.PipelineInfo],
    rng: random.Random,
) -> None:
    """Create a new variable group, authorise it for a pipeline, then delete it."""
    current_project = next((p for p in projects if p.name == project_name), None)
    del rng
    console.print("\n=== VARIABLE GROUP (create/delete) ===")

    project = current_project
    smoke_vg_name = f"_smoke_{uuid.uuid4().hex[:6]}"
    proj_refs = None
    if project is not None:
        proj_refs = [
            raw.VariableGroupProjectReference.model_validate(
                {
                    "projectReference": {"id": str(project.id), "name": project.name},
                    "name": smoke_vg_name,
                    "description": "",
                }
            )
        ]

    new_vg = raw.post_variable_group(
        project_api_call,
        raw.VariableGroupCreateRequest(
            name=smoke_vg_name,
            variables={"_test": raw.VariableInfo(value="smoke")},
            variable_group_project_references=proj_refs,
        ),
    )
    if new_vg:
        if pipelines:
            raw.patch_pipeline_permission(
                project_api_call,
                raw.PipelineResourceType.VARIABLE_GROUP,
                str(new_vg.id),
                pipelines[0].id,
                authorized=True,
            )
        if project is not None:
            raw.delete_variable_group(org_api_call, new_vg.id, [str(project.id)])
