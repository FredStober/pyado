"""Integration tests for variable group read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_variable_groups_read(
    var_groups: list[raw.VariableGroupInfo],
) -> None:
    """List variable groups.

    The var_groups session fixture calls _test_variable_groups_read.
    This test verifies the call succeeded without error.
    """


def test_variable_group_details_read(
    project_api_call: raw.ApiCall,
    var_groups: list[raw.VariableGroupInfo],
) -> None:
    """Fetch details for the first variable group."""
    console.print("\n=== VARIABLE GROUP DETAILS (read) ===")
    if not var_groups:
        return
    vg = var_groups[0]
    vg_api = raw.get_variable_group_api_call(project_api_call, vg.id)
    raw.get_variable_group_details(vg_api)
