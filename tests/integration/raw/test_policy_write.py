"""Integration tests for policy write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_policy_write(project_api_call: raw.ApiCall) -> None:
    """Create, update, and delete a policy configuration."""
    console.print("\n=== POLICY (write) ===")
    configs = raw.list_policy_configurations(project_api_call)
    raw.list_policy_types(project_api_call)
    if configs:
        template = configs[0]
        request = raw.PolicyConfigurationRequest(
            is_enabled=False,
            is_blocking=False,
            type=raw.PolicyTypeIdRef(id=template.type.id),
            settings=template.settings,
        )
    else:
        return

    created = raw.post_policy_configuration(project_api_call, request)
    pc_api_call = raw.get_policy_configuration_api_call(project_api_call, created.id)

    raw.get_policy_configuration(pc_api_call)
    raw.put_policy_configuration(pc_api_call, request)
    raw.delete_policy_configuration(pc_api_call)
