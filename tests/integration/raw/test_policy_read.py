"""Integration tests for policy read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_policy_read(project_api_call: raw.ApiCall) -> None:
    """List policy configurations and types."""
    console.print("\n=== POLICY (read) ===")

    configs = list(raw.iter_policy_configurations(project_api_call))
    assert configs == raw.list_policy_configurations(project_api_call)
    policy_types = list(raw.iter_policy_types(project_api_call))
    assert policy_types == raw.list_policy_types(project_api_call)
    if policy_types:
        first_type = policy_types[0]
        raw.get_policy_type(project_api_call, first_type.id)
