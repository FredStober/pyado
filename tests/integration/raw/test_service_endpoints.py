"""Integration tests for service endpoint endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random
import uuid

from pyado import raw
from tests.integration.raw._support import console


def test_service_endpoint_read(
    project_api_call: raw.ApiCall,
) -> None:
    """List service endpoints."""
    console.print("\n=== SERVICE ENDPOINT (read) ===")
    endpoints = list(raw.iter_service_endpoints(project_api_call))
    assert endpoints == raw.list_service_endpoints(project_api_call)


def test_service_endpoint_get_by_id(
    project_api_call: raw.ApiCall,
) -> None:
    """Get a single service endpoint by ID when at least one exists."""
    endpoints = raw.list_service_endpoints(project_api_call)
    if not endpoints:
        console.print("  skipping get_service_endpoint — no endpoints in project")
        return
    first = endpoints[0]
    console.print(f"\n=== SERVICE ENDPOINT get {first.name} ===")
    fetched = raw.get_service_endpoint(project_api_call, first.id)
    assert fetched.id == first.id
    assert fetched.name == first.name


def test_service_endpoint_write(
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    projects: list[raw.ProjectInfo],
    project_name: str,
    rng: random.Random,
) -> None:
    """Create a minimal service endpoint, update its name, then delete it."""
    del rng
    current_project = next((p for p in projects if p.name == project_name), None)
    if current_project is None:
        console.print("  skipping service endpoint write — project info not available")
        return

    console.print("\n=== SERVICE ENDPOINT (create/update/delete) ===")
    smoke_name = f"_smoke_{uuid.uuid4().hex[:6]}"
    proj_ref = raw.ServiceEndpointProjectReference.model_validate(
        {
            "projectReference": {
                "id": str(current_project.id),
                "name": current_project.name,
            },
            "name": smoke_name,
        }
    )

    new_endpoint = raw.post_service_endpoint(
        org_api_call,
        raw.ServiceEndpointCreateRequest(
            name=smoke_name,
            type="externalnugetfeed",
            url="https://api.nuget.org/v3/index.json",
            authorization=raw.ServiceEndpointAuthorization(
                scheme="Token",
                parameters={"apitoken": "smoke_test_token"},
            ),
            service_endpoint_project_references=[proj_ref],
        ),
    )
    console.print(f"  created: {new_endpoint.name}  id={new_endpoint.id}")

    updated_name = f"{smoke_name}_upd"
    updated_ref = raw.ServiceEndpointProjectReference.model_validate(
        {
            "projectReference": {
                "id": str(current_project.id),
                "name": current_project.name,
            },
            "name": updated_name,
        }
    )
    updated_endpoint = raw.put_service_endpoint(
        org_api_call,
        new_endpoint.id,
        raw.ServiceEndpointUpdateRequest(
            id=new_endpoint.id,
            name=updated_name,
            type="externalnugetfeed",
            url="https://api.nuget.org/v3/index.json",
            authorization=raw.ServiceEndpointAuthorization(
                scheme="Token",
                parameters={"apitoken": "smoke_test_token"},
            ),
            service_endpoint_project_references=[updated_ref],
        ),
    )
    console.print(f"  updated name to: {updated_endpoint.name}")

    # Share with a second project when available
    other_projects = [p for p in projects if p.id != current_project.id]
    if other_projects:
        share_ref = raw.ServiceEndpointProjectReference.model_validate(
            {
                "projectReference": {
                    "id": str(other_projects[0].id),
                    "name": other_projects[0].name,
                },
                "name": updated_name,
            }
        )
        raw.patch_service_endpoint_share(org_api_call, new_endpoint.id, [share_ref])
        console.print(f"  shared with: {other_projects[0].name}")

    raw.delete_service_endpoint(
        project_api_call, new_endpoint.id, [str(current_project.id)]
    )
    console.print("  deleted")
