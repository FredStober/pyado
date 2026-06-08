"""Integration tests for process info endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from uuid import UUID

from pyado import raw
from tests.integration.raw._support import console


def test_process_read(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Fetch process template information for the project."""
    console.print("\n=== PROCESS (read) ===")
    project_info = raw.get_project(org_api_call, project_name)
    if (
        project_info
        and project_info.capabilities
        and project_info.capabilities.process_template.template_type_id
    ):
        template_id = UUID(project_info.capabilities.process_template.template_type_id)
        raw.get_process_info(org_api_call, project_api_call, template_id)
